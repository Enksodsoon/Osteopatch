# Model contract — G3 (OsteoPatch Review)

**Status:** G3 **design only**. No pixels, no AWS, no training/fine-tune, no framework install, no deploy. Everything below is a *proposed, frozen configuration*, not a measured result. Built deterministically on the frozen G2 contract (`../data/g2-validation-report.md`, `../data/split-proposal.md`, `../data/group-class-distribution.md`) and the primary design reference `docs/02_model_and_evaluation_plan.md`.

**Independence wording (hard rule):** this project claims **case/slide-group independence** over the 4 recovered groups (Case 3 / Case 4 / Case 48 / P9). The words *patient-independent*, *patient-level*, and *clinically independent* are **never** used.

**Frozen G2 contract reused verbatim:** 3 trainable classes NON_TUMOR 536 / VIABLE_TUMOR 292 / NECROSIS 263 = **1,091 trainable**; MIXED_VIABLE_NECROTIC 53 **excluded** from primary training + headline metrics (retained in manifest). Groups: Case 3, Case 4, Case 48, P9. P9 = 100% NON_TUMOR. Case 48 NECROSIS = 2, Case 3 VIABLE = 3. Evaluation = Leave-One-Group-Out (LOGO), 4 folds.

---

## 1. Primary baseline model (chosen)

**Primary = torchvision ImageNet-pretrained `MobileNetV3-Small`, encoder frozen, a newly trained 3-output linear head.** BatchNorm statistics stay frozen. Optional, approval-gated, later: unfreeze the last feature stage for a short low-LR fine-tune (a *separate* run record, not the baseline). No architecture search; one primary is picked here and frozen.

### Why this is the right baseline for *this* data

| Constraint (from G2) | Why MobileNetV3-Small frozen-encoder fits |
|---|---|
| **Tiny, grouped data (1,091 patches, 4 groups)** | A frozen pretrained encoder + a 3-way linear head trains ~a few thousand parameters, not millions. It cannot overfit 4 groups the way a from-scratch or fully-fine-tuned deep net would. |
| **Only 4 groups, LOGO eval** | The baseline must be re-fit cheaply 4× (once per outer fold). A head-only fit is seconds-to-minutes on CPU, making 4 folds + any inner validation affordable without a GPU budget. |
| **Educational / research prototype** | A small, well-documented, reproducible torchvision model is inspectable and teachable; it is explicitly *not* a disease-trained foundation model. |
| **Low compute / fast iteration** | MobileNetV3-Small is the smallest of the candidates (≈2.5M params, ≈0.06 GFLOPs at 224²); runs on CPU for a hackathon-scale demo. |
| **Needs calibrated-ish probability outputs** | A softmax head over 3 classes yields the per-class *model class scores* the review/uncertainty policy and the UX score distribution (doc 03) require. |

### Non-benchmark architecture comparison (design-time reasoning only — nothing trained)

| Candidate | Params (approx) | Why considered | Why NOT the primary baseline here |
|---|---|---|---|
| **MobileNetV3-Small** *(chosen)* | ~2.5M | Smallest; fast CPU inference; pretrained; probability head | — (selected) |
| ResNet18 | ~11.7M | Very common, robust, well-understood baseline | 4–5× the parameters; stronger tendency to overfit 4 groups when fine-tuned; heavier per-fold refit. Kept as the **one** optional secondary comparison if a sanity check is wanted. |
| EfficientNet-B0 | ~5.3M | Good accuracy/compute trade-off, pretrained | More params than MobileNetV3-Small, compound-scaling complexity buys nothing at this data scale; slower CPU inference. |
| A small modern ConvNet (e.g. ConvNeXt-Tiny) | ~28M | Modern design, strong ImageNet | Far too large for 4 groups; designed for large-data regimes; overkill and overfit-prone here. |

**Decision:** one primary (MobileNetV3-Small, frozen encoder). ResNet18 is the *only* sanctioned optional secondary comparison, and only as an approval-gated experiment slot (see `g3-validation-report.md` experiment tiers). This is a baseline, not a benchmark; ImageNet accuracy is explicitly **not** pathology performance.

---

## 2. Training configuration (frozen a priori — from doc 02, restated, not re-decided)

Hyperparameters are **frozen a priori** rather than searched, because nested CV over 4 groups cannot yield trustworthy tuning (G2 `split-proposal.md` §3). The locked starting configuration:

