/**
 * U005 - add light and dark themes with safe local preferences.
 *
 * U005-AT01 switching themes leaves image bytes and model scores unchanged
 * U005-AT02 blocked localStorage falls back to system mode without a crash
 * U005-AT03 system mode updates when the OS preference changes
 * U005-AT04 explicit dark mode survives refresh
 * U005-AT05 all status labels remain readable and not color-only
 *
 * Stylesheets are read from disk as text for the same reason as
 * design-tokens.test.tsx: vite.config.ts sets `css: false` for the vitest
 * environment, so an injected stylesheet is empty and any computed-style
 * assertion here would pass against nothing. Three things a stylesheet cannot
 * prove from jsdom - decoded histology pixels, OS-level media emulation, and a
 * paint before the first render - are proved in the real browser rehearsal
 * whose transcript is named in the receipt.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, cleanup, act } from "@testing-library/react";
import type { AttributionMeta, ImageDetail, ImageList, Meta } from "../types";

// @ts-expect-error -- no @types/node in this project (see design-tokens.test.tsx)
import { readFileSync } from "node:fs";
// @ts-expect-error -- no @types/node in this project (see design-tokens.test.tsx)
import { fileURLToPath } from "node:url";

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return { ...actual, getImage: vi.fn(), listImages: vi.fn(), getAttributionMeta: vi.fn(), submitReview: vi.fn() };
});

import * as api from "../api";
import { PatchReview } from "../components/PatchReview";
import { ClassChip } from "../components/Shared";

// The modules under construction are imported through a function so Vite cannot
// constant-fold the specifier: a missing file then fails these tests at RUNTIME
// instead of breaking collection for the whole file.
const themePath = (): string => "../theme";
const controlPath = (): string => "../components/ThemeControl";
// Type-only references: erased at compile time, so the import stays dynamic
// while `tsc` still knows exactly what these modules export.
type ThemeModule = typeof import("../theme");
type ControlModule = typeof import("../components/ThemeControl");
const theme = (): Promise<ThemeModule> => import(/* @vite-ignore */ themePath()) as Promise<ThemeModule>;
const control = (): Promise<ControlModule> =>
  import(/* @vite-ignore */ controlPath()) as Promise<ControlModule>;

// ---- fixtures ---------------------------------------------------------------

const PRED: ImageDetail["prediction"] = {
  prediction_id: "p-u005",
  predicted_class: "VIABLE_TUMOR",
  model_version: "g4",
  model_bundle_hash: "b".repeat(64),
  inference_kind: "prototype_inference",
  scores: { NON_TUMOR: 0.21, VIABLE_TUMOR: 0.52, NECROSIS: 0.27 },
  score_label: "Model score - uncalibrated",
  top1_score: 0.52,
  top_two_margin: 0.25,
  normalized_entropy: 0.9403,
};

const IMAGE: ImageDetail = {
  image_id: "img-u005-0001",
  source_group: "Case-u005",
  qc: {
    primary_qc_status: "PASS",
    training_eligible: true,
    qc_review_flag: false,
    qc_review_reason: null,
    original_label: "NON_TUMOR",
  },
  prediction: PRED,
  review_state: { status: "unreviewed", revision: 0, latest_action: null, selected_class: null },
  review_priority_rank: 1,
  history: [],
};

const LIST: ImageList = {
  total: 1,
  page: 1,
  page_size: 60,
  sort: "priority",
  filter: "all",
  query: "",
  items: [{ ...IMAGE, history: undefined } as unknown as ImageList["items"][number]],
};

const META: Meta = {
  canonical_classes: ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"],
  review_actions: ["ACCEPT", "CORRECT", "DEFER"],
  defer_reasons: ["mixed_tissue", "poor_image_quality"],
  score_label: "Model score - uncalibrated",
  disclaimer: "Educational / research prototype.",
  g7_placeholder: "",
};

const ATTR: AttributionMeta = {
  image_id: IMAGE.image_id,
  attribution_enabled: true,
  predicted_class: "VIABLE_TUMOR",
  default_pair: { a: "VIABLE_TUMOR", b: "NON_TUMOR" },
  pairs: [{ a: "VIABLE_TUMOR", b: "NON_TUMOR" }],
  recovered_model_id: "g4-behavioral-recovery-r1",
  source_prediction_model: "g4",
  source_prediction_bundle_sha256: "b".repeat(64),
  attribution_target: "logit difference",
  disclosure: "Behaviorally reconstructed classifier.",
  method_note: "Contrastive Grad-CAM.",
};

