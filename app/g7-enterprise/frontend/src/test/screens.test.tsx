import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ImportPanel } from "../components/live/ImportPanel";
import { LiveScreen } from "../components/live/LiveScreen";
import { ReportScreen } from "../components/reports/ReportScreen";
import * as api from "../api";
import type {
  Gallery, LiveCapability, LivePatchResult, LiveRunSummary, PublicReport, ReportSummary,
} from "../types";

/**
 * ASSEMBLED-SCREEN tests.
 *
 * The leaf components were already covered in live.test.tsx. What was missing —
 * and what these defend — is the WIRING: that LiveScreen probes capability on
 * mount, sends the upload the way the API expects, and puts the SERVER's
 * supported/unresolved split on screen without recomputing it client-side.
 *
 * The one rule that must hold across the seam is that this screen never invents
 * a result: the honesty numbers come from the response, not from local maths.
 */

const CAPABILITY: LiveCapability = {
  available: true, model_id: "g4-behavioral-recovery-r1",
  tile_px: 384, max_tiles: 256, max_upload_bytes: 536870912,
  allowed_suffixes: [".tif", ".png"],
};

const SUMMARY: LiveRunSummary = {
  run_id: "live-abc123", source_kind: "patch", source_name: "field.png",
  requested_by: "reviewer@demo", created_at: "2026-10-06T00:00:00Z",
  tile_count: 1, tiles_available: 1, truncated: false,
};

function patchResult(over: Partial<PublicReport> = {}): LivePatchResult {
  return {
    mosaic_png_base64: null,
    run: {
      run_id: "live-abc123", project_id: "prj_1", source_kind: "patch",
      source_name: "field.png", stored_filename: "f.png", source_sha256: "a".repeat(64),
      byte_size: 999, model_id: "g4-behavioral-recovery-r1",
      model_bundle_sha256: "f".repeat(64), encoder_sha256: "e".repeat(64),
      created_at: "2026-10-06T00:00:00Z", requested_by: "reviewer@demo",
      latency_ms: 240, tile_count: 1, tiles_available: 1, truncated: false,
      width: 1024, height: 1024, engine: "pillow", level_count: 1,
      mpp_x: null, mpp_y: null, objective_power: null, vendor: null,
      support_flags: [], notes: "", score_label: "Model score — uncalibrated",
      is_live_inference: true, is_corpus_prediction: false,
    },
    prediction: {
      scores: { NON_TUMOR: 0.2, VIABLE_TUMOR: 0.1, NECROSIS: 0.7 },
      predicted_class: "NECROSIS", top1_score: 0.7, top_two_margin: 0.5,
      normalized_entropy: 0.4, confidence: "clear", caveat: null,
      support_flags: [], score_label: "Model score — uncalibrated",
    },
    ...over,
  } as LivePatchResult;
}

