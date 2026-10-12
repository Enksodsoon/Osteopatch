# Z012 — Build the animated HTML demo presentation using real application evidence

**Task:** Z012  |  **Track:** PLATFORM  |  **Work type:** frontend

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

**Deliverable:** Build the animated HTML demo presentation using real application evidence.

**Baseline stance:** New or partially available; inspect and reuse existing implementation.

**Additional gate:** No additional authorization beyond the bounded task should be assumed. All cloud, publication, model-fitting, data-download, and destructive actions remain gated.

A static mockup or a video is a fallback presentation artifact, not proof of a functional deployed application. Report local, offline, replay, and deployed status separately. Never reset canonical research data to restart a demo.

**Not in this task:** every other roadmap feature, automatic retraining, clinical deployment, broad refactoring, unrelated cleanup, replacement of existing authoring/steering files, or publishing/merging the work. Fix a dependency only after the integrator assigns that dependency task; do not silently absorb it.

## 3. Prerequisites

- **Z009 — Create accurate GitHub documentation, screenshots, and demo presentation materials**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.
- **A010 — Create a reproducible research review report page**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.
- **M004 — Build the Model Performance and limitation-detail pages**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.

### Exact prerequisite interfaces to inspect
**Z009:** Documentation describes the tested release scope, not every roadmap feature. ScreenshotManifest records code_sha, route, scope, mode, capture_time and asset hashes. Presentation outline:problem -> review loop -> real image/AI explanation -> human correction -> statistics/provenance -> limitations -> engineering/deployment.

**A010:** ResearchReport is bound to one AnalyticsSnapshot ID and includes scope, model identity, date, counts, reviewer comparison, QC coverage, known limitations and definitions. Print/HTML export uses that same snapshot; no automatic clinical pathology report is produced.

**M004:** Performance page consumes M003 only and clearly labels frozen out-of-fold evidence. Present headline metrics, per-class support/precision/recall/F1, available confusion matrix, fold-level caveats, and full limitation links. Operational reviewer statistics live on a different page.

## 4. Inspect before editing

- `docs/demo/presentation-outline.md`
- `docs/demo/demo-script.md`
- `docs/demo/screenshot-manifest.json`
- `docs/images/demo-release/`

Also read the current tests covering these files, the relevant API/schema definitions, and the task dependency receipts. Paths listed as inputs from a previous task may not exist until that task is accepted. Search the repository for an equivalent implementation before creating a new one; never infer file content from its name.

## 5. Allowed change surface

- `demo/presentation/index.html`
- `demo/presentation/presentation.css`
- `demo/presentation/presentation.js`
- `demo/presentation/assets/`
- `app/g6/frontend/e2e/presentation.spec.ts`

These are proposed task-owned paths. Existing files are modified narrowly; absent files are created only when the task needs them. Do not replace an entire large source file for a one-function change. Keep source and test changes together. A minimal integration hook is allowed in the existing app/router/navigation/type file only after this task has exclusive ownership of that shared file. Limit it to the module import, router registration, capability-gated navigation entry, or exact response type required by this deliverable, and list that hook in the receipt. If another worker owns it, return the unapplied hook to the integrator and mark integration pending; do not claim the user-visible feature accepted. Any broader change requires a revised task boundary.

## 6. Input/output contract

A standalone 16:9 HTML presentation with 6–8 substantive slides, local assets, previous/next controls, keyboard navigation and print/reduced-motion support. It presents the verified release story: purpose, real H&E workflow, qualified attribution, human correction, statistics, known limitations and implemented architecture. No animated mockup may be presented as a live running app.

### Non-negotiable domain semantics

Canonical classes are exactly NON_TUMOR, VIABLE_TUMOR, NECROSIS. Review actions are ACCEPT, CORRECT, DEFER; latest review status is unreviewed, reviewed, or deferred. Mixed tissue, artifact, poor quality, unknown, and deferred are metadata/review states, never an added model class.

Prediction identity is (prediction_id, image_id, model_bundle_hash, inference_kind). An analysis must select exactly one explicit prediction per image and must not silently mix model versions or replace frozen records. The current API spells the hash model_bundle_hash inside Prediction; health/model-card use model_bundle_sha256. Preserve this boundary in adapters rather than renaming the existing public contract.

Latest human label: ACCEPT resolves to the predicted class of that event's prediction_id; CORRECT resolves to selected_class; DEFER and unreviewed resolve to null. ACCEPT after a correction does NOT mean accepting the corrected class. Review events are append-only. One logical submission keeps one idempotency key across retries. A failed request may have committed: report outcome unknown and reconcile; do not promise that nothing was saved.

Every new dataset-scoped operation receives a server-resolved ScopeContext with project_id, dataset_version_id, model_bundle_hash, deployment_allowlist, review_session_id, and actor_id. Apply project membership, dataset selection, and deployment allowlist as an intersection BEFORE counting, ranking, paging, searching, or reading artifacts. Null project scope is permitted only inside explicitly loopback-only single-user mode, never by a browser-provided flag. Scope accompanies caches and exports. Absent data is null plus an unavailable reason, not zero.

Any new route below /v1/ is a local G6 route until an authenticated enterprise wrapper is explicitly installed. Enterprise wrappers use /api/v1/ and existing live-membership checks. UI must call the configured central client; never bypass authorization by falling back from an enterprise failure to a public G6 endpoint.

For a model-scoped analysis, match review events to the explicitly selected prediction_id/model hash and review_session_id. An event on a different model remains in history but does not silently mark the selected model reviewed. If the legacy endpoint has image-global status, adapt it explicitly rather than reinterpreting stored events.

