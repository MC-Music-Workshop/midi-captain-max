# Config Editor Agent Instructions

The config editor is a desktop app built with **SvelteKit 5 + Tauri 2 (Rust backend)** at `config-editor/`.

## Tech Stack

- **Frontend**: SvelteKit 5 (Svelte 5 runes mode), TypeScript, Vite
- **Desktop shell**: Tauri 2 — Rust backend handles file I/O, device detection
- **State**: Svelte stores (`formStore.ts` for form state, `stores.ts` for UI/device state)
- **Build requires `svelte-kit sync`** before `vite build` — generates `.svelte-kit/tsconfig.json`. The `build` npm script includes this.

## Key Files

| Path | Purpose |
|------|---------|
| `src/routes/+page.svelte` | App shell: device selector, save/reload/reset, ⌘S shortcut |
| `src/lib/formStore.ts` | Form state, undo/redo history (50 items), `updateField`, `normalizeConfig`, `loadConfig` |
| `src/lib/stores.ts` | UI state: devices, selectedDevice, hasUnsavedChanges, isLoading |
| `../config.schema.json` | JSON Schema (draft-07) — single source of truth for the config format |
| `src/lib/types.generated.ts` | Auto-generated TypeScript types from `config.schema.json` (run `npm run generate:types`) |
| `src/lib/types.ts` | Re-exports generated types + UI-only types |
| `src/lib/validation.ts` | Client-side validators; `validateConfig()` called before every save |
| `src/lib/api.ts` | Tauri `invoke()` wrappers for all IPC calls |
| `src/lib/components/ConfigForm.svelte` | Toolbar (Undo/Redo/View JSON/Save), keyboard shortcuts |
| `src/lib/components/ButtonRow.svelte` | Per-button fields; uses `onUpdate` callback prop |
| `src/lib/components/ButtonsSection.svelte` | Iterates buttons, wires `handleButtonUpdate → updateField` |
| `src/lib/components/DisplaySection.svelte` | Display text size settings |
| `src-tauri/src/config.rs` | Rust config structs + validation; must mirror `config.schema.json` |
| `src-tauri/src/commands.rs` | Tauri commands: read/write/validate config, restart device, path security |
| `src-tauri/src/device.rs` | USB device detection and watcher (cross-platform) |
| `src-tauri/src/installer.rs` | Firmware installer (mirrors `deploy.sh` copy order) |

## Save Flow

```
ButtonRow/DeviceSection/etc. → onUpdate(field, value)
  → ButtonsSection.handleButtonUpdate(idx, field, value)
    → formStore.updateField(`buttons[${idx}].${field}`, value)
      → setNestedValue() mutates config clone in formState
      → validate() re-runs client-side validation
      → debounced pushHistory() (500ms) for undo/redo

Save button → saveToDevice()
  → validate()
  → normalizeConfig(get(config))   ← strips type-irrelevant fields
  → JSON.stringify()
  → writeConfigRaw(path, json)     ← Tauri IPC
    → Rust: validate_device_path() + verify_device_connected()
    → serde_json::from_str() → MidiCaptainConfig
    → config.validate()
    → serde_json::to_string_pretty() → fs::write() + sync_all()
```

## Schema-Driven Config Types (CRITICAL)

**Single source of truth**: `config.schema.json` at the repo root defines every config field. When adding or changing a config field:

1. **Edit `config.schema.json`** — only place where config format is defined
2. **Regenerate TypeScript types**: `cd config-editor && npm run generate:types` — produces `src/lib/types.generated.ts`
3. **Update the Rust struct** in `src-tauri/src/config.rs` — add the field with `#[serde(skip_serializing_if = "Option::is_none")]`
4. **Update Python firmware** in `firmware/dev/core/config.py` if used at runtime

**CI validates** all `firmware/dev/config*.json` files pass the schema, and that `types.generated.ts` is up to date.

**Serde drops unknown fields silently** — if a field exists in TypeScript but not in the Rust struct, it is deserialized away and the re-serialized output omits it. Round-trip tests in `config.rs` catch this.

**The schema `title` field is load-bearing.** `json-schema-to-typescript` derives the root TypeScript interface name from `title` (PascalCased). Changing the title renames the interface and breaks every import in `types.ts`. Keep the title short and stable.

