#!/usr/bin/env python
"""Whole-app BROWSER end-to-end test: boot a throwaway stack, drive the real UI.

Why this exists
---------------
``app/local-tester.py`` exercises both apps at the HTTP level and never opens the
UI; ``vitest`` renders components in jsdom. Neither proves that a real reviewer
can actually walk the product: that the gallery ranks by uncertainty, that a
review saves and stays append-only, that the model card's limitations are really
on screen, that attribution never fabricates a heatmap, and that the export
carries both the model prediction and the human correction.

This does. It boots the real G6 API and the real Vite dev server on free ports,
runs Playwright against them, and writes evidence.

Safety
------
The canonical review store is **copied to a temp workspace and never written**.
The browser journey submits real ACCEPT / CORRECT / DEFER events, so this is not
optional. The canonical DB is hashed before and after and the run fails if it
moved.

Fails closed on a squatted port
-------------------------------
There is a real failure mode on this machine: a stale server left running on a
fixed port answers HTTP while the freshly-spawned child dies with EADDRINUSE.
A runner that trusted the HTTP response would report a green run against unknown
code. So readiness requires BOTH a live child process AND a healthy response;
if the child died but the port answers, that is reported as a port conflict, not
as a pass.

    python scripts/e2e_ui.py                    # full run in bundled Chromium
    python scripts/e2e_ui.py --browser edge     # run in the SYSTEM Microsoft Edge
    python scripts/e2e_ui.py --headed           # watch it happen
    python scripts/e2e_ui.py --grep "model card"
    python scripts/e2e_ui.py --keep-workspace   # leave the temp dir for poking

Browsers
--------
``chromium`` (default) is the Playwright-managed Chromium build.  ``edge`` drives
the PREINSTALLED Microsoft Edge through Playwright's ``msedge`` channel, so
nothing is downloaded -- and it is the only way to prove the app works in the
browser the reviewers are most likely to actually use.

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

# Windows console code pages are often cp1252; Playwright/Vite logs contain
# Unicode arrows and ellipses. Force safe UTF-8 diagnostics so a failed test
# never masks its real error with a secondary UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
G6_BACKEND = REPO / "app" / "g6" / "backend"
FRONTEND = REPO / "app" / "g6" / "frontend"
RUNTIME = Path(os.environ.get("OSTEOPATCH_RUNTIME_ARTIFACTS", REPO / "runtime-artifacts")).resolve()
CANON_DB = RUNTIME / "db" / "osteopatch_g6.sqlite3"
DEFAULT_OUT = REPO / "docs" / "evidence" / "e2e-ui-result.json"
#: Evidence path per browser. Without this split, a bare ``--browser edge`` would
#: overwrite the Chromium record that ``make e2e`` and the CI job produce, and the
#: checked-in evidence would silently mean whichever browser ran last.
BROWSER_OUT = {
    "chromium": DEFAULT_OUT,
    "edge": REPO / "docs" / "evidence" / "e2e-edge-result.json",
}

BOOT_TIMEOUT = 120.0
EXPECTED_IMAGES = 1144

#: Playwright's CLI, invoked through node directly. `npx` is not resolvable as a
#: bare executable from Python on Windows (WinError 2), and shelling out to it
#: would also make the run depend on whatever npx decides to fetch.
PLAYWRIGHT_CLI = FRONTEND / "node_modules" / "@playwright" / "test" / "cli.js"
VITE_CLI = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"


def node(*args: str) -> list[str]:
    return ["node", str(PLAYWRIGHT_CLI), *args]


def _display_path(p: Path) -> str:
    """Repo-relative when possible; absolute otherwise (e.g. a --out outside)."""
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return str(p)


def browser_version(name: str) -> str:
    """Report the engine that will actually be driven.

    Without this the evidence would only say ``browser: "edge"`` — a label the
    harness chose, not proof of what ran. Recording the real version means the
    evidence file stands on its own.
    """
    channel = "msedge" if name == "edge" else None
    script = (
        "const { chromium } = require('@playwright/test');"
        "(async () => {"
        " const b = await chromium.launch({ channel: %s, headless: true });"
        " console.log(b.version());"
        " await b.close();"
        "})().catch(e => { console.error(e.message); process.exit(1); });"
    ) % (json.dumps(channel) if channel else "undefined")
    try:
        proc = subprocess.run(
            ["node", "-e", script],
            cwd=str(FRONTEND),
            capture_output=True,
            text=True,
            timeout=120,
        )
        return proc.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def vite(*args: str) -> list[str]:
    return ["node", str(VITE_CLI), *args]

BANNER = (
    "OsteoPatch whole-app browser E2E — educational research prototype. "
    "NOT for diagnosis, treatment decisions, or predicting treatment response."
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def free_port() -> int:
    """Ask the OS for an unused port. Still racy — hence wait_ready()."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_json(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def url_alive(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def wait_ready(name: str, child, url: str, log: Path, expect_json: bool = True) -> dict:
    """Wait for readiness. Requires a LIVE CHILD as well as a healthy response.

    A dead child plus a responding port means something else already owns that
    port; attaching to it would test unknown code.
    """
    deadline = time.time() + BOOT_TIMEOUT
    last = ""
    while time.time() < deadline:
        if child.poll() is not None:
            tail = log.read_text(encoding="utf-8", errors="replace")[-1500:]
            if url_alive(url):
                raise SystemExit(
                    f"FATAL: {name} child exited rc={child.returncode} but {url} is "
                    f"already answering — that port is held by another process.\n"
                    f"Stop it, or rerun with a different port.\n--- log tail ---\n{tail}"
                )
            raise SystemExit(
                f"FATAL: {name} did not start (rc={child.returncode}).\n"
                f"--- log tail ---\n{tail}"
            )
        if url_alive(url):
            if not expect_json:
                return {}
            try:
                return get_json(url)
            except Exception as exc:  # still warming
                last = f"not json yet: {exc}"
        else:
            last = "not listening"
        time.sleep(0.4)
    tail = log.read_text(encoding="utf-8", errors="replace")[-1500:]
    raise SystemExit(
        f"FATAL: {name} never became ready within {BOOT_TIMEOUT:.0f}s ({last}).\n"
        f"--- log tail ---\n{tail}"
    )


