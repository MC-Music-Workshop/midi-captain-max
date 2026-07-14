${NOTES}

## First: Backup!

*Before doing any of this, if you haven't already, please back up your existing config and firmware to a safe place* for recovery or to revert to OEM firmware:

1. Mount the device to your computer. You may have to hold down Button 1 / KEY0 to force it to mount.
2. Copy all contents of the device to a safe place on your computer.

# Installation

Once MIDI Captain MAX is installed, manual firmware updates are no longer needed. The GUI Config Editor now includes a **Firmware Installation** section at the bottom of the window. It shows the currently installed firmware version and the bundled version available to install.

You can download either:

- The appropriate Config Editor installer for your OS: `.dmg` for macOS, `.exe` or `.msi` for Windows, `.AppImage` (portable) or `.deb` (Debian/Ubuntu) for Linux. **The Config Editor includes the bundled firmware, so you don't need to download it separately**, or
- The `MIDI-Captain-MAX-${VERSION}-complete.zip` package if you want the GUI and the firmware as separate packages.<br>For example, if you prefer the deploy script, or are on an unsupported OS, this package includes everything you need. (The GUI still includes the bundled firmware; the zip is just for convenience if you want to use the deploy script instead of the GUI installer.)

## Updating an Existing MIDI Captain MAX Install

1. Connect your MIDI Captain via USB and power it on.
   - The device may mount as `CIRCUITPY` or `MIDICAPTAIN`.
   - If no drive appears, hold switch 1 / KEY0 while plugging in USB.
2. Install and open the MIDI Captain MAX Config Editor.
3. Scroll to the **Firmware Installation** section at the bottom of the app window.
4. Click **Install Firmware**.

By default, the installer preserves your existing `config.json`. Enable **Reset config.json to bundled defaults** only if you want to overwrite your current settings with the default template.

The app will copy the firmware, reload the device, and update it in place.

## First Run of the Config Editor

The first time you use the page-template feature (**Edit Pages… → Save as template… / Add from template…**), the editor creates a folder in your Documents:

- `Documents/MIDICaptainMAX/templates`: your saved page templates. The save dialog and the template picker both point here by default.
- `Documents/MIDICaptainMAX/pages`: reserved for saved pages.

Templates are plain JSON files, one page each — feel free to back them up, rename them in Finder/Explorer, or share them with other MIDI Captain users.

## First Run on OEM Firmware

If your MIDI Captain is still running the factory Paint Audio firmware, the Config Editor may show `OEM (no VERSION.txt file)`.

The deploy script is no longer required — the entire first install can be done from the Config Editor. The installer only needs to know your device type, and you tell it that by saving a config from the editor first:

1. Hold Button 1 / KEY0 while plugging in USB to enter the OEM USB settings mode. A `MIDICAPTAIN` drive should appear.
2. Open the Config Editor and select the device. Since there's no MAX `config.json` on the drive yet, the editor starts a fresh default config.
3. Set **Device Type** to your model and click **Save to Device**.
4. Scroll to the **Firmware Installation** section and click **Install Firmware**. For a first install, enable **Reset config.json to bundled defaults** so you start from the full default template for your device.
   - If the button blocks with a CircuitPython version error, see the next section, then come back.

### If the Config Editor shows a CircuitPython version error (2026-batch devices)

2026-batch devices shipped with CP 9.2.7. The **Install Firmware** button will block with a version error. Fix this first:

1. In the **Firmware Installation** section, open **Advanced / Recovery**.
2. Click **Reflash CircuitPython 7.3.1**. The editor sends a command over serial, reboots the device into its RP2040 bootloader, copies the bundled `.uf2`, and waits for `CIRCUITPY` to remount — no physical button hold needed.
3. Once `CIRCUITPY` remounts, continue with the first-install steps above (the device is already mounted; skip step 1).

If the editor can't reach the device over serial, see the [manual bootloader entry guide](https://github.com/MC-Music-Workshop/midi-captain-max/blob/main/docs/recovery-bootloader-entry.md) (doc pending)

### Deploy script (alternative)

Prefer the command line, or on an OS the GUI doesn't support? The deploy script still performs a full first install:

1. Hold Button 1 / KEY0 while plugging in USB to enter the OEM USB settings mode. A `MIDICAPTAIN` drive should appear.
2. Download and extract `MIDI-Captain-MAX-${VERSION}-complete.zip` from the Assets section below.
3. Run the included deploy script once with your device type:
   <br>_NOTE: only enter the desired device type, not the full list of options.
   <br>For example, if you have a Nano 4, run `./deploy.sh --device nano4`_.
   - macOS / Linux: `./deploy.sh --device std10|mini6|nano4|duo2|one1`
   - Windows PowerShell: `.\deploy.ps1 -Device std10|mini6|nano4|duo2|one1`
   - Windows cmd (if PowerShell blocks unsigned scripts): `deploy.bat -Device std10|mini6|nano4|duo2|one1` — invokes `deploy.ps1` with a per-process `ExecutionPolicy Bypass`; does not change any system policy.
4. Reconnect the device and open the MIDI Captain MAX Config Editor.
5. From then on, use the **Firmware Installation** section in the app for future updates.

## Recovery

If anything goes wrong, it is fully recoverable:

1. Mount the device.
2. Erase the contents.
3. Restore your backup, or re-run the first-install steps above.
