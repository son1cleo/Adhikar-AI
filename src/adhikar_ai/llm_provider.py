from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from .config import GROQ_API_KEY, GROQ_BASE_URL, GROQ_MODEL


@dataclass
class LLMResponse:
    text: str
    raw: dict[str, Any] | None = None


class GroqClient:
    def __init__(self, api_key: str = GROQ_API_KEY, model: str = GROQ_MODEL, base_url: str = GROQ_BASE_URL):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.1, max_tokens: int = 800) -> LLMResponse:
        if not self.enabled:
            return LLMResponse(text="")

        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        text = data["choices"][0]["message"]["content"]
        return LLMResponse(text=text, raw=data)

    def json_completion(self, messages: list[dict[str, str]], fallback: dict[str, Any] | None = None) -> dict[str, Any]:
        fallback = fallback or {}
        response = self.chat(messages, temperature=0.0)
        content = response.text.strip()
        if content.startswith("```"):
            content = content.strip("`")
            content = content.removeprefix("json").strip()
        try:
            return json.loads(content)
        except Exception:
            return fallback


def get_llm_client() -> GroqClient:
    return GroqClient()
