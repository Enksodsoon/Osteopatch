"""F003 acceptance tests - centralized authorization scope + explicit selection.

Acceptance IDs (task F003 section 9):

  F003-AT01  Project A cannot see Project B in results, ranks, counts, or errors.
  F003-AT02  Two predictions for an image result in one selected row for an
             explicit model, not two gallery cards.
  F003-AT03  The 50-image deployment allowlist is honored even when project scope
             contains all 1,144 images.
  F003-AT04  Changing model hash changes selected predictions without overwriting
             the older model.
  F003-AT05  Empty permitted intersection returns an empty authorized result, not
             an unscoped fallback.

Plus Step 08's boundary review: no rows, one row, duplicate rows under a
supposedly unique identity, malformed values, changed project/model/session, and
"the request path never mutates a process-global allowlist".

Corpora
-------
Two, on purpose:

* ``two_models`` (F002 fixture) - 8 synthetic images, 2 model bundles, lets us
  build two overlapping projects deterministically. Synthetic, TEST_FIXTURE.
* the real throwaway store - the 50-image allowlist check (AT03) is meaningless
  against 8 synthetic rows, so AT03 uses the verified real corpus.

Neither test opens ``config.DB_PATH``: ``make_review_fixture`` takes a
caller-supplied root and the real corpus is copied into ``tmp_path`` first.
"""
from __future__ import annotations

import dataclasses
import os
import shutil
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from fixtures.review_fixture import (  # noqa: E402
    FIXTURE_MODEL_HASH,
    FIXTURE_MODEL_VERSION,
    FIXTURE_OTHER_MODEL_HASH,
    make_review_fixture,
)
from osteopatch import config, db, projects, queries, repo  # noqa: E402
from osteopatch import scope as scope_mod  # noqa: E402

SEED_IDS = [f"fx-0{i}" for i in range(1, 9)]

#: An allowlist narrower than both the project and the dataset.
ALLOW_5 = frozenset(SEED_IDS[:5])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_models(tmp_path):
    """The F002 ``two_models`` fixture: 8 images x 2 bundles, project __default__."""
    paths = make_review_fixture(tmp_path / "fx", "two_models")
    conn = paths.open()
    try:
        yield paths, conn
    finally:
        conn.close()


def scoped_for(project_id, *, allowlist=None, model=FIXTURE_MODEL_HASH,
               dataset_ids=frozenset(SEED_IDS), session="s-1", actor="u-1"):
    """A ScopeContext whose dataset membership is the synthetic corpus itself.

    ``dataset_ids`` is supplied explicitly because the fixture ids are, by
    design, absent from the real ingestion manifest. The server-side resolver in
    scope.py does this for the real corpus; here the test states it directly.
    """
    return scope_mod.ScopeContext(
        project_id=project_id,
        dataset_version_id="test-fixture-dataset",
        dataset_image_ids=dataset_ids,
        model_bundle_hash=model,
        deployment_allowlist=allowlist,
        review_session_id=session,
        actor_id=actor,
    )


def grant(conn, project_id, image_ids):
    projects.grant_images(conn, project_id, image_ids)


def all_predictions(conn):
    """Every stored prediction as a dict, for before/after immutability checks."""
    return sorted(
        (dict(r) for r in conn.execute("SELECT * FROM prediction")),
        key=lambda p: p["prediction_id"],
    )


# ---------------------------------------------------------------------------
# F003-AT01 - project isolation across results, ranks, counts and errors
# ---------------------------------------------------------------------------


