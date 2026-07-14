//! Page template import/export (#15 P4d). Templates are host-side JSON files,
//! one `Page` object per file. Import checks the page's *shape* against the
//! current device (see `device_shape_errors`) — no silent reshaping (D9);
//! value-level problems import fine and surface as normal in-editor errors.

use crate::commands::{write_sync, ConfigError};
use crate::config::{DeviceType, Page};
use std::fs;
use std::path::Path;
use tauri::{command, AppHandle, Manager};

#[derive(Debug, serde::Serialize)]
pub struct TemplateInfo {
    pub name: String, // file stem, e.g. "Lead Tone"
    pub path: String, // absolute path
}

/// Write `page` to `path` as pretty JSON. Overwrites.
pub(crate) fn write_template(path: &Path, page: &Page) -> Result<(), ConfigError> {
    let pretty = serde_json::to_string_pretty(page)?;
    write_sync(path, pretty.as_bytes())?;
    Ok(())
}

/// Button count the device expects per page (mirrors the match in
/// `MidiCaptainConfig::validate`). Kept local to avoid widening config.rs's API.
fn expected_button_count(device: DeviceType) -> usize {
    match device {
        DeviceType::Std10 => 10,
        DeviceType::Mini6 => 6,
        DeviceType::Nano4 => 4,
        DeviceType::Duo2 => 2,
        DeviceType::One1 => 1,
    }
}

/// Device-*shape* problems the editor cannot fix for `device` — the only reasons
/// to reject an imported template outright (D9: no silent reshaping). Value
/// problems (out-of-range jump targets, CC/channel/step values, long labels) are
/// deliberately NOT checked here: the page is inserted and those surface as
/// normal in-editor validation errors the user can fix, with save blocked until
/// they do. This mirrors D9's literal scope ("button count, capabilities").
fn device_shape_errors(device: DeviceType, page: &Page) -> Vec<String> {
    let mut errs = Vec::new();
    let expected = expected_button_count(device);
    if page.buttons.len() != expected {
        errs.push(format!(
            "This template has {} buttons; {:?} supports {}.",
            page.buttons.len(), device, expected
        ));
    }
    if device != DeviceType::Std10 {
        if page.encoder.is_some() {
            errs.push(format!("{:?} does not support an encoder.", device));
        }
        if page.expression.is_some() {
            errs.push(format!("{:?} does not support expression pedals.", device));
        }
    }
    errs
}

/// Read a template file, check its shape against `device`, and return the page as
/// a JSON value ready to insert. Value-level problems are left for in-editor
/// validation (see `device_shape_errors`).
pub(crate) fn read_template(path: &Path, device: DeviceType) -> Result<serde_json::Value, ConfigError> {
    let contents = fs::read_to_string(path)?;
    let value: serde_json::Value = serde_json::from_str(&contents)?;

    // Shape guard: must deserialize as a Page (rejects whole-config or junk files).
    let page: Page = serde_json::from_value(value)
        .map_err(|e| ConfigError::msg(format!("Not a valid page template: {e}")))?;

    let shape = device_shape_errors(device, &page);
    if !shape.is_empty() {
        return Err(ConfigError {
            message: "Template is not valid for this device".to_string(),
            details: Some(shape),
        });
    }

    Ok(serde_json::to_value(&page)?)
}

/// List `*.json` templates in `dir` (created if absent), sorted by file stem.
pub(crate) fn list_templates_in(dir: &Path) -> Result<Vec<TemplateInfo>, ConfigError> {
    fs::create_dir_all(dir)?;
    let mut out = Vec::new();
    for entry in fs::read_dir(dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.is_file() && path.extension().and_then(|e| e.to_str()) == Some("json") {
            if let Some(stem) = path.file_stem().and_then(|s| s.to_str()) {
                out.push(TemplateInfo {
                    name: stem.to_string(),
                    path: path.to_string_lossy().to_string(),
                });
            }
        }
    }
    out.sort_by(|a, b| a.name.cmp(&b.name));
    Ok(out)
}

/// Absolute path of the default templates folder
/// (`~/Documents/MIDICaptainMAX/templates`), created on demand. The frontend
/// uses this as the file pickers' default path. Lives under Documents rather
/// than the hidden app-data dir so users can find and manage their templates
/// in Finder (user request, 2026-07-13). A sibling `pages/` folder is created
/// alongside, reserved for saved pages.
fn templates_dir(app: &AppHandle) -> Result<std::path::PathBuf, ConfigError> {
    let root = app
        .path()
        .document_dir()
        .map_err(|e| ConfigError::msg(format!("Could not resolve Documents dir: {e}")))?
        .join("MIDICaptainMAX");
    fs::create_dir_all(root.join("pages"))?;
    let dir = root.join("templates");
    fs::create_dir_all(&dir)?;
    Ok(dir)
}

#[command]
pub fn page_templates_dir(app: AppHandle) -> Result<String, ConfigError> {
    Ok(templates_dir(&app)?.to_string_lossy().to_string())
}

