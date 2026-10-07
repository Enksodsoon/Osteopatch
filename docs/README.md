# Documentation

Use these guides for the current repository. Historical plans and point-in-time evidence are preserved rather than silently rewritten.

| Start here | Purpose |
|---|---|
| [AI agent handoff](agent-handoff.md) | Current application, safe full-demo startup, workflows, roles, verification and agent rules |
| [Data and artifact inventory](data-inventory.md) | Corpus provenance, class counts, model/evaluation identities, local assets and clean-clone limits |
| [Getting started](getting-started.md) | Clean-clone setup, runtime prerequisites, commands and troubleshooting |
| [Architecture](architecture.md) | Component boundaries, data flow and stable source locations |
| [Model evidence](model-evidence.md) | Frozen metrics, model identities and scientific limitations |
| [Deployment](deployment.md) | Pages publication, manual AWS frontend deployment, rollback and cost gates |
| [Agent and MCP tooling](agent-tooling.md) | Safe, opt-in Kiro/VS Code configuration and credential boundaries |
| [Repository guide](repository-guide.md) | Where files belong, ownership and what must not be committed |
| [Project status](project-status.md) | Implemented capabilities versus prerequisites and unresolved risks |

## Contributor entrypoints
[Repository overview](../README.md) · [Contributing](../CONTRIBUTING.md) · [Security](../SECURITY.md) · [Agent contract](../AGENTS.md) · [License notice](../LICENSE)

## Evidence and historical material
- [Current-state audit](current-state-audit.md) is a **dated snapshot**, not a live status endpoint.
- [Verification records](evidence/README.md) retain the revision, scope and limitations of each run.
- [Local demo readiness](evidence/demo-readiness.md) records the 7 October 2026 Chromium, WSI, backend and frontend verification on the implementation host.
- [AI-DLC history](../aidlc-docs/README.md) holds original provenance, QC, evaluations and deployment records.
- The numbered `00_`–`08_` documents, [original handoff](../README_START_HERE.md), [prompts](../prompts/README.md) and [templates](../templates/README.md) explain original decisions. Do not restart them as if implementation had not happened.
- [Dependency register](dependencies.md) and [sources/reuse register](07_sources_and_reuse_register.md) track third-party provenance.

The public website is generated from [site/](../site/README.md). Its evidence metrics are read from frozen JSON; it is not an inference service or an independent validation report.
