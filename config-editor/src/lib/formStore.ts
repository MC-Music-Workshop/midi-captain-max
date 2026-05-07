import { writable, derived, get } from 'svelte/store';
import type { MidiCaptainConfig, ButtonConfig, EncoderConfig, DeviceType } from './types';
import { validateConfig } from './validation';

interface FormState {
  config: MidiCaptainConfig;
  history: MidiCaptainConfig[];
  historyIndex: number;
  validationErrors: Map<string, string>;
  isDirty: boolean;
  _hiddenButtons?: ButtonConfig[];
  _hiddenEncoder?: EncoderConfig;
}

const HISTORY_LIMIT = 50;
const DEBOUNCE_MS = 500;

// Initialize with first checkpoint
const initialConfig: MidiCaptainConfig = {
  device: 'std10',
  buttons: [],
  encoder: undefined,
  expression: undefined,
};

const initialState: FormState = {
  config: initialConfig,
  history: [initialConfig],  // Start with checkpoint
  historyIndex: 0,           // At first checkpoint
  validationErrors: new Map(),
  isDirty: false,
};

const formState = writable<FormState>(initialState);

export { formState };
export const config = derived(formState, $state => $state.config);
export const isDirty = derived(formState, $state => $state.isDirty);
export const validationErrors = derived(formState, $state => $state.validationErrors);
export const canUndo = derived(formState, $state => $state.historyIndex > 0);
export const canRedo = derived(formState, $state =>
  $state.historyIndex < $state.history.length - 1
);

// Distinct, sorted list of select_group names already used in the config.
// Powers the autocomplete in ButtonRow's Select-Group input so users can pick
// an existing group rather than retype (and risk typos). Includes groups from
// buttons that aren't currently mode==select, since the form preserves the
// value across mode flips and we want it to remain suggestable.
export const selectGroupNames = derived(formState, $state => {
  const groups = new Set<string>();
  for (const btn of $state.config.buttons) {
    if (btn.select_group) {
      groups.add(btn.select_group);
    }
  }
  return Array.from(groups).sort();
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

export function loadConfig(newConfig: MidiCaptainConfig) {
  // Ensure display always exists so DisplaySection can traverse into it
  const config = { ...newConfig, display: newConfig.display ?? {} };
  formState.update(_state => ({
    config: structuredClone(config),
    history: [structuredClone(config)],
    historyIndex: 0,
    validationErrors: new Map(),
    isDirty: false,
  }));
}

function pushHistory(state: FormState): FormState {
  // Clear any future history if we're not at the end
  const newHistory = state.history.slice(0, state.historyIndex + 1);
  
  // Add current config to history
  newHistory.push(structuredClone(state.config));
  
  // Limit history size
  if (newHistory.length > HISTORY_LIMIT) {
    newHistory.shift();
  }
  
  return {
    ...state,
    history: newHistory,
    historyIndex: newHistory.length - 1,
    isDirty: true,
  };
}

export function undo() {
  formState.update(state => {
    if (state.historyIndex <= 0) return state;
    
    const newIndex = state.historyIndex - 1;
    return {
      ...state,
      config: structuredClone(state.history[newIndex]),
      historyIndex: newIndex,
      isDirty: newIndex !== 0,
    };
  });
}

export function redo() {
  formState.update(state => {
    if (state.historyIndex >= state.history.length - 1) return state;
    
    const newIndex = state.historyIndex + 1;
    return {
      ...state,
      config: structuredClone(state.history[newIndex]),
      historyIndex: newIndex,
      isDirty: true,
    };
  });
}

function setNestedValue(obj: any, path: string, value: any) {
  const parts = path.split('.');
  let current = obj;
  
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    const arrayMatch = part.match(/(\w+)\[(\d+)\]/);
    
    if (arrayMatch) {
      const [, key, index] = arrayMatch;
      const idx = parseInt(index);
      
      // Check array exists and is valid
      if (!current[key]) {
        throw new Error(`Invalid path "${path}": ${key} does not exist`);
      }
      if (!Array.isArray(current[key])) {
        throw new Error(`Invalid path "${path}": ${key} is not an array`);
      }
      if (idx < 0 || idx >= current[key].length) {
        throw new Error(`Invalid path "${path}": index ${idx} out of bounds for ${key} (length ${current[key].length})`);
      }
      
      current = current[key][idx];
    } else {
      // Check object property exists
      if (current[part] === undefined || current[part] === null) {
        throw new Error(`Invalid path "${path}": ${part} does not exist`);
      }
      current = current[part];
    }
  }
  
  // Same checks for the last part
  const lastPart = parts[parts.length - 1];
  const arrayMatch = lastPart.match(/(\w+)\[(\d+)\]/);
  
  if (arrayMatch) {
    const [, key, index] = arrayMatch;
    const idx = parseInt(index);
    
    if (!current[key]) {
      throw new Error(`Invalid path "${path}": ${key} does not exist`);
    }
    if (!Array.isArray(current[key])) {
      throw new Error(`Invalid path "${path}": ${key} is not an array`);
    }
    if (idx < 0 || idx >= current[key].length) {
      throw new Error(`Invalid path "${path}": index ${idx} out of bounds for ${key} (length ${current[key].length})`);
    }
    
    current[key][idx] = value;
  } else {
    current[lastPart] = value;
  }
}

export function updateField(path: string, value: any) {
  // Clear existing debounce
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  
  // Update value immediately
  formState.update(state => {
    const newConfig = structuredClone(state.config);
    setNestedValue(newConfig, path, value);
    
    return {
      ...state,
      config: newConfig,
      isDirty: true,
    };
  });
  
  // Validate after update
  validate();
  
  // Debounce history push
  debounceTimer = setTimeout(() => {
    formState.update(state => pushHistory(state));
  }, DEBOUNCE_MS);
}

export function syncButtonStates(buttonIndex: number, keytimes: number) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }

  formState.update(state => {
    const newConfig = structuredClone(state.config);
    const btn = newConfig.buttons[buttonIndex];
    if (!btn) return state;

    if (keytimes <= 1) {
      delete btn.keytimes;
      delete btn.states;
    } else {
      btn.keytimes = keytimes;
      const current = btn.states ?? [];
      if (current.length < keytimes) {
        while (current.length < keytimes) current.push({});
      } else if (current.length > keytimes) {
        current.length = keytimes;
      }
      btn.states = current;
    }

    return { ...state, config: newConfig, isDirty: true };
  });

  validate();
  formState.update(state => pushHistory(state));
}

