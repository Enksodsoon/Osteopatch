"""Read queries for the gallery, patch detail, and exports.

All reads join the three concepts WITHOUT collapsing them: the immutable
prediction, the source/QC metadata, and the current (latest) review state are
returned as distinct fields. Exports preserve BOTH the original model
prediction AND the human correction, plus the disclaimer.

Centralized scope (F003)
------------------------
Every row-returning function here answers from **one** selection:
:func:`osteopatch.scope.resolve_prediction_rows`. The gallery, the detail view,
the review-priority ranks, the search and the export therefore see the same
intersection of project, dataset version, deployment allowlist and model hash,
and ``total``/ranks can no longer describe a wider set than the caller may read.

What this replaced
------------------
* ``_base_select()`` joined ``prediction`` on ``image_id`` alone, so a second
  model bundle produced a second gallery card and an inflated total. The join is
  now model-scoped.
* the gallery ranked with ``_priority_rank_map(conn)`` - no ``project_id`` -
  while the detail view passed one, so the same image got different rank
  numbers per endpoint and the gallery's numbering counted other tenants' rows.
  Ranks are now derived from the selected rows, so they cannot disagree with the
  list they annotate.
* the deployment allowlist was applied at four call sites by three mechanisms.
  It is now one field on the scope object.

Compatibility adapters (documented, not accidental)
---------------------------------------------------
``project_id=`` is still accepted and means exactly what it meant before F003:
a project filter with no declared dataset version. :func:`scope_for_request` -
the server-side entry point - always declares the legacy dataset version, so the
deployed path applies the full four-way intersection. On the real corpus the
adapter is a no-op, because the manifest's ``image_id`` set is exactly the
store's (1,144 of 1,144); it only differs for synthetic corpora that are not in
the ingestion manifest, which is what the pre-existing isolation tests build.

Review state: an explicit adaptation
-----------------------------------
``review_store`` is image-global: ``latest_event`` returns the newest event for
an image regardless of which prediction it was recorded against. For a
model-scoped read that is wrong - an event on the other model must not mark the
selected model reviewed. ``_model_scoped_review_state`` therefore keeps the
store's **revision** (the optimistic-concurrency token, which
``repo.submit_review`` computes image-globally and which must stay that way) but
replaces the **latest event** with the newest event that actually references the
selected ``prediction_id``. Nothing is hidden: ``get_image`` still returns the
full append-only history.

Nothing in this module is a biological or clinical claim. Model scores are
uncalibrated class scores, never disease probabilities.
"""
from __future__ import annotations

import sqlite3

from . import config, review_store
from . import scope as scope_mod
from .scope import ScopeContext

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


def _resolve_scope(
    scope: ScopeContext | None,
    project_id: str | None,
    model_bundle_hash: str | None = None,
    deployment_allowlist: frozenset[str] | None = None,
    review_session_id: str | None = None,
    actor_id: str | None = None,
) -> ScopeContext:
    """Normalize ``scope`` / ``project_id`` into exactly one ScopeContext.

    Fails closed on an ambiguous request: if a caller passes both a scope and a
    ``project_id`` that disagrees, guessing which one wins could read another
    tenant's rows, so it is an error instead.
    """
    if scope is not None:
        if project_id is not None and scope.project_id != project_id:
            raise ValueError(
                f"ambiguous scope: scope.project_id={scope.project_id!r} disagrees "
                f"with project_id={project_id!r}; refusing to choose"
            )
        return scope
    # Legacy adapter: project filter with no declared dataset version.
    if project_id is not None:
        return ScopeContext(
            project_id=project_id,
            dataset_version_id=None,
            dataset_image_ids=None,
            model_bundle_hash=model_bundle_hash or scope_mod.active_model_bundle_hash(),
            deployment_allowlist=deployment_allowlist,
            review_session_id=review_session_id,
            actor_id=actor_id,
            mode=scope_mod.MODE_PROJECT_ONLY,
        )
    return ScopeContext(
        project_id=None,
        dataset_version_id=None,
        dataset_image_ids=None,
        model_bundle_hash=model_bundle_hash or scope_mod.active_model_bundle_hash(),
        deployment_allowlist=deployment_allowlist
        if deployment_allowlist is not None
        else config.load_image_allowlist(),
        review_session_id=review_session_id,
        actor_id=actor_id,
        mode=scope_mod.MODE_LOCAL_SINGLE_USER,
    )


