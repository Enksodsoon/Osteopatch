# Split proposal — G2 (OsteoPatch Review)

**Status:** G2 offline/deterministic analysis. No split is executed; this is the design + leakage assessment. Built from `canonical_manifest.csv` + `group_class_distribution.csv`. No pixels, no network, no AWS.

**Grouping unit:** the 4 recovered case/slide-group tokens (Case 3 / Case 4 / Case 48 / P9). Independence claimed is **case/slide-group independence**, never patient independence (see `patient_mapping_evidence.md`).

## 1. Why no random patch-level split

A random patch split would place patches from the **same slide/case on both sides** of the split. Patches from one WSI share stain, scanner, patient biology and often spatial adjacency, so a random split **leaks** group identity into validation/test and inflates every metric. With only 4 groups this leakage is the dominant validity risk (a Jan-2026 preprint on this dataset [S06] reports much poorer patient-level results than tile-level). **Random patch split is prohibited.**

## 2. Candidate: Leave-One-Group-Out (LOGO) grouped cross-validation

4 groups → **4 outer folds**, each holding out exactly one group as the test portion, training on the other three. All patches of a held-out group stay together; zero group overlap across the fold boundary → no case/slide leakage.

### Per-fold class representation (trainable rows only; MIXED excluded)

| Fold (held-out = test) | Test NON_TUMOR | Test VIABLE | Test NECROSIS | Test classes present | Train NON_TUMOR | Train VIABLE | Train NECROSIS | Train classes present |
|---|---|---|---|---|---|---|---|---|
| Hold out **Case 3** | 110 | 3 | 171 | 3 | 426 | 289 | 92 | 3 |
| Hold out **Case 4** | 78 | 87 | 90 | 3 | 458 | 205 | 173 | 3 |
| Hold out **Case 48** | 136 | 202 | 2 | 3 | 400 | 90 | 261 | 3 |
| Hold out **P9** | 212 | 0 | 0 | **1** | 324 | 292 | 263 | 3 |

(Train columns = whole-dataset trainable totals 536/292/263 minus the held-out group's counts.)

### How this avoids leakage

- Group is the atomic unit; a group is never split across train and test.
- All derivatives/duplicates (if any surface at the image stage) inherit their group → still never cross the boundary.
- No filename, label string, folder name, or group token is ever a model input (per doc 02 / doc 08).

### Fold-level consequences (honest)

- **P9 fold is degenerate:** test = NON_TUMOR only. On that fold VIABLE_TUMOR and NECROSIS have **no test support** → their precision/recall/F1 are **not estimable** (must be reported as "unavailable — class absent in fold", never as 0). A confusion matrix for that fold has only one true-label row populated. One-vs-rest AUROC for the two absent classes is undefined on that fold.
- **Case 48 fold:** test NECROSIS support = 2 → NECROSIS recall is estimable but statistically meaningless (CI effectively the whole [0,1]); treat as indicative only.
- **Case 3 fold:** test VIABLE support = 3 → same caveat for VIABLE.
- Only **Case 4** holds out with all three classes at usable support (78/87/90) — it is the single fold that yields a defensible per-class read, and even that is one group.

## 3. Nested validation feasibility with 4 groups

Nested grouped CV needs an inner validation split carved from the 3 training groups of each outer fold. With only **3 inner groups** per outer fold:

- An inner LOGO (3-fold) is **technically possible** for head-only hyperparameter / early-stop decisions, but each inner fold again risks a class-starved held-out group (e.g. when P9 is an inner group, inner validation sees only NON_TUMOR).
- Calibration (temperature scaling) fit on such a tiny, class-skewed inner split is **not defensible** as a reliable probability calibrator; if attempted it must be disclosed as fit-on-same-small-split (doc 02).
- **Assessment:** nested CV is feasible only as an *exploratory* mechanism to avoid test-set peeking during tuning. It cannot produce trustworthy generalization or calibration estimates from 4 groups. Prefer: freeze all hyperparameters a priori (doc 02 initial config) and use LOGO purely for reporting, OR use a single inner group as validation with the limitation stated.

## 4. The 2-train / 1-val / 1-test idea (doc 02)

Doc 02 floats "two groups train, one val, one locked test". It is only defensible if the chosen val+test groups together cover all three classes at usable support. Given P9=NON_TUMOR-only, **any assignment that puts P9 in val or test cripples that portion to one class**, and any assignment that puts P9 in train removes 212 NON_TUMOR from evaluation. No 2/1/1 assignment of these 4 groups yields a locked test set with all three classes at usable support **and** an independent val set with the same. → A single fixed 2/1/1 split **cannot** support an independent 3-way evaluation here. LOGO (reporting all 4 folds, cross-fold aggregated) is the honest alternative.

## 5. Recommendation

- **Use Leave-One-Group-Out (4-fold grouped CV) for evaluation**, report every fold plus a cross-fold aggregate, and mark not-estimable class metrics explicitly.
- **Freeze hyperparameters a priori** (doc 02 config) rather than relying on nested CV from 4 groups; if any tuning is done, confine it to each outer fold's training groups and disclose the inner-split limitation.
- **No strong generalization claim** may be drawn from 4 groups. Any headline is labelled "case/slide-group independence (4 groups) — exploratory; patient-level independence unverified."
- MIXED (53) rows are **never** in any training or primary-metric portion (see `mixed-patch-policy.md`).
