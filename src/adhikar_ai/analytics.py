from __future__ import annotations

from collections import Counter

import pandas as pd

from .contacts import load_contacts
from .config import ANALYTICS_FILE, CONTACTS_FILE
from .data import append_analytics, load_analytics


def log_complaint(record: dict) -> None:
    append_analytics(record)


def load_analytics_frame() -> pd.DataFrame:
    records = load_analytics()
    if not records:
        return pd.DataFrame(columns=["location", "category", "recipient_name", "deadline_hours", "user_wait_hours"])
    return pd.DataFrame.from_records(records)


def build_heatmap_frame() -> pd.DataFrame:
    events = load_analytics_frame()
    contacts = load_contacts(CONTACTS_FILE)
    if events.empty or not contacts:
        return pd.DataFrame(columns=["location", "category", "latitude", "longitude", "count"])

    contact_rows = pd.DataFrame([contact.__dict__ for contact in contacts])
    merged = events.merge(contact_rows, left_on="location", right_on="ward", how="left")
    merged["latitude"] = merged["latitude"].fillna(0)
    merged["longitude"] = merged["longitude"].fillna(0)
    merged = merged[merged["latitude"] != 0]
    if merged.empty:
        return pd.DataFrame(columns=["location", "category", "latitude", "longitude", "count"])

    grouped = (
        merged.groupby(["location", "category", "latitude", "longitude"], dropna=False)
        .size()
        .reset_index(name="count")
    )
    return grouped


def category_summary() -> dict[str, int]:
    events = load_analytics_frame()
    if events.empty or "category" not in events:
        return {}
    counts = Counter(events["category"].fillna("Unknown"))
    return dict(counts)
