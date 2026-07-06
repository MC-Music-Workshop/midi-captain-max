# Home Page: Run Real Firmware Button Logic in the Browser — Plan

**Date:** 2026-07-05
**Status:** Implemented (2026-07-05) — MicroPython wasm vendored in `site/vendor/micropython/`, firmware snapshots in `site/firmware/` (synced by `tools/sync-site-firmware.sh` on every Pages deploy), hero + playground run `core/button.py`/`colors.py` with a schema-valid keytimes config, live MIDI readout + config viewer added; JS engine retained as fallback (old browsers, `file://`).
**Follow-up:** the device's TFT screen was added the same way — see `docs/plans/2026-07-05-display-model-extraction.md` (pure `core/display_model.py` driving firmware, the browser canvas, and pytest).
**Context:** The home page's footswitch demos (`site/index.html`) currently re-implement button behavior in JS. Goal: run the *literal* firmware code so the demo is the same functionality by construction, not by imitation.

## Why this is feasible

`firmware/dev/core/button.py` is pure, dependency-free Python (built that way for pytest):

- `PressTracker.update(pressed, now)`: classifies polls into `short_down` / `short_up` / `long_down` / `long_up` events. Caller supplies `now` — no clock dependency.
- `KeytimesButtonState`: aggregates the tracker, two `PressCycle`s, and inherited render state (`last_fired`, per-class color/dim/label).
- `dispatch_keytimes_events(events, state, btn_config, message_callback)`: documented as "pure logic — no hardware, no time, no I/O". Takes a validated config dict, fires messages through a callback, updates render state.
- `ButtonState`: toggle/momentary state machine for non-keytimes buttons.

That is exactly a browser-embeddable surface.

## Design

1. **Runtime:** MicroPython compiled to WebAssembly (~350KB), **vendored into `site/`** (self-contained page, no CDN). Lazy-loaded after first paint so landing performance is untouched. Pyodide (full CPython, 6-10MB) rejected as overkill.
2. **Zero drift:** the deploy workflow copies `firmware/dev/core/button.py` (and `colors.py` if LED composition is included) from the firmware tree into `site/` — same pattern as the Kanban `board.json` refresh. The page always runs whatever logic is on `main`.
3. **JS becomes a thin shim:**
   - Pointer/keyboard events set a `pressed` flag; a `requestAnimationFrame` (or interval) poll loop calls `PressTracker.update(pressed, performance.now() / 1000)`.
   - Events go through `dispatch_keytimes_events` with a **real `mode: "keytimes"` config JSON snippet** — the exact config a user could flash.
   - LED ring + screen label render from `state.last_fired` and the state's short/long color/label fields — the same fields the device renders from.
   - Plain toggle/tap buttons route through `ButtonState` for consistency.
4. **Fallback:** if wasm fails to load (old browser, blocked), keep the current JS engine — it stays in the page as the fallback path.
5. **Bonus unlocked — live MIDI readout:** `message_callback` receives the real dispatched message dicts, so the demo can display "→ CC 20 val 127" per stomp, with a "view the config driving this" link. Strongest possible "this is literally the firmware" proof.

## Steps

1. Vendor MicroPython wasm build into `site/vendor/` (pin a release; note version in a comment).
2. Add deploy-time copy of `core/button.py` → `site/` (extend `tools/fetch-board.sh` or a sibling script); commit an initial snapshot so `file://` and cold deploys work.
3. Write the shim: load wasm lazily, import `button.py`, wire the poll loop + `message_callback`, render from state.
4. Swap hero VERB/SHIM button and the keytimes playground onto the engine; route toggle/tap buttons through `ButtonState`.
5. Add the MIDI message readout to the playground (and optionally the hero).
6. Verify: headless screenshots + manual stomp test from `file://` and served; confirm fallback path by blocking the wasm.

## Trade-offs / open questions

- ~350KB vendored wasm on a currently zero-dependency page (mitigated by lazy load + fallback).
- MicroPython vs CircuitPython differences don't matter for these pure modules (no `board`/`digitalio` imports).
- Keep or drop the JS engine long-term? Keeping it means two implementations again — but as an explicit *fallback*, not the primary.
