import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ImageDetail, ImageList, Meta } from "../types";

// ---- mock the api module ----
vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    getMeta: vi.fn(),
    listImages: vi.fn(),
    getImage: vi.fn(),
    submitReview: vi.fn(),
    getAttributionMeta: vi.fn(),
    getModelCard: vi.fn(),
    thumbnailUrl: (id: string) => `/thumb/${id}`,
    fullUrl: (id: string) => `/full/${id}`,
    exportUrl: (f: string) => `/export.${f}`,
    attributionUrl: (id: string, a: string, b: string) => `/attrib/${id}/${a}-${b}.png`,
  };
});

import * as api from "../api";
import { Workbench } from "../components/Workbench";
import { PatchReview } from "../components/PatchReview";
import { Disclaimer } from "../components/Shared";
import { AttributionPanel } from "../components/AttributionPanel";
import { ModelCard } from "../components/ModelCard";
import type {
  AttributionMeta,
  Limitation,
  LimitationGroup,
  ModelCard as ModelCardPayload,
} from "../types";

const ATTRIB_META: AttributionMeta = {
  image_id: "img-1",
  attribution_enabled: true,
  predicted_class: "VIABLE_TUMOR",
  default_pair: { a: "VIABLE_TUMOR", b: "NECROSIS" },
  pairs: [
    { a: "VIABLE_TUMOR", b: "NECROSIS" },
    { a: "NECROSIS", b: "VIABLE_TUMOR" },
    { a: "NON_TUMOR", b: "VIABLE_TUMOR" },
    { a: "VIABLE_TUMOR", b: "NON_TUMOR" },
    { a: "NON_TUMOR", b: "NECROSIS" },
    { a: "NECROSIS", b: "NON_TUMOR" },
  ],
  recovered_model_id: "g4-behavioral-recovery-r1",
  source_prediction_model: "baseline-frozen-g4",
  source_prediction_bundle_sha256: "01727fb8",
  attribution_target: "raw logit_A - logit_B (contrastive)",
  disclosure:
    "Attribution uses a behaviorally reconstructed classifier because the original runtime head weights were not durably preserved. Prediction behavior was verified against the original stored outputs.",
  method_note: "This is model attribution, not tissue segmentation or diagnostic annotation.",
};

const META: Meta = {
  canonical_classes: ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"],
  review_actions: ["ACCEPT", "CORRECT", "DEFER"],
  defer_reasons: ["mixed_tissue", "poor_image_quality", "insufficient_context", "uncertain_morphology", "other"],
  score_label: "Model score — uncalibrated",
  disclaimer: "Educational / research prototype",
  g7_placeholder: "Model attribution — coming in G7",
};

// ---- model card payload (limitations catalog) -----------------------------
// Mirrors the real /v1/model-card shape. LIM-VIABLE-WEAK is deliberately first
// in its group and blocking: the UI must never let it scroll away unseen.
function makeLimitation(o: Partial<Limitation> = {}): Limitation {
  return {
    id: "LIM-TEST",
    category: "model",
    severity: "high",
    pin_first: false,
    statement: "A test limitation.",
    retired_by: "Retired by doing the thing that would remove it.",
    evidence: ["docs/current-state-audit.md"],
    ...o,
  };
}

const VIABLE = makeLimitation({
  id: "LIM-VIABLE-WEAK",
  category: "model",
  severity: "blocking",
  pin_first: true,
  statement:
    "VIABLE_TUMOR is the model's weak class. Pooled out-of-fold recall is 0.110345.",
  retired_by: "Retired by widening independent VIABLE_TUMOR coverage.",
});

const UNCALIBRATED = makeLimitation({
  id: "LIM-MODEL-UNCALIBRATED",
  category: "model",
  severity: "blocking",
  statement: "calibration_status is 'uncalibrated'.",
});

const ABSENT_BUNDLE = makeLimitation({
  id: "LIM-PLATFORM-FROZEN-BUNDLE-ABSENT",
  category: "platform",
  severity: "high",
  statement: "The original frozen bundle file is not present on disk.",
});

const GROUPS: LimitationGroup[] = [
  { category: "model", count: 2, blocking_count: 2, items: [VIABLE, UNCALIBRATED] },
  { category: "platform", count: 1, blocking_count: 0, items: [ABSENT_BUNDLE] },
];

