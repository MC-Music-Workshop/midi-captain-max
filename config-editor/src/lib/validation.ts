import type { MidiCaptainConfig, Page, ButtonConfig } from './types';

// True when any short/long entry on a keytimes button fires cc_inc/cc_dec (#11).
// Such a button carries the button-level cc-step fields (cc, cc_step | cc_slots,
// cc_min/cc_max, cc_wrap, cc_initial, slot tables) shared by every entry.
export function keytimesUsesCcStep(btn: ButtonConfig): boolean {
  for (const cycle of [btn.short, btn.long]) {
    for (const entry of cycle ?? []) {
      for (const msg of [...(entry.down ?? []), ...(entry.up ?? [])]) {
        if (msg.type === 'cc_inc' || msg.type === 'cc_dec') return true;
      }
    }
  }
  return false;
}

export const CC_SLOTS_MIN = 2;
export const CC_SLOTS_MAX = 16;

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

  ccStep: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Step must be an integer';
    if (value < 1 || value > 127) return 'Step must be between 1 and 127';
    return null;
  },

  ccSlots: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Slots must be an integer';
    if (value < CC_SLOTS_MIN || value > CC_SLOTS_MAX) return `Slots must be between ${CC_SLOTS_MIN} and ${CC_SLOTS_MAX}`;
    return null;
  },

  // No upper bound: the schema has none — the firmware wraps at the ends.
  pageStep: (value: number): string | null => {
    if (!Number.isInteger(value)) return 'Step must be an integer';
    if (value < 1) return 'Step must be at least 1';
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

// cc_inc/cc_dec (#11) button-level fields. Called for plain cc_inc/cc_dec buttons
// and for keytimes buttons whose entries fire cc_inc/cc_dec (the fields ride on
// the button). Mirrors the Rust ranges in config.rs so bad values fail inline.
function validateCcStep(btn: ButtonConfig, idx: number, errors: Map<string, string>) {
  const p = `buttons[${idx}]`;
  if (btn.cc !== undefined) {
    const e = validators.cc(btn.cc);
    if (e) errors.set(`${p}.cc`, e);
  }
  if (btn.cc_step !== undefined) {
    const e = validators.ccStep(btn.cc_step);
    if (e) errors.set(`${p}.cc_step`, e);
  }
  if (btn.cc_slots !== undefined) {
    const e = validators.ccSlots(btn.cc_slots);
    if (e) errors.set(`${p}.cc_slots`, e);
  }
  const lo = btn.cc_min ?? 0;
  const hi = btn.cc_max ?? 127;
  if (btn.cc_min !== undefined) {
    const e = validators.withinRange(btn.cc_min, 0, 127);
    if (e) errors.set(`${p}.cc_min`, `Min: ${e.toLowerCase()}`);
  }
  if (btn.cc_max !== undefined) {
    const e = validators.withinRange(btn.cc_max, 0, 127);
    if (e) errors.set(`${p}.cc_max`, `Max: ${e.toLowerCase()}`);
  }
  if (lo >= hi) {
    errors.set(`${p}.cc_max`, 'Max must be greater than min');
  }
  if (btn.cc_initial !== undefined) {
    const e = validators.withinRange(btn.cc_initial, lo, hi);
    if (e) errors.set(`${p}.cc_initial`, `Initial ${e.toLowerCase()}`);
  }
  if (btn.cc_slot_names) {
    btn.cc_slot_names.forEach((name, si) => {
      if (name.length > 6) {
        errors.set(`${p}.cc_slot_names[${si}]`, 'Slot name must be 6 characters or less');
      } else if (name !== '' && !/^[\w\s-]+$/.test(name)) {
        errors.set(`${p}.cc_slot_names[${si}]`, 'Slot name contains invalid characters');
      }
    });
  }
}

// Validate one page's control-surface data against the device. Keys are
// UNPREFIXED (buttons[i]…, encoder…, expression…) — for the active page they
// feed the inline error Map that components look up by path (locked convention).
export function validatePage(page: Page, device: MidiCaptainConfig['device'], pageCount: number): Map<string, string> {
  const errors = new Map<string, string>();
  const buttons = page.buttons ?? [];
  const encoder = page.encoder;
  const expression = page.expression;

  // Page name: editor-facing metadata, schema caps at 24 chars.
  if (page.name !== undefined && page.name.length > 24) {
    errors.set('name', 'Page name must be 24 characters or less');
  }

  // Per-page MIDI channel override (0-15). Absent = inherit device default.
  if (page.global_channel !== undefined) {
    const chError = validators.channel(page.global_channel);
    if (chError) errors.set('global_channel', chError);
  }

  // Device-specific validation
  if (device === 'one1') {
    if (buttons.length > 1) {
      errors.set('device', 'ONE supports only 1 button');
    }
    if (encoder?.enabled) {
      errors.set('encoder.enabled', 'ONE does not support encoder');
    }
    if (expression?.exp1?.enabled || expression?.exp2?.enabled) {
      errors.set('expression', 'ONE does not support expression pedals');
    }
  } else if (device === 'duo2') {
    if (buttons.length > 2) {
      errors.set('device', 'DUO2 supports only 2 buttons');
    }
    if (encoder?.enabled) {
      errors.set('encoder.enabled', 'DUO2 does not support encoder');
    }
    if (expression?.exp1?.enabled || expression?.exp2?.enabled) {
      errors.set('expression', 'DUO2 does not support expression pedals');
    }
  } else if (device === 'nano4') {
    if (buttons.length > 4) {
      errors.set('device', 'NANO4 supports only 4 buttons');
    }
    if (encoder?.enabled) {
      errors.set('encoder.enabled', 'NANO4 does not support encoder');
    }
    if (expression?.exp1?.enabled || expression?.exp2?.enabled) {
      errors.set('expression', 'NANO4 does not support expression pedals');
    }
  } else if (device === 'mini6') {
    if (buttons.length > 6) {
      errors.set('device', 'Mini6 supports only 6 buttons');
    }
    if (encoder?.enabled) {
      errors.set('encoder.enabled', 'Mini6 does not support encoder');
    }
    if (expression?.exp1?.enabled || expression?.exp2?.enabled) {
      errors.set('expression', 'Mini6 does not support expression pedals');
    }
  } else if (device === 'std10') {
    if (buttons.length > 10) {
      errors.set('device', 'STD10 supports only 10 buttons');
    }
  }

  // Validate all buttons
  buttons.forEach((btn, idx) => {
    const labelError = validators.label(btn.label);
    if (labelError) errors.set(`buttons[${idx}].label`, labelError);

    const msgType = btn.type ?? 'cc';

    if (msgType === 'cc') {
      if (btn.cc !== undefined) {
        const ccError = validators.cc(btn.cc);
        if (ccError) errors.set(`buttons[${idx}].cc`, ccError);
      }
      if (btn.cc_receive !== undefined) {
        const e = validators.cc(btn.cc_receive);
        if (e) errors.set(`buttons[${idx}].cc_receive`, e);
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
    } else if ((msgType === 'cc_inc' || msgType === 'cc_dec') && btn.mode !== 'keytimes') {
      validateCcStep(btn, idx, errors);
    } else if (msgType === 'page_inc' || msgType === 'page_dec') {
      if (btn.page_step !== undefined) {
        const stepError = validators.pageStep(btn.page_step);
        if (stepError) errors.set(`buttons[${idx}].page_step`, stepError);
      }
    } else if (msgType === 'page_jump') {
      // Cross-field: the firmware clamps a bad target, the editor fails loud
      // (P1 asymmetry rule). 0-based, so max is pageCount - 1.
      if (btn.page !== undefined) {
        if (!Number.isInteger(btn.page) || btn.page < 0 || btn.page >= pageCount) {
          errors.set(`buttons[${idx}].page`, `Target page must be between 0 and ${pageCount - 1} (0-based)`);
        }
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
    // NOTE: stale short[]/long[] on a NON-keytimes button are deliberately not an
    // error. The form keeps them across a mode flip (like select_group) so switching
    // back restores the cycle, and normalizeButton strips them at save time. A rule
    // here used to set a `buttons[i].mode` error that no component rendered, leaving
    // "Fix errors to save" with nothing visible to fix.
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
      // cc_inc/cc_dec entries (#11) are direction-only; their cc/range/slot fields
      // ride on the button and validate like a plain cc_inc button.
      if (keytimesUsesCcStep(btn)) validateCcStep(btn, idx, errors);
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
                case 'cc_inc':
                case 'cc_dec':
                  // No per-message fields; see validateCcStep on the button above.
                  break;
                case 'page_inc':
                case 'page_dec': {
                  if (msg.page_step !== undefined) {
                    const e = validators.pageStep(msg.page_step);
                    if (e) errors.set(`${mp}.page_step`, e);
                  }
                  break;
                }
                case 'page_jump': {
                  // Cross-field: 0-based target, max is pageCount - 1. Firmware
                  // clamps; the editor fails loud (P1 asymmetry rule).
                  if (msg.page !== undefined) {
                    if (!Number.isInteger(msg.page) || msg.page < 0 || msg.page >= pageCount) {
                      errors.set(`${mp}.page`, `Target page must be between 0 and ${pageCount - 1} (0-based)`);
                    }
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
  if (encoder?.enabled) {
    const ccError = validators.cc(encoder.cc);
    if (ccError) errors.set('encoder.cc', ccError);

    if (encoder.channel !== undefined) {
      const chError = validators.channel(encoder.channel);
      if (chError) errors.set('encoder.channel', chError);
    }

    const min = encoder.min ?? 0;
    const max = encoder.max ?? 127;
    const rangeError = validators.range(min, max);
    if (rangeError) errors.set('encoder.range', rangeError);

    if (encoder.initial !== undefined) {
      const initError = validators.withinRange(encoder.initial, min, max);
      if (initError) errors.set('encoder.initial', `Initial ${initError.toLowerCase()}`);
    }

    if (encoder.push?.enabled) {
      const pushCcError = validators.cc(encoder.push.cc);
      if (pushCcError) errors.set('encoder.push.cc', pushCcError);

      if (encoder.push.channel !== undefined) {
        const chError = validators.channel(encoder.push.channel);
        if (chError) errors.set('encoder.push.channel', chError);
      }
      if (encoder.push.cc_on !== undefined) {
        const e = validators.cc(encoder.push.cc_on);
        if (e) errors.set('encoder.push.cc_on', e);
      }
      if (encoder.push.cc_off !== undefined) {
        const e = validators.cc(encoder.push.cc_off);
        if (e) errors.set('encoder.push.cc_off', e);
      }
    }
  }
  
  // Validate expression pedals
  for (const [key, exp] of [['exp1', expression?.exp1], ['exp2', expression?.exp2]] as const) {
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

  return errors;
}

export function validateConfig(config: MidiCaptainConfig): ValidationResult {
  const errors = new Map<string, string>();

  // Device-wide fields.
  if (config.usb_drive_name) {
    const err = validators.usbDriveName(config.usb_drive_name);
    if (err) errors.set('usb_drive_name', err);
  }

  // MIDI-IN CC page control (#15 P3b): device-wide, so it validates here, not
  // per page. Mirrors the Rust ranges in config.rs so bad values fail inline
  // instead of as an opaque save error. channel may be null (= any channel).
  const pc = config.page_control;
  if (pc) {
    if (pc.channel !== undefined && pc.channel !== null) {
      const chError = validators.channel(pc.channel);
      if (chError) errors.set('page_control.channel', chError);
    }
    if (pc.jump?.cc !== undefined) {
      const ccError = validators.cc(pc.jump.cc);
      if (ccError) errors.set('page_control.jump.cc', ccError);
    }
    for (const key of ['inc', 'dec'] as const) {
      const slot = pc[key];
      if (!slot) continue;
      const p = `page_control.${key}`;
      if (slot.cc !== undefined) {
        const ccError = validators.cc(slot.cc);
        if (ccError) errors.set(`${p}.cc`, ccError);
      }
      if (slot.value !== undefined) {
        const vError = validators.withinRange(slot.value, 0, 127);
        if (vError) errors.set(`${p}.value`, vError);
      }
      if (slot.page_step !== undefined) {
        const sError = validators.pageStep(slot.page_step);
        if (sError) errors.set(`${p}.page_step`, sError);
      }
    }
  }

  // The editor renders the active page; its errors stay unprefixed so they
  // match the paths components use for both updateField and error lookups.
  const pages = config.pages ?? [];
  const pageCount = pages.length || 1;
  const apIdx = pages.length
    ? Math.max(0, Math.min(pages.length - 1, config.active_page ?? 0))
    : 0;
  const page = pages[apIdx] ?? { buttons: [] };
  for (const [key, msg] of validatePage(page, config.device, pageCount)) {
    errors.set(key, msg);
  }

  return {
    isValid: errors.size === 0,
    errors,
  };
}

// D5 save-path check: every NON-active page, as human-readable summary lines
// for the footer error list ("Page 2 (Bad): buttons[0].cc: CC must be…").
// The active page is skipped — its errors surface inline via validateConfig.
export function validateAllPages(config: MidiCaptainConfig): string[] {
  const lines: string[] = [];
  const pages = config.pages ?? [];
  const pageCount = pages.length || 1;
  const apIdx = pages.length
    ? Math.max(0, Math.min(pages.length - 1, config.active_page ?? 0))
    : 0;
  pages.forEach((page, i) => {
    if (i === apIdx) return;
    for (const [key, msg] of validatePage(page, config.device, pageCount)) {
      const label = page.name ? `Page ${i + 1} (${page.name})` : `Page ${i + 1}`;
      lines.push(`${label}: ${key}: ${msg}`);
    }
  });
  return lines;
}
