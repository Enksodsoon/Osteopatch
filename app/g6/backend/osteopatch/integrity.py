"""Proving the frozen corpus is untouched.

The live-inference feature writes to its own tables. The reason that is safe is
that ``source_qc``, ``prediction`` and ``review_event`` are never written by it
— but "we don't write them" is a claim about code, and code changes.

:func:`corpus_row_digest` turns that claim into a value you can take before a
run and compare after it. It hashes the CONTENTS of the frozen tables in a
deterministic order, so:

  * any changed score, label, hash, id or timestamp changes the digest;
  * a changed row COUNT changes the digest;
  * reordering rows, or an unrelated write to a ``live_*`` table, does not.

This is deliberately row-content rather than file-content. A SQLite file's
bytes move for reasons that have nothing to do with the data — WAL checkpoints,
page reuse, a new table's pages — so a file hash would flag every write
anywhere in the database as corruption. It is also stricter where it matters:
it cannot be satisfied by a byte-identical file that somehow lost a row, and it
cannot be defeated by a rewrite that preserves length.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

#: The tables the frozen G4 contract covers. Anything live-related is excluded
#: on purpose: those tables are SUPPOSED to change when the app is used.
FROZEN_TABLES = ("source_qc", "prediction", "review_event")


def _rows(conn: sqlite3.Connection, table: str) -> list[dict]:
    """Every row of ``table`` as a dict, in primary-key order.

    Primary-key order (not insertion order) so the digest is stable across a
    VACUUM or a rebuild. Missing columns are impossible here: a table that
    failed to migrate would raise, which is the correct outcome.
    """
    columns = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]  # noqa: S608
    order = columns[0] if columns else "rowid"
    cursor = conn.execute(f"SELECT * FROM {table} ORDER BY {order}")  # noqa: S608
    return [dict(zip(columns, values)) for values in cursor]


def corpus_row_digest(conn: sqlite3.Connection, tables=FROZEN_TABLES) -> dict:
    """Content digest of the frozen corpus.

    Returns ``{"digest": "<sha256>", "tables": {<table>: <row_count>}}`` so a
    caller can tell "the data changed" from "the table is gone".
    """
    parts: list[str] = []
    counts: dict[str, int] = {}
    for table in tables:
        rows = _rows(conn, table)
        counts[table] = len(rows)
        parts.append(table)
        for row in rows:
            # sort_keys so dict ordering in the caller cannot move the digest
            parts.append(json.dumps(row, sort_keys=True, default=str))
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()
    return {"digest": digest, "tables": counts}


def assert_corpus_unchanged(before: dict, after: dict) -> None:
    """Raise when a live-inference run altered the frozen corpus.

    Used by the verification script so a mutation is a loud failure rather than
    a detail buried in a JSON evidence file.
    """
    if before == after:
        return
    changed = [t for t in before.get("tables", {}) if before["tables"][t] != after.get("tables", {}).get(t)]
    raise AssertionError(
        "the frozen corpus changed during a live-inference run: "
        f"digest {before.get('digest')} -> {after.get('digest')}; "
        f"row counts changed for {changed or 'unknown'}"
    )