const MODEL_CARD: ModelCardPayload = {
  model_version: "baseline-frozen-g4",
  model_bundle_sha256: "01727fb832f9d5518bbe2e33b901e7041020929c94b89cdb7a5e5195b544df63",
  calibration_status: "uncalibrated",
  canonical_classes: ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"],
  architecture: "mobilenetv3_small",
  preprocessing: {},
  intended_use: "educational",
  performance_statement: "frozen LOGO OOF",
  headline_oof: { macro_f1: 0.562311, balanced_accuracy: 0.62646, n_rows: 1028 },
  limitations: [
    "Exploratory case/slide-group independence over 4 groups ONLY; patient-level independence unverified.",
    "P9 fold is single-class (NON_TUMOR) -> VIABLE/NECROSIS not estimable there.",
    "Case-3 VIABLE test support=3 and Case-48 NECROSIS test support=2 are indicative-only (CI ~ [0,1]).",
    "Patches are not independent biological samples; no patch-as-patient bootstrap.",
    "Scores are uncalibrated model class scores, not disease probabilities.",
  ],
  limitations_full: [VIABLE, UNCALIBRATED, ABSENT_BUNDLE],
  limitations_grouped: GROUPS,
  limitations_summary: {
    total: 3,
    by_severity: { blocking: 2, high: 1, medium: 0, low: 0 },
    categories: ["model", "platform"],
    weakest_class: "VIABLE_TUMOR",
  },
  limitations_note: "frozen list verbatim + full catalog",
  disclaimer:
    "Educational / research prototype. NOT for diagnosis, treatment decisions, treatment-response prediction, or prognosis.",
  evidence_note: "prototype inference only",
  model_card_markdown: null,
};

function makeDetail(overrides: Partial<ImageDetail> = {}): ImageDetail {
  return {
    image_id: "img-1",
    source_group: "Case-3",
    qc: { primary_qc_status: "PASS", training_eligible: true, qc_review_flag: false, qc_review_reason: null, original_label: "VIABLE_TUMOR" },
    prediction: {
      prediction_id: "pred-img-1-abc",
      predicted_class: "VIABLE_TUMOR",
      model_version: "baseline-frozen-g4",
      model_bundle_hash: "01727f",
      inference_kind: "prototype_inference",
      scores: { NON_TUMOR: 0.33, VIABLE_TUMOR: 0.34, NECROSIS: 0.33 },
      score_label: "Model score — uncalibrated",
      top1_score: 0.34,
      top_two_margin: 0.01,
      normalized_entropy: 0.99,
    },
    review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
    review_priority_rank: 1,
    history: [],
    ...overrides,
  };
}

const LIST: ImageList = {
  total: 2, page: 1, page_size: 60, sort: "priority", filter: "all", query: "",
  items: [
    { image_id: "img-1", source_group: "Case-3", qc: { primary_qc_status: "PASS", training_eligible: true, qc_review_flag: false, qc_review_reason: null, original_label: "VIABLE_TUMOR" },
      prediction: { prediction_id: "p1", predicted_class: "VIABLE_TUMOR", model_version: "g4", model_bundle_hash: "x", inference_kind: "prototype_inference", scores: { NON_TUMOR: 0.33, VIABLE_TUMOR: 0.34, NECROSIS: 0.33 }, score_label: "Model score — uncalibrated", top1_score: 0.34, top_two_margin: 0.01, normalized_entropy: 0.99 },
      review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null }, review_priority_rank: 1 },
    { image_id: "img-2", source_group: "Case-4", qc: { primary_qc_status: "PASS", training_eligible: true, qc_review_flag: false, qc_review_reason: null, original_label: "NON_TUMOR" },
      prediction: { prediction_id: "p2", predicted_class: "NON_TUMOR", model_version: "g4", model_bundle_hash: "x", inference_kind: "prototype_inference", scores: { NON_TUMOR: 0.9, VIABLE_TUMOR: 0.05, NECROSIS: 0.05 }, score_label: "Model score — uncalibrated", top1_score: 0.9, top_two_margin: 0.85, normalized_entropy: 0.3 },
      review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null }, review_priority_rank: 2 },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  (api.getMeta as any).mockResolvedValue(META);
  (api.listImages as any).mockResolvedValue(LIST);
  (api.submitReview as any).mockResolvedValue({ status: 201, created: true, current_revision: 1 });
  (api.getAttributionMeta as any).mockResolvedValue(ATTRIB_META);
  (api.getModelCard as any).mockResolvedValue(MODEL_CARD);
});

