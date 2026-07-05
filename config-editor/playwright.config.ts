import { defineConfig } from '@playwright/test';

// E2e tests drive the SvelteKit frontend in Playwright's WebKit build — the
// same engine family as the WKWebView the Tauri app embeds on macOS, so
// focus/blur semantics (which several bugs hinge on) match production. The
// Rust backend is mocked at the window.__TAURI_INTERNALS__ boundary (see
// e2e/helpers.ts), so these tests cover the frontend only.
export default defineConfig({
  testDir: './e2e',
  use: {
    baseURL: 'http://localhost:1420',
  },
  projects: [{ name: 'webkit', use: { browserName: 'webkit' } }],
  webServer: {
    command: 'npm run dev',
    port: 1420,
    // `npm run tauri dev` already runs vite on 1420; reuse it during local dev.
    reuseExistingServer: true,
  },
});
