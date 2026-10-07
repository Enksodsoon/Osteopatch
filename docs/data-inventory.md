# OsteoPatch data and artifact inventory

**Inventory checked:** 7 October 2026, implementation worktree. This document distinguishes files tracked in Git from host-local runtime files. Host-local counts can change; repeat the read-only counts and the demo preflight before relying on another machine's bundle. Never copy local data into Git to make a clean clone appear complete.

## Source and provenance

The current OsteoPatch teaching corpus is the **TCIA Osteosarcoma-Tumor-Assessment** collection, DOI [`10.7937/tcia.2019.bvhjhdas`](https://doi.org/10.7937/tcia.2019.bvhjhdas). The recorded metadata source is the TCIA-hosted `ML_Features_1144.csv`; image-object metadata was joined against the collection's PathDB record. The dataset card records a published CC BY 3.0 statement and notes that attribution/terms must be reconfirmed when images are fetched or redistributed. The project itself retains its proprietary license declaration; do not assume repository visibility grants reuse rights.

The user also pointed to the [AWS NCI Imaging Data Commons registry](https://registry.opendata.aws/nci-imaging-data-commons/) as a possible data source. The available records do **not** show that this registry was used to build the current demo corpus. Do not identify the current local files as an IDC export or claim an IDC accession, snapshot or download without new verifiable evidence.

The tracked source and decision records are under `aidlc-docs/inception/data/`:

| File | Contents and use |
|---|---|
| `dataset-card.md` | TCIA identity, published source/license note, historical stage status and permitted-use boundaries |
| `data_audit.json` | Retrieved CSV metadata, hash, dimensions, raw label counts and data audit |
| `manifest.csv` | Original source terminology and per-patch metadata; preserve its source fields |
| `canonical_manifest.csv` | Ratified canonical label and eligibility mapping; unknown values must fail closed |
| `label_aliases.json` | Explicit raw-to-canonical mapping and mixed-state rule |
| `group-class-distribution.md` / `.csv` | Class counts across the four recorded case/slide grouping tokens |
| `patient_mapping_evidence.md` | Why the file identifiers are not proven biological patient identifiers |
| `split-proposal.md`, `mixed-patch-policy.md`, `g2-validation-report.md` | Grouped evaluation design, mixed-label exclusion and validation limits |
| `image-ingestion-plan.md`, `duplicate-report.md` | Image acquisition, identity and future image-QC requirements |

The source CSV record is 1,144 rows × 69 columns, retrieved 3 October 2026, SHA-256 `96fc6f3789a4ae14d536057d7db8b1353d20b0b2b94ce54b80e58ef5120281f6`. The exact source URI and collection identifiers are retained in `dataset-card.md` and `data_audit.json`.

## Cohort, labels and denominators

| Population or artifact | Count | Meaning |
|---|---:|---|
| Source metadata rows | 1,144 | Total patch records in the source manifest |
| Local TIFF patches in this worktree's ignored runtime | 1,144 | 1024 × 1024 pixel patch files observed on the implementation host |
| Matching local PNG thumbnails | 1,144 | Gallery previews observed on the implementation host |
| Ratified trainable label set | 1,091 | 536 `NON_TUMOR`, 292 `VIABLE_TUMOR`, 263 `NECROSIS` |
| Mixed review state | 53 | Raw `viable: non-viable`; retained in metadata, excluded from the three learned classes |
| G4 frozen grouped out-of-fold evaluation | 1,028 | Eligible patches across four case/slide grouping tokens; not 1,144 and not patient-independent validation |
| Current demo project scope | 50 | Disposable teaching subset chosen by the existing deterministic priority/seed path; not the evaluation set |
| Host-local recorded inference run | 1 | One run and one tile record with source and PNG artifacts verified on this host |

Raw source labels were `Non-Tumor` (536), `Viable` (292), `Non-Viable-Tumor` (263) and `viable: non-viable` (53). The ratified mapping is direct for the first two, `Non-Viable-Tumor` → `NECROSIS`, and mixed viable/non-viable → a non-trainable review state. The four grouping tokens have counts Case 3 (285), Case 4 (277), Case 48 (370) and P9 (212). They are grouping evidence from names, not independently verified patient identities; see `patient_mapping_evidence.md`.

The 1,028-patch G4 evaluation uses counts `NON_TUMOR` 484, `VIABLE_TUMOR` 290 and `NECROSIS` 254. The frozen pooled metrics are macro-F1 **0.562311**, balanced accuracy **0.626460**, secondary accuracy **0.670233**, and viable-tumor recall **0.110345**. That viable-tumor weakness is material. This exploratory four-group evaluation is not external, prospective, patient-independent or clinical validation. The historical 50-image public-demo denominator is a third, different scope. See [model-evidence.md](model-evidence.md) and the frozen G4 records in `aidlc-docs/inception/model/g4/`.

## Model and inference artifacts

| Identity | Status and hash | Correct interpretation |
|---|---|---|
| `baseline-frozen-g4` | Original bundle SHA-256 `01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63`; binary absent | Identity retained by frozen predictions/evaluation; do not claim the binary is locally recoverable |
| `g4-behavioral-recovery-r1` | Local head file SHA-256 `ffff1282f533758d7d7c8370ee6092f97f553da69918c5ee7e83632428176a73` | Recovered behavioral head for separately qualified live inference/attribution; not the original G4 model and cannot inherit its frozen metrics |
| MobileNetV3-small encoder checkpoint | SHA-256 `047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f` | Encoder used by the recovered head; separate from the recovered head bundle |

The host-local `runtime-artifacts/models/` contains nine files (about 25.4 MB total), including the recovered head, encoder checkpoint, recovered-head parameters and embedding/recovery arrays. Runtime files are ignored by Git. The frozen G4 training manifest, per-fold/overall metrics, out-of-fold predictions, confusion matrix, model card and test report are tracked under `aidlc-docs/inception/model/g4/`. A hash match proves file identity only; it does not restore the absent original artifact or justify a clinical claim.

The local source database observed in this worktree had 1,144 `source_qc` rows, 1,144 immutable `prediction` rows, five existing `review_event` rows, one `live_run`, one `live_tile`, and no saved case reports at inspection time. All 1,144 frozen predictions remain keyed to `baseline-frozen-g4` and its original hash. The one live run is keyed separately to `g4-behavioral-recovery-r1` and the encoder hash above. The launcher verified the recorded source SHA-256 and tile PNG signature. These are observations of the host-local source bundle, not promises about a clean clone or another runtime snapshot.

## WSI and derived study material

The latest browser evidence exercised upload/open/zoom/pan/annotation, original and region download, analysis and report export using a locally supplied SVS that was 20,414 × 27,401 pixels with three reader-reported levels. That specimen was not part of the osteosarcoma corpus, is not committed, and only demonstrates software file handling; it provides no evidence about model accuracy on that tissue.

The separate generated-slide record in [`evidence/demo-slide.json`](evidence/demo-slide.json) describes a 4,608 × 3,840 TIFF, SHA-256 `7f0e8542db26ecd5815637d4f3163a94d366cee8ce0564c6cf4b653f8adee91c`. The configured reader reports one level, no mpp, no objective power and no vendor. It is valid tiled input, but it is **not** a pyramid according to the reader. The generated file is host-local, not tracked in this worktree. Do not describe either slide result as whole-slide inference: the demo scans at most 16 areas.

The learning page contains sourced educational content and generated/synthetic visual study material. Those illustrations explain concepts; they are not samples from the model-training corpus, pathology ground truth, predictions or patient images. For clinical content, retain the links and limitations already present in the page rather than silently converting software explanations into medical claims.

## What a clone does and does not contain

| Available in Git | Host-local / excluded by design |
|---|---|
| Source manifests, label policy, dataset/model cards, frozen metrics and prediction records, expected artifact identities, application code and tests, curated screenshots and dated test results | Runtime database, 1,144 raw patch TIFFs, 1,144 thumbnails, model/encoder binaries, embedding arrays, live-run source/tile pixels, generated WSI fixtures and user-supplied WSI scans |

The working implementation host's `runtime-artifacts/` contained the database, all 1,144 TIFF/thumbnail pairs, nine model files and one verified recorded run when this inventory was checked. These binaries are not part of the branch or pull request. A fresh clone must restore an authorized runtime bundle and set `OSTEOPATCH_RUNTIME_ARTIFACTS` or place it in the ignored repository-root `runtime-artifacts/` directory. There is no automatic download step. The `prepare_runtime.py` exact-hash manifest serves a separate pinned bake/deploy path; the current demo launcher performs its own non-destructive source-hash check, copied-row digest check and selected-pixel/replay validation. Never rewrite a pin just to make a different database pass.

The source dataset card says images were not downloaded at the original G2 milestone on 3 October 2026. That statement is historical and accurate for that milestone. Local images were restored later and their presence was checked for the 7 October demo run. Do not rewrite the old stage report; use this inventory and the dated [demo-readiness record](evidence/demo-readiness.md) for the later local state.

## Safe handling

- Treat `runtime-artifacts/` as private local data even though the tracked dataset is de-identified/publicly described. Keep user-provided slides local and de-identified before any use.
- Do not commit image pixels, databases, models, raw live-run files, runtime logs, credentials or machine-specific paths.
- Read-only inspections of the source database are safe. Review/report writes and uploads belong in the disposable demo workspace.
- Do not run `enterprise.seed(scope_size=50)` against the source database. It updates project scope on source rows. `scripts/demo.py` first copies the database, then seeds that copy.
- Before describing any corpus number, identify its denominator and source: 1,144 source records, 1,091 ratified trainable labels, 1,028 G4 evaluation patches, or a 50-patch demo scope are not interchangeable.
- Before redistributing images or derivatives, recheck the current source terms and attribution requirement in the official collection record.
