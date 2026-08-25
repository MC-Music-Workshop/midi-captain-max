mod commands;
mod config;
mod device;
mod installer;
mod reflash;
mod templates;

use commands::{detect_oem_v5_port, eject_device, enter_bootloader, enter_bootloader_oem_v5, read_config, read_config_raw, restart_device, validate_config, write_config, write_config_raw};
use device::{scan_devices, start_device_watcher, stop_device_watcher};
use installer::{get_firmware_versions, install_firmware};
use reflash::{reflash_circuitpython, rpi_rp2_mount_path};
use templates::{export_page_template, import_page_template, list_page_templates, page_templates_dir};

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
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
            page_templates_dir
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
