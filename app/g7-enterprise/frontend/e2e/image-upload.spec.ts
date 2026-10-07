import { test, expect } from "@playwright/test";
import { resolve } from "node:path";

test("an imported pathology image gets a thumbnail and opens in the viewer", async ({ page }) => {
  const source = resolve(process.cwd(), "../../../aidlc-docs/inception/image-qc/contact-sheets/by-class__VIABLE_TUMOR.png");
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => { if (message.type() === "error") errors.push(message.text()); });
  page.on("response", response => { if (response.status() >= 400) errors.push(`${response.status()} ${response.url()}`); });
  await page.goto("/");
  await page.getByLabel("email").fill("reviewer@demo");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.getByRole("button", { name: "Images", exact: true }).click();
  await page.getByLabel("Upload WSI or image").setInputFiles(source);

  const viewer = page.getByTestId("slide-canvas");
  await expect(viewer).toBeVisible({ timeout: 30_000 });
  await expect(viewer.locator("canvas").first()).toBeAttached();
  const card = page.getByRole("button", { name: "Open by-class__VIABLE_TUMOR.png" }).first();
  await expect(card).toBeVisible();
  const thumbnail = card.getByTestId(/^slide-thumbnail-/);
  await expect.poll(() => thumbnail.evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  await card.click();
  await expect(viewer).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download original", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/by-class__VIABLE_TUMOR\.png$/);

  await page.getByRole("button", { name: "Reports", exact: true }).click();
  const picker = page.locator(".report-item-picker");
  const uploadedGroup = picker.locator(".report-item-group").nth(2);
  await expect(uploadedGroup).toContainText("Not yet analyzed · uploaded slides");
  const newestSlide = uploadedGroup.locator("li").first();
  await expect(newestSlide).toContainText("by-class__VIABLE_TUMOR.png");
  const slideThumbnail = newestSlide.locator("img.report-item-thumb");
  await expect.poll(() => slideThumbnail.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const runThumbnail = picker.locator(".report-item-group").nth(1).locator("img.report-item-thumb").first();
  await expect.poll(() => runThumbnail.evaluate(image => (image as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  expect(errors).toEqual([]);
});
