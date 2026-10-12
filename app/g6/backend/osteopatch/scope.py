"""Centralized authorization scope and explicit prediction selection.

F003. This module owns ONE question: *given a verified request, which rows may
this caller see?* Every gallery, detail, rank, search, export and count answer
must come from the same intersection, computed once.

Why this exists
---------------
``queries.py`` applied scope in four places by three mechanisms, and two of
them were wrong in ways today's data could not expose:

  * the gallery built its review-priority ranks with ``_priority_rank_map(conn)``
    and no ``project_id``, while the detail view passed one. The same image
    therefore got different rank numbers depending on which endpoint the tenant
    read, and the gallery's numbering counted other tenants' images.
  * ``model_bundle_hash`` appeared in the SELECT list and in the output dict and
    in NO WHERE clause. There was no way to ask for "this model's prediction".
  * the join was ``LEFT JOIN prediction p ON p.image_id = s.image_id``. Prediction
    identity is ``(image_id, model_bundle_hash)``, so a second bundle silently
    produced a second gallery card and an inflated total.

The real corpus has exactly one model bundle and one project, so both defects
were latent. They become live the moment a second bundle exists.

The rules this module enforces
------------------------------
1. **Exactly one prediction row per image, for one explicit model.** The model
   hash is part of the join, not a display field.
2. **The intersection happens before counting, ranking, paging or searching.**
   Project, dataset version, deployment allowlist and model hash are applied in
   the WHERE clause, so ``total`` and ranks cannot leak what a caller may not
   read.
3. **An empty intersection is an empty authorized result.** It never degrades
   into an unscoped read.
4. **Duplicates are an error, not a choice.** A store that violates
   ``UNIQUE (image_id, model_bundle_hash)`` raises
   :class:`PredictionSelectionIntegrityError` rather than picking the newest or
   the first row.
5. **Absent data is null plus a reason,** never zero and never another model's
   prediction.
6. **Nothing here mutates process-global state.** The deployment allowlist is
   carried on the scope object; the module-level cache in ``config`` is read but
   never written, so two concurrent requests for different projects cannot
   observe each other.

Relationship to what already existed
------------------------------------
``projects.py`` remains the tenancy model (grants, membership, fail-closed
unknown ids) and is used, not reimplemented. ``config.load_image_allowlist()``
remains the deployment-subset source and is read, not replaced. Before D001
introduces dataset tables, the only dataset version is the *legacy* one below;
D001 later supplies an additive stable mapping.

Nothing in this module is a biological or clinical claim. Model scores are
uncalibrated class scores, never disease probabilities.
"""
from __future__ import annotations

import csv
import hashlib
import sqlite3
from dataclasses import dataclass, field

from . import config

#: Prefix of the pre-D001 dataset version identifier.
LEGACY_DATASET_PREFIX = "legacy-ingestion-manifest:sha256:"


class ScopeError(RuntimeError):
    """Base class for scope failures. Every subclass fails closed."""


class DatasetUnavailable(ScopeError):
    """A dataset version was named but its membership cannot be established.

    Raised instead of falling back to "no restriction", which would silently
    widen a tenant's scope to the whole store.
    """


class PredictionSelectionIntegrityError(ScopeError):
    """More than one prediction row for one (image_id, model_bundle_hash).

    The selection must never resolve this by choosing a row: a duplicate means
    the store is corrupt or predates the uniqueness constraint, and any pick
    would be arbitrary.
    """


# ---------------------------------------------------------------------------
# The legacy dataset version (pre-D001)
# ---------------------------------------------------------------------------


