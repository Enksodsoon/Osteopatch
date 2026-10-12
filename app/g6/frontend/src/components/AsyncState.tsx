/**
 * U003 — one honest vocabulary for read states.
 *
 * A boolean triple (`data` / `loading` / `failed`) cannot say the difference
 * between "first load" and "refreshing", or between "no patches match" and
 * "nothing has been ingested", and it silently keeps showing the previous
 * page's cards as though they were the answer to the current query. This
 * module replaces that with one discriminated union, so each of those
 * situations has to be named before it can be rendered.
 *
 * The rule that matters: previous data is never presented as current. It is
 * carried as `refreshing` or `offline`, both of which are marked stale, and
 * the caller is expected to label them.
 *
 * No CSS is added here. Every class used below already exists (U002's tokens
 * and the workbench's `inline-error` / `empty-state` / `gallery-skeleton`).
 */

import { ApiError, classifyError, isRetryable } from "../apiErrors";

export type AsyncKind =
  | "idle"
  | "loading"
  | "refreshing"
  | "ready"
  | "empty"
  | "failed"
  | "offline";

/** Why an empty result is empty. §"no matching filters" is not "no dataset". */
export type EmptyReason = "no_dataset" | "no_match";

export type AsyncState<T> =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "refreshing"; data: T }
  | { kind: "ready"; data: T }
  | { kind: "empty"; reason: EmptyReason; data: T }
  | { kind: "failed"; error: ApiError }
  | { kind: "offline"; error: ApiError; data: T };

/**
 * Consecutive retries allowed for one query before the control is withdrawn.
 * Sequential retries are the reviewer's prerogative and stay available up to
 * this bound; what must be impossible is two requests at once (see the
 * in-flight guard in the caller).
 */
export const MAX_CONSECUTIVE_RETRIES = 3;

const PERMISSION_CODES = new Set(["forbidden", "auth_required"]);

/** True when the request failed because this client is not allowed to ask. */
export function isPermissionDenied(err: unknown): boolean {
  return err instanceof ApiError && PERMISSION_CODES.has(err.code);
}

/** True when what is on screen came from an earlier query, not the current one. */
export function isStale(state: AsyncState<unknown>): boolean {
  return state.kind === "refreshing" || state.kind === "offline";
}

/** The carried payload, if this state has one. */
export function dataOf<T>(state: AsyncState<T>): T | undefined {
  return "data" in state ? state.data : undefined;
}

/**
 * Retry is offered only when it could plausibly succeed: not a permission
 * denial, nothing in flight, retryable code, and attempts left.
 */
export function canRetry(
  state: AsyncState<unknown>,
  opts: { inFlight: boolean; attempts: number },
): boolean {
  if (opts.inFlight) return false;
  if (opts.attempts >= MAX_CONSECUTIVE_RETRIES) return false;
  if (state.kind !== "failed" && state.kind !== "offline") return false;
  if (isPermissionDenied(state.error)) return false;
  return isRetryable(state.error);
}

const BAD_RESPONSE = () =>
  new ApiError({
    status: null,
    code: "bad_response",
    message: "The server sent a response this app cannot read.",
  });

/**
 * A payload we cannot render is a failure, never an empty result.
 *
 * Total by construction: reading `items` may itself throw, and a row that is
 * not an object would crash the first card that tried to read it, so both are
 * rejected here rather than one layer deeper in the gallery.
 */
function isReadable<T>(data: T): data is T {
  if (typeof data !== "object" || data === null) return false;
  let rows: unknown;
  try {
    rows = (data as { items?: unknown }).items;
  } catch {
    return false;
  }
  return Array.isArray(rows) && rows.every((r) => typeof r === "object" && r !== null);
}

/** A request starts. With data already on screen this is a refresh, not a load. */
export function beginFetch<T>(prev: AsyncState<T>): AsyncState<T> {
  return "data" in prev ? { kind: "refreshing", data: prev.data } : { kind: "loading" };
}

/** The request answered. An empty page is named by why it is empty. */
export function resolveFetch<T>(
  _prev: AsyncState<T>,
  data: T,
  opts: { filtered: boolean },
): AsyncState<T> {
  if (!isReadable(data)) return { kind: "failed", error: BAD_RESPONSE() };
  const rows = (data as { items: unknown[] }).items;
  if (rows.length === 0) {
    return { kind: "empty", reason: opts.filtered ? "no_match" : "no_dataset", data };
  }
  return { kind: "ready", data };
}

/**
 * The request failed. An abort is ours, not the user's problem, so it leaves
 * the state alone. A real failure keeps whatever was already loaded, labelled
 * stale by the caller, rather than discarding the reviewer's context.
 */
