
# Audit trail — OsteoPatch Review

Append-only record of executed steps, commands, and owner approvals. Never claim a test passed unless it was executed with recorded output.

---

## 2026-10-03 — U1 authorized (owner Enk), continuation file absent

The U1 continuation file (`OsteoPatch_Kiro_U1_Continuation_2026-10-03.md`) was never received (transfer failed; not in uploads or workspace). Owner approved **Option 2**: proceed with explicit owner-defined conservative bounds instead of waiting for the file.

### Approved U1 bounds (authoritative for this unit)
- **Scope:** U1 only (data ingestion + split audit). Stop at **G2 REVIEW REQUIRED**.
- **Source:** official TCIA Osteosarcoma-Tumor-Assessment, DOI `10.7937/tcia.2019.bvhjhdas`, **local dev + audit only**. Never describe as IDC/AWS Open Data. Hackathon eligibility stays **UNVERIFIED**.
- **Download cap:** ≤ **500 MB** new source data. **Total U1 footprint cap:** ≤ **2 GB** (source + extracted + manifests + caches + env + temp). Inspect expected size before download; abort + report if either would be exceeded. Raw data kept **outside Git**. Delete disposable archives after extraction + checksum/provenance recorded; do not delete verified extracted source or audit artifacts without asking. 75 GB free is not permission to expand limits.
- **Env:** isolated under scratch/project-ignored; **CPU only**; no CUDA, no PyTorch/TensorFlow, no model weights, no frontend deps, no Docker (not expected for U1), no global/system package changes. Approved small deps: `idc-index`, `pytest`, Pillow, pandas/polars if needed, hashing/image-audit utils. Record exact versions.
- **Workflow:** AI-DLC **v1.0.1** only (install workshop layout if absent; never 2.x); verify steering is loaded before treating artifacts as AI-DLC artifacts; preserve existing steering + aidlc-docs history.
- **Importer:** fail-closed; canonical order NON_TUMOR(0)/VIABLE_TUMOR(1)/NECROSIS(2); never map unknown → a valid class; preserve original label strings; required rejections/checks per owner list (unknown/blank label, dup key, CSV-without-image, image-without-label, many-to-one filename, corrupt image, contradictory labels, patient overlap across split, derivatives share split).
- **Patient mapping = critical question.** Produce `patient_mapping_evidence.md`; never infer patient from folder/`Training_Set_*`/numeric substring without evidence; no patient-independent claim unless verifiable.
- **Split:** propose only after actual patient×class table; prefer group independence over patch count; no random patch split called patient-independent; if none defensible, report + propose grouped-CV or explicitly-labelled exploratory/demo eval.
- **Prohibited:** train, download weights, final metrics, build app, Grad-CAM, AWS deploy, SageMaker, buy credits, upgrade plan, change IAM, public hosting/server, patient-identifiable data, auto-retrain, proceeding to U2.
- **IDC:** `idc-index` discovery permitted (credential-free), must not block U1; keep separate: (1) related osteosarcoma imaging in IDC? (2) exact 1,144 labelled JPG patches? (3) three-class labels? (4) usable patient mapping? Do not infer yes to 2–4 from 1.

### Owner-approved G1 route
B — TCIA direct (local only). Recorded in `inception/decision-and-approval-log.md` (D1–D8) and `inception/data-source-decision.md`.

---

## Execution log (appended as steps run)

### 2026-10-03 — G5 Bounded Last-Stage Encoder Fine-Tuning (EXECUTED, local CPU, credential-free, no AWS) — NO BENEFIT
One prespecified experiment per `_G5_BRIEF.md`: does unfreezing ONLY the final MobileNetV3-Small feature stage (+ head) improve VIABLE_TUMOR discrimination without destroying NON_TUMOR/NECROSIS? Not a sweep. `@kirocrew-computer` MCP declared-but-not-configured (unavailable) — not used. Session not conductor-bound (`work_brief`=not_bound) — reported via chat + durable artifacts. **G4 artifacts untouched** (immutable comparator); all new work under `inception/model/g5/` and scratch `osteopatch_g5/`.

- **Reuse + hard gate:** reused the EXISTING scratch venv (torch 2.14.1+cpu / torchvision 0.29.1 / sklearn 1.9.1, Python 3.12.10, Win 11) and the scratch TIFFs. Re-hashed `g4/g4-training-manifest.csv` → SHA-256 `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba` **MATCH** (no hard stop). Same 1,028 cohort (NON 484 / VIABLE 290 / NECROSIS 254), same 4 LOGO groups, class order NON/VIABLE/NECROSIS, 384² full-field + pinned ImageNet norm, D4 train-only aug, per-fold inverse-freq train-only weighted CE, seed 42.
- **The one bounded change:** unfreeze ONLY `features[12]` (final stage: `Conv2dNormActivation(Conv2d 96→576 1×1 + BN576 + Hardswish)`) + `classifier` head; all earlier stages frozen. **Trainable = 7 tensors / 650,371 params** (`features.12.0.weight` 55,296; `features.12.1.weight` 576; `features.12.1.bias` 576; `classifier.0.weight` 589,824; `classifier.0.bias` 1,024; `classifier.3.weight` 3,072; `classifier.3.bias` 3); frozen 135 tensors / 870,560 params. Explicit named-param assertion (pre-run + per-fold): ONLY `features.12.*`+`classifier.*` trainable (unexpected=[], expected-but-frozen=[]). BN kept in frozen-stat eval mode throughout (final-stage affine params trainable; documented G3/G4-consistent choice). Because the final stage is trainable, G4's cached-embedding trick is invalid → full forward+backward over pixels each step (D4 applied as rot90+hflip tensor ops on the cached normalized eval tensor; pixel-identical because D4 commutes with per-channel normalize; eval = identity view).
- **Optimization (prespecified, no sweep):** two AdamW groups — final-stage LR 1e-5, head LR 1e-4; wd 1e-4; batch 16; 5 epochs fixed; no early stop; no leaky inner val; outer group never influenced training/selection/weighting.
- **Pre-run verification (`step_b_tests_g5.py`): 15/15 PASS, 0 hard failures** (`g5/test-report.json`) — manifest-hash match, class order, 1,028 eligible, exact 4 groups+support, LOGO zero outer-group overlap, each image outer-test once (1028/1028), train-only weights, train≠eval transforms, eval 3×384×384, **excluded-QC-rows-stay-excluded (0 leaked, cross-checked vs full-image-qc-results.csv)**, 0 cross-group-leakage flags, 3 finite logits, probs sum 1, **only-finalstage-and-head-trainable**, absent-class UNAVAILABLE.
- **Device + runtime:** CPU (CUDA unavailable, sanctioned fallback; no AWS). Base-tensor cache 21.9 s; fold times Case-3 89.2 s / Case-4 172.7 s / Case-48 271.8 s / P9 218.4 s; total 752.0 s (~12.5 min). **No OOM**, batch 16 stable (throughput probe confirmed), no retries/fallback beyond CUDA→CPU. One benign `float(loss)` UserWarning in the throughput probe only.
- **Per-fold LOGO (G5, held-out scored once):** Case-3 macroF1 0.5595(3cls)/acc0.765; Case-4 0.5468(3)/0.605; Case-48 0.2314(3)/0.367; P9 1.0(1cls)/1.0 (VIABLE+NECROSIS UNAVAILABLE). Fold checkpoints in scratch with SHA-256 (`g5/fold-checkpoint-hashes.json`): Case-3 `85f1ad8e…e49a`, Case-4 `33e26000…6816`, Case-48 `9823eab6…3bc0`, P9 `5c3723c1…eabb`.
- **Pooled OOF (1,028, `g5/overall-oof-metrics.json`):** macro-F1 **0.5229**, bal-acc 0.6009, acc 0.6430, log-loss 1.1993, Brier 0.5524. Confusion (true/pred NON/VIA/NEC): [[424,17,43],[161,13,116],[4,26,224]].
- **Direct G4→G5 deltas (immutable comparator, `g5/g4-vs-g5-metric-comparison.json`):** macro-F1 **−0.0394** (0.5623→0.5229); **VIABLE recall −0.0655** (0.1103→0.0448); **VIABLE F1 −0.1041** (0.1793→0.0751); VIABLE precision −0.2455; NON_TUMOR F1 −0.0517; NECROSIS F1 +0.0376; bal-acc −0.0255; Brier +0.0563 (worse). **VIABLE→NECROSIS 153→116 (−37)** BUT VIABLE→NON_TUMOR 105→161 (+56) and VIABLE-correct 32→13 (−19): error relocated, not reduced; no discrimination gain.
- **Verdict: NO BENEFIT.** Primary targets regressed and the one positive confusion shift is fully explained by a larger offsetting error, consistent across the two informative folds (Case-4, Case-48). Training loss fell monotonically every fold while held-out performance worsened → last-stage overfitting to case-specific features on a 4-group cohort. No post-hoc significance threshold invented.
- **No final G5 bundle created** (brief: build only if PROMISING). `baseline-frozen-g4` remains the prototype default; no "improved" replacement. 16 durable artifacts in `inception/model/g5/` (run-configuration, trainable-parameter-inventory, test-report, fold-histories, fold-checkpoint-hashes, g5-oof-predictions.csv, per-fold-metrics, overall-oof-metrics, confusion-matrix.csv, g4-vs-g5-metric-comparison, g4-vs-g5-confusion-comparison, viable-to-necrosis-error-comparison, g4-vs-g5-fold-comparison, training-run-summary, g5-summary.md, model-card-addendum-g5.md). `_G5_BRIEF.md` deleted at end per brief. **STOPPED at "G5 — FINE-TUNING REVIEW REQUIRED"**; did NOT proceed to multi-seed/calibration/Grad-CAM/uncertainty/API-UI/AWS/deploy.

