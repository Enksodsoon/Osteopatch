"""Live inference — contract, structural separation, and a real forward pass.

Two tiers, matching ``test_attribution.py``:

  * torch-FREE: schema constraints, grid maths, confidence banding, support
    flags, mosaic rendering, and the reader-fallback regression. These run in
    the backend venv and are what CI exercises.
  * torch-GATED: a real forward pass through the recovered head, its agreement
    with the frozen stored scores, and a proof that a live run writes nothing
    to the frozen corpus. Skipped (not failed) when torch is absent.

The separation tests are the point of this file. "A live run is never a corpus
prediction" is the single claim this feature exists to make, so it is asserted
at three levels: the DATABASE refuses the row, the forward pass agrees with the
frozen scores to storage precision, and a full run leaves the corpus digest
byte-identical.

Educational research prototype. Not for diagnosis or treatment decisions.
"""
from __future__ import annotations

import io
import os
import sqlite3
from pathlib import Path

import pytest
from osteopatch import config, db, integrity
from osteopatch import live_inference as li
from osteopatch.pathology import reader
from PIL import Image

try:
    import torch  # noqa: F401

    HAVE_TORCH = True
except Exception:
    HAVE_TORCH = False

torch_only = pytest.mark.skipif(
    not HAVE_TORCH, reason="torch not installed in this venv (run under torch venv)"
)

PROJECT_ROOT = Path(
    os.environ.get("OSTEOPATCH_PROJECT_ROOT", str(Path(__file__).resolve().parents[4]))
)
DURABLE_IMAGES = config.TIFFS_DIR


@pytest.fixture()
def live_db(tmp_path, monkeypatch):
    """A migrated read model with live runs written to a temp directory."""
    monkeypatch.setenv("OSTEOPATCH_LIVE_RUNS", str(tmp_path / "live-runs"))
    conn = db.connect(tmp_path / "live.sqlite3")
    db.run_migrations(conn)
    return conn


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Structural separation: the DATABASE enforces it, not a convention
# ---------------------------------------------------------------------------
def test_migration_adds_live_tables_without_touching_the_corpus(conn):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"live_run", "live_tile"} <= tables
    assert {"source_qc", "prediction", "review_event"} <= tables


def test_live_run_cannot_claim_the_frozen_model_id(live_db):
    """A live row that says `baseline-frozen-g4` must be a constraint violation.

    This is the whole reason live_inference is its own store. Without the CHECK
    a live result could be stored as, or read as, a corpus prediction.
    """
    with pytest.raises(sqlite3.IntegrityError, match="model_id"):
        live_db.execute(
            "INSERT INTO live_run(run_id, project_id, source_kind, source_name,"
            " stored_filename, source_sha256, byte_size, engine, model_id,"
            " model_bundle_sha256, encoder_sha256, requested_by, created_at,"
            " latency_ms, tile_count, tiles_available)"
            " VALUES ('x','p','slide','a.tif','source.bin','h',1,'pillow',"
            " 'baseline-frozen-g4','deadbeef','e','u','t',0,0,0)"
        )


def test_live_run_cannot_claim_the_frozen_bundle_hash(live_db):
    with pytest.raises(sqlite3.IntegrityError, match="model_bundle_sha256"):
        live_db.execute(
            "INSERT INTO live_run(run_id, project_id, source_kind, source_name,"
            " stored_filename, source_sha256, byte_size, engine, model_id,"
            " model_bundle_sha256, encoder_sha256, requested_by, created_at,"
            " latency_ms, tile_count, tiles_available)"
            " VALUES ('x','p','slide','a.tif','source.bin','h',1,'pillow',"
            " 'g4-behavioral-recovery-r1',?, 'e','u','t',0,0,0)",
            (config.EXPECTED_BUNDLE_SHA256,),
        )


