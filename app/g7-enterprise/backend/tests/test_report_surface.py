"""Enterprise case-report surface: authz, tenancy, exports, and isolation.

The rules this file defends:

  * ``report:write`` is a WRITER action and ``report:read`` a READER one, split
    exactly as ``CAPABILITIES`` declares. A persona that may read must not be
    able to author; a persona that may author must not be able to bypass the
    project boundary.
  * A report never mutates the corpus or the audit trail.
  * Both exports come back from ONE stored document and agree.
  * The stored hash is recomputed on read, so a reader can tell whether the
    document is the one that was signed.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

FROZEN_HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"

SEED_IMAGES = [
    ("Case-3-A10-10547-25283", [0.90, 0.05, 0.05]),
    ("Case-3-A10-10566-40206", [0.20, 0.10, 0.70]),
]


@pytest.fixture()
def stack(tmp_path, monkeypatch):
    """Enterprise app in front of a real G6 read model.

    The reloads are not optional: ``osteopatch.config`` freezes DB_PATH at
    import time, and the G6 app module holds the connection object. Without
    both, the app keeps reading the CANONICAL store while the test mutates a
    temp copy — which fails in a way that looks like a product bug.
    """
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
    from osteopatch import integrity, repo

    g6_config.TIFFS_DIR = tmp_path / "tiffs"
    g6_config.THUMBS_DIR = tmp_path / "thumbs"
    g6_config.ATTRIB_IMAGES_DIR = tmp_path / "tiffs"

    g6_conn = g6_db.connect(tmp_path / "g6.sqlite3")
    g6_db.run_migrations(g6_conn)
    for image_id, scores in SEED_IMAGES:
        g6_conn.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label,"
            " primary_qc_status, training_eligible, qc_review_flag, qc_review_reason,"
            " tiff_filename) VALUES (?,?,?,'PASS',1,0,NULL,?)",
            (image_id, "Case-3-A10", scores[2] and None, f"{image_id}.tiff"),
        )
        repo.upsert_prediction(g6_conn, image_id, FROZEN_HASH,
                               "baseline-frozen-g4", scores)
    g6_conn.commit()
    g6_app.set_conn(g6_conn)

    ent_conn = store.connect(tmp_path / "ent.sqlite3")
    app_module.set_conn(ent_conn)
    seeded = seed.seed(ent_conn, scope_size=seed.DEMO_SCOPE_SIZE)
    pid = seeded["project_id"]

    return {
        "client": TestClient(app_module.app),
        "g6_conn": g6_conn,
        "ent_conn": ent_conn,
        "integrity": integrity,
        "pid": pid,
        "images": [s[0] for s in SEED_IMAGES],
    }


def _login(stack, email):
    return stack["client"].post("/auth/login", json={"email": email}).json()["access_token"]


def _h(stack, email, project_id=None):
    h = {"Authorization": f"Bearer {_login(stack, email)}"}
    pid = project_id or stack["pid"]
    if pid:
        h["X-Project-Id"] = pid
    return h


def _post_report(stack, email, **over):
    body = {
        "case_id": "Case-3-A10",
        "title": "Osteosarcoma — Case-3-A10",
        "findings_text": "Necrosis predominates across the sampled field.",
        "image_ids": stack["images"],
        "run_ids": [],
        **over,
    }
    return stack["client"].post("/v1/reports", headers=_h(stack, email), json=body)


# ---------------------------------------------------------------------------
# Authz
# ---------------------------------------------------------------------------


def test_a_reviewer_can_author_a_report(stack):
    r = _post_report(stack, "reviewer@demo")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["n_images"] == 2
    assert body["author_email"] == "reviewer@demo"
    assert body["is_signed"] is False
    assert len(body["content_sha256"]) == 64


@pytest.mark.parametrize("route", ["/v1/images", "/api/v1/images"])
def test_gallery_search_is_applied_inside_project_scope(stack, route):
    headers = _h(stack, "reviewer@demo")
    response = stack["client"].get(route, headers=headers, params={"q": "10547"})
    assert response.status_code == 200
    assert [item["image_id"] for item in response.json()["items"]] == [stack["images"][0]]
    missing = stack["client"].get(route, headers=headers, params={"q": "not-in-the-corpus"})
    assert missing.json()["total"] == 0


def test_a_reader_only_persona_cannot_author_a_report(stack):
    """These are the roles the capability map excludes, by design."""
    for email in ("student@demo", "auditor@demo", "mle@demo"):
        assert _post_report(stack, email).status_code == 403, email


def test_a_reader_only_persona_CAN_read_a_report(stack):
    created = _post_report(stack, "reviewer@demo").json()
    for email in ("student@demo", "auditor@demo", "mle@demo", "path@demo"):
        r = stack["client"].get(f"/v1/reports/{created['report_id']}", headers=_h(stack, email))
        assert r.status_code == 200, email


def test_no_token_is_401(stack):
    assert stack["client"].get("/v1/reports").status_code == 401
    assert stack["client"].post("/v1/reports", json={}).status_code == 401


def test_anonymous_export_is_401(stack):
    created = _post_report(stack, "reviewer@demo").json()
    assert stack["client"].get(
        f"/v1/reports/{created['report_id']}/export.html").status_code == 401


# ---------------------------------------------------------------------------
# Tenancy
# ---------------------------------------------------------------------------


def test_another_project_cannot_read_or_export_the_report(stack):
    from enterprise import store
    ent = store.connect()
    admin = store.upsert_user(ent, "admin@demo")
    other = store.create_project(ent, "Other", admin["user_id"])["project_id"]

    created = _post_report(stack, "reviewer@demo").json()
    rid = created["report_id"]
    assert stack["client"].get(f"/v1/reports/{rid}",
                               headers=_h(stack, "reviewer@demo", other)).status_code == 404
    assert stack["client"].get(f"/v1/reports/{rid}/export.html",
                               headers=_h(stack, "reviewer@demo", other)).status_code == 404
    assert stack["client"].get(f"/v1/reports/{rid}/export.md",
                               headers=_h(stack, "reviewer@demo", other)).status_code == 404
    # The reviewer is not a member of `other` at all, so the listing is 404
    # rather than an empty array — a 404 keeps "does not exist" and "not yours"
    # indistinguishable, which is the point of the tenancy boundary.
    assert stack["client"].get("/v1/reports",
                               headers=_h(stack, "reviewer@demo", other)).status_code == 404


def test_an_unknown_image_is_404_not_a_silently_skipped_row(stack):
    r = _post_report(stack, "reviewer@demo",
                     image_ids=[stack["images"][0], "no-such-image"])
    assert r.status_code == 404


def test_a_report_with_no_images_is_400(stack):
    r = _post_report(stack, "reviewer@demo", image_ids=[], run_ids=[])
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Sign-off
# ---------------------------------------------------------------------------


def test_a_signed_report_records_who_and_when(stack):
    r = _post_report(stack, "reviewer@demo",
                     signer_email="reviewer@demo", signer_role="reviewer",
                     signoff_note="Reviewed against the frozen predictions.")
    body = r.json()
    assert body["is_signed"] is True
    assert body["signer_email"] == "reviewer@demo"
    assert body["signer_role"] == "reviewer"
    assert body["signed_at"]


def test_a_report_cannot_be_signed_as_another_user(stack):
    response = _post_report(stack, "reviewer@demo",
                            signer_email="path@demo", signer_role="pathologist")
    assert response.status_code == 403
    assert response.json()["detail"] == "signer_email must match the authenticated user"


def test_a_report_cannot_claim_another_project_role(stack):
    response = _post_report(stack, "reviewer@demo",
                            signer_email="reviewer@demo", signer_role="pathologist")
    assert response.status_code == 403


def test_signoff_is_partial_when_any_image_is_unresolved(stack):
    """A tied corpus patch must make the sign-off partial, loudly."""
    stack["g6_conn"].execute(
        "UPDATE prediction SET top_two_margin=0.0 WHERE image_id=?", (stack["images"][1],))
    stack["g6_conn"].commit()
    body = _post_report(stack, "reviewer@demo", signer_email="reviewer@demo",
                        signer_role="reviewer").json()
    assert body["n_unresolved"] == 1
    assert body["signoff_covers_all"] is False


def test_role_downgrade_applies_to_tokens_already_issued(stack):
    headers = _h(stack, "reviewer@demo")
    user = stack["ent_conn"].execute(
        "SELECT user_id FROM app_user WHERE email=?", ("reviewer@demo",),
    ).fetchone()
    stack["ent_conn"].execute(
        "UPDATE membership SET role='student' WHERE user_id=? AND project_id=?",
        (user["user_id"], stack["pid"]),
    )
    stack["ent_conn"].commit()
    response = stack["client"].post(
        "/v1/reports",
        headers=headers,
        json={"case_id": "Case-3-A10", "title": "Demo", "image_ids": stack["images"]},
    )
    assert response.status_code == 403


def test_parallel_membership_checks_use_independent_connections(stack):
    from enterprise import deps, store

    user = store.get_user_by_email(stack["ent_conn"], "reviewer@demo")
    with ThreadPoolExecutor(max_workers=12) as pool:
        roles = list(pool.map(
            lambda _: deps._live_role(user["user_id"], stack["pid"]), range(48)
        ))
    assert roles == ["reviewer"] * 48


# ---------------------------------------------------------------------------
# Exports agree and are self-contained
# ---------------------------------------------------------------------------


def test_both_exports_are_served_and_carry_the_same_hash(stack):
    rid = _post_report(stack, "reviewer@demo").json()["report_id"]
    html = stack["client"].get(f"/v1/reports/{rid}/export.html", headers=_h(stack, "reviewer@demo"))
    md = stack["client"].get(f"/v1/reports/{rid}/export.md", headers=_h(stack, "reviewer@demo"))

    assert html.status_code == 200 and "text/html" in html.headers["content-type"]
    assert md.status_code == 200 and "markdown" in md.headers["content-type"]

    detail = stack["client"].get(f"/v1/reports/{rid}", headers=_h(stack, "reviewer@demo")).json()
    sha = detail["content_sha256"]
    assert sha in html.text and sha in md.text
    for image_id in stack["images"]:
        assert image_id in html.text and image_id in md.text


def test_the_html_export_opens_offline_and_prints(stack):
    rid = _post_report(stack, "reviewer@demo").json()["report_id"]
    html = stack["client"].get(f"/v1/reports/{rid}/export.html",
                               headers=_h(stack, "reviewer@demo")).text
    assert html.startswith("<!doctype html>")
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert "https://" not in html
    assert "@media print" in html


def test_exports_attach_the_selected_image_preview(stack):
    from osteopatch import config
    from PIL import Image

    image_id = stack["images"][0]
    source = config.TIFFS_DIR / f"{image_id}.tiff"
    source.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 18), (176, 52, 117)).save(source, format="TIFF")

    created = _post_report(stack, "reviewer@demo", image_ids=[image_id], run_ids=[]).json()
    assert created["images"][0]["preview_attached"] is True
    assert "preview_png_base64" not in created["images"][0]
    html = stack["client"].get(
        f"/v1/reports/{created['report_id']}/export.html", headers=_h(stack, "reviewer@demo"),
    ).text
    markdown = stack["client"].get(
        f"/v1/reports/{created['report_id']}/export.md", headers=_h(stack, "reviewer@demo"),
    ).text
    assert "<img alt=\"Attached image preview" in html
    assert "data:image/png;base64," in html and "data:image/png;base64," in markdown


def test_an_unknown_export_format_is_404(stack):
    rid = _post_report(stack, "reviewer@demo").json()["report_id"]
    assert stack["client"].get(f"/v1/reports/{rid}/export.pdf",
                               headers=_h(stack, "reviewer@demo")).status_code == 404


# ---------------------------------------------------------------------------
# Provenance and isolation
# ---------------------------------------------------------------------------


def test_read_back_recomputes_the_hash_and_it_matches(stack):
    rid = _post_report(stack, "reviewer@demo").json()["report_id"]
    body = stack["client"].get(f"/v1/reports/{rid}", headers=_h(stack, "reviewer@demo")).json()
    v = body["hash_verification"]
    assert v["matches"] is True
    assert v["stored_sha256"] == v["recomputed_from_document_json"] == body["content_sha256"]


def test_authoring_a_report_leaves_the_corpus_byte_identical(stack):
    integ = stack["integrity"]
    before = integ.corpus_row_digest(stack["g6_conn"])
    _post_report(stack, "reviewer@demo")
    _post_report(stack, "reviewer@demo", title="Second report")
    integ.assert_corpus_unchanged(before, integ.corpus_row_digest(stack["g6_conn"]))


def test_authoring_a_report_writes_no_review_event(stack):
    before = stack["g6_conn"].execute("SELECT COUNT(*) FROM review_event").fetchone()[0]
    _post_report(stack, "reviewer@demo")
    after = stack["g6_conn"].execute("SELECT COUNT(*) FROM review_event").fetchone()[0]
    assert before == after == 0


def test_there_is_no_update_route(stack):
    """Append-only is enforced by what does NOT exist, not by a guard clause."""
    rid = _post_report(stack, "reviewer@demo").json()["report_id"]
    h = _h(stack, "reviewer@demo")
    for method, url in (
        ("put", f"/v1/reports/{rid}"),
        ("patch", f"/v1/reports/{rid}"),
        ("delete", f"/v1/reports/{rid}"),
    ):
        assert stack["client"].request(method, url, headers=h, json={}).status_code in (404, 405)


def test_a_revision_is_a_new_row_and_the_old_one_survives(stack):
    first = _post_report(stack, "reviewer@demo").json()
    second = _post_report(stack, "reviewer@demo", title="Revised title").json()
    assert first["report_id"] != second["report_id"]
    assert first["content_sha256"] != second["content_sha256"]

    got = stack["client"].get(f"/v1/reports/{first['report_id']}",
                              headers=_h(stack, "reviewer@demo")).json()
    assert got["title"] != "Revised title"
    assert got["content_sha256"] == first["content_sha256"]
    assert len(stack["client"].get("/v1/reports",
                                   headers=_h(stack, "reviewer@demo")).json()["reports"]) == 2


def test_the_report_never_claims_a_class_for_a_tied_patch(stack):
    stack["g6_conn"].execute(
        "UPDATE prediction SET top_two_margin=0.0, non_tumor_score=0.5, "
        "necrosis_score=0.499 WHERE image_id=?", (stack["images"][1],))
    stack["g6_conn"].commit()
    rid = _post_report(stack, "reviewer@demo").json()["report_id"]
    html = stack["client"].get(f"/v1/reports/{rid}/export.html",
                               headers=_h(stack, "reviewer@demo")).text
    supported = html.split("Patches that produced no call")[0]
    assert stack["images"][1] not in supported
    assert "INDETERMINATE" in html
    assert "Not for diagnosis" in html
    assert "not a probability" in html
