"""Real G4 bundle tests — SKIPPED when torch or the bundle is unavailable.

These exercise the frozen-contract guard against the ACTUAL bundle: hash
verification, 3-output model load, preprocessing taken from the bundle spec, and
3 finite scores that sum to 1. Run them under the torch-enabled venv.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from osteopatch import config, model

torch = pytest.importorskip("torch", reason="torch not installed in this venv")

_bundle_missing = not config.BUNDLE_PATH.exists()
pytestmark = pytest.mark.skipif(_bundle_missing, reason="G4 bundle not present")


def test_real_bundle_hash_matches():
    assert model.verify_bundle_hash() == config.EXPECTED_BUNDLE_SHA256


def test_hash_mismatch_refuses(tmp_path):
    fake = tmp_path / "fake.pt"
    fake.write_bytes(b"not the real bundle")
    with pytest.raises(model.BundleHashMismatch):
        model.verify_bundle_hash(fake)


def test_real_model_loads_three_outputs_and_canonical_order():
    loaded = model.load_model()
    assert loaded.classes == list(config.CANONICAL_CLASSES)
    assert loaded.bundle_hash == config.EXPECTED_BUNDLE_SHA256


def test_real_inference_three_finite_scores_sum_to_one():
    loaded = model.load_model()
    # find any decoded TIFF to run through
    tiffs = sorted(config.TIFFS_DIR.glob("*.tiff"))
    if not tiffs:
        pytest.skip("no decoded TIFFs present")
    scores = model.infer_scores(loaded, tiffs[0])
    assert len(scores) == 3
    assert all(s == s and abs(s) != float("inf") for s in scores)  # finite
    assert abs(sum(scores) - 1.0) < 1e-5
    assert all(s >= 0 for s in scores)


def test_preprocessing_matches_bundle_spec():
    loaded = model.load_model()
    pp = loaded.config["preprocessing"]
    assert pp["resize"] == [384, 384]
    assert pp["normalize_mean"] == [0.485, 0.456, 0.406]
    assert pp["normalize_std"] == [0.229, 0.224, 0.225]
    assert pp["antialias"] is True
