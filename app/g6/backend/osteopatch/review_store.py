"""Review-state store selector (G8).

The IMMUTABLE read model (source_qc + prediction) ALWAYS lives in SQLite — it is
frozen, read-only, and ships as a file. Only the APPEND-ONLY review_event stream
is pluggable:

  * default (unset / "sqlite")  -> the original ``repo`` SQLite functions.
  * "dynamodb"                  -> ``dynamo_review`` against an on-demand table.

Both expose the identical surface the API already uses:
    current_revision(conn, image_id)
    latest_event(conn, image_id)
    event_history(conn, image_id)
    submit_review(conn, image_id, prediction_id, action, expected_revision,
                  idempotency_key, selected_label, reason, note, reviewer)

The ``conn`` arg is kept in the signature for drop-in compatibility; the
DynamoDB path ignores it for writes/reads of review_event but still uses it to
read the IMMUTABLE prediction + image existence from SQLite (so prediction stays
the single frozen source of truth).
"""
from __future__ import annotations

import os
import sqlite3

from . import repo


def _use_dynamo() -> bool:
    return os.environ.get("OSTEOPATCH_REVIEW_STORE", "sqlite").lower() == "dynamodb"


def current_revision(conn: sqlite3.Connection, image_id: str) -> int:
    if _use_dynamo():
        from . import dynamo_review
        return dynamo_review.current_revision(image_id)
    return repo.current_revision(conn, image_id)


def latest_event(conn: sqlite3.Connection, image_id: str):
    if _use_dynamo():
        from . import dynamo_review
        return dynamo_review.latest_event(image_id)
    return repo.latest_event(conn, image_id)


def event_history(conn: sqlite3.Connection, image_id: str) -> list:
    if _use_dynamo():
        from . import dynamo_review
        return dynamo_review.event_history(image_id)
    return repo.event_history(conn, image_id)


def review_status(latest) -> str:
    # pure mapping on the latest event's action — identical in both stores
    return repo._review_status(latest)


def load_all_review_state(conn: sqlite3.Connection) -> dict:
    """Return {image_id: {"latest": latest_event|None, "revision": int}} for
    EVERY image that has any review event. One pass, so the gallery/export does
    not issue a per-image round trip. Images with no events are simply absent
    (callers treat absence as unreviewed / revision 0)."""
    if _use_dynamo():
        from . import dynamo_review
        return dynamo_review.load_all_review_state()
    # SQLite: a couple of grouped queries over the tiny review_event table
    out: dict = {}
    rows = conn.execute(
        "SELECT image_id, MAX(revision_number) AS r FROM review_event GROUP BY image_id"
    ).fetchall()
    for row in rows:
        iid = row["image_id"]
        latest = repo.latest_event(conn, iid)
        out[iid] = {"latest": latest, "revision": int(row["r"])}
    return out


def submit_review(
    conn: sqlite3.Connection,
    image_id: str,
    prediction_id: str,
    action: str,
    expected_revision: int,
    idempotency_key: str,
    selected_label: str | None = None,
    reason: str | None = None,
    note: str | None = None,
    reviewer: str | None = None,
):
    if _use_dynamo():
        from . import dynamo_review

        def _get_pred(pid):
            r = repo.get_prediction(conn, pid)
            return None if r is None else {"image_id": r["image_id"], "predicted_class": r["predicted_class"]}

        def _image_exists(iid):
            return conn.execute(
                "SELECT 1 FROM source_qc WHERE image_id = ?", (iid,)
            ).fetchone() is not None

        return dynamo_review.submit_review(
            get_prediction=_get_pred,
            image_exists=_image_exists,
            image_id=image_id,
            prediction_id=prediction_id,
            action=action,
            expected_revision=expected_revision,
            idempotency_key=idempotency_key,
            selected_label=selected_label,
            reason=reason,
            note=note,
            reviewer=reviewer,
        )
    return repo.submit_review(
        conn,
        image_id=image_id,
        prediction_id=prediction_id,
        action=action,
        expected_revision=expected_revision,
        idempotency_key=idempotency_key,
        selected_label=selected_label,
        reason=reason,
        note=note,
        reviewer=reviewer,
    )
