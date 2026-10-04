"""Safe local image serving: thumbnail + full, 127.0.0.1 only.

Browsers cannot render TIFF reliably, so both the thumbnail and the "full" image
are served as PNG derived from the decoded TIFF. The source filename comes from
the DB (``source_qc.tiff_filename``), and the resolved path MUST stay inside the
configured TIFFS_DIR — any attempt to escape it is refused (path-traversal
safe). Thumbnails are cached under scratch; full images are rendered on demand
(only the selected patch is ever loaded full-size).
"""
from __future__ import annotations

import io
import sqlite3
from pathlib import Path

from PIL import Image

from . import config


class ImageNotFound(Exception):
    pass


class UnsafePath(Exception):
    pass


class ImageDecodeError(Exception):
    """The source file exists and is in-bounds, but PIL could not decode it
    (corrupt, truncated, or an unsupported format). Surfaced as a clean 422
    rather than leaking as an unhandled 500."""
    pass


def _resolve_tiff(conn: sqlite3.Connection, image_id: str) -> Path:
    row = conn.execute(
        "SELECT tiff_filename FROM source_qc WHERE image_id = ?", (image_id,)
    ).fetchone()
    if row is None:
        raise ImageNotFound(image_id)
    fname = row["tiff_filename"]
    base = config.TIFFS_DIR
    target = (base / fname).resolve()
    # path-traversal guard: resolved path must be within TIFFS_DIR
    try:
        target.relative_to(base)
    except ValueError:
        raise UnsafePath(fname)
    if not target.exists():
        raise ImageNotFound(image_id)
    return target


def thumbnail_png(conn: sqlite3.Connection, image_id: str) -> bytes:
    """Return (and cache) a PNG thumbnail for the gallery."""
    config.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    cache = config.THUMBS_DIR / f"{image_id}.png"
    if cache.exists():
        return cache.read_bytes()
    src = _resolve_tiff(conn, image_id)
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            im.thumbnail((config.THUMBNAIL_SIZE, config.THUMBNAIL_SIZE))
            buf = io.BytesIO()
            im.save(buf, format="PNG")
    except (OSError, ValueError) as exc:
        # PIL raises UnidentifiedImageError (an OSError subclass) / OSError on a
        # truncated or corrupt TIFF, ValueError on a malformed mode. Fail clean.
        raise ImageDecodeError(f"{image_id}: {exc}") from exc
    data = buf.getvalue()
    cache.write_bytes(data)
    return data


def full_png(conn: sqlite3.Connection, image_id: str) -> bytes:
    """Render the full patch as PNG (loaded only when selected)."""
    src = _resolve_tiff(conn, image_id)
    try:
        with Image.open(src) as im:
            im = im.convert("RGB")
            buf = io.BytesIO()
            im.save(buf, format="PNG")
    except (OSError, ValueError) as exc:
        raise ImageDecodeError(f"{image_id}: {exc}") from exc
    return buf.getvalue()
