"""Project scoping — the single canonical model.

Replaces the process-global allowlist mutation that previously enforced
tenancy. Nothing here mutates process state: a project id is an explicit
argument or a column value, so two concurrent requests for different projects
cannot observe each other.

Relationship to the G8 demo subset
---------------------------------
Two different concerns were previously conflated behind one mechanism:

  * **demo subset** — the deployed demo shows a deterministic 50-image slice.
    That is DEPLOYMENT CONFIG and stays in ``config.load_image_allowlist()``.
    It is read-only and set at import.
  * **tenancy** — which project may see which images. That is what this module
    owns, and it lives in the database.

Conflating them is why tenant switching had to mutate globals at all.

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import sqlite3

#: Rows predating explicit project scoping belong here.
DEFAULT_PROJECT_ID = "__default__"


class ProjectScopeError(RuntimeError):
    """Raised for an invalid project-scope operation. Fails closed."""


def assign_legacy_project(
    conn: sqlite3.Connection, project_id: str = DEFAULT_PROJECT_ID
) -> int:
    """Backfill NULL project_id on pre-existing rows.

    Idempotent. Returns the number of rows updated.

    Deliberately updates only the ``project_id`` column of rows that do not yet
    have one. It never touches a score, a label, a model hash or a timestamp,
    and never deletes anything.
    """
    total = 0
    for table in ("source_qc", "prediction", "review_event"):
        cur = conn.execute(
            f"UPDATE {table} SET project_id = ? WHERE project_id IS NULL",  # noqa: S608
            (project_id,),
        )
        total += cur.rowcount or 0
    conn.commit()
    return total


def grant_images(
    conn: sqlite3.Connection, project_id: str, image_ids: list[str]
) -> list[str]:
    """Assign the given images to ``project_id``.

    Fail-closed: every id must already exist in ``source_qc``. An unknown id is
    rejected outright rather than silently granted, because a typo that quietly
    grants nothing is worse than a loud failure.
    """
    if not project_id or not str(project_id).strip():
        raise ProjectScopeError("project_id must be a non-empty string")
    wanted = list(dict.fromkeys(image_ids or []))
    if not wanted:
        return []

    known = {
        r["image_id"]
        for r in conn.execute(
            f"SELECT image_id FROM source_qc WHERE image_id IN ({','.join('?' * len(wanted))})",
            wanted,
        )
    }
    unknown = [i for i in wanted if i not in known]
    if unknown:
        raise ProjectScopeError(
            f"unknown image_ids rejected (fail-closed scope): {unknown[:10]}"
            f"{' …' if len(unknown) > 10 else ''}"
        )

    conn.execute(
        "UPDATE source_qc   SET project_id = ? WHERE image_id IN "
        f"({','.join('?' * len(wanted))})",
        [project_id, *wanted],
    )
    conn.execute(
        "UPDATE prediction  SET project_id = ? WHERE image_id IN "
        f"({','.join('?' * len(wanted))})",
        [project_id, *wanted],
    )
    conn.execute(
        "UPDATE review_event SET project_id = ? WHERE image_id IN "
        f"({','.join('?' * len(wanted))})",
        [project_id, *wanted],
    )
    conn.commit()
    return wanted


def project_image_ids(conn: sqlite3.Connection, project_id: str) -> list[str]:
    """Every image_id visible to ``project_id``, sorted."""
    return [
        r["image_id"]
        for r in conn.execute(
            "SELECT image_id FROM source_qc WHERE project_id = ? ORDER BY image_id",
            (project_id,),
        )
    ]


def known_image_ids(conn: sqlite3.Connection, limit: int | None = None) -> list[str]:
    """Every image_id in the corpus, for grant validation."""
    sql = "SELECT image_id FROM source_qc ORDER BY image_id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return [r["image_id"] for r in conn.execute(sql)]


def projects(conn: sqlite3.Connection) -> list[str]:
    return [
        r["project_id"]
        for r in conn.execute(
            "SELECT DISTINCT project_id FROM source_qc "
            "WHERE project_id IS NOT NULL ORDER BY project_id"
        )
    ]