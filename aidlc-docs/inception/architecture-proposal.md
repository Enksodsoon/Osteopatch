# Architecture proposal & cost envelope (Inception)

**Status:** conditional proposal. **No AWS resource was inspected or created** (no AWS access configured — see environment report). Nothing here authorizes spend or deployment. Official refs: S12–S15 in `docs/07_sources_and_reuse_register.md`.

> **Update 2026-10-03 (D9 — cloud-first pivot):** the owner now wants the dataset NOT downloaded to / stored on the Windows workstation when AWS can do data access/audit/(later)training directly. Local = control plane; AWS = data/compute plane. The section immediately below governs U1's **data** architecture and supersedes the local-scratch-download assumption. The pre-existing "local vertical slice" application design further down still stands for the *app* (U3/U4); the pivot is about where the *dataset* lives and is audited.

---

## Cloud-first U1 data architecture (D9)

### A. Direct IDC access — RULED OUT by evidence
Credential-free `idc-index` v24 investigation (see `idc-access-investigation.md`) shows the osteosarcoma collection (DOI `bvhjhdas`) is **not in IDC**: 0 series by name/DOI, 0 `BodyPartExamined=BONE`, across all 176 collections. So U1 **cannot** operate directly against IDC S3 objects. (And IDC pathology is DICOM-SM `.dcm` pyramids, not labelled JPG patches, so it would not be a drop-in equivalent even if present.)

### B. TCIA → project S3 — the remaining cloud-first route, with two blockers
**Blocker B1 (access method) — CORRECTED 2026-10-03.** An earlier version said TCIA had "no headless route." That was wrong. Two official programmatic routes exist and are now the plan:
- **TCIA Aspera CLI (`ascli` / IBM `aspera-cli`, Apache-2.0):** the maintained TCIA_Aspera_CLI_Downloads notebook documents `ascli faspex5 packages receive --url='<public faspex package URL>'` on **Linux**, **no authentication** (the public package URL carries its own passcode; this collection = Faspex package id `752`). Supports `browse` (list files + sizes before transfer) and selective file/dir receive. Needs Ruby ≥3.1 + `gem install aspera-cli` + `ascli conf ascp install`. **An AWS Linux env can run this headlessly → ephemeral disk → upload to S3.** Not runnable on this Windows control plane without Ruby+ascp, and not the intended place for the data anyway.
- **PathDB (`tcia_utils.pathdb`, base `pathdb.cancerimagingarchive.net`) — credential-free HTTP:** `getImages(collection)` returns per-image `subjectId`, `imageId`, `slideId`, `imageUrl` (`field_wsiimage`), dimensions; `downloadImages()` fetches those `imageUrl`s over **plain HTTPS, no Aspera**. This may allow object-level image retrieval AND supplies a `subjectId` field directly relevant to patient mapping. **To be verified empirically for THIS collection** (does PathDB index Osteosarcoma-Tumor-Assessment, how many subjects vs the published 4 patients, do the imageUrls resolve, do imageIds join to the CSV filenames).

The **CSV** (`ML_Features_1144.csv`, ~860 KB) is plain HTTP and audited first.
**Blocker B2 (no AWS access):** this workstation has no AWS CLI, no `~/.aws`, no credentials. Cannot inspect workshop identity/region/permissions, cannot create a bucket, cannot launch compute. Every S3/compute step is blocked until the owner configures workshop credentials in their own terminal (agents must not install credentials, switch accounts, or request pasted secrets).

**Net:** the fully-automated cloud-to-cloud ingest cannot be executed by an agent today. The realistic supported sequence, once B2 is resolved, is: owner (or an approved compute step) runs the **Aspera** download of the images once → objects land in project S3 `raw/` → **all auditing runs against S3**, not against a persistent local copy. The images may transit a machine during the one Aspera fetch, but are not *persistently stored* locally — consistent with the owner's intent.

