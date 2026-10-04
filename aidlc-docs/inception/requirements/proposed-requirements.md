# Proposed requirements (G0) — OsteoPatch Review

**Status:** PROPOSED for review. Approval of these requirements (G0) does not approve any source download (G1), data/split (G2), training/compute, or cloud spend/deploy. All gates below start **UNAPPROVED**.

Source of truth for scope: `PROJECT_BRIEF.md`, UX criteria in `docs/03_product_ux_and_acceptance.md`, contracts in `docs/08_data_and_api_contracts.md`. This file renumbers and consolidates them as reviewable requirements; it does not invent new scope.

Canonical class order (fixed): `NON_TUMOR` (0), `VIABLE_TUMOR` (1), `NECROSIS` (2). Review/quality states (uncertain, mixed, poor-quality, deferred) are **not** a fourth learned class.

---

## A. Product / functional (prefilled from brief + doc 03)

- **R-FR-01** Gallery loads the approved manifest, paginates, retains filters across detail open/close.
- **R-FR-02** Every model output uses the explicit three-class map; no alphabetical/directory-order label inference.
- **R-FR-03** A real model job can be requested for a curated image; UI distinguishes pending/running/complete/failed/cached.
- **R-FR-04** All three scores + score/calibration type shown; missing scores never render as `0`.
- **R-FR-05** Flagging and queue order follow the versioned review policy; every image stays manually reviewable.
- **R-FR-06** Attribution ties to explicit class/model/image hash, toggles fully off, labelled "attribution" not "segmentation".
- **R-FR-07** Accept/correct/defer persists across reload; source label and original prediction stay unchanged.
- **R-FR-08** Each saved action records actor, reason, server timestamp, prediction ID, revision; retries do not duplicate events.
- **R-FR-09** Competing edits → conflict (409), ask to reload/resolve; no silent overwrite.
- **R-FR-10** CSV/JSON export carries full relevant history, source/model versions, and the disclaimer.
- **R-FR-11** Model/dataset cards show real evidence; unmeasured fields read "Not measured".
- **R-FR-12** Source/reference labels absent from ordinary reviewer responses; available only in an explicitly authorized teaching/eval view (not CSS-hidden).

## B. Safety (prefilled; non-negotiable)

- **R-SAF-01** Educational-only disclaimer (EN + TH) on workbench, model card, exports.
- **R-SAF-02** No patient diagnosis, treatment-response score, survival estimate, or patient-level necrosis percentage.
- **R-SAF-03** Unknown/corrupt/out-of-scope input is rejected or explicitly deferred, never forced into a class.
- **R-SAF-04** A human correction never triggers automatic training or edits a locked benchmark label.
- **R-SAF-05** No invented image-specific morphology narrative or stock heatmap as "model evidence".

## C. Data integrity (prefilled from doc 01 / contracts)

- **R-DATA-01** Strict label mapping via an explicit approved alias table; unknown/blank labels fail closed.
- **R-DATA-02** Per-image SHA-256; reject duplicate image keys, many-to-one filename matches, corrupt images, mismatched CSV rows, contradictory labels — no silent skips.
- **R-DATA-03** Exact + perceptual near-duplicate detection; all derivatives/crops/augmentations of one source image stay in one split.
- **R-DATA-04** Patient IDs only from documented metadata or verified filename convention, with evidence; missing → `null`.
- **R-DATA-05** Preserve original source strings and the original archive separately from derivatives/tensors.
- **R-DATA-06** `source_label` immutable; manifest/split schema per contracts doc; `image_id` stable, non-colliding.

## D. Model / evaluation (prefilled from doc 02)

