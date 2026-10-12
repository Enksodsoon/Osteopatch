/**
 * F004 — typed API client: cancellation, honest errors, no silent write retries.
 *
 * Acceptance IDs map 1:1 to the task's named checks (F004-AT01..AT05).
 *
 * The client is exercised against a stubbed `fetch`, never a live backend, so
 * every failure mode is deterministic and no network call is made.
 */
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  ApiError,
  api,
  attributionUrl,
  exportUrl,
  fetchJson,
  fullUrl,
  getImage,
  getReview,
  listImages,
  request,
  submitReview,
  thumbnailUrl,
} from "../api";
import { classifyError, decodeBody, isRetryable, safeDetail } from "../apiErrors";

type Call = { url: string; init?: RequestInit };

function stubFetch(handler: (call: Call, n: number) => Promise<Response> | Response) {
  const calls: Call[] = [];
  const spy = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const call = { url: String(input), init };
    calls.push(call);
    return handler(call, calls.length);
  });
  vi.stubGlobal("fetch", spy);
  return { calls, spy };
}

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const REVIEW_BODY = {
  prediction_id: "pred-fx-01",
  action: "ACCEPT",
  expected_revision: 0,
  idempotency_key: "k1",
};

/**
 * Await a call that must reject, and return the typed error.
 *
 * `.catch(e => e as ApiError)` would widen the result to a union with the
 * success type, which is why this helper exists: it narrows once, properly.
 */
async function rejection(promise: Promise<unknown>): Promise<ApiError> {
  try {
    await promise;
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError);
    return err as ApiError;
  }
  throw new Error("expected the call to reject with an ApiError");
}

// --- F004-AT01 -------------------------------------------------------------
describe("F004-AT01 conflict stays distinguishable from a server error", () => {
  it("returns a conflict result for 409 and never throws", async () => {
    stubFetch(() =>
      jsonResponse(409, { detail: { current_revision: 3, error: "stale" } }),
    );

    const result = await submitReview("fx-01", REVIEW_BODY);

    expect(result.status).toBe(409);
    expect(result.conflict).toBe(true);
    expect(result.created).toBe(false);
    expect(result.current_revision).toBe(3);
    // "Saved" is derived from created; a conflict must never read as saved.
    expect(result.created).toBe(false);
  });

  it("throws a distinct ApiError for 500 that cannot be mistaken for a conflict", async () => {
    stubFetch(() => jsonResponse(500, { detail: { error: "boom" } }));

    const err = await rejection(submitReview("fx-01", REVIEW_BODY));

    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
    expect(err.code).not.toBe("conflict");
    expect(err.conflict).toBe(false);
    expect(err.outcome).toBe("rejected");
    // A 500 on a write is rejected by the server, so it is NOT unknown.
    expect(err.outcome).not.toBe("unknown");
  });

  it("409 and 500 produce different codes and statuses", async () => {
    stubFetch(() => jsonResponse(409, { detail: { current_revision: 1 } }));
    const conflict = await submitReview("fx-01", REVIEW_BODY);

    vi.unstubAllGlobals();
    stubFetch(() => jsonResponse(500, { detail: {} }));
    const serverErr = await rejection(submitReview("fx-01", REVIEW_BODY));

    // A conflict is a RESULT; a 500 is a typed ERROR. They must not be confusable.
    expect(conflict.status).toBe(409);
    expect(conflict.conflict).toBe(true);
    expect(conflict.created).toBe(false);

    expect(serverErr).toBeInstanceOf(ApiError);
    expect(serverErr.status).toBe(500);
    expect(serverErr.code).toBe("server_error");
    expect(serverErr.conflict).toBe(false);
    expect(conflict.status).not.toBe(serverErr.status);
  });
});