// ---- stylesheet readers -----------------------------------------------------

const readCss = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");

const tokensCss = readCss("../styles/tokens.css");
const stylesCss = readCss("../styles.css");

/** Body text of the first rule whose selector is exactly `selector`. */
function blockBody(css: string, selector: string): string {
  const at = css.indexOf(`${selector} {`);
  expect(at, `selector not found in stylesheet: ${selector}`).toBeGreaterThan(-1);
  return css.slice(at + selector.length + 2, css.indexOf("}", at));
}

/** `--name: value` pairs declared inside one rule body. */
function varsOf(body: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of body.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) out[m[1]] = m[2].trim();
  return out;
}

function hexOf(value: string): string | null {
  const m = /^#([0-9a-f]{6})$/i.exec(value.trim());
  return m ? `#${m[1].toLowerCase()}` : null;
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2.x contrast ratio between two #rrggbb literals. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const DARK_SELECTOR = ':root[data-theme="dark"]';
const SYSTEM_DARK_SELECTOR = ":root:not([data-theme])";

/**
 * Vars of a rule, or an empty map when the rule is not declared. Lenient on
 * purpose: a missing block has to fail the tests that assert on it, by name,
 * rather than abort collection for every test in the file.
 */
function varsFor(css: string, selector: string): Record<string, string> {
  const at = css.indexOf(`${selector} {`);
  if (at < 0) return {};
  return varsOf(css.slice(at + selector.length + 2, css.indexOf("}", at)));
}

const lightVars = varsFor(tokensCss, ":root");
const darkVars = varsFor(tokensCss, DARK_SELECTOR);
const systemDarkVars = varsFor(tokensCss, SYSTEM_DARK_SELECTOR);

interface Rule {
  selector: string;
  body: string;
}

/** Innermost rules, including those nested in @media blocks. */
function rules(css: string): Rule[] {
  return [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => ({
    selector: m[1].trim().replace(/\s+/g, " "),
    body: m[2],
  }));
}

/** A single selector of a possibly grouped prelude. */
function selectorsOf(prelude: string): string[] {
  return prelude
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0 && !s.startsWith("@"));
}
// ---- matchMedia / storage doubles -------------------------------------------

interface FakeMql {
  matches: boolean;
  addEventListener: (type: string, cb: (e: { matches: boolean }) => void) => void;
  removeEventListener: (type: string, cb: (e: { matches: boolean }) => void) => void;
}

/** A controllable prefers-color-scheme query; jsdom ships no matchMedia. */
function installMatchMedia(initialDark: boolean) {
  const listeners = new Set<(e: { matches: boolean }) => void>();
  let matches = initialDark;
  const mql: FakeMql = {
    get matches() {
      return matches;
    },
    addEventListener: (_type, cb) => {
      listeners.add(cb);
    },
    removeEventListener: (_type, cb) => {
      listeners.delete(cb);
    },
  };
  vi.stubGlobal(
    "matchMedia",
    vi.fn((query: string) => {
      if (query !== "(prefers-color-scheme: dark)") throw new Error(`unexpected query: ${query}`);
      return mql as unknown as MediaQueryList;
    }),
  );
  return {
    setDark(value: boolean) {
      matches = value;
      // Firing the media listeners is a state update in React's eyes. Without
      // act() every test that drives the OS preference prints an
      // "not wrapped in act(...)" warning, and the update is flushed by whatever
      // happens to tick next rather than by the test. Wrapping at the helper
      // covers every call site instead of patching each test.
      act(() => {
        for (const cb of [...listeners]) cb({ matches: value });
      });
    },
    listenerCount: () => listeners.size,
  };
}

// Captured before any test shadows it: jsdom exposes localStorage as an own
// accessor of window, so `delete` would remove it for good instead of restoring.
const ORIGINAL_LOCAL_STORAGE = Object.getOwnPropertyDescriptor(window, "localStorage");

/** Hide window.localStorage the way a cookie-blocked or private window does. */
function blockLocalStorageAccessor(): void {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    get() {
      throw new DOMException("The operation is insecure.", "SecurityError");
    },
  });
}

function restoreLocalStorageAccessor(): void {
  if (ORIGINAL_LOCAL_STORAGE) Object.defineProperty(window, "localStorage", ORIGINAL_LOCAL_STORAGE);
  else delete (window as unknown as Record<string, unknown>).localStorage;
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-preference");
  vi.mocked(api.getImage).mockResolvedValue(IMAGE);
  vi.mocked(api.listImages).mockResolvedValue(LIST);
  vi.mocked(api.getAttributionMeta).mockResolvedValue(ATTR);
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  restoreLocalStorageAccessor();
});

