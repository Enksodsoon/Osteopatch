# OsteoPatch — Full-Collection Image Ingestion QC Report

Generated: 2026-10-03T15:02:31.149416+00:00
Gate: Full-Collection Image Ingestion QC (resumed). Scope: QC only — no training, no AWS, no S3, no SageMaker, no deploy.

## 1. Reconciliation (all 1,144 rows)
- Manifest rows (source of truth): **1144**
- Retrieved: **1144** · Retrieval-failed (terminal): **0** · Missing from ledger: **0**
- Duplicate manifest IDs: 0 · duplicate PathDB IDs: 0 · duplicate URLs: 0 · unexpected extra local files: 0
- **Every manifest row has exactly one terminal retrieval + QC state. No unexplained difference.**

## 2. Retrieval
- Route: credential-free PathDB HTTP→HTTPS (301) GET. All fetches 200. Two rows initially hit a Windows rename lock (`WinError 32`, not an HTTP failure); both were re-fetched cleanly and are RETRIEVED.
- Final: 1,144/1,144 RETRIEVED, 0 persistent failures.

## 3. Decode QC
- Decoded OK: **1144/1144** · decode failures (CORRUPT): **0**
- Truncated-image loading disabled (truncation would surface as failure). Format verified by magic bytes.

## 4-7. Format / dimension / channel / bit-depth distributions (full collection)
- Format (by content): {'TIFF': 1144} · Magic: {'TIFF-LE': 1144}
- Dimensions: {'1024x1024': 1144}
- Mode/channels: {'RGB': 1144}
- Bit depth: {'8': 1144}
- **Full-dataset preprocessing status: CONFIRMED** — every image is 1024×1024 RGB 8-bit TIFF-LE, matching the frozen G3 preprocessing contract (1024→384 bilinear antialias, no crop; ImageNet-norm). 0 exceptions requiring a G3 change.

## 8. Content QC (non-semantic signals)
- Flag tallies: {'NEAR_BLANK': 23, 'LOW_INFORMATION': 59, 'VERY_BRIGHT': 8, 'LOW_VARIANCE': 1}
- These are QC signals only (never pathology). Content-flagged rows go to REVIEW, never auto-deleted.

## 9. Byte-exact duplicates
- Byte-identical groups: **0** (0 → no byte-exact duplicates in the full collection).

## 10. Pixel-identical duplicates
- Pixel-identical groups (decoded-RGB SHA-256): **0** (0 → no metadata-independent pixel duplicates).

## 11. Perceptual near-duplicate screen
- pHash (+dHash) across all decoded images; candidate pairs at Hamming ≤ 10: **3**.
- Second-stage pixel confirmation (pixel MAD/255) run on all cross-group/cross-label/high-sim candidates. None reached pixel-equivalence (MAD < 2.0). Perceptual similarity alone is NOT treated as duplication.
- Pairs:
  - hd=10: `Case-3-A12-12706-7126` [Case-3/NECROSIS] ↔ `Case-3-A16-12753-7173` [Case-3/NECROSIS] (same-group same-label; not pixel-confirmed)
  - hd=10: `Case-4-C24-36061-11151` [Case-4/VIABLE_TUMOR] ↔ `Case-4-C28-36010-11166` [Case-4/VIABLE_TUMOR] (same-group same-label; not pixel-confirmed)
  - hd=10: `Case-48-P5-C25-44980-18952` [Case-48/NON_TUMOR] ↔ `P9-B27-21147-30384` [P9/NON_TUMOR], pixel_MAD=18.844

## 12. Cross-group leakage audit (Case-3 / Case-4 / Case-48 / P9)
- Confirmed/blocking cross-group duplicates: **0**.
- Findings table: `cross-group-leakage-audit.csv`.
- The single cross-group perceptual pair (`Case-48-P5-C25-44980-18952` ↔ `P9-B27-21147-30384`, pHash hd=10, pixel MAD≈18.8/255) is a **visually-similar-but-distinct** H&E pair — classified `UNCONFIRMED_PERCEPTUAL_SIMILAR`, held in REVIEW, **does NOT block the training gate**.

## 13. Label-conflict audit
- Identical/near-identical pairs carrying conflicting labels: **0** (0 → no label conflicts on identical data).

## 14. Primary QC status (every row has exactly one)
- {'PASS': 1081, 'REVIEW': 59, 'NEAR_DUPLICATE_CANDIDATE': 4}
- PASS = pixel-level QC permits later use; it does NOT assert clinical revalidation, biological-sample independence, patient-level independence, or clinical suitability.

## 15. training_eligible (deterministic)
- Eligible by class: {'NON_TUMOR': 484, 'NECROSIS': 254, 'VIABLE_TUMOR': 290} · **Total eligible: 1028**
- Excluded: {'unresolved_review': 59, 'duplicate': 4, 'mixed': 53} (53 MIXED always ineligible by policy; 59 content-REVIEW; 4 near-dup candidates). Every `false` carries an explicit reason in `training-eligibility-summary.csv` / `full-image-qc-results.csv`.

## 16. No LOGO break
- No train/val/test folders created; no image copied into fold dirs. The eligibility manifest is the single canonical source future training consumes; fold assignment comes later from the frozen G3 case/slide-group LOGO protocol.

## 19. Count reconciliation
- Source total 1,144 = NON_TUMOR 536 + VIABLE_TUMOR 292 + NECROSIS 263 + MIXED 53.
- Retrieval: 1,144 success + 0 fail. Decode: 1,144 success + 0 corrupt.
- QC: PASS 1081 + REVIEW 59 + NEAR_DUP 4 = 1,144.
- Eligibility: 1028 eligible + 116 excluded = 1,144. ✓

## 20. Comparison to the 31-image bounded sample
- Bounded sample anticipated the full collection accurately: 100% TIFF-LE / 1024² / RGB / 8-bit held across all 1,144 (0 exceptions). The bounded gate's "0 exact/pixel/perceptual/cross-group confirmed dups" also held. The full collection surfaced more content-REVIEW outliers (23 near-blank, 59 low-information) than the 31-image subset (2 near-blank), as expected from the larger draw — not a missed exception or a design error.

## 21. G2/G3 change control
- **No G2/G3 change request required.** Full-collection evidence confirms the frozen G2/G3 preprocessing and split assumptions.

## Disk / footprint
- Scratch TIFF footprint: **288.3 MB** (288303026 bytes), well under the 1 GB soft cap. TIFFs remain in scratch only; none copied into the project tree or Git.

## Verdict
- **PASS WITH LIMITATIONS** — the collection is structurally sound and suitable for the next gate; 59 content-REVIEW + 4 near-dup-candidate rows are intentionally left unresolved and excluded from training_eligible pending human review (QC-012-style outliers). No structural failure: no manifest mismatch, no widespread retrieval failure, no corruption, no incompatible formats, no confirmed cross-group leakage, no label conflicts on identical data.
