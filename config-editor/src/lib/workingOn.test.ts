import { describe, it, expect } from 'vitest';
import { buttonStates, afterSaveToDevice, afterSaveToFileAs, workingOnLabel, type WorkingOn } from './workingOn';
import type { DetectedDevice } from './types';

const dev: DetectedDevice = { name: 'MIDICAPTAIN', path: '/Volumes/MC', config_path: '/Volumes/MC/config.json', has_config: true };
const onDevice: WorkingOn = { kind: 'device', device: dev };
const onFile: WorkingOn = { kind: 'file', path: '/Users/x/configs/lead.json' };
const onNew: WorkingOn = { kind: 'new' };

describe('buttonStates', () => {
  it('picks the ⌘S action by what you are working on', () => {
    expect(buttonStates(onDevice, true).primary).toBe('device');
    expect(buttonStates(onFile, true).primary).toBe('file');
    expect(buttonStates(onNew, true).primary).toBe('file-as');
  });

  it('shows Save to File / Reload from File only for a file', () => {
    expect(buttonStates(onFile, false).saveToFile.visible).toBe(true);
    expect(buttonStates(onFile, false).reloadFromFile.visible).toBe(true);
    for (const w of [onDevice, onNew]) {
      expect(buttonStates(w, true).saveToFile.visible).toBe(false);
      expect(buttonStates(w, true).reloadFromFile.visible).toBe(false);
    }
  });

  it('enables device buttons only when a device is connected', () => {
    for (const w of [onDevice, onFile, onNew]) {
      expect(buttonStates(w, true).saveToDevice.enabled).toBe(true);
      expect(buttonStates(w, true).reloadFromDevice.enabled).toBe(true);
      const off = buttonStates(w, false);
      expect(off.saveToDevice.enabled).toBe(false);
      expect(off.saveToDevice.hint).toMatch(/disconnected/i);
      expect(off.reloadFromDevice.enabled).toBe(false);
    }
  });
});

describe('afterSaveToDevice', () => {
  it('device: stays, clears the dot', () => {
    expect(afterSaveToDevice(onDevice, dev)).toEqual({ working: onDevice, clearsDirty: true });
  });
  it('file: stays on the file, dot unchanged', () => {
    expect(afterSaveToDevice(onFile, dev)).toEqual({ working: onFile, clearsDirty: false });
  });
  it('new: becomes the device, clears the dot', () => {
    expect(afterSaveToDevice(onNew, dev)).toEqual({ working: onDevice, clearsDirty: true });
  });
});

describe('afterSaveToFileAs', () => {
  it('device: stays on the device, dot unchanged', () => {
    expect(afterSaveToFileAs(onDevice, '/a.json')).toEqual({ working: onDevice, clearsDirty: false });
  });
  it('file: stays on the original file, dot unchanged', () => {
    expect(afterSaveToFileAs(onFile, '/a.json')).toEqual({ working: onFile, clearsDirty: false });
  });
  it('new: becomes the chosen file, clears the dot', () => {
    expect(afterSaveToFileAs(onNew, '/a.json')).toEqual({ working: { kind: 'file', path: '/a.json' }, clearsDirty: true });
  });
});

describe('workingOnLabel', () => {
  it('names the device, file, or new config', () => {
    expect(workingOnLabel(onDevice)).toBe('MIDICAPTAIN');
    expect(workingOnLabel(onFile)).toBe('lead.json');
    expect(workingOnLabel(onNew)).toBe('New config');
    expect(workingOnLabel(null)).toBe('');
  });
});
