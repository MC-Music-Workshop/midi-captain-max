# Device Reload Implementation Plan

**Status:** Shipped — device reload is in the current firmware/editor.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add "Reload Device" button to GUI that triggers CircuitPython to reload code.py and config.json without requiring manual power-cycle or serial console access.

**Architecture:** Sentinel file approach — GUI writes `.reload` file to device volume, firmware's main loop detects it and calls `supervisor.reload()`. This is cross-platform, doesn't require serial access, works during MIDI operation, and survives USB reconnects.

**Tech Stack:** CircuitPython 7.x (supervisor module), Rust (std::fs), Tauri commands, Svelte UI

---

## Background

**Current limitation:** After saving config changes, users must:
- Power-cycle the device, OR
- Connect via serial console and send Ctrl+D

This is poor UX for a GUI config editor.

**Solution:** Write a sentinel file that firmware watches:
```
/Volumes/MIDICAPTAIN/.reload  ← GUI writes this file
                               ↓ firmware detects on next loop iteration
                               ↓ calls supervisor.reload()
                               ↓ device reloads code.py and config.json
```

**Why this approach:**
- ✅ No serial console needed
- ✅ Works while MIDI is active
- ✅ Cross-platform (just file I/O)
- ✅ Simple to implement and test
- ✅ Doesn't interfere with autoreload disabled state
- ❌ Requires firmware update (users need this in their firmware)

**Alternative approaches considered:**
1. Serial console Ctrl+D — requires serial port detection, platform-specific, not reliable
2. SysEx reload command — requires MIDI enumeration, may conflict with host software
3. Unmount/remount volume — OS-specific, unreliable, requires elevated permissions

---

## Task 1: Firmware Reload Detection

**Files:**
- Modify: `firmware/dev/code.py` (add reload check in main loop)
- Test: Manual (copy .reload file, verify device reloads)

**Step 1: Add reload detection function**

Add after imports, before main loop setup:

```python
import supervisor
import os

# File that triggers device reload (written by config editor)
RELOAD_TRIGGER_FILE = ".reload"

def check_for_reload_request():
    """Check if reload was requested via sentinel file, and reload if found."""
    try:
        if RELOAD_TRIGGER_FILE in os.listdir("/"):
            print("🔄 Reload requested via .reload file")
            try:
                os.remove(RELOAD_TRIGGER_FILE)  # Clean up before reload
            except OSError:
                pass  # Ignore if already gone
            print("Reloading...")
            supervisor.reload()  # Does NOT return - device reloads immediately
    except Exception as e:
        # Defensive: never crash on reload check
        print(f"Reload check error: {e}")
```

**Step 2: Call reload check in main loop**

Find the main loop (starts with `while True:`), add check at the TOP of the loop:

```python
while True:
    # Check for reload requests FIRST (before any other processing)
    check_for_reload_request()
    
    # ... existing loop body ...
```

**Rationale:** Check at top of loop so reload happens before MIDI/button processing.

**Step 3: Test manually on device**

```bash
# Deploy updated firmware
./tools/deploy.sh /Volumes/MIDICAPTAIN

# Watch serial console (separate terminal)
screen /dev/cu.usbmodem* 115200

# Trigger reload (in another terminal)
touch /Volumes/MIDICAPTAIN/.reload

# Expected in serial console:
# 🔄 Reload requested via .reload file
# Reloading...
# [device restarts, boot.py runs, code.py starts fresh]
```

**Step 4: Verify reload behavior**

1. Modify config.json (change a button label)
2. Write .reload file: `touch /Volumes/MIDICAPTAIN/.reload`
3. Wait ~1 second (next loop iteration)
4. Verify device display shows new label
5. Verify .reload file is gone (cleaned up)

**Step 5: Commit firmware changes**

```bash
git add firmware/dev/code.py
git commit -m "feat(firmware): add .reload file detection for GUI-triggered reloads

- Check for .reload sentinel file at top of main loop
- Call supervisor.reload() if file exists
- Clean up file before reload
- Defensive error handling (never crash on reload check)
"
```

---

## Task 2: Rust Backend Command

**Files:**
- Modify: `config-editor/src-tauri/src/commands.rs` (add reload_device command)
- Modify: `config-editor/src-tauri/src/lib.rs` (register command)