describe("Disclaimer", () => {
  it("is visible without opening a panel", () => {
    render(<Disclaimer />);
    expect(screen.getByTestId("disclaimer")).toBeInTheDocument();
    expect(screen.getByTestId("disclaimer").textContent).toMatch(/NOT for diagnosis/i);
  });
});

describe("Workbench", () => {
  it("loads the gallery and can sort by review priority", async () => {
    render(<Workbench onOpen={() => {}} />);
    await screen.findByTestId("card-img-1");
    expect(screen.getByTestId("gallery").children.length).toBe(2);
    // first card shows priority rank #1 and the uncalibrated margin
    expect(screen.getByTestId("card-img-1").textContent).toMatch(/#1/);
    // change sort -> listImages re-called with sort=priority (default) then image_id
    fireEvent.change(screen.getByTestId("sort-select"), { target: { value: "image_id" } });
    await waitFor(() => expect((api.listImages as any).mock.calls.at(-1)[0].sort).toBe("image_id"));
  });

  it("opens a patch on card click", async () => {
    const onOpen = vi.fn();
    render(<Workbench onOpen={onOpen} />);
    const card = await screen.findByTestId("card-img-1");
    fireEvent.click(card);
    expect(onOpen).toHaveBeenCalledWith("img-1");
  });
});

describe("PatchReview", () => {
  it("shows all three model scores and the uncalibrated badge", async () => {
    (api.getImage as any).mockResolvedValue(makeDetail());
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={() => {}} />);
    await screen.findByTestId("review-panel");
    expect(screen.getByTestId("score-NON_TUMOR")).toBeInTheDocument();
    expect(screen.getByTestId("score-VIABLE_TUMOR")).toBeInTheDocument();
    expect(screen.getByTestId("score-NECROSIS")).toBeInTheDocument();
    expect(screen.getAllByText(/uncalibrated/i).length).toBeGreaterThan(0);
  });

  it("accepts a patch", async () => {
    (api.getImage as any).mockResolvedValue(makeDetail());
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={() => {}} />);
    await screen.findByTestId("action-ACCEPT");
    fireEvent.click(screen.getByTestId("action-ACCEPT"));
    fireEvent.click(screen.getByTestId("save-review"));
    await waitFor(() => expect(api.submitReview).toHaveBeenCalled());
    const body = (api.submitReview as any).mock.calls[0][1];
    expect(body.action).toBe("ACCEPT");
    expect(body.expected_revision).toBe(0);
  });

  it("corrects a patch to another class", async () => {
    (api.getImage as any).mockResolvedValue(makeDetail());
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={() => {}} />);
    await screen.findByTestId("action-CORRECT");
    fireEvent.click(screen.getByTestId("action-CORRECT"));
    fireEvent.click(screen.getByTestId("class-NECROSIS"));
    fireEvent.click(screen.getByTestId("save-review"));
    await waitFor(() => expect(api.submitReview).toHaveBeenCalled());
    const body = (api.submitReview as any).mock.calls[0][1];
    expect(body.action).toBe("CORRECT");
    expect(body.selected_label).toBe("NECROSIS");
  });

  it("defers a patch with a reason and never forces a class", async () => {
    (api.getImage as any).mockResolvedValue(makeDetail());
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={() => {}} />);
    await screen.findByTestId("action-DEFER");
    fireEvent.click(screen.getByTestId("action-DEFER"));
    // no class picker is shown for DEFER
    expect(screen.queryByTestId("class-NECROSIS")).toBeNull();
    fireEvent.change(screen.getByTestId("defer-reason"), { target: { value: "mixed_tissue" } });
    fireEvent.click(screen.getByTestId("save-review"));
    await waitFor(() => expect(api.submitReview).toHaveBeenCalled());
    const body = (api.submitReview as any).mock.calls[0][1];
    expect(body.action).toBe("DEFER");
    expect(body.selected_label).toBeNull();
    expect(body.reason).toBe("mixed_tissue");
  });

  it("shows review history with the original prediction unchanged", async () => {
    (api.getImage as any).mockResolvedValue(
      makeDetail({
        prediction: makeDetail().prediction, // predicted VIABLE_TUMOR
        review_state: { status: "reviewed", revision: 1, latest_action: "CORRECT", selected_class: "NON_TUMOR" },
        history: [{ review_event_id: "r1", action: "CORRECT", selected_class: "NON_TUMOR", reason: null, note: null, reviewer: "me", created_at: "2026-10-03T16:00:00Z", revision_number: 1, prediction_id: "pred-img-1-abc" }],
      }),
    );
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={() => {}} />);
    await screen.findByTestId("review-history");
    // suggested (model) class still VIABLE_TUMOR; history shows human correction to NON_TUMOR
    expect(screen.getByTestId("suggested-class").textContent).toMatch(/VIABLE_TUMOR/);
    expect(screen.getByTestId("history-rev-1").textContent).toMatch(/CORRECT.*NON_TUMOR/);
  });

  it("navigates to the next patch", async () => {
    (api.getImage as any).mockResolvedValue(makeDetail());
    const onNavigate = vi.fn();
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={onNavigate} />);
    await screen.findByTestId("next-patch");
    await waitFor(() => expect((api.listImages as any)).toHaveBeenCalled());
    fireEvent.click(screen.getByTestId("next-patch"));
    expect(onNavigate).toHaveBeenCalledWith("img-2");
  });
});


