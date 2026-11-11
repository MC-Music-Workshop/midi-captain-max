//! Tools the MCM agent uses to configure a pedal from plain language (#230).
//!
//! One implementation, two front ends: the `mcm-mcp` stdio server (`mcp.rs`)
//! and the Config Editor's chat panel. Tool names, descriptions and input
//! schemas live in `config-editor/agent/tools.json` and the instructions in
//! `agent/prompt.md`, so both front ends hand the model the same thing.

use crate::commands::{validate_config_json, validate_device_path, write_config_raw, ConfigError};
use crate::config::{migrate_to_pages, DeviceType};
use crate::config_files::{read_config_file, write_config_file};
use crate::device::{is_midi_captain_config, scan_devices};
use crate::installer::detect_device_type;
use serde_json::{json, Map, Value};
use std::fs;
use std::path::{Path, PathBuf};
use std::time::{SystemTime, UNIX_EPOCH};

pub const TOOLS_JSON: &str = include_str!("../../agent/tools.json");
pub const PROMPT: &str = include_str!("../../agent/prompt.md");
const SCHEMA_JSON: &str = include_str!("../../../config.schema.json");

/// Same cap as the editor's `PAGE_CAP` and `MidiCaptainConfig::validate`.
const PAGE_CAP: usize = 20;

fn schema() -> Value {
    serde_json::from_str(SCHEMA_JSON).expect("config.schema.json is valid JSON")
}

/// The whole config schema, or one of its `definitions`.
pub fn get_schema(definition: Option<&str>) -> Result<Value, ConfigError> {
    let mut schema = schema();
    let Some(name) = definition else { return Ok(schema) };
    let definitions = schema["definitions"].as_object_mut().expect("schema has definitions");
    definitions.remove(name).ok_or_else(|| {
        let names: Vec<&str> = definitions.keys().map(String::as_str).collect();
        ConfigError::msg(format!("No schema definition named '{name}'. Valid names: {}", names.join(", ")))
    })
}

/// `{"ok": true}`, or `{"ok": false, "errors": [...]}`.
pub fn validate(config: &Value) -> Value {
    match validate_config_json(&config.to_string()) {
        Ok(()) => json!({ "ok": true }),
        Err(e) => json!({ "ok": false, "errors": e.details.unwrap_or_else(|| vec![e.message]) }),
    }
}

/// Apply `apply_changes` arguments to a config in memory: `globals` sets (or,
/// with null, removes) top-level fields, each `pages` item replaces the page at
/// `index` or appends when `index` is the page count. Works on the raw JSON so
/// fields the Rust structs don't model survive (#215). Does not validate.
pub fn merge_changes(mut config: Value, pages: &[Value], globals: Option<&Map<String, Value>>) -> Result<Value, ConfigError> {
    let obj = config.as_object_mut().ok_or_else(|| ConfigError::msg("Config is not a JSON object"))?;

    if let Some(globals) = globals {
        let schema = schema();
        let known = schema["properties"].as_object().expect("schema has properties");
        for (key, value) in globals {
            if key == "pages" {
                return Err(ConfigError::msg("Change pages with `pages`, not `globals`"));
            }
            // An unknown top-level key would be written and silently ignored by the pedal.
            if !known.contains_key(key) {
                return Err(ConfigError::msg(format!("Unknown top-level field '{key}'")));
            }
            if value.is_null() {
                obj.remove(key);
            } else {
                obj.insert(key.clone(), value.clone());
            }
        }
    }

    let list = obj
        .get_mut("pages")
        .and_then(Value::as_array_mut)
        .ok_or_else(|| ConfigError::msg("Config has no `pages` array"))?;
    for change in pages {
        let index = change
            .get("index")
            .and_then(Value::as_u64)
            .ok_or_else(|| ConfigError::msg("Each `pages` item needs an integer `index`"))? as usize;
        let page = change
            .get("page")
            .filter(|p| p.is_object())
            .ok_or_else(|| ConfigError::msg("Each `pages` item needs a `page` object"))?
            .clone();
        if index < list.len() {
            list[index] = page;
        } else if index > list.len() {
            return Err(ConfigError::msg(format!(
                "Page index {index} is out of range: the config has {} pages (use index {} to append)",
                list.len(),
                list.len()
            )));
        } else if list.len() >= PAGE_CAP {
            return Err(ConfigError::msg(format!("A config holds at most {PAGE_CAP} pages")));
        } else {
            list.push(page);
        }
    }

    Ok(config)
}

