/**
 * F004 — typed API errors.
 *
 * One error class, one body decoder, one classifier. The point is honesty: a
 * caller must always be able to tell
 *
 *   - "the server said no"      -> outcome "rejected", status is a real number
 *   - "we do not know"          -> outcome "unknown",  status is null
 *   - "the user navigated away" -> outcome "rejected", code "aborted"
 *
 * A network failure on a MUTATION is "unknown", never "rejected": the write may
 * well have committed before the connection dropped, and reporting "not saved"
 * would be a false claim about a reviewer's decision.
 *
 * Nothing in a user-facing message may leak a token, a signed URL, an absolute
 * server path, or a stack trace. `safeDetail` is the single place that decides.
 */

export type ApiOutcome = "rejected" | "unknown";

export type ApiErrorCode =
  | "aborted"
  | "network"
  | "auth_required"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limited"
  | "upstream_unavailable"
  | "server_error"
  | "bad_response";

export interface ApiErrorInit {
  status: number | null;
  code: ApiErrorCode | string;
  message: string;
  request_id?: string;
  outcome?: ApiOutcome;
  detail?: unknown;
}

/** True when the call may have committed server-side despite failing locally. */
export function mayHaveCommitted(err: unknown): boolean {
  return err instanceof ApiError && err.outcome === "unknown";
}

/**
 * A single typed error for the whole client.
 *
 * Supports BOTH the legacy positional form `new ApiError(404, "HTTP 404", body)`
 * (kept so existing call sites and tests do not break) and the object form.
 */
export class ApiError extends Error {
  status: number | null;
  code: ApiErrorCode | string;
  request_id?: string;
  outcome: ApiOutcome;
  detail: unknown;
  /** Legacy convenience: true only for a real 409. */
  conflict: boolean;

  constructor(
    initOrStatus: ApiErrorInit | number,
    message?: string,
    detail?: unknown,
  ) {
    const init: ApiErrorInit =
      typeof initOrStatus === "number"
        ? {
            status: initOrStatus,
            code: codeForStatus(initOrStatus),
            message: message ?? `HTTP ${initOrStatus}`,
            detail,
          }
        : initOrStatus;

    super(init.message);
    this.name = "ApiError";
    this.status = init.status;
    this.code = init.code;
    this.request_id = init.request_id;
    this.detail = init.detail ?? null;
    this.conflict = init.code === "conflict" || init.status === 409;
    // Default: a definite HTTP response means the server rejected it.
    this.outcome = init.outcome ?? "rejected";
  }

  /** True when this error was produced by the user (or a scope change) aborting. */
  get aborted(): boolean {
    return this.code === "aborted";
  }

  /**
   * True when the call may already have been persisted server-side.
   *
   * A caller must not tell a reviewer their decision "was not saved" when this
   * is true; the honest message is that the outcome is unknown until the record
   * is reloaded.
   */
  get mayHaveCommitted(): boolean {
    return this.outcome === "unknown";
  }
}

export function codeForStatus(status: number): ApiErrorCode {
  if (status === 401) return "auth_required";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation";
  if (status === 429) return "rate_limited";
  if (status === 502 || status === 503 || status === 504) return "upstream_unavailable";
  if (status >= 500) return "server_error";
  return "bad_response";
}

const STATUS_TEXT: Record<string, string> = {
  aborted: "Request cancelled.",
  network: "Could not reach the server.",
  auth_required: "You are not signed in.",
  forbidden: "You do not have access to this project.",
  not_found: "That item no longer exists.",
  conflict: "This changed since you loaded it. Reload and try again.",
  validation: "That submission was rejected as invalid.",
  rate_limited: "Too many requests. Wait a moment and try again.",
  upstream_unavailable: "The server is temporarily unavailable.",
  server_error: "The server hit an error. Nothing was saved.",
  bad_response: "Unexpected response from the server.",
};

/**
 * Parse a response body AT MOST ONCE.
 *
 * Returns null for an empty, non-JSON, or unparsable body instead of throwing,
 * so a 502 HTML error page never turns into a secondary SyntaxError that hides
 * the real status.
 */
