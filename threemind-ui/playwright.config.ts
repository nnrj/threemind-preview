import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  workers: 1,
  retries: 0,
  timeout: 90000,
  expect: { timeout: 15000 },
  outputDir: "../.work/browser-results",
  reporter: "list",
  use: {
    baseURL: process.env.THREEMIND_E2E_URL || "http://127.0.0.1:8877",
    channel: process.env.THREEMIND_BROWSER || "msedge",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
});