/// Connected pedals with a mounted drive.
pub fn list_devices() -> Value {
    let devices: Vec<Value> = scan_devices()
        .into_iter()
        .map(|d| {
            json!({
                "name": d.name,
                "path": d.path,
                "has_config": d.has_config,
                "model": detect_device_type(&d.path),
            })
        })
        .collect();
    json!({ "devices": devices })
}

struct Target {
    /// The config JSON file itself.
    path: PathBuf,
    /// On a pedal's drive (device-scoped write: mount check + fsync) rather than a host file.
    on_device: bool,
}

fn resolve_target(target: Option<&str>) -> Result<Target, ConfigError> {
    let path = match target {
        Some(t) => {
            let p = PathBuf::from(t);
            if p.is_dir() { p.join("config.json") } else { p }
        }
        None => {
            let mut devices = scan_devices();
            match devices.len() {
                1 => devices.remove(0).config_path,
                0 => return Err(ConfigError::msg("No pedal is connected. Pass `target`: a pedal drive path or a saved config file.")),
                _ => return Err(ConfigError::msg("More than one pedal is connected. Pass `target`: a path from list_devices.")),
            }
        }
    };
    let on_device = validate_device_path(&path.to_string_lossy()).is_ok();
    Ok(Target { path, on_device })
}

fn describe(target: &Target, config: &Value) -> Value {
    let device: DeviceType = serde_json::from_value(config["device"].clone()).unwrap_or_default();
    json!({
        "target": target.path,
        "on_device": target.on_device,
        "model": device,
        "buttons_per_page": device.button_count(),
        "page_count": config["pages"].as_array().map_or(0, Vec::len),
    })
}

/// Read a config (legacy flat configs come back in the pages shape).
pub fn get_config(target: Option<&str>) -> Result<Value, ConfigError> {
    let target = resolve_target(target)?;
    let config: Value = serde_json::from_str(&read_config_file(&target.path)?)?;
    let mut result = describe(&target, &config);
    result["config"] = config;
    Ok(result)
}

fn backups_dir() -> Result<PathBuf, ConfigError> {
    Ok(dirs::document_dir()
        .ok_or_else(|| ConfigError::msg("Could not resolve Documents dir"))?
        .join("MIDICaptainMAX")
        .join("backups"))
}

/// Copy the config about to be replaced into `dir`; returns the copy's path.
fn write_backup(dir: &Path, config_path: &Path, contents: &str) -> Result<PathBuf, ConfigError> {
    // A pedal's file is always `config.json`, so name its backup after the drive.
    let stem = config_path.file_stem().and_then(|s| s.to_str()).unwrap_or("config");
    let label = if stem == "config" {
        config_path.parent().and_then(Path::file_name).and_then(|s| s.to_str()).unwrap_or(stem)
    } else {
        stem
    };
    let millis = SystemTime::now().duration_since(UNIX_EPOCH).map_or(0, |d| d.as_millis());
    fs::create_dir_all(dir)?;
    let backup = dir.join(format!("{label}-{millis}.json"));
    fs::write(&backup, contents)?;
    Ok(backup)
}

/// Merge → validate → back up the previous config → write. Nothing is written
/// when the merged config is invalid; the errors come back as `ok: false`.
pub fn apply_changes(target: Option<&str>, pages: &[Value], globals: Option<&Map<String, Value>>) -> Result<Value, ConfigError> {
    apply_changes_with_backups(target, pages, globals, &backups_dir()?)
}

