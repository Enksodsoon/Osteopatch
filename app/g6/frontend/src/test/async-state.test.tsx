/**
 * U003 — standardize loading, empty, offline, and retry states.
 *
 * U003-AT01 empty dataset and HTTP failure have different wording
 * U003-AT02 permission errors do not offer a bypass link
 * U003-AT03 a failed refresh keeps only explicitly labeled stale content
 * U003-AT04 rapid retries produce no concurrent unbounded request loop
 * U003-AT05 screen reader receives a concise state change announcement
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { ImageList } from "../types";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    listImages: vi.fn(),
    thumbnailUrl: (id: string) => `/thumb/${id}`,
    fullUrl: (id: string) => `/full/${id}`,
  };
});

import * as api from "../api";
import { ApiError } from "../apiErrors";
import { Workbench } from "../components/Workbench";

// The module under construction is imported through a function so Vite cannot
// constant-fold the specifier: a missing file then fails these tests at RUNTIME
// instead of breaking collection for the whole file.
function asyncStatePath(): string {
  return "../components/AsyncState";
}
const mod = () => import(/* @vite-ignore */ asyncStatePath());

function item(id: string) {
  return {
    image_id: id,
    source_group: `Case-${id}`,
    qc: { primary_qc_status: "PASS", training_eligible: true, qc_review_flag: false, qc_review_reason: null, original_label: "NON_TUMOR" as const },
    prediction: {
      prediction_id: `p-${id}`, predicted_class: "NON_TUMOR" as const, model_version: "g4",
      model_bundle_hash: "x", inference_kind: "prototype_inference",
      scores: { NON_TUMOR: 0.9, VIABLE_TUMOR: 0.05, NECROSIS: 0.05 },
      score_label: "Model score — uncalibrated", top1_score: 0.9,
      top_two_margin: 0.85, normalized_entropy: 0.3,
    },
    review_state: { status: "unreviewed" as const, revision: 0, latest_action: null, selected_class: null },
    review_priority_rank: 1,
  };
}

function listOf(ids: string[], over: Partial<ImageList> = {}): ImageList {
  return {
    total: ids.length, page: 1, page_size: 60, sort: "priority", filter: "all", query: "",
    items: ids.map(item), ...over,
  };
}

const LIST = listOf(["img-1", "img-2"], { total: 2 });
const OFFLINE = new ApiError({ status: null, code: "network", message: "Could not reach the server." });
const FORBIDDEN = new ApiError({ status: 403, code: "forbidden", message: "You do not have access to this project." });
const SERVER = new ApiError({ status: 500, code: "server_error", message: "The server hit an error. Nothing was saved." });
const ABORTED = new ApiError({ status: null, code: "aborted", message: "Request cancelled." });

beforeEach(() => {
  vi.clearAllMocks();
  (api.listImages as any).mockResolvedValue(LIST);
});

const renderBench = () => render(<Workbench onOpen={() => {}} />);

/** The workbench's completion handle, so a test waits on state and not on a sleep. */
const settled = () => waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state"));

// ---- the state contract itself: every kind §6 names, and every transition ----

