//! "Reflash CircuitPython 7.3.1" feature (issue #134).
//!
//! Recovery flow for devices on a CircuitPython newer than this firmware
//! supports (see issue #132 preflight), and — via 1200-baud-touch bootloader
//! entry (see `commands`) — the migration path off PaintAudio's OEM FW5+ C
//! firmware (issue #186; no flash erase needed — CircuitPython auto-formats
//! an invalid filesystem region on first boot, bench-verified). Note that
//! Switch 1 / KEY0 does NOT enter the bootloader; it only exposes a running
//! CP firmware's USB drive. Once `RPI-RP2` mounts, this module
//! copies the bundled `.uf2` onto it. The bootloader handles the flash + reboot
//! into the freshly written firmware on its own — we just wait for `CIRCUITPY`
//! to remount and tell the UI.

use crate::commands::ConfigError;
use crate::device::{get_volume_name, get_volumes_path};
use serde::Serialize;
use std::fs::{File, OpenOptions};
use std::path::{Path, PathBuf};
use tauri::ipc::Channel;
use tauri::{command, AppHandle, Manager};

/// FAT label the RP2040 ROM bootloader presents when BOOTSEL is held during
/// USB enumeration. Case-insensitive match — Windows sometimes uppercases,
/// macOS preserves as-mastered.
const RPI_RP2_LABEL: &str = "RPI-RP2";

/// Filename of the .uf2 we ship in `resources/circuitpython/`. Kept identical
/// to Adafruit's canonical filename so users who go looking at the bootloader
/// drive see something recognisable.
pub(crate) const BUNDLED_UF2_FILENAME: &str =
    "adafruit-circuitpython-raspberry_pi_pico-en_US-7.3.1.uf2";

#[derive(Debug, Clone, Copy, Serialize, PartialEq, Eq)]
#[serde(rename_all = "camelCase")]
pub enum ReflashPhase {
    Copying,
    AwaitingReboot,
    Done,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct ReflashProgress {
    pub phase: ReflashPhase,
    pub message: String,
}

/// Scan platform-appropriate volume roots for an `RPI-RP2` bootloader mount.
/// Returns the mount path if present, `None` otherwise.
///
/// Mirrors the volume-scanning strategy in `device::scan_devices`: drive-letter
/// walk on Windows, directory listing under `/Volumes` (macOS) or
/// `/media/$USER` / `/run/media/$USER` (Linux) elsewhere.
pub fn detect_rpi_rp2() -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        for letter in b'A'..=b'Z' {
            let drive = format!("{}:\\", letter as char);
            let path = PathBuf::from(&drive);
            if path.exists() {
                if let Some(name) = get_volume_name(&path) {
                    if name.eq_ignore_ascii_case(RPI_RP2_LABEL) {
                        return Some(path);
                    }
                }
            }
        }
        None
    }
    #[cfg(not(target_os = "windows"))]
    {
        let volumes_path = get_volumes_path();
        let entries = std::fs::read_dir(&volumes_path).ok()?;
        for entry in entries.flatten() {
            let path = entry.path();
            if let Some(name) = get_volume_name(&path) {
                if name.eq_ignore_ascii_case(RPI_RP2_LABEL) {
                    return Some(path);
                }
            }
        }
        None
    }
}

fn bundled_uf2_path(app: &AppHandle) -> Result<PathBuf, ConfigError> {
    let resource_dir = app
        .path()
        .resource_dir()
        .map_err(|e| ConfigError::msg(format!("Could not resolve app resource directory: {e}")))?;
    let uf2 = resource_dir
        .join("resources")
        .join("circuitpython")
        .join(BUNDLED_UF2_FILENAME);
    if !uf2.exists() {
        return Err(ConfigError::msg(format!(
            "Bundled CircuitPython .uf2 missing at {}. \
             This is a build-configuration issue: tools/fetch-cp-uf2.sh must run \
             before `tauri build` so the .uf2 lands in resources/circuitpython/.",
            uf2.display()
        )));
    }
    Ok(uf2)
}

