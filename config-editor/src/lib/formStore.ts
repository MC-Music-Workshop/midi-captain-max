import { writable, derived, get } from 'svelte/store';
import type { MidiCaptainConfig, ButtonConfig, EncoderConfig, DeviceType, KeytimesEntry, KeytimesMessage, MessageType, Page } from './types';
import { validateConfig } from './validation';

interface FormState {
  config: MidiCaptainConfig;
  history: MidiCaptainConfig[];
  historyIndex: number;
  validationErrors: Map<string, string>;
  isDirty: boolean;
  // Per-page button tails / encoders stashed when shrinking to a smaller device,
  // so switching back restores them. Indexed by page.
  _hiddenButtons?: ButtonConfig[][];
  _hiddenEncoder?: (EncoderConfig | undefined)[];
}

const HISTORY_LIMIT = 50;
const DEBOUNCE_MS = 500;

// Initialize with first checkpoint. Canonical pages-only shape: one empty page.
const initialConfig: MidiCaptainConfig = {
  device: 'std10',
  active_page: 0,
  pages: [{ buttons: [] }],
};

// --- Active-page indirection (#15) ---
//
// The editor renders one page at a time. These helpers are the single place that
// resolves "the active page", so the rest of the store (and every component path)
// stays page-agnostic. When page-switching UI lands (P4), only `active_page`
// changes — every read/write here follows automatically.

function activePageIndex(cfg: MidiCaptainConfig): number {
  const len = cfg.pages?.length ?? 0;
  if (len === 0) return 0;
  const ap = cfg.active_page ?? 0;
  return Math.max(0, Math.min(len - 1, ap));
}

function activePage(cfg: MidiCaptainConfig): Page {
  return cfg.pages[activePageIndex(cfg)];
}

