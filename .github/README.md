# Repository automation

| Workflow | Trigger | Purpose and boundary |
|---|---|---|
| `ci.yml` | Main push, pull request, manual | Both backend/frontend gates, scoped static analysis and repository/site checks; aggregated as `quality-gate` |
| `pages.yml` | Relevant main push, manual | Publish only the verified static `_site/` artifact |
| `codeql.yml` | Relevant main/PR changes, manual | Python and JavaScript/TypeScript code scanning; not a full security audit |
| `capabilities.yml` | Manual | Optional WSI/model import capability; no training or data validation |
| `deploy-frontend.yml` | Manual, explicit confirmation, protected environment | Existing AWS web assets only; disabled until separately authorized/configured |
| `release.yml` | Manual on trusted main | Version-checked draft research prerelease after the quality gate |

All external Actions are pinned to full commit SHAs verified against official repositories. Dependabot proposes reviewed updates for Actions, uv and both npm lockfiles; it never auto-merges or auto-deploys them. Python updates may require regenerating compatibility requirements shims in the same PR.

Standard jobs have read-only repository tokens, bounded timeouts and no cloud credentials. Write privileges are job-specific. There are no scheduled heavyweight model jobs, global agent installs or automatic paid-API calls.

Configuration references: [deployment runbook](../docs/deployment.md), [security policy](../SECURITY.md), [contributing](../CONTRIBUTING.md). Server-side repository settings are inspected separately; a YAML file alone cannot enable Pages, create an IAM role or prove a deployment.