/// Copy the bundled `.uf2` onto the `RPI-RP2` bootloader drive.
///
/// Uses explicit `OpenOptions` + `io::copy` + `sync_all` rather than
/// `std::fs::copy`. The bare `fs::copy` closes the destination via `Drop`,
/// which on macOS USB MSC volumes does not force a kernel buffer flush —
/// bytes can sit in the page cache indefinitely. The RP2040 bootloader
/// waits for the actual write, so without an explicit `sync_all` the UI
/// hangs in the "copying" state with the device never rebooting. This
/// mirrors `installer::copy_file_synced` for the same reason.
///
/// Tolerance for mid-write disconnect: the bootloader unmounts the drive
/// once it has enough bytes to commit. The OS surfaces that as either a
/// `WriteZero`/`BrokenPipe` on `io::copy` or a generic IO error on
/// `sync_all`. If the drive has vanished, treat as success — the
/// bootloader took over.
pub(crate) fn copy_uf2_to_bootloader(
    uf2_src: &Path,
    bootloader: &Path,
) -> Result<(), ConfigError> {
    let target = bootloader.join(BUNDLED_UF2_FILENAME);

    let mut reader = File::open(uf2_src).map_err(|e| {
        ConfigError::msg(format!("Failed to open bundled .uf2 at {}: {}", uf2_src.display(), e))
    })?;
    let mut writer = match OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(&target)
    {
        Ok(f) => f,
        Err(e) => return classify_post_copy_error(bootloader, "open", e),
    };

    if let Err(e) = std::io::copy(&mut reader, &mut writer) {
        return classify_post_copy_error(bootloader, "write", e);
    }

    if let Err(e) = writer.sync_all() {
        return classify_post_copy_error(bootloader, "sync", e);
    }

    // Explicitly drop the writer so the kernel finalises the file handle
    // before we return success. Belt-and-suspenders with sync_all above.
    drop(writer);
    Ok(())
}

/// Classify an IO error that happened at any step of the copy. If the
/// bootloader drive has unmounted itself (RP2040 took the bytes and is
/// flashing), treat as success regardless of which step erred. Otherwise
/// propagate with context about which step failed.
fn classify_post_copy_error(
    bootloader: &Path,
    step: &str,
    e: std::io::Error,
) -> Result<(), ConfigError> {
    if !bootloader.exists() {
        // Bootloader has unmounted itself — write accepted, reboot incoming.
        Ok(())
    } else {
        Err(ConfigError::msg(format!(
            "Failed to {} .uf2 onto {}: {}. \
             If the device disconnected mid-copy, try again.",
            step,
            bootloader.display(),
            e
        )))
    }
}

/// Tauri command: detect whether `RPI-RP2` is currently mounted.
/// UI polls this while the user does the BOOTSEL/Switch 1 hold + replug.
#[command]
pub fn rpi_rp2_mount_path() -> Option<String> {
    detect_rpi_rp2().map(|p| p.to_string_lossy().into_owned())
}

