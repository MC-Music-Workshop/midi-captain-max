//! Firmware installer — copies the bundled CircuitPython firmware from the
//! Tauri app's resource directory to a connected MIDI Captain device.
//!
//! Ordering mirrors `tools/deploy.sh`:
//! 1. boot.py (keeps autoreload disabled on an existing install)
//! 2. core/, devices/, fonts/, lib/ — files copied per-file; stale files removed
//! 3. config.json — only if missing or reset_config=true
//! 4. config-<device>.json reference configs
//! 5. code.py (LAST, so all imports are in place before the device reloads)
//! 6. VERSION
//! 7. firmware.md5 — manifest of installed bytes, used for incremental updates
//!
//! Per-file `sync_all()` on the write handle ensures bytes reach USB flash
//! before the function returns, matching `commands::write_sync`.
//!
//! Incremental updates: bundle manifest is computed at install time. If the
//! device has a `firmware.md5` from a prior install, files whose hash matches
//! the bundle are skipped. Stale files inside managed subdirs are deleted.

use crate::commands::{
    halt_and_disable_autoreload, soft_reboot_via_serial, validate_device_path,
    verify_device_connected, ConfigError,
};
use crate::config::DeviceType;
use md5::{Digest, Md5};
use serde::Serialize;
use std::collections::BTreeMap;
use std::fs::{self, File, OpenOptions};
use std::io::{BufRead, BufReader};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::ipc::Channel;
use tauri::{command, AppHandle, Manager};

/// Subdirectories the installer fully manages — stale files inside these are
/// deleted to mirror `deploy.sh`'s `rsync --delete` semantics.
const MANAGED_DIRS: &[&str] = &["core", "devices", "fonts", "lib"];

/// Bundled filename of the default config template for this device type.
fn config_source_name(dt: DeviceType) -> &'static str {
    match dt {
        DeviceType::Std10 => "config.json",
        DeviceType::Mini6 => "config-mini6.json",
        DeviceType::Nano4 => "config-nano4.json",
        DeviceType::Duo2 => "config-duo2.json",
        DeviceType::One1 => "config-one1.json",
    }
}

static INSTALL_LOCK: Mutex<()> = Mutex::new(());

#[derive(Debug, Serialize)]
pub struct InstallReport {
    pub device_type: DeviceType,
    pub files_copied: usize,
    pub files_skipped: usize,
    pub files_deleted: usize,
    pub version: String,
    pub config_preserved: bool,
}

/// Streaming progress event. Sent for every planned op (copy or delete),
/// including ops that turn into no-op skips. `current` and `total` count ops,
/// not bytes.
#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct InstallProgress {
    pub phase: InstallPhase,
    pub current: usize,
    pub total: usize,
    pub file: String,
}

#[derive(Debug, Clone, Copy, Serialize)]
#[serde(rename_all = "camelCase")]
pub enum InstallPhase {
    Planning,
    Copy,
    Skip,
    Delete,
    Manifest,
    Done,
}

fn bundled_firmware_dir(app: &AppHandle) -> Result<PathBuf, ConfigError> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| ConfigError::msg(format!("Could not resolve app resource directory: {e}")))?;
    let firmware_dir = resource_dir.join("resources").join("firmware");
    if !firmware_dir.exists() {
        return Err(ConfigError::msg(format!(
            "Bundled firmware not found at {}",
            firmware_dir.display()
        )));
    }
    Ok(firmware_dir)
}

fn detect_device_type(device_root: &Path) -> Option<DeviceType> {
    let config_path = device_root.join("config.json");
    let contents = fs::read_to_string(&config_path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&contents).ok()?;
    let dev = value.get("device").and_then(|v| v.as_str())?;
    DeviceType::from_name(dev)
}

fn copy_file_synced(src: &Path, dst: &Path) -> Result<(), ConfigError> {
    if let Some(parent) = dst.parent() {
        fs::create_dir_all(parent)?;
    }
    let mut reader = File::open(src).map_err(|e| {
        ConfigError::msg(format!("Failed to open {}: {}", src.display(), e))
    })?;
    let mut writer = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(dst)?;
    std::io::copy(&mut reader, &mut writer)?;
    writer.sync_all()?;
    Ok(())
}

