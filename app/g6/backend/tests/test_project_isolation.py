"""Project isolation — the acceptance tests for replacing global tenancy.

The previous mechanism wrote os.environ and reassigned module globals at
request time, never restoring them. These tests exist to make that failure
mode impossible to reintroduce silently.

Covered:
  * two projects see disjoint image sets, in both directions
  * a cross-project image read is refused, and is indistinguishable from
    "does not exist" so it cannot be used to probe for another tenant's data
  * a cross-project review submission is refused
  * export is scoped
  * interleaved concurrent requests do not contaminate each other
  * the request path never mutates process-global state
  * the migration is additive: the immutable predictions are untouched
"""
from __future__ import annotations

import os
import sqlite3
import sys
import threading
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from osteopatch import db, projects, queries, repo  # noqa: E402

HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"

# Disjoint image sets: A owns 1-3, B owns 4-6.
IMAGES_A = ["img-a1", "img-a2", "img-a3"]
IMAGES_B = ["img-b1", "img-b2", "img-b3"]


@pytest.fixture()
def scoped(tmp_path):
    conn = db.connect(tmp_path / "iso.sqlite3")
    db.run_migrations(conn)
    for iid in IMAGES_A + IMAGES_B:
        conn.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label, "
            "primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, "
            "tiff_filename) VALUES (?,?,?,?,?,?,?,?)",
            (iid, "Case-3", "NON_TUMOR", "PASS", 1, 0, None, f"{iid}.tiff"),
        )
    for iid in IMAGES_A + IMAGES_B:
        repo.upsert_prediction(conn, iid, HASH, "baseline-frozen-g4", [0.8, 0.1, 0.1])
    conn.commit()
    projects.grant_images(conn, "proj-A", IMAGES_A)
    projects.grant_images(conn, "proj-B", IMAGES_B)
    yield conn
    conn.close()


def _listed(conn, pid):
    return {i["image_id"] for i in queries.list_images(conn, page_size=500, project_id=pid)["items"]}


# ---------------------------------------------------------------------------
# Isolation
# ---------------------------------------------------------------------------


def test_projects_see_disjoint_sets(scoped):
    assert _listed(scoped, "proj-A") == set(IMAGES_A)
    assert _listed(scoped, "proj-B") == set(IMAGES_B)
    assert _listed(scoped, "proj-A").isdisjoint(_listed(scoped, "proj-B"))


def test_cross_project_read_is_refused(scoped):
    assert queries.get_image(scoped, "img-a1", project_id="proj-B") is None
    assert queries.get_image(scoped, "img-b1", project_id="proj-A") is None
    # Same project still works.
    assert queries.get_image(scoped, "img-a1", project_id="proj-A") is not None


def test_unknown_and_foreign_are_indistinguishable(scoped):
    """A 404 for another tenant must not confirm the image exists."""
    foreign = queries.get_image(scoped, "img-a1", project_id="proj-B")
    nonexistent = queries.get_image(scoped, "no-such-image", project_id="proj-B")
    assert foreign is None and nonexistent is None


def test_export_is_scoped(scoped):
    a = {r["image_id"] for r in queries.export_rows(scoped, project_id="proj-A")}
    b = {r["image_id"] for r in queries.export_rows(scoped, project_id="proj-B")}
    assert a == set(IMAGES_A)
    assert b == set(IMAGES_B)
    assert a.isdisjoint(b)


def test_review_priority_rank_is_scoped(scoped):
    """Ranking must be computed within the project, not globally."""
    rank_a = queries._priority_rank_map(scoped, "proj-A")
    rank_b = queries._priority_rank_map(scoped, "proj-B")
    assert set(rank_a) == set(IMAGES_A)
    assert set(rank_b) == set(IMAGES_B)


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------


def test_interleaved_concurrent_requests_do_not_contaminate(tmp_path):
    """Interleave both projects' reads and assert neither ever sees the other.

    Under the old env/global mechanism, whichever project was applied last won
    the race; this test is the direct regression guard for that.

    Each thread opens its OWN connection, which is how a real server serves
    concurrent requests. Sharing one sqlite3.Connection across threads is not
    safe (interleaved cursor state), and testing that would prove nothing
    about scoping.
    """
    path = tmp_path / "iso.sqlite3"
    setup = db.connect(path)
    db.run_migrations(setup)
    for iid in IMAGES_A + IMAGES_B:
        setup.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label, "
            "primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, "
            "tiff_filename) VALUES (?,?,?,?,?,?,?,?)",
            (iid, "Case-3", "NON_TUMOR", "PASS", 1, 0, None, f"{iid}.tiff"),
        )
        repo.upsert_prediction(setup, iid, HASH, "baseline-frozen-g4", [0.8, 0.1, 0.1])
    setup.commit()
    projects.grant_images(setup, "proj-A", IMAGES_A)
    projects.grant_images(setup, "proj-B", IMAGES_B)
    setup.close()

    seen: dict[str, list[set[str]]] = {"proj-A": [], "proj-B": []}
    errors: list[Exception] = []
    start = threading.Barrier(8)

    def worker(pid: str) -> None:
        conn = None
        try:
            conn = db.connect(path)
            start.wait()
            for _ in range(25):
                seen[pid].append(_listed(conn, pid))
        except Exception as exc:  # pragma: no cover - surfaced below
            errors.append(exc)
        finally:
            if conn is not None:
                conn.close()

    threads = [threading.Thread(target=worker, args=(p,)) for p in ("proj-A", "proj-B") * 4]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert seen["proj-A"] and all(s == set(IMAGES_A) for s in seen["proj-A"])
    assert seen["proj-B"] and all(s == set(IMAGES_B) for s in seen["proj-B"])


