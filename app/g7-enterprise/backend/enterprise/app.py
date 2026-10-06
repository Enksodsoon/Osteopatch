"""Enterprise E1 FastAPI app — authn / authz / tenancy over the review surface.

Routes:
  POST /auth/login                 -> issue a local bearer token (stand-in IdP)
  GET  /auth/me                    -> whoami + project memberships
  GET  /v1/projects                -> projects the caller belongs to
  POST /v1/projects                -> create a project (admin)
  POST /v1/projects/{id}/members   -> add a member (admin)
  GET  /v1/audit                   -> read + verify the audit chain (auditor/admin)
  GET  /api/v1/images              -> project-scoped gallery (review:read)
  POST /api/v1/images/{id}/reviews -> submit a review (review:write), audited
  GET  /v1/images, /v1/images/{id} -> the SAME handlers, at the G6-shaped paths
                                      the unified reviewer UI calls. Aliases, not
                                      copies: see the alias block below.

The review surface is enforced here (authz + tenancy) and then delegated to the
G6 review logic. When the G6 package / its data store is not importable (e.g. in
a bare test environment), the proxy returns a clearly-labelled 503 rather than a
fabricated result — never a fake prediction.

Binds 127.0.0.1 only. No torch. No AWS.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import audit, auth, config, governance, ingestion, inference, observability, registry, review_proxy, store
from .deps import Principal, require

app = FastAPI(
    title="OsteoPatch Enterprise (E1)",
    version="0.7.0-e1",
    description=config.DISCLAIMER,
)

_conn = None


def get_conn():
    global _conn
    if _conn is None:
        _conn = store.connect()
    return _conn


def set_conn(conn) -> None:
    """Test hook."""
    global _conn
    _conn = conn


@app.exception_handler(auth.AuthError)
async def _auth_error(_, exc: auth.AuthError):
    return JSONResponse(status_code=exc.http_status, content={"error": exc.message})


@app.exception_handler(governance.GovernanceError)
async def _gov_error(_, exc: governance.GovernanceError):
    return JSONResponse(status_code=exc.http_status, content={"error": exc.message})


@app.exception_handler(registry.RegistryError)
async def _reg_error(_, exc: registry.RegistryError):
    return JSONResponse(status_code=exc.http_status, content={"error": exc.message})


@app.exception_handler(ingestion.IngestionError)
async def _ing_error(_, exc: ingestion.IngestionError):
    return JSONResponse(status_code=exc.http_status, content={"error": exc.message})


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginBody(BaseModel):
    email: str = Field(..., description="E1 stand-in IdP: any seeded email")


@app.post("/auth/login")
def login(body: LoginBody):
    conn = get_conn()
    user = store.get_user_by_email(conn, body.email)
    if user is None:
        # Do not auto-provision on login — membership is an admin action.
        raise HTTPException(status_code=401, detail="unknown user (seed or invite first)")
    memberships = store.memberships_for_user(conn, user["user_id"])
    token = auth.issue_token(user_id=user["user_id"], email=user["email"], memberships=memberships)
    audit.record(user["email"], "auth.login", user["user_id"],
                 detail={"projects": [m["project_id"] for m in memberships]})
    return token


@app.get("/auth/me")
def whoami(authorization: str | None = Header(default=None)):
    from .deps import principal_from_header
    p = principal_from_header(authorization)
    conn = get_conn()
    return {
        "user_id": p.user_id,
        "email": p.email,
        "memberships": store.memberships_for_user(conn, p.user_id),
        "disclaimer": config.DISCLAIMER,
    }


# ---------------------------------------------------------------------------
# Projects (multi-tenancy)
# ---------------------------------------------------------------------------
@app.get("/v1/projects")
def list_projects(authorization: str | None = Header(default=None)):
    from .deps import principal_from_header
    p = principal_from_header(authorization)
    conn = get_conn()
    return {"projects": store.memberships_for_user(conn, p.user_id)}


class ProjectBody(BaseModel):
    name: str


@app.post("/v1/projects")
def create_project(body: ProjectBody, p: Principal = Depends(require("project:admin", project_scoped=False))):
    conn = get_conn()
    prj = store.create_project(conn, body.name, p.user_id)
    # creator becomes admin of the new project
    store.add_membership(conn, p.user_id, prj["project_id"], "admin")
    audit.record(p.email, "project.create", prj["project_id"], project_id=prj["project_id"],
                 detail={"name": body.name})
    return prj


class MemberBody(BaseModel):
    email: str
    role: str


@app.post("/v1/projects/{project_id}/members")
def add_member(project_id: str, body: MemberBody,
               p: Principal = Depends(require("project:admin", project_scoped=False))):
    conn = get_conn()
    # Authz against LIVE DB membership, not only the (possibly stale) token
    # claim: the token proves identity, the store proves current project role.
    # This lets an admin manage a project they created after their last login.
    if store.role_in_project(conn, p.user_id, project_id) != "admin":
        raise HTTPException(status_code=403, detail="must be admin of this project")
    if body.role not in config.ALL_ROLES:
        raise HTTPException(status_code=400, detail=f"invalid role; one of {config.ALL_ROLES}")
    user = store.upsert_user(conn, body.email)
    store.add_membership(conn, user["user_id"], project_id, body.role)
    audit.record(p.email, "project.add_member", user["user_id"], project_id=project_id,
                 detail={"role": body.role})
    return {"user_id": user["user_id"], "email": user["email"], "project_id": project_id, "role": body.role}


class ScopeBody(BaseModel):
    image_ids: list[str] | None = None   # explicit ids; None = grant first `limit`
    limit: int = 50


@app.post("/v1/projects/{project_id}/scope")
def set_project_scope(project_id: str, body: ScopeBody,
                      p: Principal = Depends(require("project:admin", project_scoped=False))):
    """Grant real image_ids into a project's review scope (multi-tenancy).

    This is the tenancy boundary made concrete: a project sees ONLY the images
    an admin granted it. Ids are validated against the G6 corpus; unknown ids
    are rejected (never silently granted). Writes the project's allowlist file
    the G6 read model already honours.
    """
    conn = get_conn()
    if store.role_in_project(conn, p.user_id, project_id) != "admin":
        raise HTTPException(status_code=403, detail="must be admin of this project")
    granted = review_proxy.grant_scope(project_id, image_ids=body.image_ids, limit=body.limit)
    audit.record(p.email, "project.set_scope", project_id, project_id=project_id,
                 detail={"count": len(granted)})
    return {"project_id": project_id, "granted": len(granted), "image_ids": granted[:10],
            "note": "showing first 10 of granted ids" if len(granted) > 10 else "all granted ids"}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@app.get("/v1/audit")
def read_audit(p: Principal = Depends(require("audit:read", project_scoped=False)),
               limit: int = 200):
    ok, n, bad = audit.verify_chain()
    return {
        "chain_ok": ok,
        "entries_verified": n,
        "first_bad_hash": bad,
        "entries": audit.read_entries(limit=limit),
    }


# ---------------------------------------------------------------------------
# Review surface (project-scoped, delegated to G6)
# ---------------------------------------------------------------------------
@app.get("/api/v1/images")
def gallery(p: Principal = Depends(require("review:read")),
            x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
            sort: str = "priority", filter: str = "all", page: int = 1, page_size: int = 50):
    return review_proxy.list_images(x_project_id, sort=sort, filt=filter, page=page, page_size=page_size)


@app.get("/api/v1/images/{image_id}")
def patch_detail(image_id: str, p: Principal = Depends(require("review:read")),
                 x_project_id: str | None = Header(default=None, alias="X-Project-Id")):
    return review_proxy.get_image(x_project_id, image_id)


class ReviewBody(BaseModel):
    prediction_id: str
    action: str
    selected_label: str | None = None
    reason: str | None = None
    note: str | None = None
    expected_revision: int = 0
    idempotency_key: str


@app.post("/api/v1/images/{image_id}/reviews")
def submit_review(image_id: str, body: ReviewBody,
                  p: Principal = Depends(require("review:write")),
                  x_project_id: str | None = Header(default=None, alias="X-Project-Id")):
    result = review_proxy.submit_review(x_project_id, image_id, body.model_dump(), reviewer=p.email)
    audit.record(p.email, "review.submit", image_id, project_id=x_project_id,
                 detail={"action": body.action, "idempotency_key": body.idempotency_key})
    return result


@app.get("/api/v1/exports/reviews")
def export(p: Principal = Depends(require("export:read")),
           x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
           format: str = "csv"):
    audit.record(p.email, "export.reviews", x_project_id or "-", project_id=x_project_id,
                 detail={"format": format})
    return review_proxy.export_reviews(x_project_id, format=format)


# ---------------------------------------------------------------------------
# Unified review surface (Phase 1) — the G6-shaped /v1/* paths
#
# One implementation, two mount points. The /api/v1/* handlers above are
# re-registered here at their G6 paths so the unified reviewer UI calls the
# same functions; nothing is reimplemented, so the two surfaces cannot drift.
# /api/v1/* stays exactly as it was for existing callers.
# ---------------------------------------------------------------------------
_UNIFIED_ALIASES: tuple[tuple[str, str, str], ...] = (
    ("/v1/images", "gallery", "GET"),
    ("/v1/images/{image_id}", "patch_detail", "GET"),
    ("/v1/images/{image_id}/reviews", "submit_review", "POST"),
)


def _register_unified_aliases() -> None:
    for path, handler_name, method in _UNIFIED_ALIASES:
        app.add_api_route(path, globals()[handler_name], methods=[method])


_register_unified_aliases()


@app.get("/v1/meta")
def unified_meta(p: Principal = Depends(require("review:read"))):
    """Review contract: canonical classes, actions, defer reasons, attribution
    disclosure. Requires membership; carries no project-scoped data itself."""
    return review_proxy.meta()


@app.get("/v1/model-card")
def unified_model_card(p: Principal = Depends(require("review:read"))):
    """Frozen model card + the full limitations catalog."""
    return review_proxy.model_card()


@app.get("/v1/images/{image_id}/thumbnail")
def unified_thumbnail(image_id: str, p: Principal = Depends(require("review:read")),
                      x_project_id: str | None = Header(default=None, alias="X-Project-Id")):
    """Gallery thumbnail PNG. 404 (not 403) when the image is outside the
    caller's project, so scope cannot be probed."""
    return Response(content=review_proxy.thumbnail_png(x_project_id, image_id),
                    media_type="image/png")


