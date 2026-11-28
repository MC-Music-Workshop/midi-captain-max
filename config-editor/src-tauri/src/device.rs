//! Device detection via volume mounting

use std::collections::{HashMap, HashSet};
use std::path::{Path, PathBuf};
use std::sync::mpsc::{self, Receiver, RecvTimeoutError, Sender};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{command, AppHandle, Emitter};

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

/// Get the volumes directory for the current platform
pub(crate) fn get_volumes_path() -> PathBuf {
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

/// Every mounted volume root right now, with its volume name: drive letters
/// on Windows, the entries of `get_volumes_path()` elsewhere.
fn list_mounts() -> Vec<(PathBuf, String)> {
    #[cfg(target_os = "windows")]
    let roots: Vec<PathBuf> = (b'A'..=b'Z')
        .map(|letter| PathBuf::from(format!("{}:\\", letter as char)))
        .filter(|p| p.exists())
        .collect();

    #[cfg(not(target_os = "windows"))]
    let roots: Vec<PathBuf> = std::fs::read_dir(get_volumes_path())
        .map(|entries| entries.flatten().map(|e| e.path()).collect())
        .unwrap_or_default();

    roots
        .into_iter()
        .filter_map(|p| get_volume_name(&p).map(|name| (p, name)))
        .collect()
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
pub(crate) fn get_volume_name(path: &Path) -> Option<String> {
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
pub(crate) fn get_volume_name(path: &Path) -> Option<String> {
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
fn check_volume(path: &Path) -> Option<DetectedDevice> {
    let name = get_volume_name(path)?;
    let config_path = path.join("config.json");
    let has_config = config_path.exists();

    let is_known_name = DEVICE_VOLUMES.iter().any(|v| name.eq_ignore_ascii_case(v));

    if is_known_name || is_midi_captain_config(&config_path) {
        Some(DetectedDevice {
            name: name.to_string(),
            path: path.to_path_buf(),
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
    list_mounts()
        .into_iter()
        .filter_map(|(path, _)| check_volume(&path))
        .collect()
}

/// How often the watcher rescans the mounted volumes.
const POLL_INTERVAL: Duration = Duration::from_secs(2);

/// How many polls a newly mounted, unrecognized volume is re-checked before
/// it's ignored until it unmounts. A custom-named device is only recognized
/// by reading its config.json, which often isn't readable for the first
/// second or two after the mount, so one check at mount time missed it.
const MATCH_RETRIES: u32 = 5;

/// What the watcher tells the frontend.
#[derive(Debug, Clone)]
pub(crate) enum DeviceEvent {
    Connected(DetectedDevice),
    /// The volume root that went away.
    Disconnected(PathBuf),
}

/// Diffs successive volume listings into connect/disconnect events.
///
/// A volume is identified by its root path *and* its name, so a drive that
/// comes back at the same path under a new name (a Windows drive letter
/// after a rename) reads as disconnect + connect, same as on macOS where the
/// path itself changes.
#[derive(Default)]
pub(crate) struct MountTracker {
    /// Volumes reported to the frontend as connected devices.
    known: HashSet<(PathBuf, String)>,
    /// New volumes not recognized yet, with how many checks they've had.
    pending: HashMap<(PathBuf, String), u32>,
    /// Volumes that ran out of retries; skipped until they unmount.
    ignored: HashSet<(PathBuf, String)>,
}

impl MountTracker {
    /// One poll. `mounts` is every volume mounted now; `check` says whether
    /// one is a device. Disconnects come before connects, so a device that
    /// changed name at the same path is removed before it's added back.
    pub(crate) fn poll<F>(&mut self, mounts: &[(PathBuf, String)], mut check: F) -> Vec<DeviceEvent>
    where
        F: FnMut(&Path) -> Option<DetectedDevice>,
    {
        let current: HashSet<&(PathBuf, String)> = mounts.iter().collect();
        let mut events = Vec::new();

        let mut gone: Vec<(PathBuf, String)> =
            self.known.iter().filter(|m| !current.contains(m)).cloned().collect();
        gone.sort();
        for mount in gone {
            self.known.remove(&mount);
            events.push(DeviceEvent::Disconnected(mount.0));
        }
        self.pending.retain(|m, _| current.contains(m));
        self.ignored.retain(|m| current.contains(m));

        for mount in mounts {
            if self.known.contains(mount) || self.ignored.contains(mount) {
                continue;
            }
            match check(&mount.0) {
                Some(device) => {
                    self.pending.remove(mount);
                    self.known.insert(mount.clone());
                    events.push(DeviceEvent::Connected(device));
                }
                None => {
                    let tries = self.pending.entry(mount.clone()).or_insert(0);
                    *tries += 1;
                    if *tries >= MATCH_RETRIES {
                        self.pending.remove(mount);
                        self.ignored.insert(mount.clone());
                    }
                }
            }
        }
        events
    }
}

// Global flag to prevent multiple watchers
static WATCHER_STARTED: AtomicBool = AtomicBool::new(false);

// Global shutdown signal sender (allows stopping the watcher thread)
static SHUTDOWN_TX: Mutex<Option<Sender<()>>> = Mutex::new(None);

/// Start watching for device connections.
///
/// Emits "device-connected" (a `DetectedDevice`) and "device-disconnected"
/// (the volume root path). Polls the mounted volumes every `POLL_INTERVAL`
/// on every platform. macOS/Linux used filesystem events on the volumes
/// folder before, which checked a new volume once, at mount time: a
/// custom-named drive whose config.json wasn't readable yet was never
/// detected until the app restarted.
///
/// Note: Only one watcher can run at a time to prevent thread leaks
#[command]
pub fn start_device_watcher(app: AppHandle) -> Result<(), String> {
    // Prevent multiple watchers
    if WATCHER_STARTED.swap(true, Ordering::SeqCst) {
        return Ok(()); // Already running
    }

    let (shutdown_tx, shutdown_rx): (Sender<()>, Receiver<()>) = mpsc::channel();
    if let Ok(mut guard) = SHUTDOWN_TX.lock() {
        *guard = Some(shutdown_tx);
    }

    std::thread::spawn(move || {
        let mut tracker = MountTracker::default();
        loop {
            for event in tracker.poll(&list_mounts(), check_volume) {
                let _ = match event {
                    DeviceEvent::Connected(device) => app.emit("device-connected", device),
                    DeviceEvent::Disconnected(path) => app.emit("device-disconnected", path),
                };
            }
            // Sleep until the next poll, waking early on shutdown.
            match shutdown_rx.recv_timeout(POLL_INTERVAL) {
                Err(RecvTimeoutError::Timeout) => continue,
                Ok(()) | Err(RecvTimeoutError::Disconnected) => break,
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

    /// An empty directory with an exact volume name, inside a tempdir — so
    /// these tests never touch /Volumes and can't be affected by whatever
    /// drives are actually mounted (a real MIDICAPTAIN used to flip
    /// has_config to true and fail the suite).
    #[cfg(not(target_os = "windows"))]
    fn fake_volume(dir: &tempfile::TempDir, name: &str) -> PathBuf {
        let vol = dir.path().join(name);
        std::fs::create_dir(&vol).unwrap();
        vol
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_circuitpy() {
        // Test that CIRCUITPY volume name is recognized
        let dir = tempfile::tempdir().unwrap();
        let result = check_volume(&fake_volume(&dir, "CIRCUITPY"));
        // Should return Some because the name matches, has_config will be false
        assert!(result.is_some());
        let device = result.unwrap();
        assert_eq!(device.name, "CIRCUITPY");
        assert!(!device.has_config); // No config file in the fake volume
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_midicaptain() {
        // Test that MIDICAPTAIN volume name is recognized
        let dir = tempfile::tempdir().unwrap();
        let result = check_volume(&fake_volume(&dir, "MIDICAPTAIN"));
        assert!(result.is_some());
        let device = result.unwrap();
        assert_eq!(device.name, "MIDICAPTAIN");
        assert!(!device.has_config);
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_case_insensitive() {
        // Test case insensitivity
        let dir = tempfile::tempdir().unwrap();
        let result = check_volume(&fake_volume(&dir, "circuitpy"));
        assert!(result.is_some());
        let device = result.unwrap();
        assert_eq!(device.name, "circuitpy"); // Preserves original case
    }
    
    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_invalid() {
        let dir = tempfile::tempdir().unwrap();
        let result = check_volume(&fake_volume(&dir, "SomeOtherDrive"));
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

        let result = check_volume(dir.path());
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

        let result = check_volume(dir.path());
        assert!(result.is_some(), "Volume with valid MIDI Captain config should be accepted regardless of name");
    }

    #[test]
    #[cfg(not(target_os = "windows"))]
    fn test_check_volume_custom_name_without_config() {
        // A volume with an unknown name AND no config.json should NOT be detected
        let dir = tempfile::TempDir::with_prefix("RANDOMDRIVE").unwrap();
        // No config.json written
        let result = check_volume(dir.path());
        assert!(result.is_none(), "Unknown volume with no config should not be detected");
    }

    // ── MountTracker ──────────────────────────────────────────────────────────

    fn mount(path: &str, name: &str) -> (PathBuf, String) {
        (PathBuf::from(path), name.to_string())
    }

    fn device_at(path: &Path) -> DetectedDevice {
        DetectedDevice {
            name: path.file_name().unwrap().to_string_lossy().to_string(),
            path: path.to_path_buf(),
            config_path: path.join("config.json"),
            has_config: true,
        }
    }

    /// A `check` that recognizes the listed paths as devices.
    fn devices_at<'a>(paths: &'a [&'a str]) -> impl FnMut(&Path) -> Option<DetectedDevice> + 'a {
        move |p: &Path| paths.iter().any(|d| Path::new(d) == p).then(|| device_at(p))
    }

    fn summary(events: &[DeviceEvent]) -> Vec<String> {
        events
            .iter()
            .map(|e| match e {
                DeviceEvent::Connected(d) => format!("+{}", d.path.display()),
                DeviceEvent::Disconnected(p) => format!("-{}", p.display()),
            })
            .collect()
    }

    #[test]
    fn test_tracker_connects_then_stays_quiet() {
        let mut t = MountTracker::default();
        let mounts = [mount("/Volumes/MIDICAPTAIN", "MIDICAPTAIN"), mount("/Volumes/Data", "Data")];
        let check = || devices_at(&["/Volumes/MIDICAPTAIN"]);
        assert_eq!(summary(&t.poll(&mounts, check())), ["+/Volumes/MIDICAPTAIN"]);
        assert!(t.poll(&mounts, check()).is_empty());
    }

    #[test]
    fn test_tracker_disconnect_carries_the_path() {
        let mut t = MountTracker::default();
        let check = || devices_at(&["/Volumes/MYRIG"]);
        t.poll(&[mount("/Volumes/MYRIG", "MYRIG")], check());
        assert_eq!(summary(&t.poll(&[], check())), ["-/Volumes/MYRIG"]);
        assert!(t.poll(&[], check()).is_empty());
    }

    #[test]
    fn test_tracker_rename_with_new_path_is_disconnect_then_connect() {
        // macOS/Linux: the mount point is named after the volume.
        let mut t = MountTracker::default();
        let check = || devices_at(&["/Volumes/MIDICAPTAIN", "/Volumes/STAGE_L"]);
        t.poll(&[mount("/Volumes/MIDICAPTAIN", "MIDICAPTAIN")], check());
        let events = t.poll(&[mount("/Volumes/STAGE_L", "STAGE_L")], check());
        assert_eq!(summary(&events), ["-/Volumes/MIDICAPTAIN", "+/Volumes/STAGE_L"]);
    }

    #[test]
    fn test_tracker_rename_at_same_path_is_disconnect_then_connect() {
        // Windows: the drive letter can come straight back with the new label.
        let mut t = MountTracker::default();
        let check = || devices_at(&["E:\\"]);
        t.poll(&[mount("E:\\", "MIDICAPTAIN")], check());
        let events = t.poll(&[mount("E:\\", "STAGE_L")], check());
        assert_eq!(summary(&events), ["-E:\\", "+E:\\"]);
    }

    #[test]
    fn test_tracker_late_config_is_caught_within_retry_window() {
        let mut t = MountTracker::default();
        let mounts = [mount("/Volumes/STAGE_L", "STAGE_L")];
        for _ in 0..MATCH_RETRIES - 1 {
            assert!(t.poll(&mounts, devices_at(&[])).is_empty());
        }
        // config.json became readable on the last allowed check.
        let events = t.poll(&mounts, devices_at(&["/Volumes/STAGE_L"]));
        assert_eq!(summary(&events), ["+/Volumes/STAGE_L"]);
    }

    #[test]
    fn test_tracker_ignores_unrecognized_volume_after_retries() {
        let mut t = MountTracker::default();
        let mounts = [mount("/Volumes/Backup", "Backup")];
        let mut checks = 0;
        for _ in 0..MATCH_RETRIES + 5 {
            t.poll(&mounts, |_| {
                checks += 1;
                None
            });
        }
        assert_eq!(checks, MATCH_RETRIES, "an ignored volume must not be re-read every poll");
    }

    #[test]
    fn test_tracker_rechecks_ignored_volume_after_it_remounts() {
        let mut t = MountTracker::default();
        let mounts = [mount("/Volumes/STAGE_L", "STAGE_L")];
        for _ in 0..MATCH_RETRIES {
            t.poll(&mounts, devices_at(&[]));
        }
        t.poll(&[], devices_at(&[])); // unplugged
        let events = t.poll(&mounts, devices_at(&["/Volumes/STAGE_L"]));
        assert_eq!(summary(&events), ["+/Volumes/STAGE_L"]);
    }
}
