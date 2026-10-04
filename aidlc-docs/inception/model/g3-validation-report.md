# G3 validation report — model + evaluation design review (OsteoPatch Review)

**Status:** G3 **design only**. No pixels, no AWS, no training/fine-tune, no framework install, no infra, no deploy, no UI. Built deterministically on the frozen G2 contract. This report carries the imbalance decision, the mixed-patch challenge-set design, the experiment tiers, and the **G3 gate verdict**.

**Frozen G2 contract (verbatim):** NON_TUMOR 536 / VIABLE_TUMOR 292 / NECROSIS 263 = **1,091 trainable**; MIXED 53 excluded (retained); groups Case 3 / Case 4 / Case 48 / P9; **LOGO** 4-fold CV; **P9 = 100% NON_TUMOR**; Case 48 NECROSIS = 2; Case 3 VIABLE = 3. Independence = **case/slide-group**, never patient-level. Absent-class metric = **not estimable**, never 0.

Companion G3 artifacts: `model-contract.md`, `evaluation-protocol.md`, `logo-fold-plan.csv`, `preprocessing-contract.md`, `augmentation-policy.md`, `uncertainty-review-policy.md`, `claim-boundaries.md`, `experiment-matrix.csv`.

---

## 1. Class-imbalance strategy (chosen — exactly one, no stacking)

Trainable class counts: **NON_TUMOR 536 / VIABLE_TUMOR 292 / NECROSIS 263** (ratio ≈ 2.04 : 1.11 : 1.00). Imbalance is **mild** (not an extreme long tail), and the per-fold imbalance shifts (e.g. holding out P9 removes 212 NON_TUMOR, flattening the training mix).

Options:

| Option | Verdict |
|---|---|
| **Weighted cross-entropy (train-only inverse-frequency, mean-normalized)** | **CHOSEN** — doc 02's named option; deterministic, no sampler randomness, computed **per fold** from that fold's **training** counts only. |
| Balanced sampler (oversampling minority) | Rejected for baseline — oversampling tiny per-group classes (e.g. a fold where VIABLE training support is small) risks memorizing a handful of patches. |
| Focal loss | Rejected for baseline — adds a focusing hyperparameter to tune, and tuning is not trustworthy at 4 groups. EXPLORATORY only. |
| None | Rejected — leaves the 2:1 NON_TUMOR skew unaddressed when it is cheap to correct. |

**No stacking:** weighted-CE is used **alone** (no sampler + no focal on top).

### Deterministic weight formula (frozen)

For each outer fold, using **only that fold's training-group counts** `n_c` for class `c ∈ {NON_TUMOR, VIABLE_TUMOR, NECROSIS}`:

```
raw_c   = 1 / n_c                         # inverse frequency
w_c     = raw_c * (K / Σ_k raw_k)         # normalize so mean(w) = 1, K = 3 classes present
loss    = CrossEntropy(logits, target, weight = [w_NON, w_VIA, w_NEC])
```