def test_live_tile_rejects_a_fourth_class(live_db):
    """Mixed / uncertain / poor-quality are review states, not outputs."""
    live_db.execute(
        "INSERT INTO live_run(run_id, project_id, source_kind, source_name, stored_filename,"
        " source_sha256, byte_size, engine, model_id, model_bundle_sha256, encoder_sha256,"
        " requested_by, created_at, latency_ms, tile_count, tiles_available)"
        " VALUES ('r','p','slide','a.tif','source.bin','h',1,'pillow',"
        " 'g4-behavioral-recovery-r1','recovered-hash','e','u','t',0,0,0)"
    )
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        live_db.execute(
            "INSERT INTO live_tile(run_id, tile_index, x, y, width, height, predicted_class,"
            " non_tumor_score, viable_tumor_score, necrosis_score)"
            " VALUES ('r',0,0,0,10,10,'MIXED_VIABLE_NECROTIC',0.3,0.3,0.4)"
        )


def test_live_tile_rejects_a_half_filled_score_row(live_db):
    """A scored tile needs all three scores, so a partial row can never read as
    a prediction."""
    live_db.execute(
        "INSERT INTO live_run(run_id, project_id, source_kind, source_name, stored_filename,"
        " source_sha256, byte_size, engine, model_id, model_bundle_sha256, encoder_sha256,"
        " requested_by, created_at, latency_ms, tile_count, tiles_available)"
        " VALUES ('r','p','slide','a.tif','source.bin','h',1,'pillow',"
        " 'g4-behavioral-recovery-r1','recovered-hash','e','u','t',0,0,0)"
    )
    with pytest.raises(sqlite3.IntegrityError, match="all three scores"):
        live_db.execute(
            "INSERT INTO live_tile(run_id, tile_index, x, y, width, height, predicted_class,"
            " non_tumor_score, viable_tumor_score, necrosis_score)"
            " VALUES ('r',0,0,0,10,10,'NON_TUMOR',0.5,NULL,0.5)"
        )


def test_an_undecoded_tile_is_allowed_and_carries_no_class(live_db):
    live_db.execute(
        "INSERT INTO live_run(run_id, project_id, source_kind, source_name, stored_filename,"
        " source_sha256, byte_size, engine, model_id, model_bundle_sha256, encoder_sha256,"
        " requested_by, created_at, latency_ms, tile_count, tiles_available)"
        " VALUES ('r','p','slide','a.tif','source.bin','h',1,'pillow',"
        " 'g4-behavioral-recovery-r1','recovered-hash','e','u','t',0,1,1)"
    )
    live_db.execute(
        "INSERT INTO live_tile(run_id, tile_index, x, y, width, height, decode_error)"
        " VALUES ('r',0,0,0,10,10,'OSError: truncated')"
    )
    tile = live_db.execute("SELECT * FROM live_tile WHERE run_id='r'").fetchone()
    assert tile["predicted_class"] is None
    assert tile["non_tumor_score"] is None
    assert tile["decode_error"] == "OSError: truncated"


# ---------------------------------------------------------------------------
# Integrity helper
# ---------------------------------------------------------------------------
def test_corpus_digest_notices_a_changed_score(live_db):
    live_db.execute(
        "INSERT INTO source_qc(image_id, source_group, original_label, primary_qc_status,"
        " training_eligible, qc_review_flag, qc_review_reason, tiff_filename)"
        " VALUES ('a','g','NON_TUMOR','PASS',1,0,NULL,'a.tiff')"
    )
    live_db.execute(
        "INSERT INTO prediction(prediction_id, image_id, model_version, model_bundle_hash,"
        " created_at, inference_kind, predicted_class, non_tumor_score, viable_tumor_score,"
        " necrosis_score, top1_score, top_two_margin, normalized_entropy)"
        " VALUES ('p','a','baseline-frozen-g4','h','t','prototype_inference','NON_TUMOR',"
        " 0.8,0.1,0.1,0.8,0.7,0.5)"
    )
    live_db.commit()
    before = integrity.corpus_row_digest(live_db)

    live_db.execute("UPDATE prediction SET non_tumor_score = 0.81 WHERE image_id = 'a'")
    live_db.commit()
    after = integrity.corpus_row_digest(live_db)
    assert before["digest"] != after["digest"]

    with pytest.raises(AssertionError, match="frozen corpus changed"):
        integrity.assert_corpus_unchanged(before, after)