### C. Proposed project S3 layout (us-east-1, pending permission + cost approval)
```
s3://<project-bucket>/
  raw/        immutable source JPG + CSV objects (write-once; versioning on)
  manifests/  source inventory, per-object SHA-256, canonical manifest.csv
  audit/      exclusions, duplicate report, patient_mapping_evidence
  splits/     proposed grouped split manifests
  models/     reserved for U2 (empty in U1)
```
`raw/` immutable (bucket versioning + no overwrite). Record for every object: source URL/identifier, collection DOI `10.7937/tcia.2019.bvhjhdas`, retrieval timestamp, size, SHA-256. Small CSV/JSON/MD audit copies may be pulled to the control plane for review.

### D. Cost & permission gate (must pass before any bucket/compute/transfer)
1. Inspect workshop AWS identity/region/permissions (no secrets) — **blocked (B2)**.
2. Identify which proposed resources are permitted — pending (1).
3. Estimate max U1 cost — see envelope below; U1 is near-zero if it stays in-region + public source.
4. Prefer free/public access + ephemeral compute; avoid standing resources.
5. Present any materially-costly resource creation for approval. No credit purchase, no IAM change, no account upgrade. Region `us-east-1` unless the verified environment requires otherwise.

**U1 AWS cost estimate (order-of-magnitude, UNVERIFIED until identity/region known):** S3 storage of ~200 MB ≈ **< $0.01/month**; `PUT`/`GET`/`LIST` for ~1,150 objects ≈ **cents**; in-region transfer **$0**; if a short ephemeral compute (e.g. one small Fargate task or t3.small spot) performs the Aspera fetch + hashing for well under an hour ≈ **a few cents**. **Material cost risk is low** *if* egress stays in-region and no standing compute is left running. This is a planning estimate, not a quote; real prices checked only after region/services are confirmed.

### E. U2 training data path — DESIGN ONLY (no training in U1)
Design the later training to read images from S3 directly rather than pre-downloading the whole collection.