#[command]
pub fn export_page_template(path: String, page: Page) -> Result<(), ConfigError> {
    write_template(Path::new(&path), &page)
}

#[command]
pub fn import_page_template(path: String, device: DeviceType) -> Result<serde_json::Value, ConfigError> {
    read_template(Path::new(&path), device)
}

#[command]
pub fn list_page_templates(app: AppHandle) -> Result<Vec<TemplateInfo>, ConfigError> {
    list_templates_in(&templates_dir(&app)?)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn a_page() -> Page {
        serde_json::from_value(json!({
            "name": "Lead", "buttons": [{"label": "B0", "cc": 20, "color": "green"}]
        })).unwrap()
    }

    #[test]
    fn write_then_read_back_is_a_valid_page() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("lead.json");
        write_template(&path, &a_page()).unwrap();
        let back: Page = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(back.name.as_deref(), Some("Lead"));
        assert_eq!(back.buttons.len(), 1);
    }

    fn write_json(dir: &Path, name: &str, v: serde_json::Value) -> std::path::PathBuf {
        let p = dir.join(name);
        fs::write(&p, serde_json::to_string(&v).unwrap()).unwrap();
        p
    }

    #[test]
    fn import_accepts_a_shape_matching_page() {
        let dir = tempfile::tempdir().unwrap();
        let p = write_json(dir.path(), "ok.json",
            json!({ "name": "Lead", "buttons": [{"label": "B0", "cc": 20, "color": "green"}] }));
        let value = read_template(&p, DeviceType::One1).unwrap();
        assert_eq!(value["name"], "Lead");
    }

    #[test]
    fn import_rejects_wrong_button_count_for_device() {
        let dir = tempfile::tempdir().unwrap();
        // A 10-button page (STD10-shaped) imported into a one1 config must reject:
        // one1 renders 1 button row, so 10 buttons can't be fixed in the editor.
        let buttons: Vec<_> = (0..10).map(|i| json!({"label": format!("B{i}"), "color": "green"})).collect();
        let p = write_json(dir.path(), "big.json", json!({ "buttons": buttons }));
        let err = read_template(&p, DeviceType::One1).unwrap_err();
        assert!(err.message.to_lowercase().contains("template"), "got {:?}", err);
    }

    #[test]
    fn import_rejects_encoder_on_non_std10() {
        let dir = tempfile::tempdir().unwrap();
        // Encoder is STD10-only; a one1 has no way to represent or remove it.
        let p = write_json(dir.path(), "enc.json", json!({
            "buttons": [{"label": "B0", "cc": 20, "color": "green"}],
            "encoder": {"enabled": true, "cc": 11, "label": "ENC", "min": 0, "max": 127, "initial": 64}
        }));
        assert!(read_template(&p, DeviceType::One1).is_err());
    }

    #[test]
    fn import_rejects_non_page_json() {
        let dir = tempfile::tempdir().unwrap();
        // A whole-config file (has "pages", no top-level "buttons") is not a Page.
        let p = write_json(dir.path(), "cfg.json", json!({ "device": "one1", "pages": [] }));
        assert!(read_template(&p, DeviceType::One1).is_err());
    }

    #[test]
    fn import_allows_out_of_range_jump_target() {
        let dir = tempfile::tempdir().unwrap();
        // A page_jump to page 9 is a VALUE problem, not a shape one: the page
        // imports fine and the button is flagged in-editor (P4b validation) /
        // blocked at save — NOT rejected at import.
        let p = write_json(dir.path(), "jump.json", json!({
            "buttons": [{"label": "GO", "type": "page_jump", "page": 9, "color": "green"}]
        }));
        assert!(read_template(&p, DeviceType::One1).is_ok());
    }

    #[test]
    fn list_templates_returns_sorted_json_stems() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join("Zebra.json"), "{}").unwrap();
        fs::write(dir.path().join("Alpha.json"), "{}").unwrap();
        fs::write(dir.path().join("notes.txt"), "ignore me").unwrap();
        let list = list_templates_in(dir.path()).unwrap();
        let names: Vec<_> = list.iter().map(|t| t.name.as_str()).collect();
        assert_eq!(names, ["Alpha", "Zebra"]);
    }

    #[test]
    fn list_templates_ignores_directories_named_like_templates() {
        let dir = tempfile::tempdir().unwrap();
        fs::create_dir(dir.path().join("Folder.json")).unwrap();
        fs::write(dir.path().join("Real.json"), "{}").unwrap();
        let names: Vec<_> = list_templates_in(dir.path()).unwrap()
            .into_iter().map(|t| t.name).collect();
        assert_eq!(names, ["Real"]);
    }

    #[test]
    fn list_templates_creates_missing_dir() {
        let dir = tempfile::tempdir().unwrap();
        let sub = dir.path().join("templates");
        assert!(list_templates_in(&sub).unwrap().is_empty());
        assert!(sub.is_dir());
    }
}