// Paths whose first segment is page-scoped control-surface data get prefixed with
// the active page; device-wide paths (display, global_channel, usb_drive_name,
// midi_thru_*, dev_mode, long_press_threshold_ms) pass through unchanged.
const PAGE_SCOPED_PATH = /^(buttons|encoder|expression)(\.|\[|$)/;

function pageScopedPath(cfg: MidiCaptainConfig, path: string): string {
  if (!PAGE_SCOPED_PATH.test(path)) return path;
  return `pages[${activePageIndex(cfg)}].${path}`;
}

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
// The page the editor is currently rendering. Components read page-scoped data
// (buttons/encoder/expression) from here rather than reaching into $config.
export const currentPage = derived(formState, $state => activePage($state.config));
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
  // Select groups are per-page; the editor only renders the active page, so
  // suggest groups from that page.
  for (const btn of activePage($state.config).buttons) {
    if (btn.select_group) {
      groups.add(btn.select_group);
    }
  }
  return Array.from(groups).sort();
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

// Ephemeral UI-only ids attached to KeytimesEntry/KeytimesMessage objects so
// Svelte {#each} blocks can key by stable identity across structuredClone edits.
// Stripped from any config written to disk (see normalizeConfig).
let _uiIdCounter = 0;
function _nextUiId(): number {
  return ++_uiIdCounter;
}

// Walk a config and assign `__uiId` to any page / keytimes entry / message that lacks one.
// Mutates in place; safe to call on a freshly structuredCloned config.
function _attachUiIds(cfg: MidiCaptainConfig): void {
  for (const page of cfg.pages ?? []) {
    if (typeof (page as Page).__uiId !== 'number') (page as Page).__uiId = _nextUiId();
    for (const btn of page.buttons) {
      for (const cycle of ['short', 'long'] as const) {
        const entries = (btn as unknown as Record<string, unknown>)[cycle];
        if (!Array.isArray(entries)) continue;
        for (const entry of entries as Array<Record<string, unknown>>) {
          if (typeof entry.__uiId !== 'number') entry.__uiId = _nextUiId();
          for (const slot of ['down', 'up'] as const) {
            const messages = entry[slot];
            if (!Array.isArray(messages)) continue;
            for (const msg of messages as Array<Record<string, unknown>>) {
              if (typeof msg.__uiId !== 'number') msg.__uiId = _nextUiId();
            }
          }
        }
      }
    }
  }
}

export function loadConfig(newConfig: MidiCaptainConfig) {
  // Ensure display always exists so DisplaySection can traverse into it.
  // Guarantee at least one page and clamp active_page so the pages[active]
  // paths that updateField builds are always traversable.
  const pages = newConfig.pages?.length ? newConfig.pages : [{ buttons: [] }];
  const active_page = Math.max(0, Math.min(pages.length - 1, newConfig.active_page ?? 0));
  const config = { ...newConfig, pages, active_page, display: newConfig.display ?? {} };
  const cloned = structuredClone(config);
  _attachUiIds(cloned);
  formState.update(_state => ({
    config: cloned,
    history: [structuredClone(cloned)],
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
    setNestedValue(newConfig, pageScopedPath(newConfig, path), value);

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

// --- Keytimes-mode helpers (mode: "keytimes" cycle/message mutations) ---
//
// These wrap formState updates that change the *structure* of a keytimes-mode
// button (adding/removing entries or messages). For leaf-value edits (color,
// dim, label, individual message fields), use updateField() with a dotted path.

function _defaultMessage(type: MessageType): KeytimesMessage {
  switch (type) {
    case 'cc':     return { type: 'cc', cc: 20, value: 127 };
    case 'note':   return { type: 'note', note: 60, velocity: 127 };
    case 'pc':     return { type: 'pc', program: 0 };
    case 'pc_inc': return { type: 'pc_inc', step: 1 };
    case 'pc_dec': return { type: 'pc_dec', step: 1 };
    case 'hid':    return { type: 'hid', action: 'send' };
    case 'page_inc': return { type: 'page_inc', page_step: 1 };
    case 'page_dec': return { type: 'page_dec', page_step: 1 };
    case 'page_jump': return { type: 'page_jump', page: 0 };
  }
}

function _updateButton(buttonIndex: number, mutate: (btn: ButtonConfig) => void) {
  formState.update(state => {
    const newConfig = structuredClone(state.config);
    const btn = activePage(newConfig).buttons[buttonIndex];
    if (!btn) return state;
    mutate(btn);
    return { ...state, config: newConfig, isDirty: true };
  });
  validate();
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => formState.update(state => pushHistory(state)), DEBOUNCE_MS);
}

export function addKeytimesEntry(buttonIndex: number, cycle: 'short' | 'long') {
  _updateButton(buttonIndex, btn => {
    const arr = (btn[cycle] ?? []) as KeytimesEntry[];
    arr.push({ __uiId: _nextUiId() } as KeytimesEntry);
    btn[cycle] = arr;
  });
}

export function removeKeytimesEntry(buttonIndex: number, cycle: 'short' | 'long', entryIndex: number) {
  _updateButton(buttonIndex, btn => {
    const arr = btn[cycle];
    if (!Array.isArray(arr)) return;
    arr.splice(entryIndex, 1);
    if (arr.length === 0) {
      delete btn[cycle];
    } else {
      btn[cycle] = arr;
    }
  });
}

export function addKeytimesMessage(
  buttonIndex: number,
  cycle: 'short' | 'long',
  entryIndex: number,
  slot: 'down' | 'up',
  msgType: MessageType = 'cc',
) {
  _updateButton(buttonIndex, btn => {
    const arr = btn[cycle];
    if (!Array.isArray(arr) || !arr[entryIndex]) return;
    const entry = arr[entryIndex] as KeytimesEntry;
    const messages = (entry[slot] ?? []) as KeytimesMessage[];
    messages.push({ ..._defaultMessage(msgType), __uiId: _nextUiId() } as KeytimesMessage);
    entry[slot] = messages;
  });
}

export function removeKeytimesMessage(
  buttonIndex: number,
  cycle: 'short' | 'long',
  entryIndex: number,
  slot: 'down' | 'up',
  msgIndex: number,
) {
  _updateButton(buttonIndex, btn => {
    const arr = btn[cycle];
    if (!Array.isArray(arr) || !arr[entryIndex]) return;
    const entry = arr[entryIndex] as KeytimesEntry;
    const messages = entry[slot];
    if (!Array.isArray(messages)) return;
    messages.splice(msgIndex, 1);
    if (messages.length === 0) {
      delete entry[slot];
    } else {
      entry[slot] = messages;
    }
  });
}

export function setKeytimesMessageType(
  buttonIndex: number,
  cycle: 'short' | 'long',
  entryIndex: number,
  slot: 'down' | 'up',
  msgIndex: number,
  newType: MessageType,
) {
  // Replace the whole message with a default of the new type, since type-specific
  // fields don't overlap across types (cc/value vs note/velocity vs program vs step vs key).
  _updateButton(buttonIndex, btn => {
    const arr = btn[cycle];
    if (!Array.isArray(arr) || !arr[entryIndex]) return;
    const entry = arr[entryIndex] as KeytimesEntry;
    const messages = entry[slot];
    if (!Array.isArray(messages) || !messages[msgIndex]) return;
    messages[msgIndex] = _defaultMessage(newType);
  });
}

export function syncButtonStates(buttonIndex: number, keytimes: number) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }

  formState.update(state => {
    const newConfig = structuredClone(state.config);
    const btn = activePage(newConfig).buttons[buttonIndex];
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

// Slice/pad a button array to exactly `count` entries.
function padButtons(buttons: ButtonConfig[], count: number): ButtonConfig[] {
  const out = buttons.slice(0, count);
  while (out.length < count) out.push(createDefaultButton(out.length));
  return out;
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
    const currentDevice = state.config.device;
    const targetCount = DEVICE_BUTTON_COUNT[deviceType];
    const hasEncoder = DEVICE_HAS_ENCODER[deviceType];

    // Same device: no-op
    if (deviceType === currentDevice) {
      return state;
    }

    const newState = { ...state };
    // Device button count and encoder support apply to EVERY page — a config has
    // one device, so all pages share the same control-surface shape.
    const pages = structuredClone(state.config.pages);

    // First-time initialization (no current device set): just size each page.
    if (!currentDevice) {
      for (const page of pages) {
        page.buttons = padButtons(page.buttons, targetCount);
        if (!hasEncoder && page.encoder) page.encoder = { ...page.encoder, enabled: false };
      }
      newState.config = { ...state.config, device: deviceType, pages };
      return pushHistory(newState);
    }

    const currentCount = DEVICE_BUTTON_COUNT[currentDevice];

    if (targetCount < currentCount) {
      // Shrinking: stash each page's truncated tail + encoder so switching back restores them.
      const hiddenButtons: ButtonConfig[][] = [];
      const hiddenEncoder: (EncoderConfig | undefined)[] = [];
      pages.forEach((page, i) => {
        hiddenButtons[i] = page.buttons.slice(targetCount);
        hiddenEncoder[i] = DEVICE_HAS_ENCODER[currentDevice] ? structuredClone(page.encoder) : undefined;
        page.buttons = page.buttons.slice(0, targetCount);
        if (!hasEncoder && page.encoder) page.encoder = { ...page.encoder, enabled: false };
      });
      newState._hiddenButtons = hiddenButtons;
      newState._hiddenEncoder = hiddenEncoder;
    } else {
      // Growing: restore stashed tails (per page) or pad with defaults.
      pages.forEach((page, i) => {
        const base = padButtons(page.buttons, currentCount);
        const extra = state._hiddenButtons?.[i] ?? createDefaultButtons(currentCount, targetCount - 1);
        page.buttons = [...base, ...extra].slice(0, targetCount);
        if (hasEncoder) {
          page.encoder = state._hiddenEncoder?.[i] ?? page.encoder;
        }
      });
      delete newState._hiddenButtons;
      delete newState._hiddenEncoder;
    }

    newState.config = { ...state.config, device: deviceType, pages };
    return pushHistory(newState);
  });
}

// --- Page CRUD helpers (#15 P4a) ---
//
// Each helper is one immediate history checkpoint (like syncButtonStates), so
// undo/redo steps page-wise. A pending debounced field-edit checkpoint is
// folded into the CRUD checkpoint (its config state is included in the push).
// `mutate` returns false to abort (no state change, no dirty, no history).

export const PAGE_CAP = 20;

function _commitConfigMutation(mutate: (cfg: MidiCaptainConfig) => boolean | void) {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  formState.update(state => {
    const newConfig = structuredClone(state.config);
    if (mutate(newConfig) === false) return state;
    _attachUiIds(newConfig);
    return pushHistory({ ...state, config: newConfig });
  });
  validate();
}

export function setActivePage(index: number) {
  _commitConfigMutation(cfg => {
    const clamped = Math.max(0, Math.min((cfg.pages?.length ?? 1) - 1, index));
    if (clamped === (cfg.active_page ?? 0)) return false;
    cfg.active_page = clamped;
  });
}

// Strip type-specific fields that don't belong to the button's current type.
// Prevents stale cc/note/program/etc. from accumulating in the saved JSON when
// the user switches a button's type.
function normalizeButton(btn: ButtonConfig): ButtonConfig {
  // mode: "keytimes" carries its message data inside short[]/long[] entries,
  // not at the top of the button. Strip all legacy per-type fields here so
  // serialized JSON stays clean if the user toggled the button through other
  // modes before settling on keytimes.
  if (btn.mode === 'keytimes') {
    const { cc, cc_on, cc_off, note, velocity_on, velocity_off, program, pc_step, flash_ms,
            hid_action, hid_key, hid_modifier, hid_delay_ms,
            select_group, select_repress, keytimes, states, type, ...common } = btn;
    return {
      ...common,
      ...(btn.short !== undefined && { short: btn.short }),
      ...(btn.long !== undefined && { long: btn.long }),
      ...(btn.long_press_threshold_ms !== undefined && { long_press_threshold_ms: btn.long_press_threshold_ms }),
    };
  }

  // Non-keytimes modes: keytimes/states are deprecated but still functional in v2.0.
  // Strip the new-mode-only fields (short/long/long_press_threshold_ms) if they leaked in.
  const { short: _short, long: _long, long_press_threshold_ms: _lpt, ...btnWithoutKeytimesFields } = btn;
  const type = btnWithoutKeytimesFields.type ?? 'cc';
  const { cc, cc_on, cc_off, note, velocity_on, velocity_off, program, pc_step, flash_ms,
          hid_action, hid_key, hid_modifier, hid_delay_ms,
          select_group, select_repress, ...common } = btnWithoutKeytimesFields;

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

// Recursively strip ephemeral `__uiId` markers from a deep-cloned config so they
// never reach the on-disk JSON. Operates on the input in place.
function _stripUiIds(value: unknown): void {
  if (Array.isArray(value)) {
    for (const v of value) _stripUiIds(v);
  } else if (value && typeof value === 'object') {
    delete (value as Record<string, unknown>).__uiId;
    for (const v of Object.values(value)) _stripUiIds(v);
  }
}

export function normalizeConfig(cfg: MidiCaptainConfig): MidiCaptainConfig {
  // Deep clone so the ephemeral `__uiId` strip below (and any other mutations)
  // don't reach back into the live store.
  const cloned = structuredClone(cfg);
  // Normalize each page's buttons; strip empty per-page display overrides.
  const normalized: MidiCaptainConfig = {
    ...cloned,
    pages: cloned.pages.map(page => {
      const p: Page = { ...page, buttons: page.buttons.map(normalizeButton) };
      if (p.display && Object.values(p.display).every(v => v === undefined)) {
        delete p.display;
      }
      return p;
    }),
  };
  // Strip device-wide display if no fields were set (avoids writing `"display": {}`)
  if (normalized.display && Object.values(normalized.display).every(v => v === undefined)) {
    delete normalized.display;
  }
  // Drop UI-only stable-key markers attached to keytimes entries/messages.
  _stripUiIds(normalized);
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
