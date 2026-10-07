import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: "list",
  use: {
    ...devices["Desktop Chrome"],
    baseURL: process.env.OSTEOPATCH_DEMO_URL ?? "http://127.0.0.1:8140",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
