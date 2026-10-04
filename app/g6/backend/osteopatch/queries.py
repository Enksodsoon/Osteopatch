"""Read queries for the gallery, patch detail, and exports.

All reads join the three concepts WITHOUT collapsing them: the immutable
prediction, the source/QC metadata, and the current (latest) review state are
returned as distinct fields. Exports preserve BOTH the original model
prediction AND the human correction, plus the disclaimer.
"""
from __future__ import annotations

import sqlite3

from . import config, repo

SORTABLE = {"priority", "predicted_class", "image_id"}
FILTERS = {
    "all",
    "unreviewed",
    "reviewed",
    "deferred",
    "pred_NON_TUMOR",
    "pred_VIABLE_TUMOR",
    "pred_NECROSIS",
}


def _row_to_image(conn: sqlite3.Connection, r: sqlite3.Row) -> dict:
    latest = repo.latest_event(conn, r["image_id"])
    status = repo._review_status(latest)
    return {
        "image_id": r["image_id"],
        "source_group": r["source_group"],
        "qc": {
            "primary_qc_status": r["primary_qc_status"],
            "training_eligible": bool(r["training_eligible"]),
            "qc_review_flag": bool(r["qc_review_flag"]),
            "qc_review_reason": r["qc_review_reason"],
            "original_label": r["original_label"],
        },
        "prediction": None if r["prediction_id"] is None else {
            "prediction_id": r["prediction_id"],
            "predicted_class": r["predicted_class"],
            "model_version": r["model_version"],
            "model_bundle_hash": r["model_bundle_hash"],
            "inference_kind": r["inference_kind"],
            "scores": {
                "NON_TUMOR": r["non_tumor_score"],
                "VIABLE_TUMOR": r["viable_tumor_score"],
                "NECROSIS": r["necrosis_score"],
            },
            "score_label": "Model score — uncalibrated",
            "top1_score": r["top1_score"],
            "top_two_margin": r["top_two_margin"],
            "normalized_entropy": r["normalized_entropy"],
        },
        "review_state": {
            "status": status,
            "revision": repo.current_revision(conn, r["image_id"]),
            "latest_action": None if latest is None else latest["action"],
            "selected_class": None if latest is None else latest["selected_class"],
        },
    }


def _base_select() -> str:
    return """
        SELECT s.image_id, s.source_group, s.primary_qc_status, s.training_eligible,
               s.qc_review_flag, s.qc_review_reason, s.original_label,
               p.prediction_id, p.predicted_class, p.model_version, p.model_bundle_hash,
               p.inference_kind, p.non_tumor_score, p.viable_tumor_score,
               p.necrosis_score, p.top1_score, p.top_two_margin, p.normalized_entropy
        FROM source_qc s
        LEFT JOIN prediction p ON p.image_id = s.image_id
    """


def _filter_clause(filt: str) -> tuple[str, list]:
    if filt in ("pred_NON_TUMOR", "pred_VIABLE_TUMOR", "pred_NECROSIS"):
        return " WHERE p.predicted_class = ? ", [filt.replace("pred_", "")]
    return " WHERE 1=1 ", []


def _review_status_filter(image: dict, filt: str) -> bool:
    st = image["review_state"]["status"]
    if filt == "unreviewed":
        return st == "unreviewed"
    if filt == "reviewed":
        return st == "reviewed"
    if filt == "deferred":
        return st == "deferred"
    return True


def list_images(
    conn: sqlite3.Connection,
    sort: str = "priority",
    filt: str = "all",
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    sort = sort if sort in SORTABLE else "priority"
    filt = filt if filt in FILTERS else "all"

    # Defensive clamp: the HTTP layer already enforces page>=1 and
    # 1<=page_size<=500, but list_images is also called directly (tests, future
    # callers). Clamp here so a bad page/page_size can never produce a negative
    # slice start or an unbounded page.
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))

    sql = _base_select()
    where, params = _filter_clause(filt)
    sql += where
    if q:
        sql += " AND s.image_id LIKE ? "
        params.append(f"%{q}%")

    rows = list(conn.execute(sql, params))
    images = [_row_to_image(conn, r) for r in rows]

    # review-status filters apply post-join (depend on latest event)
    if filt in ("unreviewed", "reviewed", "deferred"):
        images = [im for im in images if _review_status_filter(im, filt)]

    # sorting — predictionless rows sort last for priority/class
    def sort_key(im: dict):
        pred = im["prediction"]
        if sort == "image_id":
            return (0, im["image_id"])
        if sort == "predicted_class":
            pc = pred["predicted_class"] if pred else "~"
            return (0 if pred else 1, pc, im["image_id"])
        # priority (default): smallest margin, then highest entropy, then id
        if pred is None:
            return (1, 0.0, 0.0, im["image_id"])
        from .scoring import review_priority_key

        k = review_priority_key(
            pred["top_two_margin"], pred["normalized_entropy"], im["image_id"]
        )
        return (0,) + k

    images.sort(key=sort_key)

    total = len(images)
    start = max(0, (page - 1) * page_size)
    page_items = images[start : start + page_size]

    # attach review-priority rank (global, over all predicted images)
    rank_map = _priority_rank_map(conn)
    for im in page_items:
        im["review_priority_rank"] = rank_map.get(im["image_id"])

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "sort": sort,
        "filter": filt,
        "query": q or "",
        "items": page_items,
    }


