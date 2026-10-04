---
inclusion: always
---
# OsteoPatch project steering

Read `PROJECT_BRIEF.md` and the current `aidlc-docs/aidlc-state.md` before acting. This is a proposed educational three-class histology patch-review application, not a clinical device. Canonical class order is `NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`. Unknown source labels must raise an error; never guess a class.

Use one AI-DLC controller. The user's workshop targets v1.0.1; do not mix its steering rules with native Kiro Specs or a different AI-DLC installation without an explicit decision. This file is project context, not the official workflow.

First run is Inception only. The exact TCIA dataset's presence in the requested AWS IDC source is unverified. Resolve provenance and ask before changing the data source. Do not download a whole bucket or infer patient IDs from unverified filename patterns.

No training, installation requiring charges, cloud mutation, public sharing, paid API, account switching, or deployment before the relevant approval. Do not trust all tools on a sensitive machine. Inspect only relevant workspace files and authorized read-only cloud information; never print credentials.

Split at patient level when verifiable. Keep source labels, model predictions, and review events separate. No label leakage, automatic online retraining, fake metrics, fabricated heatmaps, or patient-level necrosis/treatment claims. An uncertainty flag is not clinical urgency, and a heatmap is not segmentation or a causal explanation.

Use bounded units, small experiments, tests and evidence. Load detailed documents only when needed. Do not launch unbounded agent teams or repetitive hooks. Record questions, answers, approvals, command results, limitations and resume instructions in `aidlc-docs/`. A proposal is not approval; a test plan is not a passed test.
