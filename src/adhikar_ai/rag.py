from __future__ import annotations

from dataclasses import asdict

from .data import query_collection
from .models import PolicyChunk


def retrieve_policy(category: str, user_text: str, limit: int = 3) -> list[PolicyChunk]:
    return query_collection(category, user_text, limit=limit)


def policy_text(chunks: list[PolicyChunk]) -> str:
    if not chunks:
        return "No matching charter text was found."
    return "\n\n".join(f"Source: {chunk.source}\n{chunk.text}" for chunk in chunks)


def top_policy(chunks: list[PolicyChunk]) -> PolicyChunk | None:
    return sorted(chunks, key=lambda item: item.score, reverse=True)[0] if chunks else None
