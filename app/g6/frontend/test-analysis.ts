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
    await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
    await page.click('button[title="Analysis"]');
    await page.waitForTimeout(2000);
    const analysisVisible = await page.isVisible('[data-testid="analysis-workspace"]');
    console.log("analysis workspace visible:", analysisVisible);
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
