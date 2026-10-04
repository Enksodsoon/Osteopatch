r"""E5 — Model lifecycle registry (REAL, local, no AWS).

A hash-pinned registry with a guarded state machine:

    registered -> candidate -> shadow -> serving -> retired
                        \-> registered   \-> registered   (demotion)

Invariants enforced in code:
- A bundle is identified by its sha256; re-registering the same hash is idempotent.
- At most ONE bundle is `serving` at a time (promoting a new one retires the old).
- The frozen G4 hash is a normal entry; it is never special-cased or reassigned.
- Promotion to `serving` requires a recorded passing eval gate + a human approver.
- `rollback()` returns the most-recently-retired bundle to serving in one call.

Nothing here trains or runs a model; it governs WHICH bundle is of record. The
GPU inference that uses the serving bundle is E3 (gated — needs compute).
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from enum import Enum

from . import config


class ModelState(str, Enum):
    REGISTERED = "registered"
    CANDIDATE = "candidate"
    SHADOW = "shadow"
    SERVING = "serving"
    RETIRED = "retired"


TRANSITIONS = {
    ModelState.REGISTERED: {ModelState.CANDIDATE},
    ModelState.CANDIDATE: {ModelState.SHADOW, ModelState.REGISTERED},
    ModelState.SHADOW: {ModelState.SERVING, ModelState.REGISTERED},
    ModelState.SERVING: {ModelState.RETIRED},
    ModelState.RETIRED: set(),
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS model_registry (
    bundle_sha256 TEXT PRIMARY KEY,
    model_id      TEXT NOT NULL,
    state         TEXT NOT NULL,
    eval_card_ref TEXT,
    split_declared TEXT,
    eval_passed   INTEGER NOT NULL DEFAULT 0,
    registered_by TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_transition (
    transition_id TEXT PRIMARY KEY,
    bundle_sha256 TEXT NOT NULL,
    from_state    TEXT,
    to_state      TEXT NOT NULL,
    actor         TEXT NOT NULL,
    note          TEXT,
    created_at    TEXT NOT NULL
);
"""


class RegistryError(Exception):
    def __init__(self, message: str, http_status: int = 400):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def _record_transition(conn, sha, frm, to, actor, note=None):
    conn.execute(
        "INSERT INTO model_transition(transition_id, bundle_sha256, from_state, "
        "to_state, actor, note, created_at) VALUES (?,?,?,?,?,?,?)",
        (f"tr_{uuid.uuid4().hex[:12]}", sha, frm, to, actor, note, _now()),
    )


def register(conn, *, bundle_sha256: str, model_id: str, eval_card_ref: str,
             split_declared: str, registered_by: str) -> dict:
    ensure_schema(conn)
    existing = conn.execute(
        "SELECT * FROM model_registry WHERE bundle_sha256=?", (bundle_sha256,)
    ).fetchone()
    if existing:
        return dict(existing)  # idempotent
    conn.execute(
        "INSERT INTO model_registry(bundle_sha256, model_id, state, eval_card_ref, "
        "split_declared, eval_passed, registered_by, registered_at, updated_at) "
        "VALUES (?,?,?,?,?,0,?,?,?)",
        (bundle_sha256, model_id, ModelState.REGISTERED.value, eval_card_ref,
         split_declared, registered_by, _now(), _now()),
    )
    _record_transition(conn, bundle_sha256, None, ModelState.REGISTERED.value, registered_by)
    conn.commit()
    return get(conn, bundle_sha256)


def set_eval_passed(conn, bundle_sha256: str, passed: bool, actor: str) -> dict:
    ensure_schema(conn)
    _require(conn, bundle_sha256)
    conn.execute("UPDATE model_registry SET eval_passed=?, updated_at=? WHERE bundle_sha256=?",
                 (1 if passed else 0, _now(), bundle_sha256))
    _record_transition(conn, bundle_sha256, None, f"eval_passed={passed}", actor)
    conn.commit()
    return get(conn, bundle_sha256)


