# Model card — template

**Status:** NOT TRAINED / NOT EVALUATED until actual evidence is attached. This template contains no performance result.

## Identity

Record architecture, encoder weights source/terms, trained head, library locks, seed, device, model hash, preprocessing hash, class order, source/split versions, training run IDs and owner.

## Intended use and exclusions

Educational three-class osteosarcoma patch review. Not diagnosis, treatment decision, patient-level necrosis quantification, prognosis or treatment-response prediction. Curated in-scope inputs only; uncertain and out-of-scope cases require human review.

## Training and selection

Record the approved training allowance, actual parameters/runs, data exclusions, validation selection and exact timing of test-set access. Report incomplete/failed experiments, not just the best-looking result.

## Evaluation

Actual baseline comparison, confusion counts, macro-F1, balanced accuracy, per-class precision/recall/F1/support, log loss, Brier score, grouping level and per-patient results when meaningful. Each unmeasured field reads **Not measured**. Do not invent narrow uncertainty intervals from correlated tiles.

## Scores and review policy

Record raw versus calibrated scores, validation calibration procedure and limitations, threshold version, coverage, unflagged error and error-capture results. State clearly that a high score can still be wrong.

## Explainability

Record Grad-CAM target/layer, transform alignment, actual sanity checks and known failures. Attribution is not segmentation, causal explanation or diagnostic proof.

## Deployment and operations

Record CPU/GPU runtime, warm/cold timings, cache behavior, supported input contract, error paths, version compatibility, rollback artifact and access/retention limits. These fields remain unverified until tested.

## Limitations and future work

Document independent-patient count, label ambiguity, stain/site variation, missing external validation, demographic coverage if actually available, and the separate approval needed before any retraining using human corrections.