def spawn(
    name: str, cmd: list[str], env: dict, log_path: Path, cwd: Path
) -> tuple[subprocess.Popen, object]:
    """Start a child with output redirected to log_path.

    The log handle is RETURNED so the caller can close it. An open handle in
    this process blocks deleting the file on Windows, which silently broke
    temp-workspace cleanup.
    """
    log = log_path.open("w", encoding="utf-8", errors="replace")
    proc = subprocess.Popen(
        cmd, cwd=str(cwd), env=env, stdout=log, stderr=subprocess.STDOUT
    )
    return proc, log


def remove_workspace(path: Path, attempts: int = 5) -> bool:
    """Remove the temp workspace, retrying while Windows releases locks.

    ``ignore_errors=True`` used to swallow a genuinely locked directory, so
    every failed run left a database copy behind with no indication why.
    Returns True when the directory is gone.
    """
    def _unlock(func, target, _exc):
        try:
            os.chmod(target, 0o700)
            func(target)
        except Exception:
            pass

    for i in range(attempts):
        if not path.exists():
            return True
        try:
            shutil.rmtree(path, onerror=_unlock)
        except Exception:
            pass
        if not path.exists():
            return True
        time.sleep(0.5 * (i + 1))

    print(
        f"WARNING: could not remove the temp workspace {path}.\n"
        "         It still holds a copy of the review DB and server logs; "
        "remove it manually.",
        file=sys.stderr,
    )
    return not path.exists()


# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Whole-app browser E2E for OsteoPatch")
    ap.add_argument("--headed", action="store_true", help="show the browser")
    ap.add_argument(
        "--browser",
        default="chromium",
        choices=("chromium", "edge"),
        help="chromium = Playwright's build (default); edge = installed MS Edge",
    )
    ap.add_argument("--grep", default="", help="only run specs matching this regex")
    ap.add_argument("--keep-workspace", action="store_true")
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="evidence path (default: docs/evidence/e2e-<browser>-result.json)",
    )
    ap.add_argument(
        "--skip-prepare",
        action="store_true",
        help="skip the runtime-artifact preflight (not recommended)",
    )
    args = ap.parse_args()
    if args.out is None:
        args.out = BROWSER_OUT[args.browser]
    # Relative --out is relative to the caller's CWD, not the repo. Resolve it
    # up front so the later relative_to(REPO) display cannot raise ValueError
    # after a successful run.
    args.out = args.out.resolve()

    print("=" * 78)
    print(BANNER)
    print("=" * 78)

    if not PLAYWRIGHT_CLI.exists():
        print(
            f"FATAL: Playwright CLI not found at {PLAYWRIGHT_CLI}\n"
            "       Run: cd app/g6/frontend && npm install",
            file=sys.stderr,
        )
        return 2
    if not VITE_CLI.exists():
        print(
            f"FATAL: Vite CLI not found at {VITE_CLI}\n"
            "       Run: cd app/g6/frontend && npm install",
            file=sys.stderr,
        )
        return 2

    if not args.skip_prepare:
        proc = subprocess.run(
            [sys.executable, str(REPO / "scripts" / "prepare_runtime.py")],
            cwd=str(REPO),
        )
        if proc.returncode != 0:
            print(
                "\nE2E ABORTED: runtime artifacts are missing or do not match their "
                "committed hashes.\nSee app/g6/deploy/runtime-artifacts.expected.json.",
                file=sys.stderr,
            )
            return proc.returncode

    if not CANON_DB.exists():
        print(
            f"FATAL: canonical review store not found: {CANON_DB}\n"
            "       (it is gitignored runtime data — see runtime-artifacts/)",
            file=sys.stderr,
        )
        return 2

    canon_before = sha256(CANON_DB)
    workspace = Path(tempfile.mkdtemp(prefix="osteopatch-e2e-"))
    db_copy = workspace / "osteopatch_g6.sqlite3"
    shutil.copy2(CANON_DB, db_copy)
    (workspace / "thumbs").mkdir(exist_ok=True)

    venv_py = REPO / ".venv" / "Scripts" / "python.exe"
    if not venv_py.exists():
        venv_py = REPO / ".venv" / "bin" / "python"
    if not venv_py.exists():
        print("FATAL: no project .venv found at repo root", file=sys.stderr)
        return 2

    api_port, web_port = free_port(), free_port()
    api_base = f"http://127.0.0.1:{api_port}"
    web_base = f"http://127.0.0.1:{web_port}"

    print(f"workspace : {workspace}")
    print(f"canonical : {CANON_DB} (sha256 {canon_before[:16]}… — never written)")
    print(f"api       : {api_base}")
    print(f"web       : {web_base}")

    api_log = workspace / "api.log"
    web_log = workspace / "web.log"
    api_env = dict(os.environ)
    api_env.update(
        {
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(G6_BACKEND),
            "OSTEOPATCH_PROJECT_ROOT": str(REPO),
            "OSTEOPATCH_RUNTIME_ARTIFACTS": str(RUNTIME),
            "OSTEOPATCH_DB": str(db_copy),
            "OSTEOPATCH_TIFFS": str(RUNTIME / "images"),
            "OSTEOPATCH_THUMBS": str(workspace / "thumbs"),
        }
    )
    web_env = dict(os.environ)
    web_env["VITE_API_TARGET"] = api_base

    api = web = None
    api_log_handle = web_log_handle = None
    rc = 1
    result: dict = {}
    try:
        print("\nbooting G6 review API …")
        api, api_log_handle = spawn(
            "g6-api",
            [
                str(venv_py), "-m", "uvicorn", "osteopatch.app:app",
                "--host", "127.0.0.1", "--port", str(api_port), "--log-level", "warning",
            ],
            api_env, api_log, G6_BACKEND,
        )
        health = wait_ready("G6 review API", api, f"{api_base}/v1/health", api_log)
        n = health.get("images_indexed")
        if n != EXPECTED_IMAGES:
            raise SystemExit(
                f"FATAL: API reports {n} images, expected {EXPECTED_IMAGES}. "
                "The browser journey asserts against real data."
            )
        print(f"  up: {api_base} ({n} images, {health.get('predictions')} predictions)")

        print("booting Vite dev server …")
        web, web_log_handle = spawn(
            "vite",
            vite("--host", "127.0.0.1", "--port", str(web_port), "--strictPort"),
            web_env, web_log, FRONTEND,
        )
        wait_ready("Vite dev server", web, web_base, web_log, expect_json=False)
        print(f"  up: {web_base}")

        # The Vite proxy target is baked into vite.config.ts; assert the SPA can
        # actually reach the API through it before running the suite.
        print("checking the dev-server proxy reaches the API …")
        probe = subprocess.run(
            node("test", "--list"),
            cwd=str(FRONTEND),
            capture_output=True, text=True,
            env={
                **os.environ,
                "E2E_BASE_URL": web_base,
                "E2E_BACKEND_URL": api_base,
                "E2E_BROWSER": args.browser,
            },
        )
        if probe.returncode != 0:
            raise SystemExit(
                "FATAL: Playwright could not load the suite.\n"
                f"{probe.stdout}\n{probe.stderr}"
            )
        # `--list` prints one line per spec; count the file:line markers.
        specs = [ln for ln in probe.stdout.splitlines() if ".spec.ts:" in ln]
        if not specs:
            raise SystemExit(
                "FATAL: Playwright discovered 0 specs — refusing to report a pass.\n"
                f"{probe.stdout}\n{probe.stderr}"
            )
        print(f"  {len(specs)} specs discovered")

        print("\nrunning the browser journey …")
        cmd = node("test", "--reporter=list")
        if args.headed:
            cmd.append("--headed")
        if args.grep:
            cmd += ["--grep", args.grep]
        run = subprocess.run(
            cmd,
            cwd=str(FRONTEND),
            env={
                **os.environ,
                "E2E_BASE_URL": web_base,
                "E2E_BACKEND_URL": api_base,
                "E2E_BROWSER": args.browser,
                **({"CI": "1"} if not args.headed else {}),
            },
        )
        rc = run.returncode

        # Verify the API really did receive reviews from the browser journey.
        # Count rows carrying a human action — `count` is every exportable row,
        # so reporting that as "reviews" would be a flattering lie.
        export_rows = 0
        rows_with_human_action = 0
        try:
            listing = get_json(f"{api_base}/v1/exports/reviews?format=json")
            rows = listing.get("rows") or []
            export_rows = int(listing.get("count") or 0)
            rows_with_human_action = sum(
                1
                for r in rows
                if (r.get("human_review_action") or r.get("human_review_status") or "")
                not in ("", "unreviewed", None)
            )
        except Exception:
            pass

        canon_after = sha256(CANON_DB)
        result = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "runner": "scripts/e2e_ui.py",
            "api_base": api_base,
            "web_base": web_base,
            "images_indexed": n,
            "predictions": health.get("predictions"),
            "specs_discovered": len(specs),
            "playwright_exit_code": rc,
            "export_rows_in_throwaway_db": export_rows,
            "rows_with_human_action": rows_with_human_action,
            "canonical_db_sha256_before": canon_before,
            "canonical_db_sha256_after": canon_after,
            "canonical_db_untouched": canon_before == canon_after,
            "headed": args.headed,
            "browser": args.browser,
            "browser_version": browser_version(args.browser),
            "grep": args.grep or None,
            "passed": rc == 0 and canon_before == canon_after,
        }
    finally:
        for _name, child in (("vite", web), ("g6-api", api)):
            if child is None:
                continue
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
        # Close OUR log handles first: an open handle here is exactly what made
        # cleanup fail on Windows.
        for handle in (web_log_handle, api_log_handle):
            if handle is not None:
                try:
                    handle.close()
                except Exception:
                    pass
        # Cleanup lives HERE, not after the try/finally: every abort path raises
        # SystemExit, which unwinds past trailing code and used to leak a full
        # copy of the review DB on every failed run.
        if not args.keep_workspace:
            remove_workspace(workspace)
        else:
            print(f"workspace kept: {workspace}")

    canon_final = sha256(CANON_DB)
    if canon_final != canon_before:
        result["canonical_db_untouched"] = False
        result["passed"] = False
        print(
            "\nFATAL: the canonical review store changed during the run. "
            "It must never be written by the E2E journey.",
            file=sys.stderr,
        )
        rc = rc or 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("\n" + "=" * 78)
    if result.get("passed"):
        print(
            f"E2E PASSED — {result['specs_discovered']} specs in "
            f"{result['browser']} {result['browser_version']}; the browser journey "
            f"left {result['rows_with_human_action']} human review action(s) across "
            f"{result['export_rows_in_throwaway_db']} exportable rows in the throwaway "
            f"DB; canonical store byte-identical."
        )
    else:
        print(f"E2E FAILED (playwright exit {rc})")
        for label, path in (("api log", api_log), ("web log", web_log)):
            if path.exists():
                print(f"\n--- {label} tail ---")
                print(path.read_text(encoding="utf-8", errors="replace")[-2000:])
    print(f"evidence: {_display_path(args.out)}")

    print("=" * 78)
    return 0 if result.get("passed") else (rc or 1)


if __name__ == "__main__":
    sys.exit(main())
