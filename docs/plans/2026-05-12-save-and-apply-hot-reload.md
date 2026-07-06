# Save & Apply — Hot Reload on Save

**Status:** Shipped — Save & Apply hot reload is in the current editor/firmware.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the "Save to Device" button with a split button whose primary action is **Save & Apply** — write `config.json` to device, then automatically hot-reload (REPL `reload_runtime_config()` via `sys.modules['__main__']`) for runtime fields, or hard-reset (`microcontroller.reset()`) when boot-level fields changed. Secondary actions: **Save** (local file) and **Save to Device, No Reload** (dev-mode only).

**Architecture:**
- Editor diffs old vs new config JSON before save via Rust command `classify_reload`. Boot-level field change → hard reset path. Otherwise → hot reload path.
- Firmware adds `reload_runtime_config()` to `code.py`. Reached over REPL via `sys.modules['__main__'].reload_runtime_config()` — NOT `import code` (would re-execute the whole file as a new module).
- Hard reset uses `import microcontroller; microcontroller.reset()` over serial — full re-enumeration, picks up USB descriptor / drive-name / HID toggle changes without physical power cycle.
- File-flush race already handled by `write_sync` in `commands.rs:232` (calls `file.sync_all()`).
- Existing `restart_device` (Ctrl-C + Ctrl-D soft reboot) is preserved as a manual fallback button but no longer the auto-save path.

**Tech Stack:** Svelte 5 (runes), TypeScript, Tauri 2 (Rust), CircuitPython 7.x, `serialport` crate.

---

## Boot-Level Field List (forces hard reset)

A change to any of these forces `microcontroller.reset()`:

- `usb_drive_name` — set in `boot.py` via `storage.remount(label=...)`; host needs re-enumeration to see new label
- `dev_mode` — `boot.py` decides whether to call `storage.disable_usb_drive()`
- `device` — pin maps and module imports decided at top of `code.py`; safer to fully reset than hot-swap
- HID descriptor toggle — `boot.py` enables HID only if any button has `type:"hid"`. Detection: `any button.type == "hid"` OR `any button.states[*].type == "hid"`. If either side's "has HID" boolean flips, descriptor must rebuild → hard reset. Note: changing a HID button's `hid_key` or `hid_modifier` is **hot**, only the on/off toggle is hard.

Everything else (CC numbers, colors, labels, flash_ms, encoder maps, expression maps, page count, display text) is hot-reloadable.

---

## Task 1: Firmware — `reload_runtime_config()`

**Files:**
- Modify: `firmware/dev/code.py`
- Test: manual on-device — no pytest mock covers full code.py runtime

**Step 1: Locate the globals and the LED/display paint logic**

Run:
```bash
grep -n "^config = load_config\|^buttons = \|^pc_values = \|^pc_flash_timers = " firmware/dev/code.py
grep -n "pixels\[\|pixels.fill\|set_status_text\|display.show\|main_group" firmware/dev/code.py | head -30
```

Note line numbers. Identify:
- The lines that paint each button's idle LED color from `buttons[i]["color"]`
- The lines that paint the display banner from `config`

**Step 2: Extract paint helpers (carefully — leave hardware init alone)**

Create two module-level functions in `code.py`. Move **only the paint lines** that consume `buttons` / `config`. Leave NeoPixel object creation, display object creation, font loading, and any one-time hardware init at the top of the file untouched.

```python
def _refresh_idle_leds():
    """Repaint each button's idle LED color from current `buttons` config."""
    # Move existing per-button idle-color loop here.
    # Reference globals: buttons, pixels, switch_to_led
    ...

def _refresh_display():
    """Repaint display banner from current `config`."""
    # Move existing display banner paint lines here.
    ...
```

Update the original startup sites to call these helpers instead of inlining the logic — single source of truth, exercises the path before reload ever runs.

**Step 3: Add `reload_runtime_config()`**

Place after the helpers, before `while True:`:

