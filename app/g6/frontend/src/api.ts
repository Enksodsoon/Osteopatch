// Typed fetch client for the OsteoPatch G6 API. All calls are relative (/v1/...)
// and go through the Vite dev proxy -> 127.0.0.1 backend. No hard-coded host,
// no second API provider: this module is the single place a request is built.
//
// F004 changes:
//   * every call accepts an optional AbortSignal, propagated straight to fetch;
//   * errors are typed and honest (see ./apiErrors) — a 409, a 500 and a
//     dropped connection during a write are three different, distinguishable
//     situations, and only the last one is "outcome unknown";
//   * a response body is read at most once, so an HTML 502 cannot turn into a
//     secondary JSON parse exception;
//   * mutations are never retried automatically.
// Existing exported signatures are unchanged; every new parameter is optional.

import type { AttributionMeta, Health, ImageDetail, ImageList, Meta, ModelCard } from "./types";
import {
  ApiError,
  classifyError,
  codeForStatus,
  decodeBody,
  messageFromBody,
  safeDetail,
  type ApiOutcome,
} from "./apiErrors";

export { ApiError, isRetryable } from "./apiErrors";

export interface RequestOptions {
  signal?: AbortSignal;
  method?: "GET" | "POST";
  body?: unknown;
  headers?: Record<string, string>;
}

// Monotonic request identity. A component can capture `lastRequestId()` before
// firing two reads and drop whichever reply is older, so a slow response B can
// never overwrite a newer response A.
let requestCounter = 0;

export const api = {
  lastRequestId(): number {
    return requestCounter;
  },
};

function nextRequestId(): number {
  requestCounter += 1;
  return requestCounter;
}

export interface HttpResult<T> {
  status: number;
  data: T;
  request_id?: string;
}

/**
 * Perform one request and return BOTH the decoded body and the real status.
 *
 * `mutation: true` is what makes a network failure report outcome "unknown"
 * instead of "rejected" — the write may have committed before the socket died.
 *
 * The status is returned rather than discarded because the review endpoint
 * answers 201 for a newly created event and 200 for an idempotent replay; a
 * caller reconciling a retry needs that distinction.
 */
