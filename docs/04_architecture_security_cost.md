# 04 — Architecture, security and cost control

This is a **conditional design proposal**. No AWS resources were inspected or created in the owner's account. Official service references are [S12–S15] in [the source register](07_sources_and_reuse_register.md).

## Decision: a local vertical slice, then one approved AWS deployment

First build React/Vite/TypeScript, a Python FastAPI adapter, the shared PyTorch model package and SQLite persistence. Bind local development to loopback by default. This gives a testable workflow and a portable demonstration even if workshop permissions or expiration prevent cloud deployment.

The proposed cloud target is a small serverless deployment, not a continuously running GPU or managed model endpoint. Local and cloud adapters share domain contracts and model artifacts; they do not train different models.

| Responsibility | Local first | Proposed AWS target |
|---|---|---|
| UI | Vite build served locally | Private S3 origin + CloudFront OAC/HTTPS |
| Reviewer identity | Explicit local demo identity, labelled non-production | Invite-only Cognito user pool + HTTP API JWT authorizer |
| API/domain operations | FastAPI | Small Python Lambda behind API Gateway HTTP API |
| Inference and attribution | Bounded local worker | Separate CPU Lambda container image in ECR |
| Images/model/heatmaps | Local artifact directories | Private S3; worker can use a pinned model bundled in its image |
| Jobs, predictions, review state/events | SQLite transaction store | DynamoDB conditional/transactional writes |
| Logs | Local structured logs | CloudWatch with short approved retention |
| Infrastructure | Local instructions | One AWS SAM/CloudFormation stack, reviewed before deploy |

Use the default CloudFront domain initially; no domain purchase or Route53 dependency. A private S3 origin does not make the entire public website confidential: only approved public teaching assets may be exposed through the distribution. Review state and APIs still require authorization.

## Short HTTP requests, asynchronous model jobs

API Gateway HTTP API integrations have a documented 30-second maximum [S13]. A Lambda function's longer possible runtime does not extend that limit. Therefore the proposed API returns an accepted **job ID immediately**, and the UI polls a status endpoint with bounded exponential backoff. Do not make a browser wait on a long PyTorch cold start through a synchronous API integration.

Cloud flow: authorized `POST /v1/jobs` → persist a job → asynchronously invoke the model worker → worker reads the approved image and pinned model → save prediction/attribution status → browser retrieves job result. Cached predictions use the same versioned contract and are labelled cached. Local mode can complete a job immediately but must still expose its true state.

The API/worker boundary needs an explicit permission check for Lambda invocation. The worker handles duplicate deliveries idempotently. Limit retries, age-out stale jobs, set a per-job timeout, and surface failed/stale status. Do not add SQS, Step Functions or another service until an observed requirement justifies it. The asynchronous worker is a bounded application function, not permission for an agent to run indefinitely.

Prediction and attribution jobs are separate so the reviewer can see scores even when an explanation is slower or fails. Attribute a requested class only, not all possible classes by default. Cache keys include image hash, model hash, preprocessing hash, calibration version, policy version and attribution target/method as applicable. A new version invalidates incompatible cached results.

## Permission and environment gate

Kiro can inspect local tool versions, disk/RAM, GPU availability, active AWS identity and configured region without exposing secrets. Use bounded authorized read-only queries. The workshop snapshot suggests `us-east-1`, not a permanent authorization.

Document which services and permissions are confirmed, unverified or denied: S3, ECR, Lambda, DynamoDB, API Gateway, Cognito, CloudFront, CloudWatch, CloudFormation/SAM and necessary role passing. A read-only success does not prove create/PassRole permission. Do not probe mutations just to find out what is allowed. No automatic switch to a personal AWS account or broadening of IAM policies.

If required services are denied, retain the local implementation and propose one simpler architecture using only explicitly permitted workshop resources. Browser ONNX is an optional separately approved reduced-scope fallback; shared audit/authentication and Grad-CAM would need a different design. Do not silently replace the promised functionality with a static mock.

## Security and data controls

Use curated, allowlisted image IDs—not arbitrary URLs, paths or uploads. Enforce project-level authorization on reads and writes. Derive the reviewer identity from the verified token, never from a user-supplied actor field. Validate body schemas, image IDs, note length, label enums and expected review revision.

Allow only the configured UI origins. Block public S3 writes and direct public access to private artifacts. Use narrowly scoped roles, encryption defaults, TLS and no browser-embedded secret/API key. Avoid placing the worker in a VPC when it does not require one; this design does not need a NAT gateway.

Review events are append-only through the application. This is an accountability design, **not a claim of immutable regulatory-grade storage**: privileged administrators could still change data. Keep original predictions independent of current review state. Concurrent saves use optimistic revision checks and an atomic state/event write; duplicate requests are idempotent.

Do not collect clinical patient data. Public source images must retain licensing/attribution metadata. Do not log JWTs, credentials, raw image bytes or sensitive free text. Logs contain request IDs, artifact versions, timing and safe error codes.

## Spending gate and bounds

Separate Kiro credits, AWS service usage, dataset-transfer/storage charges, and optional third-party services. None is assumed free or covered by the same allowance. Check current prices only after the chosen region/services and approved usage envelope are known.

Before any cloud mutation, write a budget table with remaining event credits, approved maximum spend, expiry timestamp, intended services, expected storage, maximum model jobs, maximum worker duration/memory/concurrency, API request volume, log retention, and teardown owner. Unknown budget means no new paid resources.

Budget alerts alone are not a guaranteed hard cap; AWS documents notification/usage delays [S15]. Add application admission limits and infrastructure/runtime bounds. Proposed starting limits for review: one active worker per project, at most two worker invocations concurrently overall, one-image jobs, a finite approved job count, and no unlimited retry loop. These are proposals to approve, not applied settings or guarantees that all AWS charges are capped.

No default SageMaker real-time endpoint, permanent GPU instance, RDS, OpenSearch, NAT gateway, purchased domain, Bedrock call, paid model API or purchased Kiro credits. Do not create multiple alternative architectures for comparison on the live account.

## Export, rollback and teardown

Tag project-owned resources with a project identifier and approved expiration metadata. A tag alone does not delete anything. Record the actual resource inventory and use stack-scoped deletion only after export verification and the owner's teardown approval.

Export source/lockfiles, data manifest, permitted data copy or reproducible retrieval manifest, model package, metrics, review events, configuration excluding secrets, and deployment instructions outside the temporary workshop account. A local copy on an expiring workshop host is not an independent backup.

Rollback selects a previously tested model/application artifact pair and its compatible schema. Test the rollback procedure locally and perform a small cloud smoke check only in the approved deployment. After teardown inspect project-owned buckets, container images, tables, functions, logs, authentication resources and distributions for residual charges. Do not delete shared workshop infrastructure.