/** Everything about the patch screen a theme change must not be able to move. */
function patchSnapshot() {
  const root = document.querySelector('[data-testid="patch-review"]') as HTMLElement;
  const viewerImg = document.querySelector('[data-testid="image-viewer"] img');
  return {
    html: root.outerHTML,
    images: [...root.querySelectorAll("img")].map((i) =>
      [i.getAttribute("src"), i.getAttribute("alt"), i.getAttribute("style")].join("|"),
    ),
    scores: [...root.querySelectorAll(".scorebar-value")].map((e) => e.textContent),
    overlay: root.querySelector('[data-testid="attribution-overlay-img"]')?.getAttribute("src") ?? null,
    viewerTransform: viewerImg?.getAttribute("style") ?? null,
  };
}

async function renderPatchWithControl() {
  const { ThemeControl } = await control();
  return render(
    <>
      <ThemeControl />
      <PatchReview imageId={IMAGE.image_id} meta={META} onBack={() => {}} onNavigate={() => {}} />
    </>,
  );
}

describe("U005 contract - ThemePreference and the one storage key", () => {
  it("stores the preference under osteopatch:theme:v1 and nothing else", async () => {
    const t = await theme();
    expect(t.THEME_STORAGE_KEY).toBe("osteopatch:theme:v1");
  });

  it("offers exactly system | light | dark", async () => {
    const t = await theme();
    expect([...t.THEME_PREFERENCES]).toEqual(["system", "light", "dark"]);
  });

  it("accepts only those three literals as a preference", async () => {
    const t = await theme();
    for (const good of ["system", "light", "dark"]) expect(t.isThemePreference(good)).toBe(true);
    for (const bad of ["Dark", "auto", "", "light,dark", null, undefined, 1, {}]) {
      expect(t.isThemePreference(bad), String(bad)).toBe(false);
    }
  });

  it("persists the bare literal and no clinical or reviewer data", async () => {
    const t = await theme();
    for (const pref of t.THEME_PREFERENCES) {
      window.localStorage.clear();
      const res = t.writePreference(pref);
      expect(res.saved).toBe(true);
      // Exactly one key, and its value is one of the three literals: no image id,
      // no reviewer, no project, no free text.
      expect(Object.keys(window.localStorage)).toEqual([t.THEME_STORAGE_KEY]);
      expect(window.localStorage.getItem(t.THEME_STORAGE_KEY)).toBe(pref);
    }
  });

  it("falls back to system mode for a missing or foreign stored value", async () => {
    const t = await theme();
    for (const stored of [null, "Dark", "dark;light", "42"]) {
      window.localStorage.clear();
      if (stored !== null) window.localStorage.setItem(t.THEME_STORAGE_KEY, stored);
      expect(t.readPreference(), String(stored)).toBe("system");
    }
  });
});