describe("AttributionPanel (G7 contrastive)", () => {
  it("renders the panel with the default suggested-vs-runner-up pair", async () => {
    render(<AttributionPanel imageId="img-1" />);
    await screen.findByTestId("attribution-panel");
    const sel = (await screen.findByTestId("attribution-pair")) as HTMLSelectElement;
    expect(sel.value).toBe("VIABLE_TUMOR|NECROSIS"); // default_pair
    expect(screen.getByTestId("attribution-hint").textContent).toMatch(/VIABLE_TUMOR.*rather than.*NECROSIS/);
  });

  it("offers all six ordered contrastive pairs and switches target", async () => {
    render(<AttributionPanel imageId="img-1" />);
    const sel = (await screen.findByTestId("attribution-pair")) as HTMLSelectElement;
    expect(sel.querySelectorAll("option").length).toBe(6);
    fireEvent.change(sel, { target: { value: "NECROSIS|VIABLE_TUMOR" } });
    expect(screen.getByTestId("attribution-hint").textContent).toMatch(/NECROSIS.*rather than.*VIABLE_TUMOR/);
    const img = screen.getByTestId("attribution-overlay-img") as HTMLImageElement;
    expect(img.getAttribute("src")).toBe("/attrib/img-1/NECROSIS-VIABLE_TUMOR.png");
  });

  it("keeps the original image available and toggles the overlay", async () => {
    render(<AttributionPanel imageId="img-1" />);
    await screen.findByTestId("attribution-stage");
    expect(screen.getByTestId("attribution-stage").querySelector(".attrib-base")).toBeTruthy();
    const toggle = screen.getByTestId("attribution-overlay-toggle") as HTMLInputElement;
    expect(toggle.checked).toBe(true);
    fireEvent.click(toggle);
    expect(toggle.checked).toBe(false);
    expect(screen.queryByTestId("attribution-overlay-img")).toBeNull();
  });

  it("exposes an opacity control", async () => {
    render(<AttributionPanel imageId="img-1" />);
    const op = (await screen.findByTestId("attribution-opacity")) as HTMLInputElement;
    fireEvent.change(op, { target: { value: "0.3" } });
    expect(op.value).toBe("0.3");
  });

  it("shows the required disclaimer and the recovery disclosure, always visible", async () => {
    render(<AttributionPanel imageId="img-1" />);
    await screen.findByTestId("attribution-panel");
    expect(screen.getByTestId("attribution-not-segmentation").textContent).toMatch(
      /not tissue segmentation or diagnostic annotation/i,
    );
    expect(screen.getByTestId("attribution-recovery-disclosure").textContent).toMatch(
      /behaviorally reconstructed classifier/i,
    );
    expect(screen.getByTestId("attribution-recovery-disclosure").textContent).toMatch(
      /verified against the original stored outputs/i,
    );
  });

  it("shows a loading state before the overlay loads", async () => {
    render(<AttributionPanel imageId="img-1" />);
    await screen.findByTestId("attribution-stage");
    await screen.findByTestId("attribution-loading");
  });

  it("shows an honest error state and NO heatmap when the overlay fails", async () => {
    render(<AttributionPanel imageId="img-1" />);
    const img = (await screen.findByTestId("attribution-overlay-img")) as HTMLImageElement;
    fireEvent.error(img);
    await screen.findByTestId("attribution-error");
    expect(screen.getByTestId("attribution-error").textContent).toMatch(/No heatmap is shown/i);
    expect(screen.queryByTestId("attribution-overlay-img")).toBeNull();
  });

  it("surfaces an honest error if attribution metadata cannot be fetched", async () => {
    (api.getAttributionMeta as any).mockRejectedValueOnce(new Error("boom"));
    render(<AttributionPanel imageId="img-1" />);
    await screen.findByTestId("attribution-error");
    expect(screen.getByTestId("attribution-recovery-disclosure")).toBeInTheDocument();
  });

  it("review actions still work after interacting with attribution", async () => {
    (api.getImage as any).mockResolvedValue(makeDetail());
    render(<PatchReview imageId="img-1" meta={META} onBack={() => {}} onNavigate={() => {}} />);
    await screen.findByTestId("review-panel");
    await screen.findByTestId("attribution-panel");
    const sel = screen.getByTestId("attribution-pair") as HTMLSelectElement;
    fireEvent.change(sel, { target: { value: "NON_TUMOR|NECROSIS" } });
    fireEvent.click(screen.getByTestId("action-ACCEPT"));
    fireEvent.click(screen.getByTestId("save-review"));
    await waitFor(() => expect(api.submitReview).toHaveBeenCalled());
    const body = (api.submitReview as any).mock.calls[0][1];
    expect(body.action).toBe("ACCEPT");
  });
});

