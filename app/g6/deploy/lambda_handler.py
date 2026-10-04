"""AWS Lambda entrypoint for the OsteoPatch Review API (G8).

The SAME FastAPI app (osteopatch.app:app) runs here, wrapped by Mangum for API
Gateway v2 (HTTP API) proxy integration. Nothing in the domain changes:

  * The IMMUTABLE read model (source_qc + prediction) is the frozen SQLite file,
    BAKED INTO THE IMAGE at /var/task/runtime/osteopatch_g6.sqlite3 (read-only,
    copied to a writable /tmp path on cold start because SQLite wants to open
    its dir writable for WAL/journal even on read).
  * The recovered model bundle is baked in at /var/task/runtime/models/.
  * The large pixel assets (TIFFs + thumbnails) live in the PRIVATE S3 artifacts
    bucket and are fetched to /tmp on first use (per-image, cached for the warm
    container's lifetime). The Lambda's execution role has read-only access to
    that bucket; the bucket is never public.
  * Review events persist in DynamoDB (OSTEOPATCH_REVIEW_STORE=dynamodb).

Torch stays lazy: importing this module and serving the gallery/review/export
path never loads torch. Only GET /attribution triggers the torch import.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

# ---------------------------------------------------------------------------
# Resolve runtime paths BEFORE importing the app (config reads env at import).
# ---------------------------------------------------------------------------
_TASK = Path(os.environ.get("LAMBDA_TASK_ROOT", "/var/task"))
_BAKED = _TASK / "runtime"
_TMP = Path("/tmp/osteopatch")
_TMP.mkdir(parents=True, exist_ok=True)

# Copy the frozen SQLite DB to a writable /tmp location (read model is immutable;
# the copy only exists so SQLite can open its directory). Done once per cold
# container.
_DB_SRC = _BAKED / "db" / "osteopatch_g6.sqlite3"
_DB_DST = _TMP / "osteopatch_g6.sqlite3"
if _DB_SRC.exists() and not _DB_DST.exists():
    shutil.copy2(_DB_SRC, _DB_DST)

# TIFFs + thumbnails are fetched from S3 into these /tmp dirs on demand.
_TIFFS = _TMP / "tiffs"
_THUMBS = _TMP / "thumbnails"
_TIFFS.mkdir(parents=True, exist_ok=True)
_THUMBS.mkdir(parents=True, exist_ok=True)
_ATTRIB_CACHE = _TMP / "attribution-cache"
_ATTRIB_CACHE.mkdir(parents=True, exist_ok=True)

# Point the frozen config at the baked / tmp locations. These env vars are the
# SAME override hooks config.py already honours — no code change in config.
os.environ.setdefault("OSTEOPATCH_DB", str(_DB_DST))
os.environ.setdefault("OSTEOPATCH_THUMBS", str(_THUMBS))
os.environ.setdefault("OSTEOPATCH_TIFFS", str(_TIFFS))
os.environ.setdefault("OSTEOPATCH_ATTRIB_IMAGES", str(_TIFFS))  # attribution reads TIFFs from here
os.environ.setdefault("OSTEOPATCH_ATTRIB_CACHE", str(_ATTRIB_CACHE))
os.environ.setdefault("OSTEOPATCH_RECOVERED_MODEL", str(_BAKED / "models" / "g4-behavioral-recovery-r1.pt"))
os.environ.setdefault("OSTEOPATCH_REVIEW_STORE", "dynamodb")

# G8 deployed-demo scope: restrict the gallery/detail/export to the deterministic
# 50-image representative subset baked into the image. config.load_image_allowlist
# reads this path; unset locally => full collection (unchanged).
_ALLOWLIST = _BAKED / "g8-subset-image-ids.json"
if _ALLOWLIST.exists():
    os.environ.setdefault("OSTEOPATCH_IMAGE_ALLOWLIST", str(_ALLOWLIST))

# Point torchvision at the baked ImageNet backbone-weights cache so the
# attribution path resolves them offline (no NAT egress in Lambda). The weights
# were pre-fetched into this dir at image build time.
_TORCH_HOME = _BAKED / "torch"
if _TORCH_HOME.exists():
    os.environ.setdefault("TORCH_HOME", str(_TORCH_HOME))

_ASSET_BUCKET = os.environ.get("OSTEOPATCH_ASSET_BUCKET", "")
_ASSET_TIFF_PREFIX = os.environ.get("OSTEOPATCH_ASSET_TIFF_PREFIX", "images/")
_ASSET_THUMB_PREFIX = os.environ.get("OSTEOPATCH_ASSET_THUMB_PREFIX", "thumbnails/")

_s3 = None


def _s3_client():
    global _s3
    if _s3 is None:
        import boto3
        _s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
    return _s3


def _ensure_tiff(image_id: str) -> None:
    """Fetch <image_id>.tiff from S3 into /tmp/tiffs on first use."""
    if not _ASSET_BUCKET:
        return
    dst = _TIFFS / f"{image_id}.tiff"
    if dst.exists():
        return
    key = f"{_ASSET_TIFF_PREFIX}{image_id}.tiff"
    try:
        _s3_client().download_file(_ASSET_BUCKET, key, str(dst))
    except Exception:
        # leave absent -> the app returns a clean 404 (image pixels not found)
        pass


def _ensure_thumb(image_id: str) -> None:
    if not _ASSET_BUCKET:
        return
    dst = _THUMBS / f"{image_id}.png"
    if dst.exists():
        return
    key = f"{_ASSET_THUMB_PREFIX}{image_id}.png"
    try:
        _s3_client().download_file(_ASSET_BUCKET, key, str(dst))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Build the ASGI app and a thin middleware that lazily hydrates pixel assets
# for the image-serving + attribution routes before the handler runs.
# ---------------------------------------------------------------------------
from osteopatch.app import app  # noqa: E402  (env must be set first)


@app.middleware("http")
async def _hydrate_assets(request, call_next):
    path = request.url.path
    # /v1/images/{image_id}/thumbnail|full|attribution[...]
    parts = path.strip("/").split("/")
    if len(parts) >= 4 and parts[0] == "v1" and parts[1] == "images":
        image_id = parts[2]
        tail = parts[3] if len(parts) > 3 else ""
        if tail == "thumbnail":
            _ensure_thumb(image_id)
            _ensure_tiff(image_id)  # thumbnail_png falls back to decoding the TIFF
        elif tail in ("full", "attribution"):
            _ensure_tiff(image_id)
    return await call_next(request)


from mangum import Mangum  # noqa: E402

handler = Mangum(app, lifespan="off")