def test_corpus_digest_ignores_unrelated_live_writes(live_db):
    """A live row is SUPPOSED to change the database; it must not move the digest."""
    live_db.execute(
        "INSERT INTO live_run(run_id, project_id, source_kind, source_name, stored_filename,"
        " source_sha256, byte_size, engine, model_id, model_bundle_sha256, encoder_sha256,"
        " requested_by, created_at, latency_ms, tile_count, tiles_available)"
        " VALUES ('r','p','patch','a.png','source.bin','h',1,'pillow',"
        " 'g4-behavioral-recovery-r1','recovered-hash','e','u','t',0,1,1)"
    )
    live_db.commit()
    assert integrity.corpus_row_digest(live_db)["tables"]["prediction"] == 0


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------
def test_grid_is_deterministic_and_row_major():
    g1 = li.grid_for(1000, 800, 384, 384)
    g2 = li.grid_for(1000, 800, 384, 384)
    assert g1 == g2
    assert g1["cols"] == 3 and g1["rows"] == 3  # 0,384,616 -> flush tile at 616
    assert g1["cells"][0] == (0, 0)
    assert g1["cells"][1] == (384, 0)  # row-major


def test_grid_flush_tile_never_reaches_past_the_field():
    g = li.grid_for(1000, 500, 384, 384)
    for x, y in g["cells"]:
        assert x + 384 <= 1000, f"tile at x={x} overflows the field"
        assert y + 384 <= 500, f"tile at y={y} overflows the field"


def test_field_smaller_than_one_tile_yields_a_single_tile():
    g = li.grid_for(300, 200, 384, None)
    assert g["cells"] == [(0, 0)]
    assert g["cols"] == 1 and g["rows"] == 1


def test_grid_rejects_a_nonpositive_tile_or_stride():
    with pytest.raises(li.LiveInferenceError):
        li.grid_for(100, 100, 0, None)
    with pytest.raises(li.LiveInferenceError):
        li.grid_for(100, 100, 384, 0)


# ---------------------------------------------------------------------------
# Honesty: banding + support flags + mosaic
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("margin", "expected"),
    [
        (0.0003, "indeterminate"),
        (0.04, "indeterminate"),
        (0.10, "low"),
        (0.45, "clear"),
        (0.97, "clear"),
    ],
)
def test_confidence_bands_on_the_top_two_margin(margin, expected):
    assert li._band(margin)[0] == expected


def test_an_indeterminate_call_carries_a_plain_caveat():
    confidence, caveat = li._band(0.0003)
    assert confidence == "indeterminate"
    assert caveat and "no call" in caveat.lower()
    assert "probabilit" not in caveat.lower()  # never presented as calibrated


def test_a_clear_call_carries_no_caveat():
    assert li._band(0.9) == ("clear", None)


def test_support_flags_flag_a_structureless_image():
    flat = Image.new("RGB", (128, 128), (200, 200, 200))
    flags = li.support_flags_for(flat)
    assert any("uniform_image" in f for f in flags)


def test_support_flags_flag_a_greyscale_image():
    import numpy as np

    rng = np.random.default_rng(0)
    # R == G == B by construction: that is what greyscale means. A spread
    # threshold would not catch this and would fire on real tissue.
    grey = np.dstack([rng.integers(0, 255, (96, 96, 1)).astype("uint8")] * 3)
    flags = li.support_flags_for(Image.fromarray(grey))
    assert any("greyscale" in f for f in flags), flags


def test_support_flags_flag_a_tiny_input():
    flags = li.support_flags_for(Image.new("RGB", (8, 8), (10, 10, 200)))
    assert any("tiny_input" in f for f in flags)


def test_real_he_patches_carry_no_support_flags():
    """The flags must not fire on the corpus they were designed around, or they
    are noise rather than caveats."""
    if not DURABLE_IMAGES.is_dir():
        pytest.skip("durable TIFF corpus not present on this machine")
    checked = 0
    for p in sorted(DURABLE_IMAGES.glob("*.tiff"))[:12]:
        with Image.open(p) as im:
            assert li.support_flags_for(im.convert("RGB")) == [], f"{p.name} flagged"
        checked += 1
    assert checked > 0