describe("ModelCard — full limitations catalog", () => {
  it("renders every catalogued limitation, not just the frozen five", async () => {
    render(<ModelCard />);
    await screen.findByTestId("limitations-full");
    expect(screen.getByTestId("limitation-LIM-VIABLE-WEAK")).toBeInTheDocument();
    expect(screen.getByTestId("limitation-LIM-MODEL-UNCALIBRATED")).toBeInTheDocument();
    expect(screen.getByTestId("limitation-LIM-PLATFORM-FROZEN-BUNDLE-ABSENT")).toBeInTheDocument();
    expect(screen.getByTestId("limitations-count").textContent).toMatch(/3 limitations recorded/);
  });

  it("keeps the VIABLE_TUMOR weakness first, blocking, and quoted with its recall", async () => {
    render(<ModelCard />);
    const model = await screen.findByTestId("lim-group-model");
    const first = model.querySelector("[data-testid^='limitation-']");
    expect(first?.getAttribute("data-testid")).toBe("limitation-LIM-VIABLE-WEAK");
    expect(first?.getAttribute("data-severity")).toBe("blocking");
    // severity is a word, not a colour
    expect(screen.getAllByTestId("sev-blocking").length).toBeGreaterThan(0);
    expect(screen.getByTestId("limitation-LIM-VIABLE-WEAK").textContent).toMatch(
      /0\.110345/,
    );
  });

  it("says what would retire each limitation and cites evidence", async () => {
    render(<ModelCard />);
    const item = await screen.findByTestId("limitation-LIM-VIABLE-WEAK");
    expect(item.textContent).toMatch(/What would retire it/i);
    expect(item.textContent).toMatch(/Widening independent VIABLE_TUMOR coverage/i);
    expect(item.textContent).toMatch(/docs\/current-state-audit\.md/);
  });

  it("still shows the frozen G4 evaluation caveats verbatim", async () => {
    render(<ModelCard />);
    const frozen = await screen.findByTestId("limitations-frozen");
    expect(frozen.textContent).toMatch(/patient-level independence unverified/);
    expect(frozen.textContent).toMatch(/uncalibrated model class scores/);
  });

  it("never replaces the limitations with a placeholder when the fetch fails", async () => {
    (api.getModelCard as any).mockRejectedValueOnce(new Error("boom"));
    render(<ModelCard />);
    const err = await screen.findByTestId("model-card-error");
    expect(err.textContent).toMatch(/could not be loaded/i);
    expect(err.textContent).toMatch(/nothing is shown in their place/i);
    expect(screen.queryByTestId("limitations-full")).toBeNull();
  });

  it("keeps the disclaimer and the prototype-inference note on the card", async () => {
    render(<ModelCard />);
    await screen.findByTestId("limitations-full");
    expect(screen.getByTestId("model-card").textContent).toMatch(/NOT for diagnosis/i);
    expect(screen.getByTestId("model-card").textContent).toMatch(/prototype inference only/i);
  });
});
