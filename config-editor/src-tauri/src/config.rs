//! MIDI Captain configuration types and validation
//!
//! Matches the JSON schema used by the CircuitPython firmware.

use serde::{Deserialize, Serialize};

/// Valid button colors
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum ButtonColor {
    Red,
    Green,
    Blue,
    Yellow,
    Cyan,
    Magenta,
    Orange,
    Purple,
    White,
}

/// Button trigger mode
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "lowercase")]
pub enum ButtonMode {
    #[default]
    Toggle,
    Momentary,
}

/// LED behavior when button is off
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "lowercase")]
pub enum OffMode {
    #[default]
    Dim,
    Off,
}

/// Message type for a button
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "snake_case")]
pub enum MessageType {
    #[default]
    Cc,
    Note,
    Pc,
    PcInc,
    PcDec,
}

/// Per-state overrides for keytimes cycling
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StateOverride {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc_on: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc_off: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub velocity_on: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub velocity_off: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub program: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pc_step: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub color: Option<ButtonColor>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub label: Option<String>,
}

/// Button configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ButtonConfig {
    pub label: String,
    pub color: ButtonColor,
    #[serde(rename = "type", default, skip_serializing_if = "is_default_message_type")]
    pub message_type: MessageType,
    #[serde(default)]
    pub mode: ButtonMode,
    #[serde(default, skip_serializing_if = "is_default_off_mode")]
    pub off_mode: OffMode,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub channel: Option<u8>,
    // CC fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc_on: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc_off: Option<u8>,
    // Note fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub note: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub velocity_on: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub velocity_off: Option<u8>,
    // PC fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub program: Option<u8>,
    // PC inc/dec fields
    #[serde(skip_serializing_if = "Option::is_none")]
    pub pc_step: Option<u8>,
    // PC flash feedback (all PC types)
    #[serde(skip_serializing_if = "Option::is_none")]
    pub flash_ms: Option<u16>,
    // Keytimes cycling
    #[serde(skip_serializing_if = "Option::is_none")]
    pub keytimes: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub states: Option<Vec<StateOverride>>,
}

fn is_default_off_mode(mode: &OffMode) -> bool {
    *mode == OffMode::Dim
}

fn is_default_message_type(t: &MessageType) -> bool {
    *t == MessageType::Cc
}

/// Encoder push button configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncoderPush {
    pub enabled: bool,
    pub cc: u8,
    pub label: String,
    #[serde(default)]
    pub mode: ButtonMode,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub channel: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc_on: Option<u8>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub cc_off: Option<u8>,
}

/// Rotary encoder configuration (STD10 only)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncoderConfig {
    pub enabled: bool,
    pub cc: u8,
    pub label: String,
    #[serde(default)]
    pub min: u8,
    #[serde(default = "default_max")]
    pub max: u8,
    #[serde(default = "default_initial")]
    pub initial: u8,
    pub steps: Option<u8>,
    pub push: Option<EncoderPush>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub channel: Option<u8>,
}

fn default_max() -> u8 {
    127
}
fn default_initial() -> u8 {
    64
}

/// Expression pedal polarity
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "lowercase")]
pub enum Polarity {
    #[default]
    Normal,
    Inverted,
}

/// Expression pedal configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExpressionConfig {
    pub enabled: bool,
    pub cc: u8,
    pub label: String,
    #[serde(default)]
    pub min: u8,
    #[serde(default = "default_max")]
    pub max: u8,
    #[serde(default)]
    pub polarity: Polarity,
    #[serde(default = "default_threshold")]
    pub threshold: u8,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub channel: Option<u8>,
}

fn default_threshold() -> u8 {
    2
}

/// Expression pedals container
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExpressionPedals {
    pub exp1: ExpressionConfig,
    pub exp2: ExpressionConfig,
}

/// Device type
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Default)]
#[serde(rename_all = "lowercase")]
pub enum DeviceType {
    #[default]
    Std10,
    Mini6,
    Nano4,
    Duo2,
    One1,
}

/// Display text size settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DisplayConfig {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub button_text_size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub status_text_size: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expression_text_size: Option<String>,
}

