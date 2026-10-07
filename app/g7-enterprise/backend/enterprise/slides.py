"""Disposable, project-scoped slide viewing. Model inference stays separate."""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from osteopatch import config, live_inference
from osteopatch.pathology.reader import SlideReadError, open_slide
from pydantic import BaseModel, Field


class Region(BaseModel):
    x: int = Field(default=0, ge=0)
    y: int = Field(default=0, ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    output_width: int = Field(default=1024, ge=1, le=2048)
    output_height: int | None = Field(default=None, ge=1, le=2048)


TILE_SIZE = 256


def max_deep_zoom_level(width: int, height: int) -> int:
    return math.ceil(math.log2(max(width, height)))


def root() -> Path:
    return config.LIVE_RUNS_DIR.parent / "slide-workspaces"


def get(project_id: str | None, slide_id: str) -> dict:
    if not project_id:
        raise HTTPException(400, "missing project context")
    if not re.fullmatch(r"[a-f0-9]{32}", slide_id):
        raise HTTPException(404, "unknown slide")
    try:
        meta = json.loads((root() / slide_id / "metadata.json").read_text())
    except (OSError, ValueError) as exc:
        raise HTTPException(404, "unknown slide") from exc
    if meta["project_id"] != project_id:
        raise HTTPException(404, "unknown slide")
    return meta


def listing(project_id: str | None) -> list[dict]:
    return sorted((get(project_id, path.parent.name) for path in root().glob("*/metadata.json")
                   if json.loads(path.read_text())["project_id"] == project_id),
                  key=lambda meta: meta["created_at"], reverse=True)


def upload(project_id: str, filename: str, data: bytes) -> dict:
    if not data:
        raise HTTPException(422, "empty image")
    if len(data) > config.LIVE_MAX_UPLOAD_BYTES:
        raise HTTPException(413, "image exceeds upload limit")
    if Path(filename).suffix.lower() not in config.LIVE_ALLOWED_SUFFIXES:
        raise HTTPException(415, "unsupported image extension")
    slide_id = uuid.uuid4().hex
    directory = root() / slide_id
    directory.mkdir(parents=True)
    source = directory / "source.bin"
    try:
        source.write_bytes(data)
        slide = open_slide(source)
        try:
            props = slide.properties().to_dict()
        finally:
            slide.close()
        meta = {"slide_id": slide_id, "project_id": project_id, "filename": filename,
                "source_sha256": hashlib.sha256(data).hexdigest(), "byte_size": len(data),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "tile_size": TILE_SIZE, **props}
        (directory / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        return meta
    except Exception as exc:
        shutil.rmtree(directory)
        raise HTTPException(422, f"Image could not be opened: {exc}") from exc


def source(project_id: str | None, slide_id: str) -> Path:
    get(project_id, slide_id)
    path = root() / slide_id / "source.bin"
    if not path.is_file():
        raise HTTPException(404, "uploaded source is unavailable")
    return path


def pixels(project_id: str | None, slide_id: str, region: Region) -> bytes:
    meta = get(project_id, slide_id)
    if region.x + region.width > meta["width"] or region.y + region.height > meta["height"]:
        raise HTTPException(422, "region is outside the slide")
    try:
        slide = open_slide(source(project_id, slide_id))
    except SlideReadError as exc:
        raise HTTPException(422, "uploaded image cannot be decoded") from exc
    try:
        # Read from a real pyramid level; no full-resolution WSI raster is made.
        output_height = region.output_height or 2048
        ratio = max(region.width / region.output_width, region.height / output_height, 1)
        levels = meta["level_downsamples"]
        level = max((i for i, downsample in enumerate(levels) if downsample <= ratio), default=0)
        downsample = levels[level]
        width, height = math.ceil(region.width / downsample), math.ceil(region.height / downsample)
        if width * height > 32_000_000:
            raise HTTPException(422, "This image has no suitable pyramid level. Zoom into a smaller region.")
        image = slide.read_region(region.x, region.y, level, width, height).convert("RGB")
        if region.output_height is None:
            image.thumbnail((region.output_width, output_height))
        else:
            image = image.resize((region.output_width, region.output_height))
        return live_inference._png(image)
    finally:
        slide.close()


def tile(project_id: str | None, slide_id: str, level: int, x: int, y: int) -> bytes:
    meta = get(project_id, slide_id)
    max_level = max_deep_zoom_level(meta["width"], meta["height"])
    if level < 0 or level > max_level or x < 0 or y < 0:
        raise HTTPException(404, "unknown slide tile")
    downsample = 2 ** (max_level - level)
    x0, y0 = x * TILE_SIZE * downsample, y * TILE_SIZE * downsample
    if x0 >= meta["width"] or y0 >= meta["height"]:
        raise HTTPException(404, "unknown slide tile")
    width = min(TILE_SIZE * downsample, meta["width"] - x0)
    height = min(TILE_SIZE * downsample, meta["height"] - y0)
    return pixels(project_id, slide_id, Region(
        x=x0, y=y0, width=width, height=height,
        output_width=math.ceil(width / downsample),
        output_height=math.ceil(height / downsample),
    ))


def preview(project_id: str | None, slide_id: str) -> bytes:
    meta = get(project_id, slide_id)
    return pixels(project_id, slide_id, Region(
        x=0, y=0, width=meta["width"], height=meta["height"], output_width=320,
    ))