def _priority_rank_map(conn: sqlite3.Connection) -> dict[str, int]:
    """Global deterministic review-priority rank over all predicted images."""
    from .scoring import review_priority_key

    rows = list(
        conn.execute(
            "SELECT image_id, top_two_margin, normalized_entropy FROM prediction"
        )
    )
    rows.sort(
        key=lambda r: review_priority_key(
            r["top_two_margin"], r["normalized_entropy"], r["image_id"]
        )
    )
    return {r["image_id"]: i + 1 for i, r in enumerate(rows)}


def get_image(conn: sqlite3.Connection, image_id: str) -> dict | None:
    sql = _base_select() + " WHERE s.image_id = ? "
    r = conn.execute(sql, [image_id]).fetchone()
    if r is None:
        return None
    image = _row_to_image(conn, r)
    image["review_priority_rank"] = _priority_rank_map(conn).get(image_id)
    image["history"] = [
        _event_dict(e) for e in repo.event_history(conn, image_id)
    ]
    return image


def _event_dict(e: sqlite3.Row) -> dict:
    return {
        "review_event_id": e["review_event_id"],
        "action": e["action"],
        "selected_class": e["selected_class"],
        "reason": e["reason"],
        "note": e["note"],
        "reviewer": e["reviewer"],
        "created_at": e["created_at"],
        "revision_number": e["revision_number"],
        "prediction_id": e["prediction_id"],
    }


def export_rows(conn: sqlite3.Connection) -> list[dict]:
    """One row per image that has a prediction, preserving the ORIGINAL model
    prediction AND the current human review state AND full history refs.
    """
    rows = list(
        conn.execute(_base_select() + " WHERE p.prediction_id IS NOT NULL ORDER BY s.image_id")
    )
    out = []
    for r in rows:
        latest = repo.latest_event(conn, r["image_id"])
        status = repo._review_status(latest)
        history = repo.event_history(conn, r["image_id"])
        out.append(
            {
                "image_id": r["image_id"],
                "source_group": r["source_group"],
                "qc_primary_status": r["primary_qc_status"],
                "training_eligible": bool(r["training_eligible"]),
                "qc_review_flag": bool(r["qc_review_flag"]),
                # ORIGINAL model prediction (immutable) ----------------------
                "model_version": r["model_version"],
                "model_bundle_hash": r["model_bundle_hash"],
                "inference_kind": r["inference_kind"],
                "model_predicted_class": r["predicted_class"],
                "model_score_NON_TUMOR": r["non_tumor_score"],
                "model_score_VIABLE_TUMOR": r["viable_tumor_score"],
                "model_score_NECROSIS": r["necrosis_score"],
                "model_score_label": "Model score — uncalibrated",
                "top_two_margin": r["top_two_margin"],
                "normalized_entropy": r["normalized_entropy"],
                # HUMAN review (append-only) ---------------------------------
                "human_review_status": status,
                "human_latest_action": None if latest is None else latest["action"],
                "human_corrected_class": (
                    latest["selected_class"] if latest and latest["action"] == "CORRECT" else None
                ),
                "human_defer_reason": (
                    latest["reason"] if latest and latest["action"] == "DEFER" else None
                ),
                "human_note": None if latest is None else latest["note"],
                "human_reviewer": None if latest is None else latest["reviewer"],
                "human_revision_number": 0 if latest is None else latest["revision_number"],
                "review_event_count": len(history),
                "review_event_ids": "|".join(e["review_event_id"] for e in history),
                "disclaimer": config.DISCLAIMER,
            }
        )
    return out
