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

# Runtime data root (NOT in git) — SQLite db, thumbnails, prediction cache.
SCRATCH_ROOT = _env_path(
    "OSTEOPATCH_SCRATCH",
    r"C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_g6",
)

DB_PATH = _env_path("OSTEOPATCH_DB", str(SCRATCH_ROOT / "osteopatch_g6.sqlite3"))
THUMBS_DIR = _env_path("OSTEOPATCH_THUMBS", str(SCRATCH_ROOT / "thumbnails"))

# Frozen G4 bundle (scratch, out of git).
BUNDLE_PATH = _env_path(
    "OSTEOPATCH_BUNDLE",
    r"C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_g4\final_bundle\osteopatch_g4_baseline_bundle.pt",
)

# Decoded TIFF patches (scratch, out of git) — the only pixel source.
TIFFS_DIR = _env_path(
    "OSTEOPATCH_TIFFS",
    r"C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_full_ingestion\tiffs",
)

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

# ---------------------------------------------------------------------------
# Recovered model + attribution (G7 / R1-C2) — DURABLE under runtime-artifacts/
# ---------------------------------------------------------------------------
# The behaviorally-recovered head bundle (g4-behavioral-recovery-r1), produced
# by R1-C2. Distinct identity + hash from the original baseline-frozen-g4; the
# original 01727fb8... hash is NEVER reassigned to this file.
RUNTIME_ARTIFACTS = _env_path(
    "OSTEOPATCH_RUNTIME_ARTIFACTS", str(PROJECT_ROOT / "runtime-artifacts")
)
RECOVERED_MODEL_PATH = _env_path(
    "OSTEOPATCH_RECOVERED_MODEL",
    str(RUNTIME_ARTIFACTS / "models" / "g4-behavioral-recovery-r1.pt"),
)
RECOVERED_MODEL_ID = "g4-behavioral-recovery-r1"

# Attribution image source: the durable verified TIFFs (R1-A/R1-B).
ATTRIB_IMAGES_DIR = _env_path(
    "OSTEOPATCH_ATTRIB_IMAGES", str(RUNTIME_ARTIFACTS / "images")
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
    if "_IMAGE_ALLOWLIST_CACHE" in globals() and _IMAGE_ALLOWLIST_CACHE is not _ALLOWLIST_UNSET:
        return _IMAGE_ALLOWLIST_CACHE
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


_ALLOWLIST_UNSET = object()
_IMAGE_ALLOWLIST_CACHE = _ALLOWLIST_UNSET

# Thumbnail long edge (px) for gallery; full image served separately.
THUMBNAIL_SIZE = 256

# Server binding — 127.0.0.1 ONLY (frozen constraint). Never 0.0.0.0.
HOST = "127.0.0.1"
PORT = int(os.environ.get("OSTEOPATCH_PORT", "8137"))

DEFAULT_REVIEWER = "local-reviewer"
