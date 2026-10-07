#!/usr/bin/env python
"""Build and run the unified local demo against disposable copied data.

Each launch snapshots the read model, scopes only that copy, verifies the
selected images and recorded-run artifacts, then serves the built UI on one
local origin. Ctrl+C stops the app and removes the disposable workspace; run
the same command again for a clean reset.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
G6_BACKEND = REPO / "app" / "g6" / "backend"
G7_BACKEND = REPO / "app" / "g7-enterprise" / "backend"
FRONTEND = REPO / "app" / "g7-enterprise" / "frontend"
RECOVERED_SHA256 = "ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73"
ENCODER_SHA256 = "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_only_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def snapshot_db(source: Path, target: Path) -> tuple[str, dict]:
    sys.path.insert(0, str(G6_BACKEND))
    from osteopatch.integrity import corpus_row_digest

    before = sha256_file(source)
    with closing(read_only_db(source)) as src, closing(sqlite3.connect(target)) as dst:
        digest = corpus_row_digest(src)
        src.backup(dst)
        dst.row_factory = sqlite3.Row
        if corpus_row_digest(dst) != digest:
            raise RuntimeError("copied review database failed the frozen-row digest check")
    if sha256_file(source) != before:
        raise RuntimeError("source review database changed during the read-only snapshot")
    return before, digest


def safe_name(value: object) -> str | None:
    if not isinstance(value, str) or not value or value in {".", ".."}:
        return None
    if Path(value).name != value or "/" in value or "\\" in value:
        return None
    return value


def run_artifact_error(root: Path, run: sqlite3.Row, tiles: list[sqlite3.Row]) -> str | None:
    run_id = safe_name(run["run_id"])
    if not run_id:
        return "run identifier is invalid"
    directory = root / "live-runs" / run_id
    source = directory / "source.bin"
    try:
        if source.is_symlink() or not source.is_file():
            return "stored source image is missing"
        if sha256_file(source) != run["source_sha256"]:
            return "stored source image does not match its recorded SHA-256"
    except OSError:
        return "stored source image is unavailable"
    for tile in tiles:
        filename = tile["tile_png_filename"]
        if filename is None:
            continue
        name = safe_name(filename)
        if not name:
            return "stored tile filename is invalid"
        path = directory / name
        try:
            if path.is_symlink() or not path.is_file():
                return "stored tile image is missing"
            with path.open("rb") as handle:
                if handle.read(8) != PNG_MAGIC:
                    return "stored tile image is invalid"
        except OSError:
            return "stored tile image is unavailable"
    return None


def copy_verified(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f"required source image is missing: {source.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    expected = sha256_file(source)
    shutil.copyfile(source, target)
    if sha256_file(target) != expected:
        raise RuntimeError(f"copied file failed SHA-256 verification: {source.name}")


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def request(url: str, *, token: str | None = None, project: str | None = None,
            body: bytes | None = None) -> tuple[int, dict, bytes]:
    req = urllib.request.Request(url, data=body, method="POST" if body is not None else "GET")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if project:
        req.add_header("X-Project-Id", project)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def seed_workspace(source_db: Path, workspace: Path, source_runtime: Path) -> tuple[str, list[str], int]:
    os.environ.update({
        "OSTEOPATCH_RUNTIME_ARTIFACTS": str(workspace),
        "OSTEOPATCH_DB": str(workspace / "db" / "osteopatch_g6.sqlite3"),
        "OSTEOPATCH_THUMBS": str(workspace / "thumbnails"),
        "OSTEOPATCH_TIFFS": str(workspace / "images"),
        "OSTEOPATCH_ATTRIB_IMAGES": str(workspace / "images"),
        "OSTEOPATCH_LIVE_RUNS": str(workspace / "live-runs"),
        "OSTEOPATCH_TORCH_HOME": str(workspace / "models" / "torch-hub"),
        "OSTEOPATCH_RECOVERED_MODEL": str(workspace / "models" / "g4-behavioral-recovery-r1.pt"),
        "OSTEOPATCH_ENT_DB": str(workspace / "enterprise.sqlite3"),
        "OSTEOPATCH_AUDIT_LOG": str(workspace / "audit_chain.jsonl"),
        "OSTEOPATCH_PROJECT_SCOPES": str(workspace / "project-scopes"),
        "OSTEOPATCH_SCRATCH": str(workspace / "scratch"),
    })
    sys.path[:0] = [str(G6_BACKEND), str(G7_BACKEND)]
    from enterprise import seed, store

    with closing(read_only_db(source_db)) as conn:
        latest = conn.execute(
            "SELECT project_id FROM live_run ORDER BY created_at DESC, run_id DESC LIMIT 1"
        ).fetchone()
        project_id = str(latest["project_id"]) if latest else None
        runs = conn.execute(
            "SELECT * FROM live_run WHERE project_id=? ORDER BY created_at DESC, run_id DESC",
            (project_id,),
        ).fetchall() if project_id else []
        tiles = {
            row["run_id"]: conn.execute(
                "SELECT tile_png_filename FROM live_tile WHERE run_id=? ORDER BY tile_index",
                (row["run_id"],),
            ).fetchall()
            for row in runs
        }

    ent = store.connect()
    if project_id:
        admin = store.upsert_user(ent, "admin@demo")
        ent.execute(
            "INSERT INTO project(project_id,name,created_by,created_at) VALUES (?,?,?,?)",
            (project_id, seed.DEMO_PROJECT_NAME, admin["user_id"], store.utc_now()),
        )
        ent.commit()
    seeded = seed.seed(ent, scope_size=seed.DEMO_SCOPE_SIZE)
    ent.close()
    from osteopatch import app as g6_app
    # The launcher must not pin its temporary DB open on Windows after stop.
    g6_app.close_current_connection()
    if seeded["scope"].get("status") != "granted" or seeded["scope"].get("granted") != seed.DEMO_SCOPE_SIZE:
        raise RuntimeError(f"demo image scope was not prepared: {seeded['scope']}")
    project_id = seeded["project_id"]

    g6 = read_only_db(Path(os.environ["OSTEOPATCH_DB"]))
    images = g6.execute(
        "SELECT image_id,tiff_filename FROM source_qc WHERE project_id=? ORDER BY image_id",
        (project_id,),
    ).fetchall()
    g6.close()
    if len(images) != seed.DEMO_SCOPE_SIZE:
        raise RuntimeError(f"expected {seed.DEMO_SCOPE_SIZE} copied demo patches, found {len(images)}")

    from PIL import Image

    for row in images:
        image_id = safe_name(row["image_id"])
        tiff_name = safe_name(row["tiff_filename"])
        if not image_id or not tiff_name:
            raise RuntimeError("review database contains an invalid required image filename")
        tiff = source_runtime / "images" / tiff_name
        thumb = source_runtime / "thumbnails" / f"{image_id}.png"
        target_tiff = workspace / "images" / tiff_name
        target_thumb = workspace / "thumbnails" / f"{image_id}.png"
        copy_verified(tiff, target_tiff)
        copy_verified(thumb, target_thumb)
        try:
            with Image.open(target_tiff) as img:
                img.verify()
            with Image.open(target_thumb) as img:
                if img.format != "PNG":
                    raise RuntimeError(f"thumbnail is not PNG: {image_id}")
                img.verify()
        except Exception as exc:
            raise RuntimeError(f"required patch pixels failed decode validation: {image_id}: {exc}") from exc

    verified_runs: list[str] = []
    for run in runs:
        error = run_artifact_error(source_runtime, run, tiles[run["run_id"]])
        if error:
            print(f"Recorded run {run['run_id']} unavailable: {error}")
            continue
        dest = workspace / "live-runs" / run["run_id"]
        dest.mkdir(parents=True, exist_ok=True)
        copy_verified(source_runtime / "live-runs" / run["run_id"] / "source.bin", dest / "source.bin")
        for tile in tiles[run["run_id"]]:
            if tile["tile_png_filename"]:
                name = safe_name(tile["tile_png_filename"])
                if name:
                    copy_verified(source_runtime / "live-runs" / run["run_id"] / name, dest / name)
        copied_run = read_only_db(Path(os.environ["OSTEOPATCH_DB"]))
        copied = copied_run.execute("SELECT * FROM live_run WHERE run_id=?", (run["run_id"],)).fetchone()
        copied_tiles = copied_run.execute(
            "SELECT tile_png_filename FROM live_tile WHERE run_id=? ORDER BY tile_index",
            (run["run_id"],),
        ).fetchall()
        copied_run.close()
        if copied is None or copied["source_sha256"] != run["source_sha256"]:
            raise RuntimeError(f"recorded run database record changed during snapshot: {run['run_id']}")
        error = run_artifact_error(workspace, copied, copied_tiles)
        if error:
            print(f"Recorded run {run['run_id']} unavailable after copy: {error}")
        else:
            verified_runs.append(run["run_id"])

    model = source_runtime / "models" / "g4-behavioral-recovery-r1.pt"
    if model.is_file() and not model.is_symlink() and sha256_file(model) == RECOVERED_SHA256:
        copy_verified(model, workspace / "models" / model.name)
    else:
        print("Recovered model bundle is unavailable or failed its pinned SHA-256; live inference will remain unavailable.")
    checkpoint = source_runtime / "models" / "torch-hub" / "hub" / "checkpoints" / "mobilenet_v3_small-047dcff4.pth"
    if checkpoint.is_file() and not checkpoint.is_symlink() and sha256_file(checkpoint) == ENCODER_SHA256:
        copy_verified(checkpoint, workspace / "models" / "torch-hub" / "hub" / "checkpoints" / checkpoint.name)
    return project_id, verified_runs, len(images)


def preflight(base: str, project_id: str, image_count: int, replay_ids: list[str]) -> None:
    status, _headers, body = request(f"{base}/v1/health")
    if status != 200:
        raise RuntimeError(f"local API health check failed ({status})")
    login_status, _headers, body = request(
        f"{base}/auth/login", body=json.dumps({"email": "reviewer@demo"}).encode(),
    )
    if login_status != 200:
        raise RuntimeError(f"demo login check failed ({login_status}): {body[:200]!r}")
    token = json.loads(body)["access_token"]
    status, _headers, body = request(
        f"{base}/v1/images?page=1&page_size=1", token=token, project=project_id,
    )
    gallery = json.loads(body)
    if status != 200 or gallery.get("total") != image_count or not gallery.get("items"):
        raise RuntimeError(f"authenticated gallery preflight failed ({status}); expected {image_count} patches")
    status, _headers, page_body = request(
        f"{base}/v1/images?sort=priority&filter=all&page=1&page_size=24",
        token=token, project=project_id,
    )
    page = json.loads(page_body)
    if status != 200 or len(page.get("items", [])) != min(24, image_count):
        raise RuntimeError(f"gallery paging preflight failed ({status}); expected a 24-patch page")
    image_id = gallery["items"][0]["image_id"]
    for kind in ("thumbnail", "full"):
        status, headers, payload = request(
            f"{base}/v1/images/{image_id}/{kind}", token=token, project=project_id,
        )
        if status != 200 or not payload:
            raise RuntimeError(f"authenticated {kind} preflight failed ({status}) for {image_id}")
        if kind == "thumbnail" and not payload.startswith(PNG_MAGIC):
            raise RuntimeError("gallery thumbnail preflight returned invalid PNG bytes")
    for run_id in replay_ids:
        status, _headers, body = request(
            f"{base}/v1/live/runs/{run_id}", token=token, project=project_id,
        )
        if status != 200:
            raise RuntimeError(f"verified recorded run failed API preflight ({status}): {body[:200]!r}")


def main() -> int:
    default_runtime = Path(os.environ.get("OSTEOPATCH_RUNTIME_ARTIFACTS", REPO / "runtime-artifacts"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-artifacts", type=Path, default=default_runtime,
                        help="read-only source runtime directory (defaults to OSTEOPATCH_RUNTIME_ARTIFACTS or ./runtime-artifacts)")
    parser.add_argument("--port", type=int, default=0, help="reuse a local URL across resets (0 chooses a free port)")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("--port must be between 0 and 65535")
    source_runtime = args.runtime_artifacts.resolve()
    source_db = source_runtime / "db" / "osteopatch_g6.sqlite3"
    if not source_db.is_file():
        print(f"Runtime review database missing: {source_db}\nRestore the verified runtime bundle or set OSTEOPATCH_RUNTIME_ARTIFACTS.", file=sys.stderr)
        return 2

    npm = "npm.cmd" if os.name == "nt" else "npm"
    build = subprocess.run([npm, "run", "build"], cwd=FRONTEND)
    if build.returncode:
        return build.returncode

    server: subprocess.Popen[str] | None = None
    source_hash = ""
    try:
        with tempfile.TemporaryDirectory(prefix="osteopatch-demo-") as temp:
            workspace = Path(temp)
            (workspace / "db").mkdir()
            source_hash, digest = snapshot_db(source_db, workspace / "db" / source_db.name)
            project_id, replay_ids, image_count = seed_workspace(source_db, workspace, source_runtime)
            print(f"Copied review database SHA-256: {source_hash}", flush=True)
            print(f"Verified corpus row digest: {digest['digest']} ({digest['tables']})", flush=True)
            print(f"Prepared {image_count} patch pairs; verified recorded runs: {len(replay_ids)}", flush=True)

            port = args.port or free_port()
            base = f"http://127.0.0.1:{port}"
            env = {
                **os.environ,
                "PYTHONPATH": os.pathsep.join([str(G6_BACKEND), str(G7_BACKEND)]),
                "OSTEOPATCH_ENT_PORT": str(port),
            }
            server = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "enterprise.app:app",
                 "--host", "127.0.0.1", "--port", str(port), "--log-level", "info", "--no-access-log"],
                cwd=REPO, env=env,
            )
            for _ in range(60):
                if server.poll() is not None:
                    raise RuntimeError("local API stopped during startup:\n" + (server.stdout.read() if server.stdout else ""))
                try:
                    with urllib.request.urlopen(f"{base}/v1/health", timeout=2):
                        break
                except Exception:
                    time.sleep(1)
            else:
                raise RuntimeError("local API did not become healthy within 60 seconds")

            preflight(base, project_id, image_count, replay_ids)
            if sha256_file(source_db) != source_hash:
                raise RuntimeError("source review database changed while the disposable demo was starting")
            print(f"\nOsteoPatch local educational demo: {base}", flush=True)
            print(f"Project: {project_id}; reviewer@demo (six local demo roles are seeded)", flush=True)
            print("All review writes and uploads go to a temporary copy. Press Ctrl+C to stop; rerun this command to reset.", flush=True)
            server.wait()
            return server.returncode or 0
    except KeyboardInterrupt:
        print("\nStopping the disposable demo.")
        return 0
    except Exception as exc:
        print(f"Demo startup failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
        if source_hash and sha256_file(source_db) != source_hash:
            print("Source review database changed while the demo was running; the app itself writes only to its temporary copy.", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
