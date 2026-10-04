# Project brief — OsteoPatch Review

**Proposed working name:** OsteoPatch Review. Naming is not a product claim.
**Owner's intent:** a working educational AI application, built with Kiro and deployed within limited AWS hackathon access.

## User-supplied problem

Synthesized pain point, not a quotation from a real interview:

> ภาพเนื้อเยื่อมะเร็งกระดูกมีหลายภาพ อยากเห็นอย่างรวดเร็วว่าภาพไหนน่าจะเป็นเนื้อเยื่อประเภทไหน และภาพไหนที่ต้องให้ผู้เชี่ยวชาญตรวจทานก่อน

Build an educational prototype that opens osteosarcoma histology patches, suggests one of three tissue categories, shows model scores and qualified explanations, prioritizes uncertain images for human review, and records corrections.

## Fixed scope

Three model classes, in this explicit canonical order:

| Index | Machine label | Display label |
|---|---|---|
| 0 | `NON_TUMOR` | ไม่ใช่เนื้องอก / Non-tumor |
| 1 | `VIABLE_TUMOR` | เนื้องอกที่ยังมีชีวิต / Viable tumor |
| 2 | `NECROSIS` | เนื้อตาย / Necrosis |

Uncertain, mixed, poor-quality, and deferred are **review/quality states**, not a fourth learned tissue class. Source terminology and aliases must be checked before importing labels.

The end-to-end workflow is:

**Browse patches → inspect model scores → open uncertain image → compare original and attribution → accept/change/defer → save → inspect history/export.**

## Non-goals

No clinical diagnosis; no ruling out cancer; no prognosis; no patient-level treatment-response prediction; no treatment recommendation; no patient-level necrosis percentage. No WSI segmentation, survival modelling, automatic report generation, hospital/PACS integration, or arbitrary patient upload in the first release. Human corrections do not automatically retrain the deployed model.

## Intended users and assumptions

The proposed audience is students and a supervising pathology reviewer. A first version supports a curated public dataset, one project, and a small invited review team. Desktop is primary; essential review controls remain usable on a tablet. Bilingual class labels are proposed; the rest of the interface can begin in English pending owner preference.

These are proposed defaults, not facts supplied by the owner. Kiro should ask only when the answer changes scope, safety, architecture, judging compliance, or cost.

## Definition of a complete prototype

- A real, reproducible trained model consumes image pixels and produces three outputs.
- Its evaluation uses a declared split and reports limitations; no invented accuracy claim is required to pass a software gate.
- A reviewer can browse, run or retrieve a clearly labelled real prediction, review an image, and save a correction that survives reload.
- Uncertainty ordering, attribution, provenance, and correction history are visible and testable.
- An approved AWS environment runs the chosen deployment, or a clearly documented permission blocker is reported while the local workflow remains usable.
- Source, model, configuration, evaluation, review exports and deployment instructions are portable before workshop access expires.

A model that cannot outperform an appropriate baseline must be labelled as unsuccessful at reliable classification, even if the software demonstration works. Do not disguise a weak model with cached success examples.

## Known constraints and unresolved approvals

The owner supplied the AWS NCI Imaging Data Commons registry and workshop AI-DLC materials. The workshop snapshot shows `us-east-1`, but the active permitted region must be verified. No exact budget, service allowance, deadline, access expiration, hardware capacity, or rubric was supplied. A captured countdown is not a current expiration time.

**No paid resource or external paid API is authorized by this package.** Kiro must distinguish its own credit allowance from AWS service charges. Do not purchase more credits or change to another account automatically.

## Required visible disclaimer

English: **Educational research prototype only. Not for diagnosis, treatment decisions, or predicting treatment response.**

Thai: **ต้นแบบเพื่อการเรียนรู้และการวิจัยเท่านั้น ไม่ใช้วินิจฉัย ตัดสินใจรักษา หรือทำนายผลการรักษา**

Use on the workbench, model card and exports. Avoid naming the application a diagnostic system.
