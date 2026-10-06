// Thin API client. Holds the bearer token + active project in module state and
// attaches them to every call. 127.0.0.1 backend only (via the Vite proxy).
import type {
  Gallery, GalleryItem, LiveCapability, LivePatchResult, LiveRunDetail,
  LiveRunSummary, LiveSlideResult, Me, PublicReport, ReportSummary, ServingModel,
} from "./types";

let token: string | null = null;
let projectId: string | null = null;

export function setToken(t: string | null) { token = t; }
export function setProject(p: string | null) { projectId = p; }
export function getProject() { return projectId; }

function headers(withProject = false): Record<string, string> {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  if (token) h["Authorization"] = `Bearer ${token}`;
  if (withProject && projectId) h["X-Project-Id"] = projectId;
  return h;
}

async function j<T>(res: Response): Promise<T> {
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

// ---------------------------------------------------------------------------
// Authenticated bytes
//
// Every PNG on this surface is behind `Authorization: Bearer`. An `<img src>`
// cannot carry that header, so images are fetched and handed to the DOM as an
// object URL instead. This is the only honest way to show them; dropping the
// header would trade a visible image for a broken one.
// ---------------------------------------------------------------------------

/** Fetch a PNG as an object URL. Caller MUST revoke it when done. */
export async function blobUrl(path: string): Promise<string> {
  const res = await fetch(path, { headers: headers(true) });
  if (!res.ok) {
    // 404 here is the tenancy boundary working (not "not found to you").
    throw new Error(`${res.status}: ${path}`);
  }
  return URL.createObjectURL(await res.blob());
}

// ---------------------------------------------------------------------------
// Live inference
//
// Uploads are a RAW BODY plus an `X-File-Name` header — not multipart. The
// server does not have `python-multipart` and does not need it: the browser
// sends the file bytes straight through and names them in a header. Do not
// "fix" this by switching to FormData; it will 4xx.
// ---------------------------------------------------------------------------

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

export const tileAttributionPath = (runId: string, tileIndex: number) =>
  `/v1/live/runs/${encodeURIComponent(runId)}/tiles/${tileIndex}/attribution`;

export const fullImagePath = (imageId: string) =>
  `/v1/images/${encodeURIComponent(imageId)}/full`;

export const thumbnailPath = (imageId: string) =>
  `/v1/images/${encodeURIComponent(imageId)}/thumbnail`;

export const imageAttributionPath = (imageId: string) =>
  `/v1/images/${encodeURIComponent(imageId)}/attribution`;

// ---------------------------------------------------------------------------
// Case reports
//
// There is no update function and no update route: reports are append-only, so
// a revised report is a new POST. Do not add one.
// ---------------------------------------------------------------------------

export async function createReport(body: {
  case_id: string;
  title: string;
  findings_text: string;
  image_ids: string[];
  run_ids: string[];
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

/**
 * Download an export through the authenticated client.
 *
 * A plain `<a download>` cannot work here: the endpoint needs the bearer token,
 * and the browser will not attach it to a navigation. So the bytes are fetched
 * and handed to a temporary anchor as an object URL — the same reason images go
 * through `blobUrl`.
 */
export async function downloadExport(reportId: string, fmt: "html" | "md"): Promise<void> {
  const res = await fetch(reportExportPath(reportId, fmt), { headers: headers(true) });
  if (!res.ok) {
    throw new Error(`${res.status}: could not export ${fmt}`);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${reportId}.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
