// Enterprise API types (mirror the FastAPI contracts in app.py).
export type Role =
  | "student" | "reviewer" | "pathologist" | "ml_engineer" | "admin" | "auditor";

export interface Membership { project_id: string; role: Role; name: string; }

export interface Me {
  user_id: string;
  email: string;
  memberships: Membership[];
  disclaimer: string;
}

export interface Scores { NON_TUMOR: number; VIABLE_TUMOR: number; NECROSIS: number; }

export interface Prediction {
  prediction_id: string;
  predicted_class: keyof Scores;
  scores: Scores;
  score_label: string;
  top1_score: number;
  top_two_margin: number;
  normalized_entropy: number;
  model_bundle_hash: string;
}

export interface ReviewState {
  status: string;
  revision: number;
  latest_action: string | null;
  selected_class: string | null;
}

export interface GalleryItem {
  image_id: string;
  source_group: string;
  prediction: Prediction | null;
  review_state: ReviewState;
  review_priority_rank: number | null;
}

export interface Gallery {
  total: number;
  page: number;
  page_size: number;
  items: GalleryItem[];
}

export interface ServingModel {
  bundle_sha256: string;
  model_id: string;
  state: string;
  eval_passed: number;
}

export const CLASS_LABELS: Record<keyof Scores, string> = {
  NON_TUMOR: "Non-tumor / ไม่ใช่เนื้องอก",
  VIABLE_TUMOR: "Viable tumor / เนื้องอกที่ยังมีชีวิต",
  NECROSIS: "Necrosis / เนื้อตาย",
};

// ---------------------------------------------------------------------------
// Live inference (mirrors app/g6/backend/osteopatch/live_inference.py)
// ---------------------------------------------------------------------------

/** Exactly three outputs. Anything else is a REVIEW state, never a class. */
export const CLASSES: (keyof Scores)[] = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"];

/** GET /v1/live/capability — torch-free, so the UI can call it on page load. */
export interface LiveCapability {
  available: boolean;
  reason?: string;
  hint?: string;
  model_id?: string;
  bundle_path_relative?: string;
  note?: string;
  tile_px?: number;
  max_tiles?: number;
  max_upload_bytes?: number;
  allowed_suffixes?: string[];
}

/**
 * A banded reading, NOT a probability. `indeterminate` means the top two
 * scores are too close to call; `low` means a call with little separation.
 */
export type Confidence = "clear" | "low" | "indeterminate";

export interface LivePrediction {
  scores: Scores;
  predicted_class: keyof Scores;
  top1_score: number;
  top_two_margin: number;
  normalized_entropy: number;
  confidence: Confidence;
  caveat: string | null;
  support_flags: string[];
  score_label: string;
}

export interface LiveRun {
  run_id: string;
  project_id: string;
  source_kind: "patch" | "slide";
  source_name: string;
  stored_filename: string;
  source_sha256: string;
  byte_size: number;
  model_id: string;
  model_bundle_sha256: string;
  encoder_sha256: string;
  created_at: string;
  requested_by: string;
  latency_ms: number | null;
  tile_count: number;
  tiles_available: number;
  truncated: boolean;
  width: number | null;
  height: number | null;
  engine: string | null;
  level_count: number | null;
  mpp_x: number | null;
  mpp_y: number | null;
  objective_power: number | null;
  vendor: string | null;
  support_flags: string[];
  notes: string;
  score_label: string;
  is_live_inference: true;
  is_corpus_prediction: false;
}

export interface LiveTile {
  run_id: string;
  tile_index: number;
  x: number;
  y: number;
  width: number;
  height: number;
  predicted_class: keyof Scores | null;
  non_tumor_score: number | null;
  viable_tumor_score: number | null;
  necrosis_score: number | null;
  top1_score: number | null;
  top_two_margin: number | null;
  normalized_entropy: number | null;
  confidence: Confidence | null;
  scores: Scores | null;
  support_flags: string[];
  decode_error: string | null;
  tile_png_filename: string | null;
}

export interface LiveMosaic {
  path_relative: string;
  cols: number;
  rows: number;
  cell_px: number;
  class_colours: Record<string, number[]>;
  undecoded_colour: number[];
}

export interface UncertainTile {
  index: number;
  x: number;
  y: number;
  predicted_class: keyof Scores | null;
  top_two_margin: number | null;
  confidence: Confidence | null;
}

/** GET /v1/live/runs/{id} */
export interface LiveRunDetail {
  run: LiveRun;
  tiles: LiveTile[];
  n_tiles: number;
}

