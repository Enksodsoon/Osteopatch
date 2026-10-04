# Decision and approval log — OsteoPatch Review

Actual recorded decisions. Rejected/superseding decisions are kept, not overwritten.

---

## D1 — G1 source selection

| Field | Value |
|---|---|
| Decision ID / gate | **G1** — dataset source + access route |
| Date/time | 2026-10-03, Asia/Bangkok |
| Decision owner | Enk (owner) |
| Artifact reviewed | `aidlc-docs/inception/data-source-decision.md` (via dashboard; owner notes remote file-open was offline, so Kiro must reconcile actual files) |
| Question | Q1 — IDC/AWS mandatory, TCIA direct, or verify rubric first |
| Decision | **Accepted B — official TCIA Osteosarcoma-Tumor-Assessment, DOI 10.7937/tcia.2019.bvhjhdas** |
| Authority boundary | **Local educational prototype + data audit only.** Credential-free IDC discovery (`idc-index`) permitted. |
| What remains unapproved | Hackathon/competition source eligibility (unverified, depends on rubric Q4); G2 data/split; any training; any cloud spend/deploy. TCIA must never be labelled an IDC/AWS Open Data download. |
| Evidence | Owner dashboard instruction 2026-10-03 |
| Next checkpoint | Execute bounded U1 audit → G2 REVIEW REQUIRED |

## D2 — Q2 deadline / access expiry

| Field | Value |
|---|---|
| Decision | **Deferred.** Leave unknown; do not invent a deadline from an old countdown. Does not block local audit. |
| Owner / date | Enk, 2026-10-03 |

## D3 — Q3 budget / services

| Field | Value |
|---|---|
| Decision | **No additional AWS/cloud spend authorized.** Use existing Kiro allowance; no credit purchase, no plan upgrade, no account switch. |
| Authority boundary | Zero paid cloud resources. Local CPU-only work only. |
| Owner / date | Enk, 2026-10-03 |

## D4 — Q4 rubric

| Field | Value |
|---|---|
| Decision | **Deferred / unverified.** Do not invent mandatory AWS services or claim competition compliance. |
| Owner / date | Enk, 2026-10-03 |

## D5 — Q5 reviewers / language

| Field | Value |
|---|---|
| Decision | Working default: **one local reviewer (Enk); Thai interface wording with English pathology terms.** UI work deferred to later units. |
| Owner / date | Enk, 2026-10-03 |

## D6 — Q6 inputs / exposure

| Field | Value |
|---|---|
| Decision | **Curated public dataset only.** No hospital uploads, no patient information, no public server, no public upload endpoint. |
| Owner / date | Enk, 2026-10-03 |

## D7 — Q7 AWS access

| Field | Value |
|---|---|
| Decision | **Deferred.** Do not request workshop credentials for public-source discovery; never ask owner to paste secrets. Public IDC discovery proceeds credential-free. |
| Owner / date | Enk, 2026-10-03 |

## D8 — U1 scope authorization

| Field | Value |
|---|---|
| Decision | **U1 approved**: verify/install project-local AI-DLC v1.0.1 as needed (preserve existing steering), establish a minimal CPU-only audit environment, verify provenance, acquire approved TCIA data within download/storage limits, implement+test the strict importer/auditor, reconcile counts/dups/exclusions, verify patient mapping, propose a defensible grouped split or document why not. |
| Authority boundary | No model training, no model-weight download, no app build, no deploy, no credit purchase, no permission change, no public server. Stop at **G2 REVIEW REQUIRED**. |
| Owner / date | Enk, 2026-10-03 |
| Note | Owner's approval is of this stated unit, **not** a blanket approval of everything in the inception artifacts. |

## Correction C1 — IDC credential conflation

| Field | Value |
|---|---|
| Issue | Inception G1 doc + environment report said missing AWS credentials blocked IDC discovery. |
| Correction | Missing credentials do **not** block public IDC discovery; IDC public buckets allow anonymous `--no-sign-request` access and `idc-index` needs no cloud credentials. The real limit was the missing AWS CLI tool. Corrected in `data-source-decision.md` and `environment-and-permission-report.md`. |
| Owner / date | Raised by Enk, applied 2026-10-03 |


## D9 — U1 architecture pivot: cloud-first (SUPERSEDES D8's local-download assumption)

| Field | Value |
|---|---|
| Decision ID / gate | U1 architecture (still ends at **G2**) |
| Date/time | 2026-10-03, Asia/Bangkok |
| Decision owner | Enk (owner) |
| Decision | **U1 is now cloud-first, not local-data-first.** The osteosarcoma dataset must NOT be downloaded to or persistently stored on the Windows workstation when AWS can perform access/audit/(later)training directly. Local Windows/Kiro = **control plane** (source, AI-DLC docs, IaC, commands, small manifests/reports). AWS = **data/compute plane** (dataset access, temp object storage, auditing, later training/artifacts/metrics). |
| Supersedes | **D8's assumption** that U1 downloads TCIA to local scratch. D8's *scope, bounds, importer rules, and stop-at-G2* otherwise still hold. The 500 MB/2 GB **local** caps now effectively mean "ideally ~0 raw data locally"; small audit CSV/JSON/MD review copies are fine. |
| Order of investigation | (1) Direct IDC public-S3 access for the EXACT labelled data, keeping four questions separate (collection exists / exact 1,144 patches or equivalent objects / three-class labels linkable / reliable patient mapping); do not infer 2–4 from a related collection. (2) If IDC exact-match not usable, TCIA remains approved but via a **cloud-to-cloud** route into project S3 (us-east-1), not a local download; if TCIA has no headless-automatable supported route, **document that blocker before** any local fallback. |
| Cost/permission gate | Before any bucket/compute/chargeable transfer: inspect workshop AWS identity/region/permissions (no secrets), identify permitted resources, estimate max U1 cost, prefer free/public + ephemeral compute, present any materially-costly resource creation for approval. No credit purchase, no IAM change, no account upgrade. Region us-east-1 unless verified otherwise. |
| U2 design | Design (not execute) the training data path around S3; evaluate SageMaker **FastFile** vs File vs Pipe, document why FastFile is preferred/rejected. No SageMaker training in U1. |
| Authority boundary | Still **no training**; ends at **G2 DATA/LABEL/SPLIT REVIEW REQUIRED**. |
| KNOWN BLOCKER | This workstation has **no AWS access configured** (no AWS CLI, no `~/.aws`, no credentials — verified 2026-10-03). The credential-free IDC investigation and the U2 design proceed now; **all project-S3 / workshop-identity / cloud-transfer / cloud-audit steps are blocked** until workshop credentials are configured by the owner in their own terminal (agents must not install credentials, switch accounts, or request pasted secrets). |
| Owner / date | Enk, 2026-10-03 |