/// Compute md5 of a file as lowercase hex.
fn hash_file(path: &Path) -> Result<String, ConfigError> {
    let mut f = File::open(path)
        .map_err(|e| ConfigError::msg(format!("Failed to open {}: {}", path.display(), e)))?;
    let mut hasher = Md5::new();
    std::io::copy(&mut f, &mut hasher)?;
    Ok(hex::encode(hasher.finalize()))
}

/// Walk `root` recursively, returning relative-path → md5-hex map. Paths use
/// forward slashes for cross-platform manifest stability.
fn compute_manifest(root: &Path) -> Result<BTreeMap<String, String>, ConfigError> {
    let mut out = BTreeMap::new();
    walk(root, root, &mut out)?;
    Ok(out)
}

fn walk(
    root: &Path,
    dir: &Path,
    out: &mut BTreeMap<String, String>,
) -> Result<(), ConfigError> {
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_dir() {
            walk(root, &path, out)?;
        } else {
            // Skip the manifest itself if present in bundle.
            if path.file_name().map(|n| n == "firmware.md5").unwrap_or(false) {
                continue;
            }
            let rel = path
                .strip_prefix(root)
                .map_err(|e| ConfigError::msg(format!("strip_prefix failed: {e}")))?
                .to_string_lossy()
                .replace('\\', "/");
            out.insert(rel, hash_file(&path)?);
        }
    }
    Ok(())
}

/// Read device's `firmware.md5`. Accepts md5sum format (`<hex>  <relpath>`)
/// with optional leading `./` and any whitespace separation. Missing or
/// unparseable file yields an empty map (forces full install).
fn read_device_manifest(device_root: &Path) -> BTreeMap<String, String> {
    let mut out = BTreeMap::new();
    let path = device_root.join("firmware.md5");
    let Ok(file) = File::open(&path) else {
        // Missing manifest is the expected "first-time install" path. Log a
        // single line so a user complaining "why does my reinstall copy
        // everything?" can spot it in stderr.
        eprintln!(
            "installer: no firmware.md5 at {} — full install (no incremental skips)",
            path.display()
        );
        return out;
    };
    let mut parsed = 0usize;
    let mut skipped = 0usize;
    for line in BufReader::new(file).lines().map_while(Result::ok) {
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        let mut parts = line.splitn(2, char::is_whitespace);
        let Some(hex) = parts.next() else {
            skipped += 1;
            continue;
        };
        let Some(rest) = parts.next() else {
            skipped += 1;
            continue;
        };
        let rel = rest.trim_start().trim_start_matches("./").to_string();
        if !hex.is_empty() && !rel.is_empty() {
            out.insert(rel, hex.to_lowercase());
            parsed += 1;
        } else {
            skipped += 1;
        }
    }
    if skipped > 0 {
        eprintln!(
            "installer: device manifest at {} parsed {} entries, skipped {} malformed lines",
            path.display(),
            parsed,
            skipped
        );
    }
    out
}

fn write_device_manifest(
    device_root: &Path,
    manifest: &BTreeMap<String, String>,
) -> Result<(), ConfigError> {
    let path = device_root.join("firmware.md5");
    // Build the full payload in memory, write in one fs::write call (open +
    // write_all + close), no per-line writeln! and no sync_all. The manifest
    // is purely an optimization for the next install — losing it on power
    // loss is harmless. Earlier we ended every install with `sync_all()`
    // here, but on a CircuitPython USB MSC volume that fsync can hang the
    // whole install for tens of seconds while the device's serial REPL is
    // active — visible in the GUI as "Writing manifest" never completing.
    // 80 chars/entry: md5 hex (32) + two-space separator + path (~46). Tight
    // paths re-allocate; long ones cap at one realloc. Avoids the
    // `len * 64` underestimate that triggers a reallocation on every install.
    let mut payload = String::with_capacity(manifest.len() * 80);
    for (rel, hex) in manifest {
        payload.push_str(hex);
        payload.push_str("  ");
        payload.push_str(rel);
        payload.push('\n');
    }
    fs::write(&path, payload)?;
    Ok(())
}

#[derive(Debug)]
enum Op {
    Copy { rel: String, src: PathBuf, dst: PathBuf },
    Delete { rel: String, dst: PathBuf },
}

