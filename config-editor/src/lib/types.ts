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

// Derived from generated types — no manual sync needed
export type ButtonMode = NonNullable<ButtonConfig['mode']>;
export type OffMode = NonNullable<ButtonConfig['off_mode']>;
export type MessageType = NonNullable<ButtonConfig['type']>;
export type Polarity = NonNullable<ExpressionConfig['polarity']>;
export type DeviceType = NonNullable<MIDICaptainConfig['device']>;

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