### 2026-10-03 — G4 Local LOGO Baseline Training (EXECUTED, local CPU, credential-free, no AWS)
Owner-approved execution of the frozen G3 design on the completed Full-Collection QC result. One focused run; no extra agents, no re-download, no Image-QC rerun. `@kirocrew-computer` MCP was declared-but-not-configured (unavailable) — not used. Session was not conductor-bound (`work_brief`=not_bound); reported via chat + durable artifacts.

- **Env added to EXISTING scratch venv** (`...\osteopatch_full_ingestion\.venv`, no global install, no new venv): torch 2.14.1+cpu, torchvision 0.29.1+cpu, scikit-learn 1.9.1 (numpy 2.5.3 / Pillow 12.3.0 already present). Python 3.12.10, Windows 11.
- **GPU/determinism probe:** `torch.cuda.is_available()==false` under the CPU wheel → **device CPU** (sanctioned fallback; no 2nd CUDA stack attempted, no AWS). Seeded random/numpy/torch=42; cudnn.deterministic; use_deterministic_algorithms(warn_only). Weights pinned `MobileNet_V3_Small_Weights.IMAGENET1K_V1` (ImageNet mean/std).
- **Manifest frozen BEFORE training:** `inception/model/g4/g4-training-manifest.csv` SHA-256 `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba`. Re-derived eligibility (canonical_label∈3 classes ∧ primary_qc_status==PASS ∧ training_eligible) → **1,028** (NON_TUMOR 484 / VIABLE_TUMOR 290 / NECROSIS 254); held/excluded 116; 1,028+116=1,144 reconciled; all 4 groups present; 1,028/1,028 pixel files on disk. `group-class-support.csv`: Case-3 95/3/166, Case-4 72/85/86, Case-48 126/202/2, P9 191/0/0.
- **Pre-training tests (hard-stop gate):** `step_b_tests.py` → **14/14 PASS, 0 hard failures** (`test-report.json`). canonical order; only-eligible load; MIXED/REVIEW/near-dup cannot enter; all-PASS status; train≠eval transforms (eval deterministic, train varies); eval tensor (3,384,384) matches inference contract; LOGO zero train/test overlap per fold; each image outer-test exactly once (1028/1028, max_count=1); 0 cross-group-leakage flags; fold weights from training rows only (mean-1, 0 iff class absent in train); 3 finite logits; probs finite & sum to 1; only `classifier.3.{weight,bias}` trainable (encoder frozen); absent class marked UNAVAILABLE on P9.
- **Training (`step_c_logo_train.py`):** frozen-encoder MobileNetV3-Small + new Linear(1024→3); AdamW lr1e-3 wd1e-4 batch16 ≤10 epochs, no early stopping; per-fold inverse-freq train-only class weights; train-only aug hflip/vflip/90°. Implementation: the aug family = dihedral D4 (8 views); because the encoder is frozen, the 8 per-image view embeddings were precomputed once and the head trained on a random view per image per epoch (mathematically identical to augmenting pixels through the frozen encoder; eval = identity view). Fold checkpoints saved to scratch with SHA-256 (`fold-checkpoint-hashes.json`). No OOM; batch 16 held; no fallback beyond CUDA→CPU.
- **Per-fold LOGO (neural), held-out scored once:** Case-3 macroF1 0.589(3cls)/bal0.645/acc0.807/ll0.501; Case-4 0.614(3)/0.659/0.650/0.824 (only fold with all 3 at usable support); Case-48 0.281(3)/0.658/0.391/2.685 (NECROSIS support=2 indicative); P9 degenerate 0.995(1cls)/0.990/0.990 (VIABLE+NECROSIS UNAVAILABLE). Majority baseline from training groups only = NON_TUMOR all 4 folds.
- **Pooled OOF (1,028 rows, `overall-oof-metrics.json`):** macro-F1 **0.562** (3 cls), balanced-acc **0.626**, accuracy (secondary) **0.670**, log-loss **1.195**, Brier **0.496**. Confusion (rows true / cols pred, NON/VIA/NEC): [[437,13,34],[105,32,153],[12,22,220]]. Per-class: NON P0.789/R0.903/F0.842(484); VIABLE P0.478/R0.110/F0.179(290); NEC P0.541/R0.866/F0.666(254). Dominant error VIABLE→NECROSIS (153). Majority pooled macroF1 0.213/acc0.471.
- **Final all-data model + bundle (`step_e_final_bundle.py`):** one frozen-encoder head trained on all 1,028; bundle `osteopatch_g4_baseline_bundle.pt` SHA-256 `01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63` (scratch, out of git per policy); config records class map, preprocessing, weights id, manifest hash, seed, deps, educational-use limitation, calibration_status=uncalibrated. **Reload test PASS**: fresh-load inference parity exact, outputs finite, probs sum to 1, 3 outputs. No temperature scaling (G3 defines no leakage-safe calibration at 4 groups).
- **Durable artifacts (15) in `inception/model/g4/`:** g4-training-manifest.csv, manifest-freeze.json, group-class-support.csv, test-report.json, majority-baseline-predictions.csv, oof-predictions.csv, per-fold-metrics.json, overall-oof-metrics.json, confusion-matrix.csv, fold-histories.json, fold-checkpoint-hashes.json, run-configuration.json, final-bundle.json, model-card-baseline.md, g4-summary.md.
- **Frozen-contract deviations:** none of substance (the D4-embedding-caching reformulation is documented in run-configuration.json/g4-summary.md). **STOPPED at "G4 — MODEL / EVALUATION REVIEW REQUIRED"**; did NOT proceed to fine-tuning, Grad-CAM, uncertainty tuning, API/UI, AWS, or deployment. `_G4_BRIEF.md` deleted at end per brief.



## 2026-10-03 — U1 cloud-first pivot (D9) + IDC investigation

- Owner superseded the local-download plan with a **cloud-first** architecture (control plane = Windows/Kiro; data/compute plane = AWS). Recorded as D9 in `inception/decision-and-approval-log.md`.
- In-flight local-download worker (`88475124`) was steered to stand down. Confirmed clean: it had only READ docs — **no venv, no download, no files written, zero project changes**.
- **Credential-free IDC investigation executed** with `idc-index==0.12.5` (IDC release v24) in isolated scratch venv. Commands: `IDCClient().index` + `sm_index` substring/DOI/body-part search. Result: osteosarcoma collection (DOI `bvhjhdas`) **NOT in IDC** — 0 series by name/DOI, 0 `BodyPartExamined=BONE`, across all 176 collections; only `bonemarrowwsi_pediatricleukemia` and `soft_tissue_sarcoma` are osteo/sarcoma/bone-adjacent (different diseases). Full record: `inception/idc-access-investigation.md`.
- Consequence: direct-IDC-S3 route **ruled out by evidence**. Remaining cloud route = TCIA→project S3, blocked by (B1) TCIA images are Aspera-only / no headless route, and (B2) no AWS access configured on this host.
- Architecture updated: `inception/architecture-proposal.md` §Cloud-first (S3 layout, cost gate, cost estimate, U2 FastFile-vs-File-vs-Pipe design — FastFile SELECTED).
- Nothing persistent stored on the workstation. No AWS resource created. No training.


---

