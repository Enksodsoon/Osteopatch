// Thin API client. Holds the bearer token + active project in module state and
// attaches them to every call. 127.0.0.1 backend only (via the Vite proxy).
import type {
  Gallery, GalleryItem, LiveCapability, LivePatchResult, LiveRunDetail,
  LiveRunSummary, LiveSlideResult, Me, PublicReport, ReportSummary, ServingModel,
  Meta, ModelCard, ImageList, ImageDetail, AttributionMeta,
} from "./types";

let token: string | null = null;
let projectId: string | null = null;

function headers(withProject = false): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (withProject && projectId) h["X-Project-Id"] = projectId;
  return h;
}

async function j<T>(res: Response): Promise<T> {
  expireSession(res);
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const payload = await res.json() as { detail?: unknown; error?: unknown };
      detail = payload.detail ?? payload.error ?? detail;
    } catch { /* non-JSON error body: keep status text */ }
    throw new Error(`${res.status}: ${JSON.stringify(detail)}`);
  }
  return res.json() as Promise<T>;
}

// ---- auth ----
export function setToken(t: string | null) { token = t; }
export function setProject(p: string | null) { projectId = p; }
export function getProject() { return projectId; }

export async function login(email: string): Promise<string> {
  const res = await fetch("/auth/login", {
    method: "POST", headers: headers(), body: JSON.stringify({ email }),
  });
  const data = await j<{ access_token: string }>(res);
  setToken(data.access_token);
  return data.access_token;
}

export async function me(): Promise<Me> {
  return j<Me>(await fetch("/auth/me", { headers: headers() }));
}

// ---- G6 review surface (ported, uses G7 auth headers) ----
export async function getMeta(): Promise<Meta> {
  return j<Meta>(await fetch("/v1/meta", { headers: headers(true) }));
}

export async function getHealth(): Promise<import("./types").Health> {
  return j<import("./types").Health>(await fetch("/v1/health", { headers: headers() }));
}

export async function getModelCard(): Promise<ModelCard> {
  return j<ModelCard>(await fetch("/v1/model-card", { headers: headers(true) }));
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
  return j<ImageList>(await fetch(`/v1/images?${sp.toString()}`, { headers: headers(true) }));
}

export async function getImage(imageId: string): Promise<ImageDetail> {
  return j<ImageDetail>(await fetch(`/v1/images/${encodeURIComponent(imageId)}`, { headers: headers(true) }));
}

