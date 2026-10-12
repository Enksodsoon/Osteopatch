"""F002 — contract tests for the deterministic review fixture.

Acceptance IDs map 1:1 to the task's named checks (F002-AT01..AT05).

The hand-check numbers encoded here (total=8, decided=3, deferred=2,
unreviewed=3, corrected=1, disagreement=1, completion=3/8, agreement=2/3,
correction=1/3, defer fraction=2/5) are TEST VALUES. They are never
production dashboard constants and never a claim about real tissue.

These tests build every database under pytest's ``tmp_path``. They never open
``config.DB_PATH`` or any other canonical store for writing.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest
from fixtures.review_fixture import (
    EXPECTED_DEFAULT,
    FIXTURE_MODEL_HASH,
    VARIANTS,
    add_superseded_event,
    canonical_db_sha256,
    counts_from,
    latest_states,
    make_review_fixture,
)


# --- F002-AT01 -------------------------------------------------------------
def test_F002_AT01_default_fixture_has_eight_unique_images_and_expected_statuses(tmp_path):
    """Default fixture: 8 unique ids; 3 decided / 2 deferred / 3 unreviewed."""
    fx = make_review_fixture(tmp_path / "fx")

    image_ids = sorted(r[0] for r in _connect(fx.db_path).execute("SELECT image_id FROM source_qc"))
    assert len(image_ids) == 8, image_ids
    assert len(set(image_ids)) == 8, "image ids must be unique"

    states = latest_states(_connect(fx.db_path))
    by_status = {"reviewed": 0, "deferred": 0, "unreviewed": 0}
    for st in states.values():
        by_status[st["status"]] += 1

    assert by_status == {"reviewed": 3, "deferred": 2, "unreviewed": 3}, by_status

    counts = counts_from(_connect(fx.db_path))
    assert counts["total_images"] == EXPECTED_DEFAULT["counts"]["total_images"] == 8
    assert counts["decided_images"] == 3
    assert counts["deferred_images"] == 2
    assert counts["unreviewed_images"] == 3
    assert counts["touched_images"] == 5
    assert counts["corrected_images"] == 1
    assert counts["disagreement_images"] == 1


def test_F002_AT01_expected_snapshot_file_matches_the_contract(tmp_path):
    """The fixture ships its own expected snapshot; it must equal the contract."""
    fx = make_review_fixture(tmp_path / "fx")
    written = json.loads(fx.expected_snapshot_path.read_text(encoding="utf-8"))

    assert written["definitions_version"] == "review-v1"
    assert written["counts"] == EXPECTED_DEFAULT["counts"]
    assert written["rates"] == EXPECTED_DEFAULT["rates"]


def test_F002_AT01_rates_are_the_hand_checked_fractions(tmp_path):
    fx = make_review_fixture(tmp_path / "fx")
    rates = counts_from(_connect(fx.db_path))["rates"]

    assert rates["review_completion"]["value"] == pytest.approx(3 / 8)
    assert rates["review_completion"]["numerator"] == 3
    assert rates["review_completion"]["denominator"] == 8
    assert rates["reviewer_agreement"]["value"] == pytest.approx(2 / 3)
    assert rates["correction_action_rate"]["value"] == pytest.approx(1 / 3)
    assert rates["defer_fraction"]["value"] == pytest.approx(2 / 5)


def test_F002_AT01_exactly_three_canonical_classes_and_three_actions(tmp_path):
    """Mixed/deferred stay metadata; they never become a fourth model class."""
    from osteopatch import config

    assert config.CANONICAL_CLASSES == ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")
    assert config.REVIEW_ACTIONS == ("ACCEPT", "CORRECT", "DEFER")

    conn = _connect((make_review_fixture(tmp_path / "fx")).db_path)
    classes = {r[0] for r in conn.execute("SELECT DISTINCT predicted_class FROM prediction")}
    assert classes <= set(config.CANONICAL_CLASSES)
    assert len(classes) == 3, "all three fixed classes must appear in the fixture"


# --- F002-AT02 -------------------------------------------------------------
def test_F002_AT02_superseded_event_changes_event_count_not_latest_state(tmp_path):
    """Appending an OLD event raises the event count; latest-state counts hold."""
    fx = make_review_fixture(tmp_path / "fx")
    conn = _connect(fx.db_path)

    events_before = _event_count(conn)
    counts_before = counts_from(conn)

    add_superseded_event(
        conn,
        image_id="fx-01",
        action="DEFER",
        reason="mixed_tissue",
        revision_number=0,  # older than the existing latest
    )
    events_after = _event_count(conn)
    counts_after = counts_from(conn)

    assert events_after == events_before + 1, "event count must grow"
    assert counts_after == counts_before, "latest-state counts must be unchanged"


def test_F002_AT02_default_fixture_already_carries_one_superseded_event(tmp_path):
    """fx-01 holds DEFER(rev 1) superseded by ACCEPT(rev 2); state is 'reviewed'."""
    conn = _connect((make_review_fixture(tmp_path / "fx")).db_path)

    history = [
        (r["revision_number"], r["action"])
        for r in conn.execute(
            "SELECT revision_number, action FROM review_event "
            "WHERE image_id = 'fx-01' ORDER BY revision_number"
        )
    ]
    assert history == [(1, "DEFER"), (2, "ACCEPT")], history

    states = latest_states(conn)
    assert states["fx-01"]["status"] == "reviewed"
    assert states["fx-01"]["action"] == "ACCEPT"


def test_F002_AT02_event_rows_are_append_only(tmp_path):
    """Superseding never mutates or deletes the older event."""
    fx = make_review_fixture(tmp_path / "fx")
    conn = _connect(fx.db_path)

    before = [
        (r["review_event_id"], r["revision_number"], r["action"])
        for r in conn.execute(
            "SELECT review_event_id, revision_number, action FROM review_event "
            "WHERE image_id = 'fx-01' ORDER BY revision_number"
        )
    ]
    add_superseded_event(conn, image_id="fx-01", action="DEFER", reason="other", revision_number=0)
    after = [
        (r["review_event_id"], r["revision_number"], r["action"])
        for r in conn.execute(
            "SELECT review_event_id, revision_number, action FROM review_event "
            "WHERE image_id = 'fx-01' AND revision_number IN (1, 2) ORDER BY revision_number"
        )
    ]
    assert after == before


# --- F002-AT03 -------------------------------------------------------------
def test_F002_AT03_second_model_does_not_double_the_selected_image_count(tmp_path):
    """A second bundle hash on the same images leaves the selected count at 8."""
    single = make_review_fixture(tmp_path / "single")
    multi = make_review_fixture(tmp_path / "multi", variant="two_models")

    conn_multi = _connect(multi.db_path)
    total_rows = conn_multi.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    selected_rows = conn_multi.execute(
        "SELECT COUNT(*) FROM prediction WHERE model_bundle_hash = ?", (FIXTURE_MODEL_HASH,)
    ).fetchone()[0]
    selected_images = counts_from(conn_multi, model_bundle_hash=FIXTURE_MODEL_HASH)["total_images"]

    assert total_rows == 16, "two models x eight images"
    assert selected_rows == 8
    assert selected_images == 8, "the selected model's image count must not double"

    assert counts_from(_connect(single.db_path))["total_images"] == 8


def test_F002_AT03_reviews_on_another_model_do_not_mark_the_selected_model_reviewed(tmp_path):
    """An event bound to another model's prediction stays out of this model's state."""
    conn = _connect((make_review_fixture(tmp_path / "multi", variant="two_models")).db_path)
    other_hash = _other_model_hash(conn)
    other_pred = conn.execute(
        "SELECT prediction_id FROM prediction WHERE model_bundle_hash = ? AND image_id = 'fx-06'",
        (other_hash,),
    ).fetchone()["prediction_id"]

    from osteopatch import repo

    repo.submit_review(
        conn,
        image_id="fx-06",
        prediction_id=other_pred,
        action="ACCEPT",
        expected_revision=0,
        idempotency_key="fx-other-model-accept",
    )
    states = latest_states(conn, model_bundle_hash=FIXTURE_MODEL_HASH)
    assert states["fx-06"]["status"] == "unreviewed", (
        "a review of another model's prediction must not decide the selected model"
    )


# --- F002-AT04 -------------------------------------------------------------
def test_F002_AT04_build_is_repeatable_across_two_independent_roots(tmp_path):
    """Same inputs -> same seeded content, in unrelated directories."""
    a = make_review_fixture(tmp_path / "a")
    b = make_review_fixture(tmp_path / "b")

    assert _connect(a.db_path).execute(
        "SELECT COUNT(*) FROM source_qc"
    ).fetchone()[0] == _connect(b.db_path).execute("SELECT COUNT(*) FROM source_qc").fetchone()[0]
    assert counts_from(_connect(a.db_path)) == counts_from(_connect(b.db_path))
    assert a.expected_snapshot_path.read_text(encoding="utf-8") == (
        b.expected_snapshot_path.read_text(encoding="utf-8")
    )
    assert a.image_root != b.image_root


def test_F002_AT04_does_not_import_torch_or_touch_the_network(tmp_path, monkeypatch):
    """The fixture is a plain SQLite/PNG builder: no torch, no sockets."""
    import builtins
    import socket

    import fixtures.review_fixture as rf

    monkeypatch.delitem(
        __import__("sys").modules, "torch", raising=False
    )

    real_socket = socket.socket

    def _no_network(*args, **kwargs):
        raise AssertionError("fixture must not open a socket")

    monkeypatch.setattr(socket, "socket", _no_network)

    real_import = builtins.__import__

    def _tracking_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise AssertionError("fixture must not import torch")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _tracking_import)
    assert rf.torch is None

    fx = make_review_fixture(tmp_path / "offline")
    assert counts_from(_connect(fx.db_path))["total_images"] == 8

    monkeypatch.setattr(socket, "socket", real_socket)


def test_F002_AT04_generated_pixels_are_labelled_test_fixture(tmp_path):
    """Synthetic pixels must never be presented as real H&E."""
    fx = make_review_fixture(tmp_path / "pix")
    for png in sorted(fx.image_root.glob("*.png")):
        assert png.name.startswith("TEST_FIXTURE-"), png.name

    manifest = json.loads(fx.expected_snapshot_path.read_text(encoding="utf-8"))
    assert manifest["data_mode"] == "synthetic_fixture"
    assert "not real H&E" in manifest["disclaimer"]


# --- F002-AT05 -------------------------------------------------------------
def test_F002_AT05_destroying_the_fixture_dir_leaves_source_runtime_data(tmp_path):
    """Removing the fixture tree must not touch canonical runtime artifacts."""
    import shutil

    before = canonical_db_sha256()

    fx = make_review_fixture(tmp_path / "doomed")
    assert fx.db_path.exists()
    assert any(fx.image_root.iterdir())

    shutil.rmtree(fx.root)

    assert not fx.root.exists()
    assert not fx.db_path.exists()
    assert not fx.image_root.exists()

    after = canonical_db_sha256()
    assert before == after, "canonical runtime data changed when the fixture was destroyed"


def test_F002_AT05_canonical_hash_helper_refuses_a_missing_store(tmp_path):
    """Absent data is null plus a reason, never a silent zero."""
    from osteopatch import config

    original = config.DB_PATH
    try:
        config.DB_PATH = tmp_path / "nope" / "absent.sqlite3"
        digest = canonical_db_sha256()
        assert digest is None, "a missing canonical store must report None, not a fake hash"
    finally:
        config.DB_PATH = original


# --- boundary / failure review --------------------------------------------
@pytest.mark.parametrize("variant", sorted(VARIANTS))
def test_boundary_every_declared_variant_builds(tmp_path, variant):
    """Each declared variant must build deterministically and report a scope."""
    fx = make_review_fixture(tmp_path / variant, variant=variant)
    manifest = json.loads(fx.expected_snapshot_path.read_text(encoding="utf-8"))
    assert "counts" in manifest and "scope" in manifest
    assert fx.db_path.exists()


def test_boundary_no_rows_variant_has_null_not_zero_rates(tmp_path):
    """Zero images: every rate is null WITH a reason, never a bare 0.0."""
    fx = make_review_fixture(tmp_path / "empty", variant="empty")
    counts = counts_from(_connect(fx.db_path))
    assert counts["total_images"] == 0
    assert counts["rates"]["review_completion"]["value"] is None
    assert counts["rates"]["review_completion"]["denominator"] == 0
    assert counts["rates"]["review_completion"]["unavailable_reason"]


def test_boundary_predictionless_images_stay_visible_and_leave_denominators(tmp_path):
    """Images with no prediction are counted, but never enter agreement."""
    fx = make_review_fixture(tmp_path / "nopred", variant="no_predictions")
    counts = counts_from(_connect(fx.db_path))

    assert counts["total_images"] == 8, "predictionless images remain visible"
    assert counts["predictionless_images"] == 8
    assert counts["decided_images"] == 0
    assert counts["rates"]["reviewer_agreement"]["value"] is None
    assert counts["rates"]["reviewer_agreement"]["unavailable_reason"]
    # completion still has a real denominator: images exist
    assert counts["rates"]["review_completion"]["denominator"] == 8
    assert counts["rates"]["review_completion"]["value"] == pytest.approx(0.0)


def test_boundary_no_reviews_variant_counts_all_unreviewed(tmp_path):
    fx = make_review_fixture(tmp_path / "noreviews", variant="no_reviews")
    counts = counts_from(_connect(fx.db_path))
    assert counts["total_images"] == 8
    assert counts["unreviewed_images"] == 8
    assert counts["decided_images"] == 0
    assert counts["rates"]["reviewer_agreement"]["value"] is None


def test_boundary_corrupt_asset_is_reported_unavailable_not_silently_scored(tmp_path):
    fx = make_review_fixture(tmp_path / "corrupt", variant="corrupt_asset")
    manifest = json.loads(fx.expected_snapshot_path.read_text(encoding="utf-8"))
    assert manifest["warnings"], "a corrupt asset must raise a warning"
    assert any("corrupt" in w.lower() for w in manifest["warnings"])
    assert manifest["counts"]["predictionless_images"] == 1


def test_boundary_empty_project_variant_grants_no_images(tmp_path):
    fx = make_review_fixture(tmp_path / "emptyproj", variant="empty_project")
    counts = counts_from(_connect(fx.db_path), project_id="project-with-no-images")
    assert counts["total_images"] == 0


def test_boundary_fixture_never_uses_the_config_default_db_path(tmp_path, monkeypatch):
    """Step 07: an explicit temporary DB path, never config's canonical default."""
    from osteopatch import config

    sentinel = tmp_path / "must-not-be-created.sqlite3"
    original = config.DB_PATH
    try:
        config.DB_PATH = sentinel
        fx = make_review_fixture(tmp_path / "explicit")
        assert fx.db_path != sentinel
        assert sentinel.exists() is False, "the config default must not be created or written"
    finally:
        config.DB_PATH = original


