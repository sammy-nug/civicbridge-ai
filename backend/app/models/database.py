"""SQLite storage for operational records and feedback.

Deliberately excluded: question text, answers, IP addresses and session ids. `responses` holds
only what is needed to link feedback to a response and to measure quality in aggregate.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS responses (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, language TEXT NOT NULL,
    outcome TEXT NOT NULL, latency_ms INTEGER NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT, response_id TEXT NOT NULL REFERENCES responses(id),
    rating TEXT NOT NULL, comment TEXT, created_at TEXT NOT NULL
);
"""


@contextmanager
def _connection():
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(settings.data_dir / "civicbridge.sqlite3")
    try:
        connection.executescript(SCHEMA)
        yield connection
        connection.commit()
    finally:
        connection.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_response(response_id: str, kind: str, language: str, outcome: str, latency_ms: int) -> None:
    with _connection() as db:
        db.execute("INSERT INTO responses VALUES (?, ?, ?, ?, ?, ?)", (response_id, kind, language, outcome, latency_ms, _now()))


def record_feedback(response_id: str, rating: str, comment: str | None) -> bool:
    """Store feedback. Returns False if the response id is unknown."""
    with _connection() as db:
        if db.execute("SELECT 1 FROM responses WHERE id = ?", (response_id,)).fetchone() is None:
            return False
        db.execute(
            "INSERT INTO feedback (response_id, rating, comment, created_at) VALUES (?, ?, ?, ?)",
            (response_id, rating, comment, _now()),
        )
    return True
