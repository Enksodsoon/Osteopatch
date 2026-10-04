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

export const DISCLAIMER_EN =
  "Educational research prototype only. Not for diagnosis, treatment decisions, or predicting treatment response.";
