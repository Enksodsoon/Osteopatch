"""Start a CURRENT-CODE dev stack (API + Vite) on free ports and print the URL.

Why this exists
---------------
Port 8137 is the documented default, but a server from an earlier session is
still squatting there.  It was started before the limitations catalog landed, so
it answers /v1/model-card with only the frozen five entries and no
`limitations_full` key.  Opening the app through it shows stale code.

This picks free ports instead of touching anyone else's process, points Vite at
the fresh backend via VITE_API_TARGET, and verifies the catalog really is served
before printing the URL.  Educational research prototype; not for diagnosis.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = REPO / ".venv" / "Scripts" / "python.exe"
VITE_CLI = REPO / "app" / "g6" / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
LOGDIR = REPO / "runtime-artifacts" / "devlogs"


def free_port() -> int:
    """Ask the OS for a port nobody is listening on, then let go.

    There is an unavoidable race between releasing the socket and the child
    binding it, but it is small and this keeps us off every port another
    thread or dev server already owns.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_healthy(url: str, timeout: float = 90.0, expect_json: bool = True) -> dict:
    """Poll ``url`` until it answers, and return the decoded JSON body.

    ``expect_json=False`` is for Vite's ``/``, which serves the HTML shell rather
    than JSON.  Parsing that as JSON would raise on every poll and the wait would
    never succeed, so the caller has to say which kind of readiness it means.
    Mirrors the same ``expect_json`` switch in ``scripts/e2e_ui.py``.
    """
    deadline = time.time() + timeout
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if not expect_json:
                    return {}
                return json.load(r)
        except Exception as exc:  # noqa: BLE001 - boot polling
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(0.4)
    raise SystemExit(f"FATAL: {url} never became healthy. Last error: {last}")


def main() -> int:
    LOGDIR.mkdir(parents=True, exist_ok=True)
    api_port, web_port = free_port(), free_port()
    api_base = f"http://127.0.0.1:{api_port}"
    web_base = f"http://127.0.0.1:{web_port}"

    api_log = open(LOGDIR / "dev-api.log", "w", encoding="utf-8")
    web_log = open(LOGDIR / "dev-web.log", "w", encoding="utf-8")

    api = subprocess.Popen(
        [
            str(PY), "-m", "uvicorn", "osteopatch.app:app",
            "--app-dir", str(REPO / "app" / "g6" / "backend"),
            "--host", "127.0.0.1", "--port", str(api_port),
        ],
        cwd=str(REPO), stdout=api_log, stderr=subprocess.STDOUT,
    )
    web = None
    try:
        health = wait_healthy(f"{api_base}/v1/health")
        print(f"API up: {api_base} ({health.get('images_indexed')} images)")

        web = subprocess.Popen(
            [
                "node", str(VITE_CLI),
                "--host", "--port", str(web_port), "--strictPort",
            ],
            cwd=str(REPO / "app" / "g6" / "frontend"),
            env={**os.environ, "VITE_API_TARGET": api_base},
            stdout=web_log, stderr=subprocess.STDOUT,
        )
        wait_healthy(f"{web_base}/", timeout=90.0, expect_json=False)

        # Prove the proxy reaches THIS backend, not the stale 8137 one.
        with urllib.request.urlopen(f"{web_base}/v1/health", timeout=10) as r:
            proxied = json.load(r)
        with urllib.request.urlopen(f"{web_base}/v1/model-card", timeout=15) as r:
            card = json.load(r)
    except SystemExit:
        for p in (web, api):
            if p and p.poll() is None:
                p.terminate()
        raise
    finally:
        api_log.flush()
        web_log.flush()

    full = card.get("limitations_full")
    print(f"proxied health images: {proxied.get('images_indexed')}")
    print(f"limitations (frozen five): {len(card.get('limitations', []))}")
    print(f"limitations_full entries: {len(full) if isinstance(full, list) else 'ABSENT -> STALE'}")
    print(f"evaluation_evidence_available: {card.get('evaluation_evidence_available', 'ABSENT -> STALE')}")
    print(f"pids: api={api.pid} web={web.pid}")
    print()
    print(f"OPEN IN EDGE: {web_base}")
    print(f"logs: {LOGDIR / 'dev-api.log'} , {LOGDIR / 'dev-web.log'}")
    print(f"stop: taskkill /PID {api.pid} /F  and  taskkill /PID {web.pid} /F")
    return 0


if __name__ == "__main__":
    sys.exit(main())
