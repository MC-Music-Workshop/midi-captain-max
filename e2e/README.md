# Home page E2E tests (Playwright)

End-to-end tests for `site/index.html`. They drive the page in a real browser
(Chromium) and exercise the **actual firmware logic** running in the MicroPython
wasm engine — the same `core/*.py` the device runs — so a regression in that
logic fails here, through the real UI. This is the baseline to grow.

## Run

```bash
cd e2e
npm install                      # once
npx playwright install chromium  # once
npm test                         # run the suite
npx playwright test --ui         # interactive/debug
```

The config's `webServer` starts `serve.mjs` (a tiny static server with correct
`.mjs`/`.wasm` MIME types — a plain `python -m http.server` breaks the module +
wasm loads) on port 4173 and serves `../site`.

## Layout

- `serve.mjs` — static file server with correct MIME types.
- `playwright.config.ts` — Chromium project + the static `webServer`.
- `tests/helpers.ts` — `tap`/`hold` a footswitch, `turnEncoder`/`pushEncoder`,
  `waitForFirmwareEngine` (waits for the wasm boot via the `#kt-live` badge).
- `tests/site.spec.ts` — current coverage: structure, wasm boot, keytimes
  (tap/hold/shimmer-persist), real MIDI dispatch to the log, plain toggle,
  encoder turn + push, and the JS fallback path (wasm blocked).

## Extending

Add specs under `tests/`. Wait for `waitForFirmwareEngine(page)` before
asserting on wasm-driven behavior. Prefer asserting on user-visible state
(labels, `#…-midi-lines` log text, `aria-valuenow`, `.lit` class) over
internals. CI runs this on every push (`.github/workflows/ci.yml`, job
`test-site-e2e`).