def _review_status_filter(image: dict, filt: str) -> bool:
    st = image["review_state"]["status"]
    if filt == "unreviewed":
        return st == "unreviewed"
    if filt == "reviewed":
        return st == "reviewed"
    if filt == "deferred":
        return st == "deferred"
    return True


def _to_image_dict(
    row: scope_mod.SelectedPredictionRow,
    review_state: dict,
    unavailable_reason: str | None = None,
) -> dict:
    """The gallery/detail image payload.

    Field names are unchanged from the pre-F003 response shape; only the way the
    prediction is chosen changed.
    """
    latest = review_state["latest"]
    reason = row.unavailable_reason if unavailable_reason is None else unavailable_reason
    return {
        "image_id": row.image_id,
        "source_group": row.source_group,
        "qc": {
            "primary_qc_status": row.primary_qc_status,
            "training_eligible": bool(row.training_eligible),
            "qc_review_flag": bool(row.qc_review_flag),
            "qc_review_reason": row.qc_review_reason,
            "original_label": row.original_label,
        },
        "prediction": None if row.prediction_id is None else {
            "prediction_id": row.prediction_id,
            "predicted_class": row.predicted_class,
            "model_version": row.model_version,
            "model_bundle_hash": row.model_bundle_hash,
            "inference_kind": row.inference_kind,
            "scores": {
                "NON_TUMOR": row.non_tumor_score,
                "VIABLE_TUMOR": row.viable_tumor_score,
                "NECROSIS": row.necrosis_score,
            },
            "score_label": "Model score — uncalibrated",
            "top1_score": row.top1_score,
            "top_two_margin": row.top_two_margin,
            "normalized_entropy": row.normalized_entropy,
        },
        "prediction_unavailable_reason": reason,
        "review_state": {
            "status": review_store.review_status(latest),
            "revision": review_state["revision"],
            "latest_action": None if latest is None else latest["action"],
            "selected_class": None if latest is None else latest["selected_class"],
        },
    }


def _model_scoped_review_state(
    conn: sqlite3.Connection, rows: list[scope_mod.SelectedPredictionRow]
) -> dict[str, dict]:
    """Review state per in-scope image, adapted to the selected model.

    ``review_store`` is image-global, and that is correct for the *revision*
    token (``repo.submit_review`` compares against the image-global maximum, so
    a model-scoped revision would invite 409s on a legitimate write). It is
    wrong for the *status*: an event recorded against another model's
    prediction must not mark the selected model reviewed.

    So: the revision is passed through untouched, and the latest event is
    replaced by the newest event that references the selected ``prediction_id``.
    The full append-only history remains available through ``get_image``.
    """
    selected = {r.image_id: r.prediction_id for r in rows if r.prediction_id is not None}
    index = review_store.load_all_review_state(conn)
    out: dict[str, dict] = {}
    for row in rows:
        entry = index.get(row.image_id)
        latest = entry["latest"] if entry else None
        wanted = selected.get(row.image_id)
        if latest is not None and wanted is not None:
            if latest["prediction_id"] != wanted:
                latest = _latest_event_for_prediction(conn, row.image_id, wanted)
        elif latest is not None and wanted is None:
            # In scope but nothing selected for this model: an event cannot be
            # about a prediction that does not exist in this scope.
            latest = None
        out[row.image_id] = {
            "latest": latest,
            "revision": (entry["revision"] if entry else 0),
        }
    return out


def _latest_event_for_prediction(
    conn: sqlite3.Connection, image_id: str, prediction_id: str
):
    """The newest event on ``prediction_id``, or None.

    Append-only history means "newest" is the highest revision that references
    this prediction; no event is ever rewritten or removed by this lookup.
    """
    return conn.execute(
        "SELECT * FROM review_event WHERE image_id = ? AND prediction_id = ? "
        "ORDER BY revision_number DESC LIMIT 1",
        (image_id, prediction_id),
    ).fetchone()


