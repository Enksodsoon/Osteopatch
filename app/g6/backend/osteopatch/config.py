"""OsteoPatch G6 — central configuration and frozen constants.

Everything that is part of the FROZEN G4 contract lives here as a single source
of truth: the canonical class order, the expected G4 bundle SHA-256, and the
default on-disk locations. Paths are overridable by environment variable so the
app is portable, but the defaults match the parent-verified preconditions.

Nothing in this module is a biological or clinical claim. ``training_eligible``
is NOT a class; ``MIXED_VIABLE_NECROTIC`` is excluded source metadata, never a
4th model output. The model has EXACTLY 3 outputs.
"""
from __future__ import annotations

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Frozen G4 contract (IMMUTABLE — must match the model card / final-bundle.json)
# ---------------------------------------------------------------------------
CANONICAL_CLASSES: tuple[str, str, str] = ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")
CLASS_TO_IDX = {c: i for i, c in enumerate(CANONICAL_CLASSES)}
IDX_TO_CLASS = {i: c for i, c in enumerate(CANONICAL_CLASSES)}

MODEL_VERSION = "baseline-frozen-g4"

# SHA-256 of osteopatch_g4_baseline_bundle.pt — re-verified at model load; the
# precompute script REFUSES to run on mismatch (frozen-contract guard).
EXPECTED_BUNDLE_SHA256 = (
    "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"
)

# Review / deferral vocabularies (i18n keys; English display in the string table)
REVIEW_ACTIONS = ("ACCEPT", "CORRECT", "DEFER")
DEFER_REASONS = (
    "mixed_tissue",
    "poor_image_quality",
    "insufficient_context",
    "uncertain_morphology",
    "other",
)

DISCLAIMER = (
    "Educational / research prototype. NOT for diagnosis, treatment decisions, "
    "treatment-response prediction, or prognosis. Model scores are uncalibrated "
    "class scores, never disease probabilities."
)


def _env_path(var: str, default: str) -> Path:
    return Path(os.environ.get(var, default)).resolve()


# ---------------------------------------------------------------------------
# Locations (parent-verified defaults; override via environment)
# ---------------------------------------------------------------------------
# Durable project app dir (this package lives under app/g6/backend/osteopatch).
APP_DIR = Path(__file__).resolve().parent.parent  # .../app/g6/backend


def _default_project_root() -> str:
    """.../OsteoPatch_Kiro_Handoff locally; but in the Lambda the package lives
    at /var/task/osteopatch (only 2 parents), so parents[4] would IndexError.
    Fall back to the deepest available parent rather than crash at import — the
    env var OSTEOPATCH_PROJECT_ROOT overrides this anyway on Lambda."""
    p = Path(__file__).resolve()
    try:
        return str(p.parents[4])
    except IndexError:
        return str(p.parents[len(p.parents) - 1])


PROJECT_ROOT = _env_path(
    "OSTEOPATCH_PROJECT_ROOT",
    _default_project_root(),  # .../OsteoPatch_Kiro_Handoff
)

# Runtime data root. Resolution is env var -> repo/runtime-artifacts ->
# app/runtime-artifacts. There are deliberately NO machine-specific defaults
# here: the previous hardcoded `C:\Users\enkso\.kiro\crew\scratch\...` paths
# pointed at a directory that has since been reclaimed, so every consumer
# silently fell back to a non-existent location.
def _runtime_root() -> Path:
    env = os.environ.get("OSTEOPATCH_RUNTIME_ARTIFACTS", "").strip()
    if env:
        return Path(env).resolve()
    for candidate in (PROJECT_ROOT / "runtime-artifacts", APP_DIR / "runtime-artifacts"):
        if candidate.is_dir():
            return candidate.resolve()
    # Not an error at import: the app must still start so /health can explain
    # what is missing. scripts/prepare_runtime.py reports this properly.
    return (PROJECT_ROOT / "runtime-artifacts").resolve()


RUNTIME_ARTIFACTS_ROOT = _runtime_root()

# Legacy scratch override, retained so existing local runbooks keep working.
SCRATCH_ROOT = _env_path("OSTEOPATCH_SCRATCH", str(RUNTIME_ARTIFACTS_ROOT / "scratch"))

DB_PATH = _env_path("OSTEOPATCH_DB", str(RUNTIME_ARTIFACTS_ROOT / "db" / "osteopatch_g6.sqlite3"))
THUMBS_DIR = _env_path("OSTEOPATCH_THUMBS", str(RUNTIME_ARTIFACTS_ROOT / "thumbnails"))

# The ORIGINAL frozen G4 bundle. This file no longer exists on disk (the
# reclaimable scratch that held it was lost); it is kept as a path so the
# loader's hash guard and its tests still have a target, and so a restored
# copy is picked up without a code change. Its 1,144 immutable predictions
# remain keyed to EXPECTED_BUNDLE_SHA256 and are never rewritten.
BUNDLE_PATH = _env_path(
    "OSTEOPATCH_BUNDLE",
    str(RUNTIME_ARTIFACTS_ROOT / "models" / "osteopatch_g4_baseline_bundle.pt"),
)

# Decoded TIFF patches — the only pixel source.
TIFFS_DIR = _env_path("OSTEOPATCH_TIFFS", str(RUNTIME_ARTIFACTS_ROOT / "images"))

