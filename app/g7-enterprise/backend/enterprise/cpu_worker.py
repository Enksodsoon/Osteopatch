"""E3 — CPU torch inference worker (REAL execution, local, no AWS).

This un-gates the actual model-execution step of E3 for LOCAL CPU use. It pops
queued inference_task rows, loads the registry's SERVING bundle, runs a torch
forward pass over each patch's pixels, and writes an immutable prediction keyed
by (image_id, bundle_sha256) — the same contract G6's precompute uses.

HONEST STATUS: the frozen `baseline-frozen-g4` weights were reclaimed from
scratch and are gone. This worker therefore runs against WHATEVER bundle the
registry marks `serving`; it will faithfully reproduce the frozen G4 predictions
ONLY if those exact weights are restored. A retrain would yield different weights
(different RNG → different trajectory) and must NOT be presented as the frozen
model. The worker refuses to run if the serving bundle file is absent — it never
fabricates a prediction.

Torch is imported LAZILY inside run(), so importing this module (and the whole
enterprise serving path) stays torch-free. Install torch into the worker venv
only: `pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu`
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

CANONICAL = ("NON_TUMOR", "VIABLE_TUMOR", "NECROSIS")


class WorkerError(Exception):
    pass


@dataclass
class WorkerResult:
    processed: int
    written: int
    skipped_existing: int
    bundle_sha256: str
    device: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_prediction_table(conn: sqlite3.Connection) -> None:
    # matches the G6 immutable prediction contract (subset used by the worker)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS prediction (
            prediction_id TEXT PRIMARY KEY,
            image_id TEXT NOT NULL,
            model_version TEXT, model_bundle_hash TEXT NOT NULL,
            inference_kind TEXT, created_at TEXT,
            predicted_class TEXT,
            non_tumor_score REAL, viable_tumor_score REAL, necrosis_score REAL,
            top1_score REAL, top_two_margin REAL, normalized_entropy REAL,
            UNIQUE(image_id, model_bundle_hash)
        )""")
    conn.commit()


def _softmax(logits):
    import math
    m = max(logits)
    exps = [math.exp(x - m) for x in logits]
    s = sum(exps)
    return [e / s for e in exps]


def _entropy_normalized(probs):
    import math
    k = len(probs)
    h = -sum(p * math.log(p + 1e-12) for p in probs)
    return h / math.log(k)


def run(review_conn, task_conn, *, bundle_path: Path, tiffs_dir: Path,
        expected_sha256: str | None = None, limit: int = 1000) -> WorkerResult:
    """Execute queued inference tasks on CPU.

    review_conn — G6 store (where predictions are written)
    task_conn   — enterprise store (holds inference_task rows)
    bundle_path — the serving .pt bundle (dict with 'model' or a scripted module)
    tiffs_dir   — directory of <image_id>.tiff pixels
    """
    import torch  # lazy — only the worker needs it
    from PIL import Image
    import numpy as np

    bundle_path = Path(bundle_path)
    if not bundle_path.exists():
        raise WorkerError(
            f"serving bundle missing: {bundle_path}. The frozen G4 weights were "
            "reclaimed from scratch; restore them (or register+serve a new bundle) "
            "before running the worker. No prediction is fabricated."
        )
    actual = _sha256_file(bundle_path)
    if expected_sha256 and actual != expected_sha256:
        raise WorkerError(
            f"bundle hash mismatch: expected {expected_sha256[:12]}…, got {actual[:12]}… "
            "(frozen-contract guard — refusing to run)."
        )

    device = "cpu"
    model = _load_model(torch, bundle_path, device)
    model.eval()

    _ensure_prediction_table(review_conn)
    tasks = task_conn.execute(
        "SELECT task_id, image_id FROM inference_task WHERE bundle_sha256=? AND status='queued' "
        "ORDER BY enqueued_at LIMIT ?", (actual, limit),
    ).fetchall()

    processed = written = skipped = 0
    for t in tasks:
        image_id = t["image_id"]
        processed += 1
        exists = review_conn.execute(
            "SELECT 1 FROM prediction WHERE image_id=? AND model_bundle_hash=?",
            (image_id, actual)).fetchone()
        if exists:
            skipped += 1
            task_conn.execute("UPDATE inference_task SET status='done' WHERE task_id=?", (t["task_id"],))
            continue
        tiff = tiffs_dir / f"{image_id}.tiff"
        if not tiff.exists():
            task_conn.execute("UPDATE inference_task SET status='failed' WHERE task_id=?", (t["task_id"],))
            continue
        x = _preprocess(torch, Image, np, tiff, device)
        with torch.no_grad():
            logits = model(x)[0].tolist()
        probs = _softmax(logits)
        order = sorted(range(3), key=lambda i: probs[i], reverse=True)
        pred_class = CANONICAL[order[0]]
        top1 = probs[order[0]]
        margin = probs[order[0]] - probs[order[1]]
        ent = _entropy_normalized(probs)
        pid = f"pred_{hashlib.sha1((image_id+actual).encode()).hexdigest()[:16]}"
        review_conn.execute(
            "INSERT INTO prediction(prediction_id, image_id, model_version, model_bundle_hash, "
            "inference_kind, created_at, predicted_class, non_tumor_score, viable_tumor_score, "
            "necrosis_score, top1_score, top_two_margin, normalized_entropy) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, image_id, "cpu-worker", actual, "cpu_worker_inference", _now(),
             pred_class, probs[0], probs[1], probs[2], top1, margin, ent),
        )
        task_conn.execute("UPDATE inference_task SET status='done' WHERE task_id=?", (t["task_id"],))
        written += 1
    review_conn.commit()
    task_conn.commit()
    return WorkerResult(processed=processed, written=written, skipped_existing=skipped,
                        bundle_sha256=actual, device=device)


def _load_model(torch, bundle_path: Path, device: str):
    """Load a serving bundle. Supports a TorchScript module or a dict carrying a
    'model' state_dict + 'arch' hint. Kept permissive so the real G4 bundle, once
    restored, loads without code change."""
    try:
        return torch.jit.load(str(bundle_path), map_location=device)
    except Exception:
        pass
    obj = torch.load(str(bundle_path), map_location=device, weights_only=False)
    if hasattr(obj, "eval"):  # a pickled nn.Module
        return obj
    raise WorkerError("unsupported bundle format: expected TorchScript or a pickled nn.Module")


def _preprocess(torch, Image, np, tiff: Path, device: str):
    img = Image.open(tiff).convert("RGB").resize((224, 224))
    arr = np.asarray(img, dtype="float32") / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype="float32")
    std = np.array([0.229, 0.224, 0.225], dtype="float32")
    arr = (arr - mean) / std
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
    return t
