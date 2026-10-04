# Image ingestion plan — FUTURE, DO NOT EXECUTE (OsteoPatch Review)

**Status:** design only. **No image bytes are downloaded by this plan at G2.** No AWS resource created, no training. Executed only after a later gate explicitly authorizes an image fetch. All image-level manifest fields (`image_sha256`, verified `width`/`height`, perceptual duplicate clusters) remain **PENDING-IMAGES** until then.

## Credential-free finding to preserve (established at U1, do not re-run)

- PathDB collection `Osteosarcoma-Tumor-Assessment` (collectionId 18) indexes **1,144** `.tiff` tile objects.
- CSV ↔ PathDB imageId join is **1,144 / 1,144 one-to-one** after separator normalization (strip spaces around `-`, whitespace→`-`, collapse repeats).
- Object HTTP URLs are **verified reachable** (one object probed: HEAD+GET HTTP 200, `image/tiff`, served over plain **HTTP**, no Content-Length / chunked). URL template:
  `http://pathdb.cancerimagingarchive.net/system/files/wsi/ross/Osteosarcoma-UT/converted/Osteosarcoma-UT/Training-Set-{1,2}/set{1..12}/<normalized-id>.tiff`
- Aspera route: Faspex package **752**, public (no auth expected), `ascli faspex5 packages receive`; headless `ascli`/`ascp` on a Linux/AWS host is **feasible by design**, est. transfer ~200 MB (published 196.84 MB). `ascli browse` lists sizes as a pre-flight. Blocked today only by no-AWS-access (B2).

## Plan (ordered; each step gated, none executed now)

1. **Metadata-first selection.** Drive the fetch list from `canonical_manifest.csv` (`image_url`, `image_id`), not from directory crawling. Only rows needed by the authorized unit are selected (e.g. trainable rows for a training unit; MIXED only when a review-set unit asks).
2. **Bounded test download.** Fetch a small deterministic sample first (e.g. the already-probed object + one per group) to confirm template, content-type, and decode before any bulk pull. Abort+report if size/decode diverges.
3. **Checksum validation.** On each fetched object compute SHA-256, write it to `image_sha256`, decode with Pillow to record verified `width`/`height`; reject corrupt/undecodable objects (flag, do not force into a class). Record total bytes against the standing footprint caps.
4. **Resumability.** Idempotent cache keyed by `image_id`; a present+checksum-matching file is skipped. A partial/failed object is re-fetched, never half-counted. Safe to interrupt and resume.
5. **No duplicate download.** The `image_id` key is unique (1,144 distinct); never fetch the same object twice. After bytes land, run exact-SHA-256 and perceptual near-duplicate clustering; populate `duplicate_cluster_id`; duplicate members must share a split (inherit group).
6. **Deterministic cache → manifest map.** Local cache path is a pure function of `image_id`; the manifest records cache path + checksum so a downstream step reproduces the exact file set from artifacts alone.
7. **Optional later S3 transfer.** On an authorized AWS host, stream to the project S3 prefix (FastFile design, doc architecture); keep provenance (source URL, checksum) in the manifest. Still gated; not part of G2.

## Guardrails carried forward

- Respect standing footprint caps; inspect size before any bulk fetch; abort+report if exceeded.
- Raw bytes kept outside Git. CC BY 3.0 attribution + data citation on any redistribution.
- Nothing here runs until a gate after G2 authorizes it with AWS access resolved.
