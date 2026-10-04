Using AI-DLC, continue only U2. Read the approved data/split gate, docs/02_model_and_evaluation_plan.md and the relevant contracts. Obtain the unit code-generation and compute approvals; local approval does not authorize a paid cloud job.

Build the bounded MobileNetV3-Small frozen-encoder baseline with explicit class order and matching full-patch training/serving preprocessing. Implement model-contract tests before training. Profile available hardware and set an approved per-run stop limit. At most the approved head run and optional fine-tune may execute; do not sweep models or copy published accuracy claims.

Select/calibrate on validation only, freeze the choice and review policy, then evaluate the locked test set. Report actual metrics, class support, calibration limits, failures and whether patient independence was verified. A disappointing result is not permission to tune against the test set.

Export the real model bundle, data/split hashes and model card; verify one real inference. Present G3 with exact evidence and limitations. Do not deploy or proceed to UI implementation automatically. Update state/audit and stop.
