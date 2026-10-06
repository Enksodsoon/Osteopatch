# Project status

**Repository maintenance baseline: 5 October 2026.** This is a maintained scope statement, not a live service-health monitor. Exact run evidence belongs in [docs/evidence](evidence/README.md); current Actions results are authoritative for a particular commit.

## Implemented in source
The core application includes H&E patch browsing, uncertainty-first ordering, three uncalibrated class scores, accept/correct/defer decisions, revision history, export, model-card limitations and qualified attribution. Enterprise extensions add project scope, capability-based roles, audit, registry and governance surfaces. Both interfaces have unit tests and production builds.

Repository infrastructure adds current guides, contributor/security policies, ownership and issue templates, portable commands, static-site tests, commit-pinned CI, Pages publication, reviewed dependency updates and opt-in MCP profiles. Manual workflows distinguish capability checks, frontend deployment and draft prereleases.

## What a clean clone proves
On the current rebased repository verification, **with the optional `model` extra installed** (`uv sync --locked --extra dev --extra wsi --extra model`): **160 backend tests passed with 5 environment-gated skips** (all "G4 bundle not present"), **17 tooling tests passed**, mypy and the blocking Ruff gate were clean, and both frontend production builds passed. Without that extra the torch-gated tests skip and the count is lower (112 passed / 11 skipped) — a smaller number from a *different* environment, not a regression. Which optional runtimes a given machine actually has is recorded per-machine in [docs/evidence/runtime-capability.json](evidence/runtime-capability.json).

These are software results, not evidence of clinical model performance. New repository/site checks are reported in the dated maintenance evidence record and current CI.

## Attribution and the torch-free serve path
Contrastive Grad-CAM over the recovered head returns real 384×384 overlay PNGs once the `model` extra is installed; this was verified over HTTP, including that the same (image, pair) is byte-identical on a second call and that a different pair is not. The encoder weights are cached under `runtime-artifacts/models/torch-hub` so a demo run needs no network. A subprocess import hook (`test_serve_path_torch_free.py`) proves the ordinary review routes never resolve torch — the promise in [dependencies.md C1](dependencies.md) is measured, not assumed. A torch-free machine remains fully supported; attribution then degrades to an honest 503 rather than a fabricated heatmap.

## Unified authenticated surface
The enterprise app fronts the whole review surface at the G6-shaped `/v1/*` paths, reusing the existing project-scoped handlers rather than reimplementing them. Every route was exercised over real HTTP as all six demo personas against a COPY of the read model; see [docs/evidence/unified-surface.json](evidence/unified-surface.json). Tenant scope is enforced before the G6 handler runs, so an out-of-scope image is 404 on the pixel and attribution paths too — not just on the JSON detail route.

## Operational and scientific prerequisites
| Area | Remaining boundary |
|---|---|
| Real-data reviewer | Requires a separately restored, hash-verified runtime bundle; Git does not include pixels/models/databases. |
| Original model | Original G4 binary is absent. A recovered head has a separate identity and does not restore original-model provenance or generalization claims. |
| Model reliability | Viable-tumor recall is 0.110345 in the frozen exploratory evaluation; no clinical use. |
| Torch stack | The `model` extra is ~1–2 GB and optional. It is not required to start or serve the app; only attribution and future live inference load it. |
| Enterprise security | Local issuer/dev key and prototype governance are not production authentication or a security audit. |
| Existing AWS demo | Source and deployed revisions can differ. The protected `aws-demo` GitHub environment, reviewer gate and non-secret resource identifiers are configured; frontend deployment remains disabled (`AWS_DEPLOY_ENABLED=false`) and no OIDC role is configured. Workshop access/cost approval is still required before enabling it. |
| Public demo writes | Authentication, abuse controls, budget limits and backup/retention require review before wider exposure. Do not submit private information. |
| MCP | Profiles are installed but disabled by default. Authentication and per-tool authorization must be performed in the client; no server connection is implied by a config file. |
| License | Proprietary declaration retained. Open-source dependencies do not make the project itself open source. |

## Release gate
A broader release needs verified runtime distribution rights, current artifact identities, appropriate access control, an explicitly approved cost plan, tested backup/restore and a documented threat review. Clinical-use expansion would require a separate scientific and regulatory program; it is not delivered by repository cleanup.
