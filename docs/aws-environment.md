# AWS environment — OsteoPatch Review (workshop)

**Captured:** 2026-10-03 (Asia/Bangkok) · **Region:** `us-east-1` · **Status legend:** VERIFIED / AVAILABLE-NOT-TESTED / ACCESS-DENIED / PROPOSED.

> **Credentials are TEMPORARY workshop STS credentials and must never be hard-coded, committed, or pasted into chat.**
> They live only in the local AWS CLI profile `workshop` (`~/.aws/credentials`), never in this repo or in `mcp.json`.
> The `ASIA…` access-key prefix + `assumed-role/WSParticipantRole` ARN confirm they are short-lived and will expire.

## 1. Authentication — VERIFIED
- `aws sts get-caller-identity` succeeds via profile `workshop`.
- Account: **153485202811**
- Role: `arn:aws:sts::153485202811:assumed-role/WSParticipantRole/Participant`
- Region: `us-east-1` (profile default)
- Credential source: temporary STS session credentials (Workshop Studio); **expire** — re-fetch from Workshop Studio → AWS account access → Get AWS CLI credentials when expired.

## 2. Capability matrix (read-only tests) — VERIFIED
| Service | Test | Result |
|---|---|---|
| STS | get-caller-identity | **AVAILABLE** |
| S3 | ls (own account) | **AVAILABLE** — buckets: `cdk-hnb659fds-assets-…`, `sample-app-s3bucket-…` |
| S3 (public IDC) | ls `--no-sign-request` on `idc-open-data`, `-two`, `-cr` | **AVAILABLE** (all three list) |
| CloudFormation | list-stacks | **AVAILABLE** — stacks: `CDKToolkit`, `vscode-server`, `sample-app`, `kirocrew-deployment`, `login-telemetry` (DO NOT DELETE) |
| CloudFront | list-distributions | **AVAILABLE** — 2 distributions (vscode-server, kirocrew dashboard) |
| Lambda | list-functions | **AVAILABLE** — incl. `idc-IDCLambda-*` (Identity Center), vscode health/secret, kirocrew helper |
| EC2 | describe-instances | **AVAILABLE** (read) — 5 running instances incl. 2× t3.xlarge (vscode + kirocrew), t3.micro web/load (workshop infra — DO NOT TOUCH) |
| ECR | describe-repositories | **AVAILABLE** — CDK container-assets repo exists |
| ECS | list-clusters | **AVAILABLE** (read) — 0 clusters |
| SageMaker | list training/processing/models/domains/endpoints | **AVAILABLE** (read/list) — all empty (nothing running) |
| IAM | list-roles | **AVAILABLE** (read). get-user N/A for assumed-role (expected, not a denial). |

> No create/write/PassRole was probed. A read success does **not** prove create/train/deploy permission. Those remain **AVAILABLE-NOT-TESTED** until a specific bounded create is approved.

## 3. IDC connectivity — VERIFIED (public) + prior finding
- Public IDC buckets `s3://idc-open-data/`, `/idc-open-data-two/`, `/idc-open-data-cr/` are readable anonymously in `us-east-1`. All content is **DICOM**.
- **Prior evidence (idc-index v24):** the osteosarcoma collection (DOI `10.7937/tcia.2019.bvhjhdas`) is **NOT in IDC** → direct-IDC-S3 for this project's data is impossible. See `aidlc-docs/inception/idc-access-investigation.md`.
- **Approved data route (G1 = B):** TCIA Osteosarcoma-Tumor-Assessment, local-dev only, NOT an IDC/eligibility claim.

## 4. Dataset-access strategy
- Labelled 3-class JPG patches + CSV come from **TCIA** (not IDC). CSV already audited locally (1,144 rows). Images not yet fetched.
- Preferred future path: fetch once via TCIA Aspera on a Linux/AWS compute step → land in project S3 `raw/` → audit against S3. Do NOT persist full dataset locally.

## 5. Proposed training architecture (PROPOSED — nothing provisioned)
Preference order based on verified reads (create perms still untested):
- **A. SageMaker** — list APIs work; CPU training/processing against S3 using **FastFile** input mode (stream 1,144 small JPGs, no full copy). Needs an execution role + create perms (untested).
- **B. EC2/Fargate** — if SageMaker create denied; ephemeral CPU for Aspera fetch + hashing, then stop. Account already runs t3-class instances.
- **C. Local** — P2000 GPU / CPU for tiny experiments (always available).
No GPU training proposed yet; model is a small MobileNetV3-head (CPU-feasible).

## 6. Proposed deployment architecture (PROPOSED — nothing provisioned)
- **CDK bootstrap: VERIFIED present** (`CDKToolkit` stack, bootstrap v32, assets bucket + ECR repo) — no bootstrap needed.
- Frontend: private S3 bucket + CloudFront (OAC). Backend (if needed): Lambda + API Gateway HTTP API (async 202+poll pattern). Inference: CPU Lambda container in ECR. State: DynamoDB. One reviewed SAM/CDK stack.
- Tooling: AWS CLI 2.37.9 ✓, Python 3.12.10 ✓, Node 24.19 ✓, npm 11.17 ✓, CDK 2.1144.0 ✓, Docker 29.6.1 ✓ (daemon state TBD), **SAM CLI absent** (install only if SAM chosen).

## 7. Current limitations of this temporary environment
- Credentials expire (short-lived STS) → re-fetch periodically.
- This runs on a **local Windows machine**, not the workshop VSCode Server; commands may spawn fresh processes, so creds are kept in profile `workshop`.
- No budget / expiry / rubric confirmed (owner Q2/Q3/Q4 open) → **no billable resource created**.
- Create/train/deploy permissions are UNTESTED (only reads performed).

## 8. Actions that require owner approval (nothing done without it)
- Creating any S3 project bucket, SageMaker job, EC2/Fargate task, Lambda, API Gateway, CloudFront distribution, or DynamoDB table.
- Fetching the TCIA image set (~197 MB) to any compute.
- `cdk deploy` / `sam deploy` / any stack mutation.
- Installing SAM CLI (only if SAM is the chosen IaC path).

## MCP servers configured (Phase 4)
`~/.kiro/settings/mcp.json` created with: `aws-managed` (mcp-proxy-for-aws → `https://aws-mcp.us-east-1.api.aws/mcp`, credential-chain via profile `workshop`), `aws-pricing`, `aws-iac` (cfn), `aws-documentation`, `drawio`. **No credentials in the file.** Requires a **new Kiro session** to load.
