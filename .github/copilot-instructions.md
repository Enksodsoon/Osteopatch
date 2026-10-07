# Repository guidance

Read and follow the root `AGENTS.md` before proposing or applying changes. It is the authoritative contributor/agent contract for architecture, scientific invariants, costs, verification and publication boundaries.

Start with [`docs/agent-handoff.md`](../docs/agent-handoff.md) for the current application, full demo setup, feature flow and verification commands. Use [`docs/data-inventory.md`](../docs/data-inventory.md) to understand the corpus, model artifacts and what is or is not included in a Git checkout. `docs/evidence/demo-readiness.md` is the latest dated full-demo record. Use `docs/README.md` to find other current guides.

`aidlc-docs/` and the original numbered handoff documents contain historical decisions and frozen evidence; do not restart an Inception-only workflow or overwrite historical records. Runtime images, models and databases are local-only; a clean clone needs an authorized runtime bundle before it can run the populated demo.
