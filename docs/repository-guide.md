# Repository guide

| Location | Put here | Do not put here |
|---|---|---|
| Root | Entry README, ownership/policy files, canonical dependency and editor settings | Runtime data, scratch logs, duplicated planning dumps |
| `app/g6` | Core review code, tests and existing deploy contracts | A second copy of the enterprise domain |
| `app/g7-enterprise` | Extension code and tests that reuse the core | An independent fork of model/review logic |
| `docs` | Current guides, dated audit/verification records, approved screenshots | Claims copied from plans as if verified |
| `aidlc-docs` | Preserved provenance, QC, frozen evaluations and workshop history | Silent edits to old metrics or identities |
| `site` | Explicit public HTML/CSS source | Secrets, model files, arbitrary repository exports |
| `scripts` | Small auditable developer/verification utilities | Hidden cloud mutations or global install hooks |
| `tests/tooling` | Artifact-free tests for repository and publication tooling | Fabricated real-data acceptance results |
| `config/mcp` | Credential-free, client-specific examples | Personal tokens or machine-wide settings |
| `.github` | Pinned workflows, ownership, templates and update configuration | Unrestricted deployment from fork PRs |
| `runtime-artifacts` | Local approved pixels, model binaries, databases; ignored by Git | Material intended for public source control |

## Stable paths
Application imports, deployment scripts and frozen evidence refer to existing paths. This organization pass intentionally adds navigation rather than moving the scientific record or renaming `g6`/`g7-enterprise` blindly. Any future move must update all imports, tests, build contexts and evidence links in a migration PR.

## Current versus historical
The root README and [documentation index](README.md) route current work. `README_START_HERE.md`, numbered handoff documents, templates and staged prompts are original planning context. `PACKAGE_INTEGRITY_SHA256.json` describes the historical handoff package, not an integrity digest of every future repository revision. Dated audits describe the revision they inspected; newer observations belong in a new evidence record.

## Before a commit
Inspect `git status --short` and the staged diff. Exclude secrets, local MCP tokens, virtual environments, browser caches, databases, raw image collections, model weights and generated `_site/`. Keep curated screenshots only when their public provenance is established. Run [contributor checks](../CONTRIBUTING.md) and do not include another worker's unrelated changes.