@app.get("/v1/images/{image_id}/full")
def unified_full(image_id: str, p: Principal = Depends(require("review:read")),
                 x_project_id: str | None = Header(default=None, alias="X-Project-Id")):
    """Full-resolution patch PNG."""
    return Response(content=review_proxy.full_png(x_project_id, image_id),
                    media_type="image/png")


@app.get("/v1/images/{image_id}/attribution/meta")
def unified_attribution_meta(image_id: str, p: Principal = Depends(require("review:read")),
                             x_project_id: str | None = Header(default=None, alias="X-Project-Id")):
    """Attribution availability + default contrastive pair, WITHOUT running the
    torch-loading CAM, so the UI can show the recovery disclosure up front."""
    return review_proxy.attribution_meta(x_project_id, image_id)


@app.get("/v1/images/{image_id}/attribution")
def unified_attribution(image_id: str,
                        p: Principal = Depends(require("review:read")),
                        x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
                        target_a: str | None = None, target_b: str | None = None):
    """Contrastive Grad-CAM overlay PNG.

    The X-Attrib-* provenance headers come straight from G6. A 503 from G6
    (torch absent, recovered-bundle hash mismatch) passes through unchanged —
    attribution degrades to an honest notice, never a fabricated heatmap.
    """
    body, headers = review_proxy.attribution_overlay(
        x_project_id, image_id, target_a=target_a, target_b=target_b
    )
    return Response(content=body, media_type="image/png", headers=headers)