fn apply_changes_with_backups(
    target: Option<&str>,
    pages: &[Value],
    globals: Option<&Map<String, Value>>,
    backups: &Path,
) -> Result<Value, ConfigError> {
    let target = resolve_target(target)?;
    // A host file must already be a pedal config, so this can't overwrite an unrelated file.
    if !target.on_device && !is_midi_captain_config(&target.path) {
        return Err(ConfigError::msg(format!("{} is not a MIDI Captain config", target.path.display())));
    }

    let previous = fs::read_to_string(&target.path)?;
    let current = migrate_to_pages(serde_json::from_str(&previous)?);
    let merged = merge_changes(current, pages, globals)?;

    let checked = validate(&merged);
    if checked["ok"] != true {
        return Ok(checked);
    }

    let json = serde_json::to_string_pretty(&merged)?;
    let backup = write_backup(backups, &target.path, &previous)?;
    if target.on_device {
        write_config_raw(target.path.to_string_lossy().to_string(), json)?;
    } else {
        write_config_file(&target.path, &json)?;
    }

    let mut result = describe(&target, &merged);
    result["ok"] = json!(true);
    result["backup"] = json!(backup);
    if target.on_device {
        result["note"] = json!("Saved to the pedal. It loads the new config after a restart (power-cycle, or Restart Device in the Config Editor).");
    }
    Ok(result)
}