def test_F003_AT01_project_a_cannot_see_project_b(two_models):
    """AT01: results, counts, ranks, export and error shape are all project-local.

    The two projects are granted OVERLAPPING candidate lists (Step 02's case).
    ``source_qc.project_id`` is single-valued, so assignment is last-writer-wins;
    the point under test is that after assignment neither tenant can observe the
    other's images by any route, including via a total that would leak existence.
    """
    _paths, conn = two_models
    grant(conn, "proj-A", SEED_IDS[:5])
    grant(conn, "proj-B", SEED_IDS[3:])  # overlaps A on fx-04, fx-05

    a_ids = set(projects.project_image_ids(conn, "proj-A"))
    b_ids = set(projects.project_image_ids(conn, "proj-B"))
    # fx-04/fx-05 were re-granted to B, so they left A. Ownership is exclusive.
    assert a_ids.isdisjoint(b_ids), "an image may belong to only one project"
    assert b_ids == set(SEED_IDS[3:])

    # --- results + counts ---------------------------------------------------
    res_a = queries.list_images(conn, page_size=500, scope=scoped_for("proj-A"))
    res_b = queries.list_images(conn, page_size=500, scope=scoped_for("proj-B"))
    listed_a = {i["image_id"] for i in res_a["items"]}
    listed_b = {i["image_id"] for i in res_b["items"]}
    assert listed_a == a_ids
    assert listed_b == b_ids
    assert listed_a.isdisjoint(listed_b)
    # A's total must not count B's images: B's existence is not inferable.
    assert res_a["total"] == len(a_ids)
    assert res_b["total"] == len(b_ids)
    assert len(res_a["items"]) == res_a["total"]

    # --- ranks are computed within the project ------------------------------
    for image in res_a["items"]:
        assert image["review_priority_rank"] is not None
        assert image["review_priority_rank"] <= res_a["total"]
    for image in res_b["items"]:
        assert image["review_priority_rank"] <= res_b["total"]
    # A's ranks are dense within A: no global numbering leaks through.
    assert sorted(i["review_priority_rank"] for i in res_a["items"]) == list(
        range(1, len(a_ids) + 1)
    )

    # --- export -------------------------------------------------------------
    ex_a = {r["image_id"] for r in queries.export_rows(conn, scope=scoped_for("proj-A"))}
    ex_b = {r["image_id"] for r in queries.export_rows(conn, scope=scoped_for("proj-B"))}
    assert ex_a == a_ids
    assert ex_b == b_ids

    # --- errors are indistinguishable ---------------------------------------
    foreign = queries.get_image(conn, "fx-06", scope=scoped_for("proj-A"))
    nonexistent = queries.get_image(conn, "no-such-image", scope=scoped_for("proj-A"))
    assert foreign is None and nonexistent is None
    assert queries.get_image(conn, "fx-01", scope=scoped_for("proj-A")) is not None


def test_F003_AT01_review_event_from_other_project_does_not_leak(two_models):
    """AT01: B's review activity is invisible to A, in state and in counts."""
    _paths, conn = two_models
    grant(conn, "proj-A", SEED_IDS[:4])
    grant(conn, "proj-B", SEED_IDS[4:])

    # The two_models variant already seeded events, so the current revision is
    # whatever the fixture left behind - read it rather than assuming 0.
    image_b = SEED_IDS[4]
    pid_b = repo.prediction_id_for(image_b, FIXTURE_MODEL_HASH)
    repo.submit_review(
        conn,
        image_id=image_b,
        prediction_id=pid_b,
        action="ACCEPT",
        expected_revision=repo.current_revision(conn, image_b),
        idempotency_key="f003-at01-b",
        reviewer="reviewer-b",
    )
    conn.commit()

    seen_a = queries.list_images(conn, page_size=500, scope=scoped_for("proj-A"))
    assert {i["image_id"] for i in seen_a["items"]} == set(SEED_IDS[:4])
    states = {i["image_id"]: i["review_state"] for i in seen_a["items"]}
    # fx-04 was deferred by B's seed event and is now A's, so A sees A's own
    # seeded states - exactly the fixture's, and nothing B just wrote.
    assert states["fx-01"]["status"] == "reviewed"
    assert states["fx-02"]["status"] == "reviewed"
    assert states["fx-03"]["status"] == "reviewed"
    assert states["fx-04"]["status"] == "deferred"
    # The image B just accepted is simply not in A's result set.
    assert image_b not in states
    # And the cross-project detail read stays refused, as does A seeing B's event.
    assert queries.get_image(conn, image_b, scope=scoped_for("proj-A")) is None
    assert queries.export_rows(conn, scope=scoped_for("proj-A"))[0].keys() >= {
        "image_id", "human_review_status", "scope_provenance"
    }
    assert image_b not in {
        r["image_id"] for r in queries.export_rows(conn, scope=scoped_for("proj-A"))
    }


