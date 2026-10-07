import { test, expect, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";

const evidence = `${process.env.TEMP ?? "/tmp"}/osteopatch-ui-evidence`;
const errors: string[] = [];

test.beforeAll(async () => { await mkdir(evidence, { recursive: true }); });

async function login(page: Page, email = "reviewer@demo") {
  await page.goto("/");
  await page.getByLabel("email").fill(email);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("workbench")).toBeVisible();
  await expect(page.getByText("Ready", { exact: true })).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  errors.length = 0;
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
});

test("review, self-check and append-only actions work", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 960 });
  await login(page);

  for (const name of ["Review set", "Images", "Reports", "Learn"]) {
    await expect(page.getByRole("button", { name, exact: true })).toBeVisible();
  }
  await expect(page.getByTestId("gallery").locator(".card")).toHaveCount(24);
  await page.screenshot({ path: `${evidence}/educational-review-desktop-light.png`, fullPage: true });
  const listCalls: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("/v1/images?") && request.url().includes("page_size=24")) listCalls.push(request.url());
  });

  await page.getByTestId("search-input").fill("Case-3-A10");
  await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
  await page.getByTestId("filter-select").selectOption("unreviewed");
  await page.getByTestId("search-input").fill("");
  await page.getByRole("button", { name: "Next page" }).click();
  await expect(page.getByText(/Page 2/)).toBeVisible();
  expect(listCalls.length).toBeLessThanOrEqual(8);
  await page.getByRole("button", { name: "Previous page" }).click();
  await expect(page.getByText(/Page 1/)).toBeVisible();
  await page.getByTestId("filter-select").selectOption("all");
  await page.getByTestId("search-input").fill("");

  const firstCard = page.getByTestId("gallery").locator(".card").first();
  const cardId = await firstCard.getAttribute("data-testid");
  expect(cardId).toBeTruthy();
  let imageId = cardId!.slice("card-".length);
  await page.getByTestId(`card-${imageId}`).click();
  await expect(page.getByTestId("patch-review")).toBeVisible();
  await expect(page.getByTestId("patch-review").locator(".pr-image-id")).toHaveText(imageId);
  await expect(page.getByTestId("image-viewer").getByAltText(imageId)).toBeVisible();
  const noteBounds = await page.getByTestId("review-note").boundingBox();
  expect(noteBounds?.width).toBeGreaterThan(200);
  expect(noteBounds?.height).toBeGreaterThanOrEqual(60);
  await page.screenshot({ path: `${evidence}/educational-patch-desktop-light.png`, fullPage: true });

  await page.getByRole("button", { name: "Try a self-check" }).click();
  await page.getByTestId("self-check-choice-VIABLE_TUMOR").click();
  await expect(page.getByTestId("scorebars")).toHaveCount(0);
  await expect(page.getByTestId("priority-values")).toHaveCount(0);
  await expect(page.getByTestId("review-panel")).toHaveCount(0);
  await page.getByRole("button", { name: "Reveal comparison" }).click();
  await expect(page.getByText(/not a measure of correctness/i)).toBeVisible();
  await expect(page.getByTestId("self-check").getByTestId("scorebars")).toBeVisible();
  await expect(page.getByTestId("scorebars")).toHaveCount(1);
  await expect(page.getByTestId("suggested-class")).toHaveCount(0);
  await page.screenshot({ path: `${evidence}/educational-self-check-desktop-light.png`, fullPage: true });

  const nextPatch = page.getByTestId("patch-review").locator(".pr-queue button").nth(1);
  const nextId = (await nextPatch.getAttribute("data-testid"))!.slice("queue-".length);
  await nextPatch.click();
  await expect(page.getByTestId("patch-review").locator(".pr-image-id")).toHaveText(nextId);
  imageId = nextId;
  await page.getByRole("button", { name: "Try a self-check" }).click();
  await expect(page.getByRole("button", { name: "Reveal comparison" })).toHaveCount(0);
  await expect(page.getByTestId("scorebars")).toHaveCount(0);
  await page.getByRole("button", { name: "Exit self-check" }).click();

  await page.getByRole("button", { name: /Zoom in/i }).click();
  await expect(page.getByText("125%")).toBeVisible();
  await page.getByRole("button", { name: /Reset view/i }).click();
  await expect(page.getByText("100%")).toBeVisible();

  await expect(page.getByTestId("scorebars")).toBeVisible();
  await expect(page.getByTestId("attribution-panel")).toBeVisible();

  const existingEvents = page.getByTestId("review-history").locator("[data-testid^='history-rev-']");
  const existingCount = await existingEvents.count();
  const lastRevision = existingCount
    ? Number((await existingEvents.last().getAttribute("data-testid"))!.slice("history-rev-".length))
    : 0;
  const correctRevision = lastRevision + 1;
  const deferRevision = correctRevision + 1;
  const acceptRevision = deferRevision + 1;

  await page.getByTestId("action-CORRECT").click();
  await page.getByTestId("class-NECROSIS").click();
  await page.getByTestId("review-note").fill("Educational reviewer note");
  await expect(page.getByTestId("review-note")).toHaveValue("Educational reviewer note");
  await page.getByTestId("save-review").click();
  await expect(page.getByTestId("review-msg")).toContainText(/saved/i);
  await expect(page.getByTestId(`history-rev-${correctRevision}`)).toContainText("CORRECT → NECROSIS — Educational reviewer note");

  await page.getByTestId("action-DEFER").click();
  await page.getByTestId("defer-reason").selectOption({ index: 1 });
  await page.getByTestId("save-review").click();
  await expect(page.getByTestId(`history-rev-${deferRevision}`)).toContainText("DEFER");

  await page.getByTestId("action-ACCEPT").click();
  await page.getByTestId("save-review").click();
  await expect(page.getByTestId(`history-rev-${acceptRevision}`)).toContainText("ACCEPT");

  await page.reload();
  await login(page);
  await page.getByTestId(`card-${imageId}`).click();
  await expect(page.getByTestId(`history-rev-${correctRevision}`)).toContainText("CORRECT → NECROSIS — Educational reviewer note");
  await expect(page.getByTestId(`history-rev-${deferRevision}`)).toContainText("DEFER");
  await expect(page.getByTestId(`history-rev-${acceptRevision}`)).toContainText("ACCEPT");
  expect(errors).toEqual([]);
});