/// True if `rel` looks like `name.py` and the bundle contains `name.mpy`
/// in the same parent dir, or vice versa. Used to flag stray `foo.py`
/// alongside our bundled `foo.mpy` for deletion before write.
fn alternate_extension_exists(
    bundle_rels: &BTreeMap<String, String>,
    rel: &str,
) -> bool {
    let alt = match rel.rsplit_once('.') {
        Some((stem, "py")) => format!("{}.mpy", stem),
        Some((stem, "mpy")) => format!("{}.py", stem),
        _ => return false,
    };
    bundle_rels.contains_key(&alt)
}

/// Build the ordered op list for the install. Top-level files always copy
/// (skip decision happens later via manifest compare). Managed subdirs add
/// per-file copies plus stale-file deletes.
fn build_plan(
    firmware_src: &Path,
    device_path: &Path,
    device_type: DeviceType,
    config_preserved: bool,
) -> Result<Vec<Op>, ConfigError> {
    let mut ops: Vec<Op> = Vec::new();

    let push_copy = |ops: &mut Vec<Op>, rel: &str| {
        ops.push(Op::Copy {
            rel: rel.to_string(),
            src: firmware_src.join(rel),
            dst: device_path.join(rel),
        });
    };

    push_copy(&mut ops, "boot.py");

    // Per managed subdir: emit deletes BEFORE copies. Reasoning:
    //
    //  - "Same-stem dup": if bundle has `foo.mpy` and the device's same dir
    //    has both `foo.mpy` and `foo.py`, the `.py` is a stray (typically
    //    left by `circup install --py` from older deploy.sh runs). CP's
    //    module-resolution rules between coexisting forms are version- and
    //    state-dependent, and the `.py` source often pulls in modules the
    //    runtime CP doesn't have (e.g. `busdisplay` on CP 7). Drop the
    //    alternate-extension twin first so the device only ever resolves
    //    against the bundled form.
    //
    //  - "Pure stale": any file under the device subdir that the bundle
    //    doesn't ship in any form.
    //
    // Doing deletes first means a partial-install crash leaves missing libs
    // (loud ImportError on next boot) rather than a silent fall-through to
    // an incompatible alternate form (the failure mode we just hit).
    for subdir in MANAGED_DIRS {
        let bundle_sub = firmware_src.join(subdir);
        let device_sub = device_path.join(subdir);

        let mut bundle_files = BTreeMap::new();
        if bundle_sub.exists() {
            walk(&bundle_sub, &bundle_sub, &mut bundle_files)?;
        }

        if device_sub.exists() {
            let mut device_files = BTreeMap::new();
            walk(&device_sub, &device_sub, &mut device_files).ok();
            for rel_in_sub in device_files.keys() {
                let bundle_file = bundle_sub.join(rel_in_sub);
                let in_bundle = bundle_file.exists();
                let alt_in_bundle = alternate_extension_exists(&bundle_files, rel_in_sub);
                if !in_bundle || alt_in_bundle {
                    let rel = format!("{}/{}", subdir, rel_in_sub);
                    ops.push(Op::Delete {
                        rel: rel.clone(),
                        dst: device_path.join(&rel),
                    });
                }
            }
        }

        for rel_in_sub in bundle_files.keys() {
            let rel = format!("{}/{}", subdir, rel_in_sub);
            push_copy(&mut ops, &rel);
        }
    }

    if !config_preserved {
        let bundled = config_source_name(device_type);
        ops.push(Op::Copy {
            rel: "config.json".to_string(),
            src: firmware_src.join(bundled),
            dst: device_path.join("config.json"),
        });
    }

    for dt in DeviceType::ALL {
        if *dt == DeviceType::Std10 {
            continue;
        }
        let name = config_source_name(*dt);
        if firmware_src.join(name).exists() {
            push_copy(&mut ops, name);
        }
    }

    push_copy(&mut ops, "code.py");

    if firmware_src.join("VERSION").exists() {
        push_copy(&mut ops, "VERSION");
    }

    Ok(ops)
}

