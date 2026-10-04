"""Serve the ACTUAL frozen G4 model-card info (read-only).

Pulls from the durable G4 artifacts (model-card-baseline.md, final-bundle.json,
overall-oof-metrics.json). The app does NOT recompute these; the G4 OOF LOGO
evaluation stays the immutable performance evidence.
"""
from __future__ import annotations

import json

from . import config


def _read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def model_card() -> dict:
    md = config.MODEL_CARD_DIR / "model-card-baseline.md"
    oof = _read_json(config.MODEL_CARD_DIR / "overall-oof-metrics.json") or {}
    bundle = _read_json(config.MODEL_CARD_DIR / "final-bundle.json") or {}
    cfg = (bundle or {}).get("config", {})
    return {
        "model_version": config.MODEL_VERSION,
        "model_bundle_sha256": config.EXPECTED_BUNDLE_SHA256,
        "calibration_status": cfg.get("calibration_status", "uncalibrated"),
        "canonical_classes": list(config.CANONICAL_CLASSES),
        "architecture": cfg.get("architecture"),
        "preprocessing": cfg.get("preprocessing"),
        "intended_use": cfg.get("intended_use"),
        "performance_statement": cfg.get("performance_statement"),
        "headline_oof": {
            "aggregation": oof.get("aggregation"),
            "n_rows": oof.get("n_rows"),
            "macro_f1": oof.get("macro_f1"),
            "balanced_accuracy": oof.get("balanced_accuracy"),
            "accuracy_secondary": oof.get("accuracy_secondary"),
            "log_loss": oof.get("log_loss"),
            "brier": oof.get("brier"),
            "per_class": oof.get("per_class"),
        },
        "limitations": oof.get("limitations", []),
        "disclaimer": config.DISCLAIMER,
        "evidence_note": (
            "The app performs PROTOTYPE INFERENCE only. Headline performance is "
            "the frozen G4 Leave-One-Group-Out OOF evaluation and is NOT "
            "recomputed here."
        ),
        "model_card_markdown": md.read_text(encoding="utf-8") if md.exists() else None,
    }
