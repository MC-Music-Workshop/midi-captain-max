// Config types — generated from config.schema.json
// Re-exported here for backwards compatibility. Run `npm run generate:types` to regenerate.
import type {
  MIDICaptainConfig,
  ButtonConfig,
  ButtonColor,
  ExpressionConfig,
} from './types.generated';

export type { MIDICaptainConfig as MidiCaptainConfig };
export type { ButtonConfig, ButtonColor };
export type {
  StateOverride,
  EncoderConfig,
  EncoderPush,
  ExpressionConfig,
  ExpressionPedals,
  DisplayConfig,
} from './types.generated';

// Keytimes entries/messages carry an optional ephemeral `__uiId` (UI-only, not persisted)
// so {#each} blocks key by stable identity across structuredClone-on-edit. Stripped by
// normalizeConfig before write — never reaches disk.
export type KeytimesEntry = import('./types.generated').KeytimesEntry & { __uiId?: number };
export type KeytimesMessage = import('./types.generated').KeytimesMessage & { __uiId?: number };

// Pages carry the same optional ephemeral `__uiId` as keytimes entries so the
// PageBar {#each} keys by stable identity across structuredClone edits.
// Stripped by normalizeConfig before write — never reaches disk.
export type Page = import('./types.generated').Page & { __uiId?: number };

// Derived from generated types — no manual sync needed
export type ButtonMode = NonNullable<ButtonConfig['mode']>;
export type OffMode = NonNullable<ButtonConfig['off_mode']>;
export type MessageType = NonNullable<ButtonConfig['type']>;
export type Polarity = NonNullable<ExpressionConfig['polarity']>;
export type DeviceType = NonNullable<MIDICaptainConfig['device']>;

// CycleEntryColor includes "off" in addition to the named palette colors. Used by KeytimesEntry.color.
export type CycleEntryColor = NonNullable<import('./types.generated').KeytimesEntry['color']>;

// Human-readable labels for every message type.
// `satisfies` ensures this map stays in sync with the MessageType union —
// if a new type is added to config.schema.json and types are regenerated,
// this line fails to compile until the new entry is added here.
export const MESSAGE_TYPE_LABELS = {
  cc:     'CC',
  note:   'Note',
  pc:     'PC Fixed',
  pc_inc: 'PC+',
  pc_dec: 'PC-',
  hid:    'HID',
  page_inc:  'Page+',
  page_dec:  'Page-',
  page_jump: 'Page Jump',
} as const satisfies Record<MessageType, string>;

// Same pattern for button modes — fails to compile if a new mode is added to the schema
// without updating this map.
export const BUTTON_MODE_LABELS = {
  toggle:    'Toggle',
  momentary: 'Momentary',
  flash:     'Flash',
  select:    'Select',
  keytimes:  'Keytimes (short/long)',
} as const satisfies Record<ButtonMode, string>;

export interface DetectedDevice {
  name: string;
  path: string;
  config_path: string;
  has_config: boolean;
}

export interface ConfigError {
  message: string;
  details?: string[];
}

export type InstallPhase = 'planning' | 'copy' | 'skip' | 'delete' | 'manifest' | 'done';

export interface InstallProgress {
  phase: InstallPhase;
  current: number;
  total: number;
  file: string;
}

export interface FirmwareVersions {
  /** Version on the device, or `null` for an OEM / unmanaged install. */
  device: string | null;
  /** Bundled firmware version this app would install. */
  bundled: string;
}

export interface InstallReport {
  device_type: DeviceType;
  files_copied: number;
  files_skipped: number;
  files_deleted: number;
  version: string;
  config_preserved: boolean;
}

export type ReflashPhase = 'copying' | 'awaitingReboot' | 'done';

export interface ReflashProgress {
  phase: ReflashPhase;
  message: string;
}

// Color mapping for UI
export const BUTTON_COLORS: Record<ButtonColor, string> = {
  red: '#ff0000',
  green: '#00ff00',
  blue: '#0000ff',
  yellow: '#ffff00',
  cyan: '#00ffff',
  magenta: '#ff00ff',
  orange: '#ff8000',
  purple: '#8000ff',
  white: '#ffffff',
};
