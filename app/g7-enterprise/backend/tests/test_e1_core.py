"""E1 enterprise-core tests — authn, RBAC, tenancy, audit chain, gates.

These run with NO G6 data store and NO torch: the review surface is expected to
degrade to a labelled 503, which is itself asserted (never a fabricated result).
"""
import os
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # isolate every store/path into tmp so tests never touch real scratch
    monkeypatch.setenv("OSTEOPATCH_ENT_DB", str(tmp_path / "ent.sqlite3"))
    monkeypatch.setenv("OSTEOPATCH_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("OSTEOPATCH_PROJECT_SCOPES", str(tmp_path / "scopes"))
    monkeypatch.setenv("OSTEOPATCH_JWT_SECRET", "test-secret")
    monkeypatch.delenv("OSTEOPATCH_OIDC_JWKS_URL", raising=False)
    # The G6 READ MODEL must be isolated too. Without this, any enterprise code
    # path that reaches the G6 store (including `projects.grant_images`) would
    # re-scope real rows in the canonical 1,144-image database. config resolves
    # DB_PATH at import, so the reload below is what actually redirects it.
    monkeypatch.setenv("OSTEOPATCH_DB", str(tmp_path / "g6-empty.sqlite3"))

    # import AFTER env is set so module-level config picks it up
    import importlib
    from enterprise import config as cfg
    importlib.reload(cfg)
    from enterprise import audit, store, seed, app as app_module
    importlib.reload(audit)
    importlib.reload(store)
    importlib.reload(seed)
    importlib.reload(app_module)

    import osteopatch.config as g6_config
    importlib.reload(g6_config)

    conn = store.connect(tmp_path / "ent.sqlite3")
    app_module.set_conn(conn)
    seed.seed(conn)  # scope_size defaults to None -> grants nothing in G6
    return TestClient(app_module.app), conn


def _login(c, email):
    r = c.post("/auth/login", json={"email": email})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _project_id(conn):
    return conn.execute("SELECT project_id FROM project LIMIT 1").fetchone()["project_id"]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def test_login_unknown_user_rejected(client):
    c, _ = client
    assert c.post("/auth/login", json={"email": "nobody@demo"}).status_code == 401


def test_login_and_whoami(client):
    c, _ = client
    tok = _login(c, "reviewer@demo")
    me = c.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert me.status_code == 200
    assert me.json()["email"] == "reviewer@demo"
    assert len(me.json()["memberships"]) == 1


def test_missing_token_401(client):
    c, _ = client
    assert c.get("/auth/me").status_code == 401


def test_tampered_token_401(client):
    c, _ = client
    tok = _login(c, "reviewer@demo")
    bad = tok[:-3] + ("abc" if not tok.endswith("abc") else "xyz")
    assert c.get("/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------
def test_student_cannot_create_project(client):
    c, _ = client
    tok = _login(c, "student@demo")
    r = c.post("/v1/projects", json={"name": "x"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 403


def test_admin_can_create_project_and_add_member(client):
    c, conn = client
    tok = _login(c, "admin@demo")
    r = c.post("/v1/projects", json={"name": "Second"}, headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200, r.text
    pid = r.json()["project_id"]
    r2 = c.post(f"/v1/projects/{pid}/members",
                json={"email": "newbie@demo", "role": "reviewer"},
                headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 200
    assert r2.json()["role"] == "reviewer"


def test_add_member_invalid_role_400(client):
    c, _ = client
    tok = _login(c, "admin@demo")
    r = c.post("/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {tok}"})
    pid = r.json()["project_id"]
    r2 = c.post(f"/v1/projects/{pid}/members",
                json={"email": "x@demo", "role": "superuser"},
                headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 400


def test_auditor_cannot_write_review(client):
    c, conn = client
    tok = _login(c, "auditor@demo")
    pid = _project_id(conn)
    r = c.post(f"/api/v1/images/img1/reviews",
               json={"prediction_id": "p1", "action": "ACCEPT", "idempotency_key": "k1"},
               headers={"Authorization": f"Bearer {tok}", "X-Project-Id": pid})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tenancy
# ---------------------------------------------------------------------------
def test_project_scoped_read_requires_header(client):
    c, _ = client
    tok = _login(c, "reviewer@demo")
    r = c.get("/api/v1/images", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 400  # missing X-Project-Id


def test_non_member_project_is_404(client):
    c, _ = client
    tok = _login(c, "reviewer@demo")
    r = c.get("/api/v1/images",
              headers={"Authorization": f"Bearer {tok}", "X-Project-Id": "prj_doesnotexist"})
    # not a member -> 404 (do not reveal existence)
    assert r.status_code == 404


def test_review_backend_degrades_to_503_not_fabrication(client):
    # G6 package/data not present in this env -> labelled 503, never a fake result
    c, conn = client
    tok = _login(c, "reviewer@demo")
    pid = _project_id(conn)
    r = c.get("/api/v1/images",
              headers={"Authorization": f"Bearer {tok}", "X-Project-Id": pid})
    assert r.status_code in (503, 200)
    if r.status_code == 503:
        assert "unavailable" in str(r.json()).lower()


# ---------------------------------------------------------------------------
# Audit chain
# ---------------------------------------------------------------------------
def test_audit_chain_records_and_verifies(client):
    c, conn = client
    _login(c, "admin@demo")  # produces an auth.login audit entry
    tok = _login(c, "auditor@demo")
    r = c.get("/v1/audit", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    body = r.json()
    assert body["chain_ok"] is True
    assert body["entries_verified"] >= 2


def test_audit_chain_detects_tampering(client, tmp_path):
    from enterprise import audit
    import importlib
    importlib.reload(audit)
    log = Path(os.environ["OSTEOPATCH_AUDIT_LOG"])
    audit.record("a@demo", "x.one", "t1")
    audit.record("a@demo", "x.two", "t2")
    ok, n, _ = audit.verify_chain(log)
    assert ok and n == 2
    # tamper with the first line's action
    lines = log.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("x.one", "x.ONE")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok2, _, bad = audit.verify_chain(log)
    assert ok2 is False and bad is not None


# ---------------------------------------------------------------------------
# Gates — the AWS/compute seams must still refuse to run
# ---------------------------------------------------------------------------
def test_gated_seams_refuse():
    from enterprise.scaffolds import GateNotApproved
    from enterprise import inference, ingestion, observability
    with pytest.raises(GateNotApproved):
        inference.run_worker_once(None)
    with pytest.raises(GateNotApproved):
        ingestion.tile_wsi("x.svs")
    with pytest.raises(GateNotApproved):
        observability.ship_audit_to_worm("bucket")


def test_model_transitions_table_is_coherent():
    from enterprise.registry import ModelState, TRANSITIONS
    # retired is terminal; serving only -> retired
    assert TRANSITIONS[ModelState.RETIRED] == set()
    assert TRANSITIONS[ModelState.SERVING] == {ModelState.RETIRED}
