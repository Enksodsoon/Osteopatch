import { test, expect } from "@playwright/test";
import { copyFileSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { extname } from "node:path";

const evidence = `${process.env.TEMP ?? "/tmp"}/osteopatch-ui-evidence`;
const source = process.env.OSTEOPATCH_TEST_WSI;

test("real WSI upload, navigation, annotations, inference, reports and downloads", async ({ page }) => {
  test.skip(!source, "Set OSTEOPATCH_TEST_WSI to a local educational SVS");
  test.setTimeout(240_000);
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  page.on("response", r => { if (r.status() >= 400) errors.push(`${r.status()} ${r.url()}`); });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/");
  await page.getByLabel("email").fill("reviewer@demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Images", exact: true }).click();
  const filename = `educational-demo${extname(source!)}`;
  const copy = `${process.env.TEMP ?? "/tmp"}/${filename}`;
  copyFileSync(source!, copy);
  await page.getByLabel("Upload WSI or image").setInputFiles(copy);
  const canvas = page.getByTestId("slide-canvas");
  await expect(canvas).toBeVisible({ timeout: 60_000 });
  await expect(canvas).toHaveAttribute("data-ready", "true", { timeout: 60_000 });
  await expect(canvas.locator("canvas").first()).toBeAttached();
  const fullZoom = await page.getByTestId("slide-zoom").getAttribute("data-zoom-value");
  const fullViewBounds = (await canvas.boundingBox())!;
  expect(fullViewBounds.height).toBeGreaterThan(500);
  await page.mouse.move(fullViewBounds.x + fullViewBounds.width / 2, fullViewBounds.y + fullViewBounds.height / 2);
  await page.mouse.wheel(0, -350);
  await expect.poll(() => page.getByTestId("slide-zoom").getAttribute("data-zoom-value")).not.toBe(fullZoom);
  await page.getByRole("button", { name: "Fit slide", exact: true }).click();
  const slideCard = page.getByRole("button", { name: `Open ${filename}`, exact: true }).first();
  const thumbnail = slideCard.getByTestId(/^slide-thumbnail-/);
  await expect(thumbnail).toBeVisible({ timeout: 60_000 });
  await expect.poll(() => thumbnail.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await slideCard.click();
  await expect(canvas).toBeVisible();
  await page.getByText("Slide details", { exact: true }).click();
  const details = page.locator(".slide-details");
  await expect(details).toContainText("resolution levels");
  await expect(details).toContainText(/openslide|pillow/i);
  await page.getByRole("button", { name: "Zoom in slide", exact: true }).click();
  await expect(canvas).toBeVisible();
  const bounds = (await canvas.boundingBox())!;
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.down(); await page.mouse.move(bounds.x + bounds.width / 2 + 20, bounds.y + bounds.height / 2 + 20); await page.mouse.up();
  await expect(canvas).toBeVisible();
  await page.getByRole("button", { name: "Draw annotation", exact: true }).click();
  await page.getByLabel("Annotation note", { exact: true }).fill("Practice region; tissue outside model evidence");
  await canvas.scrollIntoViewIfNeeded();
  const annotationBounds = (await canvas.boundingBox())!;
  await page.mouse.move(annotationBounds.x + annotationBounds.width * .4, annotationBounds.y + annotationBounds.height * .4);
  await page.mouse.down(); await page.mouse.move(annotationBounds.x + annotationBounds.width * .6, annotationBounds.y + annotationBounds.height * .6); await page.mouse.up();
  await expect(page.locator(".annotation-list li")).toHaveCount(1);
  const notesKey = await page.evaluate(() => Object.keys(sessionStorage).find(key => key.startsWith("slide-notes:") && JSON.parse(sessionStorage.getItem(key) ?? "[]").length === 1) ?? "");
  expect(notesKey).not.toBe("");
  await expect.poll(() => page.evaluate(key => JSON.parse(sessionStorage.getItem(key) ?? "[]").length, notesKey)).toBe(1);
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const theme of ["light", "dark"]) {
      if (await page.locator("html").getAttribute("data-theme") !== theme) await page.getByTestId("theme-toggle").click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      for (const selector of [".slide-upload", ".slide-actions button.btn-primary"]) {
        expect(await page.locator(selector).first().evaluate(el => {
          const style = getComputedStyle(el);
          const luminance = (color: string) => {
            const rgb = color.match(/[\d.]+/g)!.slice(0, 3).map(n => Number(n) / 255).map(n => n <= .04045 ? n / 12.92 : ((n + .055) / 1.055) ** 2.4);
            return rgb[0] * .2126 + rgb[1] * .7152 + rgb[2] * .0722;
          };
          if (style.backgroundColor === "rgba(0, 0, 0, 0)") return 0;
          const [a, b] = [luminance(style.color), luminance(style.backgroundColor)].sort((x, y) => y - x);
          return (a + .05) / (b + .05);
        })).toBeGreaterThanOrEqual(4.5);
      }
      if (width === 1440 || width === 390) {
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: `${evidence}/WSI-${width}-${theme}.png`, fullPage: true });
      }
    }
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  for (const name of ["Download original", "Download region PNG", "Download annotations JSON"]) {
    const downloaded = page.waitForEvent("download");
    await page.getByRole("button", { name, exact: true }).click();
    expect((await downloaded).suggestedFilename()).toMatch(/\.(svs|tif|tiff|png|json)$/i);
  }
  await expect(page.getByRole("button", { name: "Analyze this view", exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Analyze this view", exact: true }).click();
  await expect(page.getByTestId("slide-analysis-result").or(page.getByRole("alert"))).toBeVisible({ timeout: 120_000 });
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(page.getByTestId("slide-analysis-result")).toContainText("uncalibrated");
  await expect(page.getByTestId("analysis-region")).toBeVisible();
  const modelEvidence = page.getByTestId("slide-model-evidence");
  await modelEvidence.locator("summary").first().click();
  await expect(modelEvidence).toContainText("independent accuracy for this recovered model has not been measured");
  await expect(modelEvidence).toContainText("Frozen baseline accuracy 67.0%");
  await expect(modelEvidence).toContainText("Viable-tumor recall: 11.0%");
  const analysis = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download analysis JSON", exact: true }).click();
  expect((await analysis).suggestedFilename()).toMatch(/analysis.json$/);
  await page.evaluate(() => scrollTo(0, 0));
  await page.screenshot({ path: `${evidence}/WSI-analysis-desktop.png`, fullPage: true });
  await page.getByRole("button", { name: "Create case report", exact: true }).click();
  await expect(page.getByRole("button", { name: /Save report · 1/ })).toBeEnabled();
  await page.getByLabel("Report name", { exact: true }).fill("Uploaded WSI region — educational demo");
  await page.getByLabel("Findings", { exact: true }).fill("Software workflow only. Uploaded tissue is outside osteosarcoma model evidence.");
  await page.getByRole("button", { name: /Save report · 1/ }).click();
  await expect(page.getByTestId("report-hash-status")).toContainText("verified");
  const report = page.waitForEvent("download");
  await page.getByRole("button", { name: /^Download HTML/ }).click();
  const reportDownload = await report;
  expect(reportDownload.suggestedFilename()).toMatch(/html$/);
  const reportPath = await reportDownload.path();
  expect(reportPath).not.toBeNull();
  expect(await readFile(reportPath!, "utf8")).toContain("data:image/png;base64,");
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await expect(page.locator(".annotation-list li")).toHaveCount(1);
  await page.getByRole("button", { name: "Scan slide", exact: true }).click();
  await expect(page.getByTestId("slide-analysis-result")).toContainText(/tiles scored/, { timeout: 120_000 });
  await expect(page.getByTestId("analysis-tile").first()).toBeVisible();
  await expect(page.getByText(/Class map · not an attention heatmap/)).toBeVisible();
  await page.getByRole("gridcell").first().click();
  await expect(page.locator(".tile-inspect")).toBeVisible();
  await expect.poll(() => page.evaluate(key => JSON.parse(sessionStorage.getItem(key) ?? "[]").length, notesKey)).toBe(1);
  await page.reload();
  await expect.poll(() => page.evaluate(key => JSON.parse(sessionStorage.getItem(key) ?? "[]").length, notesKey)).toBe(1);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await expect(canvas).toBeVisible();
  await expect(page.locator(".annotation-list li")).toHaveCount(1);
  await page.getByRole("button", { name: /Remove annotation/ }).click();
  await expect(page.locator(".annotation-list li")).toHaveCount(0);
  await page.getByRole("button", { name: "Annotate current view", exact: true }).click();
  await expect(page.locator(".annotation-list li")).toHaveCount(1);
  await page.getByRole("button", { name: "Fit slide", exact: true }).click();
  await expect(canvas).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  expect(errors).toEqual([]);
});
