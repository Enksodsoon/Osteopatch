# Security policy

## Scope and support
OsteoPatch Review is an educational/research prototype. There is no clinical certification, production support commitment or incident-response service-level agreement. Security fixes target current `main`; historical workshop snapshots are not maintained releases.

## Reporting a vulnerability
Use the repository's **Security → Report a vulnerability** private reporting channel when available. Do not put credentials, patient information, exploit payloads against a live service, or sensitive screenshots in public issues. If private reporting is unavailable, open a minimal public issue requesting a private contact route without disclosing the vulnerability. The maintainer must establish a private route before sensitive details are exchanged.

Report the affected revision, component, preconditions, impact and a minimal non-sensitive reproduction. Do not test against third-party systems or modify other reviewers' data. No bug-bounty reward is promised.

## Trust boundaries
- Local development binds to loopback. The enterprise local identity provider and its development signing key are not production authentication.
- The historical AWS workshop demo is not a secure clinical service; do not submit private data. Public demo writes and operational authentication need explicit review before wider use.
- Model scores and attributions can be wrong. Preserve the safety disclosures and known weak-class performance.
- MCP servers are privileged software, not a sandbox. Enable only reviewed servers with limited credentials; never approve all tools automatically.
- GitHub Actions use read-only default tokens. Deployment and draft-release write privileges are restricted to their jobs and trusted `main` dispatches.

## Secrets and releases
Never commit `.env`, tokens, signing keys, session databases or runtime bundles. Use GitHub environments and short-lived OIDC credentials for an approved cloud deployment; never add long-lived AWS keys to workflow files. Rotate any exposed credential at its issuer; removing the current file does not erase history.

Dependency update automation and static analysis help discover issues but are not a security audit. See the [deployment runbook](docs/deployment.md) and [current status](docs/project-status.md) for remaining gates.
