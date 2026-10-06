-- OsteoPatch G6 — SQLite schema (migration 0004)
--
-- A case report is a SIXTH concept, and the rules here are the reason it is
-- not just another review_event:
--
--   * APPEND-ONLY. A saved report is never edited in place. `revision` is
--     always 1 for a row; a changed report is a NEW row that names the one it
--     supersedes. There is no UPDATE path in the application layer and the
--     trigger below makes a silent mutation impossible even from SQL.
--   * SEPARATE from the audit trail. Writing a report writes no review_event,
--     so producing a document can never alter what was reviewed or by whom.
--   * HASHED. `content_sha256` covers a canonical serialization of the frozen
--     `document_json`, so a later reader can recompute it and tell whether the
--     document they are holding is the one that was signed.
--
-- The three corpus concepts are untouched by this migration. A report READS
-- predictions; it never writes them.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- case_report: one immutable signed (or unsigned) document
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_report (
    report_id            TEXT PRIMARY KEY,
    project_id           TEXT NOT NULL,
    case_id              TEXT NOT NULL,
    title                TEXT NOT NULL,
    findings_text        TEXT NOT NULL,
    author_email         TEXT NOT NULL,

    -- Sign-off. A report is unsigned until a signer is recorded, and a signed
    -- report always names WHO signed and WHEN. Both are nullable because a
    -- draft genuinely has no signer — never because signing was forgotten.
    signer_email         TEXT,
    signer_role          TEXT,
    signed_at            TEXT,
    signoff_note         TEXT,

    created_at           TEXT NOT NULL,

    -- Always 1. An edit is a new row, never a bumped version.
    revision             INTEGER NOT NULL DEFAULT 1 CHECK (revision = 1),
    supersedes_report_id TEXT,

    -- The typed source, frozen at write time, plus the hash over it.
    document_json        TEXT NOT NULL CHECK (length(document_json) > 2),
    content_sha256       TEXT NOT NULL CHECK (length(content_sha256) = 64),

    -- A signed document MUST carry a signer and a signature time.
    CHECK (signed_at IS NULL OR (signer_email IS NOT NULL AND signer_role IS NOT NULL)),
    -- An unsigned draft must not look signed.
    CHECK (signer_email IS NULL OR signed_at IS NOT NULL),
    -- A report cannot supersede itself.
    CHECK (supersedes_report_id IS NULL OR supersedes_report_id <> report_id)
);
CREATE INDEX IF NOT EXISTS idx_report_project ON case_report(project_id, created_at);
CREATE INDEX IF NOT EXISTS idx_report_case    ON case_report(case_id);

-- ---------------------------------------------------------------------------
-- case_report_image: the patches a report spans, in document order
--
-- A report may cover many patches from one case. The model's own output is
-- copied in (never re-derived on read) so the document stays reproducible even
-- if the reader's store later moves on.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS case_report_image (
    report_id        TEXT NOT NULL REFERENCES case_report(report_id),
    ordinal          INTEGER NOT NULL CHECK (ordinal >= 1),
    image_id         TEXT NOT NULL,
    source_kind      TEXT NOT NULL CHECK (source_kind IN ('corpus', 'live')),
    run_id           TEXT,

    predicted_class  TEXT CHECK (
        predicted_class IS NULL
        OR predicted_class IN ('NON_TUMOR', 'VIABLE_TUMOR', 'NECROSIS')
    ),
    confidence       TEXT CHECK (
        confidence IS NULL
        OR confidence IN ('clear', 'low', 'indeterminate')
    ),
    top_two_margin   REAL,
    scores_json      TEXT,
    caveat_text      TEXT,

    PRIMARY KEY (report_id, ordinal),
    CHECK (source_kind <> 'live' OR run_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_report_image_image ON case_report_image(image_id);

-- ---------------------------------------------------------------------------
-- Append-only enforcement
--
-- Deletes are allowed (a report is the author's own document and a DELETE
-- capability exists for it); UPDATES are not. A changed report is a new row.
-- ---------------------------------------------------------------------------
CREATE TRIGGER IF NOT EXISTS case_report_no_update
BEFORE UPDATE ON case_report
BEGIN
    SELECT RAISE(ABORT, 'case_report is append-only: insert a new report instead');
END;

CREATE TRIGGER IF NOT EXISTS case_report_image_no_update
BEFORE UPDATE ON case_report_image
BEGIN
    SELECT RAISE(ABORT, 'case_report_image is append-only: insert a new report instead');
END;