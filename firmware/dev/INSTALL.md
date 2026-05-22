# MIDI Captain MAX — Firmware Installation

## Getting Started

1. **Connect** your MIDI Captain to your computer via USB
2. A drive called **CIRCUITPY** or **MIDICAPTAIN** should appear

> **Don't see the drive?** See the [Recovery](#recovery) section below.

---

## Install with the Deploy Script (Recommended)

The deploy script is the easiest way to install or update firmware. It automatically detects your device, installs required libraries, and preserves your settings.

### macOS / Linux

Open a terminal in this folder and run:

```bash
# First-time install (downloads required libraries)
./deploy.sh --install

# Update existing firmware
./deploy.sh
```

**Options:**

| Flag | What it does |
|------|-------------|
| `--install` | Full install including CircuitPython libraries |
| `--eject` | Safely eject the device after deploying |
| `--fresh` | Reset config.json to factory defaults |
| `--libs-only` | Only install/update CircuitPython libraries |

### Windows (PowerShell)

Open PowerShell in this folder and run:

```powershell
# First-time install (downloads required libraries)
.\deploy.ps1 -Install

# Update existing firmware
.\deploy.ps1
```

**Options:**

| Flag | What it does |
|------|-------------|
| `-Install` | Full install including CircuitPython libraries |
| `-Eject` | Safely eject the device after deploying |
| `-Fresh` | Reset config.json to factory defaults |
| `-LibsOnly` | Only install/update CircuitPython libraries |
| `-MountPoint E:\` | Use a specific drive letter |

> **Both scripts** auto-detect your device type (STD10 or Mini6) and preserve your existing button mappings, colors, and other settings.

---

## Manual Installation

Use this method if the deploy scripts aren't working for you.

1. **Connect** your MIDI Captain via USB
2. **Hold Button 1** (top-left footswitch) while powering on — this enables write access
3. **Copy ALL files and folders** from this package to the device drive, replacing existing files
4. **Safely eject** the drive from your computer, then unplug and replug the USB cable to restart the device

> **Important:** If you've already customized your `config.json` (button mappings, colors, etc.), **don't overwrite it** — skip that file when copying.

---

## Recovery

If your device ends up in a bad state, don't worry — it's fully recoverable:

1. Connect the device via USB (it should still show up as a drive)
2. Delete everything on the drive
3. Copy the firmware files onto the drive again
4. Safely eject the drive, then unplug and replug USB to restart

If the drive doesn't appear at all — or if the Config Editor refused to install with a CircuitPython-version error — you need to reflash CircuitPython 7.3.1.

> **Why 7.3.1 specifically?** This firmware's bundled libraries are mpy format v5 and `boot.py` uses CP 7-only APIs. CP 8.0 and later silently break it. See issue #132 for details and #2 for the planned migration to CP 9/10.

**Easiest: open the Config Editor → Firmware Installation → expand "Advanced / Recovery" → click "Reflash CircuitPython 7.3.1".** The editor drives the device into the RP2040 bootloader over its serial REPL, copies the bundled `.uf2`, and waits for `CIRCUITPY` to remount automatically. No terminal work required.

**Manual / terminal** — only needed if the GUI's auto-entry fails (device too broken to honour REPL commands, no CDC serial available). Full recipe with serial REPL commands and the physical-BOOTSEL fallback:

→ [`docs/recovery-bootloader-entry.md`](../../docs/recovery-bootloader-entry.md)

Then copy `adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2` (from the `MIDI-Captain-MAX-vX.Y.Z-complete.zip` release asset, or run `./tools/fetch-cp-uf2.sh` from a repo checkout) onto the `RPI-RP2` drive. The device reboots back to `CIRCUITPY` on its own.

> ⚠️ **Switch 1 / KEY0 does not enter the RP2040 bootloader on Captain devices.** Earlier versions of this doc said it did; that was wrong. Switch 1 only triggers the running CircuitPython firmware's "expose USB drive" branch, not the chip's ROM BOOTSEL pin. To reach `RPI-RP2`, use the serial REPL sequence in the recovery guide above, or the physical BOOTSEL button on the RP2040 module inside the enclosure.

---

## What's in This Package

| File / Folder | Description |
|---------------|-------------|
| `deploy.sh` | Install script for macOS/Linux |
| `deploy.ps1` | Install script for Windows PowerShell |
| `code.py` | Main firmware entry point |
| `boot.py` | Startup configuration |
| `config.json` | Default settings (STD10) |
| `config-mini6.json` | Default settings (Mini6) |
| `core/` | Firmware modules |
| `devices/` | Hardware definitions |
| `fonts/` | Display fonts |
| `lib/` | CircuitPython libraries |
| `VERSION.txt` | Firmware version identifier |
