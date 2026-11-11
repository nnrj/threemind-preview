import { defineConfig } from "@playwright/test";
const port = Number(process.env.THREEMIND_REPLAY_PORT || "8919");
export default defineConfig({
  testDir: "./replay-tests",
  workers: 1,
  retries: 0,
  timeout: 45000,
  outputDir: "../.work/language-replay-tests",
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    channel: process.env.THREEMIND_BROWSER || "msedge",
    viewport: { width: 1440, height: 1000 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `node node_modules/vite/bin/vite.js --host 127.0.0.1 --port ${port} --strictPort`,
    url: `http://127.0.0.1:${port}/e2e/fixtures/language-replay.html`,
    reuseExistingServer: false,
    timeout: 30000,
  },
});
