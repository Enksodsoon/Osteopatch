"""Review proxy — enforce tenancy here, delegate the real work to G6.

Project scoping is now REQUEST-SCOPED: the project id is passed as an explicit
argument down into the G6 read model, which filters on ``source_qc.project_id``.

This previously worked by writing ``os.environ["OSTEOPATCH_IMAGE_ALLOWLIST"]``
and reassigning two module globals on ``osteopatch.config`` at request time,
never restoring them. Under concurrency that let one project read another's
scope, and left the most-recently-touched project in place for later unscoped
reads. The root cause was that the schema had nowhere to store a project; the
mutation was a symptom.

When the G6 package cannot be imported (bare test env, missing runtime data),
every call returns a labelled 503 — NEVER a fabricated prediction or review.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from . import config

# ---------------------------------------------------------------------------
# G6 import is best-effort and lazy. We never crash the enterprise app just
# because the torch-free G6 web stack or its SQLite data is absent.
# ---------------------------------------------------------------------------
_G6_IMPORT_ERROR: str | None = None


def _g6():
    """Return the imported G6 app module, or raise HTTPException(503)."""
    global _G6_IMPORT_ERROR
    try:
        from osteopatch import app as g6_app  # type: ignore
        return g6_app
    except Exception as exc:  # pragma: no cover - env dependent
        _G6_IMPORT_ERROR = f"{type(exc).__name__}: {exc}"
        raise HTTPException(
            status_code=503,
            detail={
                "error": "review backend (G6) unavailable",
                "hint": "install/point OSTEOPATCH_* at the G6 data store; "
                        "no prediction is fabricated when the backend is down",
                "cause": _G6_IMPORT_ERROR,
            },
        )


def backend_status() -> dict:
    try:
        _g6()
        return {"available": True}
    except HTTPException as exc:
        return {"available": False, "detail": exc.detail}


# ---------------------------------------------------------------------------
# Tenancy — request-scoped, no process-global mutation.
# ---------------------------------------------------------------------------
def _require_project(project_id: str | None) -> str:
    if not project_id:
        raise HTTPException(status_code=400, detail="missing project context")
    return project_id


def all_corpus_image_ids(limit: int | None = None) -> list[str]:
    """Real image_ids known to the G6 store (used to validate / default a grant)."""
    from osteopatch import projects  # type: ignore

    return projects.known_image_ids(_g6().get_conn(), limit)


def grant_scope(project_id: str, *, image_ids: list[str] | None, limit: int = 50) -> list[str]:
    """Validate and persist a project's review scope.

    Scoping lives in the DATABASE now, not in a per-project JSON file that the
    process-global mechanism had to be pointed at. Unknown ids are rejected,
    never silently granted (fail-closed tenancy).
    """
    from osteopatch import projects  # type: ignore

    pid = _require_project(project_id)
    conn = _g6().get_conn()
    try:
        if image_ids is None:
            chosen = projects.known_image_ids(conn, limit=limit)
        else:
            chosen = list(dict.fromkeys(image_ids))
        return projects.grant_images(conn, pid, chosen)
    except projects.ProjectScopeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def project_image_ids(project_id: str) -> list[str]:
    """Every image visible to this project. Used by tests and diagnostics."""
    from osteopatch import projects  # type: ignore

    return projects.project_image_ids(_g6().get_conn(), _require_project(project_id))


# ---------------------------------------------------------------------------
# Delegated calls
# ---------------------------------------------------------------------------
def list_images(project_id: str | None, *, sort: str, filt: str, page: int, page_size: int) -> dict:
    pid = _require_project(project_id)
    conn = _g6().get_conn()
    from osteopatch import queries  # type: ignore
    return queries.list_images(
        conn, sort=sort, filt=filt, q=None, page=page, page_size=page_size, project_id=pid
    )


def get_image(project_id: str | None, image_id: str) -> dict:
    pid = _require_project(project_id)
    from osteopatch import queries  # type: ignore
    image = queries.get_image(_g6().get_conn(), image_id, project_id=pid)
    if image is None:
        # Indistinguishable from "does not exist" on purpose: telling the two
        # apart would let a tenant probe for another tenant's data.
        raise HTTPException(status_code=404, detail="unknown image_id (or out of project scope)")
    return image


def submit_review(project_id: str | None, image_id: str, body: dict, *, reviewer: str) -> dict:
    pid = _require_project(project_id)
    conn = _g6().get_conn()
    from osteopatch import queries, review_store  # type: ignore

    # Refuse to review an image this project cannot see, using the same
    # request-scoped filter as the read path.
    if queries.get_image(conn, image_id, project_id=pid) is None:
        raise HTTPException(status_code=404, detail="unknown image_id (or out of project scope)")

    event, created = review_store.submit_review(
        conn,
        image_id=image_id,
        prediction_id=body["prediction_id"],
        action=body["action"],
        expected_revision=body.get("expected_revision", 0),
        idempotency_key=body["idempotency_key"],
        selected_label=body.get("selected_label"),
        reason=body.get("reason"),
        note=body.get("note"),
        reviewer=reviewer,
    )
    payload = queries._event_dict(event)
    payload["created"] = created
    return payload


def export_reviews(project_id: str | None, *, format: str) -> dict:
    pid = _require_project(project_id)
    from osteopatch import queries  # type: ignore
    rows = queries.export_rows(_g6().get_conn(), project_id=pid)
    return {"format": format, "count": len(rows), "rows": rows}
