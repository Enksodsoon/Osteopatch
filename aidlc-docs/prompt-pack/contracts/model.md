# Shared contract: model

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

Keep separate evidence modes: frozen historical out-of-fold evaluation; current prototype predictions; human reviews; candidate-model experimental runs. Every artifact has a run_id, code_sha, dataset_version_id, split_manifest_sha256, preprocessing_hash, weights_sha256, class_order, seed, and output hash. Never update the frozen G4 evidence or its stored predictions during a feature task.

Current grouping evidence is case/slide-group independent, not verified patient independent. Never use random patch splits across related groups. Split assignment happens before fitting preprocessing, feature selection, calibration, model choice, or thresholds. All transformations learn from training partitions only; calibration uses disjoint permitted partitions. Test labels are not used to pick hyperparameters, operating points, epochs, or examples claimed to be representative.

MetricResult fields: metric_name, value nullable, denominator/support, class_label nullable, reference_kind, prediction_kind, split_id, n_groups, group_kind, excluded_rows_by_reason, unavailable_reason, estimator_version, evidence_path/hash. An absent-class recall is null, not zero. Counts and matrices show denominators and fixed class order. Confidence intervals need an explicit defensible grouped resampling protocol; four groups do not justify a confident generalization claim.

InferenceJob state machine: queued -> running -> succeeded|failed|cancelled. Artifacts publish atomically only after checksums, finite three-class scores, row identities, and row-count checks pass. CPU default, bounded worker count, no web-process torch dependency. A queued or partly written file is not a completed prediction artifact.

Research-later tasks may build infrastructure and test it on labeled synthetic unit fixtures. Actual new training, foundation-model downloads, calibration fitting, model promotion, or cloud compute need their own data/license/budget approval. Passing a fixture test is not successful scientific validation. Corrected labels are curated candidates only; there is no automatic retraining.