# ---------------------------------------------------------------------------
# F003-AT02 - one selected row per image for an explicit model
# ---------------------------------------------------------------------------


def test_F003_AT02_two_predictions_yield_one_row_per_image(two_models):
    """AT02: 8 images x 2 bundles must still be 8 gallery cards, not 16."""
    _paths, conn = two_models
    total = conn.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    assert total == 2 * len(SEED_IDS), "fixture must really hold two bundles"

    result = queries.list_images(
        conn, page_size=500, scope=scoped_for(projects.DEFAULT_PROJECT_ID)
    )
    assert result["total"] == len(SEED_IDS)
    ids = [i["image_id"] for i in result["items"]]
    assert len(ids) == len(set(ids)) == len(SEED_IDS), "duplicate gallery cards"
    for image in result["items"]:
        assert image["prediction"] is not None
        assert image["prediction"]["model_bundle_hash"] == FIXTURE_MODEL_HASH


def test_F003_AT02_selection_helper_returns_one_row_per_image(two_models):
    """AT02 at the helper itself: no duplicate identity in the returned rows."""
    _paths, conn = two_models
    rows = scope_mod.resolve_prediction_rows(
        conn, scoped_for(projects.DEFAULT_PROJECT_ID)
    )
    assert len(rows) == len(SEED_IDS)
    assert len({r.image_id for r in rows}) == len(SEED_IDS)
    assert {r.model_bundle_hash for r in rows} == {FIXTURE_MODEL_HASH}


def test_F003_AT02_ranking_uses_only_the_selected_model(two_models):
    """AT02: the rank map must not silently pick the other bundle for an image."""
    _paths, conn = two_models
    rank_map = queries.priority_rank_map(
        conn, scope=scoped_for(projects.DEFAULT_PROJECT_ID)
    )
    assert set(rank_map) == set(SEED_IDS)
    assert sorted(rank_map.values()) == list(range(1, len(SEED_IDS) + 1))


# ---------------------------------------------------------------------------
# F003-AT03 - the 50-image allowlist beats a 1,144-image project
# ---------------------------------------------------------------------------


@pytest.fixture()
def real_corpus(tmp_path):
    """A writable COPY of the verified real store. Never config.DB_PATH itself."""
    source = Path(config.DB_PATH)
    if not source.is_file():
        pytest.skip("real store unavailable in this environment")
    target = tmp_path / "real-copy.sqlite3"
    shutil.copy2(source, target)
    conn = db.connect(target)
    try:
        yield conn
    finally:
        conn.close()


def test_F003_AT03_allowlist_of_50_narrows_a_1144_image_project(real_corpus):
    """AT03: project scope holds all 1,144; the allowlist still yields 50."""
    conn = real_corpus
    all_ids = projects.known_image_ids(conn)
    assert len(all_ids) == 1144, f"expected the real corpus, got {len(all_ids)}"

    allowlist = frozenset(all_ids[:50])
    sc = scope_mod.ScopeContext(
        project_id=projects.DEFAULT_PROJECT_ID,
        dataset_version_id=scope_mod.legacy_dataset_version_id(),
        dataset_image_ids=None,  # resolved from the verified manifest
        model_bundle_hash=config.EXPECTED_BUNDLE_SHA256,
        deployment_allowlist=allowlist,
        review_session_id="s-real",
        actor_id="u-real",
    )
    rows = scope_mod.resolve_prediction_rows(conn, sc)
    assert len(rows) == 50
    assert {r.image_id for r in rows} == set(allowlist)

    result = queries.list_images(conn, page_size=500, scope=sc)
    assert result["total"] == 50
    assert {i["image_id"] for i in result["items"]} == set(allowlist)
    assert len(queries.export_rows(conn, scope=sc)) == 50
    # An allowlisted image is readable; a non-allowlisted one is not.
    assert queries.get_image(conn, all_ids[0], scope=sc) is not None
    assert queries.get_image(conn, all_ids[100], scope=sc) is None


