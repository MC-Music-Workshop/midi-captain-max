${NOTES}

## Installation

**Back up first.** Mount the device (hold Button 1 / KEY0 while plugging in USB if it doesn't appear) and copy its entire contents somewhere safe, so you can recover or revert to OEM firmware later.

Then download from the Assets below:

- The Config Editor installer for your OS — `.dmg` (macOS), `.exe` / `.msi` (Windows), `.AppImage` / `.deb` (Linux). **It bundles the firmware, so no separate firmware download is needed.**
- Or `MIDI-Captain-MAX-${VERSION}-complete.zip` if you want the firmware and deploy scripts separately (command line, or an OS the GUI doesn't support).

**Updating an existing MIDI Captain MAX install:** open the Config Editor, scroll to **Firmware Installation** at the bottom, and click **Install Firmware**. Your `config.json` is preserved unless you enable **Reset config.json to bundled defaults**.

**First install on OEM firmware, CircuitPython version errors (2026-batch devices), the deploy script, and recovery:** see the full [Installation Guide](https://mc-music-workshop.github.io/midi-captain-max/docs/installation).