/// Complete MIDI Captain configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MidiCaptainConfig {
    #[serde(default)]
    pub device: DeviceType,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub global_channel: Option<u8>,
    /// Custom USB volume label (max 11 chars, alphanumeric + underscore).
    /// Applied by boot.py via storage.remount() when the drive is enabled.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub usb_drive_name: Option<String>,
    /// Development mode: when true the USB drive always mounts on boot without
    /// needing to hold Switch 1.  Defaults to false (performance mode).
    #[serde(skip_serializing_if = "Option::is_none")]
    pub dev_mode: Option<bool>,
    pub buttons: Vec<ButtonConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub encoder: Option<EncoderConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expression: Option<ExpressionPedals>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub display: Option<DisplayConfig>,
}

impl MidiCaptainConfig {
    /// Validate the configuration
    pub fn validate(&self) -> Result<(), Vec<String>> {
        let mut errors = Vec::new();

        // Validate global channel (0-15 internally, display as 1-16)
        if let Some(ch) = self.global_channel {
            if ch > 15 {
                errors.push(format!("Global channel value {} is invalid (must be 1-16, stored as 0-15)", ch + 1));
            }
        }

        // Check button count matches device
        let expected_buttons = match self.device {
            DeviceType::Std10 => 10,
            DeviceType::Mini6 => 6,
            DeviceType::Nano4 => 4,
            DeviceType::Duo2 => 2,
            DeviceType::One1 => 1,
        };

        if self.buttons.len() != expected_buttons {
            errors.push(format!(
                "Expected {} buttons for {:?}, found {}",
                expected_buttons,
                self.device,
                self.buttons.len()
            ));
        }

        // Validate CC numbers (0-127) and button-specific fields
        for (i, button) in self.buttons.iter().enumerate() {
            if let Some(cc) = button.cc {
                if cc > 127 {
                    errors.push(format!("Button {} CC {} exceeds 127", i + 1, cc));
                }
            }
            if button.label.len() > 6 {
                errors.push(format!(
                    "Button {} label '{}' exceeds 6 chars",
                    i + 1,
                    button.label
                ));
            }
            if let Some(ch) = button.channel {
                if ch > 15 {
                    errors.push(format!("Button {} channel {} is invalid (must be 1-16)", i + 1, ch + 1));
                }
            }
            if let Some(val) = button.cc_on {
                if val > 127 {
                    errors.push(format!("Button {} cc_on {} exceeds 127", i + 1, val));
                }
            }
            if let Some(val) = button.cc_off {
                if val > 127 {
                    errors.push(format!("Button {} cc_off {} exceeds 127", i + 1, val));
                }
            }
            if let Some(ms) = button.flash_ms {
                if ms < 50 || ms > 5000 {
                    errors.push(format!("Button {} flash_ms {} out of range (50-5000)", i + 1, ms));
                }
            }
        }

        // Validate encoder if present
        if let Some(ref enc) = self.encoder {
            // Only STD10 supports encoder
            if self.device != DeviceType::Std10 {
                errors.push(format!("{:?} does not support encoder", self.device));
            }
            if enc.cc > 127 {
                errors.push(format!("Encoder CC {} exceeds 127", enc.cc));
            }
            if enc.label.len() > 8 {
                errors.push(format!("Encoder label '{}' exceeds 8 chars", enc.label));
            }
            if enc.max < enc.min {
                errors.push(format!("Encoder max ({}) must be >= min ({})", enc.max, enc.min));
            }
            if enc.initial < enc.min || enc.initial > enc.max {
                errors.push(format!("Encoder initial ({}) must be between min ({}) and max ({})", enc.initial, enc.min, enc.max));
            }
            if let Some(ch) = enc.channel {
                if ch > 15 {
                    errors.push(format!("Encoder channel {} is invalid (must be 1-16)", ch + 1));
                }
            }
            if let Some(ref push) = enc.push {
                if push.cc > 127 {
                    errors.push(format!("Encoder push CC {} exceeds 127", push.cc));
                }
                if push.label.len() > 8 {
                    errors.push(format!("Encoder push label '{}' exceeds 8 chars", push.label));
                }
                if let Some(ch) = push.channel {
                    if ch > 15 {
                        errors.push(format!("Encoder push channel {} is invalid (must be 1-16)", ch + 1));
                    }
                }
                if let Some(val) = push.cc_on {
                    if val > 127 {
                        errors.push(format!("Encoder push cc_on {} exceeds 127", val));
                    }
                }
                if let Some(val) = push.cc_off {
                    if val > 127 {
                        errors.push(format!("Encoder push cc_off {} exceeds 127", val));
                    }
                }
            }
        }

        // Validate expression pedals if present
        if let Some(ref exp) = self.expression {
            // Only STD10 supports expression pedals
            if self.device != DeviceType::Std10 {
                errors.push(format!("{:?} does not support expression pedals", self.device));
            }
            if exp.exp1.cc > 127 {
                errors.push(format!("EXP1 CC {} exceeds 127", exp.exp1.cc));
            }
            if exp.exp1.label.len() > 8 {
                errors.push(format!("EXP1 label '{}' exceeds 8 chars", exp.exp1.label));
            }
            if exp.exp1.max < exp.exp1.min {
                errors.push(format!("EXP1 max ({}) must be >= min ({})", exp.exp1.max, exp.exp1.min));
            }
            if let Some(ch) = exp.exp1.channel {
                if ch > 15 {
                    errors.push(format!("EXP1 channel {} is invalid (must be 1-16)", ch + 1));
                }
            }
            if exp.exp2.cc > 127 {
                errors.push(format!("EXP2 CC {} exceeds 127", exp.exp2.cc));
            }
            if exp.exp2.label.len() > 8 {
                errors.push(format!("EXP2 label '{}' exceeds 8 chars", exp.exp2.label));
            }
            if exp.exp2.max < exp.exp2.min {
                errors.push(format!("EXP2 max ({}) must be >= min ({})", exp.exp2.max, exp.exp2.min));
            }
            if let Some(ch) = exp.exp2.channel {
                if ch > 15 {
                    errors.push(format!("EXP2 channel {} is invalid (must be 1-16)", ch + 1));
                }
            }
        }

        if errors.is_empty() {
            Ok(())
        } else {
            Err(errors)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_deserialize_std10_config() {
        let json = r#"{
            "buttons": [
                {"label": "TSC", "cc": 20, "color": "green"}
            ],
            "encoder": {
                "enabled": true,
                "cc": 11,
                "label": "ENC",
                "min": 0,
                "max": 127,
                "initial": 64,
                "steps": null,
                "push": {
                    "enabled": true,
                    "cc": 14,
                    "label": "PUSH",
                    "mode": "momentary"
                }
            }
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.buttons.len(), 1);
        assert!(config.encoder.is_some());
    }

    #[test]
    fn test_deserialize_mini6_config() {
        let json = r#"{
            "device": "mini6",
            "buttons": [
                {"label": "BOOM", "cc": 20, "color": "green"}
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.device, DeviceType::Mini6);
        assert!(config.encoder.is_none());
    }

    #[test]
    fn test_deserialize_duo2_config() {
        let json = r#"{
            "device": "duo2",
            "buttons": [
                {"label": "BTN1", "cc": 20, "color": "green"},
                {"label": "BTN2", "cc": 21, "color": "blue"}
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.device, DeviceType::Duo2);
        assert_eq!(config.buttons.len(), 2);
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_deserialize_one1_config() {
        let json = r#"{
            "device": "one1",
            "buttons": [
                {"label": "BTN1", "cc": 20, "color": "green"}
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.device, DeviceType::One1);
        assert_eq!(config.buttons.len(), 1);
        assert!(config.validate().is_ok());
    }

    /// Round-trip: fields present in input JSON must survive serialize → deserialize.
    /// This class of test would have caught the missing-field bug (serde silently drops
    /// unknown fields during deserialization, so re-serializing strips them).
    #[test]
    fn test_roundtrip_note_button() {
        let json = r#"{
            "buttons": [
                {"label": "NOTE", "type": "note", "note": 60, "velocity_on": 100, "velocity_off": 0, "color": "blue", "mode": "momentary"}
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        let btn = &config.buttons[0];
        assert_eq!(btn.message_type, MessageType::Note);
        assert_eq!(btn.note, Some(60));
        assert_eq!(btn.velocity_on, Some(100));
        assert_eq!(btn.velocity_off, Some(0));

        // Re-serialize and re-parse to confirm round-trip
        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        let btn2 = &config2.buttons[0];
        assert_eq!(btn2.message_type, MessageType::Note);
        assert_eq!(btn2.note, Some(60));
        assert_eq!(btn2.velocity_on, Some(100));
    }

    #[test]
    fn test_roundtrip_pc_button() {
        let json = r#"{
            "buttons": [
                {"label": "PC", "type": "pc", "program": 42, "color": "red"}
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        let btn = &config.buttons[0];
        assert_eq!(btn.message_type, MessageType::Pc);
        assert_eq!(btn.program, Some(42));

        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        assert_eq!(config2.buttons[0].program, Some(42));
    }

    #[test]
    fn test_roundtrip_pc_inc_dec_buttons() {
        let json = r#"{
            "buttons": [
                {"label": "UP", "type": "pc_inc", "pc_step": 5, "color": "green"},
                {"label": "DN", "type": "pc_dec", "pc_step": 2, "color": "red"}
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.buttons[0].message_type, MessageType::PcInc);
        assert_eq!(config.buttons[0].pc_step, Some(5));
        assert_eq!(config.buttons[1].message_type, MessageType::PcDec);
        assert_eq!(config.buttons[1].pc_step, Some(2));

        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        assert_eq!(config2.buttons[0].pc_step, Some(5));
        assert_eq!(config2.buttons[1].pc_step, Some(2));
    }

    #[test]
    fn test_roundtrip_keytimes_and_states() {
        let json = r#"{
            "buttons": [
                {
                    "label": "CYCLE",
                    "type": "cc",
                    "cc": 20,
                    "color": "white",
                    "keytimes": 3,
                    "states": [
                        {"cc": 1, "cc_on": 127, "label": "ONE"},
                        {"cc": 2, "color": "red"},
                        {"cc": 3, "cc_off": 64}
                    ]
                }
            ]
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        let btn = &config.buttons[0];
        assert_eq!(btn.keytimes, Some(3));
        let states = btn.states.as_ref().unwrap();
        assert_eq!(states.len(), 3);
        assert_eq!(states[0].cc, Some(1));
        assert_eq!(states[0].label.as_deref(), Some("ONE"));
        assert_eq!(states[1].color, Some(ButtonColor::Red));
        assert_eq!(states[2].cc_off, Some(64));

        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        let states2 = config2.buttons[0].states.as_ref().unwrap();
        assert_eq!(states2[0].cc, Some(1));
        assert_eq!(states2[1].color, Some(ButtonColor::Red));
    }

    #[test]
    fn test_roundtrip_display_config() {
        let json = r#"{
            "buttons": [],
            "display": {
                "button_text_size": "large",
                "status_text_size": "small"
            }
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        let display = config.display.as_ref().unwrap();
        assert_eq!(display.button_text_size.as_deref(), Some("large"));

        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        assert_eq!(
            config2.display.as_ref().unwrap().button_text_size.as_deref(),
            Some("large")
        );
    }

    #[test]
    fn test_roundtrip_usb_drive_name() {
        let json = r#"{
            "buttons": [],
            "usb_drive_name": "MYCAPTAIN"
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.usb_drive_name.as_deref(), Some("MYCAPTAIN"));

        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        assert_eq!(config2.usb_drive_name.as_deref(), Some("MYCAPTAIN"));
    }

    #[test]
    fn test_roundtrip_dev_mode() {
        let json = r#"{
            "buttons": [],
            "dev_mode": true
        }"#;

        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.dev_mode, Some(true));

        let reserialized = serde_json::to_string(&config).unwrap();
        let config2: MidiCaptainConfig = serde_json::from_str(&reserialized).unwrap();
        assert_eq!(config2.dev_mode, Some(true));
    }

    /// Round-trip every shipped firmware config file: parse → serialize → parse,
    /// asserting that no fields present in the original JSON are dropped during
    /// the trip through MidiCaptainConfig. This catches the "Rust struct missing
    /// a field" bug for every config file at once, instead of needing a new
    /// per-feature test for each addition.
    #[test]
    fn test_roundtrip_all_shipped_configs() {
        use std::fs;
        use std::path::PathBuf;

        let manifest_dir = env!("CARGO_MANIFEST_DIR");
        let firmware_dev = PathBuf::from(manifest_dir)
            .join("..")
            .join("..")
            .join("firmware")
            .join("dev");

        let entries = fs::read_dir(&firmware_dev)
            .expect("firmware/dev not found");

        let mut checked = 0;
        for entry in entries {
            let path = entry.unwrap().path();
            let name = path.file_name().unwrap().to_string_lossy().to_string();
            if !name.starts_with("config") || !name.ends_with(".json") {
                continue;
            }

            let source = fs::read_to_string(&path)
                .unwrap_or_else(|e| panic!("read {}: {}", name, e));

            let original: serde_json::Value = serde_json::from_str(&source)
                .unwrap_or_else(|e| panic!("parse {} as Value: {}", name, e));

            let typed: MidiCaptainConfig = serde_json::from_str(&source)
                .unwrap_or_else(|e| panic!("parse {} as MidiCaptainConfig: {}", name, e));

            let reserialized = serde_json::to_value(&typed)
                .unwrap_or_else(|e| panic!("serialize {}: {}", name, e));

            assert_no_keys_dropped(&original, &reserialized, &name, "");
            checked += 1;
        }
        assert!(checked > 0, "expected to check at least one config file");
    }

    /// Fields that are intentionally stripped on serialize when they match
    /// their default value. (key_name, default_value_when_dropped)
    const ALLOWED_DEFAULT_DROPS: &[(&str, &str)] = &[
        ("type", "cc"),
        ("off_mode", "dim"),
    ];

    fn is_allowed_default_drop(key: &str, value: &serde_json::Value) -> bool {
        ALLOWED_DEFAULT_DROPS
            .iter()
            .any(|(k, v)| *k == key && value.as_str() == Some(*v))
    }

    /// Recursively assert every key in `original` exists in `reserialized` with
    /// an equal value. Extra keys in `reserialized` are tolerated (Rust may emit
    /// fields the JSON didn't have, e.g., from defaults). Known default-value
    /// drops (see ALLOWED_DEFAULT_DROPS) are also tolerated.
    fn assert_no_keys_dropped(
        original: &serde_json::Value,
        reserialized: &serde_json::Value,
        file: &str,
        path: &str,
    ) {
        match original {
            serde_json::Value::Object(orig_map) => {
                let reser_map = reserialized.as_object().unwrap_or_else(|| {
                    panic!("{}{}: expected object, got {:?}", file, path, reserialized)
                });
                for (k, v) in orig_map {
                    let child_path = format!("{}.{}", path, k);
                    let reser_v = match reser_map.get(k) {
                        Some(v) => v,
                        None => {
                            if is_allowed_default_drop(k, v) {
                                continue;
                            }
                            panic!(
                                "{}{}: field '{}' (value: {}) was silently dropped during round-trip — Rust struct likely missing this field",
                                file, path, k, v
                            );
                        }
                    };
                    assert_no_keys_dropped(v, reser_v, file, &child_path);
                }
            }
            serde_json::Value::Array(orig_arr) => {
                let reser_arr = reserialized.as_array().unwrap_or_else(|| {
                    panic!("{}{}: expected array, got {:?}", file, path, reserialized)
                });
                assert_eq!(
                    orig_arr.len(),
                    reser_arr.len(),
                    "{}{}: array length changed",
                    file, path
                );
                for (i, (a, b)) in orig_arr.iter().zip(reser_arr.iter()).enumerate() {
                    let child_path = format!("{}[{}]", path, i);
                    assert_no_keys_dropped(a, b, file, &child_path);
                }
            }
            _ => {
                assert_eq!(
                    original, reserialized,
                    "{}{}: value changed during round-trip",
                    file, path
                );
            }
        }
    }

    #[test]
    fn test_dev_mode_defaults_absent_when_false() {
        // When dev_mode is false (or absent), it should not appear in serialised output
        // (skip_serializing_if = "Option::is_none" only omits None, so explicit false
        // WILL be serialised; this test documents that behaviour so we notice if it
        // changes unintentionally).
        let json = r#"{ "buttons": [] }"#;
        let config: MidiCaptainConfig = serde_json::from_str(json).unwrap();
        assert_eq!(config.dev_mode, None);

        let reserialized = serde_json::to_string(&config).unwrap();
        assert!(!reserialized.contains("dev_mode"));
    }
}
