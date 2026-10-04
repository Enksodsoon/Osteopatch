# 01 — Evidence, disease context and the data-source gate

Source keys resolve in [the register](07_sources_and_reuse_register.md). Statements labelled **proposal** are project decisions, not reported research findings.

## What is verified

The user's link is the **NCI Imaging Data Commons collections registry**, an umbrella listing whose image data are DICOM [S01]. It does not itself establish that a particular labelled JPEG patch collection is available in its AWS buckets.

The closest exact task match is **TCIA Osteosarcoma-Tumor-Assessment** [S02]:

| Published collection property | Value |
|---|---|
| Public cohort | 4 selected patients, not the full 50-patient archive |
| Patch images | 1,144; 1024 × 1024 pixels; 10× |
| Class counts | Non-tumor 536; viable tumor 345; necrotic tumor 263 |
| Files and size | JPG images, about 196.84 MB; CSV annotations/features |
| Annotation | Predominant class; one annotator per image, distributed between two experts |
| Published license | CC BY 3.0; attribution and data citation required |
| Dataset DOI | `10.7937/tcia.2019.bvhjhdas` |

The release also contains folders named Training_Set_1 and Training_Set_2. Their names must not be treated as an independently validated machine-learning split. The CSV schema and exact filenames still require inspection of the actual downloaded release.

**Unverified:** whether this exact collection, its patient-level mapping and labels are hosted in the specified IDC release/AWS objects. No complete IDC catalogue query or dataset download was successfully completed for this handoff. A search result is not an object manifest. Do not state that the collection is definitely absent, and do not invent its S3 prefix.

## G1: resolve before training

Kiro must produce `aidlc-docs/inception/data-source-decision.md` with:

1. The organizer's source rule: must images actually come from IDC/AWS Open Data, or is a directly sourced TCIA public dataset acceptable?
2. Verified collection identifier, source version, object/file URLs, total bytes, label availability, license and attribution; use official metadata and bounded access checks.
3. A tiny sample-read result only after source access is allowed, with image/label matching and no large download.
4. One decision: **IDC exact-match verified**, **TCIA direct explicitly approved**, or **source requirement blocked**.

If only related osteosarcoma DICOM slides are found in IDC but their matching three-class labels are absent, that is not an equivalent training dataset. Annotation, conversion and patch extraction become a different scope requiring approval. Do not silently use TCGA, a different cancer, web photos, synthetic images, or an unverified Kaggle mirror.

## Disease context relevant to the application

Osteosarcoma is a malignant tumor in which tumor cells produce bone/osteoid [S03]. The model's task is narrower: assign a dataset-defined tissue category to an image already drawn from an osteosarcoma collection. A non-tumor patch is not a negative patient diagnosis.

Earlier research examined nuclei/texture features and CNNs to distinguish these tissue categories [S04, S05]. Fibrosis, sparsely cellular osteoid and heterogeneous tissue illustrate why image appearance is not a trivial three-way color rule. Generic morphology teaching notes need pathology review and must not be presented as findings automatically observed by this model.

Patch labels do not establish complete tumor boundaries or representative patient-level sampling. **Project rule:** never turn the number of patches labelled necrosis into a patient's necrosis percentage, response category, survival probability or treatment decision.

## Import and provenance requirements — proposal

Keep the original archive/read-only source separate from derivative previews and preprocessed tensors. A manifest row records stable image ID, source filename/path, image SHA-256, dimensions, source class, canonical class, verified patient/slide group or null, source version and exclusion reason. Preserve original strings.

Use an explicit approved alias table. Reject unknown/blank labels, duplicate image keys, many-to-one filename matches, corrupt images, mismatched CSV rows and contradictory labels. Do not skip failures silently. Reconcile the actual count and distribution against the approved release; discrepancies require a written explanation.

Check exact hashes and perceptual near-duplicates. Related copies and all derivative crops/augmentations must remain in one split. Remove burned-in annotation overlays from model inputs. Check color mode, orientation, ICC handling and image dimensions consistently; log exclusions without rewriting the source.

Patient IDs must come from documented metadata or a verified filename convention, with evidence and examples. Do not equate annotation folders, inferred numeric fragments or unknown values with patients. If mapping is incomplete, do not claim patient-independent performance.

An inspected external loader defaults an unrecognized classification string to “Viable” [S06]. Our importer must fail closed instead. Research code is a reference, not a data contract.

## Required data-gate outputs

`dataset-card.md`, `manifest.csv`, `label_aliases.json`, `patient_mapping_evidence.md`, `data_audit.json`, an exclusion/duplicate report and proposed `split_manifest.csv`. Record checksums. The manifest and split contract are specified in [08](08_data_and_api_contracts.md).

G1 approves source and access. G2 separately approves actual data quality, label mapping and split. Neither approval authorizes a cloud training job.
