"""OsteoPatch G6 FastAPI application — local educational review prototype.

Serves the gallery, patch detail, images, review submission, review history,
exports, and the model card. Binds to 127.0.0.1 only (see run_server). Imports
NO torch — all predictions are precomputed.
"""
from __future__ import annotations

import sqlite3
import threading

from fastapi import FastAPI, Query, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import config, db, exports, images, modelcard, queries, repo, review_store

# ---------------------------------------------------------------------------
# App + per-request connection
# ---------------------------------------------------------------------------
app = FastAPI(
    title="OsteoPatch Review (G6, local)",
    version="0.6.0",
    description=config.DISCLAIMER,
)

_conn: sqlite3.Connection | None = None
_thread_conn = threading.local()
_conn_init_lock = threading.Lock()


def get_conn() -> sqlite3.Connection:
    """Return the connection for the current worker thread.

    FastAPI runs synchronous endpoints in a thread pool. Sharing one SQLite
    connection across those threads can produce intermittent ``InterfaceError``
    failures under concurrent browser traffic even with ``check_same_thread``
    disabled. Production therefore keeps one connection per worker thread.

    ``_conn`` remains an explicit injected override for tests, which intentionally
    use one isolated in-memory/temp connection.
    """
    if _conn is not None:
        return _conn

    conn = getattr(_thread_conn, "conn", None)
    if conn is None:
        # Serialise first-use migration work; afterwards each thread owns its
        # independent SQLite connection and SQLite coordinates file-level writes.
        with _conn_init_lock:
            conn = db.connect()
            db.run_migrations(conn)
        _thread_conn.conn = conn
    return conn


def set_conn(conn: sqlite3.Connection) -> None:
    """Test hook: inject an in-memory / temp connection."""
    global _conn
    _conn = conn


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
@app.exception_handler(repo.ReviewError)
async def _review_error_handler(_: Request, exc: repo.ReviewError):
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": exc.message, "detail": exc.detail},
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class ReviewSubmission(BaseModel):
    prediction_id: str
    action: str = Field(..., description="ACCEPT | CORRECT | DEFER")
    selected_label: str | None = None
    reason: str | None = None
    note: str | None = None
    expected_revision: int = 0
    idempotency_key: str
    reviewer: str | None = None


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
@app.get("/v1/health")
def health():
    conn = get_conn()
    n_img = conn.execute("SELECT COUNT(*) FROM source_qc").fetchone()[0]
    n_pred = conn.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    allow = config.load_image_allowlist()
    if allow is not None:
        n_img = conn.execute(
            "SELECT COUNT(*) FROM source_qc WHERE image_id IN (%s)"
            % ",".join("?" for _ in allow),
            sorted(allow),
        ).fetchone()[0]
        n_pred = conn.execute(
            "SELECT COUNT(*) FROM prediction WHERE image_id IN (%s)"
            % ",".join("?" for _ in allow),
            sorted(allow),
        ).fetchone()[0]
    return {
        "status": "ok",
        "model_version": config.MODEL_VERSION,
        "model_bundle_sha256": config.EXPECTED_BUNDLE_SHA256,
        "images_indexed": n_img,
        "predictions": n_pred,
        "image_subset_scoped": allow is not None,
        "disclaimer": config.DISCLAIMER,
    }


# Recovery disclosure — shown verbatim in the UI attribution panel. The lost
# original absolute head was NOT recovered; attribution runs on a behaviorally
# reconstructed classifier whose prediction behavior was verified against the
# original stored softmax outputs (R1-C2). Contrastive-only because single-class
# Grad-CAM is not gauge-invariant for a zero-sum representative head.
ATTRIBUTION_DISCLOSURE = (
    "Attribution uses a behaviorally reconstructed classifier because the "
    "original runtime head weights were not durably preserved. Prediction "
    "behavior was verified against the original stored outputs."
)
ATTRIBUTION_METHOD_NOTE = (
    "This is model attribution, not tissue segmentation or diagnostic annotation."
)

# The 6 ordered contrastive pairs (A vs B), both directions for each unordered pair.
CONTRASTIVE_PAIRS = [
    {"a": "VIABLE_TUMOR", "b": "NECROSIS"},
    {"a": "NECROSIS", "b": "VIABLE_TUMOR"},
    {"a": "NON_TUMOR", "b": "VIABLE_TUMOR"},
    {"a": "VIABLE_TUMOR", "b": "NON_TUMOR"},
    {"a": "NON_TUMOR", "b": "NECROSIS"},
    {"a": "NECROSIS", "b": "NON_TUMOR"},
]


