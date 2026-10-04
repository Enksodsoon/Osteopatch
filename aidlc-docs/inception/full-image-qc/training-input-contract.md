# OsteoPatch — Training Input Contract (post full-collection QC)

Generated: 2026-10-03T15:02:31.149416+00:00

## Canonical source
Future training consumes exactly ONE deterministic file: `full-image-qc-results.csv` (full 1,144-row manifest, this directory). No directory crawling; no fold folders.

## Eligibility rule (deterministic, already materialized)
A row is training-eligible iff:
1. `canonical_label` ∈ {NON_TUMOR, VIABLE_TUMOR, NECROSIS} (the 53 MIXED_VIABLE_NECROTIC rows are `training_eligible=false` ALWAYS), AND
2. `primary_qc_status == PASS` (REVIEW / NEAR_DUPLICATE_CANDIDATE / CORRUPT / RETRIEVAL_FAILED are excluded with their recorded status).

## Eligible counts (frozen by this gate)
- NON_TUMOR: 484
- VIABLE_TUMOR: 290
- NECROSIS: 254
- **Total eligible: 1028** / 1,144.

## Preprocessing (inherited, CONFIRMED on full collection)
- Input: 1024×1024 RGB 8-bit TIFF → resize to 384×384 (bilinear, antialias, no crop) → ImageNet normalization.

## Split protocol (unchanged)
- Case/slide-group independent LOGO over Case-3 / Case-4 / Case-48 / P9 (frozen G3). NEVER described as patient-independent. Duplicate members (none found) would inherit their group to prevent split leakage.

## Pending human review (do not silently resolve)
- 59 content-REVIEW rows + 4 near-dup candidates (see `human-review-queue.csv`). A human decision can later promote some to PASS; until then they stay excluded.

## Hard constraints
- PASS is a pixel-level QC verdict only — NOT clinical revalidation, NOT biological-sample independence, NOT patient-level independence, NOT clinical suitability.
