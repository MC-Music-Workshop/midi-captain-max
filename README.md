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

<img width="1312" height="912" alt="MIDI Captain MAX Config Editor" src="https://github.com/user-attachments/assets/5e4c0b73-074b-4895-8861-d95aea7f1426" />

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

### Step 1: Back Up Your Device

Before installing anything, back up your existing firmware and config so you can recover or revert to the OEM firmware later:

1. Connect the device via USB. If no drive appears, hold **Switch 1 / KEY0** while plugging in — a `MIDICAPTAIN` (or `CIRCUITPY`) drive should mount.
2. Copy the entire contents of the drive to a safe place on your computer.

### Step 2: Download the Config Editor

Grab the installer for your OS from the [latest release](https://github.com/MC-Music-Workshop/midi-captain-max/releases/latest):

| OS | File |
|----|------|
| macOS | `MIDI-Captain-MAX-Config-Editor-<version>.dmg` |
| Windows | `...-setup.exe` or `.msi` |
| Linux | `.AppImage` or `.deb` |

The Config Editor bundles the firmware — no separate firmware download is needed.

> **Prefer the command line, or on an unsupported OS?** Download `MIDI-Captain-MAX-<version>-complete.zip` instead. It contains the firmware plus `deploy.sh` / `deploy.ps1` install scripts — see the bundled [`INSTALL.md`](firmware/dev/INSTALL.md) for usage.

### Step 3: Install the Firmware

**If your device already runs MIDI Captain MAX** (or you're updating):

1. Connect the device via USB and power it on. It mounts as `CIRCUITPY` or `MIDICAPTAIN`; if no drive appears, hold **Switch 1 / KEY0** while plugging in.
2. Open the Config Editor.
3. Scroll to the **Firmware Installation** section at the bottom of the window. It shows the installed firmware version and the bundled version available.
4. Click **Install Firmware**.

The editor copies the firmware and reloads the device in place. Your existing `config.json` is preserved by default; enable **Reset config.json to bundled defaults** only if you want to start over from the default template.

**If your device still runs the factory Paint Audio firmware**, the Config Editor shows `OEM (no VERSION.txt file)` and a one-time bootstrap is needed, because the OEM firmware has no `config.json` for device-type detection:

1. Hold **Switch 1 / KEY0** while plugging in USB. A `MIDICAPTAIN` drive appears.
2. Download and extract `MIDI-Captain-MAX-<version>-complete.zip` from the [latest release](https://github.com/MC-Music-Workshop/midi-captain-max/releases/latest).
3. Run the deploy script once with your device type (pick **one** — e.g. for a Nano 4, use `nano4`):

   - macOS / Linux: `./deploy.sh --device nano4`
   - Windows PowerShell: `.\deploy.ps1 -Device nano4`
   - Windows cmd (if PowerShell blocks unsigned scripts): `deploy.bat -Device nano4` — runs `deploy.ps1` with a per-process `ExecutionPolicy Bypass`; no system policy is changed.

   Valid device types: `std10`, `mini6`, `nano4`, `duo2`, `one1`.

4. Reconnect the device and open the Config Editor.
5. From then on, use the **Firmware Installation** section in the app for updates — the script is never needed again.

## Troubleshooting and Recovery

### CircuitPython version mismatch

If the Config Editor refuses to install with a CircuitPython version error, your device is running a newer CircuitPython than this firmware supports (typical for 2026-batch Captains, which ship with CP 9.2.7). MIDI Captain MAX currently targets **CP 7.3.1** — see [#2](https://github.com/MC-Music-Workshop/midi-captain-max/issues/2) for the planned CP 9/10 migration and [#132](https://github.com/MC-Music-Workshop/midi-captain-max/issues/132) for background.

**Easiest fix:** in the Config Editor's **Firmware Installation** section, expand **Advanced / Recovery** and click **Reflash CircuitPython 7.3.1**. The editor drives the device into the RP2040 bootloader, copies the bundled `.uf2`, and waits for the drive to remount — no terminal work required. Then click **Install Firmware**.

**Manual fallback** (only if the GUI's automatic bootloader entry fails): follow [`docs/recovery-bootloader-entry.md`](docs/recovery-bootloader-entry.md) to reach the `RPI-RP2` bootloader drive, then copy the CP 7.3.1 `.uf2` from the `-complete.zip` release asset onto it. The device reboots into `CIRCUITPY` automatically.

> ⚠️ **Switch 1 / KEY0 does not enter the RP2040 bootloader.** It only makes the running firmware expose the USB drive. To reach `RPI-RP2`, use the Config Editor's reflash button or the recovery guide above.

### Bad state / starting over

Everything is recoverable:

1. Mount the device (hold **Switch 1 / KEY0** while plugging in if needed).
2. Delete the drive's contents.
3. Restore your backup, or redo the install steps above.

## Configuration

### Config Editor (Recommended)

The Config Editor is the easiest way to configure your device:

- 🖱️ **Visual editing**: no JSON syntax to learn
- ✅ **Real-time validation**: catch errors before saving
- 🎨 **Color picker**: visual color selection
- 🔍 **Device detection**: automatically finds a connected MIDI Captain

Connect your device, edit buttons, and save — the editor writes `config.json` to the device for you.

### Editing config.json Directly

All settings live in `config.json` at the root of the device drive. The full schema is [`config.schema.json`](config.schema.json), and [`firmware/dev/`](firmware/dev/) contains commented example configs (`config-example-*.json`) covering every message type, HID, MIDI channels, and keytimes.

After editing, safely eject and power-cycle the device to load the new config.

### Custom USB Drive Name

If you own multiple MIDI Captains, give each one a unique drive name via the `usb_drive_name` field:

```json
{
  "device": "std10",
  "usb_drive_name": "MYCAPTAIN"
}
```

Requirements:

- Maximum 11 characters
- Letters, numbers, and underscores only
- Automatically converted to uppercase

The name persists across power cycles. Change it anytime by editing `config.json` and restarting the device.

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

See [`firmware/dev/config-example-keytimes.json`](firmware/dev/config-example-keytimes.json) and [`config-example-keytimes-mode.json`](firmware/dev/config-example-keytimes-mode.json) for full working examples, and the [design doc](docs/plans/2026-05-13-issue-48-press-timings.md) for details.

## Use Cases

- **Gig Performer / MainStage**: sync button states with plugin bypass
- **Ableton Live**: control track mutes/solos with visual feedback
- **Guitar Rig / Helix Native**: effect on/off with LED confirmation
- **Any MIDI-capable host**: generic CC control with bidirectional sync
- **Any application**: generic HID (keyboard and mouse) control

## License

Copyright © 2026 Maximilian Cascone. All rights reserved.

You may use this firmware freely for personal or commercial performances. Redistribution of modified versions requires permission. See [LICENSE](LICENSE) for details.

## Attribution

This project builds on work by **Helmut Keller** ([hfrk.de](https://hfrk.de)), whose original firmware demonstrated bidirectional MIDI on the MIDI Captain. His code is preserved in [`firmware/original_helmut/`](firmware/original_helmut/) as a reference.

## Questions, Comments, Suggestions

[Open an issue](https://github.com/MC-Music-Workshop/midi-captain-max/issues), or see [AGENTS.md](AGENTS.md) and [CONTRIBUTING.md](CONTRIBUTING.md) for developer documentation.
