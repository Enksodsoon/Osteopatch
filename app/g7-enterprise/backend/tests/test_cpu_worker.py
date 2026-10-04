"""E3 CPU worker test — proves the real inference pipeline on CPU.

Uses a SYNTHETIC 3-class TorchScript model + synthetic TIFFs so the full path
(load bundle -> preprocess -> forward -> softmax -> write immutable prediction ->
idempotent re-run) is exercised with real torch on CPU, WITHOUT the (missing)
frozen G4 weights. Skips cleanly if torch is not installed, since torch is an
optional worker-only dependency.
"""
import sqlite3

import pytest

torch = pytest.importorskip("torch", reason="torch is a worker-only optional dep")


@pytest.fixture()
def synth(tmp_path):
    import torch, torch.nn as nn
    from PIL import Image
    import numpy as np

    # tiny deterministic 3-class CNN -> TorchScript bundle
    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            self.p = nn.AdaptiveAvgPool2d(1)
            self.fc = nn.Linear(3, 3)
        def forward(self, x):
            return self.fc(self.p(x).flatten(1))

    torch.manual_seed(0)
    m = Net().eval()
    bundle = tmp_path / "synthetic_bundle.pt"
    torch.jit.save(torch.jit.script(m), str(bundle))

    tiffs = tmp_path / "tiffs"; tiffs.mkdir()
    for i, color in enumerate([(200, 30, 30), (30, 200, 30), (30, 30, 200)]):
        Image.fromarray(np.full((64, 64, 3), color, dtype="uint8")).save(tiffs / f"img{i}.tiff")

    return bundle, tiffs


def test_cpu_worker_runs_and_is_idempotent(tmp_path, synth):
    from enterprise import cpu_worker, inference, store
    bundle, tiffs = synth

    review = sqlite3.connect(tmp_path / "g6.sqlite3"); review.row_factory = sqlite3.Row
    ent = store.connect(tmp_path / "ent.sqlite3")

    sha = cpu_worker._sha256_file(bundle)
    inference.enqueue(ent, image_ids=["img0", "img1", "img2"], bundle_sha256=sha)
    assert inference.queue_depth(ent) == 3

    r = cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256=sha)
    assert r.processed == 3 and r.written == 3 and r.device == "cpu"
    assert inference.queue_depth(ent) == 0  # all drained

    # predictions are real + well-formed (scores sum ~1, valid class)
    rows = review.execute("SELECT * FROM prediction").fetchall()
    assert len(rows) == 3
    for row in rows:
        s = row["non_tumor_score"] + row["viable_tumor_score"] + row["necrosis_score"]
        assert abs(s - 1.0) < 1e-5
        assert row["predicted_class"] in cpu_worker.CANONICAL
        assert row["inference_kind"] == "cpu_worker_inference"

    # idempotent re-enqueue is a no-op (tasks already done -> nothing re-queued),
    # so a second run writes nothing new and the prediction count is unchanged.
    again = inference.enqueue(ent, image_ids=["img0", "img1", "img2"], bundle_sha256=sha)
    assert again["newly_queued"] == 0            # dedup at enqueue
    r2 = cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256=sha)
    assert r2.written == 0                       # nothing new written
    assert review.execute("SELECT COUNT(*) FROM prediction").fetchone()[0] == 3

    # even if a task is force-requeued, the (image_id, bundle) unique guard makes
    # the worker SKIP the existing prediction rather than duplicate it.
    ent.execute("UPDATE inference_task SET status='queued' WHERE image_id='img0'")
    ent.commit()
    r3 = cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256=sha)
    assert r3.processed == 1 and r3.written == 0 and r3.skipped_existing == 1
    assert review.execute("SELECT COUNT(*) FROM prediction").fetchone()[0] == 3


def test_worker_refuses_missing_bundle(tmp_path):
    from enterprise import cpu_worker, store
    review = sqlite3.connect(tmp_path / "g6.sqlite3"); review.row_factory = sqlite3.Row
    ent = store.connect(tmp_path / "ent.sqlite3")
    with pytest.raises(cpu_worker.WorkerError):
        cpu_worker.run(review, ent, bundle_path=tmp_path / "nope.pt", tiffs_dir=tmp_path)


def test_worker_refuses_hash_mismatch(tmp_path, synth):
    from enterprise import cpu_worker, store
    bundle, tiffs = synth
    review = sqlite3.connect(tmp_path / "g6.sqlite3"); review.row_factory = sqlite3.Row
    ent = store.connect(tmp_path / "ent.sqlite3")
    with pytest.raises(cpu_worker.WorkerError):
        cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256="deadbeef" * 8)
