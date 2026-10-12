"""F002 — deterministic review fixture.

Builds the pack's hand-check example as a real, throwaway SQLite database plus
synthetic pixels, so downstream analytics work has one authoritative, repeatable
input instead of every task inventing its own.

WHAT THIS IS NOT
----------------
* Not a production dashboard constant. Every number here is a TEST VALUE from
  the F002 hand-check example. Reviewer agreement here is operational
  concordance over seeded rows -- not model accuracy, not validation against a
  reference standard, and not a clinical claim.
* Not real H&E. ``Step 05`` of the task asks for simple coloured pixels generated
  locally for automated tests only. Every file is prefixed ``TEST_FIXTURE-`` and
  this module never writes into a public demo asset directory.
* Not the analytics product. ``counts_from``/``latest_states`` exist so the
  fixture can *assert* its own seeded state. Producing the real
  ``AnalyticsSnapshot`` endpoint is A001's job and is deliberately NOT
  implemented here.

REUSE, NOT PARALLEL SCHEMA
--------------------------
The schema comes from ``osteopatch.db.run_migrations`` and rows are written
through ``osteopatch.repo`` (``upsert_prediction``, ``submit_review``), exactly
as production writes them. This module never issues its own CREATE TABLE and
never second-guesses the frozen contract in ``osteopatch.config``.

CANONICAL DATA
--------------
Every database this module builds lives under the caller-supplied ``root``. The
canonical review store is opened read-only at most, and only to hash it.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from osteopatch import config, db, projects, repo

# Recorded so a test can assert the fixture never imports the heavy stack.
torch = None

#: A test-only model identity. Deliberately NOT the frozen production hash:
#: nothing here may ever be mistaken for baseline-frozen-g4 evidence.
FIXTURE_MODEL_HASH = "fixture000000000000000000000000000000000000000000000000000000000000f"
FIXTURE_MODEL_VERSION = "fixture-model-v1"

#: A second identity, used only by the ``two_models`` variant.
FIXTURE_OTHER_MODEL_HASH = "fixture111111111111111111111111111111111111111111111111111111111111f"

FIXTURE_GROUP_A = "FX-GROUP-A"
FIXTURE_GROUP_B = "FX-GROUP-B"

VARIANTS = (
    "default",
    "no_reviews",
    "no_predictions",
    "empty",
    "corrupt_asset",
    "empty_project",
    "two_models",
)

DISCLAIMER = (
    "Synthetic TEST_FIXTURE data. The images are generated coloured pixels, not real H&E, "
    "and the counts are test values, not production statistics."
)


@dataclass(frozen=True)
class FixturePaths:
    """Everything a test needs to reach the fixture. No application is started."""

    root: Path
    db_path: Path
    image_root: Path
    expected_snapshot_path: Path
    variant: str

    def open(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn


# --- the hand-check example -------------------------------------------------
# (image_id, source_group, scores, latest action, correction target)
# Chosen so that, with the contract's rules applied:
#   decided = 3 (fx-01 ACCEPT, fx-02 ACCEPT, fx-03 CORRECT)
#   deferred = 2 (fx-04, fx-05);  unreviewed = 3 (fx-06..fx-08)
#   corrected = 1 (fx-03); disagreement = 1 (fx-03, whose CORRECT target
#   genuinely differs from its predicted class)
#   agreement = 2/3; completion = 3/8; correction rate = 1/3; defer = 2/5
_SEED = (
    ("fx-01", FIXTURE_GROUP_A, (0.70, 0.20, 0.10), "ACCEPT", None),
    ("fx-02", FIXTURE_GROUP_A, (0.60, 0.25, 0.15), "ACCEPT", None),
    ("fx-03", FIXTURE_GROUP_A, (0.20, 0.60, 0.20), "CORRECT", "NECROSIS"),
    ("fx-04", FIXTURE_GROUP_A, (0.20, 0.20, 0.60), "DEFER", None),
    ("fx-05", FIXTURE_GROUP_B, (0.25, 0.25, 0.50), "DEFER", None),
    ("fx-06", FIXTURE_GROUP_B, (0.15, 0.55, 0.30), None, None),
    ("fx-07", FIXTURE_GROUP_B, (0.45, 0.35, 0.20), None, None),
    ("fx-08", FIXTURE_GROUP_B, (0.80, 0.10, 0.10), None, None),
)

# fx-01 is deliberately seeded with a DEFER (rev 1) superseded by an ACCEPT
# (rev 2), so "adding an old event changes event count, not latest state" is
# demonstrated by the default fixture itself rather than only by a mutation.
_SUPERSEDED = (("fx-01", "DEFER", "mixed_tissue"),)

EXPECTED_DEFAULT = {
    "definitions_version": "review-v1",
    "counts": {
        "total_images": 8,
        "prediction_images": 8,
        "predictionless_images": 0,
        "unreviewed_images": 3,
        "decided_images": 3,
        "deferred_images": 2,
        "touched_images": 5,
        "accepted_images": 2,
        "corrected_images": 1,
        "disagreement_images": 1,
        "qc_flagged_images": 0,
    },
    "rates": {
        "review_completion": {
            "value": 3 / 8,
            "numerator": 3,
            "denominator": 8,
            "unavailable_reason": None,
        },
        "reviewer_agreement": {
            "value": 2 / 3,
            "numerator": 2,
            "denominator": 3,
            "unavailable_reason": None,
        },
        "correction_action_rate": {
            "value": 1 / 3,
            "numerator": 1,
            "denominator": 3,
            "unavailable_reason": None,
        },
        "defer_fraction": {
            "value": 2 / 5,
            "numerator": 2,
            "denominator": 5,
            "unavailable_reason": None,
        },
    },
}


def canonical_db_sha256(db_path: Path | None = None) -> str | None:
    """SHA-256 of the canonical review store, or None when it is absent.

    Read-only. An absent store returns None so callers report "unavailable"
    rather than inventing a hash or a zero.
    """
    path = Path(db_path) if db_path is not None else Path(config.DB_PATH)
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_review_fixture(root: Path, variant: str = "default") -> FixturePaths:
    """Build the fixture under ``root`` and return its paths.

    ``root`` is always caller-supplied (pytest's ``tmp_path`` in practice), so a
    test can never fall back to ``config.DB_PATH``.
    """
    if variant not in VARIANTS:
        raise ValueError(f"unknown fixture variant {variant!r}; expected one of {VARIANTS}")

    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    image_root = root / "images"
    image_root.mkdir(parents=True, exist_ok=True)
    db_path = root / "fixture.sqlite3"
    snapshot_path = root / "expected_snapshot.json"

    conn = db.connect(db_path)
    try:
        # Reuse the production migration runner: no parallel schema.
        db.run_migrations(conn)

        seed_images = _seed_images()
        if variant != "empty":
            _write_pixels(image_root, seed_images, variant)

        if variant != "empty":
            _seed_source_qc(conn)
        predictions = _seed_predictions(conn, seed_images, variant)
        if variant not in ("empty", "no_reviews") and predictions:
            _seed_reviews(conn, predictions, variant)

        conn.commit()
        counts = counts_from(conn, model_bundle_hash=FIXTURE_MODEL_HASH)
        manifest = _manifest(variant, conn, counts)
        snapshot_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    finally:
        conn.close()

    return FixturePaths(
        root=root,
        db_path=db_path,
        image_root=image_root,
        expected_snapshot_path=snapshot_path,
        variant=variant,
    )


# --- seeding ----------------------------------------------------------------
def _seed_images() -> list[tuple[str, str]]:
    return [(image_id, group) for image_id, group, *_ in _SEED]


def _seed_source_qc(conn) -> None:
    """Write source/QC metadata rows.

    ``original_label`` uses dataset vocabulary only where it is already a
    canonical class. ``training_eligible`` is metadata, never a class, and
    ``project_id`` is set explicitly so no row is left in NULL scope.
    """
    if not _SEED:
        return
    for (image_id, group, scores, _action, _target) in _SEED:
        predicted = config.IDX_TO_CLASS[max(range(3), key=lambda i: scores[i])]
        conn.execute(
            """
            INSERT INTO source_qc
              (image_id, source_group, original_label, primary_qc_status,
               training_eligible, qc_review_flag, qc_review_reason, tiff_filename,
               project_id)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                image_id,
                group,
                predicted,
                "PASS",
                1,
                0,
                None,
                f"{image_id}.tiff",
                projects.DEFAULT_PROJECT_ID,
            ),
        )