describe("U005-AT01 - switching themes leaves image bytes and model scores unchanged", () => {
  it("renders the patch screen, then changes nothing but the theme attribute", async () => {
    await renderPatchWithControl();
    await screen.findByTestId("patch-review");
    // The attribution overlay is display:none until it decodes; force the load so
    // the heatmap <img> is part of what the comparison covers.
    fireEvent.load(await screen.findByTestId("attribution-overlay-img"));

    const before = patchSnapshot();
    expect(before.scores).toEqual(["0.210", "0.520", "0.270"]);
    expect(before.overlay).toContain("target_a=VIABLE_TUMOR");
    const themeBefore = document.documentElement.dataset.theme;

    fireEvent.click(await screen.findByTestId("theme-dark"));

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    expect(patchSnapshot()).toEqual(before);
    expect(themeBefore === undefined || themeBefore !== "dark").toBe(true);
  });

  it("keeps the histology <img> src and its zoom transform identical across themes", async () => {
    await renderPatchWithControl();
    await screen.findByTestId("patch-review");
    const viewerImg = () => document.querySelector('[data-testid="image-viewer"] img');
    const src = viewerImg()?.getAttribute("src");
    const transform = viewerImg()?.getAttribute("style");

    fireEvent.click(await screen.findByTestId("theme-light"));
    fireEvent.click(await screen.findByTestId("theme-dark"));

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    expect(viewerImg()?.getAttribute("src")).toBe(src);
    expect(viewerImg()?.getAttribute("style")).toBe(transform);
  });

  it("exposes no CSS that could invert or recolour an image or a heatmap", () => {
    // Step 07: histology, thumbnails and attribution overlays are evidence. A
    // filter on them would change the pixels a reviewer is judging.
    for (const css of [tokensCss, stylesCss]) {
      expect(css).not.toMatch(/mix-blend-mode/);
      for (const fn of ["invert(", "hue-rotate(", "sepia(", "saturate(", "brightness(", "contrast(", "grayscale("]) {
        expect(css.includes(fn), `${fn} must not appear in a stylesheet`).toBe(false);
      }
      // A bare `filter:`; backdrop-filter (the header blur) is allowed.
      expect(css).not.toMatch(/(^|[;{\s])filter\s*:/);
    }
    const evidenceish = /img|image|thumb|attrib|heatmap|overlay|viewer|stage/;
    for (const rule of rules(stylesCss).concat(rules(tokensCss))) {
      if (!evidenceish.test(rule.selector)) continue;
      expect(rule.body, `${rule.selector} must not filter evidence pixels`)
        .not.toMatch(/(^|[;{\s])filter\s*:/);
    }
  });

  it("keeps the image stage one fixed neutral in both themes", () => {
    // The backdrop a slide is read against is the same before and after a theme
    // switch, so nothing about the tissue's surroundings changes either.
    for (const selector of [".viewer", ".viewer-toolbar", ".viewer-stage", ".attrib-stage"]) {
      const inStyles = rules(stylesCss).filter((r) => selectorsOf(r.selector).includes(selector));
      expect(inStyles.length, `${selector} must exist in styles.css`).toBeGreaterThan(0);
      const repointed = rules(tokensCss).filter(
        (r) => selectorsOf(r.selector).some((s) => s.startsWith('[data-theme="dark"]') && s.endsWith(selector)),
      );
      expect(repointed.map((r) => r.selector), `${selector} must not be re-pointed by the dark block`).toEqual([]);
    }
  });
});

describe("U005-AT02 - blocked localStorage falls back to system mode without a crash", () => {
  it("starts in system mode when the storage accessor itself throws", async () => {
    const t = await theme();
    const media = installMatchMedia(true);
    blockLocalStorageAccessor();
    expect(() => t.readPreference()).not.toThrow();
    expect(t.readPreference()).toBe("system");
    const applied = t.applyStoredPreference();
    expect(applied.preference).toBe("system");
    expect(applied.persisted).toBe(false);
    // System mode still means something: the OS preference is honoured.
    expect(applied.resolved).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    media.setDark(false);
    expect(t.applyStoredPreference().resolved).toBe("light");
  });

  it("reports an unavailable store instead of throwing when a write is refused", async () => {
    const t = await theme();
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("QuotaExceededError", "QuotaExceededError");
    });
    const res = t.writePreference("dark");
    expect(res.saved).toBe(false);
    expect(["unavailable", "write-failed"]).toContain(res.reason);
    // The choice still applies for this session; only persistence failed.
    const applied = t.applyPreference("dark");
    expect(applied.resolved).toBe("dark");
    expect(applied.persisted).toBe(false);
    expect(applied.storageError).toBeTruthy();
    expect(document.documentElement.dataset.theme).toBe("dark");
    setItem.mockRestore();
  });

  it("reads a preference from a store whose getItem throws", async () => {
    const t = await theme();
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("The operation is insecure.", "SecurityError");
    });
    expect(t.readPreference()).toBe("system");
    expect(() => t.applyStoredPreference()).not.toThrow();
    getItem.mockRestore();
  });

  it("says out loud that a blocked store means session-only, and still themes", async () => {
    installMatchMedia(false);
    const t = await theme();
    const { ThemeControl } = await control();
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("QuotaExceededError", "QuotaExceededError");
    });
    render(<ThemeControl />);
    fireEvent.click(screen.getByTestId("theme-dark"));

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    const note = await screen.findByTestId("theme-storage-note");
    expect(note).toBeInTheDocument();
    // Honest, not a failure: the review screen is still usable.
    expect(note.textContent ?? "").toMatch(/not saved/i);
    expect(screen.getByRole("radio", { name: /dark/i })).toHaveAttribute("aria-checked", "true");
    expect(t.readPreference()).toBe("system");
    setItem.mockRestore();
  });
});