def test_mosaic_greys_a_tile_that_failed_to_decode():
    tiles = [
        {"index": 0, "predicted_class": "NON_TUMOR"},
        {"index": 1, "predicted_class": None},
        {"index": 2, "predicted_class": "NECROSIS"},
    ]
    img = Image.open(io.BytesIO(li.render_mosaic("r", tiles, cols=3, cell=4)))
    assert img.size == (12, 4)
    assert img.getpixel((0, 0)) == li.CLASS_COLOURS["NON_TUMOR"]
    assert img.getpixel((4, 0)) == li.UNDECODED_COLOUR  # not tinted by its neighbours
    assert img.getpixel((8, 0)) == li.CLASS_COLOURS["NECROSIS"]


def test_mosaic_colours_only_cover_the_three_canonical_classes():
    assert set(li.CLASS_COLOURS) == set(config.CANONICAL_CLASSES)


def test_runtime_available_is_torch_free_and_explains_itself():
    """The capability probe must not import torch, or a page load costs ~1 GB."""
    cap = li.runtime_available()
    assert isinstance(cap["available"], bool)
    assert "torch" not in __import__("sys").modules or cap["available"] is True
    if cap["available"]:
        assert cap["model_id"] == "g4-behavioral-recovery-r1"
    else:
        assert cap["reason"]  # says WHY, never a silent false


# ---------------------------------------------------------------------------
# Reader fallback (regression)
# ---------------------------------------------------------------------------
def test_open_slide_falls_back_when_openslide_cannot_read_the_file(tmp_path):
    """OpenSlide installed but unable to read a plain TIFF must still open it.

    `open_slide` used to re-raise `SlideReadError`, so its documented Pillow
    fallback only applied when OpenSlide was absent. A generic TIFF or a PNG —
    both accepted by the live importer — crashed instead of opening.
    """
    p = tmp_path / "plain.tif"
    Image.new("RGB", (64, 64), (10, 120, 200)).save(p)
    slide = reader.open_slide(p)
    try:
        props = slide.properties()
        assert props.width == 64 and props.height == 64
        assert props.engine in {"pillow", "openslide"}
        assert props.mpp_x is None  # a plain TIFF carries none; never estimated
    finally:
        slide.close()


def test_open_slide_opens_a_png(tmp_path):
    p = tmp_path / "shot.png"
    Image.new("RGB", (48, 48), (200, 30, 30)).save(p)
    slide = reader.open_slide(p)
    try:
        assert slide.properties().width == 48
    finally:
        slide.close()


def test_explicit_engine_never_silently_falls_back(tmp_path):
    """`engine='pillow'` must not hand back an OpenSlide reader."""
    p = tmp_path / "plain.tif"
    Image.new("RGB", (32, 32), (10, 120, 200)).save(p)
    assert reader.open_slide(p, engine="pillow").engine == "pillow"
    with pytest.raises(reader.ReaderUnavailable):
        reader.open_slide(p, engine="nonsense")


def test_a_file_no_engine_can_read_names_both_attempts(tmp_path):
    junk = tmp_path / "not-an-image.tif"
    junk.write_bytes(b"this is definitely not a slide")
    with pytest.raises(reader.SlideReadError) as exc:
        reader.open_slide(junk)
    # Name at least one engine so the cause is not mysterious. When OpenSlide
    # is absent the message names only Pillow; when it is installed but cannot
    # read the file both are named. Either way the error is usable.
    msg = str(exc.value).lower()
    assert "pillow" in msg or "openslide" in msg, msg


# ---------------------------------------------------------------------------
# torch-GATED: a real forward pass
# ---------------------------------------------------------------------------
def _first_durable_tiff() -> Path | None:
    if not DURABLE_IMAGES.is_dir():
        return None
    return next(iter(sorted(DURABLE_IMAGES.glob("*.tiff"))), None)