```python
def reload_runtime_config():
    """Re-read /config.json and rebuild runtime state without rebooting.

    Called over REPL by the editor's Save & Apply flow when only
    runtime fields changed. Boot-level changes (usb_drive_name, dev_mode,
    device, HID toggle) require microcontroller.reset() instead.
    """
    global config, buttons
    try:
        config = load_config()
        buttons = config["buttons"]
        # Clear in-flight LED flashes — they reference button indices in
        # the old config and would paint stale colors. Keep pc_values
        # intact so users mid-performance don't lose pc_inc/dec state
        # on a color/label edit.
        for i in range(len(pc_flash_timers)):
            pc_flash_timers[i] = 0.0
        _refresh_idle_leds()
        _refresh_display()
        print("Config hot-reloaded")
        return True
    except Exception as e:
        print("Hot reload failed:", e)
        return False
```

**Step 4: Manual on-device smoke test**

1. Deploy: `bash tools/deploy.sh`
2. Open serial: `screen $(ls /dev/cu.usbmodem*) 115200`
3. Ctrl-C to halt, send a sacrificial CRLF, then run:
   `import sys; sys.modules['__main__'].reload_runtime_config()`
   Expected: `Config hot-reloaded` printed, no crash, no reboot.
4. Edit a button color in `config.json` on the mounted drive, save.
5. Re-run the REPL line. Expected: LED color updates, serial stays up, no reboot.

**Step 5: Commit**

```bash
git add firmware/dev/code.py
git commit -m "feat(firmware): add reload_runtime_config() for hot config reload"
```

---

## Task 2: Rust — boot-level diff logic

**Files:**
- Create: `config-editor/src-tauri/src/reload_diff.rs`
- Modify: `config-editor/src-tauri/src/lib.rs` (add `mod reload_diff;`)

**Step 1: Write failing tests + impl**

Create `config-editor/src-tauri/src/reload_diff.rs`:

```rust
use serde_json::Value;

/// Decision returned by `classify_change`.
#[derive(Debug, PartialEq)]
pub enum ReloadKind {
    /// No change detected — caller can skip serial work entirely.
    None,
    /// Runtime-only change — REPL `reload_runtime_config()` is sufficient.
    Hot,
    /// Boot-level change — `microcontroller.reset()` required.
    Hard,
}

/// Returns `Hard` if any boot-level field differs between `old` and `new`,
/// `Hot` if other fields differ, `None` if equal.
pub fn classify_change(old: &Value, new: &Value) -> ReloadKind {
    if old == new {
        return ReloadKind::None;
    }
    if boot_level_differs(old, new) {
        return ReloadKind::Hard;
    }
    ReloadKind::Hot
}

fn boot_level_differs(old: &Value, new: &Value) -> bool {
    for field in ["usb_drive_name", "dev_mode", "device"] {
        if old.get(field) != new.get(field) {
            return true;
        }
    }
    has_hid(old) != has_hid(new)
}

fn has_hid(cfg: &Value) -> bool {
    let Some(buttons) = cfg.get("buttons").and_then(|v| v.as_array()) else {
        return false;
    };
    buttons.iter().any(button_has_hid)
}

fn button_has_hid(btn: &Value) -> bool {
    if btn.get("type").and_then(|v| v.as_str()) == Some("hid") {
        return true;
    }
    let Some(states) = btn.get("states").and_then(|v| v.as_array()) else {
        return false;
    };
    states.iter().any(|s| s.get("type").and_then(|v| v.as_str()) == Some("hid"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn identical_configs_yield_none() {
        let cfg = json!({"device": "STD10", "buttons": []});
        assert_eq!(classify_change(&cfg, &cfg), ReloadKind::None);
    }

    #[test]
    fn button_color_change_is_hot() {
        let old = json!({"device": "STD10", "buttons": [{"label":"1","cc":20,"color":"red"}]});
        let new = json!({"device": "STD10", "buttons": [{"label":"1","cc":20,"color":"blue"}]});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hot);
    }

    #[test]
    fn usb_drive_name_change_is_hard() {
        let old = json!({"usb_drive_name": "MIDICAPTAIN", "buttons": []});
        let new = json!({"usb_drive_name": "MYCAPTAIN", "buttons": []});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hard);
    }

    #[test]
    fn dev_mode_change_is_hard() {
        let old = json!({"dev_mode": false, "buttons": []});
        let new = json!({"dev_mode": true, "buttons": []});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hard);
    }

    #[test]
    fn device_change_is_hard() {
        let old = json!({"device": "STD10", "buttons": []});
        let new = json!({"device": "NANO4", "buttons": []});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hard);
    }

    #[test]
    fn adding_hid_button_is_hard() {
        let old = json!({"buttons": [{"type":"cc","cc":20}]});
        let new = json!({"buttons": [{"type":"cc","cc":20},{"type":"hid","hid_key":"A"}]});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hard);
    }

    #[test]
    fn removing_last_hid_button_is_hard() {
        let old = json!({"buttons": [{"type":"hid","hid_key":"A"}]});
        let new = json!({"buttons": [{"type":"cc","cc":20}]});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hard);
    }

    #[test]
    fn hid_in_state_override_counts() {
        let old = json!({"buttons": [{"type":"cc","cc":20}]});
        let new = json!({"buttons": [{"type":"cc","cc":20,"states":[{"type":"hid","hid_key":"A"}]}]});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hard);
    }

    #[test]
    fn changing_hid_key_while_descriptor_unchanged_is_hot() {
        let old = json!({"buttons": [{"type":"hid","hid_key":"A"}]});
        let new = json!({"buttons": [{"type":"hid","hid_key":"B"}]});
        assert_eq!(classify_change(&old, &new), ReloadKind::Hot);
    }
}
```

