import type { MidiCaptainConfig } from './types';

export interface ValidationResult {
  isValid: boolean;
  errors: Map<string, string>;
}

export interface FieldValidator {
  (value: any, config?: MidiCaptainConfig): string | null;
}

export const validators = {
  label: (value: string): string | null => {
    if (!value || value.trim() === '') {
      return 'Label is required';
    }
    if (value.length > 6) {
      return 'Label must be 6 characters or less';
    }
    if (!/^[\w\s-]+$/.test(value)) {
      return 'Label contains invalid characters';
    }
    return null;
  },
  
  cc: (value: number, config?: MidiCaptainConfig): string | null => {
    if (value < 0 || value > 127) {
      return 'CC must be between 0 and 127';
    }
    if (!Number.isInteger(value)) {
      return 'CC must be an integer';
    }
    return null;
  },
  
  range: (min: number, max: number): string | null => {
    if (min >= max) {
      return 'Min must be less than max';
    }
    return null;
  },
  
  withinRange: (value: number, min: number, max: number): string | null => {
    if (value < min || value > max) {
      return `Value must be between ${min} and ${max}`;
    }
    return null;
  },

  note: (value: number): string | null => {
    if (value < 0 || value > 127) return 'Note must be between 0 and 127';
    if (!Number.isInteger(value)) return 'Note must be an integer';
    return null;
  },

  velocity: (value: number): string | null => {
    if (value < 0 || value > 127) return 'Velocity must be between 0 and 127';
    if (!Number.isInteger(value)) return 'Velocity must be an integer';
    return null;
  },

  program: (value: number): string | null => {
    if (value < 0 || value > 127) return 'Program must be between 0 and 127';
    if (!Number.isInteger(value)) return 'Program must be an integer';
    return null;
  },

  pcStep: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Step must be an integer';
    if (value < 1 || value > 127) return 'Step must be between 1 and 127';
    return null;
  },

  keytimes: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Keytimes must be an integer';
    if (value < 1 || value > 99) return 'Keytimes must be between 1 and 99';
    return null;
  },

  flashMs: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Flash duration must be an integer';
    if (value < 50 || value > 5000) return 'Flash duration must be between 50 and 5000 ms';
    return null;
  },

  // value is stored as 0-15 (displayed as 1-16)
  channel: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Channel must be an integer';
    if (value < 0 || value > 15) return 'Channel must be between 1 and 16';
    return null;
  },

  usbDriveName: (value: string): string | null => {
    if (value.length > 11) return 'Drive name must be 11 characters or less';
    if (!/^[A-Za-z0-9_]*$/.test(value)) return 'Drive name may only contain A–Z, 0–9, and underscore';
    return null;
  },
};

