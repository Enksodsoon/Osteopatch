# Requirement-verification questions — OsteoPatch Review (Inception)

**How to use:** fill each `[Answer]:` and save. Unanswered items are **not** approvals and never become consent by silence. Established facts below are prefilled so you do not re-answer them. Only genuinely unresolved items that change scope/safety/architecture/compliance/cost are asked.

---

## Established by the owner / verified locally — DO NOT re-ask

- Educational osteosarcoma patch review; three fixed tissue classes (`NON_TUMOR`, `VIABLE_TUMOR`, `NECROSIS`); model scores + explanations; uncertain-image queue; human corrections; a real model + UI/UX + deployment; built with Kiro; limited AWS hackathon access; **no** clinical diagnosis or treatment-response prediction.
- Intended source link = AWS NCI IDC registry (membership of the exact labelled collection is unverified — see Q1).
- Workshop targets AI-DLC **v1.0.1**.
- **Local environment (verified this run):** Windows 11, 12 CPUs, 31.8 GB RAM, 75.3 GB free disk, NVIDIA Quadro P2000 (~5 GB VRAM, CUDA-capable), Python 3.12.10, Node 24, Git, Docker CLI (daemon stopped). AWS CLI / SAM / torch **not installed**; no `~/.aws` config; no AWS credentials present.

---

## Q1 — Dataset provenance rule (BLOCKS source selection, G1)

Must the actual images **and labels** come from the specified AWS IDC dataset, or is the exact-match TCIA collection acceptable if the app is deployed on AWS?

- **A** — IDC/AWS source mandatory.
- **B** — TCIA direct acceptable after license/provenance checks.
- **C** — Organizer rule unclear; verify rubric (Q4) first.

**[Answer]:** **B — TCIA direct**, approved by Enk 2026-10-03, for the **local educational prototype + data audit only**. Explicit change from IDC-first; does **not** establish hackathon eligibility; TCIA must never be described as an IDC/AWS Open Data download.

---

## Q2 — Deadline and access expiration (BLOCKS operations planning)

**[Answer]:** **Deferred (unknown).** Do not invent a deadline from an old countdown. Does not block local audit. — Enk, 2026-10-03

---

## Q3 — Authorized spending & service allowance (BLOCKS cloud mutation)

- Remaining AWS credits? Maximum authorized charge? Is personal out-of-pocket spend prohibited?
- Specific permitted/forbidden AWS services or IAM roles?
- Kiro credit balance/limit that should bound agent use?

**[Answer]:** **No additional AWS/cloud spend authorized.** Use existing Kiro allowance; no credit purchase, plan upgrade, or account switch. Local CPU-only work only. — Enk, 2026-10-03

---

## Q4 — Hackathon rubric (may change architecture)

Does the rubric require: Bedrock/generative AI, a specific AWS service, a specific data source, a public live URL, a minimum evaluation deliverable, or a particular presentation format?

**[Answer]:** **Unverified / deferred.** Do not invent mandatory AWS services or claim competition compliance. — Enk, 2026-10-03

---

## Q5 — Reviewers & UI language

Who reviews the prototype — owner only, students, or a small invited expert team? Is a pathology expert available to vet teaching language + a small failure sample? UI language preference: mostly English, mostly Thai, or bilingual?

**[Answer]:** Working default accepted: **one local reviewer (Enk); Thai interface wording with English pathology terms.** UI work deferred to later units. — Enk, 2026-10-03

---

## Q6 — Data input & public exposure

Is the curated public dataset enough for the first demo, or is arbitrary upload explicitly required? Should the public site expose only the app shell/public teaching assets, with review APIs restricted to invited users?

**[Answer]:** **Curated public dataset only.** No hospital uploads, no patient information, no public server, no public upload endpoint. — Enk, 2026-10-03

---

## Q7 — AWS access for verification (NEW — needed to unblock G1/G6)

The only object-level way to confirm the IDC collection, and the only way to inspect your real account/region/permissions, is through the AWS CLI — which is **not installed** here, and no credentials are configured. How do you want to proceed?

- **i** — You install AWS CLI and run `aws configure` / `aws sso login` with the workshop credentials in your own terminal, then I use `--profile <name>` for read-only checks.
- **ii** — You run the two no-credential/read-only checks yourself and paste the output: `aws s3 ls --no-sign-request s3://idc-open-data/` (needs AWS CLI) and/or the `idc-index` query for `Osteosarcoma-Tumor-Assessment`.
- **iii** — Proceed with the local-only vertical slice now and defer all AWS checks (cloud stays blocked).

**[Answer]:** **Deferred.** Do not request workshop credentials for public-source discovery; never ask the owner to paste secrets. Public IDC discovery proceeds credential-free via `idc-index`. Workshop-account verification deferred with cloud work. — Enk, 2026-10-03

---

## Recording
For every accepted default, record who accepted it and when (use `templates/decision-and-approval-log.md`). For an unanswered blocking question, independent planning continues but the affected execution step stays stopped.
