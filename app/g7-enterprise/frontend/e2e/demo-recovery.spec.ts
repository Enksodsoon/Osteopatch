import { test, expect, type Page, type Route, type Request } from "@playwright/test";
const checks = new WeakMap<Page, { injected: WeakSet<Request>; errors: string[] }>();
test.beforeEach(async ({ page }) => {
  const state = { injected: new WeakSet<Request>(), errors: [] as string[] };
  checks.set(page, state);
  page.on("pageerror", error => state.errors.push(error.message));
  page.on("console", message => {
    if (message.type() === "error" && !message.text().startsWith("Failed to load resource:")) state.errors.push(message.text());
  });
  page.on("response", response => {
    if (response.status() >= 400 && !state.injected.has(response.request())) state.errors.push(`${response.status()} ${response.url()}`);
  });
});
test.afterEach(async ({ page }) => { expect(checks.get(page)!.errors).toEqual([]); });
async function injectFailure(page: Page, pattern: string, handler: (route: Route) => Promise<void>) {
  await page.route(pattern, route => {
    checks.get(page)!.injected.add(route.request());
    return handler(route);
  });
}
const evidence = `${process.env.TEMP ?? "/tmp"}/osteopatch-ui-evidence`;

async function login(page: Page, email = "reviewer@demo") {
  await page.goto("/");
  await page.getByLabel("email").fill(email);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
}

test("consolidated image screen opens and the gallery recovers from a failed request", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Slide library", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Review set", exact: true }).click();
  await expect(page.getByTestId("workbench")).toBeVisible();
  await injectFailure(page, "**/v1/images?*", route => route.fulfill({ status: 503, json: { detail: "QA unavailable" } }));
  await page.getByTestId("search-input").fill("Case");
  await expect(page.getByRole("alert")).toBeVisible();
  await page.unroute("**/v1/images?*");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
});

test("viewer wheel and drag produce no runtime errors, missing pixels can retry", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", e => errors.push(e.message));
  page.on("console", m => { if (m.type() === "error") errors.push(m.text()); });
  await login(page);
  await page.getByTestId("gallery").locator(".card").first().click();
  const image = page.getByTestId("image-viewer").locator("img");
  await expect(image).toBeVisible();
  await image.hover();
  await page.mouse.wheel(0, -80);
  await expect(page.locator(".viewer-scale")).toHaveText("115%");
  const bounds = (await page.locator(".viewer-stage").boundingBox())!;
  await page.mouse.move(bounds.x + 30, bounds.y + 30);
  await page.mouse.down();
  await page.mouse.move(bounds.x + 60, bounds.y + 50);
  await page.mouse.up();
  await expect(image).toHaveAttribute("style", /translate\(30px, 20px\)/);
  await page.getByRole("button", { name: /Reset view/i }).click();
  await expect(image).toHaveAttribute("style", /translate\(0px, 0px\) scale\(1\)/);
  expect(errors).toEqual([]);
  await injectFailure(page, "**/v1/images/*/full", route => route.fulfill({ status: 404, json: { detail: "QA missing pixels" } }));
  await page.getByTestId("next-patch").click();
  await expect(page.getByTestId("image-viewer").getByText("no pixels", { exact: true })).toBeVisible();
  await page.unroute("**/v1/images/*/full");
  await page.getByRole("button", { name: "Retry image" }).click();
  await expect(page.getByTestId("image-viewer").locator("img")).toBeVisible();
});

test("expired authentication returns to sign-in and recovers", async ({ page }) => {
  await login(page);
  await injectFailure(page, "**/v1/images?*", route => route.fulfill({ status: 401, json: { detail: "expired" } }));
  await page.getByTestId("search-input").fill("expired");
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
  await expect(page.getByRole("alert")).toContainText("expired");
  await page.unroute("**/v1/images?*");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
});