| Setting | Value | Note |
|---|---|---|
| Encoder | MobileNetV3-Small, ImageNet-pretrained, **frozen** | BatchNorm frozen |
| Head | global-pooled embedding → linear(→3) | canonical order NON_TUMOR 0 / VIABLE_TUMOR 1 / NECROSIS 2 |
| Input | RGB, 384×384, no center crop (full-field resize) | see `preprocessing-contract.md`; dims **VERIFY AT IMAGE QC GATE** |
| Normalization | the pretrained weights' documented ImageNet RGB mean/std | pinned, see `preprocessing-contract.md` |
| Optimizer | AdamW | |
| Head LR | 1e-3 | |
| Weight decay | 1e-4 | |
| Batch size | 16 | reduce only if memory profiling requires |
| Head budget | ≤10 epochs, early-stop on validation macro-F1, patience 3 | per outer fold |
| Loss | cross-entropy, optional **train-only** inverse-frequency class weights normalized to mean 1 | see `g3-validation-report.md` §imbalance |
| Optional fine-tune | ≤5 epochs, LR 1e-5, **separate run record** | approval-gated; not the baseline |
| Seed | 42 (one seed ≠ stability; see §4) | |
| Paid/accelerated jobs | **disabled** until a separate explicit compute/budget approval | |

These values are a *starting plan*, not a runtime or accuracy promise. A per-job wall-time cap must be proposed from machine profiling **before** any training (future gate).

---

## 3. Model selection: per-fold models vs the eventual final demonstration model

Two distinct kinds of fitted model exist in this design, and they must never be confused:

1. **Per-fold evaluation models (4 of them).** One MobileNetV3-Small head is fit per LOGO outer fold on that fold's 3 training groups, and scored *only* on the held-out group it never saw. Their pooled/aggregated held-out scores are **the evaluation result** (`evaluation-protocol.md`). Each per-fold model is discarded after its held-out scoring is recorded; it is never shown to a user.
2. **The eventual final demonstration model (0 of them now).** *After* the evaluation is frozen and reported, a *single* final model may be fit on **all eligible trainable groups** for the demo/UX. Its own training-set performance is **never** reported as evaluation performance — the honest performance statement for the demo model is the frozen LOGO evaluation, carried over as an estimate with all its limitations. Fitting it is a **future, approval-gated** step; **nothing is trained now**.

**Rule:** the number printed on the model/dataset card as "performance" comes from the LOGO evaluation of the per-fold models, not from the final demo model's own fit.

---

## 4. Reproducibility requirements (what a future training run MUST record)

A future training/evaluation run is reproducible only if it records **all** of:

- **Data provenance:** canonical manifest version + hash (`canonical_manifest.csv`), dataset_version (`v2`), label-policy hash (`label_aliases.json`).
- **Fold assignment:** the exact group→(train/val/test) mapping for every fold (from `logo-fold-plan.csv`), split_version, and the verified grouping level ("case/slide-group").
- **Seed:** the single seed (42) **and** an explicit note that one seed ≠ stability.
- **Architecture:** `mobilenet_v3_small`, head shape (→3), which stages are frozen.
- **Pretrained weights identity:** the torchvision weights enum/version + its documented preprocessing + a weights file hash.
- **Preprocessing:** the frozen `preprocessing-contract.md` values actually used (dims, interpolation, normalization), plus a `preprocess_sha256`.
- **Augmentation:** the exact `augmentation-policy.md` transforms + their parameters actually applied (train-only).
- **Optimization:** optimizer (AdamW), LR (head 1e-3 / fine-tune 1e-5), scheduler (if any), weight decay, batch size, epochs, early-stop rule + patience, loss, class-weight vector (the exact numbers, see `g3-validation-report.md`).
- **Environment:** library versions (torch, torchvision, numpy, pillow, scikit-learn), device, OS.
- **Outputs:** checkpoint id/hash per fold, the output schema (`raw_scores` all 3 classes, `score_type`, canonical order), and the full per-fold + aggregate evaluation outputs.

**One seed is not stability.** A later, optional, approval-gated **multi-seed sensitivity** (e.g. 3–5 seeds, report spread of macro-F1) is the sanctioned way to show the baseline is not a single lucky draw. It is **DO-NOT-DO-YET** at this scale unless explicitly approved.

---

## 5. What this contract does NOT authorize

No pixel access, no AWS, no training/fine-tuning, no framework (torch) install, no infra, no deploy, no UI, no architecture search, no automated hyperparameter sweep, no foundation-model download, no ensemble, no segmentation/radiomics fusion. Any of these requires a new gate. If a step here is found to need a change to a **G2** artifact, it is **FLAGGED** in `g3-validation-report.md`, never edited into G2.
