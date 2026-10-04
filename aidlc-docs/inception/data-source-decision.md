# Data-source decision (G1) — Inception

**Status:** G1 **UNRESOLVED / BLOCKED** pending owner answer to Q1 and an object-level access check. This document records what is verified, what is not, and the one decision the owner must make. It does **not** approve any download or training.

Canonical class order (fixed): `NON_TUMOR` (0), `VIABLE_TUMOR` (1), `NECROSIS` (2).

---

## 1. The requirement in question

The owner supplied the **AWS NCI Imaging Data Commons (IDC) collections registry** as the intended source. G1 must answer: *do the required labelled three-class patches and their patient mapping actually come from the IDC/AWS source, or is the exact-match TCIA public collection an acceptable (explicitly approved) route?*

**Rule: do not silently substitute.** TCIA Osteosarcoma-Tumor-Assessment is a *candidate*, not an approved replacement for IDC.

---

## 2. Verified without credentials or download (read-only web)

### IDC / AWS Open Data (registry page)
- IDC public buckets: `s3://idc-open-data/`, `s3://idc-open-data-two/`, `s3://idc-open-data-cr/`.
- Region: **`us-east-1`**. Access: `--no-sign-request` (no AWS account needed to list/read).
- **All IDC image content is stored as DICOM** and distributed under CC-BY (the `-cr` bucket is CC-NC).

### TCIA Osteosarcoma-Tumor-Assessment (candidate, from official listing + indexed metadata)
| Property | Value |
|---|---|
| Public cohort | 4 selected patients (of a 50-patient archive) |
| Patch images | 1,144 · 1024×1024 px · 10× |
| Class counts | Non-tumor 536 · viable tumor 345 · necrotic tumor 263 |
| Files / size | **JPG** images (~196.84 MB) + **CSV** annotations |
| Annotation | Predominant class; one annotator/image across two experts |
| License | **CC BY 3.0** — attribution + data citation required |
| DOI | `10.7937/tcia.2019.bvhjhdas` |
| Folders | `Training_Set_1`, `Training_Set_2` — folder names, **not** a validated ML split |

Attribution to preserve if TCIA is approved: Leavey, P., Sengupta, A., Rakheja, D., Daescu, O., Arunachalam, H. B., & Mishra, R. (2019). *Osteosarcoma data from UT Southwestern/UT Dallas…* The Cancer Imaging Archive. DOI 10.7937/tcia.2019.bvhjhdas.

---

## 3. The core gap (why this is blocked)

**The two sources are different formats.** The TCIA collection's defining assets are **labelled JPG patches + a three-class CSV**. IDC's AWS buckets hold **DICOM**. Even if osteosarcoma slide imagery from this cohort is mirrored into IDC as DICOM, that does **not** guarantee the per-patch three-class labels and patient mapping are present there in a usable form.

**Unverified (honest boundary):**
- Whether the exact Osteosarcoma-Tumor-Assessment collection — with its three-class labels and patient-level mapping — exists as retrievable objects in the IDC AWS buckets.
- Its IDC `collection_id`, S3 prefix, object manifest, and total bytes.

**Correction (2026-10-03, after owner review):** an earlier version of this doc said missing AWS credentials blocked the check. That conflated two things. IDC's public buckets allow **anonymous** access (`aws s3 ls --no-sign-request s3://idc-open-data/`) with **no AWS account** — the AWS registry documents this. So the real limitation was only the missing AWS **CLI tool**, not any credential. Credential-free discovery is therefore legitimate and does **not** require the owner to configure or paste any secret. The correct no-credential route is the official **`idc-index` Python client** [S17], which queries IDC collection/series metadata and can access public data without cloud credentials.

**Still true after correction:** a successful public-access/discovery check **does not** prove the exact images, three-class labels and patient mapping are retrievable through IDC. IDC stores DICOM; the labelled JPG patches + CSV are TCIA's assets. Discovery can confirm presence/absence of an osteosarcoma collection in IDC; it cannot by itself establish label+patient-map availability.

**Rules honored:** no bucket prefix invented; the collection is **not** declared absent; no download attempted during discovery.

---

## 4. The decision options (owner must pick one route via Q1)

- **A — IDC/AWS mandatory.** If the organizer requires images to come from IDC/AWS Open Data: next step is a bounded object check (`aws s3 ls --no-sign-request` + `idc-index`) to confirm the collection id, prefix, and — critically — whether three-class labels are retrievable. If only unlabelled DICOM slides are found, **annotation/conversion/patch-extraction becomes a new, separately-approved scope**, not an equivalent dataset.
- **B — TCIA direct acceptable** (deployed on AWS): after a license/provenance check, download the ~197 MB CC-BY release within a byte limit, verify CSV schema and filenames against the actual archive, then proceed to G2. This is the lowest-risk route for the labelled three-class task.
- **C — Organizer rule unclear:** verify the hackathon rubric first (Q4), then choose A or B. **Do not treat B as accepted merely because it is convenient.**

**Technical-lead recommendation (requires owner approval):** pursue **B** for the actual training data (it is the only verified source of the exact three-class labels), *while* running the bounded IDC object check to satisfy an "images on AWS/IDC" rubric requirement if one exists. This keeps the labelled task defensible and avoids inventing labels for DICOM. **This recommendation is not an approval and no data has been fetched.**

---

## 5. Hard rules carried into G2 (do not relax)
- Reject unknown/blank labels (fail closed — never default to "Viable", unlike the inspected RadiomicsOS loader [S06]).
- Patient IDs only from documented metadata or a verified filename convention, with evidence. Missing → `null`, never a fabricated `patient_1`.
- `Training_Set_1/2` folder names are not an ML split.
- Keep original archive separate from derivatives; record SHA-256 per image; detect exact + perceptual duplicates; keep all derivatives of one image in one split.
- Do not use TCGA, a different cancer, web photos, synthetic images, or an unverified Kaggle mirror.

---

## 6. Decision record (to be completed by owner)

| Field | Value |
|---|---|
| Q1 answer (A / B / C) | **B — TCIA direct**, approved by owner (Enk) 2026-10-03 |
| Approved route | Official TCIA Osteosarcoma-Tumor-Assessment, DOI `10.7937/tcia.2019.bvhjhdas`, **for the local educational prototype + data audit only** |
| Approved by / when | Enk, 2026-10-03 (via dashboard instruction) |
| Scope caveat | **Local development only.** This is an explicit change from the IDC-first choice; it does **not** establish hackathon/competition eligibility, and TCIA downloads must never be described as IDC/AWS Open Data downloads. Competition source eligibility remains **unverified** (depends on Q4 rubric). G1 approves source + access route only; it does **not** approve data quality/split (G2) or any training/cloud job. |
| IDC discovery | Credential-free `idc-index` discovery is permitted (public, no secrets). It can confirm whether an osteosarcoma collection exists in IDC but cannot alone prove label+patient-map availability. |
