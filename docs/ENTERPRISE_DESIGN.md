# OsteoPatch — Enterprise End-to-End Software Design

> **Status:** design proposal (not built). It wraps the EXISTING, real
> `baseline-frozen-g4` 3-class patch classifier and the G6/G8 review app in a
> production-grade system. Nothing here changes the model's scope.
>
> **Educational research prototype only. Not for diagnosis, treatment
> decisions, or predicting treatment response.**
> **ต้นแบบเพื่อการเรียนรู้และการวิจัยเท่านั้น ไม่ใช้วินิจฉัย ตัดสินใจรักษา หรือทำนายผลการรักษา**

---

## 0. Reality check — what already exists vs. what "enterprise" adds

You said it has "no fully functional pathology AI for detection at all." That is
partly a terminology gap worth being precise about, because it changes the design:

**What is REAL today**
- A reproducible, trained **3-class patch classifier** (`baseline-frozen-g4`):
  `NON_TUMOR` / `VIABLE_TUMOR` / `NECROSIS`. It consumes real image pixels and
  emits three uncalibrated scores. Bundle hash is re-verified at load.
- A working **review workbench** (G6): FastAPI + SQLite backend (torch-free at
  serve time; predictions precomputed), React/TS frontend, contrastive Grad-CAM
  attribution (G7), deterministic review-priority ranking, append-only
  ACCEPT/CORRECT/DEFER events, CSV/JSON export.
- A **deployed AWS slice** (G8): containerized Lambda + API Gateway + DynamoDB +
  S3 artifacts.

**What it is NOT (by design, and these are hard non-goals)**
- Not a **detector** in the WSI sense. It classifies pre-extracted *patches*; it
  does not localize tumor on a whole-slide image, segment, or score necrosis %.
- Not calibrated — scores are class scores, never disease probabilities.
- Not multi-user, not authenticated, not audited to a compliance standard.
- `VIABLE_TUMOR` is the model's **weak class** (see G4 OOF eval). Enterprise
  packaging does not fix model quality — it makes the weakness governable.

**So "enterprise end-to-end" means** adding the *systems* layer the clinical/edu
software world requires around a model: identity, multi-tenancy, slide ingestion,
async inference at scale, human-in-the-loop governance, auditability, observability,
and a safe deploy/rollback story — without crossing any clinical non-goal.

---

## 1. Personas & top-level user journeys

| Persona | Goal | Key surfaces |
|---|---|---|
| **Student reviewer** | Learn by reviewing patches, see model reasoning | Workbench, attribution, review queue |
| **Supervising pathologist** | Adjudicate uncertain patches, sign off batches | Review queue, adjudication, dashboards |
| **Project / lab admin** | Create projects, invite reviewers, manage datasets | Admin console, dataset manager |
| **ML / platform engineer** | Register models, watch drift, promote/rollback | Model registry, monitoring, deploy |
| **Auditor / compliance** | Reconstruct who-saw-what-when, export evidence | Audit log, immutable export |

**Primary journey (reviewer):**
`Sign in (SSO) → pick project → gallery sorted by review-priority → open patch →
see 3 scores + uncertainty + Grad-CAM → ACCEPT / CORRECT / DEFER → auto-advance →
batch sign-off → export`.

**Platform journey (ML engineer):**
`Register model bundle (hash-pinned) → run eval on holdout → promote to
"candidate" → shadow-infer → compare vs incumbent → promote to "serving" or
rollback`.

---

## 2. Target architecture (logical)

```
                         ┌─────────────────────────────────────────────┐
   Browser (React SPA)   │  CloudFront + S3 (static)  ·  WAF            │
   desktop / tablet      └───────────────┬─────────────────────────────┘
          │  OIDC (PKCE)                 │  /api/*
          ▼                              ▼
   ┌──────────────┐           ┌──────────────────────┐
   │ Identity (IdP│──JWT────▶ │  API Gateway (HTTP)   │  rate-limit, authz
   │  Cognito/OIDC│           │  + Lambda authorizer  │
   └──────────────┘           └──────────┬───────────┘
                                          │
             ┌────────────────────────────┼───────────────────────────┐
             ▼                            ▼                           ▼
    ┌─────────────────┐        ┌──────────────────┐        ┌──────────────────┐
    │ Review API      │        │ Ingestion API    │        │ Inference         │
    │ (FastAPI/Lambda)│        │ (slide/patch     │        │ orchestrator      │
    │ gallery,review, │        │  upload, tiling) │        │ (async, SQS→      │
    │ export, authz   │        │                  │        │  worker→ECS/GPU)  │
    └───────┬─────────┘        └────────┬─────────┘        └─────────┬────────┘
            │                           │                            │
            ▼                           ▼                            ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Data plane:  DynamoDB (reviews/events, idempotent, append-only)       │
    │              Postgres/RDS (projects, users, datasets — relational)    │
    │              S3 (slides, patches, artifacts, attribution cache)       │
    │              OpenSearch (gallery search / priority index)             │
    └─────────────────────────────────────────────────────────────────────┘
            │
            ▼  (every mutation)
    ┌─────────────────────────────────────────────────────────────────────┐
    │ Audit log (append-only, hash-chained) → S3 Object-Lock (WORM)         │
    │ Observability: CloudWatch/OTel traces · metrics · model-drift monitor │
    └─────────────────────────────────────────────────────────────────────┘
```

Serving stays **torch-free on the hot path** (precomputed predictions); only the
inference orchestrator and attribution worker load torch, on GPU/ECS, off the
request path. This preserves the existing G6 design decision at scale.

