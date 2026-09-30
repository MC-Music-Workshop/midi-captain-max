# Issue #36: Save/Load Configs With No Device Attached

**Issue:** [#36](https://github.com/MC-Music-Workshop/midi-captain-max/issues/36) (relates to [#17](https://github.com/MC-Music-Workshop/midi-captain-max/issues/17) Saved Config Library)

**Branch:** `36-saved-configs`

**Goal:** the config editor can open, edit, and save config files on the computer with no MIDI Captain connected, and save any of them to a connected device later.

---

## Decisions (locked 2026-09-29, recorded on the issue)

| # | Decision |
|---|----------|
| D1 | **Scope:** #36 plus a default folder. Files load and save through the native file picker, defaulting to `~/Documents/MIDICaptainMAX/configs/`. The in-app "View Library" browser stays in #17. |
| D2 | **What you're working on:** the editor always works on exactly one thing: a device, a file, or a new unsaved config. The header shows which one. |
| D3 | **Load vs. save:** loading changes what you're working on. Saving never does, except the first save of a new config, which becomes the file or device it was saved to. |
| D4 | **Labels say where:** every button names its target, for example **Save to Device**, **Save to File**, **Load from File…**, **Reload from Device**. There's no bare "Save", "Reload", or "Send". |
| D5 | **Unsaved dot:** it means "what you're working on doesn't have these edits yet." Saving to the other side, for example a backup to a file while working on the device, leaves it on. |
| D6 | **Starting with no device:** **Load from File…** opens an existing file. **New Config…** asks for a device type and starts from that device's bundled default config. |
| D7 | **Unplugging the device:** the form stays open with unsaved edits. **Save to File…** still works, and **Save to Device** comes back when the device reconnects. |
| D8 | **Device type mismatch:** saving a config to a device of a different type is blocked. |
| D9 | **Drop `pages/`:** the unused `~/Documents/MIDICaptainMAX/pages/` folder is no longer created. Done in `e079fe1`. |

## What Each Button Does

"Selected device" is the one in the header's device picker. When you're working on a device, that's the device you're working on.

| Button | Working on a device | Working on a file | Working on a new config | Enabled when |
|---|---|---|---|---|
| **Save to Device** (split button: **Save to Device & Restart**) | Writes to the device. Clears the dot. | Writes to the selected device. You stay on the file, and the dot is unchanged. | Writes to the selected device. You're now working on that device. | A device is selected and connected, and its type matches (D8) |
| **Save to File** | *(hidden)* | Overwrites the file. Clears the dot. | *(hidden)* | Working on a file |
| **Save to File…** | Saves a copy to a file you choose. You stay on the device, and the dot is unchanged. | Saves a copy to a file you choose. You stay on the original file. | Saves to a file you choose. You're now working on that file, and the dot clears. | Always |
| **Load from File…** | Asks before discarding unsaved edits, then you're working on the chosen file. | Same | Same | Always |
| **Reload from Device** | Asks before discarding unsaved edits, then re-reads the device. | Asks before discarding unsaved edits, then you're working on the selected device. | Same as working on a file | A device is selected and connected |
| **Reload from File** | *(hidden)* | Asks before discarding unsaved edits, then re-reads the file from disk. | *(hidden)* | Working on a file |
| **New Config…** | Asks before discarding unsaved edits, then asks for a device type. You're now working on a new config. | Same | Same | Always |
| **Picking a device in the picker** | Same as **Reload from Device** for that device | Same | Same | A device is connected |

- **⌘S** runs **Save to Device** when you're working on a device, **Save to File** when you're working on a file, and **Save to File…** when you're working on a new config. The main toolbar button shows that label, and the other saves stay available next to it.
- **The Save to Device & Restart split button** only applies to **Save to Device**. The file saves have no menu.
- **Restart Device** and **Eject** act on the selected device, as they do today.

### Device Events

| Event | What happens |
|---|---|
| Device connects, nothing open | Auto-select it and load its config, as today. |
| Device connects, something already open | Auto-select it if nothing is selected, so **Save to Device** has a target. **Don't load it.** Report it in the status bar. |
| The device you're working on reconnects | Turn **Save to Device** back on. Don't reload over unsaved edits. |
| The device you're working on disconnects | Keep the form and its edits. You're still working on that device. **Save to Device** is disabled with a "device disconnected" hint, and **Save to File…** still works. Remove today's "unsaved changes have been lost" dialog. |

## Open Questions (confirm before or during implementation)

- **Q1: How do we check the device type (D8) when the device has no readable `config.json`?** The only way to tell a device's model is the `device` field in its current `config.json`, the same thing `installer.rs::detect_device_type` reads. Proposed: if it's missing or unreadable, ask the user to confirm the model before saving, using the same model picker the installer shows for `DEVICE_TYPE_UNKNOWN_CODE`.
- **Q2: Keyboard shortcuts beyond ⌘S?** Proposed: none for now (YAGNI). ⌘O and ⇧⌘S can be added later.
- **Q3: Several devices connected while working on a file.** Picking a device in the picker loads it, the same as today, so it replaces the file you're working on. To save a file to a second device, you'd pick that device first and then load the file. Proposed: accept this for now, since several connected devices is rare.

---

## Findings From the Current Code

- **The editor only renders when a device is selected.** `+page.svelte` gates the whole form on `$selectedDevice && !$isLoading`. Save, Reload, Restart, and Eject all assume a device.
- **Device config commands are device-scoped by design.** `read_config_raw` and `write_config_raw` in `commands.rs` call `validate_device_path`, and the write also calls `verify_device_connected`. Leave these alone and add separate file commands, the same way page templates did (P4d, D8).
- **Page templates already handle host-side file IO.** `templates.rs` reads and writes arbitrary picker-chosen paths with `std::fs`, and `AGENTS.md` records that security tradeoff as accepted. The JS file pickers are covered by `dialog:default`, so no capability change is needed.
- **`hasUnsavedChanges` is never set to `true`.** The store in `stores.ts` only ever gets `false`, which makes every guard that checks it dead code: the discard prompt on device switch, the eject warning, the disconnect warning, and the installer's check. The real dirty flag is `formStore.isDirty`. **Separately, a successful save never clears `isDirty`**, so the Save button keeps its ` *` after saving. The unsaved dot (D5) depends on one correct dirty flag, so fix both here.
- **Connecting a device auto-loads its config.** The `onDeviceConnected` handler reads and loads the device's config when it's the only device, or when it was the one selected before. With files in play, that would overwrite an open file or unsaved edits without asking.
- **Bundled default configs already exist.** `resources/firmware/config*.json` ships with the app, and `installer.rs::config_source_name(DeviceType)` maps each device type to its file. **New Config…** can reuse that lookup.
- **Opened files need the pages migration.** `read_config_raw` runs `config::migrate_to_pages` so pre-pages configs load. The file-open command has to do the same.
- **The device type is already editable offline.** `formStore.setDevice` resizes the buttons on every page, so a config for any device can be edited with nothing attached.

---

## Design

### What You're Working On

A new store in `stores.ts` records what the editor is working on:

```ts
export type WorkingOn =
  | { kind: 'device'; device: DetectedDevice }   // loaded from a device
  | { kind: 'file'; path: string }               // loaded from (or first saved to) a local file
  | { kind: 'new' };                             // New Config…, never saved

export const workingOn = writable<WorkingOn | null>(null); // null = nothing open
```

- The form renders whenever `$workingOn !== null`, not only when a device is selected.
- `selectedDevice` stays as the device picker's selection and is what **Save to Device**, **Restart Device**, and **Eject** act on. When you're working on a device, the two are the same device.
- The header shows what you're working on (the device name, the file name, or **New config**), plus the unsaved dot.
- With nothing open, the empty state shows **Load from File…** and **New Config…**, plus the existing "connect a device" hint.
- **Save to File…** opens its dialog in `configs/`. When you're working on a file, the dialog starts on that file. Otherwise it suggests a name based on the device type.

### One Dirty Flag

- Remove `hasUnsavedChanges` from `stores.ts` and use `formStore.isDirty` everywhere (`+page.svelte`, and the `FirmwareInstaller` prop).
- Add `markSaved()` to `formStore`, which sets `isDirty = false` and keeps the undo history. Call it only after a save to what you're working on (D5), not after a save to the other side.
- Every load goes through one `confirmDiscard()` helper, which uses the async `ask()` dialog instead of `window.confirm()`.

### Shared Save Steps

Pull the steps every save runs out of `saveToDevice` into one helper: blur the focused field, run `validate()`, run `validateAllPages()`, then `normalizeConfig()` and `JSON.stringify()`.

### New Rust Commands (`config_files.rs`, next to `templates.rs`)

| Command | Behavior |
|---|---|
| `configs_dir()` | Returns `~/Documents/MIDICaptainMAX/configs` and creates it if needed. Shares a `mcm_documents_root()` helper with `templates::templates_dir` so the root isn't duplicated. |
| `open_config_file(path)` | `fs::read_to_string`, then `migrate_to_pages`, then pretty JSON. Same as `read_config_raw` without the device-path check. |
| `save_config_file(path, json)` | Parses into `MidiCaptainConfig`, runs `config.validate()`, then writes pretty JSON (same checks as `write_config_raw`, minus the device checks). No `sync_all`: this is a local disk, not a USB MSC volume. |
| `default_config(device)` | Reads `bundled_firmware_dir()/config_source_name(device)` (making both `pub(crate)`), then `migrate_to_pages`, then JSON. |

- `open_config_file` and `save_config_file` take any picker-chosen path, the same accepted tradeoff as page templates. Record it in `config-editor/AGENTS.md` next to the templates note.
- Register the commands in `lib.rs` and add wrappers in `api.ts`.
- **Save to Device's type check (D5):** a small `device_config_type(device_path)` command that returns the `device` field from the device's current `config.json`, or `null`. This can reuse `installer::detect_device_type` (made `pub(crate)`).

---

## Implementation Tasks

1. **Rust file commands.** Add `config_files.rs` with the commands above, plus unit tests using `tempfile`:
   - A file written with `save_config_file` opens back unchanged.
   - An invalid config fails to save.
   - A legacy flat config opens migrated to pages.
   - `default_config` round-trips for every `DeviceType`. Split it into a path-taking inner function that the test runs against `firmware/dev/`, which is where the bundled configs come from. `test_roundtrip_all_shipped_configs` already reads that folder.
2. **Single dirty flag.** Add `markSaved()` to `formStore`, remove `hasUnsavedChanges`, and update its callers. Add `formStore.test.ts` cases showing that `markSaved` clears `isDirty` and that later edits set it again.
3. **`workingOn` store and empty state.** Add the store, change the form's render condition, and add the **Load from File…** and **New Config…** empty-state buttons, including the device-type prompt for New Config.
4. **Buttons and labels.** Build every row of the "What Each Button Does" table:
   - Pull out the shared save steps.
   - Wire ⌘S and the main toolbar label to what you're working on.
   - Limit the **Save to Device & Restart** split button to **Save to Device**.
   - Rename the footer's **Reload** button to **Reload from Device** or **Reload from File**, depending on what you're working on.
5. **Device type check.** Add the D8 check to **Save to Device** (including the Q1 fallback), reusing the existing device write and restart path.
6. **Device events.** Implement the Device Events table.
7. **Header.** Show what you're working on, plus the unsaved dot.
8. **Docs.**
   - `config-editor/AGENTS.md`: update the Save Flow diagram and key files, add the file-IO security note, and add a short section on what the editor is working on, linking this plan's button table.
   - `docs/user/`: how to load and save configs with no device, plus the `configs/` folder in the "First Run" section of `installation.md`.
9. **Verify.** Run `./tools/test-all.sh`, `npm run check` (0 warnings), and a manual pass in `npm run tauri dev`:
   - With no device: New Config…, then Save to File…, then Load from File….
   - Plug in a device: its config is not loaded over the open file. Save to Device works, and a device-type mismatch is blocked.
   - Working on the device: Save to File… keeps the dot on, and Reload from Device asks before discarding.
   - Unplug the device with edits: the edits are kept and can be saved to a file.

## Out of Scope

- The in-app library browser, list view, or "View Library" (#17).
- Recent-files list, ⌘O / ⇧⌘S (Q2).
- Moving the file dialogs into Rust to harden the IPC path boundary (noted as an option in `AGENTS.md`).
