# Dataset card — Osteosarcoma Tumor Assessment

**Dataset version:** `v2` (G2 ratified labels). **v1** was the U1 CSV/metadata audit with two labels left fail-closed/unresolved; v2 applies the ratified owner label policy. **Images still NOT downloaded** — image-level fields (SHA-256, verified dimensions, perceptual duplicates) remain PENDING (`image-ingestion-plan.md`).

**Status:** G2 offline/deterministic complete. Verdict **PASS WITH LIMITATIONS** (`g2-validation-report.md`). No pixels, no network, no AWS.

## Version history
- **v1 (U1, 2026-10-03):** CSV audited (1,144×69, SHA-256 `96fc6f37…81f6`); PathDB 1,144/1,144 join; labels `Non-Viable-Tumor`(263) and `viable: non-viable`(53) left UNRESOLVED pending owner ratification.
- **v2 (G2, 2026-10-03):** ratified policy applied — `Non-Viable-Tumor`→NECROSIS (trainable); `viable: non-viable`→review_state MIXED_VIABLE_NECROTIC (trainable=false, excluded from 3-class, retained). Primary classes NON_TUMOR/VIABLE_TUMOR/NECROSIS; no 4th learned class. Built `canonical_manifest.csv`, `group_class_distribution.csv`, `split-proposal.md`, `mixed-patch-policy.md`, `image-ingestion-plan.md`, `g2-validation-report.md`.

## Identity and rights
| Field | Value |
|---|---|
| Source collection | TCIA **Osteosarcoma-Tumor-Assessment** |
| Dataset DOI | `10.7937/tcia.2019.bvhjhdas` |
| CSV source URL | https://www.cancerimagingarchive.net/wp-content/uploads/ML_Features_1144.csv (official, no mirror) |
| CSV retrieved (UTC) | 2026-10-03T08:40:11Z |
| CSV HTTP status | 200 · content-type `text/csv` |
| CSV bytes | **880,995** |
| CSV SHA-256 | `96fc6f3789a4ae14d536057d7db8b1353d20b0b2b94ce54b80e58ef5120281f6` |
| PathDB collection | `Osteosarcoma-Tumor-Assessment` collectionId **18** (updated 2023-12-01) |
| Image objects (PathDB) | 1,144 `.tiff` converted WSI tiles over plain **HTTP** |
| License | CC BY 3.0 — attribution + data citation required (published; re-confirm at image fetch) |
| Access route verified | CSV = plain HTTPS (done). Images = PathDB plain-HTTP object GET (one probe done) **or** Aspera Faspex package 752 (not executed) |

## Population and data unit
- **Data unit:** 1,144 patch images, 1024 × 1024 px (PathDB reports 1024×1024 for all 1,144 rows), ~10× magnification (published).
- **Published cohort:** 4 selected patients. The CSV filenames and PathDB subjectIds resolve to **exactly 4 group tokens** (`Case 3`, `Case 4`, `Case 48` [internally `P5`], `P9`), consistent with 4 patients — but **subjectId in PathDB is a per-patch id, not a biological patient id** (1,144 distinct subjectIds). See `patient_mapping_evidence.md` for confidence/limits.
- Annotation: predominant class per patch; one annotator per image across two experts (published; not independently re-verified here).

## Actual audit (CSV)
- Rows 1,144 · columns 69 · classification column = `classification`.
- Raw label vocabulary (4 distinct): `Non-Tumor` 536 · `Viable` 292 · `Non-Viable-Tumor` 263 · `viable: non-viable` 53.
- Canonical (resolved, fail-closed): NON_TUMOR 536. **Two raw strings left UNRESOLVED** pending owner ratification (see label mapping below).
- 0 duplicate filenames; 0 nulls/blanks in `classification` or `image.name`; no dedicated patient/case/subject/slide/group **column** exists (grouping is encoded in the filename only).
- Image SHA-256 / corrupt-file / perceptual-duplicate checks: **PENDING** (no images downloaded).

## Label mapping (see `label_aliases.json` — RATIFIED v2)
| Raw string | Count | Canonical / review_state | Trainable | Basis |
|---|---|---|---|---|
| `Non-Tumor` | 536 | NON_TUMOR | yes | direct, matches published 536 |
| `Viable` | 292 | VIABLE_TUMOR | yes | direct |
| `Non-Viable-Tumor` | 263 | **NECROSIS** | yes | ratified: non-viable tumor == necrosis; count matches published Necrosis 263 |
| `viable: non-viable` | 53 | **MIXED_VIABLE_NECROTIC** (review_state) | **no** | ratified: mixed patch, excluded from 3-class, retained in manifest; no 4th learned class |

**Canonical counts (trainable, after ratified map):** NON_TUMOR 536 · VIABLE_TUMOR 292 · NECROSIS 263 = **1,091 trainable** + 53 MIXED excluded = **1,144**. Reconciles to published (536 / 345 = 292+53 / 263) and to the 1,144 total.

## Splits and permitted uses
- `Training_Set_1` / `Training_Set_2` folder names appear in PathDB imageUrls (`.../Training-Set-1/set*`, `.../Training-Set-2/set*`) but **must not** be treated as a validated ML split (per doc 01).
- No split proposed yet — requires the actual patient × class table and a defensible grouping decision at G2.
- **G2 split decided (v2):** Leave-One-Group-Out grouped CV over the 4 case/slide tokens; no random patch split; see `split-proposal.md`. Independent 3-way train/val/test is NOT possible (4 groups, P9 single-class) → evaluation is exploratory grouped CV.
- Educational scope only; no clinical/patient-level response claims.

## Changes
No derivative transforms applied. Original label strings preserved verbatim in `manifest.csv.source_label`.
