# Verification evidence

Each record describes a particular revision, environment and test scope. A point-in-time pass does not certify a later revision or a live deployment. Keep historical records; add a new dated result instead of rewriting old outputs.

Existing records include [baseline verification](step02-baseline.md), [static-analysis baseline](step04-static-baseline.md), [local smoke results](smoke-result.json) and [real-data browser results](e2e-ui-result.json). They do not imply that a clean clone includes the original runtime bundle.

Repository platform maintenance is documented in [repository-platform-2026-10-05.md](repository-platform-2026-10-05.md). Current GitHub Actions runs are the source for a specific commit's CI status. Scientific performance remains in the frozen G4/G5 evidence, separate from these software checks.
