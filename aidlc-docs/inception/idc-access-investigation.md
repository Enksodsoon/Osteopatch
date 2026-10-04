# IDC direct-access investigation (credential-free) — U1

**Date:** 2026-10-03 · **Method:** official `idc-index` Python client v0.12.5, IDC release **v24**, anonymous (no AWS credentials, no bulk download). Run in an isolated scratch venv; nothing stored under the project or on persistent local data storage.

**Purpose:** the cloud-first pivot (D9) asks whether the exact project data can be used *directly* from IDC's public AWS S3 (`idc-open-data*`, us-east-1, `--no-sign-request`). The four questions are kept strictly separate; 2–4 are NOT inferred from a related collection.

---

## What was queried
- Full IDC main index: **1,032,911 series rows**, **176 collections**.
- Slide-microscopy index (`sm_index`): **76,299 rows**, **73 SM collections**.
- Searched by: collection_id substrings (`osteosarcoma`, `sarcoma`, `osteo`, `tumor-assessment`), the collection **DOI** (`10.7937/tcia.2019.bvhjhdas` → token `bvhjhdas`), and `BodyPartExamined = BONE`.

## Verified findings
| Question | Result | Evidence |
|---|---|---|
| 1. Osteosarcoma collection in IDC? | **NO** | 0 matches by name/DOI; `BodyPartExamined=BONE` → 0 rows. Only osteo/sarcoma/bone-adjacent collections are `bonemarrowwsi_pediatricleukemia` (pediatric leukemia) and `soft_tissue_sarcoma` (soft-tissue sarcoma) — **different diseases**, not osteosarcoma tumor-tissue tiles. |
| 2. Exact 1,144 labelled patches / equivalent objects in IDC? | **NO** | Follows from (1); DOI `bvhjhdas` returns 0 series. |
| 3. Three-class labels (Non-Tumor/Viable/Necrosis) in IDC? | **NO** | Follows from (1). |
| 4. Reliable patient/group mapping in IDC? | **NO** | Follows from (1). |

**Conclusion:** the exact labelled osteosarcoma patch dataset is **not present in IDC** (release v24). **Direct IDC S3 operation is not possible** for this project's data. This is an evidence-based absence for *this collection* at *this release*, not a claim that IDC is unsuitable generally. Note separately: even where IDC hosts pathology, it stores **DICOM Slide Microscopy (`.dcm` pyramids)**, not the TCIA-style labelled 1024×1024 JPG patches + three-class CSV — so an IDC object would not be a drop-in equivalent even if present.

---

## Consequence for the cloud-first plan
The "operate directly against IDC objects" branch of D9 is **closed by evidence**. The remaining cloud-first route is **TCIA → project S3 (us-east-1)**. See `architecture-proposal.md` §Cloud-first for the two blockers on that route (TCIA Aspera-only access; no AWS access configured on this host).

## Reproducibility
- Package: `idc-index==0.12.5` (IDC data release `v24`).
- Isolated venv: `%KIROCREW_SCRATCH%\osteopatch-idc-venv` (disposable, not under project, not committed).
- No credentials used; no objects downloaded; metadata index only.
