# Project status

**Repository maintenance baseline: 5 October 2026.** This is a maintained scope statement, not a live service-health monitor. Exact run evidence belongs in [docs/evidence](evidence/README.md); current Actions results are authoritative for a particular commit.

## Implemented in source
The core application includes H&E patch browsing, uncertainty-first ordering, three uncalibrated class scores, accept/correct/defer decisions, revision history, export, model-card limitations and qualified attribution. Enterprise extensions add project scope, capability-based roles, audit, registry and governance surfaces. Both interfaces have unit tests and production builds.

Repository infrastructure adds current guides, contributor/security policies, ownership and issue templates, portable commands, static-site tests, commit-pinned CI, Pages publication, reviewed dependency updates and opt-in MCP profiles. Manual workflows distinguish capability checks, frontend deployment and draft prereleases.

## What a clean clone proves
On the current rebased repository verification: **112 backend tests passed with 11 environment-gated skips; 29 reviewer UI tests and 2 enterprise UI tests passed; both frontend production builds passed.** These are software results, not evidence of clinical model performance. New repository/site checks are reported in the dated maintenance evidence record and current CI.

## Operational and scientific prerequisites
| Area | Remaining boundary |
|---|---|
| Real-data reviewer | Requires a separately restored, hash-verified runtime bundle; Git does not include pixels/models/databases. |
| Original model | Original G4 binary is absent. A recovered head has a separate identity and does not restore original-model provenance or generalization claims. |
| Model reliability | Viable-tumor recall is 0.110345 in the frozen exploratory evaluation; no clinical use. |
| Enterprise security | Local issuer/dev key and prototype governance are not production authentication or a security audit. |
| Existing AWS demo | Source and deployed revisions can differ. The protected `aws-demo` GitHub environment, reviewer gate and non-secret resource identifiers are configured; frontend deployment remains disabled (`AWS_DEPLOY_ENABLED=false`) and no OIDC role is configured. Workshop access/cost approval is still required before enabling it. |
| Public demo writes | Authentication, abuse controls, budget limits and backup/retention require review before wider exposure. Do not submit private information. |
| MCP | Profiles are installed but disabled by default. Authentication and per-tool authorization must be performed in the client; no server connection is implied by a config file. |
| License | Proprietary declaration retained. Open-source dependencies do not make the project itself open source. |

## Release gate
A broader release needs verified runtime distribution rights, current artifact identities, appropriate access control, an explicitly approved cost plan, tested backup/restore and a documented threat review. Clinical-use expansion would require a separate scientific and regulatory program; it is not delivered by repository cleanup.
