# Mixed-patch policy — G2 (OsteoPatch Review)

**Status:** G2 offline/deterministic policy. Governs the **53** patches whose source label is `viable: non-viable`, canonicalized to review_state **MIXED_VIABLE_NECROTIC** (`trainable=false`). No pixels, no network, no AWS.

## What these 53 patches are

- Source string `viable: non-viable` = a patch the annotators marked as containing **both** viable tumor and non-viable (necrotic) tumor tissue in one tile.
- Ratified policy: **retained** in the manifest (`canonical_manifest.csv`, `review_state=MIXED_VIABLE_NECROTIC`, `trainable=FALSE`, `canonical_label` empty), **excluded** from the primary 3-class label set. **No 4th learned class is created.**
- Distribution across groups: Case 3 = 1, Case 4 = 22, Case 48 = 30, P9 = 0 (total 53).

## Hard contract (non-negotiable)

The 53 MIXED patches **must not**:

1. appear in any training portion of any fold;
2. enter the computation of any **headline** 3-class metric (confusion matrix, per-class P/R/F1, macro-F1, balanced accuracy, calibration);
3. be silently folded into VIABLE_TUMOR or NECROSIS (the published cohort folded them into Viable; we do **not** inherit that choice);
4. inflate any denominator or support count for the 3-class contract.

Any pipeline that reads `canonical_manifest.csv` filters to `trainable=TRUE` for the 3-class task. The MIXED rows are addressable only by explicit `review_state=MIXED_VIABLE_NECROTIC`.

## Permitted later uses (future units, not executed now)

1. **Error-analysis set** — inspect how the 3-class model scores inherently ambiguous tissue (expected low top-score / small top-two margin).
2. **Uncertainty challenge set** — a natural hard set to validate the review-flagging thresholds (doc 02: top-score < 0.70, margin < 0.15); MIXED patches *should* flag at a high rate if the uncertainty rules work.
3. **Review-workflow test fixtures** — exercise the human-review UI (ACCEPT/CORRECT/DEFER, MIXED_TISSUE reason code in doc 08) without touching held-out 3-class test data.
4. **Confidence / calibration inspection** — qualitative, reported separately and labelled "mixed-tissue subset", never merged into the primary calibration numbers.
5. **Future multilabel / hierarchical extension** — if a later dataset version adds a sanctioned mixed or multilabel target, these rows are the seed; that requires a new dataset version + fresh gate (doc 02 correction policy).

## Reporting rule

Whenever a MIXED-subset result is shown, it is tagged **"MIXED_VIABLE_NECROTIC subset (n=53) — excluded from the 3-class contract; shown for error analysis only."** It never shares an axis, denominator, or headline with the primary metrics.
