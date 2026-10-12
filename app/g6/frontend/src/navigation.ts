/** U001 — hash-routed navigation.
 *
 * Pure and framework-free: parse a location hash into a typed route, serialize a
 * route back, and hand out exactly one `hashchange` subscription. Hash routing keeps
 * the existing static hosting working with no server rewrite rules and no router
 * dependency.
 *
 * Only navigation context is ever serialized. There is deliberately no pass-through
 * of unknown query parameters: a token, patient identifier or review note cannot
 * reach the URL because the serializer builds its string from these fields alone.
 */

export type RouteName =
  | "overview"
  | "workbench"
  | "patch"
  | "source-groups"
  | "analytics"
  | "model-card"
  | "system"
  | "demo";

/** Sort and filter vocabularies. The workbench renders exactly these values. */
export const VALID_SORTS = ["priority", "predicted_class", "image_id"] as const;
export const VALID_FILTERS = [
  "all", "unreviewed", "reviewed", "deferred",
  "pred_NON_TUMOR", "pred_VIABLE_TUMOR", "pred_NECROSIS",
] as const;

/** Destinations the brief names, whether or not this build implements them. */
export const DECLARED_ROUTES: readonly RouteName[] = [
  "overview", "workbench", "patch", "source-groups",
  "analytics", "model-card", "system", "demo",
];

export interface QueueContext {
  sort: string;
  filter: string;
  q: string;
  page: number;
}

export const DEFAULT_CONTEXT: QueueContext = { sort: "priority", filter: "all", q: "", page: 1 };

/** Bounds a hand-edited or hostile URL: page is 1-based, search text is capped. */
const MAX_PAGE = 10_000;
const MAX_QUERY = 200;

export type Route =
  | { name: "workbench"; context: QueueContext }
  | { name: "patch"; imageId: string; context: QueueContext }
  | { name: "model-card" }
  | { name: "attribution" }
  | { name: "not-available"; requested: string; declared: boolean };

/** A destination that can appear in the nav bar: implemented, and top-level. */
export type NavName = "workbench" | "model-card" | "attribution";

/** Implemented destinations, in nav order. Unsupported routes are never listed. */
export const NAV_ITEMS: ReadonlyArray<{ name: NavName; label: string }> = [
  { name: "workbench", label: "Workbench" },
  { name: "model-card", label: "Model card" },
  { name: "attribution", label: "Model attribution" },
];

function oneOf(value: string | null, allowed: readonly string[], fallback: string): string {
  return value !== null && allowed.includes(value) ? value : fallback;
}

/** Drop C0/C1 control characters; a search term is plain text, never markup. */
function plainText(value: string): string {
  return [...value].filter((ch) => {
    const code = ch.codePointAt(0) ?? 0;
    return code > 31 && code !== 127;
  }).join("");
}

/** Validate a query string; anything unrecognized falls back to the default. */
export function normalizeContext(params: URLSearchParams): QueueContext {
  const rawPage = Number(params.get("page"));
  const page = Number.isInteger(rawPage) && rawPage >= 1 && rawPage <= MAX_PAGE
    ? rawPage
    : DEFAULT_CONTEXT.page;
  return {
    sort: oneOf(params.get("sort"), VALID_SORTS, DEFAULT_CONTEXT.sort),
    filter: oneOf(params.get("filter"), VALID_FILTERS, DEFAULT_CONTEXT.filter),
    q: plainText(params.get("q") ?? "").slice(0, MAX_QUERY),
    page,
  };
}

function unavailable(requested: string, declared: boolean): Route {
  return { name: "not-available", requested, declared };
}

/** Parse a location hash (`#/patch/img-1?sort=image_id`) into a typed route. */
export function parseRoute(hash: string): Route {
  const raw = hash.replace(/^#/, "");
  if (raw === "" || raw === "/") return { name: "workbench", context: DEFAULT_CONTEXT };
  const queryAt = raw.indexOf("?");
  const path = queryAt === -1 ? raw : raw.slice(0, queryAt);
  const params = new URLSearchParams(queryAt === -1 ? "" : raw.slice(queryAt + 1));
  const context = normalizeContext(params);
  const segments = path.replace(/^\/+/, "").split("/");
  const head = segments[0] ?? "";

  if (head === "workbench") return { name: "workbench", context };
  if (head === "model-card") return { name: "model-card" };
  if (head === "attribution") return { name: "attribution" };
  if (head === "patch") {
    // decode after splitting, so an id containing "/" survives the round trip
    const imageId = decodeURIComponent(segments.slice(1).join("/"));
    if (imageId === "") return unavailable(path, true);
    return { name: "patch", imageId, context };
  }
  if ((DECLARED_ROUTES as readonly string[]).includes(head)) return unavailable(path, true);
  return unavailable(path, false);
}

/** Serialize a route to a location hash. Only known context fields are emitted. */
export function serializeRoute(route: Route): string {
  if (route.name === "not-available") return `#/${route.requested.replace(/^\/+/, "")}`;
  if (route.name === "model-card") return "#/model-card";
  if (route.name === "attribution") return "#/attribution";
  const context = route.context;
  const params = new URLSearchParams();
  if (context.sort !== DEFAULT_CONTEXT.sort) params.set("sort", context.sort);
  if (context.filter !== DEFAULT_CONTEXT.filter) params.set("filter", context.filter);
  if (context.q !== "") params.set("q", context.q);
  if (context.page !== DEFAULT_CONTEXT.page) params.set("page", String(context.page));
  const query = params.toString();
  const base = route.name === "patch"
    ? `#/patch/${encodeURIComponent(route.imageId)}`
    : "#/workbench";
  return query === "" ? base : `${base}?${query}`;
}

export function currentRoute(): Route {
  return parseRoute(typeof window === "undefined" ? "" : window.location.hash);
}

/** Exactly one `hashchange` listener; the returned function removes it. */
export function subscribeToRouteChange(onChange: () => void): () => void {
  const handler = () => onChange();
  window.addEventListener("hashchange", handler);
  return () => window.removeEventListener("hashchange", handler);
}