# Source/QC metadata CSVs (durable, read-only).
QC_DIR = _env_path(
    "OSTEOPATCH_QC_DIR",
    str(PROJECT_ROOT / "aidlc-docs" / "inception" / "full-image-qc"),
)
INGESTION_MANIFEST = QC_DIR / "full-ingestion-manifest.csv"
QC_RESULTS = QC_DIR / "full-image-qc-results.csv"
HUMAN_REVIEW_QUEUE = QC_DIR / "human-review-queue.csv"  # 63-row DATA-QC queue

# G4 model-card source (durable, read-only).
MODEL_CARD_DIR = _env_path(
    "OSTEOPATCH_MODEL_CARD_DIR",
    str(PROJECT_ROOT / "aidlc-docs" / "inception" / "model" / "g4"),
)

# The behaviourally-recovered head bundle (g4-behavioral-recovery-r1), produced
# by R1-C2. Distinct identity + hash from the original baseline-frozen-g4; the
# original 01727fb8... hash is NEVER reassigned to this file.
RUNTIME_ARTIFACTS = RUNTIME_ARTIFACTS_ROOT
RECOVERED_MODEL_PATH = _env_path(
    "OSTEOPATCH_RECOVERED_MODEL",
    str(RUNTIME_ARTIFACTS_ROOT / "models" / "g4-behavioral-recovery-r1.pt"),
)
RECOVERED_MODEL_ID = "g4-behavioral-recovery-r1"

# The recovered head was previously referenced BY PATH ONLY — its hash appeared
# nowhere in code, so a swapped file would have been attributed silently. This
# pins it. Attribution refuses to run on mismatch.
RECOVERED_MODEL_SHA256 = "ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73"

# Attribution image source: the durable verified TIFFs (R1-A/R1-B).
ATTRIB_IMAGES_DIR = _env_path(
    "OSTEOPATCH_ATTRIB_IMAGES", str(RUNTIME_ARTIFACTS_ROOT / "images")
)

# Torch hub cache. torchvision fetches the frozen encoder's ImageNet weights on
# first use, so a demo run would otherwise need live internet. Pointing
# TORCH_HOME at a directory under runtime-artifacts/ (gitignored, rebuildable
# with scripts/prepare_runtime.py) keeps that fetch one-off and offline
# afterwards. Consumers set it via ``os.environ.setdefault("TORCH_HOME", ...)``
# so an operator-supplied TORCH_HOME still wins.
TORCH_HUB_DIR = _env_path(
    "OSTEOPATCH_TORCH_HOME",
    str(RUNTIME_ARTIFACTS_ROOT / "models" / "torch-hub"),
)

# Filename + SHA-256 of the encoder checkpoint the recovered head was fitted
# against. Recorded so a swapped weights file is visible in capability
# evidence rather than silently changing what the model sees. This is NOT the
# recovered head bundle: that identity lives in RECOVERED_MODEL_SHA256 above.
ENCODER_CHECKPOINT_NAME = "mobilenet_v3_small-047dcff4.pth"
ENCODER_CHECKPOINT_SHA256 = (
    "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"
)
# Deterministic Grad-CAM cache (rebuildable; kept under scratch, out of git).
ATTRIB_CACHE_DIR = _env_path(
    "OSTEOPATCH_ATTRIB_CACHE",
    str(SCRATCH_ROOT / "attribution-cache"),
)

# ---------------------------------------------------------------------------
# Image allowlist (G8 deployed-demo scope) — OPTIONAL, no-op when unset.
# ---------------------------------------------------------------------------
# When OSTEOPATCH_IMAGE_ALLOWLIST points to a JSON file, the gallery / detail /
# export / rank reads are RESTRICTED to exactly the listed image_ids. This does
# NOT change any prediction, score, or label — the immutable read model is
# untouched; it only scopes WHICH rows the deployed demo surfaces (the 50-image
# representative subset). Unset (local dev) => full 1,144-row behaviour, so the
# local app and every existing test are unaffected.
#
# Accepted file shapes: a bare JSON array of ids, or an object with a
# "subset_image_ids" (preferred) or "image_ids"/"ids" key.
IMAGE_ALLOWLIST_PATH = os.environ.get("OSTEOPATCH_IMAGE_ALLOWLIST", "").strip()


def load_image_allowlist() -> frozenset[str] | None:
    """Return the frozenset of allowed image_ids, or None when no allowlist is
    configured (meaning: do not restrict). Loaded once and cached."""
    global _IMAGE_ALLOWLIST_CACHE
    cached = _IMAGE_ALLOWLIST_CACHE
    if cached is not _ALLOWLIST_UNSET:
        assert cached is None or isinstance(cached, frozenset)
        return cached
    result: frozenset[str] | None = None
    if IMAGE_ALLOWLIST_PATH:
        p = Path(IMAGE_ALLOWLIST_PATH)
        if p.exists():
            import json

            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                ids = data.get("subset_image_ids") or data.get("image_ids") or data.get("ids") or []
            else:
                ids = data
            result = frozenset(str(i) for i in ids)
    _IMAGE_ALLOWLIST_CACHE = result
    return result


_ALLOWLIST_UNSET: object = object()
_IMAGE_ALLOWLIST_CACHE: object = _ALLOWLIST_UNSET

# Thumbnail long edge (px) for gallery; full image served separately.
THUMBNAIL_SIZE = 256

# Server binding — 127.0.0.1 ONLY (frozen constraint). Never 0.0.0.0.
HOST = "127.0.0.1"
PORT = int(os.environ.get("OSTEOPATCH_PORT", "8137"))

DEFAULT_REVIEWER = "local-reviewer"
