"""Live inference over a file the user imported.

WHAT THIS IS NOT
----------------
This is NOT the frozen G4 model. The original ``baseline-frozen-g4`` binary is
gone; what survives is a behaviourally recovered head
(``g4-behavioral-recovery-r1``) with its OWN sha256, fitted to the immutable
predictions that outlived the binary. A forward pass through it is a genuine
inference, and it is also a *different model* from the one that produced the
1,144 corpus rows.

So a live run is stored in ``live_run`` / ``live_tile`` and never in
``prediction``. The database enforces that (see migration 0003): a live row
cannot be inserted claiming ``baseline-frozen-g4`` or its bundle hash. The
1,144 corpus rows keep their values, ids and hashes byte for byte, and
``integrity.corpus_row_digest`` lets a caller prove it.

WHY IT REUSES ``attribution.get_state()``
-----------------------------------------
The encoder + recovered head + frozen preprocessing transform + the SHA-256
guard that must run BEFORE ``torch.load`` already exist in ``attribution``. A
second loader would be a second place to get the hash check wrong, and the two
could drift into disagreeing about which weights are loaded. This module is a
forward pass over that ONE verified state.

TORCH-GATED, ON-DEMAND. ``import torch`` happens inside the call, never at
module scope, so the ordinary review serve path stays torch-free
(``test_serve_path_torch_free.py`` enforces this against these routes too).

HONESTY RULES
-------------
1. Scores are uncalibrated class scores. Every response carries
   ``score_label`` saying so, and nothing renders them as probabilities.
2. A low top-two margin is reported as ``confidence: low`` /
   ``indeterminate`` with a plain-English caveat, NOT smoothed into a
   confident-looking number.
3. Input properties the file does not carry (mpp, objective power, vendor) are
   ``None``. They are never estimated.
4. ``support_flags`` are MEASURED facts about the input (a uniform image has no
   structure to score; a fully greyscale patch is outside this corpus's H&E
   contract). They are advisory: they never suppress a score, because a flag is
   a caveat, not a verdict.
5. A slide larger than ``max_tiles`` is analysed on a deterministic grid and
   says ``truncated: true`` with both counts. It never silently drops tiles.

Educational research prototype. Not for diagnosis, treatment decisions,
treatment-response prediction, or prognosis.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import sqlite3
import time
import uuid
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from . import config
from .db import utc_now
from .pathology import reader

SCORE_LABEL = "Model score — uncalibrated (recovered research head)"

#: Tile colours for the class mosaic. Chosen to match the reviewer's existing
#: class accents; a tile that failed to decode is grey, never tinted.
CLASS_COLOURS: dict[str, tuple[int, int, int]] = {
    "NON_TUMOR": (46, 125, 92),
    "VIABLE_TUMOR": (176, 58, 46),
    "NECROSIS": (108, 62, 140),
}
UNDECODED_COLOUR = (150, 150, 150)


class LiveInferenceError(RuntimeError):
    """An honest failure. Never returns a fabricated prediction in its place."""


class UnsupportedInput(LiveInferenceError):
    """The input cannot be read as an image at all (not merely low-confidence)."""


# ---------------------------------------------------------------------------
# Scores + honesty
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LivePrediction:
    """One forward pass. ``predicted_class`` is None only when scoring failed."""

    scores: dict[str, float]
    predicted_class: str | None
    top1_score: float
    top_two_margin: float
    normalized_entropy: float
    confidence: str
    caveat: str | None
    support_flags: list[str] = field(default_factory=list)
    score_label: str = SCORE_LABEL

    def to_dict(self) -> dict:
        return asdict(self)


def _softmax(logits) -> dict[str, float]:
    import numpy as np

    v = np.asarray(logits, dtype=np.float64)
    v = v - v.max()
    e = np.exp(v)
    p = e / e.sum()
    return {cls: float(p[i]) for i, cls in enumerate(config.CANONICAL_CLASSES)}


def _margin_and_entropy(scores: dict[str, float]) -> tuple[float, float]:
    import numpy as np

    ordered = sorted(scores.values(), reverse=True)
    margin = float(ordered[0] - ordered[1])
    v = np.asarray(list(scores.values()), dtype=np.float64)
    # An all-equal score vector carries no information; report full entropy
    # rather than dividing by zero.
    denom = np.log(len(v))
    entropy = float(-(v * np.log(np.clip(v, 1e-12, None))).sum() / denom) if denom > 0 else 1.0
    return margin, entropy


def _band(margin: float) -> tuple[str, str | None]:
    """Confidence band + the caveat to show with it.

    These bands describe the recovered head's OUTPUT SPREAD on this corpus. They
    are not calibrated probabilities of correctness and must never be presented
    as such — the text below says so in the response itself.
    """
    if margin < config.LIVE_MARGIN_INDETERMINATE:
        return (
            "indeterminate",
            "The top two classes are effectively tied. The model is not "
            "distinguishing them; treat this as 'no call' and defer to a human.",
        )
    if margin < config.LIVE_MARGIN_LOW:
        return (
            "low",
            "The top two classes are close. This is a weak separation between "
            "them, not a confident call.",
        )
    return ("clear", None)


def support_flags_for(image) -> list[str]:
    """Measured, advisory facts about an input image.

    Each flag states something OBSERVABLE about the pixels. None of them is a
    learned out-of-distribution score, and none suppresses the prediction — a
    flag is a caveat attached to a number, not a replacement for one.

    The greyscale test compares CHANNELS (R vs G vs B), not each channel's own
    spread. A spread threshold would fire on ordinary low-saturation tissue; R
    == G == B is the actual definition of a greyscale image.
    """
    flags: list[str] = []
    w, h = image.size
    if min(w, h) < 32:
        flags.append(f"tiny_input: smallest side is {min(w, h)}px")
    longest, shortest = max(w, h), max(1, min(w, h))
    if longest / shortest > 10:
        flags.append(f"extreme_aspect: {w}x{h} is not a square-ish field")

    small = image.convert("RGB").resize((32, 32))
    px = list(small.getdata())
    channels = list(zip(*px, strict=True))
    spreads = [max(c) - min(c) for c in channels]
    channel_gap = max(
        max(abs(a - b) for a, b in zip(channels[0], channels[1], strict=True)),
        max(abs(a - b) for a, b in zip(channels[1], channels[2], strict=True)),
    )
    if max(spreads) <= 1:
        flags.append("uniform_image: the input carries almost no structure")
    elif channel_gap == 0:
        flags.append("greyscale: H&E is stained colour, this input is not")
    return flags


def _predict_array(state: dict, pil_image) -> LivePrediction:
    """Forward pass + honest banding. Requires the recovered head to be loadable."""
    torch = state["torch"]
    from .attribution import _LOCK
    flags = support_flags_for(pil_image)
    try:
        tensor = state["transform"](pil_image.convert("RGB")).unsqueeze(0)
        with _LOCK, torch.no_grad():
            logits = state["model"](tensor)[0]
    except Exception as exc:  # pragma: no cover - model/runtime dependent
        raise LiveInferenceError(f"forward pass failed: {type(exc).__name__}: {exc}") from exc

    scores = _softmax(logits)
    ordered = sorted(scores, key=lambda c: scores[c], reverse=True)
    margin, entropy = _margin_and_entropy(scores)
    confidence, caveat = _band(margin)
    if flags:
        extra = "Input properties outside the recovered head's training contract: " + "; ".join(flags)
        caveat = f"{caveat} {extra}" if caveat else extra
    return LivePrediction(
        scores=scores,
        predicted_class=ordered[0],
        top1_score=float(scores[ordered[0]]),
        top_two_margin=margin,
        normalized_entropy=entropy,
        confidence=confidence,
        caveat=caveat,
        support_flags=flags,
    )


def runtime_available() -> dict:
    """Whether a live forward pass can run at all, and why not when it cannot.

    Never raises, never guesses. Used by the API to explain itself instead of
    failing at the first request.

    Deliberately torch-free: ``importlib.util.find_spec`` locates the package
    WITHOUT executing it, so the capability probe the UI calls on page load does
    not pull a ~1 GB runtime into the process. Actually loading the model happens
    only when a run is requested.
    """
    import importlib.util

    spec = importlib.util.find_spec("torch")
    if spec is None:
        return {
            "available": False,
            "reason": "torch is not installed (install the optional `model` extra)",
            "hint": "uv sync --locked --extra dev --extra model",
        }
    for package in ("torchvision",):
        if importlib.util.find_spec(package) is None:
            return {
                "available": False,
                "reason": f"{package} is not installed (install the optional `model` extra)",
                "hint": "uv sync --locked --extra dev --extra model",
            }
    from . import attribution

    if not attribution.RECOVERED_BUNDLE.exists():
        return {
            "available": False,
            "reason": f"recovered head bundle missing: {attribution.RECOVERED_BUNDLE}",
            "hint": "run scripts/prepare_runtime.py",
        }
    if not _pinned_file(attribution.RECOVERED_BUNDLE, config.RECOVERED_MODEL_SHA256):
        return {
            "available": False,
            "reason": "recovered head bundle failed its pinned SHA-256 check",
            "hint": "restore the verified runtime bundle",
        }
    encoder = config.TORCH_HUB_DIR / "hub" / "checkpoints" / config.ENCODER_CHECKPOINT_NAME
    if not encoder.is_file():
        return {
            "available": False,
            "reason": "pinned MobileNetV3 encoder checkpoint is missing",
            "hint": "run scripts/runtime_capability.py --warm",
        }
    if not _pinned_file(encoder, config.ENCODER_CHECKPOINT_SHA256):
        return {
            "available": False,
            "reason": "MobileNetV3 encoder checkpoint failed its pinned SHA-256 check",
            "hint": "restore the verified runtime bundle",
        }
    return {
        "available": True,
        "model_id": attribution.RECOVERED_MODEL_ID,
        "bundle_path_relative": "runtime-artifacts/models/g4-behavioral-recovery-r1.pt",
        "note": (
            "Live runs use the RECOVERED head, which is a different model from "
            "the frozen baseline-frozen-g4 that produced the corpus predictions. "
            "Results are never stored as corpus predictions."
        ),
    }


def _pinned_file(path: Path, expected: str) -> bool:
    try:
        stat = path.stat()
        return _pinned_file_cached(str(path.resolve()), expected, stat.st_size, stat.st_mtime_ns)
    except OSError:
        return False


@lru_cache(maxsize=8)
def _pinned_file_cached(path: str, expected: str, size: int, mtime_ns: int) -> bool:
    from . import attribution
    return attribution._sha256_file(Path(path)) == expected


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def run_dir(run_id: str) -> Path:
    d = config.LIVE_RUNS_DIR / run_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_run(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    source_kind: str,
    source_name: str,
    source_bytes: bytes,
    engine: str,
    props: dict | None,
    requested_by: str,
    latency_ms: float,
) -> str:
    """Insert the run row and return its id. Scores are written separately."""
    from . import attribution

    state = attribution.get_state()
    run_id = f"live-{uuid.uuid4().hex[:16]}"
    run_dir(run_id)
    (run_dir(run_id) / "source.bin").write_bytes(source_bytes)

    conn.execute(
        "INSERT INTO live_run("
        " run_id, project_id, source_kind, source_name, stored_filename, source_sha256,"
        " byte_size, engine, width, height, level_count, mpp_x, mpp_y, objective_power,"
        " vendor, model_id, model_bundle_sha256, encoder_sha256, requested_by,"
        " created_at, latency_ms, tile_count, tiles_available, truncated, support_flags, notes"
        ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            run_id, project_id, source_kind, source_name, "source.bin",
            _digest(source_bytes), len(source_bytes), engine,
            (props or {}).get("width"), (props or {}).get("height"),
            (props or {}).get("level_count"), (props or {}).get("mpp_x"),
            (props or {}).get("mpp_y"), (props or {}).get("objective_power"),
            (props or {}).get("vendor"),
            attribution.RECOVERED_MODEL_ID, state["bundle_sha256"],
            config.ENCODER_CHECKPOINT_SHA256, requested_by, utc_now(),
            latency_ms, 0, 0, 0, "[]", None,
        ),
    )
    conn.commit()
    return run_id


def save_tiles(conn: sqlite3.Connection, run_id: str, tiles: list[dict]) -> None:
    """Write per-tile scores. Tiles that failed to decode carry NULL, never 0.0."""
    for t in tiles:
        conn.execute(
            "INSERT OR REPLACE INTO live_tile("
            " run_id, tile_index, x, y, width, height, predicted_class,"
            " non_tumor_score, viable_tumor_score, necrosis_score, top1_score,"
            " top_two_margin, normalized_entropy, confidence, support_flags,"
            " decode_error, tile_png_filename"
            ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id, t["index"], t["x"], t["y"], t["width"], t["height"],
                t.get("predicted_class"), t.get("scores", {}).get("NON_TUMOR"),
                t.get("scores", {}).get("VIABLE_TUMOR"), t.get("scores", {}).get("NECROSIS"),
                t.get("top1_score"), t.get("top_two_margin"), t.get("normalized_entropy"),
                t.get("confidence"), json.dumps(t.get("support_flags", [])), t.get("decode_error"),
                t.get("tile_png_filename"),
            ),
        )
    conn.commit()


def finish_run(
    conn: sqlite3.Connection,
    run_id: str,
    *,
    tile_count: int,
    tiles_available: int,
    truncated: bool,
    support_flags: list[str],
    notes: str | None,
) -> None:
    conn.execute(
        "UPDATE live_run SET tile_count = ?, tiles_available = ?, truncated = ?,"
        " support_flags = ?, notes = ? WHERE run_id = ?",
        (tile_count, tiles_available, int(truncated), json.dumps(support_flags), notes, run_id),
    )
    conn.commit()


def get_run(conn: sqlite3.Connection, run_id: str) -> dict | None:
    row = conn.execute("SELECT * FROM live_run WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        return None
    return {k: row[k] for k in row.keys()}


def get_tiles(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM live_tile WHERE run_id = ? ORDER BY tile_index", (run_id,)
    ).fetchall()
    out = []
    for r in rows:
        d = {k: r[k] for k in r.keys()}
        d["scores"] = (
            None if d["predicted_class"] is None else {
                "NON_TUMOR": d["non_tumor_score"],
                "VIABLE_TUMOR": d["viable_tumor_score"],
                "NECROSIS": d["necrosis_score"],
            }
        )
        d["support_flags"] = json.loads(d["support_flags"] or "[]")
        out.append(d)
    return out


def verify_run_artifacts(run: dict, tiles: list[dict]) -> str | None:
    """Verify the stored source and tile images before replaying a run."""
    run_id = str(run.get("run_id", ""))
    if not run_id or Path(run_id).name != run_id or "\\" in run_id:
        return "run identifier is invalid"
    directory = config.LIVE_RUNS_DIR / run_id
    source_name = run.get("stored_filename")
    if source_name != "source.bin":
        return "stored source filename is invalid"
    source = directory / source_name
    try:
        with source.open("rb") as handle:
            source_hash = hashlib.file_digest(handle, "sha256").hexdigest()
    except OSError:
        return "stored source image is missing"
    if source_hash != run.get("source_sha256"):
        return "stored source image does not match its recorded SHA-256"

    for tile in tiles:
        filename = tile.get("tile_png_filename")
        if filename is None:
            continue
        if not isinstance(filename, str) or Path(filename).name != filename or "\\" in filename:
            return "stored tile filename is invalid"
        tile_path = directory / filename
        try:
            with tile_path.open("rb") as handle:
                if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                    return "stored tile image is invalid"
        except OSError:
            return "stored tile image is missing"
    return None


def list_runs(conn: sqlite3.Connection, project_id: str, limit: int = 50) -> list[dict]:
    """Recent live runs for one project. Never another project's."""
    rows = conn.execute(
        "SELECT run_id, source_kind, source_name, created_at, tile_count, tiles_available,"
        " truncated, requested_by FROM live_run WHERE project_id = ?"
        " ORDER BY created_at DESC, run_id DESC LIMIT ?",
        (project_id, int(limit)),
    ).fetchall()
    return [{k: r[k] for k in r.keys()} for r in rows]


