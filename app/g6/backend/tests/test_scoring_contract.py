"""Scoring math, frozen-contract, and prediction-dedup tests."""
from __future__ import annotations

import math

import pytest

from osteopatch import config, repo, scoring


def test_canonical_class_order_frozen():
    assert config.CANONICAL_CLASSES == ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")
    assert config.CLASS_TO_IDX == {"NON_TUMOR": 0, "VIABLE_TUMOR": 1, "NECROSIS": 2}


def test_exactly_three_outputs_no_fourth_class():
    assert len(config.CANONICAL_CLASSES) == 3
    assert "MIXED_VIABLE_NECROTIC" not in config.CANONICAL_CLASSES
    assert "MIXED" not in config.CANONICAL_CLASSES


def test_scores_three_finite_sum_to_one():
    s = scoring.summarize([0.2, 0.3, 0.5])
    assert len(s.scores) == 3
    assert all(math.isfinite(v) for v in s.scores.values())
    assert abs(sum(s.scores.values()) - 1.0) < 1e-9


def test_top_two_margin_and_predicted_class():
    s = scoring.summarize([0.7, 0.2, 0.1])
    assert s.predicted_class == "NON_TUMOR"
    assert abs(s.top_two_margin - 0.5) < 1e-9
    assert abs(s.top1_score - 0.7) < 1e-9


def test_normalized_entropy_bounds():
    # uniform -> entropy 1.0
    flat = scoring.normalized_entropy([1 / 3, 1 / 3, 1 / 3])
    assert abs(flat - 1.0) < 1e-9
    # one-hot -> entropy 0.0
    peak = scoring.normalized_entropy([1.0, 0.0, 0.0])
    assert abs(peak - 0.0) < 1e-9


def test_review_priority_deterministic_margin_then_entropy_then_id():
    # smaller margin first
    k_small = scoring.review_priority_key(0.01, 0.5, "b")
    k_big = scoring.review_priority_key(0.5, 0.9, "a")
    assert k_small < k_big
    # equal margin -> higher entropy first
    k_hi = scoring.review_priority_key(0.1, 0.9, "z")
    k_lo = scoring.review_priority_key(0.1, 0.2, "a")
    assert k_hi < k_lo
    # equal margin + entropy -> stable image_id
    k_a = scoring.review_priority_key(0.1, 0.5, "a")
    k_b = scoring.review_priority_key(0.1, 0.5, "b")
    assert k_a < k_b


def test_prediction_dedup_by_image_and_bundle(conn):
    pid1, created1 = repo.upsert_prediction(
        conn, "img-clear-nt", "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63",
        "baseline-frozen-g4", [0.9, 0.05, 0.05],
    )
    assert created1 is False  # already seeded in fixture
    # same (image, hash) -> same id, still no new row
    pid2, created2 = repo.upsert_prediction(
        conn, "img-clear-nt", "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63",
        "baseline-frozen-g4", [0.9, 0.05, 0.05],
    )
    assert pid1 == pid2 and created2 is False
    n = conn.execute(
        "SELECT COUNT(*) FROM prediction WHERE image_id='img-clear-nt'"
    ).fetchone()[0]
    assert n == 1


def test_metadata_is_not_a_model_class(conn):
    # the QC-review / ineligible row keeps MIXED as source metadata, but its
    # PREDICTION is still one of the 3 canonical classes
    row = conn.execute(
        "SELECT original_label, predicted_class FROM source_qc s "
        "JOIN prediction p ON p.image_id = s.image_id WHERE s.image_id='img-qc-review'"
    ).fetchone()
    assert row["original_label"] == "MIXED_VIABLE_NECROTIC"
    assert row["predicted_class"] in config.CANONICAL_CLASSES


# ---------------------------------------------------------------------------
# Hardening: scoring edge cases (defensive guards, no behavior change for valid
# 3-class softmax inputs).
# ---------------------------------------------------------------------------
def test_top1_index_empty_raises():
    with pytest.raises(ValueError):
        scoring.top1_index([])


def test_top_two_margin_requires_two_scores():
    with pytest.raises(ValueError):
        scoring.top_two_margin([0.9])


def test_normalized_entropy_single_score_is_zero_not_divzero():
    # n=1 would make log(n)=0 -> division by zero; guarded to 0.0 instead.
    assert scoring.normalized_entropy([1.0]) == 0.0


def test_normalized_entropy_all_zero_is_zero():
    assert scoring.normalized_entropy([0.0, 0.0, 0.0]) == 0.0


def test_normalized_entropy_negative_scores_clamped():
    # a stray negative must not corrupt the normalization; clamped to 0.
    v = scoring.normalized_entropy([-0.5, 0.5, 0.5])
    assert 0.0 <= v <= 1.0


def test_summarize_rejects_wrong_arity():
    with pytest.raises(ValueError):
        scoring.summarize([0.5, 0.5])


def test_summarize_rejects_non_finite():
    with pytest.raises(ValueError):
        scoring.summarize([float("nan"), 0.5, 0.5])
    with pytest.raises(ValueError):
        scoring.summarize([float("inf"), 0.5, 0.5])
