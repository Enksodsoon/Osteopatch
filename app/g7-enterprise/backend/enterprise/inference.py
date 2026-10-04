"""E3 — Inference orchestration (queue bookkeeping REAL; GPU execution gated).

What runs locally now:
- enqueue an inference job (idempotent on (image_id, bundle_hash)); the queue is
  a local table, so the orchestration + dedup + status tracking are testable.
- mark shadow vs primary so a candidate model's scores can be compared later
  without being surfaced to reviewers.

What stays gated (needs torch + GPU/compute allowance):
- actually RUNNING the model over pixels. The serving path stays torch-free;
  torch would live only in the worker. No paid compute before G-INFER.
"""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone

from .scaffolds import GateNotApproved

GATE = "G-INFER (async inference + compute allowance)"
PHASE = "E3 inference"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS inference_task (
    task_id       TEXT PRIMARY KEY,
    image_id      TEXT NOT NULL,
    bundle_sha256 TEXT NOT NULL,
    shadow        INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'queued',   -- queued|running|done|failed
    enqueued_at   TEXT NOT NULL,
    UNIQUE(image_id, bundle_sha256, shadow)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def enqueue(conn, *, image_ids: list[str], bundle_sha256: str, shadow: bool = False) -> dict:
    """Idempotently enqueue inference tasks. Re-enqueuing the same
    (image_id, bundle, shadow) is a no-op (dedup), so a retry never double-runs."""
    ensure_schema(conn)
    created = 0
    for img in image_ids:
        try:
            conn.execute(
                "INSERT INTO inference_task(task_id, image_id, bundle_sha256, shadow, "
                "status, enqueued_at) VALUES (?,?,?,?, 'queued', ?)",
                (f"inf_{uuid.uuid4().hex[:12]}", img, bundle_sha256, 1 if shadow else 0, _now()),
            )
            created += 1
        except sqlite3.IntegrityError:
            pass  # already queued/done — idempotent
    conn.commit()
    return {"bundle_sha256": bundle_sha256, "requested": len(image_ids),
            "newly_queued": created, "shadow": shadow}


def queue_depth(conn, status: str = "queued") -> int:
    ensure_schema(conn)
    return conn.execute("SELECT COUNT(*) FROM inference_task WHERE status=?", (status,)).fetchone()[0]


def run_worker_once(conn):
    """Where a GPU worker would pop a task and run the model over pixels.
    GATED: needs torch + compute allowance. Serving stays torch-free."""
    raise GateNotApproved(PHASE, GATE,
                          "GPU worker execution gated (needs torch + compute allowance). "
                          "Enqueue/dedup/status bookkeeping is live and testable now.")