## 2026-10-03 — U1 credential-free investigation (CSV audit + PathDB + Aspera feasibility)

Executed on the Windows control plane in isolated venv `%KIROCREW_SCRATCH%\osteopatch-idc-venv` (reused). **No AWS, no training, no bulk image download, no AWS resource.** Raw downloads kept OUTSIDE the project in `%KIROCREW_SCRATCH%\osteopatch-u1-raw`. MCP server `@kirocrew-computer` was declared but not configured (unavailable); all other tools present. Session was NOT bound to a conductor work item (`work_brief` → `not_bound`), so results are reported in chat + these artifacts rather than via `work_report`.

### Env / versions (recorded)
- python 3.12.10 · pandas 3.0.6 · requests 2.34.2 · pillow 12.3.0 · pytest 9.1.1 · tcia_utils (installed; `__version__` not exposed, `pathdb` module present with real signatures `getCollections(query,format)`, `getImages(query,format)`, base `https://pathdb.cancerimagingarchive.net/`).

### TASK 1 — CSV audit (official URL only)
- `GET https://www.cancerimagingarchive.net/wp-content/uploads/ML_Features_1144.csv` → **HTTP 200**, content-type `text/csv`.
- **bytes = 880,995** · **SHA-256 = `96fc6f3789a4ae14d536057d7db8b1353d20b0b2b94ce54b80e58ef5120281f6`**.
- Rows **1,144** · columns **69** · classification column = **`classification`**.
- Distinct raw labels (4): `Non-Tumor`=536, `Viable`=292, `Non-Viable-Tumor`=263, `viable: non-viable`=53.
- Canonical map (fail-closed, REAL labels only): `Non-Tumor`→NON_TUMOR, `Viable`→VIABLE_TUMOR. **`Non-Viable-Tumor`(263) and `viable: non-viable`(53) left UNRESOLVED** (flagged error, never guessed).
- Class counts vs published (Non-Tumor 536 / Viable 345 / Necrosis 263): NON_TUMOR 536=536 ✓; VIABLE_TUMOR resolved 292 (−53 vs 345, the mixed rows); NECROSIS resolved 0 (the 263 `Non-Viable-Tumor` not auto-mapped). 292+53=345 and the 263 reconcile the totals.
- No dedicated patient/case/subject/slide/group **column** exists. Filename column = `image.name`; samples `Case 3 A10-10547-25283`, `P9 B11-10159-22267`, `Case 48 - P5 C13-24121-14200`. Inferred regex `^(Case\s*\d+(?:\s*-\s*P\d+)?|P\d+)[\s-]+[A-Za-z]?\d+-\d+-\d+$`. Filename **does** encode a 4-way group (Case 3/Case 4/Case 48/P9).
- Duplicate filenames: **0** (1,144 distinct). Nulls/blanks in key cols: 0.

### TASK 2 — PathDB (tcia_utils.pathdb)
- `getCollections(query='Osteosarcoma')` → one hit: **`Osteosarcoma-Tumor-Assessment`, collectionId 18, updated 2023-12-01**.
- `getImages('Osteosarcoma-Tumor-Assessment', format='df')` → 1,144 rows (paged listofimages/18). Distinct subjectId **1,144**, distinct imageId **1,144** ⇒ **subjectId = per-patch id, NOT biological patient**.
- CSV↔PathDB join: raw exact = 0 (CSV uses spaces/` - `, PathDB uses `-`); **after normalization (strip spaces around `-`, whitespace→`-`, collapse repeats) = 1,144 / 1,144 one-to-one.** PathDB CAN map every CSV row to an image.
- Group tokens (both sides agree): Case 3=285, Case 4=277, Case 48=370 (embeds `P5`), P9=212. **4 tokens = published 4 patients** (count match; subjectId≠patient, so token→patient identity is INFERENCE — documented in `patient_mapping_evidence.md`).
- `imageUrl` folder path (documented grouping): `…/converted/Osteosarcoma-UT/Training-Set-{1,2}/set{1..12}/<id>.tiff`. All 1,144 report dims 1024×1024.
- **ONE object probed** (no bulk download): `http://pathdb.cancerimagingarchive.net/system/files/wsi/ross/Osteosarcoma-UT/converted/Osteosarcoma-UT/Training-Set-2/set1/Case-3-A10-10547-25283.tiff` → **HEAD & GET HTTP 200, content-type image/tiff**, Content-Length absent (chunked). Note: served over plain **HTTP**; objects are `.tiff` tiles (published release lists `.jpg`).

### TASK 3 — Aspera CLI feasibility (NO transfer; nothing installed)
- Client/prereqs: Ruby ≥3.1 + `gem install aspera-cli` + `ascli conf ascp install`; Linux; documented verb `ascli faspex5 packages receive --url='<public pkg>'`; this collection = Faspex package **752**.
- Auth: expected **none** (public passcode in URL). Public package addressable by URL directly: expected **yes**.
- Linux AWS env → ephemeral disk → S3: **feasible by design** (headless ascli/ascp). Temp storage estimate **~200 MB** (published 196.84 MB) < 500 MB/2 GB caps; **`ascli browse` lists sizes before transfer** (run as pre-flight). **Blocked by B2 (no AWS access on this host).** Full artifact: `inception/data/aspera-cli-feasibility.md`.

### TASK 4 — Artifacts written (absolute paths)
- `aidlc-docs\inception\data\dataset-card.md`
- `aidlc-docs\inception\data\data_audit.json`
- `aidlc-docs\inception\data\label_aliases.json`  (resolved + unresolved-pending)
- `aidlc-docs\inception\data\duplicate-report.md`
- `aidlc-docs\inception\data\patient_mapping_evidence.md`
- `aidlc-docs\inception\data\manifest.csv`  (1,144 rows per docs\08; `image_sha256`/`width`/`height` = PENDING-IMAGES; 828 resolved canonical, 316 fail-closed-flagged)
- `aidlc-docs\inception\data\aspera-cli-feasibility.md`

### Disk footprint (new)
- Raw CSV (outside project): 880,995 B · scratch work scripts/intermediates: 460,265 B · project data artifacts: 483,340 B. **Total new disk ≈ 1.82 MB** (venv reused; a few small pure-python deps may have been added to the pre-existing venv). Far under the 500 MB / 2 GB caps. No images downloaded.

### Next action (single smallest)
Owner to **ratify the two unresolved label strings** in `label_aliases.json` (`Non-Viable-Tumor`→NECROSIS? and `viable: non-viable`→? [viable / own mixed class / exclude]). That unblocks the canonical label contract and the patient×class table for a G2 split proposal. (AWS access B2 remains separately blocked for any S3/Aspera image step.)


---

## 2026-10-03 — G2 built from existing artifacts (offline, deterministic)

Session NOT bound to a conductor work item (`work_brief` → `not_bound`); ran as default agent, reported in chat + these artifacts. MCP `@kirocrew-computer` declared-but-not-configured (unavailable); all other tools present. **No AWS, no training, no deploy, no image/pixel download.** Built on the existing `manifest.csv` (1,144 rows, PathDB join preserved) — nothing re-downloaded, deleted, or restarted. Build script `_g2_build.py` run under python 3.12; fail-closed reconciliation gate passed before any write.

### Ratified label policy applied (owner, represented exactly)
- `Non-Tumor`→NON_TUMOR (trainable); `Viable`→VIABLE_TUMOR (trainable); `Non-Viable-Tumor`→NECROSIS (trainable); `viable: non-viable`(53)→review_state **MIXED_VIABLE_NECROTIC** (trainable=false, EXCLUDED from the 3-class labels, RETAINED in manifest). Primary = NON_TUMOR/VIABLE_TUMOR/NECROSIS. **No 4th learned class.**

### Reconciliation (actual, computed — matches expected exactly, no STOP)
- Total 1,144 · join 1,144/1,144 1:1 · duplicates 0 · unmatched 0.
- BEFORE map: Non-Tumor 536 · Viable 292 · Non-Viable-Tumor 263 · viable:non-viable 53.
- AFTER map (trainable): NON_TUMOR 536 · VIABLE_TUMOR 292 · NECROSIS 263 = **1,091 trainable** + **53 MIXED excluded** = 1,144. 536+292+263+53=1,144 ✓.
- Groups: Case-3 285 · Case-4 277 · Case-48 370 · P9 212 = 1,144; every trainable row has a group id. **P9 verified 100% NON_TUMOR (212/212).** Sparse: Case-48 NECROSIS=2, Case-3 VIABLE=3.

