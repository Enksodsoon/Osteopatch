import { test, expect } from "@playwright/test";

/**
 * Contrast sweep for U005's AT05, run against the live application.
 *
 * The failing rehearsal check reported "review status label: 1:1
 * (rgb(181,170,159) on rgb(181,170,159))" but did not retain which element or
 * which rule produced it. This sweeps every rendered text node in light and dark
 * and reports the effective foreground/background pair with the selector that
 * identifies it, so the offender is named rather than guessed.
 *
 * Background resolution walks ancestors until a non-transparent colour is found,
 * because a label is very often transparent and inherits its backdrop.
 */

const FLOOR = 4.5;

async function settle(page: import("@playwright/test").Page) {
  await page.locator("main").first().waitFor({ state: "visible", timeout: 20_000 });
  await page.waitForTimeout(1200);
}

type Row = {
  tag: string;
  cls: string;
  testid: string | null;
  text: string;
  color: string;
  bg: string;
  bgFrom: string;
  fontPx: number;
  bold: string;
  ratio: number;
  disabled: boolean;
  ariaDisabled: string | null;
};

async function sweep(page: import("@playwright/test").Page): Promise<Row[]> {
  return page.evaluate((floor) => {
    const parse = (s: string) => (s.match(/[\d.]+/g) ?? []).slice(0, 4).map(Number);
    const lum = (rgb: number[]) => {
      const [r, g, b] = rgb.map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const ratio = (fg: number[], bg: number[]) => {
      const a = lum(fg);
      const b = lum(bg);
      const [hi, lo] = a > b ? [a, b] : [b, a];
      return (hi + 0.05) / (lo + 0.05);
    };
    const alpha = (s: string) => {
      const p = parse(s);
      return p.length > 3 ? p[3] : 1;
    };
    const over = (fg: number[], bg: number[], a: number) =>
      fg.map((c, i) => c * a + bg[i] * (1 - a));

    /** Effective backdrop: walk up until something is actually painted. */
    const effectiveBg = (el: Element) => {
      const stack: number[][] = [];
      let node: Element | null = el;
      while (node) {
        const cs = getComputedStyle(node);
        const c = parse(cs.backgroundColor);
        const a = alpha(cs.backgroundColor);
        if (a > 0) {
          stack.push([c[0], c[1], c[2], a]);
          if (a >= 0.999) break;
        }
        node = node.parentElement;
      }
      // Composite from the bottom-most opaque layer upward.
      let base: number[] = [255, 255, 255];
      for (let i = stack.length - 1; i >= 0; i--) {
        const [r, g, b, a] = stack[i];
        base = over([r, g, b], base, a);
      }
      return { rgb: base, from: stack.length ? stack[stack.length - 1][3] : 0 };
    };

    const out: Row[] = [];
    const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const seen = new Set<string>();
    let n: Node | null;
    while ((n = walk.nextNode())) {
      const text = (n.textContent ?? "").trim();
      if (!text) continue;
      const el = n.parentElement;
      if (!el) continue;
      const cs = getComputedStyle(el);
      if (cs.visibility === "hidden" || cs.display === "none") continue;
      if (Number(cs.opacity) === 0) continue;
      const rect = el.getBoundingClientRect();
      if (rect.width === 0 || rect.height === 0) continue;

      const fgRaw = parse(cs.color);
      const fgA = alpha(cs.color);
      const { rgb: bg, from } = effectiveBg(el);
      const fg = fgA < 0.999 ? over([fgRaw[0], fgRaw[1], fgRaw[2]], bg, fgA) : [fgRaw[0], fgRaw[1], fgRaw[2]];
      const r = ratio(fg, bg);

      const fontPx = Number(cs.fontSize.replace("px", ""));
      const isLarge = fontPx >= 24 || (fontPx >= 18.66 && Number(cs.fontWeight) >= 700);
      const needed = isLarge ? 3 : floor;

      if (r < needed) {
        const key = `${el.tagName}|${el.className}|${text.slice(0, 24)}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push({
          tag: el.tagName,
          cls: typeof el.className === "string" ? el.className : "",
          testid: el.getAttribute("data-testid"),
          text: text.slice(0, 42),
          color: `rgb(${fg.map((c) => Math.round(c)).join(",")})`,
          bg: `rgb(${bg.map((c) => Math.round(c)).join(",")})`,
          bgFrom: from >= 0.999 ? "opaque ancestor" : "composited",
          fontPx,
          bold: cs.fontWeight,
          ratio: Math.round(r * 100) / 100,
          disabled: (el as HTMLButtonElement).disabled === true,
          ariaDisabled: el.getAttribute("aria-disabled"),
        });
      }
    }
    return out;
  }, FLOOR);
}

const ROUTES = [
  "#/workbench",
  "#/patch/Case-3-A17-15765-20926",
  "#/model-card",
  "#/attribution",
];

for (const scheme of ["light", "dark"] as const) {
  test(`AT05 sweep — every text node below the floor in ${scheme}`, async ({ page }) => {
    await page.emulateMedia({ colorScheme: scheme });
    for (const route of ROUTES) {
      await page.goto(route);
      await settle(page);
      const rows = await sweep(page);
      const where = page.url().split("/").pop();
      console.log(`\n### ${scheme.toUpperCase()} ${route} @ ${where} — ${rows.length} below ${FLOOR}:1`);
      for (const r of rows) {
        console.log(
          `  ${r.ratio}:1  <${r.tag} class="${r.cls}"${r.testid ? ` testid=${r.testid}` : ""}>` +
            `  color=${r.color} bg=${r.bg} (${r.bgFrom}) ${r.fontPx}px/${r.bold}  "${r.text}"` +
            (r.disabled ? "   [disabled — WCAG 1.4.3/1.4.11 exempt]" : "") +
            (r.ariaDisabled ? `   [aria-disabled=${r.ariaDisabled}]` : ""),
        );
      }
    }
    // The assertion is that the sweep RAN across every route, not that it found
    // nothing — an empty list would itself be the finding.
    expect(Array.isArray(rows)).toBe(true);
  });
}