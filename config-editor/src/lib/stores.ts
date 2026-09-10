// Svelte stores for state management
import { writable, derived } from 'svelte/store';
import type { DetectedDevice } from './types';

// Connected devices
export const devices = writable<DetectedDevice[]>([]);

// Currently selected device
export const selectedDevice = writable<DetectedDevice | null>(null);

// Current config as raw JSON (for text editor)
export const currentConfigRaw = writable<string>('');

// Whether config has unsaved changes
export const hasUnsavedChanges = writable<boolean>(false);

// Validation errors
export const validationErrors = writable<string[]>([]);

// UI state
export const isLoading = writable<boolean>(false);
export const statusMessage = writable<string>('');

// Derived: is a device selected and has config
export const canEdit = derived(
  [selectedDevice, currentConfigRaw],
  ([$device, $configRaw]) => $device !== null && $configRaw !== ''
);

// What the toolbar Save button does. Sticky across sessions via localStorage
// ('save' = write config.json only; 'save_restart' = write, then soft-reboot the
// device so the change applies immediately). The dropdown next to the button
// changes it; the button (and ⌘S) run whatever is selected.
export type SaveMode = 'save' | 'save_restart';

const SAVE_MODE_KEY = 'mcm.saveMode';

function loadSaveMode(): SaveMode {
  // localStorage can be unavailable or throw (private mode, blocked storage);
  // fall back to the plain save so the toolbar always works.
  try {
    const v = globalThis.localStorage?.getItem(SAVE_MODE_KEY);
    return v === 'save_restart' ? 'save_restart' : 'save';
  } catch {
    return 'save';
  }
}

export const saveMode = writable<SaveMode>(loadSaveMode());

saveMode.subscribe(mode => {
  try {
    globalThis.localStorage?.setItem(SAVE_MODE_KEY, mode);
  } catch {
    // Not persistable here — the choice still holds for this session.
  }
});