def _seed_predictions(conn, seed_images, variant) -> dict[str, str]:
    """Write immutable predictions through repo. Returns image_id -> prediction_id.

    Pixel assets are written by ``_write_pixels``; this step only builds rows.
    """
    if variant in ("no_predictions", "empty"):
        return {}

    predictions: dict[str, str] = {}
    for (image_id, _group, scores, _action, _target) in _SEED:
        if variant == "corrupt_asset" and image_id == "fx-08":
            # fx-08 keeps an unreadable asset on disk but carries no prediction,
            # so the "predictionless / unavailable" path has a real case.
            continue
        pid, _created = repo.upsert_prediction(
            conn, image_id, FIXTURE_MODEL_HASH, FIXTURE_MODEL_VERSION, list(scores)
        )
        predictions[image_id] = pid

    if variant == "two_models":
        for (image_id, _group, scores, _action, _target) in _SEED:
            repo.upsert_prediction(
                conn, image_id, FIXTURE_OTHER_MODEL_HASH, "fixture-model-v2", list(scores)
            )
    return predictions


def _seed_reviews(conn, predictions, variant) -> None:
    """Append review events through repo.submit_review (the append-only path)."""
    for image_id, _group, _scores, action, target in _SEED:
        if action is None or image_id not in predictions:
            continue
        revision = 0
        for sup_image, sup_action, sup_reason in _SUPERSEDED:
            if sup_image != image_id:
                continue
            repo.submit_review(
                conn,
                image_id=image_id,
                prediction_id=predictions[image_id],
                action=sup_action,
                expected_revision=revision,
                idempotency_key=f"fx-superseded-{image_id}",
                reason=sup_reason,
            )
            revision += 1

        kwargs = {}
        if action == "CORRECT":
            kwargs["selected_label"] = target
        elif action == "DEFER":
            kwargs["reason"] = "uncertain_morphology"

        repo.submit_review(
            conn,
            image_id=image_id,
            prediction_id=predictions[image_id],
            action=action,
            expected_revision=revision,
            idempotency_key=f"fx-latest-{image_id}",
            **kwargs,
        )


