import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PatchReview } from "../components/PatchReview";
import * as api from "../api";
import type { ImageDetail, ImageList, Meta } from "../types";

vi.mock("../components/ImageViewer", () => ({
  ImageViewer: () => createElement("div", { "data-testid": "image-viewer" }),
}));
vi.mock("../components/AttributionPanel", () => ({
  AttributionPanel: () => createElement("div", { "data-testid": "attribution-panel" }),
}));

const image: ImageDetail = {
  image_id: "Case-3-A10-10547-25283",
  source_group: "Case-3-A10",
  qc: {
    primary_qc_status: "PASS", training_eligible: true, qc_review_flag: false,
    qc_review_reason: null, original_label: "NON_TUMOR",
  },
  prediction: {
    prediction_id: "pred-demo", predicted_class: "NECROSIS",
    scores: { NON_TUMOR: 0.2, VIABLE_TUMOR: 0.1, NECROSIS: 0.7 },
    score_label: "uncalibrated model score", top1_score: 0.7,
    top_two_margin: 0.5, normalized_entropy: 0.4, model_bundle_hash: "demo-hash",
  },
  review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
  review_priority_rank: 1,
  history: [],
};

const meta: Meta = {
  canonical_classes: ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"],
  review_actions: ["ACCEPT", "CORRECT", "DEFER"],
  defer_reasons: ["uncertain", "poor_quality", "other"],
  score_label: "uncalibrated model score",
  disclaimer: "Educational use only.",
  g7_placeholder: "",
};

afterEach(() => {
  vi.unstubAllGlobals();
  globalThis.fetch = vi.fn() as unknown as typeof fetch;
  api.setToken(null);
  api.setProject(null);
});

describe("PatchReview self-check", () => {
  it("keeps model evidence and review controls hidden until a choice is revealed", async () => {
    api.setToken("demo-token");
    api.setProject("prj_demo");
    globalThis.fetch = (async (input: RequestInfo | URL) => {
      const url = String(input);
      const body: ImageDetail | ImageList = url.includes("/v1/images?")
        ? { total: 1, page: 1, page_size: 60, sort: "priority", filter: "all", query: "", items: [image] }
        : image;
      return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    render(<PatchReview imageId={image.image_id} meta={meta} onBack={() => {}} onNavigate={() => {}} />);
    fireEvent.click(await screen.findByRole("button", { name: /try a self-check/i }));

    expect(screen.queryByTestId("scorebars")).not.toBeInTheDocument();
    expect(screen.queryByTestId("attribution-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("review-panel")).not.toBeInTheDocument();
    expect(screen.queryByTestId("suggested-class")).not.toBeInTheDocument();
    expect(screen.queryByTestId("patch-toolbar-class")).not.toBeInTheDocument();
    expect(screen.queryByText("Original label")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("self-check-choice-NON_TUMOR"));
    fireEvent.click(screen.getByRole("button", { name: /reveal comparison/i }));

    expect(screen.getAllByTestId("scorebars")).toHaveLength(1);
    expect(screen.queryByTestId("suggested-class")).not.toBeInTheDocument();
    expect(screen.getByTestId("attribution-panel")).toBeInTheDocument();
    expect(screen.getByTestId("review-panel")).toBeInTheDocument();
    expect(screen.getByText(/agreement is a comparison with this model output/i)).toBeInTheDocument();
    expect(screen.queryByText(/correct answer/i)).not.toBeInTheDocument();
  });
});
