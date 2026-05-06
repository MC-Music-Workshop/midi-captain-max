# SPIKE: GUI Firmware Installation Feature

**Date:** 2026-02-27  
**Author:** Copilot (GitHub Agent)  
**Issue:** [#19 - feature: install firmware using GUI](https://github.com/MC-Music-Workshop/midi-captain-max/issues/19)

---

## Executive Summary

This spike analyzes the feasibility of adding firmware installation capabilities to the MIDI Captain MAX Config Editor GUI application. The goal is to eliminate the need for users to separately download and manage firmware files, instead bundling firmware with the GUI and providing one-click installation.

**Key Findings:**
1. ✅ **Technically feasible** — All capabilities of `deploy.sh` can be replicated in Tauri/Rust
2. ✅ **Architecturally sound** — Config Editor already has device detection and filesystem access
3. ⚠️ **Moderate complexity** — Requires bundling firmware, version management, and platform-specific file operations
4. ✅ **Strong user value** — Dramatically simplifies the installation experience
5. ⚠️ **Distribution tradeoffs** — Larger app bundles vs. simpler user experience

**Recommendation:** **Proceed with implementation** — The user experience gains outweigh the implementation complexity. A phased rollout is recommended.

---

## Current State Analysis

### How Users Install Firmware Today

**Current Workflow (Separate Downloads):**
1. Download `midicaptain-firmware-vX.X.X.zip` from GitHub Releases
2. Unzip to access firmware files
3. Download `MIDI-Captain-MAX-Config-Editor-vX.X.X.dmg` (or .msi, .exe)
4. Install Config Editor
5. Connect device
6. **For firmware updates:**
   - macOS/Linux: Use `deploy.sh` script (requires terminal knowledge)
   - Windows: Manually copy files via File Explorer (error-prone)
7. For config edits: Use Config Editor GUI

**Pain Points:**
- **Two separate downloads** to manage
- **Version mismatch risks** — users can install incompatible firmware/config versions
- **Terminal knowledge required** for `deploy.sh` (barrier to entry)
- **Windows users have no script** — must manually copy files (high error rate)
- **No guided experience** — users must read docs, follow multi-step instructions

### Current Capabilities

#### Config Editor (Tauri + Rust)
- ✅ Device detection (CIRCUITPY/MIDICAPTAIN volumes) — cross-platform
- ✅ Filesystem read/write with platform-specific APIs
- ✅ Safe file sync operations (`sync_all()` on Unix, `FlushFileBuffers` on Windows)
- ✅ Config validation and device-type awareness
- ✅ Real-time device connection/disconnection events

#### deploy.sh Script
The script performs these operations (lines 1-323):
1. **Auto-detect device mount point** (`/Volumes/CIRCUITPY` or `/Volumes/MIDICAPTAIN`)
2. **Detect device type** from existing config.json or mount point heuristic
3. **Install CircuitPython libraries** (optional, via `circup`)
4. **Deploy files in specific order** (dependencies → code):
   ```
   boot.py → core/ → devices/ → fonts/ → lib/ → config.json → code.py → VERSION
   ```
5. **Generate firmware manifest** (`firmware.md5`) for incremental updates
6. **Preserve existing config.json** unless `--fresh` flag specified
7. **Sync filesystem** to ensure USB writes complete
8. **Optional eject** for clean device reload

**Key Logic:**
- Uses `rsync` with `--checksum` and `--inplace` for reliability
- Writes `VERSION` file from `git describe --tags --always`
- Device-specific config selection (`config.json` for STD10, `config-mini6.json` for Mini6)
- Never overwrites user config by default

#### Firmware Distribution (CI/CD)
- CI builds firmware zip on every push (`.github/workflows/ci.yml`)
- Release workflow downloads CI artifacts and attaches to GitHub Release
- Firmware zip contains: `boot.py`, `code.py`, `core/`, `devices/`, `fonts/`, `lib/`, `config.json`, `config-mini6.json`
- Version is injected as `VERSION` file during build

---

## Implementation Approaches

### Approach 1: Bundle Firmware with Config Editor (Recommended)

**Architecture:**
```
MIDI Captain MAX Config Editor.app/
├── Contents/
│   ├── MacOS/
│   │   └── midi-captain-max-config-editor (Tauri binary)
│   ├── Resources/
│   │   └── firmware/              ← NEW
│   │       ├── boot.py
│   │       ├── code.py
│   │       ├── core/
│   │       ├── devices/
│   │       ├── fonts/
│   │       ├── lib/
│   │       ├── config.json
│   │       ├── config-mini6.json
│   │       └── VERSION
│   └── Info.plist
```

**Tauri Implementation:**
```rust
// New command: install_firmware
#[command]
async fn install_firmware(
    device_path: String,
    preserve_config: bool,
) -> Result<InstallProgress, InstallError> {
    // 1. Validate device path
    // 2. Detect device type
    // 3. Copy firmware files from bundled resources
    // 4. Generate manifest
    // 5. Preserve or install default config
    // 6. Sync filesystem
}
```

**Bundling Strategy:**
- Add firmware files to `config-editor/src-tauri/resources/` directory
- Tauri includes resources in app bundle automatically
- Access via `app_handle.path().resource_dir()` API
- CI workflow extracts firmware from zip artifact into resources before building

**Pros:**
- ✅ **Single download** — users only install Config Editor
- ✅ **Version consistency** — firmware and editor always match
- ✅ **No terminal required** — pure GUI experience
- ✅ **Cross-platform** — works on macOS, Windows, Linux
- ✅ **Offline installation** — no internet required after download
- ✅ **Incremental updates** — check manifest to skip unchanged files
- ✅ **Progress UI** — show installation status in GUI

**Cons:**
- ⚠️ **Larger app bundles** — adds ~500KB to app size (firmware files)
- ⚠️ **Build complexity** — CI must coordinate firmware + editor builds
- ⚠️ **Independent updates impossible** — firmware/editor coupled (but this is desired)

**Risks:**
- ⚠️ **File ordering critical** — must replicate deploy.sh's dependency-first sequence
- ⚠️ **Platform-specific sync** — must ensure USB writes complete (fsync edge cases)
- ⚠️ **Config preservation** — logic to detect/preserve user config must be bulletproof

**Mitigations:**
- Use integration tests on real hardware (STD10 + Mini6)
- Implement incremental rollout (alpha → beta → stable)
- Keep deploy.sh as fallback for power users
- Add dry-run mode for testing without actual writes

---

### Approach 2: Download Firmware on Demand

**Architecture:**
```
Config Editor (on first install click)
  ↓
Fetch latest firmware.zip from GitHub Releases
  ↓
Extract to temp directory
  ↓
Install from temp to device
```

**Pros:**
- ✅ **Smaller app bundles** — firmware not included
- ✅ **Independent updates** — can update firmware without updating editor
- ✅ **Always latest** — fetch newest firmware on install

**Cons:**
- ❌ **Internet required** — can't install firmware offline
- ❌ **GitHub API dependency** — rate limits, network failures
- ❌ **Version mismatch risk** — editor and firmware can drift
- ❌ **More complex** — download + extract + install pipeline
- ❌ **User confusion** — what version is being installed?

**Verdict:** Rejected — contradicts goal of "no other downloads necessary"

---

### Approach 3: Hybrid (Bundle Default + Download Updates)

**Architecture:**
- Bundle firmware with editor (like Approach 1)
- Check GitHub for newer firmware on startup
- Offer optional update download

**Pros:**
- ✅ Works offline with bundled firmware
- ✅ Can update firmware without updating editor

**Cons:**
- ⚠️ **Complex** — combines downsides of both approaches
- ⚠️ **Version confusion** — multiple firmware versions in play
- ⚠️ **Testing burden** — must test bundled + downloaded firmware

**Verdict:** Over-engineered for MVP — consider for future enhancement

---

## Detailed Design: Approach 1 (Recommended)

### Phase 1: Bundle Firmware in Config Editor

**Build Process Changes:**

1. **CI Workflow (`ci.yml`):**
   ```yaml
   - name: Build firmware
     # ... existing firmware build ...
   
   - name: Prepare firmware for bundling
     run: |
       mkdir -p config-editor/src-tauri/resources/firmware
       unzip firmware.zip -d config-editor/src-tauri/resources/firmware/
   
   - name: Build Config Editor
     # ... now includes firmware in resources ...
   ```

2. **Tauri Config (`tauri.conf.json`):**
   ```json
   {
     "bundle": {
       "resources": [
         "resources/firmware/**/*"
       ]
     }
   }
   ```

**Size Impact:**
- Firmware files: ~200KB (.py source)
- CircuitPython libs (lib/): ~300KB (.mpy compiled)
- Total: ~500KB added to app bundle

**Before:** 5-10MB app bundle  
**After:** 5.5-10.5MB app bundle (~10% increase)

---

### Phase 2: Implement Installation Logic

**New Rust Module: `installer.rs`**

```rust
pub struct FirmwareInstaller {
    firmware_path: PathBuf,
    device_path: PathBuf,
    device_type: DeviceType,
}

impl FirmwareInstaller {
    pub fn new(app_handle: &AppHandle, device_path: String) -> Result<Self>;
    
    pub async fn install(&self, options: InstallOptions) -> Result<InstallReport>;
    
    fn detect_device_type(&self) -> Result<DeviceType>;
    fn should_preserve_config(&self) -> bool;
    fn copy_files_in_order(&self, progress: ProgressCallback) -> Result<()>;
    fn generate_manifest(&self) -> Result<()>;
    fn sync_filesystem(&self) -> Result<()>;
}

pub struct InstallOptions {
    pub preserve_config: bool,
    pub incremental: bool,  // Skip unchanged files
}

pub struct InstallReport {
    pub files_copied: usize,
    pub files_skipped: usize,
    pub config_preserved: bool,
    pub device_type: DeviceType,
    pub version: String,
}
```

**Key Implementation Details:**

1. **File Ordering (Critical):**
   ```rust
   const INSTALL_ORDER: &[&str] = &[
       "boot.py",
       "core/",
       "devices/",
       "fonts/",
       "lib/",
       "config.json",  // Only if not preserving
       "code.py",      // LAST
       "VERSION.txt",
   ];
   ```

2. **Platform-Specific Sync:**
   ```rust
   #[cfg(unix)]
   fn sync_file(file: &File) -> io::Result<()> {
       file.sync_all()
   }
   
   #[cfg(windows)]
   fn sync_file(file: &File) -> io::Result<()> {
       use std::os::windows::io::AsRawHandle;
       unsafe {
           FlushFileBuffers(file.as_raw_handle());
       }
       Ok(())
   }
   ```

3. **Incremental Install (Optimization):**
   ```rust
   fn should_copy_file(&self, file: &Path) -> Result<bool> {
       // Read existing manifest
       let manifest = self.read_device_manifest()?;
       
       // Compute source file hash
       let source_hash = self.hash_file(file)?;
       
       // Compare with manifest
       Ok(!manifest.contains(file, source_hash))
   }
   ```

---

### Phase 3: GUI Integration

**New UI: Install Tab**

```svelte
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  
  let installing = false;
  let progress = 0;
  let status = '';
  
  async function installFirmware() {
    installing = true;
    try {
      const result = await invoke('install_firmware', {
        devicePath: selectedDevice.path,
        preserveConfig: true,
      });
      status = `Installed ${result.version}`;
    } catch (err) {
      status = `Error: ${err}`;
    } finally {
      installing = false;
    }
  }
</script>

<button on:click={installFirmware} disabled={!selectedDevice || installing}>
  {installing ? 'Installing...' : 'Install Firmware'}
</button>

{#if installing}
  <progress value={progress} max="100"></progress>
  <p>{status}</p>
{/if}
```

**UX Flow:**
1. User connects device
2. Device detected automatically (existing feature)
3. "Install Firmware" button appears
4. Click → progress bar → "Installation complete"
5. Optional: "Eject device" button for clean reload

---

### Phase 4: Testing & Validation

**Test Matrix:**

| Platform | Device | Config State | Expected Behavior |
|----------|--------|--------------|-------------------|
| macOS | STD10 | No config | Install default STD10 config |
| macOS | Mini6 | No config | Install default Mini6 config |
| macOS | STD10 | Existing config | Preserve user config |
| Windows | STD10 | No config | Install default config |
| Linux | Mini6 | Existing config | Preserve user config |

**Automated Tests:**
- Unit tests for file ordering logic
- Unit tests for device type detection
- Mock tests for filesystem operations
- Integration tests on real hardware (manual)

**Alpha Testing:**
- Internal testing on all 3 platforms
- Both device types (STD10 + Mini6)
- Fresh install + update scenarios

---

## Pros/Cons/Risks/Gains Summary

### PROS

#### User Experience
- ✅ **Dramatically simpler** — one download instead of two
- ✅ **No terminal required** — accessible to non-technical musicians
- ✅ **Windows support** — no more manual file copying
- ✅ **Version consistency** — firmware and editor always compatible
- ✅ **Guided experience** — UI shows progress, handles errors gracefully

#### Technical
- ✅ **Leverages existing capabilities** — device detection, filesystem access already working
- ✅ **Cross-platform** — Tauri handles OS differences
- ✅ **Incremental updates** — manifest-based skip unchanged files
- ✅ **Testable** — can unit test logic with mocks

#### Product
- ✅ **Professional polish** — matches expectations of modern desktop apps
- ✅ **Competitive advantage** — other MIDI devices don't have this
- ✅ **Reduces support burden** — fewer "how do I install?" questions

### CONS

#### Distribution
- ⚠️ **Larger app bundles** — 500KB added (~10% increase)
- ⚠️ **Coupled releases** — can't update firmware independently (but this is by design)

#### Development
- ⚠️ **Build complexity** — CI must coordinate firmware → editor bundling
- ⚠️ **Testing overhead** — must test on real hardware across platforms

#### User Impact (Minor)
- ⚠️ **Slower downloads** — slightly larger files to download
- ⚠️ **Less flexibility** — power users can't mix firmware versions (but deploy.sh still exists)

### RISKS

#### High Priority (Must Mitigate)

1. **File ordering bugs** → Device fails to boot  
   **Mitigation:** Strict ordering logic + integration tests

2. **Config overwrite bugs** → User loses custom config  
   **Mitigation:** Explicit "preserve config" default + dry-run mode

3. **Incomplete USB writes** → Corrupted firmware  
   **Mitigation:** Platform-specific fsync + eject option

4. **Device detection false positives** → Install to wrong device  
   **Mitigation:** Strict volume name validation + user confirmation

#### Medium Priority

5. **Version mismatch** → Old firmware in new editor  
   **Mitigation:** VERSION file validation + CI enforcement

6. **Build failures** → CI can't bundle firmware  
   **Mitigation:** Fail early in CI + clear error messages

7. **Platform-specific bugs** → Works on macOS but fails on Windows  
   **Mitigation:** Cross-platform testing in CI + alpha testers

#### Low Priority

8. **Bundle size bloat** → App becomes too large  
   **Impact:** 500KB is negligible (10% increase)

9. **User confusion** → "Where's the firmware zip?"  
   **Mitigation:** Clear docs + changelog

### GAINS

#### Quantitative
- **Installation steps reduced:** 7 → 3 (57% reduction)
- **Downloads required:** 2 → 1 (50% reduction)
- **Windows users:** 0% have scripted install → 100% have scripted install
- **Support burden:** Estimate 30-50% reduction in "how do I install?" issues

#### Qualitative
- **Perception:** More professional, polished product
- **Accessibility:** Non-technical musicians can now manage firmware
- **Reliability:** Consistent installation process across all platforms
- **Trust:** Users confident they have compatible firmware/editor versions

---

## Open Questions

### Q1: Do we need to port deploy.sh to PowerShell for Windows?

**Answer:** No, the GUI makes scripts obsolete for most users.

**Recommendation:**
- Keep `deploy.sh` for macOS/Linux power users (dev workflow)
- GUI becomes primary installation method for all platforms
- Document GUI installation in README as primary method
- Document `deploy.sh` as "Advanced: Manual Installation"

### Q2: Should we support independent firmware updates?

**Answer:** Not for MVP, consider for future.

**Reasoning:**
- Current version strategy couples firmware to editor releases (see AGENTS.md versioning)
- Simplifies testing (only test firmware/editor pairs that shipped together)
- Most users want "install latest everything" not "mix versions"

**Future Enhancement:** If users request it, add "Download Latest Firmware" feature (Approach 3)

### Q3: What happens to existing deploy.sh users?

**Answer:** Nothing changes for them.

- `deploy.sh` remains in repository
- CI still generates standalone firmware.zip
- Power users can continue using scripts
- GUI is an additional option, not a replacement

### Q4: How do we handle firmware updates for devices in use?

**Answer:** Guide users to reload safely.

**UX Flow:**
1. User clicks "Install Firmware"
2. App shows warning: "Device will reload. Save any unsaved work."
3. User confirms
4. App installs firmware
5. App offers "Eject Device" button (optional)
6. User can reconnect or power-cycle to start new firmware

---

## Conflicts with Open PRs

**Current Open PR:** #46 (this PR — WIP spike)

No other open PRs conflict with this work based on GitHub API query.

**Future Conflict Risk:**
- If Phase 7 of `docs/plans/2026-02-02-config-editor.md` (Firmware Installation) is started independently, coordinate to avoid duplicate work.

---

## Implementation Roadmap

### Pre-Implementation Tasks
- [ ] **Stakeholder approval** — get sign-off on Approach 1
- [ ] **Spike review** — team review of this document
- [ ] **Test hardware secured** — ensure STD10 + Mini6 available for testing

### Phase 1: Bundle Firmware (Week 1)
- [ ] Add `config-editor/src-tauri/resources/firmware/` directory
- [ ] Update CI workflow to extract firmware into resources
- [ ] Update Tauri config to include resources in bundle
- [ ] Verify firmware included in dev builds
- [ ] Test bundled firmware access via Rust API

### Phase 2: Core Installation Logic (Week 1-2)
- [ ] Create `src-tauri/src/installer.rs` module
- [ ] Implement device type detection
- [ ] Implement file ordering logic
- [ ] Implement config preservation logic
- [ ] Implement platform-specific filesystem sync
- [ ] Write unit tests for installer logic

### Phase 3: GUI Integration (Week 2)
- [ ] Add "Install" tab to Config Editor UI
- [ ] Create install button + progress UI
- [ ] Wire Tauri command to UI
- [ ] Add error handling + user feedback
- [ ] Add eject device option

### Phase 4: Testing (Week 2-3)
- [ ] Unit tests for installer module
- [ ] Integration tests on macOS (STD10 + Mini6)
- [ ] Integration tests on Windows (STD10 + Mini6)
- [ ] Integration tests on Linux (STD10)
- [ ] Alpha release for internal testing

### Phase 5: Documentation & Release (Week 3)
- [ ] Update README.md with GUI installation as primary method
- [ ] Update AGENTS.md with new architecture
- [ ] Add screenshots to docs
- [ ] Create video tutorial (optional)
- [ ] Beta release
- [ ] Gather feedback + fix issues
- [ ] Stable release

**Estimated Timeline:** 3 weeks from approval to stable release

---

## Alternatives Considered

### Alternative 1: Keep Separate Downloads
- **Verdict:** Rejected — fails user story goals

### Alternative 2: Use AppleScript (macOS only)
- **Verdict:** Rejected — not cross-platform

### Alternative 3: WebUSB Browser App
- **Verdict:** Rejected — see `docs/spikes/2026-02-17-webusb-investigation.md`
  - WebUSB blocks MIDI devices
  - Browser support limited to Chromium
  - Would need hosted or downloaded web app anyway

---

## Recommendation

**Proceed with Approach 1: Bundle Firmware with Config Editor**

**Justification:**
1. Meets all user story goals
2. Technically feasible with existing capabilities
3. Manageable risks with clear mitigations
4. Strong user experience gains
5. Reasonable implementation timeline

**Next Steps:**
1. Get stakeholder sign-off on this spike
2. Create implementation issue/milestone
3. Begin Phase 1 (Bundle Firmware)

**Success Criteria:**
- Users can install firmware with 3 clicks (connect → click install → done)
- No terminal knowledge required
- Works on macOS, Windows, Linux
- Preserves user configs by default
- 500KB bundle size increase acceptable

---

## Appendix: Technical References

### Relevant Files
- `tools/deploy.sh` — reference implementation (Bash)
- `config-editor/src-tauri/src/device.rs` — device detection
- `config-editor/src-tauri/src/commands.rs` — filesystem operations
- `.github/workflows/ci.yml` — firmware build pipeline
- `.github/workflows/release.yml` — release packaging

### Tauri APIs
- `app_handle.path().resource_dir()` — access bundled resources
- `std::fs::copy()` — file operations
- `File::sync_all()` — Unix fsync
- `FlushFileBuffers()` — Windows sync

### Key Constraints
- CircuitPython 7.x on device (RP2040)
- USB mass storage mode (not USB MIDI for firmware install)
- File ordering critical (dependencies before code.py)
- Config preservation required for user trust

---

**End of Spike Document**