describe("U005-AT03 - system mode updates when the OS preference changes", () => {
  it("follows prefers-color-scheme while the preference is system", async () => {
    const t = await theme();
    const media = installMatchMedia(false);
    expect(t.systemPrefersDark()).toBe(false);
    expect(t.applyStoredPreference().resolved).toBe("light");
    media.setDark(true);
    expect(t.systemPrefersDark()).toBe(true);
    expect(t.applyStoredPreference().resolved).toBe("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
  });

  it("repaints the live app when the OS preference changes mid-session", async () => {
    const media = installMatchMedia(false);
    const { ThemeControl } = await control();
    render(<ThemeControl />);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
    expect(screen.getByRole("radio", { name: /system|auto/i })).toHaveAttribute("aria-checked", "true");

    media.setDark(true);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    media.setDark(false);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));
  });

  it("removes the media listener on unmount", async () => {
    const media = installMatchMedia(false);
    const t = await theme();
    const { ThemeControl } = await control();
    const view = render(<ThemeControl />);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBeDefined());
    expect(media.listenerCount()).toBe(1);
    view.unmount();
    expect(media.listenerCount()).toBe(0);

    // The standalone subscription used by the pre-render bootstrap is removable too.
    const seen: boolean[] = [];
    const stop = t.subscribeToSystemTheme((dark) => seen.push(dark));
    media.setDark(true);
    media.setDark(false);
    expect(seen).toEqual([true, false]);
    stop();
    media.setDark(true);
    expect(seen).toEqual([true, false]);
    expect(media.listenerCount()).toBe(0);
  });

  it("an explicit choice is not overridden when the OS flips", async () => {
    const t = await theme();
    const media = installMatchMedia(false);
    t.writePreference("light");
    expect(t.applyStoredPreference().resolved).toBe("light");
    media.setDark(true);
    expect(t.applyStoredPreference().resolved).toBe("light");
    // ...and the recorded choice is still light, not silently rewritten to system.
    expect(window.localStorage.getItem(t.THEME_STORAGE_KEY)).toBe("light");
  });

  it("survives a browser with no prefers-color-scheme query at all", async () => {
    const t = await theme();
    vi.stubGlobal("matchMedia", undefined);
    expect(t.systemPrefersDark()).toBe(false);
    expect(t.applyStoredPreference().resolved).toBe("light");
    const { ThemeControl } = await control();
    render(<ThemeControl />);
    fireEvent.click(screen.getByTestId("theme-dark"));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
  });
});

describe("U005-AT04 - explicit dark mode survives refresh", () => {
  it("re-applies a stored dark choice on a cold start", async () => {
    const t = await theme();
    installMatchMedia(false); // OS stays light: the stored choice has to win
    t.writePreference("dark");
    // Simulate the refresh: the document is rebuilt from scratch and the stored
    // preference is re-read, exactly as main.tsx does before the first render.
    document.documentElement.removeAttribute("data-theme");
    const applied = t.applyStoredPreference();
    expect(applied.preference).toBe("dark");
    expect(applied.resolved).toBe("dark");
    expect(applied.persisted).toBe(true);
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(document.documentElement.dataset.themePreference).toBe("dark");
  });

  it("round-trips the bare literal through storage", async () => {
    const t = await theme();
    t.writePreference("dark");
    expect(window.localStorage.getItem(t.THEME_STORAGE_KEY)).toBe("dark");
    expect(t.readPreference()).toBe("dark");
    expect(t.resolvePreference("dark", false)).toBe("dark");
    expect(t.resolvePreference("system", true)).toBe("dark");
    expect(t.resolvePreference("light", true)).toBe("light");
  });

  it("comes back dark after the control is unmounted and mounted again", async () => {
    installMatchMedia(false);
    const { ThemeControl } = await control();
    const first = render(<ThemeControl />);
    fireEvent.click(await screen.findByTestId("theme-dark"));
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    first.unmount();

    document.documentElement.removeAttribute("data-theme");
    render(<ThemeControl />); // the remount stands in for the refresh
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
    expect(screen.getByRole("radio", { name: /dark/i })).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByTestId("theme-storage-note")).toBeNull();
  });
});