function createDefaultButton(index: number): ButtonConfig {
  return {
    label: `BTN${index}`,
    cc: 20 + index,
    color: 'white',
    off_mode: 'dim',
  };
}

function createDefaultButtons(startIndex: number, endIndex: number): ButtonConfig[] {
  const defaults: ButtonConfig[] = [];
  for (let i = startIndex; i <= endIndex; i++) {
    defaults.push(createDefaultButton(i));
  }
  return defaults;
}

// Button count per device type
const DEVICE_BUTTON_COUNT: Record<DeviceType, number> = {
  one1: 1,
  duo2: 2,
  nano4: 4,
  mini6: 6,
  std10: 10,
};

// Whether a device supports encoder
const DEVICE_HAS_ENCODER: Record<DeviceType, boolean> = {
  one1: false,
  duo2: false,
  nano4: false,
  mini6: false,
  std10: true,
};

// Whether a device supports expression pedals
export const DEVICE_HAS_EXPRESSION: Record<DeviceType, boolean> = {
  one1: false,
  duo2: false,
  nano4: false,
  mini6: false,
  std10: true,
};

// Whether a device has a TFT display (for display settings)
export const DEVICE_HAS_TFT: Record<DeviceType, boolean> = {
  one1: false,
  duo2: false,
  nano4: true,
  mini6: true,
  std10: true,
};

