"""E4 — Human-in-the-loop governance (REAL, local, no AWS).

Three capabilities, all backed by the enterprise SQLite store:

1. Adjudication — a pathologist resolves a reviewer disagreement on a patch.
   Append-only; the model prediction and the reviewer's event are never mutated.
2. Batch sign-off — lock a set of reviewed images into an immutable, snapshotted
   batch (hash over the member image_ids + resolved states).
3. Correction store — CAPTURE corrections for a future, separately-approved
   retraining decision. It never auto-feeds training (hard non-goal).

Governance rows live in the enterprise DB (separate from the G6 review store);
the G6 immutable review/prediction model is untouched.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone

from . import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS adjudication (
    adjudication_id TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    image_id        TEXT NOT NULL,
    resolver        TEXT NOT NULL,
    resolved_label  TEXT NOT NULL,
    rationale       TEXT,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS signoff_batch (
    batch_id    TEXT PRIMARY KEY,
    project_id  TEXT NOT NULL,
    signed_by   TEXT NOT NULL,
    image_ids   TEXT NOT NULL,          -- JSON array, frozen at sign-off
    content_sha TEXT NOT NULL,          -- hash of sorted image_ids + states
    created_at  TEXT NOT NULL,
    locked      INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS correction_capture (
    capture_id   TEXT PRIMARY KEY,
    project_id   TEXT NOT NULL,
    image_id     TEXT NOT NULL,
    from_label   TEXT NOT NULL,         -- model predicted class
    to_label     TEXT NOT NULL,         -- human corrected class
    captured_by  TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    consumed_by_training INTEGER NOT NULL DEFAULT 0  -- stays 0: capture-only
);
"""


class GovernanceError(Exception):
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _nid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# 1. Adjudication
# ---------------------------------------------------------------------------
def adjudicate(conn, *, project_id: str, image_id: str, resolver: str,
               resolved_label: str, rationale: str | None = None) -> dict:
    ensure_schema(conn)
    if resolved_label not in config_canonical():
        raise GovernanceError(f"resolved_label must be one of {config_canonical()}")
    aid = _nid("adj")
    conn.execute(
        "INSERT INTO adjudication(adjudication_id, project_id, image_id, resolver, "
        "resolved_label, rationale, created_at) VALUES (?,?,?,?,?,?,?)",
        (aid, project_id, image_id, resolver, resolved_label, rationale, _now()),
    )
    conn.commit()
    return {"adjudication_id": aid, "image_id": image_id, "resolved_label": resolved_label,
            "resolver": resolver}


def adjudication_history(conn, project_id: str, image_id: str) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT * FROM adjudication WHERE project_id=? AND image_id=? ORDER BY created_at",
        (project_id, image_id),
    ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# 2. Batch sign-off
# ---------------------------------------------------------------------------
def sign_off_batch(conn, *, project_id: str, signed_by: str,
                   image_ids: list[str], states: dict[str, str]) -> dict:
    """Freeze a reviewed batch. `states` maps image_id -> resolved state string.
    content_sha is a hash over the sorted (image_id, state) pairs so the batch is
    tamper-evident."""
    ensure_schema(conn)
    if not image_ids:
        raise GovernanceError("cannot sign off an empty batch")
    ordered = sorted(set(image_ids))
    payload = json.dumps([[i, states.get(i, "")] for i in ordered], separators=(",", ":"))
    content_sha = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    bid = _nid("batch")
    conn.execute(
        "INSERT INTO signoff_batch(batch_id, project_id, signed_by, image_ids, "
        "content_sha, created_at, locked) VALUES (?,?,?,?,?,?,1)",
        (bid, project_id, signed_by, json.dumps(ordered), content_sha, _now()),
    )
    conn.commit()
    return {"batch_id": bid, "project_id": project_id, "signed_by": signed_by,
            "image_count": len(ordered), "content_sha": content_sha, "locked": True}


def get_batch(conn, batch_id: str) -> dict | None:
    ensure_schema(conn)
    r = conn.execute("SELECT * FROM signoff_batch WHERE batch_id=?", (batch_id,)).fetchone()
    if r is None:
        return None
    d = dict(r)
    d["image_ids"] = json.loads(d["image_ids"])
    d["locked"] = bool(d["locked"])
    return d


# ---------------------------------------------------------------------------
# 3. Correction store (capture-only)
# ---------------------------------------------------------------------------
def capture_correction(conn, *, project_id: str, image_id: str, from_label: str,
                       to_label: str, captured_by: str) -> dict:
    """Record a human correction for POSSIBLE future retraining. It is never
    auto-consumed: consumed_by_training stays 0 and there is no code path that
    feeds this into training (hard non-goal)."""
    ensure_schema(conn)
    canon = config_canonical()
    if from_label not in canon or to_label not in canon:
        raise GovernanceError(f"labels must be in {canon}")
    cid = _nid("corr")
    conn.execute(
        "INSERT INTO correction_capture(capture_id, project_id, image_id, from_label, "
        "to_label, captured_by, created_at, consumed_by_training) VALUES (?,?,?,?,?,?,?,0)",
        (cid, project_id, image_id, from_label, to_label, captured_by, _now()),
    )
    conn.commit()
    return {"capture_id": cid, "image_id": image_id, "from_label": from_label,
            "to_label": to_label, "consumed_by_training": False}


def correction_store(conn, project_id: str) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT * FROM correction_capture WHERE project_id=? ORDER BY created_at",
        (project_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def config_canonical() -> tuple[str, ...]:
    """Canonical 3-class order. Mirrors the frozen G6/G4 contract; kept local so
    E4 does not hard-depend on the G6 package being importable."""
    return ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")
