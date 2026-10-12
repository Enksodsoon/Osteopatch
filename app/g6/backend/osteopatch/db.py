"""SQLite connection + migration runner.

The schema and migration SQL live under this package (durable, in-project); the
database file itself lives under scratch (runtime data, out of git). Migrations
are applied idempotently and recorded in ``schema_migrations``.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from . import config

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

# Startup migration bookkeeping. F007: migrations run once per DATABASE, not
# once per worker thread, and a failed run is never recorded as done.
_MIGRATION_LOCK = threading.Lock()
_MIGRATED: set[str] = set()


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


def initialize(conn: sqlite3.Connection, db_path: Path | str | None = None) -> list[int]:
    """Bring one database to head, at most once per process, under a lock.

    Returns the migration versions applied by THIS call (empty when another
    thread already initialized the same database). The database is recorded as
    migrated only after ``run_migrations`` returns, so a failed initialization
    is retried by the next caller instead of leaving a half-built schema behind
    a cached "done" marker.

    Keyed by resolved path, so a test (or a second store) that points
    ``DB_PATH`` at a new file still gets its own migrations.
    """
    key = str(Path(db_path if db_path is not None else config.DB_PATH).resolve())
    with _MIGRATION_LOCK:
        if key in _MIGRATED:
            return []
        applied = run_migrations(conn)
        _MIGRATED.add(key)
        return applied


def close(conn: sqlite3.Connection) -> None:
    """Release a connection: end any open transaction, then close the handle.

    Idempotent — SQLite treats a second ``close()`` as a no-op. Used by the
    bounded request lifecycle so a transaction a handler left open is rolled
    back instead of being inherited by the next request on the same thread.
    """
    try:
        if conn.in_transaction:
            conn.rollback()
    except sqlite3.ProgrammingError:
        pass  # already closed - nothing of ours is still open
    except sqlite3.Error as exc:
        # Report, do not hide: a caller must never read a silent rollback
        # failure as a clean release of an uncommitted write.
        print(f"[db] rollback before close failed: {exc}")
    finally:
        conn.close()


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

    _post_migrate(conn)
    return newly


def _post_migrate(conn: sqlite3.Connection) -> None:
    """Idempotent data work that belongs after the schema is in place.

    The legacy project backfill lives here rather than in SQL so the default
    project id is defined once, in ``projects.DEFAULT_PROJECT_ID``, instead of
    being hardcoded into a migration file.

    Deliberately NOT gated on "this call applied a migration". A database that
    already recorded the migration but was interrupted before the backfill — or
    one whose rows were added before the column existed — would otherwise be
    skipped forever, leaving rows permanently unscoped.
    """
    applied = _applied_versions(conn)
    if 2 not in applied:
        return
    from . import projects

    rows = projects.assign_legacy_project(conn)
    if rows:
        print(f"[db] backfilled project scope on {rows} pre-existing rows")