/** GET /v1/live/runs — the summary shape used by the history rail. */
export interface LiveRunSummary {
  run_id: string;
  source_kind: "patch" | "slide";
  source_name: string;
  requested_by: string;
  created_at: string;
  tile_count: number;
  tiles_available: number;
  truncated: boolean;
}

/** POST /v1/live/patches */
export interface LivePatchResult {
  run: LiveRun;
  prediction: LivePrediction;
  mosaic_png_base64: string | null;
}

/** POST /v1/live/slides — no single `prediction`: a slide is many tiles. */
export interface LiveSlideResult {
  run: LiveRun;
  mosaic: LiveMosaic;
  mosaic_png_base64: string | null;
  most_uncertain_tiles: UncertainTile[];
}

/**
 * Roles that may import and score. Mirrors `live:analyze` in
 * `app/g7-enterprise/backend/enterprise/config.py` — keep the two in step.
 * The UI uses this to explain WHY a button is absent, never to hide a 403.
 */
export const LIVE_ANALYZE_ROLES: Role[] = ["reviewer", "pathologist", "ml_engineer", "admin"];

/** Plain-English reason a persona cannot import, shown instead of a dead button. */
export const LIVE_ANALYZE_DENIED_REASON: Record<string, string> = {
  student:
    "Your role here is learner, and running a forward pass is a writer action — it spends CPU and stores results. You can still open and read every run below.",
  auditor:
    "Auditor is read-only across this capability map by design — an audit trail should not be writable by the person auditing it. You can still open and read every run below.",
};

/** Measured caveats about the INPUT, never verdicts about the diagnosis. */
export const SUPPORT_FLAG_LABELS: Record<string, string> = {
  tiny_input: "Input is smaller than the encoder's training contract.",
  extreme_aspect: "Extreme aspect ratio; the encoder sees stretched pixels.",
  uniform_image: "Near-uniform image — there is no structure to score.",
  greyscale: "Greyscale input is outside this corpus's H&E colour contract.",
};

// ---------------------------------------------------------------------------
// Case reports (mirrors app/g6/backend/osteopatch/reporting.py)
// ---------------------------------------------------------------------------

export interface ReportImage {
  ordinal: number;
  image_id: string;
  source_kind: "corpus" | "live";
  run_id: string | null;
  predicted_class: keyof Scores | null;
  confidence: Confidence | null;
  top_two_margin: number | null;
  scores: Scores | null;
  caveat: string | null;
  corroborated: boolean;
  /** False when the model made no call. Such an image is never a finding. */
  determinate: boolean;
}

/**
 * The server decides this split, and the UI renders it. It is deliberately not
 * recomputed here: one authority for "is this a result" means the screen and
 * the exported document cannot disagree about it.
 */
export interface PublicReport {
  report_id: string;
  project_id: string;
  case_id: string;
  title: string;
  findings_text: string;
  author_email: string;
  created_at: string;
  is_signed: boolean;
  signer_email: string | null;
  signer_role: string | null;
  signed_at: string | null;
  signoff_note: string | null;
  signoff_covers_all: boolean;
  content_sha256: string;
  disclaimer: string;
  n_images: number;
  n_supported: number;
  n_unresolved: number;
  images: ReportImage[];
  model_card: Record<string, unknown>;
  limitations_summary: { total?: number; by_severity?: Record<string, number> };
  limitations_text: { id: string; severity: string; category: string; statement: string }[];
  score_label: string;
  export_endpoints: { html: string; markdown: string };
  hash_verification?: HashVerification;
}

export interface HashVerification {
  report_id: string;
  stored_sha256: string;
  recomputed_from_document_json: string;
  hash_of_typed_document: string;
  matches: boolean;
  document_json_is_canonical: boolean;
}

export interface ReportSummary {
  report_id: string;
  case_id: string;
  title: string;
  author_email: string;
  created_at: string;
  signer_email: string | null;
  content_sha256: string;
  n_images: number;
}

/** Roles that may author a signed document. Mirrors `report:write`. */
export const REPORT_WRITE_ROLES: Role[] = ["reviewer", "pathologist", "admin"];

export const REPORT_WRITE_DENIED_REASON: Record<string, string> = {
  student:
    "A learner drafts practice notes, not the case record. You can still read every report below.",
  auditor:
    "Auditor is read-only across this capability map — an audit trail should not be writable by whoever audits it. You can still read every report below.",
  ml_engineer:
    "This is a clinical document; the roles that may author one are the ones that review cases. You can still read every report below.",
};

