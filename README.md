[![CI](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/ci.yml/badge.svg)](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/ci.yml)
[![Release](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/release.yml/badge.svg)](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/release.yml)

# MIDI Captain MAX

Custom firmware for [Paint Audio MIDI Captain](https://paintaudio.com/) foot controllers, plus a GUI Config Editor for installing and customizing it.

## What It Does

MIDI Captain MAX turns your MIDI Captain into a **bidirectional MIDI controller**: your host software (DAW, plugin host) can control the device's LEDs and display, not just receive button presses.

See the [open issues](https://github.com/MC-Music-Workshop/midi-captain-max/issues) and the [prioritized Kanban board](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1) for what's coming next.

## Key Features

- **Bidirectional MIDI**: the host can update LED and display state on the device
- **GUI Config Editor**: customize button labels, CC numbers, and colors visually — no JSON required
- **One-click firmware install**: the Config Editor installs and updates the firmware for you
- **Short / long press (keytimes mode)**: each button can fire different messages on a short tap vs. a long hold, with independent multi-state cycles per timing class
- **HID messages**: send keyboard and mouse events in addition to MIDI
- **Custom drive names**: useful when managing multiple Captains
- **Dev mode**: quickly test config changes without remounting the device
- **Signed installation packages**: install without security warnings or manual overrides (macOS and Linux)
- **Stage-ready**: no unexpected resets, no crashes, no surprises

## Use Cases

- **Gig Performer / MainStage**: sync button states with plugin bypass
- **Ableton Live**: control track mutes/solos with visual feedback
- **Guitar Rig / Helix Native**: effect on/off with LED confirmation
- **Any MIDI-capable host**: generic CC control with bidirectional sync
- **Any application**: generic HID (keyboard and mouse) control

## Supported Devices

| Device | Status |
|--------|--------|
| STD10 | ✅ |
| MINI6 | ✅ |
| NANO4 | ✅ |
| DUO | ✅ |
| ONE | ✅ |
| EXP/SW | Pending |

## Installation

Full walkthrough: **[Installation Guide](https://mc-music-workshop.github.io/midi-captain-max/docs/installation)** — first install on OEM firmware, updating, CircuitPython version errors, the deploy script, and recovery.

The short version:

1. **Back up your device.** Connect via USB (hold **Switch 1 / KEY0** while plugging in if no drive appears) and copy the entire drive somewhere safe.
2. **Download the Config Editor** for your OS from the [latest release](https://github.com/MC-Music-Workshop/midi-captain-max/releases/latest) — `.dmg` (macOS), `.exe` / `.msi` (Windows), `.AppImage` / `.deb` (Linux). It bundles the firmware, so there's no separate firmware download.
3. **Install the firmware:** open the editor, scroll to **Firmware Installation** at the bottom of the window, and click **Install Firmware**. Your `config.json` is preserved unless you enable **Reset config.json to bundled defaults**.

Devices still running the factory Paint Audio firmware need a one-time device-type step first, and 2026-batch devices (CircuitPython 9.2.7) need a **Reflash CircuitPython 7.3.1** first — both are covered in the guide.

> **Prefer the command line, or on an unsupported OS?** Download `MIDI-Captain-MAX-<version>-complete.zip` instead. It contains the firmware plus `deploy.sh` / `deploy.ps1` install scripts — see the bundled [`INSTALL.md`](firmware/dev/INSTALL.md) for usage.

## Configuration

### Config Editor (Recommended)

The Config Editor is the easiest way to configure your device:

- 🖱️ **Visual editing**: no JSON syntax to learn
- ✅ **Real-time validation**: catch errors before saving
- 🎨 **Color picker**: visual color selection
- 🔍 **Device detection**: automatically finds a connected MIDI Captain

Connect your device, edit buttons, and save — the editor writes `config.json` to the device for you.

<img width="75%" height="75%" alt="MIDI Captain MAX Config Editor" src="https://github.com/user-attachments/assets/5e4c0b73-074b-4895-8861-d95aea7f1426" />

### Editing config.json Directly

**Don't do this unless you know what you're doing.** The Config Editor is safer and easier. There is nothing you can do in the JSON that the editor can't do for you, and the editor will catch errors before they break your device.

All settings live in `config.json` at the root of the device drive. The full schema is [`config.schema.json`](config.schema.json), and [`firmware/dev/`](firmware/dev/) contains commented example configs (`config-example-*.json`) covering every message type, HID, MIDI channels, and keytimes.

After editing, safely eject and power-cycle the device to load the new config.

### Custom USB Drive Name

If you own multiple MIDI Captains, it gets confusing which one is which when they're all named MIDICAPTAIN. Give each one a unique drive name in two steps — both are needed:

1. **Rename the drive** in Finder (macOS) or File Explorer (Windows), just like renaming a USB stick. FAT volume labels allow up to 11 characters (letters, numbers, and underscores; stored as uppercase), and the name persists across power cycles.
2. **Set `usb_drive_name` in `config.json` to the same name** (the Config Editor has a field for it):

   ```json
   {
     "device": "std10",
     "usb_drive_name": "MYCAPTAIN"
   }
   ```

The field tells the tooling what the drive is called: the deploy script uses it to find a custom-named drive, and the Config Editor requires it to match the actual volume name when it's set. It can't rename the drive itself yet.

### Keytimes (Multi-State Cycling + Short/Long Press)

Set a button's `mode` to `"keytimes"` to make it cycle through multiple states on repeated presses, similar to the OEM SuperMode firmware. Each state has its own messages and LED color, and short taps and long holds get **independent** state cycles via the `short` and `long` arrays.

Example — a reverb button that cycles 50% → 75% → 100% wet on each tap:

```json
{
  "label": "VERB",
  "color": "blue",
  "mode": "keytimes",
  "short": [
    { "down": [{ "type": "cc", "cc": 20, "value": 64 }],  "color": "blue" },
    { "down": [{ "type": "cc", "cc": 20, "value": 96 }],  "color": "cyan" },
    { "down": [{ "type": "cc", "cc": 20, "value": 127 }], "color": "white" }
  ]
}
```

- **First press**: sends CC20=64, LED turns blue
- **Second press**: sends CC20=96, LED turns cyan
- **Third press**: sends CC20=127, LED turns white
- **Fourth press**: cycles back to the first state

Each state can specify `down` and/or `up` message lists (any message type: `cc`, `pc`, `note`, HID, etc.) and a `color`. Add a `long` array to give long holds their own separate cycle; the tap/hold boundary is set by the top-level `long_press_threshold_ms` (default 500).

Full walkthrough — press events, when cycles advance, LED/label rules, `long_overlay`, and page behavior — in the **[Keytimes Guide](https://mc-music-workshop.github.io/midi-captain-max/docs/keytimes)**. Working configs: [`config-example-keytimes.json`](firmware/dev/config-example-keytimes.json) and [`config-example-keytimes-mode.json`](firmware/dev/config-example-keytimes-mode.json).

## License

Copyright © 2026 Maximilian Cascone. All rights reserved.

You may use this firmware freely for personal or commercial performances. Redistribution of modified versions requires permission. See [LICENSE](LICENSE) for details.

## Attribution

This project builds on work by **Helmut Keller** ([hfrk.de](https://hfrk.de)), whose original firmware demonstrated bidirectional MIDI on the MIDI Captain. His code is preserved in [`firmware/original_helmut/`](firmware/original_helmut/) as a reference.

## Questions, Comments, Suggestions

[Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues), or see [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for developer documentation.
