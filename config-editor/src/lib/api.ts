// Tauri command wrappers

import { invoke, Channel } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';
import type {
  MidiCaptainConfig,
  DetectedDevice,
  FirmwareVersions,
  InstallProgress,
  InstallReport,
  ReflashProgress,
} from './types';

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

export async function restartDevice(path: string): Promise<void> {
  return invoke('restart_device', { path });
}

export async function ejectDevice(path: string): Promise<void> {
  return invoke('eject_device', { path });
}

// Device operations
export async function scanDevices(): Promise<DetectedDevice[]> {
  return invoke('scan_devices');
}

export async function startDeviceWatcher(): Promise<void> {
  return invoke('start_device_watcher');
}

// Firmware installer
export async function getFirmwareVersions(devicePath: string): Promise<FirmwareVersions> {
  return invoke('get_firmware_versions', { devicePath });
}

export async function installFirmware(
  devicePath: string,
  resetConfig: boolean,
  onProgress: (p: InstallProgress) => void,
): Promise<InstallReport> {
  const channel = new Channel<InstallProgress>();
  channel.onmessage = onProgress;
  return invoke('install_firmware', {
    devicePath,
    resetConfig,
    onProgress: channel,
  });
}

/**
 * Return the mount path of the RPI-RP2 bootloader drive, or null if not present.
 * UI polls this while the user does the BOOTSEL/Switch 1 hold + replug to enter
 * the RP2040 ROM bootloader.
 */
export async function rpiRp2MountPath(): Promise<string | null> {
  return invoke('rpi_rp2_mount_path');
}

/**
 * Copy the bundled CircuitPython 7.3.1 .uf2 onto a mounted RPI-RP2 drive.
 * Caller must have already observed `rpiRp2MountPath()` returning non-null —
 * the command errors out if the bootloader drive isn't mounted.
 *
 * Resolves once bytes are written (or the bootloader has unmounted itself
 * mid-copy, which counts as success). Reboot back to CIRCUITPY is handled by
 * the RP2040 ROM bootloader; the UI should poll `scanDevices()` afterward.
 */
export async function reflashCircuitpython(
  onProgress: (p: ReflashProgress) => void,
): Promise<void> {
  const channel = new Channel<ReflashProgress>();
  channel.onmessage = onProgress;
  return invoke('reflash_circuitpython', { onProgress: channel });
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
