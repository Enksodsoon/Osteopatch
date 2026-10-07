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

import base64
import json
from pathlib import Path

from fastapi import HTTPException, Response

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
        ) from exc


def backend_status() -> dict:
    try:
        _g6()
        return {"available": True}
    except HTTPException as exc:
        return {"available": False, "detail": exc.detail}


def g6_conn():
    """The G6 read-model connection, honouring the G6 ``set_conn`` test hook.

    Public so callers that legitimately share the read model (demo scoping,
    diagnostics) do not have to reach into a private module global.
    """
    return _g6().get_conn()


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
def list_images(project_id: str | None, *, sort: str, filt: str, page: int, page_size: int, q: str | None = None) -> dict:
    pid = _require_project(project_id)
    conn = _g6().get_conn()
    from osteopatch import queries  # type: ignore
    return queries.list_images(
        conn, sort=sort, filt=filt, q=q, page=page, page_size=page_size, project_id=pid
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

    from osteopatch.repo import ReviewError

    try:
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
    except ReviewError as exc:
        # The delegated G6 app's exception handlers do not run in this app.
        raise HTTPException(status_code=exc.http_status,
                            detail={"error": exc.message, **(exc.detail or {})}) from exc
    payload = queries._event_dict(event)
    payload["created"] = created
    return payload


def export_reviews(project_id: str | None, *, format: str) -> dict:
    pid = _require_project(project_id)
    from osteopatch import queries  # type: ignore
    rows = queries.export_rows(_g6().get_conn(), project_id=pid)
    return {"format": format, "count": len(rows), "rows": rows}


# ---------------------------------------------------------------------------
# Unified review surface (Phase 1)
#
# The G6 handlers are called directly rather than re-implemented, so the
# unified app cannot drift from the review API it fronts: one contract, one
# implementation. What this layer adds is TENANCY -- every one of these checks
# the image is inside the caller's project BEFORE the G6 handler runs, so a
# caller cannot read a neighbour's patch by guessing an image_id.
# ---------------------------------------------------------------------------
def _require_in_project(image_id: str, project_id: str) -> None:
    """Fail closed when the image is absent from the caller's project.

    404, not 403: telling "out of scope" apart from "does not exist" would let
    a tenant probe for another tenant's corpus.
    """
    from osteopatch import queries  # type: ignore

    if queries.get_image(_g6().get_conn(), image_id, project_id=project_id) is None:
        raise HTTPException(status_code=404, detail="unknown image_id (or out of project scope)")


def _unwrap(response: Response) -> tuple[bytes, dict[str, str]]:
    """Split a G6 handler result into (body, headers).

    G6 signals honest failure by RETURNING a JSONResponse (404 unknown image,
    400 bad class, 503 attribution runtime unavailable). That status is
    preserved verbatim rather than flattened, so a caller never sees a 200
    carrying an error body -- and never sees a fabricated image.
    """
    status = getattr(response, "status_code", 200)
    if status != 200:
        try:
            detail = json.loads(response.body)
        except Exception:  # pragma: no cover - defensive; body is our own JSON
            detail = {"error": "G6 handler failed", "status": status}
        raise HTTPException(status_code=status, detail=detail)
    return bytes(response.body), dict(response.headers)


def meta() -> dict:
    """Review contract: canonical classes, actions, attribution disclosure."""
    return _g6().meta()


def health() -> dict:
    """Read-model health: indexed images, prediction count, subset scoping."""
    return _g6().health()


def model_card() -> dict:
    """Frozen model card + the full limitations catalog."""
    return _g6().get_model_card()


def thumbnail_png(project_id: str | None, image_id: str) -> bytes:
    pid = _require_project(project_id)
    _require_in_project(image_id, pid)
    body, _ = _unwrap(_g6().get_thumbnail(image_id))
    return body


def full_png(project_id: str | None, image_id: str) -> bytes:
    pid = _require_project(project_id)
    _require_in_project(image_id, pid)
    body, _ = _unwrap(_g6().get_full(image_id))
    return body


def attribution_meta(project_id: str | None, image_id: str) -> dict:
    """Attribution availability + default contrastive pair, WITHOUT running the
    torch-loading CAM. Lets the UI render the panel and the recovery disclosure
    before the user asks for an overlay."""
    pid = _require_project(project_id)
    _require_in_project(image_id, pid)
    return _g6().get_attribution_meta(image_id)


def attribution_overlay(
    project_id: str | None,
    image_id: str,
    *,
    target_a: str | None = None,
    target_b: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    """Contrastive Grad-CAM overlay PNG plus the X-Attrib-* provenance headers.

    `target_a`/`target_b` default to the predicted class vs its runner-up,
    exactly as the G6 endpoint does. A 503 from G6 (torch absent, bundle hash
    mismatch) is passed through unchanged: attribution degrades honestly rather
    than returning a fabricated heatmap.
    """
    pid = _require_project(project_id)
    _require_in_project(image_id, pid)
    response = _g6().get_attribution(
        image_id, target_a=target_a, target_b=target_b, format="png"
    )
    return _unwrap(response)


def review_export_rows(project_id: str | None) -> list[dict]:
    """Raw export rows for this project. Serialisation lives in
    ``osteopatch.exports`` so both apps emit byte-identical downloads."""
    pid = _require_project(project_id)
    from osteopatch import queries  # type: ignore
    return queries.export_rows(_g6().get_conn(), project_id=pid)


def top_priority_image_ids(limit: int) -> list[str]:
    """The ``limit`` most review-priority images across the whole corpus.

    Unscoped on purpose: this reads the frozen read model to pick a demo scope,
    before any project owns those rows. Deterministic -- the ranking is a pure
    function of the frozen scores.
    """
    from osteopatch import queries  # type: ignore

    listing = queries.list_images(
        g6_conn(), sort="priority", filt="all", q=None, page=1,
        page_size=limit, project_id=None,
    )
    return [item["image_id"] for item in listing["items"]]


# ---------------------------------------------------------------------------
# Live inference (delegated down; torch stays lazy inside osteopatch)
#
# Same contract as the rest of this module: TENANCY is enforced HERE, before
# osteopatch does any work, and every honest failure (torch absent, bundle hash
# mismatch, undecodable upload, a slide too large to score fully) keeps its own
# status instead of being flattened into a generic error.
# ---------------------------------------------------------------------------
def _require_live_owner(run_id: str, project_id: str) -> dict:
    """404 unless this run belongs to the caller's project.

    A live run carries uploaded user bytes and its derived tiles. Leaking it
    across tenants is the same problem as leaking a corpus patch, so the answer
    is 404 either way.
    """
    from osteopatch import live_inference  # type: ignore

    run = live_inference.get_run(g6_conn(), run_id)
    if run is None or run["project_id"] != _require_project(project_id):
        raise HTTPException(status_code=404, detail="unknown live run")
    return run


def _live_error(exc: Exception) -> HTTPException:
    """Map an osteopatch live-inference failure onto an honest HTTP status."""
    from osteopatch import live_inference  # type: ignore

    if isinstance(exc, live_inference.UnsupportedInput):
        return HTTPException(status_code=422, detail={"error": str(exc)})
    if isinstance(exc, live_inference.LiveInferenceError):
        return HTTPException(status_code=503, detail={"error": str(exc)})
    return HTTPException(status_code=503, detail={"error": f"{type(exc).__name__}: {exc}"})


def _read_upload(filename: str, data: bytes) -> bytes:
    """Validate an upload's size and extension before any model work happens.

    Cheap rejections first: a 600 MB body should not cost a torch import.
    """
    from osteopatch import config as g6_config  # type: ignore

    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    if len(data) > g6_config.LIVE_MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "upload too large",
                "bytes": len(data),
                "limit_bytes": g6_config.LIVE_MAX_UPLOAD_BYTES,
            },
        )
    suffix = Path(filename or "").suffix.lower()
    if suffix not in g6_config.LIVE_ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": f"unsupported file type {suffix or '(none)'}",
                "allowed": list(g6_config.LIVE_ALLOWED_SUFFIXES),
            },
        )
    return data


