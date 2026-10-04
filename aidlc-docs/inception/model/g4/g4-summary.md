# G4 — Local LOGO Baseline Training — Summary

**Executed:** 2026-10-03. Device **CPU**. Seed **42**. One focused run, autonomous,
no new agents, no AWS, no re-download, no Image-QC rerun.

## 1. Device & environment
CPU (torch 2.14.1+cpu; `torch.cuda.is_available()==false`; sanctioned CPU fallback, no
second CUDA stack attempted). Python 3.12.10, torchvision 0.29.1+cpu, numpy 2.5.3,
scikit-learn 1.9.1, Pillow 12.3.0. Pinned weights `MobileNet_V3_Small_Weights.IMAGENET1K_V1`.

## 2. Training manifest (frozen BEFORE training)
`g4-training-manifest.csv` — SHA-256 `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba`.
Eligible **1,028**: NON_TUMOR 484 / VIABLE_TUMOR 290 / NECROSIS 254. 116 held/excluded unused.

## 3. Group × class support (post-QC)
| Group | NON_TUMOR | VIABLE_TUMOR | NECROSIS | total |
|---|---|---|---|---|
| Case-3 | 95 | 3 | 166 | 264 |
| Case-4 | 72 | 85 | 86 | 243 |
| Case-48 | 126 | 202 | 2 | 330 |
| P9 | 191 | 0 | 0 | 191 |
| **TOTAL** | **484** | **290** | **254** | **1028** |

## 4. Pre-training tests
14/14 tests PASS, 0 hard failures (`test-report.json`). Covered: canonical class order;
only-eligible rows; MIXED/REVIEW/near-dup excluded; train≠eval transforms; eval matches the
384×384 inference contract; LOGO no-group-leakage; each image outer-test exactly once; no
cross-group-leakage flags; fold weights from training rows only; 3 finite logits; probs
finite & sum to 1; encoder frozen / head trainable; absent-class marked UNAVAILABLE.

## 5. Majority baseline (per fold, from TRAINING groups only)
Majority class = **NON_TUMOR** for all 4 folds. Pooled majority: accuracy 0.471, macro-F1 0.213.

## 6. Per-fold LOGO results (neural)
| Fold (held out) | n | present classes | macro-F1 (n cls) | bal.acc | acc | log loss | Brier | notes |
|---|---|---|---|---|---|---|---|---|
| Case-3 | 264 | 3 | 0.589 (3) | 0.645 | 0.807 | 0.501 | 0.280 | VIABLE support=3 → indicative only |
| Case-4 | 243 | 3 | 0.614 (3) | 0.659 | 0.650 | 0.824 | 0.471 | only fold with all 3 at usable support |
| Case-48 | 330 | 3 | 0.281 (3) | 0.658 | 0.391 | 2.685 | 0.965 | NECROSIS support=2 → indicative only |
| P9 | 191 | 1 | 0.995 (1) | 0.990 | 0.990 | 0.050 | 0.016 | DEGENERATE: NON_TUMOR only; VIABLE/NECROSIS UNAVAILABLE |

Per-class metrics for a class absent from a fold's test are **UNAVAILABLE** (never 0/1).
Full detail in `per-fold-metrics.json`.

## 7. Combined pooled OOF (headline; each image scored once)
- **macro-F1 = 0.562 (3 classes)**, balanced accuracy = 0.626, accuracy (secondary) = 0.670,
  multiclass log loss = 1.195, multiclass Brier = 0.496.
- Per-class (support): NON_TUMOR P0.789/R0.903/F0.842 (484); VIABLE_TUMOR P0.478/R0.110/F0.179
  (290); NECROSIS P0.541/R0.866/F0.666 (254).

### Confusion matrix (pooled, counts; rows=true, cols=pred)
| true \ pred | NON_TUMOR | VIABLE_TUMOR | NECROSIS |
|---|---|---|---|
| NON_TUMOR | 437 | 13 | 34 |
| VIABLE_TUMOR | 105 | 32 | 153 |
| NECROSIS | 12 | 22 | 220 |

Neural vs majority (descriptive): macro-F1 0.562 vs 0.213; accuracy 0.670 vs 0.471.
The dominant error is VIABLE_TUMOR→NECROSIS (153) — the frozen ImageNet encoder separates
viable tumor from necrosis poorly.

## 8. Training time
Embedding precompute (1,028 imgs × 8 D4 views, once): ~a few minutes (cached).
Head training per fold: Case-3 0.55s, Case-4 0.56s, Case-48 0.68s, P9 0.75s. LOGO total 2.55s.
Final all-data head: 0.86s. (Cost is dominated by the one-time frozen-encoder embedding pass.)

## 9. OOM / retry / fallback
None. CPU run; batch 16 held throughout; no batch-size reduction; CUDA→CPU was the only
documented fallback.

## 10. Final prototype model (all 1,028 eligible)
Trained one frozen-encoder head on all eligible data. Bundle
`osteopatch_g4_baseline_bundle.pt` — SHA-256
`01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63` (scratch; out of git).
**Reload test PASSED**: fresh-load inference parity exact, outputs finite, probs sum to 1,
3 outputs. Calibration_status = uncalibrated. Honest performance = the LOGO OOF above, NOT
this model's own training fit.

## 11. Frozen-contract deviations
None of substance. One documented implementation reformulation: the permitted train-only
aug (hflip/vflip/90-rot) is the D4 group (8 views); since the encoder is frozen, the 8
per-image view embeddings were precomputed once and the head trained on a random view per
image per epoch — mathematically identical to augmenting pixels through the frozen encoder,
far cheaper on CPU. Eval uses the identity view. See `run-configuration.json`.

## 12. Scientific limitations
Exploratory case/slide-group independence over 4 groups only; patient-level independence
unverified. P9 single-class; Case-3 VIABLE=3 / Case-48 NECROSIS=2 indicative-only; patches
not independent biological samples; uncalibrated scores; ImageNet backbone ≠ pathology model.

## 13. Recommendation for the next construction unit
Review these results, then (approval-gated) consider: (a) a short low-LR fine-tune of the
last feature stage as a separate run record to address the VIABLE/NECROSIS confusion;
(b) multi-seed sensitivity (3–5 seeds) to show the baseline is not a lucky draw;
(c) explicitly keep calibration/Grad-CAM/uncertainty/API/UI/AWS OUT until separately gated.
Do NOT treat the pooled macro-F1 as a generalization guarantee.