test("exports and recorded replay use stored project data", async ({ page }) => {
  await login(page);
  const [csv] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-csv").click(),
  ]);
  expect(csv.suggestedFilename()).toMatch(/reviews.*\.csv/i);
  const [json] = await Promise.all([
    page.waitForEvent("download"),
    page.getByTestId("export-json").click(),
  ]);
  expect(json.suggestedFilename()).toMatch(/reviews.*\.json/i);

  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Case report" })).toBeVisible();
  const checkbox = page.locator('input[type="checkbox"][aria-label^="Include "]').first();
  const imageLabel = await checkbox.getAttribute("aria-label");
  await checkbox.check();
  const findings = page.getByLabel("Findings", { exact: true });
  await findings.fill("Educational review of the displayed model evidence.");
  await findings.selectText();
  await page.getByRole("button", { name: "Bold", exact: true }).click();
  await expect(findings.locator("b, strong")).toHaveText("Educational review of the displayed model evidence.");
  await page.getByRole("button", { name: /save report · 1 item/i }).click();
  await expect(page.getByTestId("report-hash-status")).toContainText("verified");
  await expect(page.getByText(/saved reports/i)).toBeVisible();
  const [html] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /download html/i }).click(),
  ]);
  expect(html.suggestedFilename()).toMatch(/\.html$/i);
  const [markdown] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: /download markdown/i }).click(),
  ]);
  expect(markdown.suggestedFilename()).toMatch(/\.md$/i);
  expect(imageLabel).toContain("Include ");

  await page.getByRole("button", { name: "Images", exact: true }).click();
  await page.locator(".recorded-results > summary").click();
  await expect(page.getByRole("heading", { name: "Saved results" })).toBeVisible();
  const recorded = page.locator(".runlist .runitem").first();
  await expect(recorded).toBeVisible();
  await recorded.click();
  await expect(page.getByTestId("recorded-run-detail")).toContainText("does not run the model again");
  expect(errors).toEqual([]);
});

test("reader role and responsive themes stay usable", async ({ page }) => {
  await login(page, "student@demo");
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(page.getByRole("heading", { name: /writing reports is not available/i })).toBeVisible();
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await page.locator(".recorded-results > summary").click();
  await expect(page.getByRole("heading", { name: "Saved results" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Analyze this view", exact: true })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Scan slide", exact: true })).toBeDisabled();

  for (const [width, label] of [[1440, "desktop"], [768, "tablet"], [390, "mobile"]] as const) {
    await page.setViewportSize({ width, height: 844 });
    for (const section of ["Review set", "Images", "Reports", "Learn"]) {
      await expect(page.getByRole("button", { name: section, exact: true })).toBeVisible();
    }
    await page.evaluate(() => window.scrollTo(0, 0));
    const headerBounds = await page.locator(".app-header").boundingBox();
    const navBounds = await page.locator(".app-nav").boundingBox();
    expect(navBounds!.y).toBeGreaterThanOrEqual(headerBounds!.y);
    expect(navBounds!.y + navBounds!.height).toBeLessThanOrEqual(headerBounds!.y + headerBounds!.height + 1);
    await expect(page.locator(".app-header + .disclaimer")).toHaveCount(0);
    await page.getByRole("button", { name: "Learn", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Osteosarcoma", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Accredited and specialist sources" })).toBeVisible();
    for (const theme of ["light", "dark"] as const) {
      const current = await page.locator("html").getAttribute("data-theme");
      if (current !== theme) await page.getByTestId("theme-toggle").click();
      await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
      expect(overflow, `horizontal overflow at ${width}px in ${theme} theme`).toBe(false);
      if (width === 1440) await page.screenshot({ path: `${evidence}/educational-guide-desktop-${theme}-viewport.png` });
      await page.screenshot({ path: `${evidence}/educational-${label}-${theme}.png`, fullPage: true });
    }
  }
  await page.setViewportSize({ width: 320, height: 844 });
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), "horizontal overflow at 320px").toBe(false);
  const toggle = page.getByTestId("theme-toggle");
  const target = await toggle.boundingBox();
  expect(target?.height).toBeGreaterThanOrEqual(44);
  await toggle.focus();
  expect(await toggle.evaluate((el) => parseFloat(getComputedStyle(el).outlineWidth))).toBeGreaterThanOrEqual(3);
  await page.emulateMedia({ reducedMotion: "reduce" });
  expect(await page.locator(".app-nav button").first().evaluate((el) => parseFloat(getComputedStyle(el).transitionDuration))).toBeLessThan(0.001);
  expect(errors).toEqual([]);
});