def test_boundary_duplicate_retry_reuses_one_idempotency_key(tmp_path):
    """One logical submission keeps one idempotency key across retries."""
    from osteopatch import repo

    fx = make_review_fixture(tmp_path / "retry")
    conn = _connect(fx.db_path)
    pred = conn.execute(
        "SELECT prediction_id FROM prediction WHERE image_id = 'fx-06'"
    ).fetchone()["prediction_id"]

    before = _event_count(conn)
    for _ in range(3):
        repo.submit_review(
            conn,
            image_id="fx-06",
            prediction_id=pred,
            action="ACCEPT",
            expected_revision=0,
            idempotency_key="fx-retry-key",
        )
    assert _event_count(conn) == before + 1, "a replayed submission must not append twice"


def test_boundary_missing_prediction_id_fails_loudly(tmp_path):
    """Malformed / unknown input raises a typed error, never a silent zero."""
    from osteopatch import repo

    conn = _connect((make_review_fixture(tmp_path / "bad")).db_path)
    with pytest.raises(repo.NotFoundError):
        repo.submit_review(
            conn,
            image_id="fx-06",
            prediction_id="pred-does-not-exist",
            action="ACCEPT",
            expected_revision=0,
            idempotency_key="fx-bad",
        )


def test_boundary_selected_class_that_matches_prediction_is_not_a_disagreement(tmp_path):
    """ACCEPT resolves to the predicted class; it can never disagree."""

    conn = _connect((make_review_fixture(tmp_path / "agree")).db_path)
    states = latest_states(conn)
    for image_id in ("fx-01", "fx-02"):
        assert states[image_id]["action"] == "ACCEPT"
        assert states[image_id]["effective_label"] == states[image_id]["predicted_class"]
    assert states["fx-03"]["action"] == "CORRECT"
    assert states["fx-03"]["effective_label"] != states["fx-03"]["predicted_class"]


