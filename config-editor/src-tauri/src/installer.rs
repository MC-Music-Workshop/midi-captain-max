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

use crate::commands::{
    validate_device_path, verify_device_connected, write_sync, ConfigError,
};
use serde::Serialize;
use std::fs;
use std::path::{Path, PathBuf};
use tauri::{command, AppHandle, Manager};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DeviceType {
    Std10,
    Mini6,
    Nano4,
    Duo2,
    One1,
}

impl DeviceType {
    /// Bundled filename of the default config for this device type.
    fn config_source_name(self) -> &'static str {
        match self {
            DeviceType::Std10 => "config.json",
            DeviceType::Mini6 => "config-mini6.json",
            DeviceType::Nano4 => "config-nano4.json",
            DeviceType::Duo2 => "config-duo2.json",
            DeviceType::One1 => "config-one1.json",
        }
    }

    fn parse(s: &str) -> Option<Self> {
        match s {
            "std10" => Some(DeviceType::Std10),
            "mini6" => Some(DeviceType::Mini6),
            "nano4" => Some(DeviceType::Nano4),
            "duo2" => Some(DeviceType::Duo2),
            "one1" => Some(DeviceType::One1),
            _ => None,
        }
    }
}

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
    DeviceType::parse(dev)
}

/// Copy a single file, syncing the write to physical storage before returning.
fn copy_file_synced(src: &Path, dst: &Path) -> Result<(), ConfigError> {
    if let Some(parent) = dst.parent() {
        fs::create_dir_all(parent)?;
    }
    let data = fs::read(src).map_err(|e| ConfigError::msg(format!(
        "Failed to read {}: {}", src.display(), e
    )))?;
    write_sync(dst, &data)?;
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

/// Reference configs deploy.sh pushes alongside the active `config.json`
/// so every device type's template is available on the device for inspection.
const REFERENCE_CONFIGS: &[&str] = &[
    "config-one1.json",
    "config-duo2.json",
    "config-mini6.json",
    "config-nano4.json",
];

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

    // 1. boot.py
    copy_file_synced(
        &firmware_src.join("boot.py"),
        &device_path.join("boot.py"),
    )?;
    files_copied += 1;

    // 2. Core modules, device definitions, fonts, libraries — wipe + copy.
    for subdir in &["core", "devices", "fonts", "lib"] {
        let src_dir = firmware_src.join(subdir);
        if src_dir.exists() {
            files_copied += copy_dir_synced(&src_dir, &device_path.join(subdir))?;
        }
    }

    // 3. config.json — preserve unless caller opts in to reset.
    let active_config = device_path.join("config.json");
    let config_preserved = active_config.exists() && !reset_config;
    if !config_preserved {
        let src_config = firmware_src.join(device_type.config_source_name());
        copy_file_synced(&src_config, &active_config)?;
        files_copied += 1;
    }

    // 4. Reference configs for every supported device.
    for name in REFERENCE_CONFIGS {
        let src = firmware_src.join(name);
        if src.exists() {
            copy_file_synced(&src, &device_path.join(name))?;
            files_copied += 1;
        }
    }

    // 5. code.py LAST.
    copy_file_synced(
        &firmware_src.join("code.py"),
        &device_path.join("code.py"),
    )?;
    files_copied += 1;

    // 6. VERSION.
    let version_src = firmware_src.join("VERSION");
    let version = if version_src.exists() {
        let v = fs::read_to_string(&version_src)?.trim().to_string();
        copy_file_synced(&version_src, &device_path.join("VERSION"))?;
        files_copied += 1;
        v
    } else {
        "dev".to_string()
    };

    Ok(InstallReport {
        device_type,
        files_copied,
        version,
        config_preserved,
    })
}

/// Tauri command: install bundled firmware onto the connected device.
#[command]
pub fn install_firmware(
    app: AppHandle,
    device_path: String,
    reset_config: bool,
) -> Result<InstallReport, ConfigError> {
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
        fs::write(dir.join("config-mini6.json"), br#"{"device":"mini6"}"#).unwrap();
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
    fn mini6_device_gets_mini6_default_config_on_fresh_install() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        // Seed a mini6 config, then delete it so detect_device_type falls back —
        // simulating "device had config.json but user removed it". The test is
        // really about: when we DO install a fresh config.json, is it the mini6 one?
        seed_device(device.path(), "mini6");
        let user_config = device.path().join("config.json");
        // Detect type from user config first, then remove it to force fresh install.
        let expected = detect_device_type(device.path()).unwrap();
        assert_eq!(expected, DeviceType::Mini6);
        fs::remove_file(&user_config).unwrap();
        // Re-seed to let install succeed (detect needs a device)
        seed_device(device.path(), "mini6");

        let report = install_firmware_from(bundle.path(), device.path(), true).unwrap();
        assert_eq!(report.device_type, DeviceType::Mini6);
        let installed = fs::read_to_string(device.path().join("config.json")).unwrap();
        // Bundled mini6 config contains `"device":"mini6"` and no `"custom"` field.
        assert!(installed.contains(r#""device":"mini6""#));
        assert!(!installed.contains("custom"));
    }

    #[test]
    fn reference_configs_always_written() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        install_firmware_from(bundle.path(), device.path(), false).unwrap();

        for name in REFERENCE_CONFIGS {
            assert!(device.path().join(name).exists(), "reference config {} missing", name);
        }
    }

    #[test]
    fn stale_core_files_are_removed() {
        let bundle = TempDir::new().unwrap();
        let device = TempDir::new().unwrap();
        make_bundle(bundle.path());
        seed_device(device.path(), "std10");

        // Simulate an older installation with a .mpy that's no longer in the bundle.
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
        assert!(err.message.contains("boot.py"), "error message should mention the missing file, got: {}", err.message);
        // code.py on device should not have been written
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
    fn code_py_written_last() {
        // If code.py exists on device before other files are copied, and the
        // install fails midway, the device could try to import missing modules
        // from core/. Verify ordering by staging a failure in the bundle after
        // boot.py but before code.py. We do this by removing code.py from the
        // bundle AFTER pre-flight. (Pre-flight catches it, so this test can't
        // directly observe the order.) Instead, just assert code.py and VERSION
        // modification times are >= boot.py's in a normal run.
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
        assert!(code_mtime >= boot_mtime, "code.py must be written at or after boot.py");
    }
}