Worked example — **F4 (hold out P9)**, training counts NON 324 / VIA 292 / NEC 263:
`raw = [1/324, 1/292, 1/263] = [0.003086, 0.003425, 0.003802]`; `Σraw = 0.010313`; `w = raw * 3 / Σraw = [0.898, 0.996, 1.106]`, mean = 1.000. (Weights are recomputed per fold from that fold's training counts; absent classes in a fold are simply not present in `K`.) Class weights are **train-only** — never applied to validation/test scoring.

---

## 2. Mixed-state challenge set (the 53 MIXED patches) — separate from headline

The 53 `MIXED_VIABLE_NECROTIC` patches are **not** in any training portion of any fold and **not** in any headline 3-class metric (`../data/mixed-patch-policy.md`, hard contract). They are **not a 4th test class.** G3 designs a dedicated, separately-reported analysis:

**Design: run the frozen 3-class model (the per-fold models, or the eventual final model, applied as inference-only) over all 53 MIXED patches and report, as a tagged subset:**

1. **VIABLE vs NECROSIS score balance** — distribution of `score_VIABLE` vs `score_NECROSIS` (expectation: these two scores compete; NON_TUMOR score should be low). A histogram of `score_VIABLE − score_NECROSIS` centered near 0 would be consistent with genuine mixing.
2. **Entropy** — distribution of softmax entropy over the 53 (expectation: higher than confident single-class patches).
3. **Top1–top2 margin** — expectation: **small** margins; the mixed set *should* flag at a **high rate** under the review rule (margin < 0.15 or top < 0.70), which is a positive validation of the uncertainty policy.
4. **Saliency** — Grad-CAM over MIXED patches, inspected qualitatively (does attribution light up both viable and necrotic regions?).
5. **Human-review behavior** — do these patches route to review and get `MIXED_TISSUE` deferrals in the workflow (doc 08 reason code)?

**Reporting tag (mandatory):** every MIXED result is labelled **"MIXED_VIABLE_NECROTIC subset (n=53) — excluded from the 3-class contract; shown for error analysis only."** It never shares an axis, denominator, or headline with the primary metrics. Per-group MIXED counts (Case 3 = 1, Case 4 = 22, Case 48 = 30, P9 = 0) are preserved for context. This is design only; nothing is run now.

---

## 3. Calibration & uncertainty (summary; full policy in `uncertainty-review-policy.md`)

- **Baseline score type:** `UNCALIBRATED_SOFTMAX`. Calibration (temperature scaling) is **SECONDARY, feasibility-gated**, fit only inside training groups, disclosed; Platt/isotonic **not feasible yet** at 4 groups.
- **Baseline uncertainty signal:** top1–top2 **margin** (+ max-softmax), lower margin = higher review priority; deterministic priority key frozen; **0-denominator → "unavailable", never 0 error**.

---

## 4. Experiment tiers (summary; full matrix in `experiment-matrix.csv`)

- **REQUIRED BASELINE:** frozen-encoder MobileNetV3-Small 3-class head; uncalibrated-softmax + margin review ranking; Grad-CAM attribution; mixed-state challenge-set analysis.
- **SECONDARY (approved-slot):** ResNet18 sanity comparison; short last-stage fine-tune; temperature-scaling; 224-vs-384; small brightness/contrast jitter.
- **DO NOT DO YET:** hyperparameter sweeps / architecture search; heavy full fine-tune; ensembles; stain-normalization research; SSL; multi-task/multilabel (incl. a MIXED target); multi-seed sensitivity (recommended *later*). Each needs a new gate (some + a revised compute budget / expert review).

Claims stay **proportional to 4 groups** (`claim-boundaries.md`).

---

## 5. Reproducibility (summary; full list in `model-contract.md` §4)

A future run must record: manifest version/hash, fold assignment, seed (+ "one seed ≠ stability"), architecture, pretrained-weights version/hash, preprocessing (`preprocess_sha256`), augmentation, optimizer/LR/scheduler/batch/epochs/early-stop, loss + exact class-weight vector, library versions, per-fold checkpoint id, and the output schema. Optional later multi-seed sensitivity is the sanctioned stability check.

---

## 6. G2 change flags (none required)

G3 required **no change to any G2 artifact.** All G2 files are preserved unchanged. The one data-side item G3 depends on but does **not** resolve is the **Image QC gate** (verified pixel dims, channel count, SHA-256, perceptual dedup), which is already a known PENDING step in G2's `image-ingestion-plan.md` (B2/AWS-blocked) — this is a dependency, not a G2 defect, so nothing is flagged *against* G2.

---

## 7. G3 gate checklist (PASS criteria)

| # | PASS criterion | Result |
|---|---|---|
| 1 | One primary baseline chosen | ✓ MobileNetV3-Small frozen-encoder, 3-class head (`model-contract.md`) |
| 2 | Input / preprocessing contract explicit | ✓ `preprocessing-contract.md` (known-vs-assumed; pixel items marked VERIFY AT IMAGE QC GATE) |
| 3 | Augmentation explicit | ✓ `augmentation-policy.md` (baseline = hflip+vflip+90°; rest tiered) |
| 4 | Imbalance strategy explicit | ✓ weighted-CE, deterministic per-fold formula, no stacking (§1) |
| 5 | All 4 LOGO folds specified | ✓ `evaluation-protocol.md` §1 + `logo-fold-plan.csv` |
| 6 | Validation avoids case/slide-group leakage | ✓ a-priori-frozen hyperparams / no leaky patch-level val; group-aware inner val only (`evaluation-protocol.md` §2) |
| 7 | Absent-class metric behavior defined | ✓ "not estimable", never 0; weak-support tagged (§ evaluation-protocol §3) |
| 8 | Metric set frozen | ✓ PRIMARY/SECONDARY/EXPLORATORY/NOT-APPROPRIATE table |
| 9 | Aggregation strategy frozen | ✓ pooled out-of-fold predictions + per-fold spread |
| 10 | Uncertainty ranking frozen | ✓ margin + max-softmax, deterministic priority key |
| 11 | Mixed-patch handling separate | ✓ challenge-set design, tagged, not a 4th class (§2) |
| 12 | Reproducibility requirements explicit | ✓ `model-contract.md` §4 |
| 13 | Claim boundaries explicit | ✓ `claim-boundaries.md` |
| 14 | No pixels / AWS / training / deploy used | ✓ design only; nothing executed |

All 14 PASS criteria are met **as a design**.

---

## 8. Verdict: **PASS WITH LIMITATIONS**

The G3 **design is complete** — every PASS criterion is satisfied. The verdict is **PASS WITH LIMITATIONS** (not a clean PASS) because the **4-group structure materially restricts the evaluation the design can ever produce**, even though the design itself is sound:

1. **4 groups only** → LOGO is the honest ceiling; no independent fixed 3-way train/val/test exists.
2. **P9 fold (F4) is degenerate** → VIABLE_TUMOR + NECROSIS **not estimable**; its macro-F1/balanced-accuracy average only 1 class.
3. **Sparse test classes:** Case 48 NECROSIS = 2, Case 3 VIABLE = 3 → those per-class reads are **indicative only**.
4. **Case/slide-group independence, NOT patient independence** — token→patient identity unverified.
5. **Only Case 4 (F2)** gives a 3-class usable-support read, and it is still a single group.
6. **Calibration not defensible** at this scale → uncalibrated softmax is the honest default.
7. **Nested CV untrustworthy** from 4 groups → hyperparameters frozen a priori.
8. **Image QC still PENDING** (pixel dims/SHA/dedup) → preprocessing assumptions remain QC-gated; B2/AWS-blocked.
9. **No clinical-validity / generalization claim** is supportable.

The design does the honest-maximum with this data; the ceiling is the data, not the protocol.

---

## 9. Single recommended next gate

**Image QC gate** — authorize the bounded test image fetch in `../data/image-ingestion-plan.md` (resolve AWS access B2 first) to verify pixel dimensions, channel count, bit depth, decode-success, SHA-256, and perceptual duplicates, **confirming the `preprocessing-contract.md` assumptions marked VERIFY AT IMAGE QC GATE before any training**. No training until pixels are QC-verified and G3 is signed off.
