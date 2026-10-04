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
    import numpy as np
    import torch
    import torch.nn as nn
    from PIL import Image

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


#: The frozen G4 preprocessing contract. Declared here explicitly because the
#: synthetic TorchScript bundle carries no metadata, and the worker refuses to
#: guess an input resolution. This mirrors the real contract at
#: aidlc-docs/inception/model/g4/final-bundle.json.
G4_PREPROCESSING = {
    "resize": [384, 384],
    "interpolation": "bilinear",
    "antialias": True,
    "normalize_mean": [0.485, 0.456, 0.406],
    "normalize_std": [0.229, 0.224, 0.225],
}


def test_cpu_worker_runs_and_is_idempotent(tmp_path, synth):
    from enterprise import cpu_worker, inference, store
    bundle, tiffs = synth

    review = sqlite3.connect(tmp_path / "g6.sqlite3"); review.row_factory = sqlite3.Row
    ent = store.connect(tmp_path / "ent.sqlite3")

    sha = cpu_worker._sha256_file(bundle)
    inference.enqueue(ent, image_ids=["img0", "img1", "img2"], bundle_sha256=sha)
    assert inference.queue_depth(ent) == 3

    r = cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256=sha,
                       preprocessing=G4_PREPROCESSING)
    assert r.processed == 3 and r.written == 3 and r.device == "cpu"
    assert r.preprocessing_source == "caller"
    assert inference.queue_depth(ent) == 0  # all drained

    # predictions are real + well-formed (scores sum ~1, valid class)
    rows = review.execute("SELECT * FROM prediction").fetchall()
    assert len(rows) == 3
    for row in rows:
        s = row["non_tumor_score"] + row["viable_tumor_score"] + row["necrosis_score"]
        assert abs(s - 1.0) < 1e-5
        assert row["predicted_class"] in cpu_worker.CANONICAL
        assert row["inference_kind"] == "cpu_worker_inference"

    # The prediction id uses the CANONICAL scheme shared with the review API.
    # A private scheme here would be invisible to the read path while still
    # colliding on UNIQUE(image_id, model_bundle_hash).
    from osteopatch import repo as g6_repo  # type: ignore

    for row in rows:
        assert row["prediction_id"] == g6_repo.prediction_id_for(
            row["image_id"], row["model_bundle_hash"]
        )

    # Entropy is never negative (the old local copy could return ~-1e-12).
    for row in rows:
        assert row["normalized_entropy"] >= 0.0
        assert row["top_two_margin"] >= -1e-9

    # idempotent re-enqueue is a no-op (tasks already done -> nothing re-queued),
    # so a second run writes nothing new and the prediction count is unchanged.
    again = inference.enqueue(ent, image_ids=["img0", "img1", "img2"], bundle_sha256=sha)
    assert again["newly_queued"] == 0            # dedup at enqueue
    r2 = cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256=sha,
                        preprocessing=G4_PREPROCESSING)
    assert r2.written == 0                       # nothing new written
    assert review.execute("SELECT COUNT(*) FROM prediction").fetchone()[0] == 3

    # even if a task is force-requeued, the (image_id, bundle) unique guard makes
    # the worker SKIP the existing prediction rather than duplicate it.
    ent.execute("UPDATE inference_task SET status='queued' WHERE image_id='img0'")
    ent.commit()
    r3 = cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256=sha,
                        preprocessing=G4_PREPROCESSING)
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
        cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs, expected_sha256="deadbeef" * 8,
                       preprocessing=G4_PREPROCESSING)


def test_worker_refuses_to_guess_preprocessing(tmp_path, synth):
    """No bundle spec and no explicit contract => refuse, never assume 224.

    This is the regression guard for the defect where the worker silently
    resized to 224x224 against a model trained at 384x384.
    """
    from enterprise import cpu_worker, store
    bundle, tiffs = synth
    review = sqlite3.connect(tmp_path / "g6.sqlite3"); review.row_factory = sqlite3.Row
    ent = store.connect(tmp_path / "ent.sqlite3")
    with pytest.raises(cpu_worker.WorkerError, match="preprocessing"):
        cpu_worker.run(review, ent, bundle_path=bundle, tiffs_dir=tiffs,
                       expected_sha256=cpu_worker._sha256_file(bundle))


def test_worker_uses_the_supplied_contract_not_a_constant(tmp_path, synth):
    """Changing the contract changes the tensor the model sees."""
    import numpy as np
    from enterprise import cpu_worker
    bundle, tiffs = synth
    tiff = tiffs / "img0.tiff"

    import torch

    def make(size):
        return cpu_worker._preprocess(
            torch, __import__("PIL.Image", fromlist=["Image"]), np, tiff,
            size, np.asarray([0.485, 0.456, 0.406], dtype="float32"),
            np.asarray([0.229, 0.224, 0.225], dtype="float32"), "cpu",
        )

    assert tuple(make((384, 384)).shape) == (1, 3, 384, 384)
    assert tuple(make((224, 224)).shape) == (1, 3, 224, 224)
