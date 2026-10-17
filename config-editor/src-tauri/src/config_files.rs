//! Whole-config files on the host (#36): open, save, and start new configs with
//! no device attached. Separate from `read_config_raw`/`write_config_raw`, which
//! are device-scoped by design (`validate_device_path`, `verify_device_connected`).
//! Like page templates, these take any picker-chosen path — the same accepted
//! tradeoff recorded in `config-editor/AGENTS.md`.

use crate::commands::ConfigError;
use crate::config::{migrate_to_pages, DeviceType, MidiCaptainConfig};
use crate::installer::{bundled_firmware_dir, config_source_name, detect_device_type};
use crate::templates::mcm_documents_root;
use std::fs;
use std::path::Path;
use tauri::{command, AppHandle};

/// Read `path`, migrate legacy flat configs to pages, return pretty JSON.
pub(crate) fn read_config_file(path: &Path) -> Result<String, ConfigError> {
    let contents = fs::read_to_string(path)?;
    let value: serde_json::Value = serde_json::from_str(&contents)?;
    Ok(serde_json::to_string_pretty(&migrate_to_pages(value))?)
}

/// Validate `json` as a config and write it to `path` as pretty JSON. Writes to a
/// temp file in the same folder and renames it into place, so a crash mid-save
/// can't leave a half-written config. Invalid configs never touch the target.
pub(crate) fn write_config_file(path: &Path, json: &str) -> Result<(), ConfigError> {
    let config: MidiCaptainConfig = serde_json::from_str(json)?;
    if let Err(errors) = config.validate() {
        return Err(ConfigError {
            message: "Validation failed".to_string(),
            details: Some(errors),
        });
    }
    let pretty = serde_json::to_string_pretty(&config)?;

    let mut tmp_name = path.file_name().unwrap_or_default().to_os_string();
    tmp_name.push(".tmp");
    let tmp = path.with_file_name(tmp_name);
    let result = fs::write(&tmp, pretty.as_bytes()).and_then(|_| fs::rename(&tmp, path));
    if result.is_err() {
        let _ = fs::remove_file(&tmp);
    }
    result?;
    Ok(())
}

/// Bundled default config for `device` from `firmware_dir`, as pretty JSON.
pub(crate) fn read_default_config(firmware_dir: &Path, device: DeviceType) -> Result<String, ConfigError> {
    read_config_file(&firmware_dir.join(config_source_name(device)))
}

#[command]
pub fn configs_dir(app: AppHandle) -> Result<String, ConfigError> {
    let dir = mcm_documents_root(&app)?.join("configs");
    fs::create_dir_all(&dir)?;
    Ok(dir.to_string_lossy().to_string())
}

#[command]
pub fn open_config_file(path: String) -> Result<String, ConfigError> {
    read_config_file(Path::new(&path))
}

#[command]
pub fn save_config_file(path: String, json: String) -> Result<(), ConfigError> {
    write_config_file(Path::new(&path), &json)
}

#[command]
pub fn default_config(app: AppHandle, device: DeviceType) -> Result<String, ConfigError> {
    read_default_config(&bundled_firmware_dir(&app)?, device)
}

/// The `device` field of the device's current `config.json`, or `None` when it
/// isn't readable (Save to Device uses this for the type-mismatch check).
#[command]
pub fn device_config_type(device_path: String) -> Result<Option<DeviceType>, ConfigError> {
    crate::commands::validate_device_path(&device_path)?;
    Ok(detect_device_type(Path::new(&device_path)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    fn firmware_dev() -> PathBuf {
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..").join("firmware").join("dev")
    }

    #[test]
    fn saved_file_opens_back_unchanged() {
        let dir = tempfile::tempdir().unwrap();
        let json = read_default_config(&firmware_dev(), DeviceType::Mini6).unwrap();
        let path = dir.path().join("mine.json");
        write_config_file(&path, &json).unwrap();
        // The first save fills in serde defaults; after that, open → save is stable.
        let opened = read_config_file(&path).unwrap();
        write_config_file(&path, &opened).unwrap();
        assert_eq!(read_config_file(&path).unwrap(), opened);
    }

    #[test]
    fn invalid_config_fails_and_leaves_existing_file_untouched() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("mine.json");
        fs::write(&path, "original").unwrap();
        // Parseable but invalid: a bad button count for the device is a validate() failure.
        let mut v: serde_json::Value =
            serde_json::from_str(&read_default_config(&firmware_dev(), DeviceType::Mini6).unwrap()).unwrap();
        v["pages"][0]["buttons"] = serde_json::json!([]);
        assert!(write_config_file(&path, &v.to_string()).is_err());
        assert!(write_config_file(&path, "not json").is_err());
        assert_eq!(fs::read_to_string(&path).unwrap(), "original");
    }

    #[test]
    fn legacy_flat_config_opens_as_pages() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("legacy.json");
        fs::write(&path, r#"{"device":"one1","buttons":[{"label":"B0","cc":20,"color":"green"}]}"#).unwrap();
        let v: serde_json::Value = serde_json::from_str(&read_config_file(&path).unwrap()).unwrap();
        assert!(v.get("buttons").is_none());
        assert_eq!(v["pages"][0]["buttons"][0]["label"], "B0");
    }

    #[test]
    fn default_config_round_trips_for_every_device_type() {
        for &device in DeviceType::ALL {
            let json = read_default_config(&firmware_dev(), device).unwrap();
            let config: MidiCaptainConfig = serde_json::from_str(&json).unwrap();
            assert_eq!(config.device, device);
            config.validate().unwrap_or_else(|e| panic!("{device:?}: {e:?}"));
        }
    }
}