export const DISCLAIMER_EN =
  "Educational research prototype only. Not for diagnosis, treatment decisions, or predicting treatment response.";

// ---------------------------------------------------------------------------
// G6 review surface types (mirrors app/g6/backend/osteopatch/app.py + queries.py)
// ---------------------------------------------------------------------------

export type CanonicalClass = "NON_TUMOR" | "VIABLE_TUMOR" | "NECROSIS";
export type ReviewAction = "ACCEPT" | "CORRECT" | "DEFER";
export type ReviewStatus = "unreviewed" | "reviewed" | "deferred";

export interface QcMeta {
  primary_qc_status: string;
  training_eligible: boolean;
  qc_review_flag: boolean;
  qc_review_reason: string | null;
  original_label: string | null;
}

export interface ReviewStateG6 {
  status: ReviewStatus;
  revision: number;
  latest_action: ReviewAction | null;
  selected_class: CanonicalClass | null;
}

export interface ImageSummary {
  image_id: string;
  source_group: string;
  qc: QcMeta;
  prediction: Prediction | null;
  review_state: ReviewStateG6;
  review_priority_rank: number | null;
}

export interface ImageDetail extends ImageSummary {
  history: ReviewEvent[];
}

export interface ReviewEvent {
  review_event_id: string;
  action: ReviewAction;
  selected_class: CanonicalClass | null;
  reason: string | null;
  note: string | null;
  reviewer: string;
  created_at: string;
  revision_number: number;
  prediction_id: string;
}

export interface ImageList {
  total: number;
  page: number;
  page_size: number;
  sort: string;
  filter: string;
  query: string;
  items: ImageSummary[];
}

export interface AttributionPair {
  a: CanonicalClass;
  b: CanonicalClass;
}

export interface AttributionBlock {
  enabled: boolean;
  method: string;
  attribution_target: string;
  recovered_model_id: string;
  source_prediction_model: string;
  pairs: AttributionPair[];
  disclosure: string;
  method_note: string;
}

export interface AttributionMeta {
  image_id: string;
  attribution_enabled: boolean;
  predicted_class: CanonicalClass;
  default_pair: AttributionPair;
  pairs: AttributionPair[];
  recovered_model_id: string;
  source_prediction_model: string;
  source_prediction_bundle_sha256: string;
  attribution_target: string;
  disclosure: string;
  method_note: string;
}

// ---- limitations catalog (served by /v1/model-card) ----------------------
export type LimitationSeverity = "blocking" | "high" | "medium" | "low";

export type LimitationCategory =
  | "claim"
  | "data"
  | "model"
  | "evaluation"
  | "attribution"
  | "platform"
  | "deployment"
  | "process";

export interface Limitation {
  id: string;
  category: LimitationCategory;
  severity: LimitationSeverity;
  pin_first: boolean;
  statement: string;
  retired_by: string;
  evidence: string[];
}

export interface LimitationGroup {
  category: LimitationCategory;
  count: number;
  blocking_count: number;
  items: Limitation[];
}

export interface LimitationsSummary {
  total: number;
  by_severity: Record<LimitationSeverity, number>;
  categories: LimitationCategory[];
  weakest_class: string;
}

export interface ModelCard {
  model_version: string;
  model_bundle_sha256: string;
  calibration_status: string;
  canonical_classes: CanonicalClass[];
  architecture: string | null;
  preprocessing: unknown;
  intended_use: string | null;
  performance_statement: string | null;
  headline_oof: Record<string, unknown>;
  limitations: string[];
  evaluation_evidence_available: boolean;
  evaluation_evidence_unavailable_reason: string;
  limitations_full: Limitation[];
  limitations_grouped: LimitationGroup[];
  limitations_summary: LimitationsSummary;
  limitations_note: string;
  disclaimer: string;
  evidence_note: string;
  model_card_markdown: string | null;
}

export interface Meta {
  canonical_classes: CanonicalClass[];
  review_actions: ReviewAction[];
  defer_reasons: string[];
  score_label: string;
  disclaimer: string;
  g7_placeholder: string;
  attribution_enabled?: boolean;
  attribution?: AttributionBlock;
}

export interface Health {
  status: string;
  model_version: string;
  model_bundle_sha256: string;
  images_indexed: number;
  predictions: number;
  image_subset_scoped?: boolean;
  disclaimer: string;
}
