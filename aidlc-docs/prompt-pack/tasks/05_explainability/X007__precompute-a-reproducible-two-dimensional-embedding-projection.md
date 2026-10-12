# X007 — Precompute a reproducible two-dimensional embedding projection

**Task:** X007  |  **Track:** PLATFORM  |  **Work type:** script

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

**Deliverable:** Precompute a reproducible two-dimensional embedding projection.

**Baseline stance:** New or partially available; inspect and reuse existing implementation.

**Additional gate:** No additional authorization beyond the bounded task should be assumed. All cloud, publication, model-fitting, data-download, and destructive actions remain gated.

A stored heatmap is permitted only as a checksum-verified precomputed artifact with explicit provenance and a precomputed label. It must never masquerade as a new live calculation or verified tissue segmentation.

**Not in this task:** every other roadmap feature, automatic retraining, clinical deployment, broad refactoring, unrelated cleanup, replacement of existing authoring/steering files, or publishing/merging the work. Fix a dependency only after the integrator assigns that dependency task; do not silently absorb it.

## 3. Prerequisites

- **X004 — Extract versioned embeddings with the existing approved encoder**: require an accepted receipt or demonstrate the equivalent existing behavior before starting.

### Exact prerequisite interfaces to inspect
**X004:** EmbeddingArtifact follows the attribution contract. Extract features at a documented fixed layer of an already approved locally available encoder. Output one finite vector per approved image plus ordered IDs; no classifier retraining or foundation-model download.

## 4. Inspect before editing

- `app/g6/backend/osteopatch/embedding_artifacts.py`
- `pyproject.toml`

Also read the current tests covering these files, the relevant API/schema definitions, and the task dependency receipts. Paths listed as inputs from a previous task may not exist until that task is accepted. Search the repository for an equivalent implementation before creating a new one; never infer file content from its name.

## 5. Allowed change surface

- `scripts/project_embeddings.py`
- `app/g6/backend/osteopatch/projection_artifacts.py`
- `app/g6/backend/tests/test_projection_artifacts.py`

These are proposed task-owned paths. Existing files are modified narrowly; absent files are created only when the task needs them. Do not replace an entire large source file for a one-function change. Keep source and test changes together. A minimal integration hook is allowed in the existing app/router/navigation/type file only after this task has exclusive ownership of that shared file. Limit it to the module import, router registration, capability-gated navigation entry, or exact response type required by this deliverable, and list that hook in the receipt. If another worker owns it, return the unapplied hook to the integrator and mark integration pending; do not claim the user-visible feature accepted. Any broader change requires a revised task boundary.

## 6. Input/output contract

ProjectionArtifact{projection_id, embedding_artifact_sha256, method:"pca"|"umap", parameters, seed, ordered_image_ids, xy, artifact_sha256}. Start with deterministic PCA; UMAP is optional after an explicit dependency/license review. No labels are used to optimize apparent separation.

### Non-negotiable domain semantics

Canonical classes are exactly NON_TUMOR, VIABLE_TUMOR, NECROSIS. Review actions are ACCEPT, CORRECT, DEFER; latest review status is unreviewed, reviewed, or deferred. Mixed tissue, artifact, poor quality, unknown, and deferred are metadata/review states, never an added model class.

Prediction identity is (prediction_id, image_id, model_bundle_hash, inference_kind). An analysis must select exactly one explicit prediction per image and must not silently mix model versions or replace frozen records. The current API spells the hash model_bundle_hash inside Prediction; health/model-card use model_bundle_sha256. Preserve this boundary in adapters rather than renaming the existing public contract.

Latest human label: ACCEPT resolves to the predicted class of that event's prediction_id; CORRECT resolves to selected_class; DEFER and unreviewed resolve to null. ACCEPT after a correction does NOT mean accepting the corrected class. Review events are append-only. One logical submission keeps one idempotency key across retries. A failed request may have committed: report outcome unknown and reconcile; do not promise that nothing was saved.

Every new dataset-scoped operation receives a server-resolved ScopeContext with project_id, dataset_version_id, model_bundle_hash, deployment_allowlist, review_session_id, and actor_id. Apply project membership, dataset selection, and deployment allowlist as an intersection BEFORE counting, ranking, paging, searching, or reading artifacts. Null project scope is permitted only inside explicitly loopback-only single-user mode, never by a browser-provided flag. Scope accompanies caches and exports. Absent data is null plus an unavailable reason, not zero.

Any new route below /v1/ is a local G6 route until an authenticated enterprise wrapper is explicitly installed. Enterprise wrappers use /api/v1/ and existing live-membership checks. UI must call the configured central client; never bypass authorization by falling back from an enterprise failure to a public G6 endpoint.

For a model-scoped analysis, match review events to the explicitly selected prediction_id/model hash and review_session_id. An event on a different model remains in history but does not silently mark the selected model reviewed. If the legacy endpoint has image-global status, adapt it explicitly rather than reinterpreting stored events.

