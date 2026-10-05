"""Serve the ACTUAL frozen G4 model-card info (read-only).

Pulls from the durable G4 artifacts (model-card-baseline.md, final-bundle.json,
overall-oof-metrics.json). The app does NOT recompute these; the G4 OOF LOGO
evaluation stays the immutable performance evidence.

Two limitation surfaces are returned, and the distinction matters:

``limitations``
    The five frozen strings from ``overall-oof-metrics.json``, VERBATIM. These
    are durable evaluation evidence. They are never rewritten, filtered or
    reordered here.

``limitations_full`` / ``limitations_summary`` / ``limitations_grouped``
    The full catalog from :mod:`osteopatch.limitations`, which adds the data,
    attribution, platform, deployment and process caveats the frozen five
    cannot express. Every entry there cites an evidence file that a test checks
    still exists, and states what would retire it.
"""
from __future__ import annotations

import json

from . import config, limitations


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

    # The frozen G4 evaluation artifacts live in aidlc-docs/, which is NOT
    # copied into the Lambda image. Verified by running this module with an
    # absent MODEL_CARD_DIR: `limitations` comes back [] and every headline
    # metric is None. An empty list is indistinguishable from "no caveats",
    # which is exactly the wrong thing to imply about this model — so the
    # response states the absence instead of letting the UI render a blank.
    evidence_available = bool(oof)
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
        # Frozen G4 evaluation caveats — verbatim, never modified.
        "limitations": oof.get("limitations", []),
        "evaluation_evidence_available": evidence_available,
        "evaluation_evidence_unavailable_reason": (
            ""
            if evidence_available
            else (
                "The frozen G4 evaluation artifacts (aidlc-docs/inception/model/g4) "
                "are not present in this deployment, so the OOF metrics and the "
                "frozen caveat list cannot be shown. They are not missing because "
                "there were none. The limitations catalog below is unaffected — it "
                "ships inside the application package."
            )
        ),
        # The complete catalog (see limitations.py), grouped for display.
        "limitations_full": limitations.catalog(),
        "limitations_grouped": limitations.grouped(),
        "limitations_summary": limitations.summary(),
        "disclaimer": config.DISCLAIMER,
        "evidence_note": (
            "The app performs PROTOTYPE INFERENCE only. Headline performance is "
            "the frozen G4 Leave-One-Group-Out OOF evaluation and is NOT "
            "recomputed here."
        ),
        "limitations_note": (
            "'limitations' is the frozen G4 evaluation caveat list, quoted "
            "verbatim. 'limitations_full' is the complete catalog, including "
            "data, attribution, platform, deployment and process limitations "
            "that the frozen evaluation cannot express. Each full entry cites an "
            "evidence file and states what would retire it. This is an "
            "educational prototype, not a diagnostic device."
        ),
        "model_card_markdown": md.read_text(encoding="utf-8") if md.exists() else None,
    }
