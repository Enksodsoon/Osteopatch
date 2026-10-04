# Model Card Addendum — G5 Last-Stage Fine-Tune Variant (`laststage-finetuned-g5`)

This addendum extends the G4 baseline model card (`g4/model-card-baseline.md`). It documents the G5 experiment only; **it does not change the current default model.**

## Version & status
- **Variant name:** `laststage-finetuned-g5` (distinct from `baseline-frozen-g4`).
- **Status:** experimental, evaluated, **NOT adopted**. Result = **NO BENEFIT**.
- **Current prototype default remains `baseline-frozen-g4`.** No final all-data G5 bundle was built; no "improved" replacement exists.
- **Calibration status:** uncalibrated (not reached — no bundle).

## What differs from G4
Identical data cohort (1,028 eligible / 4 LOGO groups / class order `[NON_TUMOR, VIABLE_TUMOR, NECROSIS]`), preprocessing (384² full-field, pinned ImageNet norm), D4 train-only aug, per-fold inverse-freq train-only weighted CE, and seed (42). The single change: unfreeze **only** the final MobileNetV3-Small feature stage (`features[12]`) + the classifier head (650,371 trainable params / 7 tensors; all earlier stages frozen, 870,560 params). Discriminative AdamW LRs (final-stage 1e-5, head 1e-4), wd 1e-4, batch 16, 5 epochs, no early stop, no sweep. BN kept in frozen-stat eval mode throughout.

## Evaluation (LOGO out-of-fold, same protocol as G4)
Pooled macro-F1 **0.5229** (G4 0.5623, Δ −0.0394); VIABLE_TUMOR recall **0.0448** (G4 0.1103, Δ −0.0655); VIABLE_TUMOR F1 **0.0751** (G4 0.1793, Δ −0.1041); NON_TUMOR F1 0.7903 (Δ −0.0517); NECROSIS F1 0.7033 (Δ +0.0376); Brier 0.5524 (Δ +0.0563, worse). VIABLE→NECROSIS confusions fell 153→116 but VIABLE→NON_TUMOR rose 105→161 and VIABLE correct fell 32→13 — a relocation of error, not improved discrimination.

## Honest-performance statement
As with G4, honest performance is the LOGO OOF evaluation carried with all limitations; the model's own training fit is not an evaluation metric (G5 training loss fell monotonically while held-out performance worsened — last-stage overfitting on a 4-group cohort). The VIABLE_TUMOR ceiling is driven by data scope (viable concentrated in Case-4/Case-48 across only 4 slide groups), not by last-stage capacity.

## Intended use & limitations
Unchanged from G4: educational / research prototype only; NOT patient-level, NOT diagnosis, NOT treatment-response, NOT prognosis; exploratory case/slide-group-independent patch classification over 4 groups; patient-level independence unverified; patches are not independent biological samples; scores are uncalibrated model class scores, not disease probabilities; P9 fold is single-class so VIABLE/NECROSIS are UNAVAILABLE there.

## Provenance
Full detail: `g5/g5-summary.md`, `g5/run-configuration.json`, `g5/test-report.json`, `g5/g4-vs-g5-metric-comparison.json`, `g5/g4-vs-g5-confusion-comparison.json`, `g5/viable-to-necrosis-error-comparison.json`, `g5/g4-vs-g5-fold-comparison.json`. Reused G4 manifest SHA-256 `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba` (re-hash verified).
