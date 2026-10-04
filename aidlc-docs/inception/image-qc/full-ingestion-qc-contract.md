# Full-ingestion QC contract — future complete-collection ingestion (OsteoPatch Review)

**Status:** deterministic rules for the FUTURE full 1,144-image ingestion QC. **Not executed here** (this gate ran a bounded 31-image sample only). No training, no AWS, no bulk download authorized by this document. Derived from the bounded QC findings + the frozen `../model/preprocessing-contract.md`.

Every future exclusion MUST be an **explicit QC state**, never a silent drop. Statuses:
`PASS` · `REVIEW` · `CORRUPT` · `EXACT_DUPLICATE` · `NEAR_DUPLICATE_CANDIDATE` · `MANIFEST_MISMATCH`.

## 1. Selection / provenance
- Drive the fetch list from `canonical_manifest.csv` (`image_id`, `image_url`) — never directory crawling.
- Each object maps to exactly one manifest row by `image_id`. A fetched object whose id/filename/URL does not reconcile 1:1 → `MANIFEST_MISMATCH` (never force-matched).

## 2. Retrieval rules
- Plain HTTP(S) GET, follow the HTTP→HTTPS 301 redirect (observed). Credential-free. No browser automation, no AWS.
- `Content-Length` is usually absent (chunked) — enforce the **per-file 25 MB cap** by counting streamed bytes and aborting the file if exceeded (record size, status `REVIEW`, do not force).
- Enforce a **standing total footprint cap** for the run; inspect/track cumulative bytes; abort+report if the cap would be exceeded.
- **Conservative retry** (≤3, backoff) on transient errors. A persistent non-200 → status `REVIEW` with the HTTP code, stays visible.
- **Resumable, idempotent cache keyed by `image_id`**: a present file whose SHA-256 matches the recorded value is skipped (no re-download). A partial/failed file is re-fetched, never half-counted.

## 3. Format & decodability
- **Allowed formats:** TIFF (little-endian `II*\x00` or big-endian `MM\x00*`), verified by **magic bytes, not extension**. Observed sample: 100% TIFF-LE.
- Decode must fully `load()` with the stock Pillow TIFF decoder (truncated-image loading DISABLED so truncation surfaces as failure).
- Undecodable / truncated / magic-mismatch-to-nonimage → `CORRUPT`. Never forced into a class, never zero-filled.

## 4. Expected pixel properties (reject/flag deviations explicitly)
| Property | Expected (from sample) | Deviation handling |
|---|---|---|
| Channels / mode | 3-channel RGB | RGBA → composite over white per preprocessing contract, status `REVIEW`; grayscale → `REVIEW` (confirm genuine H&E before replicate), never silent convert; palette/CMYK → `REVIEW`. |
| Dimensions | 1024×1024 square | non-square or < 256² floor → `REVIEW` (choose letterbox vs stretch explicitly; record). |
| Bit depth | 8-bit/channel | 16-bit → `REVIEW` with a documented downcast, never silent. |
| EXIF/orientation | none meaningful observed | if an orientation tag is present, apply deterministically and record. |

## 5. Dimension handling
- Record verified `width`/`height` per file. The frozen transform is full-field resize 1024→384 (bilinear, antialias, no crop). Any image not 1024² gets its resize path recorded as a QC note (status `REVIEW` if a policy choice is forced).

## 6. Hashing + duplicates
- Compute **byte SHA-256** on every file (write to `image_sha256`).
- Compute a **pixel SHA-256** on the deterministically decoded RGB array (catches same-pixels / different-compression).
- Identical byte hash → `EXACT_DUPLICATE`; identical pixel hash with differing byte hash → `EXACT_DUPLICATE` (pixel-identical variant). Record cluster id; **remove nothing automatically**; duplicate members MUST share a split (inherit group).
- Compute **pHash + dHash**. Pairs with Hamming distance ≤ 10 → `NEAR_DUPLICATE_CANDIDATE` (perceptual ≠ proof; confirm with a pixel-similarity check). **Any cross-group OR cross-label near-duplicate is ESCALATED as a leakage concern**, not silently kept.

## 7. Content QC (non-semantic, human-reviewable)
- Per file: mean, std, fraction near-white (>235), fraction near-black (<20), Shannon entropy.
- Flag `REVIEW` candidates: mostly-white (>0.90), mostly-black (>0.90), low-variance (std<8), low-entropy (<3), over/under-exposed. **No auto-delete.**

## 8. Label plausibility (never relabel)
- Visual, glaring-problem screening only (blank carrying a tissue label, obvious non-histology, corrupt-with-label, duplicate-with-conflicting-label) → status `REVIEW`, note "REQUIRES HUMAN REVIEW". **Never silently change a class.** Do not reinterpret histology from morphology.

## 9. Image → manifest mapping
- Deterministic 1:1. Local cache path is a pure function of `image_id`. Manifest records cache path + both hashes so the exact file set is reproducible from artifacts alone.

## 10. Logging
- Append-only run log: per file → image_id, HTTP status, content-type, content-length (if any), bytes, byte+pixel SHA-256, format/magic, mode/channels/bit-depth/dims, content flags, final QC status. Failures stay visible. Cumulative byte total vs cap recorded.

## 11. Promotion rule
- Only `PASS` images are eligible for training. `REVIEW` images await an explicit human decision. `CORRUPT`, `*_DUPLICATE` (beyond the retained representative), `MANIFEST_MISMATCH` are excluded **with their recorded status**, never a silent drop. The excluded-count-by-status table is part of the ingestion report.