def test_F003_AT03_legacy_dataset_membership_is_the_manifest(real_corpus):
    """AT03: the legacy dataset id comes from the manifest SHA-256, and its
    membership is the manifest's image_ids - not a filename guess."""
    version_id = scope_mod.legacy_dataset_version_id()
    assert version_id.startswith("legacy-ingestion-manifest:sha256:")
    digest = version_id.rsplit(":", 1)[1]
    assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest)
    assert scope_mod.legacy_dataset_image_ids() == frozenset(
        projects.known_image_ids(real_corpus)
    )
    # Naming an unknown dataset without explicit membership fails closed rather
    # than silently widening to the whole store.
    unknown = scope_mod.ScopeContext(
        project_id=projects.DEFAULT_PROJECT_ID,
        dataset_version_id="dataset-that-does-not-exist",
        model_bundle_hash=config.EXPECTED_BUNDLE_SHA256,
    )
    with pytest.raises(scope_mod.DatasetUnavailable):
        _ = unknown.effective_dataset_image_ids
    with pytest.raises(scope_mod.DatasetUnavailable):
        scope_mod.resolve_prediction_rows(real_corpus, unknown)


# ---------------------------------------------------------------------------
# F003-AT04 - changing the model hash changes the selection, nothing is rewritten
# ---------------------------------------------------------------------------


def test_F003_AT04_changing_model_hash_changes_selection_without_overwriting(two_models):
    _paths, conn = two_models
    before = all_predictions(conn)

    owner = projects.DEFAULT_PROJECT_ID
    sel_v1 = scope_mod.resolve_prediction_rows(conn, scoped_for(owner))
    sel_v2 = scope_mod.resolve_prediction_rows(
        conn, scoped_for(owner, model=FIXTURE_OTHER_MODEL_HASH)
    )

    assert len(sel_v1) == len(sel_v2) == len(SEED_IDS)
    assert {r.model_bundle_hash for r in sel_v1} == {FIXTURE_MODEL_HASH}
    assert {r.model_bundle_hash for r in sel_v2} == {FIXTURE_OTHER_MODEL_HASH}
    assert {r.image_id for r in sel_v1} == {r.image_id for r in sel_v2}
    # Same images, different predictions selected - and the ids differ per model.
    assert {r.prediction_id for r in sel_v1}.isdisjoint(
        {r.prediction_id for r in sel_v2}
    )

    # The older model is untouched: the stored prediction set is unchanged.
    assert all_predictions(conn) == before
    assert len(before) == 2 * len(SEED_IDS)
    v1 = [p for p in before if p["model_bundle_hash"] == FIXTURE_MODEL_HASH]
    v2 = [p for p in before if p["model_bundle_hash"] == FIXTURE_OTHER_MODEL_HASH]
    assert len(v1) == len(v2) == len(SEED_IDS)
    assert all(p["model_version"] == FIXTURE_MODEL_VERSION for p in v1)
    assert all(p["model_version"] == "fixture-model-v2" for p in v2)


def test_F003_AT04_gallery_reflects_the_requested_model_only(two_models):
    _paths, conn = two_models
    res_v2 = queries.list_images(
        conn,
        page_size=500,
        scope=scoped_for(
            projects.DEFAULT_PROJECT_ID, model=FIXTURE_OTHER_MODEL_HASH
        ),
    )
    assert res_v2["total"] == len(SEED_IDS)
    for image in res_v2["items"]:
        assert image["prediction"]["model_bundle_hash"] == FIXTURE_OTHER_MODEL_HASH
        assert image["prediction"]["model_version"] == "fixture-model-v2"


# ---------------------------------------------------------------------------
# F003-AT05 - empty permitted intersection is an empty authorized result
# ---------------------------------------------------------------------------


