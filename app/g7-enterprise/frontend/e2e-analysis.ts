import { chromium } from "playwright";

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));
  try {
    await page.goto("http://localhost:5174", { waitUntil: "networkidle" });
    await page.click('input[type="email"]');
    await page.fill('input[type="email"]', "demo@example.com");
    await page.fill('input[type="password"]', "demo");
    await page.click('button[type="submit"]');
    await page.waitForTimeout(3000);
    await page.click('button[title="Analysis"]');
    await page.waitForTimeout(3000);
    const workspace = page.locator('[data-testid="analysis-workspace"]');
    const visible = await workspace.isVisible();
    console.log("analysis workspace visible:", visible);
    if (errors.length) {
      console.log("console errors:", errors.join("\n"));
    } else {
      console.log("no console errors");
    }
  } catch (e) {
    console.error(e);
  } finally {
    await browser.close();
  }
})();