/// Pure installer. `progress` is invoked for every op (copy/skip/delete) plus
/// a final `Manifest` and `Done` event.
pub fn install_firmware_from(
    firmware_src: &Path,
    device_path: &Path,
    reset_config: bool,
    progress: &mut dyn FnMut(InstallProgress),
) -> Result<InstallReport, ConfigError> {
    for required in &["boot.py", "code.py"] {
        let p = firmware_src.join(required);
        if !p.exists() {
            return Err(ConfigError::msg(format!(
                "Bundled firmware is missing required file: {}",
                required
            )));
        }
    }

    let device_type = detect_device_type(device_path).ok_or_else(|| {
        ConfigError::msg(
            "Could not detect device type from config.json on the device. \
             Ensure the device has a valid config.json declaring a recognized \
             'device' field (std10, mini6, nano4, duo2, one1).",
        )
    })?;

    progress(InstallProgress {
        phase: InstallPhase::Planning,
        current: 0,
        total: 0,
        file: "computing manifest".to_string(),
    });

    let bundle_manifest = compute_manifest(firmware_src)?;
    let device_manifest = read_device_manifest(device_path);

    let active_config = device_path.join("config.json");
    let config_preserved = active_config.exists() && !reset_config;

    let plan = build_plan(firmware_src, device_path, device_type, config_preserved)?;
    let total = plan.len();

    let mut files_copied = 0usize;
    let mut files_skipped = 0usize;
    let mut files_deleted = 0usize;
    // Final manifest reflects what actually ends up on the device, not the
    // full bundle. Built up as ops execute so it can't disagree with reality.
    let mut final_manifest: BTreeMap<String, String> = BTreeMap::new();

    for (idx, op) in plan.iter().enumerate() {
        let current = idx + 1;
        match op {
            Op::Copy { rel, src, dst } => {
                let bundle_hex = bundle_manifest.get(rel).cloned();
                let device_hex = device_manifest.get(rel);
                let same_hash = matches!(
                    (bundle_hex.as_ref(), device_hex),
                    (Some(a), Some(b)) if a == b
                );
                if same_hash && dst.exists() {
                    files_skipped += 1;
                    progress(InstallProgress {
                        phase: InstallPhase::Skip,
                        current,
                        total,
                        file: rel.clone(),
                    });
                } else {
                    copy_file_synced(src, dst)?;
                    files_copied += 1;
                    progress(InstallProgress {
                        phase: InstallPhase::Copy,
                        current,
                        total,
                        file: rel.clone(),
                    });
                }
                if let Some(hex) = bundle_hex {
                    final_manifest.insert(rel.clone(), hex);
                }
            }
            Op::Delete { rel, dst } => {
                if dst.exists() {
                    fs::remove_file(dst)?;
                    files_deleted += 1;
                }
                progress(InstallProgress {
                    phase: InstallPhase::Delete,
                    current,
                    total,
                    file: rel.clone(),
                });
            }
        }
    }

    // Preserved config.json is on the device but not in the plan; hash the
    // actual on-device bytes so the manifest reflects what's there.
    if config_preserved {
        if let Ok(hex) = hash_file(&active_config) {
            final_manifest.insert("config.json".to_string(), hex);
        }
    }

    // Fire a Manifest event _before_ the write so the UI can show "Writing
    // manifest" while it's in flight (and so we can tell from the last-seen
    // event whether a hang happened in the write itself or somewhere
    // earlier).
    progress(InstallProgress {
        phase: InstallPhase::Manifest,
        current: total,
        total,
        file: "firmware.md5".to_string(),
    });
    write_device_manifest(device_path, &final_manifest)?;

    let version = fs::read_to_string(firmware_src.join("VERSION"))
        .map(|s| s.trim().to_string())
        .unwrap_or_else(|_| "dev".to_string());

    progress(InstallProgress {
        phase: InstallPhase::Done,
        current: total,
        total,
        file: String::new(),
    });

    Ok(InstallReport {
        device_type,
        files_copied,
        files_skipped,
        files_deleted,
        version,
        config_preserved,
    })
}