def test_F003_AT05_empty_intersection_returns_empty_not_unscoped(two_models):
    """AT05: an allowlist disjoint from the project yields zero rows, and the
    unscoped fallback (all 8 images) is never reached."""
    _paths, conn = two_models
    grant(conn, "proj-A", SEED_IDS[:3])
    disjoint = frozenset(SEED_IDS[5:])  # owned by __default__, none by proj-A

    sc = scoped_for("proj-A", allowlist=disjoint)
    assert scope_mod.resolve_prediction_rows(conn, sc) == []

    result = queries.list_images(conn, page_size=500, scope=sc)
    assert result["total"] == 0
    assert result["items"] == []

    assert queries.export_rows(conn, scope=sc) == []
    assert queries.priority_rank_map(conn, scope=sc) == {}
    # Detail reads stay refused rather than falling back to an unscoped read.
    for image_id in SEED_IDS[:3] + sorted(disjoint):
        assert queries.get_image(conn, image_id, scope=sc) is None


def test_F003_AT05_empty_dataset_membership_returns_empty(two_models):
    _paths, conn = two_models
    sc = scoped_for(projects.DEFAULT_PROJECT_ID, dataset_ids=frozenset())
    assert scope_mod.resolve_prediction_rows(conn, sc) == []
    assert queries.list_images(conn, page_size=500, scope=sc)["total"] == 0


def test_F003_AT05_unknown_project_is_empty_not_everything(two_models):
    """AT05: a project that owns nothing must not see the corpus."""
    _paths, conn = two_models
    sc = scoped_for("proj-that-owns-nothing")
    assert scope_mod.resolve_prediction_rows(conn, sc) == []
    res = queries.list_images(conn, page_size=500, scope=sc)
    assert res["total"] == 0 and res["items"] == []


# ---------------------------------------------------------------------------
# Step 06 - duplicate rows under a supposedly unique identity
# ---------------------------------------------------------------------------

_DROP_UNIQUE_SQL = """
PRAGMA foreign_keys = OFF;
CREATE TABLE prediction_fixed (
    prediction_id       TEXT PRIMARY KEY,
    image_id            TEXT NOT NULL,
    model_version       TEXT NOT NULL,
    model_bundle_hash   TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    inference_kind      TEXT NOT NULL,
    predicted_class     TEXT NOT NULL,
    non_tumor_score     REAL NOT NULL,
    viable_tumor_score  REAL NOT NULL,
    necrosis_score      REAL NOT NULL,
    top1_score          REAL NOT NULL,
    top_two_margin      REAL NOT NULL,
    normalized_entropy  REAL NOT NULL,
    project_id          TEXT
);
INSERT INTO prediction_fixed SELECT * FROM prediction;
DROP TABLE prediction;
ALTER TABLE prediction_fixed RENAME TO prediction;
PRAGMA foreign_keys = ON;
"""


def test_step06_duplicate_identity_raises_integrity_error(tmp_path):
    """Step 06: a store violating UNIQUE(image_id, model_bundle_hash) must
    produce an integrity error, never a silently chosen prediction."""
    conn = db.connect(tmp_path / "dup.sqlite3")
    db.run_migrations(conn)
    try:
        conn.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label, "
            "primary_qc_status, training_eligible, qc_review_flag, "
            "qc_review_reason, tiff_filename, project_id) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            ("dup-1", "G", "NON_TUMOR", "PASS", 1, 0, None, "dup-1.tiff", "proj"),
        )
        conn.commit()

        # Rebuild `prediction` WITHOUT its UNIQUE(image_id, model_bundle_hash),
        # then write two rows for one image under one model: the corrupted or
        # legacy store Step 06 warns about.
        conn.executescript(_DROP_UNIQUE_SQL)
        for suffix in ("a", "b"):
            conn.execute(
                "INSERT INTO prediction(prediction_id, image_id, model_version, "
                "model_bundle_hash, created_at, inference_kind, predicted_class, "
                "non_tumor_score, viable_tumor_score, necrosis_score, top1_score, "
                "top_two_margin, normalized_entropy, project_id) "
                "VALUES (?,?,?,?,'2026-01-01T00:00:00+00:00',"
                "'prototype_inference','NON_TUMOR',0.5,0.3,0.2,0.5,0.2,0.9,?)",
                (f"dup-{suffix}", "dup-1", "m", FIXTURE_MODEL_HASH, "proj"),
            )
        conn.commit()

        sc = scope_mod.ScopeContext(
            project_id="proj",
            dataset_version_id="test-fixture-dataset",
            dataset_image_ids=frozenset({"dup-1"}),
            model_bundle_hash=FIXTURE_MODEL_HASH,
        )
        with pytest.raises(scope_mod.PredictionSelectionIntegrityError) as excinfo:
            scope_mod.resolve_prediction_rows(conn, sc)
        message = str(excinfo.value)
        assert "dup-1" in message
        assert FIXTURE_MODEL_HASH in message, "the error must name the model scope"

        # It is an error, not a silent pick: the gallery path surfaces it too.
        with pytest.raises(scope_mod.PredictionSelectionIntegrityError):
            queries.list_images(conn, page_size=10, scope=sc)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Step 03 / 07 - immutability, server-side resolution, no global mutation