## Config Normalization

`normalizeConfig()` in `formStore.ts` is called at save time. It strips type-irrelevant fields per button type:
- `cc`: keeps `cc`, `cc_on`, `cc_off`
- `note`: keeps `note`, `velocity_on`, `velocity_off`
- `pc`: keeps `program`, `flash_ms` (only when `mode` is `flash` or unset)
- `pc_inc`/`pc_dec`: keeps `pc_step`, `flash_ms` (only when `mode` is `flash` or unset)

Also strips `display: {}` if no display fields were set.

## `setNestedValue` Path Format

`updateField` uses dot-notation paths with array index notation:
- `buttons[0].label` — button field
- `buttons[0].states[1].cc` — state override field
- `encoder.push.cc_on` — nested object field
- `display.button_text_size` — top-level optional object

**Gotcha**: throws if any intermediate path segment is `undefined` or `null`. `loadConfig` initializes `display: {}` even when the config JSON has no `display` field, so the path is always traversable.

## Validation Notes

Key constraints from `config.schema.json`:
- **Button labels**: max 6 chars, pattern `[\w \-]+`
- **Encoder/expression labels**: max 8 chars
- **Channels**: 0-15 (displayed 1-16)
- **MIDI bytes** (cc, note, program, velocity, etc.): 0-127
- **pc_step**: 1-127; **keytimes**: 1-99; **flash_ms**: 50-5000

**Cross-field rules** (enforced by Rust + `tests/test_config_cross_fields.py`):
- Button array length must match device type (std10=10, mini6=6, nano4=4, duo2=2, one1=1)
- Encoder and expression are STD10-only
- `encoder.initial` must be in `[encoder.min, encoder.max]`
- `expression.max >= expression.min`
- `states.length` should match `keytimes` when `states` is present

## `mode` vs `off_mode`

- **`mode` (toggle/momentary/flash/select/keytimes)**: applies to CC, Note, and PC types. For PC types, MIDI is always sent on press regardless of mode. Flash option only appears for PC types in the GUI.
- **`off_mode` (dim/off)**: LED appearance when button is "off" — applies to non-keytimes modes only.

## `mode: "keytimes"` (#48)

The keytimes mode is rendered by `KeytimesEditor.svelte`, which composes per-cycle editors and `KeytimesMessageEditor.svelte` for individual Message entries. When a button is in keytimes mode:

