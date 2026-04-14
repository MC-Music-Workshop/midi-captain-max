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
