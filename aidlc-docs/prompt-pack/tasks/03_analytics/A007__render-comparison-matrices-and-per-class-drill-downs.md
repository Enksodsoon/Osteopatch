# A007 — Render comparison matrices and per-class drill-downs

**Task:** A007  |  **Track:** DEMO  |  **Work type:** frontend

**Planning status:** PLANNED — NOT EXECUTED by this prompt pack.

> Deliver one independently testable increment. Already-working behavior should be verified and reused, not rebuilt. The file is a complete task brief; no prior chat memory is required.

## 1. Global task guardrails

You are implementing ONE task in the existing OsteoPatch Review repository. Do not execute the entire roadmap. The owner wants an educational/research patch-review application and a truthful working demo, not a clinical product.

Repository: Enksodsoon/osteopatch-review. Known local checkout: C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff. Inspected remote baseline: 57c1efc77e67f691708bb9a825c621953fcea358. This is a reference snapshot, not an instruction to reset to it. The current local checkout may contain newer, uncommitted work. Read the actual checkout and its authorized project instructions first.

Operate on a clean isolated task branch/worktree approved by the owner or integrator. Record current branch, HEAD, and dirty files. Never reset --hard, delete branches/PRs, restore another worker’s files, stage -A, force-push, or overwrite uncommitted work. A task branch alone does not isolate two workers sharing the same directory. When another worker owns a required file, stop with the exact conflict rather than editing around it. New worktrees do not automatically contain ignored runtime data: use a verified read-only asset source plus a throwaway writable database, not the canonical database.

Reuse working features and installed libraries. Do not add a parallel API, duplicate role system, new frontend framework, global CSS override pile, or second source of model truth. All proposed new file paths and symbols below are design targets, not claims they already exist. If the equivalent component exists elsewhere, extend it and document the mapping. NEXT in a migration path means the next unused migration identifier chosen by the integrator; never create a literal NEXT migration or edit an applied migration.

Do not install/update dependencies, call a paid API, download model weights/datasets, train/calibrate a model, create cloud resources, change IAM, publish data, deploy, or schedule workers unless that action has its own explicit authorization. Default additional budget is USD 0. Never request secrets in chat or print credentials. Prepare-only deployment work is not permission to deploy. Do not claim regulatory compliance or clinical validation.

Use only authorized, de-identified assets and real evidence. Synthetic data belongs in labeled test fixtures, not production screenshots or claimed model results. Preserve the original frozen evaluation and all model/image/review provenance. Keep source-group identity separate from patient identity. Do not manufacture missing WSI coordinates, physical scale, metrics, tissue labels, approvals, heatmaps, or successful tests.

Write tests first. Read failure output before changing code. Run targeted tests, then affected regressions. Fix defects within this task; a missing prerequisite or unrelated defect becomes a precise blocker, not an invitation to rebuild the project. After two unsuccessful repair attempts at the same failure, document the failing test, suspected cause, and attempted changes for review; do not weaken the test or continue blindly.

Never commit, push, merge, or release automatically. Return the focused diff and an evidence receipt for the integrator. When the execution brief explicitly authorizes a commit, stage only reviewed task-owned paths and verify the staged diff. A task is not accepted merely because code was written or a process started.

## 2. Objective and boundary

**Deliverable:** Render comparison matrices and per-class drill-downs.

**Baseline stance:** New or partially available; inspect and reuse existing implementation.

**Additional gate:** No additional authorization beyond the bounded task should be assumed. All cloud, publication, model-fitting, data-download, and destructive actions remain gated.

Use the authoritative snapshot; never compute collection-wide totals from the first gallery page. Chart selections must preserve project, dataset, model, session, reference type, and denominators when opening the corresponding records.

**Not in this task:** every other roadmap feature, automatic retraining, clinical deployment, broad refactoring, unrelated cleanup, replacement of existing authoring/steering files, or publishing/merging the work. Fix a dependency only after the integrator assigns that dependency task; do not silently absorb it.

## 3. Prerequisites

- **A006 — Compute review comparison matrices and per-class operational counts**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.
- **A005 — Build the Disagreement Explorer with evidence drill-down**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.
- **U002 — Consolidate the editorial design tokens without redesigning behavior**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.

