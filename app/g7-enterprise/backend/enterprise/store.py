"""Enterprise store — users, projects, memberships. SQLite, separate from G6.

Relational entities that are genuinely relational (who belongs to which project
in which role) live here. The immutable review/prediction model stays in the G6
store untouched.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_user (
    user_id    TEXT PRIMARY KEY,
    email      TEXT NOT NULL UNIQUE,
    oidc_sub   TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS project (
    project_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS membership (
    user_id    TEXT NOT NULL,
    project_id TEXT NOT NULL,
    role       TEXT NOT NULL,
    PRIMARY KEY (user_id, project_id),
    FOREIGN KEY (user_id)    REFERENCES app_user(user_id),
    FOREIGN KEY (project_id) REFERENCES project(project_id)
);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else config.ENT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.executescript(_SCHEMA)
    conn.commit()
    return conn


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
def upsert_user(conn: sqlite3.Connection, email: str, oidc_sub: str | None = None) -> dict:
    email = email.strip().lower()
    row = conn.execute("SELECT * FROM app_user WHERE email = ?", (email,)).fetchone()
    if row is not None:
        return dict(row)
    uid = _new_id("usr")
    conn.execute(
        "INSERT INTO app_user(user_id, email, oidc_sub, created_at) VALUES (?,?,?,?)",
        (uid, email, oidc_sub, utc_now()),
    )
    conn.commit()
    return {"user_id": uid, "email": email, "oidc_sub": oidc_sub}


def get_user_by_email(conn: sqlite3.Connection, email: str) -> dict | None:
    row = conn.execute("SELECT * FROM app_user WHERE email = ?", (email.strip().lower(),)).fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Projects + membership
# ---------------------------------------------------------------------------
def create_project(conn: sqlite3.Connection, name: str, created_by: str) -> dict:
    pid = _new_id("prj")
    conn.execute(
        "INSERT INTO project(project_id, name, created_by, created_at) VALUES (?,?,?,?)",
        (pid, name, created_by, utc_now()),
    )
    conn.commit()
    return {"project_id": pid, "name": name, "created_by": created_by}


def add_membership(conn: sqlite3.Connection, user_id: str, project_id: str, role: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO membership(user_id, project_id, role) VALUES (?,?,?)",
        (user_id, project_id, role),
    )
    conn.commit()


def memberships_for_user(conn: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT m.project_id, m.role, p.name "
        "FROM membership m JOIN project p ON p.project_id = m.project_id "
        "WHERE m.user_id = ? ORDER BY p.name",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def role_in_project(conn: sqlite3.Connection, user_id: str, project_id: str) -> str | None:
    row = conn.execute(
        "SELECT role FROM membership WHERE user_id = ? AND project_id = ?",
        (user_id, project_id),
    ).fetchone()
    return row["role"] if row else None