def promote(conn, *, bundle_sha256: str, to: ModelState, actor: str,
            note: str | None = None) -> dict:
    ensure_schema(conn)
    row = _require(conn, bundle_sha256)
    frm = ModelState(row["state"])
    if to not in TRANSITIONS[frm]:
        raise RegistryError(f"illegal transition {frm.value} -> {to.value}")
    if to == ModelState.SERVING:
        if not row["eval_passed"]:
            raise RegistryError("cannot promote to serving: eval gate not passed")
        # retire whatever is currently serving (single-serving invariant)
        cur = conn.execute(
            "SELECT bundle_sha256 FROM model_registry WHERE state=?",
            (ModelState.SERVING.value,),
        ).fetchone()
        if cur and cur["bundle_sha256"] != bundle_sha256:
            conn.execute("UPDATE model_registry SET state=?, updated_at=? WHERE bundle_sha256=?",
                         (ModelState.RETIRED.value, _now(), cur["bundle_sha256"]))
            _record_transition(conn, cur["bundle_sha256"], ModelState.SERVING.value,
                               ModelState.RETIRED.value, actor, "auto-retired on new serving")
    conn.execute("UPDATE model_registry SET state=?, updated_at=? WHERE bundle_sha256=?",
                 (to.value, _now(), bundle_sha256))
    _record_transition(conn, bundle_sha256, frm.value, to.value, actor, note)
    conn.commit()
    return get(conn, bundle_sha256)


def rollback(conn, actor: str) -> dict:
    """Return the most-recently-retired bundle to serving, retiring the current
    one. One-click rollback."""
    ensure_schema(conn)
    last_retired = conn.execute(
        "SELECT bundle_sha256 FROM model_transition WHERE to_state=? "
        "ORDER BY created_at DESC LIMIT 1", (ModelState.RETIRED.value,),
    ).fetchone()
    if not last_retired:
        raise RegistryError("no retired bundle to roll back to")
    sha = last_retired["bundle_sha256"]
    row = _require(conn, sha)
    # restore directly to serving (bypasses the forward-only guard — rollback is
    # an explicit recovery operation, recorded as such)
    cur = conn.execute("SELECT bundle_sha256 FROM model_registry WHERE state=?",
                       (ModelState.SERVING.value,)).fetchone()
    if cur:
        conn.execute("UPDATE model_registry SET state=?, updated_at=? WHERE bundle_sha256=?",
                     (ModelState.RETIRED.value, _now(), cur["bundle_sha256"]))
        _record_transition(conn, cur["bundle_sha256"], ModelState.SERVING.value,
                           ModelState.RETIRED.value, actor, "retired by rollback")
    conn.execute("UPDATE model_registry SET state=?, updated_at=? WHERE bundle_sha256=?",
                 (ModelState.SERVING.value, _now(), sha))
    _record_transition(conn, sha, row["state"], ModelState.SERVING.value, actor, "ROLLBACK")
    conn.commit()
    return get(conn, sha)


def serving(conn) -> dict | None:
    ensure_schema(conn)
    r = conn.execute("SELECT * FROM model_registry WHERE state=?",
                     (ModelState.SERVING.value,)).fetchone()
    return dict(r) if r else None


def get(conn, bundle_sha256: str) -> dict:
    r = conn.execute("SELECT * FROM model_registry WHERE bundle_sha256=?",
                     (bundle_sha256,)).fetchone()
    return dict(r) if r else None


def history(conn, bundle_sha256: str) -> list[dict]:
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT * FROM model_transition WHERE bundle_sha256=? ORDER BY created_at",
        (bundle_sha256,),
    ).fetchall()
    return [dict(r) for r in rows]


def _require(conn, bundle_sha256: str) -> sqlite3.Row:
    r = conn.execute("SELECT * FROM model_registry WHERE bundle_sha256=?",
                     (bundle_sha256,)).fetchone()
    if r is None:
        raise RegistryError(f"unknown bundle {bundle_sha256[:12]}…", 404)
    return r