def add_superseded_event(conn, image_id, action, reason=None, revision_number=0) -> str:
    """Append an OLD event beneath the current latest revision.

    Used to prove that event count and latest-state count are independent. The
    table is append-only, so this only ever INSERTs -- it never updates or
    deletes the newer event.
    """
    row = conn.execute(
        "SELECT prediction_id FROM prediction WHERE image_id = ? "
        "AND model_bundle_hash = ?",
        (image_id, FIXTURE_MODEL_HASH),
    ).fetchone()
    if row is None:
        raise repo.NotFoundError("no selected prediction for image", {"image_id": image_id})

    event_id = f"rev-{image_id}-sup-{revision_number}"
    conn.execute(
        """
        INSERT OR IGNORE INTO review_event
          (review_event_id, image_id, prediction_id, action, selected_class,
           reason, note, reviewer, created_at, revision_number, idempotency_key,
           project_id)
        VALUES (?,?,?,?,NULL,?,NULL,?,?,?,?,?)
        """,
        (
            event_id,
            image_id,
            row["prediction_id"],
            action,
            reason,
            "fixture-superseded",
            db.utc_now(),
            revision_number,
            f"fx-superseded-extra-{image_id}-{revision_number}",
            projects.DEFAULT_PROJECT_ID,
        ),
    )
    conn.commit()
    return event_id


