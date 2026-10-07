import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ImportPanel } from "../components/live/ImportPanel";
import { ReviewScreen } from "../components/ReviewScreen";
import { VerdictCard } from "../components/live/VerdictCard";
import { TileGrid, TileInspector, UncertainRank } from "../components/live/TileGrid";
import { ProvenanceStrip } from "../components/live/ProvenanceStrip";
import * as api from "../api";
import type {
  LiveCapability, LivePatchResult, LiveRun, LiveTile,
} from "../types";

// ---------------------------------------------------------------------------
// The rules these tests defend are product rules, not implementation details:
//  1. a low-confidence outcome must NOT be rendered as a confident class;
//  2. a role that cannot import must be told why, not given a dead button;
//  3. the upload is a raw body + X-File-Name, never FormData;
//  4. absent input properties render as "not in file", never as 0 or blank.
// ---------------------------------------------------------------------------

const CAPABILITY: LiveCapability = {
  available: true,
  model_id: "g4-behavioral-recovery-r1",
  tile_px: 384,
  max_tiles: 256,
  max_upload_bytes: 536870912,
  allowed_suffixes: [".tif", ".png"],
};

function run(over: Partial<LiveRun> = {}): LiveRun {
  return {
    run_id: "live-abc123", project_id: "prj_1", source_kind: "patch",
    source_name: "field.png", stored_filename: "s.png", source_sha256: "a".repeat(64),
    byte_size: 1234, model_id: "g4-behavioral-recovery-r1",
    model_bundle_sha256: "f".repeat(64), encoder_sha256: "e".repeat(64),
    created_at: "2026-10-06T00:00:00Z", requested_by: "reviewer@demo",
    latency_ms: 240, tile_count: 1, tiles_available: 1, truncated: false,
    width: 1024, height: 1024, engine: "pillow", level_count: 1,
    mpp_x: null, mpp_y: null, objective_power: null, vendor: null,
    support_flags: [], notes: "", score_label: "Model score — uncalibrated (recovered research head)",
    is_live_inference: true, is_corpus_prediction: false, ...over,
  };
}

function patchResult(over: Partial<LivePatchResult["prediction"]> = {}): LivePatchResult {
  return {
    run: run(),
    mosaic_png_base64: null,
    prediction: {
      scores: { NON_TUMOR: 0.5, VIABLE_TUMOR: 0.001, NECROSIS: 0.499 },
      predicted_class: "NON_TUMOR",
      top1_score: 0.5, top_two_margin: 0.001, normalized_entropy: 0.63,
      confidence: "indeterminate", caveat: "Top two classes are effectively tied.",
      support_flags: [], score_label: "Model score — uncalibrated (recovered research head)",
      ...over,
    },
  };
}

function tile(over: Partial<LiveTile> = {}): LiveTile {
  return {
    run_id: "live-abc123", tile_index: 0, x: 0, y: 0, width: 384, height: 384,
    predicted_class: "NON_TUMOR", non_tumor_score: 0.7, viable_tumor_score: 0.01,
    necrosis_score: 0.29, top1_score: 0.7, top_two_margin: 0.4,
    normalized_entropy: 0.5, confidence: "clear",
    scores: { NON_TUMOR: 0.7, VIABLE_TUMOR: 0.01, NECROSIS: 0.29 },
    support_flags: [], decode_error: null, tile_png_filename: "t0.png", ...over,
  };
}

