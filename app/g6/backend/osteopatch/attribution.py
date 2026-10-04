"""Contrastive Grad-CAM attribution for the behaviorally-recovered G4 head.

TORCH-GATED, ON-DEMAND. The main FastAPI serving path stays torch-free: torch /
pytorch-grad-cam are imported lazily only when an attribution is actually
requested. Predictions are never produced here (prediction state is immutable
and lives in the G6 DB); this module only explains an existing prediction.

Why CONTRASTIVE (logit_A - logit_B), not single-class:
  The recovered head is a zero-sum-gauge representative of the lost absolute
  head. A common-mode vector added to all three logits leaves softmax (and the
  A-B logit difference) unchanged but changes per-class gradients — so ordinary
  single-class Grad-CAM is NOT gauge-invariant and would not reproduce the
  original G4 single-class CAM. The pairwise logit difference IS gauge-invariant
  and is the only defensible attribution target here. Default pair =
  predicted class (A) vs runner-up (B).

Model identity:
  * recovered model `g4-behavioral-recovery-r1` (its own sha256)
  * source predictions attributed to the ORIGINAL `baseline-frozen-g4`
    (01727fb8...). Never conflated; never written back to the G6 DB.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config

# ---------------------------------------------------------------------------
# Recovered-model locations (durable; produced by R1-C2)
# ---------------------------------------------------------------------------
RECOVERED_BUNDLE = config.RECOVERED_MODEL_PATH
RECOVERED_MODEL_ID = "g4-behavioral-recovery-r1"
RECOVERY_RECORD_ID = "R1-C2"

_LOCK = threading.Lock()
_STATE: dict | None = None  # lazily-loaded torch state (model, cam target layer, meta)


class AttributionError(RuntimeError):
    """Honest failure — never a fabricated heatmap."""


# ---------------------------------------------------------------------------
# Lazy torch model build (frozen encoder + recovered head), full forward
# ---------------------------------------------------------------------------
def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _build_state() -> dict:
    import torch
    import torch.nn as nn
    from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights
    from torchvision.transforms import v2
    import torchvision

    if not RECOVERED_BUNDLE.exists():
        raise AttributionError(
            f"recovered model bundle missing: {RECOVERED_BUNDLE} (run R1-C2 recovery first)"
        )
    bundle = torch.load(str(RECOVERED_BUNDLE), map_location="cpu", weights_only=False)
    if bundle.get("model_id") != RECOVERED_MODEL_ID:
        raise AttributionError(f"unexpected recovered model_id: {bundle.get('model_id')}")
    if tuple(bundle["classes"]) != config.CANONICAL_CLASSES:
        raise AttributionError("recovered bundle class order != canonical")

    W = np.asarray(bundle["head_state_dict"]["weight"], dtype=np.float32)
    B = np.asarray(bundle["head_state_dict"]["bias"], dtype=np.float32)

    base = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1)
    base.eval()
    # Replace the final classifier linear with the recovered head.
    base.classifier[-1] = nn.Linear(1024, 3)
    with torch.no_grad():
        base.classifier[-1].weight.copy_(torch.tensor(W))
        base.classifier[-1].bias.copy_(torch.tensor(B))
    base.eval()
    for p in base.parameters():
        p.requires_grad_(True)  # grad-cam needs grads to flow to the target layer

    preproc = bundle["preprocessing"]
    interp = getattr(
        torchvision.transforms.InterpolationMode,
        str(preproc.get("interpolation", "bilinear")).upper(),
        torchvision.transforms.InterpolationMode.BILINEAR,
    )
    tf = v2.Compose([
        v2.ToImage(),
        v2.Resize((int(preproc["resize"][0]), int(preproc["resize"][1])),
                  interpolation=interp, antialias=bool(preproc.get("antialias", True))),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=list(preproc["normalize_mean"]), std=list(preproc["normalize_std"])),
    ])

    # Target layer: last spatial conv block of the feature extractor.
    target_layer = base.features[-1]

    return {
        "torch": torch,
        "model": base,
        "transform": tf,
        "target_layer": target_layer,
        "target_layer_name": "model.features[-1]",
        "bundle_sha256": _sha256_file(RECOVERED_BUNDLE),
        "preprocessing": preproc,
        "preprocessing_version": bundle.get("gauge", {}).get("definition", "zero-sum")[:0] or "r1c2-v1",
        "gradcam_lib": "pytorch-grad-cam",
        "gradcam_version": _gradcam_version(),
    }


def _gradcam_version() -> str:
    import importlib.metadata as md
    try:
        return md.version("grad-cam")
    except Exception:
        return "unknown"


def get_state() -> dict:
    global _STATE
    with _LOCK:
        if _STATE is None:
            _STATE = _build_state()
        return _STATE


# ---------------------------------------------------------------------------
# Contrastive target: raw (logit_A - logit_B) via a custom callable model target
# ---------------------------------------------------------------------------
def _contrastive_target(idx_a: int, idx_b: int):
    """pytorch-grad-cam target: scalar = logit_A - logit_B (RAW logits)."""
    def _fn(model_output):
        # model_output is the (3,) logit vector for one sample
        return model_output[idx_a] - model_output[idx_b]
    return _fn


# ---------------------------------------------------------------------------
# Core attribution
# ---------------------------------------------------------------------------
@dataclass
class AttributionResult:
    image_id: str
    target_a: str
    target_b: str
    cam: np.ndarray            # (H,W) float32 in [0,1]
    overlay_png: bytes
    heatmap_png: bytes
    meta: dict
    cache_key: str
    latency_ms: float
    cached: bool


def _softmax(logits: np.ndarray) -> np.ndarray:
    m = logits.max()
    e = np.exp(logits - m)
    return e / e.sum()


def compute_attribution(
    image_path: Path,
    image_id: str,
    target_a: str,
    target_b: str,
) -> AttributionResult:
    if target_a not in config.CLASS_TO_IDX or target_b not in config.CLASS_TO_IDX:
        raise AttributionError(f"invalid class(es): {target_a}, {target_b}")
    if target_a == target_b:
        raise AttributionError("target_a and target_b must differ")
    if not Path(image_path).exists():
        raise AttributionError(f"image not found: {image_path}")

    st = get_state()
    cache_key = _cache_key(image_id, target_a, target_b, st["bundle_sha256"])
    cache_png = config.ATTRIB_CACHE_DIR / f"{cache_key}.png"
    cache_meta = config.ATTRIB_CACHE_DIR / f"{cache_key}.json"
    cache_npy = config.ATTRIB_CACHE_DIR / f"{cache_key}.npy"

    if cache_png.exists() and cache_meta.exists() and cache_npy.exists():
        t0 = time.time()
        cam = np.load(cache_npy)
        meta = json.loads(cache_meta.read_text(encoding="utf-8"))
        overlay = cache_png.read_bytes()
        heat = (config.ATTRIB_CACHE_DIR / f"{cache_key}.heat.png").read_bytes()
        return AttributionResult(image_id, target_a, target_b, cam, overlay, heat,
                                 meta, cache_key, round((time.time() - t0) * 1000, 2), True)

    torch = st["torch"]
    from pytorch_grad_cam import GradCAM
    from PIL import Image

    t0 = time.time()
    idx_a = config.CLASS_TO_IDX[target_a]
    idx_b = config.CLASS_TO_IDX[target_b]

    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        input_tensor = st["transform"](rgb).unsqueeze(0)  # (1,3,384,384)
        rgb_384 = np.asarray(rgb.resize((384, 384))).astype(np.float32) / 255.0

    # prediction scores (float32) — for metadata ONLY; never written to DB
    with torch.no_grad():
        logits = st["model"](input_tensor)[0].numpy()
    probs = _softmax(logits)

    targets = [ _ClosureTarget(_contrastive_target(idx_a, idx_b)) ]
    with GradCAM(model=st["model"], target_layers=[st["target_layer"]]) as cam_engine:
        grayscale = cam_engine(input_tensor=input_tensor, targets=targets)[0]  # (384,384) in [0,1]
    cam = np.asarray(grayscale, dtype=np.float32)

    overlay_png, heatmap_png = _render(rgb_384, cam)

    meta = {
        "image_id": image_id,
        "recovered_model_id": RECOVERED_MODEL_ID,
        "recovered_model_sha256": st["bundle_sha256"],
        "source_prediction_model": "baseline-frozen-g4",
        "source_prediction_bundle_sha256": config.EXPECTED_BUNDLE_SHA256,
        "recovery_record_id": RECOVERY_RECORD_ID,
        "target_class_a": target_a,
        "comparator_b": target_b,
        "attribution_target": "raw logit_A - logit_B (contrastive)",
        "target_layer": st["target_layer_name"],
        "gradcam_lib": st["gradcam_lib"],
        "gradcam_version": st["gradcam_version"],
        "preprocessing_version": st["preprocessing_version"],
        "cam_shape": list(cam.shape),
        "cam_finite": bool(np.isfinite(cam).all()),
        "cam_min": float(cam.min()),
        "cam_max": float(cam.max()),
        "model_logits": {config.IDX_TO_CLASS[i]: float(logits[i]) for i in range(3)},
        "model_scores_for_reference": {config.IDX_TO_CLASS[i]: float(probs[i]) for i in range(3)},
        "cache_key": cache_key,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "note": "Attribution over a behaviorally-reconstructed classifier; prediction behavior verified against the original stored model outputs. Not tissue segmentation or diagnostic annotation.",
    }

    # deterministic cache write
    config.ATTRIB_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(cache_npy, cam)
    cache_png.write_bytes(overlay_png)
    (config.ATTRIB_CACHE_DIR / f"{cache_key}.heat.png").write_bytes(heatmap_png)
    cache_meta.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    return AttributionResult(image_id, target_a, target_b, cam, overlay_png, heatmap_png,
                             meta, cache_key, round((time.time() - t0) * 1000, 2), False)


class _ClosureTarget:
    """Adapts a plain closure to the pytorch-grad-cam target interface."""
    def __init__(self, fn):
        self._fn = fn
    def __call__(self, model_output):
        return self._fn(model_output)


def _cache_key(image_id: str, a: str, b: str, bundle_sha: str) -> str:
    raw = f"{image_id}|{a}|{b}|{RECOVERED_MODEL_ID}|{bundle_sha}|r1c2-v1"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _render(rgb_384: np.ndarray, cam: np.ndarray) -> tuple[bytes, bytes]:
    """Overlay (jet heatmap over image) + standalone heatmap, both PNG bytes.

    Uses a pure-numpy jet colormap to avoid a matplotlib dependency.
    """
    import io
    from PIL import Image

    heat_rgb = _jet(cam)  # (H,W,3) float [0,1]
    overlay = (0.55 * rgb_384 + 0.45 * heat_rgb)
    overlay = np.clip(overlay, 0, 1)

    def to_png(arr: np.ndarray) -> bytes:
        im = Image.fromarray((arr * 255).astype(np.uint8), mode="RGB")
        buf = io.BytesIO(); im.save(buf, format="PNG"); return buf.getvalue()

    return to_png(overlay), to_png(heat_rgb)


def _jet(x: np.ndarray) -> np.ndarray:
    """Minimal jet colormap, numpy only. x in [0,1] -> (H,W,3) in [0,1]."""
    x = np.clip(x, 0.0, 1.0)
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return np.stack([r, g, b], axis=-1)


# ---------------------------------------------------------------------------
# Validation helpers (target-layer + gauge-invariance) — used by tests + script
# ---------------------------------------------------------------------------
def validate_target_layer(image_path: Path) -> dict:
    """Experimentally validate model.features[-1]: retains spatial dims, grads
    are non-zero, CAM is finite/non-empty and VARIES with the target pair."""
    st = get_state()
    torch = st["torch"]
    from pytorch_grad_cam import GradCAM
    from PIL import Image

    with Image.open(image_path) as im:
        x = st["transform"](im.convert("RGB")).unsqueeze(0)

    # feature map spatial dims at the target layer
    acts = {}
    def hook(_m, _i, o): acts["out"] = o.detach()
    h = st["target_layer"].register_forward_hook(hook)
    with torch.no_grad():
        _ = st["model"](x)
    h.remove()
    fmap = acts["out"]

    def cam_for(a, b):
        targets = [_ClosureTarget(_contrastive_target(a, b))]
        with GradCAM(model=st["model"], target_layers=[st["target_layer"]]) as eng:
            return np.asarray(eng(input_tensor=x, targets=targets)[0], dtype=np.float32)

    cam_01 = cam_for(0, 1)
    cam_02 = cam_for(0, 2)
    cam_12 = cam_for(1, 2)
    return {
        "target_layer": st["target_layer_name"],
        "feature_map_shape": list(fmap.shape),
        "feature_map_spatial": list(fmap.shape[-2:]),
        "retains_spatial_dims": fmap.shape[-1] >= 2 and fmap.shape[-2] >= 2,
        "cam_shape": list(cam_01.shape),
        "cam_finite": bool(np.isfinite(cam_01).all()),
        "cam_nonempty_nonconstant": float(cam_01.std()) > 1e-6,
        "cam_std_pair_01": float(cam_01.std()),
        "varies_with_target_01_vs_02": float(np.abs(cam_01 - cam_02).max()),
        "varies_with_target_01_vs_12": float(np.abs(cam_01 - cam_12).max()),
        "target_sensitivity_ok": float(np.abs(cam_01 - cam_02).max()) > 1e-6,
    }


def gauge_invariance_check(image_path: Path, common_scale: float = 3.7) -> dict:
    """Add an arbitrary identical common-mode vector+bias to ALL 3 class heads
    and confirm: (1) softmax predictions unchanged, (2) single-class CAM CAN
    change, (3) contrastive A-B CAM unchanged within tolerance."""
    import copy
    st = get_state()
    torch = st["torch"]
    import torch.nn as nn
    from pytorch_grad_cam import GradCAM
    from pytorch_grad_cam.utils.model_targets import ClassifierOutputTarget
    from PIL import Image

    with Image.open(image_path) as im:
        x = st["transform"](im.convert("RGB")).unsqueeze(0)

    base = st["model"]
    gauged = copy.deepcopy(base)
    # common-mode vector v (1024) + scalar c added to every class row/bias
    torch.manual_seed(7)
    v = torch.randn(1024) * common_scale
    c = float(torch.randn(1).item()) * common_scale
    with torch.no_grad():
        gauged.classifier[-1].weight += v.unsqueeze(0)  # same v to all 3 rows
        gauged.classifier[-1].bias += c

    with torch.no_grad():
        lb = base(x)[0]; lg = gauged(x)[0]
        pb = torch.softmax(lb, 0).numpy(); pg = torch.softmax(lg, 0).numpy()

    def single_cam(model, cls):
        with GradCAM(model=model, target_layers=[model.features[-1]]) as eng:
            return np.asarray(eng(input_tensor=x, targets=[ClassifierOutputTarget(cls)])[0], dtype=np.float32)

    def contrastive_cam(model, a, b):
        with GradCAM(model=model, target_layers=[model.features[-1]]) as eng:
            return np.asarray(eng(input_tensor=x, targets=[_ClosureTarget(_contrastive_target(a, b))])[0], dtype=np.float32)

    single_base = single_cam(base, 0)
    single_gauged = single_cam(gauged, 0)
    contr_base = contrastive_cam(base, 0, 1)
    contr_gauged = contrastive_cam(gauged, 0, 1)

    return {
        "common_mode_scale": common_scale,
        "softmax_max_abs_diff": float(np.abs(pb - pg).max()),
        "softmax_unchanged": bool(np.abs(pb - pg).max() < 1e-5),
        "argmax_unchanged": bool(int(pb.argmax()) == int(pg.argmax())),
        "single_class_cam_max_abs_diff": float(np.abs(single_base - single_gauged).max()),
        "single_class_cam_can_change": bool(np.abs(single_base - single_gauged).max() > 1e-4),
        "contrastive_cam_max_abs_diff": float(np.abs(contr_base - contr_gauged).max()),
        "contrastive_cam_invariant": bool(np.abs(contr_base - contr_gauged).max() < 1e-3),
    }
