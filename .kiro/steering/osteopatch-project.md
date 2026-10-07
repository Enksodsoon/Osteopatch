---
inclusion: always
---
# OsteoPatch project context

Read `AGENTS.md`, `docs/agent-handoff.md`, `docs/data-inventory.md` and `docs/README.md` first. `docs/evidence/demo-readiness.md` is the latest dated end-to-end verification record. OsteoPatch Review is already implemented; the original Inception-only handoff is historical. Preserve its evidence without rerunning or mixing workflow controllers.

The canonical output order is `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. This is an educational/research prototype, not a clinical device. Unknown labels must fail. Mixed, uncertain and poor-quality are review/QC states. Scores are uncalibrated. Heatmaps are neither segmentation nor a causal explanation. Corrections are append-only and never automatically retrain a model.

Preserve the separate identities of the absent original G4 binary and the recovered attribution head. Keep frozen records in `aidlc-docs/` unchanged; document new work in a dated evidence record.

No paid service, AWS mutation, public data expansion, model training, global MCP installation or broad deletion without explicit task-specific authorization. Never print credentials or trust all MCP tools. Shared MCP profiles are disabled by default; authentication and tool approval are separate steps.

Inspect current Git status and protect other workers' changes. Use small tested changes and the verification commands in `AGENTS.md`. Report actual test results, skips, deployment state and blockers; configuration is not execution.

For a runnable demo, use `make unified-app` or the portable `scripts/demo.py` command in `docs/agent-handoff.md`. Runtime images, model files and databases are gitignored; a clean clone must restore an authorized local bundle. Never seed or run write-capable checks against that source bundle.
