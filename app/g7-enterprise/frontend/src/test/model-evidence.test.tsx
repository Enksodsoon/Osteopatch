import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ModelCard } from "../types";

const { getModelCard } = vi.hoisted(() => ({ getModelCard: vi.fn() }));
vi.mock("../api", () => ({ getModelCard }));

import { ModelEvidenceSummary } from "../components/ModelCard";

const frozenCard = {
  model_version: "baseline-frozen-g4",
  model_bundle_sha256: "a".repeat(64),
  calibration_status: "uncalibrated",
  canonical_classes: ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"],
  architecture: "MobileNetV3 Small",
  preprocessing: { resize: [384, 384] },
  intended_use: null,
  performance_statement: null,
  headline_oof: {
    n_rows: 1028,
    accuracy_secondary: 0.670233,
    balanced_accuracy: 0.62646,
    macro_f1: 0.562311,
    per_class: {
      NON_TUMOR: { recall: 0.902893, f1: 0.842004, support: 484 },
      VIABLE_TUMOR: { recall: 0.110345, f1: 0.179272, support: 290 },
      NECROSIS: { recall: 0.866142, f1: 0.665658, support: 254 },
    },
  },
  evaluation_evidence_available: true,
  evaluation_evidence_unavailable_reason: "",
  limitations: [],
  limitations_full: [],
  limitations_grouped: [],
  limitations_summary: { total: 0, by_severity: { blocking: 0, high: 0, medium: 0, low: 0 }, categories: [], weakest_class: "VIABLE_TUMOR" },
  limitations_note: "",
  disclaimer: "",
  evidence_note: "",
  model_card_markdown: null,
} as ModelCard;

describe("ModelEvidenceSummary", () => {
  beforeEach(() => getModelCard.mockReset().mockResolvedValue(frozenCard));

  it("separates live recovered-head performance from frozen baseline metrics", async () => {
    render(<ModelEvidenceSummary runModelId="g4-behavioral-recovery-r1" />);
    await waitFor(() => expect(screen.getByText("Frozen baseline accuracy 67.0%")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("slide-model-evidence").querySelector("summary")!);
    expect(screen.getByText(/independent accuracy for this recovered model has not been measured/i)).toBeInTheDocument();
    expect(screen.getByText("Viable-tumor recall: 11.0% in that baseline evaluation.")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Model setup"));
    expect(screen.getByText("MobileNetV3 Small")).toBeInTheDocument();
  });

  it("does not turn missing evaluation evidence into a zero accuracy", async () => {
    getModelCard.mockResolvedValue({ ...frozenCard, evaluation_evidence_available: false,
      headline_oof: { accuracy_secondary: null } });
    render(<ModelEvidenceSummary runModelId="unqualified-model" />);
    await waitFor(() => expect(screen.getByText("Frozen evaluation unavailable")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("slide-model-evidence").querySelector("summary")!);
    expect(screen.getByText(/no accuracy estimate is shown/i)).toBeInTheDocument();
    expect(screen.queryByText("0.0%")).not.toBeInTheDocument();
  });
});