# ---------------------------------------------------------------------------


def test_step03_scope_context_is_immutable(two_models):
    _paths, conn = two_models
    del conn
    sc = scoped_for("proj")
    # A frozen dataclass raises FrozenInstanceError; assert that exactly, so a
    # blanket `Exception` cannot hide a different failure behind it.
    with pytest.raises(dataclasses.FrozenInstanceError):
        sc.project_id = "proj-other"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        sc.deployment_allowlist = frozenset({"fx-99"})  # type: ignore[misc]
    assert sc.project_id == "proj"
    assert sc.deployment_allowlist is None


def test_step03_scope_context_rejects_malformed_values():
    with pytest.raises(ValueError):
        scope_mod.ScopeContext(model_bundle_hash="")
    with pytest.raises(ValueError):
        scope_mod.ScopeContext(model_bundle_hash="   ")
    with pytest.raises(ValueError):
        scope_mod.ScopeContext(project_id="")


def test_step07_cache_key_covers_scope_and_model():
    base = scoped_for("proj-A")
    distinct = [
        base,
        scoped_for("proj-B"),                                   # project
        scoped_for("proj-A", model=FIXTURE_OTHER_MODEL_HASH),   # model
        scoped_for("proj-A", allowlist=ALLOW_5),                # allowlist
        scoped_for("proj-A", session="s-2"),                    # session
        scoped_for("proj-A", actor="u-2"),                      # actor
        scoped_for("proj-A", dataset_ids=frozenset(SEED_IDS[:4])),  # dataset
    ]
    keys = [s.cache_key for s in distinct]
    assert len(set(keys)) == len(keys), "project/model/session/allowlist/actor/dataset"
    # An identical scope is a stable, order-independent digest.
    assert base.cache_key == scoped_for("proj-A").cache_key
    assert len(base.cache_key) == 64
    assert all(c in "0123456789abcdef" for c in base.cache_key)


def test_step07_read_never_mutates_a_process_global_allowlist(two_models):
    """Step 07: no request may impersonate a project by editing global state."""
    import osteopatch.config as g6_config

    _paths, conn = two_models

    def snapshot():
        return {
            "env": os.environ.get("OSTEOPATCH_IMAGE_ALLOWLIST"),
            "cfg_path": getattr(g6_config, "IMAGE_ALLOWLIST_PATH", None),
            "cfg_cache": id(getattr(g6_config, "_IMAGE_ALLOWLIST_CACHE", None)),
        }

    before = snapshot()
    queries.list_images(conn, page_size=10, scope=scoped_for("proj-A", allowlist=ALLOW_5))
    scope_mod.resolve_prediction_rows(conn, scoped_for("proj-B"))
    queries.export_rows(conn, scope=scoped_for("proj-A", allowlist=ALLOW_5))
    assert before == snapshot(), "a read mutated process-global allowlist state"


