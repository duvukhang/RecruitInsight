import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./e2e",
  testMatch: ['app.spec.ts', 'upgrade.live.spec.ts'],
  use: {
    baseURL: "http://localhost:8080",
    channel: "chrome",
    headless: true,
    screenshot: "only-on-failure",
  },
  workers: 1,
  timeout: 60000,
  reporter: [["list"], ["html", { open: "never" }]],
});
