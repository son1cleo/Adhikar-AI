from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

from pypdf import PdfReader

from .config import ANALYTICS_FILE, CHROMA_DIR, COLLECTION_NAME, CHARTER_DIR
from .models import PolicyChunk
from .utils import compact_lines, split_text


def read_document(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return compact_lines(pages)
    return path.read_text(encoding="utf-8")


def load_charter_files(
    charter_dir: Path = CHARTER_DIR,
    text_splitter=None,
) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []
    if not charter_dir.exists():
        return chunks

    for path in sorted(charter_dir.iterdir()):
        if path.suffix.lower() not in {".pdf", ".txt", ".md"}:
            continue
        content = read_document(path)
        if text_splitter is not None:
            split_chunks = text_splitter.split_text(content)
        else:
            split_chunks = split_text(content, chunk_size=1000, overlap=200)
        for index, chunk in enumerate(split_chunks):
            chunks.append(
                PolicyChunk(
                    text=chunk,
                    source=f"{path.name}#chunk-{index + 1}",
                    category=detect_policy_category(chunk),
                )
            )
    return chunks


def detect_policy_category(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ["garbage", "waste", "moyla", "আবর্জনা", "ময়লা"]):
        return "Waste"
    if any(token in lowered for token in ["road", "street", "pothole", "রাস্তা", "গর্ত"]):
        return "Road"
    if any(token in lowered for token in ["electric", "light", "বিদ্যুৎ", "পাওয়ার", "power"]):
        return "Electrical"
    if any(token in lowered for token in ["water", "পানি", "sewer", "drain"]):
        return "Water"
    return "General"


def ensure_analytics_store() -> None:
    ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)


def append_analytics(record: dict) -> None:
    ensure_analytics_store()
    with ANALYTICS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def load_analytics() -> list[dict]:
    if not ANALYTICS_FILE.exists():
        return []
    records: list[dict] = []
    with ANALYTICS_FILE.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class HashEmbeddingFunction:
    def __init__(self, dimensions: int = 64):
        self.dimensions = dimensions

    def name(self) -> str:
        return "hash_embedding"

    def __call__(self, input):  # chromadb expects this signature
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        normalized = (text or "").lower()
        for index in range(max(1, len(normalized) - 2)):
            gram = normalized[index : index + 3]
            digest = hashlib.sha256(gram.encode("utf-8")).hexdigest()
            bucket = int(digest[:8], 16) % self.dimensions
            vector[bucket] += 1.0
        norm = sum(value * value for value in vector) ** 0.5 or 1.0
        return [value / norm for value in vector]


def get_collection():
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=HashEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )


def rebuild_collection(chunks: Iterable[PolicyChunk]) -> int:
    collection = get_collection()
    try:
        existing = collection.get(include=[])
        if existing.get("ids"):
            collection.delete(ids=existing["ids"])
    except Exception:
        pass

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict] = []
    for index, chunk in enumerate(chunks):
        ids.append(f"chunk-{index}")
        documents.append(chunk.text)
        metadatas.append({"source": chunk.source, "category": chunk.category})

    if ids:
        collection.add(ids=ids, documents=documents, metadatas=metadatas)
    return len(ids)


def query_collection(category: str, query_text: str, limit: int = 3) -> list[PolicyChunk]:
    collection = get_collection()
    search_query = f"{category} {query_text} {' '.join(_keywords_for_category(category))}"
    try:
        response = collection.query(
            query_texts=[search_query],
            n_results=limit,
            where={"category": category},
        )
    except Exception:
        return keyword_fallback(category, query_text, limit=limit)

    chunks: list[PolicyChunk] = []
    documents = response.get("documents", [[]])[0]
    metadatas = response.get("metadatas", [[]])[0]
    distances = response.get("distances", [[]])[0]
    for document, metadata, distance in zip(documents, metadatas, distances):
        chunks.append(
            PolicyChunk(
                text=document,
                source=metadata.get("source", "unknown"),
                category=metadata.get("category", category),
                score=max(0.0, 1.0 - float(distance or 0.0)),
            )
        )

    if chunks:
        return chunks

    return keyword_fallback(category, query_text, limit=limit)


def keyword_fallback(category: str, query_text: str, limit: int = 3) -> list[PolicyChunk]:
    chunks = load_charter_files()
    keywords = [keyword.lower() for keyword in _keywords_for_category(category)]
    ranked: list[PolicyChunk] = []
    for chunk in chunks:
        haystack = f"{chunk.text} {query_text}".lower()
        score = sum(1 for keyword in keywords if keyword in haystack)
        if score:
            ranked.append(PolicyChunk(text=chunk.text, source=chunk.source, category=chunk.category, score=float(score)))
    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:limit]


def _keywords_for_category(category: str) -> list[str]:
    lookup = {
        "Waste": ["ময়লা", "আবর্জনা", "garbage", "waste", "48 hours", "৪৮ ঘণ্টা"],
        "Road": ["রাস্তা", "পথ", "road", "pothole"],
        "Electrical": ["বিদ্যুৎ", "electric", "light", "power"],
        "Water": ["পানি", "water", "drain", "sewer"],
    }
    return lookup.get(category, [])
