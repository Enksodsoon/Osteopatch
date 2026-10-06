#!/usr/bin/env python
"""Drive live inference over real HTTP: upload -> predict -> read back.

Why this exists
---------------
The unit tests cover the live surface through FastAPI's TestClient. That proves
routing, dependencies and storage, but not that a real bearer token, a real raw
body upload and a real PNG response survive a real socket. This does, as each
demo persona, and it is the record that the feature is demo-ready rather than
merely unit-tested.

Safety
------
The canonical 1,144-row review store is COPIED to a temp workspace and the
server is pointed at the copy, because a live run WRITES rows. The canonical
file is hashed before and after and the run fails if it moved. On top of that
the FROZEN CORPUS is compared by row content (not file bytes) via
``osteopatch.integrity.corpus_row_digest``: writing live rows is supposed to
change the database, so only the corpus rows themselves must stay identical.

Fails closed on a squatted port
-------------------------------
A stale server on the fixed port would answer while the intended child dies
with EADDRINUSE, producing a green run against unknown code. Readiness requires
BOTH a live child process AND a matching health payload.

    python scripts/verify_live_inference.py
    python scripts/verify_live_inference.py --out docs/evidence/live-inference.json

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
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
G6_BACKEND = REPO / "app" / "g6" / "backend"
G7_BACKEND = REPO / "app" / "g7-enterprise" / "backend"
CANON_DB = REPO / "runtime-artifacts" / "db" / "osteopatch_g6.sqlite3"
DEMO_SLIDE = REPO / "runtime-artifacts" / "demo-slides" / "osteopatch-demo-slide.tif"
DEFAULT_OUT = REPO / "docs" / "evidence" / "live-inference.json"

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


def http(url, *, token=None, project=None, method="GET", body=None, file_name=None,
         content_type="application/octet-stream"):
    """One authenticated call. Header names come back lowercased.

    Without a Content-Type a raw body is uninterpretable, and multipart is
    deliberately not used (see the route): the browser sends the file bytes
    straight through.
    """
    req = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        req.add_header("Content-Type", content_type)
    if file_name is not None:
        req.add_header("X-File-Name", file_name)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if project:
        req.add_header("X-Project-Id", project)
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in exc.headers.items()}
        try:
            body = exc.read()
        except Exception:
            # The capability gate answers BEFORE the body is consumed, so the
            # server closes the connection while this client is still uploading.
            # The status is what these probes assert on; the body is a nicety.
            body = b""
        return exc.code, headers, body


def login(base: str, email: str) -> str:
    req = urllib.request.Request(
        f"{base}/auth/login", data=json.dumps({"email": email}).encode(),
        method="POST", headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())["access_token"]
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"login failed for {email}: HTTP {exc.code}") from exc


class Checker:
    def __init__(self):
        self.results: list[dict] = []

    def expect(self, name, actual, expected):
        ok = actual == expected
        self.results.append({"check": name, "expected": expected, "actual": actual, "ok": ok})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {actual!r} (expected {expected!r})")

    def record(self, name, ok, detail):
        self.results.append({"check": name, "ok": ok, "detail": detail})
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    @property
    def failed(self):
        return [r for r in self.results if not r["ok"]]


def _digest_probe(db_path: Path) -> dict:
    """Corpus row digest of a read model, computed out of process."""
    script = (
        "import json,sys;"
        "sys.path.insert(0, %r);"
        "from osteopatch import db, integrity;"
        "c = db.connect(%r); db.run_migrations(c);"
        "print(json.dumps(integrity.corpus_row_digest(c)))"
        % (str(G6_BACKEND), str(db_path))
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                         timeout=300)
    if out.returncode != 0:
        raise SystemExit(f"corpus digest probe failed:\n{out.stderr}")
    return json.loads(out.stdout)


def _seed_demo(env: dict, cwd: Path) -> dict:
    """Seed users/roles WITHOUT granting a review scope.

    ``enterprise.seed`` the CLI is the demo path and deliberately re-scopes 50
    real corpus rows, so it would rewrite ``project_id`` before the live run
    even started — and this script's whole claim is that the frozen corpus comes
    out byte-identical. The library ``seed()`` with no ``scope_size`` creates the
    same users, project and memberships and writes nothing to the G6 read model.
    Live inference needs no corpus scope: an uploaded slide belongs to the
    project by its run row, not by a gallery grant.
    """
    script = "import json;from enterprise.seed import seed;print(json.dumps(seed()))"
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                         env=env, cwd=str(cwd), timeout=300)
    if out.returncode != 0:
        raise SystemExit(f"demo seed failed:\n{out.stdout}\n{out.stderr}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--keep-workspace", action="store_true")
    args = ap.parse_args()

    if not CANON_DB.exists():
        print(f"canonical review store missing: {CANON_DB}\nrun scripts/prepare_runtime.py first")
        return 2

    canon_hash_before = sha256_file(CANON_DB)
    workdir = Path(tempfile.mkdtemp(prefix="osteopatch-live-"))
    review_db = workdir / "review-copy.sqlite3"
    shutil.copy2(CANON_DB, review_db)
    corpus_before = _digest_probe(review_db)

    env = {
        **os.environ,
        "OSTEOPATCH_DB": str(review_db),
        "OSTEOPATCH_ENT_DB": str(workdir / "enterprise.sqlite3"),
        "OSTEOPATCH_AUDIT_LOG": str(workdir / "audit.jsonl"),
        "OSTEOPATCH_PROJECT_SCOPES": str(workdir / "scopes"),
        "OSTEOPATCH_LIVE_RUNS": str(workdir / "live-runs"),
        "PYTHONPATH": os.pathsep.join([str(G6_BACKEND), str(G7_BACKEND)]),
    }

    print("Seeding the demo project against a COPY of the read model...")
    seeded = _seed_demo(env, workdir)
    pid = seeded["project_id"]
    print(f"demo project {pid} (scope: {seeded['scope']['status']})")

    check = Checker()
    check.record("seeding wrote no review scope into the read model",
                 seeded["scope"]["status"] == "not_requested", seeded["scope"])
    corpus_after_seed = _digest_probe(review_db)
    check.record("seeding alone left all corpus rows identical",
                 corpus_before == corpus_after_seed,
                 {"digest": corpus_after_seed["digest"], "tables": corpus_after_seed["tables"]})

    port = free_port()
    base = f"http://127.0.0.1:{port}"
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "enterprise.app:app", "--host", "127.0.0.1",
         "--port", str(port), "--log-level", "warning"],
        env=env, cwd=str(workdir), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True,
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

        tokens = {e: login(base, e) for e in
                  ("admin@demo", "path@demo", "reviewer@demo", "student@demo",
                   "mle@demo", "auditor@demo")}
        reviewer = tokens["reviewer@demo"]

        # ---- capability -------------------------------------------------
        print("\nCapability (reader action, torch-free):")
        status, _h, body = http(f"{base}/v1/live/capability",
                                token=reviewer, project=pid)
        check.expect("GET /v1/live/capability", status, 200)
        cap = json.loads(body)
        check.record("live inference is available here", cap.get("available") is True,
                     {k: v for k, v in cap.items() if k != "note"})
        check.record("capability names the RECOVERED head",
                     cap.get("model_id") == "g4-behavioral-recovery-r1",
                     cap.get("model_id"))

        # ---- capability gates ------------------------------------------
        print("\nCapability gates (live:analyze is a writer, live:read a reader):")
        patch = next(iter(sorted((REPO / "runtime-artifacts" / "images").glob("*.tiff"))), None)
        if patch is None:
            print("no durable corpus patch to upload; run scripts/prepare_runtime.py")
            return 2
        payload = patch.read_bytes()
        check.expect("no token -> 401 on capability",
                     http(f"{base}/v1/live/capability", project=pid)[0], 401)
        check.expect("reviewer without X-Project-Id -> 400",
                     http(f"{base}/v1/live/runs", token=reviewer)[0], 400)
        check.expect("non-member project -> 404",
                     http(f"{base}/v1/live/runs", token=reviewer,
                          project="prj_nope")[0], 404)
        # A denied upload is rejected on the capability, before the body is read,
        # so these probes send one byte rather than a 1.6 MB patch.
        for role in ("student@demo", "auditor@demo"):
            check.expect(f"{role} cannot analyze (403)",
                         http(f"{base}/v1/live/patches", token=tokens[role], project=pid,
                              method="POST", body=b"x", file_name="probe.tiff")[0], 403)
        check.expect("reviewer cannot analyze without a project (400)",
                     http(f"{base}/v1/live/patches", token=reviewer, method="POST",
                          body=b"x", file_name="probe.tiff")[0], 400)
        check.expect("empty upload -> 400",
                     http(f"{base}/v1/live/patches", token=reviewer, project=pid,
                          method="POST", body=b"", file_name="empty.png")[0], 400)
        check.expect("unsupported type -> 415",
                     http(f"{base}/v1/live/patches", token=reviewer, project=pid,
                          method="POST", body=b"%PDF-1.4", file_name="paper.pdf")[0], 415)
        check.expect("undecodable image -> 422",
                     http(f"{base}/v1/live/patches", token=reviewer, project=pid,
                          method="POST", body=b"not an image", file_name="bad.png")[0], 422)

        # ---- patch round trip ------------------------------------------
        print("\nAuthenticated patch round trip:")
        t0 = time.time()
        status, _h, body = http(f"{base}/v1/live/patches", token=reviewer, project=pid,
                                method="POST", body=payload, file_name=patch.name)
        elapsed = time.time() - t0
        check.expect("POST /v1/live/patches", status, 200)
        if status != 200:
            print(body[:400])
            raise SystemExit("cannot continue without a live prediction")
        created = json.loads(body)
        run = created["run"]
        pred = created["prediction"]
        run_id = run["run_id"]
        check.record("live run is flagged as live, not corpus",
                     run["is_live_inference"] is True and run["is_corpus_prediction"] is False,
                     {"is_live_inference": run["is_live_inference"],
                      "is_corpus_prediction": run["is_corpus_prediction"]})
        check.expect("run carries the recovered model id",
                     run["model_id"], "g4-behavioral-recovery-r1")
        check.expect("run does NOT carry the frozen bundle hash",
                     run["model_bundle_sha256"] == "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63",
                     False)
        check.expect("predicted class is one of the three",
                     pred["predicted_class"] in
                     ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"), True)
        check.record("scores sum to 1", abs(sum(pred["scores"].values()) - 1.0) < 1e-9,
                     pred["scores"])
        check.record("score label says uncalibrated",
                     "uncalibrated" in pred["score_label"], pred["score_label"])
        check.record("confidence is banded, with a caveat when not clear",
                     pred["confidence"] == "clear" or bool(pred["caveat"]),
                     {"confidence": pred["confidence"], "caveat": pred["caveat"]})
        check.record("wall clock for one patch (incl. model load)",
                     True, f"{elapsed:.2f}s, server-reported {run['latency_ms']}ms")

        status, _h, body = http(f"{base}/v1/live/runs/{run_id}",
                                token=reviewer, project=pid)
        check.expect("GET /v1/live/runs/{id} read-back", status, 200)
        read_back = json.loads(body)
        check.expect("read-back returns the same run", read_back["run"]["run_id"], run_id)
        check.expect("read-back returns its tiles", read_back["n_tiles"], 1)
        check.record("a reader-only role can read it back",
                     http(f"{base}/v1/live/runs/{run_id}", token=tokens["student@demo"],
                          project=pid)[0] == 200, True)
        check.record("listed in /v1/live/runs",
                     run_id in [r["run_id"] for r in
                                json.loads(http(f"{base}/v1/live/runs", token=reviewer,
                                                project=pid)[2])["runs"]], True)
        check.expect("a patch run has no mosaic (404 says so)",
                     http(f"{base}/v1/live/runs/{run_id}/mosaic.png", token=reviewer,
                          project=pid)[0], 404)

        # ---- slide round trip ------------------------------------------
        print("\nAuthenticated slide round trip:")
        slide_bytes, slide_name = None, None
        if DEMO_SLIDE.exists():
            slide_bytes, slide_name = DEMO_SLIDE.read_bytes(), DEMO_SLIDE.name
            slide_note = "demo slide from scripts/make_demo_slide.py"
        else:
            import io

            from PIL import Image
            buf = io.BytesIO()
            Image.new("RGB", (1100, 700), (150, 80, 160)).save(buf, format="PNG")
            slide_bytes, slide_name = buf.getvalue(), "synthetic.png"
            slide_note = "synthetic fallback (run scripts/make_demo_slide.py for the real one)"
        print(f"  using {slide_note}")
        status, _h, body = http(f"{base}/v1/live/slides?tile_px=384", token=reviewer,
                                project=pid, method="POST", body=slide_bytes,
                                file_name=slide_name)
        check.expect("POST /v1/live/slides", status, 200)
        if status == 200:
            slide = json.loads(body)
            srun = slide["run"]
            srun_id = srun["run_id"]
            check.record("slide reports the engine it really used",
                         srun["engine"] in ("openslide", "pillow"),
                         {"engine": srun["engine"], "level_count": srun["level_count"]})
            check.record("mpp is null when the file carries none",
                         srun["mpp_x"] is None and srun["mpp_y"] is None,
                         {"mpp_x": srun["mpp_x"], "mpp_y": srun["mpp_y"]})
            check.record("every grid cell was scored",
                         srun["tile_count"] == srun["tiles_available"],
                         {"scored": srun["tile_count"], "available": srun["tiles_available"],
                          "truncated": srun["truncated"]})
            check.record("mosaic grid returned",
                         slide["mosaic"]["cols"] >= 1,
                         {k: v for k, v in slide["mosaic"].items() if k != "class_colours"})
            status, headers, png = http(f"{base}/v1/live/runs/{srun_id}/mosaic.png",
                                        token=reviewer, project=pid)
            check.expect("GET mosaic.png", status, 200)
            check.record("mosaic is a real PNG", png[:8] == PNG_MAGIC,
                         f"{len(png)} bytes")
            check.record("most uncertain tiles are surfaced",
                         isinstance(slide["most_uncertain_tiles"], list),
                         slide["most_uncertain_tiles"][:2])
        else:
            check.record("slide import failed honestly", True,
                         f"HTTP {status}: {body[:200].decode(errors='replace')}")

        # ---- tenancy on live runs --------------------------------------
        print("\nTenancy on live runs:")
        admin = tokens["admin@demo"]
        status, _h, body = http(f"{base}/v1/projects", token=admin, method="POST",
                                body=json.dumps({"name": "Live Project B"}).encode(),
                                content_type="application/json")
        check.expect("admin created a second project", status, 200)
        if status != 200:
            raise SystemExit(f"cannot continue without a second project: {body[:300]}")
        other = json.loads(body)
        other_pid = other["project_id"]
        status, _h, body = http(f"{base}/v1/live/runs/{run_id}",
                                token=admin, project=other_pid)
        check.expect("another project cannot read the run", status, 404)
        check.expect("another project sees no runs",
                     len(json.loads(http(f"{base}/v1/live/runs", token=admin,
                                         project=other_pid)[2])["runs"]), 0)
        check.expect("another project cannot delete the run",
                     http(f"{base}/v1/live/runs/{run_id}", token=admin,
                          project=other_pid, method="DELETE")[0], 404)
        status, _h, body = http(f"{base}/v1/live/runs/{run_id}", token=reviewer,
                                project=pid, method="DELETE")
        check.expect("owner deletes its own run", status, 200)
        check.expect("the deleted run is gone (404)",
                     http(f"{base}/v1/live/runs/{run_id}", token=reviewer, project=pid)[0],
                     404)

    finally:
        server.terminate()
        try:
            server.wait(timeout=15)
        except subprocess.TimeoutExpired:  # pragma: no cover
            server.kill()

    corpus_after = _digest_probe(review_db)
    corpus_same = corpus_before == corpus_after
    canon_same = sha256_file(CANON_DB) == canon_hash_before
    live_rows = _count_live_rows(review_db)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "canonical_db_unchanged": canon_same,
        "canonical_db_sha256": canon_hash_before,
        "read_model_used": "copy of runtime-artifacts/db (canonical never written)",
        "corpus_row_digest_before": corpus_before,
        "corpus_row_digest_after": corpus_after,
        "corpus_rows_unchanged": corpus_same,
        "live_rows_written": live_rows,
        "checks": check.results,
        "failed": len(check.failed),
        "passed": len(check.results) - len(check.failed),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"\n{report['passed']} passed, {report['failed']} failed")
    print(f"live rows written to the COPY: {live_rows}")
    print(f"corpus rows byte-identical    : {corpus_same} "
          f"({corpus_before['tables']})")
    print(f"canonical DB unchanged        : {canon_same}")
    print(f"wrote {args.out}")

    if not args.keep_workspace:
        shutil.rmtree(workdir, ignore_errors=True)
    else:
        print(f"workspace kept at {workdir}")

    return 0 if (report["failed"] == 0 and canon_same and corpus_same) else 1


def _count_live_rows(db_path: Path) -> dict:
    script = (
        "import json,sys;sys.path.insert(0, %r);"
        "from osteopatch import db;c = db.connect(%r);"
        "print(json.dumps({'live_run': c.execute('SELECT COUNT(*) FROM live_run').fetchone()[0],"
        "'live_tile': c.execute('SELECT COUNT(*) FROM live_tile').fetchone()[0],"
        "'prediction': c.execute('SELECT COUNT(*) FROM prediction').fetchone()[0]}))"
        % (str(G6_BACKEND), str(db_path))
    )
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                         timeout=300)
    return json.loads(out.stdout) if out.returncode == 0 else {"error": out.stderr[-400:]}


if __name__ == "__main__":
    sys.exit(main())