**Step 1: Add reload command to commands.rs**

Add at end of file, before closing:

```rust
/// Trigger device reload by writing sentinel file
/// Device firmware detects this file and calls supervisor.reload()
#[command]
pub fn reload_device(device_path: String) -> Result<(), ConfigError> {
    // Validate path is on a known device volume
    validate_device_path(&device_path)?;
    
    let device_path = Path::new(&device_path);
    
    // Verify device is still connected
    verify_device_connected(device_path)?;
    
    // Write .reload file at volume root
    let reload_file = device_path.join(".reload");
    
    // Write empty file (firmware just checks existence)
    File::create(&reload_file).map_err(|e| ConfigError {
        message: format!("Failed to write reload trigger: {}", e),
        details: None,
    })?;
    
    // Sync to ensure file is written before firmware checks
    #[cfg(unix)]
    {
        use std::process::Command;
        let _ = Command::new("sync").output(); // Best effort, ignore errors
    }
    
    Ok(())
}
```

**Step 2: Register command in lib.rs**

In `invoke_handler` section, add `reload_device` to the list:

```rust
        .invoke_handler(tauri::generate_handler![
            read_config,
            read_config_raw,
            write_config,
            write_config_raw,
            validate_config,
            scan_devices,
            start_device_watcher,
            stop_device_watcher,
            reload_device  // ← ADD THIS
        ])
```

**Step 3: Add import to commands.rs**

At top of commands.rs where `use std::fs::{...}` is:

```rust
use std::fs::{self, File};  // File already imported
```

(If File is not imported, add it. Check imports first.)

**Step 4: Test compilation**

```bash
cd config-editor/src-tauri
cargo build
```

Expected: Clean build with no errors

**Step 5: Commit backend changes**

```bash
git add config-editor/src-tauri/src/commands.rs config-editor/src-tauri/src/lib.rs
git commit -m "feat(backend): add reload_device command

- Writes .reload sentinel file to device volume root
- Validates device path and connection before write
- Syncs filesystem (Unix) to ensure file is visible to firmware
- Returns error if device disconnected during operation
"
```

---

## Task 3: TypeScript API Binding

**Files:**
- Modify: `config-editor/src/lib/api.ts` (add reloadDevice function)
- Modify: `config-editor/src/lib/types.ts` (if error types need update)

**Step 1: Add reloadDevice function to api.ts**

Add at end of file, after other command bindings:

```typescript
/**
 * Trigger device reload by writing .reload sentinel file.
 * Device firmware detects this and calls supervisor.reload().
 * 
 * @param devicePath - Path to device volume (e.g., "/Volumes/MIDICAPTAIN")
 * @throws Error if device disconnected or write fails
 */
export async function reloadDevice(devicePath: string): Promise<void> {
  return await invoke('reload_device', { devicePath });
}
```

**Step 2: Verify types are correct**

Check if `invoke` is properly typed (should be from `@tauri-apps/api/core`):

```typescript
import { invoke } from '@tauri-apps/api/core';
```

If not present, add it.

**Step 3: Test TypeScript compilation**

```bash
cd config-editor
npm run check
```

Expected: No TypeScript errors

**Step 4: Commit API binding**

```bash
git add config-editor/src/lib/api.ts
git commit -m "feat(api): add reloadDevice binding

- Wraps reload_device Tauri command
- Takes device path, triggers .reload file write
- Throws on error (device disconnected, write failed)
"
```

---

## Task 4: UI Button and UX

**Files:**
- Modify: `config-editor/src/routes/+page.svelte` (add Reload button + handler)
- Maybe modify: `config-editor/src/lib/stores.ts` (if reload status tracking needed)

**Step 1: Add reload handler function**

In `<script>` section of +page.svelte, after other async functions (like handleSaveToDevice), add:

