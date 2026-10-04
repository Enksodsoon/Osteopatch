# G5 — Bounded Last-Stage Encoder Fine-Tuning — Summary

**Status: EXPERIMENT COMPLETE → "G5 — FINE-TUNING REVIEW REQUIRED".**
**Result classification: NO BENEFIT.** G4 (`baseline-frozen-g4`) remains the prototype default. No final G5 bundle was created. All G4 artifacts are preserved unchanged.

This was ONE prespecified experiment: does unfreezing *only* the final MobileNetV3-Small feature stage (+ head) improve VIABLE_TUMOR discrimination without destroying NON_TUMOR/NECROSIS? It is not permission for architecture / augmentation / loss / hyperparameter search.

---

## 1. The one bounded change (trainable layers / param count)
Start = torchvision MobileNetV3-Small, `MobileNet_V3_Small_Weights.IMAGENET1K_V1`. Freeze all, replace the final linear with a fresh 3-output head, then unfreeze **only** the final feature stage + the classifier.

- **Final feature stage** = `features[12]` (highest-index module of `model.features`, which has 13 modules indexed 0–12): `Conv2dNormActivation(Conv2d(96→576,1×1,bias=False) + BatchNorm2d(576) + Hardswish)`.
- **Head** = `classifier` = `Linear(576→1024) · Hardswish · Dropout(0.2) · Linear(1024→3)`.
- **Trainable (7 tensors, 650,371 params):** `features.12.0.weight` (55,296), `features.12.1.weight` (576), `features.12.1.bias` (576), `classifier.0.weight` (589,824), `classifier.0.bias` (1,024), `classifier.3.weight` (3,072), `classifier.3.bias` (3).
- **Frozen:** 135 tensors / 870,560 params (feature modules 0–11, all with `requires_grad=False`).
- **Assertion (pre-run + per-fold):** explicit named-parameter check that EXACTLY `features.12.*` + `classifier.*` are trainable — `unexpected_trainable=[]`, `expected_but_frozen=[]`. PASS.
- **BatchNorm convention:** all BN kept in eval (frozen running stats) each epoch, including the unfrozen final stage's BN; its affine params remain trainable with gradients flowing through the fixed-stat normalization. Consistent with G3/G4 frozen-BN behavior (documented choice).

## 2. Device + runtime
CPU (torch 2.14.1+cpu; `cuda_available=false` — sanctioned fallback, no AWS). 6 threads / 12 CPUs. Base-tensor cache 21.9 s. Fold train+eval times: Case-3 89.2 s, Case-4 172.7 s, Case-48 271.8 s, P9 218.4 s; total 752.0 s (~12.5 min). No OOM; batch 16 stable.

## 3. Reused frozen G4 inputs (hashes)
- `g4/g4-training-manifest.csv` SHA-256 `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba` — **re-hashed at start, MATCH** (no hard stop). Same 1,028 cohort (NON 484 / VIABLE 290 / NECROSIS 254), 116 held/excluded.
- Same 4 LOGO groups (Case-3/Case-4/Case-48/P9), same split, class order `[NON_TUMOR, VIABLE_TUMOR, NECROSIS]`, same 384² full-field + pinned ImageNet norm, same D4 train-only aug, same per-fold inverse-freq train-only weighted CE, seed 42.
- Comparator (read-only): `g4/oof-predictions.csv`, `g4/overall-oof-metrics.json`, `g4/per-fold-metrics.json`.

## 4. Pre-run verification (15 hard tests, 0 failures)
manifest_hash_match · canonical_class_order · only_eligible_rows_load (1028) · exact_four_groups_and_support · logo_zero_outer_group_contamination (overlap 0 all folds) · each_image_outer_test_exactly_once (1028/1028) · fold_weights_training_only · train_eval_transforms_differ · eval_matches_inference_contract (3×384×384) · excluded_qc_rows_stay_excluded (0 leaked, cross-checked vs full-image-qc-results.csv) · no_cross_group_leakage_flag · model_three_finite_logits · probs_finite_sum_to_one · **only_finalstage_and_head_trainable** · absent_class_marked_unavailable. Full table: `g5/test-report.json`.

## 5. G4 pooled OOF (immutable baseline)
macro-F1 **0.5623**, bal-acc 0.6265, acc 0.6702, log-loss 1.1947, Brier 0.4961. Per-class F1: NON 0.8420, VIABLE 0.1793 (recall 0.1103), NECROSIS 0.6657.

## 6. G5 pooled OOF
macro-F1 **0.5229**, bal-acc 0.6009, acc 0.6430, log-loss 1.1993, Brier 0.5524. Per-class F1: NON 0.7903, VIABLE 0.0751 (recall 0.0448), NECROSIS 0.7033.

## 7. G4 → G5 deltas (every metric; + = G5 higher)
| metric | G4 | G5 | Δ |
|---|---|---|---|
| macro-F1 | 0.5623 | 0.5229 | **−0.0394** |
| balanced accuracy | 0.6265 | 0.6009 | −0.0255 |
| accuracy | 0.6702 | 0.6430 | −0.0272 |
| log-loss | 1.1947 | 1.1993 | +0.0046 (worse) |
| Brier | 0.4961 | 0.5524 | +0.0563 (worse) |
| NON_TUMOR F1 | 0.8420 | 0.7903 | −0.0517 |
| **VIABLE_TUMOR recall** | 0.1103 | 0.0448 | **−0.0655** |
| **VIABLE_TUMOR F1** | 0.1793 | 0.0751 | **−0.1041** |
| VIABLE_TUMOR precision | 0.4776 | 0.2321 | −0.2455 |
| NECROSIS F1 | 0.6657 | 0.7033 | +0.0376 |