### Exact prerequisite interfaces to inspect
**A006:** GET /v1/analytics/comparison returns {snapshot_id, scope, reference_kind:"latest_reviewer_decision", class_order, matrix, eligible_n, excluded_counts, per_class_counts}. Rows are human decision; columns model prediction. This matrix is operational comparison, NOT held-out model performance.

**A005:** A separate explorer shows thumbnail, model label -> effective human label, review actor/time, raw score margin, QC flags, and note preview. Opening an item preserves the disagreement query and references the correct reviewed prediction.

**U002:** Use semantic variables for canvas, surface, text, muted-text, border, accent, focus, warning, error, and the three labeled class accents. Preserve the existing earth-tone editorial direction. Small text is not a way to fit more UI; body minimum 14px and supporting labels minimum 12px at normal desktop zoom are design targets.

## 4. Inspect before editing

- `app/g6/frontend/src/components/DisagreementExplorer.tsx`
- `app/g6/frontend/src/api.ts`

Also read the current tests covering these files, the relevant API/schema definitions, and the task dependency receipts. Paths listed as inputs from a previous task may not exist until that task is accepted. Search the repository for an equivalent implementation before creating a new one; never infer file content from its name.

## 5. Allowed change surface

- `app/g6/frontend/src/components/ReviewComparison.tsx`
- `app/g6/frontend/src/test/review-comparison.test.tsx`

These are proposed task-owned paths. Existing files are modified narrowly; absent files are created only when the task needs them. Do not replace an entire large source file for a one-function change. Keep source and test changes together. A minimal integration hook is allowed in the existing app/router/navigation/type file only after this task has exclusive ownership of that shared file. Limit it to the module import, router registration, capability-gated navigation entry, or exact response type required by this deliverable, and list that hook in the receipt. If another worker owns it, return the unapplied hook to the integrator and mark integration pending; do not claim the user-visible feature accepted. Any broader change requires a revised task boundary.

## 6. Input/output contract

Render a labeled3x3 table/heatmap with row header Human decision and column header Model prediction. Toggle counts versus row-normalized proportions; zero-row proportions show unavailable. Every cell links to its exact contributing query.

### Non-negotiable domain semantics

Canonical classes are exactly NON_TUMOR, VIABLE_TUMOR, NECROSIS. Review actions are ACCEPT, CORRECT, DEFER; latest review status is unreviewed, reviewed, or deferred. Mixed tissue, artifact, poor quality, unknown, and deferred are metadata/review states, never an added model class.

Prediction identity is (prediction_id, image_id, model_bundle_hash, inference_kind). An analysis must select exactly one explicit prediction per image and must not silently mix model versions or replace frozen records. The current API spells the hash model_bundle_hash inside Prediction; health/model-card use model_bundle_sha256. Preserve this boundary in adapters rather than renaming the existing public contract.

Latest human label: ACCEPT resolves to the predicted class of that event's prediction_id; CORRECT resolves to selected_class; DEFER and unreviewed resolve to null. ACCEPT after a correction does NOT mean accepting the corrected class. Review events are append-only. One logical submission keeps one idempotency key across retries. A failed request may have committed: report outcome unknown and reconcile; do not promise that nothing was saved.

Every new dataset-scoped operation receives a server-resolved ScopeContext with project_id, dataset_version_id, model_bundle_hash, deployment_allowlist, review_session_id, and actor_id. Apply project membership, dataset selection, and deployment allowlist as an intersection BEFORE counting, ranking, paging, searching, or reading artifacts. Null project scope is permitted only inside explicitly loopback-only single-user mode, never by a browser-provided flag. Scope accompanies caches and exports. Absent data is null plus an unavailable reason, not zero.

Any new route below /v1/ is a local G6 route until an authenticated enterprise wrapper is explicitly installed. Enterprise wrappers use /api/v1/ and existing live-membership checks. UI must call the configured central client; never bypass authorization by falling back from an enterprise failure to a public G6 endpoint.

For a model-scoped analysis, match review events to the explicitly selected prediction_id/model hash and review_session_id. An event on a different model remains in history but does not silently mark the selected model reviewed. If the legacy endpoint has image-global status, adapt it explicitly rather than reinterpreting stored events.

