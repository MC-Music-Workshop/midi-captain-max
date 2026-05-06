${NOTES}

## First: Backup!

*Before doing any of this, if you haven't already, please back up your existing config and firmware to a safe place* for recovery or to revert to OEM firmware:

1. Mount the device to your computer. You may have to hold down Button 1 / KEY0 to force it to mount.
2. Copy all contents of the device to a safe place on your computer.

# Installation

Once MIDI Captain MAX is installed, manual firmware updates are no longer needed. The GUI Config Editor now includes a **Firmware Installation** section at the bottom of the window. It shows the currently installed firmware version and the bundled version available to install.

You can download either:

- The appropriate Config Editor installer for your OS: `.dmg` for macOS, `.exe` or `.msi` for Windows. **The Config Editor includes the bundled firmware, so you don't need to download it separately**, or
- The `MIDI-Captain-MAX-v1.10.0-complete.zip` package if you want the GUI and the firmware as separate packages.<br>For example, if you need to use the deploy script for the first install, or for an unsupported OS, this package includes everything you need. (The GUI still includes the bundled firmware; the zip is just for convenience if you want to use the deploy script instead of the GUI installer.)

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