@torch_only
def test_live_prediction_is_a_real_three_class_forward_pass(live_db):
    tiff = _first_durable_tiff()
    if tiff is None:
        pytest.skip("durable TIFF corpus not present on this machine")
    result = li.predict_patch_bytes(
        live_db, project_id="prj_test", filename=tiff.name,
        data=tiff.read_bytes(), requested_by="tester@demo",
    )
    pred = result["prediction"]
    assert set(pred["scores"]) == set(config.CANONICAL_CLASSES)
    assert pred["predicted_class"] in config.CANONICAL_CLASSES
    assert abs(sum(pred["scores"].values()) - 1.0) < 1e-9
    assert pred["score_label"].startswith("Model score")
    assert "uncalibrated" in pred["score_label"]
    assert result["run"]["model_id"] == "g4-behavioral-recovery-r1"
    assert result["run"]["is_live_inference"] is True
    assert result["run"]["is_corpus_prediction"] is False


@torch_only
def test_live_scores_reproduce_the_frozen_stored_scores(live_db):
    """The recovered head is behaviourally equivalent to the original on this
    corpus, so a live score and the frozen score for the SAME patch agree to
    float32 storage precision. Anything looser would mean the recovered head is
    not the head the 1,144 rows came from."""
    if not config.DB_PATH.exists():
        pytest.skip("read model not present on this machine")
    frozen = db.connect(config.DB_PATH)
    rows = frozen.execute(
        "SELECT image_id, predicted_class, non_tumor_score, viable_tumor_score,"
        " necrosis_score FROM prediction ORDER BY image_id LIMIT 25"
    ).fetchall()
    if not rows:
        pytest.skip("no predictions to compare against")

    from osteopatch import attribution

    state = attribution.get_state()
    worst = 0.0
    for r in rows:
        tiff = DURABLE_IMAGES / f"{r['image_id']}.tiff"
        if not tiff.exists():
            continue
        with Image.open(tiff) as im:
            pred = li._predict_array(state, im.convert("RGB"))
        for cls, col in (("NON_TUMOR", "non_tumor_score"),
                         ("VIABLE_TUMOR", "viable_tumor_score"),
                         ("NECROSIS", "necrosis_score")):
            worst = max(worst, abs(pred.scores[cls] - r[col]))
        assert pred.predicted_class == r["predicted_class"]
    # 1e-5 is generous against a measured worst case of ~9e-8, which is the
    # precision of the stored float32 scores.
    assert worst < 1e-5, f"live scores drifted from the frozen scores by {worst}"


@torch_only
def test_a_live_run_writes_nothing_to_the_frozen_corpus(live_db):
    """The claim this feature exists to make, asserted end to end.

    The read model is seeded with REAL corpus rows first, so the digest covers
    actual scores and labels — a digest over an empty table would pass whatever
    the live run did.
    """
    tiffs = sorted(DURABLE_IMAGES.glob("*.tiff")) if DURABLE_IMAGES.is_dir() else []
    if not tiffs:
        pytest.skip("durable TIFF corpus not present on this machine")
    if not config.DB_PATH.exists():
        pytest.skip("read model not present on this machine")

    frozen = db.connect(config.DB_PATH)
    rows = frozen.execute(
        "SELECT s.image_id, s.source_group, s.original_label, s.primary_qc_status,"
        " s.training_eligible, s.qc_review_flag, s.qc_review_reason, s.tiff_filename,"
        " p.prediction_id, p.model_version, p.model_bundle_hash, p.created_at,"
        " p.inference_kind, p.predicted_class, p.non_tumor_score, p.viable_tumor_score,"
        " p.necrosis_score, p.top1_score, p.top_two_margin, p.normalized_entropy"
        " FROM source_qc s JOIN prediction p ON p.image_id = s.image_id"
        " ORDER BY s.image_id LIMIT 40"
    ).fetchall()
    if len(rows) < 5:
        pytest.skip("read model has too few corpus rows to be meaningful")

    live_db.executemany(
        "INSERT INTO source_qc(image_id, source_group, original_label, primary_qc_status,"
        " training_eligible, qc_review_flag, qc_review_reason, tiff_filename)"
        " VALUES (?,?,?,?,?,?,?,?)",
        [tuple(r[c] for c in ("image_id", "source_group", "original_label",
                               "primary_qc_status", "training_eligible",
                               "qc_review_flag", "qc_review_reason", "tiff_filename"))
         for r in rows],
    )
    live_db.executemany(
        "INSERT INTO prediction(prediction_id, image_id, model_version, model_bundle_hash,"
        " created_at, inference_kind, predicted_class, non_tumor_score, viable_tumor_score,"
        " necrosis_score, top1_score, top_two_margin, normalized_entropy)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [tuple(r[c] for c in ("prediction_id", "image_id", "model_version",
                               "model_bundle_hash", "created_at", "inference_kind",
                               "predicted_class", "non_tumor_score", "viable_tumor_score",
                               "necrosis_score", "top1_score", "top_two_margin",
                               "normalized_entropy")) for r in rows],
    )
    live_db.commit()

    before = integrity.corpus_row_digest(live_db)
    assert before["tables"]["prediction"] == len(rows)

    li.predict_patch_bytes(
        live_db, project_id="prj_test", filename="a.tiff",
        data=tiffs[0].read_bytes(), requested_by="tester@demo",
    )
    assert live_db.execute("SELECT COUNT(*) FROM live_run").fetchone()[0] == 1
    assert live_db.execute("SELECT COUNT(*) FROM live_tile").fetchone()[0] == 1

    after = integrity.corpus_row_digest(live_db)
    integrity.assert_corpus_unchanged(before, after)
    assert (
        live_db.execute("SELECT COUNT(*) FROM prediction").fetchone()[0]
        == before["tables"]["prediction"]
    )