/// Read a firmware version from a `VERSION` file in `dir`. Returns the file's
/// trimmed contents or `None` if the file is missing/unreadable.
fn read_version_file(dir: &Path) -> Option<String> {
    fs::read_to_string(dir.join("VERSION"))
        .ok()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct FirmwareVersions {
    /// Version on the device, if a `VERSION` file is present at the device
    /// root. `None` indicates an OEM / unmanaged install — the device wasn't
    /// flashed by us (or the file was deleted).
    pub device: Option<String>,
    /// Version of the firmware bundled in this app build.
    pub bundled: String,
}

/// Tauri command: report the installed firmware version on the device and the
/// version of the bundled firmware this app would install. Used by the UI to
/// show "OEM" / "v1.x.y → v1.x.z" before the user clicks Install.
#[command]
pub fn get_firmware_versions(
    app: AppHandle,
    device_path: String,
) -> Result<FirmwareVersions, ConfigError> {
    validate_device_path(&device_path)?;
    let device = PathBuf::from(&device_path);
    verify_device_connected(&device)?;
    let firmware_src = bundled_firmware_dir(&app)?;

    Ok(FirmwareVersions {
        device: read_version_file(&device),
        bundled: read_version_file(&firmware_src).unwrap_or_else(|| "dev".to_string()),
    })
}

/// Tauri command: install bundled firmware onto the connected device.
/// `on_progress` receives streaming `InstallProgress` events.
///
/// `async` + `spawn_blocking` offloads the per-file `sync_all()` storm to a
/// blocking-pool thread. A sync `#[command]` would peg Tauri's IPC thread for
/// the duration of the install (visible as a beach ball / unresponsive UI),
/// and would also stall the Channel that feeds progress events back to JS.
///
/// Wraps the pure installer with two serial-port operations:
///
/// 1. **Pre-flight halt**: send Ctrl-C + `supervisor.runtime.autoreload = False`
///    so CircuitPython doesn't soft-reboot mid-install. Without this, CP
///    detects file changes, schedules a reload, briefly remounts CIRCUITPY
///    read-only, and the final manifest write blocks indefinitely — the
///    "never reaches Done phase" symptom.
///
/// 2. **Post-install soft reboot**: send Ctrl-C + Ctrl-D so the freshly
///    installed firmware loads cleanly. Best-effort: a failure here doesn't
///    invalidate a successful install (user can power-cycle).
#[command]
pub async fn install_firmware(
    app: AppHandle,
    device_path: String,
    reset_config: bool,
    on_progress: Channel<InstallProgress>,
) -> Result<InstallReport, ConfigError> {
    validate_device_path(&device_path)?;
    let device = PathBuf::from(&device_path);
    verify_device_connected(&device)?;
    let firmware_src = bundled_firmware_dir(&app)?;

    tauri::async_runtime::spawn_blocking(move || {
        let _guard = INSTALL_LOCK.try_lock().map_err(|_| {
            ConfigError::msg("A firmware install is already in progress on this app instance.")
        })?;

        // Best-effort: bundled `boot.py` already calls
        // `supervisor.disable_autoreload()` on flashed devices, so the
        // pre-flight is redundant in steady state. Hard-failing here would
        // also abort the install whenever another process holds the serial
        // port (tio, screen, devtools serial console), which is too brittle.
        // The downside on a fresh install with autoreload still on: CP may
        // soft-reboot mid-write — but `boot.py` is the FIRST file we copy,
        // so the autoreload-off setting takes effect before the bulk of
        // writes. Worst case is a partial install on the very first flash;
        // the manifest-based incremental retry on the next install fills
        // any gaps.
        let _ = halt_and_disable_autoreload(&device);

        let mut emit = |p: InstallProgress| {
            let _ = on_progress.send(p);
        };
        let report = install_firmware_from(&firmware_src, &device, reset_config, &mut emit)?;

        // Best-effort: a soft-reboot failure here is non-fatal — the firmware
        // is already on disk, user can power-cycle. We swallow the error.
        let _ = soft_reboot_via_serial(&device);

        Ok(report)
    })
    .await
    .map_err(|e| ConfigError::msg(format!("Install task panicked: {e}")))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn make_bundle(dir: &Path) {
        fs::write(dir.join("boot.py"), b"# boot").unwrap();
        fs::write(dir.join("code.py"), b"# code").unwrap();
        fs::write(dir.join("config.json"), br#"{"device":"std10","from":"bundle"}"#).unwrap();
        fs::write(dir.join("config-mini6.json"), br#"{"device":"mini6","from":"bundle"}"#).unwrap();
        fs::write(dir.join("config-nano4.json"), br#"{"device":"nano4"}"#).unwrap();
        fs::write(dir.join("config-duo2.json"), br#"{"device":"duo2"}"#).unwrap();
        fs::write(dir.join("config-one1.json"), br#"{"device":"one1"}"#).unwrap();
        fs::write(dir.join("VERSION"), b"v0.0.0-test\n").unwrap();

        fs::create_dir(dir.join("core")).unwrap();
        fs::write(dir.join("core/config.py"), b"# core.config").unwrap();
        fs::write(dir.join("core/button.py"), b"# core.button").unwrap();

        fs::create_dir(dir.join("devices")).unwrap();
        fs::write(dir.join("devices/std10.py"), b"# std10").unwrap();
        fs::write(dir.join("devices/mini6.py"), b"# mini6").unwrap();

        fs::create_dir(dir.join("fonts")).unwrap();
        fs::write(dir.join("fonts/PTSans.pcf"), b"fakepcf").unwrap();

        fs::create_dir(dir.join("lib")).unwrap();
        fs::write(dir.join("lib/adafruit_st7789.mpy"), b"fakempy").unwrap();
    }

    fn seed_device(dir: &Path, device: &str) {
        fs::write(
            dir.join("config.json"),
            format!(r#"{{"device":"{}","custom":"user-edit"}}"#, device).as_bytes(),
        )
        .unwrap();
    }

    fn install(bundle: &Path, device: &Path, reset: bool) -> InstallReport {
        let mut sink = |_p: InstallProgress| {};
        install_firmware_from(bundle, device, reset, &mut sink).unwrap()
    }

    #[test]
    fn device_type_detected_from_device_config() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "mini6");

        let report = install(bundle.path(), device.path(), false);
        assert_eq!(report.device_type, DeviceType::Mini6);
    }

    #[test]
    fn preserves_existing_config_by_default() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        let report = install(bundle.path(), device.path(), false);

        assert!(report.config_preserved);
        let cfg = fs::read_to_string(device.path().join("config.json")).unwrap();
        assert!(cfg.contains(r#""custom":"user-edit""#), "user config must survive");
    }

    #[test]
    fn reset_config_overwrites_user_edits() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        let report = install(bundle.path(), device.path(), true);

        assert!(!report.config_preserved);
        let cfg = fs::read_to_string(device.path().join("config.json")).unwrap();
        assert!(cfg.contains(r#""from":"bundle""#), "bundled config must replace user's");
        assert!(!cfg.contains("user-edit"));
    }

    #[test]
    fn mini6_device_gets_mini6_default_config_on_reset() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "mini6");

        let report = install(bundle.path(), device.path(), true);

        assert_eq!(report.device_type, DeviceType::Mini6);
        let installed = fs::read_to_string(device.path().join("config.json")).unwrap();
        assert!(installed.contains(r#""device":"mini6""#));
        assert!(installed.contains(r#""from":"bundle""#));
        assert!(!installed.contains("user-edit"));
    }

    #[test]
    fn reference_configs_always_written() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install(bundle.path(), device.path(), false);

        for dt in DeviceType::ALL {
            if *dt == DeviceType::Std10 {
                continue;
            }
            let name = config_source_name(*dt);
            assert!(device.path().join(name).exists(), "reference config {} missing", name);
        }
    }

    #[test]
    fn std10_template_never_clobbers_non_std10_active_config() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "mini6");

        install(bundle.path(), device.path(), true);

        let active = fs::read_to_string(device.path().join("config.json")).unwrap();
        assert!(active.contains(r#""device":"mini6""#), "got: {}", active);
        assert!(!active.contains(r#""device":"std10""#));
    }

    #[test]
    fn stale_core_files_are_removed() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        fs::create_dir(device.path().join("core")).unwrap();
        fs::write(device.path().join("core/stale.mpy"), b"old").unwrap();

        let report = install(bundle.path(), device.path(), false);

        assert!(!device.path().join("core/stale.mpy").exists());
        assert!(device.path().join("core/config.py").exists());
        assert!(report.files_deleted >= 1);
    }

    #[test]
    fn missing_boot_py_fails_before_writing() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");
        fs::remove_file(bundle.path().join("boot.py")).unwrap();

        let mut sink = |_p: InstallProgress| {};
        let err = install_firmware_from(bundle.path(), device.path(), false, &mut sink).unwrap_err();
        assert!(err.message.contains("boot.py"), "got: {}", err.message);
        assert!(!device.path().join("code.py").exists());
    }

    #[test]
    fn unknown_device_type_refuses_install() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        fs::write(device.path().join("config.json"), br#"{"device":"unknown"}"#).unwrap();

        let mut sink = |_p: InstallProgress| {};
        let err = install_firmware_from(bundle.path(), device.path(), false, &mut sink).unwrap_err();
        assert!(err.message.to_lowercase().contains("device type"));
        assert!(!device.path().join("boot.py").exists());
    }

    #[test]
    fn code_py_mtime_at_or_after_boot_py() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install(bundle.path(), device.path(), false);

        let boot_mtime = fs::metadata(device.path().join("boot.py"))
            .unwrap()
            .modified()
            .unwrap();
        let code_mtime = fs::metadata(device.path().join("code.py"))
            .unwrap()
            .modified()
            .unwrap();
        assert!(code_mtime >= boot_mtime);
    }

    #[test]
    fn same_stem_py_is_deleted_when_bundle_ships_mpy() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        // Device has BOTH the .mpy (matching bundle) and a stray .py for the
        // same module name — the failure mode that bricked a real device.
        fs::create_dir_all(device.path().join("lib")).unwrap();
        fs::write(
            device.path().join("lib/adafruit_st7789.mpy"),
            b"fakempy",
        )
        .unwrap();
        fs::write(
            device.path().join("lib/adafruit_st7789.py"),
            b"raise ImportError('cp9 only')",
        )
        .unwrap();

        let report = install(bundle.path(), device.path(), false);

        assert!(
            !device.path().join("lib/adafruit_st7789.py").exists(),
            "stray .py twin must be removed when bundle ships the .mpy"
        );
        assert!(
            device.path().join("lib/adafruit_st7789.mpy").exists(),
            ".mpy from bundle must remain"
        );
        assert!(report.files_deleted >= 1);
    }

    #[test]
    fn delete_ops_run_before_copy_ops_in_managed_dir() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        fs::create_dir_all(device.path().join("lib")).unwrap();
        fs::write(device.path().join("lib/adafruit_st7789.py"), b"old").unwrap();

        let mut events: Vec<InstallProgress> = Vec::new();
        {
            let mut sink = |p: InstallProgress| events.push(p);
            install_firmware_from(bundle.path(), device.path(), false, &mut sink).unwrap();
        }

        // For the lib subdir: the Delete event for `lib/adafruit_st7789.py`
        // must appear before any Copy event for `lib/adafruit_st7789.mpy`.
        let del_idx = events
            .iter()
            .position(|p| matches!(p.phase, InstallPhase::Delete) && p.file == "lib/adafruit_st7789.py")
            .expect("delete event for stray .py");
        let copy_idx = events
            .iter()
            .position(|p| {
                matches!(p.phase, InstallPhase::Copy | InstallPhase::Skip)
                    && p.file == "lib/adafruit_st7789.mpy"
            })
            .expect("copy/skip event for bundled .mpy");
        assert!(
            del_idx < copy_idx,
            "delete must precede copy in same managed subdir (del={}, copy={})",
            del_idx,
            copy_idx,
        );
    }

    // ---- Phase 2b additions ----

    #[test]
    fn manifest_written_after_install() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install(bundle.path(), device.path(), false);

        let manifest_path = device.path().join("firmware.md5");
        assert!(manifest_path.exists(), "firmware.md5 must be written");
        let contents = fs::read_to_string(&manifest_path).unwrap();
        assert!(contents.contains("boot.py"));
        assert!(contents.contains("code.py"));
        assert!(contents.contains("core/config.py"));
        // Two-space md5sum format
        for line in contents.lines() {
            assert!(line.contains("  "), "line should be md5sum-format: {}", line);
        }
    }

    #[test]
    fn incremental_skips_unchanged_files() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        // First install populates manifest.
        let r1 = install(bundle.path(), device.path(), false);
        assert!(r1.files_copied > 0);
        assert_eq!(r1.files_skipped, 0);

        // Second install: nothing changed in bundle → all files skip.
        let r2 = install(bundle.path(), device.path(), false);
        assert!(r2.files_skipped > 0, "expected skips, got {:?}", r2);
        // boot.py/code.py/configs/version + core/devices/fonts/lib all skip.
        assert_eq!(r2.files_copied, 0, "no copies expected on no-op reinstall");
    }

    #[test]
    fn incremental_copies_changed_files_only() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install(bundle.path(), device.path(), false);

        // Mutate one bundle file.
        fs::write(bundle.path().join("core/button.py"), b"# updated").unwrap();

        let r2 = install(bundle.path(), device.path(), false);
        assert_eq!(r2.files_copied, 1, "only changed file should copy, got {:?}", r2);
        assert!(r2.files_skipped > 0);

        let installed = fs::read(device.path().join("core/button.py")).unwrap();
        assert_eq!(installed, b"# updated");
    }

    #[test]
    fn progress_events_fire_in_order() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        let mut events: Vec<InstallProgress> = Vec::new();
        {
            let mut sink = |p: InstallProgress| events.push(p);
            install_firmware_from(bundle.path(), device.path(), false, &mut sink).unwrap();
        }

        assert!(matches!(events.first().unwrap().phase, InstallPhase::Planning));
        assert!(matches!(events.last().unwrap().phase, InstallPhase::Done));

        let manifest_seen = events
            .iter()
            .any(|p| matches!(p.phase, InstallPhase::Manifest));
        assert!(manifest_seen, "manifest event must fire");

        // current monotonic among in-plan ops.
        let in_plan: Vec<_> = events
            .iter()
            .filter(|p| matches!(
                p.phase,
                InstallPhase::Copy | InstallPhase::Skip | InstallPhase::Delete
            ))
            .collect();
        for w in in_plan.windows(2) {
            assert!(w[1].current >= w[0].current, "current must be monotonic");
        }
        // All in-plan ops share the same total.
        if let Some(first) = in_plan.first() {
            for p in &in_plan {
                assert_eq!(p.total, first.total);
            }
        }
    }

    #[test]
    fn manifest_excludes_bundle_files_not_in_plan() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        // Add a bundle file that isn't part of the install plan.
        fs::write(
            bundle.path().join("config-example-extra.json"),
            br#"{"device":"std10","kind":"example"}"#,
        )
        .unwrap();
        seed_device(device.path(), "std10");

        install(bundle.path(), device.path(), false);

        let manifest = fs::read_to_string(device.path().join("firmware.md5")).unwrap();
        assert!(
            !manifest.contains("config-example-extra.json"),
            "manifest must only list files actually installed, got:\n{}",
            manifest
        );
        assert!(manifest.contains("boot.py"));
        assert!(manifest.contains("config.json"), "preserved config.json must be in manifest");
    }

    #[test]
    fn manifest_preserved_config_uses_device_bytes_hash() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install(bundle.path(), device.path(), false);

        // Compute hash of bundle's std10 template vs. the actual device config.
        let bundle_hash = hash_file(&bundle.path().join("config.json")).unwrap();
        let device_hash = hash_file(&device.path().join("config.json")).unwrap();
        assert_ne!(
            bundle_hash, device_hash,
            "test premise: seeded user config differs from bundle template"
        );

        let manifest = fs::read_to_string(device.path().join("firmware.md5")).unwrap();
        assert!(manifest.contains(&device_hash), "manifest should record device-bytes hash for preserved config.json");
        // Find the config.json line specifically — bundle hash must not appear next to config.json.
        let config_line = manifest
            .lines()
            .find(|l| l.ends_with("  config.json"))
            .expect("config.json line in manifest");
        assert!(config_line.starts_with(&device_hash));
        assert!(!config_line.starts_with(&bundle_hash));
    }

    #[test]
    fn manifest_roundtrip_skips_after_external_rewrite() {
        // Hand-craft a manifest and verify reads parse it.
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        // Compute bundle manifest, write it to device pre-install, also copy
        // every bundle file onto the device with matching bytes. Now first
        // install should be a full no-op-skip.
        let bm = compute_manifest(bundle.path()).unwrap();
        for rel in bm.keys() {
            let src = bundle.path().join(rel);
            let dst = device.path().join(rel);
            if let Some(parent) = dst.parent() {
                fs::create_dir_all(parent).unwrap();
            }
            fs::copy(&src, &dst).unwrap();
        }
        // Overwrite device config.json with the seeded user edit again, but
        // its hash now differs from the bundle template — so the active
        // config copy step is gated by `config_preserved`, not the manifest.
        seed_device(device.path(), "std10");
        write_device_manifest(device.path(), &bm).unwrap();

        let r = install(bundle.path(), device.path(), false);
        // config.json is preserved (config_preserved=true), so it isn't in the plan.
        // Every other file matches → all skips.
        assert_eq!(r.files_copied, 0);
        assert!(r.files_skipped > 0);
    }
}
