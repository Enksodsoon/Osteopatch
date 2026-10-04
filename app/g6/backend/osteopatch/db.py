"""SQLite connection + migration runner.

The schema and migration SQL live under this package (durable, in-project); the
database file itself lives under scratch (runtime data, out of git). Migrations
are applied idempotently and recorded in ``schema_migrations``.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else config.DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _applied_versions(conn: sqlite3.Connection) -> set[int]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations "
        "(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    return {r[0] for r in conn.execute("SELECT version FROM schema_migrations")}


def run_migrations(conn: sqlite3.Connection) -> list[int]:
    """Apply every unapplied *.sql migration in version order. Returns applied."""
    applied = _applied_versions(conn)
    newly: list[int] = []
    for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(sql_file.name.split("_", 1)[0])
        if version in applied:
            continue
        conn.executescript(sql_file.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (version, utc_now()),
        )
        conn.commit()
        newly.append(version)
    return newly
