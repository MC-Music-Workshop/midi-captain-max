# Issue #11 — CC Increment/Decrement (`cc_inc` / `cc_dec`)

**Status:** Shipped on branch `11-cc-step`.
**Issue:** https://github.com/MC-Music-Workshop/midi-captain-max/issues/11

## What it does

A `cc_inc` / `cc_dec` button steps a **shared CC value** up or down instead of
sending a fixed `cc_on`/`cc_off`. The value is keyed by `(channel, cc)` and
shared by every cc-step button on every page. Two value modes:

| Mode | Chosen by | Per press | LED | Status line |
|------|-----------|-----------|-----|-------------|
| STEP | `cc_slots` absent | `value ± cc_step` | flashes (`flash_ms`), rest per `off_mode` | `TX CC7=64` |
| SLOT | `cc_slots` 2–16 | move one slot, send the slot's middle value | stays lit at `cc_slot_colors[i]` | slot name or `TX AMP 2/4` |

Boundary rule (both modes): `cc_wrap` (default) lands **on** the opposite bound;
off clamps at the bound and sends it.

## Config shape

```json
{ "label": "AMP", "type": "cc_inc", "cc": 30, "cc_slots": 4,
  "cc_slot_colors": ["red", "green", "blue", "yellow"],
  "cc_slot_names": ["MARSH", "FENDER", "VOX", "MESA"], "color": "white" }

{ "label": "VOL UP", "type": "cc_inc", "cc": 7, "cc_step": 5,
  "cc_min": 0, "cc_max": 127, "cc_wrap": false, "cc_initial": 64, "color": "green" }
```

Keytimes: `{ "type": "cc_inc" }` / `{ "type": "cc_dec" }` entries are
direction-only; the cc-step fields above sit on the button and are shared by the
short and long cycles (inc on tap, dec on hold).

## Decisions that differ from the issue text

- **`cc_inc`/`cc_dec` types, not a single `CC_STEP` type with a direction flag** —
  mirrors the existing `pc_inc`/`pc_dec` pair, so dispatch, editor labels (`CC+`/`CC-`)
  and keytimes entries follow a pattern the codebase already has.
- **No `CC_SLOT_TYPE` field.** An unnamed slot displays `<button label> n/N`
  (`AMP 2/4`), so the label already plays that role. One field fewer, same UX.
- **Slot tables are arrays** (`cc_slot_colors`, `cc_slot_names`), not
  `{"SLOT_1": …}` objects. Positional, validated per index; shorter arrays fall
  back to the button color / `label n/N`.
- **`mode` is coerced to `flash`** for cc_inc/cc_dec (toggle/momentary/select
  don't apply); the editor offers only "Single press" and keytimes.
- **Keytimes STEP mode does not flash.** The keytimes entry color/dim/label rules
  own the LED as for any other keytimes entry. SLOT mode overrides them: the slot
  color and name own the LED and label for every press length (as the issue asks).
- **RX only reacts on change.** An incoming value in the same slot (SLOT) or equal
  to the current value (STEP) updates nothing — not even the status line.
- **Incoming values are clamped** into `cc_min..cc_max` before being stored.
  In STEP mode the value is otherwise taken as-is: the step is a stride from wherever
  the value sits, not a grid. After the host sends 1 with `cc_step: 2`, presses go 3, 5, 7.
  Verified on hardware and kept, because the pedal then shows and re-sends exactly what
  the host had. **Possible future option:** snap incoming STEP values to multiples of
  `cc_step` from `cc_min` (SLOT mode already snaps to slot midpoints). Would need a
  per-button opt-in, since it makes the pedal re-send a value the host never sent.
- **All buttons on the key react** to a change, whether it came from a local press
  or from RX: STEP buttons all flash, SLOT buttons all recolor. One rule, no
  "pressed vs sibling" special case.
- **The 6-char label cap still applies** to slot names. The status line carries the
  full `label n/N` text; the segment display (DUO2/ONE1) shows the slot number.

## Where things live

- `firmware/dev/core/cc_step.py` — pure math (step/wrap/clamp, slot index/value,
  color/name lookup). `tests/test_cc_step.py`.
- `firmware/dev/core/config.py::_validate_cc_step_fields` — one sanitizer shared by
  the plain type path and `_validate_keytimes_button`.
- `firmware/dev/core/midi_rx.py` — `("cc_step", i)` action.
- `firmware/dev/code.py` — `cc_values`, `send_cc_step`, `_refresh_cc_step_buttons`,
  `_show_cc_step`, SLOT hooks in `set_button_state` / `_render_keytimes_led`,
  `update_status(text, number=None)`.
- `config-editor/src/lib/components/CcStepFields.svelte` — the editor block, mounted
  by `ButtonRow` for both the plain type and the keytimes "Shared CC settings" panel.
- Schema: `MessageType` enum, `KeytimesMessage` variant, eight `ButtonConfig` fields.