**Step 2: Wire module into `lib.rs`**

Add `mod reload_diff;` near other `mod` declarations.

**Step 3: Run tests**

Run: `cd config-editor/src-tauri && cargo test --lib reload_diff`
Expected: 9 tests pass.

**Step 4: Commit**

```bash
git add config-editor/src-tauri/src/reload_diff.rs config-editor/src-tauri/src/lib.rs
git commit -m "feat(editor): add boot-level config diff classifier"
```

---

## Task 3: Rust — `hot_reload_device`, `hard_reset_device`, `classify_reload`

**Files:**
- Modify: `config-editor/src-tauri/src/commands.rs` (add three commands near `restart_device`)
- Modify: `config-editor/src-tauri/src/lib.rs` (register all three in `tauri::generate_handler!`)

**Step 1: Add serial helpers and commands in `commands.rs`**

After `soft_reboot_via_serial`:

```rust
/// Trigger firmware hot reload over REPL — calls `reload_runtime_config()`
/// in the already-running __main__ (code.py). Does NOT re-run boot.py.
/// `code.py` runs as __main__; `import code` would re-execute the whole
/// file as a separate module, so we reach the live function via
/// `sys.modules['__main__']` instead.
pub(crate) fn hot_reload_via_serial(path: &Path) -> Result<(), ConfigError> {
    let mut port = open_device_serial(path)?;

    // Ctrl-C: drop to REPL. CP consumes next byte as the "press any key" prompt.
    port.write_all(&[0x03]).map_err(|e| ConfigError {
        message: format!("Failed to send interrupt: {}", e),
        details: None,
    })?;
    std::thread::sleep(Duration::from_millis(500));

    // Sacrificial CRLF — consumed as the prompt keypress.
    port.write_all(b"\r\n").map_err(|e| ConfigError {
        message: format!("Failed to enter REPL: {}", e),
        details: None,
    })?;
    std::thread::sleep(Duration::from_millis(200));

    // Reach into the running __main__ and call the reload function.
    let cmd = b"import sys; sys.modules['__main__'].reload_runtime_config()\r\n";
    port.write_all(cmd).map_err(|e| ConfigError {
        message: format!("Failed to send reload command: {}", e),
        details: None,
    })?;
    port.flush().map_err(|e| ConfigError {
        message: format!("Failed to flush: {}", e),
        details: None,
    })?;
    std::thread::sleep(Duration::from_millis(300));

    Ok(())
}

/// Hard-reset the MCU via `microcontroller.reset()`. Forces full
/// USB re-enumeration — required for usb_drive_name, dev_mode, device,
/// and HID descriptor changes. ~2s before device reappears on host.
pub(crate) fn hard_reset_via_serial(path: &Path) -> Result<(), ConfigError> {
    let mut port = open_device_serial(path)?;

    port.write_all(&[0x03]).map_err(|e| ConfigError {
        message: format!("Failed to send interrupt: {}", e),
        details: None,
    })?;
    std::thread::sleep(Duration::from_millis(500));

    port.write_all(b"\r\n").map_err(|e| ConfigError {
        message: format!("Failed to enter REPL: {}", e),
        details: None,
    })?;
    std::thread::sleep(Duration::from_millis(200));

    let cmd = b"import microcontroller; microcontroller.reset()\r\n";
    port.write_all(cmd).map_err(|e| ConfigError {
        message: format!("Failed to send reset command: {}", e),
        details: None,
    })?;
    port.flush().map_err(|e| ConfigError {
        message: format!("Failed to flush: {}", e),
        details: None,
    })?;
    // Don't sleep long — port will drop on reset. Port handle drops on
    // function return; serialport crate handles the disconnect.
    std::thread::sleep(Duration::from_millis(50));

    Ok(())
}

#[command]
pub fn hot_reload_device(path: String) -> Result<(), ConfigError> {
    validate_device_path(&path)?;
    let p = Path::new(&path);
    verify_device_connected(p)?;
    hot_reload_via_serial(p)
}

#[command]
pub fn hard_reset_device(path: String) -> Result<(), ConfigError> {
    validate_device_path(&path)?;
    let p = Path::new(&path);
    verify_device_connected(p)?;
    hard_reset_via_serial(p)
}

/// Classify a config change as None / Hot / Hard. Used by the editor
/// to pick reload strategy after writing config.json to the device.
#[command]
pub fn classify_reload(old: serde_json::Value, new: serde_json::Value) -> &'static str {
    use crate::reload_diff::{classify_change, ReloadKind};
    match classify_change(&old, &new) {
        ReloadKind::None => "None",
        ReloadKind::Hot => "Hot",
        ReloadKind::Hard => "Hard",
    }
}
```

