// Thin API client. Holds the bearer token + active project in module state and
// attaches them to every call. 127.0.0.1 backend only (via the Vite proxy).
import type { Gallery, GalleryItem, Me, ServingModel } from "./types";

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