test("saved report can reopen after leaving, including for readers", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await page.getByLabel("Report name", { exact: true }).fill("Demo history recovery");
  await page.locator('input[aria-label^="Include Case-"]').first().check();
  await page.getByRole("button", { name: /Save report · 1/ }).click();
  await expect(page.getByTestId("report-hash-status")).toContainText("verified");
  await page.getByRole("button", { name: "Review set", exact: true }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await page.getByRole("button", { name: /Demo history recovery/ }).first().click();
  await expect(page.getByTestId("report-hash-status")).toContainText("verified");
  await page.getByRole("button", { name: "Edit as new revision", exact: true }).click();
  await expect(page.getByText(/New revision of rep-/)).toBeVisible();
  await expect(page.getByLabel("Report name", { exact: true })).toHaveValue("Demo history recovery");
  await page.getByLabel("Report name", { exact: true }).fill("Demo history recovery — revised");
  await page.getByRole("button", { name: /Save revision · 1/ }).click();
  await expect(page.getByText(/Revision of rep-/)).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("email").fill("student@demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await page.getByRole("button", { name: /Demo history recovery/ }).first().click();
  await expect(page.getByRole("button", { name: /Download Markdown/ })).toBeVisible();
});

test("all primary screens fit narrow layouts and exports remain accessible", async ({ page }) => {
  await login(page);
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ["light", "dark"]) {
      if (await page.locator("html").getAttribute("data-theme") !== theme) await page.getByTestId("theme-toggle").click();
      await expect(page.getByTestId("export-csv")).toBeVisible();
      for (const screen of ["Review set", "Images", "Reports", "Learn"]) {
        await page.getByRole("button", { name: screen, exact: true }).click();
        if (screen === "Reports") await expect(page.getByLabel("Search slide library", { exact: true })).toBeVisible();
        if (screen === "Images") await expect(page.getByRole("heading", { name: "Slide library", exact: true })).toBeVisible();
        expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `${screen} at ${width} ${theme}`).toBe(true);
        if (screen === "Review set") {
          await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
          await expect(page.getByTestId("gallery").locator(".card img")).toHaveCount(await page.getByTestId("gallery").locator(".card").count());
        }
        if (width === 1440 || width === 390) await page.screenshot({ path: `${evidence}/${screen.replaceAll(" ", "-")}-${width}-${theme}.png`, fullPage: true });
      }
    }
  }
});

test("all gallery filters, sorting, paging and returning to search context work", async ({ page }) => {
  await login(page);
  for (const filter of ["unreviewed", "reviewed", "deferred", "pred_NON_TUMOR", "pred_VIABLE_TUMOR", "pred_NECROSIS", "all"]) {
    await page.getByTestId("filter-select").selectOption(filter);
    await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
  }
  for (const sort of ["predicted_class", "image_id", "priority"]) {
    await page.getByTestId("sort-select").selectOption(sort);
    await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
  }
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.getByText(/Page 2/)).toBeVisible();
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.getByText(/Page 3/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Next page", exact: true })).toBeDisabled();
  await page.getByTestId("gallery").locator(".card").first().click();
  await page.getByRole("button", { name: /Back to review set/ }).click();
  await expect(page.getByText(/Page 3/)).toBeVisible();
  await page.getByTestId("search-input").fill("Case-3-A10");
  await expect(page.getByTestId("gallery").locator(".card").first()).toBeVisible();
  await page.getByTestId("gallery").locator(".card").first().click();
  await page.getByRole("button", { name: /Back to review set/ }).click();
  await expect(page.getByTestId("search-input")).toHaveValue("Case-3-A10");
  await page.getByTestId("search-input").fill("no-such-demo-patch");
  await expect(page.getByTestId("workbench-empty")).toBeVisible();
});