**Step 2: Register all three commands in `lib.rs`**

Find `tauri::generate_handler!` and add: `commands::hot_reload_device, commands::hard_reset_device, commands::classify_reload`.

**Step 3: Build**

Run: `cd config-editor/src-tauri && cargo build`
Expected: clean build.

**Step 4: Commit**

```bash
git add config-editor/src-tauri/src/commands.rs config-editor/src-tauri/src/lib.rs
git commit -m "feat(editor): add hot_reload, hard_reset, classify_reload tauri commands"
```

---

## Task 4: TypeScript API wrappers

**Files:**
- Modify: `config-editor/src/lib/api.ts`

**Step 1: Add wrappers next to existing `restartDevice`**

```typescript
export async function hotReloadDevice(path: string): Promise<void> {
  return invoke('hot_reload_device', { path });
}

export async function hardResetDevice(path: string): Promise<void> {
  return invoke('hard_reset_device', { path });
}

export async function classifyReload(
  oldConfig: unknown,
  newConfig: unknown,
): Promise<'None' | 'Hot' | 'Hard'> {
  return invoke('classify_reload', { old: oldConfig, new: newConfig });
}
```

**Step 2: Type-check**

Run: `cd config-editor && npm run check`
Expected: 0 errors.

**Step 3: Commit**

```bash
git add config-editor/src/lib/api.ts
git commit -m "feat(editor): add hotReloadDevice, hardResetDevice, classifyReload api wrappers"
```

---

## Task 5: SplitButton component

**Files:**
- Create: `config-editor/src/lib/components/SplitButton.svelte`

**Step 1: Create the component**

Key fix vs first draft: outside-click handler uses `pointerdown` AND checks whether the target lies inside the menu — otherwise menu items are clicked away before their `click` fires.

