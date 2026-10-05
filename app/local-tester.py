#!/usr/bin/env python
"""Local app tester — drives BOTH apps over real HTTP, against real data.

    python app/local-tester.py

What it boots (127.0.0.1 only, two free ports, nothing in AWS):

  1. G6 review API  (app/g6/backend)          -> http://127.0.0.1:<p1>
  2. Enterprise E1-E6 (app/g7-enterprise)     -> http://127.0.0.1:<p2>
       ...which imports the G6 package in-process behind auth + tenancy.

The canonical review store (runtime-artifacts/db/osteopatch_g6.sqlite3) is
NEVER written to: the tester copies it to a temp workspace, and the enterprise
users / audit chain / project scopes are created fresh there too. The canonical
store is left byte-identical (verified with sha256 before and after).

Checks are real HTTP requests against the same URLs a browser would hit — not
in-process TestClient calls. Exit code is 0 only when every check passes.

  --keep-workspace   do not delete the temp workspace on exit
  --out FILE         also write the results JSON here
  --only g6|enterprise|all

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
G6_BACKEND = REPO / "app" / "g6" / "backend"
ENT_BACKEND = REPO / "app" / "g7-enterprise" / "backend"
RUNTIME = REPO / "runtime-artifacts"
CANON_DB = RUNTIME / "db" / "osteopatch_g6.sqlite3"

FROZEN_BUNDLE = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"
BOOT_TIMEOUT = 90.0

BANNER = (
    "OsteoPatch local tester — educational research prototype. "
    "NOT for diagnosis, treatment decisions, or predicting treatment response."
)


# ---------------------------------------------------------------------------
# tiny HTTP client (stdlib only, so the tester runs on any python)
# ---------------------------------------------------------------------------
class Resp:
    def __init__(self, status: int, headers: dict, body: bytes):
        self.status = status
        self.headers = headers
        self.body = body

    def json(self):
        return json.loads(self.body.decode("utf-8"))

    def text(self, n: int = 200) -> str:
        return self.body.decode("utf-8", "replace")[:n]

    def content_type(self) -> str:
        """Case-insensitive Content-Type lookup (urllib does not normalise keys)."""
        for k, v in self.headers.items():
            if k.lower() == "content-type":
                return v
        return ""


def http(method: str, url: str, *, body=None, headers=None, timeout: float = 60.0) -> Resp:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return Resp(r.status, dict(r.headers), r.read())
    except urllib.error.HTTPError as e:  # 4xx/5xx are data, not crashes
        return Resp(e.code, dict(e.headers or {}), e.read())


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def venv_python(venv: Path) -> str | None:
    if not venv.exists():
        return None
    for rel in ("Scripts/python.exe", "bin/python"):
        p = venv / rel
        if p.exists():
            return str(p)
    return None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# results
# ---------------------------------------------------------------------------
class Results:
    def __init__(self):
        self.checks: list[dict] = []

    def check(self, group: str, name: str, ok: bool, detail: str = "") -> bool:
        self.checks.append(
            {"group": group, "name": name, "ok": bool(ok), "detail": detail[:400]}
        )
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {name}" + (f" - {detail[:160]}" if detail else ""))
        return bool(ok)

    def eq(self, group: str, name: str, actual, expected, note: str = "") -> bool:
        ok = actual == expected
        detail = note or (f"actual={actual!r} expected={expected!r}")
        return self.check(group, name, ok, detail)

    @property
    def failed(self) -> list[dict]:
        return [c for c in self.checks if not c["ok"]]


# ---------------------------------------------------------------------------
# boot
# ---------------------------------------------------------------------------
def base_env(workspace: Path, db_path: Path) -> dict:
    env = dict(os.environ)
    env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "OSTEOPATCH_PROJECT_ROOT": str(REPO),
            "OSTEOPATCH_RUNTIME_ARTIFACTS": str(RUNTIME),
            "OSTEOPATCH_DB": str(db_path),
            "OSTEOPATCH_TIFFS": str(RUNTIME / "images"),
            "OSTEOPATCH_THUMBS": str(workspace / "thumbs"),
            "OSTEOPATCH_BUNDLE": str(RUNTIME / "models" / "g4-behavioral-recovery-r1.pt"),
        }
    )
    return env


class Server:
    def __init__(self, name: str, proc: subprocess.Popen, port: int, log: Path):
        self.name = name
        self.proc = proc
        self.port = port
        self.log = log
        self.base = f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)


def spawn(name: str, args: list[str], env: dict, port: int, workspace: Path) -> Server:
    log = workspace / f"{name}.log"
    fh = log.open("wb")
    proc = subprocess.Popen(
        args, env=env, stdout=fh, stderr=subprocess.STDOUT, cwd=str(REPO)
    )
    return Server(name, proc, port, log)


def wait_healthy(server: Server, path: str) -> bool:
    deadline = time.time() + BOOT_TIMEOUT
    while time.time() < deadline:
        if server.proc.poll() is not None:
            print(f"    [{server.name}] process exited early (rc={server.proc.returncode})")
            print(f"    log tail: {server.log.read_text(errors='replace')[-800:]}")
            return False
        try:
            r = http("GET", server.base + path, timeout=5)
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    print(f"    [{server.name}] did not become healthy at {path} within {BOOT_TIMEOUT:.0f}s")
    print(f"    log tail: {server.log.read_text(errors='replace')[-800:]}")
    return False


# ---------------------------------------------------------------------------
# G6 review app — direct, unauthenticated HTTP surface
# ---------------------------------------------------------------------------
def test_g6(g6: Server, r: Results) -> dict:
    print("\n-- G6 review API (direct) " + "-" * 46)
    g = "G6"
    state: dict = {}

    h = http("GET", f"{g6.base}/v1/health")
    body = h.json() if h.status == 200 else {}
    state["health"] = body
    r.check(g, "health 200", h.status == 200, f"status={h.status}")
    r.eq(g, "model_version is the frozen G4 bundle", body.get("model_version"), "baseline-frozen-g4")
    r.eq(g, "bundle sha256 matches the frozen contract", body.get("model_bundle_sha256"), FROZEN_BUNDLE)
    r.eq(g, "1,144 images indexed", body.get("images_indexed"), 1144)
    r.eq(g, "1,144 immutable predictions", body.get("predictions"), 1144)
    r.eq(g, "no subset scoping when no allowlist is set", body.get("image_subset_scoped"), False)

    gal = http("GET", f"{g6.base}/v1/images?sort=priority&page_size=5")
    gb = gal.json() if gal.status == 200 else {}
    items = gb.get("items", [])
    r.check(g, "gallery 200", gal.status == 200, f"status={gal.status}")
    r.eq(g, "gallery total = 1,144", gb.get("total"), 1144)
    r.eq(g, "5 items on the page", len(items), 5)
    ranks = [i.get("review_priority_rank") for i in items]
    r.eq(g, "review-priority rank is 1..5 (uncertainty first)", ranks, [1, 2, 3, 4, 5])

    target = items[0]
    state["target"] = target
    det = http("GET", f"{g6.base}/v1/images/{target['image_id']}")
    db_ = det.json() if det.status == 200 else {}
    scores = (db_.get("prediction") or {}).get("scores") or {}
    r.check(g, "patch detail 200", det.status == 200, f"status={det.status}")
    r.eq(g, "exactly 3 class scores (never a 4th class)", len(scores), 3)
    r.check(
        g,
        "scores are labelled uncalibrated",
        (db_.get("prediction") or {}).get("scores_uncalibrated") is True
        or "uncalibrat" in json.dumps(db_.get("prediction") or {}).lower(),
        f"prediction keys={sorted((db_.get('prediction') or {}).keys())}",
    )

    thumb = http("GET", f"{g6.base}/v1/images/{target['image_id']}/thumbnail")
    r.check(
        g,
        "thumbnail serves REAL pixels (image/png)",
        thumb.status == 200 and thumb.body[:8] == b"\x89PNG\r\n\x1a\n",
        f"status={thumb.status} bytes={len(thumb.body)} ct={thumb.content_type()!r}",
    )

    nf = http("GET", f"{g6.base}/v1/images/Case-does-not-exist")
    r.eq(g, "unknown image_id -> 404", nf.status, 404)

    # --- review write path: create / idempotent replay / stale revision -------
    pid = (db_.get("prediction") or {}).get("prediction_id")
    state["prediction_id"] = pid
    state["scores_before"] = scores
    idem = uuid.uuid4().hex

    r1 = http(
        "POST",
        f"{g6.base}/v1/images/{target['image_id']}/reviews",
        body={
            "prediction_id": pid,
            "action": "ACCEPT",
            "expected_revision": 0,
            "idempotency_key": idem,
            "reviewer": "local-tester",
        },
    )
    r1b = r1.json() if r1.status in (200, 201) else {}
    r.eq(g, "ACCEPT creates a review event (201)", r1.status, 201)
    r.eq(g, "created flag true", r1b.get("created"), True)
    r.eq(g, "revision advanced to 1", r1b.get("current_revision"), 1)
    state["revision_1"] = r1b

    r2 = http(
        "POST",
        f"{g6.base}/v1/images/{target['image_id']}/reviews",
        body={
            "prediction_id": pid,
            "action": "ACCEPT",
            "expected_revision": 0,
            "idempotency_key": idem,
            "reviewer": "local-tester",
        },
    )
    r2b = r2.json() if r2.status in (200, 201) else {}
    r.eq(g, "replayed idempotency key -> 200 (not a new event)", r2.status, 200)
    r.eq(g, "replay reports created=false", r2b.get("created"), False)
    r.eq(g, "replay does not bump the revision", r2b.get("current_revision"), 1)

    r3 = http(
        "POST",
        f"{g6.base}/v1/images/{target['image_id']}/reviews",
        body={
            "prediction_id": pid,
            "action": "DEFER",
            "reason": "uncertain_morphology",
            "expected_revision": 0,
            "idempotency_key": uuid.uuid4().hex,
            "reviewer": "local-tester",
        },
    )
    r.eq(g, "stale expected_revision -> 409", r3.status, 409)

    hist = http("GET", f"{g6.base}/v1/images/{target['image_id']}/review")
    hb = hist.json() if hist.status == 200 else {}
    r.check(g, "review history 200", hist.status == 200, f"status={hist.status}")
    r.eq(g, "exactly one event after replay", len(hb.get("history", [])), 1)
    r.eq(g, "review status flips to reviewed", hb.get("status"), "reviewed")

    det2 = http("GET", f"{g6.base}/v1/images/{target['image_id']}")
    d2 = det2.json() if det2.status == 200 else {}
    scores_after = (d2.get("prediction") or {}).get("scores") or {}
    r.check(
        g,
        "prediction is IMMUTABLE after a human review",
        scores_after == state["scores_before"],
        f"before={state['scores_before']} after={scores_after}",
    )

    exp = http("GET", f"{g6.base}/v1/exports/reviews?format=json")
    eb = exp.json() if exp.status == 200 else {}
    rows = eb.get("rows", [])
    r.check(g, "export 200", exp.status == 200, f"status={exp.status}")
    r.eq(g, "export keeps all 1,144 predictions", eb.get("count"), 1144)
    r.check(g, "export carries the disclaimer", "NOT for diagnosis" in (eb.get("disclaimer") or ""))
    hit = next((x for x in rows if x.get("image_id") == target["image_id"]), None)
    r.check(g, "export row present for the reviewed patch", hit is not None)
    if hit:
        r.check(
            g,
            "export preserves BOTH model prediction and human action",
            bool(hit.get("model_predicted_class")) and bool(hit.get("human_latest_action")),
            f"model_predicted_class={hit.get('model_predicted_class')!r} "
            f"human_latest_action={hit.get('human_latest_action')!r}",
        )
        r.check(
            g,
            "export keeps model scores and the human label in separate columns",
            all(k in hit for k in ("model_score_NON_TUMOR", "model_score_VIABLE_TUMOR",
                                   "model_score_NECROSIS", "human_review_status")),
            f"keys={sorted(hit.keys())}",
        )

    csv_exp = http("GET", f"{g6.base}/v1/exports/reviews?format=csv")
    r.check(
        g,
        "csv export served as text/csv",
        csv_exp.status == 200 and "text/csv" in csv_exp.content_type(),
        f"status={csv_exp.status} ct={csv_exp.content_type()!r} bytes={len(csv_exp.body)}",
    )

    # ---- model card: the limitations a reviewer is entitled to see ---------
    mc = http("GET", f"{g6.base}/v1/model-card")
    mcb = mc.json() if mc.status == 200 else {}
    state["model_card"] = {
        "limitations_total": (mcb.get("limitations_summary") or {}).get("total"),
        "by_severity": (mcb.get("limitations_summary") or {}).get("by_severity"),
    }
    r.check(g, "model-card 200", mc.status == 200, f"status={mc.status}")
    r.eq(g, "model-card bundle sha256 matches the frozen contract",
         mcb.get("model_bundle_sha256"), FROZEN_BUNDLE)

    frozen_lims = mcb.get("limitations") or []
    r.eq(g, "frozen G4 evaluation caveats served verbatim", len(frozen_lims), 5)
    r.check(
        g,
        "frozen caveat list is the real one (4 groups, uncalibrated)",
        any("4 groups ONLY" in s for s in frozen_lims)
        and any("uncalibrated" in s for s in frozen_lims),
        f"n={len(frozen_lims)}",
    )

    full_lims = mcb.get("limitations_full") or []
    total = (mcb.get("limitations_summary") or {}).get("total")
    r.check(
        g,
        "full limitations catalog served (not just the frozen five)",
        isinstance(full_lims, list) and total == len(full_lims) and total >= 25,
        f"total={total} groups={len(mcb.get('limitations_grouped') or [])}",
    )
    r.check(
        g,
        "every catalogued limitation cites evidence and states what would retire it",
        all(
            isinstance(d.get("evidence"), list) and d["evidence"]
            and str(d.get("retired_by") or "").strip()
            for d in full_lims
        ),
        f"n={len(full_lims)}",
    )

    model_group = next(
        (x for x in (mcb.get("limitations_grouped") or []) if x.get("category") == "model"),
        {},
    )
    model_items = model_group.get("items") or []
    first_model = model_items[0] if model_items else {}
    r.check(
        g,
        "VIABLE_TUMOR weakness leads the model group and is BLOCKING",
        first_model.get("id") == "LIM-VIABLE-WEAK"
        and first_model.get("severity") == "blocking",
        f"first={first_model.get('id')!r} sev={first_model.get('severity')!r}",
    )
    r.check(
        g,
        "VIABLE_TUMOR weakness quotes the frozen pooled recall (0.110345)",
        "0.110345" in str(first_model.get("statement") or ""),
        f"stmt={str(first_model.get('statement') or '')[:90]!r}",
    )
    r.check(
        g,
        "model card states the claim boundary",
        "NOT for diagnosis" in (mcb.get("disclaimer") or ""),
    )

    # Attribution needs torch + the recovered bundle; the torch-free G6 web venv
    # must degrade honestly. Either it works, or it refuses — never a fake map.
    attr = http("GET", f"{g6.base}/v1/images/{target['image_id']}/attribution")
    r.check(
        g,
        "attribution is real or honestly refuses (never a fabricated map)",
        attr.status in (200, 501, 503),
        f"status={attr.status} body={attr.text(120)!r}",
    )
    if attr.status == 200:
        state["attribution_available"] = True
    else:
        state["attribution_available"] = False
        print(f"       note: torch-free venv -> attribution degrades to {attr.status} "
              f"(expected; use the torch venv for live Grad-CAM)")
    return state


# ---------------------------------------------------------------------------
# Enterprise layer — auth, RBAC, tenancy, governance, registry, drift, audit
# ---------------------------------------------------------------------------
def test_enterprise(ent: Server, state: dict, r: Results, args_g6_url: str = "") -> None:
    print("\n-- Enterprise E1-E6 (auth / RBAC / tenancy / governance) " + "-" * 11)
    e = "E1-E6"

    health = http("GET", f"{ent.base}/v1/health")
    hb = health.json() if health.status == 200 else {}
    r.check(e, "enterprise health 200", health.status == 200, f"status={health.status}")
    r.check(
        e,
        "review backend (G6) reachable in-process",
        (hb.get("review_backend") or {}).get("available") is True,
        f"review_backend={hb.get('review_backend')}",
    )
    r.check(e, "audit chain verifies on boot", hb.get("audit_chain_ok") is True)

    # --- authn ---------------------------------------------------------------
    def login(email: str) -> str | None:
        res = http("POST", f"{ent.base}/auth/login", body={"email": email})
        if res.status != 200:
            return None
        return res.json().get("access_token")

    tok = {e_: login(f"{e_}@demo") for e_ in ("admin", "path", "reviewer", "student", "mle", "auditor")}
    r.check(e, "all 6 seeded roles can log in", all(tok.values()), f"tokens={sum(1 for v in tok.values() if v)}/6")

    unknown = http("POST", f"{ent.base}/auth/login", body={"email": "nobody@demo"})
    r.eq(e, "unknown user cannot auto-provision on login", unknown.status, 401)

    def H(t, pid=None, extra=None):
        h = {}
        if t:
            h["Authorization"] = f"Bearer {t}"
        if pid:
            h["X-Project-Id"] = pid
        h.update(extra or {})
        return h

    # No credentials at all, and no project context: authn must be checked first.
    anon = http("GET", f"{ent.base}/api/v1/images")
    r.eq(e, "no bearer token at all -> 401", anon.status, 401)
    bogus = http("GET", f"{ent.base}/api/v1/images", headers=H("not-a-jwt"))
    r.eq(e, "forged token -> 401", bogus.status, 401)

    me = http("GET", f"{ent.base}/auth/me", headers=H(tok["reviewer"]))
    meb = me.json() if me.status == 200 else {}
    r.eq(e, "whoami returns the caller's membership", len(meb.get("memberships", [])), 1)
    pid = (meb.get("memberships") or [{}])[0].get("project_id")
    r.check(e, "demo project id resolved", bool(pid), f"pid={pid}")

    nopid = http("GET", f"{ent.base}/api/v1/images", headers=H(tok["reviewer"]))
    r.eq(e, "missing X-Project-Id -> 400 (project scoping is mandatory)", nopid.status, 400)

    # --- tenancy (fail-closed) ----------------------------------------------
    outsider = http("GET", f"{ent.base}/api/v1/images", headers=H(tok["reviewer"], "proj-does-not-exist"))
    r.eq(e, "non-member project -> 404 (does not leak existence)", outsider.status, 404)

    scope = http("POST", f"{ent.base}/v1/projects/{pid}/scope", body={"limit": 30}, headers=H(tok["admin"]))
    sb = scope.json() if scope.status == 200 else {}
    r.eq(e, "admin grants 30 real images into the project", sb.get("granted"), 30)

    unknown_ids = http(
        "POST",
        f"{ent.base}/v1/projects/{pid}/scope",
        body={"image_ids": ["totally-made-up-id"]},
        headers=H(tok["admin"]),
    )
    r.eq(e, "unknown image_ids rejected (fail-closed scope)", unknown_ids.status, 400)

    gal = http("GET", f"{ent.base}/api/v1/images?sort=priority&page_size=50", headers=H(tok["reviewer"], pid))
    gb = gal.json() if gal.status == 200 else {}
    items = gb.get("items", [])
    r.check(e, "scoped gallery 200", gal.status == 200, f"status={gal.status}")
    r.eq(e, "gallery is scoped to the granted 30", gb.get("total"), 30)
    r.check(
        e,
        "every scoped item is a real G6 prediction",
        all(i.get("prediction", {}).get("prediction_id") for i in items),
    )

    scoped_ids = [i["image_id"] for i in items]
    # An image that is real in G6 but NOT in this project's scope must 404.
    # The G6 server is up in every mode, so resolve the probe from the live
    # corpus rather than depending on the G6 phase having run first.
    probe = (state.get("target") or {}).get("image_id")
    if not probe or probe in scoped_ids:
        corpus = http("GET", f"{args_g6_url}/v1/images?sort=image_id&page_size=500").json()
        probe = next((i["image_id"] for i in corpus.get("items", [])
                      if i["image_id"] not in scoped_ids), None)
    if probe and probe not in scoped_ids:
        outside = http("GET", f"{ent.base}/api/v1/images/{probe}", headers=H(tok["reviewer"], pid))
        r.eq(e, "real-but-out-of-scope patch -> 404 (tenancy boundary)", outside.status, 404)
    else:
        r.check(e, "an out-of-scope probe image was available", False,
                "could not find a corpus image outside the project scope")
    in_scope = http("GET", f"{ent.base}/api/v1/images/{scoped_ids[0]}", headers=H(tok["reviewer"], pid))
    r.eq(e, "in-scope patch detail resolves", in_scope.status, 200)

    # --- RBAC ----------------------------------------------------------------
    adj_denied = http(
        "POST",
        f"{ent.base}/v1/projects/{pid}/adjudications",
        body={"image_id": scoped_ids[0], "resolved_label": "NECROSIS"},
        headers=H(tok["reviewer"], pid),
    )
    r.eq(e, "reviewer cannot adjudicate -> 403", adj_denied.status, 403)

    adj_student = http(
        "POST",
        f"{ent.base}/v1/projects/{pid}/adjudications",
        body={"image_id": scoped_ids[0], "resolved_label": "NECROSIS"},
        headers=H(tok["student"], pid),
    )
    r.eq(e, "student cannot adjudicate -> 403", adj_student.status, 403)

    proj_denied = http("POST", f"{ent.base}/v1/projects", body={"name": "nope"}, headers=H(tok["reviewer"]))
    r.eq(e, "reviewer cannot create projects -> 403", proj_denied.status, 403)

    audit_denied = http("GET", f"{ent.base}/v1/audit", headers=H(tok["reviewer"]))
    r.eq(e, "reviewer cannot read the audit log -> 403", audit_denied.status, 403)

    model_denied = http("GET", f"{ent.base}/v1/models/serving", headers=H(tok["reviewer"]))
    r.eq(e, "reviewer cannot touch the model registry -> 403", model_denied.status, 403)

    # --- review through the authz gate --------------------------------------
    tgt = items[0]
    pid_pred = (tgt.get("prediction") or {}).get("prediction_id")
    corr = http(
        "POST",
        f"{ent.base}/api/v1/images/{tgt['image_id']}/reviews",
        body={
            "prediction_id": pid_pred,
            "action": "CORRECT",
            "selected_label": "NECROSIS",
            "expected_revision": 0,
            "idempotency_key": uuid.uuid4().hex,
        },
        headers=H(tok["reviewer"], pid),
    )
    cb = corr.json() if corr.status in (200, 201) else {}
    r.check(e, "CORRECT accepted through the RBAC gate", corr.status in (200, 201), f"status={corr.status}")
    r.eq(e, "CORRECT recorded as a new event", cb.get("created"), True)

    reread = http("GET", f"{ent.base}/api/v1/images/{tgt['image_id']}", headers=H(tok["reviewer"], pid))
    rdb = reread.json() if reread.status == 200 else {}
    r.eq(
        e,
        "review survives a reload (status flips to reviewed)",
        (rdb.get("review_state") or {}).get("status"),
        "reviewed",
    )
    r.eq(
        e,
        "the human CORRECT label is recorded separately from the model",
        (rdb.get("review_state") or {}).get("selected_class"),
        "NECROSIS",
    )
    r.check(
        e,
        "model prediction unchanged by the human correction",
        (rdb.get("prediction") or {}).get("scores") == (tgt.get("prediction") or {}).get("scores"),
    )
    r.eq(e, "history length 1 after the correction", len(rdb.get("history", [])), 1)

    # --- E2 ingestion --------------------------------------------------------
    ds = http(
        "POST",
        f"{ent.base}/v1/datasets",
        body={"source": "TCIA-Osteosarcoma", "license": "TCIA", "split_declared": "slide-group-independent"},
        headers=H(tok["admin"]),
    )
    dsb = ds.json() if ds.status == 200 else {}
    r.check(e, "E2 dataset registered", ds.status == 200, f"status={ds.status}")

    man = http(
        "POST",
        f"{ent.base}/v1/datasets/{dsb.get('dataset_id')}/manifest",
        body={"rows": [
            {"image_id": scoped_ids[0], "original_label": "NON_TUMOR", "source_group": "Case-3"},
            {"image_id": scoped_ids[1], "original_label": "NECROSIS", "source_group": "Case-3"},
        ]},
        headers=H(tok["admin"]),
    )
    r.check(e, "E2 valid manifest indexed", man.status == 200, f"status={man.status}")

    bad = http(
        "POST",
        f"{ent.base}/v1/datasets/{dsb.get('dataset_id')}/manifest",
        body={"rows": [{"image_id": "x1", "original_label": "MIXED_VIABLE_NECROTIC", "source_group": "P1"}]},
        headers=H(tok["admin"]),
    )
    r.eq(e, "E2 fails closed on a non-canonical label", bad.status, 400)

    # --- E3 inference enqueue ------------------------------------------------
    enq1 = http(
        "POST",
        f"{ent.base}/v1/inference/enqueue",
        body={"image_ids": scoped_ids[:5], "bundle_sha256": FROZEN_BUNDLE},
        headers=H(tok["mle"]),
    )
    e1 = enq1.json() if enq1.status == 200 else {}
    r.eq(e, "E3 enqueue creates tasks", e1.get("newly_queued"), 5)
    enq2 = http(
        "POST",
        f"{ent.base}/v1/inference/enqueue",
        body={"image_ids": scoped_ids[:5], "bundle_sha256": FROZEN_BUNDLE},
        headers=H(tok["mle"]),
    )
    e2 = enq2.json() if enq2.status == 200 else {}
    r.eq(e, "E3 enqueue is idempotent (re-enqueue adds nothing)", e2.get("newly_queued"), 0)

    # --- E4 governance -------------------------------------------------------
    adj = http(
        "POST",
        f"{ent.base}/v1/projects/{pid}/adjudications",
        body={"image_id": scoped_ids[0], "resolved_label": "NECROSIS", "rationale": "local tester"},
        headers=H(tok["path"], pid),
    )
    r.check(e, "pathologist adjudicates", adj.status == 200, f"status={adj.status}")

    cap = http(
        "POST",
        f"{ent.base}/v1/projects/{pid}/corrections",
        body={"image_id": scoped_ids[0], "from_label": "VIABLE_TUMOR", "to_label": "NECROSIS"},
        headers=H(tok["reviewer"], pid),
    )
    capb = cap.json() if cap.status == 200 else {}
    r.check(e, "correction captured", cap.status == 200, f"status={cap.status}")
    r.eq(e, "corrections are capture-only (never auto-retrain)", capb.get("consumed_by_training"), False)

    so = http(
        "POST",
        f"{ent.base}/v1/projects/{pid}/signoffs",
        body={"image_ids": scoped_ids[:5], "states": {i: "deferred" for i in scoped_ids[:5]}},
        headers=H(tok["path"], pid),
    )
    sob = so.json() if so.status == 200 else {}
    r.check(e, "batch sign-off accepted", so.status == 200, f"status={so.status}")
    r.eq(e, "sign-off batch is locked (tamper-evident)", sob.get("locked"), True)
    r.check(e, "sign-off carries a content hash", bool(sob.get("content_sha")))

    # --- E5 registry ---------------------------------------------------------
    reg = http(
        "POST",
        f"{ent.base}/v1/models",
        body={
            "bundle_sha256": FROZEN_BUNDLE,
            "model_id": "baseline-frozen-g4",
            "eval_card_ref": "aidlc-docs g4",
            "split_declared": "slide-group-independent (LOGO)",
        },
        headers=H(tok["mle"]),
    )
    r.check(e, "E5 registers the frozen bundle", reg.status == 200, f"status={reg.status}")
    for to in ("candidate", "shadow"):
        st = http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": FROZEN_BUNDLE, "to": to}, headers=H(tok["mle"]))
        r.check(e, f"E5 promote {reg.status and to}", st.status == 200, f"status={st.status}")
    srv = http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": FROZEN_BUNDLE, "to": "serving", "eval_passed": True}, headers=H(tok["mle"]))
    srvb = srv.json() if srv.status == 200 else {}
    r.check(e, "E5 promotes to serving with eval gate", srv.status == 200, f"status={srv.status}")
    r.eq(e, "serving state is 'serving'", srvb.get("state"), "serving")

    # A second candidate that must NOT reach serving without a passing eval gate.
    http(
        "POST",
        f"{ent.base}/v1/models",
        body={"bundle_sha256": "a" * 64, "model_id": "no-eval", "eval_card_ref": "x", "split_declared": "x"},
        headers=H(tok["mle"]),
    )
    http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": "a" * 64, "to": "candidate"}, headers=H(tok["mle"]))
    http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": "a" * 64, "to": "shadow"}, headers=H(tok["mle"]))
    g3 = http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": "a" * 64, "to": "serving"}, headers=H(tok["mle"]))
    r.eq(e, "E5 refuses to serve a model whose eval did not pass", g3.status, 400)

    serving_now = http("GET", f"{ent.base}/v1/models/serving", headers=H(tok["mle"]))
    sbn = serving_now.json() if serving_now.status == 200 else {}
    r.eq(e, "serving model is the frozen G4 bundle", sbn.get("model_id"), "baseline-frozen-g4")

    # Promote a second, eval-passed bundle: the single-serving invariant retires
    # the incumbent, which is what makes a rollback possible.
    v2 = "b" * 64
    http(
        "POST",
        f"{ent.base}/v1/models",
        body={"bundle_sha256": v2, "model_id": "candidate-v2", "eval_card_ref": "shadow",
              "split_declared": "slide-group-independent"},
        headers=H(tok["mle"]),
    )
    for to in ("candidate", "shadow"):
        http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": v2, "to": to}, headers=H(tok["mle"]))
    up = http("POST", f"{ent.base}/v1/models/promote", body={"bundle_sha256": v2, "to": "serving", "eval_passed": True}, headers=H(tok["mle"]))
    r.check(e, "a second bundle takes over serving", up.status == 200, f"status={up.status}")
    s2 = http("GET", f"{ent.base}/v1/models/serving", headers=H(tok["mle"]))
    s2b = s2.json() if s2.status == 200 else {}
    r.eq(e, "single-serving invariant: serving is now candidate-v2 only", s2b.get("model_id"), "candidate-v2")

    rb = http("POST", f"{ent.base}/v1/models/rollback", headers=H(tok["mle"]))
    rbb = rb.json() if rb.status == 200 else {}
    r.check(e, "E5 one-click rollback works", rb.status == 200, f"status={rb.status} body={rb.text(120)}")
    r.eq(e, "rollback restores the frozen G4 bundle", rbb.get("model_id"), "baseline-frozen-g4")
    s3 = http("GET", f"{ent.base}/v1/models/serving", headers=H(tok["mle"]))
    s3b = s3.json() if s3.status == 200 else {}
    r.eq(e, "exactly one serving model after rollback", s3b.get("model_id"), "baseline-frozen-g4")

    # --- E6 drift ------------------------------------------------------------
    dr = http(
        "GET",
        f"{ent.base}/v1/projects/{pid}/drift?bundle_sha256={FROZEN_BUNDLE}",
        headers=H(tok["mle"]),
    )
    drb = dr.json() if dr.status == 200 else {}
    r.check(e, "E6 drift report returned", dr.status == 200, f"status={dr.status}")
    r.check(e, "drift is computed over the scoped project predictions", (drb.get("n_predictions") or 0) > 0,
            f"n_predictions={drb.get('n_predictions')} n_reviewed={drb.get('n_reviewed')}")
    r.check(e, "drift reports an alert list", isinstance(drb.get("alerts"), list), f"alerts={drb.get('alerts')}")

    drift_denied = http(
        "GET",
        f"{ent.base}/v1/projects/{pid}/drift?bundle_sha256={FROZEN_BUNDLE}",
        headers=H(tok["reviewer"]),
    )
    r.eq(e, "reviewer cannot read drift -> 403", drift_denied.status, 403)

    # --- audit ---------------------------------------------------------------
    av = http("GET", f"{ent.base}/v1/audit", headers=H(tok["auditor"]))
    avb = av.json() if av.status == 200 else {}
    r.check(e, "auditor reads the audit log", av.status == 200, f"status={av.status}")
    r.eq(e, "hash chain verifies", avb.get("chain_ok"), True)
    r.check(e, "audit entries were written", (avb.get("entries_verified") or 0) > 0,
            f"entries={avb.get('entries_verified')}")
    kinds = {en.get("action") for en in (avb.get("entries") or [])}
    r.check(e, "every mutation kind is audited", {"review.submit", "auth.login"} <= kinds, f"kinds={sorted(k for k in kinds if k)}")


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Local full-stack tester for G6 + Enterprise E1-E6")
    ap.add_argument("--keep-workspace", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--only", choices=["g6", "enterprise", "all"], default="all")
    args = ap.parse_args()

    print("=" * 78)
    print(BANNER)
    print("=" * 78)

    if not CANON_DB.exists():
        print(f"FATAL: canonical review store not found: {CANON_DB}")
        print("       (it is gitignored runtime data — see runtime-artifacts/)")
        return 2

    canon_before = sha256(CANON_DB)
    workspace = Path(tempfile.mkdtemp(prefix="osteopatch-tester-"))
    print(f"workspace : {workspace}")
    print(f"canonical: {CANON_DB} (sha256 {canon_before[:16]}… — never written)")

    db_copy = workspace / "osteopatch_g6.sqlite3"
    shutil.copy2(CANON_DB, db_copy)
    (workspace / "thumbs").mkdir(exist_ok=True)
    (workspace / "project_scopes").mkdir(exist_ok=True)

    g6_py = venv_python(G6_BACKEND / ".venv")
    ent_py = venv_python(ENT_BACKEND / ".webvenv")
    print(f"g6 venv  : {g6_py or 'MISSING -> falling back to sys.executable'}")
    print(f"ent venv : {ent_py or 'MISSING -> falling back to sys.executable'}")

    g6_env = base_env(workspace, db_copy)
    g6_env["PYTHONPATH"] = str(G6_BACKEND)
    g6_env["OSTEOPATCH_PORT"] = str(free_port())

    ent_env = base_env(workspace, db_copy)
    ent_env["PYTHONPATH"] = os.pathsep.join([str(ENT_BACKEND), str(G6_BACKEND)])
    ent_env["OSTEOPATCH_ENT_DB"] = str(workspace / "enterprise.sqlite3")
    ent_env["OSTEOPATCH_AUDIT_LOG"] = str(workspace / "audit_chain.jsonl")
    ent_env["OSTEOPATCH_PROJECT_SCOPES"] = str(workspace / "project_scopes")
    ent_env["OSTEOPATCH_ENT_SCRATCH"] = str(workspace)
    ent_env["OSTEOPATCH_ENT_PORT"] = str(free_port())

    g6 = ent = None
    r = Results()
    try:
        print("\nbooting G6 review API …")
        g6 = spawn("g6", [g6_py or sys.executable, "-m", "osteopatch.server"], g6_env,
                   int(g6_env["OSTEOPATCH_PORT"]), workspace)
        if not wait_healthy(g6, "/v1/health"):
            print("FATAL: G6 review API did not start")
            return 2
        print(f"  up: {g6.base}")

        print("seeding enterprise demo users …")
        seed = subprocess.run(
            [ent_py or sys.executable, "-m", "enterprise.seed"],
            env=ent_env, cwd=str(REPO), capture_output=True, text=True, timeout=180,
        )
        if seed.returncode != 0:
            print(f"FATAL: seed failed rc={seed.returncode}\n{seed.stdout}\n{seed.stderr}")
            return 2

        print("booting enterprise E1-E6 …")
        ent = spawn("ent", [ent_py or sys.executable, "-m", "uvicorn", "enterprise.app:app",
                            "--host", "127.0.0.1", "--port", ent_env["OSTEOPATCH_ENT_PORT"],
                            "--log-level", "warning"],
                    ent_env, int(ent_env["OSTEOPATCH_ENT_PORT"]), workspace)
        if not wait_healthy(ent, "/v1/health"):
            print("FATAL: enterprise app did not start")
            return 2
        print(f"  up: {ent.base}")

        state: dict = {}
        if args.only in ("g6", "all"):
            state = test_g6(g6, r)
        if args.only in ("enterprise", "all"):
            test_enterprise(ent, state, r, args_g6_url=g6.base)

        canon_after = sha256(CANON_DB)
        r.check(
            "safety",
            "canonical review store is byte-identical after the run",
            canon_before == canon_after,
            f"before={canon_before[:16]}… after={canon_after[:16]}…",
        )

    finally:
        for s in (ent, g6):
            if s:
                s.stop()
        print("\nstopped servers.")

    passed = len(r.checks) - len(r.failed)
    print("\n" + "=" * 78)
    print(f"RESULT: {passed}/{len(r.checks)} checks passed")
    if r.failed:
        print("\nFAILED:")
        for c in r.failed:
            print(f"  - [{c['group']}] {c['name']}: {c['detail']}")
    print(f"G6     : {g6.base if g6 else 'n/a'}")
    print(f"Enter. : {ent.base if ent else 'n/a'}")
    print("=" * 78)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(
                {
                    "banner": BANNER,
                    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "g6_url": g6.base if g6 else None,
                    "enterprise_url": ent.base if ent else None,
                    "canonical_db_sha256": canon_before,
                    "passed": passed,
                    "total": len(r.checks),
                    "checks": r.checks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"results written to {out}")

    if not args.keep_workspace:
        shutil.rmtree(workspace, ignore_errors=True)
    else:
        print(f"workspace kept at {workspace}")

    return 0 if not r.failed else 1


if __name__ == "__main__":
    sys.exit(main())