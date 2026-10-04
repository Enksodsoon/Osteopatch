# Model Card — OsteoPatch G4 Baseline (frozen-encoder MobileNetV3-Small)

**Status:** G4 executed baseline. Educational / research prototype. **NOT** a clinical
device. **NOT** patient-level validation, **NOT** diagnosis, **NOT** treatment-response,
**NOT** prognosis. Scores are **uncalibrated** model class scores, never disease
probabilities.

## Model
- **Architecture:** torchvision `mobilenet_v3_small`, ImageNet-pretrained
  (`MobileNet_V3_Small_Weights.IMAGENET1K_V1`), **encoder frozen** (requires_grad=False,
  BatchNorm in eval), a newly trained 3-output linear head (`Linear(1024 -> 3)`).
- **Canonical output order (fixed):** `[0]=NON_TUMOR, [1]=VIABLE_TUMOR, [2]=NECROSIS`.
- **Input / preprocessing:** RGB, full-field resize to 384×384 (bilinear, antialias,
  **no crop**), normalized with the pinned ImageNet mean `[0.485,0.456,0.406]` / std
  `[0.229,0.224,0.225]`. Train-only augmentation: hflip / vflip / 90°-multiple rotation only.
- **Training:** AdamW lr=1e-3, wd=1e-4, batch=16, ≤10 epochs, no early stopping
  (a-priori-frozen hyperparameters; the outer held-out group never informs tuning).
  Loss: cross-entropy with inverse-frequency, train-only class weights normalized to mean 1.
- **Seed:** 42 (one seed is not stability; multi-seed sensitivity is a future, approval-gated step).
- **Device:** CPU (CUDA unavailable in this environment; sanctioned fallback).
- **Calibration:** uncalibrated. No temperature scaling (G3 defines no leakage-safe
  calibration procedure at 4 groups).

## Data
- **Source / provenance:** Osteosarcoma-UT (PathDB / TCIA) H&E patch tiles; labels per the
  ratified owner policy (`aidlc-docs/inception/data/label_aliases.json`:
  Non-Tumor→NON_TUMOR, Viable→VIABLE_TUMOR, Non-Viable-Tumor→NECROSIS; `viable: non-viable`
  → MIXED_VIABLE_NECROTIC, excluded).
- **Three dataset-defined patch classes:** NON_TUMOR, VIABLE_TUMOR, NECROSIS. No 4th learned class.
- **Eligible cohort (frozen):** **1,028** patches — NON_TUMOR 484 / VIABLE_TUMOR 290 /
  NECROSIS 254. Training manifest SHA-256
  `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba`.
- **116 QC-held/excluded rows are unused:** 53 MIXED_VIABLE_NECROTIC + 59 content-REVIEW +
  4 near-duplicate candidates (pending human review; never silently resolved).
- **Grouping:** 4 recovered case/slide groups — Case-3, Case-4, Case-48, P9.

## Evaluation
- **Protocol:** Leave-One-Group-Out (LOGO), 4 folds. The held-out group is scored exactly
  once per fold by a model that never saw that group. **Case/slide-group-independent,
  exploratory** evaluation over 4 groups — patient-level independence is **unverified**.
- **Principal summary:** pooled out-of-fold (each of the 1,028 patches scored once).
  Reported together with the per-fold table (never the aggregate alone).
- **Pooled OOF (headline):** macro-F1 = **0.562** (3 classes), balanced accuracy = **0.626**,
  accuracy (secondary) = **0.670**, log loss = **1.195**, Brier = **0.496**.
- **Honest performance statement for the final all-data model:** the frozen LOGO OOF
  evaluation above, carried as an estimate with all limitations. The final model's own
  training-set fit is **not** an evaluation metric.

## Structural limitations (do not remove)
- **P9 fold is single-class (NON_TUMOR only):** VIABLE_TUMOR and NECROSIS have no test support
  there and their per-class metrics are **UNAVAILABLE / UNDEFINED**, never fabricated.
- **Sparse support:** Case-3 VIABLE_TUMOR test support = 3; Case-48 NECROSIS test support = 2 —
  those per-class reads are **indicative only (CI ≈ [0,1])**.
- **Only 4 groups** — too few for any generalization claim.
- **VIABLE_TUMOR is the weak class** in the pooled result (recall ≈ 0.11; most confusions are
  VIABLE→NECROSIS), consistent with a frozen ImageNet encoder that was never trained on
  pathology.
- **Patches are not independent biological samples;** no patch-as-patient bootstrapping.
- ImageNet accuracy of the backbone is **not** pathology performance.

## Artifacts
- Durable (git): `g4-training-manifest.csv`, `group-class-support.csv`,
  `majority-baseline-predictions.csv`, `oof-predictions.csv`, `per-fold-metrics.json`,
  `overall-oof-metrics.json`, `confusion-matrix.csv`, `run-configuration.json`,
  `fold-histories.json`, `fold-checkpoint-hashes.json`, `final-bundle.json`,
  `test-report.json`, `model-card-baseline.md`, `g4-summary.md`.
- Large weights (scratch, out of git, hashes recorded): 4 fold checkpoints + final bundle
  (`osteopatch_g4_baseline_bundle.pt`, SHA-256
  `01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63`).