Attribution is a separate evidence artifact, not a new prediction and not tissue segmentation. Metadata identifies image_id, source_image_sha256, source_prediction_id, prediction_model_hash, attribution_model_id/hash, target_a, target_b, method_version, target_layer, preprocessing_hash, dimensions, generated_at_utc, cached flag, and latency_ms. target_a and target_b are different members of the three canonical classes.

The target is the contrastive logit difference logit(A)-logit(B). The stored G4 predictions and the behaviorally reconstructed attribution model must remain explicitly distinct; do not relabel reconstructed weights as recovered original weights. Display the repository's recovery disclosure and non-segmentation disclaimer on success AND every error state.

Render an overlay only after the bytes decode and their image/model/pair identity matches the current selection. Key request state by image_id plus ordered class pair plus artifact hash; cancel or ignore outdated responses. Pair reversal changes the computation, not merely the legend. No attribution placeholder may masquerade as a computed heatmap.

EmbeddingArtifact uses encoder_id, encoder_sha256, feature_layer, preprocessing_hash, source_image_sha256, dataset_version_id, ordered image IDs, shape, dtype, and artifact_sha256. Similarity uses a compatible artifact only; score is not diagnostic probability. Exclude the query image and exact duplicate pixel hashes. A 2D projection is exploratory visualization, not a clinical cluster label or an evaluation result.

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

- [ ] **Step 01.** Validate the complete embedding artifact before projection.

- [ ] **Step 02.** Implement deterministic PCA to 2D as the no-new-heavy-dependency baseline; record centering/scaling decisions.

- [ ] **Step 03.** Handle fewer than three samples or degenerate rank with a clear limited/unavailable outcome.

- [ ] **Step 04.** Store projected coordinates with exact ordered IDs and upstream hash.

- [ ] **Step 05.** Never refit a projection every time the user changes a class-color filter; preserve coordinate stability.

- [ ] **Step 06.** If adding UMAP later, record package version, seed, neighbors, min_dist and fit population; mark it exploratory.

- [ ] **Step 07.** Test row/ID alignment and repeatability, not whether class clusters look attractive.

- [ ] **Step 08.** Do not add clinical cluster names or performance scores based on visual separation.

## 9. Acceptance tests — implement before the feature

Assign the IDs below to test names or comments so the reviewer can trace each assertion to executable evidence. Use the designated task test file and existing framework conventions. Where a check is necessarily manual or real-asset dependent, say so and keep it NOT_RUN until observed; it is not replaced by a fixture pass.

- [ ] **X007-AT01.** Repeated PCA on the same artifact produces equivalent coordinates within tolerance.

- [ ] **X007-AT02.** Filtering changes visible points, not their stored positions.

- [ ] **X007-AT03.** NaN embeddings are rejected before projection.

- [ ] **X007-AT04.** Projection IDs change when upstream features/parameters change.

- [ ] **X007-AT05.** A degenerate dataset does not invent meaningful cluster separation.

### Boundary and failure review

Always exercise the applicable cases: no rows; one row; duplicate input/retry; missing or malformed values; unavailable artifact; unauthorized object; changed project/model/session; stale response; concurrent revision; canceled job/request; and partial failure. Use null plus a reason for undefined metrics. A permission error must not fall back to an unscoped or unauthenticated API. A timeout after a write means outcome unknown until reconciled.

## 10. Verification commands

Working directory: **repository root**
```text
uv run pytest app/g6/backend/tests/test_projection_artifacts.py -q
```

Working directory: **repository root**
```text
git diff --check
```

Use the project’s installed/locked environment. Missing dependencies are setup blockers, not permission to install them. Existing suite names or CLI options may have changed: inspect them and record any equivalent command used. Do not launch two test runners that share output directories or databases. Exit 0 is required where a command is run; skipped real-artifact checks remain SKIPPED.

## 11. User-visible rehearsal

Generate a real, versioned exploratory map from the approved embeddings.

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

Test success and acceptance are separate: a reviewer may reject a green implementation for an incorrect requirement, security boundary, or misleading scientific claim. Do not mark a task accepted yourself. Save an optional task-owned receipt at docs/task-evidence/X007-receipt.json only; do not replace global steering files.

**STOP after this task.** Do not begin the next dependency or feature, continue in the background, or schedule another run. A missing prerequisite requires a precise blocker, not a fake completed screen. A script that was prepared but not executed is PREPARED, not a verified experiment or deployment.

## 13. Source and implementation references

- [Inspected repository snapshot](https://github.com/Enksodsoon/osteopatch-review/tree/57c1efc77e67f691708bb9a825c621953fcea358)

Repository links identify the inspected planning baseline. Recheck the real checkout before editing. Public documentation is implementation guidance, not a claim that a library is already installed or that the app currently supports the feature.
