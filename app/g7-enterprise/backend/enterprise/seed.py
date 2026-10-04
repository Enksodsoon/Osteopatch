"""Seed demo users + a demo project with the full role matrix (idempotent).

Run: python -m enterprise.seed
Creates:
  - project "Demo Osteosarcoma Review"
  - users: admin@demo, path@demo, reviewer@demo, student@demo, mle@demo, auditor@demo
    each with the matching role in the demo project.
"""
from __future__ import annotations

from . import store

DEMO_USERS = [
    ("admin@demo", "admin"),
    ("path@demo", "pathologist"),
    ("reviewer@demo", "reviewer"),
    ("student@demo", "student"),
    ("mle@demo", "ml_engineer"),
    ("auditor@demo", "auditor"),
]
DEMO_PROJECT_NAME = "Demo Osteosarcoma Review"


def seed(conn=None) -> dict:
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
    return {"project_id": pid, "users": [e for e, _ in DEMO_USERS]}


if __name__ == "__main__":
    result = seed()
    print("Seeded demo project:", result["project_id"])
    for email in result["users"]:
        print("  user:", email)
    print("\nLogin example:")
    print('  POST /auth/login {"email": "reviewer@demo"}')
    print(f'  then send header  X-Project-Id: {result["project_id"]}')
