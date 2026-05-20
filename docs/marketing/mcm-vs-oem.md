# MIDI Captain MAX vs. Factory OEM Firmware

A feature-by-feature comparison of **MIDI Captain MAX (MCM)** against **Paint Audio's factory SuperMode 4.0 firmware**, running on the same hardware.

---

## At a Glance

| | **MIDI Captain MAX** | **OEM (Paint Audio SuperMode 4.0)** |
|---|---|---|
| **Bidirectional MIDI** | ✅ Host updates LEDs and display in real time | ❌ One-way only |
| **Config format** | ✅ Modern, validated config — readable and shareable | ⚠️ Cryptic bracket strings in text files (`[1][CC][69][0]`) |
| **Editor** | ✅ GUI Config Editor with live validation | ❌ Hand-edit text files |
| **Firmware updates** | ✅ One-click from the editor | ❌ Manual drag-and-drop |
| **Source** | ✅ Open source — readable, hackable, forkable | ❌ Closed binary |
| **Custom USB drive name** | ✅ Per-device | ❌ Always `MIDICAPTAIN` |
| **Signed installers** | ✅ macOS + Windows (Linux coming soon) | ❌ N/A |

---

## Feature-by-Feature Parity

### Button Behavior

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| **Keytimes** — multi-press cycling (up to 9 states) | **Keytimes** (same name, expanded) — up to **99** states per button | ⬆️ Parity, 11× the depth |
| Short / long press timings (fire on press-down, press-up, long-hold, and long-release) | All four actions supported, with independent short and long press cycles | ✅ Parity |
| Multiple commands per press (any combination of message types) | Stack as many messages as you want on any press action, edited visually in the GUI | ✅ Parity |
| Standard LED behavior (lights on press) | Default toggle / momentary behavior | ✅ |
| Radio-group buttons (one lit at a time) — single implicit group | **Unlimited named radio groups** — set up as many independent button groups as you want, with configurable behavior when pressing the already-active button (re-send, do nothing, or deselect) | ⬆️ Parity, more configurable |
| Tap-tempo beat-flash LED mode | — | 🛠️ [Coming soon](https://github.com/MC-Music-Workshop/midi-captain-max/issues/80) |
| Per-segment color on the 3-segment LED ring | Single color per button today; per-segment control and even simple LED animations are on the roadmap, with GUI editing far easier than OEM's hex-by-segment syntax | 🛠️ [Coming soon](https://github.com/MC-Music-Workshop/midi-captain-max/issues/58) |
| Momentary (LED on while held) | Momentary mode | ✅ |
| Toggle (latching on/off) | Toggle mode | ✅ |
| — | **Flash mode** — brief LED flash on press, perfect for program-change buttons | 🆕 MCM-only |

### Message Types

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| MIDI CC | Full CC with separate on / off values and channel | ✅ |
| MIDI Note | Full note with velocity and channel | ✅ |
| MIDI Program Change | Full PC with channel | ✅ |
| PC increment (steps 1–5) | PC increment with any step size you choose | ⬆️ Parity (any step, not just 1–5) |
| PC decrement (steps 1–5) | PC decrement with any step size | ⬆️ Parity (any step, not just 1–5) |
| PC random (`[2][PC][random][-]`) | — | ➖ Gap (Do you use this? Get in touch!) |
| PC auto-bank (`[1][PC][auto][bank_inc / bank_dec / 0..7]`) | — | ➖ Gap (Do you use this? Get in touch!) |
| HID keyboard and mouse | Full keyboard and mouse control of any application | ✅ |
| HID press / release / modifiers (Ctrl, Shift, Alt, etc.) | Press, release, and chord with all standard modifiers | ✅ |
| HID delay (insert a pause between keystrokes) | — | 🛠️ Pending |

### Pages

Pages are **coming soon to MCM**, with far more flexibility than OEM. OEM supports up to 99 pages, but the page-change action is hard-coded (no user config). MCM's version will be fully configurable — any button, any action, plus host-driven page jumps via bidirectional MIDI.

### Expression Pedals

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| Two expression pedals (set CC and channel) | Two pedals with channel, CC, value range, polarity, sensitivity, and custom label per pedal | ⬆️ Parity, richer config |
| Live value display on device | ✅ MCM shows pedal value on the OLED | ✅ |
| Hardware availability | STD10 only (the only Captain with pedal ports) | Same on both |

### Encoder

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| Encoder CC and name | Encoder with custom CC, channel, label, value range, starting value, and step size | ⬆️ Parity, richer config |
| Encoder push button | Push button as its own fully configurable control — channel, CC, label, momentary or toggle, separate on / off values | 🆕 MCM-only level of control |

### Global / Display Settings

| OEM Feature | MCM Equivalent | Status |
|---|---|---|
| MIDI Thru on/off (single global toggle) | **MIDI Thru routing matrix** — 4 independent USB ↔ DIN routes, each toggleable | ⬆️ Parity, far richer |
| PC display grouping modes (`123` / `abc3` / `abc4` / `abc5` / `abc8`) | — | ➖ Gap — open to adding once requirements are scoped |
| PC offset, bank offset, group size | — | ➖ Gap — open to adding once requirements are scoped |
| — | Basic text-size tuning today (button labels, status line, expression-pedal readouts); richer typography, layout, and per-page display control on the roadmap | 🆕 MCM-only (early; growing) |
| — | Custom USB drive name: great for juggling multiple Captains | 🆕 MCM-only |
| — | Bidirectional MIDI: host can drive LEDs / display | 🆕 MCM-only headline feature |

### Tooling & Workflow

| OEM | MCM | Status |
|---|---|---|
| Hand-edit `supersetup/pageX.txt` in a text editor | GUI Config Editor: visual layout, color picker, live validation, device auto-detect | 🆕 MCM-only |
| No validation — typo in a config file silently misbehaves | Live validation catches mistakes before you save | 🆕 MCM-only |
| Manual firmware flashing (drag-and-drop, hold KEY0 on boot) | One-click firmware install from the GUI | 🆕 MCM-only |
| Edit config, eject, replug, repeat | **Setup Mode** — tweak your config and hear the change without ever remounting the pedal | 🆕 MCM-only |
| Closed binary firmware | Open source — readable, hackable, forkable | 🆕 MCM-only |
| No signed installers | Signed installers for macOS and Windows — no security warnings, no manual overrides (Linux coming soon) | 🆕 MCM-only |

### Supported Hardware

| Device | MCM | OEM |
|---|---|---|
| STD10 | ✅ | ✅ |
| MINI6 | ✅ | ✅ |
| NANO4 | ✅ | ✅ |
| DUO   | ✅ | ✅ |
| ONE   | ✅ | ✅ |

Paint Audio's newer **EXP/SW** is a separate product, not a Captain variant; MCM has not been ported to it (yet).

---

## Summary

**Where MCM clearly wins:**
- Bidirectional MIDI — the gamechanger that puts your DAW and your pedalboard on the same page
- GUI editor with live validation, signed installers, one-click updates
- Custom USB drive names, Setup Mode, open source
- `select` radio-group mode, `flash` mode, configurable `pc_step`, richer encoder + expression pedal config

**Where OEM still has features MCM lacks:**
- Pages and everything tied to them (page names, CC 20 page jump, PC/page persistence) — **coming soon**
- `tap` LED mode (beat flash) — coming soon
- Per-segment colors on the 3-segment LED ring (and animation, both coming soon)
- PC `random` and PC `auto` bank macros
- HID delay (pause between keystrokes) — pending
- PC display grouping modes (`abc3` / `abc4` / etc.) — open to adding, awaiting requirements

Track upcoming work on the [public roadmap](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1) — pages are the biggest item on deck.

---

## The Pitch

MCM keeps the parts of OEM SuperMode that real players use — keytimes cycling, expression pedals, HID, all the MIDI types — and adds the things performers have been asking for: bidirectional state, a real editor, validated config, painless updates, and open source under the hood. The OEM still wins on a handful of advanced macros and on pages, both of which are on the roadmap.

Built on Paint Audio's solid hardware. Inspired by [Helmut Keller](https://hfrk.de), whose original firmware first demonstrated bidirectional MIDI on the Captain. Extended by an open-source community.

---

*Questions? [Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues). MCM is free to use for personal and commercial performance — see [LICENSE](../../LICENSE).*
