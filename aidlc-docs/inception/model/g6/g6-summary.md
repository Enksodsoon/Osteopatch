# G6 — Local OsteoPatch Review MVP — Summary

**Gate verdict:** **G6 — LOCAL PRODUCT REVIEW REQUIRED** (complete working local prototype; acceptance path passes end-to-end).
**Date:** 2026-10-03 (Asia/Bangkok). **Model decision frozen:** `baseline-frozen-g4` is the prototype default; G5 (NO BENEFIT) not used. No fine-tune, no architecture search, no multi-seed, no AWS, no deploy, no Grad-CAM, no LLM.

> **Certification note.** The implementation worker (`bc7dd1d9`) was killed by a runtime process shutdown (provider shutdown) at teardown — AFTER all source, the SQLite DB, the frontend install/build, and the test runs had been written to disk. The parent (default) did **not** re-dispatch. Instead it verified the result **live from disk**: recreated the web venv the kill destroyed, re-ran the full backend + frontend suites, independently ran the 12-step acceptance path against the real app, probed the DB, then finished the teardown steps the kill skipped (this summary, the test report, the E2E evidence, the audit + state updates, and deleting the stray `_G6_BRIEF.md`). G4/G5 artifacts untouched.

## 1. Stack & versions
- **Backend:** Python 3.12 · FastAPI 0.115.6 · uvicorn 0.34.0 · pydantic 2.10.4 · Pillow 11 · SQLite (stdlib). PyTorch 2.14.1+cpu / torchvision 0.29.1 used **only** by the one-time precompute script (the server is torch-free).
- **Frontend:** React 18.3 · TypeScript 5.7 · Vite 6 · Vitest 2.1.9.
- **Two-venv design (by intent):** `precompute.py` runs under the torch venv; the server + API tests run under a torch-free web venv (`requirements.txt`: fastapi/uvicorn/pydantic/pillow/numpy + pytest/httpx). The browser never waits on PyTorch.

## 2. Model loaded
`baseline-frozen-g4`, bundle SHA-256 **`01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63`** — re-verified at load; the loader (and `precompute.py`) **refuse to start on mismatch** (`test_hash_mismatch_refuses` green). Canonical order `[NON_TUMOR, VIABLE_TUMOR, NECROSIS]`; preprocessing taken from the bundle (384² full-field resize + pinned ImageNet norm), not re-implemented.

## 3-4. Data indexed & predictions precomputed
- **1,144** source patches indexed (`source_qc`) — the full decoded collection, correctly broader than the 1,028 training-eligible set.
- **1,144** immutable predictions precomputed (one per image), **0 duplicate** `(image_id, model_bundle_hash)` groups, all carrying the frozen G4 hash. Each row: 3 class scores + `top1_score` + `top_two_margin` + `normalized_entropy` + `inference_kind="prototype_inference"`.
- Prediction class distribution (prototype inference, **not** evaluation): NON_TUMOR 510 / VIABLE_TUMOR 330 / NECROSIS 304. **Kept separate** from the frozen G4 OOF evidence — no headline metric was recomputed.

## 5. API endpoints
`GET /v1/health`, `GET /v1/meta`, `GET /v1/model-card`, `GET /v1/images` (sort/filter/search/paginate), `GET /v1/images/{id}`, `GET /v1/predictions/{id}` (read-only), `GET /v1/images/{id}/thumbnail`, `GET /v1/images/{id}/full` (127.0.0.1-only, path-traversal-safe), `GET /v1/images/{id}/review` (state+revision+full history), `POST /v1/images/{id}/reviews` (201 / 200-idempotent / 409 / 422 / 404), `GET /v1/exports/reviews?format=csv|json`.

## 6-8. Tests (all live, re-run by parent)
- **Backend 34/34:** 5 torch real-bundle (hash match, mismatch-refuses, 3 canonical outputs, preprocessing parity, scores sum to one) + 29 API/safety/scoring (gallery sort/filter, 201/409/422/404, idempotent replay, append-only, prediction-immutable-after-correction, export preserves both, canonical order, no-4th-class, deterministic ranking).
- **Frontend 9/9 vitest** + clean `vite build`.
- **E2E 12/12** — the mandated acceptance path, against the real FastAPI app over a copy of the real DB (evidence: `e2e-acceptance-evidence.json`).

