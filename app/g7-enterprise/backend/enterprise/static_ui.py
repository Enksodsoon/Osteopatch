"""Serving the built unified frontend from the API, same-origin.

Why this exists
---------------
The unified UI has to talk to ``/v1/*`` on a different origin than the Vite dev
server. There are two ways to settle that, and only one of them is honest:

  * **CORS** — the browser would preflight every call, including the custom
    ``X-File-Name`` and ``X-Project-Id`` headers. It needs a credentialed-origin
    allowlist, which on a 127.0.0.1 prototype means trusting whatever port the
    presenter happens to be running. That is a real widening for a demo.
  * **Same origin** — serve the built bundle from this app. No preflight, no
    allowlist, no cross-origin trust decision at all.

So this serves ``dist/`` when it exists. In development the Vite proxy in
``frontend/vite.config.ts`` still handles it and this module is inert.

Fails closed and quietly
------------------------
A missing ``dist/`` is normal (fresh clone, no build yet) and is NOT an error:
this logs one line and mounts nothing, leaving the API exactly as it was. It
never serves the repository, never serves ``runtime-artifacts``, and never
invents a page for an unknown API route.

The mount goes LAST so that every ``/v1`` and ``/api/v1`` route above keeps
priority; an SPA catch-all registered first would shadow the entire API.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

log = logging.getLogger(__name__)

#: ``app/g7-enterprise/frontend/dist``. Resolved from this file so the backend
#: works regardless of the process's working directory.
DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def mount_frontend(app: FastAPI, dist: Path = DIST) -> bool:
    """Serve the built SPA at ``/`` when ``dist/index.html`` exists.

    Returns whether it mounted. Safe to call unconditionally and safe to call
    when the bundle has not been built.
    """
    index = dist / "index.html"
    if not index.is_file():
        log.info(
            "frontend bundle not built at %s — serving the API only "
            "(run: npm --prefix app/g7-enterprise/frontend run build)",
            dist,
        )
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_root() -> FileResponse:
        return FileResponse(index)

    # Client-side routes are single-segment here (no router library), so any
    # remaining GET that is not an API path and does not look like a file falls
    # back to the shell. API prefixes are excluded explicitly rather than by
    # ordering, so a new route added below this line cannot be swallowed.
    @app.get("/{spa_path:path}", include_in_schema=False)
    def spa_fallback(spa_path: str) -> FileResponse:
        if spa_path.startswith(("v1/", "api/", "auth/")):
            return FileResponse(index, status_code=404)
        candidate = dist / spa_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)

    log.info("serving the unified frontend from %s", dist)
    return True