# Shared contract: attribution

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

Attribution is a separate evidence artifact, not a new prediction and not tissue segmentation. Metadata identifies image_id, source_image_sha256, source_prediction_id, prediction_model_hash, attribution_model_id/hash, target_a, target_b, method_version, target_layer, preprocessing_hash, dimensions, generated_at_utc, cached flag, and latency_ms. target_a and target_b are different members of the three canonical classes.

The target is the contrastive logit difference logit(A)-logit(B). The stored G4 predictions and the behaviorally reconstructed attribution model must remain explicitly distinct; do not relabel reconstructed weights as recovered original weights. Display the repository's recovery disclosure and non-segmentation disclaimer on success AND every error state.

Render an overlay only after the bytes decode and their image/model/pair identity matches the current selection. Key request state by image_id plus ordered class pair plus artifact hash; cancel or ignore outdated responses. Pair reversal changes the computation, not merely the legend. No attribution placeholder may masquerade as a computed heatmap.

EmbeddingArtifact uses encoder_id, encoder_sha256, feature_layer, preprocessing_hash, source_image_sha256, dataset_version_id, ordered image IDs, shape, dtype, and artifact_sha256. Similarity uses a compatible artifact only; score is not diagnostic probability. Exclude the query image and exact duplicate pixel hashes. A 2D projection is exploratory visualization, not a clinical cluster label or an evaluation result.
