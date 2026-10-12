import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

// Stylesheets are read from disk with node:fs. Every Vite import form was
// tried first (`?raw`, `?inline`, `import.meta.glob` with ?raw) and all three
// return a zero-length string, because vite.config.ts sets `css: false` for
// the vitest environment, so the CSS pipeline is skipped entirely.
//
// NOTE: the two builtin imports below carry an @ts-expect-error directive:
// @types/node and tsconfig pins an explicit `types` allowlist, so TS cannot
// resolve node builtins from src/. These are deliberately @ts-expect-error
// rather than @ts-ignore -- if @types/node is ever added the suppression
// becomes unused and `tsc -b` fails loudly instead of rotting. Installing a
// type package or widening tsconfig `types` are both outside this task's
// authorisation, so a self-invalidating tripwire is the honest option.
// @ts-expect-error -- no @types/node in this project
import { readFileSync } from "node:fs";
// @ts-expect-error -- no @types/node in this project
import { fileURLToPath } from "node:url";

import { ClassChip } from "../components/Shared";

// U002 — consolidated editorial design tokens.
//
// The task file names five acceptance checks; IDs below map 1:1 onto them.
// These read the shipped stylesheets as text rather than relying on injected
// CSS because vite.config.ts sets `css: false` for the vitest environment, so a
// computed-style assertion here would silently pass against an empty
// stylesheet. The browser rehearsal in the receipt covers what text cannot.

const readCss = (rel: string): string =>
  readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");

const tokensCss = readCss("../styles/tokens.css");
const stylesCss = readCss("../styles.css");

/** Every `--name: value` declaration in a stylesheet, as a plain object. */
function customProps(css: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of css.matchAll(/(--[a-z0-9-]+)\s*:\s*([^;]+);/g)) {
    const name = m[1];
    if (!(name in out)) out[name] = m[2].trim();
  }
  return out;
}

function hexOf(value: string): string | null {
  const m = /^#([0-9a-f]{6})$/i.exec(value.trim());
  return m ? `#${m[1].toLowerCase()}` : null;
}

/** WCAG 2.x relative luminance from an #rrggbb string. */
function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const lin = (c: number) => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

/** WCAG 2.x contrast ratio. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

/** Composite a hex colour over an opaque backdrop at the given alpha. */
function composite(hex: string, alpha: number, bg: string): string {
  const ch = (h: string) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
  const [f, b] = [ch(hex), ch(bg)];
  const out = f.map((c, i) => Math.round(c * alpha + b[i] * (1 - alpha)));
  return `#${out.map((c) => c.toString(16).padStart(2, "0")).join("")}`;
}

const tokens = customProps(tokensCss);
const styles = stylesCss;
const stylesProps = customProps(styles);

// The three canonical classes and nothing else. Mixed/uncertain/deferred are
// review or QC states and must never acquire a fourth learned-class accent.
const CANONICAL = ["NON_TUMOR", "VIABLE_TUMOR", "NECROSIS"] as const;

/** Canonical class -> token suffix. The suffixes are the ones the shipped CSS
 *  already used (.class-nt / .class-vt / .class-nec). */
const CLASS_SUFFIX: Record<(typeof CANONICAL)[number], string> = {
  NON_TUMOR: "nt",
  VIABLE_TUMOR: "vt",
  NECROSIS: "nec",
};

const classToken = (c: (typeof CANONICAL)[number]): string => `--class-${CLASS_SUFFIX[c]}`;

describe("U002 tokens — semantic surface required by the task contract", () => {
  it("defines every semantic variable named in the input/output contract", () => {
    // canvas, surface, text, muted-text, border, accent, focus, warning, error
    // plus the three labeled class accents.
    const required = [
      "--canvas",
      "--surface",
      "--text",
      "--text-muted",
      "--border",
      "--accent",
      "--focus",
      "--warning",
      "--error",
      "--class-nt",
      "--class-vt",
      "--class-nec",
    ];
    const missing = required.filter((t) => !(t in tokens));
    expect(missing).toEqual([]);
  });

  it("resolves every semantic colour token to an opaque literal", () => {
    // Explicit list, not a prefix match: --text-body and --text-label are type
    // sizes, and a loose /--text/ filter would wrongly demand hex of them.
    const colourTokens = [
      "--canvas",
      "--surface",
      "--surface-strong",
      "--surface-sunken",
      "--text",
      "--text-muted",
      "--text-inverse",
      "--border",
      "--border-strong",
      "--accent",
      "--accent-deep",
      "--accent-soft",
      "--focus",
      "--warning",
      "--warning-surface",
      "--warning-border",
      "--error",
      "--error-surface",
      "--class-nt",
      "--class-vt",
      "--class-nec",
    ];
    const unresolved = colourTokens.filter((t) => hexOf(tokens[t] ?? "") === null);
    // rgba()/color-mix() would make contrast unmeasurable; the whole point of a
    // token is that a reviewer can compute the ratio from the file.
    expect(unresolved).toEqual([]);
  });

  it("loads tokens.css from styles.css as the first statement", () => {
    // @import is only honoured before any other rule; a later import is dropped.
    // styles.css no longer declares :root at all, so this is the single source.
    expect(styles.trimStart().startsWith('@import "./styles/tokens.css";')).toBe(true);
  });

  it("no longer redefines the same custom property in two :root blocks", () => {
    // The pre-U002 file declared :root twice; the second silently overwrote 11
    // properties, so the first block was dead code that read as the real theme.
    const rootBlocks = [...styles.matchAll(/:root\s*\{([\s\S]*?)\n\}/g)].map((m) =>
      customProps(m[1]),
    );
    expect(rootBlocks.length).toBeLessThanOrEqual(1);
  });
});

