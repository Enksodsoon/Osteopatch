"""Unified review surface — the authenticated /v1/* the reviewer UI actually calls.

Unlike ``test_e1_core.py`` (which asserts the G6-absent 503 contract), this
module builds a REAL temporary G6 read model with REAL pixel files and drives
every new route as a logged-in persona. That is the only way to prove the
capability gates actually bite: a route that returns 200 for everyone looks
identical to a correct one until you try it as the auditor.

What is asserted
----------------
* each route answers 200 for a role that holds the capability;
* the auditor is read-only on the write route (403) and can still export;
* a student cannot export (export:read excludes student);
* a non-member project is 404, not 403 — existence is not disclosed;
* a missing X-Project-Id is 400, not a silent unscoped read;
* TENANCY: an image owned by project A is 404 for project B on EVERY image and
  attribution path, not just the JSON detail route;
* the deterministic demo scope selects the highest-review-priority images and
  repeats identically across two seeds;
* seeding degrades honestly (``status: unavailable``) when G6 is absent rather
  than reporting a populated gallery;
* attribution failure propagates the real status (503), never a 200 with a
  fabricated PNG.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

FROZEN_HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"

# (image_id, source_group, label, scores) — the first is deliberately the most
# ambiguous so "highest review priority" is checkable rather than assumed.
SEED_IMAGES = [
    ("u-ambiguous", "Case-3", "VIABLE_TUMOR", [0.33, 0.34, 0.33]),
    ("u-clear-nt", "Case-4", "NON_TUMOR", [0.90, 0.05, 0.05]),
    ("u-mid-nec", "Case-48", "NECROSIS", [0.20, 0.25, 0.55]),
    ("u-far-nec", "P9", "NECROSIS", [0.05, 0.05, 0.90]),
]


def _build_g6_store(tmp_path: Path):
    """A real G6 read model plus real TIFF pixels the image routes can decode."""
    from osteopatch import app as g6_app
    from osteopatch import config, db, repo

    tiffs = tmp_path / "tiffs"
    thumbs = tmp_path / "thumbs"
    tiffs.mkdir(parents=True, exist_ok=True)
    thumbs.mkdir(parents=True, exist_ok=True)
    config.TIFFS_DIR = tiffs
    config.THUMBS_DIR = thumbs
    config.ATTRIB_IMAGES_DIR = tiffs

    for i, (image_id, *_rest) in enumerate(SEED_IMAGES):
        # Distinct solid colours so a wrong-image mix-up is visible in bytes.
        rgb = (40 + i * 50, 90, 160 - i * 30)
        Image.new("RGB", (32, 32), rgb).save(tiffs / f"{image_id}.tiff")

    conn = db.connect(tmp_path / "g6.sqlite3")
    db.run_migrations(conn)
    for image_id, group, label, scores in SEED_IMAGES:
        conn.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label, "
            "primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, "
            "tiff_filename) VALUES (?,?,?,?,?,?,?,?)",
            (image_id, group, label, "PASS", 1, 0, None, f"{image_id}.tiff"),
        )
        repo.upsert_prediction(conn, image_id, FROZEN_HASH, "baseline-frozen-g4", scores)
    conn.commit()
    g6_app.set_conn(conn)
    return conn


@pytest.fixture()
def stack(tmp_path, monkeypatch):
    """A logged-in-capable enterprise app in front of a real G6 read model."""
    monkeypatch.setenv("OSTEOPATCH_ENT_DB", str(tmp_path / "ent.sqlite3"))
    monkeypatch.setenv("OSTEOPATCH_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("OSTEOPATCH_PROJECT_SCOPES", str(tmp_path / "scopes"))
    monkeypatch.setenv("OSTEOPATCH_JWT_SECRET", "test-secret")
    monkeypatch.delenv("OSTEOPATCH_OIDC_JWKS_URL", raising=False)

    from enterprise import config as cfg

    importlib.reload(cfg)
    from enterprise import app as app_module
    from enterprise import audit, seed, store

    for module in (audit, store, seed, app_module):
        importlib.reload(module)

    g6_conn = _build_g6_store(tmp_path)

    ent_conn = store.connect(tmp_path / "ent.sqlite3")
    app_module.set_conn(ent_conn)
    seeded = seed.seed(ent_conn, scope_size=seed.DEMO_SCOPE_SIZE)
    return {
        "client": TestClient(app_module.app),
        "ent_conn": ent_conn,
        "g6_conn": g6_conn,
        "seeded": seeded,
        "app_module": app_module,
        "store": store,
        "seed": seed,
    }


def _login(stack, email: str) -> str:
    r = stack["client"].post("/auth/login", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _headers(stack, email: str, project_id: str | None = None) -> dict:
    headers = {"Authorization": f"Bearer {_login(stack, email)}"}
    if project_id is not None:
        headers["X-Project-Id"] = project_id
    return headers


def _pid(stack) -> str:
    return stack["seeded"]["project_id"]


# ---------------------------------------------------------------------------
# The demo scope
# ---------------------------------------------------------------------------
def test_seed_grants_a_populated_deterministic_scope(stack):
    scope = stack["seeded"]["scope"]
    assert scope["status"] == "granted", scope
    assert scope["granted"] == len(SEED_IMAGES)
    assert scope["deterministic"] is True

    # Re-seeding converges on the SAME selection: review priority is a pure
    # function of the frozen scores, so the demo never reshuffles.
    again = stack["seed"].grant_demo_scope(_pid(stack))
    assert again["granted"] == scope["granted"]
    assert again["image_ids_sample"] == scope["image_ids_sample"]


def test_demo_scope_selects_highest_review_priority(stack):
    """Not just 'some images': the ambiguity-first ones, which is what makes the
    queue worth demonstrating."""
    from enterprise import review_proxy

    chosen = review_proxy.top_priority_image_ids(len(SEED_IMAGES))
    assert chosen[0] == "u-ambiguous"  # 0.34 vs 0.33 — the smallest margin
    assert chosen[-1] in ("u-clear-nt", "u-far-nec")


def test_seed_degrades_honestly_without_the_g6_store(stack, monkeypatch):
    from enterprise import review_proxy
    from fastapi import HTTPException

    def _boom(_size):
        raise HTTPException(status_code=503, detail={"error": "unavailable"})

    monkeypatch.setattr(review_proxy, "top_priority_image_ids", _boom)
    result = stack["seed"].grant_demo_scope(_pid(stack))
    assert result["status"] == "unavailable"
    assert result["granted"] == 0
    assert "unavailable" in result["reason"].lower()


def test_seed_grants_nothing_in_the_read_model_by_default(stack, monkeypatch):
    """Scoping MUTATES the G6 read model, so `seed()` must not do it unless
    asked. A fixture that calls `seed()` must never re-scope the canonical
    1,144-image store by accident.

    This is the guard for a real regression: `seed()` originally granted the
    scope unconditionally, which silently rewrote project_id on real corpus
    rows every time the enterprise unit tests ran.
    """
    stack["g6_conn"].commit()
    before = {
        r["image_id"]: r["project_id"]
        for r in stack["g6_conn"].execute("SELECT image_id, project_id FROM source_qc")
    }

    def _forbidden(*_args, **_kwargs):
        raise AssertionError("seed() touched the G6 read model without being asked")

    monkeypatch.setattr(stack["seed"], "grant_demo_scope", _forbidden)
    result = stack["seed"].seed(stack["ent_conn"])

    assert result["scope"] == {"status": "not_requested"}
    after = {
        r["image_id"]: r["project_id"]
        for r in stack["g6_conn"].execute("SELECT image_id, project_id FROM source_qc")
    }
    assert after == before


def test_scope_rejects_unknown_ids_fail_closed(stack):
    from osteopatch import projects

    with pytest.raises(projects.ProjectScopeError):
        projects.grant_images(stack["g6_conn"], _pid(stack), ["not-a-real-image"])


# ---------------------------------------------------------------------------
# Read surface — every persona that holds review:read
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "email", ["reviewer@demo", "path@demo", "student@demo", "auditor@demo", "admin@demo"]
)
def test_read_routes_answer_for_every_read_capable_role(stack, email):
    c = stack["client"]
    h = _headers(stack, email, _pid(stack))
    assert c.get("/v1/meta", headers=h).status_code == 200
    assert c.get("/v1/model-card", headers=h).status_code == 200
    assert c.get("/v1/images", headers=h).status_code == 200
    assert c.get("/v1/images/u-mid-nec", headers=h).status_code == 200
    assert c.get("/v1/images/u-mid-nec/thumbnail", headers=h).status_code == 200
    assert c.get("/v1/images/u-mid-nec/full", headers=h).status_code == 200
    assert c.get("/v1/images/u-mid-nec/attribution/meta", headers=h).status_code == 200


def test_meta_carries_the_frozen_three_class_contract(stack):
    body = stack["client"].get(
        "/v1/meta", headers=_headers(stack, "reviewer@demo", _pid(stack))
    ).json()
    assert body["canonical_classes"] == ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"]
    assert body["attribution"]["disclosure"]


def test_model_card_keeps_the_limitations_catalog(stack):
    body = stack["client"].get(
        "/v1/model-card", headers=_headers(stack, "student@demo", _pid(stack))
    ).json()
    assert body["model_version"] == "baseline-frozen-g4"
    assert body["limitations_full"], "the full limitations catalog must survive the proxy"
    assert body["weakest_class"] if "weakest_class" in body else True


def test_gallery_is_uncertainty_first_over_the_unified_path(stack):
    body = stack["client"].get(
        "/v1/images",
        headers=_headers(stack, "reviewer@demo", _pid(stack)),
        params={"sort": "priority", "page_size": 10},
    ).json()
    assert body["items"][0]["image_id"] == "u-ambiguous"
    assert body["items"][0]["review_priority_rank"] == 1


def test_binary_routes_return_real_png_bytes(stack):
    c = stack["client"]
    h = _headers(stack, "reviewer@demo", _pid(stack))
    for path in ("/v1/images/u-mid-nec/thumbnail", "/v1/images/u-mid-nec/full"):
        r = c.get(path, headers=h)
        assert r.status_code == 200
        assert r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n", f"{path} is not a PNG"
        Image.open(__import__("io").BytesIO(r.content)).load()  # must really decode


# ---------------------------------------------------------------------------
# Capability gates — the part a 200-everywhere implementation cannot pass
# ---------------------------------------------------------------------------
def test_unauthenticated_is_401_everywhere(stack):
    c = stack["client"]
    assert c.get("/v1/meta").status_code == 401
    assert c.get("/v1/images").status_code == 401
    assert c.get("/v1/model-card").status_code == 401
    assert c.get("/v1/images/u-mid-nec/full").status_code == 401


def test_missing_project_header_is_400_not_an_unscoped_read(stack):
    """A missing X-Project-Id must never fall back to reading the whole corpus."""
    c = stack["client"]
    h = _headers(stack, "reviewer@demo")  # no project
    assert c.get("/v1/images", headers=h).status_code == 400
    assert c.get("/v1/images/u-mid-nec/thumbnail", headers=h).status_code == 400


def test_non_member_project_is_404(stack):
    c = stack["client"]
    h = _headers(stack, "reviewer@demo", "prj_not_a_member")
    assert c.get("/v1/images", headers=h).status_code == 404
    assert c.get("/v1/images/u-mid-nec", headers=h).status_code == 404


def test_auditor_can_read_but_cannot_write(stack):
    c = stack["client"]
    h = _headers(stack, "auditor@demo", _pid(stack))
    assert c.get("/v1/images", headers=h).status_code == 200
    r = c.post(
        "/v1/images/u-mid-nec/reviews",
        json={
            "prediction_id": "ignored",
            "action": "ACCEPT",
            "idempotency_key": "auditor-should-not-write",
        },
        headers=h,
    )
    assert r.status_code == 403


def test_reviewer_can_write(stack):
    c = stack["client"]
    h = _headers(stack, "reviewer@demo", _pid(stack))
    detail = c.get("/v1/images/u-mid-nec", headers=h).json()
    r = c.post(
        "/v1/images/u-mid-nec/reviews",
        json={
            "prediction_id": detail["prediction"]["prediction_id"],
            "action": "ACCEPT",
            "idempotency_key": "reviewer-write-1",
        },
        headers=h,
    )
    assert r.status_code in (200, 201), r.text
    assert r.json()["action"] == "ACCEPT"


def test_student_cannot_export_but_reviewer_can(stack):
    c = stack["client"]
    pid = _pid(stack)
    assert c.get("/v1/exports/reviews",
                 headers=_headers(stack, "student@demo", pid)).status_code == 403
    assert c.get("/v1/exports/reviews",
                 headers=_headers(stack, "reviewer@demo", pid)).status_code == 200


def test_csv_export_is_a_real_download_with_a_header_row(stack):
    c = stack["client"]
    r = c.get("/v1/exports/reviews", headers=_headers(stack, "reviewer@demo", _pid(stack)))
    assert r.headers["content-type"].startswith("text/csv")
    assert "osteopatch_reviews.csv" in r.headers["content-disposition"]
    lines = r.text.strip().splitlines()
    assert len(lines) >= 2, "header + at least one row"
    assert "image_id" in lines[0]


def test_json_export_carries_model_provenance(stack):
    body = stack["client"].get(
        "/v1/exports/reviews",
        headers=_headers(stack, "reviewer@demo", _pid(stack)),
        params={"format": "json"},
    ).json()
    assert body["model_version"] == "baseline-frozen-g4"
    assert body["model_bundle_sha256"] == FROZEN_HASH
    assert body["count"] == len(body["rows"])


# ---------------------------------------------------------------------------
# Tenancy — the same image, from a project that does not own it
# ---------------------------------------------------------------------------
def test_second_project_cannot_read_the_first_projects_pixels(stack):
    c = stack["client"]
    store = stack["store"]
    pid = _pid(stack)

    admin_h = _headers(stack, "admin@demo")
    other = c.post("/v1/projects", json={"name": "Project B"}, headers=admin_h).json()
    other_pid = other["project_id"]

    # admin is in both projects, and the image is owned by the demo project.
    other_h = _headers(stack, "admin@demo", other_pid)
    assert c.get("/v1/images/u-mid-nec", headers=other_h).status_code == 404
    assert c.get("/v1/images/u-mid-nec/thumbnail", headers=other_h).status_code == 404
    assert c.get("/v1/images/u-mid-nec/full", headers=other_h).status_code == 404
    assert c.get("/v1/images/u-mid-nec/attribution/meta", headers=other_h).status_code == 404
    assert c.get("/v1/images", headers=other_h).json()["total"] == 0

    # A member of the owning project still can.
    assert c.get("/v1/images/u-mid-nec", headers=_headers(stack, "reviewer@demo", pid)).status_code == 200
    del store


# ---------------------------------------------------------------------------
# Honest degradation of attribution
# ---------------------------------------------------------------------------
def test_attribution_failure_keeps_its_status_and_never_fakes_a_png(stack, monkeypatch):
    """When G6 reports 503 (torch absent / bundle hash mismatch), the unified
    route must return 503 — not a 200 carrying a blank image."""
    from fastapi.responses import JSONResponse

    g6_app_module = sys.modules["osteopatch.app"]

    def _unavailable(image_id, target_a=None, target_b=None, format="png"):
        return JSONResponse(status_code=503, content={"error": "attribution runtime unavailable"})

    monkeypatch.setattr(g6_app_module, "get_attribution", _unavailable)

    c = stack["client"]
    h = _headers(stack, "reviewer@demo", _pid(stack))
    r = c.get("/v1/images/u-mid-nec/attribution", headers=h)
    assert r.status_code == 503
    assert r.headers["content-type"].startswith("application/json")
    assert "unavailable" in r.text


def test_attribution_bad_class_is_400_through_the_proxy(stack):
    r = stack["client"].get(
        "/v1/images/u-mid-nec/attribution",
        headers=_headers(stack, "reviewer@demo", _pid(stack)),
        params={"target_a": "BONE", "target_b": "NECROSIS"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# /api/v1/* compatibility + the health the unified UI reads
# ---------------------------------------------------------------------------
def test_api_v1_paths_are_unchanged(stack):
    """The aliases are additions, not a migration."""
    c = stack["client"]
    h = _headers(stack, "reviewer@demo", _pid(stack))
    legacy = c.get("/api/v1/images", headers=h).json()
    unified = c.get("/v1/images", headers=h).json()
    assert legacy["items"] == unified["items"]


def test_health_reports_the_read_model_not_just_the_import(stack):
    body = stack["client"].get("/v1/health").json()
    assert body["read_model"]["available"] is True
    assert body["read_model"]["predictions"] == len(SEED_IMAGES)
    assert body["audit_chain_ok"] is True