def test_boundary_counts_are_images_not_prediction_rows(tmp_path):
    """Prediction counts must never exceed the image count, in either mode.

    Regression guard: the first implementation seeded prediction_images from the
    total when no model was selected AND then counted rows again, reporting 16
    predictions for 8 images on the two_models fixture.
    """
    fx = make_review_fixture(tmp_path / "rows", variant="two_models")
    conn = _connect(fx.db_path)
    rows = conn.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    assert rows == 16, "two models x eight images"

    for label, model_hash in (("selected", FIXTURE_MODEL_HASH), ("any model", None)):
        counts = counts_from(conn, model_bundle_hash=model_hash)
        assert counts["prediction_images"] == 8, label
        assert counts["predictionless_images"] == 0, label
        assert counts["total_images"] == 8, label
        assert counts["prediction_images"] <= counts["total_images"], label


# --- helpers ---------------------------------------------------------------
def _connect(db_path):
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _event_count(conn) -> int:
    return conn.execute("SELECT COUNT(*) FROM review_event").fetchone()[0]


def _other_model_hash(conn) -> str:
    row = conn.execute(
        "SELECT model_bundle_hash FROM prediction WHERE model_bundle_hash != ? LIMIT 1",
        (FIXTURE_MODEL_HASH,),
    ).fetchone()
    return row["model_bundle_hash"]


def sha256_of(path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()