// The USB Drive Name rule, shared with the firmware.
//
// boot.py writes the drive's FAT label only when config.json sets
// usb_drive_name (firmware/dev/core/config.py get_explicit_usb_drive_name).
// A missing or unusable name leaves the label alone, so a CIRCUITPY drive or
// one renamed in Finder keeps its name. The label is written at boot, and only
// a hard reset runs boot.py, so the editor hard-resets the device when a save
// changes the name. Keep explicitUsbDriveName in step with the Python;
// tests/fixtures/usb-drive-names.json is checked by both test suites.

/** FAT label for a configured name, or null when the drive should keep its label. */
export function explicitUsbDriveName(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const name = raw.toUpperCase().trim().replace(/[^A-Z0-9_]/g, '').slice(0, 11);
  return name || null;
}

/**
 * A mounted volume's name as its FAT label. macOS mounts a second volume with
 * a name already in use as "NAME 1"; labels can't contain spaces, so that
 * suffix is never part of the label.
 */
export function volumeLabel(volumeName: string): string {
  return volumeName.replace(/ \d+$/, '').toUpperCase();
}

/** The new name the device needs a hard reset to apply, or null if none. */
export function driveRenameTarget(config: unknown, volumeName: string): string | null {
  const raw = config && typeof config === 'object'
    ? (config as { usb_drive_name?: unknown }).usb_drive_name
    : undefined;
  const want = explicitUsbDriveName(raw);
  if (want === null) return null;
  return volumeLabel(volumeName) === want ? null : want;
}
