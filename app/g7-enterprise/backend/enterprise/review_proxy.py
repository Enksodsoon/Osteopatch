"""Review proxy — enforce tenancy here, delegate the real work to G6.

Project scoping is applied by pointing the G6 app at that project's image
allowlist (the mechanism G6 already supports via OSTEOPATCH_IMAGE_ALLOWLIST),
so we reuse the immutable read model instead of duplicating it. Each project's
scope file lives under config.PROJECT_SCOPE_DIR.

When the G6 package cannot be imported (bare test env, missing scratch data),
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
# Tenancy — set the per-project allowlist for the duration of a call.
# ---------------------------------------------------------------------------
def _project_scope_path(project_id: str) -> Path:
    return config.PROJECT_SCOPE_DIR / f"{project_id}.json"


def write_project_scope(project_id: str, image_ids: list[str]) -> Path:
    config.PROJECT_SCOPE_DIR.mkdir(parents=True, exist_ok=True)
    path = _project_scope_path(project_id)
    path.write_text(json.dumps({"subset_image_ids": sorted(set(image_ids))}), encoding="utf-8")
    return path


def all_corpus_image_ids(limit: int | None = None) -> list[str]:
    """Real image_ids known to the G6 store (used to validate / default a grant)."""
    g6 = _g6()
    conn = g6.get_conn()
    q = "SELECT image_id FROM source_qc ORDER BY image_id"
    if limit:
        q += f" LIMIT {int(limit)}"
    return [r["image_id"] for r in conn.execute(q).fetchall()]


def grant_scope(project_id: str, *, image_ids: list[str] | None, limit: int = 50) -> list[str]:
    """Validate and persist a project's review scope. Unknown ids are rejected,
    never silently granted (fail-closed tenancy)."""
    known = set(all_corpus_image_ids())
    if image_ids is None:
        chosen = all_corpus_image_ids(limit=limit)
    else:
        unknown = [i for i in image_ids if i not in known]
        if unknown:
            raise HTTPException(status_code=400, detail={
                "error": "unknown image_ids rejected (fail-closed scope)",
                "unknown": unknown[:10], "unknown_count": len(unknown),
            })
        chosen = list(dict.fromkeys(image_ids))
    write_project_scope(project_id, chosen)
    return chosen


def _apply_scope(project_id: str | None) -> None:
    """Point G6 config at this project's allowlist. A project with no scope file
    sees an EMPTY set (fail-closed) rather than the full corpus."""
    if not project_id:
        raise HTTPException(status_code=400, detail="missing project context")
    import os
    import sys
    path = _project_scope_path(project_id)
    if not path.exists():
        # fail closed: empty scope file so the project sees nothing it wasn't granted
        write_project_scope(project_id, [])
    os.environ["OSTEOPATCH_IMAGE_ALLOWLIST"] = str(path)
    # G6 captures IMAGE_ALLOWLIST_PATH as a module constant at import time and
    # caches the parsed set. Mutate the EXACT module object G6 is using (resolved
    # from sys.modules, not a fresh import that could bind a different instance
    # under a different sys.path entry) and bust its cache, so the new scope
    # takes effect deterministically for this call.
    g6_config = sys.modules.get("osteopatch.config")
    if g6_config is None:  # not imported yet
        try:
            from osteopatch import config as g6_config  # type: ignore
        except Exception:
            # G6 not importable here (backend unavailable). Leave env set; the
            # subsequent _g6() call raises the clean 503. Never fabricate.
            return
    g6_config.IMAGE_ALLOWLIST_PATH = str(path)
    g6_config._IMAGE_ALLOWLIST_CACHE = g6_config._ALLOWLIST_UNSET


# ---------------------------------------------------------------------------
# Delegated calls
# ---------------------------------------------------------------------------
def list_images(project_id: str | None, *, sort: str, filt: str, page: int, page_size: int) -> dict:
    _apply_scope(project_id)
    g6 = _g6()
    conn = g6.get_conn()
    from osteopatch import queries  # type: ignore
    return queries.list_images(conn, sort=sort, filt=filt, q=None, page=page, page_size=page_size)


def get_image(project_id: str | None, image_id: str) -> dict:
    _apply_scope(project_id)
    g6 = _g6()
    from osteopatch import queries  # type: ignore
    image = queries.get_image(g6.get_conn(), image_id)
    if image is None:
        raise HTTPException(status_code=404, detail="unknown image_id (or out of project scope)")
    return image


def submit_review(project_id: str | None, image_id: str, body: dict, *, reviewer: str) -> dict:
    _apply_scope(project_id)
    g6 = _g6()
    from osteopatch import review_store  # type: ignore
    event, created = review_store.submit_review(
        g6.get_conn(),
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
    from osteopatch import queries  # type: ignore
    payload = queries._event_dict(event)
    payload["created"] = created
    return payload


def export_reviews(project_id: str | None, *, format: str) -> dict:
    _apply_scope(project_id)
    g6 = _g6()
    from osteopatch import queries  # type: ignore
    rows = queries.export_rows(g6.get_conn())
    return {"format": format, "count": len(rows), "rows": rows}
