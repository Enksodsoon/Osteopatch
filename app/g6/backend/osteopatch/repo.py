"""Data-access + review-logic layer over SQLite.

Keeps the three concepts separate: predictions are inserted once and never
updated; review events are only ever appended; source/QC metadata is read-only
here. Review safety (idempotency, optimistic concurrency, validation) lives in
``submit_review`` and raises typed errors the API maps to 404/409/422.
"""
from __future__ import annotations

import sqlite3
import uuid

from . import config, scoring
from .db import utc_now

CANON = set(config.CANONICAL_CLASSES)


# ---- typed review errors ---------------------------------------------------
class ReviewError(Exception):
    http_status = 400

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(ReviewError):
    http_status = 404


class ConflictError(ReviewError):
    http_status = 409


class ValidationError(ReviewError):
    http_status = 422


# ---- predictions -----------------------------------------------------------
def prediction_id_for(image_id: str, bundle_hash: str) -> str:
    """Deterministic prediction id so dedup is stable across runs."""
    return f"pred-{image_id}-{bundle_hash[:12]}"


def upsert_prediction(
    conn: sqlite3.Connection,
    image_id: str,
    bundle_hash: str,
    model_version: str,
    scores: list[float],
) -> tuple[str, bool]:
    """Insert a prediction if (image_id, bundle_hash) is new; else reuse.

    Returns (prediction_id, created). Never duplicates, never mutates an
    existing row — the model prediction is immutable.
    """
    pid = prediction_id_for(image_id, bundle_hash)
    existing = conn.execute(
        "SELECT prediction_id FROM prediction WHERE image_id = ? AND model_bundle_hash = ?",
        (image_id, bundle_hash),
    ).fetchone()
    if existing:
        return existing["prediction_id"], False

    summ = scoring.summarize(scores)
    conn.execute(
        """
        INSERT INTO prediction
          (prediction_id, image_id, model_version, model_bundle_hash, created_at,
           inference_kind, predicted_class, non_tumor_score, viable_tumor_score,
           necrosis_score, top1_score, top_two_margin, normalized_entropy)
        VALUES (?, ?, ?, ?, ?, 'prototype_inference', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            pid, image_id, model_version, bundle_hash, utc_now(),
            summ.predicted_class,
            summ.scores["NON_TUMOR"], summ.scores["VIABLE_TUMOR"],
            summ.scores["NECROSIS"], summ.top1_score, summ.top_two_margin,
            summ.normalized_entropy,
        ),
    )
    return pid, True


def get_prediction(conn: sqlite3.Connection, prediction_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM prediction WHERE prediction_id = ?", (prediction_id,)
    ).fetchone()


def get_prediction_for_image(conn: sqlite3.Connection, image_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM prediction WHERE image_id = ? AND model_bundle_hash = ? ",
        (image_id, _active_bundle_hash(conn)),
    ).fetchone() or conn.execute(
        "SELECT * FROM prediction WHERE image_id = ? ORDER BY created_at LIMIT 1",
        (image_id,),
    ).fetchone()


def _active_bundle_hash(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT model_bundle_hash FROM prediction ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    return row["model_bundle_hash"] if row else config.EXPECTED_BUNDLE_SHA256


# ---- review state ----------------------------------------------------------
def current_revision(conn: sqlite3.Connection, image_id: str) -> int:
    row = conn.execute(
        "SELECT MAX(revision_number) AS r FROM review_event WHERE image_id = ?",
        (image_id,),
    ).fetchone()
    return int(row["r"]) if row and row["r"] is not None else 0


def latest_event(conn: sqlite3.Connection, image_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM review_event WHERE image_id = ? "
        "ORDER BY revision_number DESC LIMIT 1",
        (image_id,),
    ).fetchone()


def event_history(conn: sqlite3.Connection, image_id: str) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM review_event WHERE image_id = ? ORDER BY revision_number ASC",
            (image_id,),
        )
    )


def _review_status(latest: sqlite3.Row | None) -> str:
    if latest is None:
        return "unreviewed"
    return {"ACCEPT": "reviewed", "CORRECT": "reviewed", "DEFER": "deferred"}[
        latest["action"]
    ]


# ---- review submission (idempotency + concurrency + validation) -----------
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
) -> tuple[sqlite3.Row, bool]:
    """Append one review event. Returns (event_row, created).

    * 404 — unknown image_id or prediction_id.
    * 422 — invalid action/class relationship, or prediction/image mismatch.
    * 409 — expected_revision does not match the current revision (stale).
    * idempotent — same idempotency_key on the same image returns the original
      event with created=False and inserts nothing new.
    """
    img = conn.execute(
        "SELECT image_id FROM source_qc WHERE image_id = ?", (image_id,)
    ).fetchone()
    if img is None:
        raise NotFoundError("unknown image_id", {"image_id": image_id})

    pred = get_prediction(conn, prediction_id)
    if pred is None:
        raise NotFoundError("unknown prediction_id", {"prediction_id": prediction_id})
    if pred["image_id"] != image_id:
        raise ValidationError(
            "prediction_id does not belong to image_id",
            {"image_id": image_id, "prediction_id": prediction_id},
        )

    action = (action or "").upper()
    if action not in config.REVIEW_ACTIONS:
        raise ValidationError("invalid action", {"action": action})

    # action/class relationship validation
    if action == "CORRECT":
        if selected_label not in CANON:
            raise ValidationError(
                "CORRECT requires a valid canonical class",
                {"selected_label": selected_label, "allowed": list(config.CANONICAL_CLASSES)},
            )
    elif action == "ACCEPT":
        if selected_label is not None and selected_label != pred["predicted_class"]:
            raise ValidationError(
                "ACCEPT cannot carry a label contradicting the prediction",
                {"selected_label": selected_label, "predicted_class": pred["predicted_class"]},
            )
        selected_label = None
    elif action == "DEFER":
        if selected_label is not None:
            raise ValidationError(
                "DEFER must not carry a class", {"selected_label": selected_label}
            )
        if reason is not None and reason not in config.DEFER_REASONS:
            raise ValidationError(
                "invalid defer reason",
                {"reason": reason, "allowed": list(config.DEFER_REASONS)},
            )

    # idempotent replay — same key on same image returns the original
    prior = conn.execute(
        "SELECT * FROM review_event WHERE image_id = ? AND idempotency_key = ?",
        (image_id, idempotency_key),
    ).fetchone()
    if prior is not None:
        return prior, False

    # optimistic concurrency
    cur_rev = current_revision(conn, image_id)
    if int(expected_revision) != cur_rev:
        raise ConflictError(
            "stale expected_revision",
            {"expected_revision": expected_revision, "current_revision": cur_rev},
        )

    new_rev = cur_rev + 1
    event_id = f"rev-{image_id}-{new_rev}-{uuid.uuid4().hex[:8]}"
    try:
        conn.execute(
            """
            INSERT INTO review_event
              (review_event_id, image_id, prediction_id, action, selected_class,
               reason, note, reviewer, created_at, revision_number, idempotency_key)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id, image_id, prediction_id, action, selected_label,
                reason, note, reviewer or config.DEFAULT_REVIEWER, utc_now(),
                new_rev, idempotency_key,
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        # racing writer took this revision/key first
        conn.rollback()
        again = conn.execute(
            "SELECT * FROM review_event WHERE image_id = ? AND idempotency_key = ?",
            (image_id, idempotency_key),
        ).fetchone()
        if again is not None:
            return again, False
        raise ConflictError("concurrent revision conflict", {"error": str(exc)})

    row = conn.execute(
        "SELECT * FROM review_event WHERE review_event_id = ?", (event_id,)
    ).fetchone()
    return row, True
