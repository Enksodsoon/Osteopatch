# G2 validation report — OsteoPatch Review

**Status:** G2 offline/deterministic. No pixels, no network, no AWS, no training. Built from existing artifacts (`manifest.csv` → `canonical_manifest.csv`) under the **ratified** label policy. This report carries the T6 evaluation plan and the T10 gate verdict.

## 1. Reconciliation (actual, computed)

| Metric | Value |
|---|---|
| Total rows | 1,144 |
| CSV↔PathDB join (1:1) | 1,144 / 1,144 |
| Duplicate image_id | 0 |
| Unmatched | 0 |
| Source labels BEFORE map | Non-Tumor 536 · Viable 292 · Non-Viable-Tumor 263 · viable: non-viable 53 |
| Canonical AFTER map (trainable) | NON_TUMOR 536 · VIABLE_TUMOR 292 · NECROSIS 263 |
| Trainable total | 1,091 |
| MIXED excluded (review-only) | 53 |
| Reconciliation | 536+292+263+53 = 1,144 ✓ ; trainable 1,091 + MIXED 53 = 1,144 ✓ |

Expected source distribution (Non-Tumor 536 / Viable 292 / Non-Viable-Tumor 263 / mixed 53 = 1,144) **matches actual exactly** — no STOP condition triggered.

## 2. Grouping

4 case/slide-group tokens: Case 3 (285) · Case 4 (277) · Case 48 (370) · P9 (212) = 1,144. Every trainable row carries a group id. **Case/slide-group independence only — NOT patient-independent** (`patient_mapping_evidence.md`). See `group-class-distribution.md` for the full group × class table; P9 is 100% NON_TUMOR.

## 3. Evaluation plan (T6)

Evaluation is **grouped** (Leave-One-Group-Out, 4 folds; see `split-proposal.md`). For each fold and for the cross-fold aggregate, report:

- **Confusion matrix** with raw counts (one per fold + aggregate). A class absent from a fold's test portion yields an empty true-label row — shown as such, never as zeros implying perfect/also-failed performance.
- **Per-class precision / recall / F1** with **support**. Where a class has no test support in a fold (e.g. VIABLE_TUMOR and NECROSIS on the P9 fold), report **"not estimable — class absent"**, never 0.
- **Macro-F1** computed only over classes present in that fold; disclose how many classes it averages so a 1-class or 2-class fold macro is not compared against a 3-class fold macro.
- **Balanced accuracy** over present classes, with the same disclosure.
- **Support** table per fold (train + test counts per class).
- **Calibration / confidence** (optional, if practical): temperature scaling fit only inside an outer fold's training groups; report before/after log loss + multiclass Brier; **disclose** fit-on-small-split limitation; if not defensible, return uncalibrated softmax labelled as such. Never claimed as clinical probability.
- **Uncertainty / review ranking:** deterministic priority key (quality → increasing top-score → increasing top-two margin → image_id); report coverage, flagged count, error among unflagged, error-capture among flagged; "unavailable" when a denominator is 0.
- **AUROC (one-vs-rest):** per present class only; for a class absent in a fold's test portion the OvR AUROC is **undefined** and reported as such.
- **Accuracy** may be shown but is never the lone headline (class imbalance + P9 single-class fold make it misleading).
- **Cross-fold aggregate:** pool predictions across folds for an overall confusion matrix / macro-F1, AND report the per-fold spread, so the P9-fold degeneracy and the sparse NECROSIS/VIABLE folds stay visible.

**No clinical-validity claim.** All metrics are exploratory on 4 groups. MIXED (53) excluded from every number above (`mixed-patch-policy.md`).

### Not-estimable map (from the actual distribution)

| Fold (test group) | NON_TUMOR | VIABLE_TUMOR | NECROSIS |
|---|---|---|---|
| Case 3 | estimable (110) | weak (3) | estimable (171) |
| Case 4 | estimable (78) | estimable (87) | estimable (90) |
| Case 48 | estimable (136) | estimable (202) | weak (2) |
| P9 | estimable (212) | **not estimable (0)** | **not estimable (0)** |

## 4. G2 gate checklist (T10)

| # | Criterion | Result |
|---|---|---|
| 1 | All 1,144 rows accounted for | ✓ 1,091 trainable + 53 MIXED |
| 2 | Join 1:1 or exceptions documented | ✓ 1,144/1,144, 0 unmatched, 0 dup |
| 3 | Mapping deterministic | ✓ pure lookup, fail-closed, no guesses |
| 4 | MIXED excluded from primary labels | ✓ trainable=FALSE, retained in manifest |
| 5 | Every trainable row has a group id | ✓ all ∈ {Case-3,Case-4,Case-48,P9} |
| 6 | No patch-level leakage in eval design | ✓ LOGO grouped CV; random patch split prohibited |
| 7 | 4-group limit documented | ✓ split-proposal + this report + patient_mapping_evidence |
| 8 | Reproducible from artifacts | ✓ built offline from manifest.csv; no pixels/AWS |
| 9 | No pixels / AWS needed | ✓ |
| 10 | Independent 3-way train/val/test possible? | ✗ **4 groups + P9 single-class prevent it** |

## 5. Verdict: **PASS WITH LIMITATIONS**

The data layer is sound, deterministic, fully reconciled, leakage-aware, and reproducible from artifacts — but criterion 10 fails: **4 case/slide groups (one of them, P9, single-class) cannot support an independent 3-way train/val/test split, nor a defensible patient-level generalization claim.** Per the brief this is explicitly a PASS WITH LIMITATIONS, not a clean PASS.

### Limitations (exact)

1. **4 groups only** → no independent fixed train/val/test; evaluation is grouped LOGO, exploratory.
2. **P9 is 100% NON_TUMOR** → VIABLE_TUMOR and NECROSIS not estimable on the P9 fold; macro metrics on that fold average <3 classes.
3. **Sparse classes:** Case 48 NECROSIS = 2, Case 3 VIABLE = 3 → those per-class reads are indicative only.
4. **Case/slide-group independence, NOT patient independence** — token→biological-patient identity is unverified (count coincidence + disjoint slides only).
5. **Image-level checks PENDING** — SHA-256, verified dimensions, perceptual duplicates require bytes not yet fetched (`image-ingestion-plan.md`); exact/perceptual dedup across splits is therefore not yet enforced.
6. **MIXED (53)** carried for review/error-analysis only; no sanctioned learned representation yet.
7. **Nested CV from 4 groups** cannot yield trustworthy tuning/calibration estimates; hyperparameters are frozen a priori.
8. **No clinical-validity / generalization claim** is supportable at G2.

## 6. Single recommended next gate

Proceed to **G3 (model/eval design sign-off)** on this grouped-CV plan **without fetching pixels** — OR, if an image-dependent step is wanted first, authorize the **bounded test download** in `image-ingestion-plan.md` (requires resolving AWS access B2). Recommended: **G3 model/eval design review on the frozen-encoder baseline + LOGO plan**, keeping the image fetch as the subsequent gated step.
