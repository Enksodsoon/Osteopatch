-- OsteoPatch G6 — SQLite schema (migration 0001)
--
-- Three SEPARATE, non-overwriting concepts:
--   1. source_qc  : source/QC metadata (image_id, group, dataset label, QC
--                   status, training_eligible). Read-only mirror of the frozen
--                   QC manifest. training_eligible is NOT a class; MIXED is NOT
--                   a 4th class.
--   2. prediction : IMMUTABLE model output. One row per (image_id,
--                   model_bundle_hash). Never updated by human review.
--   3. review_event : APPEND-ONLY human review. A correction inserts a NEW row;
--                   it never mutates a prediction. Optimistic concurrency via
--                   revision_number; idempotency via idempotency_key.
--
-- The 63-row DATA-QC human-review-queue is mirrored as a metadata flag
-- (qc_review_flag) on source_qc; it is deliberately NOT the model
-- review-priority queue.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL
);

-- 1. Source / QC metadata ---------------------------------------------------
CREATE TABLE IF NOT EXISTS source_qc (
    image_id            TEXT PRIMARY KEY,
    source_group        TEXT NOT NULL,
    original_label      TEXT,            -- dataset-provided canonical label (may be excluded class)
    primary_qc_status   TEXT NOT NULL,   -- PASS / REVIEW / NEAR_DUPLICATE_CANDIDATE ...
    training_eligible   INTEGER NOT NULL,-- 0/1 — NOT a biological class
    qc_review_flag      INTEGER NOT NULL DEFAULT 0, -- in the 63-row DATA-QC queue
    qc_review_reason    TEXT,            -- content flags / near-dup, if any
    tiff_filename       TEXT NOT NULL
);

-- 2. Prediction (IMMUTABLE) -------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction (
    prediction_id       TEXT PRIMARY KEY,  -- deterministic: image_id + bundle hash
    image_id            TEXT NOT NULL REFERENCES source_qc(image_id),
    model_version       TEXT NOT NULL,
    model_bundle_hash   TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    inference_kind      TEXT NOT NULL,     -- always 'prototype_inference'
    predicted_class     TEXT NOT NULL,     -- one of the 3 canonical classes
    non_tumor_score     REAL NOT NULL,
    viable_tumor_score  REAL NOT NULL,
    necrosis_score      REAL NOT NULL,
    top1_score          REAL NOT NULL,
    top_two_margin      REAL NOT NULL,
    normalized_entropy  REAL NOT NULL,
    UNIQUE (image_id, model_bundle_hash)   -- dedup: reuse, never duplicate
);
CREATE INDEX IF NOT EXISTS idx_prediction_image ON prediction(image_id);

-- 3. ReviewEvent (APPEND-ONLY) ---------------------------------------------
CREATE TABLE IF NOT EXISTS review_event (
    review_event_id     TEXT PRIMARY KEY,
    image_id            TEXT NOT NULL REFERENCES source_qc(image_id),
    prediction_id       TEXT NOT NULL REFERENCES prediction(prediction_id),
    action              TEXT NOT NULL,     -- ACCEPT | CORRECT | DEFER
    selected_class      TEXT,              -- canonical class for CORRECT; else NULL
    reason              TEXT,              -- defer reason or free label
    note                TEXT,              -- optional free text
    reviewer            TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    revision_number     INTEGER NOT NULL,  -- monotonic per image_id, 1-based
    idempotency_key     TEXT NOT NULL,
    UNIQUE (image_id, revision_number),
    UNIQUE (image_id, idempotency_key)     -- idempotent replay dedup
);
CREATE INDEX IF NOT EXISTS idx_review_image ON review_event(image_id);
CREATE INDEX IF NOT EXISTS idx_review_pred ON review_event(prediction_id);