describe("ImportPanel — capability honesty", () => {
  it("offers the import control to a writer role", () => {
    render(<ImportPanel role="reviewer" capability={CAPABILITY} busy={false} onImport={() => {}} />);
    expect(screen.getByRole("button", { name: /import and score$/i })).toBeInTheDocument();
  });

  it("does NOT offer a button that would 403 — it explains, for a student", () => {
    render(<ImportPanel role="student" capability={CAPABILITY} busy={false} onImport={() => {}} />);
    expect(screen.queryByRole("button", { name: /import and score/i })).not.toBeInTheDocument();
    expect(screen.getByText(/not available to your role/i)).toBeInTheDocument();
    expect(screen.getByText(/learner/i)).toBeInTheDocument();
  });

  it("explains the read-only reason for an auditor", () => {
    render(<ImportPanel role="auditor" capability={CAPABILITY} busy={false} onImport={() => {}} />);
    expect(screen.queryByRole("button", { name: /import and score/i })).not.toBeInTheDocument();
    expect(screen.getByText(/read-only across this capability map/i)).toBeInTheDocument();
  });

  it("explains a missing runtime instead of a broken control", () => {
    render(
      <ImportPanel
        role="reviewer"
        capability={{ available: false, reason: "torch is not installed", hint: "uv sync --extra model" }}
        busy={false}
        onImport={() => {}}
      />,
    );
    expect(screen.getByText(/torch is not installed/i)).toBeInTheDocument();
    expect(screen.getByText(/uv sync --extra model/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /import and score/i })).not.toBeInTheDocument();
  });

  it("sends a raw body with X-File-Name and never FormData", async () => {
    const calls: Array<{ url: string; init: RequestInit }> = [];
    const orig = globalThis.fetch;
    globalThis.fetch = (async (url: string, init: RequestInit) => {
      calls.push({ url: String(url), init });
      return new Response(JSON.stringify(patchResult()), {
        status: 200, headers: { "Content-Type": "application/json" },
      });
    }) as typeof fetch;

    const file = new File([new Uint8Array([1, 2, 3])], "field.png", { type: "image/png" });
    const onImport = vi.fn(async () => { await api.importPatch(file); });
    render(<ImportPanel role="reviewer" capability={CAPABILITY} busy={false} onImport={onImport} />);

    fireEvent.change(screen.getByLabelText(/choose a patch or slide/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /import and score$/i }));

    await waitFor(() => expect(calls).toHaveLength(1));
    const { url, init } = calls[0];
    expect(url).toBe("/v1/live/patches");
    const h = init.headers as Record<string, string>;
    expect(h["X-File-Name"]).toBe("field.png");
    expect(h["Content-Type"]).toBe("application/octet-stream");
    // The body must be the File itself, not a FormData with a multipart boundary.
    expect(init.body).toBe(file);
    expect(init.body).not.toBeInstanceOf(FormData);
    globalThis.fetch = orig;
  });
});

