import { defineConfig } from "@playwright/test";
import { fileURLToPath } from "node:url";
export default defineConfig({
  testDir: "./e2e",
  testMatch: "research.spec.ts",
  use: { baseURL: "http://127.0.0.1:5173", channel: "chrome", headless: true },
  webServer: { command: "npm run dev -- --host 127.0.0.1", url: "http://127.0.0.1:5173", reuseExistingServer: true },
  workers: 1,
  reporter: [["list"], ["junit", { outputFile: fileURLToPath(new URL("../artifacts/upgrade-browser.xml", import.meta.url)) }]],
});
