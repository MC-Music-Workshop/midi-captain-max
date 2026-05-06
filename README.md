[![CI](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/ci.yml/badge.svg)](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/ci.yml)
[![Release](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/release.yml/badge.svg)](https://github.com/MC-Music-Workshop/midi-captain-max/actions/workflows/release.yml)

# MIDI Captain MAX Custom Firmware for Paint Audio MIDI Captain Devices

## What It Does

This firmware transforms your MIDI Captain into a **bidirectional MIDI controller** where your host software (DAW, plugin host) can control the device's LEDs and display, not just receive button presses.

Momentary and toggle modes are currently supported. Many more features are coming! See here for [all open features and issues](https://github.com/MC-Music-Workshop/midi-captain-max/issues), and [the prioritized Kanban board of upcoming work](https://github.com/orgs/MC-Music-Workshop/projects/1/views/1).

## Key Features
- **Bidirectional MIDI** — Host can update LEDs/display state on MCM
- **GUI Config Editor** — Customize button labels, CC numbers, and colors with the GUI Config Editor
- **Dev Mode** - Quickly test config changes without remounting the device
- **Custom Drive Names** - Useful when managing multiple Captains
- **HID Messages** - send keyboard and mouse messages in addition to MIDI
- **Signed Installation Packages** — Install without security warnings or manual overrides (macOS and Linux)
- **Stage-ready** — No unexpected resets, no crashes, no surprises

### Includes a **GUI Config Editor**!

<img width="1312" height="912" alt="MCM-config-editor" src="https://github.com/user-attachments/assets/5e4c0b73-074b-4895-8861-d95aea7f1426" />


## Supported Devices

| Device | Status |
|--------|--------|
| STD10 | ✅ |
| MINI6 | ✅  |
| NANO4 | ✅  |
| DUO  | ✅ |
| ONE | ✅ |
| EXP/SW | Pending |

# Installation

## First: Backup!

*Before doing any of this, if you haven't already, please back up your existing config and firmware to a safe place* for recovery or to revert to OEM firmware:

1. Mount the device to your computer. You may have to hold down Button 1 / KEY0 to force it to mount.
2. Copy all contents of the device to a safe place on your computer.

## Installation

Once MIDI Captain MAX v1.10.0 or later is installed, manual firmware updates are no longer needed. The GUI Config Editor now includes a **Firmware Installation** section at the bottom of the window. It shows the currently installed firmware version and the bundled version available to install.

You can download either:

1. The appropriate Config Editor installer for your OS: `.dmg` for macOS, `.exe` or `.msi` for Windows. **The Config Editor includes the bundled firmware, so you don't need to download it separately**.
2. The `MIDI-Captain-MAX-v1.10.0-complete.zip` package if you want the GUI and the firmware as separate packages.<br>For example, if you need to use the deploy script for the first install, or for an unsupported OS, this package includes everything you need. (The GUI still includes the bundled firmware; the zip is just for convenience if you want to use the deploy script instead of the GUI installer.)

## Updating an Existing MIDI Captain MAX Install

1. Connect your MIDI Captain via USB and power it on.
   - The device may mount as `CIRCUITPY` or `MIDICAPTAIN`.
   - If no drive appears, hold switch 1 / KEY0 while plugging in USB.
2. Install and open the MIDI Captain MAX Config Editor.
3. Scroll to the **Firmware Installation** section at the bottom of the app window.
4. Click **Install Firmware**.

By default, the installer preserves your existing `config.json`. Enable **Reset config.json to bundled defaults** only if you want to overwrite your current settings with the default template.

The app will copy the firmware, reload the device, and update it in place.

## First Run on OEM Firmware

If your MIDI Captain is still running the factory Paint Audio firmware, the Config Editor may show `OEM (no VERSION.txt file)`.

In many cases, the first install still requires a one-time bootstrap because the OEM firmware does not provide a MIDI Captain MAX `config.json` for device-type detection.

1. Hold Button 1 / KEY0 while plugging in USB to enter the OEM USB settings mode. A `MIDICAPTAIN` drive should appear.
2. Download and extract `MIDI-Captain-MAX-v1.10.0-complete.zip` from the Assets section below.
3. Run the included deploy script once with your device type:
   <br>_NOTE: only enter the desired device type, not the full list of options.
   <br>For example, if you have a Nano 4, run `./deploy.sh --device nano4`_.
   - macOS / Linux: `./deploy.sh --device std10|mini6|nano4|duo2|one1`
   - Windows PowerShell: `.\deploy.ps1 -Device std10|mini6|nano4|duo2|one1`
4. Reconnect the device and open the MIDI Captain MAX Config Editor.
5. From then on, use the **Firmware Installation** section in the app for future updates.

## Recovery

If anything goes wrong, it is fully recoverable:

1. Mount the device.
2. Erase the contents.
3. Restore your backup, or re-run the first-install steps above.

# Configuration

## Custom USB Drive Name

If you have multiple MIDI Captain devices, you can give each one a unique name! Edit the `usb_drive_name` field in `config.json`:

```json
{
  "device": "std10",
  "usb_drive_name": "MYCAPTAIN",
  ...
}
```

**Requirements:**
- Maximum 11 characters
- Letters, numbers, and underscores only
- Will be automatically converted to uppercase

The name persists across power cycles and USB disconnects. Change it anytime by editing config.json and restarting the device.

## Config Editor App

# Features

- 🖱️ **Visual editing** — No JSON syntax to learn
- ✅ **Real-time validation** — Catch errors before saving
- 🎨 **Color picker** — Visual color selection 
- 🔍 **Device detection** — Automatically detects connected MIDI Captain

### Advanced: Keytimes (Multi-Press Cycling)

**Keytimes** allows a button to cycle through multiple states on repeated presses, similar to the OEM SuperMode firmware. Each state can have different MIDI values and LED colors.

#### Example: 3-State Reverb Button

```json
{
  "label": "VERB",
  "cc": 20,
  "keytimes": 3,
  "states": [
    {"cc_on": 64, "color": "blue"},      // State 1: 50% wet
    {"cc_on": 96, "color": "cyan"},      // State 2: 75% wet  
    {"cc_on": 127, "color": "white"}     // State 3: 100% wet
  ]
}
```

- **First press**: Sends CC20=64, LED shows blue
- **Second press**: Sends CC20=96, LED shows cyan
- **Third press**: Sends CC20=127, LED shows white
- **Fourth press**: Cycles back to state 1

#### Per-State Options

Each state in the `states` array can override:
- `cc_on`: MIDI CC value to send (0-127)
- `cc_off`: Value when turning off (optional)
- `color`: LED color for this state
- `label`: Display label for this state (future)

#### Notes

- Keytimes defaults to 1 (standard toggle/momentary behavior)
- Maximum 99 states per button
- Works with both toggle and momentary modes
- When cycling, the button always sends the `cc_on` value for the current state

## Use Cases

- **Gig Performer / MainStage** — Sync button states with plugin bypass
- **Ableton Live** — Control track mutes/solos with visual feedback
- **Guitar Rig / Helix Native** — Effect on/off with LED confirmation
- **Any MIDI-capable host** — Generic CC control with bidirectional sync
- **Any Application** - Generic HID (keyboard and mouse) can control any application

## License

Copyright © 2026 Maximilian Cascone. All rights reserved.

You may use this firmware freely for personal or commercial performances. Redistribution of modified versions requires permission. See [LICENSE](LICENSE) for details.

## Attribution

This project builds on work by **Helmut Keller** ([hfrk.de](https://hfrk.de)), whose original firmware demonstrated bidirectional MIDI on the MIDI Captain. His code is preserved in `firmware/original_helmut/` as a reference.

## Questions, Comments, Suggestions are welcome

[Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues) or check [AGENTS.md](AGENTS.md) for developer documentation.

