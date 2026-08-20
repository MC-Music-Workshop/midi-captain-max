# Page Control via MIDI-IN

Page Control lets an inbound MIDI CC switch the pedal's active page — jump straight to a page, or step forward/back — driven entirely by the host. It's a device-level setting, not tied to any button.

## Why this matters

Page switching already works locally — assign a button the `page_inc`, `page_dec`, or `page_jump` type and it switches pages on press (or, if you wire it to a hold event in a keytimes button, on a long-press instead). Page Control adds the other direction: your DAW, amp modeler, or a MIDI-capable pedal upstream can flip pages on its own. Jump to a "Solo" page when a track arms, step through pages in time with a setlist, or sync page state to a snapshot change — no foot required.

## How it works

Page Control is a single device-level block (`page_control` in the config) with up to three independent slots:

| Slot | Trigger | Effect |
|---|---|---|
| **jump** | any value on its CC | switches to that value as an absolute page index (0-based), clamped to range |
| **inc** | CC value matches a gate (default 127) | advances the active page by `page_step`, wrapping past the last page to page 0 |
| **dec** | CC value matches a gate (default 127) | retreats the active page by `page_step`, wrapping past page 0 to the last page |

All three slots share one optional MIDI channel filter. Checking order is fixed: **jump, then inc, then dec** — the first slot whose CC matches wins.

### Jump: absolute targeting

```jsonc
"page_control": {
  "jump": { "cc": 20 }
}
```

Sending CC 20 with value 2 jumps straight to page 3 (0-based index 2). Values are clamped, so CC 20 = 99 on a 3-page config still lands on the last page (index 2) rather than doing nothing or erroring.

### Inc / dec: relative stepping

```jsonc
"page_control": {
  "inc": { "cc": 21, "value": 127, "page_step": 1 },
  "dec": { "cc": 22, "value": 127, "page_step": 1 }
}
```

`value` is a **trigger gate**, not a target page — the slot only fires when the incoming CC value exactly equals it (127 by default). This is deliberate: a footswitch or expression pedal sweeping through CC values won't accidentally page through your set. Sending CC 21 = 127 advances one page (wrapping); CC 22 = 127 goes back one page (also wrapping). Set `page_step` to move more than one page at a time.

### Channel filtering

```jsonc
"page_control": {
  "channel": 0,
  "jump": { "cc": 20 }
}
```

`channel` (0-based; the editor shows 1–16) applies to all three slots at once. Omit it (or leave it `null`) to accept the trigger on any channel — useful if you're not sure which channel your host will send on, at the cost of it also responding to that CC from anything else in the chain.

::: warning A bad channel disables everything
If `channel` is present but malformed (not an integer 0–15), the **entire `page_control` block is disabled** rather than being coerced to a default. This is deliberate — silently falling back to "any channel" would turn a scoping typo into every matching CC on every channel switching pages. The practical consequence is that a typo'd channel makes page control stop working altogether, which is a much more obvious failure than it half-working. If page control seems dead, check this field first.
:::

### Disabling

```jsonc
"page_control": { "enabled": false, "jump": { "cc": 20 } }
```

`enabled: false` turns the whole block off without deleting your slot config — handy for temporarily disabling page control without losing your CC assignments.

## Interaction with button processing

A matching Page Control CC **short-circuits** normal button processing entirely — it never reaches state sync, select sync, or any button's CC matching, even if a button on the current page happens to share that CC number.

Practical implication: pick CC numbers for `jump`/`inc`/`dec` that don't collide with CCs you're also using on buttons, or the button will simply never see those messages.

Two details worth knowing:

- **MIDI THRU still forwards it.** The short-circuit only applies to MCM's own button/page logic. The message is still relayed downstream per your [THRU matrix](./midi-thru.md) settings — Page Control never blocks forwarding.
- **Same-page requests are absorbed, not passed through.** If the resolved target equals the current page (e.g. `jump` to the page you're already on, or `inc` on a single-page config), nothing visibly happens — no page rebuild, no status line update. But the CC still counts as handled and does *not* fall through to button processing.

## Worked example: DAW transport-linked pages

Say pages 1–3 correspond to song sections (Intro / Verse / Chorus) and your DAW sends CC 30 with the section index (0, 1, 2) as playback reaches each marker:

```jsonc
"page_control": {
  "channel": 0,
  "jump": { "cc": 30 }
}
```

As the song plays, the pedal's active page tracks the DAW automatically — no footswitch presses required. Pair this with [state sync](./inbound-midi.md) on the buttons within each page and the entire rig — page and button state alike — stays locked to what the DAW is doing.

## Status line

A handled Page Control message shows on the LCD status line as `PAGE n` (1-based) when it actually changes the page. Same-page requests don't produce a status line update, since nothing changed.
