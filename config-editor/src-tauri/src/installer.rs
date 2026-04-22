//! Firmware installer — copies the bundled CircuitPython firmware from the
//! Tauri app's resource directory to a connected MIDI Captain device.
//!
//! Ordering mirrors `tools/deploy.sh`:
//! 1. boot.py (keeps autoreload disabled on an existing install)
//! 2. core/, devices/, fonts/, lib/ — directories replace their targets wholesale
//! 3. config.json — only if missing or reset_config=true
//! 4. config-<device>.json reference configs
//! 5. code.py (LAST, so all imports are in place before the device reloads)
//! 6. VERSION
//!
//! Per-file `sync_all()` on the write handle ensures bytes reach USB flash
//! before the function returns, matching `commands::write_sync`.

use crate::commands::{validate_device_path, verify_device_connected, ConfigError};
use crate::config::DeviceType;
use serde::Serialize;
use std::fs::{self, File, OpenOptions};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use tauri::{command, AppHandle, Manager};

/// Bundled filename of the default config template for this device type.
/// Kept here rather than on `DeviceType` itself so the config crate stays
/// unaware of firmware-installer filesystem conventions.
///
/// Note: `Std10` returns `"config.json"` — that filename serves double duty
/// as both the Std10 template in the bundle *and* the active-config slot on
/// every device. The reference-config loop below skips the active device's
/// template to avoid a double-write that would otherwise be a no-op for
/// Std10 but still a wasted sync on other devices.
fn config_source_name(dt: DeviceType) -> &'static str {
    match dt {
        DeviceType::Std10 => "config.json",
        DeviceType::Mini6 => "config-mini6.json",
        DeviceType::Nano4 => "config-nano4.json",
        DeviceType::Duo2 => "config-duo2.json",
        DeviceType::One1 => "config-one1.json",
    }
}

/// Single-install lock: prevents a concurrent `install_firmware` invocation
/// (e.g. double-click, or two tabs of the same app) from interleaving writes
/// to the same device.
static INSTALL_LOCK: Mutex<()> = Mutex::new(());

#[derive(Debug, Serialize)]
pub struct InstallReport {
    pub device_type: DeviceType,
    pub files_copied: usize,
    pub version: String,
    pub config_preserved: bool,
}

/// Resolve the bundled firmware directory inside the Tauri app resources.
/// Phase 1 wires `config-editor/src-tauri/resources/firmware/**/*` into the
/// bundle; the `resources/` glob prefix is preserved in the built layout, so
/// the runtime path is `<resource_dir>/resources/firmware`.
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

/// Read `<device_root>/config.json` and parse the `device` field.
/// Returns `None` if the config is missing, unreadable, or declares an
/// unknown device type.
fn detect_device_type(device_root: &Path) -> Option<DeviceType> {
    let config_path = device_root.join("config.json");
    let contents = fs::read_to_string(&config_path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&contents).ok()?;
    let dev = value.get("device").and_then(|v| v.as_str())?;
    DeviceType::from_name(dev)
}

/// Stream-copy `src` to `dst`, then fsync the write handle before it drops.
/// Avoids buffering the whole file in memory while still guaranteeing the
/// bytes reach physical storage (same durability contract as `write_sync`).
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

/// Wipe `dst` and re-populate it from `src` (recursive). Returns file count.
///
/// The wipe-first policy mirrors `deploy.sh`'s `rsync --delete` semantics —
/// prevents stale `.py` / `.mpy` pairs from coexisting on the device and
/// triggering `ImportError` on the wrong module form being loaded.
fn copy_dir_synced(src: &Path, dst: &Path) -> Result<usize, ConfigError> {
    if dst.exists() {
        fs::remove_dir_all(dst)?;
    }
    fs::create_dir_all(dst)?;
    let mut count = 0;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let path = entry.path();
        let target = dst.join(entry.file_name());
        if path.is_dir() {
            count += copy_dir_synced(&path, &target)?;
        } else {
            copy_file_synced(&path, &target)?;
            count += 1;
        }
    }
    Ok(count)
}

/// Pure installer: takes resolved source and destination paths, no Tauri
/// context. Callable from tests with tempdirs.
pub fn install_firmware_from(
    firmware_src: &Path,
    device_path: &Path,
    reset_config: bool,
) -> Result<InstallReport, ConfigError> {
    // Pre-flight: refuse to start writing if any required source file is missing.
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

    let mut files_copied = 0usize;

    copy_file_synced(
        &firmware_src.join("boot.py"),
        &device_path.join("boot.py"),
    )?;
    files_copied += 1;

    for subdir in &["core", "devices", "fonts", "lib"] {
        let src_dir = firmware_src.join(subdir);
        if src_dir.exists() {
            files_copied += copy_dir_synced(&src_dir, &device_path.join(subdir))?;
        }
    }

    let active_config = device_path.join("config.json");
    let config_preserved = active_config.exists() && !reset_config;
    if !config_preserved {
        let src_config = firmware_src.join(config_source_name(device_type));
        copy_file_synced(&src_config, &active_config)?;
        files_copied += 1;
    }

    // Reference configs for every non-Std10 device, so users can see the
    // templates for other devices alongside their active config. Std10 is
    // skipped because its template filename is `config.json` — the active
    // slot, not a reference slot. Copying it here would clobber the active
    // config we just wrote (critical when device_type != Std10).
    //
    // For a non-Std10 active device (e.g. Mini6), we *do* re-copy the same
    // bytes to `config-mini6.json` as a reference. Same content, different
    // filename; a minor redundant write that matches deploy.sh's behavior.
    for dt in DeviceType::ALL {
        if *dt == DeviceType::Std10 {
            continue;
        }
        let name = config_source_name(*dt);
        let src = firmware_src.join(name);
        if src.exists() {
            copy_file_synced(&src, &device_path.join(name))?;
            files_copied += 1;
        }
    }

    // code.py LAST — everything else is in place before the device reloads.
    copy_file_synced(
        &firmware_src.join("code.py"),
        &device_path.join("code.py"),
    )?;
    files_copied += 1;

    let version_src = firmware_src.join("VERSION");
    let version = match fs::read_to_string(&version_src) {
        Ok(contents) => {
            copy_file_synced(&version_src, &device_path.join("VERSION"))?;
            files_copied += 1;
            contents.trim().to_string()
        }
        Err(_) => "dev".to_string(),
    };

    Ok(InstallReport {
        device_type,
        files_copied,
        version,
        config_preserved,
    })
}