export function decodeBody(raw: string | null | undefined): unknown {
  if (raw === null || raw === undefined) return null;
  const text = raw.trim();
  if (text === "") return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Pull a human-safe message out of a decoded FastAPI-style error body. */
export function messageFromBody(status: number | null, code: string, body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (detail && typeof detail === "object") {
    const d = detail as { error?: unknown; message?: unknown };
    if (typeof d.error === "string" && d.error.trim()) return d.error.trim();
    if (typeof d.message === "string" && d.message.trim()) return d.message.trim();
  }
  if (status !== null) return `Request failed (HTTP ${status}).`;
  return STATUS_TEXT[code] ?? "Request failed.";
}

const SECRET_KEYS = new Set([
  "token",
  "access_token",
  "refresh_token",
  "authorization",
  "auth",
  "password",
  "secret",
  "api_key",
  "apikey",
  "cookie",
  "set-cookie",
  "stack",
  "traceback",
  "signed_url",
  "url",
]);

/**
 * Strip anything unsafe to render or log.
 *
 * Removes stack traces and credentials outright, and replaces values that look
 * like signed URLs or absolute server paths with a redaction marker rather than
 * trying to guess which part is sensitive.
 */
export function safeDetail(value: unknown, depth = 0): unknown {
  if (depth > 6) return "[truncated]";
  if (value === null || value === undefined) return null;
  if (typeof value === "string") return redactString(value);
  if (typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map((v) => safeDetail(v, depth + 1));

  const out: Record<string, unknown> = {};
  for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
    if (SECRET_KEYS.has(key.toLowerCase())) {
      out[key] = "[redacted]";
      continue;
    }
    out[key] = safeDetail(val, depth + 1);
  }
  return out;
}

function redactString(text: string): string {
  let out = text;
  if (/Traceback \(most recent call last\)/i.test(out)) return "[redacted stack]";
  out = out.replace(/eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)?/g, "[redacted token]");
  out = out.replace(/X-Amz-Signature=[^&\s]+/gi, "X-Amz-Signature=[redacted]");
  out = out.replace(/\/(?:srv|var|home|Users|root)\/[^\s"']*/g, "[redacted path]");
  out = out.replace(/[A-Za-z]:\\[^\s"']*/g, "[redacted path]");
  out = out.replace(/runtime-artifacts[^\s"']*/g, "[redacted path]");
  return out;
}

/** Turn a thrown value from `fetch` into a typed error. */
export function classifyError(
  err: unknown,
  opts: { mutation?: boolean } = {},
): ApiError {
  const mutation = opts.mutation === true;
  const isAbort =
    (err instanceof Error && err.name === "AbortError") ||
    (typeof err === "object" && err !== null && (err as { name?: string }).name === "AbortError");

  if (isAbort) {
    // An abort we initiated means the request never completed on our terms.
    return new ApiError({
      status: null,
      code: "aborted",
      message: STATUS_TEXT.aborted,
      outcome: "rejected",
    });
  }

  if (err instanceof ApiError) return err;

  if (err instanceof TypeError || (err instanceof Error && /fetch|network/i.test(err.message))) {
    // THE IMPORTANT ONE: a dropped connection during a write may have committed.
    return new ApiError({
      status: null,
      code: "network",
      message: mutation
        ? "Connection lost while saving. The review may or may not have been recorded — reload before retrying."
        : STATUS_TEXT.network,
      outcome: mutation ? "unknown" : "rejected",
    });
  }

  return new ApiError({
    status: null,
    code: "bad_response",
    message: STATUS_TEXT.bad_response,
    outcome: "rejected",
  });
}

const RETRYABLE_CODES = new Set<string>([
  "network",
  "rate_limited",
  "server_error",
  "upstream_unavailable",
]);

const NEVER_RETRY_CODES = new Set<string>([
  "aborted",
  "auth_required",
  "forbidden",
  "not_found",
  "conflict",
  "validation",
  "bad_response",
]);

/**
 * Retry policy. A caller must pass whether the call was a mutation.
 *
 * Writes are NEVER retried automatically: a replayed review with a fresh
 * idempotency key could record a second decision. Auth failures are never
 * retried, because a retry against an unauthenticated local endpoint would
 * silently downgrade the request.
 */
export function isRetryable(err: unknown, opts: { mutation?: boolean } = {}): boolean {
  if (opts.mutation === true) return false;
  if (!(err instanceof ApiError)) return false;
  if (NEVER_RETRY_CODES.has(err.code)) return false;
  return RETRYABLE_CODES.has(err.code);
}

/** Convenience for deciding whether a rejection may have been persisted. */
export function isUnknownOutcome(err: unknown): boolean {
  return mayHaveCommitted(err);
}