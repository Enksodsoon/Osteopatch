#!/usr/bin/env python
"""Record exactly which optional runtimes this machine can actually use.

Phase 0 of the demo-readiness work. The web serve path stays torch-free, so
"torch is installed" is invisible from /v1/health — it only shows up when
attribution or live inference is requested. This script makes that capability
explicit and reproducible instead of implied, and writes it to
``docs/evidence/runtime-capability.json`` so a reviewer can see which machine
produced which number.

What it reports
---------------
* torch / torchvision / grad-cam versions and whether the optional stack is
  importable AT ALL (never a fabricated version when absent).
* the OpenSlide / Pillow whole-slide engines.
* the frozen recovered head bundle's SHA-256, checked against its pin.
* the frozen encoder checkpoint's SHA-256, checked against its pin.
* the number of the 1,144 immutable predictions actually readable.

Usage
-----
    python scripts/runtime_capability.py                 # print the report
    python scripts/runtime_capability.py --warm          # fetch encoder weights first
    python scripts/runtime_capability.py --out FILE.json # also write evidence

``--warm`` downloads the ImageNet encoder checkpoint ONCE into
``runtime-artifacts/models/torch-hub`` so a later demo run needs no network.
It is the only step in this script that touches the internet, and it says so.

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "app" / "g6" / "backend"))

from osteopatch import config  # noqa: E402
from osteopatch.pathology import reader  # noqa: E402

EVIDENCE_DEFAULT = REPO / "docs" / "evidence" / "runtime-capability.json"


def sha256_file(path: Path) -> str | None:
    """SHA-256 of ``path``, or None when it does not exist. Never a guess."""
    if not path.exists():
        return None
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _version(distribution: str) -> str | None:
    import importlib.metadata as md

    try:
        return md.version(distribution)
    except Exception:
        return None


def warm_encoder_weights() -> dict:
    """Fetch the frozen encoder checkpoint into the durable runtime tree.

    The ONLY network-touching step. `TORCH_HOME` is pointed at
    ``runtime-artifacts/models/torch-hub`` (gitignored) so subsequent demo runs
    resolve the weights locally.
    """
    from torchvision.models import MobileNet_V3_Small_Weights, mobilenet_v3_small

    hub_dir = config.TORCH_HUB_DIR
    hub_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TORCH_HOME", str(hub_dir))

    t0 = time.time()
    weights = MobileNet_V3_Small_Weights.IMAGENET1K_V1
    mobilenet_v3_small(weights=weights).eval()
    return {
        "warmed": True,
        "encoder_checkpoint": config.ENCODER_CHECKPOINT_NAME,
        "torch_home": os.environ["TORCH_HOME"],
        "elapsed_s": round(time.time() - t0, 2),
    }


def torch_stack() -> dict:
    """Versions + importability of the optional model stack.

    A missing component reports ``available: false`` with a null version. It is
    never described as working because it was requested in a lock file.
    """
    out: dict = {
        "installed": False,
        "versions": {},
        "note": (
            "Optional. The web serve path is torch-free by design; this stack is "
            "imported lazily by attribution and live inference only."
        ),
    }
    try:
        import pytorch_grad_cam  # noqa: F401
        import torch  # noqa: F401
        import torchvision  # noqa: F401
    except Exception as exc:
        out["import_error"] = f"{type(exc).__name__}: {exc}"
        out["versions"] = {
            "torch": _version("torch"),
            "torchvision": _version("torchvision"),
            "grad_cam": _version("grad-cam"),
        }
        return out

    out["installed"] = True
    out["versions"] = {
        "torch": _version("torch"),
        "torchvision": _version("torchvision"),
        "grad_cam": _version("grad-cam"),
    }
    return out


def recovered_head() -> dict:
    """Identity of the behaviorally-recovered head, checked against its pin."""
    path = config.RECOVERED_MODEL_PATH
    actual = sha256_file(path)
    return {
        "model_id": config.RECOVERED_MODEL_ID,
        "path_relative": _rel(path),
        "present": path.exists(),
        "sha256": actual,
        "sha256_matches_pin": actual == config.RECOVERED_MODEL_SHA256
        if actual is not None
        else None,
        "original_frozen_model": {
            "model_id": config.MODEL_VERSION,
            "sha256": config.EXPECTED_BUNDLE_SHA256,
            "present": config.BUNDLE_PATH.exists(),
            "note": (
                "The original G4 bundle is absent and stays absent. Its hash is "
                "never reassigned to the recovered head."
            ),
        },
    }


def encoder_weights() -> dict:
    """Frozen encoder checkpoint identity, checked against its pin."""
    path = config.TORCH_HUB_DIR / "hub" / "checkpoints" / config.ENCODER_CHECKPOINT_NAME
    actual = sha256_file(path)
    return {
        "checkpoint": config.ENCODER_CHECKPOINT_NAME,
        "torch_home_relative": _rel(config.TORCH_HUB_DIR),
        "path_relative": _rel(path),
        "present": path.exists(),
        "sha256": actual,
        "sha256_matches_pin": actual == config.ENCODER_CHECKPOINT_SHA256
        if actual is not None
        else None,
        "note": (
            "ImageNet MobileNetV3-small encoder the recovered head was fitted "
            "against. This is NOT the recovered head bundle; that identity is "
            "recorded separately above."
        ),
    }


def read_model() -> dict:
    """The immutable read model: how many predictions are actually readable."""
    from osteopatch import db

    out: dict = {"db_path_relative": _rel(config.DB_PATH), "present": config.DB_PATH.exists()}
    if not out["present"]:
        out["note"] = "read model absent; run scripts/prepare_runtime.py"
        return out
    try:
        conn = db.connect()
        db.run_migrations(conn)
        out["images_indexed"] = conn.execute("SELECT COUNT(*) FROM source_qc").fetchone()[0]
        out["predictions"] = conn.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
        out["canonical_classes"] = list(config.CANONICAL_CLASSES)
        del conn
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _rel(path: Path) -> str:
    """Repo-relative path when possible, so evidence files stay portable."""
    try:
        return str(Path(path).resolve().relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path)


def build_report(*, warm: bool) -> dict:
    report: dict = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "wsi_engines": reader.engine_report(),
        "torch_stack": torch_stack(),
        "recovered_head": recovered_head(),
        "encoder_weights": encoder_weights(),
        "read_model": read_model(),
        "disclaimer": config.DISCLAIMER,
    }
    if warm:
        report["warm"] = warm_encoder_weights()
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--warm",
        action="store_true",
        help="fetch the frozen encoder checkpoint into runtime-artifacts (needs network once)",
    )
    ap.add_argument("--out", type=Path, default=None, help="also write the report as JSON")
    args = ap.parse_args()

    report = build_report(warm=args.warm)
    if args.warm:
        # Re-read so the evidence reflects the state AFTER warming.
        report["encoder_weights"] = encoder_weights()

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
        print(f"\nwrote {args.out}", file=sys.stderr)

    # Exit 0 even when torch is missing: a torch-free machine is a valid, fully
    # supported configuration of this prototype. Capability is recorded, not gated.
    return 0


if __name__ == "__main__":
    sys.exit(main())
