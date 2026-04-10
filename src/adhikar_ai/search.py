from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests

from .config import BRAVE_SEARCH_API_KEY, BRAVE_SEARCH_BASE_URL


@dataclass
class SearchResult:
    title: str
    url: str
    description: str


class BraveSearchClient:
    def __init__(self, api_key: str = BRAVE_SEARCH_API_KEY, base_url: str = BRAVE_SEARCH_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def search(self, query: str, count: int = 5) -> list[SearchResult]:
        if not self.enabled:
            return []

        headers = {
            "X-Subscription-Token": self.api_key,
            "Accept": "application/json",
        }
        params = {"q": query, "count": count}
        response = requests.get(self.base_url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = data.get("web", {}).get("results", [])
        output: list[SearchResult] = []
        for item in results[:count]:
            output.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    description=item.get("description", ""),
                )
            )
        return output


def enrich_complaint_context(category: str, location: str) -> list[dict[str, Any]]:
    client = BraveSearchClient()
    if not client.enabled:
        return []

    query = f"{category} civic issue {location} Dhaka"
    results = client.search(query, count=5)
    return [result.__dict__ for result in results]
