# Saving and Loading Configs

The Config Editor can open, edit, and save configs on your computer with no MIDI Captain connected, and send any of them to a device later.

## What you're working on

The editor always works on exactly one thing, shown in the header:

- **Device**: the config loaded from a connected MIDI Captain.
- **File**: a config file on your computer.
- **New config**: a fresh config that hasn't been saved yet.

A **●** next to the name means what you're working on doesn't have your latest edits yet.

**Loading** changes what you're working on. **Saving** never does, except the first save of a new config, which becomes the file or device you saved it to.

## Buttons

| Button | What it does |
|---|---|
| **Load from File…** | Opens a config file. Asks first if you have unsaved edits. |
| **New Config…** | Asks for a device model and starts from that model's default config. |
| **Save to File…** | Saves to a file you choose, starting in `Documents/MIDICaptainMAX/configs`. |
| **Save to File** | Overwrites the file you're working on (only shown when working on a file). |
| **Save to Device** | Writes to the selected device. The ▾ menu chooses whether it also restarts the device. |
| **Reload from Device** / **Reload from File** | Discards your edits and re-reads from that source. Asks first. |

`⌘S` (`Ctrl+S` on Windows and Linux) runs the save that matches what you're working on: **Save to Device** for a device, **Save to File** for a file, **Save to File…** for a new config.

## Common tasks

**Edit with no device attached:** click **Load from File…** (or **New Config…**), edit, then **Save to File**.

**Back up a device's config:** with the device loaded, click **Save to File…**. The device stays open and the ● stays on if you have unsent edits.

**Send a file to a device:** load the file, plug in the device, then click **Save to Device**. You stay on the file. If the device is a different model than the config, the editor asks before writing.

**Two devices connected:** picking a device in the header loads it. To save a file to the second device, pick that device first, then load the file.

## Unplugging a device

Your edits stay open. **Save to File…** still works, and **Save to Device** comes back when the device reconnects. Plugging a device in never replaces a file or unsaved edits you have open.