/** Text pairs the palette must keep legible on their own surface. */
const TEXT_PAIRS: [string, string][] = [
  ["--text", "--canvas"],
  ["--text", "--surface"],
  ["--text", "--surface-strong"],
  ["--text", "--surface-sunken"],
  ["--text-muted", "--canvas"],
  ["--text-muted", "--surface"],
  ["--text-muted", "--surface-strong"],
  ["--text-muted", "--surface-sunken"],
  ["--accent", "--surface"],
  ["--accent-deep", "--surface"],
  ["--accent-deep", "--accent-soft"],
  ["--on-accent", "--accent"],
  ["--warning", "--warning-surface"],
  ["--warning", "--surface-strong"],
  ["--error", "--error-surface"],
  ["--error", "--surface-strong"],
  ["--class-nt", "--surface"],
  ["--class-vt", "--surface"],
  ["--class-nec", "--surface"],
  ["--class-nt", "--surface-strong"],
  ["--class-vt", "--surface-strong"],
  ["--class-nec", "--surface-strong"],
];

/** Non-text pairs: focus ring, class fills, legend dots. 3:1 floor. */
const GRAPHIC_PAIRS: [string, string][] = [
  ["--focus", "--canvas"],
  ["--focus", "--surface"],
  ["--focus", "--surface-strong"],
  ["--focus", "--surface-sunken"],
  ["--class-nt", "--surface-sunken"],
  ["--class-vt", "--surface-sunken"],
  ["--class-nec", "--surface-sunken"],
  ["--border-strong", "--surface"],
];

/** Contrast of a token pair, or NaN when either token is not an opaque hex. */
function ratioIn(vars: Record<string, string>, [fg, bg]: [string, string]): number {
  const a = hexOf(vars[fg] ?? "");
  const b = hexOf(vars[bg] ?? "");
  if (a === null || b === null) return NaN;
  return contrast(a, b);
}

const fmtRatio = (r: number): string => (Number.isNaN(r) ? "not declared as an opaque hex" : `${r.toFixed(2)}:1`);

type Pair = [string, string];

/** Pairs below `floor`, named rather than merely counted. */
function belowFloor(vars: Record<string, string>, pairs: Pair[], floor: number): string[] {
  return pairs
    .map((p) => [p, ratioIn(vars, p)] as const)
    .filter(([, r]) => !(r >= floor))
    .map(([p, r]) => `${p[0]} on ${p[1]}: ${fmtRatio(r)} (floor ${floor}:1)`);
}