Use one immutable AnalyticsSnapshot per response: schema_version="1", snapshot_id, generated_at_utc, scope, definitions_version="review-v1", counts, rates, warnings, and provenance. scope contains project_id, dataset_version_id, model_bundle_hash, review_session_id, deployment_subset, and reference_kind. It must describe the actual included rows, not the entire collection when a 50-image allowlist is active. One explicit prediction per image; latest review events only unless a metric is explicitly event-based.

counts: total_images, prediction_images, unreviewed_images, decided_images, deferred_images, accepted_images, corrected_images, disagreement_images, qc_flagged_images, touched_images. decided = latest ACCEPT or CORRECT. touched = decided + deferred. Disagreement is effective human label != the reviewed prediction's class, NOT merely action == CORRECT. Legacy redundant corrections must not inflate disagreement. Predictionless images remain visible but are excluded from prediction-agreement denominators.

Each rate is {value: number|null, numerator: int, denominator: int, unavailable_reason: string|null}. review_completion = decided/total_images; touched_fraction = touched/total_images; reviewer_agreement = agreeing valid decided predictions/valid decided predictions; correction_action_rate = corrected/decided; defer_fraction = deferred/touched. Event counts and distinct-image counts have different labels. No denominator -> null.

Hand-check fixture: eight images with one prediction each; two latest ACCEPTs, one genuinely different CORRECT, two latest DEFERs, and three never reviewed. Expected counts: total=8, decided=3, touched=5, deferred=2, unreviewed=3, corrected=1, disagreement=1. Completion=3/8; agreement=2/3; correction=1/3; defer fraction=2/5. Add an old event on one image: current-state counts must remain unchanged. These are test values, NEVER production dashboard constants.

Reviewer agreement is operational concordance, not model accuracy or reference-standard validation. Evaluation metrics must come from separate frozen held-out evidence. Prediction-class frequencies over sampled patches are not tissue area fractions or clinical percent necrosis. Selection-biased review data cannot establish triage benefit. Keep source labels, individual reviews, adjudicated labels, and held-out reference labels separately identified.

Current-state counts use the latest applicable event for each selected image/prediction/session. Reviews linked only to another model are preserved in a separate unmatched_review_images warning/count and are excluded from this model’s agreement/decided denominator; the selected-model state remains unreviewed until reviewed. This must be tested with two model versions for the same image.

## 7. Execution workflow

1. Read this entire task and the current project instructions. Record git status and HEAD; verify the allowed checkout and the task’s write ownership.
2. Inspect the listed files and each prerequisite’s acceptance receipt. Confirm the required symbols/contracts exist at the current code revision. Implemented-looking UI is not proof that a dependency works.
3. Write a short task-specific change plan: current behavior, exact files, contract changes, tests, and actions requiring approval. Do not invent missing values. A missing prerequisite produces BLOCKED with the missing file/symbol/receipt named.
4. Add the acceptance tests below to the named task-owned test file. Use existing test conventions and deterministic fixtures. Run them before implementation and confirm they fail for the intended missing behavior, not a broken environment. If equivalent behavior already exists, demonstrate it and prefer NO_CHANGE_VERIFIED.
5. Perform the implementation steps below in order. After each step, inspect the diff and run its narrowest relevant test. One numbered step is one checkable action; do not jump to downstream tasks.
6. Run every applicable verification command, inspect its terminal exit code, and inspect relevant logs. A skipped real-data test is not a real-data pass. Record the actual test counts rather than copying historical counts.
7. Rehearse the task’s user-visible scenario on an isolated session. For UI work inspect loading, empty, failure, permission-denied, success, and rapid-navigation states. Verify keyboard access and the supported viewport. Screenshots must show the tested build.
8. Re-read the diff against the task boundary. Produce the receipt and stop. The integrator reviews and accepts the result before any dependent task begins.

## 8. Task-specific implementation steps

- [ ] **Step 01.** Build the accessible table first, then add color intensity as redundant information.

- [ ] **Step 02.** Keep canonical ordering and explicit axis titles visible at all viewport sizes.

- [ ] **Step 03.** Show eligible_n, excluded reasons, scope and reference-kind banner beside the matrix.

- [ ] **Step 04.** Format zero-denominator cells as N/A with an explanation, not 0%.

- [ ] **Step 05.** Add a counts/proportions toggle that never changes which rows were included.

