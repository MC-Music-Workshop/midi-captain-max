# MIDI Captain MAX Config Editor Implementation Plan

**Status:** Shipped — became the current Config Editor app.
> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

---

## Current Status (2026-02-05)

| Phase | Status |
|-------|--------|
| Phase 1-5 | ✅ Complete |
| Code review fixes | ✅ Complete (6 issues fixed) |
| macOS architecture review | ✅ Complete (8 issues identified) |
| **Next up** | **Phase 8: Tasks 8.1-8.3 (critical macOS fixes)** |

**Recommendation:** Do Phase 8 critical tasks (8.1-8.3) before Phases 6-7 to fix foundation issues first.

---

**Goal:** Build a cross-platform desktop app (Tauri + Svelte) that edits MIDI Captain config files, replaces the current AppleScript installer, and supports future expansion to Windows and mobile.

**Architecture:** Rust backend handles filesystem operations (device detection, config read/write, profile storage). Svelte frontend provides the UI with JSON text editor, validation, and device-specific field handling. The app combines firmware installation and config editing into a unified experience.

**Tech Stack:** Tauri v2, Svelte 5, TypeScript, Rust, CodeMirror 6 (JSON editor)

**GitHub Issue:** [#5 - create a config editor app](https://github.com/MC-Music-Workshop/midi-captain-max/issues/5)

---

## Table of Contents

1. [Phase 1: Project Scaffolding](#phase-1-project-scaffolding)
2. [Phase 2: Rust Backend Core](#phase-2-rust-backend-core)
3. [Phase 3: Device Detection](#phase-3-device-detection)
4. [Phase 4: Svelte Frontend MVP](#phase-4-svelte-frontend-mvp)
5. [Phase 5: JSON Editor Integration](#phase-5-json-editor-integration)
6. [Phase 6: Profile Management](#phase-6-profile-management)
7. [Phase 7: Firmware Installation](#phase-7-firmware-installation)
8. [Phase 8: macOS Architecture Hardening](#phase-8-macos-architecture-hardening) ← NEW
9. [Phase 9: Validation & Device-Specific UI](#phase-9-validation--device-specific-ui)
10. [Phase 10: Packaging & Distribution](#phase-10-packaging--distribution)
11. [Future Phases](#future-phases)

---

## Phase 1: Project Scaffolding

### Task 1.1: Install Prerequisites

**Step 1: Verify/install Rust**

Run:
```bash
rustc --version
```

If not installed:
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source ~/.cargo/env
```

Expected: Rust 1.75+ installed

**Step 2: Install Tauri CLI**

Run:
```bash
cargo install create-tauri-app --locked
cargo install tauri-cli --locked
```

Expected: `cargo tauri --version` shows 2.x

**Step 3: Verify Node.js**

Run:
```bash
node --version && npm --version
```

Expected: Node 18+ and npm 9+

---

### Task 1.2: Create Tauri + Svelte Project

**Files:**
- Create: `config-editor/` (new directory in repo root)

**Step 1: Scaffold the project**

Run:
```bash
cd /Users/maximiliancascone/github/midi-captain-max
npm create tauri-app@latest config-editor -- --template svelte-ts
```

Select options:
- Package manager: `npm`
- UI template: `svelte-ts`

**Step 2: Verify project structure**

```
config-editor/
├── src/                    # Svelte frontend
│   ├── App.svelte
│   ├── main.ts
│   └── lib/
├── src-tauri/              # Rust backend
│   ├── src/
│   │   └── main.rs
│   ├── Cargo.toml
│   └── tauri.conf.json
├── package.json
├── svelte.config.js
├── tsconfig.json
└── vite.config.ts
```

**Step 3: Install dependencies and test**

Run:
```bash
cd config-editor
npm install

# Install all project dependencies upfront
# CodeMirror for JSON editor with syntax highlighting
npm install @codemirror/state @codemirror/view @codemirror/lang-json @codemirror/theme-one-dark @codemirror/commands

# Test the scaffold
npm run tauri dev
```

Expected: Empty Tauri window opens. `package.json` now includes CodeMirror dependencies.

**Step 4: Commit**

```bash
git add config-editor/
git commit -m "feat: scaffold Tauri + Svelte config editor project"
```

---

### Task 1.3: Configure Tauri for macOS

**Files:**
- Modify: `config-editor/src-tauri/tauri.conf.json`

**Step 1: Update app metadata**

Edit `tauri.conf.json`:
```json
{
  "$schema": "https://schema.tauri.app/config/2",
  "productName": "MIDI Captain MAX Config Editor",
  "version": "0.1.0",
  "identifier": "com.mcmusicworkshop.midicaptain.configeditor",
  "build": {
    "frontendDist": "../dist"
  },
  "app": {
    "windows": [
      {
        "title": "MIDI Captain MAX Config Editor",
        "width": 1000,
        "height": 700,
        "resizable": true,
        "minWidth": 800,
        "minHeight": 600
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": ["app", "dmg"],
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "macOS": {
      "minimumSystemVersion": "10.15"
    }
  }
}
```

**Step 2: Commit**

```bash
git add config-editor/src-tauri/tauri.conf.json
git commit -m "chore: configure Tauri app metadata for macOS"
```

---

## Phase 2: Rust Backend Core

### Task 2.1: Add Rust Dependencies

**Files:**
- Modify: `config-editor/src-tauri/Cargo.toml`

**Step 1: Add dependencies**

```toml
[dependencies]
tauri = { version = "2", features = ["macos-private-api"] }
tauri-plugin-shell = "2"
tauri-plugin-dialog = "2"
tauri-plugin-fs = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
notify = "6"
dirs = "5"
```

**Step 2: Run cargo check**

```bash
cd config-editor/src-tauri
cargo check
```

Expected: Compiles without errors

**Step 3: Commit**

```bash
git add config-editor/src-tauri/Cargo.toml
git commit -m "chore: add Rust dependencies for config editor"
```

---

### Task 2.2: Define Config Types

**Files:**
- Create: `config-editor/src-tauri/src/config.rs`

**Step 1: Create config module**

```rust
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

/// Button configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ButtonConfig {
    pub label: String,
    pub cc: u8,
    pub color: ButtonColor,
    #[serde(default)]
    pub mode: ButtonMode,
    #[serde(default, skip_serializing_if = "is_default_off_mode")]
    pub off_mode: OffMode,
}

fn is_default_off_mode(mode: &OffMode) -> bool {
    *mode == OffMode::Dim
}

/// Encoder push button configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EncoderPush {
    pub enabled: bool,
    pub cc: u8,
    pub label: String,
    #[serde(default)]
    pub mode: ButtonMode,
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
}

fn default_max() -> u8 { 127 }
fn default_initial() -> u8 { 64 }

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
}

fn default_threshold() -> u8 { 2 }

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
}

/// Complete MIDI Captain configuration
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MidiCaptainConfig {
    #[serde(default)]
    pub device: DeviceType,
    pub buttons: Vec<ButtonConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub encoder: Option<EncoderConfig>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub expression: Option<ExpressionPedals>,
}

impl MidiCaptainConfig {
    /// Validate the configuration
    pub fn validate(&self) -> Result<(), Vec<String>> {
        let mut errors = Vec::new();

        // Check button count matches device
        let expected_buttons = match self.device {
            DeviceType::Std10 => 10,
            DeviceType::Mini6 => 6,
        };
        
        if self.buttons.len() != expected_buttons {
            errors.push(format!(
                "Expected {} buttons for {:?}, found {}",
                expected_buttons, self.device, self.buttons.len()
            ));
        }

        // Validate CC numbers (0-127)
        for (i, button) in self.buttons.iter().enumerate() {
            if button.cc > 127 {
                errors.push(format!("Button {} CC {} exceeds 127", i + 1, button.cc));
            }
            if button.label.len() > 8 {
                errors.push(format!("Button {} label '{}' exceeds 8 chars", i + 1, button.label));
            }
        }

        // Validate encoder if present
        if let Some(ref enc) = self.encoder {
            if enc.cc > 127 {
                errors.push(format!("Encoder CC {} exceeds 127", enc.cc));
            }
            if let Some(ref push) = enc.push {
                if push.cc > 127 {
                    errors.push(format!("Encoder push CC {} exceeds 127", push.cc));
                }
            }
        }

        // Validate expression pedals if present
        if let Some(ref exp) = self.expression {
            if exp.exp1.cc > 127 {
                errors.push(format!("EXP1 CC {} exceeds 127", exp.exp1.cc));
            }
            if exp.exp2.cc > 127 {
                errors.push(format!("EXP2 CC {} exceeds 127", exp.exp2.cc));
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
}
```

**Step 2: Add module to main.rs**

Add to `src-tauri/src/main.rs`:
```rust
mod config;
```

**Step 3: Run tests**

```bash
cd config-editor/src-tauri
cargo test
```

Expected: 2 tests pass

**Step 4: Commit**

```bash
git add config-editor/src-tauri/src/config.rs
git add config-editor/src-tauri/src/main.rs
git commit -m "feat: add Rust config types with validation"
```

---

### Task 2.3: Implement Config File Operations

**Files:**
- Create: `config-editor/src-tauri/src/commands.rs`

**Step 1: Create Tauri commands**

```rust
//! Tauri commands for config file operations

use crate::config::MidiCaptainConfig;
use std::fs;
use std::path::PathBuf;
use tauri::command;

/// Error type for config operations
#[derive(Debug, serde::Serialize)]
pub struct ConfigError {
    pub message: String,
    pub details: Option<Vec<String>>,
}

impl From<std::io::Error> for ConfigError {
    fn from(e: std::io::Error) -> Self {
        ConfigError {
            message: e.to_string(),
            details: None,
        }
    }
}

impl From<serde_json::Error> for ConfigError {
    fn from(e: serde_json::Error) -> Self {
        ConfigError {
            message: format!("JSON parse error: {}", e),
            details: None,
        }
    }
}

/// Read config from a file path
#[command]
pub fn read_config(path: String) -> Result<MidiCaptainConfig, ConfigError> {
    let contents = fs::read_to_string(&path)?;
    let config: MidiCaptainConfig = serde_json::from_str(&contents)?;
    Ok(config)
}

/// Read raw JSON from a file (for text editor)
#[command]
pub fn read_config_raw(path: String) -> Result<String, ConfigError> {
    let contents = fs::read_to_string(&path)?;
    // Pretty-print the JSON
    let value: serde_json::Value = serde_json::from_str(&contents)?;
    let pretty = serde_json::to_string_pretty(&value)?;
    Ok(pretty)
}

/// Write config to a file path
#[command]
pub fn write_config(path: String, config: MidiCaptainConfig) -> Result<(), ConfigError> {
    // Validate before writing
    if let Err(errors) = config.validate() {
        return Err(ConfigError {
            message: "Validation failed".to_string(),
            details: Some(errors),
        });
    }
    
    let json = serde_json::to_string_pretty(&config)?;
    fs::write(&path, json)?;
    Ok(())
}

/// Write raw JSON to a file (from text editor)
#[command]
pub fn write_config_raw(path: String, json: String) -> Result<(), ConfigError> {
    // Validate JSON is parseable
    let config: MidiCaptainConfig = serde_json::from_str(&json)?;
    
    // Validate config
    if let Err(errors) = config.validate() {
        return Err(ConfigError {
            message: "Validation failed".to_string(),
            details: Some(errors),
        });
    }
    
    // Pretty-print and write
    let pretty = serde_json::to_string_pretty(&config)?;
    fs::write(&path, pretty)?;
    Ok(())
}

/// Validate JSON without writing
#[command]
pub fn validate_config(json: String) -> Result<(), ConfigError> {
    let config: MidiCaptainConfig = serde_json::from_str(&json)?;
    
    if let Err(errors) = config.validate() {
        return Err(ConfigError {
            message: "Validation failed".to_string(),
            details: Some(errors),
        });
    }
    
    Ok(())
}

/// Get default profiles directory
#[command]
pub fn get_profiles_dir() -> Result<PathBuf, ConfigError> {
    let documents = dirs::document_dir().ok_or(ConfigError {
        message: "Could not find Documents folder".to_string(),
        details: None,
    })?;
    
    let profiles_dir = documents.join("MIDI Captain").join("profiles");
    
    // Create if doesn't exist
    if !profiles_dir.exists() {
        fs::create_dir_all(&profiles_dir)?;
    }
    
    Ok(profiles_dir)
}

/// List saved profiles
#[command]
pub fn list_profiles() -> Result<Vec<String>, ConfigError> {
    let profiles_dir = get_profiles_dir()?;
    
    let mut profiles = Vec::new();
    for entry in fs::read_dir(&profiles_dir)? {
        let entry = entry?;
        let path = entry.path();
        if path.extension().map_or(false, |ext| ext == "json") {
            if let Some(name) = path.file_stem() {
                profiles.push(name.to_string_lossy().to_string());
            }
        }
    }
    
    profiles.sort();
    Ok(profiles)
}

/// Save config as a profile
#[command]
pub fn save_profile(name: String, config: MidiCaptainConfig) -> Result<(), ConfigError> {
    let profiles_dir = get_profiles_dir()?;
    let path = profiles_dir.join(format!("{}.json", name));
    
    let json = serde_json::to_string_pretty(&config)?;
    fs::write(&path, json)?;
    Ok(())
}

/// Load a profile by name
#[command]
pub fn load_profile(name: String) -> Result<MidiCaptainConfig, ConfigError> {
    let profiles_dir = get_profiles_dir()?;
    let path = profiles_dir.join(format!("{}.json", name));
    
    let contents = fs::read_to_string(&path)?;
    let config: MidiCaptainConfig = serde_json::from_str(&contents)?;
    Ok(config)
}

/// Check if a profile exists
#[command]
pub fn profile_exists(name: String) -> Result<bool, ConfigError> {
    let profiles_dir = get_profiles_dir()?;
    let path = profiles_dir.join(format!("{}.json", name));
    Ok(path.exists())
}
```

**Step 2: Register commands in main.rs**

```rust
mod config;
mod commands;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            commands::read_config,
            commands::read_config_raw,
            commands::write_config,
            commands::write_config_raw,
            commands::validate_config,
            commands::get_profiles_dir,
            commands::list_profiles,
            commands::save_profile,
            commands::load_profile,
            commands::profile_exists,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**Step 3: Verify compilation**

```bash
cd config-editor
npm run tauri dev
```

Expected: App compiles and runs

**Step 4: Commit**

```bash
git add config-editor/src-tauri/src/commands.rs
git add config-editor/src-tauri/src/main.rs
git commit -m "feat: add Tauri commands for config and profile operations"
```

---

## Phase 3: Device Detection

### Task 3.1: Implement Volume Watcher

**Files:**
- Create: `config-editor/src-tauri/src/device.rs`

**Step 1: Create device detection module**

```rust
//! Device detection via volume mounting

use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher, Event, EventKind};
use std::path::PathBuf;
use std::sync::mpsc;
use tauri::{command, AppHandle, Emitter, Manager};

/// Known device volume names
const DEVICE_VOLUMES: &[&str] = &["CIRCUITPY", "MIDICAPTAIN"];

/// Detected device info
#[derive(Debug, Clone, serde::Serialize)]
pub struct DetectedDevice {
    pub name: String,
    pub path: PathBuf,
    pub config_path: PathBuf,
    pub has_config: bool,
}

/// Check if a volume is a MIDI Captain device
fn check_volume(path: &PathBuf) -> Option<DetectedDevice> {
    let name = path.file_name()?.to_str()?;
    
    if DEVICE_VOLUMES.iter().any(|v| name.eq_ignore_ascii_case(v)) {
        let config_path = path.join("config.json");
        let has_config = config_path.exists();
        
        Some(DetectedDevice {
            name: name.to_string(),
            path: path.clone(),
            config_path,
            has_config,
        })
    } else {
        None
    }
}

/// Scan for connected devices
#[command]
pub fn scan_devices() -> Vec<DetectedDevice> {
    let volumes_path = PathBuf::from("/Volumes");
    let mut devices = Vec::new();
    
    if let Ok(entries) = std::fs::read_dir(&volumes_path) {
        for entry in entries.flatten() {
            let path = entry.path();
            if let Some(device) = check_volume(&path) {
                devices.push(device);
            }
        }
    }
    
    devices
}

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

// Global flag to prevent multiple watchers
static WATCHER_STARTED: AtomicBool = AtomicBool::new(false);

/// Start watching for device connections
/// Emits "device-connected" and "device-disconnected" events
/// Note: Only one watcher can run at a time to prevent thread leaks
#[command]
pub fn start_device_watcher(app: AppHandle) -> Result<(), String> {
    // Prevent multiple watchers
    if WATCHER_STARTED.swap(true, Ordering::SeqCst) {
        return Ok(()); // Already running
    }
    
    let (tx, rx) = mpsc::channel();
    
    let mut watcher = RecommendedWatcher::new(
        move |res: Result<Event, notify::Error>| {
            if let Ok(event) = res {
                let _ = tx.send(event);
            }
        },
        Config::default(),
    ).map_err(|e| e.to_string())?;
    
    watcher.watch(
        std::path::Path::new("/Volumes"),
        RecursiveMode::NonRecursive,
    ).map_err(|e| e.to_string())?;
    
    // Spawn thread to handle events
    std::thread::spawn(move || {
        // Keep watcher alive
        let _watcher = watcher;
        
        for event in rx {
            match event.kind {
                EventKind::Create(_) => {
                    // Volume mounted - check if it's a device
                    for path in &event.paths {
                        if let Some(device) = check_volume(path) {
                            let _ = app.emit("device-connected", device);
                        }
                    }
                }
                EventKind::Remove(_) => {
                    // Volume unmounted
                    for path in &event.paths {
                        if let Some(name) = path.file_name() {
                            let name_str = name.to_string_lossy().to_string();
                            if DEVICE_VOLUMES.iter().any(|v| name_str.eq_ignore_ascii_case(v)) {
                                let _ = app.emit("device-disconnected", name_str);
                            }
                        }
                    }
                }
                _ => {}
            }
        }
    });
    
    Ok(())
}
```

**Step 2: Add module and commands to main.rs**

```rust
mod config;
mod commands;
mod device;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .invoke_handler(tauri::generate_handler![
            commands::read_config,
            commands::read_config_raw,
            commands::write_config,
            commands::write_config_raw,
            commands::validate_config,
            commands::get_profiles_dir,
            commands::list_profiles,
            commands::save_profile,
            commands::load_profile,
            commands::profile_exists,
            device::scan_devices,
            device::start_device_watcher,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

**Step 3: Verify compilation**

```bash
cd config-editor
cargo check --manifest-path src-tauri/Cargo.toml
```

**Step 4: Commit**

```bash
git add config-editor/src-tauri/src/device.rs
git add config-editor/src-tauri/src/main.rs
git commit -m "feat: add device detection via volume watching"
```

---

## Phase 4: Svelte Frontend MVP

### Task 4.1: Create TypeScript Types

**Files:**
- Create: `config-editor/src/lib/types.ts`

**Step 1: Define TypeScript interfaces**

```typescript
// MIDI Captain config types - mirrors Rust structs

export type ButtonColor = 
  | 'red' | 'green' | 'blue' | 'yellow' 
  | 'cyan' | 'magenta' | 'orange' | 'purple' | 'white';

export type ButtonMode = 'toggle' | 'momentary';
export type OffMode = 'dim' | 'off';
export type Polarity = 'normal' | 'inverted';
export type DeviceType = 'std10' | 'mini6';

export interface ButtonConfig {
  label: string;
  cc: number;
  color: ButtonColor;
  mode?: ButtonMode;
  off_mode?: OffMode;
}

export interface EncoderPush {
  enabled: boolean;
  cc: number;
  label: string;
  mode?: ButtonMode;
}

export interface EncoderConfig {
  enabled: boolean;
  cc: number;
  label: string;
  min?: number;
  max?: number;
  initial?: number;
  steps?: number | null;
  push?: EncoderPush;
}

export interface ExpressionConfig {
  enabled: boolean;
  cc: number;
  label: string;
  min?: number;
  max?: number;
  polarity?: Polarity;
  threshold?: number;
}

export interface ExpressionPedals {
  exp1: ExpressionConfig;
  exp2: ExpressionConfig;
}

export interface MidiCaptainConfig {
  device?: DeviceType;
  buttons: ButtonConfig[];
  encoder?: EncoderConfig;
  expression?: ExpressionPedals;
}

export interface DetectedDevice {
  name: string;
  path: string;
  config_path: string;
  has_config: boolean;
}

export interface ConfigError {
  message: string;
  details?: string[];
}

// Color mapping for UI
export const BUTTON_COLORS: Record<ButtonColor, string> = {
  red: '#ff0000',
  green: '#00ff00',
  blue: '#0000ff',
  yellow: '#ffff00',
  cyan: '#00ffff',
  magenta: '#ff00ff',
  orange: '#ff8000',
  purple: '#8000ff',
  white: '#ffffff',
};
```

**Step 2: Commit**

```bash
git add config-editor/src/lib/types.ts
git commit -m "feat: add TypeScript types for config"
```

---

### Task 4.2: Create Tauri API Wrapper

**Files:**
- Create: `config-editor/src/lib/api.ts`

**Step 1: Create API module**

```typescript
// Tauri command wrappers

import { invoke } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type { MidiCaptainConfig, DetectedDevice, ConfigError } from './types';

// Config operations
export async function readConfig(path: string): Promise<MidiCaptainConfig> {
  return invoke('read_config', { path });
}

export async function readConfigRaw(path: string): Promise<string> {
  return invoke('read_config_raw', { path });
}

export async function writeConfig(path: string, config: MidiCaptainConfig): Promise<void> {
  return invoke('write_config', { path, config });
}

export async function writeConfigRaw(path: string, json: string): Promise<void> {
  return invoke('write_config_raw', { path, json });
}

export async function validateConfig(json: string): Promise<void> {
  return invoke('validate_config', { json });
}

// Profile operations
export async function getProfilesDir(): Promise<string> {
  return invoke('get_profiles_dir');
}

export async function listProfiles(): Promise<string[]> {
  return invoke('list_profiles');
}

export async function saveProfile(name: string, config: MidiCaptainConfig): Promise<void> {
  return invoke('save_profile', { name, config });
}

export async function loadProfile(name: string): Promise<MidiCaptainConfig> {
  return invoke('load_profile', { name });
}

export async function profileExists(name: string): Promise<boolean> {
  return invoke('profile_exists', { name });
}

// Device operations
export async function scanDevices(): Promise<DetectedDevice[]> {
  return invoke('scan_devices');
}

export async function startDeviceWatcher(): Promise<void> {
  return invoke('start_device_watcher');
}

// Event listeners
export function onDeviceConnected(callback: (device: DetectedDevice) => void) {
  return listen<DetectedDevice>('device-connected', (event) => {
    callback(event.payload);
  });
}

export function onDeviceDisconnected(callback: (name: string) => void) {
  return listen<string>('device-disconnected', (event) => {
    callback(event.payload);
  });
}
```

**Step 2: Commit**

```bash
git add config-editor/src/lib/api.ts
git commit -m "feat: add Tauri API wrapper"
```

---

### Task 4.3: Create Main App Layout

**Files:**
- Modify: `config-editor/src/App.svelte`
- Create: `config-editor/src/lib/stores.ts`

**Step 1: Create stores for state management**

```typescript
// config-editor/src/lib/stores.ts
import { writable, derived } from 'svelte/store';
import type { DetectedDevice, MidiCaptainConfig } from './types';

// Connected devices
export const devices = writable<DetectedDevice[]>([]);

// Currently selected device
export const selectedDevice = writable<DetectedDevice | null>(null);

// Current config (parsed)
export const currentConfig = writable<MidiCaptainConfig | null>(null);

// Current config as raw JSON (for text editor)
export const currentConfigRaw = writable<string>('');

// Whether config has unsaved changes
export const hasUnsavedChanges = writable<boolean>(false);

// Validation errors
export const validationErrors = writable<string[]>([]);

// UI state
export const isLoading = writable<boolean>(false);
export const statusMessage = writable<string>('');

// Derived: is a device selected and has config
export const canEdit = derived(
  [selectedDevice, currentConfig],
  ([$device, $config]) => $device !== null && $config !== null
);
```

**Step 2: Create main App layout**

```svelte
<!-- config-editor/src/App.svelte -->
<script lang="ts">
  import { onMount } from 'svelte';
  import { 
    devices, selectedDevice, currentConfigRaw, 
    hasUnsavedChanges, validationErrors, statusMessage, isLoading 
  } from './lib/stores';
  import { 
    scanDevices, startDeviceWatcher, readConfigRaw, writeConfigRaw,
    onDeviceConnected, onDeviceDisconnected 
  } from './lib/api';
  import type { DetectedDevice } from './lib/types';

  let editorContent = '';
  
  onMount(async () => {
    // Initial device scan
    $devices = await scanDevices();
    
    // Start watching for device changes
    await startDeviceWatcher();
    
    // Listen for device events
    onDeviceConnected((device) => {
      $devices = [...$devices, device];
      $statusMessage = `Device connected: ${device.name}`;
    });
    
    onDeviceDisconnected((name) => {
      $devices = $devices.filter(d => d.name !== name);
      if ($selectedDevice?.name === name) {
        $selectedDevice = null;
        $currentConfigRaw = '';
      }
      $statusMessage = `Device disconnected: ${name}`;
    });
    
    // Auto-select if only one device
    if ($devices.length === 1) {
      await selectDevice($devices[0]);
    }
  });
  
  async function selectDevice(device: DetectedDevice) {
    if ($hasUnsavedChanges) {
      if (!confirm('You have unsaved changes. Discard them?')) {
        return;
      }
    }
    
    $selectedDevice = device;
    $isLoading = true;
    
    try {
      if (device.has_config) {
        $currentConfigRaw = await readConfigRaw(device.config_path);
        editorContent = $currentConfigRaw;
      } else {
        $currentConfigRaw = '';
        editorContent = '';
        $statusMessage = 'No config.json found on device';
      }
      $hasUnsavedChanges = false;
      $validationErrors = [];
    } catch (e: any) {
      $statusMessage = `Error reading config: ${e.message || e}`;
    } finally {
      $isLoading = false;
    }
  }
  
  async function saveToDevice() {
    if (!$selectedDevice) return;
    
    $isLoading = true;
    try {
      await writeConfigRaw($selectedDevice.config_path, editorContent);
      $currentConfigRaw = editorContent;
      $hasUnsavedChanges = false;
      $validationErrors = [];
      $statusMessage = 'Config saved to device!';
    } catch (e: any) {
      if (e.details) {
        $validationErrors = e.details;
      }
      $statusMessage = `Error: ${e.message || e}`;
    } finally {
      $isLoading = false;
    }
  }
  
  function handleEditorChange(event: Event) {
    const target = event.target as HTMLTextAreaElement;
    editorContent = target.value;
    $hasUnsavedChanges = editorContent !== $currentConfigRaw;
  }
</script>

<main>
  <header>
    <h1>MIDI Captain MAX Config Editor</h1>
    <div class="device-selector">
      {#if $devices.length === 0}
        <span class="no-device">No device connected</span>
      {:else}
        <select 
          value={$selectedDevice?.name ?? ''} 
          on:change={(e) => {
            const device = $devices.find(d => d.name === e.currentTarget.value);
            if (device) selectDevice(device);
          }}
        >
          <option value="" disabled>Select device...</option>
          {#each $devices as device}
            <option value={device.name}>{device.name}</option>
          {/each}
        </select>
      {/if}
    </div>
  </header>
  
  <div class="editor-container">
    {#if $selectedDevice}
      <textarea
        class="json-editor"
        value={editorContent}
        on:input={handleEditorChange}
        spellcheck="false"
        placeholder="No config loaded"
      ></textarea>
    {:else}
      <div class="placeholder">
        <p>Connect a MIDI Captain device or select one from the dropdown.</p>
        <p>Watching for devices: CIRCUITPY, MIDICAPTAIN</p>
      </div>
    {/if}
  </div>
  
  {#if $validationErrors.length > 0}
    <div class="errors">
      <strong>Validation Errors:</strong>
      <ul>
        {#each $validationErrors as error}
          <li>{error}</li>
        {/each}
      </ul>
    </div>
  {/if}
  
  <footer>
    <div class="status">{$statusMessage}</div>
    <div class="actions">
      {#if $hasUnsavedChanges}
        <span class="unsaved">● Unsaved changes</span>
      {/if}
      <button 
        on:click={saveToDevice} 
        disabled={!$selectedDevice || !$hasUnsavedChanges || $isLoading}
      >
        Save to Device
      </button>
    </div>
  </footer>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #1e1e1e;
    color: #d4d4d4;
  }
  
  main {
    display: flex;
    flex-direction: column;
    height: 100vh;
  }
  
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: #2d2d2d;
    border-bottom: 1px solid #404040;
  }
  
  h1 {
    margin: 0;
    font-size: 18px;
    font-weight: 500;
  }
  
  .device-selector select {
    padding: 6px 12px;
    font-size: 14px;
    background: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
  }
  
  .no-device {
    color: #888;
    font-style: italic;
  }
  
  .editor-container {
    flex: 1;
    padding: 20px;
    overflow: hidden;
  }
  
  .json-editor {
    width: 100%;
    height: 100%;
    font-family: 'SF Mono', Monaco, 'Courier New', monospace;
    font-size: 14px;
    line-height: 1.5;
    background: #1e1e1e;
    color: #d4d4d4;
    border: 1px solid #404040;
    border-radius: 4px;
    padding: 16px;
    resize: none;
    box-sizing: border-box;
  }
  
  .json-editor:focus {
    outline: none;
    border-color: #0078d4;
  }
  
  .placeholder {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100%;
    color: #888;
  }
  
  .errors {
    padding: 12px 20px;
    background: #3c1f1f;
    border-top: 1px solid #5c2f2f;
    color: #f48771;
  }
  
  .errors ul {
    margin: 8px 0 0 0;
    padding-left: 20px;
  }
  
  footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: #2d2d2d;
    border-top: 1px solid #404040;
  }
  
  .status {
    color: #888;
    font-size: 13px;
  }
  
  .actions {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .unsaved {
    color: #dcdcaa;
    font-size: 13px;
  }
  
  button {
    padding: 8px 16px;
    font-size: 14px;
    background: #0078d4;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  button:hover:not(:disabled) {
    background: #1084d8;
  }
  
  button:disabled {
    background: #555;
    cursor: not-allowed;
  }
</style>
```

**Step 3: Verify it runs**

```bash
cd config-editor
npm run tauri dev
```

Expected: App shows with header, editor area, footer

**Step 4: Commit**

```bash
git add config-editor/src/lib/stores.ts
git add config-editor/src/App.svelte
git commit -m "feat: add main app layout with device selector and JSON editor"
```

---

## Phase 5: JSON Editor Integration

### Task 5.1: Add CodeMirror for Syntax Highlighting

**Files:**
- Create: `config-editor/src/lib/components/JsonEditor.svelte`
- Modify: `config-editor/src/App.svelte`

> **Note:** CodeMirror dependencies were installed in Task 1.2. If starting fresh, run:
> `npm install @codemirror/state @codemirror/view @codemirror/lang-json @codemirror/theme-one-dark @codemirror/commands`

**Step 1: Create JsonEditor component**

```svelte
<!-- config-editor/src/lib/components/JsonEditor.svelte -->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { EditorState } from '@codemirror/state';
  import { EditorView, keymap, lineNumbers, highlightActiveLine } from '@codemirror/view';
  import { json } from '@codemirror/lang-json';
  import { oneDark } from '@codemirror/theme-one-dark';
  import { defaultKeymap } from '@codemirror/commands';

  export let value: string = '';
  export let readonly: boolean = false;

  const dispatch = createEventDispatcher<{ change: string }>();
  
  let container: HTMLDivElement;
  let view: EditorView;

  onMount(() => {
    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        highlightActiveLine(),
        json(),
        oneDark,
        keymap.of(defaultKeymap),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const newValue = update.state.doc.toString();
            dispatch('change', newValue);
          }
        }),
        EditorState.readOnly.of(readonly),
      ],
    });

    view = new EditorView({
      state,
      parent: container,
    });
  });

  onDestroy(() => {
    view?.destroy();
  });

  // Update content when value prop changes externally
  $: if (view && value !== view.state.doc.toString()) {
    view.dispatch({
      changes: {
        from: 0,
        to: view.state.doc.length,
        insert: value,
      },
    });
  }
</script>

<div class="editor-wrapper" bind:this={container}></div>

<style>
  .editor-wrapper {
    height: 100%;
    overflow: auto;
    border: 1px solid #404040;
    border-radius: 4px;
  }
  
  .editor-wrapper :global(.cm-editor) {
    height: 100%;
  }
  
  .editor-wrapper :global(.cm-scroller) {
    font-family: 'SF Mono', Monaco, 'Courier New', monospace;
    font-size: 14px;
  }
</style>
```

**Step 2: Update App.svelte to use JsonEditor**

Replace the `<textarea>` with the JsonEditor component:

```svelte
<!-- In App.svelte, update the imports and editor section -->
<script lang="ts">
  // ... existing imports ...
  import JsonEditor from './lib/components/JsonEditor.svelte';
  
  // ... rest of script ...
  
  function handleEditorChange(event: CustomEvent<string>) {
    editorContent = event.detail;
    $hasUnsavedChanges = editorContent !== $currentConfigRaw;
  }
</script>

<!-- Replace the textarea in editor-container -->
<div class="editor-container">
  {#if $selectedDevice}
    <JsonEditor 
      value={editorContent} 
      on:change={handleEditorChange}
    />
  {:else}
    <div class="placeholder">
      <p>Connect a MIDI Captain device or select one from the dropdown.</p>
      <p>Watching for devices: CIRCUITPY, MIDICAPTAIN</p>
    </div>
  {/if}
</div>
```

**Step 3: Test**

```bash
cd config-editor
npm run tauri dev
```

Expected: JSON editor with syntax highlighting, line numbers

**Step 4: Commit**

```bash
git add config-editor/src/lib/components/JsonEditor.svelte
git add config-editor/src/App.svelte
git commit -m "feat: add CodeMirror JSON editor with syntax highlighting"
```

---

## Phase 6: Profile Management

### Task 6.1: Add Profile UI

**Files:**
- Create: `config-editor/src/lib/components/ProfileManager.svelte`
- Modify: `config-editor/src/App.svelte`

**Step 1: Create ProfileManager component**

```svelte
<!-- config-editor/src/lib/components/ProfileManager.svelte -->
<script lang="ts">
  import { createEventDispatcher, onMount } from 'svelte';
  import { listProfiles, saveProfile, loadProfile, profileExists } from '../api';
  import type { MidiCaptainConfig } from '../types';

  export let currentConfig: MidiCaptainConfig | null = null;
  
  const dispatch = createEventDispatcher<{ 
    load: MidiCaptainConfig;
    status: string;
  }>();

  let profiles: string[] = [];
  let selectedProfile = '';
  let newProfileName = '';
  let showSaveDialog = false;
  let isSaving = false;
  let isLoading = false;

  onMount(async () => {
    await refreshProfiles();
  });

  async function refreshProfiles() {
    try {
      profiles = await listProfiles();
    } catch (e: any) {
      dispatch('status', `Error loading profiles: ${e.message || e}`);
    }
  }

  async function handleLoad() {
    if (!selectedProfile) return;
    
    isLoading = true;
    try {
      const config = await loadProfile(selectedProfile);
      dispatch('load', config);
      dispatch('status', `Loaded profile: ${selectedProfile}`);
    } catch (e: any) {
      dispatch('status', `Error loading profile: ${e.message || e}`);
    } finally {
      isLoading = false;
    }
  }

  async function handleSave() {
    if (!newProfileName.trim() || !currentConfig) return;
    
    const name = newProfileName.trim();
    
    // Check if exists
    try {
      const exists = await profileExists(name);
      if (exists) {
        if (!confirm(`Profile "${name}" already exists. Overwrite?`)) {
          return;
        }
      }
    } catch (e) {
      // Ignore, proceed with save
    }
    
    isSaving = true;
    try {
      await saveProfile(name, currentConfig);
      await refreshProfiles();
      selectedProfile = name;
      newProfileName = '';
      showSaveDialog = false;
      dispatch('status', `Saved profile: ${name}`);
    } catch (e: any) {
      dispatch('status', `Error saving profile: ${e.message || e}`);
    } finally {
      isSaving = false;
    }
  }
</script>

<div class="profile-manager">
  <div class="profile-load">
    <select bind:value={selectedProfile}>
      <option value="" disabled>Select profile...</option>
      {#each profiles as profile}
        <option value={profile}>{profile}</option>
      {/each}
    </select>
    <button on:click={handleLoad} disabled={!selectedProfile || isLoading}>
      Load
    </button>
  </div>
  
  {#if showSaveDialog}
    <div class="save-dialog">
      <input 
        type="text" 
        placeholder="Profile name" 
        bind:value={newProfileName}
        on:keydown={(e) => e.key === 'Enter' && handleSave()}
      />
      <button on:click={handleSave} disabled={!newProfileName.trim() || isSaving}>
        Save
      </button>
      <button class="cancel" on:click={() => showSaveDialog = false}>
        Cancel
      </button>
    </div>
  {:else}
    <button on:click={() => showSaveDialog = true} disabled={!currentConfig}>
      Save Profile...
    </button>
  {/if}
</div>

<style>
  .profile-manager {
    display: flex;
    gap: 12px;
    align-items: center;
  }
  
  .profile-load {
    display: flex;
    gap: 4px;
  }
  
  select, input {
    padding: 6px 12px;
    font-size: 14px;
    background: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
  }
  
  input {
    width: 150px;
  }
  
  .save-dialog {
    display: flex;
    gap: 4px;
  }
  
  button {
    padding: 6px 12px;
    font-size: 14px;
    background: #3c3c3c;
    color: #d4d4d4;
    border: 1px solid #555;
    border-radius: 4px;
    cursor: pointer;
  }
  
  button:hover:not(:disabled) {
    background: #4c4c4c;
  }
  
  button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  button.cancel {
    background: transparent;
    border-color: transparent;
  }
</style>
```

**Step 2: Integrate ProfileManager into App.svelte**

Add to header section. Note: We parse `editorContent` to pass a config object to ProfileManager, with error handling for invalid JSON:

```svelte
<script lang="ts">
  // Add helper function to safely parse current editor content
  function getCurrentConfigObject(): MidiCaptainConfig | null {
    try {
      return editorContent ? JSON.parse(editorContent) : null;
    } catch {
      return null; // Invalid JSON, can't save as profile
    }
  }
</script>

<header>
  <h1>MIDI Captain MAX Config Editor</h1>
  
  <ProfileManager 
    currentConfig={getCurrentConfigObject()}
    on:load={(e) => {
      editorContent = JSON.stringify(e.detail, null, 2);
      $currentConfigRaw = editorContent;
      $hasUnsavedChanges = false;
    }}
    on:status={(e) => $statusMessage = e.detail}
  />
  
  <div class="device-selector">
    <!-- existing device selector -->
  </div>
</header>
```

**Step 3: Commit**

```bash
git add config-editor/src/lib/components/ProfileManager.svelte
git add config-editor/src/App.svelte
git commit -m "feat: add profile save/load UI"
```

---

## Phase 7: Firmware Installation

### Task 7.1: Add Firmware Install Command

**Files:**
- Modify: `config-editor/src-tauri/src/commands.rs`

**Step 1: Add firmware installation command**

Add to `commands.rs`:

```rust
/// Path to bundled firmware files (installed by pkg)
const FIRMWARE_DIR: &str = "/usr/local/share/midicaptain-firmware";

/// Install firmware to a device
#[command]
pub fn install_firmware(device_path: String) -> Result<(), ConfigError> {
    let firmware_path = std::path::Path::new(FIRMWARE_DIR);
    let device_path = std::path::Path::new(&device_path);
    
    if !firmware_path.exists() {
        return Err(ConfigError {
            message: format!("Firmware not found at {}. Run the installer first.", FIRMWARE_DIR),
            details: None,
        });
    }
    
    // Files to copy
    let files = ["code.py", "boot.py"];
    let dirs = ["devices", "fonts"];
    
    for file in &files {
        let src = firmware_path.join(file);
        let dst = device_path.join(file);
        if src.exists() {
            fs::copy(&src, &dst)?;
        }
    }
    
    for dir in &dirs {
        let src = firmware_path.join(dir);
        let dst = device_path.join(dir);
        if src.exists() {
            // Remove existing dir first
            if dst.exists() {
                fs::remove_dir_all(&dst)?;
            }
            copy_dir_recursive(&src, &dst)?;
        }
    }
    
    Ok(())
}

/// Recursively copy a directory
fn copy_dir_recursive(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
    fs::create_dir_all(dst)?;
    for entry in fs::read_dir(src)? {
        let entry = entry?;
        let src_path = entry.path();
        let dst_path = dst.join(entry.file_name());
        
        if src_path.is_dir() {
            copy_dir_recursive(&src_path, &dst_path)?;
        } else {
            fs::copy(&src_path, &dst_path)?;
        }
    }
    Ok(())
}

/// Check if firmware is installed
#[command]
pub fn is_firmware_installed() -> bool {
    std::path::Path::new(FIRMWARE_DIR).join("code.py").exists()
}
```

**Step 2: Register new commands in main.rs**

Add to the `generate_handler!` macro:

```rust
commands::install_firmware,
commands::is_firmware_installed,
```

**Step 3: Commit**

```bash
git add config-editor/src-tauri/src/commands.rs
git add config-editor/src-tauri/src/main.rs
git commit -m "feat: add firmware installation commands"
```

---

### Task 7.2: Add Install Firmware UI

**Files:**
- Create: `config-editor/src/lib/components/FirmwareInstaller.svelte`

**Step 1: Create component**

```svelte
<!-- config-editor/src/lib/components/FirmwareInstaller.svelte -->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { DetectedDevice } from '../types';
  import { createEventDispatcher } from 'svelte';

  export let device: DetectedDevice | null = null;
  
  const dispatch = createEventDispatcher<{ status: string }>();
  
  let isInstalling = false;
  let firmwareInstalled = false;

  async function checkFirmware() {
    firmwareInstalled = await invoke('is_firmware_installed');
  }
  
  async function installFirmware() {
    if (!device) return;
    
    if (!confirm(`Install firmware to ${device.name}? This will overwrite existing firmware files.`)) {
      return;
    }
    
    isInstalling = true;
    try {
      await invoke('install_firmware', { devicePath: device.path });
      dispatch('status', `Firmware installed to ${device.name}!`);
    } catch (e: any) {
      dispatch('status', `Error: ${e.message || e}`);
    } finally {
      isInstalling = false;
    }
  }
  
  $: if (device) checkFirmware();
</script>

{#if device}
  <button 
    class="install-btn"
    on:click={installFirmware} 
    disabled={isInstalling || !firmwareInstalled}
    title={firmwareInstalled ? 'Install firmware to device' : 'Firmware not found - run installer first'}
  >
    {#if isInstalling}
      Installing...
    {:else}
      Install Firmware
    {/if}
  </button>
{/if}

<style>
  .install-btn {
    padding: 6px 12px;
    font-size: 14px;
    background: #4a7c4e;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
  }
  
  .install-btn:hover:not(:disabled) {
    background: #5a8c5e;
  }
  
  .install-btn:disabled {
    background: #555;
    cursor: not-allowed;
  }
</style>
```

**Step 2: Add to App.svelte actions section**

```svelte
<div class="actions">
  <FirmwareInstaller 
    device={$selectedDevice} 
    on:status={(e) => $statusMessage = e.detail}
  />
  <!-- existing buttons -->
</div>
```

**Step 3: Commit**

```bash
git add config-editor/src/lib/components/FirmwareInstaller.svelte
git add config-editor/src/App.svelte
git commit -m "feat: add firmware install button"
```

---

## Phase 8: macOS Architecture Hardening

> **Added 2026-02-04** after macOS architecture review. Addresses critical issues for production quality.

### Task 8.1: Create macOS Entitlements

**Files:**
- Create: `config-editor/src-tauri/Entitlements.plist`
- Modify: `config-editor/src-tauri/tauri.conf.json`

**Context:** The app needs entitlements for `/Volumes` access. Without them, code signing and notarization will fail.

**Step 1: Create entitlements file**

Create `config-editor/src-tauri/Entitlements.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Hardened runtime -->
    <key>com.apple.security.cs.allow-unsigned-executable-memory</key>
    <false/>
    
    <!-- For removable media access (USB devices) -->
    <key>com.apple.security.files.user-selected.read-write</key>
    <true/>
    
    <!-- /Volumes access for device detection -->
    <key>com.apple.security.temporary-exception.files.absolute-path.read-write</key>
    <array>
        <string>/Volumes/</string>
    </array>
</dict>
</plist>
```

**Step 2: Update tauri.conf.json to reference entitlements**

In the `bundle.macOS` section:
```json
"macOS": {
  "minimumSystemVersion": "10.15",
  "signingIdentity": "-",
  "entitlements": "Entitlements.plist"
}
```

**Step 3: Commit**

```bash
git add config-editor/src-tauri/Entitlements.plist
git add config-editor/src-tauri/tauri.conf.json
git commit -m "feat: add macOS entitlements for /Volumes access"
```

---

### Task 8.2: Fix Volume Ejection Race Condition

**Files:**
- Modify: `config-editor/src-tauri/src/commands.rs`

**Context:** When a user ejects a device via Finder, there's a window where the volume still appears in `/Volumes` but writes will fail or corrupt data. We need to verify mount state before writes and sync after.

**Step 1: Add mount verification and sync to write_config**

Add to `commands.rs`:
```rust
use std::os::unix::fs::MetadataExt;

/// Check if a volume is still mounted (not being ejected)
fn is_volume_mounted(volume_path: &std::path::Path) -> bool {
    // Check if we can stat the volume and it has a different device ID than root
    if let (Ok(vol_meta), Ok(root_meta)) = (
        volume_path.metadata(),
        std::path::Path::new("/").metadata()
    ) {
        vol_meta.dev() != root_meta.dev()
    } else {
        false
    }
}

/// Get the volume path from a file path (e.g., /Volumes/CIRCUITPY from /Volumes/CIRCUITPY/config.json)
fn get_volume_path(path: &std::path::Path) -> Option<std::path::PathBuf> {
    path.ancestors()
        .find(|p| p.parent() == Some(std::path::Path::new("/Volumes")))
        .map(|p| p.to_path_buf())
}
```

**Step 2: Update write_config to use verification**

```rust
#[command]
pub fn write_config(path: String, config: MidiCaptainConfig) -> Result<(), ConfigError> {
    validate_device_path(&path)?;
    
    let path_obj = std::path::Path::new(&path);
    
    // Verify volume is still mounted
    if let Some(volume_path) = get_volume_path(path_obj) {
        if !is_volume_mounted(&volume_path) {
            return Err(ConfigError {
                message: "Device was disconnected".to_string(),
                details: None,
            });
        }
    }
    
    // Validate before writing
    if let Err(errors) = config.validate() {
        return Err(ConfigError {
            message: "Validation failed".to_string(),
            details: Some(errors),
        });
    }
    
    let json = serde_json::to_string_pretty(&config)?;
    fs::write(&path, &json)?;
    
    // Sync to ensure data reaches device before user ejects
    if let Ok(file) = fs::File::open(&path) {
        let _ = file.sync_all();
    }
    
    Ok(())
}
```

**Step 3: Do the same for write_config_raw**

Apply the same mount verification and sync to `write_config_raw`.

**Step 4: Commit**

```bash
git add config-editor/src-tauri/src/commands.rs
git commit -m "fix: add mount verification and sync to prevent data loss on ejection"
```

---

### Task 8.3: Configure FSEvents for Lower Latency

**Files:**
- Modify: `config-editor/src-tauri/src/device.rs`

**Context:** The notify crate's default FSEvents config can have up to 30-second delays. Configure for faster response.

**Step 1: Update watcher configuration**

In `start_device_watcher`:
```rust
use notify::Config;
use std::time::Duration;

let config = Config::default()
    .with_poll_interval(Duration::from_millis(500));

let mut watcher = RecommendedWatcher::new(
    move |res: Result<Event, notify::Error>| {
        if let Ok(event) = res {
            let _ = tx.send(event);
        }
    },
    config,  // Use configured settings instead of Config::default()
)?;
```

**Step 2: Commit**

```bash
git add config-editor/src-tauri/src/device.rs
git commit -m "perf: configure FSEvents for lower latency device detection"
```

---

### Task 8.4: Add Device Disconnection Warning Dialog

**Files:**
- Modify: `config-editor/src/App.svelte`
- Modify: `config-editor/package.json` (add dialog plugin if needed)

**Context:** If a device is disconnected while the editor has unsaved changes, users should be warned about data loss.

**Step 1: Update disconnect handler in App.svelte**

```typescript
import { message } from '@tauri-apps/plugin-dialog';

// In the device disconnect handler:
unlistenDisconnect = await onDeviceDisconnected(async (name) => {
  const wasSelected = selectedDevice?.name === name;
  
  devices = devices.filter(d => d.name !== name);
  
  if (wasSelected) {
    if (hasUnsavedChanges) {
      await message(
        `Device "${name}" was disconnected. Your unsaved changes have been lost.`,
        { title: 'Device Disconnected', kind: 'warning' }
      );
    }
    selectedDevice = null;
    currentConfigRaw = '';
    hasUnsavedChanges = false;
  }
  
  statusMessage = `Device disconnected: ${name}`;
});
```

**Step 2: Commit**

```bash
git add config-editor/src/App.svelte
git commit -m "feat: add warning dialog when device disconnected with unsaved changes"
```

---

### Task 8.5: Remove Unnecessary macOSPrivateApi Flag

**Files:**
- Modify: `config-editor/src-tauri/tauri.conf.json`

**Context:** `macOSPrivateApi: true` enables private APIs (transparent backgrounds, etc.) that we don't use. Remove to simplify notarization.

**Step 1: Set macOSPrivateApi to false**

In `tauri.conf.json`:
```json
"app": {
  "macOSPrivateApi": false,
  // ...
}
```

**Step 2: Commit**

```bash
git add config-editor/src-tauri/tauri.conf.json
git commit -m "chore: disable macOSPrivateApi flag (not needed)"
```

---

### Task 8.6: Add Dark Mode Support

**Files:**
- Modify: `config-editor/src/App.svelte`

**Context:** macOS HIG requires apps to respect system Dark/Light mode preferences.

**Step 1: Replace hardcoded dark styles with CSS custom properties**

```css
:global(body) {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  
  /* Light mode defaults */
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --bg-tertiary: #e0e0e0;
  --text-primary: #1e1e1e;
  --text-secondary: #666666;
  --border-color: #d0d0d0;
  --accent: #0078d4;
  --success: #4a7c4e;
  --warning: #f0ad4e;
  
  background: var(--bg-primary);
  color: var(--text-primary);
}

@media (prefers-color-scheme: dark) {
  :global(body) {
    --bg-primary: #1e1e1e;
    --bg-secondary: #2d2d2d;
    --bg-tertiary: #3c3c3c;
    --text-primary: #d4d4d4;
    --text-secondary: #888888;
    --border-color: #404040;
    --accent: #0078d4;
    --success: #4a7c4e;
    --warning: #f0ad4e;
  }
}
```

**Step 2: Update component styles to use CSS variables**

Replace hardcoded colors (`#1e1e1e`, `#2d2d2d`, etc.) with `var(--bg-primary)`, `var(--bg-secondary)`, etc.

**Step 3: Commit**

```bash
git add config-editor/src/App.svelte
git commit -m "feat: add dark/light mode support following system preference"
```

---

### Task 8.7: Add Keyboard Shortcut (⌘S to Save)

**Files:**
- Modify: `config-editor/src/App.svelte`

**Context:** macOS users expect ⌘S to save. Add keyboard shortcut support.

**Step 1: Add keydown listener in onMount**

```typescript
// In onMount:
const handleKeydown = async (e: KeyboardEvent) => {
  if (e.metaKey && e.key === 's') {
    e.preventDefault();
    if (selectedDevice && hasUnsavedChanges) {
      await saveToDevice();
    }
  }
};

document.addEventListener('keydown', handleKeydown);

// In cleanup:
return () => {
  document.removeEventListener('keydown', handleKeydown);
  // ... other cleanup
};
```

**Step 2: Commit**

```bash
git add config-editor/src/App.svelte
git commit -m "feat: add ⌘S keyboard shortcut to save"
```

---

### Task 8.8: Fix Minor Issues (App Category, HTML Title)

**Files:**
- Modify: `config-editor/src-tauri/tauri.conf.json`
- Modify: `config-editor/src/app.html`

**Step 1: Change app category to Music**

In `tauri.conf.json`:
```json
"bundle": {
  "category": "Music",
  // ...
}
```

**Step 2: Fix HTML title**

In `src/app.html`:
```html
<title>MIDI Captain Config Editor</title>
```

**Step 3: Commit**

```bash
git add config-editor/src-tauri/tauri.conf.json
git add config-editor/src/app.html
git commit -m "chore: fix app category and HTML title"
```

---

## Phase 9: Validation & Device-Specific UI

### Task 9.1: Add Live Validation

**Files:**
- Modify: `config-editor/src/App.svelte`

**Step 1: Add debounced validation**

```svelte
<script lang="ts">
  import { validateConfig } from './lib/api';
  
  let validationTimeout: ReturnType<typeof setTimeout>;
  
  function handleEditorChange(event: CustomEvent<string>) {
    editorContent = event.detail;
    $hasUnsavedChanges = editorContent !== $currentConfigRaw;
    
    // Debounced validation
    clearTimeout(validationTimeout);
    validationTimeout = setTimeout(async () => {
      try {
        await validateConfig(editorContent);
        $validationErrors = [];
      } catch (e: any) {
        if (e.details) {
          $validationErrors = e.details;
        } else {
          $validationErrors = [e.message || 'Invalid JSON'];
        }
      }
    }, 500);
  }
</script>
```

**Step 2: Commit**

```bash
git add config-editor/src/App.svelte
git commit -m "feat: add live validation with debounce"
```

---

### Task 9.2: Add Color Picker (if native is easy)

The native macOS color picker can be accessed via Tauri's dialog plugin or a custom Rust command. For MVP, we'll use a simple HTML color input which maps well to the defined colors.

**Files:**
- Create: `config-editor/src/lib/components/ColorPicker.svelte`

**Step 1: Create simple color picker**

```svelte
<!-- config-editor/src/lib/components/ColorPicker.svelte -->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { ButtonColor } from '../types';
  import { BUTTON_COLORS } from '../types';

  export let value: ButtonColor = 'green';
  
  const dispatch = createEventDispatcher<{ change: ButtonColor }>();
  
  const colorOptions: ButtonColor[] = [
    'red', 'green', 'blue', 'yellow', 
    'cyan', 'magenta', 'orange', 'purple', 'white'
  ];
</script>

<div class="color-picker">
  {#each colorOptions as color}
    <button
      class="color-swatch"
      class:selected={value === color}
      style="background-color: {BUTTON_COLORS[color]}"
      title={color}
      on:click={() => {
        value = color;
        dispatch('change', color);
      }}
    />
  {/each}
</div>

<style>
  .color-picker {
    display: flex;
    gap: 4px;
  }
  
  .color-swatch {
    width: 24px;
    height: 24px;
    border: 2px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    padding: 0;
  }
  
  .color-swatch:hover {
    border-color: #888;
  }
  
  .color-swatch.selected {
    border-color: white;
    box-shadow: 0 0 4px rgba(255,255,255,0.5);
  }
</style>
```

This color picker is for future GUI mode. For MVP, the JSON editor is sufficient.

**Step 2: Commit**

```bash
git add config-editor/src/lib/components/ColorPicker.svelte
git commit -m "feat: add color picker component for future GUI mode"
```

---

## Phase 10: Packaging & Distribution

### Task 10.1: Update Build Script

**Files:**
- Modify: `tools/build-installer.sh`

**Step 1: Add Tauri build to installer script**

Add section to build the Tauri app before packaging:

```bash
# Build the Tauri config editor app
echo "Building Tauri config editor..."
TAURI_DIR="$PROJECT_ROOT/config-editor"

if [ -d "$TAURI_DIR" ]; then
    cd "$TAURI_DIR"
    npm install
    npm run tauri build
    
    # Copy the built app to payload
    BUILT_APP="$TAURI_DIR/src-tauri/target/release/bundle/macos/MIDI Captain MAX Config Editor.app"
    if [ -d "$BUILT_APP" ]; then
        rm -rf "$PAYLOAD_ROOT/Applications/MIDI Captain Installer.app"  # Remove old AppleScript app
        cp -R "$BUILT_APP" "$PAYLOAD_ROOT/Applications/"
        echo "  ✓ Tauri app added to payload"
    fi
    
    cd "$PROJECT_ROOT"
fi
```

**Step 2: Commit**

```bash
git add tools/build-installer.sh
git commit -m "chore: update installer to include Tauri config editor"
```

---

### Task 10.2: Update CI/CD

**Files:**
- Modify: `.github/workflows/ci.yml`

**Step 1: Add Tauri build job**

Add job for building the config editor:

```yaml
build-config-editor:
  runs-on: macos-latest
  steps:
    - uses: actions/checkout@v4
    
    - name: Setup Node.js
      uses: actions/setup-node@v4
      with:
        node-version: '20'
    
    - name: Setup Rust
      uses: dtolnay/rust-toolchain@stable
    
    - name: Install dependencies
      run: |
        cd config-editor
        npm install
    
    - name: Build Tauri app
      run: |
        cd config-editor
        npm run tauri build
    
    - name: Upload artifact
      uses: actions/upload-artifact@v4
      with:
        name: config-editor-macos
        path: config-editor/src-tauri/target/release/bundle/macos/*.app
```

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add Tauri config editor build job"
```

---

## Future Phases

These are planned for post-MVP:

### Phase 10: GUI Editor Mode
- Visual button layout preview
- Click-to-edit fields
- Drag-and-drop CC assignment
- Toggle between JSON and GUI views

### Phase 11: Windows Support
- Tauri builds for Windows out of the box
- Update device detection for Windows drive letters
- Test and fix any path handling issues

### Phase 12: Mobile Support (Tauri v2)
- iOS app via Tauri mobile
- Android app
- Requires USB OTG detection or Bluetooth config transfer

### Phase 13: Advanced Features
- Backup/restore device configs
- Config diff/merge
- Preset library sharing
- SysEx configuration import

---

## Appendix: File Structure Summary

After completing all phases:

```
config-editor/
├── src/                          # Svelte frontend
│   ├── App.svelte
│   ├── main.ts
│   └── lib/
│       ├── api.ts
│       ├── stores.ts
│       ├── types.ts
│       └── components/
│           ├── JsonEditor.svelte
│           ├── ProfileManager.svelte
│           ├── FirmwareInstaller.svelte
│           └── ColorPicker.svelte
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── main.rs
│   │   ├── config.rs
│   │   ├── commands.rs
│   │   └── device.rs
│   ├── Cargo.toml
│   └── tauri.conf.json
├── package.json
└── ...
```

---

## Execution

This plan has 10 phases with approximately 25 tasks. Estimated effort:

| Phase | Status | Effort |
|-------|--------|--------|
| Phase 1: Project Scaffolding | ✅ Complete | - |
| Phase 2: Rust Backend Core | ✅ Complete | - |
| Phase 3: Device Detection | ✅ Complete | - |
| Phase 4: Svelte Frontend MVP | ✅ Complete | - |
| Phase 5: JSON Editor Integration | ✅ Complete | - |
| Phase 6: Profile Management | Not started | 2-3 hours |
| Phase 7: Firmware Installation | Not started | 2-3 hours |
| Phase 8: macOS Architecture Hardening | Not started | 3-4 hours |
| Phase 9: Validation & Device-Specific UI | Not started | 2-3 hours |
| Phase 10: Packaging & Distribution | Not started | 2-3 hours |

**Code Review Fixes Applied:**
- ✅ Path traversal protection (Critical)
- ✅ CSP enabled (Critical)
- ✅ Event listener memory leak fix (Important)
- ✅ Encoder/expression validation (Important)
- ✅ Watcher shutdown mechanism (Minor)
- ✅ Meaningful tests (Minor)

**macOS Review Issues (Phase 8):**
- 🔴 Create entitlements file (Task 8.1)
- 🔴 Fix volume ejection race condition (Task 8.2)
- 🔴 Configure FSEvents latency (Task 8.3)
- 🟠 Add disconnect warning dialog (Task 8.4)
- 🟠 Remove macOSPrivateApi flag (Task 8.5)
- 🟠 Add dark mode support (Task 8.6)
- 🟡 Add ⌘S keyboard shortcut (Task 8.7)
- 🟡 Fix app category and title (Task 8.8)

Ready to execute? Use the executing-plans skill.
