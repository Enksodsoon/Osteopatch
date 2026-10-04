# Augmentation policy — G3 (OsteoPatch Review)

**Status:** G3 **design only**. No pixels. Train-only augmentations; **never** applied to validation or test, and **never** fit using test data (doc 02). The baseline is deliberately **conservative and simple**: it must preserve tissue morphology and H&E color semantics, because the label describes the predominant content of the *whole* patch at ~10×.

Classification is **PRIMARY** (in the baseline), **OPTIONAL EXPERIMENT** (approval-gated slot, secondary), or **AVOID FOR BASELINE**.

| Transform | Tier | Rationale |
|---|---|---|
| **Horizontal flip** | **PRIMARY** | Tissue has no canonical left/right orientation; morphology-preserving; standard, safe. |
| **Vertical flip** | **PRIMARY** | Same — no canonical up/down orientation in a patch; morphology-preserving. |
| **90° rotations (0/90/180/270)** | **PRIMARY** | Patch orientation is arbitrary; 90° steps are lossless (no interpolation artifacts, no border fill); morphology-preserving. Doc 02 explicitly proposes rotation in 90° steps + flips as the train-only augmentations. |
| **Arbitrary-angle rotation** | **AVOID FOR BASELINE** | Introduces interpolation blur + border fill (reflect/zeros) that alters fine nuclear/osteoid texture the classes depend on; not needed when 90° steps already cover orientation. |
| **Random crop (small region, inherit patch label)** | **AVOID FOR BASELINE** | The label is for the *predominant whole-patch* content; a small random crop may contain a different tissue type yet inherit the patch label → **label noise**. Doc 02 warns against exactly this. Full-field resize is used instead. |
| **Random resized crop** | **AVOID FOR BASELINE** | Same label-noise risk as random crop, plus scale distortion away from the ~10× the labels were assigned at. |
| **Brightness jitter** | **OPTIONAL EXPERIMENT** | Mild brightness variation models scanner/illumination differences, but H&E intensity carries signal; only a *small* range, and only as a secondary slot after visual review. |
| **Contrast jitter** | **OPTIONAL EXPERIMENT** | Same reasoning as brightness — small range, secondary, post-review. |
| **Saturation / hue jitter** | **AVOID FOR BASELINE** | H&E hue (hematoxylin blue-purple vs eosin pink) is **diagnostic signal**; perturbing hue/saturation can turn viable-looking tissue necrotic-looking and corrupt the label relationship. Only a *very* small, expert-reviewed range would ever be considered, and not in the baseline. |
| **Stain-color augmentation / stain normalization** | **AVOID FOR BASELINE** (research-tier) | Stain-space augmentation/normalization is a *research* technique (needs stain-matrix estimation, risks introducing artifacts on 4 groups). Doc 02: add modest stain/color variation **only after expert visual review**. It is `DO-NOT-DO-YET` (see `g3-validation-report.md`). |
| **Cutout / random erasing** | **AVOID FOR BASELINE** | Can erase the very region that defines the predominant class; unjustified at this data scale. |
| **MixUp / CutMix** | **AVOID FOR BASELINE** | Blends labels across classes — directly hostile to a 3-class morphology task with a separate MIXED category already carved out; would manufacture artificial mixed patches. |

## Baseline augmentation set (frozen)

**Train-only:** random horizontal flip (p=0.5) · random vertical flip (p=0.5) · random 90° rotation (uniform over {0°,90°,180°,270°}). Nothing else.

**Validation / test:** **no augmentation** — resize + normalize only (identical to the deterministic inference transform in `preprocessing-contract.md`).

## Hard rules

- Augmentation parameters are **never** tuned on test data.
- Augmentation is **train-split only**; derivatives inherit the parent split/group (no augmented copy of a held-out group's patch ever enters training).
- Any move of brightness/contrast from OPTIONAL to PRIMARY, or any stain augmentation, requires **expert visual review + an approved experiment slot** and is recorded as a separate run.
