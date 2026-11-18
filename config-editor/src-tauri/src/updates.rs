//! In-app updates (#18): the editor downloads and installs a new release of
//! itself, then restarts.
//!
//! The feeds are written by `.github/workflows/homebrew.yml` from the same
//! release, and under the same rules, as the Homebrew casks: `stable.json`
//! follows stable releases, `beta.json` betas, rcs and stables, `alpha.json`
//! every release. A build follows the feed of the channel it was released on.

use semver::Version;
use serde::Serialize;
use tauri::{command, ipc::Channel, AppHandle};
use tauri_plugin_updater::{Update, UpdaterExt};

use crate::commands::ConfigError;

const STABLE_FEED: &str =
    "https://raw.githubusercontent.com/MC-Music-Workshop/midi-captain-max/updater/stable.json";
const BETA_FEED: &str =
    "https://raw.githubusercontent.com/MC-Music-Workshop/midi-captain-max/updater/beta.json";
const ALPHA_FEED: &str =
    "https://raw.githubusercontent.com/MC-Music-Workshop/midi-captain-max/updater/alpha.json";

/// The version this build was released as. CI passes it in `MCM_VERSION`
/// because a Windows build's own version is WiX-safe (`1.15.0-beta.3` becomes
/// `1.15.0-3`), which sorts below `1.15.0-beta.3` and would offer the same
/// update forever.
fn release_version(package_version: &Version) -> Version {
    option_env!("MCM_VERSION")
        .and_then(|v| Version::parse(v).ok())
        .unwrap_or_else(|| package_version.clone())
}

/// Alphas follow the alpha feed, other prereleases (beta, rc) the beta feed,
/// stable releases the stable feed.
fn feed_url(version: &Version) -> &'static str {
    if version.pre.is_empty() {
        STABLE_FEED
    } else if version.pre.as_str().starts_with("alpha") {
        ALPHA_FEED
    } else {
        BETA_FEED
    }
}

fn updater_error(e: impl std::fmt::Display) -> ConfigError {
    ConfigError::msg(e.to_string())
}

async fn find_update(app: &AppHandle) -> Result<Option<Update>, ConfigError> {
    if cfg!(debug_assertions) {
        return Err(ConfigError::msg(
            "Updates are turned off in development builds.",
        ));
    }
    let current = release_version(&app.package_info().version);
    let feed = feed_url(&current).parse().map_err(updater_error)?;
    app.updater_builder()
        .endpoints(vec![feed])
        .map_err(updater_error)?
        // Compare against the release version, not the (possibly WiX-mangled)
        // package version the plugin passes in.
        .version_comparator(move |_, remote| remote.version > current)
        .build()
        .map_err(updater_error)?
        .check()
        .await
        .map_err(updater_error)
}

#[derive(Debug, Serialize)]
pub struct UpdateInfo {
    /// Version running now.
    pub current: String,
    /// Version on offer.
    pub version: String,
}

/// Tauri command: is a newer release available on this build's channel?
#[command]
pub async fn check_for_update(app: AppHandle) -> Result<Option<UpdateInfo>, ConfigError> {
    let update = find_update(&app).await?;
    Ok(update.map(|u| UpdateInfo {
        current: release_version(&app.package_info().version).to_string(),
        version: u.version,
    }))
}

#[derive(Clone, Serialize)]
#[serde(tag = "phase", rename_all = "camelCase")]
pub enum UpdateProgress {
    Downloading { downloaded: u64, total: Option<u64> },
    Installing,
}

/// Tauri command: download, verify (against the public key in
/// `tauri.conf.json`), install, and restart into the new version.
#[command]
pub async fn install_update(
    app: AppHandle,
    on_progress: Channel<UpdateProgress>,
) -> Result<(), ConfigError> {
    let update = find_update(&app)
        .await?
        .ok_or_else(|| ConfigError::msg("No update is available."))?;
    let mut downloaded = 0u64;
    update
        .download_and_install(
            |chunk, total| {
                downloaded += chunk as u64;
                let _ = on_progress.send(UpdateProgress::Downloading { downloaded, total });
            },
            || {
                let _ = on_progress.send(UpdateProgress::Installing);
            },
        )
        .await
        .map_err(updater_error)?;
    #[cfg(target_os = "macos")]
    if relaunch_via_launch_services() {
        app.exit(0);
        return Ok(());
    }
    app.restart();
}

/// The `.app` bundle holding `exe` (`X.app/Contents/MacOS/<binary>`), if any.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
fn app_bundle(exe: &std::path::Path) -> Option<std::path::PathBuf> {
    exe.ancestors()
        .nth(3)
        .filter(|p| p.extension().is_some_and(|ext| ext == "app"))
        .map(std::path::Path::to_path_buf)
}

/// Open the updated app through Launch Services (`open -n`), as a click in
/// Finder would. `AppHandle::restart` spawns the new binary as a child of this
/// process instead; once this one exits, macOS shows "… is running in the
/// background" for the orphaned copy. False when not running from a bundle.
#[cfg(target_os = "macos")]
fn relaunch_via_launch_services() -> bool {
    let Some(bundle) = std::env::current_exe().ok().and_then(|exe| app_bundle(&exe)) else {
        return false;
    };
    // -n: start a new instance even though this (old) one is still running.
    std::process::Command::new("/usr/bin/open")
        .arg("-n")
        .arg(bundle)
        .spawn()
        .is_ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn v(s: &str) -> Version {
        Version::parse(s).unwrap()
    }

    #[test]
    fn stable_builds_follow_the_stable_feed() {
        assert_eq!(feed_url(&v("1.15.0")), STABLE_FEED);
    }

    #[test]
    fn prerelease_builds_follow_the_beta_feed() {
        assert_eq!(feed_url(&v("1.15.0-beta.3")), BETA_FEED);
        assert_eq!(feed_url(&v("1.15.0-rc.1")), BETA_FEED);
    }

    #[test]
    fn app_bundle_is_found_from_the_binary_path() {
        let exe = std::path::Path::new("/Applications/MIDI Captain MAX Config Editor.app/Contents/MacOS/config-editor");
        assert_eq!(
            app_bundle(exe).as_deref(),
            Some(std::path::Path::new("/Applications/MIDI Captain MAX Config Editor.app"))
        );
    }

    #[test]
    fn no_app_bundle_outside_one() {
        // `cargo run` / `tauri dev` binaries live in target/, not a bundle.
        assert_eq!(app_bundle(std::path::Path::new("/repo/target/debug/config-editor")), None);
    }

    #[test]
    fn alpha_builds_follow_the_alpha_feed() {
        assert_eq!(feed_url(&v("1.16.0-alpha.1")), ALPHA_FEED);
    }

    #[test]
    fn release_version_falls_back_to_the_package_version() {
        // MCM_VERSION is unset for `cargo test`.
        if option_env!("MCM_VERSION").is_none() {
            assert_eq!(release_version(&v("1.2.3")), v("1.2.3"));
        }
    }

    #[test]
    fn wix_safe_version_would_sort_below_its_own_release() {
        // Why release_version exists: comparing the Windows package version
        // against the feed would always see an update.
        assert!(v("1.15.0-beta.3") > v("1.15.0-3"));
    }
}