def live_capability() -> dict:
    """Whether a live run can execute on this machine. Torch-free by design."""
    from osteopatch import config as g6_config  # type: ignore
    from osteopatch import live_inference  # type: ignore

    return {
        **live_inference.runtime_available(),
        "tile_px": g6_config.LIVE_TILE_PX,
        "max_tiles": g6_config.LIVE_MAX_TILES,
        "max_upload_bytes": g6_config.LIVE_MAX_UPLOAD_BYTES,
        "allowed_suffixes": list(g6_config.LIVE_ALLOWED_SUFFIXES),
    }


def live_predict_patch(project_id: str | None, filename: str, data: bytes, *, reviewer: str) -> dict:
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    payload = _read_upload(filename, data)
    try:
        return live_inference.predict_patch_bytes(
            g6_conn(), project_id=pid, filename=filename, data=payload,
            requested_by=reviewer,
        )
    except Exception as exc:
        raise _live_error(exc) from exc


def live_analyze_slide(
    project_id: str | None, filename: str, data: bytes, *, reviewer: str,
    tile_px: int | None = None, stride: int | None = None, max_tiles: int | None = None,
) -> dict:
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    payload = _read_upload(filename, data)
    try:
        return live_inference.analyze_slide_bytes(
            g6_conn(), project_id=pid, filename=filename, data=payload,
            requested_by=reviewer, tile_px=tile_px, stride=stride, max_tiles=max_tiles,
        )
    except Exception as exc:
        raise _live_error(exc) from exc


