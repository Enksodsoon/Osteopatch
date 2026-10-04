# Environment and permission report — Inception

**Run date:** 2026-10-03 (Asia/Bangkok) · **Status:** read-only inspection, nothing installed, created, or spent.
**Scope:** local workstation + authorized read-only AWS inspection. No secrets printed. No cloud mutation attempted.

This report is evidence for G0 (requirements/workflow) and G1 (source/access). It does not approve any install, download, training run, or deployment.

---

## 1. Local workstation — VERIFIED

| Property | Value | Note |
|---|---|---|
| OS | Microsoft Windows 11 Pro, build 10.0.26200, 64-bit | Shell is PowerShell |
| Logical CPUs | 12 | |
| RAM | 31.8 GB | Comfortable for a small head-only training run |
| Disk C: free | **75.3 GB** | **Tight.** TCIA public cohort is ~197 MB raw, but torch/CUDA wheels, a Docker image, and node_modules can consume 10–30 GB. Monitor before any download or Docker build. |
| GPU 0 | NVIDIA Quadro **P2000**, driver 582.16, ~5 GB VRAM (nvidia-smi reports 5120 MiB) | CUDA-capable (Pascal). Adequate for MobileNetV3-Small head training at batch 16; **not** for large models. Batch size may need reduction after memory profiling (U2). |
| GPU 1 | Intel UHD Graphics 770 | Integrated; not used for training |

### Toolchain — VERIFIED present

| Tool | Version | For |
|---|---|---|
| Python | 3.12.10 (`...\Programs\Python\Python312`) | model/domain package |
| pip | present | |
| Node.js | v24.19.0 | React/Vite frontend |
| npm | 11.17.0 | |
| git | 2.55.0.windows.2 | version control |
| Docker CLI | 29.6.1 | worker container image (U5) |

### Toolchain — gaps (NOT installed)

| Item | State | Consequence |
|---|---|---|
| **AWS CLI** | **absent** (no `aws` on PATH; not in standard install dirs) | Cannot run even a no-sign-request `aws s3 ls` object check. Needed for the bounded IDC membership verification in G1. |
| **AWS SAM CLI** | **absent** | Needed for `sam validate`/deploy in U5 (deferred). |
| **kiro-cli** | not on PATH in this shell | Workshop recipe assumes `kiro-cli chat`; verify how the user launches Kiro. |
| **uv** | absent | Optional; pip is sufficient. |
| **PyTorch / torchvision** | absent | Expected — no implementation yet. Install deferred to U2 behind G2 + compute approval. |
| **Docker daemon** | CLI present but **daemon not running** (`docker info` returned empty server version) | Docker Desktop must be started before any worker image build (U5, deferred). |
| Python 3.12 vs torch | note | Confirm current torchvision provides a CUDA/CPU wheel for Python 3.12 at install time (U2). |

---

## 2. AWS identity, region, services — UNVERIFIED (hard blocker for cloud planning)

**No authorized AWS access is configured on this machine.** Verified facts:

- No `aws` executable found (CLI not installed).
- No `~/.aws` directory exists (no `config`, no `credentials`).
- No AWS credential environment variables are set. The only `AWS_*` variable present is `AWS_EXECUTION_ENV = "AmazonQ-For-CLI Version/2.27.1 acp-client/kirocrew"`, which is the KiroCrew CLI runtime user-agent marker — **not** an AWS credential or an assumed role.

**Therefore none of the following could be inspected, and all are recorded as not verifiable rather than assumed:**

| Item | State |
|---|---|
| Active AWS account / caller identity (`sts get-caller-identity`) | not verifiable |
| Active authorized region (workshop snapshot says `us-east-1`; a captured value is not a live authorization) | not verifiable |
| Permissions on S3, ECR, Lambda, DynamoDB, API Gateway, Cognito, CloudFront, CloudWatch, CloudFormation/SAM, IAM PassRole | not verifiable |
| Remaining AWS credits / budget | not verifiable |
| Workshop/account access expiration | not verifiable |

**No mutation was probed to discover permissions** (per the security rule: a read-only success never implies create/PassRole, and we do not probe writes to learn what is allowed).

### What this means for the plan
- The **local vertical slice (U1–U4) can proceed** on this machine once G0–G3 are approved; it needs no AWS.
- The **cloud deployment (U5) is blocked** at the environment level until the user either (a) installs and configures AWS CLI with the workshop credentials in their own terminal, or (b) runs the IDC/AWS checks themselves and pastes results. Agents must not install credentials or switch accounts.

> **Correction (2026-10-03):** the absence of AWS credentials does **not** block *public IDC discovery*. IDC's public buckets permit anonymous access (`aws s3 ls --no-sign-request s3://idc-open-data/`) with no AWS account, and the official `idc-index` Python client queries IDC metadata and public data with no cloud credentials at all. The only thing missing locally for the `aws s3` form is the AWS **CLI tool**; the `idc-index` route avoids even that. Credential configuration remains required only for inspecting the owner's *own workshop account* (identity/region/permissions) and for cloud deployment (U5).

### Public IDC facts VERIFIED without credentials (read-only web, no download)
From the AWS Open Data registry entry for NCI IDC:
- IDC public buckets: `s3://idc-open-data/`, `s3://idc-open-data-two/`, `s3://idc-open-data-cr/`; **region `us-east-1`**; **all content is DICOM**; accessible `--no-sign-request` (no AWS account required for listing/reading).
- This confirms IDC distributes **DICOM**, not the TCIA-style labelled JPG patches + CSV. See the data-source decision for why that matters.

---

## 3. AI-DLC / Kiro workflow state — VERIFIED

- The handoff folder contains **only** the project steering file `.kiro/steering/osteopatch-project.md` (`inclusion: always`).
- **No AI-DLC rules are installed**: there is no `.kiro/steering/aws-aidlc-rules/` and no `.kiro/aws-aidlc-rule-details/`.
- No native Kiro Specs workflow and no AI-DLC 2.x command layout were found in this folder.

**Consequence:** the workflow controller is **not yet chosen or installed**. This is decision G0-W (see requirements). Installing v1.0.1 per `docs/00_ai_dlc_setup.md` is a reviewed choice, not something to do silently, and must use a fresh inspection of the official v1.0.1 release archive. Do not mix v1 install steps with 2.x slash commands.

---

## 4. Honest limitations of this report
- AWS findings are **absence-of-configuration** facts, not a statement that the user has no AWS account — only that this machine has no configured access right now.
- The IDC bucket facts come from the public registry page; an **object-level manifest for the osteosarcoma collection was not retrieved** (needs AWS CLI or `idc-index`).
- Disk headroom (75 GB) is a point-in-time reading; re-check before any download or Docker build.
- Docker daemon state can change; re-check at U5.
