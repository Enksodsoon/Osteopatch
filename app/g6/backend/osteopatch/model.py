"""Frozen G4 model loading + prototype inference (torch-dependent).

This module is imported only by the one-time precompute script and by the
torch-gated model test. The FastAPI server itself NEVER imports torch — all
predictions are precomputed, so opening a patch in the browser does not wait on
PyTorch.

Guarantees enforced here:
  * The bundle SHA-256 is re-verified at load; a mismatch RAISES and refuses to
    run (frozen-contract guard).
  * Preprocessing is taken from the bundle's own packaged spec
    (``config.preprocessing``) — resize/interpolation/antialias/normalize are
    read from the bundle, not re-invented. The one thing the bundle stores as a
    spec rather than a callable is rebuilt faithfully from those exact values.
  * Output is a 3-vector softmax over the canonical class order; this is
    PROTOTYPE INFERENCE, never an independent evaluation.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from . import config


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class BundleHashMismatch(RuntimeError):
    """Raised when the on-disk bundle hash != the frozen expected hash."""


@dataclass
class LoadedModel:
    model: object            # torch.nn.Module in eval mode
    eval_transform: object   # torchvision v2 transform
    classes: list[str]
    bundle_hash: str
    model_version: str
    config: dict


def verify_bundle_hash(bundle_path: Path | str | None = None) -> str:
    """Return the bundle hash, raising BundleHashMismatch if it is not the
    frozen expected value. Pure (hashlib only); no torch needed.
    """
    path = Path(bundle_path) if bundle_path else config.BUNDLE_PATH
    actual = sha256_file(path)
    if actual != config.EXPECTED_BUNDLE_SHA256:
        raise BundleHashMismatch(
            f"G4 bundle hash mismatch: expected "
            f"{config.EXPECTED_BUNDLE_SHA256}, got {actual} ({path})"
        )
    return actual


def _build_eval_transform(preproc: dict):
    """Rebuild the frozen eval transform from the bundle's packaged spec."""
    import torch
    import torchvision
    from torchvision.transforms import v2

    size = preproc["resize"]  # [384, 384]
    interp_name = preproc.get("interpolation", "bilinear").upper()
    interp = getattr(
        torchvision.transforms.InterpolationMode, interp_name,
        torchvision.transforms.InterpolationMode.BILINEAR,
    )
    return v2.Compose(
        [
            v2.ToImage(),
            v2.Resize(
                (int(size[0]), int(size[1])),
                interpolation=interp,
                antialias=bool(preproc.get("antialias", True)),
            ),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(
                mean=list(preproc["normalize_mean"]),
                std=list(preproc["normalize_std"]),
            ),
        ]
    )


def load_model(bundle_path: Path | str | None = None) -> LoadedModel:
    """Verify hash, load the frozen bundle, rebuild model + eval transform."""
    import torch
    import torch.nn as nn
    from torchvision.models import mobilenet_v3_small

    path = Path(bundle_path) if bundle_path else config.BUNDLE_PATH
    bundle_hash = verify_bundle_hash(path)

    ckpt = torch.load(str(path), map_location="cpu", weights_only=False)
    cfg = ckpt["config"]
    classes = list(ckpt["classes"])
    if tuple(classes) != config.CANONICAL_CLASSES:
        raise RuntimeError(
            f"bundle class order {classes} != canonical "
            f"{list(config.CANONICAL_CLASSES)}"
        )

    model = mobilenet_v3_small(weights=None)
    in_features = model.classifier[-1].in_features
    model.classifier[-1] = nn.Linear(in_features, len(classes))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    eval_tf = _build_eval_transform(cfg["preprocessing"])
    return LoadedModel(
        model=model,
        eval_transform=eval_tf,
        classes=classes,
        bundle_hash=bundle_hash,
        model_version=cfg.get("run_id", config.MODEL_VERSION),
        config=cfg,
    )


def infer_scores(loaded: LoadedModel, image_path: Path | str) -> list[float]:
    """Run prototype inference on one patch -> 3 softmax scores (canonical order)."""
    import torch
    from PIL import Image

    with Image.open(image_path) as im:
        img = im.convert("RGB")
        x = loaded.eval_transform(img).unsqueeze(0)
    with torch.no_grad():
        probs = torch.softmax(loaded.model(x), dim=1)[0]
    return [float(v) for v in probs.tolist()]