- [ ] **Step 06.** Wire off-diagonal cells into A005 with both class filters.

- [ ] **Step 07.** Do not visually combine historical evaluation and routine reviewer matrices under one unlabeled selector.

- [ ] **Step 08.** Provide a plain-text/table export path through A011 when implemented.

## 9. Acceptance tests — implement before the feature

Assign the IDs below to test names or comments so the reviewer can trace each assertion to executable evidence. Use the designated task test file and existing framework conventions. Where a check is necessarily manual or real-asset dependent, say so and keep it NOT_RUN until observed; it is not replaced by a fixture pass.

- [ ] **A007-AT01.** Cell labels and drill-down filters agree exactly.

- [ ] **A007-AT02.** A zero-support row has no invented normalized percentages.

- [ ] **A007-AT03.** Count and proportion modes preserve matrix membership.

- [ ] **A007-AT04.** Keyboard users can activate every populated cell.

- [ ] **A007-AT05.** The screen labels the reference as reviewer decision, not ground truth.

### Boundary and failure review

Always exercise the applicable cases: no rows; one row; duplicate input/retry; missing or malformed values; unavailable artifact; unauthorized object; changed project/model/session; stale response; concurrent revision; canceled job/request; and partial failure. Use null plus a reason for undefined metrics. A permission error must not fall back to an unscoped or unauthenticated API. A timeout after a write means outcome unknown until reconciled.

## 10. Verification commands

Working directory: **repository root**
```text
npm --prefix app/g6/frontend test -- src/test/review-comparison.test.tsx
```

Working directory: **repository root**
```text
npm --prefix app/g6/frontend run build
```

Working directory: **repository root**
```text
git diff --check
```

Use the project’s installed/locked environment. Missing dependencies are setup blockers, not permission to install them. Existing suite names or CLI options may have changed: inspect them and record any equivalent command used. Do not launch two test runners that share output directories or databases. Exit 0 is required where a command is run; skipped real-artifact checks remain SKIPPED.

## 11. User-visible rehearsal

Click an off-diagonal cell and inspect the exact patches behind it.

Use a disposable session or test database, identify the actual data scope, and state the expected visible result before clicking. For a non-UI task show the exact API/CLI output and provenance instead. Do not alter a model score, reference label, or real review to make the example more dramatic. Verify refresh/reload behavior where data is saved.

## 12. Receipt and stopping point

Return a plain-language result and a machine-readable receipt with:
- task_id; status: IMPLEMENTED_VERIFIED | NO_CHANGE_VERIFIED | PARTIAL | BLOCKED | FAILED;
- baseline_sha; candidate_sha if committed; otherwise baseline_sha plus SHA-256 of the reviewed diff; actual branch/worktree;
- changed_files and why each is necessary; produced symbols/endpoints/types; dependency receipts inspected;
- tests: exact command, cwd, terminal exit_code, passed/failed/skipped counts when available, and evidence path;
- acceptance: one entry for each named test below with PASS | FAIL | SKIPPED | NOT_RUN and evidence;
- data_mode: synthetic_fixture | real_authorized_data | verified_replay, actual scope, model/artifact identities;
- canonical_data_unchanged: verified true/false, or not_checked with reason; never assume it;
- UI/browser observations where applicable; remaining limitations; blocked prerequisites and required approval;
- one exact next action for the integrator. Do not start it.

Test success and acceptance are separate: a reviewer may reject a green implementation for an incorrect requirement, security boundary, or misleading scientific claim. Do not mark a task accepted yourself. Save an optional task-owned receipt at docs/task-evidence/A007-receipt.json only; do not replace global steering files.

**STOP after this task.** Do not begin the next dependency or feature, continue in the background, or schedule another run. A missing prerequisite requires a precise blocker, not a fake completed screen. A script that was prepared but not executed is PREPARED, not a verified experiment or deployment.

## 13. Source and implementation references

- [Inspected repository snapshot](https://github.com/Enksodsoon/osteopatch-review/tree/57c1efc77e67f691708bb9a825c621953fcea358)
- [scikit-learn: model evaluation metrics](https://scikit-learn.org/stable/modules/model_evaluation.html)

Repository links identify the inspected planning baseline. Recheck the real checkout before editing. Public documentation is implementation guidance, not a claim that a library is already installed or that the app currently supports the feature.
