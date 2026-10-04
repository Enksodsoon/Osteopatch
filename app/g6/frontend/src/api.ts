// Typed fetch client for the OsteoPatch G6 API. All calls are relative (/v1/...)
// and go through the Vite dev proxy -> 127.0.0.1 backend.

import type { ImageDetail, ImageList, Meta } from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail: unknown = null;
    try {
      detail = await res.json();
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, `HTTP ${res.status}`, detail);
  }
  return (await res.json()) as T;
}

export async function getMeta(): Promise<Meta> {
  return j<Meta>(await fetch("/v1/meta"));
}

export async function listImages(params: {
  sort?: string;
  filter?: string;
  q?: string;
  page?: number;
  page_size?: number;
}): Promise<ImageList> {
  const sp = new URLSearchParams();
  if (params.sort) sp.set("sort", params.sort);
  if (params.filter) sp.set("filter", params.filter);
  if (params.q) sp.set("q", params.q);
  sp.set("page", String(params.page ?? 1));
  sp.set("page_size", String(params.page_size ?? 60));
  return j<ImageList>(await fetch(`/v1/images?${sp.toString()}`));
}

export async function getImage(imageId: string): Promise<ImageDetail> {
  return j<ImageDetail>(await fetch(`/v1/images/${encodeURIComponent(imageId)}`));
}

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
}

export async function submitReview(
  imageId: string,
  body: SubmitReviewBody,
): Promise<SubmitReviewResult> {
  const res = await fetch(`/v1/images/${encodeURIComponent(imageId)}/reviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (res.status === 409) {
    const d = await res.json().catch(() => ({}));
    return {
      status: 409,
      created: false,
      conflict: true,
      current_revision: (d?.detail?.current_revision as number) ?? 0,
    };
  }
  const data = await j<any>(res);
  return {
    status: res.status,
    created: !!data.created,
    current_revision: data.current_revision,
    review_event_id: data.review_event_id,
  };
}

export function thumbnailUrl(imageId: string): string {
  return `/v1/images/${encodeURIComponent(imageId)}/thumbnail`;
}

export function fullUrl(imageId: string): string {
  return `/v1/images/${encodeURIComponent(imageId)}/full`;
}

export function exportUrl(format: "csv" | "json"): string {
  return `/v1/exports/reviews?format=${format}`;
}

// ---- attribution (G7) ------------------------------------------------------
import type { AttributionMeta } from "./types";

export async function getAttributionMeta(imageId: string): Promise<AttributionMeta> {
  return j<AttributionMeta>(
    await fetch(`/v1/images/${encodeURIComponent(imageId)}/attribution/meta`),
  );
}

/** Overlay PNG URL for a specific contrastive pair. Cache-busting is handled by
 *  the backend's deterministic cache (same pair -> same bytes). */
export function attributionUrl(imageId: string, targetA: string, targetB: string): string {
  const sp = new URLSearchParams({ target_a: targetA, target_b: targetB, format: "png" });
  return `/v1/images/${encodeURIComponent(imageId)}/attribution?${sp.toString()}`;
}

export function newIdempotencyKey(): string {
  return `ui-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}