describe("AsyncState transitions", () => {
  const rows: Array<{
    name: string;
    from: "idle" | "loading" | "ready" | "refreshing";
    event: "begin" | "resolve" | "reject" | "abort";
    arg?: unknown;
    filtered?: boolean;
    want: string;
    wantData?: boolean;
  }> = [
    { name: "idle -> loading (no data to refresh)", from: "idle", event: "begin", want: "loading", wantData: false },
    { name: "ready -> refreshing keeps the previous page", from: "ready", event: "begin", want: "refreshing", wantData: true },
    { name: "refreshing -> refreshing again", from: "refreshing", event: "begin", want: "refreshing", wantData: true },
    { name: "loading -> loading while already loading", from: "loading", event: "begin", want: "loading", wantData: false },
    { name: "loading -> ready", from: "loading", event: "resolve", want: "ready", wantData: true },
    { name: "loading -> empty/no_dataset (nothing ingested)", from: "loading", event: "resolve", filtered: false, want: "empty", wantData: true },
    { name: "loading -> empty/no_match (filters excluded everything)", from: "loading", event: "resolve", filtered: true, want: "empty", wantData: true },
    { name: "idle -> failed (network, nothing to show)", from: "idle", event: "reject", arg: OFFLINE, want: "failed", wantData: false },
    { name: "idle -> failed (server error is still failed)", from: "idle", event: "reject", arg: SERVER, want: "failed", wantData: false },
    { name: "ready -> offline keeps the previous page", from: "ready", event: "reject", arg: OFFLINE, want: "offline", wantData: true },
    { name: "refreshing -> offline keeps the previous page", from: "refreshing", event: "reject", arg: OFFLINE, want: "offline", wantData: true },
    { name: "ready -> offline on 403 still keeps it (already-scoped data)", from: "ready", event: "reject", arg: FORBIDDEN, want: "offline", wantData: true },
    { name: "an aborted request is ignored, not shown as a failure", from: "ready", event: "abort", want: "ready", wantData: true },
    { name: "an aborted first load stays loading", from: "loading", event: "abort", want: "loading", wantData: false },
  ];

  it.each(rows)("$name", async ({ from, event, arg, filtered, want, wantData }) => {
    const { beginFetch, resolveFetch, rejectFetch } = await mod();
    // An `empty` outcome needs an empty page; every other row needs rows.
    const data = listOf(want === "empty" ? [] : ["img-1"]);
    const state: any = {
      idle: { kind: "idle" },
      loading: { kind: "loading" },
      ready: { kind: "ready", data },
      refreshing: { kind: "refreshing", data },
    }[from];
    expect(state.kind).toBe(from);

    const next = event === "begin" ? beginFetch(state)
      : event === "resolve" ? resolveFetch(state, data, { filtered: filtered === true })
      : event === "abort" ? rejectFetch(state, ABORTED)
      : rejectFetch(state, arg as never);

    expect(next.kind).toBe(want);
    expect("data" in next ? next.data !== undefined : false).toBe(wantData === true);
  });

  it("separates no_dataset from no_match", async () => {
    const { beginFetch, resolveFetch } = await mod();
    const loading = beginFetch({ kind: "idle" });
    const none = resolveFetch(loading, listOf([]), { filtered: false });
    const some = resolveFetch(loading, listOf([]), { filtered: true });
    expect(none.kind).toBe("empty");
    expect(some.kind).toBe("empty");
    expect((none as any).reason).toBe("no_dataset");
    expect((some as any).reason).toBe("no_match");
  });

  it("marks refreshing and offline as stale, and ready/empty as not", async () => {
    const { isStale } = await mod();
    expect(isStale({ kind: "refreshing", data: LIST })).toBe(true);
    expect(isStale({ kind: "offline", error: OFFLINE, data: LIST })).toBe(true);
    expect(isStale({ kind: "ready", data: LIST })).toBe(false);
    expect(isStale({ kind: "empty", reason: "no_match", data: LIST })).toBe(false);
  });

  it("treats 401 and 403 as permission, never as retryable", async () => {
    const { isPermissionDenied } = await mod();
    expect(isPermissionDenied(FORBIDDEN)).toBe(true);
    expect(isPermissionDenied(new ApiError({ status: 401, code: "auth_required", message: "x" }))).toBe(true);
    expect(isPermissionDenied(OFFLINE)).toBe(false);
    expect(isPermissionDenied(SERVER)).toBe(false);
  });

  it("bounds consecutive retries for one query", async () => {
    const { MAX_CONSECUTIVE_RETRIES, canRetry } = await mod();
    expect(MAX_CONSECUTIVE_RETRIES).toBe(3);
    const failed = { kind: "failed", error: SERVER } as const;
    expect(canRetry(failed, { inFlight: false, attempts: 0 })).toBe(true);
    expect(canRetry(failed, { inFlight: true, attempts: 0 })).toBe(false);
    expect(canRetry(failed, { inFlight: false, attempts: MAX_CONSECUTIVE_RETRIES })).toBe(false);
    // A permission denial is never retryable, however few attempts have been made.
    expect(canRetry({ kind: "failed", error: FORBIDDEN }, { inFlight: false, attempts: 0 })).toBe(false);
  });
});

// ---- user-visible behaviour in the workbench ----