```svelte
<script lang="ts">
  interface MenuItem {
    label: string;
    onclick: () => void;
    disabled?: boolean;
    hidden?: boolean;
  }

  interface Props {
    primaryLabel: string;
    primaryOnClick: () => void;
    primaryDisabled?: boolean;
    primaryTitle?: string;
    menu: MenuItem[];
    variant?: 'primary' | 'secondary';
  }

  let {
    primaryLabel,
    primaryOnClick,
    primaryDisabled = false,
    primaryTitle = '',
    menu,
    variant = 'primary',
  }: Props = $props();

  let open = $state(false);
  let rootEl: HTMLDivElement | undefined = $state();
  let menuEl: HTMLUListElement | undefined = $state();

  function toggle() { open = !open; }
  function close() { open = false; }

  // pointerdown so the close fires before the menuitem click; check that
  // the pointer landed outside both the menu and the toggle, otherwise
  // the menuitem click would land on nothing.
  function handlePointerDown(e: PointerEvent) {
    const t = e.target as Node;
    if (rootEl && rootEl.contains(t)) return;
    close();
  }

  function handleKey(e: KeyboardEvent) {
    if (e.key === 'Escape') close();
    if (e.altKey && e.key === 'ArrowDown') { e.preventDefault(); open = true; }
  }

  $effect(() => {
    if (open) {
      document.addEventListener('pointerdown', handlePointerDown);
      return () => document.removeEventListener('pointerdown', handlePointerDown);
    }
  });

  const visibleMenu = $derived(menu.filter(m => !m.hidden));
</script>

<div class="split" bind:this={rootEl} onkeydown={handleKey} role="group">
  <button
    class="primary {variant}"
    onclick={primaryOnClick}
    disabled={primaryDisabled}
    title={primaryTitle}
  >
    {primaryLabel}
  </button>
  <button
    class="caret {variant}"
    onclick={toggle}
    aria-haspopup="menu"
    aria-expanded={open}
    aria-label="More save options"
    disabled={visibleMenu.length === 0}
  >
    ▾
  </button>
  {#if open && visibleMenu.length > 0}
    <ul class="menu" role="menu" bind:this={menuEl}>
      {#each visibleMenu as item}
        <li role="none">
          <button
            role="menuitem"
            disabled={item.disabled}
            onclick={() => { item.onclick(); close(); }}
          >
            {item.label}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  .split { position: relative; display: inline-flex; }
  .primary { border-top-right-radius: 0; border-bottom-right-radius: 0; }
  .caret {
    border-top-left-radius: 0;
    border-bottom-left-radius: 0;
    border-left: 1px solid rgba(0,0,0,0.15);
    padding: 0 0.5rem;
  }
  .menu {
    position: absolute; top: 100%; right: 0; margin: 0.25rem 0 0;
    padding: 0.25rem 0; list-style: none;
    background: var(--bg, #fff); color: var(--fg, #000);
    border: 1px solid #888; border-radius: 4px;
    min-width: 220px; z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  }
  .menu button {
    display: block; width: 100%; text-align: left;
    background: none; border: 0; padding: 0.5rem 0.75rem;
    font: inherit; cursor: pointer;
  }
  .menu button:hover:not(:disabled) { background: rgba(0,0,0,0.08); }
  .menu button:disabled { opacity: 0.5; cursor: not-allowed; }
</style>
```

**Step 2: Type-check**

Run: `cd config-editor && npm run check`
Expected: 0 errors.

**Step 3: Commit**

```bash
git add config-editor/src/lib/components/SplitButton.svelte
git commit -m "feat(editor): add SplitButton component"
```

---

## Task 6: Wire Save & Apply into +page.svelte

**Files:**
- Modify: `config-editor/src/routes/+page.svelte`
- Modify: `config-editor/src/lib/components/ConfigForm.svelte`

**Step 1: Read existing save flow**

Existing flow (verified):
- `saveToDevice()` at `+page.svelte:174` calls `normalizeConfig(get(config))` → `JSON.stringify(_, null, 2)` → `writeConfigRaw($selectedDevice.config_path, configJson)` → sets `$currentConfigRaw = configJson` and `$hasUnsavedChanges = false` → prompts to restart.
- `$currentConfigRaw` is the post-save "last known on-device" raw JSON — perfect "old" side for the diff.
- `config` is the form store (Svelte store); `dev_mode` is on the same shape.

**Step 2: Replace `saveToDevice` with three actions in `+page.svelte`**