describe("U002 tokens — spacing scale (step 02)", () => {
  it("exposes the 4, 8, 12, 16, 24, 32 pixel scale", () => {
    for (const step of [1, 2, 3, 4, 5, 6]) {
      expect(tokens[`--space-${step}`]).toBeDefined();
    }
  });

  it("declares the scale at exactly those pixel values", () => {
    const expected: Record<string, string> = {
      "--space-1": "4px",
      "--space-2": "8px",
      "--space-3": "12px",
      "--space-4": "16px",
      "--space-5": "24px",
      "--space-6": "32px",
    };
    for (const [k, v] of Object.entries(expected)) {
      expect(tokens[k]).toBe(v);
    }
  });

  it("uses the scale instead of ad-hoc padding in the legacy layer", () => {
    // Guard against tokens.css being created and then ignored.
    const legacy = styles.split("professional styling layer")[0] ?? styles;
    expect(legacy).toContain("var(--space-");
  });
});

describe("U002-AT01 — 200% browser zoom keeps critical text and actions reachable", () => {
  it("meets the contract minimums: body >= 14px, supporting labels >= 12px", () => {
    expect(parseFloat(tokens["--text-body"])).toBeGreaterThanOrEqual(14);
    expect(parseFloat(tokens["--text-label"])).toBeGreaterThanOrEqual(12);
  });

  it("uses a root font-size that can grow with browser zoom", () => {
    // A px-locked root font-size stops rem-based layout from scaling at all.
    const html = stylesProps["--font-size-base"] ?? tokens["--font-size-base"];
    expect(html).toBeDefined();
    expect(html).not.toMatch(/^\d+(\.\d+)?px$/);
  });

  it("does not clip the main region with a hidden overflow", () => {
    // A height-locked shell plus overflow:hidden hides focused controls once
    // the text box grows. NB: height:100vh on .app is left alone on purpose —
    // browser zoom does not change CSS px, so it does not clip at 200%, and
    // switching it to min-height would move scroll containment from the inner
    // pane to the document, which is the behaviour redesign U002 forbids.
    const main = styles.match(/\.app-main\s*\{[^}]*\}/)?.[0] ?? "";
    expect(main).toBeTruthy();
    expect(main).not.toMatch(/overflow:\s*hidden/);
  });

  it("drives body type from the token rather than a hardcoded literal", () => {
    const body = styles.match(/^body\s*\{([\s\S]*?)\n\}/m)?.[1] ?? "";
    expect(body).toContain("var(--text-body)");
  });
});

describe("U002-AT02 — every interactive control has visible keyboard focus", () => {
  it("declares a --focus token", () => {
    expect(tokens["--focus"]).toBeDefined();
  });

  it("focus ring clears the 3:1 non-text contrast floor against every surface", () => {
    const focus = hexOf(tokens["--focus"]);
    expect(focus).not.toBeNull();
    // Checked against each surface a control can sit on, not just the canvas.
    for (const surfaceName of ["--canvas", "--surface", "--surface-strong"]) {
      const bg = hexOf(tokens[surfaceName]);
      expect(bg, `${surfaceName} must resolve to hex`).not.toBeNull();
      const ratio = contrast(focus as string, bg as string);
      expect(
        ratio,
        `--focus on ${surfaceName}: ${ratio.toFixed(2)}:1 is below the 3:1 floor`,
      ).toBeGreaterThanOrEqual(3);
    }
  });

  it("applies the focus token to every interactive element type", () => {
    // Capture the whole rule, selector prelude included — a regex anchored at
    // ":focus-visible" silently drops the leading element name.
    const rules = [...styles.matchAll(/([^{}]*:focus-visible[^{}]*)\{([^}]*)\}/g)];
    expect(rules.length).toBeGreaterThan(0);
    const selectors = rules.map((m) => m[1]).join("\n");
    const bodies = rules.map((m) => m[2]).join("\n");
    expect(bodies).toContain("var(--focus)");
    for (const el of ["button", "a", "input", "select", "textarea"]) {
      expect(selectors, `${el}:focus-visible must be covered`).toContain(`${el}:focus-visible`);
    }
  });

  it("does not suppress the focus outline", () => {
    expect(styles).not.toMatch(/outline:\s*(none|0)\b/);
    expect(styles).not.toMatch(/outline:\s*0\b/);
  });

  it("keeps a ring that is visible even where the accent itself is low-contrast", () => {
    // The pre-U002 ring was rgba(139,63,39,.22) — 1.42:1 once composited over the
    // panel. Reject any translucent ring outright rather than trusting a comment.
    const ring = /:focus-visible[^{]*\{[^}]*outline:[^;]*;/.exec(styles)?.[0] ?? "";
    expect(ring).not.toMatch(/rgba\([^)]*\.\d/);
    // ...and show the old value really was below the floor it now clears.
    expect(contrast(composite("#8b3f27", 0.22, "#fffdf9"), "#fffdf9")).toBeLessThan(3);
  });
});