```typescript
  async function handleReloadDevice() {
    if (!$selectedDevice) return;
    
    try {
      $isLoading = true;
      $statusMessage = 'Reloading device...';
      
      await reloadDevice($selectedDevice.path);
      
      // Device will disconnect briefly during reload
      // Show success message (device will reconnect automatically)
      $statusMessage = 'Device reload triggered successfully';
      
      await message(
        'Device is reloading. It will reconnect in a few seconds.',
        { title: 'Reload Triggered', kind: 'info' }
      );
      
    } catch (error: any) {
      console.error('Reload failed:', error);
      $statusMessage = `Reload failed: ${error.message || error}`;
      
      await message(
        `Failed to reload device: ${error.message || error}`,
        { title: 'Reload Error', kind: 'error' }
      );
    } finally {
      $isLoading = false;
    }
  }
```

**Step 2: Add import for reloadDevice**

At top of file, add to existing api imports:

```typescript
  import { 
    scanDevices, startDeviceWatcher, readConfigRaw, writeConfigRaw,
    onDeviceConnected, onDeviceDisconnected, reloadDevice  // ← ADD THIS
  } from '$lib/api';
```

**Step 3: Add Reload button to toolbar**

Find the toolbar section (near Save button), add Reload button:

```svelte
      <button 
        on:click={handleSaveToDevice}
        disabled={!$selectedDevice || $isLoading || !$hasUnsavedChanges || $validationErrors.size > 0}
        class="btn btn-primary"
        title={$validationErrors.size > 0 ? 'Cannot save: validation errors present' : 'Save config to device (⌘S)'}
      >
        {$isLoading ? 'Saving...' : 'Save to Device'}
      </button>
      
      <!-- Reload button (new) -->
      <button 
        on:click={handleReloadDevice}
        disabled={!$selectedDevice || $isLoading}
        class="btn btn-secondary"
        title="Reload device (apply saved config without power cycle)"
      >
        Reload Device
      </button>
```

**Step 4: Test UI in browser**

```bash
cd config-editor
npm run tauri dev
```

1. Connect device (or use mock data)
2. Verify "Reload Device" button appears
3. Verify button is disabled when no device selected
4. Verify button is enabled when device connected
5. Click button → should show "Reloading..." status
6. If device is real, verify it actually reloads

**Step 5: Test integration with real device**

1. Start config editor with real device connected
2. Make config change, save it
3. Click "Reload Device"
4. Expected flow:
   - Status shows "Reloading device..."
   - Dialog: "Device is reloading. It will reconnect in a few seconds."
   - Device briefly disconnects
   - Device reconnects after 2-3 seconds
   - Updated config is visible on device display/LEDs

**Step 6: Commit UI changes**

```bash
git add config-editor/src/routes/+page.svelte
git commit -m "feat(ui): add Reload Device button

- Triggers device reload via .reload sentinel file
- Disabled when no device selected or during operations
- Shows dialog explaining device will reconnect
- Auto-reconnect logic handles device coming back online
"
```

---

## Task 5: Documentation Updates

**Files:**
- Modify: `docs/plans/2026-02-09-config-form-editor-design.md` (add reload feature docs)
- Modify: `README.md` (add reload feature to feature list)
- Maybe create: `docs/firmware-reload-protocol.md` (document .reload mechanism)

**Step 1: Document reload protocol**

Create `docs/firmware-reload-protocol.md`:

```markdown
# Device Reload Protocol

**Version:** 1.0  
**Date:** 2026-02-10

---

## Overview

The config editor can trigger device reloads without requiring serial console access or power cycling.

## Mechanism

**Sentinel file:** `/.reload` at device volume root

**Firmware behavior:**
1. Main loop checks for `.reload` file on every iteration (~100-200ms)
2. If file exists:
   - Print reload message to serial console
   - Delete `.reload` file (cleanup)
   - Call `supervisor.reload()` (CircuitPython restart)
3. Device reboots:
   - `boot.py` runs (USB drive mode check, autoreload disable)
   - `code.py` loads fresh from disk
   - `config.json` is re-read

**GUI workflow:**
1. User clicks "Reload Device" button
2. GUI writes empty `.reload` file to device volume
3. GUI syncs filesystem (Unix: `sync` command)
4. Firmware detects file within ~200ms
5. Device reloads, briefly disconnects USB
6. Device reconnects 2-3 seconds later
7. GUI auto-selects device when reconnected

## Error Handling

**Device disconnected during write:**
- Rust command validates device is mounted
- Returns error if volume check fails
- GUI shows error dialog

**Reload file write fails:**
- Rust command returns IO error
- GUI shows error dialog
- Device remains running (not affected)

**Firmware reload fails:**
- `supervisor.reload()` never returns (always succeeds or hangs)
- Defensive try/except around file operations prevents firmware crash
- Worst case: device keeps running, .reload file stays (harmless)

## Testing

**Manual test:**
```bash
# Connect device, then:
touch /Volumes/MIDICAPTAIN/.reload