describe("VerdictCard — an uncertain result must not look certain", () => {
  it("withholds the class name entirely when indeterminate", () => {
    const r = patchResult();
    render(<VerdictCard run={r.run} prediction={r.prediction} />);
    expect(screen.getByRole("heading", { name: /not determined/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Non-tumor" })).not.toBeInTheDocument();
    expect(screen.getByText(/no class is being asserted/i)).toBeInTheDocument();
  });

  it("names the class when the top two are actually separated", () => {
    const r = patchResult({
      confidence: "clear", top_two_margin: 0.42,
      scores: { NON_TUMOR: 0.5, VIABLE_TUMOR: 0.001, NECROSIS: 0.499 },
    });
    render(<VerdictCard run={r.run} prediction={r.prediction} />);
    expect(screen.getByRole("heading", { name: "Non-tumor" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /not determined/i })).not.toBeInTheDocument();
  });

  it("uses a friendly source label for a slide and hides the technical file hash", () => {
    const r = patchResult();
    render(<VerdictCard run={r.run} prediction={r.prediction} sourceLabel="Selected slide view" />);
    expect(screen.getByText("Selected slide view")).toBeInTheDocument();
    expect(screen.queryByText(/a{16}/)).not.toBeInTheDocument();
  });

  it("always states that the score is uncalibrated and not a probability", () => {
    const r = patchResult();
    render(<VerdictCard run={r.run} prediction={r.prediction} />);
    expect(screen.getByText(/uncalibrated/i)).toBeInTheDocument();
    expect(screen.getByText(/not a probability/i)).toBeInTheDocument();
  });

  it("surfaces the server's caveat rather than swallowing it", () => {
    const r = patchResult();
    render(<VerdictCard run={r.run} prediction={r.prediction} />);
    expect(screen.getByText(/effectively tied/i)).toBeInTheDocument();
  });

  it("explains a measured input caveat", () => {
    const r = patchResult({ support_flags: ["greyscale"] });
    render(<VerdictCard run={r.run} prediction={r.prediction} />);
    expect(screen.getByText(/greyscale input is outside this corpus/i)).toBeInTheDocument();
  });

  it("labels the run as live so it cannot be mistaken for a corpus prediction", () => {
    const r = patchResult();
    render(<VerdictCard run={r.run} prediction={r.prediction} />);
    expect(screen.getByText(/not a corpus prediction/i)).toBeInTheDocument();
  });
});

describe("TileGrid — uncertainty is a visual state, not a class colour", () => {
  const mosaic = {
    path_relative: "x", cols: 3, rows: 2, cell_px: 18,
    class_colours: {} as Record<string, number[]>, undecoded_colour: [150, 150, 150],
  };

  it("marks an indeterminate tile indeterminate in its accessible name", () => {
    const tiles = [
      tile({ tile_index: 0 }),
      tile({ tile_index: 1, confidence: "indeterminate", predicted_class: "NECROSIS" }),
    ];
    render(<TileGrid tiles={tiles} mosaic={mosaic} onInspect={() => {}} />);
    expect(screen.getByRole("gridcell", { name: /tile 1, indeterminate/i })).toBeInTheDocument();
  });

  it("does not add the indeterminate tile twice to the tile count", () => {
    const tiles = [
      tile({ tile_index: 0, predicted_class: "NON_TUMOR" }),
      tile({ tile_index: 1, confidence: "indeterminate", predicted_class: "NECROSIS" }),
    ];
    render(<TileGrid tiles={tiles} mosaic={mosaic} onInspect={() => {}} />);
    expect(screen.getAllByRole("gridcell")).toHaveLength(2);
    expect(screen.getByText(/of those 2/i)).toBeInTheDocument();
  });

  it("reports a tile that could not be decoded rather than colouring it", () => {
    const tiles = [tile({ tile_index: 0, decode_error: "truncated file", predicted_class: null, confidence: null })];
    render(<TileGrid tiles={tiles} mosaic={mosaic} onInspect={() => {}} />);
    expect(screen.getByRole("gridcell", { name: /could not be decoded/i })).toBeInTheDocument();
  });

  it("refuses to name a class in the inspector for an indeterminate tile", () => {
    const t = tile({ tile_index: 4, confidence: "indeterminate", top_two_margin: 0.004 });
    render(<TileInspector tile={t} />);
    expect(screen.getByText(/indeterminate/i)).toBeInTheDocument();
    expect(screen.getByText(/no class is asserted for this tile/i)).toBeInTheDocument();
  });
});

describe("UncertainRank — the guidance list is reachable from a stored run", () => {
  it("ranks the least-separated tiles first", () => {
    const tiles = [
      tile({ tile_index: 1, top_two_margin: 0.40 }),
      tile({ tile_index: 2, top_two_margin: 0.01, confidence: "indeterminate" }),
      tile({ tile_index: 3, top_two_margin: 0.22 }),
    ];
    render(<UncertainRank tiles={tiles} />);
    const items = screen.getAllByRole("listitem");
    expect(items[0]).toHaveTextContent("#2");
    expect(items[1]).toHaveTextContent("#3");
  });

  it("labels the closest tile indeterminate rather than naming its class", () => {
    const tiles = [
      tile({ tile_index: 9, top_two_margin: 0.004, confidence: "indeterminate", predicted_class: "NECROSIS" }),
    ];
    render(<UncertainRank tiles={tiles} />);
    expect(screen.getByText("indeterminate")).toBeInTheDocument();
    expect(screen.queryByText("NECROSIS")).not.toBeInTheDocument();
  });

  it("renders nothing when there is no scored tile to rank", () => {
    const { container } = render(<UncertainRank tiles={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ReviewScreen — an empty scope is explained, not left as a dead end", () => {
  it("says why the gallery is empty and how to populate it", async () => {
    const orig = globalThis.fetch;
    globalThis.fetch = (async () => new Response(
      JSON.stringify({ total: 0, page: 1, page_size: 24, items: [] }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    )) as typeof fetch;
    render(<ReviewScreen role="reviewer" />);
    await waitFor(() =>
      expect(screen.getByText(/no images in this project/i)).toBeInTheDocument());
    expect(screen.getByText(/owns no images yet/i)).toBeInTheDocument();
    expect(screen.getByText("python -m enterprise.seed")).toBeInTheDocument();
    globalThis.fetch = orig;
  });
});

describe("ProvenanceStrip — absent means absent", () => {
  it("renders null mpp/objective/vendor as 'not in file', never as a number", () => {
    render(<ProvenanceStrip run={run()} />);
    const dds = screen.getAllByText("not in file");
    expect(dds).toHaveLength(3);
    expect(screen.queryByText(/0\.00/)).not.toBeInTheDocument();
  });

  it("shows the recovered head's identity, never the frozen bundle", () => {
    render(<ProvenanceStrip run={run()} />);
    expect(screen.getByText("g4-behavioral-recovery-r1")).toBeInTheDocument();
    expect(screen.getByText("f".repeat(64))).toBeInTheDocument();
  });

  it("reports truncation with both counts rather than a single total", () => {
    render(<ProvenanceStrip run={run({ tile_count: 100, tiles_available: 256, truncated: true })} />);
    expect(screen.getByText("100 of 256")).toBeInTheDocument();
  });
});
