# Preprocessing / input contract — G3 (OsteoPatch Review)

**Status:** G3 **design only**. No pixels fetched. This contract SEPARATES what is **known from source** from what is a **proposed preprocessing assumption**. Every pixel-dependent item is marked **VERIFY AT IMAGE QC GATE** and must not be treated as confirmed until bytes are inspected (`../data/image-ingestion-plan.md`, still PENDING, B2-blocked).

Training-serving parity is mandatory (doc 03 NFR-05, doc 08): the exact transform frozen here, with a `preprocess_sha256`, is the one used at both train and inference.

---

## 1. Known from source (G2 / docs — do not re-derive)

| Fact | Value | Source |
|---|---|---|
| Data unit | patch image | `../data/dataset-card.md` |
| Reported dimensions | **1024 × 1024 px for all 1,144 rows** (PathDB-reported) | `../data/dataset-card.md`, audit log |
| Reported magnification | ~10× (published) | `../data/dataset-card.md` |
| Reported object format | `.tiff` tiles in PathDB (published release lists `.jpg`) — format discrepancy noted | audit log |
| Image bytes / SHA-256 / verified dims | **PENDING — no images downloaded** | `../data/dataset-card.md`, `image-ingestion-plan.md` |

**Consequence:** the 1024×1024 figure is *PathDB metadata*, not a per-file pixel measurement. It is treated as the expected dimension but **VERIFY AT IMAGE QC GATE** before any training.

---

## 2. Proposed preprocessing assumptions (frozen for the baseline, pending QC)

| Item | Proposed policy | Status |
|---|---|---|
| **Color space** | Decode to **RGB**. | proposed assumption |
| **Input dims to model** | Resize full field to **384 × 384**, **no center crop** (labels describe the predominant content of the *whole* patch, so cropping could inherit a wrong label — doc 02). | proposed assumption |
| **Interpolation** | **Bilinear** downsample 1024→384; antialias on. | proposed assumption; **VERIFY AT IMAGE QC GATE** (actual source dims) |
| **Normalization** | The **pretrained weights' documented ImageNet RGB mean/std** (mean ≈ [0.485, 0.456, 0.406], std ≈ [0.229, 0.224, 0.225]) — pinned from the exact torchvision weights enum used, not hard-copied blindly; the weights' own `transforms()` is the source of truth. | proposed assumption |
| **Scaling order** | decode → RGB → resize(384, bilinear, antialias) → to-tensor [0,1] → normalize(mean,std). Frozen order. | proposed assumption |
| **Aspect ratio / non-square** | Source is reported square (1024²). **If** a non-square image appears at QC: resize-to-square-with-defined-policy (letterbox vs stretch) must be chosen and recorded then; do **not** assume square. | **VERIFY AT IMAGE QC GATE** |
| **Alpha channel** | If a 4-channel (RGBA) image appears: composite over a defined background (white) → RGB, or reject if transparency is semantically meaningful. Decide at QC. | **VERIFY AT IMAGE QC GATE** |
| **Grayscale fallback** | If a single-channel image appears: replicate to 3 channels **only** if QC confirms it is a genuine grayscale H&E capture; otherwise flag. H&E is expected RGB, so grayscale is a QC anomaly, not a silent convert. | **VERIFY AT IMAGE QC GATE** |
| **Corrupted-image behavior** | A file that fails to decode is **rejected** with an explicit error (doc 03 SAF-03, doc 08: no fabricated zero-filled prediction). It is **never** forced into one of the 3 classes. Logged to the QC report. | proposed policy |
| **Minimum pixel dims** | Reject (or flag for review) any image below a **min decoded dimension threshold** (proposed floor: 256×256 before resize) as insufficient context; exact floor **VERIFY AT IMAGE QC GATE** against the real size distribution. | proposed assumption |
| **Bit depth** | Expect 8-bit/channel; if 16-bit tiles appear, define a documented downcast at QC. | **VERIFY AT IMAGE QC GATE** |

---

## 3. Do-not-leak rules (from doc 02 / doc 08, restated)

Model input is **pixels only**. The following are **never** model inputs: filename, source label string, folder name (`Training-Set-*`, `set*`), group token (Case 3 / P9 …), patient/subject id, annotation overlays, or any CSV target-proxy column. Children/derivatives inherit the parent split and the parent group.

---

## 4. The 384-vs-224 question

Doc 02 pins 384×384 as the initial input and marks a 224-vs-384 comparison as **optional**, consuming one approved experiment slot — **not** an automatic sweep. The baseline is **384×384**. 224 is a `SECONDARY` experiment at most (see `g3-validation-report.md`).

---

## 5. QC gate dependency (explicit)

Nothing in §2 marked **VERIFY AT IMAGE QC GATE** is confirmed. The Image QC gate (future, pixel-dependent, B2/AWS-blocked) must produce: per-file verified dimensions, channel count, bit depth, decode-success, SHA-256, and perceptual-duplicate check — **before** these assumptions become the training transform. Until then the preprocessing contract is **design-frozen but QC-pending**.
