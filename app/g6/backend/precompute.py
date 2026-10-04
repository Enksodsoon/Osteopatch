"""One-time G4 prototype-inference precompute over all decoded patches.

Run under a venv that has torch/torchvision/PIL (e.g. the existing ingestion
venv). It:

  1. Re-verifies the G4 bundle SHA-256 and REFUSES on mismatch.
  2. Migrates the SQLite schema and loads source/QC metadata.
  3. Loads the frozen bundle and runs PROTOTYPE INFERENCE on every patch that
     has a decoded TIFF, storing immutable predictions.
  4. Dedups by (image_id + model_bundle_hash): an existing prediction row is
     REUSED, never recomputed or duplicated — so re-running is cheap and safe.

This is prototype inference, NOT an independent evaluation. The G4 OOF LOGO
result remains the immutable performance evidence.

Usage:
    <torch-venv>\\Scripts\\python.exe precompute.py [--limit N]
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Make the osteopatch package importable when run as a loose script.
BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from osteopatch import config, db, metadata, model, repo  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="debug: cap #images")
    args = ap.parse_args()

    print(f"[precompute] bundle: {config.BUNDLE_PATH}")
    # 1. hash guard
    bundle_hash = model.verify_bundle_hash()
    print(f"[precompute] bundle SHA-256 verified: {bundle_hash}")

    # 2. db + metadata
    conn = db.connect()
    applied = db.run_migrations(conn)
    print(f"[precompute] migrations applied: {applied or 'none (already current)'}")
    summ = metadata.load_source_metadata(conn)
    print(f"[precompute] source/QC metadata: {summ}")

    # 3. load model
    loaded = model.load_model()
    print(
        f"[precompute] model loaded: version={loaded.model_version} "
        f"classes={loaded.classes}"
    )

    rows = list(
        conn.execute("SELECT image_id, tiff_filename FROM source_qc ORDER BY image_id")
    )
    if args.limit:
        rows = rows[: args.limit]

    created = reused = missing = 0
    t0 = time.time()
    for i, r in enumerate(rows, start=1):
        image_id = r["image_id"]
        # dedup fast-path
        existing = conn.execute(
            "SELECT 1 FROM prediction WHERE image_id = ? AND model_bundle_hash = ?",
            (image_id, bundle_hash),
        ).fetchone()
        if existing:
            reused += 1
            continue
        tiff = config.TIFFS_DIR / r["tiff_filename"]
        if not tiff.exists():
            missing += 1
            continue
        scores = model.infer_scores(loaded, tiff)
        repo.upsert_prediction(
            conn, image_id, bundle_hash, config.MODEL_VERSION, scores
        )
        created += 1
        if i % 100 == 0:
            conn.commit()
            print(f"[precompute] {i}/{len(rows)} (created={created} reused={reused})")
    conn.commit()

    total_pred = conn.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
    dt = round(time.time() - t0, 1)
    print(
        f"[precompute] DONE in {dt}s — created={created} reused={reused} "
        f"missing_tiff={missing} total_predictions={total_pred}"
    )
    print(f"[precompute] db: {config.DB_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
