/** U001 — stable navigation, deep links, browser history.
 *
 * Acceptance IDs U001-AT01..AT05 are assigned below so a reviewer can trace each
 * claim to executable evidence. The pure route module is imported lazily inside the
 * tests that need it, so the App-level acceptance tests fail on missing *behaviour*
 * rather than on a module that has not been written yet.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import type { ImageDetail, ImageList, Meta } from "../types";
// type-only: erased at runtime, so the module tests still fail at run time
import type { QueueContext, Route } from "../navigation";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    getMeta: vi.fn(),
    getHealth: vi.fn(),
    listImages: vi.fn(),
    getImage: vi.fn(),
    submitReview: vi.fn(),
    getModelCard: vi.fn(),
    getAttributionMeta: vi.fn(),
    thumbnailUrl: (id: string) => `/thumb/${id}`,
    fullUrl: (id: string) => `/full/${id}`,
    exportUrl: (f: string) => `/export.${f}`,
    attributionUrl: (id: string, a: string, b: string) => `/attrib/${id}/${a}-${b}.png`,
  };
});

import * as api from "../api";
import App from "../App";

const META: Meta = {
  canonical_classes: ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"],
  review_actions: ["ACCEPT", "CORRECT", "DEFER"],
  defer_reasons: ["mixed_tissue", "poor_image_quality", "insufficient_context", "uncertain_morphology", "other"],
  score_label: "Model score — uncalibrated",
  disclaimer: "Educational / research prototype",
  g7_placeholder: "Model attribution — coming in G7",
};

const QC = { primary_qc_status: "PASS", training_eligible: true, qc_review_flag: false, qc_review_reason: null, original_label: "VIABLE_TUMOR" } as const;

function summary(id: string, rank: number): ImageList["items"][number] {
  return {
    image_id: id, source_group: "Case-3", qc: { ...QC },
    prediction: { prediction_id: `p-${id}`, predicted_class: "VIABLE_TUMOR", model_version: "g4", model_bundle_hash: "x", inference_kind: "prototype_inference", scores: { NON_TUMOR: 0.33, VIABLE_TUMOR: 0.34, NECROSIS: 0.33 }, score_label: "Model score — uncalibrated", top1_score: 0.34, top_two_margin: 0.01, normalized_entropy: 0.99 },
    review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
    review_priority_rank: rank,
  };
}

const LIST: ImageList = {
  total: 2, page: 1, page_size: 60, sort: "priority", filter: "all", query: "",
  items: [summary("img-1", 1), summary("img-2", 2)],
};

function detail(id: string): ImageDetail {
  return {
    image_id: id, source_group: "Case-3", qc: { ...QC },
    prediction: { prediction_id: `pred-${id}`, predicted_class: "VIABLE_TUMOR", model_version: "baseline-frozen-g4", model_bundle_hash: "01727f", inference_kind: "prototype_inference", scores: { NON_TUMOR: 0.33, VIABLE_TUMOR: 0.34, NECROSIS: 0.33 }, score_label: "Model score — uncalibrated", top1_score: 0.34, top_two_margin: 0.01, normalized_entropy: 0.99 },
    review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
    review_priority_rank: 1, history: [],
  };
}

const NAV_MODULE = "../navigation";

/** Fetches issued by the workbench itself. PatchReview also lists images on mount to
 *  build its prev/next queue, and that call carries no search term, so counting every
 *  `listImages` call would conflate the two screens. */
function workbenchFetches(): number {
  return (api.listImages as any).mock.calls.filter((c: any[]) => c[0]?.q !== undefined).length;
}

/** Move the location the way Back/Forward does, and let React see it.
 *
 * Only the hash is set: jsdom fires `hashchange` itself, exactly as a browser does.
 * Dispatching a synthetic event as well would double-count every step. */
