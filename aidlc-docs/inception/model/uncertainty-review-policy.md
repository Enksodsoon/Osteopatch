# Uncertainty, review-ranking, calibration & explanation policy — G3 (OsteoPatch Review)

**Status:** G3 **design only**. No pixels, no training. Governs how the frozen 3-class model's outputs are turned into (a) a review-priority ranking, (b) a calibration stance, and (c) an explanation. Grounded in doc 02 (§Human-review selection, §Calibration, §Explanation contract) and doc 03 (UX, FR-04/05/06, SAF-03/05).

**Vocabulary rule (hard):** a softmax output is a **"model class score"** / **"model confidence score"**, never a disease probability or a certainty of a diagnosis. A score of 0.9 is *not* "90% certain the patient has this condition."

---

## 1. Baseline uncertainty score (chosen)

**Chosen baseline uncertainty signal: `top1_minus_top2 margin`** on the selected score vector, with **max-softmax (top score)** as the secondary signal — both already named by the doc 02 review rule (flag if top score < 0.70 **or** top-two margin < 0.15).

| Property | Definition |
|---|---|
| Primary score | `margin = top1_score − top2_score` on the chosen score vector (uncalibrated softmax by default; see §3) |
| Secondary score | `top_score = max_c score_c` |
| Ranking direction | **lower margin = more uncertain = higher review priority**; ties broken by lower top_score |
| Tie behavior | fully deterministic priority key (§2); a **zero margin** must still flag uncertainty (doc 08) even though canonical class order resolves the predicted-class label |
| Reviewer sees | all three class scores, the score type (UNCALIBRATED_SOFTMAX / TEMPERATURE_SCALED), the margin, and the human-readable **review reason codes** — never a single "confidence %" presented as certainty |

Entropy was considered as the single baseline signal but **not** chosen: margin + top-score map directly onto the already-specified doc 02 thresholds and the doc 08 `review_reason_codes` (`LOW_TOP_SCORE`, `CLOSE_TOP_TWO`), keeping the baseline minimal and already-contracted. Entropy stays an EXPLORATORY alternative.

## 2. Deterministic review-priority key (frozen)

Flagged images are ordered by a stable, deterministic key (doc 02):

```
sort by:  (1) quality concern first (QUALITY_FLAG)      [desc: flagged-for-quality before not]
          (2) increasing top_score                       [lower score = higher priority]
          (3) increasing top_two_margin                  [lower margin  = higher priority]
          (4) image_id                                    [final stable tiebreak]
```

Reason codes returned (doc 08 enum): `LOW_TOP_SCORE` (top < 0.70), `CLOSE_TOP_TWO` (margin < 0.15), `QUALITY_FLAG`, plus the deferral/correction reasons (`MIXED_TISSUE`, `INSUFFICIENT_CONTEXT`, `OTHER`) which are **review reasons, not model classes**. Every image remains manually reviewable regardless of flag.

**Thresholds (0.70 / 0.15) are unvalidated starting settings**, versioned (`review_policy_version`), tuned only on validation data, and labelled with which score type they apply to. A flag is **review priority, not medical urgency**. An unflagged image is **not** certified safe (confidence rules can miss confidently-wrong predictions).

### Review-policy reporting (on the evaluation set)

Report: coverage (fraction not flagged), flagged count, error among unflagged, error-capture rate among flagged, and a risk–coverage curve when support allows. **When a denominator is 0, report "unavailable", never 0 error** (directly relevant to the P9 fold and the sparse-class folds).

## 3. Calibration stance (very conservative)

| Option | Placement | Reason |
|---|---|---|
| **Raw / uncalibrated softmax** | **BASELINE (default)** | Honest default; labelled `UNCALIBRATED_SOFTMAX`. The scores the review ranking uses by default. |
| **Temperature scaling** | **SECONDARY, feasibility-gated** | Candidate validation-only method (doc 02 [S10]); fit **only inside an outer fold's training groups**, never on the held-out test. Save fitted T, the split used, and before/after log loss + Brier. **Disclose** if the same tiny split was used for selection and calibration. |
| **Platt scaling** | **NOT FEASIBLE YET** | Per-class 1-vs-rest logistic fit needs more independent calibration data than 4 groups provide. |
| **Isotonic regression** | **NOT FEASIBLE YET** | Non-parametric; badly overfits a tiny class-skewed calibration split. |

**Rule:** calibration on this 4-group data is **not defensible as a reliable probability calibrator** (G2 `split-proposal.md` §3). If temperature scaling is attempted, it is reported with its fit-on-small-split limitation; if it is not defensible, return **uncalibrated softmax labelled as such**. Raw and calibrated scores are kept **separate** (`raw_scores` vs `calibrated_scores`, `score_type`; doc 08). A calibrated 0.9 is still a model class score, not a clinical probability.

## 4. Explanation (baseline requirement chosen)

| Option | Placement | Reason |
|---|---|---|
| **Grad-CAM / CAM attribution for an explicit class** | **BASELINE REQUIREMENT** | Doc 02 §Explanation + doc 03 FR-06 require a class-targeted attribution the reviewer can toggle. It must enable gradients (an inference-only/no-gradient path must **not** silently emit an empty overlay). |
| Score-distribution display | **BASELINE REQUIREMENT** | The three class scores shown as a distribution (doc 03 FR-04). |
| Deterministic review reasons | **BASELINE REQUIREMENT** | The reason codes from §2. |
| Nearest-example (reference set) | **DEFERRED / OPTIONAL** | May come **only** from the approved training reference set with provenance; must never leak a test label through the UI. Not in the baseline. |

### Explanation wording constraints (hard)

An attribution map **highlights regions that influenced the model's score** for the labelled target class. It is **NOT**: segmentation, causal reasoning, histologic proof, nuclei/osteoid observation, or a substitute for pathologist review. Each attribution is tied to an explicit `target_class` + `model_sha256` + `image_sha256` (doc 08) and offers an unchanged original-image view. If attribution fails, display **"Attribution unavailable"** and keep review working (doc 03 NFR-03). No fabricated saliency, no stock heatmap, no invented morphology narrative (doc 03 SAF-05).

---

## 5. Reviewer language

Interface wording is Thai with English pathology terms retained (NON_TUMOR / VIABLE_TUMOR / NECROSIS kept in English; surrounding UI copy and review reasons localized to Thai). This is a UX-copy note for a later UI unit, not a model-contract change; recorded here so the eventual review UI inherits it.