## 9. Local launch
See `app/g6/README.md` → **Run OsteoPatch locally**. In short: precompute once under the torch venv, then `uvicorn osteopatch.app:app --host 127.0.0.1 --port 8137` for the backend and `npm run dev` for the frontend. No AWS credentials; 127.0.0.1 only.

## 10. Screenshots
Not captured — no headless browser was driven in this verification pass (the UI is exercised by vitest + the real-backend E2E instead). **Not fabricated.** A follow-up can capture live screenshots with `playwright-cli` against the running dev server.

## 11. Database
`C:\Users\enkso\.kiro\crew\scratch\runtime-0a306834\osteopatch_g6\osteopatch_g6.sqlite3` (scratch, out of git; schema + migration `0001_initial.sql` live in the project). Tables: `source_qc` (image_id, source_group, original_label, primary_qc_status, training_eligible, qc_review_flag, qc_review_reason, tiff_filename), `prediction` (immutable), `review_event` (append-only, revision_number + idempotency_key), `schema_migrations`.

## 12. Review-priority implementation
Deterministic ranking (torch-free `scoring.py`): **(1) smallest `top_two_margin` → (2) highest `normalized_entropy` → (3) stable `image_id`.** Raw values exposed in the UI ("Top-two score margin: 0.04"); **no** calibrated confidence, **no** threshold tuning, **no** error-prediction claim. All scores labelled "Model score — uncalibrated". The 63-row data-QC review queue is kept as a separate `QC REVIEW` badge, never merged with model review-priority.

## 13. Prediction immutability (proof)
E2E step 9 + `test_prediction_immutable_after_correction`: after a CORRECT event flips the human class, `GET /v1/predictions/{id}` still returns the original `predicted_class` and identical scores; the correction lives only as a new `review_event`. A correction is `model prediction → human correction event`, never a mutation of the prediction row.

## 14. Export evidence
`GET /v1/exports/reviews` (CSV + JSON) emits one row per image carrying **both** the original model prediction (`model_predicted_class`, `model_score_*`, hash, `inference_kind`) **and** the current human state (`human_latest_action`, `human_corrected_class`, `human_defer_reason`, `human_note`, `human_revision_number`, `review_event_ids`), plus the educational disclaimer and model hash. CSV header verified; 1,144 rows.

## 15. Deviations from frozen product requirements
**None of substance.** The only notable implementation choice is the deliberate **two-venv split** (torch for precompute, torch-free for the server/tests) — it satisfies "the browser must not wait on PyTorch" and keeps the server lightweight; it is not a contract change. Screenshots were not captured this pass (documented, not fabricated).

## 16. Artifact paths
- **App source (durable, in git):** `app/g6/backend/` (osteopatch package: config, scoring, model, db, repo, queries, images, modelcard, app, server; migrations/0001_initial.sql; precompute.py; requirements.txt; tests/) and `app/g6/frontend/` (src: App, components/{Workbench, PatchReview, ImageViewer, ReviewPanel, ModelCard, Shared}, api/types/strings, test/ui.test.tsx; vite/ts config).
- **G6 gate artifacts:** `aidlc-docs/inception/model/g6/` → `g6-summary.md` (this file), `test-report.json`, `e2e-acceptance-evidence.json`.
- **Runtime data (scratch, out of git):** `osteopatch_g6/osteopatch_g6.sqlite3` (+ wal/shm), thumbnails, webvenv.
- `aidlc-docs/audit.md` and `aidlc-docs/aidlc-state.md` updated.

## 17. Recommendation for G7
Open **G7 — Model attribution (Grad-CAM)** on the frozen `baseline-frozen-g4`, filling the reserved "Model attribution — coming in G7" UI tab with class-targeted Grad-CAM overlays (per the frozen G3 explanation plan) — still local, no AWS, no new modeling. Keep carrying the standing scientific caveats: exploratory, case/slide-group-independent over 4 groups, P9 single-class, **VIABLE_TUMOR is the weak class**, scores uncalibrated, not diagnosis/prognosis/treatment-response. Secondary options remain separately gated: capture live UI screenshots, multi-seed sensitivity of the G4 baseline, and triage of the 63-row data-QC queue (which never blocked this build).
