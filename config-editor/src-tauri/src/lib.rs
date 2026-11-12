pub mod agent;
mod commands;
mod config_files;
mod config;
mod device;
mod installer;
mod reflash;
mod secrets;
mod templates;
mod updates;

use agent::agent_tool;
use commands::{detect_oem_v5_port, eject_device, enter_bootloader, enter_bootloader_oem_v5, read_config, read_config_raw, restart_device, validate_config, write_config, write_config_raw};
use config_files::{configs_dir, default_config, device_config_type, open_config_file, save_config_file};
use device::{scan_devices, start_device_watcher, stop_device_watcher};
use installer::{get_firmware_versions, install_firmware};
use secrets::{agent_key_delete, agent_key_get, agent_key_set};
use reflash::{reflash_circuitpython, rpi_rp2_mount_path};
use templates::{export_page_template, import_page_template, list_page_templates, page_templates_dir};
use updates::{check_for_update, install_update};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .invoke_handler(tauri::generate_handler![
            read_config,
            read_config_raw,
            write_config,
            write_config_raw,
            validate_config,
            restart_device,
            eject_device,
            enter_bootloader,
            enter_bootloader_oem_v5,
            detect_oem_v5_port,
            scan_devices,
            start_device_watcher,
            stop_device_watcher,
            install_firmware,
            get_firmware_versions,
            reflash_circuitpython,
            rpi_rp2_mount_path,
            export_page_template,
            import_page_template,
            list_page_templates,
            page_templates_dir,
            configs_dir,
            open_config_file,
            save_config_file,
            default_config,
            device_config_type,
            check_for_update,
            install_update,
            agent_tool,
            agent_key_get,
            agent_key_set,
            agent_key_delete
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
