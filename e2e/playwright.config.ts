import { defineConfig, devices } from "@playwright/test";

// E2E tests for the home page (site/index.html). They drive the real firmware
// logic running in the MicroPython wasm engine, so Chromium is used — the
// broadest wasm + pointer-events support, and the primary target for the
// eventual Web MIDI features. A tiny correct-MIME static server (serve.mjs)
// hosts site/ so the .mjs/.wasm loads succeed.
const PORT = 4173;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "on-first-retry",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: `node serve.mjs ${PORT}`,
    port: PORT,
    reuseExistingServer: !process.env.CI,
  },
});
