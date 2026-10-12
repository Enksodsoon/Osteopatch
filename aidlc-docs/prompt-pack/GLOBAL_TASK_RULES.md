# Global task rules

You are implementing ONE task in the existing OsteoPatch Review repository. Do not execute the entire roadmap. The owner wants an educational/research patch-review application and a truthful working demo, not a clinical product.

Repository: Enksodsoon/osteopatch-review. Known local checkout: C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff. Inspected remote baseline: 57c1efc77e67f691708bb9a825c621953fcea358. This is a reference snapshot, not an instruction to reset to it. The current local checkout may contain newer, uncommitted work. Read the actual checkout and its authorized project instructions first.

Operate on a clean isolated task branch/worktree approved by the owner or integrator. Record current branch, HEAD, and dirty files. Never reset --hard, delete branches/PRs, restore another worker’s files, stage -A, force-push, or overwrite uncommitted work. A task branch alone does not isolate two workers sharing the same directory. When another worker owns a required file, stop with the exact conflict rather than editing around it. New worktrees do not automatically contain ignored runtime data: use a verified read-only asset source plus a throwaway writable database, not the canonical database.

Reuse working features and installed libraries. Do not add a parallel API, duplicate role system, new frontend framework, global CSS override pile, or second source of model truth. All proposed new file paths and symbols below are design targets, not claims they already exist. If the equivalent component exists elsewhere, extend it and document the mapping. NEXT in a migration path means the next unused migration identifier chosen by the integrator; never create a literal NEXT migration or edit an applied migration.

Do not install/update dependencies, call a paid API, download model weights/datasets, train/calibrate a model, create cloud resources, change IAM, publish data, deploy, or schedule workers unless that action has its own explicit authorization. Default additional budget is USD 0. Never request secrets in chat or print credentials. Prepare-only deployment work is not permission to deploy. Do not claim regulatory compliance or clinical validation.

Use only authorized, de-identified assets and real evidence. Synthetic data belongs in labeled test fixtures, not production screenshots or claimed model results. Preserve the original frozen evaluation and all model/image/review provenance. Keep source-group identity separate from patient identity. Do not manufacture missing WSI coordinates, physical scale, metrics, tissue labels, approvals, heatmaps, or successful tests.

Write tests first. Read failure output before changing code. Run targeted tests, then affected regressions. Fix defects within this task; a missing prerequisite or unrelated defect becomes a precise blocker, not an invitation to rebuild the project. After two unsuccessful repair attempts at the same failure, document the failing test, suspected cause, and attempted changes for review; do not weaken the test or continue blindly.

Never commit, push, merge, or release automatically. Return the focused diff and an evidence receipt for the integrator. When the execution brief explicitly authorizes a commit, stage only reviewed task-owned paths and verify the staged diff. A task is not accepted merely because code was written or a process started.

## Workflow

1. Read this entire task and the current project instructions. Record git status and HEAD; verify the allowed checkout and the task’s write ownership.
2. Inspect the listed files and each prerequisite’s acceptance receipt. Confirm the required symbols/contracts exist at the current code revision. Implemented-looking UI is not proof that a dependency works.
3. Write a short task-specific change plan: current behavior, exact files, contract changes, tests, and actions requiring approval. Do not invent missing values. A missing prerequisite produces BLOCKED with the missing file/symbol/receipt named.
4. Add the acceptance tests below to the named task-owned test file. Use existing test conventions and deterministic fixtures. Run them before implementation and confirm they fail for the intended missing behavior, not a broken environment. If equivalent behavior already exists, demonstrate it and prefer NO_CHANGE_VERIFIED.
5. Perform the implementation steps below in order. After each step, inspect the diff and run its narrowest relevant test. One numbered step is one checkable action; do not jump to downstream tasks.
6. Run every applicable verification command, inspect its terminal exit code, and inspect relevant logs. A skipped real-data test is not a real-data pass. Record the actual test counts rather than copying historical counts.
7. Rehearse the task’s user-visible scenario on an isolated session. For UI work inspect loading, empty, failure, permission-denied, success, and rapid-navigation states. Verify keyboard access and the supported viewport. Screenshots must show the tested build.
8. Re-read the diff against the task boundary. Produce the receipt and stop. The integrator reviews and accepts the result before any dependent task begins.

## Receipt

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

Test success and acceptance are separate: a reviewer may reject a green implementation for an incorrect requirement, security boundary, or misleading scientific claim. Do not mark a task accepted yourself. Save an optional task-owned receipt at docs/task-evidence/<TASK_ID>-receipt.json only; do not replace global steering files.
