"""Shared pytest fixtures: an isolated temp SQLite DB + seeded data + client.

Tests do NOT depend on torch or the real bundle for the API/logic paths — they
seed deterministic synthetic predictions. A separate torch-gated test exercises
the real bundle hash + load when torch is importable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from osteopatch import db, repo  # noqa: E402

BUNDLE_HASH = "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63"

# Deterministic synthetic patches: (image_id, group, label, qc_status, elig, qc_flag, scores)
SEED_IMAGES = [
    # ambiguous (small margin) — should rank FIRST under priority
    ("img-ambiguous", "Case-3", "VIABLE_TUMOR", "PASS", 1, 0, [0.33, 0.34, 0.33]),
    # clear NON_TUMOR — large margin, ranks last
    ("img-clear-nt", "Case-4", "NON_TUMOR", "PASS", 1, 0, [0.90, 0.05, 0.05]),
    # mid NECROSIS
    ("img-mid-nec", "Case-48", "NECROSIS", "PASS", 1, 0, [0.20, 0.25, 0.55]),
    # a DATA-QC-flagged, training-ineligible row (metadata only, still predicted)
    ("img-qc-review", "P9", "MIXED_VIABLE_NECROTIC", "REVIEW", 0, 1, [0.40, 0.35, 0.25]),
]


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "test.sqlite3"
    c = db.connect(db_path)
    db.run_migrations(c)
    # seed source_qc
    for iid, grp, label, qc, elig, flag, _ in SEED_IMAGES:
        c.execute(
            "INSERT INTO source_qc(image_id, source_group, original_label, "
            "primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, "
            "tiff_filename) VALUES (?,?,?,?,?,?,?,?)",
            (iid, grp, label, qc, elig, flag, "flag" if flag else None, f"{iid}.tiff"),
        )
    # seed immutable predictions
    for iid, *_rest in SEED_IMAGES:
        scores = _rest[-1]
        repo.upsert_prediction(c, iid, BUNDLE_HASH, "baseline-frozen-g4", scores)
    c.commit()
    return c


@pytest.fixture()
def client(conn, monkeypatch):
    from fastapi.testclient import TestClient

    from osteopatch import app as app_module

    app_module.set_conn(conn)
    return TestClient(app_module.app)


def pred_id(image_id: str) -> str:
    return repo.prediction_id_for(image_id, BUNDLE_HASH)
