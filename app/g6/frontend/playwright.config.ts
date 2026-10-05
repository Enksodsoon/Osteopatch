import { defineConfig, devices } from "@playwright/test";

/**
 * Whole-app BROWSER end-to-end suite.
 *
 * This is deliberately separate from `vitest` (jsdom component tests). Vitest
 * proves components render; this proves a real reviewer can actually walk the
 * product in a real browser and that what they see matches what the API says.
 *
 * Both servers are booted by `scripts/e2e_ui.py`, which picks free ports and
 * injects them here. There is deliberately NO `webServer` block: a stale
 * process squatting on the configured port is a real failure mode on this
 * machine, and a runner that silently attaches to someone else's server would
 * report a green run against unknown code. The harness fails closed instead.
 *
 * Browser selection is injected too (E2E_BROWSER) and defaults to the bundled
 * Chromium, so CI is unchanged. `edge` drives the SYSTEM Microsoft Edge via
 * Playwright's `msedge` channel: no download, and it exercises the browser the
 * reviewers are most likely to actually use.
 */
const baseURL = process.env.E2E_BASE_URL;
const backendURL = process.env.E2E_BACKEND_URL;

if (!baseURL || !backendURL) {
  throw new Error(
    "E2E_BASE_URL and E2E_BACKEND_URL are required. " +
      "Run via: python scripts/e2e_ui.py",
  );
}

/** An unknown browser name must fail here, not silently fall back to Chromium. */
const BROWSERS = {
  chromium: () => ({ ...devices["Desktop Chrome"] }),
  // `msedge` is Playwright's channel name for the preinstalled Edge.
  edge: () => ({ ...devices["Desktop Chrome"], channel: "msedge" as const }),
} as const;

type BrowserName = keyof typeof BROWSERS;

const requested = (process.env.E2E_BROWSER ?? "chromium").trim().toLowerCase();
if (!(requested in BROWSERS)) {
  throw new Error(
    `Unknown E2E_BROWSER ${JSON.stringify(requested)}. ` +
      `Supported: ${Object.keys(BROWSERS).join(", ")}.`,
  );
}
const browser = requested as BrowserName;

export default defineConfig({
  testDir: "./e2e",
  // Reviews mutate a throwaway copy of the DB, but tests still share one stack.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  reporter: process.env.CI ? [["list"], ["json", { outputFile: "e2e-results.json" }]] : [["list"]],
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "off",
    actionTimeout: 10_000,
  },
  projects: [{ name: browser, use: BROWSERS[browser]() }],
});