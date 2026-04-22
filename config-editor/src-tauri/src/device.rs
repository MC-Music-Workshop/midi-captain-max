//! Device detection via volume mounting

#[cfg(not(target_os = "windows"))]
use notify::{Config, RecommendedWatcher, RecursiveMode, Watcher, Event, EventKind};
use std::path::PathBuf;
use std::sync::mpsc::{self, Sender, Receiver};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{command, AppHandle, Emitter};

#[cfg(target_os = "windows")]
use std::collections::HashSet;

/// Known device volume names
const DEVICE_VOLUMES: &[&str] = &["CIRCUITPY", "MIDICAPTAIN"];

/// Check if a path contains a recognizable MIDI Captain config.json by
/// looking for the "device" key with a known device type value.
///
/// Used as a fallback when the volume name is not in `DEVICE_VOLUMES` —
/// i.e., the user has configured a custom `usb_drive_name` in their config.
pub fn is_midi_captain_config(config_path: &std::path::Path) -> bool {
    if !config_path.exists() {
        return false;
    }
    let Ok(contents) = std::fs::read_to_string(config_path) else { return false };
    let Ok(value) = serde_json::from_str::<serde_json::Value>(&contents) else { return false };
    value
        .get("device")
        .and_then(|v| v.as_str())
        .and_then(crate::config::DeviceType::from_name)
        .is_some()
}

/// Parse a config.json and return the explicitly declared `usb_drive_name` if set,
/// or `None` if the config is not a valid MIDI Captain config or has no custom name.
///
/// Returns `None` if:
/// - the file doesn't exist, isn't valid JSON, or isn't a MIDI Captain config
/// - the config is valid but has no `usb_drive_name` (no custom name declared)
pub fn parse_midi_captain_config(config_path: &std::path::Path) -> Option<String> {
    if !config_path.exists() {
        return None;
    }
    let contents = std::fs::read_to_string(config_path).ok()?;
    let value: serde_json::Value = serde_json::from_str(&contents).ok()?;
    let device = value.get("device").and_then(|v| v.as_str())?;
    crate::config::DeviceType::from_name(device)?;
    // Return usb_drive_name only if explicitly set — no default fallback
    value
        .get("usb_drive_name")
        .and_then(|v| v.as_str())
        .map(|s| s.to_string())
}

/// Get the volumes directory for the current platform
fn get_volumes_path() -> PathBuf {
    #[cfg(target_os = "macos")]
    {
        PathBuf::from("/Volumes")
    }
    #[cfg(target_os = "linux")]
    {
        // On Linux, removable media is typically in /media/$USER or /run/media/$USER
        if let Some(user) = std::env::var_os("USER") {
            let media_path = PathBuf::from("/media").join(&user);
            if media_path.exists() {
                return media_path;
            }
            let run_media_path = PathBuf::from("/run/media").join(&user);
            if run_media_path.exists() {
                return run_media_path;
            }
        }
        // Fallback to /media
        PathBuf::from("/media")
    }
    #[cfg(target_os = "windows")]
    {
        // On Windows, we'll scan drive letters instead
        PathBuf::from("")
    }
}

/// Scan for devices on Windows by checking all drive letters
#[cfg(target_os = "windows")]
fn scan_windows_drives() -> Vec<DetectedDevice> {
    let mut devices = Vec::new();
    
    // Check drive letters A-Z
    for letter in b'A'..=b'Z' {
        let drive = format!("{}:\\", letter as char);
        let path = PathBuf::from(&drive);
        
        if path.exists() {
            // Get volume label
            if let Some(device) = check_volume(&path) {
                devices.push(device);
            }
        }
    }
    
    devices
}

/// Detected device info
#[derive(Debug, Clone, serde::Serialize)]
pub struct DetectedDevice {
    pub name: String,
    pub path: PathBuf,
    pub config_path: PathBuf,
    pub has_config: bool,
}

/// Get the volume name for a given path
#[cfg(target_os = "windows")]
fn get_volume_name(path: &PathBuf) -> Option<String> {
    use std::os::windows::ffi::OsStrExt;
    use std::ffi::OsString;
    use std::os::windows::ffi::OsStringExt;
    
    let path_str = path.to_str()?;
    let mut volume_name: Vec<u16> = vec![0; 261]; // MAX_PATH + 1
    
    unsafe {
        let root: Vec<u16> = OsString::from(path_str)
            .encode_wide()
            .chain(Some(0))
            .collect();
        
        let result = winapi::um::fileapi::GetVolumeInformationW(
            root.as_ptr(),
            volume_name.as_mut_ptr(),
            volume_name.len() as winapi::shared::minwindef::DWORD,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            0,
        );
        
        if result != 0 {
            // Find null terminator
            let len = volume_name.iter().position(|&c| c == 0).unwrap_or(volume_name.len());
            let name = OsString::from_wide(&volume_name[..len]);
            return name.into_string().ok();
        }
    }
    
    None
}