def _rank_map_from_rows(rows: list[scope_mod.SelectedPredictionRow]) -> dict[str, int]:
    """Deterministic review-priority rank over the SELECTED rows only.

    Derived from the same list the gallery pages, so a rank can never describe a
    wider population than the caller is shown.
    """
    from .scoring import review_priority_key

    # A row is rankable only if it has a prediction AND both score summaries:
    # ranking on a missing value would be ranking on absence. The narrowed
    # triples are what the key function sees, so the values it receives are
    # floats rather than `float | None`.
    rankable: list[tuple[float, float, str]] = [
        (r.top_two_margin, r.normalized_entropy, r.image_id)
        for r in rows
        if r.prediction_id is not None
        and r.top_two_margin is not None
        and r.normalized_entropy is not None
    ]
    rankable.sort(key=lambda t: review_priority_key(t[0], t[1], t[2]))
    return {image_id: i + 1 for i, (_m, _e, image_id) in enumerate(rankable)}


def priority_rank_map(
    conn: sqlite3.Connection,
    scope: ScopeContext | None = None,
    project_id: str | None = None,
    model_bundle_hash: str | None = None,
) -> dict[str, int]:
    """``{image_id: rank}`` within the resolved scope, for predicted images."""
    resolved = _resolve_scope(scope, project_id, model_bundle_hash)
    return _rank_map_from_rows(scope_mod.resolve_prediction_rows(conn, resolved))


def _priority_rank_map(
    conn: sqlite3.Connection, project_id: str | None = None
) -> dict[str, int]:
    """Compatibility wrapper for the pre-F003 private name.

    Kept because an existing isolation regression calls it positionally. It now
    routes through the same selection as every other read, so it is scoped by
    construction rather than by remembering to pass an argument.
    """
    return priority_rank_map(conn, project_id=project_id)


def list_images(
    conn: sqlite3.Connection,
    sort: str = "priority",
    filt: str = "all",
    q: str | None = None,
    page: int = 1,
    page_size: int = 50,
    project_id: str | None = None,
    scope: ScopeContext | None = None,
    model_bundle_hash: str | None = None,
    deployment_allowlist: frozenset[str] | None = None,
    review_session_id: str | None = None,
    actor_id: str | None = None,
) -> dict:
    """The gallery page for one resolved scope.

    Scope is applied first and in SQL, so ``total``, the ranks and the page all
    describe exactly the rows the caller may read.
    """
    sort = sort if sort in SORTABLE else "priority"
    filt = filt if filt in FILTERS else "all"

    # Defensive clamp: the HTTP layer already enforces page>=1 and
    # 1<=page_size<=500, but list_images is also called directly (tests, future
    # callers). Clamp here so a bad page/page_size can never produce a negative
    # slice start or an unbounded page.
    page = max(1, int(page))
    page_size = min(500, max(1, int(page_size)))

    resolved = _resolve_scope(
        scope, project_id, model_bundle_hash, deployment_allowlist,
        review_session_id, actor_id,
    )
    # One selection, reused: `scoped_rows` is the authorized universe, and the
    # ranks below must describe that universe rather than the filtered page.
    scoped_rows = scope_mod.resolve_prediction_rows(conn, resolved)
    rows = list(scoped_rows)

    # Search is applied to the ALREADY-scoped rows, never to widen them.
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in r.image_id.lower()]

    # Class filters target the selected model's prediction only.
    if filt in ("pred_NON_TUMOR", "pred_VIABLE_TUMOR", "pred_NECROSIS"):
        wanted = filt.replace("pred_", "")
        rows = [r for r in rows if r.predicted_class == wanted]

    review_state = _model_scoped_review_state(conn, rows)
    images = [_to_image_dict(r, review_state[r.image_id]) for r in rows]

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

    # Ranks come from the same scoped selection as the list itself, so they can
    # never count another project's images (the pre-F003 gallery rank ignored
    # project_id entirely while the detail view honoured it).
    rank_map = _rank_map_from_rows(scoped_rows)
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


