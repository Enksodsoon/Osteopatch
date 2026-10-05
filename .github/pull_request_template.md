## What and why

Describe the user-facing or maintenance problem and the smallest change that solves it.

## Verification

Paste exact commands and results. Distinguish clean-clone tests, runtime-dependent skips, real-data tests and deployments.

## Safety and compatibility

- [ ] No patient data, secrets, runtime databases or model binaries are committed.
- [ ] Class order, model identities, frozen evaluation evidence and append-only review behavior are preserved.
- [ ] Educational limitations remain visible; no unsupported clinical or performance claims were added.
- [ ] Documentation, dependency records and generated shims are updated where applicable.
- [ ] No paid service or cloud resource mutation is hidden in setup or CI.

## Risk and rollback

Describe affected interfaces and how this change can be reverted safely. Attach screenshots for visual changes without private information.
