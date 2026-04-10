// Config types — generated from config.schema.json
// Re-exported here for backwards compatibility. Run `npm run generate:types` to regenerate.
export type {
  MIDICaptainConfig as MidiCaptainConfig,
  ButtonConfig,
  ButtonColor,
  StateOverride,
  EncoderConfig,
  EncoderPush,
  ExpressionConfig,
  ExpressionPedals,
  DisplayConfig,
} from './types.generated';

export type ButtonMode = 'toggle' | 'momentary';
export type OffMode = 'dim' | 'off';
export type MessageType = 'cc' | 'note' | 'pc' | 'pc_inc' | 'pc_dec';
export type Polarity = 'normal' | 'inverted';
export type DeviceType = 'std10' | 'mini6' | 'nano4' | 'duo2' | 'one1';

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
export const BUTTON_COLORS: Record<import('./types.generated').ButtonColor, string> = {
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
