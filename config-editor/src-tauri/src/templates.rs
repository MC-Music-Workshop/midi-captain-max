//! Page template import/export (#15 P4d). Templates are host-side JSON files,
//! one `Page` object per file. Import validates the page against the *current*
//! device via `MidiCaptainConfig::validate()` — no silent reshaping (D9).

use crate::commands::{write_sync, ConfigError};
use crate::config::Page; // DeviceType added in Task 6, where it's first used.
use std::fs;
use std::path::Path;

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
}
