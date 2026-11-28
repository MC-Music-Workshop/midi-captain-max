import { describe, it, expect } from 'vitest';
import { explicitUsbDriveName, volumeLabel, driveRenameTarget } from './driveName';
import shared from '../../../tests/fixtures/usb-drive-names.json';

describe('explicitUsbDriveName', () => {
  // Same table as tests/test_usb_drive_name.py, so editor and firmware agree.
  it.each(shared.cases)('$input → $explicit', ({ input, explicit }) => {
    expect(explicitUsbDriveName(input)).toBe(explicit);
  });

  it('is null when the setting is absent', () => {
    expect(explicitUsbDriveName(undefined)).toBeNull();
  });
});

describe('volumeLabel', () => {
  it('drops the suffix macOS adds to a duplicate volume name', () => {
    expect(volumeLabel('MYBOARD 1')).toBe('MYBOARD');
    expect(volumeLabel('MYBOARD')).toBe('MYBOARD');
  });

  it('compares case-insensitively', () => {
    expect(volumeLabel('midicaptain')).toBe('MIDICAPTAIN');
  });
});

describe('driveRenameTarget', () => {
  it('asks for a rename when the configured name differs from the drive', () => {
    expect(driveRenameTarget({ usb_drive_name: 'Stage L' }, 'CIRCUITPY')).toBe('STAGEL');
  });

  it('does nothing when the drive already has the name', () => {
    expect(driveRenameTarget({ usb_drive_name: 'myboard' }, 'MYBOARD')).toBeNull();
    expect(driveRenameTarget({ usb_drive_name: 'MYBOARD' }, 'MYBOARD 1')).toBeNull();
  });

  it('never renames when the name is not set or unusable', () => {
    expect(driveRenameTarget({}, 'STAGELEFT')).toBeNull();
    expect(driveRenameTarget({ usb_drive_name: '' }, 'CIRCUITPY')).toBeNull();
    expect(driveRenameTarget({ usb_drive_name: '!!!' }, 'CIRCUITPY')).toBeNull();
    expect(driveRenameTarget(null, 'CIRCUITPY')).toBeNull();
  });
});
