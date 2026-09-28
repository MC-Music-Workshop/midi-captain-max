# Listen CC for `mode: "keytimes"` buttons

**Status:** Design, not yet implemented.

## Problem

`cc_receive` ("Listen CC") lets a plain CC/toggle/select button send on one CC
and take its LED/state from a different one (`docs/user/inbound-midi.md`,
"Listen CC: send on one CC, listen on another"). It's explicitly unavailable
for `mode: "keytimes"` (`config.schema.json:450`), and keytimes buttons ignore
all inbound MIDI today unless their entries are `cc_inc`/`cc_dec`
(`docs/user/inbound-midi.md:84`).

A keytimes button with a `short[]` toggle (2 entries: off/on, CC 20 via `up`)
and a `long[]` mode cycle (3 entries: CC 120 values 0/50/100 via `down`,
`long_overlay: true`) has no way to reflect host-side changes at all — e.g. a
Gig Performer widget with its **Sync** behavior enabled has nothing to sync
*to* on this button.

Separately reported: enabling Sync on the mode widget produced a rapid MIDI
loop. Traced through `midi_rx.py`/`code.py`: every RX action (`state`,
`select`, `cc_step`) is state/LED-only — none of them call a MIDI-send
function, so the firmware cannot originate a TX loop from an RX message. The
loop has to be a Gig Performer-side MIDI routing/binding issue (widget input
and Sync output both bound to CC 120 with GP's own echo active), independent
of this feature. Not addressed here.

## Design

### Schema (`config.schema.json`)

Two new optional button-level fields, valid only when `mode: "keytimes"`:

- `short_cc_receive` (`MidiByte`): CC number the **short** cycle listens on.
- `long_cc_receive` (`MidiByte`): CC number the **long** cycle listens on.

Matched against the button's own `channel`, same as `cc_receive` today.
`short`/`long` are independent `PressCycle`s (`button.py`), so they need
independent listen numbers — a single button-level field can't cover both.

One new optional field on cycle entries (inside `short[]`/`long[]` objects):

- `rx_value` (`MidiByte`): the exact incoming value that selects this entry.

Exact match only, Select-style — no above-63 fallback, no "on/off"
convention, since a cycle can have more than two positions and there's no
natural split. Entries without `rx_value` are simply unreachable from inbound
MIDI (e.g. a transient flash-only entry).

```json
"short_cc_receive": 20,
"short": [
  { "up": [{ "type": "cc", "cc": 20, "value": 0 }], "rx_value": 0 },
  { "up": [{ "type": "cc", "cc": 20, "value": 127 }], "rx_value": 127 }
],
"long_cc_receive": 120,
"long_overlay": true,
"long": [
  { "down": [{ "type": "cc", "cc": 120, "value": 0 }], "color": "red", "rx_value": 0 },
  { "down": [{ "type": "cc", "cc": 120, "value": 50 }], "color": "green", "rx_value": 50 },
  { "down": [{ "type": "cc", "cc": 120, "value": 100 }], "color": "blue", "rx_value": 100 }
]
```

### Validation (`config.py`)

- `_validate_keytimes_button`: parse `short_cc_receive`/`long_cc_receive`
  (int 0-127, persist only if present — same pattern as `cc_receive`).
- `_validate_keytimes_entry`: parse `rx_value` (int 0-127) per entry.
- Warn at boot (style of the `cc_on == cc_off` warning, `config.py:570-574`)
  if two entries in the same cycle share an `rx_value` — ambiguous, first
  match wins.

### RX matching (`midi_rx.py`)

`find_cc_rx_action` currently returns a 2-tuple `(action, index)`. Extend to
a 3-tuple `(action, index, extra)`, `extra=None` for existing actions, to
carry the matched track + entry for the new case:

- Check `mode == "keytimes"` buttons for `short_cc_receive`/`long_cc_receive`
  matches (cc + channel) before the existing cc_step/state/select scan —
  same tier as `is_cc_step_button`.
- On a track match, scan that track's entries for an exact `rx_value` match.
  No match → no action (message simply doesn't land, same as today).
- Return `("keytimes", i, {"track": "short"|"long", "entry": idx})`.

All three existing call-site unpacks (`code.py:1158` and any other callers)
move from `action, i = ...` to `action, i, extra = ...`.

### Dispatch (`code.py`)

New branch in `_process_midi_msg` for `action == "keytimes"`:

- Set `state.short_cycle`/`long_cycle`'s index to the matched entry (needs a
  setter on `PressCycle`, `button.py:228` — it currently only advances).
- Apply that entry's `color`/`dim`/`label` to `state.short_color`/`dim`/`label`
  (or `long_*`) — reuse the entry-applying logic already in
  `dispatch_keytimes_events` rather than duplicating it.
- Repaint the LED through the same path a normal press-end event uses
  (`long_overlay` precedence unchanged).
- Do **not** dispatch the entry's `down`/`up` MIDI messages — state/LED-only,
  matching every other RX action in this firmware.
- `update_status(f"RX CC{cc}={val}")`.

### Local press behavior — unchanged

Per your call: physical presses keep repainting immediately, same as today.
RX independently corrects the index/color if the host disagrees (setting to
the same value it already has is a no-op, so agreement causes no flicker).
This differs from the plain-button `cc_receive` behavior (which suppresses
local repaint entirely) — deliberate, since here local response stays instant
and RX is a correction path rather than the sole authority.

### Docs

- `config.schema.json`: reword the `cc_receive` description's keytimes
  exclusion note to point at `short_cc_receive`/`long_cc_receive` instead of
  just saying "not available."
- `docs/user/inbound-midi.md:84` and the Quick Reference table: describe the
  new per-track listen behavior; keep the existing "keytimes reacts to
  CC+/CC-" note (unaffected, orthogonal mechanism).

### Tests

- `config.py`: `short_cc_receive`/`long_cc_receive`/`rx_value` validation,
  including the duplicate-`rx_value` warning.
- `midi_rx.py`: exact-match / no-fallback / no-match-not-configured cases for
  both tracks independently, plus the 3-tuple return shape.
- `code.py`/integration (mock-based): RX sets cycle index + LED without
  sending MIDI; `long_overlay` precedence holds after an RX-driven change.
