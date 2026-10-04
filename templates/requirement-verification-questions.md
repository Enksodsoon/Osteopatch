# Requirement-verification questions — template

**Status:** unanswered items below are not approvals. Kiro copies/adapts this into the actual AI-DLC requirements directory, retaining answers already supplied and adding only necessary questions.

## Established by the owner — do not ask again

Educational osteosarcoma patch review; three tissue classes; model scores and explanations; uncertain-image queue; human corrections; actual model, UI/UX and deployment; Kiro; limited AWS hackathon access; no clinical diagnosis or treatment-response prediction. The intended source link is the AWS NCI IDC registry. The supplied workshop targets AI-DLC v1.0.1.

## Inspect before asking

Kiro should inspect relevant local OS/tool versions, workspace state, installed AI-DLC workflow, available memory/GPU/disk, active authorized AWS identity/region, and visible service constraints. Never expose credentials or assume create permission from read access. Record “not verifiable” instead of inventing a value.

## Q1 — Dataset provenance rule (blocking source selection)

Must the actual images and labels come from the specified AWS IDC dataset, or is the exact-match TCIA collection acceptable if the application is deployed on AWS?

Choices: A — IDC/AWS source mandatory. B — TCIA direct acceptable after license/provenance checks. C — Organizer's rule unclear; verify the rubric first.

Recommended decision: establish the organizer's rule. Do not treat B as accepted merely because it is convenient.

[Answer]: UNANSWERED

## Q2 — Deadline and account expiration (blocking operations planning)

What are the submission/demo deadline and the exact expiration of AWS/workshop access? Use full date/time and timezone, preferably Asia/Bangkok. A captured countdown is not enough. Does the deployed URL need to remain available after the event?

[Answer]: UNANSWERED

## Q3 — Authorized spending and service allowance (blocking cloud mutation)

What AWS credits remain, what maximum charge is authorized, and is personal out-of-pocket spending prohibited? Are there specific permitted/forbidden services or roles? What Kiro credit balance/limit should constrain agent use?

Default until answered: no new paid resources, paid APIs, credit purchases or account switching. Read-only inspection and local planning do not authorize a training/deployment bill.

[Answer]: UNANSWERED

## Q4 — Hackathon rubric (may change architecture)

Does the rubric require Bedrock/generative AI, a specific AWS service, a specific data source, a public live URL, a minimum evaluation deliverable, or a particular presentation format?

Recommended default: do not add a paid LLM solely for decoration. The actual image classifier and review workflow should remain the core unless the rubric requires an additional capability.

[Answer]: UNANSWERED

## Q5 — Reviewers and UI language

Who will review the prototype: only the owner, students, or a small invited expert team? Is a pathology expert available to review teaching language and a small failure sample? Prefer mostly English, mostly Thai, or bilingual UI?

Recommended default: small invited team, desktop-first, bilingual class labels, English technical UI. Label student edits separately from expert adjudications.

[Answer]: UNANSWERED

## Q6 — Data input and public exposure

Is the curated public dataset sufficient for the first demo, or is arbitrary upload explicitly required? Should the public website expose only the application shell/public teaching assets, with review APIs restricted to invited users?

Recommended default: curated images only; invited reviewers; no patient uploads and no unauthenticated write endpoint. Upload support is a separate scope/security decision.

[Answer]: UNANSWERED

## Record the result

For every accepted default, record who accepted it and when. For an unanswered blocking question, complete independent planning and stop only the affected execution step. Do not convert silence into consent.