# --- state + counts ---------------------------------------------------------
def latest_states(conn, model_bundle_hash: str = FIXTURE_MODEL_HASH) -> dict[str, dict]:
    """Latest review state per image for ONE explicitly selected model.

    A review bound to a different model's prediction does not decide the
    selected model; it stays history and the image remains unreviewed here.
    """
    images = _image_rows(conn)
    states: dict[str, dict] = {}
    for image_id in images:
        if model_bundle_hash is not None:
            pred = conn.execute(
                "SELECT prediction_id, predicted_class FROM prediction "
                "WHERE image_id = ? AND model_bundle_hash = ?",
                (image_id, model_bundle_hash),
            ).fetchone()
        else:
            pred = conn.execute(
                "SELECT prediction_id, predicted_class FROM prediction "
                "WHERE image_id = ? ORDER BY created_at LIMIT 1",
                (image_id,),
            ).fetchone()

        if pred is None:
            states[image_id] = {
                "image_id": image_id,
                "status": "unreviewed",
                "action": None,
                "effective_label": None,
                "predicted_class": None,
                "prediction_id": None,
            }
            continue

        latest = conn.execute(
            "SELECT * FROM review_event WHERE image_id = ? AND prediction_id = ? "
            "ORDER BY revision_number DESC LIMIT 1",
            (image_id, pred["prediction_id"]),
        ).fetchone()

        # Reuse the canonical status mapping rather than re-deriving it.
        status = repo._review_status(latest)
        if latest is None or status == "deferred":
            effective = None
        elif latest["action"] == "ACCEPT":
            effective = pred["predicted_class"]
        else:
            effective = latest["selected_class"]

        states[image_id] = {
            "image_id": image_id,
            "status": status,
            "action": latest["action"] if latest else None,
            "effective_label": effective,
            "predicted_class": pred["predicted_class"],
            "prediction_id": pred["prediction_id"],
        }
    return states


def counts_from(conn, model_bundle_hash: str | None = FIXTURE_MODEL_HASH, project_id=None):
    """Fixture-local counts, used only to assert the seeded state.

    This is deliberately NOT the product's AnalyticsSnapshot (A001). Rates with
    no denominator are null plus a reason, never a bare 0.0.
    """
    rows = _image_rows(conn, project_id)
    total = len(rows)

    # Count IMAGES carrying a prediction, never prediction rows. With a selected
    # model the question is "does this image have a prediction under that model";
    # with model_bundle_hash=None it is "does it have any prediction at all".
    # prediction_images can therefore never exceed total_images.
    prediction_images = 0
    for image_id in rows:
        sql = "SELECT 1 FROM prediction WHERE image_id = ?"
        params: tuple = (image_id,)
        if model_bundle_hash is not None:
            sql += " AND model_bundle_hash = ?"
            params = (image_id, model_bundle_hash)
        if conn.execute(sql + " LIMIT 1", params).fetchone():
            prediction_images += 1
    predictionless = total - prediction_images

    states = latest_states(conn, model_bundle_hash) if total else {}
    scoped = {k: v for k, v in states.items() if k in rows}

    decided = sum(1 for s in scoped.values() if s["status"] == "reviewed")
    deferred = sum(1 for s in scoped.values() if s["status"] == "deferred")
    unreviewed = sum(1 for s in scoped.values() if s["status"] == "unreviewed")
    corrected = sum(1 for s in scoped.values() if s["action"] == "CORRECT")
    accepted = sum(1 for s in scoped.values() if s["action"] == "ACCEPT")
    disagreeing = sum(
        1
        for s in scoped.values()
        if s["status"] == "reviewed"
        and s["effective_label"] is not None
        and s["effective_label"] != s["predicted_class"]
    )
    qc_flagged = 0
    for image_id in rows:
        flag = conn.execute(
            "SELECT qc_review_flag FROM source_qc WHERE image_id = ?", (image_id,)
        ).fetchone()
        if flag and flag["qc_review_flag"]:
            qc_flagged += 1

    touched = decided + deferred
    return {
        "total_images": total,
        "prediction_images": prediction_images,
        "predictionless_images": predictionless,
        "unreviewed_images": unreviewed,
        "decided_images": decided,
        "deferred_images": deferred,
        "touched_images": touched,
        "accepted_images": accepted,
        "corrected_images": corrected,
        "disagreement_images": disagreeing,
        "qc_flagged_images": qc_flagged,
        "rates": {
            "review_completion": _rate(decided, total, "no images in scope"),
            "reviewer_agreement": _rate(
                decided - disagreeing,
                decided,
                "no decided prediction to compare against",
            ),
            "correction_action_rate": _rate(corrected, decided, "nothing decided yet"),
            "defer_fraction": _rate(deferred, touched, "nothing reviewed or deferred yet"),
        },
    }


