# Keytimes: Multi-State Buttons and Long Presses

Keytimes turns one footswitch into several. Set a button's `mode` to `"keytimes"` and each press advances it through a cycle of states — its own messages, its own LED color, its own screen label. Short taps and long holds get **separate** cycles, so a single switch can tap through three reverb levels *and* hold for a tuner.

This is the MIDI Captain MAX equivalent of the OEM SuperMode behavior, with per-state control over everything the button does.

## How a press becomes events

Every physical press produces one or two timing events, split by the long-press threshold (500 ms by default):

| Event | When it fires |
|---|---|
| `short_down` | immediately, on every press |
| `short_up` | on release, if the release came **before** the threshold |
| `long_down` | the moment the threshold elapses, while still held |
| `long_up` | on release, if the release came **after** the threshold |

A quick tap therefore fires `short_down` then `short_up`. A hold fires `short_down`, then `long_down` at the threshold, then `long_up` on release — note that `short_down` fires on a hold too, which matters (see [Taps vs. holds](#taps-vs-holds-the-short_down-trap)).

The short events are served by the `short[]` cycle, the long events by `long[]`. The two have independent counters.

## Anatomy of a keytimes button

```jsonc
{
  "label": "VERB",
  "color": "blue",
  "mode": "keytimes",
  "long_press_threshold_ms": 600,   // optional per-button override
  "short": [
    { "down": [{ "type": "cc", "cc": 20, "value": 64 }],  "color": "blue",  "label": "LO" },
    { "down": [{ "type": "cc", "cc": 20, "value": 96 }],  "color": "cyan",  "label": "MID" },
    { "down": [{ "type": "cc", "cc": 20, "value": 127 }], "color": "white", "label": "MAX" }
  ],
  "long": [
    { "down": [{ "type": "cc", "cc": 21, "value": 127 }], "color": "red",   "label": "TUNER" },
    { "down": [{ "type": "cc", "cc": 21, "value": 0 }],   "color": "blue",  "label": "VERB" }
  ]
}
```

Tapping sends CC20 = 64 → 96 → 127 → back to 64, with the LED and screen label following along. Holding is a separate two-state cycle that toggles a tuner, untouched by how many times you've tapped.

Each entry in `short[]` / `long[]` takes:

| Field | What it does |
|---|---|
| `down` | messages fired on that cycle's *down* event (`short_down` / `long_down`) |
| `up` | messages fired on that cycle's *up* event (`short_up` / `long_up`) |
| `color` | LED color for this position. Omit to inherit the button's `color`; `"off"` forces the LED dark |
| `dim` | render the resolved color at 15% brightness |
| `label` | screen text for this position (max 6 characters; letters, digits, spaces, hyphens and `_`). Omit to inherit the button's `label` |

`down` and `up` are arrays, so an entry can be silent on one event and active on the other.

## When the cycle advances

Cycles advance at **press-end** — on `short_up` / `long_up` — and only for the timing class that actually did something during that press.

"Did something" means **the slot had at least one message in it**. An empty slot is a complete no-op: no MIDI, no LED or label change, and no cycle advance. This is deliberate — it's what lets you build a button that only responds to holds, without taps quietly walking the short cycle forward.

### Taps vs. holds: the `short_down` trap

Because `short_down` fires on *every* press — including the start of a hold — a short entry that puts its messages in `down` will also fire (and advance) when you hold the button.

If you want taps and holds to stay fully independent, put the short cycle's messages in `up` instead of `down`:

```jsonc
"short": [
  { "up": [{ "type": "cc", "cc": 20, "value": 64 }], "color": "blue" }
]
```

`short_up` only fires on a release *before* the threshold, so a hold never touches the short cycle. The tradeoff: the message fires on release rather than on press. Use `down` when you want instant response and don't mind holds advancing the short cycle too.

## LED and label rules

By default the LED shows **whichever timing class fired most recently** — tap and the LED shows the short entry's color, hold and it shows the long entry's, tap again and it's back to short. The screen label follows the same rule.

Within that, colors resolve like this:

1. Short entry's color is `"off"` → LED dark. Short `"off"` is a kill switch and wins over everything.
2. Long entry has a color → that color.
3. Short entry has a color → that color.
4. Nothing set → the button-level `color`.
5. No button color either → dark.

A `dim: true` on the winning layer renders it at reduced brightness. `off_color` is ignored on keytimes buttons — the cycle entries own the LED.

### `long_overlay`: make the hold color stick

Set `"long_overlay": true` on the button when the long cycle represents a **mode** that should stay visible while you keep tapping — a shimmer-on color riding over a reverb level cycle, say. The long color (and its label) persists instead of flipping back on the next tap, while short presses still send their messages normally. A short `"off"` entry still kills the LED.

Clearing the long layer (a long entry with no color) drops back to the normal last-press-wins behavior.

## What a cycle entry can send

Entries accept the same message types as a regular button:

| Type | Fields |
|---|---|
| `cc` | `cc`, `value`, optional `channel` |
| `note` | `note`, `velocity`, optional `channel` |
| `pc` | `program`, optional `channel` |
| `pc_inc` / `pc_dec` | optional `step`, `channel` |
| `cc_inc` / `cc_dec` | none — see below |
| `page_inc` / `page_dec` | optional `page_step` |
| `page_jump` | `page` |
| `hid` | `action`, `key`, optional `modifier`, `delay_ms` |

`cc_inc` / `cc_dec` entries carry no fields of their own: the CC number, channel, step size, min/max, wrap behavior, and slot color/name tables are configured **once on the button**, and every entry just picks a direction. That's what lets one keytimes button tap-up and hold-down through a shared CC value.

`page_inc` / `page_dec` / `page_jump` in a `long[]` entry is the usual way to put page switching on a hold while the taps do something musical.

## Threshold tuning

`long_press_threshold_ms` sets the tap/hold boundary in milliseconds (50–5000):

- Top-level in the config: the global default, 500 ms.
- On a button: overrides the global for that button only.

Raise it if you're accidentally triggering holds mid-song; lower it if holds feel sluggish. Only keytimes buttons use it.

## Pages and keytimes

Switching pages **resets every keytimes cycle on the incoming page back to its first entry** — cycle positions are not preserved across page switches. Shared `cc_inc`/`cc_dec` values and PC patch memory *are* preserved.

So after a page switch, a keytimes button is back at entry 1 and shows the button-level color and label until its first press.

## Editing in the Config Editor

Set a button's **Mode** to `keytimes` and the **Keytimes** editor appears with a **Short Press Cycle** and a **Long Press Cycle** section. Per entry you get a color dropdown (with `(inherit)` and an `⌀` dark option), a dim checkbox, a label field, and the `down` / `up` message slots. Empty slots are flagged with a hint, since an empty slot means that event does nothing at all.

The per-button threshold field and the `long_overlay` checkbox sit above the two cycles.

## Worked examples

**Three-level reverb, tap only** — the config at the top of this page, minus the `long` array.

**Tap to toggle, hold for tuner:**

```jsonc
{
  "label": "DLY",
  "color": "green",
  "mode": "keytimes",
  "short": [
    { "up": [{ "type": "cc", "cc": 22, "value": 127 }], "color": "green" },
    { "up": [{ "type": "cc", "cc": 22, "value": 0 }],   "color": "off" }
  ],
  "long": [
    { "down": [{ "type": "cc", "cc": 31, "value": 127 }], "color": "red", "label": "TUNE" },
    { "down": [{ "type": "cc", "cc": 31, "value": 0 }],   "label": "DLY" }
  ]
}
```

Taps toggle the delay (LED green / dark, using `up` so holds don't disturb the toggle); holds toggle the tuner in red.

**Hold to change page:**

```jsonc
{
  "label": "SOLO",
  "color": "yellow",
  "mode": "keytimes",
  "short": [
    { "down": [{ "type": "cc", "cc": 25, "value": 127 }] }
  ],
  "long": [
    { "down": [{ "type": "page_inc" }], "color": "white", "label": "PAGE" }
  ]
}
```

## Deprecated fields

The old flat `keytimes: <count>` and `states: [...]` fields are **forbidden** on `mode: "keytimes"` buttons — use `short[]` / `long[]`. On other modes they still load with a deprecation warning at boot and will be removed in v3.0.

## Full examples in the repo

- [`config-example-keytimes.json`](https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/firmware/dev/config-example-keytimes.json)
- [`config-example-keytimes-mode.json`](https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/firmware/dev/config-example-keytimes-mode.json)
- [`config-example-mini6-keytimes.json`](https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/firmware/dev/config-example-mini6-keytimes.json)
