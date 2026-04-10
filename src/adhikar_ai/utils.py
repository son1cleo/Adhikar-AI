from __future__ import annotations

import math
import re
from typing import Iterable, List


BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")

KEYWORDS = {
    "Waste": ["waste", "garbage", "trash", "moyla", "ময়লা", "আবর্জনা", "dustbin", "cleaning"],
    "Road": ["road", "street", "pothole", "রাস্তা", "গর্ত", "pavement", "footpath"],
    "Electrical": ["electric", "electrical", "light", "বিদ্যুৎ", "লাইট", "power", "pole"],
    "Water": ["water", "পানি", "drain", "sewer", "pipeline", "লাইন"],
}


def normalize_text(text: str) -> str:
    return text.translate(BANGLA_DIGITS).lower().strip()


def split_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: List[str] = []
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(text_length, start + chunk_size)
        chunks.append(cleaned[start:end])
        if end >= text_length:
            break
        start = max(0, end - overlap)

    return chunks


def extract_duration_hours(text: str | None) -> int | None:
    if not text:
        return None

    normalized = normalize_text(text)
    match = re.search(r"(\d+)\s*(days?|day|দিন)", normalized)
    if match:
        return int(match.group(1)) * 24

    match = re.search(r"(\d+)\s*(hours?|hour|ঘণ্টা|ঘন্টা)", normalized)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*(minutes?|minute|মিনিট)", normalized)
    if match:
        return max(1, math.ceil(int(match.group(1)) / 60))

    return None


def extract_policy_deadline_hours(text: str) -> int | None:
    return extract_duration_hours(text)


def category_keywords(category: str) -> list[str]:
    return KEYWORDS.get(category, [])


def compact_lines(lines: Iterable[str]) -> str:
    return "\n".join(line.strip() for line in lines if line and line.strip())
