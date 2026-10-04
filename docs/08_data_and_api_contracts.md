# 08 — Data and API contracts

**Status:** proposed schema version 1. Names below are stable project decisions for Kiro to review before implementation. The examples specify types and invariants, not measured results.

## Canonical enums

`TissueClass = NON_TUMOR | VIABLE_TUMOR | NECROSIS` with numeric order 0, 1, 2.

`ReviewAction = ACCEPT | CORRECT | DEFER`.

`ReviewStatus = UNREVIEWED | ACCEPTED | CORRECTED | DEFERRED`.

`JobKind = PREDICT | ATTRIBUTE`; `JobStatus = PENDING | RUNNING | SUCCEEDED | FAILED`.

`ScoreType = UNCALIBRATED_SOFTMAX | TEMPERATURE_SCALED`.

`ReviewReason = LOW_TOP_SCORE | CLOSE_TOP_TWO | QUALITY_FLAG | MIXED_TISSUE | INSUFFICIENT_CONTEXT | OTHER`.

The source may encode labels in a different order. Map explicit observed aliases into the canonical order and save the mapping; unknown values cause import failure.

## Dataset manifest

One row per source image: `image_id`, `source_uri`, `source_filename`, `image_sha256`, `width`, `height`, `source_label`, `canonical_label`, `patient_id` (nullable), `slide_id` (nullable), `group_evidence`, `duplicate_cluster_id` (nullable), `dataset_version`, `included`, `exclusion_reason`.

`image_id` must be a stable non-colliding ID, not a transient row index. `source_label` is immutable. The split manifest records `image_id`, `split` (TRAIN/VALIDATION/TEST), `split_version` and the verified grouping level. Children always retain their parent split. Missing patient identity is null, not a fabricated “patient_1”.

## Prediction

`prediction_id`, `image_id`, `image_sha256`, `model_version`, `model_sha256`, `preprocess_sha256`, `dataset_version`, `raw_scores` (all three classes), `calibrated_scores` (nullable, all three if present), `score_type`, `predicted_class`, `top_score`, `top_two_margin`, `calibration_version`, `review_policy_version`, `needs_review`, `review_reason_codes`, `created_at_utc`, `execution_mode` (LIVE/CACHED), `runtime_ms` (nullable when not measured).

Scores must be finite, in [0,1], and sum to 1 within a documented tolerance of 0.00001. Recompute top score/margin from the selected score vector, not from an unrelated field. Ties use canonical class order, but the zero margin must flag uncertainty. An error does not generate a normal Prediction with zero-filled scores.

Cache lookup returns the existing prediction provenance; it must not falsify the original computation time or claim it just ran. Record retrieval time separately when required. A human edit never changes this record.

## Job

`job_id`, `kind`, `image_id`, `model_version`, `prediction_id` (required for ATTRIBUTE), `requested_class` (required for ATTRIBUTE), `status`, `created_at_utc`, `updated_at_utc`, `deadline_at_utc`, `idempotency_key`, `request_hash`, `result_id` (nullable), `error_code` (nullable).

The worker performs an atomic transition, tolerates duplicate delivery, and will not write two different results for the same completed job. A timed-out/stale job is surfaced as failed with a safe error. Retrying creates or resumes a well-defined idempotent request; it does not loop indefinitely.

## Review state and event

A review state is scoped to the approved project and image: `project_id`, `image_id`, `current_revision`, `review_status`, `latest_human_label` (nullable), `latest_event_id`.

A review event records `event_id`, `idempotency_key`, `request_hash`, `project_id`, `image_id`, `prediction_id`, `action`, `previous_revision`, `new_revision`, `previous_human_label` (nullable), `human_label` (nullable for DEFER), `reason_code`, `note`, `actor_id`, `actor_role`, `created_at_utc`, `model_version`, `dataset_version`.

ACCEPT uses the referenced model class. CORRECT requires a chosen class and reason. DEFER permits a null human label and requires a reason. SKIP is navigation, not a silent acceptance event. Server code supplies actor and time. No user-provided actor is trusted.

Write the event and state change atomically. A repeated idempotency key with the same request returns the original event; the same key with different content is a conflict. An outdated expected revision is a conflict. Application history is not deleted to implement an undo.

## Attribution

`attribution_id`, `image_id`, `image_sha256`, `prediction_id`, `target_class`, `model_sha256`, `preprocess_sha256`, `method`, `target_layer`, `map_uri`, `created_at_utc`, `status`, `limitation_text`.

Attribution errors remain explicit. Do not return a placeholder image under a success status. Test alignment to the original after resizing, and ensure the original display can be recovered exactly.

## Endpoints

All project endpoints except health/public model-card material require the selected auth mode. Local demo identity is explicitly labelled and must not ship as an unauthenticated cloud write mode.

| Method and path | Contract |
|---|---|
| `GET /health` | Minimal readiness/version; no secrets or internal filesystem paths |
| `GET /v1/images` | Paginated curated images; class/review filters; no reference labels in normal review mode |
| `GET /v1/images/{image_id}` | Image display metadata and authorized artifact references |
| `POST /v1/jobs` | Validated job request with idempotency key; HTTP 202 with job ID, or an explicitly cached/completed result contract |
| `GET /v1/jobs/{job_id}` | Authorized job status and result reference |
| `GET /v1/predictions/{prediction_id}` | Immutable prediction contract |
| `GET /v1/images/{image_id}/review` | Current state plus authorized event history |
| `POST /v1/images/{image_id}/reviews` | Action, prediction ID, selected label/reason, expected revision and idempotency key; HTTP 201 or original idempotent result |
| `GET /v1/exports/reviews` | CSV/JSON with versions, complete relevant audit events and disclaimer |
| `GET /v1/model-card` | Actual evaluation and intended-use/limitation metadata |

Use 401 for missing/invalid authentication; 403 for insufficient project authorization; 404 for unknown permitted objects; 409 for conflicts; 422 for invalid input; and 503 for unavailable services. Never return a fabricated successful prediction to mask a failure.

## Python domain interfaces

Implement in small modules and use these signatures across local/cloud adapters:

- `load_manifest(path: Path) -> list[ImageRecord]`
- `audit_manifest(records: list[ImageRecord]) -> DataAuditReport`
- `validate_split(records: list[ImageRecord], split: SplitManifest) -> SplitAuditReport`
- `load_model_bundle(path: Path) -> ModelBundle`
- `predict_image(image: PIL.Image.Image, bundle: ModelBundle) -> ModelOutput`
- `apply_review_policy(output: ModelOutput, quality: QualityFlags, policy: ReviewPolicy) -> ReviewDecision`
- `attribute_image(image: PIL.Image.Image, bundle: ModelBundle, target: TissueClass) -> AttributionMap`
- `submit_job(request: JobRequest, actor: Actor, store: JobStore) -> Job`
- `save_review(request: ReviewRequest, actor: Actor, store: ReviewStore) -> ReviewEvent`

Define types in `src/osteopatch/contracts.py`; TypeScript types are generated from or checked against the same API schema. Domain functions do not directly access AWS credentials or browser state. Storage and job-dispatch adapters implement the shared protocols.
