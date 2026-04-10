from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CHARTER_DIR = DATA_DIR / "charters"
CONTACTS_FILE = DATA_DIR / "contacts" / "dncc_officers_sample.csv"
ANALYTICS_DIR = DATA_DIR / "analytics"
ANALYTICS_FILE = ANALYTICS_DIR / "complaints.jsonl"
CHROMA_DIR = DATA_DIR / ".chroma"
COLLECTION_NAME = "citizen_charters"

DEFAULT_MODEL_PROVIDER = "local"
DEFAULT_MAX_RESULTS = 3


def _env(name: str, default: str = "") -> str:
	return os.getenv(name, default).strip()


GROQ_API_KEY = _env("GROQ_API_KEY")
GROQ_MODEL = _env("GROQ_MODEL", "llama-3.1-70b-versatile")
GROQ_BASE_URL = _env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

BRAVE_SEARCH_API_KEY = _env("BRAVE_SEARCH_API_KEY")
BRAVE_SEARCH_BASE_URL = _env("BRAVE_SEARCH_BASE_URL", "https://api.search.brave.com/res/v1/web/search")

SUPABASE_URL = _env("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")
SUPABASE_ANON_KEY = _env("SUPABASE_ANON_KEY")

SMTP_HOST = _env("SMTP_HOST")
SMTP_PORT = int(_env("SMTP_PORT", "587"))
SMTP_USERNAME = _env("SMTP_USERNAME")
SMTP_PASSWORD = _env("SMTP_PASSWORD")
EMAIL_FROM_ADDRESS = _env("EMAIL_FROM_ADDRESS")