- The legacy CC/Note/PC/HID per-button fields are hidden in `ButtonRow.svelte` (they don't apply — message data lives inside `short[].down[]` / `up[]` Message objects)
- The Type selector is still shown but has no effect (it's used by other modes)
- The legacy `keytimes` spinner is hidden (deprecated in favor of `short[]`/`long[]` array lengths)
- `off_mode` is hidden (color/dim live per cycle entry instead)
- `KeytimesEditor` renders threshold input, short cycle entries, long cycle entries

Mutations on the nested structure (add/remove entry, add/remove message, change message type) go through dedicated `formStore` helpers (`addKeytimesEntry`, `removeKeytimesEntry`, `addKeytimesMessage`, `removeKeytimesMessage`, `setKeytimesMessageType`) because `updateField()` requires intermediate path components to already exist. Leaf-value edits (color, dim, label, individual message field values) use `updateField()`.

`normalizeButton` strips legacy per-type fields when `mode === 'keytimes'` so save output stays clean even if the button was toggled through other modes before settling on keytimes. For non-keytimes modes, it strips the `short`/`long`/`long_press_threshold_ms` fields.

## Accessibility Conventions

The config editor is held to **0 svelte-check warnings**. When adding form controls:

- Every `<label>` must associate with its control via `for`/`id` pairing, or wrap-style.
- For multi-instance components, derive unique IDs from the prop index. `ButtonRow` exposes `fieldId(field)` and `stateFieldId(si, field)` helpers — use them when adding fields.
- Use Svelte 5 event syntax: `onclick`, `onblur`, `onchange` — never `on:click` etc.
- Modal dialogs need `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, `tabindex="-1"`, and an Escape key handler.
- Backdrops need `role="presentation"` + `tabindex="-1"` + an `onkeydown` handler.

## Serial Soft-Reboot

`restart_device` sends Ctrl-C (`0x03`) + Ctrl-D (`0x04`) over serial to trigger a CircuitPython soft reload. The USB drive stays mounted — no eject or power cycle needed.

- **Port discovery**: Filters by Adafruit VID (`0x239A`). Requires exactly one Adafruit device connected.
- **macOS cu.*/tty.* deduplication**: Each USB serial device appears as both `/dev/cu.*` and `/dev/tty.*`. Code deduplicates by preferring `cu.*` (doesn't block waiting for carrier detect).
- **Timing**: 500ms delay between Ctrl-C and Ctrl-D. Verified on macOS; VM USB passthrough adds unreliable latency.
- **Serial port busy**: If another program has the port open, the open will fail. Frontend shows manual restart instructions as fallback.

## Eject Device

`eject_device` safely unmounts the device volume:
- **macOS**: `diskutil eject`
- **Linux**: `gio mount -u` with `umount` fallback
- **Windows**: PowerShell `Shell.Application` COM object `.InvokeVerb("Eject")`

## Firmware Installer (`installer.rs`)

Mirrors `deploy.sh`'s copy order. Key rules:

- **Use `#[command] async fn`** plus `tauri::async_runtime::spawn_blocking` for filesystem/USB work — sync commands on the IPC thread peg the UI and stall `Channel<T>` event delivery to JS.
- **Stale-delete + same-stem `.py`/`.mpy` dedupe MUST run before copies** in managed dirs (`core/devices/fonts/lib`). A partial-install crash with old order caused silent fallthrough to incompatible alternates.
- **Don't `sync_all` the manifest (`firmware.md5`).** `fsync` on the USB MSC volume can hang for tens of seconds while CircuitPython is at REPL. The manifest is non-safety-critical; bare `fs::write` is correct.
- **Manifest reflects what's on the device, not what's in the bundle.** Build `final_manifest` during plan execution from Copy/Skip ops only; for `config_preserved` cases hash the actual on-device `config.json`.
- **Pre-flight halt is best-effort.** `commands::halt_and_disable_autoreload` is wrapped in `let _ =` — serial port may be held by `tio`/`screen`, and `boot.py` already disables autoreload.
- **The manifest skip is only trustworthy for files the installer alone writes.** `firmware.md5` goes stale whenever anything else writes the device: editor saves (`write_config` never touches the manifest), hand edits, and `deploy.sh`/`deploy.ps1` (which hash the *repo* dev dir, not the device). The active `config.json` is therefore exempt from the same-hash skip — the plan only includes it when it's missing or the user asked for a reset — and its manifest entry keys off the device-specific template actually copied (`config_source_name(device_type)`), not `rel`. Other files still trust the manifest, so a hand-edited `code.py` survives a reinstall of the same version. Deleting `firmware.md5` on the device is the escape hatch that forces a full install.
- **Reset can't rescue a `config.json` with a broken `device` field.** `detect_device_type` reads the current on-device config to pick which template to copy, so a corrupt/device-less config fails the install before the reset happens.

## Device Snapshots Go Stale (`+page.svelte`, `device.rs`)

`DetectedDevice` is a point-in-time snapshot: `has_config` is a one-shot `exists()` at scan time (`device.rs`). A device re-detected mid-mount — which happens routinely during the post-install soft reboot — can freeze `has_config: false` into the selected-device store for the rest of the session.

- **Never gate a user-initiated read on `snapshot.has_config`.** It turned the Reload button into a silent no-op (no error, no status change). Attempt the read and let a missing file error into the footer. `selectDevice` still gates on it (lower risk: its snapshot is usually fresh from a click, and it reports "No config.json found").
- **The post-install auto-reload races the device reboot.** The install command initiates the soft reboot *before* returning, so `onInstalled → reloadFromDevice` can read during the remount window; a lost race leaves stale form state with only a footer status message. When the GUI contradicts the device, read `/Volumes/MIDICAPTAIN/config.json` directly to see which side is wrong.

## Reflash CircuitPython / Bootloader Entry (`enter_bootloader`, `ReflashCircuitPython.svelte`)

Drives a device into RP2040 ROM bootloader mode over serial (`microcontroller.on_next_reset(RunMode.UF2)` + `reset()`), then copies the bundled CP 7.3.1 `.uf2`.

- **The reset drops USB mid-command — serial-entry errors are NOT failures.** `reset()` kills the USB connection while the serial write/flush is still in flight, so `enter_bootloader` routinely returns an error ("Device was disconnected") even when entry *succeeded*. Don't dead-end the flow on it: fall through to polling for the `RPI-RP2` mount, which is the real source of truth. Escalate to an error only if no bootloader mount appears within the watchdog window.
- **Reflashing the `.uf2` reformats the CIRCUITPY filesystem** — `code.py`, `config.json`, `lib/` are all wiped. The intended recovery flow is reflash CP → then reinstall MCM via Install Firmware. Back up custom `config.json` first.
- **CTA wiring for the #132 refusal**: the CP-version preflight (`installer.rs`) stamps `CP_VERSION_UNSUPPORTED_CODE` ("cp_version_unsupported") into `ConfigError.details[0]`. `FirmwareInstaller.svelte` matches that code (not the human message) to surface the reflash CTA at the error. `details` is otherwise unused by the install path — it's the machine-signal channel.

## Page Templates (`templates.rs`, #15 P4d)

Templates are host-side JSON files, one bare `Page` object per file (no
`pages`/`device` wrapper — D7). Import checks device *shape* only (button
count, encoder/expression capability — D9); value problems (out-of-range jump
targets, etc.) import fine and surface as normal in-editor validation errors.

- **Default folder is `~/Documents/MIDICaptainMAX/templates`** (resolved via
  `document_dir()`, created on demand) — under Documents, not the hidden
  app-data dir, so users can manage templates in Finder. A sibling
  `MIDICaptainMAX/pages/` folder is created alongside, reserved for saved
  pages.
- **Accepted security tradeoff (recorded 2026-07-13):**
  `export_page_template` / `import_page_template` accept arbitrary
  user-chosen paths over IPC *without* `validate_device_path` — "save/load
  anywhere via the native file picker" is the feature (D8). This means a
  hypothetically compromised webview could read/overwrite any user-writable
  file, unlike every other path-taking command, which is device-scoped. Risk
  accepted because the webview only ever loads bundled content. If hardening
  is ever wanted, move the save/open dialogs into Rust
  (`tauri_plugin_dialog`'s Rust API) so the chosen path never crosses IPC.
- Template IO is Rust `std::fs`, so it needs **no** JS `fs` capability; the
  JS-side pickers are covered by `dialog:default` (already grants
  `allow-save`/`allow-open` in tauri-plugin-dialog 2.6.0 — do not add scope
  entries to `capabilities/default.json` unless a future plugin version drops
  them).

## Tauri Windows Installer

`tauri.conf.json` `bundle.windows.nsis.installMode`:
- `"perUser"` (default): installs to `AppData` — hard to find
- `"both"`: prompts user to choose per-machine (Program Files) or per-user, defaulting to Program Files

## Running Tests

```bash
cd config-editor/src-tauri
cargo test
```

Requires GTK system libraries on Linux (`sudo apt-get install -y libgtk-3-dev libwebkit2gtk-4.1-dev`). No extra steps on macOS.

**Fresh worktree gotcha:** `cargo test` (and any Tauri build) fails in the build script with `glob pattern resources/circuitpython/*.uf2 path not found` until firmware + the CP `.uf2` are staged into `src-tauri/resources/`. `npm run tauri dev` stages them via a predev hook, but a worktree where you've only ever run `cargo test` won't have them. Fix: run `tools/bundle-firmware-for-dev.sh` from the repo root once (stages firmware and fetches the pinned `.uf2` via `tools/fetch-cp-uf2.sh`; both idempotent).

`test_roundtrip_all_shipped_configs` parses every `firmware/dev/config*.json` file and round-trips through the typed Rust struct — catches "struct missing a field" silent data loss without needing a per-feature test.

Also run:
```bash
cd config-editor && npm run check        # TypeScript / Svelte
cd config-editor && npm run generate:types   # regenerate types from schema
```