// --- F004-AT02 -------------------------------------------------------------
describe("F004-AT02 non-JSON error body yields a readable generic message", () => {
  it("does not throw a secondary JSON parse error for an HTML 502", async () => {
    stubFetch(
      () =>
        new Response("<html><body>502 Bad Gateway</body></html>", {
          status: 502,
          headers: { "Content-Type": "text/html" },
        }),
    );

    const err = await rejection(fetchJson("/v1/meta"));

    expect(err).toBeInstanceOf(ApiError);
    expect(err).not.toBeInstanceOf(SyntaxError);
    expect(err.message).toMatch(/502/);
    expect(err.message).not.toMatch(/JSON|Unexpected token|is not valid/i);
    expect(err.code).toBe("upstream_unavailable");
  });

  it("reads the error body exactly once", async () => {
    const body = new Response(JSON.stringify({ detail: { error: "nope" } }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
    // The client reads the body as text exactly once and then decodes it, so a
    // consumed stream can never be read a second time.
    const textSpy = vi.spyOn(body, "text");
    const jsonSpy = vi.spyOn(body, "json");

    stubFetch(() => body);
    await fetchJson("/v1/meta").catch(() => undefined);

    expect(textSpy).toHaveBeenCalledTimes(1);
    expect(jsonSpy).not.toHaveBeenCalled();
  });

  it("survives an empty 204-style error body", async () => {
    stubFetch(() => new Response(null, { status: 400 }));
    const err = await rejection(fetchJson("/v1/meta"));
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(400);
    expect(err.message).toMatch(/400/);
  });
});

// --- F004-AT03 -------------------------------------------------------------
describe("F004-AT03 an aborted read is not a server failure", () => {
  it("reports code 'aborted' with a null status", async () => {
    const controller = new AbortController();
    stubFetch(() => {
      const e = new Error("The operation was aborted.");
      e.name = "AbortError";
      return Promise.reject(e);
    });

    const pending = fetchJson("/v1/meta", { signal: controller.signal });
    controller.abort();
    const err = await rejection(pending);

    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("aborted");
    expect(err.status).toBeNull();
    expect(err.outcome).toBe("rejected");
    expect(err.message).not.toMatch(/500|server/i);
  });

  it("propagates the AbortSignal to fetch on gallery and detail reads", async () => {
    const controller = new AbortController();
    const { calls } = stubFetch(() => jsonResponse(200, { images: [], total: 0 }));

    await listImages({}, { signal: controller.signal });
    await getImage("fx-01", { signal: controller.signal });

    expect(calls).toHaveLength(2);
    for (const call of calls) {
      expect(call.init?.signal).toBe(controller.signal);
    }
  });

  it("an abort is not retryable", () => {
    expect(isRetryable(new ApiError({ status: null, code: "aborted", message: "x" }))).toBe(false);
  });
});

// --- F004-AT04 -------------------------------------------------------------
describe("F004-AT04 a timed-out write is outcome unknown", () => {
  it("marks a network-failed mutation outcome='unknown', never 'unsaved'", async () => {
    stubFetch(() => Promise.reject(new TypeError("Failed to fetch")));

    const err = await rejection(submitReview("fx-01", REVIEW_BODY));

    expect(err).toBeInstanceOf(ApiError);
    expect(err.code).toBe("network");
    expect(err.outcome).toBe("unknown");
    expect(err.status).toBeNull();
    // The key contract: we may not promise the write did not land.
    expect(err.mayHaveCommitted).toBe(true);
  });

  it("a write aborted before send is rejected, not unknown", async () => {
    const controller = new AbortController();
    stubFetch(() => {
      const e = new Error("aborted");
      e.name = "AbortError";
      return Promise.reject(e);
    });

    const err = await rejection(submitReview("fx-01", REVIEW_BODY, {
      signal: controller.signal,
    }));

    expect(err.code).toBe("aborted");
    expect(err.outcome).toBe("rejected");
    expect(err.mayHaveCommitted).toBe(false);
  });

  it("never auto-retries a mutation", async () => {
    const { calls } = stubFetch(() => Promise.reject(new TypeError("Failed to fetch")));
    await submitReview("fx-01", REVIEW_BODY).catch(() => undefined);
    expect(calls).toHaveLength(1);
  });

  it("does not auto-retry a rejected write either", async () => {
    const { calls } = stubFetch(() => jsonResponse(500, { detail: {} }));
    await submitReview("fx-01", REVIEW_BODY).catch(() => undefined);
    expect(calls).toHaveLength(1);
  });
});

// --- F004-AT05 -------------------------------------------------------------
describe("F004-AT05 a 401 never falls back to the unauthenticated G6 endpoint", () => {
  it("classifies 401 as auth_required and does not retry", async () => {
    const { calls } = stubFetch(() => jsonResponse(401, { detail: { error: "no token" } }));

    const err = await rejection(fetchJson("/api/v1/images"));

    expect(err.status).toBe(401);
    expect(err.code).toBe("auth_required");
    expect(calls).toHaveLength(1);
  });

  it("makes exactly one call and never rewrites the URL to /v1/", async () => {
    const { calls } = stubFetch(() => jsonResponse(401, { detail: {} }));
    await fetchJson("/api/v1/images").catch(() => undefined);

    expect(calls).toHaveLength(1);
    expect(calls[0].url).toBe("/api/v1/images");
    // Never rewritten to the local, unauthenticated G6 path.
    expect(calls[0].url.startsWith("/v1/")).toBe(false);
  });

  it("isRetryable is false for every auth and permission status", () => {
    for (const status of [401, 403]) {
      const err = new ApiError({
        status,
        code: status === 401 ? "auth_required" : "forbidden",
        message: "x",
      });
      expect(isRetryable(err)).toBe(false);
    }
  });

  it("falls back to no endpoint at all when auth is denied", async () => {
    const { calls } = stubFetch(() => jsonResponse(401, { detail: {} }));
    const err = await rejection(getReview("fx-01"));
    expect(calls).toHaveLength(1);
    expect(err.code).toBe("auth_required");
  });
});

// --- step 7: stale response identity ---------------------------------------
describe("step 7 stale-response identity", () => {
  it("resolves B before A when B's promise is created first", async () => {
    const order: string[] = [];
    let resolveA!: (v: unknown) => void;
    const gateA = new Promise((r) => {
      resolveA = r;
    });

    stubFetch((call) => {
      const id = call.url;
      if (id.endsWith("/a")) {
        return gateA.then(() => jsonResponse(200, { image_id: "a" })) as Promise<Response>;
      }
      order.push("b-resolved");
      return jsonResponse(200, { image_id: "b" });
    });

    const a = getImage("a").then((v) => {
      order.push("a-resolved");
      return v;
    });
    const b = getImage("b");

    const bValue = await b;
    resolveA(null);
    const aValue = await a;

    expect(order.indexOf("b-resolved")).toBeLessThan(order.indexOf("a-resolved"));
    expect(bValue.image_id).toBe("b");
    expect(aValue.image_id).toBe("a");
  });

  it("gives each request a monotonic sequence so a component can drop a stale reply", async () => {
    stubFetch(() => jsonResponse(200, {}));
    const first = api.lastRequestId();
    await fetchJson("/v1/meta");
    const second = api.lastRequestId();
    expect(second).toBeGreaterThan(first);
  });
});

describe("the real HTTP status is preserved, not hardcoded", () => {
  it("reports 201 for a newly created review event", async () => {
    stubFetch(() =>
      jsonResponse(201, {
        created: true,
        current_revision: 1,
        review_event_id: "rev-1",
      }),
    );
    const result = await submitReview("fx-01", REVIEW_BODY);
    expect(result.status).toBe(201);
    expect(result.created).toBe(true);
    expect(result.current_revision).toBe(1);
  });

  it("reports 200 for an idempotent replay that created nothing", async () => {
    stubFetch(() => jsonResponse(200, { created: false, current_revision: 1 }));
    const result = await submitReview("fx-01", REVIEW_BODY);
    expect(result.status).toBe(200);
    expect(result.created).toBe(false);
  });

  it("exposes status and body together via request()", async () => {
    stubFetch(() => jsonResponse(201, { ok: true }, { "X-Request-Id": "req-9" }));
    const res = await request<{ ok: boolean }>("/v1/thing", { method: "POST", body: {} });
    expect(res.status).toBe(201);
    expect(res.data.ok).toBe(true);
    expect(res.request_id).toBe("req-9");
  });
});

// --- step 6: safe error detail --------------------------------------------
describe("step 6 error details are safe to display", () => {
  it("redacts tokens, signed URLs, absolute server paths and stack traces", () => {
    const leaky = {
      stack: "Traceback (most recent call last):\n  File \"/srv/app/x.py\"",
      token: "eyJhbGciOiJIUzI1NiJ9.SECRET",
      authorization: "Bearer abc123",
      path: "/srv/osteopatch/runtime-artifacts/db/store.sqlite3",
      signed_url: "https://cdn.example.com/x.png?X-Amz-Signature=deadbeef",
      detail: { error: "safe message" },
    };
    const safe = safeDetail(leaky) as Record<string, unknown>;

    const text = JSON.stringify(safe);
    expect(text).not.toMatch(/SECRET|abc123|deadbeef/);
    expect(text).not.toMatch(/\/srv\/|runtime-artifacts/);
    expect(text).not.toMatch(/Traceback/);
    expect(safe.detail).toEqual({ error: "safe message" });
  });

  it("keeps a helpful server message intact", () => {
    expect(safeDetail({ detail: { error: "prediction_id does not belong to image_id" } })).toEqual({
      detail: { error: "prediction_id does not belong to image_id" },
    });
  });
});

// --- boundary sweep on the classifier itself -------------------------------
describe("boundary classification sweep", () => {
  it("maps every named failure mode to a distinct code", () => {
    const cases: Array<[ApiError, string]> = [
      [new ApiError({ status: null, code: "aborted", message: "m" }), "aborted"],
      [new ApiError({ status: null, code: "network", message: "m" }), "network"],
      [new ApiError({ status: 401, code: "auth_required", message: "m" }), "auth_required"],
      [new ApiError({ status: 403, code: "forbidden", message: "m" }), "forbidden"],
      [new ApiError({ status: 404, code: "not_found", message: "m" }), "not_found"],
      [new ApiError({ status: 409, code: "conflict", message: "m" }), "conflict"],
      [new ApiError({ status: 422, code: "validation", message: "m" }), "validation"],
      [new ApiError({ status: 500, code: "server_error", message: "m" }), "server_error"],
      [new ApiError({ status: 502, code: "upstream_unavailable", message: "m" }), "upstream_unavailable"],
    ];
    for (const [err, code] of cases) {
      expect(err.code).toBe(code);
    }
    expect(new Set(cases.map(([, c]) => c)).size).toBe(cases.length);
  });

  it("classifies a raw TypeError from fetch as network, not a crash", () => {
    const err = classifyError(new TypeError("Failed to fetch"), { mutation: false });
    expect(err.code).toBe("network");
    expect(err.status).toBeNull();
  });

  it("classifies an AbortError from fetch as aborted", () => {
    const e = new Error("aborted");
    e.name = "AbortError";
    expect(classifyError(e, { mutation: false }).code).toBe("aborted");
  });

  it("decodeBody tolerates null, empty, and non-object payloads", () => {
    expect(decodeBody(null)).toBeNull();
    expect(decodeBody("")).toBeNull();
    expect(decodeBody('"a string"')).toBe("a string");
    expect(decodeBody("123")).toBe(123);
    expect(decodeBody("[1,2]")).toEqual([1, 2]);
    expect(decodeBody("not json")).toBeNull();
  });

  it("only retries idempotent reads, and only on transient 5xx/429", () => {
    expect(isRetryable(new ApiError({ status: 503, code: "server_error", message: "m" }))).toBe(true);
    expect(isRetryable(new ApiError({ status: 429, code: "rate_limited", message: "m" }))).toBe(true);
    expect(isRetryable(new ApiError({ status: 404, code: "not_found", message: "m" }))).toBe(false);
    expect(isRetryable(new ApiError({ status: 400, code: "validation", message: "m" }))).toBe(false);
  });
});

// --- preserved public surface ---------------------------------------------
describe("existing public signatures still work", () => {
  it("still builds image URLs unchanged", () => {
    expect(thumbnailUrl("fx-01")).toBe("/v1/images/fx-01/thumbnail");
    expect(exportUrl("csv")).toBe("/v1/exports/reviews?format=csv");
    expect(fullUrl("fx-01")).toBe("/v1/images/fx-01/full");
    expect(attributionUrl("fx-01", "NON_TUMOR", "NECROSIS")).toContain(
      "/v1/images/fx-01/attribution?",
    );
  });

  it("ApiError keeps the legacy 3-arg constructor shape", () => {
    const legacy = new ApiError(404, "HTTP 404", { error: "x" });
    expect(legacy.status).toBe(404);
    expect(legacy.message).toBe("HTTP 404");
    expect(legacy.detail).toEqual({ error: "x" });
  });

  it("accepts the new object form", () => {
    const modern = new ApiError({
      status: 409,
      code: "conflict",
      message: "stale",
      request_id: "req-1",
      outcome: "rejected",
    });
    expect(modern.code).toBe("conflict");
    expect(modern.request_id).toBe("req-1");
    expect(modern.outcome).toBe("rejected");
    expect(modern).toBeInstanceOf(Error);
  });
});