async function go(hash: string) {
  await act(async () => {
    window.location.hash = hash;
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  window.location.hash = "";
  (api.getMeta as any).mockResolvedValue(META);
  (api.getHealth as any).mockResolvedValue({ status: "ok", model_version: "baseline-frozen-g4", model_bundle_sha256: "01727f", images_indexed: 1144, predictions: 1144, disclaimer: "Educational" });
  (api.listImages as any).mockResolvedValue(LIST);
  (api.getImage as any).mockImplementation((id: string) => Promise.resolve(detail(id)));
  (api.submitReview as any).mockResolvedValue({ status: 201, created: true, current_revision: 1 });
  (api.getAttributionMeta as any).mockResolvedValue(null);
  (api.getModelCard as any).mockResolvedValue(null);
});

afterEach(() => {
  window.location.hash = "";
});

describe("U001 route module — pure parse/serialize", () => {
  it("U001-AT03 round-trips ids with spaces and reserved characters", async () => {
    const nav = await import(/* @vite-ignore */ NAV_MODULE);
    const ids = [
      "img-1",
      "a b",
      "a/b",
      "a#b?c=d&e",
      "100%",
      "café-9",
      "../../etc/passwd",
      "a+b=c&d",
    ];
    for (const id of ids) {
      const hash = nav.serializeRoute({ name: "patch", imageId: id, context: nav.DEFAULT_CONTEXT });
      // nothing that would terminate or split the path/query may survive unencoded
      const body = hash.replace(/^#\//, "");
      expect(body.slice(0, body.search(/[?#]/) === -1 ? undefined : body.search(/[?#]/)))
        .not.toMatch(/[?#]/);
      const back = nav.parseRoute(hash);
      expect(back.name, `round-trip failed for ${JSON.stringify(id)}`).toBe("patch");
      expect(back.name === "patch" ? back.imageId : "").toBe(id);
    }
  });

  it("rejects unknown enum values and out-of-range pages with safe defaults", async () => {
    const nav = await import(/* @vite-ignore */ NAV_MODULE);
    // each row: a hand-edited URL, and the value that must come back
    const cases: Array<[string, Partial<QueueContext>]> = [
      ["#/workbench?sort=DROP+TABLE", { sort: nav.DEFAULT_CONTEXT.sort }],
      ["#/workbench?filter=pred_MIXED", { filter: nav.DEFAULT_CONTEXT.filter }],
      ["#/workbench?page=0", { page: nav.DEFAULT_CONTEXT.page }],
      ["#/workbench?page=-3", { page: nav.DEFAULT_CONTEXT.page }],
      ["#/workbench?page=1e999", { page: nav.DEFAULT_CONTEXT.page }],
      ["#/workbench?page=abc", { page: nav.DEFAULT_CONTEXT.page }],
      ["#/workbench?page=99999999", { page: nav.DEFAULT_CONTEXT.page }],
      ["#/workbench?sort=image_id&filter=reviewed&q=a+b&page=7",
        { sort: "image_id", filter: "reviewed", q: "a b", page: 7 }],
    ];
    for (const [hash, expected] of cases) {
      const route = nav.parseRoute(hash);
      const ctx = route.name === "workbench" || route.name === "patch" ? route.context : null;
      expect(ctx, `no queue context parsed from ${hash}`).not.toBeNull();
      for (const [key, want] of Object.entries(expected)) {
        expect(ctx![key as keyof QueueContext], `${hash} -> ${key}`).toBe(want);
      }
    }
  });

  it("accepts every sort/filter value the rendered workbench actually offers", async () => {
    // Anti-drift: the URL validator must not reject a value the UI can produce.
    const nav = await import(/* @vite-ignore */ NAV_MODULE);
    const { Workbench } = await import("../components/Workbench");
    render(<Workbench onOpen={() => {}} />);
    const sortValues = [...(await screen.findByTestId("sort-select")).querySelectorAll("option")]
      .map((o) => (o as HTMLOptionElement).value);
    const filterValues = [...screen.getByTestId("filter-select").querySelectorAll("option")]
      .map((o) => (o as HTMLOptionElement).value);
    expect(sortValues.length).toBeGreaterThan(0);
    for (const s of sortValues) {
      const back = nav.parseRoute(`#/workbench?sort=${encodeURIComponent(s)}`);
      expect(back.name === "workbench" ? back.context.sort : "", `sort ${s} was rejected`).toBe(s);
    }
    for (const f of filterValues) {
      const back = nav.parseRoute(`#/workbench?filter=${encodeURIComponent(f)}`);
      expect(back.name === "workbench" ? back.context.filter : "", `filter ${f} was rejected`).toBe(f);
    }
  });

  it("maps every route in the brief's union, and unknown paths to a not-available route", async () => {
    const nav = await import(/* @vite-ignore */ NAV_MODULE);
    // declared by the brief but not implemented in this build
    for (const name of ["overview", "source-groups", "analytics", "system", "demo"]) {
      const route = nav.parseRoute(`#/${name}`);
      expect(route.name === "not-available" && route.declared, `${name} should parse as a declared route`).toBe(true);
    }
    // implemented destinations parse to themselves
    expect(nav.parseRoute("#/workbench").name).toBe("workbench");
    expect(nav.parseRoute("#/attribution").name).toBe("attribution");
    expect(nav.parseRoute("#/model-card").name).toBe("model-card");
    const unknown = nav.parseRoute("#/nope/deep/path");
    expect(unknown.name).toBe("not-available");
    expect(unknown.name === "not-available" ? unknown.declared : true).toBe(false);
  });

  it("serializes only allowlisted navigation context and never extra fields", async () => {
    const nav = await import(/* @vite-ignore */ NAV_MODULE);
    const hash = nav.serializeRoute({
      name: "workbench",
      context: { ...nav.DEFAULT_CONTEXT, q: "case 3" },
      // deliberately smuggled in: neither may reach the URL
      ...({ token: "secret-token", review_note: "dx: invasive carcinoma", patient_id: "P-1" } as object),
    } as Route);
    expect(hash).not.toMatch(/token|note|patient/i);
    const keys = [...new URLSearchParams(hash.split("?")[1] ?? "").keys()].sort();
    expect(keys.every((k) => ["sort", "filter", "q", "page"].includes(k))).toBe(true);
  });
});

describe("U001 App integration — deep links, history, unavailable routes", () => {
  it("U001-AT01 restores the same image id and queue context from a patch URL", async () => {
    // A refresh is exactly this: the app mounts with the URL already set.
    window.location.hash = "#/patch/img-42?sort=image_id&filter=reviewed&q=case+3&page=2";
    render(<App />);
    await screen.findByTestId("patch-review");
    expect((api.getImage as any).mock.calls.at(-1)?.[0]).toBe("img-42");
    // the queue context travelled with the link and must come back on Back
    fireEvent.click(screen.getAllByText(/back to workbench/i)[0]);
    await screen.findByTestId("workbench");
    expect(window.location.hash).toContain("sort=image_id");
    expect(window.location.hash).toContain("filter=reviewed");
    expect(window.location.hash).toContain("page=2");
    expect((screen.getByTestId("sort-select") as HTMLSelectElement).value).toBe("image_id");
    expect((screen.getByTestId("filter-select") as HTMLSelectElement).value).toBe("reviewed");
    expect((screen.getByTestId("search-input") as HTMLInputElement).value).toBe("case 3");
  });

  it("U001-AT02 moves between screens exactly once per history step and removes its listener", async () => {
    const added: EventListenerOrEventListenerObject[] = [];
    const removed: EventListenerOrEventListenerObject[] = [];
    const realAdd = window.addEventListener.bind(window);
    const realRemove = window.removeEventListener.bind(window);
    const addSpy = vi.spyOn(window, "addEventListener").mockImplementation((type: any, fn: any, opts: any) => {
      if (type === "hashchange") added.push(fn);
      return realAdd(type, fn, opts);
    });
    const removeSpy = vi.spyOn(window, "removeEventListener").mockImplementation((type: any, fn: any, opts: any) => {
      if (type === "hashchange") removed.push(fn);
      return realRemove(type, fn, opts);
    });

    const { unmount } = render(<App />);
    await screen.findByTestId("workbench");
    const before = workbenchFetches();

    await go("#/patch/img-1");
    await screen.findByTestId("patch-review");
    // Back: one history step must re-render the workbench once. A second listener
    // would setRoute twice and fire a second fetch for the same screen.
    await go("#/workbench");
    await screen.findByTestId("workbench");
    await waitFor(() => expect(workbenchFetches()).toBe(before + 1));
    expect(screen.queryByTestId("patch-review")).toBeNull();

    expect(added.length, "no hashchange listener was registered").toBeGreaterThan(0);
    unmount();
    expect(removed, "hashchange listeners leaked past unmount").toEqual(added);
    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it("U001-AT04 shows a meaningful view instead of an empty screen for unknown routes", async () => {
    for (const hash of ["#/analytics", "#/nope/deep/path", "#/patch/"]) {
      window.location.hash = hash;
      const view = render(<App />);
      const notice = await screen.findByTestId("route-unavailable");
      expect(notice.textContent ?? "").not.toMatch(/^\s*$/);
      expect(notice.textContent ?? "").toMatch(/not available/i);
      // the shell still renders, so this is not a blank page
      expect(screen.getByTestId("disclaimer")).toBeInTheDocument();
      view.unmount();
    }
  });

  it("U001-AT05 keeps tokens and review notes out of the URL", async () => {
    const { container } = render(<App />);
    await screen.findByTestId("workbench");
    await go("#/patch/img-1");
    await screen.findByTestId("patch-review");
    const note = screen.getByTestId("review-note");
    fireEvent.change(note, { target: { value: "dx: invasive carcinoma, block A3" } });
    fireEvent.click(screen.getAllByText(/back to workbench/i)[0]);
    await screen.findByTestId("workbench");
    const url = window.location.href;
    expect(url).not.toMatch(/invasive|carcinoma|dx:|block A3/i);
    expect(url).not.toMatch(/token|bearer|authorization|api[_-]?key|session=/i);
    // only navigation context is ever serialized
    for (const pair of window.location.hash.split("?")[1]?.split("&") ?? []) {
      expect(["sort", "filter", "q", "page"]).toContain(decodeURIComponent(pair.split("=")[0]));
    }
    expect(container.querySelector("[data-nav-token]")).toBeNull();
  });
});