@app.get("/v1/meta")
def meta():
    return {
        "canonical_classes": list(config.CANONICAL_CLASSES),
        "review_actions": list(config.REVIEW_ACTIONS),
        "defer_reasons": list(config.DEFER_REASONS),
        "score_label": "Model score — uncalibrated",
        "disclaimer": config.DISCLAIMER,
        # G7: attribution is now wired. g7_placeholder retained (empty) only so
        # any older client that reads the key does not crash; the real signal is
        # attribution_enabled + the attribution block below.
        "g7_placeholder": "",
        "attribution_enabled": True,
        "attribution": {
            "enabled": True,
            "method": "contrastive-grad-cam",
            "attribution_target": "raw logit_A - logit_B (contrastive)",
            "recovered_model_id": config.RECOVERED_MODEL_ID,
            "source_prediction_model": config.MODEL_VERSION,
            "pairs": CONTRASTIVE_PAIRS,
            "disclosure": ATTRIBUTION_DISCLOSURE,
            "method_note": ATTRIBUTION_METHOD_NOTE,
        },
    }


@app.get("/v1/model-card")
def get_model_card():
    return modelcard.model_card()


# ---------------------------------------------------------------------------
# Attribution (G7) — contrastive Grad-CAM over the behaviorally-recovered head.
# torch / pytorch-grad-cam are imported LAZILY inside the handler, so the normal
# serving path (gallery, review, export) stays torch-free.
# ---------------------------------------------------------------------------
def _default_pair_for(prediction_row) -> tuple[str, str]:
    """Default contrastive pair = predicted class (A) vs runner-up (B),
    derived from the stored G6 prediction scores."""
    scores = {
        "NON_TUMOR": prediction_row["non_tumor_score"],
        "VIABLE_TUMOR": prediction_row["viable_tumor_score"],
        "NECROSIS": prediction_row["necrosis_score"],
    }
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ordered[0][0], ordered[1][0]


@app.get("/v1/images/{image_id}/attribution")
def get_attribution(
    image_id: str,
    target_a: str | None = Query(None),
    target_b: str | None = Query(None),
    format: str = Query("png", description="png (overlay) | json (meta + base64)"),
):
    import base64

    conn = get_conn()
    pred = repo.get_prediction_for_image(conn, image_id)
    if pred is None:
        return JSONResponse(status_code=404, content={"error": "unknown image_id"})

    # default pair = predicted vs runner-up from the stored G6 row
    if target_a is None or target_b is None:
        target_a, target_b = _default_pair_for(pred)

    if target_a not in config.CLASS_TO_IDX or target_b not in config.CLASS_TO_IDX:
        return JSONResponse(status_code=400, content={"error": "invalid class", "detail": {"target_a": target_a, "target_b": target_b}})
    if target_a == target_b:
        return JSONResponse(status_code=400, content={"error": "target_a and target_b must differ"})

    image_path = config.ATTRIB_IMAGES_DIR / f"{image_id}.tiff"
    if not image_path.exists():
        return JSONResponse(status_code=404, content={"error": "image pixels not found", "detail": {"path": str(image_path)}})

    # lazy torch — only now does the attribution module (and torch) load
    from . import attribution
    try:
        result = attribution.compute_attribution(image_path, image_id, target_a, target_b)
    except attribution.AttributionError as exc:
        return JSONResponse(status_code=503, content={"error": "attribution unavailable", "detail": str(exc)})
    except ImportError as exc:
        # torch / pytorch-grad-cam not installed in this environment — honest
        # degradation, never a fabricated heatmap.
        return JSONResponse(
            status_code=503,
            content={"error": "attribution runtime unavailable (torch not installed)", "detail": str(exc)},
        )

    if format == "json":
        return {
            "image_id": image_id,
            "target_a": result.target_a,
            "target_b": result.target_b,
            "cached": result.cached,
            "latency_ms": result.latency_ms,
            "overlay_png_base64": base64.b64encode(result.overlay_png).decode("ascii"),
            "heatmap_png_base64": base64.b64encode(result.heatmap_png).decode("ascii"),
            "meta": result.meta,
            "disclosure": ATTRIBUTION_DISCLOSURE,
            "method_note": ATTRIBUTION_METHOD_NOTE,
        }
    # default: overlay PNG, with meta surfaced in headers for the UI
    return Response(
        content=result.overlay_png,
        media_type="image/png",
        headers={
            "X-Attrib-Target-A": result.target_a,
            "X-Attrib-Target-B": result.target_b,
            "X-Attrib-Cached": str(result.cached).lower(),
            "X-Attrib-Latency-Ms": str(result.latency_ms),
            "X-Attrib-Recovered-Model": result.meta["recovered_model_id"],
            "X-Attrib-Target-Layer": result.meta["target_layer"],
            "Cache-Control": "no-store",
        },
    )


@app.get("/v1/images/{image_id}/attribution/meta")
def get_attribution_meta(image_id: str):
    """Attribution availability + default pair for an image, WITHOUT running the
    (expensive, torch-loading) CAM. Lets the UI render the panel + default
    selection and the recovery disclosure before the user requests an overlay."""
    conn = get_conn()
    pred = repo.get_prediction_for_image(conn, image_id)
    if pred is None:
        return JSONResponse(status_code=404, content={"error": "unknown image_id"})
    da, db_ = _default_pair_for(pred)
    return {
        "image_id": image_id,
        "attribution_enabled": True,
        "predicted_class": pred["predicted_class"],
        "default_pair": {"a": da, "b": db_},
        "pairs": CONTRASTIVE_PAIRS,
        "recovered_model_id": config.RECOVERED_MODEL_ID,
        "source_prediction_model": config.MODEL_VERSION,
        "source_prediction_bundle_sha256": config.EXPECTED_BUNDLE_SHA256,
        "attribution_target": "raw logit_A - logit_B (contrastive)",
        "disclosure": ATTRIBUTION_DISCLOSURE,
        "method_note": ATTRIBUTION_METHOD_NOTE,
    }


