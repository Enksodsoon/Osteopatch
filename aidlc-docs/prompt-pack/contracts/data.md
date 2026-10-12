# Shared contract: data

**Status:** Proposed design contract; reconcile additively with the accepted repository interfaces.

Research hierarchy: project -> dataset_version -> source_group -> optional verified slide -> patch. source_group_id is not a patient ID. The current four case/slide groups must not be relabeled as four independent patients. A patch without a verified parent slide or spatial coordinates remains an independent patch asset in the viewer; do not arrange patches into a fake whole slide.

AssetRecord fields: image_id, dataset_version_id, source_group_id, asset_kind (patch|whole_slide), source_sha256, width_px, height_px, channels, format_detected, original_label_raw, canonical_reference_label nullable, reference_provenance_id nullable, parent_slide_id nullable, level0_x/y/width/height nullable, mpp_x/y nullable, objective_power nullable, license_record_id, qc_status, inclusion_state. Legacy source_group and qc.original_label remain preserved for existing consumers.

Physical units require finite positive metadata with a stated source. Pixel dimensions or TIFF DPI alone must not be presented as histologic magnification. Blank physical metadata means unknown; show display zoom separately. Original files are immutable. Derivatives carry parent hash and transform version. Dataset versions, QC decisions, and manifests are append-only/versioned; no replacing a frozen training-eligibility decision in place.

Uploads go into a private quarantine with a generated internal name, bounded byte/pixel limits, content validation, authorization, and checksums before indexing. Extension alone is insufficient. Reject unsafe paths, directory traversal, remote-file fetch tricks, decompression bombs, active content, and unsupported bundles. Never publish slide label/barcode images by default. Patient-identifying fields are outside the demo data contract.