def live_run(project_id: str | None, run_id: str) -> dict:
    """A stored run plus its tiles. 404 across tenants, like every other read."""
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    run = _require_live_owner(run_id, pid)
    public = live_inference.public_run(g6_conn(), run_id)
    tiles = live_inference.get_tiles(g6_conn(), run_id)
    artifact_error = live_inference.verify_run_artifacts(run, tiles)
    if artifact_error:
        raise HTTPException(
            status_code=503,
            detail={"error": "recorded run artifacts are unavailable", "reason": artifact_error},
        )
    return {"run": public, "tiles": tiles, "n_tiles": len(tiles)}


def live_runs(project_id: str | None, limit: int = 50) -> list[dict]:
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    return live_inference.list_runs(g6_conn(), pid, limit=limit)


def live_mosaic(project_id: str | None, run_id: str) -> bytes:
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    _require_live_owner(run_id, pid)
    data = live_inference.mosaic_bytes(run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="no mosaic for this run (patch runs have none)")
    return data


def live_thumbnail(project_id: str | None, run_id: str) -> bytes:
    """Return the first real tile image for a project-scoped uploaded run."""
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    _require_live_owner(run_id, pid)
    tiles = live_inference.get_tiles(g6_conn(), run_id)
    tile = next((item for item in tiles if item.get("tile_png_filename")), None)
    if tile is None:
        raise HTTPException(status_code=404, detail="no tile image is available for this run")
    index = int(tile["tile_index"])
    if tile["tile_png_filename"] != f"tile-{index:04d}.png":
        raise HTTPException(status_code=503, detail="recorded tile filename is invalid")
    data = live_inference.tile_png_bytes(run_id, index)
    if data is None or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=503, detail="recorded tile image is unavailable")
    return data


def live_tile_attribution(
    project_id: str | None, run_id: str, tile_index: int,
    *, target_a: str | None = None, target_b: str | None = None,
) -> tuple[bytes, dict[str, str]]:
    """Contrastive Grad-CAM over one imported tile.

    Uses the same recovered head, hash guard and recovery disclosure as corpus
    attribution -- explaining a live tile must not be a weaker claim than
    explaining a corpus patch.
    """
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    _require_live_owner(run_id, pid)
    tile_path = live_inference.run_dir(run_id) / f"tile-{int(tile_index):04d}.png"
    if not tile_path.exists():
        raise HTTPException(status_code=404, detail="unknown tile index for this run")
    from osteopatch import attribution  # type: ignore

    try:
        result = attribution.compute_attribution(
            tile_path, f"{run_id}:tile-{int(tile_index):04d}",
            target_a or "NON_TUMOR", target_b or "VIABLE_TUMOR",
        )
    except Exception as exc:
        raise _live_error(exc) from exc
    return result.overlay_png, {
        "X-Attrib-Recovered-Model": attribution.RECOVERED_MODEL_ID,
        "X-Attrib-Run-Id": run_id,
        "X-Attrib-Tile-Index": str(tile_index),
        "X-Attrib-Target-A": result.target_a,
        "X-Attrib-Target-B": result.target_b,
    }


