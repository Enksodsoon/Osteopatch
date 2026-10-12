# OsteoPatch model tuning report

Run: `20261008T014711Z`
Status: **COMPLETE**
Device: `cpu`; elapsed: 3876s / 8496s
Eligible images: 1028 / 1144; four slide/case groups; patient independence unverified.
Qualification: **NOT_QUALIFIED** — viable recall improved +0.0161 vs +0.05 required; necrosis recall declined -0.0249 vs -0.02 allowed; Case-48 improved only +0.0033.

All scores are uncalibrated research outputs. This evaluation does not establish patient-level or clinical performance.

Historical G4 is descriptive only: macro-F1 **0.5623**, viable-tumor recall **0.1103**.

Handoff evidence reports G5 regressed both metrics; exact G5 values are unavailable, so no numeric comparison is made.

## Qualification gate results

Across the three seed-level out-of-fold comparisons, mean viable-tumor recall improved by **0.0161** (1.61 percentage points), below the required +0.05. Mean macro-F1 improved by **0.0015**; mean non-tumor recall changed by **-0.0048**; mean necrosis recall changed by **-0.0249**, exceeding the allowed 0.02 decline. Case-4 viable recall improved by **0.0471** and Case-48 by **0.0033**. The group-direction check passed, but the overall viable-recall and necrosis-balance gates failed.

The final four-group held-out selection chose `frozen_inverse`, the fresh ImageNet encoder with a linear head. The two tumor-weighted configurations were not eligible under the within-two-point class-balance rule. An all-data `frozen_inverse` artifact was fitted for research handoff, but it remains **NOT_QUALIFIED**, was not registered, and is not selectable by the app. Live analysis continues to use the recovered model by default.

## Final group-held-out selection and all-data artifact

| Configuration | Macro-F1 | Viable recall | Non-tumor recall | Necrosis recall |
|---|---:|---:|---:|---:|
| `frozen_inverse` | 0.6001436527 | 0.1896551724 | 0.9049586777 | 0.8425196850 |
| `frozen_tumor2x` | 0.6098437986 | 0.2275862069 | 0.8946280992 | 0.8149606299 |
| `stage12_tumor2x` | 0.5593153630 | 0.1034482759 | 0.9070247934 | 0.8267716535 |

The selected all-data artifact is `osteopatch-unqualified-20261008T014711Z`, trained on all 1,028 eligible images with 3,075 trainable parameters. Bundle SHA-256: `a899e3108d6ea5cbf52cd5b6e99b1efb4127f99214440015b827cdcfe4a8acfa`. Save path: `runtime-artifacts/models/unqualified/osteopatch-unqualified-20261008T014711Z.pt`. Reload parity passed. This fit is not independent evaluation and does not change the NOT_QUALIFIED decision.

The recorded finalization duration of 642.16 seconds starts after frozen-feature embedding generation. The finalization stage had a 1,800-second hard deadline and completed within it. Including both earlier failures and the outer evaluation, the conservative campaign compute upper bound is 11,486.35 seconds, leaving at least 2,913.65 seconds of the four-hour allowance.

## Per-seed out-of-fold metrics

| Seed | Candidate macro-F1 | Candidate viable recall | Comparator macro-F1 | Comparator viable recall |
|---:|---:|---:|---:|---:|
| 42 | 0.6053114967712783 | 0.21724137931034482 | 0.600143652737188 | 0.1896551724137931 |
| 43 | 0.5833788155652097 | 0.14482758620689656 | 0.5770602100222136 | 0.12758620689655173 |
| 44 | 0.5861995620972351 | 0.19310344827586207 | 0.5932486889803963 | 0.1896551724137931 |

## Outer-fold group results

| Seed | Held-out group | Candidate macro-F1 | Candidate viable recall | Comparator macro-F1 | Comparator viable recall |
|---:|---|---:|---:|---:|---:|
| 42 | Case-3 | 0.57029187063343 | 0.3333333333333333 | 0.58659423602434 | 0.3333333333333333 |
| 42 | Case-4 | 0.7419268602983147 | 0.5764705882352941 | 0.7169265112469981 | 0.4823529411764706 |
| 42 | Case-48 | 0.3042758705549403 | 0.06435643564356436 | 0.3042758705549403 | 0.06435643564356436 |
| 42 | P9 | None | NA | None | NA |
| 43 | Case-3 | 0.5827215096564942 | 0.3333333333333333 | 0.5973159332079506 | 0.3333333333333333 |
| 43 | Case-4 | 0.686010576018634 | 0.36470588235294116 | 0.6643455668779361 | 0.3176470588235294 |
| 43 | Case-48 | 0.27365406218689803 | 0.04950495049504951 | 0.26974214686296255 | 0.04455445544554455 |
| 43 | P9 | None | NA | None | NA |
| 44 | Case-3 | 0.5575804941707234 | 0.3333333333333333 | 0.5771167048054919 | 0.3333333333333333 |
| 44 | Case-4 | 0.7245100103465529 | 0.5294117647058824 | 0.7245100103465529 | 0.5294117647058824 |
| 44 | Case-48 | 0.2732709740092841 | 0.04950495049504951 | 0.27178088284665264 | 0.04455445544554455 |
| 44 | P9 | None | NA | None | NA |