```typescript
import {
  hotReloadDevice, hardResetDevice, classifyReload, writeConfigRaw,
} from '$lib/api';
import { save as saveFileDialog } from '@tauri-apps/plugin-dialog';

async function saveAndApply() {
  if (!$selectedDevice) return;
  if (!validate()) {
    await message('Please fix validation errors before saving', { title: 'Validation Error', kind: 'error' });
    return;
  }
  $isLoading = true;
  try {
    const oldRaw = $currentConfigRaw;
    const configObj = normalizeConfig(get(config));
    const newJson = JSON.stringify(configObj, null, 2);

    await writeConfigRaw($selectedDevice.config_path, newJson);
    $currentConfigRaw = newJson;
    $hasUnsavedChanges = false;

    let oldObj: unknown = {};
    let newObj: unknown = configObj;
    try { oldObj = JSON.parse(oldRaw); } catch {}

    const kind = await classifyReload(oldObj, newObj);
    if (kind === 'None') {
      $statusMessage = 'Saved — no changes';
    } else if (kind === 'Hard') {
      $statusMessage = 'Saved. Rebooting…';
      await hardResetDevice($selectedDevice.config_path);
      $statusMessage = 'Saved & rebooted';
    } else {
      $statusMessage = 'Saved. Reloading…';
      await hotReloadDevice($selectedDevice.config_path);
      $statusMessage = 'Saved & applied';
    }
  } catch (e: any) {
    $statusMessage = `Error: ${e.message || e}`;
    await message($statusMessage, { title: 'Error', kind: 'error' });
  } finally {
    $isLoading = false;
  }
}

async function saveLocalOnly() {
  if (!validate()) {
    await message('Please fix validation errors before saving', { title: 'Validation Error', kind: 'error' });
    return;
  }
  const path = await saveFileDialog({
    defaultPath: 'config.json',
    filters: [{ name: 'JSON', extensions: ['json'] }],
  });
  if (!path) return;
  $isLoading = true;
  try {
    const configObj = normalizeConfig(get(config));
    const json = JSON.stringify(configObj, null, 2);
    await writeConfigRaw(path, json);
    $statusMessage = `Saved to ${path}`;
  } catch (e: any) {
    $statusMessage = `Error: ${e.message || e}`;
    await message($statusMessage, { title: 'Error', kind: 'error' });
  } finally {
    $isLoading = false;
  }
}

async function saveToDeviceNoReload() {
  if (!$selectedDevice) return;
  if (!validate()) return;
  $isLoading = true;
  try {
    const configObj = normalizeConfig(get(config));
    const newJson = JSON.stringify(configObj, null, 2);
    await writeConfigRaw($selectedDevice.config_path, newJson);
    $currentConfigRaw = newJson;
    $hasUnsavedChanges = false;
    $statusMessage = 'Saved to device — reload skipped';
  } catch (e: any) {
    $statusMessage = `Error: ${e.message || e}`;
  } finally {
    $isLoading = false;
  }
}

// Derived dev-mode flag from the form store. Adjust property access to
// match the actual store shape verified during Step 1.
const devMode = $derived($config?.dev_mode === true);
```

**Step 3: Replace the existing save button**

Current button is in `ConfigForm.svelte:102-109`. Two options — pick whichever fits the codebase style:

**Option A (recommended):** Remove the save button from `ConfigForm.svelte` entirely. Render `SplitButton` directly in the toolbar area of `+page.svelte` where `ConfigForm` sits. Cleaner separation: form owns validation, page owns persistence.

**Option B:** Keep button inside `ConfigForm.svelte`, change its `Props` to:
```typescript
interface Props {
  onSaveAndApply: () => void;
  onSaveLocal: () => void;
  onSaveNoReload: () => void;
  devMode: boolean;
  hasErrors: boolean;
  isDirty: boolean;
  hasDeviceConnected: boolean;
  children?: Snippet;
}
```
and render:
```svelte
<SplitButton
  primaryLabel={hasErrors ? 'Fix errors to save' : isDirty ? 'Save & Apply *' : 'Save & Apply'}
  primaryOnClick={onSaveAndApply}
  primaryDisabled={hasErrors || !hasDeviceConnected}
  primaryTitle="Save & Apply (⌘S)"
  variant="primary"
  menu={[
    { label: 'Save (local file only)', onclick: onSaveLocal },
    { label: 'Save to Device, No Reload', onclick: onSaveNoReload, hidden: !devMode, disabled: !hasDeviceConnected },
  ]}
/>
```

**Step 4: Update ⌘S keyboard handler**

`+page.svelte:113` currently calls `saveToDevice()`. Change to `saveAndApply()`.

**Step 5: Type-check**

Run: `cd config-editor && npm run check`
Expected: 0 errors.

**Step 6: Manual UI test**

