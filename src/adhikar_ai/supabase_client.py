from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests

from .config import SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL


@dataclass
class SupabaseUser:
    id: str
    email: str
    name: str


class SupabaseStore:
    def __init__(self, url: str = SUPABASE_URL, service_role_key: str = SUPABASE_SERVICE_ROLE_KEY):
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.service_role_key)

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }

    def _request(self, method: str, path: str, params: dict[str, str] | None = None, payload: Any | None = None):
        if not self.enabled:
            return None
        response = requests.request(
            method,
            f"{self.url}/rest/v1/{path.lstrip('/')}",
            headers=self._headers(),
            params=params,
            data=json.dumps(payload) if payload is not None else None,
            timeout=30,
        )
        response.raise_for_status()
        if response.text:
            return response.json()
        return None

    def upsert_user(self, name: str, email: str) -> SupabaseUser | None:
        if not self.enabled:
            return None
        rows = self._request(
            "POST",
            "users",
            params={"on_conflict": "email"},
            payload={"name": name, "email": email},
        )
        if isinstance(rows, list) and rows:
            row = rows[0]
            return SupabaseUser(id=row["id"], email=row["email"], name=row["name"])
        return None

    def create_session(self, user_id: str) -> str | None:
        if not self.enabled:
            return None
        rows = self._request("POST", "chat_sessions", payload={"user_id": user_id})
        if isinstance(rows, list) and rows:
            return rows[0]["id"]
        return None

    def insert_message(self, session_id: str, role: str, content: str) -> None:
        if not self.enabled:
            return
        self._request("POST", "chat_messages", payload={"session_id": session_id, "role": role, "content": content})

    def fetch_messages(self, session_id: str) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        rows = self._request(
            "GET",
            "chat_messages",
            params={"session_id": f"eq.{session_id}", "order": "timestamp.asc"},
        )
        return rows if isinstance(rows, list) else []

    def insert_policy_violation(self, record: dict[str, Any]) -> None:
        if not self.enabled:
            return
        self._request("POST", "policy_violations", payload=record)


supabase_store = SupabaseStore()