/// Run the tool `name` with JSON `args` (the shapes in `agent/tools.json`).
pub fn call_tool(name: &str, args: &Map<String, Value>) -> Result<Value, ConfigError> {
    let target = args.get("target").and_then(Value::as_str);
    match name {
        "list_devices" => Ok(list_devices()),
        "get_schema" => get_schema(args.get("definition").and_then(Value::as_str)),
        "get_config" => get_config(target),
        "validate" => Ok(validate(args.get("config").ok_or_else(|| ConfigError::msg("`config` is required"))?)),
        "apply_changes" => apply_changes(
            target,
            args.get("pages").and_then(Value::as_array).map_or(&[], Vec::as_slice),
            args.get("globals").and_then(Value::as_object),
        ),
        _ => Err(ConfigError::msg(format!("Unknown tool '{name}'"))),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn nano4() -> Value {
        serde_json::from_str(include_str!("../../../firmware/dev/config-nano4.json")).unwrap()
    }

    fn page(label: &str) -> Value {
        let mut page = nano4()["pages"][0].clone();
        page["buttons"][0]["label"] = json!(label);
        page
    }

    #[test]
    fn tool_definitions_match_the_dispatcher() {
        let tools: Vec<Value> = serde_json::from_str(TOOLS_JSON).unwrap();
        let names: Vec<&str> = tools.iter().map(|t| t["name"].as_str().unwrap()).collect();
        assert_eq!(names, ["list_devices", "get_schema", "get_config", "validate", "apply_changes"]);
        for tool in &tools {
            assert!(tool["description"].is_string() && tool["input_schema"]["type"] == "object", "{tool}");
        }
        let err = call_tool("nope", &Map::new()).unwrap_err();
        assert!(err.message.contains("Unknown tool"));
    }

    #[test]
    fn get_schema_returns_whole_schema_or_one_definition() {
        assert!(get_schema(None).unwrap()["definitions"]["ButtonConfig"].is_object());
        assert!(get_schema(Some("ButtonConfig")).unwrap()["properties"]["label"].is_object());
        let err = get_schema(Some("Nope")).unwrap_err();
        assert!(err.message.contains("KeytimesMessage"), "{}", err.message);
    }

    #[test]
    fn validate_reports_errors() {
        assert_eq!(validate(&nano4()), json!({ "ok": true }));
        let mut bad = nano4();
        bad["pages"][0]["buttons"].as_array_mut().unwrap().pop();
        let result = validate(&bad);
        assert_eq!(result["ok"], false);
        assert!(result["errors"][0].as_str().unwrap().contains("Page 1"), "{result}");
    }

    #[test]
    fn merge_replaces_and_appends_pages_and_sets_globals() {
        let globals = json!({ "global_channel": 3, "usb_drive_name": null });
        let merged = merge_changes(
            nano4(),
            &[json!({ "index": 0, "page": page("ONE") }), json!({ "index": 1, "page": page("TWO") })],
            globals.as_object(),
        )
        .unwrap();
        assert_eq!(merged["pages"][0]["buttons"][0]["label"], "ONE");
        assert_eq!(merged["pages"][1]["buttons"][0]["label"], "TWO");
        assert_eq!(merged["global_channel"], 3);
        assert!(merged.get("usb_drive_name").is_none());
        assert_eq!(validate(&merged), json!({ "ok": true }));
    }

    #[test]
    fn merge_rejects_bad_indexes_page_cap_and_unknown_globals() {
        let err = merge_changes(nano4(), &[json!({ "index": 2, "page": page("X") })], None).unwrap_err();
        assert!(err.message.contains("out of range"));

        let mut full = nano4();
        full["pages"] = Value::Array(vec![page("P"); PAGE_CAP]);
        let err = merge_changes(full, &[json!({ "index": PAGE_CAP, "page": page("X") })], None).unwrap_err();
        assert!(err.message.contains("at most 20"));

        for globals in [json!({ "pages": [] }), json!({ "global_chanel": 1 })] {
            assert!(merge_changes(nano4(), &[], globals.as_object()).is_err(), "{globals}");
        }
    }

    #[test]
    fn apply_changes_writes_a_valid_change_and_backs_up_the_previous_file() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("mine.json");
        let original = serde_json::to_string_pretty(&nano4()).unwrap();
        fs::write(&path, &original).unwrap();
        let backups = dir.path().join("backups");

        let mut changed = page("FS4");
        changed["buttons"][0]["not_in_rust_structs"] = json!(true);
        let result = apply_changes_with_backups(
            path.to_str(),
            &[json!({ "index": 0, "page": changed })],
            None,
            &backups,
        )
        .unwrap();

        assert_eq!(result["ok"], true, "{result}");
        assert_eq!(result["model"], "nano4");
        assert_eq!(result["buttons_per_page"], 4);
        let written: Value = serde_json::from_str(&fs::read_to_string(&path).unwrap()).unwrap();
        assert_eq!(written["pages"][0]["buttons"][0]["label"], "FS4");
        assert_eq!(written["pages"][0]["buttons"][0]["not_in_rust_structs"], true);
        assert_eq!(fs::read_to_string(result["backup"].as_str().unwrap()).unwrap(), original);

        let read = get_config(path.to_str()).unwrap();
        assert_eq!(read["config"], written);
        assert_eq!(read["page_count"], 1);
    }

    #[test]
    fn apply_changes_leaves_the_file_alone_when_the_result_is_invalid() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("mine.json");
        let original = serde_json::to_string_pretty(&nano4()).unwrap();
        fs::write(&path, &original).unwrap();
        let backups = dir.path().join("backups");

        let mut short = page("X");
        short["buttons"].as_array_mut().unwrap().pop();
        let result =
            apply_changes_with_backups(path.to_str(), &[json!({ "index": 0, "page": short })], None, &backups).unwrap();

        assert_eq!(result["ok"], false);
        assert!(!result["errors"].as_array().unwrap().is_empty());
        assert_eq!(fs::read_to_string(&path).unwrap(), original);
        assert!(!backups.exists());
    }

    #[test]
    fn apply_changes_refuses_a_file_that_is_not_a_pedal_config() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("package.json");
        fs::write(&path, r#"{"name": "something-else", "pages": [{"buttons": []}]}"#).unwrap();
        let err = apply_changes_with_backups(path.to_str(), &[], None, &dir.path().join("backups")).unwrap_err();
        assert!(err.message.contains("not a MIDI Captain config"));
    }
}