#[cfg(not(target_os = "windows"))]
fn get_volume_name(path: &PathBuf) -> Option<String> {
    path.file_name()?.to_str().map(|s| s.to_string())
}

/// Check if a volume is a MIDI Captain device.
///
/// Accepts:
/// 1. Volumes with a known name (CIRCUITPY, MIDICAPTAIN), or
/// 2. Volumes whose config.json identifies as a MIDI Captain device
///    (has a known `"device"` value: `"std10"`, `"mini6"`, `"nano4"`, `"duo2"`, or `"one1"`).
///    This covers user-renamed drives (e.g. renamed in Finder) where the
///    volume name no longer matches the default "MIDICAPTAIN".
fn check_volume(path: &PathBuf) -> Option<DetectedDevice> {
    let name = get_volume_name(path)?;
    let config_path = path.join("config.json");
    let has_config = config_path.exists();

    let is_known_name = DEVICE_VOLUMES.iter().any(|v| name.eq_ignore_ascii_case(v));

    if is_known_name || is_midi_captain_config(&config_path) {
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
    #[cfg(target_os = "windows")]
    {
        scan_windows_drives()
    }
    
    #[cfg(not(target_os = "windows"))]
    {
        let volumes_path = get_volumes_path();
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
}

// Global flag to prevent multiple watchers
static WATCHER_STARTED: AtomicBool = AtomicBool::new(false);

// Global shutdown signal sender (allows stopping the watcher thread)
static SHUTDOWN_TX: Mutex<Option<Sender<()>>> = Mutex::new(None);

/// Start watching for device connections
/// Emits "device-connected" and "device-disconnected" events
/// Note: Only one watcher can run at a time to prevent thread leaks
#[command]
pub fn start_device_watcher(app: AppHandle) -> Result<(), String> {
    // Prevent multiple watchers
    if WATCHER_STARTED.swap(true, Ordering::SeqCst) {
        return Ok(()); // Already running
    }
    
    #[cfg(target_os = "windows")]
    {
        start_windows_watcher(app)
    }
    
    #[cfg(not(target_os = "windows"))]
    {
        start_unix_watcher(app)
    }
}

/// Windows-specific watcher using polling
#[cfg(target_os = "windows")]
fn start_windows_watcher(app: AppHandle) -> Result<(), String> {
    let (shutdown_tx, shutdown_rx): (Sender<()>, Receiver<()>) = mpsc::channel();
    
    // Store shutdown sender for later use
    if let Ok(mut guard) = SHUTDOWN_TX.lock() {
        *guard = Some(shutdown_tx);
    }
    
    // Spawn polling thread
    std::thread::spawn(move || {
        let mut known_devices: HashSet<String> = HashSet::new();
        
        // Initial scan
        for device in scan_windows_drives() {
            known_devices.insert(device.name.clone());
        }
        
        loop {
            // Check for shutdown signal
            if shutdown_rx.try_recv().is_ok() {
                break;
            }
            
            // Scan for devices
            let current_devices = scan_windows_drives();
            let current_names: HashSet<String> = 
                current_devices.iter().map(|d| d.name.clone()).collect();
            
            // Check for newly connected devices
            for device in current_devices {
                if !known_devices.contains(&device.name) {
                    let name = device.name.clone();
                    let _ = app.emit("device-connected", device);
                    known_devices.insert(name);
                }
            }
            
            // Check for disconnected devices
            let disconnected: Vec<String> = known_devices
                .difference(&current_names)
                .cloned()
                .collect();
            
            for name in disconnected {
                let _ = app.emit("device-disconnected", name.clone());
                known_devices.remove(&name);
            }
            
            // Poll every 2 seconds
            std::thread::sleep(Duration::from_secs(2));
        }
        
        // Reset flag so watcher can be restarted if needed
        WATCHER_STARTED.store(false, Ordering::SeqCst);
    });
    
    Ok(())
}

/// Unix-specific watcher using filesystem events
#[cfg(not(target_os = "windows"))]
fn start_unix_watcher(app: AppHandle) -> Result<(), String> {
    let (tx, rx) = mpsc::channel();
    let (shutdown_tx, shutdown_rx): (Sender<()>, Receiver<()>) = mpsc::channel();
    
    // Store shutdown sender for later use
    if let Ok(mut guard) = SHUTDOWN_TX.lock() {
        *guard = Some(shutdown_tx);
    }
    
    let mut watcher = RecommendedWatcher::new(
        move |res: Result<Event, notify::Error>| {
            if let Ok(event) = res {
                let _ = tx.send(event);
            }
        },
        // Configure for lower latency on macOS FSEvents
        Config::default().with_poll_interval(Duration::from_millis(500)),
    ).map_err(|e| e.to_string())?;
    
    let volumes_path = get_volumes_path();
    watcher.watch(
        &volumes_path,
        RecursiveMode::NonRecursive,
    ).map_err(|e| e.to_string())?;
    
    // Spawn thread to handle events
    std::thread::spawn(move || {
        // Keep watcher alive
        let _watcher = watcher;
        
        // Track which paths we have emitted "device-connected" for,
        // so we can emit the matching "device-disconnected" even when
        // the volume has a custom name not in DEVICE_VOLUMES.
        let mut known_midi_captain_paths = std::collections::HashSet::new();
        
        loop {
            // Check for shutdown signal (non-blocking)
            if shutdown_rx.try_recv().is_ok() {
                break;
            }
            
            // Check for filesystem events (with timeout to allow shutdown checks)
            match rx.recv_timeout(std::time::Duration::from_millis(100)) {
                Ok(event) => {
                    match event.kind {
                        EventKind::Create(_) => {
                            // Volume mounted - check if it's a device
                            for path in &event.paths {
                                if let Some(device) = check_volume(path) {
                                    known_midi_captain_paths.insert(path.clone());
                                    let _ = app.emit("device-connected", device);
                                }
                            }
                        }
                        EventKind::Remove(_) => {
                            // Volume unmounted - emit disconnect if we previously detected it
                            for path in &event.paths {
                                if known_midi_captain_paths.remove(path) {
                                    let name_str = path
                                        .file_name()
                                        .map(|n| n.to_string_lossy().to_string())
                                        .unwrap_or_default();
                                    let _ = app.emit("device-disconnected", name_str);
                                }
                            }
                        }
                        _ => {}
                    }
                }
                Err(mpsc::RecvTimeoutError::Timeout) => {
                    // No event, continue loop (allows shutdown check)
                }
                Err(mpsc::RecvTimeoutError::Disconnected) => {
                    // Channel closed, exit thread
                    break;
                }
            }
        }
        
        // Reset flag so watcher can be restarted if needed
        WATCHER_STARTED.store(false, Ordering::SeqCst);
    });
    
    Ok(())
}

/// Stop the device watcher thread (called on app shutdown)
#[command]
pub fn stop_device_watcher() -> Result<(), String> {
    if let Ok(mut guard) = SHUTDOWN_TX.lock() {
        if let Some(tx) = guard.take() {
            let _ = tx.send(());
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_circuitpy() {
        // Test that CIRCUITPY volume name is recognized
        let path = PathBuf::from("/Volumes/CIRCUITPY");
        let result = check_volume(&path);
        // Should return Some because the name matches, has_config will be false
        assert!(result.is_some());
        let device = result.unwrap();
        assert_eq!(device.name, "CIRCUITPY");
        assert!(!device.has_config); // No actual config file exists in test
    }
    
    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_midicaptain() {
        // Test that MIDICAPTAIN volume name is recognized
        let path = PathBuf::from("/Volumes/MIDICAPTAIN");
        let result = check_volume(&path);
        assert!(result.is_some());
        let device = result.unwrap();
        assert_eq!(device.name, "MIDICAPTAIN");
        assert!(!device.has_config);
    }
    
    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_case_insensitive() {
        // Test case insensitivity
        let path = PathBuf::from("/Volumes/circuitpy");
        let result = check_volume(&path);
        assert!(result.is_some());
        let device = result.unwrap();
        assert_eq!(device.name, "circuitpy"); // Preserves original case
    }
    
    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_invalid() {
        let path = PathBuf::from("/Volumes/SomeOtherDrive");
        let result = check_volume(&path);
        assert!(result.is_none());
    }
    
    #[test]
    fn test_device_volumes_list() {
        // Verify the expected device names are in the list
        assert!(DEVICE_VOLUMES.contains(&"CIRCUITPY"));
        assert!(DEVICE_VOLUMES.contains(&"MIDICAPTAIN"));
        assert!(!DEVICE_VOLUMES.contains(&"Macintosh HD"));
    }

    #[test]
    fn test_is_midi_captain_config_std10() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "std10", "buttons": []}"#).unwrap();
        assert!(is_midi_captain_config(&path));
    }

    #[test]
    fn test_is_midi_captain_config_mini6() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "mini6", "buttons": []}"#).unwrap();
        assert!(is_midi_captain_config(&path));
    }

    #[test]
    fn test_is_midi_captain_config_duo2() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "duo2", "buttons": []}"#).unwrap();
        assert!(is_midi_captain_config(&path));
    }

    #[test]
    fn test_is_midi_captain_config_one1() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "one1", "buttons": []}"#).unwrap();
        assert!(is_midi_captain_config(&path));
    }

    #[test]
    fn test_is_midi_captain_config_unknown_device() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "unknown", "buttons": []}"#).unwrap();
        assert!(!is_midi_captain_config(&path));
    }

    #[test]
    fn test_is_midi_captain_config_no_device_field() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"buttons": []}"#).unwrap();
        // No "device" field → not recognised as MIDI Captain
        assert!(!is_midi_captain_config(&path));
    }

    #[test]
    fn test_is_midi_captain_config_missing_file() {
        let path = std::path::Path::new("/nonexistent/config.json");
        assert!(!is_midi_captain_config(path));
    }

    #[test]
    fn test_is_midi_captain_config_invalid_json() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, "not json at all").unwrap();
        assert!(!is_midi_captain_config(&path));
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_custom_name_with_matching_config() {
        // A volume whose basename matches the config's usb_drive_name should be detected.
        // We create a tempdir with a known suffix so the basename is predictable.
        let dir = tempfile::tempdir().unwrap();
        // Determine the actual volume name (tempdir basename)
        let vol_name = dir.path().file_name().unwrap().to_string_lossy().to_string();
        let config_path = dir.path().join("config.json");
        // Set usb_drive_name to match the volume basename
        std::fs::write(
            &config_path,
            format!(r#"{{"device": "std10", "usb_drive_name": "{}", "buttons": []}}"#, vol_name),
        )
        .unwrap();

        let result = check_volume(&dir.path().to_path_buf());
        assert!(result.is_some(), "Custom-named volume should be detected when config name matches");
        let device = result.unwrap();
        assert!(device.has_config);
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_custom_name_accepted_with_valid_config() {
        // A valid MIDI Captain config.json on a volume whose name does NOT match
        // the config's usb_drive_name should still be accepted — this covers
        // drives renamed in Finder where config.json still has the old name.
        let dir = tempfile::tempdir().unwrap();
        let config_path = dir.path().join("config.json");
        std::fs::write(
            &config_path,
            r#"{"device": "std10", "usb_drive_name": "TOTALLY_DIFFERENT", "buttons": []}"#,
        )
        .unwrap();

        let result = check_volume(&dir.path().to_path_buf());
        assert!(result.is_some(), "Volume with valid MIDI Captain config should be accepted regardless of name");
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_custom_name_without_config() {
        // A volume with an unknown name AND no config.json should NOT be detected
        let dir = tempfile::TempDir::with_prefix("RANDOMDRIVE").unwrap();
        // No config.json written
        let result = check_volume(&dir.path().to_path_buf());
        assert!(result.is_none(), "Unknown volume with no config should not be detected");
    }

    #[test]
    fn test_parse_midi_captain_config_returns_drive_name() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "std10", "usb_drive_name": "MYRIG", "buttons": []}"#).unwrap();
        assert_eq!(parse_midi_captain_config(&path).as_deref(), Some("MYRIG"));
    }

    #[test]
    fn test_parse_midi_captain_config_returns_none_when_no_custom_name() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "mini6", "buttons": []}"#).unwrap();
        assert_eq!(parse_midi_captain_config(&path), None);
    }

    #[test]
    fn test_parse_midi_captain_config_returns_none_for_non_device() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("config.json");
        std::fs::write(&path, r#"{"device": "unknown"}"#).unwrap();
        assert!(parse_midi_captain_config(&path).is_none());
    }
}
