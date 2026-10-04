"""Review-safety tests: validation, append-only, idempotency, concurrency,
immutability."""
from __future__ import annotations

import pytest

from osteopatch import repo

HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"


def _pid(image_id):
    return repo.prediction_id_for(image_id, HASH)


def test_accept_creates_event(conn):
    ev, created = repo.submit_review(
        conn, "img-clear-nt", _pid("img-clear-nt"), "ACCEPT",
        expected_revision=0, idempotency_key="k1",
    )
    assert created and ev["action"] == "ACCEPT" and ev["revision_number"] == 1


def test_correct_requires_valid_class(conn):
    with pytest.raises(repo.ValidationError):
        repo.submit_review(
            conn, "img-ambiguous", _pid("img-ambiguous"), "CORRECT",
            expected_revision=0, idempotency_key="k2", selected_label="BONE",
        )
    with pytest.raises(repo.ValidationError):
        repo.submit_review(
            conn, "img-ambiguous", _pid("img-ambiguous"), "CORRECT",
            expected_revision=0, idempotency_key="k2b", selected_label=None,
        )


def test_correct_with_valid_class(conn):
    ev, created = repo.submit_review(
        conn, "img-ambiguous", _pid("img-ambiguous"), "CORRECT",
        expected_revision=0, idempotency_key="k3", selected_label="NECROSIS",
    )
    assert created and ev["selected_class"] == "NECROSIS"


def test_accept_cannot_contradict_prediction(conn):
    # img-clear-nt predicted NON_TUMOR; ACCEPT with a different label is invalid
    with pytest.raises(repo.ValidationError):
        repo.submit_review(
            conn, "img-clear-nt", _pid("img-clear-nt"), "ACCEPT",
            expected_revision=0, idempotency_key="k4", selected_label="NECROSIS",
        )


def test_defer_must_not_carry_class(conn):
    with pytest.raises(repo.ValidationError):
        repo.submit_review(
            conn, "img-mid-nec", _pid("img-mid-nec"), "DEFER",
            expected_revision=0, idempotency_key="k5", selected_label="NECROSIS",
        )
    ev, created = repo.submit_review(
        conn, "img-mid-nec", _pid("img-mid-nec"), "DEFER",
        expected_revision=0, idempotency_key="k5b", reason="mixed_tissue",
    )
    assert created and ev["action"] == "DEFER" and ev["selected_class"] is None


def test_defer_invalid_reason_rejected(conn):
    with pytest.raises(repo.ValidationError):
        repo.submit_review(
            conn, "img-mid-nec", _pid("img-mid-nec"), "DEFER",
            expected_revision=0, idempotency_key="k5c", reason="banana",
        )


def test_append_only_history_grows(conn):
    repo.submit_review(conn, "img-ambiguous", _pid("img-ambiguous"), "ACCEPT",
                       expected_revision=0, idempotency_key="a1")
    repo.submit_review(conn, "img-ambiguous", _pid("img-ambiguous"), "CORRECT",
                       expected_revision=1, idempotency_key="a2", selected_label="VIABLE_TUMOR")
    hist = repo.event_history(conn, "img-ambiguous")
    assert [e["revision_number"] for e in hist] == [1, 2]
    assert [e["action"] for e in hist] == ["ACCEPT", "CORRECT"]


def test_idempotent_replay_returns_original(conn):
    ev1, c1 = repo.submit_review(conn, "img-clear-nt", _pid("img-clear-nt"), "ACCEPT",
                                 expected_revision=0, idempotency_key="dup")
    ev2, c2 = repo.submit_review(conn, "img-clear-nt", _pid("img-clear-nt"), "ACCEPT",
                                 expected_revision=0, idempotency_key="dup")
    assert c1 is True and c2 is False
    assert ev1["review_event_id"] == ev2["review_event_id"]
    n = conn.execute("SELECT COUNT(*) FROM review_event WHERE image_id='img-clear-nt'").fetchone()[0]
    assert n == 1


def test_stale_revision_conflict_409(conn):
    repo.submit_review(conn, "img-mid-nec", _pid("img-mid-nec"), "ACCEPT",
                       expected_revision=0, idempotency_key="r1")
    with pytest.raises(repo.ConflictError):
        # current revision is now 1, but we claim 0 -> stale
        repo.submit_review(conn, "img-mid-nec", _pid("img-mid-nec"), "CORRECT",
                           expected_revision=0, idempotency_key="r2", selected_label="VIABLE_TUMOR")


def test_unknown_image_and_prediction_404(conn):
    with pytest.raises(repo.NotFoundError):
        repo.submit_review(conn, "nope", _pid("img-clear-nt"), "ACCEPT",
                           expected_revision=0, idempotency_key="x1")
    with pytest.raises(repo.NotFoundError):
        repo.submit_review(conn, "img-clear-nt", "pred-does-not-exist", "ACCEPT",
                           expected_revision=0, idempotency_key="x2")


def test_prediction_mismatch_422(conn):
    # prediction belongs to a DIFFERENT image
    with pytest.raises(repo.ValidationError):
        repo.submit_review(conn, "img-clear-nt", _pid("img-ambiguous"), "ACCEPT",
                           expected_revision=0, idempotency_key="x3")


def test_prediction_immutable_after_correction(conn):
    before = dict(repo.get_prediction(conn, _pid("img-ambiguous")))
    repo.submit_review(conn, "img-ambiguous", _pid("img-ambiguous"), "CORRECT",
                       expected_revision=0, idempotency_key="imm", selected_label="NON_TUMOR")
    after = dict(repo.get_prediction(conn, _pid("img-ambiguous")))
    assert before == after  # the prediction row is byte-for-byte unchanged
    assert after["predicted_class"] == "VIABLE_TUMOR"  # original model call stands
