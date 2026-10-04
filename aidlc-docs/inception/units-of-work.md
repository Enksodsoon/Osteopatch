# Units of work (staged plan) — OsteoPatch Review

**Status:** proposed, gated plan. **U0 is the only unit touched this run** (inception artifacts). U1–U6 are **NOT EXECUTED** and each is blocked behind its gate. A plan is not permission to implement; a listed command is a *future* verification command, not a passed test.

Global constraints (carried from `docs/05_...` and the brief): canonical order `NON_TUMOR, VIABLE_TUMOR, NECROSIS`; educational scope only; no source substitution, no unverifiable patient split, no fabricated results, no automatic retraining, no unapproved spend, no public unauthenticated review writes; preserve source labels + predictions; check licensing before copying external code.

---

## U0 — Inception & source decision  — **DONE (this run)**
**Deliverable:** approved scope + defensible source route. No app code, no paid resources.
**Produced under `aidlc-docs/inception/`:**
- `requirements/proposed-requirements.md`
- `requirements/requirement-verification-questions.md`
- `environment-and-permission-report.md`
- `data-source-decision.md` (G1 blocked)
- `architecture-proposal.md` (+ cost envelope)
- `risk-register.md`
- `aidlc-state.md`
**Open blockers:** Q1 (source rule), Q2 (deadline/expiry), Q3 (budget/services), Q4 (rubric), Q7 (AWS access for verification). G0/G1 await owner.
**Exit:** owner answers blocking questions + approves G0; chooses G1 route.

---

## U1 — Data ingestion & split audit — NOT EXECUTED
**Gate:** G0 + G1 approved; this unit's code-gen plan reviewed.
**Create:** `src/osteopatch/contracts.py`, `data/{manifest,labels,audit,splits}.py`, `tests/data/{test_labels,test_manifest,test_splits}.py`.
**Produces:** `load_manifest`, `audit_manifest`, `validate_split`; `manifest.csv`, `split_manifest.csv`, `dataset-card.md`, `label_aliases.json`, `patient_mapping_evidence.md`, `data_audit.json`, exclusion/duplicate report.
**Test-first:** `test_unknown_label_rejected`, `test_duplicate_key_rejected`, `test_unmatched_csv_image_rejected`, `test_patient_overlap_rejected`, `test_parent_derivatives_share_split`.
**Gate out:** **G2** (data/label/split). Download only the approved source within a byte limit. Stop before training.

## U2 — Train & evaluate bounded baseline — NOT EXECUTED
**Gate:** G2 **and** a local/paid compute allowance (paid compute = separate explicit budget approval even if local training is approved).
**Create:** `ml/{model,preprocess,train,evaluate,calibrate,bundle}.py`, `tests/ml/{test_bundle,test_preprocess,test_metrics}.py`.
**Produces:** `load_model_bundle`, `predict_image`, a real bundle, evaluation, `model-card.md`.
**Test-first:** `test_output_class_order`, `test_train_serve_transform_equal`, `test_bundle_hash_mismatch_rejected`, `test_scores_finite_and_normalized`, `test_missing_class_metrics_explicit`.
**Must:** memory-profile the P2000 first + set a per-run wall-time cap; compare majority-class baseline vs frozen-encoder vs ≤1 fine-tune; freeze candidate before locked test; report true metrics incl. a failed baseline.
**Gate out:** **G3** (model/eval acceptance).

## U3 — Local end-to-end vertical slice — NOT EXECUTED
**Gate:** G3 accepted with limitations visible.
**Create:** `domain/{jobs,reviews}.py`, `adapters/{sqlite_store,local_worker,local_api}.py`, `apps/web/src/api/`, `pages/Workbench.tsx`, `components/ReviewEditor.tsx`, `tests/{domain,api}/`, `tests/e2e/review-flow.spec.ts`.
**Produces:** `submit_job`, `save_review`; gallery → job → scores → saved review flow.
**Test-first:** invalid IDs, job failure, source-label hiding, immutable predictions, retry idempotency, stale-revision conflict, persisted review across restart.
**Coverage:** FR-01/02/03/04/07/08/09/12, NFR-02/03/05, SAF-03/04.
**Gate out:** **G4** (local workflow acceptance) with a real demo + exact commands/results.

## U4 — Review prioritization, attribution, polished UX — NOT EXECUTED
**Gate:** G4 accepted; no new paid services.
**Create:** `domain/{review_policy,exports}.py`, `explain/gradcam.py`, `apps/web/src/components/{ImageViewer,ScorePanel}.tsx`, `pages/{ReviewHistory,ModelCard}.tsx`, `tests/explain/`, `tests/e2e/{uncertainty,accessibility}.spec.ts`.
**Produces:** `apply_review_policy`, `attribute_image`, versioned explanations, history/export, full educational UI.
**Test-first:** exact threshold boundaries, stable tie ordering, zero-denominator metrics, explicit attribution failure, target-class identity, image alignment, complete audit export, visible disclaimer.
**Must:** real Grad-CAM with gradients enabled; a sanity check (parameter-randomization/perturbation) documented as **not** clinical faithfulness; keyboard-only + narrow-screen checks.
**Coverage:** remaining FRs, SAF-01/02/05, NFR-01/04.
**Gate out:** **G5** (complete local prototype acceptance) + known failures.

## U5 — Reviewed AWS deployment — NOT EXECUTED (blocked: no AWS access)
**Gate:** **G6A** approving exact stack, account/region, service/role requirements, usage cap, retention, cost envelope. **Also environment-blocked** until AWS CLI/credentials exist (Q7).
**Create:** `adapters/{dynamodb_store,aws_api,aws_worker,aws_dispatch}.py`, `infra/template.yaml`, `infra/worker.Dockerfile`, `tests/cloud/{test_contracts,test_template}.py`, `aidlc-docs/operations/deployment.md`.
**Test-first (cloud):** authenticated writes, source-label authorization, no public bucket writes, no NAT/permanent-GPU/paid-LLM resources, bounded worker settings, no plaintext secrets.
**Must:** show stack plan/change set **without executing** before approval; `sam validate --lint`; container-local inference test; deploy only the approved stack; secret-free inventory.
**Gate out:** **G6B** (cloud acceptance evidence) — never claim deploy success from an IaC file alone. Keep local fallback working; never silently weaken auth after an AccessDenied.

## U6 — Release, demo, export, cleanup — NOT EXECUTED
**Gate:** release scope accepted; cleanup needs its own approval (**G7B**).
**Create:** `scripts/export_project.py`, `tests/operations/test_restore.py`, `aidlc-docs/operations/{demo-script,release-checklist,rollback,teardown}.md`.
**Must:** failing restore test (version refs, event counts, revision continuity, no secrets) → implement export → restore in a clean folder + reproduce one prediction + one review history → **G7A** (release/export acceptance), confirm independent export destination before expiry → present exact project-owned resource list → **G7B** → delete only those, verify residuals, leave shared workshop infra untouched.

---

## Session continuity
After each unit, update `aidlc-docs/aidlc-state.md` + an `audit.md` with decision, files, commit, test command/output, limitations, one next step. Record SKIPPED with reason rather than pretending a pass. On interruption use `prompts/resume.md`; inspect stored artifacts before rebuilding/retraining.