### Split / eval design
- No random patch split (leakage). **Leave-One-Group-Out grouped CV**, 4 folds; P9 fold is single-class (VIABLE/NECROSIS not estimable); nested CV from 4 groups not trustworthy → hyperparameters frozen a priori. Independence is **case/slide-group**, NOT patient. No clinical-validity claim.

### G2 verdict: PASS WITH LIMITATIONS
All 9 data criteria pass; criterion 10 (independent 3-way split) fails due to 4 groups + P9 single-class. Limitations enumerated in `g2-validation-report.md`.

### Files created/updated (absolute paths)
- `aidlc-docs\inception\data\label_aliases.json` (RATIFIED, overwrote v1 fail-closed version)
- `aidlc-docs\inception\data\canonical_manifest.csv` (new, 1,144 rows)
- `aidlc-docs\inception\data\group_class_distribution.csv` (new)
- `aidlc-docs\inception\data\group-class-distribution.md` (new)
- `aidlc-docs\inception\data\split-proposal.md` (new)
- `aidlc-docs\inception\data\mixed-patch-policy.md` (new)
- `aidlc-docs\inception\data\image-ingestion-plan.md` (new, future — not executed)
- `aidlc-docs\inception\data\g2-validation-report.md` (new, T6 eval plan + T10 verdict)
- `aidlc-docs\inception\data\dataset-card.md` (versioned v1→v2)
- `aidlc-docs\audit.md` (this entry)
- `aidlc-docs\aidlc-state.md` (updated)
- Preserved unchanged: `manifest.csv`, `data_audit.json`, `duplicate-report.md`, `patient_mapping_evidence.md`, `aspera-cli-feasibility.md`.

### Next gate (single recommendation)
G3 model/eval design review on the frozen-encoder baseline + LOGO plan, WITHOUT fetching pixels. Image fetch (`image-ingestion-plan.md`) stays a later gated step pending AWS access (B2).



---

## 2026-10-03 — G3 model/eval design review built (offline, deterministic, DESIGN ONLY)

Session NOT bound to a conductor work item (`work_brief` → `not_bound`); ran as default agent, reported in chat + these artifacts. MCP `@kirocrew-computer` declared-but-not-configured (unavailable); all other tools present. **No pixels, no AWS, no training/fine-tune, no framework (torch) install, no infra, no deploy, no UI, no restart of U1/G2, no edits to any G2 artifact.** Built deterministically on the frozen G2 contract (`inception/data/*`) + primary refs `docs/02`, `docs/03`, `docs/08`.

### Frozen G2 contract reused verbatim
NON_TUMOR 536 / VIABLE_TUMOR 292 / NECROSIS 263 = 1,091 trainable; MIXED 53 excluded (retained); groups Case 3 / Case 4 / Case 48 / P9; LOGO 4-fold; P9 100% NON_TUMOR; Case 48 NECROSIS=2; Case 3 VIABLE=3. Independence = case/slide-group (never patient-level). Absent-class metric = "not estimable", never 0.

### G3 decisions (frozen)
- **Baseline:** torchvision MobileNetV3-Small, ImageNet-pretrained, **frozen encoder**, new 3-class linear head; non-benchmark comparison to ResNet18/EfficientNet-B0/ConvNeXt-Tiny (ResNet18 = only optional secondary). One primary; no arch search.
- **Preprocessing:** RGB; 384×384 full-field resize (no crop); pinned ImageNet mean/std; bilinear+antialias; corrupt→reject (never forced into a class). Known-from-source vs proposed-assumption separated; all pixel items marked **VERIFY AT IMAGE QC GATE** (dims are PathDB metadata, not per-file measured).
- **Augmentation:** baseline = hflip + vflip + 90° rotations (train-only); brightness/contrast = OPTIONAL EXPERIMENT; hue/saturation + stain = AVOID FOR BASELINE; random/resized crop AVOID (label is whole-patch predominant).
- **Imbalance:** **weighted cross-entropy**, deterministic per-fold inverse-frequency weights normalized to mean 1 (worked F4 example: w = [0.898, 0.996, 1.106]); **no stacking**; train-only.
- **Eval:** LOGO 4-fold; internal validation = **a-priori-frozen hyperparameters / no leaky patch-level val** (optional group-aware whole-inner-group val, disclosed); hyperparams reused across folds (no per-fold search). All 4 folds specified in `logo-fold-plan.csv`; P9 fold degenerate (1 class) shown not hidden.
- **Metrics:** confusion/per-class P-R-F1+support/macro-F1/balanced-acc = PRIMARY; accuracy/OvR-AUROC/PR-AUC/log-loss/Brier = SECONDARY; ECE = EXPLORATORY; disease-probability + patch-bootstrap-CI = NOT APPROPRIATE. Absent class = "not estimable" (never 0); weak support (VIABLE=3, NECROSIS=2) tagged "indicative only".
- **Aggregation:** **pooled out-of-fold predictions** as principal summary, always reported with per-fold spread (big group never masks small-group failure).
- **Uncertainty:** top1–top2 **margin** (+ max-softmax), lower margin = higher priority; deterministic priority key (quality→top_score→margin→image_id); 0-denominator → "unavailable". Thresholds 0.70/0.15 unvalidated, versioned.
- **Calibration:** uncalibrated softmax = baseline; temperature-scaling = SECONDARY feasibility-gated (fit in training groups only, disclosed); Platt/isotonic = not feasible yet. "model class score", never disease probability.
- **Explanation:** Grad-CAM class-targeted = BASELINE REQUIREMENT (gradients enabled; "Attribution unavailable" on failure); nearest-example DEFERRED; hard wording constraints (not segmentation/causal/proof/substitute for pathologist).
- **Mixed set (53):** separate "mixed-state challenge set" (score balance / entropy / margin / saliency / human-review), tagged subset, never a 4th class, never in headline.
- **Model selection:** per-fold eval models (discarded after held-out scoring) vs eventual final demo model (fit on all eligible groups AFTER eval frozen; its train performance never reported as eval). Train nothing now.
- **Reproducibility:** full record list frozen; one seed ≠ stability; optional later multi-seed sensitivity.
- **Claims:** exploratory/educational/case-slide-group(4)/patch-level only; NOT patient-level/clinical/diagnostic/treatment-response/prognosis/necrosis-%; patch counts not independent biological samples.

### G2 change flags: NONE. All G2 files preserved unchanged. (Image QC remains a known-PENDING G2 dependency, B2/AWS-blocked — a dependency, not a G2 defect.)

### G3 verdict: PASS WITH LIMITATIONS
All 14 PASS criteria met as a design; verdict is PASS WITH LIMITATIONS because the 4-group structure (P9 single-class; sparse NECROSIS=2 / VIABLE=3; case/slide-group not patient independence; calibration not defensible; nested CV untrustworthy; image QC pending) materially restricts the achievable evaluation even though the design is complete.

### Files created (absolute paths)
- `aidlc-docs\inception\model\model-contract.md`
- `aidlc-docs\inception\model\preprocessing-contract.md`
- `aidlc-docs\inception\model\augmentation-policy.md`
- `aidlc-docs\inception\model\evaluation-protocol.md`
- `aidlc-docs\inception\model\logo-fold-plan.csv`
- `aidlc-docs\inception\model\uncertainty-review-policy.md`
- `aidlc-docs\inception\model\claim-boundaries.md`
- `aidlc-docs\inception\model\experiment-matrix.csv`
- `aidlc-docs\inception\model\g3-validation-report.md`

### Files updated
- `aidlc-docs\audit.md` (this entry)
- `aidlc-docs\aidlc-state.md` (G3 row + decision summary + next step)
- Scratch `aidlc-docs\inception\model\_G3_BRIEF.md` deleted on completion.

### Preserved unchanged (all G2 + prior)
`inception\data\*` (canonical_manifest.csv, label_aliases.json, group_class_distribution.csv/.md, split-proposal.md, mixed-patch-policy.md, image-ingestion-plan.md, g2-validation-report.md, dataset-card.md, manifest.csv, data_audit.json, duplicate-report.md, patient_mapping_evidence.md, aspera-cli-feasibility.md) and all `inception\*` inception artifacts.

### Next gate (single recommendation)
**Image QC gate** — authorize the bounded test fetch in `inception\data\image-ingestion-plan.md` (resolve AWS access B2 first) to verify pixel dims / channels / bit depth / decode / SHA-256 / perceptual dedup, confirming the preprocessing items marked VERIFY AT IMAGE QC GATE before any training. No training until pixels QC-verified and G3 signed off.