/// Tauri command: install bundled firmware onto the connected device.
///
/// A process-wide `try_lock` guards against the double-click / re-entrant
/// case. A second invocation while one is in flight returns an error rather
/// than blocking — the UI should disable the button during install, and the
/// lock is a belt-and-braces backstop.
#[command]
pub fn install_firmware(
    app: AppHandle,
    device_path: String,
    reset_config: bool,
) -> Result<InstallReport, ConfigError> {
    let _guard = INSTALL_LOCK.try_lock().map_err(|_| {
        ConfigError::msg("A firmware install is already in progress on this app instance.")
    })?;
    validate_device_path(&device_path)?;
    let device = PathBuf::from(&device_path);
    verify_device_connected(&device)?;
    let firmware_src = bundled_firmware_dir(&app)?;
    install_firmware_from(&firmware_src, &device, reset_config)
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

    #[test]
    fn device_type_detected_from_device_config() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "mini6");

        let report = install_firmware_from(bundle.path(), device.path(), false).unwrap();
        assert_eq!(report.device_type, DeviceType::Mini6);
    }

    #[test]
    fn preserves_existing_config_by_default() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        let report = install_firmware_from(bundle.path(), device.path(), false).unwrap();

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

        let report = install_firmware_from(bundle.path(), device.path(), true).unwrap();

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

        let report = install_firmware_from(bundle.path(), device.path(), true).unwrap();

        assert_eq!(report.device_type, DeviceType::Mini6);
        let installed = fs::read_to_string(device.path().join("config.json")).unwrap();
        // The mini6 bundled config has `"from":"bundle"`; the seeded user config did not.
        assert!(installed.contains(r#""device":"mini6""#));
        assert!(installed.contains(r#""from":"bundle""#), "should be the bundled mini6 template, not the user seed");
        assert!(!installed.contains("user-edit"));
    }

    #[test]
    fn reference_configs_always_written() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install_firmware_from(bundle.path(), device.path(), false).unwrap();

        // Every non-active device's template should land on the device as a reference.
        for dt in DeviceType::ALL {
            if *dt == DeviceType::Std10 {
                continue; // active device in this test
            }
            let name = config_source_name(*dt);
            assert!(device.path().join(name).exists(), "reference config {} missing", name);
        }
    }

    #[test]
    fn std10_template_never_clobbers_non_std10_active_config() {
        // Regression guard: Std10's template filename is `config.json`, the
        // same filename as the active-config slot. If the reference-config
        // loop copied Std10's template, it would overwrite the Mini6 active
        // config we just wrote. Symptom if the skip breaks: device's
        // config.json ends up with `"device":"std10"` on a Mini6 device.
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "mini6");

        install_firmware_from(bundle.path(), device.path(), true).unwrap();

        let active = fs::read_to_string(device.path().join("config.json")).unwrap();
        assert!(active.contains(r#""device":"mini6""#), "active config must remain the Mini6 template, got: {}", active);
        assert!(!active.contains(r#""device":"std10""#), "Std10 template must not clobber the active slot");
    }

    #[test]
    fn stale_core_files_are_removed() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        fs::create_dir(device.path().join("core")).unwrap();
        fs::write(device.path().join("core/stale.mpy"), b"old").unwrap();

        install_firmware_from(bundle.path(), device.path(), false).unwrap();

        assert!(!device.path().join("core/stale.mpy").exists(), "stale file must be removed");
        assert!(device.path().join("core/config.py").exists(), "new file must be present");
    }

    #[test]
    fn missing_boot_py_fails_before_writing() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");
        fs::remove_file(bundle.path().join("boot.py")).unwrap();

        let err = install_firmware_from(bundle.path(), device.path(), false).unwrap_err();
        assert!(err.message.contains("boot.py"), "error should mention the missing file, got: {}", err.message);
        // No writes should have happened.
        assert!(!device.path().join("code.py").exists());
    }

    #[test]
    fn unknown_device_type_refuses_install() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        fs::write(device.path().join("config.json"), br#"{"device":"unknown"}"#).unwrap();

        let err = install_firmware_from(bundle.path(), device.path(), false).unwrap_err();
        assert!(err.message.to_lowercase().contains("device type"));
        assert!(!device.path().join("boot.py").exists());
    }

    #[test]
    fn code_py_mtime_at_or_after_boot_py() {
        // Weak but real: if `code.py` were written before `boot.py`, a mid-install
        // crash could leave a device that boots into incomplete firmware. Mtime
        // comparison is coarse (filesystem resolution) but catches gross order swaps.
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install_firmware_from(bundle.path(), device.path(), false).unwrap();

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
}
