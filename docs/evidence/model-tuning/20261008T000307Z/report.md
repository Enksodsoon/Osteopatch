# OsteoPatch model tuning report

Run: `20261008T000307Z`
Status: **FAILED**
Device: `cpu`; elapsed: 1445s / 14400s
Eligible images: 1028 / 1144; four slide/case groups; patient independence unverified.
Qualification: **NOT_QUALIFIED** — campaign incomplete

All scores are uncalibrated research outputs. This evaluation does not establish patient-level or clinical performance.

Historical G4 is descriptive only: macro-F1 **0.5623**, viable-tumor recall **0.1103**.

Handoff evidence reports G5 regressed both metrics; exact G5 values are unavailable, so no numeric comparison is made.

## Per-seed out-of-fold metrics

| Seed | Candidate macro-F1 | Candidate viable recall | Comparator macro-F1 | Comparator viable recall |
|---:|---:|---:|---:|---:|

## Outer-fold group results

| Seed | Held-out group | Candidate macro-F1 | Candidate viable recall | Comparator macro-F1 | Comparator viable recall |
|---:|---|---:|---:|---:|---:|
| 42 | Case-3 | 0.5698744545365523 | 0.3333333333333333 | 0.5819978577511483 | 0.3333333333333333 |
| 42 | Case-4 | 0.712646334545267 | 0.5294117647058824 | 0.6656385288730755 | 0.38823529411764707 |
| 42 | Case-48 | 0.29367666181766616 | 0.09405940594059406 | 0.28801284229418783 | 0.06435643564356436 |

## Per-class support and metrics

Fold-level confusion matrices, per-class precision/recall/F1/support, balanced accuracy, log loss, and Brier score are in `run-report.json`. Undefined metrics are `null` when a held-out group lacks that class.

## Failed or incomplete experiments

| Configuration | Seed | Status | Epochs completed | Detail |
|---|---:|---|---:|---|
| None | | | | |

## Reproduction

`uv run --locked --extra dev --extra model python scripts/model_tuning.py --image-root "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\images" --pretrained-weights "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\models\torch-hub\hub\checkpoints\mobilenet_v3_small-047dcff4.pth" --manifest "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\wt\model-tuning\aidlc-docs\inception\full-image-qc\full-image-qc-results.csv" --runtime-model-dir "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\models" --budget-hours 4.0 --seeds 42,43,44`

The exact environment, image and split hashes, fold selection metrics, epoch losses, parameter counts, checkpoint hashes, timings, hardware, and failure details are in `run-report.json`. `oof-predictions.csv`, `error-review.csv`, and `excluded-images.csv` contain the completed prediction and review exports.
