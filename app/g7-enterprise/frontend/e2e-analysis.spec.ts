import { test, expect } from "@playwright/test";

test("analysis view renders without console errors", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(msg.text());
  });
  page.on("pageerror", (err) => errors.push(err.message));

  await page.goto("http://localhost:5174", { waitUntil: "networkidle" });
  await page.click('input[type="email"]');
  await page.fill('input[type="email"]', "demo@example.com");
  await page.fill('input[type="password"]', "demo");
  await page.click('button[type="submit"]');
  await page.waitForTimeout(2000);
  await page.click('button[title="Analysis"]');
  await page.waitForTimeout(2000);

  const workspace = page.locator('[data-testid="analysis-workspace"]');
  await expect(workspace).toBeVisible({ timeout: 10000 });

  if (errors.length) {
    console.log("console errors:", errors.join("\n"));
  }
  expect(errors).toHaveLength(0);
});
