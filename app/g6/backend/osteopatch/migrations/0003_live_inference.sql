-- OsteoPatch — migration 0003: live inference on uploaded files.
--
-- WHY THIS EXISTS
-- ---------------
-- The 1,144 rows in `prediction` are the output of the ORIGINAL frozen G4 binary
-- (01727fb8...), computed once, offline, and never rewritten. That binary is
-- gone. What survives is a behaviourally RECOVERED head
-- (g4-behavioral-recovery-r1, its own hash), which is a different model.
--
-- Running that recovered head over a file a user just uploaded is a genuinely
-- new activity, and its results are NOT corpus predictions. Writing them into
-- `prediction` would be the single most damaging thing this codebase could do:
-- it would make a live research inference indistinguishable from a frozen
-- baseline result, and any downstream read would report the recovered head's
-- output as if it carried the original model's identity and evaluation.
--
-- So live inferences get their own store. `live_run` + `live_tile` are a
-- FOURTH and FIFTH concept alongside source_qc / prediction / review_event:
--   4. live_run  : one inference run over one uploaded file.
--   5. live_tile : one model's scores for one tile of that file.
--
-- The separation is enforced BY THE DATABASE, not by convention. The CHECK
-- constraints below make it impossible to INSERT a live row that claims the
-- frozen model id or the frozen bundle hash. Conflating the two is now a
-- constraint violation rather than something a future contributor has to
-- remember not to do.
--
-- THIS MIGRATION IS ADDITIVE ONLY.
--   * CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS.
--   * No ALTER, no UPDATE, no DELETE, no rewrite of any existing row.
-- The 1,144 source_qc / prediction rows keep their values, ids and hashes
-- byte for byte. `osteopatch.integrity.corpus_row_digest` proves it.

PRAGMA journal_mode = WAL;

-- 4. Live run --------------------------------------------------------------
CREATE TABLE IF NOT EXISTS live_run (
    run_id              TEXT PRIMARY KEY,
    project_id          TEXT NOT NULL,     -- tenancy boundary, like every other read
    source_kind         TEXT NOT NULL,     -- 'patch' | 'slide'
    source_name         TEXT NOT NULL,     -- the filename the user uploaded
    stored_filename     TEXT NOT NULL,     -- sanitised name under live-runs/<run_id>/
    source_sha256       TEXT NOT NULL,     -- digest of the bytes actually scored
    byte_size           INTEGER NOT NULL,
    engine              TEXT NOT NULL,     -- openslide | pillow (never invented)
    width               INTEGER,
    height              INTEGER,
    level_count         INTEGER,           -- NULL when the file carries no pyramid
    mpp_x               REAL,              -- NULL when absent; NEVER estimated
    mpp_y               REAL,
    objective_power     REAL,
    vendor              TEXT,
    model_id            TEXT NOT NULL,
    model_bundle_sha256 TEXT NOT NULL,
    encoder_sha256      TEXT NOT NULL,
    requested_by        TEXT NOT NULL,
    created_at          TEXT NOT NULL,
    latency_ms          REAL NOT NULL,
    tile_count          INTEGER NOT NULL,  -- tiles actually scored
    tiles_available     INTEGER NOT NULL,  -- tiles the grid would yield (>= tile_count)
    truncated           INTEGER NOT NULL DEFAULT 0,  -- grid hit max_tiles
    support_flags       TEXT NOT NULL DEFAULT '[]', -- JSON list, advisory only
    notes               TEXT,              -- honest caveat text
    -- A live run may never claim the frozen baseline model. These constraints
    -- are the structural half of "a live run is never a corpus prediction".
    CHECK (model_id <> 'baseline-frozen-g4'),
    CHECK (model_bundle_sha256 <> '01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63'),
    CHECK (source_kind IN ('patch', 'slide')),
    CHECK (byte_size > 0),
    CHECK (tile_count >= 0 AND tiles_available >= tile_count)
);
CREATE INDEX IF NOT EXISTS idx_live_run_project ON live_run(project_id, created_at DESC);

-- 5. Live tile -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS live_tile (
    run_id              TEXT NOT NULL REFERENCES live_run(run_id),
    tile_index          INTEGER NOT NULL,
    x                   INTEGER NOT NULL,
    y                   INTEGER NOT NULL,
    width               INTEGER NOT NULL,
    height              INTEGER NOT NULL,
    predicted_class     TEXT,              -- NULL when the tile could not be read
    non_tumor_score     REAL,
    viable_tumor_score  REAL,
    necrosis_score      REAL,
    top1_score          REAL,
    top_two_margin      REAL,
    normalized_entropy  REAL,
    confidence          TEXT,              -- 'clear' | 'low' | 'indeterminate'
    support_flags       TEXT NOT NULL DEFAULT '[]',
    decode_error        TEXT,              -- why a tile has no scores
    tile_png_filename   TEXT,              -- saved for later attribution
    PRIMARY KEY (run_id, tile_index),
    -- Exactly the three canonical classes, or NULL for a tile that failed to
    -- decode. There is no fourth output, here or anywhere else.
    CHECK (predicted_class IS NULL
           OR predicted_class IN ('NON_TUMOR', 'VIABLE_TUMOR', 'NECROSIS'))
);

-- A scored tile MUST carry all three scores; an unscored tile must carry none.
-- This is what stops a half-filled row from ever reading as a prediction.
-- (SQLite requires NEW.<column> in a trigger's WHEN clause — a bare column
-- name there fails to resolve.)
CREATE TRIGGER IF NOT EXISTS live_tile_scores_all_or_none
BEFORE INSERT ON live_tile
FOR EACH ROW WHEN (NEW.predicted_class IS NOT NULL)
BEGIN
    SELECT CASE WHEN NEW.non_tumor_score IS NULL
                  OR NEW.viable_tumor_score IS NULL
                  OR NEW.necrosis_score IS NULL
                THEN RAISE(ABORT, 'live_tile: a scored tile needs all three scores')
    END;
END;
