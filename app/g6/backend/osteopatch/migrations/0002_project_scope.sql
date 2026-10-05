-- OsteoPatch — migration 0002: explicit project scoping.
--
-- WHY THIS EXISTS
-- ---------------
-- Multi-tenancy was previously enforced by mutating process-global state at
-- request time: the enterprise proxy wrote os.environ["OSTEOPATCH_IMAGE_ALLOWLIST"]
-- and reassigned two module globals on osteopatch.config, without ever
-- restoring them. Under concurrency one project could read another's scope,
-- and the most-recently-touched project leaked into later unscoped reads.
--
-- The root cause was not that mutation. It was that NO TABLE HAD A PROJECT.
-- Tenancy had nowhere to live, so it was smuggled into a global.
--
-- THIS MIGRATION IS ADDITIVE ONLY.
--   * ALTER TABLE ... ADD COLUMN, which SQLite performs as a schema change
--     without rewriting existing rows.
--   * Every new column is NULLABLE.
--   * No UPDATE, DELETE or REWRITE touches the `prediction` table.
--
-- The 1,144 immutable predictions keep their rows, their values, their
-- model_bundle_hash (01727fb8...), and their ids, byte for byte. A test
-- asserts this pre/post.
--
-- NULL means "the legacy default project". Backfill happens in Python via
-- osteopatch.projects.assign_legacy_project() so the default project id is
-- defined in one place rather than hardcoded in SQL.

ALTER TABLE source_qc   ADD COLUMN project_id TEXT;
ALTER TABLE prediction  ADD COLUMN project_id TEXT;
ALTER TABLE review_event ADD COLUMN project_id TEXT;

-- The hot read path is always "images of project X, newest state first".
CREATE INDEX IF NOT EXISTS idx_source_qc_project  ON source_qc(project_id, image_id);
CREATE INDEX IF NOT EXISTS idx_prediction_project ON prediction(project_id, image_id);
CREATE INDEX IF NOT EXISTS idx_review_project     ON review_event(project_id, image_id);