def get_image(
    conn: sqlite3.Connection,
    image_id: str,
    project_id: str | None = None,
    scope: ScopeContext | None = None,
    model_bundle_hash: str | None = None,
    deployment_allowlist: frozenset[str] | None = None,
    review_session_id: str | None = None,
    actor_id: str | None = None,
) -> dict | None:
    """One image within scope, or ``None``.

    ``None`` covers "does not exist", "another project" and "outside the
    deployment allowlist" alike, on purpose: distinguishing them would let a
    tenant probe for another tenant's data.
    """
    resolved = _resolve_scope(
        scope, project_id, model_bundle_hash, deployment_allowlist,
        review_session_id, actor_id,
    )
    rows = scope_mod.resolve_prediction_rows(conn, resolved)
    match = next((r for r in rows if r.image_id == image_id), None)
    if match is None:
        return None
    image = _to_image_dict(match, _model_scoped_review_state(conn, [match])[match.image_id])
    image["review_priority_rank"] = _rank_map_from_rows(rows).get(image_id)
    image["history"] = [
        _event_dict(e) for e in review_store.event_history(conn, image_id)
    ]
    return image


def _event_dict(e) -> dict:
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


def export_rows(
    conn: sqlite3.Connection,
    project_id: str | None = None,
    scope: ScopeContext | None = None,
    model_bundle_hash: str | None = None,
    deployment_allowlist: frozenset[str] | None = None,
    review_session_id: str | None = None,
    actor_id: str | None = None,
) -> list[dict]:
    """One row per image in scope that has a prediction for the selected model.

    Preserving the ORIGINAL model prediction AND the current human review state
    AND full history refs. The scope travels with the rows (as
    ``scope_provenance``) so an exported file records which project, dataset
    version and model produced it.
    """
    resolved = _resolve_scope(
        scope, project_id, model_bundle_hash, deployment_allowlist,
        review_session_id, actor_id,
    )
    rows = [r for r in scope_mod.resolve_prediction_rows(conn, resolved)
            if r.prediction_id is not None]
    review_state = _model_scoped_review_state(conn, rows)
    provenance = resolved.provenance()

    out = []
    for r in rows:
        state = review_state[r.image_id]
        latest = state["latest"]
        status = review_store.review_status(latest)
        history = review_store.event_history(conn, r.image_id)
        out.append(
            {
                "image_id": r.image_id,
                "source_group": r.source_group,
                "qc_primary_status": r.primary_qc_status,
                "training_eligible": bool(r.training_eligible),
                "qc_review_flag": bool(r.qc_review_flag),
                # ORIGINAL model prediction (immutable) ----------------------
                "model_version": r.model_version,
                "model_bundle_hash": r.model_bundle_hash,
                "inference_kind": r.inference_kind,
                "model_predicted_class": r.predicted_class,
                "model_score_NON_TUMOR": r.non_tumor_score,
                "model_score_VIABLE_TUMOR": r.viable_tumor_score,
                "model_score_NECROSIS": r.necrosis_score,
                "model_score_label": "Model score — uncalibrated",
                "top_two_margin": r.top_two_margin,
                "normalized_entropy": r.normalized_entropy,
                # HUMAN review (append-only) ---------------------------------
                "human_review_status": status,
                "human_latest_action": None if latest is None else latest["action"],
                "human_corrected_class": (
                    latest["selected_class"]
                    if latest and latest["action"] == "CORRECT"
                    else None
                ),
                "human_defer_reason": (
                    latest["reason"] if latest and latest["action"] == "DEFER" else None
                ),
                "human_note": None if latest is None else latest["note"],
                "human_reviewer": None if latest is None else latest["reviewer"],
                "human_revision_number": state["revision"],
                "review_event_count": len(history),
                "review_event_ids": "|".join(e["review_event_id"] for e in history),
                "scope_provenance": provenance,
                "disclaimer": config.DISCLAIMER,
            }
        )
    return out
