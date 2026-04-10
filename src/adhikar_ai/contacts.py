from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from .models import ContactRecord
from .utils import normalize_text


def load_contacts(path: Path) -> list[ContactRecord]:
    if not path.exists():
        return []

    records: list[ContactRecord] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            records.append(
                ContactRecord(
                    ward=row.get("ward", "").strip(),
                    neighborhood=row.get("neighborhood", "").strip(),
                    councillor=row.get("councillor", "").strip(),
                    zonal_executive=row.get("zonal_executive", "").strip(),
                    email=row.get("email", "").strip(),
                    phone=row.get("phone", "").strip(),
                    latitude=float(row.get("latitude", 0) or 0),
                    longitude=float(row.get("longitude", 0) or 0),
                )
            )
    return records


def find_contact(location: str, contacts: Iterable[ContactRecord]) -> ContactRecord | None:
    normalized_location = normalize_text(location)
    for contact in contacts:
        if normalized_location in normalize_text(contact.ward) or normalized_location in normalize_text(contact.neighborhood):
            return contact

    contacts_list = list(contacts)
    return contacts_list[0] if contacts_list else None


def contact_to_dict(contact: ContactRecord | None) -> dict:
    return asdict(contact) if contact else {}
