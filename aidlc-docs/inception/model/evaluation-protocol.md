# Evaluation protocol — G3 (OsteoPatch Review)

**Status:** G3 **design only**. No pixels, no AWS, no training. This protocol is **frozen before any pixels exist**. It operationalizes the G2 evaluation plan (`../data/g2-validation-report.md` §3, `../data/split-proposal.md`) into an executable-later contract. Independence claimed is **case/slide-group independence** over 4 groups (Case 3 / Case 4 / Case 48 / P9) — never patient-level.

Companion machine-readable file: `logo-fold-plan.csv`.

---

## 1. External evaluation = Leave-One-Group-Out (LOGO), 4 folds

The atomic unit is the **group**. Each outer fold holds out exactly one group as the **test** portion and trains on the other three. A group is **never** split across the train/test boundary → zero case/slide leakage. The held-out test portion **never** influences optimization (no tuning, no early-stop signal, no calibration fit touches it).

Random patch-level splitting is **prohibited** (G2 `split-proposal.md` §1): it leaks slide/group identity and inflates every metric.

### The 4 outer folds (trainable rows only; MIXED 53 excluded everywhere)

| Fold | Test (held-out) group | Train groups | Test N / per class (NON/VIA/NEC) | Train N / per class (NON/VIA/NEC) | Classes present in test |
|---|---|---|---|---|---|
| F1 | **Case 3** | Case 4 + Case 48 + P9 | 284 / 110·3·171 | 807 / 426·289·92 | 3 (VIABLE weak = 3) |
| F2 | **Case 4** | Case 3 + Case 48 + P9 | 255 / 78·87·90 | 836 / 458·205·173 | 3 (all usable) |
| F3 | **Case 48** | Case 3 + Case 4 + P9 | 340 / 136·202·2 | 751 / 400·90·261 | 3 (NECROSIS weak = 2) |
| F4 | **P9** | Case 3 + Case 4 + Case 48 | 212 / 212·0·0 | 879 / 324·292·263 | **1 (NON_TUMOR only)** |

