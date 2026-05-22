# Config Editor UI Automated Testing — Exploration

Status: exploration only, no implementation. Documents the option space for adding
automated UI tests to the Tauri/SvelteKit config editor.

## Two paths

### Path 2 — Browser + mocked Tauri (recommended first step)

- Install: `@playwright/test`
- Boot `vite dev` (port 5173); Playwright drives Chromium / WebKit / Firefox
- Mock `@tauri-apps/api` `invoke` via Vite alias or `window.__TAURI__` stub
- **Covers**: Svelte components, CodeMirror editor, form validation, schema-driven UI, routing
- **Misses**: file dialogs, NVM writes, firmware bundle, anything Rust-side
- Fast (~seconds per test). Runs in CI on Linux runners.

### Path 1 — Real Tauri via `tauri-driver`

- Stack: `tauri-driver` (Rust binary) + `webdriverio` (Playwright's Tauri story is weak; community uses WDI)
- macOS gotcha: needs `WebKitWebDriver`; flaky on Apple Silicon
- Linux gotcha: needs `webkit2gtk-driver`
- **Covers**: full IPC, real dialogs, real file I/O, real binary
- Slow (~10s+ per test), needs prod-ish build, fragile in CI

## Hybrid options worth knowing

- `@playwright/experimental-ct-svelte` — component-test mode, isolates components, skips app shell
- Vitest Browser Mode — Vite-native, lighter runner than Playwright, good for component logic

## Coverage map for this app

| Surface | Best path |
|---|---|
| Schema editor / form widgets | Path 2 (cheap, high value) |
| Live JSON CodeMirror sync | Path 2 |
| Open/Save dialog flow | Path 1 (only place that exercises real `tauri-plugin-dialog`) |
| `bundle-firmware-for-dev` integration | Path 1 |
| Device write/read (USB serial) | Neither — needs hardware mock |

## Effort estimate

- Path 2 scaffold + 5 smoke tests: ~half day
- Path 1 first green test on macOS: ~full day, mostly fighting drivers
- Maintenance: Path 2 low; Path 1 high (driver versions drift with OS updates)

## Recommendation when ready to execute

1. Path 2 first — broad cheap coverage of Svelte UI + form/editor behavior.
2. Add Path 1 only for the 2-3 flows that genuinely require real Tauri (dialogs, file I/O, firmware bundle).
3. Skip device-IO automation; keep that manual or build a serial mock.

## Open questions for future implementation pass

- Which CI runner OS for Path 1? (macOS-latest needed if WebKit fidelity matters; Linux cheaper)
- Mock strategy for `@tauri-apps/api` — Vite alias vs runtime `window.__TAURI__` stub
- Component-test (`ct-svelte`) vs full-app Playwright for widget-level tests
- Snapshot/visual regression layer? (Playwright has built-in; adds flake)