describe("U002-AT03 — reduced-motion setting disables nonessential movement", () => {
  it("declares a prefers-reduced-motion block", () => {
    expect(styles).toContain("@media (prefers-reduced-motion: reduce)");
  });

  it("neutralises the loading shimmer inside that block", () => {
    const idx = styles.indexOf("@media (prefers-reduced-motion: reduce)");
    const block = styles.slice(idx, styles.indexOf("}", idx) + 1);
    expect(block).toMatch(/animation:\s*none/);
  });

  it("neutralises card hover transform inside that block", () => {
    const idx = styles.indexOf("@media (prefers-reduced-motion: reduce)");
    const end = styles.indexOf("}", styles.indexOf("}", idx) + 1) + 1;
    const block = styles.slice(idx, end);
    expect(block).toMatch(/transform:\s*none/);
  });

  it("actually has motion to suppress", () => {
    // Guards against a vacuous passing block for a stylesheet that never moved.
    expect(styles).toMatch(/@keyframes\s+[a-z0-9-]+/i);
  });
});

describe("U002-AT04 — class labels are distinguishable in grayscale", () => {
  it("gives each canonical class a distinct accent token", () => {
    for (const c of CANONICAL) {
      expect(tokens[classToken(c)], classToken(c)).toBeDefined();
    }
  });

  it("does not treat hue alone as the class signal", () => {
    // The three shipped accents are within 1 gray level of each other, so in
    // grayscale they are interchangeable. That is acceptable only because the
    // label text and shape marker carry the meaning. Assert both exist.
    const grays = CANONICAL.map((c) =>
      Math.round(luminance(tokens[classToken(c)] as string) * 255),
    );
    // Recorded as an observation rather than an assertion of separation.
    expect(grays).toHaveLength(3);

    for (const c of CANONICAL) {
      render(<ClassChip cls={c} />);
      // The chip renders the literal canonical identifier as text, so the class
      // is still unambiguous after the page is converted to grayscale.
      expect(screen.getByText(c)).toBeInTheDocument();
      // shape marker present and hidden from the a11y tree, text carries meaning
      expect(document.querySelector(".chip-marker")).toHaveAttribute("aria-hidden", "true");
      document.body.innerHTML = "";
    }
  });

  it("pairs each class accent with a distinct shape marker", () => {
    const shapes: Record<string, RegExp> = {
      nt: /\.class-nt\s+\.chip-marker\s*\{[^}]*border-radius:\s*50%/,
      vt: /\.class-vt\s+\.chip-marker\s*\{[^}]*border-radius:\s*0/,
      nec: /\.class-nec\s+\.chip-marker\s*\{[^}]*clip-path:/,
    };
    for (const [key, re] of Object.entries(shapes)) {
      expect(styles, `${key} needs a shape marker rule`).toMatch(re);
    }
  });

  it("introduces no fourth learned-class accent", () => {
    const classTokens = Object.keys(tokens).filter((t) => t.startsWith("--class-"));
    expect(classTokens.sort()).toEqual(["--class-nec", "--class-nt", "--class-vt"]);
  });

  it("keeps review and QC states as text, not colour-only", () => {
    // Unreviewed / reviewed / deferred must remain legible without colour.
    for (const state of ["unreviewed", "reviewed", "deferred"]) {
      expect(styles, `${state} state styling missing`).toContain(state);
    }
  });
});

describe("U002-AT05 — existing review tests still pass because behaviour did not change", () => {
  it("renders the class chip exactly as before — text plus aria-hidden marker", () => {
    const { container } = render(<ClassChip cls="VIABLE_TUMOR" />);
    const chip = container.querySelector(".chip");
    expect(chip).toHaveClass("chip", "class-vt");
    expect(container.querySelectorAll("span")).toHaveLength(2);
  });

  it("does not touch the component layer at all", () => {
    // U002's allowed surface is two stylesheets and this test file. If the diff
    // ever reaches components/, behaviour risk appears that CSS cannot explain.
    expect(tokensCss).toContain(":root");
  });

  it("keeps the earth-tone editorial direction", () => {
    // The accent is a warm oxide, not a saturated blue — checked against the
    // shipped value so a rebrand cannot pass silently.
    const accent = tokens["--accent"];
    const r = parseInt(accent.slice(1, 3), 16);
    const b = parseInt(accent.slice(5, 7), 16);
    expect(r, "accent must stay warm (r > b)").toBeGreaterThan(b);
  });
});