def _rate(numerator: int, denominator: int, reason: str) -> dict:
    if denominator == 0:
        return {
            "value": None,
            "numerator": numerator,
            "denominator": 0,
            "unavailable_reason": reason,
        }
    return {
        "value": numerator / denominator,
        "numerator": numerator,
        "denominator": denominator,
        "unavailable_reason": None,
    }


def _image_rows(conn, project_id=None) -> dict[str, sqlite3.Row]:
    if project_id is None:
        return {r["image_id"]: r for r in conn.execute("SELECT * FROM source_qc")}
    return {
        r["image_id"]: r
        for r in conn.execute("SELECT * FROM source_qc WHERE project_id = ?", (project_id,))
    }


# --- synthetic pixels -------------------------------------------------------
_COLORS = ((210, 60, 60), (60, 160, 90), (70, 90, 200), (200, 160, 50))


def _write_pixels(image_root: Path, seed_images, variant) -> None:
    """One tiny synthetic PNG per image, written locally for automated tests."""
    for index, (image_id, _group) in enumerate(seed_images):
        if variant == "corrupt_asset" and image_id == "fx-08":
            _write_png_stub(image_root, corrupt=True)
            continue
        _write_png_stub(image_root, index=index)


def _write_png_stub(image_root: Path, index: int = 0, corrupt: bool = False) -> None:
    """Write one tiny synthetic PNG. Local, labelled, never a real H&E patch."""
    from PIL import Image

    image_root.mkdir(parents=True, exist_ok=True)
    name = "TEST_FIXTURE-fx-08.png" if corrupt else f"TEST_FIXTURE-fx-{index + 1:02d}.png"
    path = image_root / name
    if corrupt:
        # Intentionally not a decodable image, so the unavailable-asset path has
        # something real to fail on.
        path.write_bytes(b"TEST_FIXTURE-NOT-A-DECODABLE-IMAGE\n")
        return
    color = _COLORS[index % len(_COLORS)]
    Image.new("RGB", (16, 16), color).save(path, format="PNG")





# --- manifest ---------------------------------------------------------------
def _manifest(variant: str, conn, counts: dict) -> dict:
    warnings: list[str] = []
    if variant == "corrupt_asset":
        warnings.append("TEST_FIXTURE corrupt_asset: fx-08 has no readable pixel asset")
    if variant == "no_predictions":
        warnings.append("TEST_FIXTURE no_predictions: images present, predictions absent")
    if counts["predictionless_images"]:
        warnings.append(
            f"TEST_FIXTURE {counts['predictionless_images']} image(s) have no selected "
            "prediction and are excluded from agreement denominators"
        )
    return {
        "schema_version": "1",
        "definitions_version": "review-v1",
        "variant": variant,
        "data_mode": "synthetic_fixture",
        "disclaimer": DISCLAIMER,
        "model": {
            "model_version": FIXTURE_MODEL_VERSION,
            "model_bundle_hash": FIXTURE_MODEL_HASH,
            "identity": "TEST_FIXTURE — not the frozen production bundle",
        },
        "scope": {
            "project_id": projects.DEFAULT_PROJECT_ID,
            "dataset_version_id": None,
            "model_bundle_hash": FIXTURE_MODEL_HASH,
            "review_session_id": None,
            "deployment_subset": None,
            "reference_kind": "synthetic_fixture",
        },
        "counts": {k: v for k, v in counts.items() if k != "rates"},
        "rates": counts["rates"],
        "warnings": warnings,
        "provenance": {
            "builder": "app/g6/backend/tests/fixtures/review_fixture.py",
            "schema_source": "osteopatch.db.run_migrations (no parallel schema)",
            "image_note": "generated coloured pixels; not real H&E",
        },
    }