@app.get("/v1/exports/reviews")
def unified_export(p: Principal = Depends(require("export:read")),
                   x_project_id: str | None = Header(default=None, alias="X-Project-Id"),
                   format: str = "csv"):
    """G6-shaped review export: a real CSV download, or the JSON envelope.

    Distinct from /api/v1/exports/reviews, which returns the row envelope for
    the enterprise UI rather than a file. Both read the same rows.
    """
    from osteopatch import exports  # type: ignore

    rows = review_proxy.review_export_rows(x_project_id)
    audit.record(p.email, "export.reviews", x_project_id or "-", project_id=x_project_id,
                 detail={"format": format, "rows": len(rows)})
    if format == "json":
        return exports.json_envelope(rows)
    return StreamingResponse(
        iter([exports.rows_to_csv(rows)]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={exports.CSV_FILENAME}"},
    )


# ---------------------------------------------------------------------------
# E4 — Governance (adjudication, batch sign-off, correction capture)
# ---------------------------------------------------------------------------
class AdjudicateBody(BaseModel):
    image_id: str
    resolved_label: str
    rationale: str | None = None


@app.post("/v1/projects/{project_id}/adjudications")
def post_adjudication(project_id: str, body: AdjudicateBody,
                      p: Principal = Depends(require("review:adjudicate"))):
    conn = get_conn()
    r = governance.adjudicate(conn, project_id=project_id, image_id=body.image_id,
                              resolver=p.email, resolved_label=body.resolved_label,
                              rationale=body.rationale)
    audit.record(p.email, "govern.adjudicate", body.image_id, project_id=project_id,
                 detail={"resolved_label": body.resolved_label})
    return r


class SignoffBody(BaseModel):
    image_ids: list[str]
    states: dict[str, str] = {}


@app.post("/v1/projects/{project_id}/signoffs")
def post_signoff(project_id: str, body: SignoffBody,
                 p: Principal = Depends(require("review:adjudicate"))):
    conn = get_conn()
    r = governance.sign_off_batch(conn, project_id=project_id, signed_by=p.email,
                                  image_ids=body.image_ids, states=body.states)
    audit.record(p.email, "govern.signoff", r["batch_id"], project_id=project_id,
                 detail={"image_count": r["image_count"], "content_sha": r["content_sha"]})
    return r


class CorrectionBody(BaseModel):
    image_id: str
    from_label: str
    to_label: str


@app.post("/v1/projects/{project_id}/corrections")
def post_correction(project_id: str, body: CorrectionBody,
                    p: Principal = Depends(require("review:write"))):
    conn = get_conn()
    r = governance.capture_correction(conn, project_id=project_id, image_id=body.image_id,
                                      from_label=body.from_label, to_label=body.to_label,
                                      captured_by=p.email)
    audit.record(p.email, "govern.capture_correction", body.image_id, project_id=project_id,
                 detail={"from": body.from_label, "to": body.to_label})
    return r


# ---------------------------------------------------------------------------
# E5 — Model registry
# ---------------------------------------------------------------------------
class RegisterModelBody(BaseModel):
    bundle_sha256: str
    model_id: str
    eval_card_ref: str
    split_declared: str


@app.post("/v1/models")
def register_model(body: RegisterModelBody,
                   p: Principal = Depends(require("model:manage", project_scoped=False))):
    conn = get_conn()
    r = registry.register(conn, bundle_sha256=body.bundle_sha256, model_id=body.model_id,
                          eval_card_ref=body.eval_card_ref, split_declared=body.split_declared,
                          registered_by=p.email)
    audit.record(p.email, "model.register", body.bundle_sha256, detail={"model_id": body.model_id})
    return r


class PromoteBody(BaseModel):
    bundle_sha256: str
    to: str
    eval_passed: bool | None = None
    note: str | None = None


@app.post("/v1/models/promote")
def promote_model(body: PromoteBody,
                  p: Principal = Depends(require("model:manage", project_scoped=False))):
    conn = get_conn()
    if body.eval_passed is not None:
        registry.set_eval_passed(conn, body.bundle_sha256, body.eval_passed, p.email)
    r = registry.promote(conn, bundle_sha256=body.bundle_sha256,
                         to=registry.ModelState(body.to), actor=p.email, note=body.note)
    audit.record(p.email, "model.promote", body.bundle_sha256, detail={"to": body.to})
    return r


@app.post("/v1/models/rollback")
def rollback_model(p: Principal = Depends(require("model:manage", project_scoped=False))):
    conn = get_conn()
    r = registry.rollback(conn, p.email)
    audit.record(p.email, "model.rollback", r["bundle_sha256"])
    return r


@app.get("/v1/models/serving")
def serving_model(p: Principal = Depends(require("model:manage", project_scoped=False))):
    return registry.serving(get_conn()) or {"serving": None}


# ---------------------------------------------------------------------------
# E6 — Drift monitor (local). WORM/OTel seam stays gated in observability.py.
# ---------------------------------------------------------------------------
@app.get("/v1/projects/{project_id}/drift")
def drift(project_id: str, bundle_sha256: str,
          p: Principal = Depends(require("model:manage", project_scoped=False))):
    # Drift is computed over THIS project's predictions only. The image set is
    # read from the database via the request-scoped project id — no global is
    # mutated, so a concurrent request for another project cannot affect this.
    g6 = review_proxy._g6()
    ids = review_proxy.project_image_ids(project_id)
    rep = observability.drift_report(
        g6.get_conn(), bundle_sha256=bundle_sha256, image_ids=ids or None
    )
    audit.record(p.email, "obs.drift_report", bundle_sha256, project_id=project_id,
                 detail={"alerts": rep.alerts})
    return {
        "bundle_sha256": rep.bundle_sha256, "n_predictions": rep.n_predictions,
        "n_reviewed": rep.n_reviewed, "mean_scores": rep.mean_scores,
        "mean_top_two_margin": rep.mean_top_two_margin, "mean_entropy": rep.mean_entropy,
        "defer_rate": rep.defer_rate, "correction_rate": rep.correction_rate,
        "disagreement_rate": rep.disagreement_rate, "alerts": rep.alerts,
    }


# ---------------------------------------------------------------------------
# E2 — Ingestion (dataset register + manifest index). Pixel pipeline gated.
# ---------------------------------------------------------------------------
class DatasetBody(BaseModel):
    source: str
    license: str = ""
    split_declared: str = ""


@app.post("/v1/datasets")
def register_dataset(body: DatasetBody,
                     p: Principal = Depends(require("project:admin", project_scoped=False))):
    conn = get_conn()
    r = ingestion.register_dataset(conn, source=body.source, license=body.license,
                                   split_declared=body.split_declared, created_by=p.email)
    audit.record(p.email, "ingest.register_dataset", r["dataset_id"], detail={"source": body.source})
    return r


class ManifestBody(BaseModel):
    rows: list[dict]


@app.post("/v1/datasets/{dataset_id}/manifest")
def index_manifest(dataset_id: str, body: ManifestBody,
                   p: Principal = Depends(require("project:admin", project_scoped=False))):
    conn = get_conn()
    r = ingestion.index_manifest(conn, dataset_id=dataset_id, rows=body.rows)
    audit.record(p.email, "ingest.index_manifest", dataset_id, detail={"indexed": r["indexed"]})
    return r


# ---------------------------------------------------------------------------
# E3 — Inference orchestration (enqueue/dedup local; GPU execution gated)
# ---------------------------------------------------------------------------
class EnqueueBody(BaseModel):
    image_ids: list[str]
    bundle_sha256: str
    shadow: bool = False


@app.post("/v1/inference/enqueue")
def enqueue_inference(body: EnqueueBody,
                      p: Principal = Depends(require("model:manage", project_scoped=False))):
    conn = get_conn()
    r = inference.enqueue(conn, image_ids=body.image_ids, bundle_sha256=body.bundle_sha256,
                          shadow=body.shadow)
    audit.record(p.email, "infer.enqueue", body.bundle_sha256,
                 detail={"newly_queued": r["newly_queued"], "shadow": body.shadow})
    return r


@app.get("/v1/health")
def health():
    ok, n, _ = audit.verify_chain()
    report: dict = {
        "status": "ok",
        "layer": "enterprise-full (E1 live + E2–E6 local; AWS seam gated)",
        "external_oidc": config.USE_EXTERNAL_OIDC,
        "audit_chain_ok": ok,
        "audit_entries": n,
        "review_backend": review_proxy.backend_status(),
        "disclaimer": config.DISCLAIMER,
    }
    # The unified UI shows this as its single "is the demo ready?" indicator, so
    # it needs the READ MODEL's counts too — not just "the package imported".
    # A G6 store that is absent or unreadable reports why, never a zero that
    # would read as an empty corpus.
    try:
        read_model = review_proxy.health()
    except HTTPException as exc:
        report["read_model"] = {"available": False, "detail": exc.detail}
    else:
        report["read_model"] = {"available": True, **read_model}
    return report
