# OsteoPatch tuning model card

Run: `20261008T014711Z`
Qualification: **NOT_QUALIFIED**
Qualified candidate: `none`
Final configuration: `frozen_inverse` (selected by four-group held-out validation)
Research artifact: `osteopatch-unqualified-20261008T014711Z` (not qualified, registered, or app-selectable)

## Intended use
Exploratory research comparison of three-class patch scoring on the verified OsteoPatch full-image QC dataset.

## Evaluation and data
1028 eligible images from four case/slide groups; 116 excluded images retained in the manifest. Patient independence is unverified.
Outer evaluation uses leave-one-group-out folds. Inner group-held-out predictions choose among the frozen-head comparator, a 2x viable-tumor loss-weighted head, and 2x weighted final-feature-stage fine-tuning.

## Performance and limitations
Per-seed and per-group metrics, including absent-class support, are in `report.md` and `run-report.json`. Scores are uncalibrated. Small group count and unverified patient independence limit generalization claims; this is not a clinical or diagnostic model.
The all-data research artifact follows group-held-out procedure selection; its fit is not an independent evaluation. The outer-fold results evaluate the training procedure.

Historical reference: G4 macro-F1 0.5623 and viable-tumor recall 0.1103. The handoff reports a G5 regression on both, without exact values.

Across the three seeds, mean viable-tumor recall improved by 1.61 percentage points, below the 5-point gate. Mean macro-F1 improved by 0.15 points; non-tumor recall changed by -0.48 points, while necrosis recall declined by 2.49 points and exceeded the allowed 2-point loss. Case-4 improved by 4.71 points and Case-48 by 0.33 points.

Two earlier attempts failed: the first hit an undefined-recall F1 calculation after 1,445.36 seconds; the second exhausted host CPU memory after 4,364.55 seconds at batch size 16. The completed batch-8 run finished all folds in 3,876.44 seconds. Full attempt details are in the dated report and schedule record.

The final group-held-out selection chose the fresh frozen-head comparator. Its all-data research bundle uses 1,028 eligible images, has 3,075 trainable parameters, and passed reload parity. Its SHA-256 is `a899e3108d6ea5cbf52cd5b6e99b1efb4127f99214440015b827cdcfe4a8acfa`; it is stored under `runtime-artifacts/models/unqualified/` and was not added to the qualified registry. No candidate was registered or exposed. The existing recovered model remains the live-analysis default.

## Qualification decision
3 seeds; mean viable recall +0.05; macro-F1 nondecreasing; other class recalls within -0.02; improvement in Case-4 and Case-48

## Provenance
Pretrained checkpoint SHA-256: `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f`.
Manifest SHA-256: `25c580a7c383bd7484038d13d581757604dc48c5eaba44d8d4a092efb3867360`; split SHA-256: `c87f3354eb266047c3d69ca1a574cd46cd30d93661e1309c89363f81342370b5`.
Full software, hardware, training, and artifact hashes are in `run-report.json`.
