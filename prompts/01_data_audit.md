Using AI-DLC, continue only U1 of docs/05_ai_dlc_and_work_units.md. Read the actual state/audit and confirm G0/G1 explicitly approve the exact source and access. If not, stop the affected step and present the missing approval; do not substitute a dataset.

Review the unit code-generation plan before coding. Implement strict labelled-image ingestion and a documented patient/duplicate audit against the approved source. Unknown labels, missing matches and collisions must fail; no fallback to Viable. Verify patient identifiers rather than copying research filename assumptions. Do not use folder names as a train/test split.

Run the data tests and real audit, produce the dataset card and immutable manifest/split hashes, and present G2 for approval. Report actual counts/exclusions/class support. Do not train a model in this unit. Record exact commands and outcomes, commit the bounded changes, update state/audit, then stop.
