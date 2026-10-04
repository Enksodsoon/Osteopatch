# 05 — Kiro implementation plan and review gates

> **For Kiro:** execute through the approved AI-DLC workflow, one unit at a time. This is a proposed plan for review, not permission to implement every unit now. Use test-first changes and record evidence. The execution method is Kiro; do not redirect the user to another agent product.

**Goal:** deliver a real educational three-class patch-review application with accountable human correction.
**Architecture:** a shared Python model/domain package, local FastAPI/SQLite adapters, a React frontend, and one separately approved AWS deployment with bounded asynchronous inference.
**Stack:** Python/PyTorch/torchvision, React/Vite/TypeScript, pytest, frontend unit tests and Playwright; AWS SAM/CloudFormation for the selected cloud target.
**Spec:** [PROJECT_BRIEF](../PROJECT_BRIEF.md), [requirements](03_product_ux_and_acceptance.md), [model plan](02_model_and_evaluation_plan.md), and [contracts](08_data_and_api_contracts.md).

## Global constraints

Canonical order is `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. Educational scope only. No source substitution, unverifiable patient split, fabricated results, automatic retraining, unapproved spending, or public unauthenticated review writes. Preserve source labels and predictions. No external code is copied before its licensing and dependencies are checked.

All checklist items below begin unexecuted. Commands are **future verification commands after Kiro implements the relevant files**. They are not currently runnable application instructions and do not establish passed tests.

## Review focus

Unknown labels must fail instead of becoming viable tumor. Duplicate/patient leakage must block an independent-evaluation claim. Class order and preprocessing must agree between training and serving. Expired credentials, failed/stale jobs and unavailable attribution must be visible without losing review history. Concurrent or repeated saves must not erase history or duplicate events.

## Proposed repository boundaries

- `src/osteopatch/contracts.py`: shared typed schemas/enums/protocols.
- `src/osteopatch/data/`: manifest, label mapping, duplicate audit, verified split.
- `src/osteopatch/ml/`: model, preprocessing, training, evaluation, calibration and bundle loading.
- `src/osteopatch/domain/`: job/review policy, transactions and exports.
- `src/osteopatch/explain/`: attribution and alignment.
- `src/osteopatch/adapters/`: local HTTP, storage, dispatch and cloud handlers.
- `apps/web/src/`: workbench, viewer, review controls, API client and model card.
- `infra/template.yaml`: the approved cloud stack only.
- `tests/`, `apps/web/tests/`, `tests/e2e/`: requirements-linked tests.
- `artifacts/`: versioned run outputs; large data and secrets excluded from Git.
- `aidlc-docs/`: actual questions, decisions, approvals, state, audit and unit evidence.

## U0 — Inception and source decision

**Deliverable:** an approved scope and a defensible source route. No application code or paid resources.
**Files:** create actual AI-DLC requirements, workflow plan, environment report, source decision, risk register and approval log under `aidlc-docs/inception/`.
**Inputs:** this handoff and authorized read-only environment information.
**Outputs:** precise constraints for U1; open blockers remain visible.

- [ ] Detect workspace, installed Kiro/AI-DLC workflow and relevant local hardware without printing credentials.
- [ ] Read official source metadata; resolve the IDC-versus-TCIA requirement. Do not invent a bucket prefix or download an entire registry.
- [ ] Write a short file-based questionnaire, prefilling known facts and proposed defaults.
- [ ] Write numbered requirements and a staged implementation plan; identify unsupported services/permissions and unapproved costs.
- [ ] Present G0 (requirements/workflow) and G1 (exact source/access) decisions. Stop for the owner.

**Evidence:** document paths, retrieved metadata, unresolved checks and recorded owner decisions. No “tests passed” claim is appropriate here.

## U1 — Data ingestion and split audit

**Gate before starting:** G0/G1 approved and the code-generation plan for this unit reviewed.
**Create:** `src/osteopatch/contracts.py`, `data/manifest.py`, `data/labels.py`, `data/audit.py`, `data/splits.py`, `tests/data/test_labels.py`, `test_manifest.py`, `test_splits.py`.
**Produces:** `load_manifest`, `audit_manifest`, `validate_split` as defined in the contracts, plus `manifest.csv`, `split_manifest.csv` and a dataset card.

- [ ] Write failing tests: `test_unknown_label_rejected`, `test_duplicate_key_rejected`, `test_unmatched_csv_image_rejected`, `test_patient_overlap_rejected`, `test_parent_derivatives_share_split`.
- [ ] Run `python -m pytest tests/data -q` and record the expected initial failures.
- [ ] Implement the minimal strict importer/auditor; download only the approved source within its byte limit. Reconcile actual schema, images and labels.
- [ ] Run the tests again and the real data audit; attach patient × class counts, duplicates/exclusions, provenance and exact split hashes.
- [ ] Commit the reviewed unit without raw data/secrets; present **G2: data/label/split approval**. Stop before training.

**Rejectable outcome:** unverifiable patient IDs or missing class coverage. A demo-only fallback must be explicitly labelled and approved, never silently described as independent validation.

## U2 — Train and evaluate the bounded baseline

**Gate:** G2 and a local/paid compute allowance approved. Paid compute requires separate explicit budget approval even when local training is approved.
**Create:** `ml/model.py`, `ml/preprocess.py`, `ml/train.py`, `ml/evaluate.py`, `ml/calibrate.py`, `ml/bundle.py`, `tests/ml/test_bundle.py`, `test_preprocess.py`, `test_metrics.py`.
**Consumes:** approved manifests and class map.
**Produces:** `load_model_bundle`, `predict_image`, a real model bundle, evaluation and model card.

- [ ] Write failing tests: `test_output_class_order`, `test_train_serve_transform_equal`, `test_bundle_hash_mismatch_rejected`, `test_scores_finite_and_normalized`, `test_missing_class_metrics_explicit`.
- [ ] Run `python -m pytest tests/ml -q` to establish failures, then implement the model/transform/artifact contract.
- [ ] Profile hardware and establish the per-run stop limit. Run only the approved head/fine-tuning experiments; record seeds, configuration, logs and all failures.
- [ ] Select on validation; fit calibration only where justified; freeze the candidate and review policy before locked testing. Report true metrics and limitations, including a failed baseline comparison if that occurs.
- [ ] Run tests and one real image inference, commit reproducible code and present **G3: model/evaluation acceptance**.

**Evidence:** weights and checksums, learning logs, baseline comparison, class support, confusion counts, calibration status and explicit no-generalization caveat where required. No accuracy threshold may be invented after seeing the test results.

## U3 — Local end-to-end vertical slice

**Gate:** G3 accepted for the intended educational use, with limitations visible.
**Create:** `domain/jobs.py`, `domain/reviews.py`, `adapters/sqlite_store.py`, `adapters/local_worker.py`, `adapters/local_api.py`, `apps/web/src/api/`, `pages/Workbench.tsx`, `components/ReviewEditor.tsx`, `tests/domain/`, `tests/api/`, `tests/e2e/review-flow.spec.ts`.
**Consumes:** real U2 bundle; typed contracts.
**Produces:** `submit_job`, `save_review`; working gallery → job → scores → saved review flow.

- [ ] Write failing tests for invalid IDs, job failure, source-label hiding, immutable predictions, retry idempotency, stale revision conflicts and persisted review state.
- [ ] Run `python -m pytest tests/domain tests/api -q` and record failures; implement minimal domain logic and SQLite transactions.
- [ ] Build the React gallery and review flow using the real API. Clearly label any test fixtures; they must not replace the real model in demo mode.
- [ ] Run backend tests, frontend type/unit checks and `npx playwright test tests/e2e/review-flow.spec.ts` from the configured project root. Restart the local service and verify a saved correction remains.
- [ ] Commit; present **G4: local workflow acceptance** with an actual demonstration and exact commands/results.

**Coverage:** FR-01/02/03/04/07/08/09/12, NFR-02/03/05, SAF-03/04. Saving a correction must never change the source label or deployed model.

## U4 — Review prioritization, attribution and polished UX

**Gate:** G4 accepted; no new paid services needed.
**Create:** `domain/review_policy.py`, `domain/exports.py`, `explain/gradcam.py`, `apps/web/src/components/ImageViewer.tsx`, `ScorePanel.tsx`, `pages/ReviewHistory.tsx`, `pages/ModelCard.tsx`, `tests/explain/`, `tests/e2e/uncertainty.spec.ts`, `tests/e2e/accessibility.spec.ts`.
**Produces:** `apply_review_policy`, `attribute_image`, versioned explanations, history/export and complete educational interface.

- [ ] Write failing tests for exact threshold boundaries, stable tie ordering, zero-denominator metrics, explicit attribution failure, target-class identity, image alignment, complete audit export and visible disclaimer.
- [ ] Run the targeted tests; implement deterministic policy and actual Grad-CAM with gradients enabled. Test a parameter-randomization or perturbation sanity check and document that this does not establish clinical faithfulness.
- [ ] Add zoom/pan, original/overlay toggle, all score bars, explanations of flags, defer reasons, history and role-controlled label reveal.
- [ ] Run unit and end-to-end tests; check keyboard-only interaction, narrow screens and a failed attribution request. A small usability pilot may compare finding/reviewing ambiguous patches with and without prioritization; report its actual sample and results without making efficiency claims in advance.
- [ ] Commit; present **G5: complete local prototype acceptance** and known failures.

**Coverage:** remaining FRs, SAF-01/02/05 and NFR-01/04. Heatmaps are labelled attribution, not segmentations. A model score is not a patient-risk estimate.

## U5 — Reviewed AWS deployment

**Gate before cloud mutations:** **G6A**, approving exact stack, account/region, service/role requirements, usage cap, retention and cost envelope.
**Create:** `adapters/dynamodb_store.py`, `adapters/aws_api.py`, `adapters/aws_worker.py`, `adapters/aws_dispatch.py`, `infra/template.yaml`, `infra/worker.Dockerfile`, `tests/cloud/test_contracts.py`, `tests/cloud/test_template.py`, `aidlc-docs/operations/deployment.md`.
**Produces:** the same API/model contracts running in the approved AWS environment.

- [ ] Write failing cloud contract tests and template assertions: authenticated writes, source-label authorization, no public bucket writes, no NAT/permanent GPU/paid LLM resources, bounded worker settings and no plaintext secrets.
- [ ] Implement minimal adapters and IaC; run `python -m pytest tests/cloud -q`, `sam validate --lint` and container-local inference tests. Show the resulting stack plan/change set without executing it before approval.
- [ ] Confirm G6A explicitly; deploy only that stack. Record resource IDs privately where appropriate and a secret-free inventory.
- [ ] Verify HTTPS/UI, authorized and unauthorized paths, a real model job, worker retries/timeouts, revision conflicts, persistence, warm/cold timings, cache provenance and log redaction. Observe actual charges/usage where the account permits it; a missing billing view remains a limitation.
- [ ] Present **G6B: cloud acceptance evidence**, including blockers and remaining resources. Do not claim deployment success from an IaC file alone.

**Coverage:** SEC-01/02, OPS-01 and the existing functional suite against the live environment. Keep local fallback working; do not silently weaken authentication after an AccessDenied error.

## U6 — Release, demonstration, export and cleanup

**Gate:** cloud/local release scope explicitly accepted; cleanup requires its own approval.
**Create:** `scripts/export_project.py`, `tests/operations/test_restore.py`, `aidlc-docs/operations/demo-script.md`, `release-checklist.md`, `rollback.md`, `teardown.md`.
**Produces:** a reproducible release and verified portable bundle—not merely an expiring URL.

- [ ] Write a failing restore test checking image/model version references, review event counts, revision continuity and absence of secrets.
- [ ] Implement and run export; restore in a clean local folder and reproduce one prediction and one review history.
- [ ] Run the release test matrix, record exact artifacts/versions, and prepare a truthful demo with source, uncertainty, human correction and limitations.
- [ ] Present **G7A: release/export acceptance**; confirm the independent export destination before account access expires.
- [ ] For teardown, present the exact project-owned resource list and request **G7B**. Only after approval delete those resources and verify residual storage/images/logs/distributions. Leave shared workshop resources untouched.

## Session continuity and credit control

After each unit update `aidlc-docs/aidlc-state.md` and `audit.md` with the decision, files, commit, test command/output, limitations and one next step. Record SKIPPED with its reason instead of pretending the task passed. Use [the resume prompt](../prompts/resume.md) after interruption. Do not rebuild or retrain because chat context was lost; inspect the stored artifacts first.