---

## 3. Feature inventory (the "all features available" checklist)

### 3.1 Identity & access
- OIDC/SSO sign-in (Cognito or external IdP), PKCE for the SPA.
- **RBAC**: `student`, `reviewer`, `pathologist`, `admin`, `ml_engineer`, `auditor`.
- Per-**project** scoping (multi-tenant): a user sees only projects they're invited to.
- Session + refresh tokens; short-lived API JWTs; Lambda authorizer enforces role×project.

### 3.2 Dataset & slide ingestion
- Admin creates a **project**, attaches a dataset (curated public set first;
  arbitrary upload gated behind an explicit admin capability — mirrors the
  non-goal of "no arbitrary patient upload in v1").
- **Slide/patch ingestion pipeline**: upload → virus/format scan → tiling into
  patches (if WSI handed in) → QC metadata (`source_qc`) → index for gallery.
- Patient/slide-group split preserved; **fail-closed on unknown labels**.

### 3.3 Inference at scale
- **Batch precompute** job (existing `precompute.py` logic) runs as an async
  worker fleet; predictions keyed by `(image_id, model_bundle_hash)` — idempotent.
- **Shadow inference**: a candidate model scores the same patches in parallel for
  comparison, never shown to reviewers until promoted.
- Every prediction immutable, hash-pinned to its model bundle.

### 3.4 Review workbench (the reviewer's core screen)
- Gallery with deterministic **review-priority ranking** (uncertainty-first).
- Patch detail: original image, 3 uncalibrated scores, `top_two_margin`,
  `normalized_entropy`, suggested class.
- **Contrastive Grad-CAM** attribution (predicted vs runner-up), with the honest
  recovery disclosure already in the codebase.
- Actions: **ACCEPT / CORRECT / DEFER** (+ defer reason), keyboard-driven,
  auto-advance, optimistic concurrency (`expected_revision`), idempotency keys.
- Append-only `review_event`; model prediction row never mutates.

### 3.5 Human-in-the-loop governance
- **Adjudication**: a pathologist resolves disagreements; a correction by a
  student can be escalated for sign-off.
- **Batch sign-off**: lock a reviewed batch, snapshot it, export.
- Corrections are **captured, not auto-fed** to training (explicit non-goal) —
  they land in a labelled-correction store for a *future, separately-approved*
  retraining decision.

### 3.6 Model lifecycle
- **Model registry**: bundle, hash, eval card, split declaration, limitations.
- States: `registered → candidate → shadow → serving → retired`.
- Promotion requires a passing eval gate + human approval; **one-click rollback**.
- **Drift monitor**: score-distribution + defer-rate + correction-rate tracked
  per model version; alert on crossing thresholds.

### 3.7 Audit, compliance, export
- Hash-chained, append-only **audit log** of every read/mutation, to WORM storage.
- Immutable **export** (CSV/JSON) carrying model prediction + human action + who/when.
- Model card and disclaimer surfaced on workbench, card, and every export.

### 3.8 Observability & ops
- Distributed tracing (OTel), structured logs, RED metrics per endpoint.
- Health/readiness probes; the bundle-hash mismatch **fail-to-start** guard kept.
- SLOs: p95 gallery < 300 ms (precomputed), attribution async < 5 s.

---

## 4. Data model (extends what exists)

Keeps the three non-overwriting concepts from G6, adds the enterprise entities:

- `project(id, name, dataset_id, created_by, …)`
- `user(id, email, oidc_sub, …)` · `membership(user_id, project_id, role)`
- `dataset(id, source, license, split_declared, …)`
- `source_qc(image_id, group, original_label, qc_status, training_eligible, …)` *(existing)*
- `prediction(prediction_id, image_id, model_bundle_hash, scores…, immutable)* *(existing)*
- `review_event(…, revision, idempotency_key, reviewer, append-only)* *(existing)*
- `model_registry(bundle_hash, state, eval_card_ref, promoted_by, …)`
- `audit_entry(seq, prev_hash, actor, action, target, ts, hash)` *(hash-chained)*

Append-only + hash-pinning + idempotency are already the project's house style;
enterprise just applies them everywhere.

## 5. Security & compliance posture
- Encryption at rest (S3/DynamoDB/RDS KMS) and in transit (TLS everywhere).
- No secrets in code; workshop/temporary creds never hard-coded (existing rule).
- WORM audit retention; least-privilege IAM per service.
- Data-handling note: curated/public data in v1; PHI path is explicitly **out of
  scope** until a separate privacy review — the non-goals protect this boundary.

## 6. Deploy, environments, rollback
- Envs: `dev → staging → prod`, each its own stack (CDK, mirrors G8 approach).
- Blue/green or canary on the API; model promotion decoupled from code deploy.
- One-click **rollback** for both app version and serving model version.
- Teardown runbook (mirrors the project's "approved teardown" gate).

## 7. Phased delivery (safe, gated — do not skip gates)
1. **E1 Multi-user core** — SSO, RBAC, projects, port G6 review API behind authz.
2. **E2 Ingestion** — dataset manager + patch pipeline + gallery search index.
3. **E3 Inference at scale** — async worker fleet, shadow inference, attribution worker.
4. **E4 Governance** — adjudication, batch sign-off, correction store.
5. **E5 Model lifecycle** — registry, promotion gate, drift monitor, rollback.
6. **E6 Audit & observability** — hash-chained audit → WORM, OTel, SLO dashboards.

Each phase ends behind an approval gate, consistent with the existing AI-DLC plan.
No training, paid resource, or cloud mutation before the relevant gate approval.