describe("U005-AT05 - all status labels remain readable and not color-only", () => {
  it("keeps every text pair legible in the dark palette (4.5:1)", () => {
    expect(belowFloor(darkVars, TEXT_PAIRS, 4.5)).toEqual([]);
  });

  it("keeps muted text legible on every LIGHT surface, not only the dark palette", () => {
    // The dark palette was always checked at 4.5:1, but the light palette was
    // only ever held to "not worse than dark". That gap is how --text-muted
    // shipped at 4.19:1 on --surface-sunken — the backdrop behind the theme
    // control's own options — while its comment claimed 5.01:1. The light
    // palette now has to clear the same floor outright, on every surface that
    // can sit behind muted text.
    const pairs: Pair[] = [
      ["--text-muted", "--canvas"],
      ["--text-muted", "--surface"],
      ["--text-muted", "--surface-sunken"],
      ["--text-muted", "--surface-strong"],
    ];
    expect(belowFloor(lightVars, pairs, 4.5)).toEqual([]);
  });

  it("keeps focus rings, class fills and legend dots at or above the 3:1 floor", () => {
    expect(belowFloor(darkVars, GRAPHIC_PAIRS, 3)).toEqual([]);
  });

  it("does not make the low-contrast light pairs worse", () => {
    // These are the pairs the light theme itself only just manages; dark must be
    // at least as good, not merely "not terrible".
    const pairs: Pair[] = [
      ["--text-muted", "--canvas"],
      ["--text-muted", "--surface-sunken"],
      ["--class-nt", "--surface"],
      ["--class-vt", "--surface"],
      ["--class-nec", "--surface"],
    ];
    const worse = pairs
      .map((p) => [p, ratioIn(lightVars, p), ratioIn(darkVars, p)] as const)
      .filter(([, l, d]) => !(d >= l))
      .map(([p, l, d]) => `${p[0]} on ${p[1]}: light ${fmtRatio(l)} -> dark ${fmtRatio(d)}`);
    expect(worse).toEqual([]);
  });

  it("keeps the three canonical classes labelled and shape-marked, never colour-only", () => {
    for (const cls of ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"] as const) {
      const { container } = render(<ClassChip cls={cls} />);
      expect(screen.getByText(cls)).toBeInTheDocument();
      expect(container.querySelector(".chip-marker")).toHaveAttribute("aria-hidden", "true");
      cleanup();
    }
    // The dark palette carries exactly the same three accents - no fourth learned
    // class, and none of the review/QC states acquires an accent.
    for (const vars of [darkVars, systemDarkVars]) {
      const accents = Object.keys(vars).filter((k) => k.startsWith("--class-")).sort();
      expect(accents).toEqual(["--class-nec", "--class-nt", "--class-vt"]);
    }
  });

  it("keeps every review status a text label with a readable colour in both themes", () => {
    for (const state of ["unreviewed", "reviewed", "deferred"]) {
      expect(stylesCss, `${state} state styling missing`).toContain(`.status-${state}`);
    }
    // The pill behind those labels is re-pointed in dark, and each label colour
    // still clears 4.5:1 on the surface it now sits on.
    const pill = expectDarkOverride(".card-status");
    expect(pill.body).toMatch(/var\(--surface-strong\)|var\(--surface\)/);
    const pairs: Pair[] = [
      ["--text-muted", "--surface-strong"],
      ["--class-nt", "--surface-strong"],
      ["--warning", "--surface-strong"],
    ];
    expect(belowFloor(darkVars, pairs, 4.5)).toEqual([]);
  });

  it("gives every literal colour pair it introduces in dark a readable ratio", () => {
    for (const rule of darkOverrideRules()) {
      const bg = /background(?:-color)?\s*:\s*(#[0-9a-fA-F]{6})/.exec(rule.body);
      const fg = /(?:^|[;\s])color\s*:\s*(#[0-9a-fA-F]{6})/.exec(rule.body);
      if (!bg || !fg) continue;
      const r = contrast(bg[1].toLowerCase(), fg[1].toLowerCase());
      expect(r, `${rule.selector}: ${r.toFixed(2)}:1`).toBeGreaterThanOrEqual(4.5);
    }
  });
});

// ---- dark-theme stylesheet guards -------------------------------------------

const DARK_PREFIX = '[data-theme="dark"]';

/** Rules in tokens.css that only apply to the explicit dark theme. */
function darkOverrideRules(): Rule[] {
  return rules(stripComments(tokensCss)).filter((r) =>
    selectorsOf(r.selector).some((s) => s.startsWith(DARK_PREFIX)),
  );
}

function darkOverrideFor(selector: string): Rule | undefined {
  return darkOverrideRules().find((r) =>
    selectorsOf(r.selector).includes(`${DARK_PREFIX} ${selector}`),
  );
}

function expectDarkOverride(selector: string): Rule {
  const hit = darkOverrideFor(selector);
  expect(hit, `no dark override for ${selector}`).toBeDefined();
  return hit as Rule;
}

function stripComments(css: string): string {
  return css.replace(/\/\*[\s\S]*?\*\//g, "");
}

/**
 * Literal backgrounds in styles.css that are deliberately NOT re-pointed in
 * dark, each with the reason it is safe.
 */
const KEEPS_ITS_LIGHT_OR_FIXED_BACKGROUND: Record<string, string> = {
  ".viewer": "the slide stage is one fixed neutral in both themes",
  ".viewer-toolbar": "same fixed neutral as the stage it sits on",
  ".viewer-toolbar button": "toolbar controls on the fixed dark stage",
  ".viewer-stage": "the fixed dark reading stage",
  ".attrib-stage": "attribution overlays are composited on black in both themes",
  ".attrib-loading": "white text on a black scrim over the image",
  ".attrib-error": "white text on a red scrim over the image",
  ".card-rank": "the rank pill is already a dark chip on the thumbnail in both themes",
  ".app-nav button.active": "styles.css re-declares it later with var(--surface-strong)",
};

/** Every styles.css selector whose background is a literal rather than a token. */
function literalBackgroundSelectors(): string[] {
  const literal = /background(?:-color)?\s*:\s*(#[0-9a-fA-F]{3,8}|rgba?\(|linear-gradient)/;
  const out: string[] = [];
  for (const rule of rules(stripComments(stylesCss))) {
    if (!literal.test(rule.body)) continue;
    for (const s of selectorsOf(rule.selector)) if (!out.includes(s)) out.push(s);
  }
  return out;
}

describe("U005 dark theme - the stylesheet a reviewer can audit", () => {
  it("keeps the light :root block first so first-occurrence parsing still means light", () => {
    expect(tokensCss.indexOf(":root {")).toBeLessThan(tokensCss.indexOf(DARK_SELECTOR));
    expect(tokensCss.indexOf(DARK_SELECTOR)).toBeLessThan(tokensCss.indexOf(SYSTEM_DARK_SELECTOR));
  });

  it("declares the same dark values for an explicit choice and for the system query", () => {
    // The two paths are the same palette written twice because a media query
    // cannot share a declaration block. This is what stops them drifting.
    expect(Object.keys(systemDarkVars).filter((k) => k.startsWith("--"))).toEqual(
      Object.keys(darkVars).filter((k) => k.startsWith("--")),
    );
    expect(systemDarkVars).toEqual(darkVars);
  });

  it("resolves every dark colour token to an opaque hex literal", () => {
    const unresolved = Object.entries(darkVars)
      .filter(([k]) => k.startsWith("--") && /surface|text|border|accent|class|focus|warning|error|shadow/.test(k))
      .filter(([, v]) => hexOf(v) === null)
      .map(([k, v]) => `${k}: ${v}`);
    expect(unresolved).toEqual([]);
  });

  it("tells the browser which colour scheme is active in each theme", () => {
    // UA-drawn widgets (scrollbars, checkbox, range track, select popup) follow
    // color-scheme; without it they stay light inside a dark page.
    expect(blockBody(tokensCss, ":root")).toMatch(/color-scheme:\s*light/);
    expect(blockBody(tokensCss, DARK_SELECTOR)).toMatch(/color-scheme:\s*dark/);
    expect(blockBody(tokensCss, SYSTEM_DARK_SELECTOR)).toMatch(/color-scheme:\s*dark/);
  });

  it("keeps the earth-tone editorial direction in dark", () => {
    for (const [name, vars] of [["explicit", darkVars], ["system", systemDarkVars]] as const) {
      const accent = hexOf(vars["--accent"] ?? "");
      expect(accent, `${name} accent must be hex`).not.toBeNull();
      const r = parseInt((accent as string).slice(1, 3), 16);
      const b = parseInt((accent as string).slice(5, 7), 16);
      expect(r, `${name} accent must stay warm (r > b)`).toBeGreaterThan(b);
    }
  });

  it("re-points every literal background that would stay light in dark", () => {
    const missing: string[] = [];
    for (const selector of literalBackgroundSelectors()) {
      if (KEEPS_ITS_LIGHT_OR_FIXED_BACKGROUND[selector]) continue;
      if (!darkOverrideFor(selector)) missing.push(selector);
    }
    expect(missing).toEqual([]);
  });

  it("only changes colour in dark, never layout", () => {
    const geometry = /(^|[;{\s])(width|height|padding|margin|font-size|font-weight|line-height|transform|top|left|right|bottom|grid-template-columns|display|position)\s*:/;
    for (const rule of darkOverrideRules()) {
      expect(rule.body, `${rule.selector} must not change layout`).not.toMatch(geometry);
    }
  });

  it("keeps form controls, charts, tables and overlays readable in dark", () => {
    // Step 06. UA form controls inherit a light background and a dark colour, so
    // the inherited text colour has to be replaced, not just the page around it.
    const form = darkOverrideRules().find((r) => /(^|[\s,])input[\s,{:]/.test(r.selector) || /(^|[\s,])select[\s,{:]/.test(r.selector));
    expect(form, "dark mode must re-point input/select/textarea").toBeDefined();
    expect(form?.body).toMatch(/var\(--surface-strong\)|var\(--surface\)/);
    for (const selector of [".scorebars", ".scorebar-track", ".lim-item", ".lim-item.lim-blocking"]) {
      expectDarkOverride(selector);
    }
    // The model-card table needs no override: every colour in it is a token, so it
    // follows the surface it is printed on. Assert that rather than assuming it.
    for (const rule of rules(stylesCss).filter((r) => r.selector.startsWith(".kv"))) {
      expect(rule.body, ".kv must not hard-code a colour").not.toMatch(/(^|[;\s])(color|background)\s*:\s*#/);
    }
  });

  it("keeps a disabled control readable rather than recoloured per theme", () => {
    // Disabled styling is opacity-based in styles.css, so it fades towards whatever
    // surface it sits on and keeps working in both themes; a dark override must not
    // swap in a fixed disabled colour.
    expect(stylesCss).toMatch(/\.btn-primary:disabled\s*\{[^}]*opacity/);
    for (const rule of darkOverrideRules()) {
      if (!rule.selector.includes(":disabled")) continue;
      expect(rule.body, "disabled state must not hard-code a colour").not.toMatch(/(^|[;\s])color\s*:\s*#/);
    }
  });
});