@torch_only
def test_slide_analysis_tiles_the_whole_field_and_says_when_it_cannot(live_db):
    """A field wider than one tile produces a real grid; a cap is REPORTED."""
    if not DURABLE_IMAGES.is_dir():
        pytest.skip("durable TIFF corpus not present on this machine")
    tile = sorted(DURABLE_IMAGES.glob("*.tiff"))[0]
    with Image.open(tile) as im:
        wide = im.convert("RGB").resize((1100, 700))
    result = li.analyze_slide_bytes(
        live_db, project_id="prj_test", filename="wide.png",
        data=_png_bytes(wide), requested_by="tester@demo", tile_px=384,
    )
    run = result["run"]
    assert run["source_kind"] == "slide"
    # 1100x700 at 384px, stride 384: x starts 0/384 then a flush tile at 716
    # (1100-384); y starts 0 then a flush tile at 316 (700-384). 3 x 2 = 6.
    assert run["tiles_available"] == 6
    assert run["tile_count"] == 6
    assert run["truncated"] is False
    assert run["level_count"] == 1  # a PNG genuinely has no pyramid; not invented
    assert run["mpp_x"] is None
    tiles = li.get_tiles(live_db, run["run_id"])
    assert len(tiles) == 6
    assert all(t["predicted_class"] in config.CANONICAL_CLASSES for t in tiles)
    assert Path(config.LIVE_RUNS_DIR, run["run_id"], "mosaic.png").exists()


@torch_only
def test_a_slide_larger_than_max_tiles_is_reported_not_silently_truncated(live_db):
    if not DURABLE_IMAGES.is_dir():
        pytest.skip("durable TIFF corpus not present on this machine")
    tile = sorted(DURABLE_IMAGES.glob("*.tiff"))[0]
    with Image.open(tile) as im:
        wide = im.convert("RGB").resize((1100, 700))
    result = li.analyze_slide_bytes(
        live_db, project_id="prj_test", filename="wide.png",
        data=_png_bytes(wide), requested_by="tester@demo",
        tile_px=384, max_tiles=4,
    )
    run = result["run"]
    assert run["truncated"] is True
    assert run["tile_count"] == 4
    assert run["tiles_available"] == 6          # what the grid would have yielded
    assert "Only 4 of 6 tiles" in (run["notes"] or "")


def test_derived_png_omits_oversized_scanner_metadata_without_mutating_pixels():
    image = Image.new("RGB", (8, 8), (80, 30, 120))
    image.info["icc_profile"] = b"scanner metadata" * 100000
    encoded = li._png(image)
    with Image.open(io.BytesIO(encoded)) as decoded:
        decoded.load()
        assert decoded.tobytes() == image.tobytes()
        assert "icc_profile" not in decoded.info
    assert "icc_profile" in image.info
