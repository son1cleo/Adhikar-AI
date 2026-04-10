from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ANALYTICS_DIR

DB_PATH = ANALYTICS_DIR / "policy_violations.db"


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS policy_violations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    category TEXT NOT NULL,
    location TEXT NOT NULL,
    ward TEXT,
    neighborhood TEXT,
    area_code TEXT,
    consistency_status TEXT,
    severity_flag TEXT,
    policy_deadline_hours INTEGER,
    user_duration_hours INTEGER,
    policy_vs_reality_gap_hours INTEGER,
    is_violation INTEGER NOT NULL,
    session_id TEXT,
    user_id TEXT,
    recipient_name TEXT,
    recipient_email TEXT,
    complaint_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    user_id TEXT,
    recipient_email TEXT,
    recipient_name TEXT,
    sent_at TEXT,
    status TEXT,
    complaint_json TEXT NOT NULL
);
"""


def _connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_policy_violation_table() -> None:
    with _connect() as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_columns(conn, "policy_violations", {
            "area_code": "TEXT",
            "consistency_status": "TEXT",
            "severity_flag": "TEXT",
            "policy_vs_reality_gap_hours": "INTEGER",
            "session_id": "TEXT",
            "user_id": "TEXT",
            "recipient_name": "TEXT",
            "recipient_email": "TEXT",
        })
        _ensure_columns(conn, "email_logs", {
            "session_id": "TEXT",
            "user_id": "TEXT",
            "recipient_email": "TEXT",
            "recipient_name": "TEXT",
            "sent_at": "TEXT",
            "status": "TEXT",
        })
        conn.commit()


def _ensure_columns(conn: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    for column_name, column_type in columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")


def insert_policy_violation(payload: dict[str, Any]) -> int:
    ensure_policy_violation_table()

    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO policy_violations (
                created_at,
                category,
                location,
                ward,
                neighborhood,
                area_code,
                consistency_status,
                severity_flag,
                policy_deadline_hours,
                user_duration_hours,
                policy_vs_reality_gap_hours,
                is_violation,
                session_id,
                user_id,
                recipient_name,
                recipient_email,
                complaint_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                payload.get("category", "Unknown"),
                payload.get("location", ""),
                payload.get("ward"),
                payload.get("neighborhood"),
                payload.get("area_code"),
                payload.get("consistency_status"),
                payload.get("severity_flag"),
                payload.get("policy_deadline_hours"),
                payload.get("user_duration_hours"),
                payload.get("policy_vs_reality_gap_hours"),
                1 if payload.get("is_violation") else 0,
                payload.get("session_id"),
                payload.get("user_id"),
                payload.get("recipient_name"),
                payload.get("recipient_email"),
                json.dumps(payload.get("complaint_json", {}), ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def insert_email_log(payload: dict[str, Any]) -> int:
    ensure_policy_violation_table()
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO email_logs (
                session_id,
                user_id,
                recipient_email,
                recipient_name,
                sent_at,
                status,
                complaint_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("session_id"),
                payload.get("user_id"),
                payload.get("recipient_email"),
                payload.get("recipient_name"),
                datetime.now(timezone.utc).isoformat(),
                payload.get("status", "draft"),
                json.dumps(payload.get("complaint_json", {}), ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def ward_violation_counts() -> list[dict[str, Any]]:
    ensure_policy_violation_table()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(ward, ''), location) AS ward,
                COUNT(*) AS total_violations
            FROM policy_violations
            WHERE is_violation = 1
            GROUP BY COALESCE(NULLIF(ward, ''), location)
            ORDER BY total_violations DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def violation_map_points() -> list[dict[str, Any]]:
    ensure_policy_violation_table()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT
                COALESCE(NULLIF(ward, ''), location) AS ward,
                COUNT(*) AS total_violations
            FROM policy_violations
            WHERE is_violation = 1
            GROUP BY COALESCE(NULLIF(ward, ''), location)
            """
        ).fetchall()
    return [dict(row) for row in rows]


def list_policy_violations(limit: int = 200) -> list[dict[str, Any]]:
    ensure_policy_violation_table()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM policy_violations
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]