test("model evidence, patch pixels and attribution recover from API failures", async ({ page }) => {
  await login(page);
  await injectFailure(page, "**/v1/model-card", route => route.fulfill({ status: 503, json: { detail: "QA unavailable" } }));
  await page.getByRole("button", { name: "Learn", exact: true }).click();
  await page.getByText("Technical model notes", { exact: true }).click();
  await page.getByRole("button", { name: "Open model evidence", exact: true }).click();
  await expect(page.getByTestId("model-card-error")).toBeVisible();
  await page.unroute("**/v1/model-card");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(page.getByTestId("limitations-full")).toBeVisible();
  await page.locator(".lim-evidence summary").first().click();
  await expect(page.locator(".lim-evidence").first()).toHaveAttribute("open", "");
  await page.getByRole("button", { name: "Review set", exact: true }).click();
  await injectFailure(page, "**/v1/images/*/attribution/meta", route => route.fulfill({ status: 503, json: { detail: "QA unavailable" } }));
  await page.getByTestId("gallery").locator(".card").first().click();
  await expect(page.getByTestId("attribution-error")).toBeVisible();
  await page.unroute("**/v1/images/*/attribution/meta");
  await page.getByRole("button", { name: "Retry attribution" }).click();
  await expect(page.getByTestId("attribution-unavailable").or(page.getByTestId("attribution-pair"))).toBeVisible();
  await injectFailure(page, "**/v1/images/Case-*", route => route.fulfill({ status: 503, json: { detail: "QA unavailable" } }));
  await page.getByTestId("patch-review").locator(".pr-queue button").nth(1).click();
  await expect(page.getByRole("alert")).toBeVisible();
  await page.unroute("**/v1/images/Case-*");
  await page.getByRole("button", { name: "Try again", exact: true }).click();
  await expect(page.getByTestId("patch-review")).toBeVisible();
});

test("roles hide forbidden actions and allow returning to another demo persona", async ({ page }) => {
  await login(page, "auditor@demo");
  await page.getByTestId("gallery").locator(".card").first().click();
  await expect(page.getByTestId("save-review")).toHaveCount(0);
  await expect(page.getByText(/cannot save reviews/)).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.getByLabel("email").fill("mle@demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Slide library", exact: true })).toBeVisible();
  await page.locator(".recorded-results > summary").click();
  await expect(page.getByRole("heading", { name: "Saved results" })).toBeVisible();
  await page.getByRole("button", { name: "Review set", exact: true }).click();
  await expect(page.getByText(/review set is not available/)).toBeVisible();
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(page.getByText(/Writing reports is not available/)).toBeVisible();
  await page.getByText("Tools", { exact: true }).click();
  await page.getByRole("button", { name: "Model registry", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Serving model", exact: true })).toBeVisible();
});

