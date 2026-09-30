// What the editor is working on, and what each button does about it (#36).
// The rules live here as pure functions so the button table in
// docs/plans/2026-09-29-issue-36-saved-configs.md can be tested row by row.
import type { DetectedDevice } from './types';

export type WorkingOn =
  | { kind: 'device'; device: DetectedDevice } // loaded from a device
  | { kind: 'file'; path: string } // loaded from (or first saved to) a local file
  | { kind: 'new' }; // New Config…, never saved

/** The action ⌘S and the highlighted toolbar button run. */
export type PrimarySave = 'device' | 'file' | 'file-as';

export interface ButtonStates {
  primary: PrimarySave;
  saveToDevice: { enabled: boolean; hint?: string };
  saveToFile: { visible: boolean }; // overwrite the open file
  reloadFromDevice: { enabled: boolean };
  reloadFromFile: { visible: boolean };
}

/** `deviceConnected`: a device is selected and currently connected. */
export function buttonStates(working: WorkingOn, deviceConnected: boolean): ButtonStates {
  return {
    primary: working.kind === 'device' ? 'device' : working.kind === 'file' ? 'file' : 'file-as',
    saveToDevice: {
      enabled: deviceConnected,
      hint: deviceConnected ? undefined : 'Device disconnected',
    },
    saveToFile: { visible: working.kind === 'file' },
    reloadFromDevice: { enabled: deviceConnected },
    reloadFromFile: { visible: working.kind === 'file' },
  };
}

export interface SaveOutcome {
  working: WorkingOn;
  clearsDirty: boolean; // D5: only a save to what you're working on clears the dot
}

/** Save to Device: a new config becomes the device it was saved to (D3). */
export function afterSaveToDevice(working: WorkingOn, device: DetectedDevice): SaveOutcome {
  if (working.kind === 'new') return { working: { kind: 'device', device }, clearsDirty: true };
  return { working, clearsDirty: working.kind === 'device' };
}

/** Save to File… (choose a path): a new config becomes that file (D3). */
export function afterSaveToFileAs(working: WorkingOn, path: string): SaveOutcome {
  if (working.kind === 'new') return { working: { kind: 'file', path }, clearsDirty: true };
  return { working, clearsDirty: false };
}

export function fileName(path: string): string {
  return path.split(/[\\/]/).pop() || path;
}

export function workingOnLabel(working: WorkingOn | null): string {
  if (!working) return '';
  if (working.kind === 'device') return working.device.name;
  if (working.kind === 'file') return fileName(working.path);
  return 'New config';
}
