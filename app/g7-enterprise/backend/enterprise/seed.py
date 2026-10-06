"""Seed demo users + a demo project with the full role matrix (idempotent).

Run: python -m enterprise.seed
Creates:
  - project "Demo Osteosarcoma Review"
  - users: admin@demo, path@demo, reviewer@demo, student@demo, mle@demo, auditor@demo
    each with the matching role in the demo project.
  - a DETERMINISTIC review scope for that project: the ``DEMO_SCOPE_SIZE`` most
    review-priority images in the corpus.

Why the scope matters
---------------------
A login that lands on an empty gallery is not a demo. Without a grant, the new
project owns no images and every read is a 404 by design. Seeding the scope
here means a fresh clone plus one seed command gives a presenter a populated,
uncertainty-first queue.

Determinism is the point. Review priority is a pure function of the frozen
scores (margin + normalised entropy), so the same read model always yields the
same 50 images — the demo does not reshuffle between runs. It is *not* a
random sample and is not presented as representative of the full 1,144.

Re-granting is idempotent: ``projects.grant_images`` re-assigns project_id, so
re-seeding converges rather than accumulating.

Degradation is honest
---------------------
Seeding must also work where the G6 read model is absent — a bare test
environment, a clone with no runtime artifacts. The scope step then reports
``status: "unavailable"`` with the reason, and seeding still succeeds. It never
reports a populated gallery it did not populate.

Scoping is opt-in
-----------------
``seed()`` does NOT grant a scope unless asked (``scope_size`` is not None),
because granting WRITES to the G6 read model — it re-assigns ``project_id`` on
real corpus rows. A test fixture calling ``seed()`` must never be able to
re-scope the canonical 1,144-image store by accident. The CLI is the demo path
and asks for it explicitly.
"""
from __future__ import annotations

import logging

from . import store

log = logging.getLogger(__name__)

DEMO_USERS = [
    ("admin@demo", "admin"),
    ("path@demo", "pathologist"),
    ("reviewer@demo", "reviewer"),
    ("student@demo", "student"),
    ("mle@demo", "ml_engineer"),
    ("auditor@demo", "auditor"),
]
DEMO_PROJECT_NAME = "Demo Osteosarcoma Review"

#: How many images the demo project owns. Matches the G8 deployed-demo subset
#: size so local and hosted demos present the same amount of work.
DEMO_SCOPE_SIZE = 50


def grant_demo_scope(project_id: str, size: int = DEMO_SCOPE_SIZE) -> dict:
    """Grant the demo project its deterministic review scope.

    MUTATES the G6 read model: ``projects.grant_images`` re-assigns
    ``project_id`` on real corpus rows. Callers that only need users and roles
    must not call this.

    Returns a status dict rather than raising: seeding is also the local
    test-fixture entry point, and a missing G6 store is a valid configuration
    there. The returned dict says exactly what happened, so no caller has to
    guess whether the gallery will be populated.
    """
    from fastapi import HTTPException

    from . import review_proxy

    try:
        image_ids = review_proxy.top_priority_image_ids(size)
    except HTTPException as exc:
        return {
            "status": "unavailable",
            "requested": size,
            "granted": 0,
            "reason": "G6 review backend unavailable",
            "detail": exc.detail,
        }

    if not image_ids:
        return {
            "status": "empty",
            "requested": size,
            "granted": 0,
            "reason": "corpus returned no images; run scripts/prepare_runtime.py",
        }

    from osteopatch import projects  # type: ignore

    conn = review_proxy.g6_conn()
    try:
        granted = projects.grant_images(conn, project_id, image_ids)
    except projects.ProjectScopeError as exc:
        # Fail-closed: an unknown id is rejected, never silently skipped.
        return {
            "status": "rejected",
            "requested": size,
            "granted": 0,
            "reason": str(exc),
        }

    return {
        "status": "granted",
        "requested": size,
        "granted": len(granted),
        "selection": "highest review priority (frozen score margin + normalised entropy)",
        "deterministic": True,
        "image_ids_sample": granted[:5],
    }


def seed(conn=None, *, scope_size: int | None = None) -> dict:
    """Create/refresh the demo project, its users, and its memberships.

    ``scope_size=None`` (the default) grants NOTHING in the G6 read model. Pass
    ``scope_size=DEMO_SCOPE_SIZE`` — as the CLI below does — to also populate
    the gallery.
    """
    conn = conn or store.connect()
    admin = store.upsert_user(conn, "admin@demo")
    # reuse an existing demo project if present
    existing = conn.execute(
        "SELECT project_id FROM project WHERE name = ?", (DEMO_PROJECT_NAME,)
    ).fetchone()
    if existing:
        pid = existing["project_id"]
    else:
        pid = store.create_project(conn, DEMO_PROJECT_NAME, admin["user_id"])["project_id"]
    for email, role in DEMO_USERS:
        u = store.upsert_user(conn, email)
        store.add_membership(conn, u["user_id"], pid, role)
    return {
        "project_id": pid,
        "users": [e for e, _ in DEMO_USERS],
        "scope": grant_demo_scope(pid, scope_size) if scope_size else {"status": "not_requested"},
    }


if __name__ == "__main__":
    result = seed(scope_size=DEMO_SCOPE_SIZE)
    print("Seeded demo project:", result["project_id"])
    for email in result["users"]:
        print("  user:", email)
    scope = result["scope"]
    print(f"\nDemo scope: {scope['status']} ({scope.get('granted', 0)}/{scope.get('requested', 0)} images)")
    if scope["status"] != "granted":
        print("  reason:", scope.get("reason"))
    print("\nLogin example:")
    print('  POST /auth/login {"email": "reviewer@demo"}')
    print(f'  then send header  X-Project-Id: {result["project_id"]}')
