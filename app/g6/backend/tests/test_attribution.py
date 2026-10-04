"""G7 attribution tests — contrastive Grad-CAM over the recovered head.

Two tiers:
  * torch-FREE logic tests (endpoint wiring, default pair, class validation,
    cache-key composition, DB/review immutability around an attribution call) —
    run under the backend .venv.
  * torch-GATED tests (real model load, live CAM dims/finiteness, contrastive
    A-B vs B-A distinctness, model-state stability, gauge_invariance_check on a
    durable TIFF) — run under the torch venv; skipped (not failed) when torch
    is absent, per the "No module named X from the wrong venv is not a defect"
    rule.

These exercise the DURABLE runtime artifacts (recovered model + durable TIFFs)
via environment variables so nothing points at reclaimable scratch.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from osteopatch import config, repo

HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"

PROJECT_ROOT = Path(
    os.environ.get("OSTEOPATCH_PROJECT_ROOT", str(Path(__file__).resolve().parents[4]))
)
DURABLE_IMAGES = Path(
    os.environ.get("OSTEOPATCH_ATTRIB_IMAGES", str(PROJECT_ROOT / "runtime-artifacts" / "images"))
)
RECOVERED_MODEL = Path(
    os.environ.get(
        "OSTEOPATCH_RECOVERED_MODEL",
        str(PROJECT_ROOT / "runtime-artifacts" / "models" / "g4-behavioral-recovery-r1.pt"),
    )
)

try:
    import torch  # noqa: F401
    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False

torch_only = pytest.mark.skipif(
    not HAVE_TORCH, reason="torch not installed in this venv (run under torch venv)"
)


def _first_durable_tiff() -> Path | None:
    if not DURABLE_IMAGES.exists():
        return None
    for p in sorted(DURABLE_IMAGES.glob("*.tiff")):
        return p
    return None


# ---------------------------------------------------------------------------
# torch-FREE logic / wiring tests
# ---------------------------------------------------------------------------
def test_default_pair_is_predicted_vs_runner_up():
    from osteopatch import app as app_module
    row = {
        "non_tumor_score": 0.33, "viable_tumor_score": 0.34, "necrosis_score": 0.33,
        "predicted_class": "VIABLE_TUMOR",
    }
    a, b = app_module._default_pair_for(row)
    assert a == "VIABLE_TUMOR"
    assert b in ("NON_TUMOR", "NECROSIS")
    assert a != b


def test_meta_reports_attribution_enabled_and_six_pairs(client):
    m = client.get("/v1/meta").json()
    assert m["attribution_enabled"] is True
    assert m["g7_placeholder"] == ""
    pairs = m["attribution"]["pairs"]
    assert len(pairs) == 6
    seen = {(p["a"], p["b"]) for p in pairs}
    assert len(seen) == 6
    assert all(a != b for a, b in seen)
    assert "behaviorally reconstructed" in m["attribution"]["disclosure"]


def test_attribution_meta_endpoint_default_pair(client):
    r = client.get("/v1/images/img-mid-nec/attribution/meta")
    assert r.status_code == 200
    j = r.json()
    assert j["attribution_enabled"] is True
    assert j["predicted_class"] == "NECROSIS"
    assert j["default_pair"] == {"a": "NECROSIS", "b": "VIABLE_TUMOR"}
    assert j["source_prediction_model"] == "baseline-frozen-g4"
    assert j["recovered_model_id"] == "g4-behavioral-recovery-r1"


def test_attribution_meta_unknown_image_404(client):
    assert client.get("/v1/images/nope/attribution/meta").status_code == 404


def test_attribution_invalid_class_400(client):
    r = client.get("/v1/images/img-mid-nec/attribution?target_a=BONE&target_b=NECROSIS")
    assert r.status_code == 400


def test_attribution_equal_pair_400(client):
    r = client.get("/v1/images/img-mid-nec/attribution?target_a=NECROSIS&target_b=NECROSIS")
    assert r.status_code == 400


def test_attribution_unknown_image_404(client):
    assert client.get("/v1/images/nope/attribution").status_code == 404


def test_attribution_call_does_not_mutate_prediction_or_review(client, conn):
    before_pred = dict(repo.get_prediction(conn, repo.prediction_id_for("img-mid-nec", HASH)))
    before_rev = conn.execute("SELECT COUNT(*) FROM review_event").fetchone()[0]
    client.get("/v1/images/img-mid-nec/attribution?target_a=NECROSIS&target_b=VIABLE_TUMOR")
    after_pred = dict(repo.get_prediction(conn, repo.prediction_id_for("img-mid-nec", HASH)))
    after_rev = conn.execute("SELECT COUNT(*) FROM review_event").fetchone()[0]
    assert before_pred == after_pred
    assert before_rev == after_rev


def test_cache_key_includes_image_model_pair_and_version():
    from osteopatch import attribution
    k_ab = attribution._cache_key("img-x", "VIABLE_TUMOR", "NECROSIS", "shaAAA")
    k_ba = attribution._cache_key("img-x", "NECROSIS", "VIABLE_TUMOR", "shaAAA")
    k_other_img = attribution._cache_key("img-y", "VIABLE_TUMOR", "NECROSIS", "shaAAA")
    k_other_model = attribution._cache_key("img-x", "VIABLE_TUMOR", "NECROSIS", "shaBBB")
    assert k_ab != k_ba
    assert k_ab != k_other_img
    assert k_ab != k_other_model


# ---------------------------------------------------------------------------
# torch-GATED tests (real recovered model + durable TIFF)
# ---------------------------------------------------------------------------
@torch_only
def test_recovered_model_loads_with_correct_identity():
    from osteopatch import attribution
    assert RECOVERED_MODEL.exists(), f"durable recovered model missing: {RECOVERED_MODEL}"
    st = attribution.get_state()
    assert st["target_layer_name"] == "model.features[-1]"
    assert st["gradcam_lib"] == "pytorch-grad-cam"
    assert st["bundle_sha256"] != config.EXPECTED_BUNDLE_SHA256


@torch_only
def test_model_identity_separation_constant():
    from osteopatch import attribution
    assert attribution.RECOVERED_MODEL_ID == "g4-behavioral-recovery-r1"
    assert attribution.RECOVERED_MODEL_ID != config.MODEL_VERSION


@torch_only
def test_live_contrastive_cam_finite_and_correct_dims():
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    assert tiff is not None, "no durable TIFF found"
    r = attribution.compute_attribution(tiff, tiff.stem, "VIABLE_TUMOR", "NECROSIS")
    assert tuple(r.meta["cam_shape"]) == (384, 384)
    assert r.meta["cam_finite"] is True
    assert r.meta["attribution_target"] == "raw logit_A - logit_B (contrastive)"
    assert r.meta["target_layer"] == "model.features[-1]"
    assert r.meta["recovered_model_id"] == "g4-behavioral-recovery-r1"
    assert r.meta["source_prediction_model"] == "baseline-frozen-g4"


@torch_only
def test_contrastive_order_matters_ab_vs_ba():
    import numpy as np
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    ab = attribution.compute_attribution(tiff, tiff.stem, "VIABLE_TUMOR", "NECROSIS").cam
    ba = attribution.compute_attribution(tiff, tiff.stem, "NECROSIS", "VIABLE_TUMOR").cam
    assert float(np.abs(ab - ba).max()) > 1e-3


@torch_only
def test_different_pair_is_not_the_same_cam():
    import numpy as np
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    p1 = attribution.compute_attribution(tiff, tiff.stem, "VIABLE_TUMOR", "NECROSIS").cam
    p2 = attribution.compute_attribution(tiff, tiff.stem, "NON_TUMOR", "NECROSIS").cam
    assert float(np.abs(p1 - p2).max()) > 1e-3


@torch_only
def test_model_state_stable_after_attribution():
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    st = attribution.get_state()
    w_before = st["model"].classifier[-1].weight.detach().clone()
    training_before = st["model"].training
    attribution.compute_attribution(tiff, tiff.stem, "NON_TUMOR", "VIABLE_TUMOR")
    st2 = attribution.get_state()
    assert st2["model"].training == training_before
    assert bool((st2["model"].classifier[-1].weight.detach() == w_before).all())


@torch_only
def test_invalid_class_raises_attribution_error():
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    with pytest.raises(attribution.AttributionError):
        attribution.compute_attribution(tiff, tiff.stem, "BONE", "NECROSIS")
    with pytest.raises(attribution.AttributionError):
        attribution.compute_attribution(tiff, tiff.stem, "NECROSIS", "NECROSIS")


@torch_only
def test_gauge_invariance_live_on_durable_tiff():
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    gi = attribution.gauge_invariance_check(tiff)
    assert gi["softmax_unchanged"] is True
    assert gi["argmax_unchanged"] is True
    assert gi["single_class_cam_can_change"] is True
    assert gi["contrastive_cam_invariant"] is True


@torch_only
def test_target_layer_validation_live():
    from osteopatch import attribution
    tiff = _first_durable_tiff()
    v = attribution.validate_target_layer(tiff)
    assert v["retains_spatial_dims"] is True
    assert tuple(v["feature_map_spatial"]) == (12, 12)
    assert v["cam_finite"] is True
    assert v["target_sensitivity_ok"] is True