export async function submitReviewG6(
  imageId: string,
  body: {
    prediction_id: string;
    action: string;
    selected_label?: string | null;
    reason?: string | null;
    note?: string | null;
    expected_revision: number;
    idempotency_key: string;
  },
): Promise<{ status: number; created: boolean; current_revision: number; review_event_id?: string; conflict?: boolean }> {
  const res = await fetch(`/v1/images/${encodeURIComponent(imageId)}/reviews`, {
    method: "POST",
    headers: headers(true),
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

export function exportReviewsUrl(format: "csv" | "json"): string {
  return `/v1/exports/reviews?format=${format}`;
}

function expireSession(res: Response) {
  if (res.status === 401 && token) {
    token = null;
    projectId = null;
    window.dispatchEvent(new Event("osteopatch:session-expired"));
  }
}

async function download(path: string, filename: string): Promise<void> {
  const res = await fetch(path, { headers: headers(true) });
  expireSession(res);
  if (!res.ok) throw new Error(`${res.status}: could not download ${filename}`);
  saveBlob(await res.blob(), filename);
}

function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function downloadJson(data: unknown, filename: string): void {
  saveBlob(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }), filename);
}

export interface SlideMeta {
  slide_id: string; project_id: string; filename: string; source_sha256: string; byte_size: number;
  width: number; height: number; engine: string; level_count: number; created_at: string;
  level_downsamples: number[]; tile_size: number; mpp_x: number | null; mpp_y: number | null;
}
export type SlideRegion = { x: number; y: number; width: number; height: number };
export async function slides(): Promise<SlideMeta[]> {
  return (await j<{ slides: SlideMeta[] }>(await fetch("/v1/slides", { headers: headers(true) }))).slides;
}
export async function uploadSlide(file: File): Promise<SlideMeta> {
  return j(await fetch("/v1/slides", { method: "POST", body: file,
    headers: { ...headers(true), "Content-Type": "application/octet-stream", "X-File-Name": encodeURIComponent(file.name) } }));
}
export const slideRegionPath = (id: string, region: SlideRegion) =>
  `/v1/slides/${id}/region.png?${new URLSearchParams({ x: String(region.x), y: String(region.y), width: String(region.width), height: String(region.height) })}`;
export const slideTilePath = (id: string, level: number, x: number, y: number) =>
  `/v1/slides/${id}/tiles/${level}/${x}/${y}.png`;
export function slideTileHeaders() { return headers(true); }
export const slideThumbnailPath = (id: string) => `/v1/slides/${id}/thumbnail.png`;
export function downloadSlide(id: string, filename: string): Promise<void> {
  return download(`/v1/slides/${id}/source`, filename);
}
export function downloadRegion(id: string, region: SlideRegion): Promise<void> {
  return download(slideRegionPath(id, region), `${id}-region.png`);
}
export async function analyzeSlide(id: string, region: SlideRegion | null): Promise<LivePatchResult | LiveSlideResult> {
  return j(await fetch(`/v1/slides/${id}/analyze`, { method: "POST", headers: headers(true), body: JSON.stringify(region) }));
}

export function downloadReviews(format: "csv" | "json"): Promise<void> {
  return download(exportReviewsUrl(format), `osteopatch-reviews.${format}`);
}

// ---- G6 attribution ----
export async function getAttributionMeta(imageId: string): Promise<AttributionMeta> {
  return j<AttributionMeta>(
    await fetch(`/v1/images/${encodeURIComponent(imageId)}/attribution/meta`, { headers: headers(true) }),
  );
}

/** Overlay PNG URL for a specific contrastive pair. */
export function attributionUrl(imageId: string, targetA: string, targetB: string): string {
  const sp = new URLSearchParams({ target_a: targetA, target_b: targetB, format: "png" });
  return `/v1/images/${encodeURIComponent(imageId)}/attribution?${sp.toString()}`;
}

export function newIdempotencyKey(): string {
  return `ui-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

/**
 * Fetch an authenticated PNG as an object URL. The G7 backend requires a Bearer
 * token for image endpoints, so a plain <img src> cannot work — this fetches
 * with auth headers and hands the DOM a blob URL instead.
 */
export async function authenticatedImageUrl(path: string): Promise<string> {
  return blobUrl(path);
}

// ---- G7 enterprise: existing functions (unchanged) ----
export async function gallery(sort = "priority", page = 1, pageSize = 24): Promise<Gallery> {
  const q = new URLSearchParams({ sort, page: String(page), page_size: String(pageSize) });
  return j<Gallery>(await fetch(`/api/v1/images?${q}`, { headers: headers(true) }));
}

export async function patch(imageId: string): Promise<GalleryItem> {
  return j<GalleryItem>(await fetch(`/api/v1/images/${encodeURIComponent(imageId)}`, { headers: headers(true) }));
}

export async function submitReview(
  imageId: string, predictionId: string, action: "ACCEPT" | "CORRECT" | "DEFER",
  opts: { selected_label?: string; reason?: string } = {},
) {
  const body = {
    prediction_id: predictionId, action,
    idempotency_key: `${imageId}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    ...opts,
  };
  return j(await fetch(`/api/v1/images/${encodeURIComponent(imageId)}/reviews`, {
    method: "POST", headers: headers(true), body: JSON.stringify(body),
  }));
}

export async function servingModel(): Promise<ServingModel | { serving: null }> {
  return j(await fetch("/v1/models/serving", { headers: headers() }));
}

export async function registerModel(body: {
  bundle_sha256: string; model_id: string; eval_card_ref: string; split_declared: string;
}) {
  return j(await fetch("/v1/models", { method: "POST", headers: headers(), body: JSON.stringify(body) }));
}

export async function promoteModel(bundle_sha256: string, to: string, eval_passed?: boolean) {
  return j(await fetch("/v1/models/promote", {
    method: "POST", headers: headers(), body: JSON.stringify({ bundle_sha256, to, eval_passed }),
  }));
}

export async function rollbackModel() {
  return j(await fetch("/v1/models/rollback", { method: "POST", headers: headers() }));
}

export async function health() {
  return j(await fetch("/v1/health", { headers: headers() }));
}

