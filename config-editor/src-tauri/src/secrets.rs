//! The Assistant's API key (#230) in the OS credential store: macOS Keychain,
//! Windows Credential Manager, Secret Service on Linux. The webview holds the
//! key only in memory; it is never written to localStorage or a file.

use crate::commands::ConfigError;
use keyring::{Entry, Error};
use tauri::command;

const SERVICE: &str = "com.mcmusicworkshop.midicaptain.configeditor";
const ACCOUNT: &str = "anthropic-api-key";

fn entry() -> Result<Entry, ConfigError> {
    Entry::new(SERVICE, ACCOUNT).map_err(store_error)
}

fn store_error(e: Error) -> ConfigError {
    ConfigError::msg(format!("Could not use the system keychain: {e}"))
}

/// The stored key, or `None` when there isn't one.
#[command]
pub fn agent_key_get() -> Result<Option<String>, ConfigError> {
    match entry()?.get_password() {
        Ok(key) => Ok(Some(key)),
        Err(Error::NoEntry) => Ok(None),
        Err(e) => Err(store_error(e)),
    }
}

#[command]
pub fn agent_key_set(key: String) -> Result<(), ConfigError> {
    entry()?.set_password(&key).map_err(store_error)
}

/// Remove the stored key. Not having one is not an error.
#[command]
pub fn agent_key_delete() -> Result<(), ConfigError> {
    match entry()?.delete_credential() {
        Ok(()) | Err(Error::NoEntry) => Ok(()),
        Err(e) => Err(store_error(e)),
    }
}