def live_delete_run(project_id: str | None, run_id: str) -> dict:
    """Delete a run and its uploaded bytes. A writer action: the user's data."""
    from osteopatch import live_inference  # type: ignore

    pid = _require_project(project_id)
    _require_live_owner(run_id, pid)
    conn = g6_conn()
    live_inference.delete_run(conn, run_id)
    return {"run_id": run_id, "deleted": True}


# ---------------------------------------------------------------------------
# Case reports (delegated down into osteopatch)
#
# Same contract as everything else in this module: tenancy is enforced HERE,
# before osteopatch does any work, and an honest failure keeps its own status.
#
# A report is APPEND-ONLY and lives in its own tables. Authoring one writes
# nothing to source_qc, prediction or review_event, so producing a document
# cannot alter what was reviewed or by whom. There is deliberately NO update
# route: a revised report is a new row.
# ---------------------------------------------------------------------------
def _require_report_owner(report_id: str, project_id: str) -> dict:
    """404 unless this report belongs to the caller's project."""
    conn = g6_conn()
    row = conn.execute(
        "SELECT report_id, project_id, case_id, title FROM case_report WHERE report_id = ?",
        (report_id,),
    ).fetchone()
    if row is None or row["project_id"] != _require_project(project_id):
        raise HTTPException(status_code=404, detail="unknown report")
    return dict(row)


def _report_error(exc: Exception) -> HTTPException:
    """Map an osteopatch reporting failure onto an honest HTTP status."""
    from osteopatch import reporting  # type: ignore

    if isinstance(exc, reporting.ReportScopeError):
        return HTTPException(status_code=404, detail={"error": str(exc)})
    if isinstance(exc, reporting.SignoffError):
        return HTTPException(status_code=422, detail={"error": str(exc)})
    if isinstance(exc, reporting.ReportError):
        return HTTPException(status_code=400, detail={"error": str(exc)})
    return HTTPException(status_code=503, detail={"error": f"{type(exc).__name__}: {exc}"})


def _report_preview_png(load) -> str | None:
    """Capture an available PNG as base64; missing pixels never block notes."""
    try:
        data = load()
    except (HTTPException, OSError):
        return None
    if not data or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    return base64.b64encode(data).decode("ascii")


def _collect_report_images(image_ids: list[str], run_ids: list[str], slide_ids: list[str], project_id: str) -> list[dict]:
    """Gather teaching patches, analyzed runs, and uploaded images for a report.

    A report may span corpus patches and imported live tiles. Both are read here
    and copied into the document at write time, so the exported file stays
    reproducible even if the source store later changes. An id that is unknown
    — or belongs to another project — is a 404, never a silently skipped row.
    """
    pid = _require_project(project_id)
    conn = g6_conn()
    out: list[dict] = []
    live_ids = [r for r in run_ids if r]

    for image_id in image_ids or []:
        row = conn.execute(
            """SELECT s.image_id, s.source_group, p.predicted_class,
                      p.top_two_margin, p.non_tumor_score, p.viable_tumor_score,
                      p.necrosis_score, p.model_bundle_hash,
                      (SELECT COUNT(*) FROM review_event e WHERE e.image_id = s.image_id)
                        AS n_reviews
               FROM source_qc s
               LEFT JOIN prediction p ON p.image_id = s.image_id
              WHERE s.image_id = ? AND s.project_id IN (?, '__default__')""",
            (image_id, pid),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"unknown image: {image_id}")
        out.append({
            "image_id": row["image_id"],
            "source_kind": "corpus",
            "run_id": None,
            "predicted_class": row["predicted_class"],
            # A frozen corpus row carries a margin but no confidence band, so
            # reporting.py decides from the margin.
            "confidence": None,
            "top_two_margin": row["top_two_margin"],
            "scores": None if row["predicted_class"] is None else {
                "NON_TUMOR": row["non_tumor_score"],
                "VIABLE_TUMOR": row["viable_tumor_score"],
                "NECROSIS": row["necrosis_score"],
            },
            "corroborated": bool(row["n_reviews"]),
            "preview_png_base64": _report_preview_png(lambda image_id=image_id: thumbnail_png(pid, image_id)),
        })

    for run_id in live_ids:
        from osteopatch import live_inference  # type: ignore

        run = live_inference.get_run(conn, run_id)
        if run is None or run["project_id"] != pid:
            raise HTTPException(status_code=404, detail=f"unknown live run: {run_id}")
        tiles = live_inference.get_tiles(conn, run_id)
        preview = None
        if tiles:
            first = tiles[0]
            index = int(first["tile_index"])
            if first.get("tile_png_filename") == f"tile-{index:04d}.png":
                preview = _report_preview_png(
                    lambda run_id=run_id, index=index: live_inference.tile_png_bytes(run_id, index)
                )
        for t in tiles:
            out.append({
                "image_id": f"{run_id}#tile-{int(t['tile_index']):04d}",
                "source_kind": "live",
                "run_id": run_id,
                "predicted_class": t["predicted_class"],
                "confidence": t["confidence"],
                "top_two_margin": t["top_two_margin"],
                "scores": t["scores"],
                "corroborated": False,
                "preview_png_base64": preview if int(t["tile_index"]) == int(tiles[0]["tile_index"]) and tiles else None,
            })

    if slide_ids:
        from . import slides as slide_store

        for slide_id in slide_ids:
            meta = slide_store.get(pid, slide_id)
            out.append({
                "image_id": f"slide:{slide_id}",
                "source_kind": "slide",
                "analysis_status": "not_analyzed",
                "run_id": None,
                "predicted_class": None,
                "confidence": None,
                "top_two_margin": None,
                "scores": None,
                "caveat": f"{meta['filename']} was included without an AI run. No model result is attached.",
                "preview_png_base64": _report_preview_png(
                    lambda slide_id=slide_id: slide_store.preview(pid, slide_id)
                ),
            })
    return out


