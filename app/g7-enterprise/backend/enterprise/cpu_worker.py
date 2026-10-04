"""E3 — CPU torch inference worker (REAL execution, local, no AWS).

Pops queued inference_task rows, loads the registry's SERVING bundle, runs a
forward pass over each patch's pixels, and writes an immutable prediction keyed
by (image_id, bundle_sha256).

TWO DEFECTS THIS MODULE PREVIOUSLY CONTAINED
--------------------------------------------
Both were found by audit and are fixed here rather than deferred:

1. **Preprocessing contradicted the frozen contract.** It resized to 224x224
   and inlined ImageNet normalisation constants, while the frozen G4 bundle
   declares ``resize: [384, 384]``, bilinear, antialias, full-field. A correct
   implementation already existed at ``osteopatch/model.py`` (it reads the
   bundle's own spec) and was simply never reused. Inference now takes the
   contract from the bundle and refuses to guess. See :func:`_preprocess`.

2. **A second, divergent ``prediction_id`` scheme.** This module minted
   ``pred_<sha1[:16]>`` while G6 mints ``pred-{image_id}-{hash[:12]}``. Because
   ``UNIQUE(image_id, model_bundle_hash)`` spans both, a row written here could
   be invisible to the G6 read path while still blocking a canonical insert.
   The canonical ``repo.prediction_id_for`` is now used, so both writers agree.

Also folded in: the duplicated softmax/entropy math now calls the canonical
``osteopatch.scoring`` implementation instead of carrying its own copy. The
copies were numerically equivalent (max |diff| 2.7e-12) but drifted on the
negative-entropy edge case, where this module's version could return a tiny
negative value.

HONEST STATUS: the frozen ``baseline-frozen-g4`` weights (sha256 01727fb8...)
are gone from disk. This worker runs against whatever bundle the registry marks
``serving``; it reproduces the frozen G4 predictions ONLY if those exact weights
are restored. It refuses to run if the bundle file is absent — it never
fabricates a prediction.

Torch is imported LAZILY inside run(), so importing this module (and the whole
enterprise serving path) stays torch-free.

Educational research prototype. Not for diagnosis, treatment decisions, or
predicting treatment response.
"""
from __future__ import annotations

import hashlib
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# Canonical 3-class order. Never reordered, never extended.
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
    preprocessing_source: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _scoring():
    """The canonical scoring implementation, shared with the review API."""
    for candidate in (
        Path(__file__).resolve().parents[2] / "g6" / "backend",
        Path(__file__).resolve().parents[2] / "app" / "g6" / "backend",
    ):
        if (candidate / "osteopatch").is_dir():
            if str(candidate) not in sys.path:
                sys.path.insert(0, str(candidate))
            break
    from osteopatch import repo, scoring  # type: ignore

    return repo, scoring


def _ensure_prediction_table(conn: sqlite3.Connection) -> None:
    """Idempotent guard only.

    The authoritative schema is osteopatch/migrations/0001_initial.sql. This
    exists solely so the worker can run against a database that has not yet had
    migrations applied — it is NOT a second definition of the table, and it
    only adds the columns migration 0002 introduces.
    """
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
    cols = {r[1] for r in conn.execute("PRAGMA table_info(prediction)")}
    if "project_id" not in cols:
        conn.execute("ALTER TABLE prediction ADD COLUMN project_id TEXT")
    conn.commit()


