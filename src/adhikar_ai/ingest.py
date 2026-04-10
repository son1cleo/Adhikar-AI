from __future__ import annotations

import argparse
import importlib
from pathlib import Path

def _fallback_splitter_class():
    class RecursiveCharacterTextSplitter:  # minimal fallback
        def __init__(self, chunk_size: int, chunk_overlap: int, separators: list[str]):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.separators = separators

        def split_text(self, text: str) -> list[str]:
            if not text.strip():
                return []
            pieces = []
            for block in text.split("।"):
                block = block.strip()
                if block:
                    pieces.append(block + "।")

            chunks: list[str] = []
            current = ""
            for piece in pieces:
                candidate = (current + " " + piece).strip() if current else piece
                if len(candidate) <= self.chunk_size:
                    current = candidate
                else:
                    if current:
                        chunks.append(current)
                    current = piece
            if current:
                chunks.append(current)

            if self.chunk_overlap <= 0 or len(chunks) <= 1:
                return chunks

            overlapped: list[str] = []
            for idx, chunk in enumerate(chunks):
                if idx == 0:
                    overlapped.append(chunk)
                    continue
                prefix = chunks[idx - 1][-self.chunk_overlap :]
                overlapped.append((prefix + " " + chunk).strip())
            return overlapped

    return RecursiveCharacterTextSplitter


def _load_recursive_splitter():
    for module_name in ("langchain_text_splitters", "langchain.text_splitter"):
        try:
            module = importlib.import_module(module_name)
            cls = getattr(module, "RecursiveCharacterTextSplitter", None)
            if cls is not None:
                return cls
        except Exception:
            continue
    return _fallback_splitter_class()


RecursiveCharacterTextSplitter = _load_recursive_splitter()

from .data import load_charter_files, rebuild_collection
from .config import CHARTER_DIR


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the citizen charter Chroma collection")
    parser.add_argument(
        "--charter-dir",
        type=Path,
        default=CHARTER_DIR,
        help="Directory containing DNCC and DSCC charter PDFs or text files",
    )
    args = parser.parse_args()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", "।", ".", " ", ""],
    )
    chunks = load_charter_files(args.charter_dir, text_splitter=splitter)
    if not chunks:
        raise SystemExit(f"No charter documents found in {args.charter_dir}")
    count = rebuild_collection(chunks)
    print(f"Indexed {count} charter chunks.")


if __name__ == "__main__":
    main()