def create_report(
    project_id: str | None,
    *,
    case_id: str,
    title: str,
    findings_text: str,
    findings_html: str | None,
    image_ids: list[str],
    run_ids: list[str] | None,
    slide_ids: list[str] | None,
    revision_of: str | None,
    author: str,
    signer_email: str | None,
    signer_role: str | None,
    signoff_note: str | None,
) -> dict:
    """Author (and optionally sign) an append-only case report."""
    from osteopatch import reporting  # type: ignore

    pid = _require_project(project_id)
    if revision_of:
        _require_report_owner(revision_of, pid)
    images = _collect_report_images(image_ids or [], run_ids or [], slide_ids or [], pid)
    if not images:
        raise HTTPException(
            status_code=400,
            detail={"error": "a report must include at least one item"},
        )
    try:
        doc = reporting.draft_document(
            project_id=pid,
            case_id=case_id,
            title=title,
            findings_text=findings_text,
            findings_html=findings_html,
            revision_of=revision_of,
            author_email=author,
            images=images,
            signer_email=signer_email,
            signer_role=signer_role,
            signoff_note=signoff_note,
        )
        return reporting.store_document(g6_conn(), doc)
    except Exception as exc:
        raise _report_error(exc) from exc


def list_reports(project_id: str | None, limit: int = 50) -> list[dict]:
    from osteopatch import reporting  # type: ignore

    return reporting.list_reports(g6_conn(), _require_project(project_id), limit=limit)


def get_report(project_id: str | None, report_id: str) -> dict:
    from osteopatch import reporting  # type: ignore

    _require_report_owner(report_id, project_id)
    doc = reporting.load_document(g6_conn(), report_id)
    payload = reporting.public_report(doc)
    payload["hash_verification"] = reporting.verify_hash(g6_conn(), report_id)
    return payload


def render_report_export(project_id: str | None, report_id: str, fmt: str) -> tuple[bytes, str]:
    """Return ``(bytes, media_type)`` for one export format.

    Both formats render from the SAME loaded typed document, which is what makes
    it impossible for them to disagree.
    """
    from osteopatch import reporting  # type: ignore

    _require_report_owner(report_id, project_id)
    doc = reporting.load_document(g6_conn(), report_id)
    if fmt == "md":
        return doc.to_markdown().encode("utf-8"), "text/markdown; charset=utf-8"
    if fmt == "html":
        return doc.to_html().encode("utf-8"), "text/html; charset=utf-8"
    raise HTTPException(status_code=404, detail=f"unknown export format: {fmt}")
