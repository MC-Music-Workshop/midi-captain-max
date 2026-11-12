//! In-app updates (#18): the editor downloads and installs a new release of
//! itself, then restarts.
//!
//! The feeds are written by `.github/workflows/homebrew.yml` from the same
//! release, and under the same rules, as the Homebrew casks: `stable.json`
//! follows stable releases, `beta.json` follows betas, rcs and stables. A build
//! follows the feed of the channel it was released on.

use semver::Version;
use serde::Serialize;
use tauri::{command, ipc::Channel, AppHandle};
use tauri_plugin_updater::{Update, UpdaterExt};

use crate::commands::ConfigError;

const STABLE_FEED: &str =
    "https://raw.githubusercontent.com/MC-Music-Workshop/midi-captain-max/updater/stable.json";
const BETA_FEED: &str =
    "https://raw.githubusercontent.com/MC-Music-Workshop/midi-captain-max/updater/beta.json";

/// The version this build was released as. CI passes it in `MCM_VERSION`
/// because a Windows build's own version is WiX-safe (`1.15.0-beta.3` becomes
/// `1.15.0-3`), which sorts below `1.15.0-beta.3` and would offer the same
/// update forever.
fn release_version(package_version: &Version) -> Version {
    option_env!("MCM_VERSION")
        .and_then(|v| Version::parse(v).ok())
        .unwrap_or_else(|| package_version.clone())
}

/// Prereleases follow the beta feed, stable releases the stable feed.
fn feed_url(version: &Version) -> &'static str {
    if version.pre.is_empty() {
        STABLE_FEED
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
    app.restart();
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