/** Route every endpoint the screens touch. Returns the calls that were made. */
function mockApi(handlers: Record<string, unknown>) {
  const calls: { url: string; init: RequestInit }[] = [];
  globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
    const u = String(url);
    calls.push({ url: u, init: init ?? {} });
    const key = Object.keys(handlers).find((k) => u.includes(k));
    const value = key ? handlers[key] : { runs: [], reports: [] };
    if (value instanceof Error) return new Response(JSON.stringify({ detail: String(value) }), { status: 500 });
    return new Response(JSON.stringify(value), {
      status: 200, headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
  return calls;
}

afterEach(() => {
  globalThis.fetch = vi.fn() as unknown as typeof fetch;
  api.setToken(null);
  api.setProject(null);
});

/** Mirrors what App.tsx does on login: the project lives in module state. */
function enterProject() {
  api.setToken("test-token");
  api.setProject("prj_1");
}

describe("LiveScreen — assembled wiring", () => {
  it("probes capability and run history on mount", async () => {
    enterProject();
    const calls = mockApi({
      "/v1/live/capability": CAPABILITY,
      "/v1/live/runs": { runs: [SUMMARY] },
    });
    render(<LiveScreen role="reviewer" projectId="prj_1" />);

    await waitFor(() => expect(calls.some((c) => c.url.includes("/v1/live/capability"))).toBe(true));
    expect(calls.some((c) => c.url.includes("/v1/live/runs"))).toBe(true);
    // The capability probe is a reader action and carries the project header.
    const probe = calls.find((c) => c.url.includes("/v1/live/capability"))!;
    expect((probe.init.headers as Record<string, string>)["X-Project-Id"]).toBe("prj_1");
    await waitFor(() =>
      expect(screen.getByText("g4-behavioral-recovery-r1")).toBeInTheDocument());
  });

  it("uploads the chosen file and renders the server's verdict", async () => {
    enterProject();
    const calls = mockApi({
      "/v1/live/capability": CAPABILITY,
      "/v1/live/runs": { runs: [] },
      "/v1/live/patches": patchResult(),
    });
    render(<LiveScreen role="reviewer" projectId="prj_1" />);
    await screen.findByText("g4-behavioral-recovery-r1");

    const file = new File([new Uint8Array([1, 2, 3])], "field.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/choose a patch or slide/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /import and score$/i }));

    await waitFor(() => expect(calls.some((c) => c.url.includes("/v1/live/patches"))).toBe(true));
    expect(await screen.findByRole("heading", { name: "Necrosis" })).toBeInTheDocument();
    expect(screen.getByText(/not a corpus prediction/i)).toBeInTheDocument();
  });

  it("shows the server's honest split rather than computing its own", async () => {
    enterProject();
    mockApi({
      "/v1/live/capability": CAPABILITY,
      "/v1/live/runs": { runs: [] },
      "/v1/live/patches": patchResult(),
    });
    render(<LiveScreen role="reviewer" projectId="prj_1" />);
    await screen.findByText("g4-behavioral-recovery-r1");
    await waitFor(() => expect(screen.getByText(/recorded demo runs/i)).toBeInTheDocument());
  });

  it("tells a reader-only persona why there is no import control", async () => {
    enterProject();
    mockApi({ "/v1/live/capability": CAPABILITY, "/v1/live/runs": { runs: [SUMMARY] } });
    render(<LiveScreen role="auditor" projectId="prj_1" />);
    await screen.findByText(/not available to your role/i);
    expect(screen.queryByRole("button", { name: /import and score/i })).not.toBeInTheDocument();
  });

  it("surfaces an upload failure instead of an empty screen", async () => {
    enterProject();
    globalThis.fetch = (async (url: string) => {
      if (String(url).includes("/v1/live/patches")) {
        return new Response(JSON.stringify({ detail: "unsupported type" }), { status: 415 });
      }
      return new Response(JSON.stringify(
        String(url).includes("capability") ? CAPABILITY : { runs: [] },
      ), { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    render(<LiveScreen role="reviewer" projectId="prj_1" />);
    await screen.findByText("g4-behavioral-recovery-r1");
    const file = new File([new Uint8Array([1])], "invalid.png", { type: "image/png" });
    fireEvent.change(screen.getByLabelText(/choose a patch or slide/i), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /import and score$/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/415|refused/i);
  });
});

describe("ReportScreen — assembled wiring", () => {
  const GALLERY: Gallery = {
    total: 2, page: 1, page_size: 50,
    items: [
      {
        image_id: "Case-3-A10-10547-25283", source_group: "Case-3-A10",
        review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
        review_priority_rank: 1,
        prediction: {
          prediction_id: "p1", predicted_class: "NECROSIS",
          scores: { NON_TUMOR: 0.2, VIABLE_TUMOR: 0.1, NECROSIS: 0.7 },
          score_label: "uncalibrated", top1_score: 0.7, top_two_margin: 0.0,
          normalized_entropy: 0.6, model_bundle_hash: "abc",
        },
      },
      {
        image_id: "Case-3-A10-10566-40206", source_group: "Case-3-A10",
        review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
        review_priority_rank: 2,
        prediction: {
          prediction_id: "p2", predicted_class: "VIABLE_TUMOR",
          scores: { NON_TUMOR: 0.1, VIABLE_TUMOR: 0.8, NECROSIS: 0.1 },
          score_label: "uncalibrated", top1_score: 0.8, top_two_margin: 0.7,
          normalized_entropy: 0.3, model_bundle_hash: "abc",
        },
      },
    ],
  };

  const MADE: PublicReport = {
    report_id: "rep-abc", project_id: "prj_1", case_id: "Case-3-A10",
    title: "Case review", findings_text: "Necrosis dominates.",
    author_email: "reviewer@demo", created_at: "2026-10-06T00:00:00Z",
    is_signed: true, signer_email: "reviewer@demo", signer_role: "reviewer",
    signed_at: "2026-10-06T00:00:00Z", signoff_note: null,
    signoff_covers_all: false,
    content_sha256: "f".repeat(64),
    disclaimer: "Educational research prototype.", n_images: 2,
    n_supported: 1, n_unresolved: 1,
    images: [{
      ordinal: 1, image_id: "Case-3-A10-10547-25283", source_kind: "corpus", run_id: null,
      predicted_class: "NECROSIS", confidence: "clear", top_two_margin: 0.7,
      scores: { NON_TUMOR: 0.1, VIABLE_TUMOR: 0.2, NECROSIS: 0.7 }, caveat: null,
      corroborated: false, determinate: true,
    }], model_card: {}, limitations_summary: {}, limitations_text: [],
    score_label: "uncalibrated",
    export_endpoints: { html: "/v1/reports/rep-abc/export.html", markdown: "/v1/reports/rep-abc/export.md" },
    hash_verification: {
      report_id: "rep-abc", stored_sha256: "f".repeat(64),
      recomputed_from_document_json: "f".repeat(64),
      hash_of_typed_document: "f".repeat(64), matches: true,
      document_json_is_canonical: true,
    },
  };

  it("warns before submitting that a tied patch cannot become a finding", async () => {
    enterProject();
    mockApi({ "/api/v1/images": GALLERY, "/v1/reports": { reports: [] } });
    render(<ReportScreen role="reviewer" projectId="prj_1" userEmail="reviewer@demo" />);
    await screen.findByLabelText(/include Case-3-A10-10547-25283/i);

    // the first image has margin 0.000 -> would be recorded as no-call
    fireEvent.click(screen.getByLabelText(/include Case-3-A10-10547-25283/i));
    fireEvent.click(screen.getByLabelText(/include Case-3-A10-10566-40206/i));

    const warn = await screen.findByRole("status");
    expect(warn).toHaveTextContent(/sign-off partial/i);
  });

  it("posts the picked images and shows the recomputed hash", async () => {
    enterProject();
    const calls = mockApi({
      "/api/v1/images": GALLERY, "/v1/reports": { reports: [] },
    });
    // the POST returns the made report; subsequent GETs return history
    globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
      const u = String(url);
      calls.push({ url: u, init: init ?? {} });
      if (u.endsWith("/v1/reports/rep-abc")) {
        return new Response(JSON.stringify(MADE), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
      if (u.endsWith("/v1/reports") && init.method === "POST") {
        return new Response(JSON.stringify(MADE), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
      if (u.includes("/api/v1/images")) {
        return new Response(JSON.stringify(GALLERY), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ reports: [] }), { status: 200,
        headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    render(<ReportScreen role="reviewer" projectId="prj_1" userEmail="reviewer@demo" />);
    await screen.findByLabelText(/include Case-3-A10-10547-25283/i);
    fireEvent.click(screen.getByLabelText(/include Case-3-A10-10547-25283/i));
    const editor = screen.getByRole("textbox", { name: "Findings" });
    editor.innerHTML = "<p>Necrosis dominates.</p>";
    fireEvent.input(editor);
    fireEvent.click(screen.getByRole("button", { name: /save report/i }));

    await waitFor(() => expect(calls.some((c) => c.init.method === "POST")).toBe(true));
    const post = calls.find((c) => c.init.method === "POST")!;
    const body = JSON.parse(String(post.init.body));
    expect(body.image_ids).toEqual(["Case-3-A10-10547-25283"]);
    expect(body.findings_text).toBe("Necrosis dominates.");
    expect(body.findings_html).toBe("<p>Necrosis dominates.</p>");
    expect(body.signer_email).toBe("reviewer@demo");

    expect(await screen.findByText(/content check · verified/i)).toBeInTheDocument();
    expect(screen.getByText(MADE.content_sha256)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download html/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /download markdown/i })).toBeInTheDocument();
  });

  it("marks a partial sign-off rather than implying full coverage", async () => {
    enterProject();
    globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
      const u = String(url);
      if (u.endsWith("/v1/reports/rep-abc")) {
        return new Response(JSON.stringify(MADE), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
      if (u.endsWith("/v1/reports") && init.method === "POST") {
        return new Response(JSON.stringify(MADE), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
      if (u.includes("/api/v1/images")) {
        return new Response(JSON.stringify(GALLERY), { status: 200,
          headers: { "Content-Type": "application/json" } });
      }
      return new Response(JSON.stringify({ reports: [] as ReportSummary[] }),
        { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;

    render(<ReportScreen role="reviewer" projectId="prj_1" userEmail="reviewer@demo" />);
    await screen.findByLabelText(/include Case-3-A10-10547-25283/i);
    fireEvent.click(screen.getByLabelText(/include Case-3-A10-10547-25283/i));
    fireEvent.click(screen.getByRole("button", { name: /save report/i }));

    await screen.findByText(/signed\s+—\s+partial/i);
    // The tally chip and the explanation both name the no-call count; assert the
    // explanation, which is the one carrying the meaning.
    expect(screen.getByText(/no determinable class/i)).toBeInTheDocument();
  });

  it("offers no authoring control to a reader-only persona", async () => {
    enterProject();
    mockApi({ "/api/v1/images": GALLERY, "/v1/reports": { reports: [] } });
    render(<ReportScreen role="student" projectId="prj_1" userEmail="student@demo" />);
    await screen.findByText(/writing reports is not available to your role/i);
    expect(screen.queryByRole("button", { name: /save report/i })).not.toBeInTheDocument();
  });

  it("uses one picker with thumbnails and rich-text tools", async () => {
    enterProject();
    const slide = { slide_id: "a".repeat(32), project_id: "prj_1", filename: "teaching.svs",
      source_sha256: "b".repeat(64), byte_size: 100, width: 2048, height: 1024,
      engine: "openslide", level_count: 2, created_at: "2026-10-06T00:00:00Z",
      level_downsamples: [1, 4], mpp_x: null, mpp_y: null };
    const calls = mockApi({
      "/api/v1/images": GALLERY,
      "/v1/live/runs": { runs: [SUMMARY] },
      "/v1/slides": { slides: [slide] },
      "/v1/reports": { reports: [] },
    });
    render(<ReportScreen role="reviewer" projectId="prj_1" userEmail="reviewer@demo" />);
    await screen.findByText("teaching.svs");
    expect(screen.getByText(/AI analyzed · teaching set/i)).toBeInTheDocument();
    expect(screen.getByText(/AI analyzed · uploaded images/i)).toBeInTheDocument();
    expect(screen.getByText(/Not yet analyzed · uploaded slides/i)).toBeInTheDocument();
    const bold = screen.getByRole("button", { name: "Bold" });
    expect(bold.querySelector("svg")).toBeInTheDocument();
    expect(bold.textContent).toBe("");
    fireEvent.change(screen.getByLabelText("Search slide library"), {
      target: { value: "teaching.svs · uploaded slide" },
    });
    expect(screen.getByLabelText("Include teaching.svs")).toBeChecked();
    expect(screen.getByLabelText("Report name")).toHaveValue("Case review — teaching.svs");
    fireEvent.change(screen.getByLabelText("Report name"), { target: { value: "My teaching slide report" } });
    expect(screen.getByLabelText("Report name")).toHaveValue("My teaching slide report");
    expect(await screen.findByTestId(`slide-thumbnail-${slide.slide_id}`)).toBeInTheDocument();
    await waitFor(() => expect(calls.some((call) => call.url.includes("/thumbnail"))).toBe(true));
    expect(calls.some((call) => call.url.includes("/live/runs/live-abc123/thumbnail.png"))).toBe(true);
  });

  it("opens a saved report and starts an append-only revision with its content", async () => {
    enterProject();
    const history = [{ report_id: MADE.report_id, case_id: MADE.case_id, title: MADE.title,
      author_email: MADE.author_email, created_at: MADE.created_at, signer_email: MADE.signer_email,
      content_sha256: MADE.content_sha256, n_images: 1 }];
    const calls: { url: string; init: RequestInit }[] = [];
    globalThis.fetch = (async (url: string, init: RequestInit = {}) => {
      const u = String(url); calls.push({ url: u, init });
      if (u.endsWith("/v1/reports/rep-abc")) return new Response(JSON.stringify(MADE), { status: 200 });
      if (u.endsWith("/v1/reports") && init.method === "POST") return new Response(JSON.stringify(MADE), { status: 200 });
      if (u.includes("/api/v1/images")) return new Response(JSON.stringify(GALLERY), { status: 200 });
      if (u.includes("/v1/live/runs")) return new Response(JSON.stringify({ runs: [] }), { status: 200 });
      if (u.endsWith("/v1/slides")) return new Response(JSON.stringify({ slides: [] }), { status: 200 });
      return new Response(JSON.stringify({ reports: history }), { status: 200 });
    }) as typeof fetch;

    render(<ReportScreen role="reviewer" projectId="prj_1" userEmail="reviewer@demo" />);
    fireEvent.click(await screen.findByRole("button", { name: /Case review/i }));
    fireEvent.click(await screen.findByRole("button", { name: /Edit as new revision/i }));
    expect(screen.getByRole("textbox", { name: "Findings" })).toHaveTextContent("Necrosis dominates.");
    expect(screen.getByLabelText(/include Case-3-A10-10547-25283/i)).toBeChecked();
    fireEvent.click(screen.getByRole("button", { name: /Save revision/i }));
    await waitFor(() => expect(calls.some((call) => call.init.method === "POST")).toBe(true));
    const body = JSON.parse(String(calls.find((call) => call.init.method === "POST")?.init.body));
    expect(body.revision_of).toBe("rep-abc");
    expect(body.image_ids).toContain("Case-3-A10-10547-25283");
  });
});

describe("import validation", () => {
  it("rejects unsupported, empty and oversized files before calling inference", () => {
    const onImport = vi.fn();
    render(<ImportPanel role="reviewer" capability={{ ...CAPABILITY, max_upload_bytes: 5 }} busy={false} onImport={onImport} />);
    const input = screen.getByLabelText("Choose a patch or slide to import");
    for (const file of [new File(["x"], "bad.pdf"), new File([], "empty.png"), new File(["123456"], "large.png")]) {
      fireEvent.change(input, { target: { files: [file] } });
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /^Import and score$/ })).toBeDisabled();
    }
    expect(onImport).not.toHaveBeenCalled();
    const file = new File(["123"], "ok.png");
    fireEvent.change(input, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /^Import and score$/ }));
    expect(onImport).toHaveBeenCalledWith(file, "patch");
  });
});