1. `cd config-editor && npm run tauri dev`
2. Connect a device, load its config.
3. Change a button color → **Save & Apply** → expect "Saved & applied", LED color updates on device, no reboot, serial stays connected.
4. Caret → **Save (local file only)** → expect Tauri save dialog, no device write.
5. Change `usb_drive_name` → **Save & Apply** → expect "Saved & rebooted", drive remounts with new name, host re-enumerates (~2s).
6. Toggle a button to `type:"hid"` → **Save & Apply** → expect hard reset (HID descriptor change).
7. Enable `dev_mode` in config (via Save & Apply, which triggers hard reset), reconnect, then caret menu shows **Save to Device, No Reload**. Click → file written, no reload. Manually click existing Reload button → works.
8. Disconnect device → primary button disabled, **Save (local)** still works.
9. Confirm SplitButton: click outside menu closes it; click on menu item still fires (regression test for click-outside ordering).

**Step 7: Commit**

```bash
git add config-editor/src/routes/+page.svelte config-editor/src/lib/components/ConfigForm.svelte
git commit -m "feat(editor): Save & Apply split button with auto hot-reload / hard-reset"
```

---

## Task 7: AGENTS.md updates

**Files:**
- Modify: `firmware/AGENTS.md`
- Modify: `config-editor/AGENTS.md` (if present) or root `AGENTS.md`

**Step 1: Document hot-reload contract in `firmware/AGENTS.md`**

Add under "Firmware Patterns":

```markdown
### Hot Config Reload

`reload_runtime_config()` in `code.py` re-reads `/config.json` and rebuilds
runtime state (buttons, LEDs, display, MIDI maps) without re-running
`boot.py`. Called over REPL by the config-editor's Save & Apply flow as
`sys.modules['__main__'].reload_runtime_config()` — NOT `import code`,
which would re-execute the whole file as a separate module.

**Cannot hot-reload** — these require `microcontroller.reset()`:
- `usb_drive_name` — set by `storage.remount(label=...)` in `boot.py`
- `dev_mode` — controls `storage.disable_usb_drive()` in `boot.py`
- `device` — pin maps and module imports decided at top of `code.py`
- HID descriptor toggle — `boot.py` enables HID conditionally on any
  `type:"hid"` button; descriptor rebuild needs USB re-enumeration.
  Changing `hid_key` / `hid_modifier` on an existing HID button is hot;
  only the on/off toggle is hard.

The editor diffs old vs new config in `reload_diff.rs` and picks
hot-reload vs hard-reset automatically.
```

**Step 2: Commit**

```bash
git add firmware/AGENTS.md config-editor/AGENTS.md
git commit -m "docs: document hot config reload contract"
```

---

## Out of Scope (V1)

- mtime-based auto-watch in firmware (extra loop overhead, race conditions)
- Partial reloads (LED-only, display-only)
- Rollback on reload failure — surface error to user, they re-save
- Remembering "last used" secondary as new primary
- Arrow-key navigation inside the SplitButton dropdown
- Touch UI / mobile breakpoints for the SplitButton menu
- Vitest setup for the SplitButton + diff logic on the TS side (Rust side already has unit tests)

---

## Review Patches Applied (vs first draft)

- **Bug 1:** REPL command changed from `from code import reload_runtime_config` to `import sys; sys.modules['__main__'].reload_runtime_config()` (code.py runs as `__main__`, `import code` would re-execute it).
- **Bug 2:** SplitButton outside-click uses `pointerdown` and checks `rootEl.contains(target)` so menu items still receive clicks.
- **Bug 3:** `pc_values` no longer reset on hot reload — preserves mid-performance pc_inc/dec state.
- **Bug 4:** `classify_reload` Tauri command explicit in Task 3 Step 1 + registered in `lib.rs` Step 2.
- **Gap 1 (file flush race):** retracted — `write_sync` (`commands.rs:232`) already `sync_all()`s before returning. No extra sleep needed.
- **Gap 2 (currentConfigJson, devMode):** resolved — uses `$currentConfigRaw` store and `normalizeConfig(get(config))` consistent with existing `saveToDevice`. `devMode` from `$config?.dev_mode`.
- **Gap 3 (saveLocalOnly stub):** concrete impl using `@tauri-apps/plugin-dialog` `save()`.
- **Nit 3 (extract helpers):** Task 1 Step 2 now explicit: move only paint lines, leave hardware init alone, and update startup sites to call the helpers (single source of truth).
