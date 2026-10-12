# Shared contract: analytics

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

Use one immutable AnalyticsSnapshot per response: schema_version="1", snapshot_id, generated_at_utc, scope, definitions_version="review-v1", counts, rates, warnings, and provenance. scope contains project_id, dataset_version_id, model_bundle_hash, review_session_id, deployment_subset, and reference_kind. It must describe the actual included rows, not the entire collection when a 50-image allowlist is active. One explicit prediction per image; latest review events only unless a metric is explicitly event-based.

counts: total_images, prediction_images, unreviewed_images, decided_images, deferred_images, accepted_images, corrected_images, disagreement_images, qc_flagged_images, touched_images. decided = latest ACCEPT or CORRECT. touched = decided + deferred. Disagreement is effective human label != the reviewed prediction's class, NOT merely action == CORRECT. Legacy redundant corrections must not inflate disagreement. Predictionless images remain visible but are excluded from prediction-agreement denominators.

Each rate is {value: number|null, numerator: int, denominator: int, unavailable_reason: string|null}. review_completion = decided/total_images; touched_fraction = touched/total_images; reviewer_agreement = agreeing valid decided predictions/valid decided predictions; correction_action_rate = corrected/decided; defer_fraction = deferred/touched. Event counts and distinct-image counts have different labels. No denominator -> null.

Hand-check fixture: eight images with one prediction each; two latest ACCEPTs, one genuinely different CORRECT, two latest DEFERs, and three never reviewed. Expected counts: total=8, decided=3, touched=5, deferred=2, unreviewed=3, corrected=1, disagreement=1. Completion=3/8; agreement=2/3; correction=1/3; defer fraction=2/5. Add an old event on one image: current-state counts must remain unchanged. These are test values, NEVER production dashboard constants.

Reviewer agreement is operational concordance, not model accuracy or reference-standard validation. Evaluation metrics must come from separate frozen held-out evidence. Prediction-class frequencies over sampled patches are not tissue area fractions or clinical percent necrosis. Selection-biased review data cannot establish triage benefit. Keep source labels, individual reviews, adjudicated labels, and held-out reference labels separately identified.

Current-state counts use the latest applicable event for each selected image/prediction/session. Reviews linked only to another model are preserved in a separate unmatched_review_images warning/count and are excluded from this model’s agreement/decided denominator; the selected-model state remains unreviewed until reviewed. This must be tested with two model versions for the same image.
