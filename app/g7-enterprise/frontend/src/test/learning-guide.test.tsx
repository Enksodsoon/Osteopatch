import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { LearningGuide } from "../components/LearningGuide";

describe("LearningGuide", () => {
  it("presents sourced osteosarcoma study content and clear model boundaries", () => {
    render(<LearningGuide onOpenModel={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Osteosarcoma" })).toBeInTheDocument();
    expect(screen.getByText(/tumour cells directly produce osteoid/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "A coordinated diagnostic pathway" })).toBeInTheDocument();
    expect(screen.getByText(/patch label ≠ treatment response/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /health professional version/i })).toHaveAttribute(
      "href",
      "https://www.cancer.gov/types/bone/hp/osteosarcoma-treatment-pdq",
    );
    expect(screen.getByRole("link", { name: "Cancer Protocol: Bone Resection" })).toHaveAttribute(
      "href",
      "https://www.cap.org/wp-content/uploads/protocols/cp-other-bone-resection-20-4010.pdf?download=true",
    );
    expect(screen.getAllByRole("img", { name: /synthetic h&e-style illustration/i })).toHaveLength(3);
  });

  it("reveals short knowledge-check explanations and opens model evidence", () => {
    const onOpenModel = vi.fn();
    render(<LearningGuide onOpenModel={onOpenModel} />);

    fireEvent.click(screen.getByText("Does a high model score mean a high chance of disease?"));
    expect(screen.getByText(/scores are uncalibrated class scores/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /explore model evidence and limitations/i }));
    expect(onOpenModel).toHaveBeenCalledOnce();
  });
});
