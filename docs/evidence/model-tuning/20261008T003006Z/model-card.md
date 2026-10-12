# OsteoPatch tuning model card

Run: `20261008T003006Z`
Qualification: **NOT_QUALIFIED**
Model ID: `No candidate bundle`
Final configuration: `not selected`

## Intended use
Exploratory research comparison of three-class patch scoring on the verified OsteoPatch full-image QC dataset.

## Evaluation and data
1028 eligible images from four case/slide groups; 116 excluded images retained in the manifest. Patient independence is unverified.
Outer evaluation uses leave-one-group-out folds. Inner group-held-out predictions choose among the frozen-head comparator, a 2x viable-tumor loss-weighted head, and 2x weighted final-feature-stage fine-tuning.

## Performance and limitations
Per-seed and per-group metrics, including absent-class support, are in `report.md` and `run-report.json`. Scores are uncalibrated. Small group count and unverified patient independence limit generalization claims; this is not a clinical or diagnostic model.
If a candidate bundle exists, its all-data fit follows group-held-out procedure selection; its own fit is not an independent evaluation. The outer-fold results evaluate the training procedure.

Historical reference: G4 macro-F1 0.5623 and viable-tumor recall 0.1103. The handoff reports a G5 regression on both, without exact values.

## Qualification decision
campaign incomplete

## Provenance
Pretrained checkpoint SHA-256: `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`.
Manifest SHA-256: `25c580a7c383bd7484038d13d581757604dc48c5eaba44d8d4a092efb3867360`; split SHA-256: `c87f3354eb266047c3d69ca1a574cd46cd30d93661e1309c89363f81342370b5`.
Full software, hardware, training, and artifact hashes are in `run-report.json`.