# Watch serial console for:
# 🔄 Reload requested via .reload file
# Reloading...
# [boot sequence starts]
```

**Automated test scenarios:**
1. Write .reload with device connected → device reloads
2. Write .reload during MIDI operation → device reloads (MIDI reconnects)
3. Modify config.json, write .reload → new config loads
4. Write .reload multiple times rapidly → only one reload happens
5. Disconnect device after .reload written → no crash, file cleaned up on reconnect

## Compatibility

**CircuitPython versions:**
- ✅ CP 7.x: `supervisor.reload()` supported
- ✅ CP 8.x+: `supervisor.reload()` still supported (unchanged API)

**Device models:**
- ✅ STD10: Tested, working
- ✅ Mini6: Should work (same volume mounting, same supervisor module)
- ✅ Mini1/Mini2/Mini4: Not tested, but should work (same architecture)

## Security

**Path validation:**
- Rust backend validates path starts with `/Volumes/CIRCUITPY` or `/Volumes/MIDICAPTAIN`
- Prevents path traversal attacks
- Canonicalizes path before check

**Impact radius:**
- Only affects connected device
- No system-wide effects
- No elevated permissions needed

## Future Enhancements

**Possible improvements:**
1. **Reload status feedback:** Device could write `.reload_done` file after successful reload
2. **Reload logging:** Firmware could append to `.reload_log` with timestamps
3. **Conditional reload:** Only reload if `.reload` file contains specific version hash
4. **SysEx alternative:** Send SysEx reload command via MIDI (no file I/O needed)
```

**Step 2: Update README feature list**

In README.md, find the features section and add:

```markdown
- **Device Reload:** Reload firmware/config from GUI without power cycling
```

**Step 3: Update design doc**

In `docs/plans/2026-02-09-config-form-editor-design.md`, add to "Future Features" or "Implemented Features" section:

```markdown
### Device Reload (Implemented 2026-02-10)

"Reload Device" button triggers CircuitPython reload via `.reload` sentinel file:
- No serial console needed
- Works during MIDI operation
- Device reconnects automatically after 2-3 seconds
- Documented in [firmware-reload-protocol.md](../firmware-reload-protocol.md)
```

**Step 4: Commit documentation**

```bash
git add docs/firmware-reload-protocol.md docs/plans/2026-02-09-config-form-editor-design.md README.md
git commit -m "docs: document device reload protocol

- New firmware-reload-protocol.md with complete technical spec
- Updated feature lists in README and design doc
- Includes error handling, testing, and security considerations
"
```

---

## Task 6: Test Edge Cases

**Files:**
- None (manual testing only)

**Step 1: Test with device disconnected during reload**

1. Connect device
2. Click "Reload Device"
3. Immediately unplug device (during reload)
4. Expected: Error dialog "Device was disconnected"
5. Verify no crash, UI remains functional

**Step 2: Test rapid repeated reloads**

1. Connect device
2. Click "Reload Device"
3. Wait for dialog
4. Immediately click "Reload Device" again (before reconnect)
5. Expected: Button disabled during first reload
6. Expected: Second reload happens after reconnect

**Step 3: Test reload with unsaved changes**

1. Connect device
2. Modify config (unsaved changes)
3. Click "Reload Device" (without saving)
4. Expected: Device reloads with OLD config (unsaved changes not applied)
5. Verify status message makes this clear

**Step 4: Test reload after save**

1. Connect device
2. Modify config
3. Save config
4. Click "Reload Device"
5. Expected: Device reloads with NEW config
6. Verify changes appear on device (LEDs, display)

**Step 5: Test with Mini6 device**

1. Connect Mini6 (if available)
2. Load Mini6 config
3. Click "Reload Device"
4. Expected: Same behavior as STD10
5. Verify device reloads successfully