// ---- Authenticated bytes (G7) ----
export async function blobUrl(path: string): Promise<string> {
  const res = await fetch(path, { headers: headers(true) });
  expireSession(res);
  if (!res.ok) {
    throw new Error(`${res.status}: ${path}`);
  }
  return URL.createObjectURL(await res.blob());
}

// ---- Live inference (G7) ----
export async function liveCapability(): Promise<LiveCapability> {
  return j<LiveCapability>(await fetch("/v1/live/capability", { headers: headers(true) }));
}

async function upload(path: string, file: File): Promise<Response> {
  const h: Record<string, string> = { "Content-Type": "application/octet-stream" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (projectId) h["X-Project-Id"] = projectId;
  h["X-File-Name"] = file.name;
  return fetch(path, { method: "POST", headers: h, body: file });
}

export async function importPatch(file: File): Promise<LivePatchResult> {
  return j<LivePatchResult>(await upload("/v1/live/patches", file));
}

export async function importSlide(
  file: File,
  opts: { tile_px?: number; stride?: number; max_tiles?: number } = {},
): Promise<LiveSlideResult> {
  const q = new URLSearchParams();
  if (opts.tile_px != null) q.set("tile_px", String(opts.tile_px));
  if (opts.stride != null) q.set("stride", String(opts.stride));
  if (opts.max_tiles != null) q.set("max_tiles", String(opts.max_tiles));
  const qs = q.toString();
  return j<LiveSlideResult>(await upload(`/v1/live/slides${qs ? `?${qs}` : ""}`, file));
}

export async function liveRuns(limit = 20): Promise<LiveRunSummary[]> {
  const d = await j<{ runs: LiveRunSummary[] }>(
    await fetch(`/v1/live/runs?limit=${limit}`, { headers: headers(true) }),
  );
  return d.runs;
}

export async function liveRun(runId: string): Promise<LiveRunDetail> {
  return j<LiveRunDetail>(
    await fetch(`/v1/live/runs/${encodeURIComponent(runId)}`, { headers: headers(true) }),
  );
}

export async function deleteLiveRun(runId: string): Promise<{ deleted: boolean }> {
  return j(await fetch(`/v1/live/runs/${encodeURIComponent(runId)}`, {
    method: "DELETE", headers: headers(true),
  }));
}

export const mosaicPath = (runId: string) =>
  `/v1/live/runs/${encodeURIComponent(runId)}/mosaic.png`;

export const liveThumbnailPath = (runId: string) =>
  `/v1/live/runs/${encodeURIComponent(runId)}/thumbnail.png`;

export const tileAttributionPath = (runId: string, tileIndex: number) =>
  `/v1/live/runs/${encodeURIComponent(runId)}/tiles/${tileIndex}/attribution`;

export const fullImagePath = (imageId: string) =>
  `/v1/images/${encodeURIComponent(imageId)}/full`;

export const thumbnailPath = (imageId: string) =>
  `/v1/images/${encodeURIComponent(imageId)}/thumbnail`;

export const imageAttributionPath = (imageId: string) =>
  `/v1/images/${encodeURIComponent(imageId)}/attribution`;

// ---- Case reports (G7) ----
export async function createReport(body: {
  case_id: string;
  title: string;
  findings_text: string;
  findings_html?: string;
  image_ids: string[];
  run_ids: string[];
  slide_ids?: string[];
  revision_of?: string | null;
  signer_email?: string | null;
  signer_role?: string | null;
  signoff_note?: string | null;
}): Promise<PublicReport> {
  return j<PublicReport>(await fetch("/v1/reports", {
    method: "POST", headers: headers(true), body: JSON.stringify(body),
  }));
}

export async function reports(limit = 50): Promise<ReportSummary[]> {
  const d = await j<{ reports: ReportSummary[] }>(
    await fetch(`/v1/reports?limit=${limit}`, { headers: headers(true) }),
  );
  return d.reports;
}

export async function report(reportId: string): Promise<PublicReport> {
  return j<PublicReport>(
    await fetch(`/v1/reports/${encodeURIComponent(reportId)}`, { headers: headers(true) }),
  );
}

export const reportExportPath = (reportId: string, fmt: "html" | "md") =>
  `/v1/reports/${encodeURIComponent(reportId)}/export.${fmt}`;

export async function downloadExport(reportId: string, fmt: "html" | "md"): Promise<void> {
  return download(reportExportPath(reportId, fmt), `${reportId}.${fmt}`);
}
