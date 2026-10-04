# Image QC gate report — OsteoPatch Review

**Date (UTC):** 2026-10-03 · **Gate:** Image QC (bounded sample) · **Scope:** QC only — no training, no AWS/S3, no deploy, no full-collection download, no edits to frozen G2/G3.

**Environment:** isolated scratch venv at `C:\Users\enkso\.kiro\crew\scratch\runtime-64fa3dc5\osteopatch-qc\.venv` (CPU, credential-free). Python 3.12.10 · pandas 3.0.6 · requests 2.34.2 · pillow 12.3.0 · imagehash 4.3.2 · numpy 2.5.3. QC images in an isolated dir **outside** the project tree: `C:\Users\enkso\.kiro\crew\scratch\runtime-64fa3dc5\osteopatch-qc\qc_sample\`.

---

## VERDICT: **PASS WITH LIMITATIONS**

The bounded PathDB route works end-to-end; every sampled object has deterministic 1:1 manifest provenance; all sampled files decode reliably; dimensions / channels / bit-depth / format are characterized; the 384×384 assumption is supported; duplicate + corruption/blank checks ran; **no cross-group leakage signal** in the sample; full-ingestion QC rules are explicit. **Limitation:** this is a 31-image bounded sample, not the full 1,144-image collection — **full-collection ingestion QC (`full-ingestion-qc-contract.md`) is still required before any training.** Verdict is PASS WITH LIMITATIONS, not PASS, for that reason alone — no FAIL condition (unstable URLs / widespread decode failure / manifest mismatch / material cross-group duplicates / unsupported properties) was observed.

---

## Method
Deterministic bounded sample (seed 42) of 31 rows from `canonical_manifest.csv`, covering all 4 groups × all 3 trainable classes where available + 3 MIXED + 23 distinct `source_folder_set` values (`qc-sample-manifest.csv`). Each tile fetched over plain HTTP (per-file cap 25 MB, total cap 400 MB), recording HTTP status / content-type / content-length / byte size / SHA-256. Decoded via Pillow (magic bytes, not extension), extracting format / dims / channels / mode / bit-depth / alpha / EXIF, content statistics, byte+pixel exact-dup hashes, and pHash/dHash perceptual hashes.

## Findings

### PathDB retrieval
- **31/31 retrieved and decoded = 100% success.** HTTP→HTTPS 301 redirect then 200 on all; `Content-Type: image/tiff`; **no `Content-Length` (chunked, `Transfer-Encoding: chunked`)** as expected; `Accept-Ranges: bytes`. No retries needed. No failures to report.
- Total downloaded: **7.69 MB** across 31 tiles (max single file well under the 25 MB per-file cap; total far under the 400 MB cap — **no abort**).

### Format & decodability
- **100% TIFF little-endian** (magic `II*\x00`), extension `.tiff` matches detected magic on all 31. Stock Pillow TIFF decoder: 31/31 full `.load()` success, 0 truncation/corruption (truncated-image loading was disabled so corruption would surface).

### Dimensions — 384×384 decision
- **31/31 are exactly 1024×1024** (confirms the PathDB-reported figure as a per-file pixel measurement on the sample). Full distribution: `{1024x1024: 31}`.
- **384×384 = ACCEPTABLE WITH RESIZING (CONFIRMED on sample).** All sources square 1024² → uniform bilinear+antialias downscale 1024→384 (~2.67×), no crop, no padding, no aspect distortion. The frozen G3 full-field resize policy is appropriate.

### Channels / color / bit depth
- **31/31 RGB, 3 channels, no alpha, no palette/grayscale.** 8-bit/channel on all. H&E eosin/hematoxylin staining visually confirmed (contact sheets). → **RGB→tensor→ImageNet-norm is safe**; mean intensities 135–239 (photographic range, no clipping/narrow-range anomaly). Alpha and grayscale branches were not triggered (none present).

### Content QC (non-semantic)
- 29/31 OK. **2 flagged for human review (not deleted):** `QC-006` (Case-3, NON_TUMOR; entropy 2.63 — small tissue fragment on white, acceptable) and `QC-012` (Case-4, NON_TUMOR; 94.7% near-white, entropy 1.72 — near-empty). Both are NON_TUMOR, so pale/sparse content is plausible; neither is corrupt or non-histology.

### Duplicates & leakage
- **Exact byte duplicates: 0. Pixel-identical duplicates: 0.**
- **Perceptual near-duplicate candidates (pHash/dHash Hamming ≤ 10): 0 pairs.** → **No cross-group or cross-label near-duplicate leakage signal in the sample.** (Full-collection perceptual clustering still owed at ingestion.)

### Manifest integrity
- 31/31 objects map 1:1 to their `canonical_manifest.csv` row by `image_id`; URL/filename/id reconcile; the only redirect is the expected HTTP→HTTPS 301. 0 mismatches.

### Label plausibility (visual only — never relabeled)
- 1 entry marked **REQUIRES HUMAN REVIEW**: `QC-012` (near-blank NON_TUMOR). No relabeling performed. See `label-plausibility.csv`.

### G2/G3 contract
- **No contradiction found → no CHANGE REQUEST required.** All G2/G3 files preserved unedited. Every testable G3 pixel assumption is CONFIRMED on the sample (`preprocessing-verification.md`).

---

## Storage report (TASK 16)
- Images downloaded: **31** (`.tiff`). Total image bytes: **7.69 MB**.
- Retained: all 31 (kept for reproducibility of this gate). Exact QC dir: `C:\Users\enkso\.kiro\crew\scratch\runtime-64fa3dc5\osteopatch-qc\qc_sample\`.
- No originals copied into the docs tree; only small derived PNG contact sheets live under `aidlc-docs\...\contact-sheets\`. No extra confidence-downloads taken.

---

## RETURN (15 items, actual values)
1. **# sampled:** 31 (of 1,144) — 4 groups × 3 trainable classes where available + 3 MIXED + 23 folder-sets.
2. **PathDB success rate:** 31/31 = **100%**.
3. **Formats:** 100% TIFF little-endian (`II*\x00`); extension matches magic on all.
4. **Dimensions:** 100% **1024×1024** (0 non-square, 0 under 256² floor).
5. **Channels + bit depth:** 100% 3-channel RGB, no alpha, **8-bit/channel**.
6. **384×384 decision:** **ACCEPTABLE WITH RESIZING** (confirmed) — uniform 1024→384 bilinear+antialias, no crop/pad/distortion.
7. **Decoder compatibility:** stock Pillow TIFF decoder, 31/31 full load, 0 corrupt/truncated.
8. **Blank/outlier count:** 2 flagged (QC-006, QC-012), both NON_TUMOR, human-reviewable, not deleted.
9. **Exact-duplicate count:** 0 byte-identical, 0 pixel-identical.
10. **Near-dup candidates:** 0 pairs (pHash/dHash ≤ 10).
11. **Cross-group leakage concern:** none detected in the sample.
12. **Preprocessing assumptions:** all 8 testable G3 pixel assumptions CONFIRMED on sample; 0 rejected; 3 conditional branches (grayscale/alpha/corrupt) not triggered. No CHANGE REQUEST.
13. **Gate verdict:** **PASS WITH LIMITATIONS** (sample supports proceeding; full-collection QC still required before training).
14. **Files created:** see list below.
15. **Recommended next gate:** **Full-collection image ingestion QC** — run `full-ingestion-qc-contract.md` over all 1,144 objects (resumable, cached, byte+pixel+perceptual dedup, status-per-image) on an authorized host; promote only `PASS` images before the training gate.

## Files created (absolute paths)
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\qc-sample-manifest.csv`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\image-qc-results.csv`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\dimension-summary.csv`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\duplicate-analysis.csv`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\label-plausibility.csv`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\preprocessing-verification.md`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\full-ingestion-qc-contract.md`
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\image-qc-report.md` (this file)
- `C:\Users\enkso\.kiro\crew\workspace\osteopatch\OsteoPatch_Kiro_Handoff\aidlc-docs\inception\image-qc\contact-sheets\` (10 PNG sheets: by-class ×4, by-group ×4, mixed-examples, flagged-outliers)

**No training, no AWS/S3, no deploy, no full-collection download, no G2/G3 edits were performed.**
