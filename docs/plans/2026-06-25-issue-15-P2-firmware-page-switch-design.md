# Issue #15 P2 — Firmware Runtime Page Switching (Design)

**Date:** 2026-06-25
**Branch:** `15-pages`
**Phase:** P2 (firmware runtime). P1 (schema + migration) landed in `2f8146c` / `af80cfa`.

## Goal

Make the active page switchable at runtime, in RAM. When the active page
changes, the device re-renders everything that depends on it — buttons,
LEDs, screen labels, encoder, and expression pedals — so the controller
behaves as the newly-selected page defines.

This phase delivers the **mechanism** only. The triggers that call it
(press-timing inc/dec, MIDI-IN CC page-jump) are P3. For P2, the switch is
reachable via the serial REPL for testing.

## Locked decisions

| Decision | Choice | Rationale |
|---|---|---|
| State on return to a page | **Reset on entry** | Cheapest; one flat state set, no per-page RAM. Returning to a page rebuilds its buttons/encoder from config defaults. Door left open for a future global toggle + per-page override to "remember" page state. |
| How P2 invokes the switch | **REPL-callable only** | Clean P2 (mechanism) / P3 (triggers) split. No hot-loop change, no throwaway trigger code. |
| Per-page override resolution | **Channel only** | Wire 3-level `global_channel` resolution (button → page → device). Per-page `display` override deferred to P4 (avoids font-reload RAM churn with no editor to produce overrides yet). Display stays device-wide. |
| Program Change memory across switches | **Carry across** | Patch memory follows the rig, not the layout — matches how a player thinks. One-line seam left for a future `pc_carryover` config toggle (see below). |

## Player-visible behavior

On a page switch, instantly:

- Buttons become the new page's buttons (labels, colors, MIDI assignments).
- Screen updates to the new page's button labels.
- LEDs repaint for the new page.
- Encoder + expression pedals adopt the new page's settings.

Switching back to a previously-visited page presents it **fresh** —
toggles/latches reset to config defaults (reset-on-entry).

The active page lives **in RAM only**. Power-cycle returns to whatever
`active_page` is saved in the on-disk config. The device never rewrites the
config file (CircuitPython read-only FS / host write-conflict constraint).

Program Change / patch memory **carries across** page switches: if page 1
left the rig on patch 7, a page-2 increment button goes to 8.

## Mechanism

### The seam: split boot init into one-time vs per-page

Today all per-page state is assigned inline at module scope during boot
(`code.py` ~283–648), and encoder/expression config is baked into ~16
module **constants** (`ENC_*`, `CC_*`, `EXP*_CHANNEL`) read directly by the
hot-loop handlers. Nothing is re-runnable. P2 splits boot init:

- **One-time (boot only):** hardware objects (`switches`, `encoder`,
  `pixels`, `display`), fonts, the display `Group` + label/box **objects**,
  `pc_values[]`. Never change on a page switch.
- **Per-page (boot + every switch):** a new `switch_page(n)` function.

### `switch_page(n)` — order of operations

1. Clamp `n` to a valid page index (reuse `get_active_page` clamp logic);
   set the `active_page` global and `config["active_page"] = n` (RAM only).
2. Re-derive the `buttons` global; recompute the `ENC_*` / `EXP_*` / `CC_*`
   constants via `global` reassignment. Keeping them as plain globals (vs.
   dict lookups in the handler) keeps the hot loop cheap — a switch is rare,
   the loop is hot.
3. Rebuild `button_states[]` and `keytimes_states[]` from config defaults
   (reset-on-entry). Reset `pc_flash_timers[]`, `hid_flash_timers[]`,
   `encoder_value`, `encoder_slot`.
4. **Update** existing display labels' `.text` / `.color` in place — never
   recreate the objects (avoids RAM-fragmenting churn on RP2040).
5. `init_leds()` repaint.

Boot calls `switch_page(active_page)` **once** after the display/hardware
objects exist, replacing the old inline per-page block. This is the DRY win:
one code path renders a page, used at boot and on every switch.

`button_states[]` / `keytimes_states[]` array **sizes** are constant — all
pages share the device's fixed button count (enforced by the P1 validators),
so the switch rebuilds contents, never resizes.

`pc_values[]` (16-element per-MIDI-channel patch memory) is **not** reset on
switch — this is the "carry across" decision.

### Channel resolution (3-level)

Per-button channel wins; else the active page's `global_channel`; else the
device-level default. The effective page-level default is recomputed once in
`switch_page` and stored in a global used as the fallback wherever runtime
dispatch currently uses the top-level `global_channel`.

### Testability

- **Pure logic** (page clamp, channel resolution) lives in `core/` and is
  covered by pytest. `get_active_page` already exists; add a channel
  resolver if the logic doesn't fit cleanly inline.
- **`switch_page`** lives in `code.py`, wires hardware, and is tested
  **on-device via the serial REPL** (`>>> switch_page(1)`). Matches the
  existing core-tested / code.py-tested-on-device split.

## Out of scope (future)

- **`pc_carryover` config toggle.** Carry-across is the P2 behavior. A
  device-level bool (default `true` = carry; `false` = reset `pc_values` on
  switch) is a clean later add — `switch_page` has exactly one line where
  patch memory is (not) reset. Costs the #81 three-layer schema tax
  (Python/Rust/TS) + a P4 editor field, so deferred until requested.
- **Per-page state preservation** ("remember" toggles/latches/encoder per
  page) — global toggle + per-page override, future enhancement.
- **Per-page `display` override** — P4 (font-reload churn).
- **Switch triggers** (press-timing inc/dec, MIDI-IN CC jump) — P3.

## Notes for select / keytimes modes

- AGENTS.md (firmware) line ~256: select-mode page-restore must repaint LEDs
  from `button_states[i].state`, not config defaults — relevant only if/when
  per-page preservation lands. Under reset-on-entry, rebuilding from config
  defaults is correct (a re-entered page starts fresh).
- Keytimes cycle state (AGENTS.md ~223) resets on switch under reset-on-entry.
  Per-page `(page_id, button_idx)` keying is the future-preservation path.