def delete_run(conn: sqlite3.Connection, run_id: str) -> None:
    conn.execute("DELETE FROM live_tile WHERE run_id = ?", (run_id,))
    conn.execute("DELETE FROM live_run WHERE run_id = ?", (run_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Mosaic
# ---------------------------------------------------------------------------
def render_mosaic(run_id: str, tiles: list[dict], cols: int, cell: int = 18) -> bytes:
    """One solid cell per tile, coloured by predicted class; grey if undecoded.

    Deliberately NOT a heatmap. Colour here encodes a discrete class per tile,
    not a continuous importance value, and a tile that failed to decode is grey
    rather than being coloured with its neighbours' class.
    """
    from PIL import Image

    cols = max(1, cols)
    rows_n = max(1, (len(tiles) + cols - 1) // cols)
    img = Image.new("RGB", (cols * cell, rows_n * cell), UNDECODED_COLOUR)
    cache: dict[tuple[int, int, int], Image.Image] = {}
    for t in tiles:
        colour = CLASS_COLOURS.get(t.get("predicted_class") or "", UNDECODED_COLOUR)
        swatch = cache.get(colour)
        if swatch is None:
            swatch = Image.new("RGB", (cell, cell), colour)
            cache[colour] = swatch
        img.paste(swatch, ((t["index"] % cols) * cell, (t["index"] // cols) * cell))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def grid_for(width: int, height: int, tile_px: int, stride: int | None) -> dict:
    """Deterministic tiling grid for a ``width`` x ``height`` field.

    Row-major, so tile index N maps to a stable (x, y). A final tile is added
    flush to the right/bottom edge when the stride would otherwise leave tissue
    unscored; that tile is smaller than ``tile_px``, which is why callers clamp
    tile width/height to the field.
    """
    # `stride or tile_px` would silently swallow stride=0 (0 is falsy) and turn
    # a caller mistake into a different, valid-looking grid.
    stride = tile_px if stride is None else int(stride)
    tile_px = int(tile_px)
    if stride < 1:
        raise LiveInferenceError(f"stride must be >= 1, got {stride}")
    if tile_px < 1:
        raise LiveInferenceError(f"tile_px must be >= 1, got {tile_px}")

    def axis(extent: int) -> list[int]:
        if extent <= tile_px:
            return [0]
        starts = list(range(0, extent - tile_px + 1, stride))
        if starts[-1] + tile_px < extent:
            starts.append(extent - tile_px)
        return starts

    xs, ys = axis(int(width)), axis(int(height))
    return {"cells": [(x, y) for y in ys for x in xs], "cols": len(xs), "rows": len(ys)}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def predict_patch_bytes(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    filename: str,
    data: bytes,
    requested_by: str,
) -> dict:
    """Single-patch import: one forward pass, one row."""
    from PIL import Image

    from . import attribution

    try:
        with Image.open(io.BytesIO(data)) as im:
            im.load()
            pil = im.convert("RGB")
    except Exception as exc:
        raise UnsupportedInput(f"could not decode {filename!r} as an image: {exc}") from exc

    t0 = time.time()
    state = attribution.get_state()
    prediction = _predict_array(state, pil)

    run_id = create_run(
        conn,
        project_id=project_id,
        source_kind="patch",
        source_name=filename,
        source_bytes=data,
        engine="pillow",
        props={"width": pil.size[0], "height": pil.size[1], "level_count": 1,
               "mpp_x": None, "mpp_y": None, "objective_power": None, "vendor": None},
        requested_by=requested_by,
        latency_ms=0.0,
    )
    run_dir(run_id).joinpath("tile-0000.png").write_bytes(_png(pil))
    save_tiles(conn, run_id, [{
        "index": 0, "x": 0, "y": 0, "width": pil.size[0], "height": pil.size[1],
        "predicted_class": prediction.predicted_class, "scores": prediction.scores,
        "top1_score": prediction.top1_score, "top_two_margin": prediction.top_two_margin,
        "normalized_entropy": prediction.normalized_entropy,
        "confidence": prediction.confidence, "support_flags": prediction.support_flags,
        "tile_png_filename": "tile-0000.png",
    }])
    finish_run(
        conn, run_id,
        tile_count=1, tiles_available=1, truncated=False,
        support_flags=prediction.support_flags,
        notes=prediction.caveat,
    )
    conn.execute("UPDATE live_run SET latency_ms = ? WHERE run_id = ?",
                 (round((time.time() - t0) * 1000, 2), run_id))
    conn.commit()

    return {
        "run": public_run(conn, run_id),
        "prediction": prediction.to_dict(),
        "mosaic_png_base64": None,
    }


def analyze_slide_bytes(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    filename: str,
    data: bytes,
    requested_by: str,
    tile_px: int | None = None,
    stride: int | None = None,
    max_tiles: int | None = None,
) -> dict:
    """Import a slide, tile it deterministically, score every tile.

    Reports ``truncated`` rather than silently dropping tiles when the grid is
    bigger than ``max_tiles``, and reports per-tile decode failures as grey
    cells rather than dropping them.
    """
    tile_px = int(tile_px or config.LIVE_TILE_PX)
    max_tiles = int(max_tiles or config.LIVE_MAX_TILES)
    suffix = Path(filename).suffix.lower()

    # OpenSlide needs a real path, so the bytes land in the run's own directory
    # before anything opens them. The name is ours, not the user's, so a
    # hostile filename cannot escape the runs directory.
    import tempfile

    from . import attribution

    t0 = time.time()
    state = attribution.get_state()
    scratch = Path(tempfile.mkdtemp(prefix="osteopatch-import-"))
    stored = scratch / f"import{suffix}"
    stored.write_bytes(data)

    try:
        slide = reader.open_slide(stored)
    except (reader.ReaderUnavailable, reader.SlideReadError) as exc:
        raise UnsupportedInput(f"{filename!r} could not be opened as a slide: {exc}") from exc

    try:
        props = slide.properties().to_dict()
        grid = grid_for(props["width"], props["height"], tile_px, stride)
        cells = grid["cells"]
        truncated = len(cells) > max_tiles
        scored_cells = cells[:max_tiles]

        run_id = create_run(
            conn, project_id=project_id, source_kind="slide", source_name=filename,
            source_bytes=data, engine=slide.engine, props=props,
            requested_by=requested_by, latency_ms=0.0,
        )
        out_dir = run_dir(run_id)

        tiles: list[dict] = []
        overall_flags: list[str] = []
        for i, (x, y) in enumerate(scored_cells):
            entry = {
                "index": i, "x": x, "y": y,
                "width": min(tile_px, props["width"]), "height": min(tile_px, props["height"]),
            }
            try:
                region = slide.read_region(x, y, 0, entry["width"], entry["height"]).convert("RGB")
                prediction = _predict_array(state, region)
            except Exception as exc:
                # A tile that cannot be read is a GREY CELL with a reason, not a
                # dropped tile and not a zero score.
                entry.update(decode_error=f"{type(exc).__name__}: {exc}", confidence=None)
                tiles.append(entry)
                continue
            for flag in prediction.support_flags:
                if flag not in overall_flags:
                    overall_flags.append(flag)
            entry.update(
                predicted_class=prediction.predicted_class, scores=prediction.scores,
                top1_score=prediction.top1_score, top_two_margin=prediction.top_two_margin,
                normalized_entropy=prediction.normalized_entropy,
                confidence=prediction.confidence, support_flags=prediction.support_flags,
            )
            entry["tile_png_filename"] = f"tile-{i:04d}.png"
            out_dir.joinpath(entry["tile_png_filename"]).write_bytes(_png(region))
            tiles.append(entry)

        save_tiles(conn, run_id, tiles)
        mosaic = render_mosaic(run_id, tiles, grid["cols"])
        out_dir.joinpath("mosaic.png").write_bytes(mosaic)

        notes = _slide_note(truncated, len(cells), len(scored_cells), tiles)
        finish_run(
            conn, run_id, tile_count=len(tiles), tiles_available=len(cells),
            truncated=truncated, support_flags=overall_flags, notes=notes,
        )
        conn.execute("UPDATE live_run SET latency_ms = ? WHERE run_id = ?",
                     (round((time.time() - t0) * 1000, 2), run_id))
        conn.commit()

        uncertain = sorted(
            (t for t in tiles if t.get("top_two_margin") is not None),
            key=lambda t: t["top_two_margin"],
        )[:10]
        return {
            "run": public_run(conn, run_id),
            "mosaic_png_base64": None,
            "mosaic": {
                "path_relative": f"live-runs/{run_id}/mosaic.png",
                "cols": grid["cols"], "rows": grid["rows"], "cell_px": 18,
                "class_colours": {k: list(v) for k, v in CLASS_COLOURS.items()},
                "undecoded_colour": list(UNDECODED_COLOUR),
            },
            "most_uncertain_tiles": [
                {"index": t["index"], "x": t["x"], "y": t["y"],
                 "predicted_class": t["predicted_class"],
                 "top_two_margin": t["top_two_margin"], "confidence": t["confidence"]}
                for t in uncertain
            ],
        }
    finally:
        slide.close()
        shutil.rmtree(scratch, ignore_errors=True)


def _slide_note(truncated: bool, available: int, scored: int, tiles: list[dict]) -> str:
    failed = [t for t in tiles if t.get("decode_error")]
    indeterminate = [t for t in tiles if t.get("confidence") == "indeterminate"]
    parts = []
    if truncated:
        parts.append(
            f"Only {scored} of {available} tiles were scored (max_tiles cap). "
            "The unscored region is NOT represented in the mosaic."
        )
    if failed:
        parts.append(f"{len(failed)} tile(s) could not be decoded and are grey in the mosaic.")
    if indeterminate:
        parts.append(
            f"{len(indeterminate)} tile(s) had a near-tied top-two score — treat those as no call."
        )
    parts.append("Scores are uncalibrated class scores from a recovered research head.")
    return " ".join(parts)


def _png(pil_image) -> bytes:
    # Derived PNGs carry RGB pixels, not arbitrarily large scanner ICC/text
    # metadata. The source file and its original metadata remain untouched.
    pil_image = pil_image.copy()
    pil_image.info.clear()
    buf = io.BytesIO()
    pil_image.save(buf, format="PNG")
    return buf.getvalue()


def public_run(conn: sqlite3.Connection, run_id: str) -> dict:
    """A stored run, with the honesty fields made explicit rather than buried."""
    row = get_run(conn, run_id)
    if row is None:
        return {}
    row["support_flags"] = json.loads(row["support_flags"] or "[]")
    row["truncated"] = bool(row["truncated"])
    row["is_live_inference"] = True
    row["is_corpus_prediction"] = False
    row["score_label"] = SCORE_LABEL
    return row


def mosaic_bytes(run_id: str) -> bytes | None:
    path = config.LIVE_RUNS_DIR / run_id / "mosaic.png"
    return path.read_bytes() if path.exists() else None


def tile_png_bytes(run_id: str, index: int) -> bytes | None:
    path = config.LIVE_RUNS_DIR / run_id / f"tile-{index:04d}.png"
    return path.read_bytes() if path.exists() else None