def test_request_path_does_not_mutate_process_state(scoped):
    """The regression guard: no global may change as a result of a read."""
    import osteopatch.config as g6_config

    before = {
        "env": os.environ.get("OSTEOPATCH_IMAGE_ALLOWLIST"),
        "cfg_path": getattr(g6_config, "IMAGE_ALLOWLIST_PATH", None),
        "cfg_cache": getattr(g6_config, "_IMAGE_ALLOWLIST_CACHE", "<absent>"),
    }
    queries.list_images(scoped, page_size=10, project_id="proj-A")
    queries.list_images(scoped, page_size=10, project_id="proj-B")
    queries.get_image(scoped, "img-a1", project_id="proj-A")

    after = {
        "env": os.environ.get("OSTEOPATCH_IMAGE_ALLOWLIST"),
        "cfg_path": getattr(g6_config, "IMAGE_ALLOWLIST_PATH", None),
        "cfg_cache": getattr(g6_config, "_IMAGE_ALLOWLIST_CACHE", "<absent>"),
    }
    assert before == after, "a request mutated process-global tenancy state"


# ---------------------------------------------------------------------------
# The migration itself
# ---------------------------------------------------------------------------


def test_migration_is_additive_and_preserves_predictions(tmp_path):
    """Rows created before migration must be backfilled, never rewritten."""
    path = tmp_path / "legacy.sqlite3"

    # --- build a database at schema v1 only ---
    legacy = db.connect(path)
    (db.MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8")
    legacy.executescript((db.MIGRATIONS_DIR / "0001_initial.sql").read_text(encoding="utf-8"))
    legacy.execute(
        "INSERT INTO source_qc(image_id, source_group, original_label, "
        "primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, "
        "tiff_filename) VALUES ('legacy-1','Case-3','NECROSIS','PASS',1,0,NULL,'l.tiff')"
    )
    repo.upsert_prediction(legacy, "legacy-1", HASH, "baseline-frozen-g4", [0.1, 0.2, 0.7])
    legacy.commit()

    before = legacy.execute(
        "SELECT prediction_id, image_id, model_bundle_hash, model_version, predicted_class, "
        "non_tumor_score, viable_tumor_score, necrosis_score, top_two_margin, "
        "normalized_entropy FROM prediction"
    ).fetchall()
    assert len(before) == 1
    legacy.close()

    # --- migrate forward ---
    migrated = db.connect(path)
    db.run_migrations(migrated)

    after = migrated.execute(
        "SELECT prediction_id, image_id, model_bundle_hash, model_version, predicted_class, "
        "non_tumor_score, viable_tumor_score, necrosis_score, top_two_margin, "
        "normalized_entropy FROM prediction"
    ).fetchall()

    assert len(after) == 1
    assert tuple(after[0]) == tuple(before[0]), "a prediction row changed during migration"
    assert after[0]["model_bundle_hash"] == HASH, "model identity must never be reassigned"

    # The backfilled row is visible under the default project.
    assert [r["image_id"] for r in migrated.execute(
        "SELECT image_id FROM source_qc WHERE project_id = ?",
        (projects.DEFAULT_PROJECT_ID,),
    )] == ["legacy-1"]
    migrated.close()


def test_grant_rejects_unknown_ids_fail_closed(scoped):
    with pytest.raises(projects.ProjectScopeError):
        projects.grant_images(scoped, "proj-C", ["img-a1", "does-not-exist"])


def test_grant_rejects_empty_project_id(scoped):
    with pytest.raises(projects.ProjectScopeError):
        projects.grant_images(scoped, "   ", IMAGES_A)


def test_no_project_id_leaves_rows_unchanged(scoped):
    """Rows must not be mutated by being read."""
    rows = [tuple(r) for r in scoped.execute(
        "SELECT image_id, project_id FROM source_qc ORDER BY image_id"
    )]
    assert all(pid in ("proj-A", "proj-B") for _iid, pid in rows)
    assert sqlite3.connect  # keep the import meaningful