export function validateConfig(config: MidiCaptainConfig): ValidationResult {
  const errors = new Map<string, string>();
  
  // Device-specific validation
  if (config.device === 'one1') {
    if (config.buttons.length > 1) {
      errors.set('device', 'ONE supports only 1 button');
    }
    if (config.encoder?.enabled) {
      errors.set('encoder.enabled', 'ONE does not support encoder');
    }
    if (config.expression?.exp1?.enabled || config.expression?.exp2?.enabled) {
      errors.set('expression', 'ONE does not support expression pedals');
    }
  } else if (config.device === 'duo2') {
    if (config.buttons.length > 2) {
      errors.set('device', 'DUO2 supports only 2 buttons');
    }
    if (config.encoder?.enabled) {
      errors.set('encoder.enabled', 'DUO2 does not support encoder');
    }
    if (config.expression?.exp1?.enabled || config.expression?.exp2?.enabled) {
      errors.set('expression', 'DUO2 does not support expression pedals');
    }
  } else if (config.device === 'nano4') {
    if (config.buttons.length > 4) {
      errors.set('device', 'NANO4 supports only 4 buttons');
    }
    if (config.encoder?.enabled) {
      errors.set('encoder.enabled', 'NANO4 does not support encoder');
    }
    if (config.expression?.exp1?.enabled || config.expression?.exp2?.enabled) {
      errors.set('expression', 'NANO4 does not support expression pedals');
    }
  } else if (config.device === 'mini6') {
    if (config.buttons.length > 6) {
      errors.set('device', 'Mini6 supports only 6 buttons');
    }
    if (config.encoder?.enabled) {
      errors.set('encoder.enabled', 'Mini6 does not support encoder');
    }
    if (config.expression?.exp1?.enabled || config.expression?.exp2?.enabled) {
      errors.set('expression', 'Mini6 does not support expression pedals');
    }
  } else if (config.device === 'std10') {
    if (config.buttons.length > 10) {
      errors.set('device', 'STD10 supports only 10 buttons');
    }
  }
  
  // Validate usb_drive_name
  if (config.usb_drive_name) {
    const err = validators.usbDriveName(config.usb_drive_name);
    if (err) errors.set('usb_drive_name', err);
  }

  // Validate all buttons
  config.buttons.forEach((btn, idx) => {
    const labelError = validators.label(btn.label);
    if (labelError) errors.set(`buttons[${idx}].label`, labelError);

    const msgType = btn.type ?? 'cc';

    if (msgType === 'cc') {
      if (btn.cc !== undefined) {
        const ccError = validators.cc(btn.cc);
        if (ccError) errors.set(`buttons[${idx}].cc`, ccError);
      }
    } else if (msgType === 'note') {
      if (btn.note !== undefined) {
        const noteError = validators.note(btn.note);
        if (noteError) errors.set(`buttons[${idx}].note`, noteError);
      }
      if (btn.velocity_on !== undefined) {
        const velError = validators.velocity(btn.velocity_on);
        if (velError) errors.set(`buttons[${idx}].velocity_on`, velError);
      }
      if (btn.velocity_off !== undefined) {
        const velError = validators.velocity(btn.velocity_off);
        if (velError) errors.set(`buttons[${idx}].velocity_off`, velError);
      }
    } else if (msgType === 'pc') {
      if (btn.program !== undefined) {
        const progError = validators.program(btn.program);
        if (progError) errors.set(`buttons[${idx}].program`, progError);
      }
    } else if (msgType === 'pc_inc' || msgType === 'pc_dec') {
      if (btn.pc_step !== undefined) {
        const stepError = validators.pcStep(btn.pc_step);
        if (stepError) errors.set(`buttons[${idx}].pc_step`, stepError);
      }
    } else if (msgType === 'hid') {
      const validActions = ['send', 'press', 'release', 'delay'];
      if (btn.hid_action !== undefined && !validActions.includes(btn.hid_action)) {
        errors.set(`buttons[${idx}].hid_action`, 'Invalid HID action');
      }
      const validModifiers = ['ctrl', 'shift', 'alt', 'option', 'windows'];
      if (btn.hid_modifier !== undefined && !validModifiers.includes(btn.hid_modifier)) {
        errors.set(`buttons[${idx}].hid_modifier`, 'Invalid modifier');
      }
      if (btn.hid_delay_ms !== undefined) {
        if (!Number.isInteger(btn.hid_delay_ms) || btn.hid_delay_ms < 1 || btn.hid_delay_ms > 5000) {
          errors.set(`buttons[${idx}].hid_delay_ms`, 'Delay must be between 1 and 5000 ms');
        }
      }
    }

    if (btn.channel !== undefined) {
      const chError = validators.channel(btn.channel);
      if (chError) errors.set(`buttons[${idx}].channel`, chError);
    }

    if (btn.flash_ms !== undefined) {
      const fError = validators.flashMs(btn.flash_ms);
      if (fError) errors.set(`buttons[${idx}].flash_ms`, fError);
    }

    if (btn.states && (btn.keytimes === undefined || btn.keytimes <= 1)) {
      errors.set(`buttons[${idx}].states`, 'states requires keytimes > 1');
    }

    // mode: "keytimes" validation (#48): short/long entries + per-button threshold.
    // short[]/long[] are only allowed when mode === 'keytimes'.
    if (btn.mode !== 'keytimes' && (btn.short || btn.long)) {
      errors.set(`buttons[${idx}].mode`, `short/long are only valid when mode is "keytimes"`);
    }
    // Legacy keytimes/states are forbidden on the new mode='keytimes' (use short[]/long[] instead).
    if (btn.mode === 'keytimes') {
      if (btn.keytimes !== undefined) {
        errors.set(`buttons[${idx}].keytimes`, `'keytimes' is not allowed on mode="keytimes" (use short[]/long[])`);
      }
      if (btn.states !== undefined) {
        errors.set(`buttons[${idx}].states`, `'states' is not allowed on mode="keytimes" (use short[]/long[])`);
      }
    }
    if (btn.mode === 'keytimes' && btn.long_press_threshold_ms !== undefined) {
      const t = btn.long_press_threshold_ms;
      if (!Number.isInteger(t) || t < 50 || t > 5000) {
        errors.set(`buttons[${idx}].long_press_threshold_ms`, 'Threshold must be between 50 and 5000 ms');
      }
    }
    if (btn.mode === 'keytimes') {
      // Validate Message objects nested inside short[i].down[j] / up[j] and same for long.
      for (const cycle of ['short', 'long'] as const) {
        const entries = btn[cycle];
        if (!entries) continue;
        entries.forEach((entry, ei) => {
          for (const slot of ['down', 'up'] as const) {
            const messages = entry[slot];
            if (!messages) continue;
            messages.forEach((msg, mi) => {
              const mp = `buttons[${idx}].${cycle}[${ei}].${slot}[${mi}]`;
              switch (msg.type) {
                case 'cc': {
                  const e = validators.cc(msg.cc);
                  if (e) errors.set(`${mp}.cc`, e);
                  const v = validators.withinRange(msg.value, 0, 127);
                  if (v) errors.set(`${mp}.value`, v);
                  break;
                }
                case 'note': {
                  const e = validators.note(msg.note);
                  if (e) errors.set(`${mp}.note`, e);
                  const v = validators.velocity(msg.velocity);
                  if (v) errors.set(`${mp}.velocity`, v);
                  break;
                }
                case 'pc': {
                  const e = validators.program(msg.program);
                  if (e) errors.set(`${mp}.program`, e);
                  break;
                }
                case 'pc_inc':
                case 'pc_dec': {
                  if (msg.step !== undefined) {
                    const e = validators.pcStep(msg.step);
                    if (e) errors.set(`${mp}.step`, e);
                  }
                  break;
                }
                case 'hid': {
                  if (msg.delay_ms !== undefined) {
                    if (!Number.isInteger(msg.delay_ms) || msg.delay_ms < 1 || msg.delay_ms > 5000) {
                      errors.set(`${mp}.delay_ms`, 'Delay must be between 1 and 5000 ms');
                    }
                  }
                  break;
                }
              }
              if (msg.type !== 'hid' && (msg as { channel?: number }).channel !== undefined) {
                const cherr = validators.channel((msg as { channel?: number }).channel!);
                if (cherr) errors.set(`${mp}.channel`, cherr);
              }
            });
          }
        });
      }
    }

    if (btn.keytimes !== undefined) {
      const ktError = validators.keytimes(btn.keytimes);
      if (ktError) errors.set(`buttons[${idx}].keytimes`, ktError);

      if (btn.states) {
        btn.states.forEach((state, si) => {
          const sp = `buttons[${idx}].states[${si}]`;
          if (state.cc !== undefined) {
            const e = validators.cc(state.cc);
            if (e) errors.set(`${sp}.cc`, e);
          }
          if (state.cc_on !== undefined) {
            const e = validators.withinRange(state.cc_on, 0, 127);
            if (e) errors.set(`${sp}.cc_on`, e);
          }
          if (state.cc_off !== undefined) {
            const e = validators.withinRange(state.cc_off, 0, 127);
            if (e) errors.set(`${sp}.cc_off`, e);
          }
          if (state.note !== undefined) {
            const e = validators.note(state.note);
            if (e) errors.set(`${sp}.note`, e);
          }
          if (state.velocity_on !== undefined) {
            const e = validators.velocity(state.velocity_on);
            if (e) errors.set(`${sp}.velocity_on`, e);
          }
          if (state.velocity_off !== undefined) {
            const e = validators.velocity(state.velocity_off);
            if (e) errors.set(`${sp}.velocity_off`, e);
          }
          if (state.program !== undefined) {
            const e = validators.program(state.program);
            if (e) errors.set(`${sp}.program`, e);
          }
          if (state.pc_step !== undefined) {
            const e = validators.pcStep(state.pc_step);
            if (e) errors.set(`${sp}.pc_step`, e);
          }
          if (state.label !== undefined) {
            const e = validators.label(state.label);
            if (e) errors.set(`${sp}.label`, e);
          }
          if (state.hid_delay_ms !== undefined) {
            if (!Number.isInteger(state.hid_delay_ms) || state.hid_delay_ms < 1 || state.hid_delay_ms > 5000) {
              errors.set(`${sp}.hid_delay_ms`, 'Delay must be between 1 and 5000 ms');
            }
          }
        });
      }
    }
  });
  
  // Validate encoder
  if (config.encoder?.enabled) {
    const ccError = validators.cc(config.encoder.cc);
    if (ccError) errors.set('encoder.cc', ccError);

    if (config.encoder.channel !== undefined) {
      const chError = validators.channel(config.encoder.channel);
      if (chError) errors.set('encoder.channel', chError);
    }

    const min = config.encoder.min ?? 0;
    const max = config.encoder.max ?? 127;
    const rangeError = validators.range(min, max);
    if (rangeError) errors.set('encoder.range', rangeError);

    if (config.encoder.initial !== undefined) {
      const initError = validators.withinRange(config.encoder.initial, min, max);
      if (initError) errors.set('encoder.initial', `Initial ${initError.toLowerCase()}`);
    }

    if (config.encoder.push?.enabled) {
      const pushCcError = validators.cc(config.encoder.push.cc);
      if (pushCcError) errors.set('encoder.push.cc', pushCcError);

      if (config.encoder.push.channel !== undefined) {
        const chError = validators.channel(config.encoder.push.channel);
        if (chError) errors.set('encoder.push.channel', chError);
      }
      if (config.encoder.push.cc_on !== undefined) {
        const e = validators.cc(config.encoder.push.cc_on);
        if (e) errors.set('encoder.push.cc_on', e);
      }
      if (config.encoder.push.cc_off !== undefined) {
        const e = validators.cc(config.encoder.push.cc_off);
        if (e) errors.set('encoder.push.cc_off', e);
      }
    }
  }
  
  // Validate expression pedals
  for (const [key, exp] of [['exp1', config.expression?.exp1], ['exp2', config.expression?.exp2]] as const) {
    if (!exp?.enabled) continue;
    const p = `expression.${key}`;

    const ccError = validators.cc(exp.cc);
    if (ccError) errors.set(`${p}.cc`, ccError);

    if (exp.channel !== undefined) {
      const chError = validators.channel(exp.channel);
      if (chError) errors.set(`${p}.channel`, chError);
    }

    const min = exp.min ?? 0;
    const max = exp.max ?? 127;
    const rangeError = validators.range(min, max);
    if (rangeError) errors.set(`${p}.range`, rangeError);
  }
  
  return {
    isValid: errors.size === 0,
    errors,
  };
}