| SageMaker input mode | Fit for this project | Verdict |
|---|---|---|
| **FastFile** | Exposes S3 objects as POSIX files, **streamed on demand**; a conventional PyTorch `ImageFolder`/`PIL.Image.open(path)` loader works unchanged; no full-collection copy before training starts; ideal for 1,144 small JPGs with random access per epoch. | **SELECTED** |
| File | Copies the ENTIRE channel to the instance EBS before training starts; wastes time/disk for a streamable small set; forces full materialization (against the owner's intent). | Rejected (full copy) |
| Pipe | Streams as an ordered byte pipe via a `PipeModeDataset`; needs TFRecord/RecordIO-style sequential sharding and a non-filesystem loader; poor fit for random-access per-image PIL loading and small-N shuffling. | Rejected (needs re-plumbing, no filesystem semantics) |

**Why FastFile:** keeps the exact same image-loading code locally and in-cloud (train/serve parity, R-NFR-05), avoids a full-collection download, and suits random per-epoch access over a small object count. Revisit only if profiling shows per-object latency dominates (then consider pre-sharding to RecordIO + Pipe). Still gated behind G2 + separate compute/budget approval; **not executed in U1.**

---

## Decision: local vertical slice first, then one optionally-approved AWS deployment

Build and demonstrate everything locally; cloud is an additive, separately-approved step so the project still has a portable, working demo even if AWS access is denied or expires.

### Shared core (same code local + cloud)
- `src/osteopatch/contracts.py` — typed enums/schemas/protocols (single source of truth; TS types checked against it).
- `src/osteopatch/{data,ml,domain,explain}/` — manifest/label/audit/split; model/preprocess/train/eval/calibrate/bundle; jobs/reviews/policy/exports; Grad-CAM. No AWS creds / browser state inside domain code.
- Adapters implement shared protocols for storage + job dispatch.

### Option L — Local (default, no AWS)
| Responsibility | Local |
|---|---|
| UI | React/Vite/TS served on loopback |
| API/domain | Python FastAPI, loopback-bound |
| Inference/attribution | bounded local worker (CPU or P2000 GPU) |
| Persistence | SQLite transaction store |
| Identity | explicit local demo identity, labelled non-production |
| Logs | local structured logs |

### Option C — Cloud (only after G6A; blocked today)
| Responsibility | AWS target |
|---|---|
| UI | private S3 origin + CloudFront OAC/HTTPS (default CloudFront domain; no domain purchase/Route53) |
| Identity | invite-only Cognito user pool + HTTP API JWT authorizer |
| API/domain | small Python Lambda behind API Gateway **HTTP API** |
| Inference/attribution | separate **CPU** Lambda container image in ECR (pinned model bundled) |
| Artifacts | private S3 |
| State/events | DynamoDB conditional/transactional writes |
| Logs | CloudWatch, short approved retention |
| IaC | one SAM/CloudFormation stack, reviewed before deploy |

**Async pattern (required):** API Gateway HTTP API has a 30s integration max [S13], shorter than a PyTorch cold start. So `POST /v1/jobs` returns **202 + job ID**, the UI polls `GET /v1/jobs/{id}` with bounded exponential backoff; worker is idempotent, retries limited, stale jobs aged-out. Predict and attribute are **separate** jobs so scores show even if explanation is slow/fails. Cache keys include image/model/preprocess/calibration/policy hashes + attribution target.

### Option C-fallback — reduced scope (only if services denied)
Optional browser **ONNX Runtime Web** [S18] for inference only, with a different (reduced) design for audit/auth/Grad-CAM — a separately approved reduced scope, **not** a silent static mock replacing promised functionality.

---

## Explicitly excluded (no approval sought)
SageMaker real-time endpoint, permanent GPU instance, RDS, OpenSearch, NAT gateway, purchased domain, Bedrock/any paid LLM API, purchased Kiro credits, multiple parallel architectures on the live account.

---

## Security controls (carried from doc 04)
Curated allowlisted image IDs only (no arbitrary URL/path/upload); project-level authz on read+write; reviewer identity from verified token (never a user-supplied actor field); schema/enum/length/revision validation; CORS to configured UI origins only; block public S3 writes + direct access to private artifacts; narrow roles, encryption defaults, TLS, no browser-embedded secrets; worker not in a VPC (no NAT); append-only review events (accountability design, **not** immutable regulatory storage); no clinical patient data; no JWT/credential/raw-bytes/sensitive-text logging.

---

## Cost envelope — PROPOSAL ONLY (all values UNKNOWN until Q2/Q3/Q4 answered)

> **Unknown budget ⇒ no new paid resources.** This table is the structure to approve before any cloud mutation; it is not an estimate of charges and nothing is pre-approved.

| Field | Value |
|---|---|
| Remaining AWS credits | **UNKNOWN (Q3)** |
| Approved max spend (USD) | **UNKNOWN (Q3)** — default $0 until set |
| Personal out-of-pocket allowed? | **UNKNOWN (Q3)** — default: prohibited |
| Access expiry (date/time + tz) | **UNKNOWN (Q2)** |
| Intended services | S3, CloudFront, Cognito, API Gateway HTTP API, Lambda (x2), ECR, DynamoDB, CloudWatch, CloudFormation |
| Region | workshop snapshot `us-east-1`; **live authorization UNVERIFIED** |
| Expected storage | small (model bundle + curated images + heatmaps); exact TBD |
| Max model jobs (finite) | **to approve** (default: small finite count, no unlimited retry) |
| Worker bounds | 1 active worker/project; ≤2 concurrent invocations overall; one-image jobs; per-job timeout; capped memory |
| API request volume | small-team only |
| Log retention | short, approved |
| Teardown owner | **TBD (Q2/owner)** |
| Kiro credit balance/limit | **UNKNOWN (Q3)** |

**Guardrails:** budget alerts are not a guaranteed hard cap (AWS notification/usage delays [S15]); add application admission limits + infra/runtime bounds. Separate four cost buckets: Kiro credits, AWS service usage, data transfer/storage, optional third-party. Check live prices only after region/services/usage are fixed.

---

## Export / rollback / teardown (summary; detail at U6)
Tag project-owned resources with project id + expiry metadata (a tag deletes nothing). Export source/lockfiles, data manifest (or reproducible retrieval manifest), model package, metrics, review events, config (no secrets), deploy instructions — to a destination **outside** the expiring workshop account. Stack-scoped deletion only after export verification + explicit G7B. Rollback = a previously tested model/app artifact pair; test locally + a small cloud smoke check. After teardown, inspect project-owned buckets/images/tables/functions/logs/auth/distributions for residual charges; leave shared workshop infra untouched.
