# OsteoPatch — separate task prompt library

**129 implementation prompts · 11 phases · prepared 5 October 2026**

This is a planning and handoff package. It does not claim that its proposed features have been built, tested, clinically validated, or deployed. The existing repository is the starting point, not a blank project.

## Start here

1. Read `BASELINE_AND_SOURCES.md` and `EXECUTION_ORDER.md`.
2. Give **F001** to the first agent: `tasks/00_foundation/F001__inventory-the-real-baseline-without-changing-product-code.md`. It inventories the actual checkout and preserves existing work.
3. Give one complete task Markdown file to each subsequent fresh agent session. Each file contains the relevant safety rules, dependency contracts, exact target files, step-by-step changes, named acceptance checks, verification commands, and a stopping point.
4. Review the diff and receipt with `templates/REVIEW_ONE_TASK.md`. Only an accepted prerequisite unlocks its dependent task. Start no more than one writer by default.

Do not run the folder numerically without checking dependencies: some review tasks consume an analytics contract, and some whole-slide tasks consume a model job interface. `TASK_MANIFEST.json` is the machine-readable source of task dependencies, not evidence that work is complete.

## What the package contains

| File/folder | Purpose |
|---|---|
| `TASK_INDEX.md` | All 129 tasks with track and dependencies |
| `EXECUTION_ORDER.md` | Dependency-led core-review and demo-release routes |
| `tasks/` | One fully self-contained prompt per task |
| `contracts/` | Shared scientific, data, scope, and engineering definitions |
| `GLOBAL_TASK_RULES.md` | Safety, test-first workflow, isolation, and receipt rules |
| `FEATURE_COVERAGE.md` | Mapping to all 69 sections of the previous roadmap |
| `BASELINE_AND_SOURCES.md` | Actual inspected baseline and primary references |
| `TASK_MANIFEST.json` | IDs, contracts, paths, dependencies, and initial PLANNED status |
| `templates/` | Execute, review, repair, and evidence-receipt templates |
| `PACK_VALIDATION.json` | Structural checks performed on this planning package |

## Release tiers

**DEMO:** core experience, reports, provenance, guided session, and release verification. **PLATFORM:** teaching, collaboration, import workflows, WSI foundations, or larger usability extensions. **RESEARCH:** experiments, calibration, outliers, active learning, spatial area summaries, or candidate model development; actual scientific work requires its own approval. **GATED_DEPLOY:** preparation by default; publishing/cloud mutation requires separate explicit authorization.

The proposed full demo closure currently has **52 tasks including prerequisites**. This is not 52 mandatory new builds: verified existing behavior may satisfy tasks with NO_CHANGE_VERIFIED. It is also not a runtime or cost estimate. Research and enterprise work can remain planned while the bounded demo is accepted.

## Important boundaries

The numerical examples in test fixtures are not production statistics. Reviewer agreement is not model accuracy. Source groups are not verified patients. The WSI feature needs real slides and coordinates. Display zoom is not microscope magnification. Reconstructed attribution weights are not silently substituted for frozen model artifacts. Seeded-email login is demo identity, not shared-deployment authentication.

Every task stops at its own receipt. There is no automatic continuation, scheduling, training, merge, or deployment. Default additional authorized cloud spend remains **USD 0**. The prompts reduce ambiguity; they do not replace review of security-sensitive or scientific work.