- **R-ML-01** First model = torchvision MobileNetV3-Small (ImageNet pretrained encoder) + new 3-output head; frozen encoder first. No foundation model / segmentation net / large ensemble / auto-sweep.
- **R-ML-02** Patient-level independence for the split whenever verified metadata permits; assert zero patient overlap when patient-level evaluation is claimed; zero source-image overlap always; no duplicate clusters across splits.
- **R-ML-03** Compare a majority-class baseline, the frozen-encoder classifier, and at most one fine-tuned candidate. A model that cannot beat the baseline is labelled unsuccessful — no cached success examples.
- **R-ML-04** Freeze weights/preprocessing/thresholds/candidate before the locked test set. Report confusion counts, macro-F1, balanced accuracy, per-class P/R/F1 + support, log loss, multiclass Brier. Absent class metrics → "unavailable" with reason.
- **R-ML-05** Qualified confidence: keep raw vs calibrated scores separate; temperature scaling validation-only; never relabel a 0.9 score as "90% certain the patient has this condition".
- **R-ML-06** Immutable predictions (contracts): scores finite, in [0,1], sum to 1 ±1e-5; an error never yields a zero-filled "normal" prediction; cache never falsifies compute time.
- **R-ML-07** Deterministic review policy: provisional flags top-score < 0.70 or top-two margin < 0.15 (unvalidated starting values, tuned only on validation, versioned); deterministic priority ordering; a flag is review priority, **not** medical urgency.
- **R-ML-08** Grad-CAM attribution for an explicit target class with gradients enabled; on failure show "Attribution unavailable" and keep review working; no empty/placeholder overlay under success.

## E. Architecture / NFR / security (prefilled from doc 04 / contracts)

- **R-ARCH-01** Local-first vertical slice (React/Vite/TS + FastAPI + shared PyTorch package + SQLite); loopback-bound dev.
- **R-ARCH-02** Cloud (if approved) = small serverless: S3+CloudFront OAC, Cognito-authorized HTTP API + Lambda, CPU Lambda worker (ECR image), DynamoDB; async job-ID + polling (API Gateway 30s limit); no SageMaker endpoint / permanent GPU / RDS / NAT / Bedrock.
- **R-NFR-01** All essential review actions keyboard-accessible; never state-by-color-alone.
- **R-NFR-02** Local state survives restart; cloud state survives Lambda recycling.
- **R-NFR-03** Failed model/attribution request leaves image + history usable with explicit error.
- **R-NFR-04** Proposed targets (measure, don't assert): warm predict p95 ≤3 s, cached detail ≤2 s, save ack ≤2 s.
- **R-NFR-05** Versioned API/model/data IDs on saved results; train/serve preprocessing agree.
- **R-SEC-01** Cloud write endpoints require verified auth/authorization for the one approved project; identity from token, never a user-supplied actor field.
- **R-SEC-02** No secrets/tokens/image bytes in logs; curated allowlisted image IDs only (no arbitrary URL/path/upload); 401/403/404/409/422/503 used correctly.
- **R-OPS-01** Deploy/delete only an approved named stack inventory; never touch others' workshop assets.
- **R-OPS-02** A tested portable export exists before teardown/expiry.

## F. Workflow / process

- **R-WF-01 (G0-W, UNRESOLVED)** Choose and install exactly one lifecycle controller. Default proposal: AI-DLC **v1.0.1** per `docs/00_ai_dlc_setup.md`, installed into a fresh `.kiro/steering/` from a freshly-inspected official release archive; do not mix with native Kiro Specs or 2.x commands. No rules are installed yet.
- **R-WF-02** Record every question/answer/approval/command-result/limitation in `aidlc-docs/`; a proposal is not approval; a test plan is not a passed test.
- **R-WF-03** No `--trust-all-tools` on this personal machine; rely on ordinary tool approvals + explicit human stage gates.

---

## Gate ledger (all UNAPPROVED)

| Gate | Decides | State |
|---|---|---|
| G0 | These requirements + staged plan | UNAPPROVED |
| G0-W | Workflow controller choice/install | UNRESOLVED (default: v1.0.1) |
| G1 | Exact source + access route (Q1) | BLOCKED — see `data-source-decision.md` |
| G2 | Data quality / label mapping / split | UNAPPROVED |
| G3 | Model / evaluation acceptance | UNAPPROVED |
| G4 | Local workflow acceptance | UNAPPROVED |
| G5 | Complete local prototype | UNAPPROVED |
| G6A/G6B | Cloud deploy approval / evidence | BLOCKED — no AWS access configured |
| G7A/G7B | Release-export / teardown | UNAPPROVED |
