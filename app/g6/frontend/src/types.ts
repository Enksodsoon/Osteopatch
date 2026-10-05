// API response types mirroring the FastAPI backend.

export type CanonicalClass = "NON_TUMOR" | "VIABLE_TUMOR" | "NECROSIS";
export type ReviewAction = "ACCEPT" | "CORRECT" | "DEFER";
export type ReviewStatus = "unreviewed" | "reviewed" | "deferred";

export interface Scores {
  NON_TUMOR: number;
  VIABLE_TUMOR: number;
  NECROSIS: number;
}

export interface Prediction {
  prediction_id: string;
  predicted_class: CanonicalClass;
  model_version: string;
  model_bundle_hash: string;
  inference_kind: string;
  scores: Scores;
  score_label: string;
  top1_score: number;
  top_two_margin: number;
  normalized_entropy: number;
}

export interface QcMeta {
  primary_qc_status: string;
  training_eligible: boolean;
  qc_review_flag: boolean;
  qc_review_reason: string | null;
  original_label: string | null;
}

export interface ReviewState {
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
  review_state: ReviewState;
  review_priority_rank: number | null;
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

export interface ImageDetail extends ImageSummary {
  history: ReviewEvent[];
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
// `Limitations` (below) are the FROZEN G4 evaluation caveats, quoted verbatim
// from the artifact and never edited in place. `Limitation` entries are the
// full catalog: each one cites an evidence file and states what would retire
// it. See app/g6/backend/osteopatch/limitations.py.
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