/// Tauri command: copy the bundled CircuitPython 7.3.1 `.uf2` onto a mounted
/// `RPI-RP2` bootloader. UI must have already prompted the user to enter
/// bootloader mode and observed `rpi_rp2_mount_path()` returning `Some`.
///
/// Returns once bytes are copied (or the bootloader has unmounted itself,
/// which counts as success). UI then polls `scan_devices` for `CIRCUITPY`
/// to remount, which signals the new firmware has booted.
#[command]
pub async fn reflash_circuitpython(
    app: AppHandle,
    on_progress: Channel<ReflashProgress>,
) -> Result<(), ConfigError> {
    let uf2 = bundled_uf2_path(&app)?;

    tauri::async_runtime::spawn_blocking(move || {
        let bootloader = detect_rpi_rp2().ok_or_else(|| {
            ConfigError::msg(
                "RPI-RP2 bootloader drive not found. Use the editor's automatic \
                 bootloader entry or see docs/recovery-bootloader-entry.md. \
                 (Holding Switch 1 / KEY0 does NOT enter the bootloader — it only \
                 exposes a running CircuitPython firmware's USB drive.)",
            )
        })?;

        let _ = on_progress.send(ReflashProgress {
            phase: ReflashPhase::Copying,
            message: format!(
                "Copying CircuitPython 7.3.1 onto {}",
                bootloader.display()
            ),
        });

        copy_uf2_to_bootloader(&uf2, &bootloader)?;

        let _ = on_progress.send(ReflashProgress {
            phase: ReflashPhase::AwaitingReboot,
            message:
                "Bootloader is flashing the .uf2 and will reboot the device shortly."
                    .to_string(),
        });

        let _ = on_progress.send(ReflashProgress {
            phase: ReflashPhase::Done,
            message:
                "CircuitPython 7.3.1 written. Wait for CIRCUITPY to remount, then click Install Firmware."
                    .to_string(),
        });

        Ok(())
    })
    .await
    .map_err(|e| ConfigError::msg(format!("Reflash task panicked: {e}")))?
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use tempfile::TempDir;

    fn make_fake_uf2(dir: &Path) -> PathBuf {
        let p = dir.join("fake.uf2");
        // 1 KB of dummy bytes — enough to exercise the copy.
        fs::write(&p, vec![0xAB; 1024]).unwrap();
        p
    }

    #[test]
    fn copy_uf2_happy_path_writes_file_with_canonical_name() {
        let bundle = TempDir::new().unwrap();
        let bootloader = TempDir::new().unwrap();
        let src = make_fake_uf2(bundle.path());

        copy_uf2_to_bootloader(&src, bootloader.path()).unwrap();

        let dest = bootloader.path().join(BUNDLED_UF2_FILENAME);
        assert!(dest.exists(), "destination .uf2 must exist after copy");
        let bytes = fs::read(&dest).unwrap();
        assert_eq!(bytes.len(), 1024);
        assert!(bytes.iter().all(|&b| b == 0xAB));
    }

    #[test]
    fn copy_uf2_bootloader_vanished_mid_copy_treated_as_success() {
        // Simulate: the bootloader drive disappears between fs::copy starting and
        // finishing. Easiest deterministic model: point bootloader at a path that
        // doesn't exist by the time we check. fs::copy itself will fail because the
        // dest dir is missing; the leniency branch then sees `!bootloader.exists()`
        // and treats it as success.
        let bundle = TempDir::new().unwrap();
        let src = make_fake_uf2(bundle.path());

        let phantom_bootloader = PathBuf::from("/tmp/this-mount-point-does-not-exist-9e8a7f");
        // Make sure it really doesn't exist.
        let _ = fs::remove_dir_all(&phantom_bootloader);

        // fs::copy fails (no such dir), but the leniency branch should swallow it.
        let result = copy_uf2_to_bootloader(&src, &phantom_bootloader);
        assert!(
            result.is_ok(),
            "vanished bootloader should be treated as success, got: {:?}",
            result
        );
    }

    #[test]
    fn copy_uf2_real_failure_with_present_bootloader_propagates() {
        // Bootloader dir exists, but the destination path is a directory — copy
        // fails. Should NOT be swallowed.
        let bundle = TempDir::new().unwrap();
        let bootloader = TempDir::new().unwrap();
        let src = make_fake_uf2(bundle.path());

        // Pre-create a *directory* at the target filename so fs::copy errors.
        let blocker = bootloader.path().join(BUNDLED_UF2_FILENAME);
        fs::create_dir(&blocker).unwrap();

        let result = copy_uf2_to_bootloader(&src, bootloader.path());
        assert!(
            result.is_err(),
            "copy onto present-but-blocked bootloader must error"
        );
    }

    #[test]
    fn bundled_uf2_filename_matches_adafruit_canonical() {
        // Sanity guard: if someone bumps the pinned CP version, they need to
        // also update this constant — and the test name forces the diff to
        // mention the right thing.
        assert!(BUNDLED_UF2_FILENAME.contains("7.3.1"));
        assert!(BUNDLED_UF2_FILENAME.contains("raspberry_pi_pico"));
        assert!(BUNDLED_UF2_FILENAME.ends_with(".uf2"));
    }
}
