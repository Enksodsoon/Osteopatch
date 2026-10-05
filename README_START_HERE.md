# OsteoPatch Review — original Kiro handoff

> **Historical planning entrypoint.** This document records the pre-implementation handoff from 3 October 2026 and is retained for provenance. The project has since been implemented, tested, and deployed. For the current product, architecture, verification status, and run instructions, start with [README.md](README.md).

**Prepared:** 3 October 2026 · **Historical status:** pre-implementation proposal (superseded by the current repository state).
**Execution environment:** Kiro and the user's limited AWS hackathon account.

This package turns the user's brief into a staged, reviewable project. It contains planning documents, acceptance criteria, questionnaires, and prompts. It contains **no trained model, downloaded dataset, application implementation, AWS deployment, or completed test results**. No source-selection, spending, or deployment approval is implied.

## Start here

1. Extract this ZIP into a new project folder and open the **inner `OsteoPatch_Kiro_Handoff` folder** in Kiro. Preserve the hidden `.kiro` directory. Do not overwrite an existing project's steering files.
2. Read [the project brief](PROJECT_BRIEF.md) and [the source-selection gate](docs/01_evidence_and_dataset_gate.md). The specified AWS IDC registry is not yet a verified source for the exact labelled patches.
3. Follow [the workflow setup guide](docs/00_ai_dlc_setup.md). Use the workshop-compatible v1.0.1 workflow in a fresh workspace, or explicitly choose the already-installed alternative. Do not mix workflows.
4. Paste [the Inception-only prompt](prompts/00_inception_only.md) into Kiro. It must investigate and ask questions before building or incurring charges.
5. Review the files Kiro generates under `aidlc-docs/`. Approve one gate at a time; then use the corresponding prompt in `prompts/`. Approval for planning is not approval for a paid job or deployment.

The steering file in this package is **project context only**, not a bundled replacement for the official AI-DLC rules. The package deliberately does not install dependencies, vendor external repositories, create agent swarms, or run hooks automatically.

## Reading map

| Document | What it decides |
|---|---|
| [Project brief](PROJECT_BRIEF.md) | Purpose, non-goals, success criteria, known facts and assumptions |
| [AI-DLC setup](docs/00_ai_dlc_setup.md) | Version choice, safe activation, human gates |
| [Evidence and data gate](docs/01_evidence_and_dataset_gate.md) | Exact dataset, licensing, patient mapping, import risks |
| [Model and evaluation](docs/02_model_and_evaluation_plan.md) | Baselines, leakage prevention, calibration, review selection |
| [Product and UX](docs/03_product_ux_and_acceptance.md) | Screens, interactions, numbered acceptance criteria |
| [Architecture and cost](docs/04_architecture_security_cost.md) | Local-first design, conditional AWS deployment, security |
| [Work units](docs/05_ai_dlc_and_work_units.md) | Bounded implementation tasks, interfaces, tests and gates |
| [Testing and release](docs/06_test_release_demo_plan.md) | Verification matrix, demonstration, export and teardown |
| [Sources and reuse](docs/07_sources_and_reuse_register.md) | Primary-source links, inspection limits, reuse decisions |
| [Contracts](docs/08_data_and_api_contracts.md) | Canonical labels, API responses, audit events |
| [Open questions](templates/requirement-verification-questions.md) | Questions Kiro cannot answer from local inspection |

## Workflow states

All gates start **UNAPPROVED**. All implementation and runtime verification tasks start **NOT EXECUTED**. Keep this distinction when reporting progress.

A useful next session ends with a source decision, an environment/permission report, a bounded budget proposal, and a requirements review—not an unreviewed application scaffold.

The user's workshop sources are identified in the source register. They are not copied into the ZIP, which avoids redistributing account-specific workshop text. Research findings are dated; Kiro must verify mutable access paths, versions, licensing, service permissions, and prices before using them.
