/* eslint-disable */
/**
 * AUTO-GENERATED from config.schema.json — do not edit manually.
 * Run: npm run generate:types
 */

/**
 * Standard MIDI byte value (0-127).
 */
export type MidiByte = number;
export type ButtonColor = "red" | "green" | "blue" | "yellow" | "cyan" | "magenta" | "orange" | "purple" | "white";
/**
 * 'send' = press+release, 'press' = hold key, 'release' = release key(s), 'delay' = pause execution.
 */
export type HidAction = "send" | "press" | "release" | "delay";
/**
 * Modifier key held during the HID action. 'option' is macOS Alt; 'windows' is the Windows/Meta key.
 */
export type HidModifier = "ctrl" | "shift" | "alt" | "option" | "windows";

/**
 * Configuration for Paint Audio MIDI Captain MAX custom firmware. This schema is the single source of truth for the config format — TypeScript types are generated from it, Rust structs are validated against it, and Python firmware uses it as reference. Note: the title field drives the generated TypeScript interface name, so keep it short and stable.
 */
export interface MIDICaptainConfig {
  /**
   * Device model. Determines button count and feature availability (encoder/expression are STD10-only).
   */
  device?: "std10" | "mini6" | "nano4" | "duo2" | "one1";
  /**
   * Default MIDI channel for all components. Stored as 0-15, displayed as 1-16 in UI.
   */
  global_channel?: number;
  /**
   * USB drive volume label. FAT32 compatible: uppercase alphanumeric + underscore, max 11 chars.
   */
  usb_drive_name?: string;
  /**
   * When true, USB drive mounts on every boot. When false (default), requires holding Switch 1 during boot.
   */
  dev_mode?: boolean;
  /**
   * Button configurations. Array length must match device type: std10=10, mini6=6, nano4=4, duo2=2, one1=1.
   */
  buttons: ButtonConfig[];
  encoder?: EncoderConfig;
  expression?: ExpressionPedals;
  display?: DisplayConfig;
}
export interface ButtonConfig {
  /**
   * Display label. Max 6 chars, alphanumeric + space + hyphen.
   */
  label: string;
  /**
   * LED color for this button.
   */
  color: "red" | "green" | "blue" | "yellow" | "cyan" | "magenta" | "orange" | "purple" | "white";
  /**
   * MIDI message type. Determines which fields apply. Default: 'cc'.
   */
  type?: "cc" | "note" | "pc" | "pc_inc" | "pc_dec" | "hid";
  /**
   * Button behavior. 'toggle' = latching LED on/off, 'momentary' = LED on while held, 'flash' = brief LED flash on press (PC types only, default for PC types), 'select' = radio-group exclusivity (PC and CC only, requires select_group). Default for CC/Note/HID: 'toggle'.
   */
  mode?: "toggle" | "momentary" | "flash" | "select";
  /**
   * Radio-group identifier. Required when mode='select'. Pressing a select-mode button activates it and deactivates all sibling buttons sharing the same select_group. PC and CC types only.
   */
  select_group?: string;
  /**
   * Behavior when re-pressing the already-active select-group member. Default: 'resend'.
   */
  select_repress?: "resend" | "nothing" | "deselect";
  /**
   * LED behavior when button is off. Default: 'dim'.
   */
  off_mode?: "dim" | "off";
  /**
   * Per-button MIDI channel override. Inherits global_channel if omitted.
   */
  channel?: number;
  /**
   * CC number. Used when type='cc'. Default: 20 + button index.
   */
  cc?: number;
  /**
   * CC value sent when button is pressed (ON). Default: 127.
   */
  cc_on?: number;
  /**
   * CC value sent when button is released (OFF). Default: 0.
   */
  cc_off?: number;
  /**
   * MIDI note number. Used when type='note'. Default: 60 (Middle C).
   */
  note?: number;
  /**
   * Note velocity when pressed. Used when type='note'. Default: 127.
   */
  velocity_on?: number;
  /**
   * Note velocity when released (Note Off). Used when type='note'. Default: 0.
   */
  velocity_off?: number;
  /**
   * Program number. Used when type='pc'. Default: 0.
   */
  program?: number;
  /**
   * Step size for program change increment/decrement. Used when type='pc_inc' or 'pc_dec'.
   */
  pc_step?: number;
  /**
   * LED flash duration in milliseconds. Used when type is PC and mode is 'flash'.
   */
  flash_ms?: number;
  /**
   * Number of states to cycle through on press. 1 = no cycling.
   */
  keytimes?: number;
  /**
   * Per-state overrides. Array length should match keytimes value.
   */
  states?: StateOverride[];
  /**
   * 'send' = press+release, 'press' = hold key, 'release' = release key(s), 'delay' = pause execution.
   */
  hid_action?: "send" | "press" | "release" | "delay";
  /**
   * Key name for HID action. Used when type='hid'. Valid values: A-Z, 0-9, F1-F12, Mouse_L, Mouse_R, Space, Esc, Caps, Right, Left, Up, Down, End, Del, PageUp, PageDown, Enter, Pause, Table, BackSpace, Home, Ins, PrintS, all (for release-all).
   */
  hid_key?: string;
  /**
   * Modifier key held during the HID action. 'option' is macOS Alt; 'windows' is the Windows/Meta key.
   */
  hid_modifier?: "ctrl" | "shift" | "alt" | "option" | "windows";
  /**
   * Delay duration in milliseconds. Used when type='hid' and hid_action='delay'.
   */
  hid_delay_ms?: number;
}
/**
 * Per-state overrides applied when cycling through keytimes. All fields optional — only specified fields override the base button config.
 */