(Train per-class = whole-dataset trainable totals 536/292/263 minus the held-out group's counts. Totals: trainable 1,091.)

**The P9 fold (F4) is degenerate and is shown, never hidden:** test = NON_TUMOR only → VIABLE_TUMOR and NECROSIS have **no test support** on F4 and their per-class metrics are **not estimable** there. The Case 48 fold (F3, NECROSIS test support = 2) and the Case 3 fold (F1, VIABLE test support = 3) yield **indicative-only** reads for those classes. **Case 4 (F2)** is the single fold with all three classes at usable test support (78/87/90).

---

## 2. Internal validation strategy (chosen) — least misleading at 4 groups

Each outer fold has only **3 training groups**, so any internal validation is carved from those 3. Options considered:

| Option | Verdict at 4 groups |
|---|---|
| Patch-level random validation inside the training groups | **PROHIBITED** — leaks the same source groups across train/val (identical leakage mode as a random split), inflating the val signal used for early-stop. |
| Leave-one-more-whole-group-as-val (inner LOGO, 3-fold) | Technically possible, but an inner held-out group can be class-starved (e.g. P9 as inner val → single class), making the early-stop macro-F1 signal unreliable. |
| Nested group-aware CV | Not trustworthy from 3 inner groups (G2 `split-proposal.md` §3); cannot produce reliable tuning/calibration. |
| **No fixed val + a priori frozen hyperparameters + constrained epochs** | **CHOSEN as primary.** Hyperparameters are frozen a priori (doc 02 config in `model-contract.md`); the head is trained for a fixed small epoch budget. This avoids *any* leaky validation signal and matches the "freeze hyperparameters a priori, use LOGO purely for reporting" recommendation (G2 `split-proposal.md` §5). |

**Chosen protocol:** **a-priori-frozen hyperparameters + constrained epoch budget, no leaky validation.** When an early-stop signal is nonetheless wanted, the **only** sanctioned validation is a **whole inner group** held out from the 3 training groups (group-aware), with its class-starvation limitation disclosed per fold — **never** a patch-level random val that spans the same groups.

### Per-fold tuning discipline

| Question | Answer (frozen) |
|---|---|
| Train groups | the 3 non-held-out groups (table §1) |
| Val group(s) | **none by default** (a-priori frozen hyperparameters); if an inner val is used, exactly **one whole inner group**, group-aware, limitation disclosed |
| Hyperparameter selection | **frozen a priori** (doc 02 config); no per-fold search |
| Hyperparameters reused across outer folds? | **Yes** — the same frozen config is used for all 4 folds (there is no per-fold search to reuse). This is disclosed, not hidden. |
| What is statistically independent | the held-out **group** vs the 3 training groups (case/slide-group independence) |
| What is **not** independent | the **patches within** a group are not independent biological samples; the 4 groups are too few for a generalization claim |

Minimal tuning only. The locked test (held-out group) is scored exactly once per fold, after the fold's model and all its settings are frozen.

---

## 3. Metric set (frozen) — each classified PRIMARY / SECONDARY / EXPLORATORY / NOT APPROPRIATE

| Metric | Tier | Notes / absent-class handling |
|---|---|---|
| **Confusion matrix (raw counts)** | **PRIMARY** | One per fold + one pooled aggregate. A class absent from a fold's test → its true-label row is **empty**, shown as such, never zero-filled. |
| **Per-class precision / recall / F1 + support** | **PRIMARY** | Reported with support. Absent class in a fold → **"not estimable — class absent"**, never 0. Weak support (VIABLE=3 on F1, NECROSIS=2 on F3) → value shown **tagged "indicative only, CI ≈ [0,1]"**. |
| **Macro-F1** | **PRIMARY** | Computed **only over classes present** in that fold; the number of classes averaged is **disclosed** (so a 1-class P9-fold macro is never compared to a 3-class fold macro). |
| **Balanced accuracy** | **PRIMARY** | Over present classes only; same class-count disclosure. |
| **Overall accuracy** | **SECONDARY** | Shown but **never the lone headline** (imbalance + P9 single-class fold make it misleading). |
| **Support (per-class train+test counts)** | **PRIMARY** | Always shown; it is what makes the not-estimable/weak cells legible. |
| **OvR AUROC (per present class)** | **SECONDARY** | Per class present in the fold's test; for an absent class the OvR AUROC is **undefined → reported as such**. Needs ≥1 positive and ≥1 negative in the fold. |
| **PR-AUC (per present class)** | **SECONDARY** | Same presence requirement; more informative than AUROC under imbalance; absent/weak classes flagged. |
| **Log loss** | **SECONDARY** | Probability-quality metric on the held-out scores; reported per fold + aggregate. Sensitive to miscalibration. |
| **Brier score (multiclass)** | **SECONDARY** | Mean over images of the sum of squared class-probability errors (doc 02 definition). Reported alongside log loss. |
| **ECE (expected calibration error)** | **EXPLORATORY** | Reported only with an explicit caveat (tiny grouped data; see `uncertainty-review-policy.md` / `g3-validation-report.md` calibration). Not a reliability guarantee. |
| **Any single-number "disease probability"** | **NOT APPROPRIATE** | A softmax score is a **model class score**, never a patient disease probability (doc 02; `claim-boundaries.md`). |
| **Bootstrapped narrow CIs over patches** | **NOT APPROPRIATE** | Bootstrapping patches as if independent biological samples manufactures false precision (doc 02). |

### Absent-class rule (single source of truth)

A class with **zero test support** in a fold is **"not estimable — class absent in fold"** for every metric that needs its positives (precision/recall/F1, OvR AUROC, PR-AUC). It is **never** entered as 0 and **never** averaged in as 0. This is why macro-F1/balanced-accuracy explicitly report *how many* classes they averaged.

---

## 4. Cross-fold aggregation (principal summary chosen)

Three candidates:

| Method | What it does | Weakness here |
|---|---|---|
| Macro-average across folds | Average each fold's macro-F1 | A degenerate fold (P9, 1 class) and a 3-class fold are averaged as peers → distorts. |
| Support-weighted across folds | Weight folds by test size | The **big group dominates** and can mask a small-group failure — exactly what G2 warns against. |
| **Pooled out-of-fold predictions** | Concatenate every patch's held-out prediction, compute one confusion matrix / macro-F1 over the pool | Each trainable patch appears **once**, scored by the fold that never saw its group. Honest single summary; no group double-counted. |

**Chosen principal summary: pooled out-of-fold predictions** (one aggregate confusion matrix + macro-F1 over the pool), **always reported together with the per-fold table and the per-fold spread.** The pooled summary is the headline *number*; the per-fold spread is what keeps the P9 degeneracy and the sparse NECROSIS/VIABLE folds **visible**. Neither replaces the other. The big group never silently masks a small-group failure because the per-fold breakdown is reported beside the pool, every time.

---

## 5. Reporting rules

- Report the pooled aggregate **and** all 4 per-fold results together — never the aggregate alone.
- Every absent/weak class cell carries its tag ("not estimable" / "indicative only").
- Accuracy is never the lone headline.
- All numbers are labelled **exploratory, case/slide-group independence (4 groups), patient-level independence unverified** (`claim-boundaries.md`).
- MIXED (53) never enters any number here (`../data/mixed-patch-policy.md`); its separate challenge-set analysis lives in `g3-validation-report.md`.
- A poor result is **reported**, not used to silently reselect a run (doc 02).
