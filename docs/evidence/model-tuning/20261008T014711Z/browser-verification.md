# Real-image browser verification

Status: **PASS** for authenticated gallery thumbnails, local model selection, and patch inference.

- Browser: Codex in-app browser against the local G7 Vite app and local FastAPI service.
- Isolation: G6 SQLite backup, enterprise database, audit log, project scopes, live runs, and attribution cache were placed under a unique Windows temporary directory. The corpus TIFF directory and recovered bundle were read-only inputs.
- Input: `Case-3-A10-10547-25283.tiff`, 238,242 bytes; SHA-256 `3d3da0c24d03c97a5bd6e93627d0137fd41d4adf4d2414a005bb307b96995144`, matching `full-ingestion-manifest.csv`.
- Gallery: initial browser pass exposed 401s because `Workbench` used a plain `<img>` for an authenticated endpoint. Reused the existing `AuthenticatedImage` helper. Follow-up loaded all 50 visible thumbnails at 256×256; all thumbnail requests returned 200.
- UI: only `g4-behavioral-recovery-r1` was shown; no unqualified candidate was selectable.
- Result: two patch runs, `live-73a87233cf5c4113` (3,476.21 ms) and `live-9f327d383feb4b98` (2,911.98 ms), each scored one tile and persisted `model_id=g4-behavioral-recovery-r1` with bundle SHA-256 `ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73`.
- Output: both runs returned `NECROSIS` for an input whose manifest label is `NON_TUMOR`; class scores `NON_TUMOR=0.281798`, `VIABLE_TUMOR=0.018017`, `NECROSIS=0.700185`. The UI identified these as uncalibrated class scores, not probabilities. This repeated single-image mismatch is a smoke-test observation, not a performance estimate.
- Scope: this confirms the browser-to-API model identity path and real-file upload only; it is not an evaluation result and does not change the failed qualification decision.

The isolated browser QA files remain under `C:\Users\enkso\AppData\Local\Temp\osteopatch-real-image-browser-qa-20261008-e9c45d88`.
