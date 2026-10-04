# 02 — Model, evaluation and uncertainty plan

**Everything numerical below is a proposed experimental configuration or acceptance target, not a measured result.** Primary references are [S04–S06, S09–S11] in [the source register](07_sources_and_reuse_register.md).

## Small, reproducible first model

Use a torchvision **MobileNetV3-Small ImageNet-pretrained encoder** with a newly trained three-output linear head. This is an image classifier—not an LLM and not a model already trained for this disease. Official torchvision provides the architecture/weights [S09]. Its ImageNet performance is not pathology performance.

Start with a frozen feature extractor and train only the head. Keep frozen BatchNorm statistics fixed. If validation evidence warrants it and the experiment allowance permits, unfreeze the last feature stage for a short, low-learning-rate fine-tune. Do not begin with a foundation-model download, radiomics fusion, segmentation network, large ensemble or automated hyperparameter sweep.

Compare a majority-class baseline, the frozen-encoder classifier, and at most one fine-tuned candidate. A more elaborate hierarchical classifier is an optional later experiment, not a hackathon prerequisite.

## Proposed initial configuration

| Setting | Initial proposal |
|---|---|
| Input | RGB full patch resized to 384 × 384; no center crop |
| Normalization | Pinned pretrained encoder's documented RGB normalization |
| Head | Global pooled embedding → linear layer with 3 outputs |
| Reproducibility | Seed 42; record libraries, weights ID/hash, data/split hashes and device |
| Training | AdamW; head learning rate 0.001; weight decay 0.0001 |
| Batch size | 16, reduced only if memory profiling requires it |
| Head budget | At most 10 epochs; early stop on validation macro-F1, patience 3 |
| Optional fine-tune | At most 5 epochs; learning rate 0.00001; separate run record |
| Loss | Cross-entropy; optional train-only inverse-frequency class weights normalized to mean 1 |
| Experiments | One head run plus at most one fine-tuning run; expansion requires approval |
| Paid jobs | Disabled until a separate explicit compute/budget approval |

Kiro must profile the available machine and propose a per-job wall-time cap before training. These settings are a starting plan, not a promise of runtime or accuracy. A 224-versus-384 comparison is optional and consumes an approved experiment slot; it is not an automatic extra sweep.

Because labels describe the predominant content of the complete patch, randomly cropping a small region and inheriting its label may be misleading. Use full-field resizing initially. Rotation in 90-degree steps and horizontal/vertical flips are proposed train-only augmentations. Add modest stain/color variation only after expert visual review. Never fit normalization or augmentation parameters using test data.

## Split and leakage policy

The unit of independence is the patient whenever verified metadata permits it. Before training, produce a patient × class count table and a split diagram/table with every source image assigned exactly once.

A small first experiment may use **two patients for training, one for validation, one for locked testing**, but only if the verified class support makes that design defensible. Approve the exact patient assignment and seed before model selection. Do not force an impossible split or silently relocate test images to fix missing classes.

Where this split is unsuitable, propose a grouped evaluation design. A later leave-one-patient-out assessment has four outer folds; any tuning/calibration must remain inside each outer training portion. Its extra runs require a revised compute budget. Patient-based folds must not be disguised as independent thousands-of-image cohorts.

If no trustworthy patient map exists, a slide-grouped or deduplicated image split can support an **exploratory workflow demo only**. Display “Patient-level independence unverified.” Do not report it as clinical/general-population validation.

All derivative images inherit the parent split. Do not use filenames, source label strings, folder names, patient IDs, annotation overlays or CSV target proxies as model inputs. Split checks must assert zero patient overlap when patient-level evaluation is claimed, zero source-image overlap, and no known duplicate clusters across splits.

A January 2026 preprint on this dataset reports substantially poorer results with independent patient-level testing than suggested by tile-level evaluation [S06]. This supports treating split validity as a central project risk, not copying an attractive accuracy number.

## Selection, calibration and reporting

Select a candidate using validation macro-F1, with per-class recall, class support and deployment latency also inspected. Freeze weights, preprocessing, threshold configuration and the selected candidate before evaluating the locked test set. A poor test result is reported, not used to silently select a different run.

Report confusion matrices with counts; macro-F1; balanced accuracy; per-class precision/recall/F1 and support; log loss; and multiclass Brier score. Define Brier score as the mean over images of the sum of squared class-probability errors. Report undefined class metrics as unavailable with the reason rather than treating an absent class as a successful result. Accuracy may be included but is not the headline by itself.

Report per-patient results where available and explain the very small number of independent patients. Do not bootstrap images as if they were independent patients to manufacture narrow confidence intervals. A four-patient cohort cannot support a strong generalizability claim.

Temperature scaling is a candidate validation-only calibration method [S10], not a guarantee of reliable clinical probabilities. Save its fitted temperature, validation split, before/after log loss and Brier score. If the same small validation set is used for both model selection and calibration, disclose that limitation. If calibration is not defensible, return uncalibrated softmax scores and label them as such.

Keep raw and calibrated scores separate. Never label a score of 0.9 as “90% certain the patient has this condition.” It is a model output for the supplied patch under the evaluated task.

## Human-review selection

Provisional demonstration rules: flag a valid image when top-class score is below **0.70**, or the top-two margin is below **0.15**. These are unvalidated starting settings. Tune only on validation, version the thresholds and state which score type they use. Every image remains reviewable regardless of flag.

Sort flagged images by a deterministic priority key: quality concerns first, then increasing top score, then increasing top-two margin, then image ID. Return reason codes and human-readable descriptions; ties must be stable. A flag indicates **review priority, not medical urgency**.

Report coverage (fraction not flagged), flagged count, error among unflagged images, and error-capture rate among flagged images on the evaluation set. Provide a risk–coverage table/curve when there are enough examples. When the denominator is zero, return unavailable, not zero error. Confidence rules may miss confidently wrong predictions; never claim that an unflagged image is safe.

Quality flags are heuristics, not validated out-of-distribution detection. Restrict the first release to curated in-scope images. Reject corrupt/non-image input instead of forcing it into one of three classes.

## Explanation contract

Show three distinct things: the score distribution; a Grad-CAM attribution for an explicit class; and deterministic review reasons. Grad-CAM visualizes model attribution [S11], not segmentation, causal reasoning or diagnostic proof. Label the target class, model version and transform, and offer an unchanged original-image view.

Do not generate fake saliency images, infer nuclei/osteoid observations from a class label, or use generic stock heatmaps. The attribution path must enable gradients; an inference-only/no-gradient context must not silently produce an empty overlay. If attribution fails, display “Attribution unavailable” and preserve review functionality.

Optional educational class descriptions are static, cited, expert-reviewed context, not image-specific evidence. Optional nearest examples may come only from the approved training reference set with provenance; never leak test labels through the explanation UI.

## Model artifacts and correction policy

Export weights, `label_map.json`, `preprocess.json`, `calibration.json`, `review_policy.json`, `model-card.md`, training configuration, data/split checksums, run logs and evaluation outputs. ONNX is optional; require numeric parity tests before selecting it as the runtime.

Human corrections append events linked to the original model prediction. They do not replace the source label or become automatic ground truth. Any future retraining needs expert adjudication, a new dataset version and a fresh evaluation decision; held-out examples stay protected from training leakage.