export interface StateOverride {
  cc?: MidiByte;
  cc_on?: MidiByte;
  cc_off?: MidiByte;
  note?: MidiByte;
  velocity_on?: MidiByte;
  velocity_off?: MidiByte;
  program?: MidiByte;
  pc_step?: number;
  color?: ButtonColor;
  label?: string;
  hid_action?: HidAction;
  /**
   * Key name override for this keytime state.
   */
  hid_key?: string;
  hid_modifier?: HidModifier;
  hid_delay_ms?: number;
}
/**
 * Rotary encoder configuration. Only supported on STD10.
 */
export interface EncoderConfig {
  /**
   * Enable/disable rotary encoder.
   */
  enabled: boolean;
  /**
   * Standard MIDI byte value (0-127).
   */
  cc: number;
  /**
   * Display label. Max 8 chars.
   */
  label: string;
  /**
   * Standard MIDI byte value (0-127).
   */
  min?: number;
  /**
   * Standard MIDI byte value (0-127).
   */
  max?: number;
  /**
   * Standard MIDI byte value (0-127).
   */
  initial?: number;
  /**
   * Number of discrete steps. null = continuous rotation.
   */
  steps?: number | null;
  /**
   * Per-encoder MIDI channel override. Inherits global_channel if omitted.
   */
  channel?: number;
  push?: EncoderPush;
}
/**
 * Encoder push button configuration.
 */
export interface EncoderPush {
  /**
   * Enable/disable encoder push button.
   */
  enabled: boolean;
  /**
   * Standard MIDI byte value (0-127).
   */
  cc: number;
  /**
   * Display label. Max 8 chars.
   */
  label: string;
  /**
   * Button behavior. Default: 'momentary'.
   */
  mode?: "toggle" | "momentary" | "flash" | "select";
  /**
   * Per-push MIDI channel override. Inherits encoder channel or global_channel if omitted.
   */
  channel?: number;
  /**
   * Standard MIDI byte value (0-127).
   */
  cc_on?: number;
  /**
   * Standard MIDI byte value (0-127).
   */
  cc_off?: number;
}
/**
 * Expression pedal configurations. Only supported on STD10.
 */
export interface ExpressionPedals {
  exp1: ExpressionConfig;
  exp2: ExpressionConfig;
}
export interface ExpressionConfig {
  /**
   * Enable/disable this expression pedal.
   */
  enabled: boolean;
  /**
   * Standard MIDI byte value (0-127).
   */
  cc: number;
  /**
   * Display label. Max 8 chars.
   */
  label: string;
  /**
   * Standard MIDI byte value (0-127).
   */
  min?: number;
  /**
   * Standard MIDI byte value (0-127).
   */
  max?: number;
  /**
   * Sweep direction. Default: 'normal'.
   */
  polarity?: "normal" | "inverted";
  /**
   * Standard MIDI byte value (0-127).
   */
  threshold?: number;
  /**
   * Per-pedal MIDI channel override. Inherits global_channel if omitted.
   */
  channel?: number;
}
/**
 * Display and text rendering settings.
 */
export interface DisplayConfig {
  /**
   * Button label text size.
   */
  button_text_size?: "small" | "medium" | "large";
  /**
   * Status display text size.
   */
  status_text_size?: "small" | "medium" | "large";
  /**
   * Expression pedal text size.
   */
  expression_text_size?: "small" | "medium" | "large";
}
