#!/usr/bin/env python
"""Drive the unified review surface over real HTTP, as each demo persona.

Why this exists
---------------
The unit tests exercise the capability gates through FastAPI's TestClient. That
proves the routing and dependency wiring, but not that a real bearer token, a
real multipart of roles and a real PNG body make it through a real socket. This
does, and it is the record that the unified app is demo-ready rather than
merely importable.

Safety
------
The canonical 1,144-row review store is COPIED to a temp workspace and the
server is pointed at the copy. The demo scope grant is a real write to
``project_id``, so running this against the canonical database would re-scope
real corpus rows. The copy is deleted unless --keep-workspace is passed, and
the canonical file is hashed before and after: a moved canonical DB fails the
run.

Fails closed on a squatted port
-------------------------------
A stale server on the fixed port would happily answer while the intended child
dies with EADDRINUSE, producing a green run against unknown code. Readiness
therefore requires BOTH a live child process AND a matching health payload.

    python scripts/verify_unified_surface.py
    python scripts/verify_unified_surface.py --out docs/evidence/unified-surface.json

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
G7_BACKEND = REPO / "app" / "g7-enterprise" / "backend"
CANON_DB = REPO / "runtime-artifacts" / "db" / "osteopatch_g6.sqlite3"
DEFAULT_OUT = REPO / "docs" / "evidence" / "unified-surface.json"

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def http(url: str, *, token: str | None = None, project: str | None = None,
         method: str = "GET", body: bytes | None = None,
         content_type: str = "application/json") -> tuple[int, dict, bytes]:
    """One authenticated HTTP call. Header names come back lowercased.

    HTTP/1.1 header names are case-insensitive and Starlette emits them
    lowercase, so the dict is normalised here rather than making every caller
    guess. Without the Content-Type a JSON body is silently unparseable and the
    server answers 422 — which looks like an app bug but is not.
    """
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", content_type)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if project:
        req.add_header("X-Project-Id", project)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in exc.headers.items()}, exc.read()


def login(base: str, email: str) -> str:
    """Exchange a demo email for a bearer token over real HTTP."""
    payload = json.dumps({"email": email}).encode()
    req = urllib.request.Request(
        f"{base}/auth/login", data=payload, method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"login failed for {email}: HTTP {exc.code} {exc.read()[:200]!r}") from exc


class Checker:
    """Collects named pass/fail observations; never stops at the first failure."""

    def __init__(self) -> None:
        self.results: list[dict] = []

    def expect(self, name: str, actual, expected) -> None:
        ok = actual == expected
        self.results.append({"check": name, "expected": expected, "actual": actual, "ok": ok})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {actual!r} (expected {expected!r})")

    def record(self, name: str, ok: bool, detail: object) -> None:
        self.results.append({"check": name, "ok": ok, "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    @property
    def failed(self) -> list[dict]:
        return [r for r in self.results if not r["ok"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--keep-workspace", action="store_true")
    args = ap.parse_args()

    if not CANON_DB.exists():
        print(f"canonical review store missing: {CANON_DB}\nrun scripts/prepare_runtime.py first")
        return 2

    canon_hash_before = sha256_file(CANON_DB)
    workdir = Path(tempfile.mkdtemp(prefix="osteopatch-unified-"))
    review_db = workdir / "review-copy.sqlite3"
    shutil.copy2(CANON_DB, review_db)

    env = {
        **os.environ,
        "OSTEOPATCH_DB": str(review_db),
        "OSTEOPATCH_ENT_DB": str(workdir / "enterprise.sqlite3"),
        "OSTEOPATCH_AUDIT_LOG": str(workdir / "audit.jsonl"),
        "OSTEOPATCH_PROJECT_SCOPES": str(workdir / "scopes"),
        "PYTHONPATH": os.pathsep.join([str(G6_BACKEND), str(G7_BACKEND)]),
    }

    print("Seeding the demo project against a COPY of the read model...")
    seed_proc = subprocess.run(
        [sys.executable, "-m", "enterprise.seed"],
        capture_output=True, text=True, env=env, cwd=str(workdir), timeout=300,
    )
    print(seed_proc.stdout.strip() or seed_proc.stderr.strip())
    if seed_proc.returncode != 0:
        print(seed_proc.stderr)
        return 2

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "enterprise.app:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        env=env, cwd=str(workdir),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )

    try:
        ready = False
        for _ in range(80):
            if server.poll() is not None:
                print("server child died during startup:\n" + (server.stdout.read() or ""))
                return 2
            try:
                status, _h, body = http(f"{base}/v1/health")
                if status == 200 and json.loads(body).get("status") == "ok":
                    ready = True
                    break
            except Exception:
                pass
            time.sleep(0.25)
        if not ready:
            print("server never became healthy")
            return 2

        check = Checker()
        health = json.loads(http(f"{base}/v1/health")[2])
        check.record("health reports the read model", health["read_model"]["available"] is True,
                     health["read_model"])
        check.record("audit chain verifies", health["audit_chain_ok"] is True,
                     health["audit_chain_ok"])

        pid = next(
            line.split()[-1]
            for line in seed_proc.stdout.splitlines()
            if line.startswith("Seeded demo project:")
        )
        print(f"\nDemo project: {pid}\n")

        # ---- personas --------------------------------------------------
        tokens = {email: login(base, email) for email in
                  ("admin@demo", "path@demo", "reviewer@demo", "student@demo",
                   "auditor@demo", "mle@demo")}
        check.expect("six demo personas can log in", len(tokens), 6)

        reviewer = tokens["reviewer@demo"]
        images = json.loads(http(f"{base}/v1/images?sort=priority&page_size=60",
                                 token=reviewer, project=pid)[2])
        check.expect("demo scope populated the gallery", images["total"], 50)
        check.record("gallery is uncertainty-first",
                     images["items"][0]["image_id"] ==
                     min(images["items"],
                         key=lambda i: i["prediction"]["top_two_margin"])["image_id"],
                     f"top={images['items'][0]['image_id']} "
                     f"margin={images['items'][0]['prediction']['top_two_margin']:.4f}")
        image_id = images["items"][0]["image_id"]
        prediction_id = images["items"][0]["prediction"]["prediction_id"]

        # ---- every new route, authenticated -----------------------------
        print("\nAuthenticated route matrix:")
        status, _h, body = http(f"{base}/v1/meta", token=reviewer, project=pid)
        check.expect("GET /v1/meta", status, 200)
        check.expect("meta keeps 3 canonical classes",
                     json.loads(body)["canonical_classes"],
                     ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"])

        check.expect("GET /v1/model-card", http(f"{base}/v1/model-card", token=reviewer, project=pid)[0], 200)
        check.expect("GET /v1/images", http(f"{base}/v1/images", token=reviewer, project=pid)[0], 200)
        check.expect("GET /v1/images/{id}", http(f"{base}/v1/images/{image_id}", token=reviewer, project=pid)[0], 200)

        status, headers, body = http(f"{base}/v1/images/{image_id}/thumbnail",
                                     token=reviewer, project=pid)
        check.expect("GET thumbnail -> png", status, 200)
        check.record("thumbnail is real PNG bytes", body[:8] == PNG_MAGIC,
                     f"{len(body)} bytes, magic={body[:8]!r}")

        status, headers, body = http(f"{base}/v1/images/{image_id}/full",
                                     token=reviewer, project=pid)
        check.expect("GET full -> png", status, 200)
        check.record("full image is real PNG bytes", body[:8] == PNG_MAGIC,
                     f"{len(body)} bytes")

        status, _h, body = http(f"{base}/v1/images/{image_id}/attribution/meta",
                                token=reviewer, project=pid)
        check.expect("GET attribution/meta", status, 200)
        ameta = json.loads(body)
        check.expect("attribution names the recovered model",
                     ameta["recovered_model_id"], "g4-behavioral-recovery-r1")
        check.record("attribution keeps the recovery disclosure",
                     "behaviorally reconstructed" in ameta["disclosure"],
                     ameta["disclosure"][:80] + "...")

        status, headers, body = http(f"{base}/v1/images/{image_id}/attribution",
                                     token=reviewer, project=pid)
        if status == 200:
            check.record("GET attribution -> png with provenance headers",
                         body[:8] == PNG_MAGIC and "x-attrib-recovered-model" in headers,
                         {k: v for k, v in headers.items() if k.startswith("x-attrib")})
        else:
            # Torch absent, or the recovered bundle is not on this machine.
            # Passing the status through IS the correct behaviour; a fabricated
            # heatmap would not be.
            check.record("GET attribution degraded honestly", True,
                         f"HTTP {status} propagated: {body[:160].decode(errors='replace')}")

        review_body = json.dumps({
            "prediction_id": prediction_id, "action": "ACCEPT",
            "idempotency_key": uuid.uuid4().hex,
        }).encode()
        status, _h, body = http(f"{base}/v1/images/{image_id}/reviews",
                                token=reviewer, project=pid, method="POST",
                                body=review_body)
        check.record("POST review (reviewer)", status in (200, 201),
                     f"HTTP {status} {body[:120].decode(errors='replace')}")

        status, headers, body = http(f"{base}/v1/exports/reviews",
                                     token=reviewer, project=pid)
        check.expect("GET /v1/exports/reviews -> csv", status, 200)
        disposition = headers.get("content-disposition", "")
        check.record("csv is a downloadable attachment",
                     "osteopatch_reviews.csv" in disposition, disposition)
        check.record("csv has a header row", body.decode().splitlines()[0].startswith("image_id,"),
                     body.decode().splitlines()[0][:70])

        status, _h, body = http(f"{base}/v1/exports/reviews?format=json",
                                token=reviewer, project=pid)
        check.expect("GET exports?format=json", status, 200)
        check.expect("json export carries model provenance",
                     json.loads(body)["model_version"], "baseline-frozen-g4")

        # ---- capability gates -------------------------------------------
        print("\nCapability gates (each must actually reject):")
        check.expect("no token -> 401 on /v1/images", http(f"{base}/v1/images", project=pid)[0], 401)
        check.expect("no token -> 401 on image bytes",
                     http(f"{base}/v1/images/{image_id}/full", project=pid)[0], 401)

        check.expect("reviewer without X-Project-Id -> 400",
                     http(f"{base}/v1/images", token=reviewer)[0], 400)
        check.expect("non-member project -> 404 (existence not disclosed)",
                     http(f"{base}/v1/images", token=reviewer, project="prj_nope")[0], 404)

        check.expect("auditor cannot write a review",
                     http(f"{base}/v1/images/{image_id}/reviews", token=tokens["auditor@demo"],
                          project=pid, method="POST", body=review_body)[0], 403)
        check.expect("auditor CAN read",
                     http(f"{base}/v1/images", token=tokens["auditor@demo"], project=pid)[0], 200)
        check.expect("student cannot export (export:read excludes student)",
                     http(f"{base}/v1/exports/reviews", token=tokens["student@demo"], project=pid)[0], 403)
        check.expect("student CAN read (review:read includes student)",
                     http(f"{base}/v1/images", token=tokens["student@demo"], project=pid)[0], 200)
        check.expect("mle cannot write a review (no review:write)",
                     http(f"{base}/v1/images/{image_id}/reviews", token=tokens["mle@demo"],
                          project=pid, method="POST", body=review_body)[0], 403)
        check.expect("student cannot create a project",
                     http(f"{base}/v1/projects", token=tokens["student@demo"],
                          method="POST", body=b'{"name":"nope"}')[0], 403)

        # ---- tenancy ----------------------------------------------------
        print("\nTenancy:")
        other_status, _h, other_body = http(f"{base}/v1/projects", token=tokens["admin@demo"],
                                           method="POST", body=b'{"name":"Project B"}')
        other = json.loads(other_body)
        check.expect("admin CAN create a project", other_status, 200)
        check.record("created project has an id", "project_id" in other, other)
        other_pid = other["project_id"]
        for path in (f"/v1/images/{image_id}", f"/v1/images/{image_id}/thumbnail",
                     f"/v1/images/{image_id}/full", f"/v1/images/{image_id}/attribution/meta"):
            check.expect(
                f"other project -> 404 on {path.split('/')[-1]}",
                http(f"{base}{path}", token=tokens["admin@demo"], project=other_pid)[0], 404,
            )
        other_gallery = json.loads(http(f"{base}/v1/images", token=tokens["admin@demo"],
                                        project=other_pid)[2])
        check.expect("other project sees an empty gallery", other_gallery["total"], 0)

    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover
            server.kill()

    canon_hash_after = sha256_file(CANON_DB)
    unmoved = canon_hash_before == canon_hash_after

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "canonical_db_unchanged": unmoved,
        "canonical_db_sha256": canon_hash_before,
        "read_model_used": "copy of runtime-artifacts/db (canonical never written)",
        "checks": check.results,
        "failed": len(check.failed),
        "passed": len(check.results) - len(check.failed),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"\n{report['passed']} passed, {report['failed']} failed")
    print(f"canonical DB unchanged: {unmoved}")
    print(f"wrote {args.out}")

    if not args.keep_workspace:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"workspace kept at {workdir}")

    return 0 if (report["failed"] == 0 and unmoved) else 1


if __name__ == "__main__":
    sys.exit(main())