describe("U003-AT01 empty dataset and HTTP failure have different wording", () => {
  it("tells an un-ingested dataset apart from a request that failed", async () => {
    (api.listImages as any).mockResolvedValue(listOf([], { total: 0 }));
    renderBench();
    await settled();
    const empty = screen.getByTestId("workbench").getAttribute("data-async-state");
    const emptyText = screen.getByTestId("async-state").textContent ?? "";
    expect(empty).toBe("empty");
    expect(emptyText).toMatch(/no patches have been loaded|no dataset/i);

    (api.listImages as any).mockRejectedValue(SERVER);
    render(<Workbench onOpen={() => {}} />);
    await waitFor(() =>
      expect(screen.getAllByTestId("workbench")[1]).toHaveAttribute("data-async-state", "failed"),
    );
    const failedText = screen.getAllByTestId("async-state")[1].textContent ?? "";
    expect(failedText).not.toBe(emptyText);
    expect(failedText).toMatch(/could not be loaded|server/i);
    // The empty wording must not be reused for a failure, and vice versa.
    expect(emptyText).not.toMatch(/could not be loaded/i);
    expect(failedText).not.toMatch(/no patches have been loaded|no dataset/i);
  });

  it("uses the no-match wording when a filter excludes every patch", async () => {
    (api.listImages as any).mockResolvedValue(listOf([], { total: 0 }));
    render(<Workbench onOpen={() => {}} />);
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "empty"));
    fireEvent.change(screen.getByTestId("filter-select"), { target: { value: "unreviewed" } });
    await waitFor(() =>
      expect(screen.getByTestId("async-state")).toHaveAttribute("data-empty-reason", "no_match"),
    );
    expect(screen.getByTestId("async-state").textContent ?? "").toMatch(/no patches match/i);
  });

  it("uses the no-dataset wording when nothing is ingested and nothing is filtered", async () => {
    (api.listImages as any).mockResolvedValue(listOf([], { total: 0 }));
    renderBench();
    await settled();
    expect(screen.getByTestId("async-state")).toHaveAttribute("data-empty-reason", "no_dataset");
  });
});

describe("U003-AT02 permission errors do not offer a bypass link", () => {
  it.each([
    ["403 forbidden", FORBIDDEN],
    ["401 auth_required", new ApiError({ status: 401, code: "auth_required", message: "You are not signed in." })],
  ])("offers no retry, no link, and makes no second call for %s", async (_name, err) => {
    (api.listImages as any).mockRejectedValue(err);
    renderBench();
    await settled();
    const box = screen.getByTestId("async-state");
    expect(box).toHaveAttribute("data-async-state", "failed");
    expect(box.textContent).toMatch(/access|not signed in/i);
    expect(screen.queryByTestId("async-retry")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
    expect(box.querySelector("a")).toBeNull();
    // No fallback to an unscoped or unauthenticated endpoint.
    expect(api.listImages).toHaveBeenCalledTimes(1);
    const only = (api.listImages as any).mock.calls[0];
    expect(only[0]).toEqual(expect.objectContaining({ filter: "all" }));
  });

  it("still offers retry for a retryable server error", async () => {
    (api.listImages as any).mockRejectedValue(SERVER);
    renderBench();
    await settled();
    expect(screen.getByTestId("async-retry")).toBeEnabled();
  });
});

/** A promise the test settles by hand, so a pending request can be observed. */
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => { resolve = res; reject = rej; });
  return { promise, resolve, reject };
}