**Step 6: Document test results**

Add to commit message or test log:

```bash
git commit --allow-empty -m "test: verify device reload edge cases

Tested scenarios:
- ✅ Reload with device disconnected during operation
- ✅ Rapid repeated reload clicks (button properly disabled)
- ✅ Reload with unsaved changes (warning shown, old config loads)
- ✅ Reload after save (new config loads successfully)
- ✅ Mini6 compatibility (if tested)

All edge cases handled gracefully, no crashes.
"
```

---

## Task 7: Consider UX Improvements (Optional)

**Step 1: Add save + reload combo button**

Many users will want to save and reload in one click. Consider adding:

```svelte
      <button 
        on:click={handleSaveAndReload}
        disabled={!$selectedDevice || $isLoading || !$hasUnsavedChanges || $validationErrors.size > 0}
        class="btn btn-primary"
        title="Save config and reload device in one step"
      >
        Save & Reload
      </button>
```

Handler:
```typescript
  async function handleSaveAndReload() {
    await handleSaveToDevice();
    if ($statusMessage.includes('successfully')) {  // Save succeeded
      await handleReloadDevice();
    }
  }
```

**Step 2: Add auto-reload preference**

Some users might want automatic reload after every save:

```typescript
  // In stores.ts or settings store:
  export const autoReloadAfterSave = writable(false);
  
  // In handleSaveToDevice():
  if (get(autoReloadAfterSave)) {
    await handleReloadDevice();
  }
```

Add checkbox in settings section:
```svelte
  <label>
    <input type="checkbox" bind:checked={$autoReloadAfterSave} />
    Auto-reload device after saving
  </label>
```

**Step 3: Show reload progress bar**

Device takes 2-3 seconds to reload. Show progress:

```svelte
  {#if isReloading}
    <div class="reload-progress">
      <div class="spinner"></div>
      <p>Device reloading... it will reconnect in a few seconds</p>
    </div>
  {/if}
```

**Step 4: Decide which improvements to implement**

These are all optional enhancements. Implement based on user feedback and testing.

If implementing any, commit separately:

```bash
git add [files]
git commit -m "feat(ui): add save+reload combo button

Users often want to save and reload together. New button does both in sequence.
"
```

---

## Final Checklist

**Before merging:**
- [ ] Firmware reload detection works on real hardware
- [ ] Rust command compiles without warnings
- [ ] TypeScript has no type errors
- [ ] UI button appears and is properly enabled/disabled
- [ ] Real device reload test: config changes are applied
- [ ] Documentation is complete and accurate
- [ ] Edge cases tested (disconnect during reload, rapid clicks, etc.)
- [ ] All commits have clear messages
- [ ] Code follows existing style/conventions

**Post-merge:**
- [ ] Update CHANGELOG.md with new feature
- [ ] Tag release if this is part of a version bump
- [ ] Test firmware+GUI together in real performance scenario
- [ ] Update user-facing docs (if any)
- [ ] Consider adding reload button to quick-start guide

---

## Notes for Implementer

**Timing considerations:**
- Device reload takes 2-3 seconds (USB disconnect/reconnect)
- Main loop iteration in firmware is ~100-200ms (reload detection latency)
- GUI file write + sync is <50ms typically
- Total user-perceived time: ~3-4 seconds from click to device ready

**Common pitfalls:**
- Don't try to read config immediately after reload — device needs time to reconnect
- .reload file MUST be deleted before reload() to prevent infinite reload loops
- Sync filesystem after write (Unix) to ensure firmware sees file
- Validate device path to prevent security issues

**Testing without hardware:**
- You can test file write by checking if `.reload` appears on volume
- You can't test actual reload without real device (no CircuitPython simulator)
- Use mock device for UI testing, real device for integration testing

**Performance:**
- File write is fast (<1ms typically)
- Sync can be slow on some systems (up to 100ms)
- Don't reload in tight loops (GUI prevents this with disabled button)

**Future compatibility:**
- CP 8.x+: `supervisor.reload()` unchanged, should work
- Other devices (Kemper, etc.): Would need same firmware pattern
- Web-based config editor: Would use browser file system API instead of Tauri