## Per-class support and metrics

Fold-level confusion matrices, per-class precision/recall/F1/support, balanced accuracy, log loss, and Brier score are in `run-report.json`. Undefined metrics are `null` when a held-out group lacks that class.

## Failed or incomplete campaign attempts

The completed batch-8 outer evaluation had 132 complete training runs and no failed folds. Finalization added 12 group-held-out selection fits and one all-data fit; bundle reload parity passed. Two earlier attempts in this same four-hour campaign are preserved separately:

| Run | Status | Elapsed | Outcome |
|---|---|---:|---|
| `20261008T000307Z` | Failed | 1,445.36 s | Sparse-class metric calculation raised `TypeError` when F1 used undefined recall; guard and regression test added. |
| `20261008T003006Z` | Failed | 4,364.55 s | CPU allocator ran out of memory requesting 5,308,416 bytes; batch size reduced from 16 to 8 with the reason recorded. |
| `20261008T014711Z` | Complete | 3,876.44 s | All three seeds and four outer folds completed; qualification gate failed, so no model was registered. |

The scheduled 01:00 launch also exited before logging because PowerShell unwrapped a single runtime path; the runner was corrected before these attempts. The preceding run directories retain their complete logs and partial artifacts.

The one-time Task Scheduler job ended with `LastTaskResult=0`, no next run, and no remaining training or finalization process.

## Real-image browser check

The local G7 browser flow successfully imported a manifest-verified TIFF and scored one tile. Two runs persisted `model_id=g4-behavioral-recovery-r1` and bundle hash `ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73`; the unqualified bundle was not exposed. The input manifest label is `NON_TUMOR`, while both smoke-test runs returned `NECROSIS` with uncalibrated scores 0.282 / 0.018 / 0.700. The browser also exposed and verified a fix for authenticated gallery thumbnails: all 50 returned 200 and rendered at 256×256. The check used a temporary copy of the G6 database and temporary run storage. Full details are in [`browser-verification.md`](browser-verification.md).

## Implementation validation

- Backend suites: `uv run --locked --extra dev --extra model pytest app/g6/backend/tests app/g7-enterprise/backend/tests -q` — **291 passed, 5 skipped**.
- Tuning checks: `uv run --locked --extra dev --extra model pytest tests/tooling/test_model_tuning.py -q` — **7 passed**. These cover grouped split isolation, missing-class rejection, metrics, selection, exclusions, and checkpoint hashing.
- G7 frontend: `npm test -- --run` — **35 passed**; `npm run build` — **passed**. Vite reports the existing mixed static/dynamic `api.ts` import warning.
- Lint: Ruff passed on the tuning scripts and tests. `git diff --check` passed; Git emitted line-ending normalization notices for CRLF-configured files.
- The backend suites include model hash rejection, selected-model attribution identity, rollback, and frozen-corpus immutability checks.
- Headroom executable was unavailable at its documented locations; no request routing or token-savings claim is made.

## Reproduction

`uv run --locked --extra dev --extra model python scripts/model_tuning.py --image-root "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\images" --pretrained-weights "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\models\torch-hub\hub\checkpoints\mobilenet_v3_small-047dcff4.pth" --manifest "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\wt\model-tuning\aidlc-docs\inception\full-image-qc\full-image-qc-results.csv" --runtime-model-dir "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\models" --budget-hours 2.36 --batch-size 8 --batch-size-reduction-reason "Previous batch 16 run failed due host CPU memory exhaustion" --seeds 42,43,44`

The exact environment, image and split hashes, fold selection metrics, epoch losses, parameter counts, checkpoint hashes, timings, hardware, final selection, artifact hash, and failure details are in `run-report.json`. `oof-predictions.csv`, `error-review.csv`, and `excluded-images.csv` contain the completed prediction and review exports.

Final selection and nonselectable all-data fit reproduction:

`uv run --locked --extra dev --extra model python scripts/finalize_model_tuning.py --report "docs/evidence/model-tuning/20261008T014711Z/run-report.json" --manifest "aidlc-docs/inception/full-image-qc/full-image-qc-results.csv" --image-root "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\images" --pretrained-weights "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\models\torch-hub\hub\checkpoints\mobilenet_v3_small-047dcff4.pth" --runtime-model-dir "C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\runtime-artifacts\models" --budget-seconds 1800 --batch-size 8`