export async function request<T = unknown>(
  path: string,
  opts: RequestOptions & { mutation?: boolean } = {},
): Promise<HttpResult<T>> {
  const { signal, method = "GET", body, headers = {}, mutation = false } = opts;
  nextRequestId();

  let res: Response;
  try {
    res = await fetch(path, {
      method,
      signal,
      headers: {
        ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...headers,
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch (err) {
    // Abort and network failure both happen BEFORE we can see a status.
    throw classifyError(err, { mutation });
  }

  // Read the body exactly once, regardless of content type.
  let raw: string | null = null;
  try {
    raw = await res.text();
  } catch {
    raw = null;
  }
  const parsed = decodeBody(raw);

  if (!res.ok) {
    const code = codeForStatus(res.status);
    throw new ApiError({
      status: res.status,
      code,
      // An HTML error page yields parsed === null and still produces a readable
      // message that names the status, rather than a JSON parse exception.
      message: messageFromBody(res.status, code, parsed),
      request_id: res.headers?.get?.("X-Request-Id") ?? undefined,
      outcome: "rejected",
      detail: safeDetail(parsed),
    });
  }

  return {
    status: res.status,
    data: parsed as T,
    request_id: res.headers?.get?.("X-Request-Id") ?? undefined,
  };
}

/** Decode a response body, discarding the status. */
export async function fetchJson<T = unknown>(
  path: string,
  opts: RequestOptions & { mutation?: boolean } = {},
): Promise<T> {
  const result = await request<T>(path, opts);
  return result.data;
}

// ---- metadata / gallery / detail ------------------------------------------
export async function getMeta(opts: RequestOptions = {}): Promise<Meta> {
  return fetchJson<Meta>("/v1/meta", opts);
}

export async function getHealth(opts: RequestOptions = {}): Promise<Health> {
  return fetchJson<Health>("/v1/health", opts);
}

export async function getModelCard(opts: RequestOptions = {}): Promise<ModelCard> {
  return fetchJson<ModelCard>("/v1/model-card", opts);
}

export async function listImages(
  params: {
    sort?: string;
    filter?: string;
    q?: string;
    page?: number;
    page_size?: number;
  },
  opts: RequestOptions = {},
): Promise<ImageList> {
  const sp = new URLSearchParams();
  if (params.sort) sp.set("sort", params.sort);
  if (params.filter) sp.set("filter", params.filter);
  if (params.q) sp.set("q", params.q);
  sp.set("page", String(params.page ?? 1));
  sp.set("page_size", String(params.page_size ?? 60));
  return fetchJson<ImageList>(`/v1/images?${sp.toString()}`, opts);
}

export async function getImage(imageId: string, opts: RequestOptions = {}): Promise<ImageDetail> {
  return fetchJson<ImageDetail>(`/v1/images/${encodeURIComponent(imageId)}`, opts);
}

export async function getReview(
  imageId: string,
  opts: RequestOptions = {},
): Promise<ImageDetail> {
  return fetchJson<ImageDetail>(`/v1/images/${encodeURIComponent(imageId)}/review`, opts);
}

// ---- review submission -----------------------------------------------------
export interface SubmitReviewBody {
  prediction_id: string;
  action: string;
  selected_label?: string | null;
  reason?: string | null;
  note?: string | null;
  expected_revision: number;
  idempotency_key: string;
  reviewer?: string;
}

export interface SubmitReviewResult {
  status: number;
  created: boolean;
  current_revision: number;
  review_event_id?: string;
  conflict?: boolean;
  /** "unknown" when the connection dropped and the write may have committed. */
  outcome?: ApiOutcome;
}

export async function submitReview(
  imageId: string,
  body: SubmitReviewBody,
  opts: RequestOptions = {},
): Promise<SubmitReviewResult> {
  const path = `/v1/images/${encodeURIComponent(imageId)}/reviews`;

  // A 409 is a normal, expected answer — not a transport failure — so it is
  // inspected directly rather than routed through the throw path. Nothing else
  // about the call changes, and `created` stays false so no caller can read it
  // as "Saved".
  try {
    const result = await request<Record<string, unknown>>(path, {
      ...opts,
      method: "POST",
      body,
      mutation: true,
    });
    return {
      // The backend answers 201 for a newly created event and 200 for an
      // idempotent replay. Both are real and the difference is meaningful, so
      // the actual status is reported rather than a hardcoded one.
      status: result.status,
      created: result.data?.created === true,
      current_revision: Number(result.data?.current_revision ?? 0),
      review_event_id: result.data?.review_event_id as string | undefined,
      outcome: "rejected",
    };
  } catch (err) {
    if (err instanceof ApiError && err.status === 409) {
      const detail = err.detail as { detail?: { current_revision?: number } } | null;
      return {
        status: 409,
        created: false,
        conflict: true,
        current_revision: Number(detail?.detail?.current_revision ?? 0),
        outcome: "rejected",
      };
    }
    // Never auto-retry a mutation; surface the typed error to the caller.
    throw err;
  }
}

// ---- attribution -----------------------------------------------------------
export async function getAttributionMeta(
  imageId: string,
  opts: RequestOptions = {},
): Promise<AttributionMeta> {
  return fetchJson<AttributionMeta>(
    `/v1/images/${encodeURIComponent(imageId)}/attribution/meta`,
    opts,
  );
}

/** Overlay PNG URL for a specific contrastive pair. Cache-busting is handled by
 *  the backend's deterministic cache (same pair -> same bytes). */
export function attributionUrl(imageId: string, targetA: string, targetB: string): string {
  const sp = new URLSearchParams({ target_a: targetA, target_b: targetB, format: "png" });
  return `/v1/images/${encodeURIComponent(imageId)}/attribution?${sp.toString()}`;
}

// ---- URLs (unchanged) ------------------------------------------------------
export function thumbnailUrl(imageId: string): string {
  return `/v1/images/${encodeURIComponent(imageId)}/thumbnail`;
}

export function fullUrl(imageId: string): string {
  return `/v1/images/${encodeURIComponent(imageId)}/full`;
}

export function exportUrl(format: "csv" | "json"): string {
  return `/v1/exports/reviews?format=${format}`;
}

export function newIdempotencyKey(): string {
  return `ui-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}
