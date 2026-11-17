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
- **One-click firmware install**: the Config Editor installs and updates the firmware for you, and tells you when your pedal's firmware is older than the editor
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
2. **Download the Config Editor** for your OS from the [latest release](https://github.com/MC-Music-Workshop/midi-captain-max/releases/latest) — `.dmg` (macOS), `.exe` / `.msi` (Windows), `.AppImage` / `.deb` (Linux). It bundles the firmware, so there's no separate firmware download. On macOS you can install it with Homebrew instead: `brew install --cask mc-music-workshop/tap/midi-captain-max`.
3. **Install the firmware:** open the editor, scroll to **Firmware Installation** at the bottom of the window, and click **Install Firmware**. Your `config.json` is preserved unless you enable **Reset config.json to bundled defaults**. Later, when the pedal's firmware is older than the editor's, a notice at the top of the window offers **Update Firmware**.

Devices still running the factory Paint Audio firmware need a one-time device-type step first, and 2026-batch devices (CircuitPython 9.2.7) need a **Reflash CircuitPython 7.3.1** first — both are covered in the guide.

> **Prefer the command line, or on an unsupported OS?** Download `MIDI-Captain-MAX-<version>-complete.zip` instead. It contains the firmware plus `deploy.sh` / `deploy.ps1` install scripts — see the bundled [`INSTALL.md`](firmware/dev/INSTALL.md) for usage.

## Configuration

### Config Editor

Configure your device with the Config Editor:

- 🖱️ **Visual editing**: no JSON syntax to learn
- ✅ **Real-time validation**: catch errors before saving
- 🎨 **Color picker**: visual color selection
- 🔍 **Device detection**: automatically finds a connected MIDI Captain

Connect your device, edit buttons, and save — the editor writes `config.json` to the device for you.

<img width="75%" height="75%" alt="MIDI Captain MAX Config Editor" src="https://github.com/user-attachments/assets/5e4c0b73-074b-4895-8861-d95aea7f1426" />

### Custom USB Drive Name

If you own multiple MIDI Captains, it gets confusing which one is which when they're all named MIDICAPTAIN. Give each one a unique drive name in two steps — both are needed:

1. **Rename the drive** in Finder (macOS) or File Explorer (Windows), just like renaming a USB stick. FAT volume labels allow up to 11 characters (letters, numbers, and underscores; stored as uppercase), and the name persists across power cycles.
2. **Enter the same name in the Config Editor's USB Drive Name field** and save.

The field tells the tooling what the drive is called: the deploy script uses it to find a custom-named drive, and the Config Editor requires it to match the actual volume name when it's set. It can't rename the drive itself yet.

### Keytimes (Multi-State Cycling + Short/Long Press)

Set a button's **Mode** to **Keytimes (short/long)** to make it cycle through multiple states on repeated presses, similar to the OEM SuperMode firmware. Each entry has its own messages and LED color, and short taps and long holds get **independent** cycles: the **Short Press Cycle** and the **Long Press Cycle**.

Example: a reverb button that cycles 50% → 75% → 100% wet on each tap has three Short Press Cycle entries, each sending CC20 (64, 96, 127) with its own color (blue, cyan, white):

- **First press**: sends CC20=64, LED turns blue
- **Second press**: sends CC20=96, LED turns cyan
- **Third press**: sends CC20=127, LED turns white
- **Fourth press**: cycles back to the first state

Each entry can send messages on press and/or release (any message type: CC, PC, note, HID, etc.). Add Long Press Cycle entries to give long holds their own separate cycle; the tap/hold boundary is the **Long-press threshold** (default 500 ms).

Full walkthrough — press events, when cycles advance, LED/label rules, long-press color overlay, and page behavior — in the **[Keytimes Guide](https://mc-music-workshop.github.io/midi-captain-max/docs/keytimes)**.

## License

Copyright © 2026 Maximilian Cascone. All rights reserved.

You may use this firmware freely for personal or commercial performances. Redistribution of modified versions requires permission. See [LICENSE](LICENSE) for details.

## Attribution

This project builds on work by **Helmut Keller** ([hfrk.de](https://hfrk.de)), whose original firmware demonstrated bidirectional MIDI on the MIDI Captain. His code is preserved in [`firmware/original_helmut/`](firmware/original_helmut/) as a reference.

## Questions, Comments, Suggestions

[Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues), or see [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for developer documentation.
