"""Live inference over the authenticated surface.

Layered so CI (which runs torch-free) still covers everything except the model
itself:

  * torch-FREE: capability gating per role, tenancy, upload validation, filename
    sanitisation, and the full upload -> predict -> read-back -> delete round
    trip with the forward pass stubbed at ``live_inference._predict_array``.
    That is the seam between "the model" and "everything that stores, scopes and
    serves the model's answer", so a stub here leaves the plumbing genuinely
    exercised rather than skipped.
  * torch-GATED: the same round trip with the REAL recovered head, asserting a
    three-class result and a byte-identical corpus afterwards.

A live run must never be conflated with the 1,144 frozen baseline predictions.
That is asserted here over real HTTP, not just at the storage layer.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import importlib
import io
import math
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

FROZEN_HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"
SEED_IMAGES = [
    ("l-clear-nt", "Case-4", "NON_TUMOR", [0.90, 0.05, 0.05]),
    ("l-mid-nec", "Case-48", "NECROSIS", [0.20, 0.25, 0.55]),
]


def _have_model_runtime() -> bool:
    try:
        import torch  # noqa: F401
    except Exception:
        return False
    from osteopatch import live_inference
    return live_inference.runtime_available()["available"]


model_runtime = pytest.mark.skipif(
    not _have_model_runtime(), reason="pinned recovered model or encoder artifact unavailable; plumbing tests cover this route"
)


@pytest.fixture()
def stack(tmp_path, monkeypatch):
    """Enterprise app in front of a real G6 read model, with live runs on tmp."""
    monkeypatch.setenv("OSTEOPATCH_ENT_DB", str(tmp_path / "ent.sqlite3"))
    monkeypatch.setenv("OSTEOPATCH_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("OSTEOPATCH_PROJECT_SCOPES", str(tmp_path / "scopes"))
    monkeypatch.setenv("OSTEOPATCH_JWT_SECRET", "test-secret")
    monkeypatch.setenv("OSTEOPATCH_LIVE_RUNS", str(tmp_path / "live-runs"))
    monkeypatch.setenv("OSTEOPATCH_DB", str(tmp_path / "g6.sqlite3"))
    monkeypatch.delenv("OSTEOPATCH_OIDC_JWKS_URL", raising=False)

    from enterprise import config as cfg

    importlib.reload(cfg)
    from enterprise import app as app_module
    from enterprise import audit, seed, store

    for module in (audit, store, seed, app_module):
        importlib.reload(module)

    import osteopatch.config as g6_config

    importlib.reload(g6_config)

    from osteopatch import app as g6_app
    from osteopatch import db as g6_db
    from osteopatch import repo

    tiffs = tmp_path / "tiffs"
    tiffs.mkdir(parents=True, exist_ok=True)
    g6_config.TIFFS_DIR = tiffs
    g6_config.THUMBS_DIR = tmp_path / "thumbs"
    g6_config.ATTRIB_IMAGES_DIR = tiffs

    for i, (image_id, *_rest) in enumerate(SEED_IMAGES):
        Image.new("RGB", (32, 32), (40 + i * 50, 90, 160)).save(tiffs / f"{image_id}.tiff")

    g6_conn = g6_db.connect(tmp_path / "g6.sqlite3")
    g6_db.run_migrations(g6_conn)
    for image_id, group, label, scores in SEED_IMAGES:
        g6_conn.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label,"
            " primary_qc_status, training_eligible, qc_review_flag, qc_review_reason,"
            " tiff_filename) VALUES (?,?,?,'PASS',1,0,NULL,?)",
            (image_id, group, label, f"{image_id}.tiff"),
        )
        repo.upsert_prediction(
            g6_conn, image_id, FROZEN_HASH, "baseline-frozen-g4", scores
        )
    g6_conn.commit()
    g6_app.set_conn(g6_conn)

    ent_conn = store.connect(tmp_path / "ent.sqlite3")
    app_module.set_conn(ent_conn)
    seeded = seed.seed(ent_conn, scope_size=seed.DEMO_SCOPE_SIZE)
    return {
        "client": TestClient(app_module.app),
        "g6_conn": g6_conn,
        "seeded": seeded,
        "tmp": tmp_path,
    }


@pytest.fixture()
def stub_forward(monkeypatch):
    """Replace the forward pass, keeping everything around it real.

    The stub sits at the model boundary, so routing, storage, tenancy,
    validation and auditing are all genuinely exercised without torch.
    """
    from osteopatch import live_inference as li

    def _fake(state, image):
        return li.LivePrediction(
            scores={"NON_TUMOR": 0.80, "VIABLE_TUMOR": 0.10, "NECROSIS": 0.10},
            predicted_class="NON_TUMOR",
            top1_score=0.80,
            top_two_margin=0.70,
            normalized_entropy=0.42,
            confidence="clear",
            caveat=None,
            support_flags=[],
        )

    monkeypatch.setattr(li, "_predict_array", _fake)
    # create_run reads the verified bundle identity; stub it too so the
    # torch-free path does not need the recovered weights on disk.
    monkeypatch.setattr(
        "osteopatch.attribution.get_state",
        lambda: {"bundle_sha256": "stub-bundle-sha"},
    )
    monkeypatch.setattr(
        "osteopatch.attribution.RECOVERED_BUNDLE", Path("does-not-exist.pt")
    )
    return _fake


def _login(stack, email):
    r = stack["client"].post("/auth/login", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(stack, email, project_id=None):
    headers = {"Authorization": f"Bearer {_login(stack, email)}"}
    if project_id is not None:
        headers["X-Project-Id"] = project_id
    return headers


def _pid(stack):
    return stack["seeded"]["project_id"]


def _png(colour=(120, 60, 180)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (128, 128), colour).save(buf, format="PNG")
    return buf.getvalue()


def _post(stack, email, path, body, name="patch.png", project=None):
    return stack["client"].post(
        path,
        content=body,
        headers={**_h(stack, email, project if project is not None else _pid(stack)),
                 "X-File-Name": name,
                 "Content-Type": "application/octet-stream"},
    )


# ---------------------------------------------------------------------------
# Capability split: live:read is a reader, live:analyze is a writer
# ---------------------------------------------------------------------------
READ_ROLES = ["admin@demo", "path@demo", "reviewer@demo", "student@demo",
              "mle@demo", "auditor@demo"]
WRITE_ROLES = ["admin@demo", "path@demo", "reviewer@demo", "mle@demo"]


@pytest.mark.parametrize("email", READ_ROLES)
def test_every_role_can_read_live_capability(stack, email):
    r = stack["client"].get("/v1/live/capability", headers=_h(stack, email, _pid(stack)))
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["available"], bool)
    assert body["tile_px"] == 384
    assert ".svs" in body["allowed_suffixes"]


@pytest.mark.parametrize("email", WRITE_ROLES)
def test_writer_roles_get_through_the_analyze_gate(stack, stub_forward, email):
    """Reaching the handler, not the gate, is the assertion: the body is empty,
    so a permitted caller gets a validation error rather than a 403."""
    r = _post(stack, email, "/v1/live/patches", b"")
    assert r.status_code == 400, r.text
    assert "empty upload" in r.text


@pytest.mark.parametrize("email", ["student@demo", "auditor@demo"])
def test_reader_only_roles_cannot_analyze(stack, stub_forward, email):
    r = _post(stack, email, "/v1/live/patches", _png())
    assert r.status_code == 403, r.text
    assert "live:analyze" in r.text


def test_analyze_requires_authentication(stack):
    r = stack["client"].post("/v1/live/patches", content=_png(),
                             headers={"X-Project-Name": "x"})
    assert r.status_code == 401


def test_reader_only_roles_cannot_delete_a_run(stack, stub_forward):
    r = stack["client"].delete("/v1/live/runs/whatever",
                               headers=_h(stack, "auditor@demo", _pid(stack)))
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tenancy + project context
# ---------------------------------------------------------------------------
def test_missing_project_header_is_400_not_an_unscoped_run(stack):
    r = stack["client"].get("/v1/live/runs", headers=_h(stack, "reviewer@demo"))
    assert r.status_code == 400


def test_non_member_project_is_404(stack):
    r = stack["client"].get("/v1/live/runs",
                            headers=_h(stack, "reviewer@demo", "prj_not_a_member"))
    assert r.status_code == 404


def test_analyze_requires_a_project_context(stack, stub_forward):
    r = _post(stack, "reviewer@demo", "/v1/live/patches", _png(), project="")
    assert r.status_code in (400, 404)


# ---------------------------------------------------------------------------
# Upload validation, before any model work
# ---------------------------------------------------------------------------
def test_empty_upload_is_400(stack, stub_forward):
    r = _post(stack, "reviewer@demo", "/v1/live/patches", b"")
    assert r.status_code == 400


def test_unsupported_extension_is_415(stack, stub_forward):
    r = _post(stack, "reviewer@demo", "/v1/live/patches", b"%PDF-1.4", name="paper.pdf")
    assert r.status_code == 415
    assert ".svs" in r.text


def test_oversized_upload_is_refused_before_any_work(stack, stub_forward, monkeypatch):
    """413, and nothing stored.

    The observable property is not the HTTP status alone — it is that an upload
    past the cap costs no model work and leaves no run behind.
    """
    from osteopatch import config as g6_config

    monkeypatch.setattr(g6_config, "LIVE_MAX_UPLOAD_BYTES", 64)
    r = _post(stack, "reviewer@demo", "/v1/live/patches", _png(), name="big.png")
    assert r.status_code == 413
    assert "too large" in r.text
    assert stack["g6_conn"].execute("SELECT COUNT(*) FROM live_run").fetchone()[0] == 0


def test_undecodable_image_is_422_not_a_guess(stack, stub_forward):
    r = _post(stack, "reviewer@demo", "/v1/live/patches",
              b"this is not an image at all", name="broken.png")
    assert r.status_code == 422
    assert "could not decode" in r.text


def test_hostile_filename_is_reduced_to_a_basename(stack, stub_forward):
    """`X-File-Name` is an untrusted label; it must never be stored as a path."""
    r = _post(stack, "reviewer@demo", "/v1/live/patches", _png(),
              name="../../../../etc/passwd.png")
    assert r.status_code == 200, r.text
    stored = r.json()["run"]["source_name"]
    assert "/" not in stored and "\\" not in stored
    assert stored == "passwd.png"


# ---------------------------------------------------------------------------
# Round trip (torch-free, forward pass stubbed)
# ---------------------------------------------------------------------------
def test_upload_predict_read_back_delete_round_trip(stack, stub_forward):
    c = stack["client"]
    pid = _pid(stack)

    created = _post(stack, "reviewer@demo", "/v1/live/patches", _png())
    assert created.status_code == 200, created.text
    run = created.json()["run"]
    run_id = run["run_id"]

    assert run["is_live_inference"] is True
    assert run["is_corpus_prediction"] is False
    assert run["model_id"] == "g4-behavioral-recovery-r1"
    assert run["project_id"] == pid
    assert run["requested_by"] == "reviewer@demo"
    assert created.json()["prediction"]["predicted_class"] == "NON_TUMOR"

    # read-back
    got = c.get(f"/v1/live/runs/{run_id}", headers=_h(stack, "reviewer@demo", pid))
    assert got.status_code == 200
    assert got.json()["run"]["run_id"] == run_id
    assert got.json()["n_tiles"] == 1
    assert got.json()["tiles"][0]["scores"]["NON_TUMOR"] == 0.80
    thumb = c.get(f"/v1/live/runs/{run_id}/thumbnail.png", headers=_h(stack, "student@demo", pid))
    assert thumb.status_code == 200 and thumb.content.startswith(b"\x89PNG")

    # listed
    listing = c.get("/v1/live/runs", headers=_h(stack, "reviewer@demo", pid)).json()
    assert [r["run_id"] for r in listing["runs"]] == [run_id]

    # readable by a reader-only role
    assert c.get(f"/v1/live/runs/{run_id}",
                 headers=_h(stack, "student@demo", pid)).status_code == 200

    # delete is a writer action
    deleted = c.delete(f"/v1/live/runs/{run_id}", headers=_h(stack, "reviewer@demo", pid))
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert c.get(f"/v1/live/runs/{run_id}",
                 headers=_h(stack, "reviewer@demo", pid)).status_code == 404


def test_recorded_tiles_can_be_included_in_an_unsigned_report(stack, stub_forward):
    created = _post(stack, "reviewer@demo", "/v1/live/patches", _png())
    assert created.status_code == 200, created.text
    run_id = created.json()["run"]["run_id"]
    response = stack["client"].post("/v1/reports", headers=_h(stack, "reviewer@demo", _pid(stack)), json={
        "case_id": "education", "title": "Recorded evidence", "findings_text": "Practice notes",
        "image_ids": [], "run_ids": [run_id],
    })
    assert response.status_code == 200, response.text
    doc = response.json()
    assert doc["is_signed"] is False
    assert doc["images"][0]["scores"] == created.json()["prediction"]["scores"]
    assert doc["images"][0]["run_id"] == run_id


def test_a_live_run_is_invisible_to_another_project(stack, stub_forward):
    c = stack["client"]
    run_id = _post(stack, "reviewer@demo", "/v1/live/patches", _png()).json()["run"]["run_id"]

    admin = _login(stack, "admin@demo")
    other = c.post("/v1/projects", json={"name": "Other"}, headers={"Authorization": f"Bearer {admin}"})
    assert other.status_code == 200, other.text
    other_pid = other.json()["project_id"]
    oh = {"Authorization": f"Bearer {admin}", "X-Project-Id": other_pid}

    assert c.get(f"/v1/live/runs/{run_id}", headers=oh).status_code == 404
    assert c.get(f"/v1/live/runs/{run_id}/mosaic.png", headers=oh).status_code == 404
    assert c.get(f"/v1/live/runs/{run_id}/thumbnail.png", headers=oh).status_code == 404
    assert c.get("/v1/live/runs", headers=oh).json()["runs"] == []
    # and it cannot be deleted from outside either
    assert c.delete(f"/v1/live/runs/{run_id}", headers=oh).status_code == 404


def test_unknown_run_is_404(stack):
    r = stack["client"].get("/v1/live/runs/live-doesnotexist",
                            headers=_h(stack, "reviewer@demo", _pid(stack)))
    assert r.status_code == 404


def test_recorded_run_refuses_missing_tile_artifacts(stack, stub_forward):
    from osteopatch import live_inference

    run_id = _post(stack, "reviewer@demo", "/v1/live/patches", _png()).json()["run"]["run_id"]
    tile = live_inference.run_dir(run_id) / "tile-0000.png"
    tile.unlink()
    response = stack["client"].get(
        f"/v1/live/runs/{run_id}", headers=_h(stack, "reviewer@demo", _pid(stack)),
    )
    assert response.status_code == 503
    assert "stored tile image is missing" in response.text


def test_recorded_run_refuses_source_hash_mismatch(stack, stub_forward):
    from osteopatch import live_inference

    run_id = _post(stack, "reviewer@demo", "/v1/live/patches", _png()).json()["run"]["run_id"]
    (live_inference.run_dir(run_id) / "source.bin").write_bytes(b"changed source")
    response = stack["client"].get(
        f"/v1/live/runs/{run_id}", headers=_h(stack, "reviewer@demo", _pid(stack)),
    )
    assert response.status_code == 503
    assert "recorded SHA-256" in response.text


def test_a_patch_run_has_no_mosaic_and_says_so(stack, stub_forward):
    run_id = _post(stack, "reviewer@demo", "/v1/live/patches", _png()).json()["run"]["run_id"]
    r = stack["client"].get(f"/v1/live/runs/{run_id}/mosaic.png",
                            headers=_h(stack, "reviewer@demo", _pid(stack)))
    assert r.status_code == 404
    assert "patch runs have none" in r.text


def test_live_runs_are_audited(stack, stub_forward):
    from enterprise import audit

    _post(stack, "reviewer@demo", "/v1/live/patches", _png())
    actions = [e["action"] for e in audit.read_entries(limit=200)]
    assert "live.predict_patch" in actions


# ---------------------------------------------------------------------------
# Corpus isolation, over HTTP
# ---------------------------------------------------------------------------
def test_live_runs_never_touch_the_frozen_corpus(stack, stub_forward):
    from osteopatch import integrity

    before = integrity.corpus_row_digest(stack["g6_conn"])
    assert before["tables"]["prediction"] == len(SEED_IMAGES)

    for colour in ((10, 10, 10), (200, 200, 200), (5, 250, 90)):
        assert _post(stack, "reviewer@demo", "/v1/live/patches",
                     _png(colour), name="x.png").status_code == 200

    after = integrity.corpus_row_digest(stack["g6_conn"])
    integrity.assert_corpus_unchanged(before, after)
    # ...and the live rows really were written, so this is not a vacuous pass
    assert stack["g6_conn"].execute("SELECT COUNT(*) FROM live_run").fetchone()[0] == 3


def test_no_live_row_ever_appears_in_the_corpus_gallery(stack, stub_forward):
    """A live run must not become reviewable corpus work."""
    _post(stack, "reviewer@demo", "/v1/live/patches", _png())
    gallery = stack["client"].get("/v1/images",
                                  headers=_h(stack, "reviewer@demo", _pid(stack))).json()
    assert gallery["total"] == len(SEED_IMAGES)
    assert all(item["image_id"] in {i[0] for i in SEED_IMAGES} for item in gallery["items"])


# ---------------------------------------------------------------------------
# torch-GATED: the same round trip with the REAL recovered head
# ---------------------------------------------------------------------------
@model_runtime
def test_real_forward_pass_over_http(stack):
    created = _post(stack, "reviewer@demo", "/v1/live/patches", _png())
    assert created.status_code == 200, created.text
    p = created.json()["prediction"]
    assert p["predicted_class"] in {"NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"}
    assert abs(sum(p["scores"].values()) - 1.0) < 1e-9
    # The class is the ARGMAX of the scores, not an independent field: a
    # response whose label disagrees with its own numbers is a broken one.
    assert p["predicted_class"] == max(p["scores"], key=p["scores"].get)
    assert "uncalibrated" in p["score_label"]
    assert created.json()["run"]["model_id"] == "g4-behavioral-recovery-r1"


@model_runtime
def test_real_slide_analysis_over_http(stack):
    wide = Image.new("RGB", (1100, 700), (150, 80, 160))
    buf = io.BytesIO()
    wide.save(buf, format="PNG")
    created = _post(stack, "path@demo", "/v1/live/slides?tile_px=384", buf.getvalue(),
                    name="field.png")
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["run"]["tiles_available"] == 6
    assert body["run"]["tile_count"] == 6
    assert body["mosaic"]["cols"] == 3 and body["mosaic"]["rows"] == 2

    run_id = body["run"]["run_id"]
    png = stack["client"].get(f"/v1/live/runs/{run_id}/mosaic.png",
                              headers=_h(stack, "path@demo", _pid(stack)))
    assert png.status_code == 200
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"
    Image.open(io.BytesIO(png.content)).load()


@model_runtime
def test_a_real_slide_run_leaves_the_corpus_byte_identical(stack):
    from osteopatch import integrity

    before = integrity.corpus_row_digest(stack["g6_conn"])
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), (150, 80, 160)).save(buf, format="PNG")
    assert _post(stack, "reviewer@demo", "/v1/live/slides", buf.getvalue(),
                 name="field.png").status_code == 200
    integrity.assert_corpus_unchanged(
        before, integrity.corpus_row_digest(stack["g6_conn"])
    )

@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_review_conflict_returns_current_revision_without_appending(stack, prefix):
    headers = _h(stack, "reviewer@demo", _pid(stack))
    client = stack["client"]
    detail = client.get(f"{prefix}/images/l-clear-nt", headers=headers).json()
    body = {"prediction_id": detail["prediction"]["prediction_id"], "action": "ACCEPT",
            "expected_revision": detail["review_state"]["revision"], "idempotency_key": "first"}
    assert client.post(f"{prefix}/images/l-clear-nt/reviews", headers=headers, json=body).status_code == 200
    body["idempotency_key"] = "second"
    conflict = client.post(f"{prefix}/images/l-clear-nt/reviews", headers=headers, json=body)
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["current_revision"] == body["expected_revision"] + 1
    after = client.get(f"{prefix}/images/l-clear-nt", headers=headers).json()
    assert len(after["history"]) == len(detail["history"]) + 1


def test_slide_upload_view_download_is_scoped_and_torch_free(stack):
    headers = _h(stack, "reviewer@demo", _pid(stack))
    data = _png()
    uploaded = stack["client"].post("/v1/slides", headers={**headers, "X-File-Name": "demo.png"}, content=data)
    assert uploaded.status_code == 200, uploaded.text
    meta = uploaded.json()
    path = f"/v1/slides/{meta['slide_id']}"
    assert meta["width"] > 0 and meta["engine"] in {"pillow", "openslide"}
    assert meta["tile_size"] == 256
    max_level = math.ceil(math.log2(max(meta["width"], meta["height"])))
    tile = stack["client"].get(f"{path}/tiles/{max_level}/0/0.png", headers=headers)
    assert tile.status_code == 200 and tile.content.startswith(b"\x89PNG")
    assert Image.open(io.BytesIO(tile.content)).size == (128, 128)
    assert stack["client"].get(f"{path}/tiles/{max_level}/0/0.png", headers={**headers, "X-Project-Id": "other-project"}).status_code == 404
    assert stack["client"].get(f"{path}/tiles/{max_level}/1/0.png", headers=headers).status_code == 404
    region = {"x": 0, "y": 0, "width": meta["width"], "height": meta["height"]}
    image = stack["client"].get(path + "/region.png", params=region, headers=headers)
    assert image.status_code == 200 and image.content.startswith(b"\x89PNG")
    thumb = stack["client"].get(path + "/thumbnail.png", headers=headers)
    assert thumb.status_code == 200 and thumb.content.startswith(b"\x89PNG")
    assert stack["client"].get(path + "/source", headers=headers).content == data
    assert stack["client"].get(path + "/source", headers={**headers, "X-Project-Id": "other-project"}).status_code == 404
    region["x"] = meta["width"]
    assert stack["client"].get(path + "/region.png", params=region, headers=headers).status_code == 422
    assert stack["client"].post("/v1/slides", headers={**headers, "X-File-Name": "bad.png"}, content=b"not pixels").status_code == 422
    assert stack["client"].post("/v1/slides", headers={**_h(stack, "student@demo", _pid(stack)), "X-File-Name": "demo.png"}, content=data).status_code == 403


def test_slide_region_analysis_preserves_parent_identity(stack, stub_forward):
    headers = _h(stack, "reviewer@demo", _pid(stack))
    meta = stack["client"].post("/v1/slides", headers={**headers, "X-File-Name": "demo.png"}, content=_png()).json()
    path = f"/v1/slides/{meta['slide_id']}/analyze"
    region = {"x": 0, "y": 0, "width": 32, "height": 32}
    result = stack["client"].post(path, headers=headers, json=region)
    assert result.status_code == 200, result.text
    assert result.json()["source_region"]["source_sha256"] == meta["source_sha256"]
    run = stack["client"].get(f"/v1/live/runs/{result.json()['run']['run_id']}", headers=headers)
    assert meta["source_sha256"] in run.json()["run"]["notes"]
    assert stack["client"].post(path, headers=headers, json={**region, "width": 999999}).status_code == 422