def test_step07_allowlist_of_one_is_not_widened_by_the_others(two_models):
    """A narrow scope and a wide scope over the same project are independent."""
    _paths, conn = two_models
    wide = queries.list_images(
        conn, page_size=500, scope=scoped_for(projects.DEFAULT_PROJECT_ID)
    )
    narrow = queries.list_images(
        conn,
        page_size=500,
        scope=scoped_for(projects.DEFAULT_PROJECT_ID, allowlist=ALLOW_5),
    )
    assert narrow["total"] == 5
    assert wide["total"] == len(SEED_IDS)
    assert {i["image_id"] for i in narrow["items"]} == set(ALLOW_5)
    # Narrow ranks are recomputed for the narrow set, not sliced from the wide one.
    assert sorted(i["review_priority_rank"] for i in narrow["items"]) == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Boundary and failure review
# ---------------------------------------------------------------------------


def test_boundary_no_rows_at_all(tmp_path):
    """An empty store returns an empty authorized result, not an error."""
    conn = db.connect(tmp_path / "none.sqlite3")
    db.run_migrations(conn)
    try:
        sc = scope_mod.ScopeContext(
            project_id=projects.DEFAULT_PROJECT_ID,
            dataset_version_id="test-fixture-dataset",
            dataset_image_ids=frozenset(),
            model_bundle_hash=FIXTURE_MODEL_HASH,
        )
        assert scope_mod.resolve_prediction_rows(conn, sc) == []
        res = queries.list_images(conn, page_size=10, scope=sc)
        assert res == {
            "total": 0,
            "page": 1,
            "page_size": 10,
            "sort": "priority",
            "filter": "all",
            "query": "",
            "items": [],
        }
        assert queries.export_rows(conn, scope=sc) == []
        assert queries.get_image(conn, "anything", scope=sc) is None
    finally:
        conn.close()


def test_boundary_one_row(two_models):
    _paths, conn = two_models
    single = scoped_for(projects.DEFAULT_PROJECT_ID, dataset_ids=frozenset({"fx-01"}))
    rows = scope_mod.resolve_prediction_rows(conn, single)
    assert len(rows) == 1 and rows[0].image_id == "fx-01"
    res = queries.list_images(conn, page_size=50, scope=single)
    assert res["total"] == 1
    assert res["items"][0]["review_priority_rank"] == 1


def test_boundary_image_without_prediction_is_reported_as_null(two_models):
    """A selected row with no prediction for this model keeps its identity and
    reports a null prediction plus a reason - never a zero score, and never the
    other model's prediction."""
    _paths, conn = two_models
    conn.execute("DELETE FROM prediction WHERE image_id = ?", ("fx-02",))
    conn.commit()
    rows = scope_mod.resolve_prediction_rows(
        conn, scoped_for(projects.DEFAULT_PROJECT_ID)
    )
    by_id = {r.image_id: r for r in rows}
    assert len(by_id) == len(SEED_IDS)
    assert by_id["fx-02"].prediction_id is None
    assert by_id["fx-02"].unavailable_reason is not None
    res = queries.list_images(
        conn, page_size=500, scope=scoped_for(projects.DEFAULT_PROJECT_ID)
    )
    assert res["total"] == len(SEED_IDS)
    fx2 = next(i for i in res["items"] if i["image_id"] == "fx-02")
    assert fx2["prediction"] is None
    assert fx2["review_priority_rank"] is None


def test_boundary_paging_is_stable_across_pages(two_models):
    _paths, conn = two_models
    sc = scoped_for(projects.DEFAULT_PROJECT_ID)
    first = queries.list_images(conn, page=1, page_size=3, sort="image_id", scope=sc)
    second = queries.list_images(conn, page=2, page_size=3, sort="image_id", scope=sc)
    assert first["total"] == second["total"] == len(SEED_IDS)
    seen = [i["image_id"] for i in first["items"]]
    seen += [i["image_id"] for i in second["items"]]
    assert seen == SEED_IDS[:6]
    assert len(set(seen)) == len(seen)


def test_boundary_scope_and_project_argument_cannot_disagree(two_models):
    """Fail closed: an ambiguous double-specified scope is an error."""
    _paths, conn = two_models
    sc = scoped_for("proj-A")
    with pytest.raises(ValueError):
        queries.list_images(conn, page_size=10, scope=sc, project_id="proj-B")