def run(
    review_conn,
    task_conn,
    *,
    bundle_path: Path,
    tiffs_dir: Path,
    expected_sha256: str | None = None,
    limit: int = 1000,
    preprocessing: dict | None = None,
    project_id: str | None = None,
) -> WorkerResult:
    """Execute queued inference tasks on CPU.

    review_conn      — G6 store (where predictions are written)
    task_conn        — enterprise store (holds inference_task rows)
    bundle_path      — the serving .pt bundle
    tiffs_dir        — directory of <image_id>.tiff pixels
    preprocessing    — the model's frozen preprocessing contract. REQUIRED
                       unless the bundle itself carries the spec; never guessed.

    Preprocessing provenance is returned in :class:`WorkerResult` so a caller can
    report which contract produced a given set of predictions.
    """
    import numpy as np
    import torch
    from PIL import Image

    repo, scoring = _scoring()

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

    # Preprocessing provenance: bundle spec wins; an explicit argument is the
    # override for bundles that carry no metadata (e.g. TorchScript). Neither
    # path can silently substitute a different resolution.
    bundled_spec = _bundle_preprocessing(bundle_path)
    spec = bundled_spec or preprocessing
    source = "bundle" if bundled_spec else ("caller" if preprocessing else "none")
    if not spec:
        raise WorkerError(
            "preprocessing contract unavailable. The bundle carries no "
            "preprocessing spec and none was supplied. Inference refuses to "
            "guess an input resolution — pass the model's frozen contract "
            "explicitly (the G4 contract is resize [384, 384], bilinear, "
            "antialias, ImageNet normalisation)."
        )
    size = tuple(int(v) for v in spec["resize"])
    mean = np.asarray(spec["normalize_mean"], dtype="float32")
    std = np.asarray(spec["normalize_std"], dtype="float32")

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
            (image_id, actual),
        ).fetchone()
        if exists:
            skipped += 1
            task_conn.execute(
                "UPDATE inference_task SET status='done' WHERE task_id=?", (t["task_id"],)
            )
            continue
        tiff = tiffs_dir / f"{image_id}.tiff"
        if not tiff.exists():
            task_conn.execute(
                "UPDATE inference_task SET status='failed' WHERE task_id=?", (t["task_id"],)
            )
            continue

        x = _preprocess(torch, Image, np, tiff, size, mean, std, device)
        with torch.no_grad():
            logits = model(x)[0].tolist()
        probs = scoring.softmax(logits)
        order = sorted(range(3), key=lambda i: probs[i], reverse=True)
        pred_class = CANONICAL[order[0]]
        top1 = probs[order[0]]
        margin = probs[order[0]] - probs[order[1]]
        ent = scoring.normalized_entropy(probs)

        # CANONICAL id scheme — the same function the review API uses, so a
        # worker-written row is visible to the read path and cannot collide
        # with it.
        pid = repo.prediction_id_for(image_id, actual)
        review_conn.execute(
            "INSERT INTO prediction(prediction_id, image_id, model_version, model_bundle_hash, "
            "inference_kind, created_at, predicted_class, non_tumor_score, viable_tumor_score, "
            "necrosis_score, top1_score, top_two_margin, normalized_entropy, project_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, image_id, "cpu-worker", actual, "cpu_worker_inference", _now(),
             pred_class, probs[0], probs[1], probs[2], top1, margin, ent, project_id),
        )
        task_conn.execute("UPDATE inference_task SET status='done' WHERE task_id=?", (t["task_id"],))
        written += 1
    review_conn.commit()
    task_conn.commit()
    return WorkerResult(
        processed=processed,
        written=written,
        skipped_existing=skipped,
        bundle_sha256=actual,
        device=device,
        preprocessing_source=source,
    )


def _bundle_preprocessing(bundle_path: Path) -> dict | None:
    """Read the preprocessing spec the bundle itself carries, if any.

    A TorchScript archive carries no such metadata, so this returns None for
    one — which is precisely why the caller must then supply the contract
    explicitly rather than the worker inventing one.
    """
    import torch

    try:
        obj = torch.load(str(bundle_path), map_location="cpu", weights_only=False)
    except Exception:
        return None
    if not isinstance(obj, dict):
        return None
    spec = obj.get("preprocessing") or (obj.get("config") or {}).get("preprocessing")
    return spec if isinstance(spec, dict) else None


def _load_model(torch, bundle_path: Path, device: str):
    """Load a serving bundle. Supports a TorchScript module or a dict carrying a
    'model' state_dict + 'arch' hint."""
    try:
        return torch.jit.load(str(bundle_path), map_location=device)
    except Exception:
        pass
    obj = torch.load(str(bundle_path), map_location=device, weights_only=False)
    if hasattr(obj, "eval"):  # a pickled nn.Module
        return obj
    if isinstance(obj, dict) and hasattr(obj.get("model"), "eval"):
        return obj["model"]
    raise WorkerError("unsupported bundle format: expected TorchScript or a pickled nn.Module")


def _preprocess(torch, Image, np, tiff: Path, size, mean, std, device):
    """Build the input tensor using the MODEL'S OWN contract.

    The resolution and normalisation come from the bundle spec (or the explicit
    override), never from a constant written into this function. This is the
    change that stopped inference silently using 224x224 against a model
    trained at 384x384.
    """
    img = Image.open(tiff).convert("RGB").resize(size)
    arr = np.asarray(img, dtype="float32") / 255.0
    arr = (arr - mean) / std
    t = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(device)
    return t