describe("U003-AT03 a failed refresh keeps only explicitly labeled stale content", () => {
  it("retains the previous page as stale, never as current results", async () => {
    const first = deferred<ImageList>();
    (api.listImages as any).mockReturnValueOnce(first.promise).mockRejectedValueOnce(OFFLINE);
    renderBench();

    first.resolve(LIST);
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "ready"));
    expect(screen.getByTestId("gallery")).toHaveAttribute("data-stale", "false");

    // The next query fails. The cards on screen belong to the PREVIOUS query.
    fireEvent.change(screen.getByTestId("filter-select"), { target: { value: "unreviewed" } });
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "offline"));

    expect(screen.getByTestId("gallery")).toHaveAttribute("data-stale", "true");
    expect(screen.getByTestId("async-state")).toHaveAttribute("data-stale", "true");
    expect(screen.getByTestId("async-state").textContent ?? "").toMatch(/out of date/i);
    expect(screen.getByTestId("async-state").textContent ?? "").toMatch(/appear to be offline/i);
    // Retained, but only ever as stale.
    expect(screen.getByTestId("card-img-1")).toBeInTheDocument();
    expect(screen.getByTestId("gallery")).toHaveTextContent(/img-1/);
  });

  it("marks the previous page stale while a new query is still loading", async () => {
    const first = deferred<ImageList>();
    const second = deferred<ImageList>();
    (api.listImages as any).mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise);
    renderBench();
    first.resolve(LIST);
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "ready"));

    fireEvent.change(screen.getByTestId("search-input"), { target: { value: "img-9" } });
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "refreshing"));
    // Stale, not silently presented as results for "img-9".
    expect(screen.getByTestId("gallery")).toHaveAttribute("data-stale", "true");
    expect(screen.getByTestId("async-state").textContent ?? "").not.toMatch(/img-9.*result/i);

    second.resolve(listOf(["img-9"]));
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "ready"));
    expect(screen.getByTestId("gallery")).toHaveAttribute("data-stale", "false");
    expect(screen.getByTestId("card-img-9")).toBeInTheDocument();
  });

  // Found by the §11 rehearsal: the stale banner used to say "Offline" whatever
  // had actually happened, so a 500 or a 403 was reported to the reviewer as a
  // dropped connection. Only a real network failure is offline.
  it("does not report a server error or a denial as being offline", async () => {
    const first = deferred<ImageList>();
    (api.listImages as any).mockReturnValueOnce(first.promise).mockRejectedValueOnce(SERVER);
    renderBench();
    first.resolve(LIST);
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "ready"));

    fireEvent.change(screen.getByTestId("search-input"), { target: { value: "img" } });
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "offline"));

    const box = screen.getByTestId("async-state").textContent ?? "";
    expect(box).not.toMatch(/offline/i);
    expect(box).toMatch(/could not be refreshed/i);
    expect(screen.getByTestId("async-status").textContent ?? "").not.toMatch(/offline/i);
    // Still stale, and still retryable: the server answered, it just erred.
    expect(screen.getByTestId("async-state")).toHaveAttribute("data-stale", "true");
    expect(screen.getByTestId("async-retry")).toBeInTheDocument();
  });

  it("discards previous data on a first-load failure rather than inventing any", async () => {
    (api.listImages as any).mockRejectedValue(OFFLINE);
    renderBench();
    await settled();
    expect(screen.queryByTestId(/^card-/)).toBeNull();
    expect(screen.getByTestId("async-state")).toHaveAttribute("data-async-state", "failed");
  });
});

describe("U003-AT04 rapid retries produce no concurrent unbounded request loop", () => {
  it("issues one request per retry however fast the button is clicked", async () => {
    const retry = deferred<ImageList>();
    (api.listImages as any).mockRejectedValueOnce(SERVER).mockReturnValue(retry.promise);
    renderBench();
    await settled();

    const button = screen.getByTestId("async-retry");
    for (let i = 0; i < 12; i += 1) fireEvent.click(button);
    // Twelve clicks, one request: while a retry is in flight the control is gone,
    // and the handler refuses a second start even if it is invoked anyway.
    expect(api.listImages).toHaveBeenCalledTimes(2);
    expect(screen.queryByTestId("async-retry")).toBeNull();
    retry.resolve(LIST);
    await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "ready"));
    expect(api.listImages).toHaveBeenCalledTimes(2);
  });

  it("stops offering retry after the consecutive-retry bound for one query", async () => {
    (api.listImages as any).mockRejectedValue(SERVER);
    renderBench();
    await settled();
    for (let i = 0; i < 6; i += 1) {
      const button = screen.queryByTestId("async-retry");
      if (!button) break;
      fireEvent.click(button);
      await waitFor(() => expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "failed"));
    }
    expect(screen.queryByTestId("async-retry")).toBeNull();
    expect(screen.getByTestId("async-state").textContent ?? "").toMatch(/reload the page|give up|try again later/i);
    // 1 initial + 3 bounded retries, never 7.
    expect(api.listImages).toHaveBeenCalledTimes(4);
  });

  it("aborts a superseded request instead of letting responses race", async () => {
    const seen: AbortSignal[] = [];
    (api.listImages as any).mockImplementation((_p: unknown, opts: any) => {
      seen.push(opts.signal);
      return deferred<ImageList>().promise;
    });
    renderBench();
    const sort = screen.getByTestId("sort-select");
    fireEvent.change(sort, { target: { value: "image_id" } });
    fireEvent.change(sort, { target: { value: "predicted_class" } });
    fireEvent.change(sort, { target: { value: "image_id" } });
    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen.every(Boolean)).toBe(true);
    // Every request but the live one was cancelled.
    expect(seen.slice(0, -1).every((s) => s.aborted)).toBe(true);
    expect(seen[seen.length - 1].aborted).toBe(false);
  });
});

