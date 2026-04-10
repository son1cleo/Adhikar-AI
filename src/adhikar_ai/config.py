from __future__ import annotations

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