def legacy_manifest_sha256() -> str:
    """SHA-256 of the verified, immutable ingestion manifest.

    Read from disk on every call rather than hardcoded, so a replaced manifest
    yields a different dataset identity instead of silently inheriting this
    one's membership.
    """
    path = config.INGESTION_MANIFEST
    if not path.is_file():
        raise DatasetUnavailable(
            f"ingestion manifest not found at {path}; the legacy dataset version "
            "cannot be established (refusing to treat the corpus as unrestricted)"
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy_dataset_version_id() -> str:
    """The legacy dataset version id, derived from the manifest SHA-256.

    The identifier *is* the content digest, so membership and identity cannot
    drift apart: change the manifest and both change together.
    """
    return f"{LEGACY_DATASET_PREFIX}{legacy_manifest_sha256()}"


def legacy_dataset_image_ids() -> frozenset[str]:
    """Membership of the legacy dataset: the manifest's ``image_id`` values.

    Taken from the manifest column, never from filenames and never from
    whatever happens to be in the database.
    """
    path = config.INGESTION_MANIFEST
    if not path.is_file():
        raise DatasetUnavailable(
            f"ingestion manifest not found at {path}; legacy dataset membership "
            "is unavailable (refusing to invent membership)"
        )
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "image_id" not in reader.fieldnames:
            raise DatasetUnavailable(
                f"ingestion manifest at {path} has no 'image_id' column "
                f"(found: {reader.fieldnames!r})"
            )
        return frozenset(row["image_id"] for row in reader if row.get("image_id"))


def active_model_bundle_hash() -> str:
    """The single active deployment identity for this prototype.

    This is the frozen G4 bundle hash from :mod:`osteopatch.config` - the single
    source of truth for model identity, reused rather than duplicated. The real
    enterprise deployment registry (E5, ``model:manage``) will supply this per
    deployment; until then the frozen contract constant is the honest answer,
    and it is the value every server-resolved scope uses.
    """
    return config.EXPECTED_BUNDLE_SHA256


# ---------------------------------------------------------------------------
# The scope itself
# ---------------------------------------------------------------------------

#: A scope resolved for a specific, authenticated, project-scoped request.
MODE_SCOPED = "scoped"

#: The explicitly-local loopback single-user mode. The only mode permitted to
#: omit a project, and the only mode permitted to omit a dataset version.
#: Never reachable from a browser-provided flag: ``queries`` builds it only when
#: no project is supplied, and the G6 app binds 127.0.0.1 only.
MODE_LOCAL_SINGLE_USER = "local_single_user"

#: Compatibility mode for the pre-F003 ``project_id=`` library argument: a
#: project filter with NO declared dataset version, i.e. exactly the semantics
#: ``queries.list_images(project_id=...)`` had before F003. It exists so the
#: existing isolation regressions keep their meaning, and it is a strict subset of
#: the full contract: project, model and allowlist are all still applied.
#: :func:`scope_for_request` - the server-side entry point - never produces it,
#: so no deployed request can reach a read without a dataset version.
MODE_PROJECT_ONLY = "project_only"

MODES = (MODE_SCOPED, MODE_LOCAL_SINGLE_USER, MODE_PROJECT_ONLY)


@dataclass(frozen=True)
class ScopeContext:
    """An immutable, server-resolved authorization scope.

    Frozen on purpose: a scope that a request handler could mutate partway
    through would defeat the point of computing the intersection once.

    Parameters
    ----------
    project_id:
        The owning project. ``None`` is legal **only** in
        :data:`MODE_LOCAL_SINGLE_USER`. A blank string is always rejected - it
        would otherwise select the rows whose ``project_id`` is ``''``.
    dataset_version_id:
        Which dataset version this read is about. ``None`` means "no dataset
        restriction is declared", which is legal only in local single-user mode.
        The pre-D001 value is :func:`legacy_dataset_version_id`.
    dataset_image_ids:
        Membership of that dataset version, resolved server-side. ``None`` means
        "resolve it from ``dataset_version_id``"; for the legacy version that is
        the manifest's ``image_id`` column. Never populated from a query string.
    model_bundle_hash:
        The explicit model whose predictions are selected. Required, because an
        analysis must never silently mix model versions.
    deployment_allowlist:
        The deployed demo subset. ``None`` means no deployment restriction (local
        dev). This is carried per-scope precisely so that scoping one project
        never requires editing a process-global allowlist.
    review_session_id, actor_id:
        Provenance carried alongside the scope so an event, a cache key or an
        export can be attributed to the session and actor that produced it.
    """

    project_id: str | None = None
    dataset_version_id: str | None = None
    dataset_image_ids: frozenset[str] | None = None
    model_bundle_hash: str = ""
    deployment_allowlist: frozenset[str] | None = None
    review_session_id: str | None = None
    actor_id: str | None = None
    mode: str = MODE_SCOPED
    _cache_key: str | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if not self.model_bundle_hash or not self.model_bundle_hash.strip():
            raise ValueError(
                "model_bundle_hash is required and must be non-empty: an analysis "
                "must select one explicit model, never mix model versions"
            )
        if self.project_id is not None and not str(self.project_id).strip():
            raise ValueError("project_id must be a non-empty string or None")
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")
        if self.mode == MODE_LOCAL_SINGLE_USER:
            if self.project_id is not None:
                raise ValueError(
                    "local single-user mode must not carry a project_id; a scoped "
                    "read must use MODE_SCOPED"
                )
        else:
            # Both MODE_SCOPED and MODE_PROJECT_ONLY are project-scoped.
            if self.project_id is None:
                raise ValueError(
                    "a scoped read requires a project_id; null project scope is "
                    "permitted only in explicitly-local single-user mode"
                )
            if self.dataset_version_id is None and self.mode == MODE_SCOPED:
                raise ValueError(
                    "a scoped read requires a dataset_version_id; D001 will supply "
                    "an additive stable mapping, and until then the legacy manifest "
                    "dataset is the only dataset"
                )
        # Normalise the allowlist and membership to genuine frozensets so an
        # equal-but-differently-typed pair cannot produce two cache keys.
        if self.deployment_allowlist is not None:
            object.__setattr__(
                self, "deployment_allowlist", frozenset(self.deployment_allowlist)
            )
        if self.dataset_image_ids is not None:
            object.__setattr__(
                self, "dataset_image_ids", frozenset(self.dataset_image_ids)
            )

    # -- derived ----------------------------------------------------------
    @property
    def effective_dataset_image_ids(self) -> frozenset[str] | None:
        """Membership to intersect against, resolving the legacy version lazily.

        ``None`` means "no dataset restriction declared", which is legal only in
        local single-user mode. A named version whose membership cannot be
        established raises rather than degrading to unrestricted.
        """
        if self.dataset_image_ids is not None:
            return self.dataset_image_ids
        if self.dataset_version_id is None:
            return None
        if self.dataset_version_id.startswith(LEGACY_DATASET_PREFIX):
            return legacy_dataset_image_ids()
        raise DatasetUnavailable(
            f"unknown dataset_version_id {self.dataset_version_id!r} with no "
            "explicit membership; refusing to widen the scope to the whole store"
        )

    @property
    def is_local_single_user(self) -> bool:
        return self.mode == MODE_LOCAL_SINGLE_USER

    @property
    def cache_key(self) -> str:
        """A stable digest of every field that can change the authorized result.

        Any cache keyed on rows must key on this instead, so a project, model,
        allowlist or session change cannot serve another scope's rows. The
        allowlist and dataset membership contribute by digest rather than by
        value, so a 1,144-id allowlist does not make the key unreadable.
        """
        cached = self._cache_key
        if cached is None:
            parts = [
                self.mode,
                self.project_id or "",
                self.dataset_version_id or "",
                self.model_bundle_hash,
                self.review_session_id or "",
                self.actor_id or "",
                _digest_of(self.effective_dataset_image_ids),
                _digest_of(self.deployment_allowlist),
            ]
            joined = "\x1f".join(parts)
            cached = hashlib.sha256(joined.encode("utf-8")).hexdigest()
            object.__setattr__(self, "_cache_key", cached)
        return cached

    def provenance(self) -> dict:
        """The scope as data, for an export header or a response envelope."""
        return {
            "mode": self.mode,
            "project_id": self.project_id,
            "dataset_version_id": self.dataset_version_id,
            "model_bundle_hash": self.model_bundle_hash,
            "review_session_id": self.review_session_id,
            "actor_id": self.actor_id,
            "deployment_allowlist_size": (
                None
                if self.deployment_allowlist is None
                else len(self.deployment_allowlist)
            ),
            "cache_key": self.cache_key,
        }


def _digest_of(values: frozenset[str] | None) -> str:
    if values is None:
        return "-"
    joined = "\x1e".join(sorted(values))
    return f"{len(values)}:{hashlib.sha256(joined.encode('utf-8')).hexdigest()}"


# ---------------------------------------------------------------------------
# The selected row
# ---------------------------------------------------------------------------

#: Reason recorded when an image is in scope but has no prediction for the
#: selected model. Distinct from "no prediction for any model", because the
#: contract forbids borrowing the other model's answer.
REASON_NO_PREDICTION_FOR_MODEL = (
    "no prediction for the selected model_bundle_hash (the image is in scope; "
    "another model's prediction exists but must not be substituted)"
)


@dataclass(frozen=True)
class SelectedPredictionRow:
    """One image, its source/QC metadata, and at most one selected prediction.

    Frozen, and carrying the scope's model identity on every row, so a row
    cannot be passed between scopes without the mismatch being visible.
    """

    image_id: str
    source_group: str | None
    primary_qc_status: str | None
    training_eligible: bool
    qc_review_flag: bool
    qc_review_reason: str | None
    original_label: str | None
    project_id: str | None
    model_bundle_hash: str
    prediction_id: str | None
    predicted_class: str | None
    model_version: str | None
    inference_kind: str | None
    non_tumor_score: float | None
    viable_tumor_score: float | None
    necrosis_score: float | None
    top1_score: float | None
    top_two_margin: float | None
    normalized_entropy: float | None
    unavailable_reason: str | None = None

    @property
    def has_prediction(self) -> bool:
        return self.prediction_id is not None


#: Columns selected for every image in scope, with the model-scoped prediction.
_SELECT_SQL = """
    SELECT s.image_id, s.source_group, s.primary_qc_status, s.training_eligible,
           s.qc_review_flag, s.qc_review_reason, s.original_label, s.project_id,
           p.prediction_id, p.predicted_class, p.model_version, p.inference_kind,
           p.model_bundle_hash, p.non_tumor_score, p.viable_tumor_score,
           p.necrosis_score, p.top1_score, p.top_two_margin, p.normalized_entropy
    FROM source_qc s
    LEFT JOIN prediction p
           ON p.image_id = s.image_id
          AND p.model_bundle_hash = ?
    WHERE 1 = 1
"""


def resolve_prediction_rows(
    conn: sqlite3.Connection, scope: ScopeContext
) -> list[SelectedPredictionRow]:
    """The authorized rows for ``scope``: exactly one per image, one model.

    Project membership, dataset version, deployment allowlist and model hash are
    intersected **in the WHERE clause**, before the caller counts, ranks, pages,
    searches or exports. The returned list is therefore already the authorized
    universe: there is no wider set to accidentally fall back to.

    Raises
    ------
    PredictionSelectionIntegrityError
        If the store yields more than one row for one
        ``(image_id, model_bundle_hash)``. Never resolved by picking a row.
    DatasetUnavailable
        If the named dataset version's membership cannot be established.
    """
    membership = scope.effective_dataset_image_ids
    params: list = [scope.model_bundle_hash]

    if scope.project_id is not None:
        params.append(scope.project_id)

    # Each restriction gets its OWN placeholder run. Reusing one name here is a
    # silent binding-count mismatch whenever a dataset and an allowlist are both
    # declared, which is precisely the deployed configuration.
    dataset_clause = ""
    allowlist_clause = ""

    if membership is not None:
        if not membership:
            # An explicitly empty intersection is an authorized empty result.
            # Returning here (instead of building a broad query and filtering in
            # Python) is what makes AT05 "empty, not unscoped" true by
            # construction rather than by accident.
            return []
        dataset_clause = " AND s.image_id IN (" + ",".join("?" for _ in membership) + ") "
        params.extend(sorted(membership))

    if scope.deployment_allowlist is not None:
        if not scope.deployment_allowlist:
            return []
        allowlist_clause = (
            " AND s.image_id IN (" + ",".join("?" for _ in scope.deployment_allowlist) + ") "
        )
        params.extend(sorted(scope.deployment_allowlist))

    sql = _SELECT_SQL
    if scope.project_id is not None:
        sql += " AND s.project_id = ? "
    sql += dataset_clause
    sql += allowlist_clause
    sql += " ORDER BY s.image_id "

    rows = conn.execute(sql, params).fetchall()
    _assert_unique_identity(rows, scope)
    return [_to_selected_row(r, scope) for r in rows]


def _assert_unique_identity(rows, scope: ScopeContext) -> None:
    """Fail closed on duplicate ``(image_id, model_bundle_hash)``.

    The schema enforces this with ``UNIQUE (image_id, model_bundle_hash)``, so a
    duplicate means a corrupted store or one that predates the constraint. Any
    resolution - newest, first, highest score - would be an arbitrary silent
    choice, so the selection errors instead.
    """
    seen: dict[str, str] = {}
    for row in rows:
        image_id = row["image_id"]
        prediction_id = row["prediction_id"]
        if prediction_id is None:
            continue
        previous = seen.get(image_id)
        if previous is not None and previous != prediction_id:
            raise PredictionSelectionIntegrityError(
                f"duplicate prediction rows for image_id={image_id!r} under "
                f"model_bundle_hash={scope.model_bundle_hash!r}: "
                f"{previous!r} and {prediction_id!r}. The store violates "
                "UNIQUE (image_id, model_bundle_hash); refusing to choose one."
            )
        seen[image_id] = prediction_id


def _to_selected_row(row, scope: ScopeContext) -> SelectedPredictionRow:
    prediction_id = row["prediction_id"]
    return SelectedPredictionRow(
        image_id=row["image_id"],
        source_group=row["source_group"],
        primary_qc_status=row["primary_qc_status"],
        training_eligible=bool(row["training_eligible"]),
        qc_review_flag=bool(row["qc_review_flag"]),
        qc_review_reason=row["qc_review_reason"],
        original_label=row["original_label"],
        project_id=row["project_id"],
        model_bundle_hash=scope.model_bundle_hash,
        prediction_id=prediction_id,
        predicted_class=row["predicted_class"],
        model_version=row["model_version"],
        inference_kind=row["inference_kind"],
        non_tumor_score=row["non_tumor_score"],
        viable_tumor_score=row["viable_tumor_score"],
        necrosis_score=row["necrosis_score"],
        top1_score=row["top1_score"],
        top_two_margin=row["top_two_margin"],
        normalized_entropy=row["normalized_entropy"],
        unavailable_reason=(
            None if prediction_id is not None else REASON_NO_PREDICTION_FOR_MODEL
        ),
    )


# ---------------------------------------------------------------------------
# Server-side resolution
# ---------------------------------------------------------------------------


def scope_for_request(
    *,
    project_id: str | None,
    model_bundle_hash: str | None = None,
    deployment_allowlist: frozenset[str] | None = None,
    review_session_id: str | None = None,
    actor_id: str | None = None,
    dataset_version_id: str | None = None,
    dataset_image_ids: frozenset[str] | None = None,
) -> ScopeContext:
    """Build a :class:`ScopeContext` from server-side inputs only.

    Nothing here reads a query string. ``project_id`` is expected to have been
    verified against membership by the caller (the enterprise ``deps.require``
    dependency already does this with a live-DB fallback), the model comes from
    :func:`active_model_bundle_hash`, and the allowlist comes from deployment
    configuration. A browser may ask *which* project; it may never assert which
    images, which model or which roles apply.

    With no ``project_id`` the result is :data:`MODE_LOCAL_SINGLE_USER` - the
    documented loopback-only path. The deployment allowlist is then taken from
    ``config.load_image_allowlist()`` so the deployed-demo subset still applies
    without anyone editing a process global.
    """
    allow = deployment_allowlist
    if project_id is None:
        if allow is None:
            allow = config.load_image_allowlist()
        return ScopeContext(
            project_id=None,
            dataset_version_id=None,
            dataset_image_ids=None,
            model_bundle_hash=model_bundle_hash or active_model_bundle_hash(),
            deployment_allowlist=allow,
            review_session_id=review_session_id,
            actor_id=actor_id,
            mode=MODE_LOCAL_SINGLE_USER,
        )
    return ScopeContext(
        project_id=project_id,
        dataset_version_id=dataset_version_id or legacy_dataset_version_id(),
        dataset_image_ids=dataset_image_ids,
        model_bundle_hash=model_bundle_hash or active_model_bundle_hash(),
        deployment_allowlist=allow,
        review_session_id=review_session_id,
        actor_id=actor_id,
        mode=MODE_SCOPED,
    )


def selected_prediction_ids(
    conn: sqlite3.Connection, scope: ScopeContext
) -> dict[str, str]:
    """``{image_id: prediction_id}`` for the scope, for review-state matching.

    Kept separate from :func:`resolve_prediction_rows` so callers that only need
    the identity mapping do not pay for the QC metadata. Both go through the same
    intersection and the same integrity check.
    """
    return {
        row.image_id: row.prediction_id
        for row in resolve_prediction_rows(conn, scope)
        if row.prediction_id is not None
    }