describe("U003-AT05 screen reader receives a concise state change announcement", () => {
  it("announces loading then completion in a polite live region", async () => {
    const first = deferred<ImageList>();
    (api.listImages as any).mockReturnValueOnce(first.promise);
    renderBench();

    const region = screen.getByTestId("async-status");
    expect(region).toHaveAttribute("role", "status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region).toHaveAttribute("aria-busy", "true");
    expect(region.textContent ?? "").toMatch(/loading/i);

    first.resolve(LIST);
    await waitFor(() => expect(region).toHaveAttribute("aria-busy", "false"));
    expect(region.textContent ?? "").toMatch(/2 patches|ready|loaded/i);
  });

  it("announces a hard failure assertively, because there is nothing to read", async () => {
    (api.listImages as any).mockRejectedValue(SERVER);
    renderBench();
    await waitFor(() => expect(screen.getByTestId("async-status")).toHaveAttribute("role", "alert"));
    expect(screen.getByTestId("async-status")).toHaveAttribute("aria-live", "assertive");
  });

  it("keeps the announcement concise and free of card content", async () => {
    (api.listImages as any).mockResolvedValue(listOf(["img-1", "img-2"]));
    renderBench();
    await settled();
    const said = screen.getByTestId("async-status").textContent ?? "";
    expect(said.length).toBeLessThanOrEqual(120);
    expect(said).not.toContain("img-1");
    expect(said).not.toContain("0.900");
  });
});

describe("Step 08 browser-test handle and boundary review", () => {
  it("publishes a state a browser test can await, without a fixed sleep", async () => {
    const first = deferred<ImageList>();
    (api.listImages as any).mockReturnValueOnce(first.promise);
    renderBench();
    const root = screen.getByTestId("workbench");
    expect(root).toHaveAttribute("data-async-state", "loading");
    first.resolve(LIST);
    await waitFor(() => expect(root).toHaveAttribute("data-async-state", "ready"));
    // The same attribute the rehearsal and any future e2e spec waits on.
    expect(root.getAttribute("data-async-state")).toMatch(/^(idle|loading|refreshing|ready|empty|failed|offline)$/);
  });

  it("keeps the controls, so a retry repeats the same validated query", async () => {
    (api.listImages as any).mockRejectedValue(SERVER);
    renderBench();
    await settled();
    expect(screen.getByTestId("search-input")).toHaveValue("");
    expect(screen.getByTestId("filter-select")).toHaveValue("all");
    fireEvent.click(screen.getByTestId("async-retry"));
    await waitFor(() => expect(api.listImages).toHaveBeenCalledTimes(2));
    // Identical parameters, not a reset to defaults and not a dropped filter.
    expect((api.listImages as any).mock.calls[1][0]).toEqual((api.listImages as any).mock.calls[0][0]);
    expect(screen.getByTestId("search-input")).toHaveValue("");
  });

  it.each([
    ["null payload", null],
    ["undefined payload", undefined],
    ["items is not an array", { total: 0, page: 1, page_size: 60, sort: "priority", filter: "all", query: "", items: {} }],
  ])("reports %s as an unexpected response instead of rendering it as empty", async (_n, payload) => {
    (api.listImages as any).mockResolvedValue(payload);
    renderBench();
    await settled();
    expect(screen.getByTestId("async-state")).toHaveAttribute("data-async-state", "failed");
    expect(screen.queryByTestId(/^card-/)).toBeNull();
    expect(screen.queryByTestId("async-retry")).toBeNull();
  });

  it("survives one row and does not treat a single patch as empty", async () => {
    (api.listImages as any).mockResolvedValue(listOf(["img-1"], { total: 1 }));
    renderBench();
    await settled();
    expect(screen.getByTestId("workbench")).toHaveAttribute("data-async-state", "ready");
    expect(screen.getByTestId("card-img-1")).toBeInTheDocument();
    expect(screen.queryByTestId("async-state")).toBeNull();
  });
});