export function rejectFetch<T>(prev: AsyncState<T>, err: unknown): AsyncState<T> {
  const error = err instanceof ApiError ? err : classifyError(err);
  if (error.aborted) return prev;
  return "data" in prev
    ? { kind: "offline", error, data: prev.data }
    : { kind: "failed", error };
}

/**
 * A concise sentence for assistive technology. Deliberately short and free of
 * patch ids, scores and labels: a screen-reader user changing a filter should
 * hear that the result set changed, not have a page of cards read out.
 */
export function announcement<T>(state: AsyncState<T>): string {
  switch (state.kind) {
    case "idle":
      return "";
    case "loading":
      return "Loading patches.";
    case "refreshing":
      return "Updating the patch list.";
    case "offline":
      return isOffline(state.error)
        ? "Offline. Showing the previous patch list."
        : "Could not refresh. Showing the previous patch list.";
    case "failed":
      return "The patch queue could not be loaded.";
    case "empty":
      return state.reason === "no_match"
        ? "No patches match these filters."
        : "No patches have been loaded into this dataset.";
    case "ready": {
      const total = (state.data as { total?: unknown } | null)?.total;
      return typeof total === "number" ? `${total} patches loaded.` : "Patch list loaded.";
    }
  }
}

/**
 * Whether the reviewer is actually offline.
 *
 * Only a dropped connection is offline. A 500 or a 403 means the server was
 * reached and answered, so telling the reviewer they are offline would be a
 * small but real untruth about why the data is stale.
 */
function isOffline(err: ApiError): boolean {
  return err.code === "network";
}

/** The stale banner, which must not claim more certainty than we have. */
function staleTitle(err: ApiError): string {
  return isOffline(err)
    ? "You appear to be offline."
    : "The patch list could not be refreshed.";
}
function copy<T>(state: AsyncState<T>): { title: string; hint: string } {
  switch (state.kind) {
    case "failed":
    case "offline":
      return state.kind === "offline"
        ? { title: `${staleTitle(state.error)} Showing the previous list — out of date.`, hint: state.error.message }
        : { title: "The patch queue could not be loaded.", hint: state.error.message };
    case "empty":
      return state.reason === "no_match"
        ? { title: "No patches match these filters.", hint: "Clear the search or choose a broader review state." }
        : {
            title: "No patches have been loaded into this dataset yet.",
            hint: "Once a dataset version is ingested and selected, its patches appear here.",
          };
    default:
      return { title: "", hint: "" };
  }
}

export interface AsyncStatusProps<T> {
  state: AsyncState<T>;
  onRetry?: () => void;
  /** Consecutive retries already spent on the current query. */
  attempts?: number;
  inFlight?: boolean;
}

/**
 * The one place read state is rendered.
 *
 * Two regions, deliberately: a live region that always exists so state changes
 * are announced even when nothing visible changes, and a box for the states a
 * reviewer has to act on. A hard failure with nothing to read is an alert
 * (assertive); everything else is a status (polite).
 */
export function AsyncStatus<T>({ state, onRetry, attempts = 0, inFlight = false }: AsyncStatusProps<T>) {
  const hard = state.kind === "failed";
  const busy = state.kind === "loading" || state.kind === "refreshing";
  const retryable = Boolean(onRetry) && canRetry(state, { inFlight, attempts });
  const spent =
    !retryable &&
    (state.kind === "failed" || state.kind === "offline") &&
    !isPermissionDenied(state.error) &&
    attempts >= MAX_CONSECUTIVE_RETRIES;
  const { title, hint } = copy(state);

  return (
    <>
      <div
        data-testid="async-status"
        role={hard ? "alert" : "status"}
        aria-live={hard ? "assertive" : "polite"}
        aria-busy={busy}
      >
        {announcement(state)}
      </div>

      {(state.kind === "loading" || state.kind === "refreshing" || state.kind === "empty" || hard || state.kind === "offline") && (
        <div
          className={hard || state.kind === "offline" ? "inline-error" : "empty-state"}
          data-testid="async-state"
          data-async-state={state.kind}
          data-stale={isStale(state)}
          data-empty-reason={state.kind === "empty" ? state.reason : undefined}
        >
          {busy ? (
            <>
              <span className="muted small">{title || announcement(state)}</span>
              <span className="gallery-skeleton" aria-hidden="true" />
            </>
          ) : state.kind === "empty" ? (
            <div data-testid="workbench-empty">
              <strong>{title}</strong>
              <span>{hint}</span>
            </div>
          ) : (
            <>
              <strong>{title}</strong>
              <span>{hint}</span>
            </>
          )}

          {retryable && (
            <button className="btn-link" type="button" data-testid="async-retry" onClick={onRetry}>
              Try again
            </button>
          )}
          {spent && <span className="muted small">Reload the page to try again.</span>}
        </div>
      )}
    </>
  );
}