## 2026-10-03 — Image QC gate (bounded sample) EXECUTED — PASS WITH LIMITATIONS

- Scope honored: QC only. **No training, no AWS/S3, no deploy, no full-collection download, no G2/G3 edits.** `@kirocrew-computer` MCP server was unavailable (not configured) — not needed; all work done with standard tools.
- Isolated scratch venv at `C:\Users\enkso\.kiro\crew\scratch\runtime-64fa3dc5\osteopatch-qc\.venv` (CPU, credential-free): Python 3.12.10, pandas 3.0.6, requests 2.34.2, pillow 12.3.0, imagehash 4.3.2, numpy 2.5.3. QC images isolated OUTSIDE project at `...\osteopatch-qc\qc_sample\`.
- **Deterministic bounded sample (seed 42): 31 images** of 1,144, covering all 4 groups × 3 trainable classes where available + 3 MIXED + 23 source-folder-sets.
- **PathDB retrieval 31/31 = 100%** over plain HTTP (301 HTTP→HTTPS then 200, `image/tiff`, chunked/no Content-Length, Accept-Ranges bytes). Total **7.69 MB** (under 25 MB per-file + 400 MB total caps; no abort).
- **Format** 100% TIFF-LE (magic `II*\x00`, matches ext). **Decode** 31/31 Pillow full-load, 0 corrupt. **Dims** 100% 1024×1024. **Channels** 100% RGB/3ch/no-alpha. **Bit depth** 8-bit. → 384×384 = ACCEPTABLE WITH RESIZING (confirmed, uniform downscale no crop); RGB→ImageNet-norm safe.
- **Content QC:** 2 flagged (QC-006, QC-012; both NON_TUMOR, near-blank/low-entropy) → human-reviewable, NOT deleted. **Exact dups 0** (byte + pixel). **Perceptual near-dups 0** pairs → no cross-group/cross-label leakage signal. **Manifest** 31/31 1:1, only the expected 301 redirect, 0 mismatches.
- **Label plausibility:** QC-012 marked REQUIRES HUMAN REVIEW; no relabeling. **No G2/G3 contradiction → no CHANGE REQUEST.** All 8 testable G3 pixel assumptions CONFIRMED on sample (3 conditional branches not triggered).
- **Verdict: PASS WITH LIMITATIONS** — bounded sample supports proceeding; full 1,144-collection ingestion QC still required before training.
- Artifacts under `inception/image-qc/`: qc-sample-manifest.csv, image-qc-results.csv, dimension-summary.csv, duplicate-analysis.csv, label-plausibility.csv, preprocessing-verification.md, full-ingestion-qc-contract.md, image-qc-report.md, contact-sheets/ (10 PNGs). `_IMAGE_QC_BRIEF.md` deleted on completion. All G2/G3 files preserved.

---

## 2026-10-03 — Full-Collection Image Ingestion QC gate EXECUTED (resumed) — PASS WITH LIMITATIONS

- Scope honored: QC only. **No training, no AWS/S3, no SageMaker, no deploy, no tuning, no secondary experiments, no G2/G3 edits.** `@kirocrew-computer` MCP server unavailable (not configured) — not needed; all work with standard tools.
- **Resumed** from persisted scratch (`...\runtime-0a306834\osteopatch_full_ingestion\`): existing `.venv` (requests 2.34.2 / Pillow 12.3.0 / imagehash 4.3.2 / numpy 2.5.3), `tiffs\`, and append-only `ingestion_ledger.jsonl` reused. Venv NOT rebuilt; ledger NOT recreated; disk preflight (66.66 GB free) NOT repeated.
- **Ledger integrity:** 98 pre-cached objects re-verified by SHA-256 (98/98 match, 0 mismatch, 0 missing). Acquisition resumed from row 99; 1,046 remaining fetched via credential-free PathDB HTTP→HTTPS (301→200). Two rows (`Case-3-A14-34515-24089`, `Case-3-A14-34677-35228`) hit a transient Windows rename lock (`WinError 32`, not an HTTP error) and were re-fetched cleanly with a rename-retry loop.
- **Reconciliation: 1,144/1,144** — retrieved 1,144, persistent failures 0, missing-from-ledger 0, duplicate manifest/PathDB/URL IDs 0, unexpected extra local files 0. canonical_manifest.csv is source of truth; deterministic image_id→file mapping.
- **Decode QC:** Pillow full-load (truncation-as-failure) 1,144/1,144 OK, 0 CORRUPT. Format 100% TIFF-LE (magic bytes), 100% **1024×1024**, 100% **RGB** 3-channel no-alpha, 100% **8-bit** → **full-dataset preprocessing CONFIRMED** against frozen G3; 0 exceptions.
- **Content QC (non-semantic):** NEAR_BLANK 23, LOW_INFORMATION 59, VERY_BRIGHT 8, LOW_VARIANCE 1 → routed to REVIEW, never auto-deleted.
- **Three-tier dedup:** byte-SHA-256 exact dups **0 groups**; decoded-RGB pixel-SHA-256 identical **0 groups**; perceptual pHash(+dHash) candidates (Hamming ≤10) **3 pairs**, all second-stage pixel-confirmed (MAD/255) — **0 reached pixel-equivalence** (MAD<2.0). Perceptual similarity alone never treated as duplication.
- **Cross-group leakage audit (Case-3/Case-4/Case-48/P9):** **0 confirmed/blocking.** The one cross-group perceptual pair (`Case-48-P5-C25-44980-18952` ↔ `P9-B27-21147-30384`, hd=10, pixel MAD≈18.8/255) classified `UNCONFIRMED_PERCEPTUAL_SIMILAR`, held in REVIEW, does NOT block training. **Label-conflict audit: 0** conflicts on identical/near-identical data.
- **Per-row status (exactly one each):** PASS 1081, REVIEW 59, NEAR_DUPLICATE_CANDIDATE 4. **training_eligible:** NON_TUMOR 484 + VIABLE_TUMOR 290 + NECROSIS 254 = **1,028**; excluded 116 = 53 MIXED (policy, always false) + 59 content-REVIEW + 4 near-dup candidates. Every false carries an explicit reason. Counts reconcile: 1,028 + 116 = 1,144.
- **No G2/G3 CHANGE REQUEST** — full-collection evidence confirms frozen preprocessing/split assumptions. No LOGO break (no fold folders, no image copied into docs tree).
- **Scratch footprint 287.7 MB** (under 1 GB soft cap); TIFFs remain in scratch only, never in the project tree or Git.
- **Verdict: PASS WITH LIMITATIONS** — collection structurally sound; 63 trainable-label rows (59 REVIEW + 4 near-dup) intentionally unresolved + excluded pending human review. No structural failure.
- Artifacts under `inception/full-image-qc/`: full-ingestion-manifest.csv, full-image-qc-results.csv, dimension-channel-summary.csv, content-qc-outliers.csv, exact-duplicate-analysis.csv, near-duplicate-analysis.csv, cross-group-leakage-audit.csv, human-review-queue.csv, training-eligibility-summary.csv, full-image-qc-report.md, training-input-contract.md, contact-sheets/ (4 populated: near-blank-low-info, color-intensity-outliers, perceptual-near-dup-candidates, cross-group-dup-candidates; 3 zero-finding documented). `_FULLQC_BRIEF.md` deleted on completion. All prior-gate files preserved.

---

## 2026-10-03 — G5 Bounded Last-Stage Encoder Fine-Tuning EXECUTED — NO BENEFIT

- Scope honored: ONE prespecified experiment only. **No architecture/augmentation/loss/hyperparameter search, no multi-seed, no calibration, no Grad-CAM, no uncertainty tuning, no UI/API, no AWS, no deploy, no G2/G3/QC rerun, no re-download.** One focused worker.
- **G4 is the immutable comparator — all G4 artifacts preserved unchanged** (verified: g4/ last-modified 10:34–10:37 PM, before G5's 11:06+ writes).
- **Note on run completion:** the worker runtime process was killed at teardown (provider shutdown) AFTER all compute finished and all 16 G5 durable artifacts were written (11:06–11:09 PM). The result was certified by reading the on-disk artifacts directly and independently re-checking the arithmetic (confusion rows reconcile to supports 484/290/254=1,028; VIABLE recall 13/290=0.0448; viable→necrosis/non_tumor/correct deltas −37/+56/−19 reconcile). The two teardown steps the kill interrupted — this audit entry and the aidlc-state.md update — were completed by the parent, and `_G5_BRIEF.md` was deleted.
- **The one bounded change:** start = MobileNetV3-Small `IMAGENET1K_V1`, fresh 3-output head; unfreeze ONLY `features[12]` (final feature stage: Conv 96→576 1×1 + BN576 + Hardswish) + `classifier`. **Trainable = 7 tensors / 650,371 params**; frozen 135 tensors / 870,560 params. Per-fold named-parameter assertion `only_finalstage_and_head_trainable` PASS (`unexpected_trainable=[]`, `expected_but_frozen=[]`). BN kept in eval (frozen running stats) per G3/G4 convention.
- **Device/runtime:** CPU (torch 2.14.1+cpu; CUDA unavailable → sanctioned fallback, no AWS). Fold times Case-3 89.2s / Case-4 172.7s / Case-48 271.8s / P9 218.4s; total 752s (~12.5 min). No OOM, batch 16 stable, no retries.
- **Reused frozen G4 inputs:** manifest SHA-256 `8b462ead87d0ffa3617e2d2afadbbf6ca685b85240e3349432408f352cf7e9ba` **re-hashed at start → MATCH** (no hard stop); same 1,028 cohort (NON 484 / VIABLE 290 / NEC 254), same 4 LOGO groups, class order, 384² preprocessing, D4 train-only aug, fold-local train-only weighted CE, seed 42.
- **Pre-run tests: 15/15 PASS, 0 failures** (manifest hash match, class order, 1,028 eligible-only, four groups+support, LOGO zero outer-group contamination, each image outer-test once, train-only fold weights, train≠eval transforms, eval matches 3×384×384 inference contract, excluded QC rows stay excluded, no cross-group leakage flag, 3 finite logits, probs sum to 1, **only final-stage+head trainable**, absent-class UNAVAILABLE).
- **Result (pooled OOF 1,028): macro-F1 0.5229 (G4 0.5623, Δ −0.0394), bal-acc 0.6009 (Δ −0.0255), acc 0.6430 (Δ −0.0272), log-loss 1.1993 (Δ +0.0046 worse), Brier 0.5524 (Δ +0.0563 worse).** Per-class F1 NON 0.790 (Δ −0.052) / VIABLE 0.075 (Δ −0.104) / NEC 0.703 (Δ +0.038).
- **Primary targets regressed:** VIABLE_TUMOR recall 0.1103→0.0448 (Δ −0.0655), VIABLE F1 0.1793→0.0751 (Δ −0.1041), VIABLE precision 0.478→0.232 (Δ −0.245).
- **VIABLE→NECROSIS errors 153→116 (−37) but NOT a real gain:** VIABLE→NON_TUMOR rose 105→161 (+56) and VIABLE correct fell 32→13 (−19). Fine-tuning merely relocated viable's confusion from necrosis to non-tumor while reducing true positives.
- **Fold macro-F1 (G4→G5):** Case-3 0.589→0.560, Case-4 0.614→0.547 (the one balanced 3-class fold regresses), Case-48 0.281→0.231, P9 0.995→1.000 (single-class; VIABLE/NEC UNAVAILABLE, not manufactured). Training loss fell monotonically every fold → last-stage overfitting to case-specific features on a 4-group cohort.
- **Decision: NO BENEFIT** (measured; no post-hoc significance threshold invented). Primary targets moved the wrong way, NON_TUMOR also down, calibration worse, regression consistent across the two informative folds; the lone "positive" (viable→necrosis −37) fully explained by larger viable→non_tumor rise + fewer viable correct.
- **No final G5 bundle created** (bundle only if PROMISING). `baseline-frozen-g4` stays the prototype default; no misleading "improved" replacement. Diagnostic fold checkpoints in scratch (`osteopatch_g5/checkpoints/`), hashes recorded in `g5/fold-checkpoint-hashes.json`.
- **16 durable artifacts** in `inception/model/g5/`: run-configuration.json, trainable-parameter-inventory.json, test-report.json, fold-histories.json, fold-checkpoint-hashes.json, g5-oof-predictions.csv (1028 rows), per-fold-metrics.json, overall-oof-metrics.json, confusion-matrix.csv, g4-vs-g5-metric-comparison.json, g4-vs-g5-confusion-comparison.json, viable-to-necrosis-error-comparison.json, g4-vs-g5-fold-comparison.json, training-run-summary.json, g5-summary.md, model-card-addendum-g5.md.
- **Recommendation:** keep `baseline-frozen-g4` as default; do NOT pursue broader fine-tuning on this 4-group cohort (the minimal variant already overfits). The VIABLE_TUMOR ceiling is a **data-scope / group-count** limitation (4 slide groups, viable concentrated in Case-4/Case-48), not last-stage capacity — widen case/group coverage for VIABLE before further adaptation. Multi-seed / calibration / Grad-CAM / uncertainty remain future approval-gated steps.
- **Verdict: G5 — FINE-TUNING REVIEW REQUIRED (NO BENEFIT).** STOPPED; no fine-tune beyond this, no Grad-CAM/uncertainty/multi-seed/calibration/UI/AWS/deploy.


---

## 2026-10-03 — G6 Local OsteoPatch Review MVP EXECUTED — LOCAL PRODUCT REVIEW REQUIRED

- Scope honored: build the working local review app only. **No fine-tune, no architecture search, no multi-seed, no re-train, no G4/G5/QC rerun, no re-download, no AWS, no Docker/Redis/Postgres/auth/paid API/LLM, no Grad-CAM, no public deploy.** Model decision frozen: `baseline-frozen-g4` is the prototype default; the failed G5 model is NOT used. One focused implementation worker.
- **Note on run completion (same pattern as G5):** worker `bc7dd1d9` runtime process was killed at teardown (provider shutdown) AFTER all source, the SQLite DB, the frontend install/build, and the test runs were written to disk. The parent did NOT re-dispatch. It certified the result **live from disk**: recreated the torch-free web venv the kill destroyed, re-ran the full backend + frontend suites, independently ran the 12-step acceptance path against the real app over a copy of the real DB, probed the DB, then completed the teardown steps the kill skipped — g6-summary.md, test-report.json, e2e-acceptance-evidence.json, app/g6/README.md, this audit entry, the aidlc-state.md update — and deleted the stray `_G6_BRIEF.md`. **All G4/G5 artifacts untouched.**
- **Stack:** backend FastAPI 0.115.6 / uvicorn 0.34.0 / pydantic 2.10.4 / Pillow 11 / SQLite (torch-free server; torch 2.14.1+cpu used only by precompute.py). Frontend React 18.3 / TypeScript 5.7 / Vite 6 / Vitest 2.1.9. Two-venv design by intent (torch for precompute, torch-free web venv for server+API tests) so the browser never waits on PyTorch.
- **Model loaded:** `baseline-frozen-g4`, bundle SHA-256 `01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63` — re-verified at load; loader + precompute REFUSE on mismatch (`test_hash_mismatch_refuses` green). Canonical order [NON_TUMOR, VIABLE_TUMOR, NECROSIS]; preprocessing taken from the bundle (384² full-field resize + pinned ImageNet norm).
- **Indexed/precomputed:** 1,144 source patches (`source_qc`); **1,144 immutable predictions**, 0 duplicate (image_id, model_bundle_hash) groups, all carrying the frozen G4 hash; each row has 3 scores + top1 + top_two_margin + normalized_entropy + inference_kind=`prototype_inference`. Prediction class dist (prototype inference, NOT eval): NON_TUMOR 510 / VIABLE_TUMOR 330 / NECROSIS 304 — kept separate from the frozen G4 OOF evidence; no headline metric recomputed.
- **API (13 endpoints):** /v1/health, /v1/meta, /v1/model-card, /v1/images (sort/filter/search/paginate), /v1/images/{id}, /v1/predictions/{id} (read-only), /v1/images/{id}/thumbnail, /v1/images/{id}/full (127.0.0.1-only, path-traversal-safe), /v1/images/{id}/review (state+revision+history), POST /v1/images/{id}/reviews (201/200-idempotent/409/422/404), /v1/exports/reviews?format=csv|json.
- **Tests (all re-run live by parent):** backend **34/34** = 5 torch real-bundle (hash match, mismatch-refuses, 3 canonical outputs, preprocessing parity, scores sum to one) + 29 API/safety/scoring (gallery sort/filter, 201/409/422/404, idempotent replay, append-only, prediction-immutable-after-correction, export preserves both, canonical order, no-4th-class, deterministic ranking, entropy bounds, dedup). Frontend **9/9** vitest + clean `vite build`. **E2E 12/12** acceptance path pass.
- **Review-priority (deterministic, NOT calibrated):** smallest top_two_margin → highest normalized_entropy → stable image_id. Raw values exposed in UI; scores labelled "Model score — uncalibrated"; no confidence %/threshold tuning/error-prediction. The 63-row data-QC queue kept as a separate `QC REVIEW` badge, never merged with model review-priority.
- **Prediction immutability proven:** E2E step 9 + `test_prediction_immutable_after_correction` — after CORRECT (NON_TUMOR→VIABLE_TUMOR), GET /v1/predictions/{id} still returns NON_TUMOR with identical scores; the correction lives only as a new append-only review_event (revision 0→1).
- **Export evidence:** CSV + JSON emit one row per image with BOTH the model prediction (model_predicted_class, model_score_*, hash, inference_kind) AND the current human state (human_latest_action, human_corrected_class, human_defer_reason, human_note, human_revision_number, review_event_ids) + disclaimer + model hash. 1,144 rows; header verified.
- **Safety guards:** idempotent replay (same key → 200, no dup); stale expected_revision → 409; ACCEPT-no-contradiction / CORRECT-valid-class / DEFER-no-class validation; unknown image/prediction → 404; wrong image↔prediction relationship → 422; server binds 127.0.0.1 only (never 0.0.0.0).
- **Deviations from frozen product requirements: none of substance.** Only notable choice = the deliberate two-venv split (serves "browser must not wait on PyTorch"); not a contract change. Screenshots not captured this pass (no headless browser driven) — documented, NOT fabricated; the G7 "Model attribution — coming in G7" tab is reserved and intentionally empty.
- **Artifacts:** app source under `app/g6/backend/` (osteopatch pkg: config/scoring/model/db/repo/queries/images/modelcard/app/server, migrations/0001_initial.sql, precompute.py, requirements.txt, tests/) and `app/g6/frontend/` (App + components Workbench/PatchReview/ImageViewer/ReviewPanel/ModelCard/Shared, api/types/strings, test/ui.test.tsx); `app/g6/README.md` (local run). G6 gate artifacts under `inception/model/g6/`: g6-summary.md, test-report.json, e2e-acceptance-evidence.json. Runtime data (scratch, out of git): osteopatch_g6/osteopatch_g6.sqlite3 (+wal/shm), thumbnails, webvenv. `_G6_BRIEF.md` deleted.
- **Recommendation:** open **G7 — Model attribution (Grad-CAM)** on the frozen baseline, filling the reserved UI tab with class-targeted overlays (local, no AWS, no new modeling). Secondary separately-gated: capture live UI screenshots, multi-seed sensitivity of G4, triage the 63-row data-QC queue.
- **Verdict: G6 — LOCAL PRODUCT REVIEW REQUIRED.** STOPPED; no G7/Grad-CAM/AWS/deploy without review.


---

## 2026-10-04 - R1 Recovery Gate - R1-A/R1-B DONE & CLEAN - HOLDING at model-reconstruction fork

- Scope honored for this step: path-common recovery ONLY (durable storage + re-materialize/verify the 1,144 source images + thumbnails). **No head reconstruction, no retrain, no G5, no LOGO/OOF rerun, no architecture/recipe change, no multi-seed, no alternative XAI, no AWS, no deploy, no G7.** One focused worker; `drawio` MCP server unavailable this session (failed to start) - not needed.
- **Why:** the load-bearing G4 runtime artifacts (final `.pt` bundle, D4 embedding cache, 1,144 decoded TIFFs, torch venv, training/precompute script) lived only in reclaimable scratch (`runtime-0a306834\osteopatch_g4` + `osteopatch_full_ingestion`) and were reclaimed. Survived: all frozen durable docs, and in scratch the **G6 SQLite** (1,144 immutable predictions keyed on original hash `01727fb8...`, **0 review events**) + the torch-free **web venv**.
- **R1-A:** created durable `runtime-artifacts/` (`images/ models/ thumbnails/ recovery/`) at the project root. Added a repo-root `.gitignore` and an app `.gitignore` entry so raw TIFFs + model binaries are NEVER committed (project tree is not a git repo yet; rules are defensive). Durable root documented here, in `aidlc-state.md`, and in `runtime-artifacts/recovery/r1-recovery-summary.md`.
- **R1-B:** re-fetched all **1,144** source TIFFs from the frozen manifest's public PathDB `image_url` (no credentials), streaming one image at a time with retry+backoff and a resumable ledger. Each object verified against the frozen `sha256` + `byte_size` and decode-checked `mode==RGB` / `dims==1024x1024` vs frozen QC. **Result: 1,144/1,144 VERIFIED & written, 0 integrity mismatches, 0 fetch/decode failures.** Independently re-verified from disk (1,144 files; ledger all VERIFIED; random re-hash spot-checks match). ~74 min single-stream, memory-safe. Rebuilt **1,144** durable thumbnails (RGB->256px->PNG, mirroring `images.py`).
- **Reconstruction env prepared (not used to retrain):** torch venv rebuilt to the exact frozen G4 env (py 3.12.10 / torch 2.14.1+cpu / torchvision 0.29.1+cpu / numpy 2.5.3 / pillow 12.3.0 / sklearn 1.9.1 / CPU). Frozen encoder confirmed deterministic + cross-load identical (max abs diff 0.0).
- **HELD at the one-way-door fork:** the final all-data head (`Linear(1024->3)`) weights + its training script + RNG stream are unrecoverable (surviving OOF = per-fold models, not the final model, and differ from stored final scores). A faithful recipe-retrain yields a *different* model whose raw softmax scores cannot meet the brief's strict <=1e-6 parity vs the stored predictions (predicted-class parity is plausible: median stored margin 0.97, only 1 patch <0.01). The brief forbids entering Grad-CAM on a merely "similar" model. **Owner decision required** on what "the recovered model" may be (fit-to-stored-predictions vs faithful-retrain-with-documented-tolerance vs faithful-retrain-strict-STOP-if-fail) before any reconstruction/retrain/G7.
- **Process lesson recorded:** load-bearing frozen runtime artifacts must NEVER exist solely in reclaimable scratch storage. Artifact classes: raw TIFFs + model bundles = DURABLE RUNTIME DEPENDENCY (`runtime-artifacts/`); thumbnails = EPHEMERAL/REBUILDABLE; recovery ledger/manifest/report = DURABLE EVIDENCE.
- **Artifacts:** `runtime-artifacts/images/` (1,144 TIFFs), `runtime-artifacts/thumbnails/` (1,144 PNGs), `runtime-artifacts/recovery/{source-image-recovery-ledger.csv, recovery-manifest.csv, integrity-check-report.json, r1-recovery-summary.md}`. `runtime-artifacts/models/` intentionally empty pending the fork decision. All scratch helper scripts kept under `KIROCREW_SCRATCH` (`runtime-e7b05a83`), none in the project tree.



---

## 2026-10-04 - R1-C behavioral head recovery COMPLETE + G7 built - DOC-SYNC correction

- **What this entry corrects:** the prior `2026-10-04 ... HOLDING at model-reconstruction fork`
  entry above remains a true record of state AT THAT TIME. This entry records that R1-C was
  subsequently EXECUTED and VERIFIED on disk, but its own teardown doc-update step never landed
  because the R1-C worker was killed at teardown (the recurring provider-shutdown-at-teardown
  pattern seen on G5/G6). `aidlc-state.md` and `r1-recovery-summary.md` were left describing the
  fork as still-pending and `models/` as empty. Discovered while investigating a "stale subagent
  in the other chat" report. No subagent was running (spawn_list clean); the staleness was two
  outdated state docs, not a hung process.
- **Fix applied (docs only; no work re-run, no clobber):** corrected `aidlc-state.md` (header
  phase/current-gate, R1 decision-summary paragraph, gate-ledger R1 row, Next-step section) and
  `r1-recovery-summary.md` (status line, HELD->RESOLVED section, models/ path list) to match the
  verified on-disk artifacts. Per the standing lesson, finished the killed worker's skipped
  doc-update step directly rather than re-dispatching (which could overwrite a valid result).
- **Verified on-disk evidence used (not re-run):**
  - `recovery-run-report.json`: `stage=complete`, `accept=true`, `classification=BEHAVIORALLY_VERIFIED_RECOVERY`;
    parity `max_abs_score_diff 2.38e-07` (< atol 1e-6), 1144/1144 predicted-class agreement, 0 outside atol;
    lstsq log-odds RMSE ~1.25e-07; zero-sum gauge (`sum_c W_c=0`, `sum_c b_c=0`).
  - `recovery-reload-stability.json`: `reload_vs_committed_max_abs_diff 4.99e-13`, reload_stable true.
  - `g7-target-layer-and-gauge-invariance.json`: target layer `model.features[-1]` (spatial 12x12,
    target-sensitive), gauge-invariance verdict PASS (contrastive CAM invariant 7.8e-07; single-class CAN change).
  - `runtime-artifacts/models/`: `g4-behavioral-recovery-r1.pt` (hash `ffff1282...`, distinct from
    original `01727fb8...` which is never reassigned), `r1-embeddings.npy` (1144x1024), head weight/bias,
    pairwise coefficients.
  - Live G7 app code: `osteopatch/attribution.py` + `/v1/images/{id}/attribution[/meta]` endpoints
    (contrastive logit_A-logit_B, lazy torch, on-demand+cached), `tests/test_attribution.py` (18 tests collected).
- **Outcome:** R1 fork RESOLVED via path 1 (fit the head to the surviving immutable predictions ->
  exact score parity by construction). Current gate is now **G7 - MODEL ATTRIBUTION REVIEW REQUIRED**.
  Still owner-gated: sign-off of the behaviorally-recovered model as "the recovered model" + review of G7;
  no screenshots/multi-seed/calibration/uncertainty/AWS/deploy until then.


---

## 2026-10-04 — R1-C2 behavioral recovery + G7 contrastive attribution CERTIFIED (owner-approved, local, no AWS/retrain)

Owner approved Recovery Gate R1 then R1-C2 (behavioral reconstruction of the lost G4 linear head) and a revised G7 using contrastive Grad-CAM only. Executed across focused workers; final certification completed directly by the parent from disk + a live run after the certification worker was interrupted at the screenshot step (its backend/frontend test reports were already persisted).

### R1-C2 — behavioral head recovery (BEHAVIORALLY_VERIFIED_RECOVERY)
- Lost original head weights of `baseline-frozen-g4` (sha256 `01727fb8…`) are irretrievable; recovered the observable decision function instead. Recovered encoder bit-identical (sha256 `331b88ec…`). Embeddings 1144×1025, rank 1025, cond ~2744, log-odds LSQ RMSE ~1.2e-7, no regularization. Canonical zero-sum gauge.
- Recovered model `g4-behavioral-recovery-r1` (sha256 `ffff1282…`), distinct identity; G6 predictions NEVER rewritten.
- Parity vs surviving G6 oracle: 1,144/1,144 predicted-class (100%); max 2.4e-7 / mean 7.8e-9 / p95 1.2e-7; 0 rows outside 1e-6 (tolerance justified by G6 REAL precision ~5e-7@6dp). Reload 4.9e-13.
- Gauge-invariance test PASS (single-class CAM changes 0.75; contrastive A−B invariant 7.8e-7). Target layer `model.features[-1]` [1,576,12,12].
- Evidence: runtime-artifacts/recovery/recovery-run-report.json, g7-target-layer-and-gauge-invariance.json, recovery-prediction-parity.csv (1144 rows).

### G7 — contrastive attribution (certified live)
- grad-cam 1.5.5; target `model.features[-1]`; custom scalar target `logit_A − logit_B` (gauge-invariant); default pair = suggested vs runner-up; 6 selectable pairs; deterministic cache (cold==cached verified).
- Backend tests (evidence/backend-test-report.json): torch-free .venv 53 passed/0 failed/10 skipped; torch venv 62 passed/0 failed/5 skipped (5 = test_real_bundle.py gating on original scratch bundle, forbidden to touch — expected).
- Frontend (evidence/frontend-test-report.json): vitest 18/18; clean tsc+vite build, 0 TS errors.
- E2E/G6 regression (evidence/e2e-result.json): PASS 11/11 against a SCRATCH COPY; original prediction byte-identical + still baseline-frozen-g4/01727fb8; CORRECT+DEFER persist; export intact.
- Live attribution (evidence/attribution-live-check.json): PASS; VIABLE-vs-NECROSIS (1c759906) ≠ NECROSIS-vs-VIABLE (e2cff287). Latency CPU: cold ~7.2s (one-time load), cached ~35ms, warm ~113–142ms.
- Real screenshots (evidence/screenshots/): A-workbench, B-review-screen, C-attribution-overlay, D1-viable-vs-necrosis, D2-necrosis-vs-viable, E-review-history.
- Immutability/durability: durable DB runtime-artifacts/db/osteopatch_g6.sqlite3 review_event=0, 1,144 predictions all baseline-frozen-g4. Durable runtime deps under runtime-artifacts/ (gitignored).
- Summary: runtime-artifacts/recovery/g7-summary.md.

### Process lesson recorded
Load-bearing frozen runtime artifacts must never exist solely in reclaimable scratch. Classify: ephemeral/rebuildable (thumbnails, caches) · durable evidence (recovery reports) · durable runtime dependency (recovered model bundle, source TIFFs, review DB) — the last belong under runtime-artifacts/.

**Verdict: G7 — ATTRIBUTION / VISUAL REVIEW REQUIRED** (implementation complete + certified; awaiting owner visual review). No AWS/deploy/calibration/uncertainty-tuning performed.


---

## 2026-10-04 — G8 AWS Deployment / Hackathon Demo CERTIFIED (owner-approved, 50-image subset, us-east-1)

Owner approved deploying the certified G7 app to the workshop account using a deterministic 50-image representative subset. Deployed via CDK (stack OsteoPatchG8); final live validation + screenshots completed directly by the parent after the deploy worker wedged on a non-returning playwright-cli open (certified from AWS + the live CloudFront URL, not the worker's completion flag).

### Architecture (cost-minimal; SCP denied App Runner, so Lambda-container route)
- Frontend: private S3 osteopatch-web-153485202811 + CloudFront (OAC) → https://dgv0wpd8tglrw.cloudfront.net
- Backend: Lambda container image osteopatch-api (3008 MB/90 s, torch+grad-cam, lazy-torch serve) + API GW HTTP API wx414e64ja
- Review state: DynamoDB on-demand osteopatch-reviews (thin adapter, same domain model; prediction immutable, append-only reviews)
- Assets: recovered model + 50 TIFFs (11.7 MiB) + 50 thumbnails (5.4 MiB) in private S3 osteopatch-artifacts-153485202811
- IaC under app/g6/deploy/ (CDK). Workshop role WSParticipantRole = AdministratorAccess.

### Live validation (all 15 PASS against CloudFront)
Health: model baseline-frozen-g4 / bundle 01727fb8… / images_indexed 50 / predictions 50; /v1/images total=50. Subset banner visible ('deterministic 50-image representative subset … 1,144 patches'). Workbench + 50 real thumbnails + review-priority sort; patch opens, 3 scores; contrastive Grad-CAM live (VIABLE vs NECROSIS + reverse, hint flips, overlay recomputes) via the torch Lambda; CORRECT saved → persisted to DynamoDB (revision 1), survives reload (patch 'Reviewed', history #1); export /v1/exports/reviews = 50 rows incl. the CORRECT, model baseline-frozen-g4; model-attribution + behavioral-recovery disclaimers visible. Demo review cleaned afterward (reviews table back to 0 → pristine). Original prediction identity preserved (baseline-frozen-g4/01727fb8); recovered model id g4-behavioral-recovery-r1 never conflated.

### Evidence
Screenshots: runtime-artifacts/evidence/g8/screenshots/ (A workbench, B review, C attribution, D1 viable-vs-necrosis, D2 necrosis-vs-viable, E review-history). Subset ids: runtime-artifacts/recovery/g8-subset-image-ids.json. Summary: aidlc-docs/g8-deployment-summary.md.

### Cost / teardown
~$0 demo window; ~$0.20–0.30/mo if left running (ECR image + S3). Teardown: cdk destroy OsteoPatchG8 + empty asset bucket. No GPU/SageMaker/RDS/NAT/App Runner. No new training/calibration/architecture expansion; did NOT upload the other 1,094 images.

### Security / exposure
Educational prototype, no patient-identifiable data. Private S3 (OAC), no public bucket. Review WRITE endpoint open on the demo API (bounded, no auth) — documented limitation acceptable for hackathon. Disclaimers visible in-UI.

**Verdict: G8 — DEPLOYED DEMO REVIEW REQUIRED** (deployed + live-certified; awaiting owner review). Local runtime preserved; redeploy reproducible from the durable tree.