export function setDevice(deviceType: DeviceType) {
  formState.update(state => {
    const newState = { ...state };
    const currentDevice = state.config.device;
    const targetCount = DEVICE_BUTTON_COUNT[deviceType];

    // Same device: no-op
    if (deviceType === currentDevice) {
      return state;
    }

    // First-time initialization (no current device set)
    if (!currentDevice) {
      const buttons = state.config.buttons.slice(0, targetCount);
      while (buttons.length < targetCount) {
        buttons.push(createDefaultButton(buttons.length));
      }
      newState.config = {
        ...state.config,
        device: deviceType,
        buttons,
        encoder: !DEVICE_HAS_ENCODER[deviceType] && state.config.encoder
          ? { ...state.config.encoder, enabled: false }
          : state.config.encoder,
      };
      return pushHistory(newState);
    }

    const currentCount = DEVICE_BUTTON_COUNT[currentDevice];

    // Switching to a device with fewer buttons: preserve extras
    if (targetCount < currentCount) {
      if (state.config.buttons.length > targetCount) {
        newState._hiddenButtons = state.config.buttons.slice(targetCount);
      }
      if (state.config.encoder && DEVICE_HAS_ENCODER[currentDevice]) {
        newState._hiddenEncoder = structuredClone(state.config.encoder);
      }
      newState.config = {
        ...state.config,
        device: deviceType,
        buttons: state.config.buttons.slice(0, targetCount),
        encoder: !DEVICE_HAS_ENCODER[deviceType] && state.config.encoder
          ? { ...state.config.encoder, enabled: false }
          : state.config.encoder,
      };
    }

    // Switching to a device with more buttons: restore preserved or create defaults
    else {
      const buttons = state.config.buttons.slice(0, currentCount);
      while (buttons.length < currentCount) {
        buttons.push(createDefaultButton(buttons.length));
      }

      // Restore hidden buttons or create defaults for the extra slots
      const extra = state._hiddenButtons || createDefaultButtons(currentCount, targetCount - 1);
      newState.config = {
        ...state.config,
        device: deviceType,
        buttons: [...buttons, ...extra].slice(0, targetCount),
        encoder: DEVICE_HAS_ENCODER[deviceType]
          ? (state._hiddenEncoder || state.config.encoder)
          : state.config.encoder,
      };

      delete newState._hiddenButtons;
      delete newState._hiddenEncoder;
    }

    return pushHistory(newState);
  });
}

// Strip type-specific fields that don't belong to the button's current type.
// Prevents stale cc/note/program/etc. from accumulating in the saved JSON when
// the user switches a button's type.
function normalizeButton(btn: ButtonConfig): ButtonConfig {
  const type = btn.type ?? 'cc';
  const { cc, cc_on, cc_off, note, velocity_on, velocity_off, program, pc_step, flash_ms,
          hid_action, hid_key, hid_modifier, hid_delay_ms,
          select_group, select_repress, ...common } = btn;

  // Select mode (radio-group) is valid only on PC and CC. select_group/select_repress
  // are stripped on serialize when mode != 'select' so the JSON stays clean even if
  // the form preserved them across mode flips.
  const isSelectMode = common.mode === 'select';
  const selectFields = isSelectMode ? {
    ...(select_group !== undefined && { select_group }),
    ...(select_repress !== undefined && { select_repress }),
  } : {};

  switch (type) {
    case 'cc':
      return {
        ...common,
        ...(cc !== undefined && { cc }),
        ...(cc_on !== undefined && { cc_on }),
        ...(cc_off !== undefined && { cc_off }),
        ...selectFields,
      };
    case 'note':
      return {
        ...common,
        ...(note !== undefined && { note }),
        ...(velocity_on !== undefined && { velocity_on }),
        ...(velocity_off !== undefined && { velocity_off }),
      };
    case 'pc': {
      const pcFlashMode = common.mode === undefined || common.mode === 'flash';
      return {
        ...common,
        ...(program !== undefined && { program }),
        ...(pcFlashMode && flash_ms !== undefined && { flash_ms }),
        ...selectFields,
      };
    }
    case 'pc_inc':
    case 'pc_dec': {
      const pcFlashMode = common.mode === undefined || common.mode === 'flash';
      return {
        ...common,
        ...(pc_step !== undefined && { pc_step }),
        ...(pcFlashMode && flash_ms !== undefined && { flash_ms }),
      };
    }
    case 'hid':
      return {
        ...common,
        ...(hid_action !== undefined && { hid_action }),
        ...(hid_key !== undefined && { hid_key }),
        ...(hid_modifier !== undefined && { hid_modifier }),
        ...(hid_delay_ms !== undefined && { hid_delay_ms }),
      };
    default:
      return btn;
  }
}

export function normalizeConfig(cfg: MidiCaptainConfig): MidiCaptainConfig {
  const normalized: MidiCaptainConfig = { ...cfg, buttons: cfg.buttons.map(normalizeButton) };
  // Strip display if no fields were set (avoids writing `"display": {}` for untouched configs)
  if (normalized.display && Object.values(normalized.display).every(v => v === undefined)) {
    delete normalized.display;
  }
  return normalized;
}

export function validate() {
  const state = get(formState);
  const result = validateConfig(state.config);
  
  formState.update(s => ({
    ...s,
    validationErrors: result.errors,
  }));
  
  return result.isValid;
}