# ---------------------------------------------------------------------------
# Images / gallery
# ---------------------------------------------------------------------------
@app.get("/v1/images")
def list_images(
    sort: str = Query("priority"),
    filter: str = Query("all"),
    q: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
):
    conn = get_conn()
    return queries.list_images(conn, sort=sort, filt=filter, q=q, page=page, page_size=page_size)


@app.get("/v1/images/{image_id}")
def get_image(image_id: str):
    conn = get_conn()
    image = queries.get_image(conn, image_id)
    if image is None:
        return JSONResponse(status_code=404, content={"error": "unknown image_id"})
    return image


@app.get("/v1/predictions/{prediction_id}")
def get_prediction(prediction_id: str):
    conn = get_conn()
    r = repo.get_prediction(conn, prediction_id)
    if r is None:
        return JSONResponse(status_code=404, content={"error": "unknown prediction_id"})
    return {
        "prediction_id": r["prediction_id"],
        "image_id": r["image_id"],
        "model_version": r["model_version"],
        "model_bundle_hash": r["model_bundle_hash"],
        "inference_kind": r["inference_kind"],
        "created_at": r["created_at"],
        "predicted_class": r["predicted_class"],
        "scores": {
            "NON_TUMOR": r["non_tumor_score"],
            "VIABLE_TUMOR": r["viable_tumor_score"],
            "NECROSIS": r["necrosis_score"],
        },
        "score_label": "Model score — uncalibrated",
        "top1_score": r["top1_score"],
        "top_two_margin": r["top_two_margin"],
        "normalized_entropy": r["normalized_entropy"],
    }


@app.get("/v1/images/{image_id}/thumbnail")
def get_thumbnail(image_id: str):
    conn = get_conn()
    try:
        data = images.thumbnail_png(conn, image_id)
    except images.ImageNotFound:
        return JSONResponse(status_code=404, content={"error": "image not found"})
    except images.UnsafePath:
        return JSONResponse(status_code=400, content={"error": "unsafe path"})
    except images.ImageDecodeError as exc:
        return JSONResponse(status_code=422, content={"error": "image could not be decoded", "detail": str(exc)})
    return Response(content=data, media_type="image/png")


@app.get("/v1/images/{image_id}/full")
def get_full(image_id: str):
    conn = get_conn()
    try:
        data = images.full_png(conn, image_id)
    except images.ImageNotFound:
        return JSONResponse(status_code=404, content={"error": "image not found"})
    except images.UnsafePath:
        return JSONResponse(status_code=400, content={"error": "unsafe path"})
    except images.ImageDecodeError as exc:
        return JSONResponse(status_code=422, content={"error": "image could not be decoded", "detail": str(exc)})
    return Response(content=data, media_type="image/png")


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------
@app.get("/v1/images/{image_id}/review")
def get_review(image_id: str):
    conn = get_conn()
    if conn.execute(
        "SELECT 1 FROM source_qc WHERE image_id = ?", (image_id,)
    ).fetchone() is None:
        return JSONResponse(status_code=404, content={"error": "unknown image_id"})
    latest = review_store.latest_event(conn, image_id)
    return {
        "image_id": image_id,
        "revision": review_store.current_revision(conn, image_id),
        "status": review_store.review_status(latest),
        "latest": None if latest is None else queries._event_dict(latest),
        "history": [queries._event_dict(e) for e in review_store.event_history(conn, image_id)],
    }


@app.post("/v1/images/{image_id}/reviews")
def post_review(image_id: str, body: ReviewSubmission):
    conn = get_conn()
    event, created = review_store.submit_review(
        conn,
        image_id=image_id,
        prediction_id=body.prediction_id,
        action=body.action,
        expected_revision=body.expected_revision,
        idempotency_key=body.idempotency_key,
        selected_label=body.selected_label,
        reason=body.reason,
        note=body.note,
        reviewer=body.reviewer,
    )
    payload = queries._event_dict(event)
    payload["created"] = created
    payload["current_revision"] = review_store.current_revision(conn, image_id)
    return JSONResponse(status_code=201 if created else 200, content=payload)


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------
@app.get("/v1/exports/reviews")
def export_reviews(format: str = Query("csv")):
    conn = get_conn()
    rows = queries.export_rows(conn)
    if format == "json":
        return exports.json_envelope(rows)
    return StreamingResponse(
        iter([exports.rows_to_csv(rows)]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename={exports.CSV_FILENAME}",
        },
    )