DemoRun contains run_id, session_id, dataset_version_id, allowlisted_image_ids, model_bundle_hash, code_sha, scenario_version, run_mode(live_local|live_deployed|verified_replay), asset_manifest_sha256, created_at_utc, and isolated_review_store_id. Every screen/export indicates its actual data scope and whether inference/attribution is live or precomputed replay. Synthetic test data is not displayed as real pathology data.

Create a fresh isolated demo review store from an approved pristine template. Never reset, clear, or overwrite the canonical 1,144-image research review DB or a shared production table. Restart creates a new demo session. Saved reviews must survive refresh within that session. Scope every new analytic view to that same session.

Curated scenarios: clear example; ambiguous score example; genuine prediction-versus-approved-reference disagreement; contrastive attribution. Each scenario points to a real permitted image and evidence. If no approved adjudication exists, say dataset-label disagreement, not confirmed model error. Never change a prediction to make the script compelling. Fixed example choices are disclosed as curated, not random/external validation.

Release gate separately records backend tests, frontend tests/build, fixture integration, real-data integration, actual browser journey, dependency/security review, and live deployment. PASS requires observed results for the stated code SHA. SKIPPED, BLOCKED, STALE, and NOT_RUN are not PASS. Real attribution execution and honest unavailable behavior are separate test outcomes.

Default additional cloud budget is USD 0. Preparing a deployment package is allowed; creating resources, synchronizing public assets, invalidating a CDN, deploying a Lambda/container, changing IAM, or publishing a release requires explicit authorization and valid scoped credentials. Never paste secrets into the chat or repository. UI-only deployment does not deploy new backend endpoints. Stop rather than serving an incompatible frontend/backend pair.

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

- [ ] **Step 01.** Read the accepted outline and screenshots, then map each slide to its evidence ID before creating layout.

- [ ] **Step 02.** Build a single local HTML entry point with semantic slide sections; no remote fonts, CDN dependency, paid framework or analytics tracker is needed.

- [ ] **Step 03.** Use the existing minimalist earth-tone direction, readable large typography, generous space and actual app screenshots with legible captions.

- [ ] **Step 04.** Implement left/right keyboard navigation, labeled buttons, current-slide indicator, focus management and a visible exit/fullscreen affordance.

- [ ] **Step 05.** Use short opacity/translation transitions only; disable transitions under prefers-reduced-motion and allow every slide to be reached without animation.

- [ ] **Step 06.** Populate numbers from the accepted exported report snapshot or embed a frozen display payload with a manifest hash; do not type illustrative percentages into the deck.

- [ ] **Step 07.** Mark the original/recovered model distinction, review-versus-evaluation statistics, data subset and live/replay status where shown.

- [ ] **Step 08.** Test local offline opening, 1920×1080 and 1366×768 layouts, keyboard-only navigation, print layout and the absence of blank/broken assets. Record screenshots of the rendered presentation.

## 9. Acceptance tests — implement before the feature

Assign the IDs below to test names or comments so the reviewer can trace each assertion to executable evidence. Use the designated task test file and existing framework conventions. Where a check is necessarily manual or real-asset dependent, say so and keep it NOT_RUN until observed; it is not replaced by a fixture pass.

- [ ] **Z012-AT01.** Every substantive slide references a real accepted screenshot, report or source rather than fabricated app state.

- [ ] **Z012-AT02.** Navigation reaches every slide and has no keyboard trap.

- [ ] **Z012-AT03.** Reduced-motion mode has no required animation or automatic slide advance.

- [ ] **Z012-AT04.** The deck opens offline with all authorized assets and no external tracking request.

- [ ] **Z012-AT05.** Displayed model/statistical values match the accepted report and the limitations slide remains included.

### Boundary and failure review

Always exercise the applicable cases: no rows; one row; duplicate input/retry; missing or malformed values; unavailable artifact; unauthorized object; changed project/model/session; stale response; concurrent revision; canceled job/request; and partial failure. Use null plus a reason for undefined metrics. A permission error must not fall back to an unscoped or unauthenticated API. A timeout after a write means outcome unknown until reconciled.

## 10. Verification commands

Working directory: **repository root, only after inspecting the existing isolated real-data harness and satisfying its prerequisites**
```text
uv run python scripts/e2e_ui.py
```

Working directory: **repository root**
```text
git diff --check
```

Use the project’s installed/locked environment. Missing dependencies are setup blockers, not permission to install them. Existing suite names or CLI options may have changed: inspect them and record any equivalent command used. Do not launch two test runners that share output directories or databases. Exit 0 is required where a command is run; skipped real-artifact checks remain SKIPPED.

## 11. User-visible rehearsal

Present the complete HTML deck, then switch to the actual app for the live reviewer interaction.

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

Test success and acceptance are separate: a reviewer may reject a green implementation for an incorrect requirement, security boundary, or misleading scientific claim. Do not mark a task accepted yourself. Save an optional task-owned receipt at docs/task-evidence/Z012-receipt.json only; do not replace global steering files.

**STOP after this task.** Do not begin the next dependency or feature, continue in the background, or schedule another run. A missing prerequisite requires a precise blocker, not a fake completed screen. A script that was prepared but not executed is PREPARED, not a verified experiment or deployment.

## 13. Source and implementation references

- [Inspected repository snapshot](https://github.com/Enksodsoon/osteopatch-review/tree/57c1efc77e67f691708bb9a825c621953fcea358)
- [Playwright: testing user-visible behavior](https://playwright.dev/docs/best-practices)
- [Existing limitations catalog](https://github.com/Enksodsoon/osteopatch-review/blob/57c1efc77e67f691708bb9a825c621953fcea358/app/g6/backend/osteopatch/limitations.py)

Repository links identify the inspected planning baseline. Recheck the real checkout before editing. Public documentation is implementation guidance, not a claim that a library is already installed or that the app currently supports the feature.