test("report errors preserve drafts, unsigned run report persists and exports fail visibly", async ({ page }) => {
  await login(page);
  await injectFailure(page, "**/v1/reports?*", route => route.fulfill({ status: 503, json: { detail: "QA report history unavailable" } }));
  await page.getByRole("button", { name: "Reports", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await page.unroute("**/v1/reports?*");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await page.getByLabel("Report name", { exact: true }).fill("Unsigned recorded evidence summary");
  await page.getByLabel("Findings", { exact: true }).fill("Educational notes retained after failure.");
  await page.locator('input[aria-label^="Include run "]').first().check();
  await page.getByLabel("Sign this report", { exact: true }).uncheck();
  await injectFailure(page, "**/v1/reports", route => route.fulfill({ status: 503, json: { detail: "QA write unavailable" } }));
  await page.getByRole("button", { name: /Save report · 1/ }).click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await expect(page.getByLabel("Findings", { exact: true })).toHaveText("Educational notes retained after failure.");
  await page.unroute("**/v1/reports");
  await page.getByRole("button", { name: /Save report · 1/ }).click();
  await expect(page.getByText("Draft — unsigned", { exact: true })).toBeVisible();
  await expect(page.getByTestId("report-hash-status")).toContainText("verified");
  await injectFailure(page, "**/v1/reports/*/export.md", route => route.fulfill({ status: 503, body: "QA download unavailable" }));
  await page.getByRole("button", { name: "Download Markdown with images", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("503");
  await page.unroute("**/v1/reports/*/export.md");
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download Markdown with images", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.md$/);
});

test("recorded detail failure retries without inference, tile inspection works", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await page.locator(".recorded-results > summary").click();
  const recorded = page.locator(".runlist .runitem").first();
  await expect(recorded).toBeVisible();
  await injectFailure(page, "**/v1/live/runs/live-*", route => route.fulfill({ status: 503, json: { detail: "Recorded artifacts unavailable" } }));
  await recorded.click();
  await expect(page.getByRole("alert")).toContainText("unavailable");
  await page.unroute("**/v1/live/runs/live-*");
  await recorded.click();
  await expect(page.getByTestId("recorded-run-detail")).toBeVisible();
  await page.getByRole("gridcell").first().click();
  await expect(page.locator(".tile-inspect")).toContainText("uncalibrated");
});

test("concurrent reviews retain the draft and retry at the refreshed revision", async ({ page, context }) => {
  await login(page);
  const other = await context.newPage();
  await login(other);
  await page.getByTestId("gallery").locator(".card").first().click();
  const id = await page.locator(".pr-image-id").innerText();
  await other.getByTestId("gallery").locator(`[data-testid="card-${id}"]`).click();
  await page.getByTestId("review-note").fill("Draft survives a concurrent review");
  await other.getByTestId("save-review").click();
  await expect(other.getByTestId("review-msg")).toContainText(/saved/i);
  // This real 409 is expected; every other response remains checked.
  await page.route("**/v1/images/*/reviews", async route => {
    checks.get(page)!.injected.add(route.request());
    const response = await route.fetch();
    expect(response.status()).toBe(409);
    await route.fulfill({ response });
  });
  await page.getByTestId("save-review").click();
  await expect(page.getByTestId("review-msg")).toContainText(/another|changed|conflict/i);
  await expect(page.getByTestId("review-note")).toHaveValue("Draft survives a concurrent review");
  await page.unroute("**/v1/images/*/reviews");
  await page.getByTestId("save-review").click();
  await expect(page.getByTestId("review-msg")).toContainText(/saved/i);
  await other.close();
});

test("rapid navigation discards obsolete patch responses", async ({ page }) => {
  await login(page);
  await page.getByTestId("gallery").locator(".card").first().click();
  const buttons = page.locator(".pr-queue button");
  const second = (await buttons.nth(1).getAttribute("data-testid"))!.replace("queue-", "");
  const third = (await buttons.nth(2).getAttribute("data-testid"))!.replace("queue-", "");
  let release!: () => void;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let started!: () => void;
  const received = new Promise<void>(resolve => { started = resolve; });
  await page.route(`**/v1/images/${second}`, async route => {
    const response = await route.fetch(); started(); await gate; await route.fulfill({ response });
  });
  await page.getByTestId(`queue-${second}`).click();
  await received;
  // Navigation stays available through the primary workbench while loading.
  await page.getByRole("button", { name: "Review set", exact: true }).click();
  await page.getByTestId(`card-${third}`).click();
  await expect(page.locator(".pr-image-id")).toHaveText(third);
  release();
  await expect(page.getByTestId("image-viewer").locator("img")).toBeVisible();
  await expect(page.locator(".pr-image-id")).toHaveText(third);
  for (const width of [1440, 768, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const theme of ["light", "dark"]) {
      if (await page.locator("html").getAttribute("data-theme") !== theme) await page.getByTestId("theme-toggle").click();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("body *")].filter(e => e.getBoundingClientRect().right > innerWidth).map(e => ({ tag: e.tagName, cls: e.className, right: e.getBoundingClientRect().right })).slice(0, 12)))).toBe(true);
      if (width === 1440 || width === 390) await page.screenshot({ path: `${evidence}/Patch-${width}-${theme}.png`, fullPage: true });
    }
  }
});

test("keyboard navigation and reduced motion remain usable", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await login(page);
  await page.getByRole("button", { name: "Images", exact: true }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("heading", { name: "Slide library", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Review set", exact: true }).focus();
  await page.keyboard.press("Enter");
  const card = page.getByTestId("gallery").locator(".card").first();
  for (let i = 0; i < 40 && !(await card.evaluate(element => element === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  await expect(card).toBeFocused();
  expect(await card.evaluate(element => getComputedStyle(element).outlineStyle)).not.toBe("none");
  await page.keyboard.press("Enter");
  await expect(page.getByTestId("patch-review")).toBeVisible();
  await page.getByRole("button", { name: "Try a self-check" }).focus();
  await page.keyboard.press("Enter");
  await page.getByTestId("self-check-choice-NON_TUMOR").focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Reveal comparison" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.getByText(/not a measure of correctness/)).toBeVisible();
});
