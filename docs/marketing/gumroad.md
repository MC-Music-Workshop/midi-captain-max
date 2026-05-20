# MIDI Captain MAX

**Bidirectional, open-source firmware + GUI editor for the Paint Audio MIDI Captain.**

Your DAW finally talks back. LEDs and the display update in real time from the host — not just one-way button presses. Configure everything in a real GUI with live validation. One-click firmware updates. Signed installers. Open source under the hood.

Built on Paint Audio's solid hardware. Inspired by [Helmut Keller](https://hfrk.de), whose original firmware first demonstrated bidirectional MIDI on the Captain.

---

## The Headline Features

- **Bidirectional MIDI** — host updates LEDs and display in real time. The Captain is no longer a one-way button box.
- **GUI Config Editor** — visual layout, color picker, live validation, device auto-detect. No more hand-editing cryptic bracket strings like `[1][CC][69][0]`.
- **One-click firmware install** — built into the editor. No drag-and-drop, no KEY0 dance after the first install.
- **Signed installers** — macOS and Windows. No security warnings, no manual overrides. (Linux coming.)
- **Setup Mode** — tweak config and hear the change without ejecting and replugging.
- **Open source** — readable, hackable, forkable. MIT licensed.

## What's New

- **MIDI Thru routing matrix** — 4 independent USB ↔ DIN routes, each toggleable. Replaces the OEM's single global on/off.
- **HID keyboard + mouse** — drive any application from a footswitch. Full modifier support (Ctrl, Shift, Alt, etc.).
- **SELECT mode for PC and CC** — unlimited named radio groups. Configure what happens when you press the already-active button: re-send, do nothing, or deselect.
- **Flash mode** — brief LED flash on press. Perfect for program-change buttons.
- **Keytimes up to 99 states** — OEM caps at 9. Same idea, 11× the depth.
- **`pc_step` with any step size** — OEM is limited to 1–5. Pick any number.
- **Encoder push button as a full control** — channel, CC, label, momentary or toggle, separate on/off values.
- **Custom USB drive name** — per-device. Great when juggling multiple Captains.
- **Richer expression-pedal config** — channel, CC, value range, polarity, sensitivity, custom label, per pedal.

## How It Stacks Up Against OEM (Paint Audio SuperMode 4.0)

| | **MIDI Captain MAX** | **OEM SuperMode 4.0** |
|---|---|---|
| Bidirectional MIDI | ✅ host drives LEDs + display | ❌ one-way |
| Config format | ✅ readable, validated, shareable | ⚠️ cryptic bracket strings |
| Editor | ✅ GUI with live validation | ❌ hand-edit text files |
| Firmware updates | ✅ one click | ❌ manual drag-and-drop |
| Source | ✅ open | ❌ closed binary |
| Signed installers | ✅ macOS + Windows | ❌ N/A |

Full feature-by-feature parity audit: [mcm-vs-oem.md](https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/docs/marketing/mcm-vs-oem.md).

**Honest about gaps:** OEM still wins on a handful of advanced macros (PC `random`, PC `auto` bank), the `tap` beat-flash LED mode, per-segment LED ring colors, and pages. All of those are on the [public roadmap](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1) — pages are the biggest item on deck.

## Supported Hardware

| Device | Status |
|---|---|
| STD10 | ✅ |
| MINI6 | ✅ |
| NANO4 | ✅ |
| DUO   | ✅ |
| ONE   | ✅ |
| EXP/SW | not yet (separate Paint Audio product, not a Captain variant) |

## What You Get

- **Config Editor installer** for your OS (`.dmg` for macOS, `.exe` / `.msi` for Windows). The editor bundles the firmware — one download.
- **Complete zip** with the editor, the firmware, and the deploy script if you'd rather flash from the terminal or use an unsupported OS.

## Installation, Short Version

1. Back up your existing Captain (mount it, copy everything off — keep it somewhere safe).
2. Install the Config Editor.
3. Plug in the Captain. The editor auto-detects it.
4. Click **Install Firmware** in the editor.

First install on OEM firmware needs a one-time bootstrap with the deploy script (held KEY0 while plugging in). Full instructions on the [GitHub README](https://github.com/MC-Music-Workshop/midi-captain-max#installation).

## License

MIT. Free for personal and commercial performance. Hack it, fork it, ship it.

## Support

- Bugs, feature requests, questions: [open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues).
- Roadmap: [project board](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1).

---

*Pay-what-you-want. If MCM saves you time on stage or in the studio, the suggested price helps keep the lights on. If it doesn't fit your budget, take it anyway — that's the point of open source.*