## 8. G4 vs G5 pooled confusion matrices (rows=true, cols=pred, order NON/VIA/NEC)
```
G4                              G5                              Δ (G5 − G4)
NON  [437, 13,  34]             NON  [424, 17,  43]             [-13,  +4,  +9]
VIA  [105, 32, 153]             VIA  [161, 13, 116]             [+56, -19, -37]
NEC  [ 12, 22, 220]             NEC  [  4, 26, 224]             [ -8,  +4,  +4]
```

## 9. VIABLE_TUMOR recall / F1 change
Recall 0.1103 → 0.0448 (**−0.0655**); F1 0.1793 → 0.0751 (**−0.1041**). Both the primary targets moved the **wrong** way.

## 10. VIABLE → NECROSIS error count change
G4 **153/290** → G5 **116/290** (−37). But this did NOT become correct: VIABLE→NON_TUMOR rose 105 → **161** (+56) and VIABLE correct fell 32 → **13** (−19). Fine-tuning merely *relocated* viable's confusion from necrosis to non-tumor while reducing true positives. No net gain in viable discrimination.

## 11. Fold-by-fold comparison (macro-F1; VIABLE recall)
| fold | support (N/V/Nec) | G4 macro-F1 | G5 macro-F1 | Δ | G4 VIA recall | G5 VIA recall |
|---|---|---|---|---|---|---|
| Case-3 | 95/3/166 | 0.5893 | 0.5595 | −0.0298 | 0.333 (n=3) | 0.333 (n=3) |
| Case-4 | 72/85/86 | 0.6137 | 0.5468 | −0.0670 | 0.2353 | 0.0824 |
| Case-48 | 126/202/2 | 0.2808 | 0.2314 | −0.0494 | 0.0545 | 0.0248 |
| P9 | 191/0/0 | 0.9947 (1cls) | 1.0000 (1cls) | — | UNAVAILABLE | UNAVAILABLE |

Case-4 (the only well-balanced 3-class fold) and Case-48 (viable-heavy) both regress on VIABLE. P9's VIABLE/NECROSIS stay UNAVAILABLE (single-class, not manufactured). Case-3 VIABLE support=3 is indicative-only. Details: `g5/g4-vs-g5-fold-comparison.json`.

## 12. Failures / OOM / retries
None. No OOM, no batch-size reduction, no retries. Training loss fell monotonically every fold (e.g. Case-3 0.762→0.221), i.e. the model fit *training* data well but generalized worse to held-out groups — consistent with last-stage overfitting to case-specific features on a 4-group cohort. One benign `UserWarning` about `float(loss)` in the throughput probe only (the trainer uses `loss.item()`).

## 13. Decision: NO BENEFIT (measured evidence)
Bounded last-stage fine-tuning **failed to improve** the frozen baseline. The primary targets regressed (VIABLE recall −0.0655, VIABLE F1 −0.1041, pooled macro-F1 −0.0394), with NON_TUMOR also down (F1 −0.0517) and calibration worse (Brier +0.0563). The only "positive" signal (VIABLE→NECROSIS −37) is explained entirely by a larger VIABLE→NON_TUMOR increase (+56) and fewer VIABLE correct (−19) — not improved discrimination. The regression is consistent across the two informative folds. No post-hoc significance threshold was invented; the classification rests on the direction and consistency of the measured deltas.

## 14. Model bundle / hash
**None created.** Per the brief, a final all-1,028 G5 bundle is trained ONLY if PROMISING. Result is NO BENEFIT → `baseline-frozen-g4` stays the default; no misleading "improved" replacement. Fold checkpoints (diagnostic only) in scratch:
- Case-3 `85f1ad8e3b5bd81dfd78276355fbd420531b8fe7b5f2053697af8a930686e49a`
- Case-4 `33e26000ef4dde548377435ecb48766e1324ac0ff49ed44d89433596d5ca6816`
- Case-48 `9823eab61d3f5c5e49647adfc0510d4688e36fdd68580c3aae257f3906c83bc0`
- P9 `5c3723c1042a3971dc7c881dabd67539e8242a28384f3eddf3e9ed84276ceabb`

## 15. Durable artifacts (under aidlc-docs/inception/model/g5/)
`run-configuration.json` · `trainable-parameter-inventory.json` · `test-report.json` · `fold-histories.json` · `fold-checkpoint-hashes.json` · `g5-oof-predictions.csv` (1028 rows) · `per-fold-metrics.json` · `overall-oof-metrics.json` · `confusion-matrix.csv` · `g4-vs-g5-metric-comparison.json` · `g4-vs-g5-confusion-comparison.json` · `viable-to-necrosis-error-comparison.json` · `g4-vs-g5-fold-comparison.json` · `training-run-summary.json` · `g5-summary.md` · `model-card-addendum-g5.md`. Large fold checkpoints live in scratch (`osteopatch_g5/checkpoints/`), hashes recorded above. All G4 artifacts untouched.

## 16. Recommended next action
Keep `baseline-frozen-g4` as the prototype default. Do **not** pursue broader fine-tuning on this 4-group cohort — the bounded minimal variant already overfits and hurts the frozen baseline, so a larger unfreeze would almost certainly be worse. The VIABLE_TUMOR ceiling is a **data-scope / group-count** limitation (4 slide groups, viable concentrated in Case-4/Case-48), not a last-stage-capacity limitation. The highest-value next step is widening case/group coverage for VIABLE_TUMOR (more independent slides) before any further adaptation; multi-seed stability, calibration, Grad-CAM, and uncertainty policy remain future approval-gated steps. **STOP here pending owner review.**
