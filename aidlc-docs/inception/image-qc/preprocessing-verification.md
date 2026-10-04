# Preprocessing verification — Image QC gate (OsteoPatch Review)

**Status:** executed on a **bounded, deterministic QC sample of 31 images** (seed 42) drawn from the frozen `canonical_manifest.csv` (1,144 rows). Covers all 4 groups × all 3 trainable classes where available + 3 MIXED + 23 distinct source-folder-sets. Pixels inspected with Pillow 12.3.0.

**Scope limit (do not over-read):** these verdicts are for the sampled 31. "CONFIRMED" below means *confirmed on the bounded sample with zero counter-examples*; the full 1,144-image ingestion QC (`full-ingestion-qc-contract.md`) must still run before training. No G2/G3 file was edited; any contradiction would be raised as a CHANGE REQUEST (none required — see below).

Each G3 pixel-dependent assumption (from `../model/preprocessing-contract.md` §2) → QC evidence → status.

| # | G3 pixel assumption | QC evidence (sample n=31) | Status |
|---|---|---|---|
| 1 | **Decode to RGB** | 31/31 decoded as mode `RGB`, 3 channels, no palette, no CMYK/unusual colorspace. H&E eosin/hematoxylin staining visually confirmed on contact sheets. | **CONFIRMED** (sample) |
| 2 | **1024×1024 source dims** (PathDB-reported) | 31/31 measured **1024×1024** by Pillow. 0 non-square, 0 below the proposed 256² floor. | **CONFIRMED** (sample) |
| 3 | **384×384 full-field resize, no crop, bilinear+antialias** | All sources are 1024×1024 → a uniform downscale 1024→384 (factor ~2.67), no padding/letterbox needed; square→square so no aspect distortion. Full-field (no crop) consistent with whole-patch labels. | **CONFIRMED as ACCEPTABLE WITH RESIZING** (sample) |
| 4 | **ImageNet RGB mean/std normalization** | Inputs are ordinary 8-bit RGB photographic-range H&E; ImageNet-pretrained normalization is applicable (dynamic range populated, not clipped; mean intensities 170–250, typical tissue). No property blocks standard normalization. | **CONFIRMED** (sample) |
| 5 | **Square patches** | 31/31 are 1024×1024 (square). 0 non-square in sample. | **CONFIRMED** (sample) |
| 6 | **No alpha channel** | 31/31 have no alpha band (`RGB`, bands = R,G,B). 0 RGBA. | **CONFIRMED** (sample) |
| 7 | **Standard 8-bit depth** | 31/31 are 8-bit/channel. 0 16-bit, 0 `I;16`, no high-bit downcast needed. | **CONFIRMED** (sample) |
| 8 | **Ordinary decoder compatibility** | 31/31 open and fully `.load()` with stock Pillow TIFF decoder; magic bytes `II*\x00` (little-endian TIFF) match the `.tiff` extension on all 31; 0 truncation/corruption (truncated-load was disabled so corruption would surface). | **CONFIRMED** (sample) |
| — | **Grayscale fallback policy** | No grayscale image appeared in the sample, so the replicate-vs-fail-closed branch was not exercised. Policy remains as written for the full run. | **NOT EXERCISED** (no sample trigger) |
| — | **Alpha-composite policy** | No RGBA image appeared; the composite-over-white branch was not exercised. Policy remains for the full run. | **NOT EXERCISED** (no sample trigger) |
| — | **Corrupt-image reject policy** | No corrupt/undecodable file appeared; reject-with-error path not exercised on real corruption. | **NOT EXERCISED** (no sample trigger) |

## Evidence pointers
- Per-image record: `image-qc-results.csv` (format, magic, mode, channels, bit depth, dims, EXIF, content stats, hashes).
- Dimension/channel/mode/bit-depth distribution: `dimension-summary.csv`.
- Duplicate + perceptual analysis: `duplicate-analysis.csv`.
- Visual confirmation: `contact-sheets/`.

## Net result
Every pixel-dependent G3 assumption that was **testable on the bounded sample is CONFIRMED on that sample**, with zero counter-examples. No assumption was contradicted → **no CHANGE REQUEST to G2/G3 is required.** Three conditional branches (grayscale, alpha, corrupt) were not triggered by the sample and keep their frozen policy for the full ingestion run.
