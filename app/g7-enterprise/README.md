# OsteoPatch Enterprise (E1) — Multi-User Core

> **Current application and demo instructions:** this file preserves the phase-specific E1 implementation notes and contains older standalone commands and status descriptions. For the supported unified app (G7 UI + enterprise API + G6 review API), current capabilities, safe data handling and current tests, use the repository-root [AI agent handoff](../../docs/agent-handoff.md), [data inventory](../../docs/data-inventory.md) and [demo readiness record](../../docs/evidence/demo-readiness.md). Start the populated demo with `make unified-app` or the `scripts/demo.py` command there; do not use the manual seed commands below against the source runtime database.

> **Status:** E1 built and runnable locally. E2–E6 are gated scaffolds (see
> `scaffolds/`). No AWS mutation, no spend — binds `127.0.0.1` only.
>
> **Educational research prototype only. Not for diagnosis, treatment
> decisions, or predicting treatment response.**

This layer wraps the existing **G6 review API** (`app/g6/backend/osteopatch`)
with the enterprise systems concerns it lacked: identity, role-based access
control, and project-scoped multi-tenancy — **without forking** the review
logic. The G6 app is mounted as-is behind an auth + tenancy gate.

## What E1 adds (all real, all tested)
- **OIDC-style auth** — a local, deterministic token issuer (`/auth/login`) that
  stands in for Cognito/an external IdP. Same JWT shape, swappable for real OIDC
  by config. No real IdP call, no secret in code.
- **RBAC** — roles `student · reviewer · pathologist · admin · ml_engineer ·
  auditor`, enforced per route by dependency injection.
- **Multi-tenancy** — every reviewer sees only the **projects** they're a member
  of; gallery/review/export reads are project-scoped via the existing
  image-allowlist mechanism (no change to the immutable prediction model).
- **Audit** — every mutation appends a hash-chained `audit_entry` (local file
  WORM-sim; S3 Object-Lock in E6).

## Architecture (local)
```
SPA ──JWT──▶ enterprise app (FastAPI)
                 │  authn (verify JWT)  →  authz (role×project)  →  audit
                 ▼
             G6 review API  (mounted sub-app, torch-free)
                 ▼
             SQLite (reviews/events)  +  enterprise.sqlite3 (users/projects/audit)
```

## Run locally
```powershell
cd app\g7-enterprise\backend
python -m venv .webvenv
.webvenv\Scripts\python.exe -m pip install -r requirements.txt
.webvenv\Scripts\python.exe -m uvicorn enterprise.app:app --host 127.0.0.1 --port 8140
```
Seed demo users/projects (idempotent):
```powershell
.webvenv\Scripts\python.exe -m enterprise.seed
```
Then: `POST /auth/login {"email":"reviewer@demo"}` → bearer token → call
`/api/v1/images` etc. with `Authorization: Bearer <token>`.

## Tests
```powershell
cd app\g7-enterprise\backend
.webvenv\Scripts\python.exe -m pytest -q
```

## Full-stack demo over the REAL G6 data (no AWS, no spend)
Drives the whole journey against the live 1,144-row G6 SQLite store through the
auth / RBAC / tenancy gate. Point it at a COPY of the G6 db so demo review writes
never touch the canonical store:
```powershell
cd app\g7-enterprise\backend
# copy the real G6 db somewhere disposable, then:
$env:OSTEOPATCH_DB="<copy>\osteopatch_g6.sqlite3"
$env:PYTHONPATH="<repo>\app\g6\backend"
.webvenv\Scripts\python.exe -m enterprise.demo_fullstack
```
It prints: admin grants 50 real images into a project → reviewer sees the
uncertainty-ranked gallery → opens the most-uncertain patch → ACCEPT / CORRECT /
DEFER against real immutable predictions → export preserving model-vs-human →
tenancy isolation (a second project sees disjoint images; a non-member gets 404)
→ hash-chained audit verified. **Every number comes from the real model/data.**

> Note: TIFF pixels + the G4 bundle were reclaimed from scratch, so the
> pixel-serving endpoints (thumbnail/full/attribution) degrade honestly to a
> labelled error — never a fabricated image. The metadata/prediction/review/
> export surface is fully live.

## Tests

## Gated scaffolds (NOT built — design-complete stubs)
Only the genuine AWS/compute SEAMS remain gated now (they raise `GateNotApproved`):
- **E2** `ingestion.scan_and_upload`, `ingestion.tile_wsi` — pixel pipeline / WSI tiling
- **E3** `inference.run_worker_once` — GPU model execution (needs torch + compute)
- **E6** `observability.ship_audit_to_worm`, `export_otel_traces` — S3 Object-Lock + OTel

Everything ELSE in E2–E6 is now REAL local code (see below).

## Phases built (all local, all tested — no AWS, no spend)
| Phase | Module | What runs locally now |
|---|---|---|
| **E1** | `app`, `auth`, `deps`, `store`, `review_proxy`, `audit` | SSO-stub, RBAC, multi-tenancy, hash-chained audit, review surface over G6 |
| **E2** | `ingestion` | dataset register + manifest index (fail-closed on unknown labels) |
| **E3** | `inference` | idempotent enqueue + dedup + queue status (GPU exec gated) |
| **E4** | `governance` | adjudication, batch sign-off (tamper-evident hash), capture-only corrections |
| **E5** | `registry` | model state machine, eval gate, single-serving invariant, one-click rollback |
| **E6** | `observability` | drift monitor (defer/correction/disagreement rates + alerts); WORM/OTel gated |

## Full demo over the REAL G6 data (every phase)
```powershell
cd app\g7-enterprise\backend
$env:OSTEOPATCH_DB="<COPY-of>\osteopatch_g6.sqlite3"
$env:PYTHONPATH="<repo>\app\g6\backend"
.webvenv\Scripts\python.exe -m enterprise.demo_full      # E1 live + E2–E6
.webvenv\Scripts\python.exe -m enterprise.demo_fullstack # E1 review journey only
```

## Gated scaffolds base
`scaffolds/__init__.py` holds the `GateNotApproved` base the gated seams raise.
