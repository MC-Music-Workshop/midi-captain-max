import { describe, it, expect } from 'vitest';
import { validateConfig, validateAllPages, buttonTurnsOff, keytimesUsesCcStep, ledStylesIgnored } from './validation';
import type { MidiCaptainConfig } from './types';

function twoPageConfig(): MidiCaptainConfig {
  return {
    device: 'one1',
    active_page: 0,
    pages: [
      { name: 'Home', buttons: [{ label: 'OK', cc: 20, color: 'green' }] },
      { name: 'Bad', buttons: [{ label: 'OK', cc: 200, color: 'green' }] }, // cc out of range
    ],
  };
}

describe('multi-page validation (D5)', () => {
  it('inline validateConfig only covers the active page (unprefixed keys)', () => {
    expect(validateConfig(twoPageConfig()).isValid).toBe(true);
  });

  it('validateAllPages reports non-active-page errors as prefixed summary lines', () => {
    const lines = validateAllPages(twoPageConfig());
    expect(lines).toHaveLength(1);
    expect(lines[0]).toContain('Page 2 (Bad)');
    expect(lines[0]).toContain('buttons[0].cc');
  });

  it('validateAllPages skips the active page — inline errors own it', () => {
    const cfg = twoPageConfig();
    cfg.active_page = 1;
    expect(validateAllPages(cfg)).toHaveLength(0);
    expect(validateConfig(cfg).isValid).toBe(false);
  });

  it('rejects page names over 24 chars (schema maxLength)', () => {
    const cfg = twoPageConfig();
    cfg.pages[0].name = 'A'.repeat(25);
    cfg.pages[1].buttons[0].cc = 20;
    const result = validateConfig(cfg);
    expect(result.errors.get('name')).toContain('24');
  });
});

describe('page trigger button fields (P4b)', () => {
  // Two valid pages; page indices 0 and 1 exist, 2 does not.
  function pageTriggerConfig(btn: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [
        { name: 'Home', buttons: [{ label: 'GO', color: 'green', ...btn } as never] },
        { name: 'Solo', buttons: [{ label: 'OK', cc: 20, color: 'green' }] },
      ],
    };
  }

  it('rejects page_step < 1 on page_inc', () => {
    const result = validateConfig(pageTriggerConfig({ type: 'page_inc', page_step: 0 }));
    expect(result.errors.get('buttons[0].page_step')).toContain('at least 1');
  });

  it('rejects a page_jump target outside the page list', () => {
    const result = validateConfig(pageTriggerConfig({ type: 'page_jump', page: 2 }));
    expect(result.errors.get('buttons[0].page')).toContain('between 0 and 1');
  });

  it('accepts a valid page_jump target', () => {
    expect(validateConfig(pageTriggerConfig({ type: 'page_jump', page: 1 })).isValid).toBe(true);
  });

  it('ignores stale page fields on a non-page-type button (type-gated)', () => {
    expect(validateConfig(pageTriggerConfig({ type: 'cc', cc: 20, page: 99 })).isValid).toBe(true);
  });
});

describe('keytimes page-switch messages', () => {
  // A keytimes-mode button whose short-press down slot holds one message.
  // Two pages exist (indices 0, 1); index 2+ is out of range.
  function ktConfig(msg: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [
        { name: 'Home', buttons: [{ label: 'GO', color: 'green', mode: 'keytimes', short: [{ down: [msg] }] }] as never },
        { name: 'Solo', buttons: [{ label: 'OK', cc: 20, color: 'green' }] },
      ],
    } as never;
  }

  const base = 'buttons[0].short[0].down[0]';

  it('rejects a keytimes page_jump target outside the page list', () => {
    const result = validateConfig(ktConfig({ type: 'page_jump', page: 2 }));
    expect(result.errors.get(`${base}.page`)).toContain('between 0 and 1');
  });

  it('accepts a valid keytimes page_jump target', () => {
    expect(validateConfig(ktConfig({ type: 'page_jump', page: 1 })).isValid).toBe(true);
  });

  it('rejects a keytimes page_inc step below 1', () => {
    const result = validateConfig(ktConfig({ type: 'page_inc', page_step: 0 }));
    expect(result.errors.get(`${base}.page_step`)).toContain('at least 1');
  });

  it('accepts a valid keytimes page_dec step', () => {
    expect(validateConfig(ktConfig({ type: 'page_dec', page_step: 2 })).isValid).toBe(true);
  });
});

describe('page_control validation (P4b)', () => {
  function pcConfig(pc: unknown): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [{ buttons: [{ label: 'OK', cc: 20, color: 'green' }] }],
      page_control: pc as MidiCaptainConfig['page_control'],
    };
  }

  it('accepts a full valid block', () => {
    const result = validateConfig(pcConfig({
      enabled: true, channel: 0,
      jump: { cc: 20 }, inc: { cc: 21, value: 127, page_step: 1 }, dec: { cc: 22 },
    }));
    expect(result.isValid).toBe(true);
  });

  it('rejects out-of-range slot fields with per-field keys', () => {
    const result = validateConfig(pcConfig({
      jump: { cc: 200 }, inc: { cc: 21, value: 300, page_step: 0 },
    }));
    expect(result.errors.get('page_control.jump.cc')).toContain('127');
    expect(result.errors.get('page_control.inc.value')).toContain('127');
    expect(result.errors.get('page_control.inc.page_step')).toContain('at least 1');
  });

  it('rejects an out-of-range channel', () => {
    const result = validateConfig(pcConfig({ channel: 16, jump: { cc: 20 } }));
    expect(result.errors.get('page_control.channel')).toBeTruthy();
  });
});

describe('per-page global_channel (P4d)', () => {
  function cfgWith(ch: number): MidiCaptainConfig {
    return {
      device: 'one1',
      active_page: 0,
      pages: [{ name: 'Home', global_channel: ch, buttons: [{ label: 'B0', cc: 20, color: 'green' }] }],
    } as never;
  }

  it('rejects a per-page channel above 15 (active page, unprefixed key)', () => {
    expect(validateConfig(cfgWith(16)).errors.get('global_channel')).toContain('between 1 and 16');
  });

  it('accepts a per-page channel in range', () => {
    expect(validateConfig(cfgWith(15)).isValid).toBe(true);
  });

  it('surfaces a bad channel on a NON-active page as a prefixed save-blocker line', () => {
    const cfg = {
      device: 'one1', active_page: 0,
      pages: [
        { name: 'Home', buttons: [{ label: 'B0', cc: 20, color: 'green' }] },
        { name: 'Bad', global_channel: 99, buttons: [{ label: 'B1', cc: 21, color: 'red' }] },
      ],
    } as never;
    const lines = validateAllPages(cfg);
    expect(lines.some(l => l.includes('Page 2 (Bad)') && l.includes('global_channel'))).toBe(true);
  });
});

describe('encoder push (validated like a footswitch)', () => {
  function pushConfig(push: Record<string, unknown>, extra: Partial<MidiCaptainConfig> = {}): MidiCaptainConfig {
    return {
      device: 'std10', active_page: 0,
      pages: [{ buttons: [{ label: 'OK', cc: 20, color: 'green' }],
        encoder: { enabled: true, cc: 11, label: 'ENC', push: { enabled: true, cc: 14, label: 'PUSH', ...push } as never } }],
      ...extra,
    };
  }

  it('accepts a cc_inc push with step fields', () => {
    expect(validateConfig(pushConfig({ type: 'cc_inc', cc_step: 8, cc_min: 0, cc_max: 64 })).isValid).toBe(true);
  });

  it('reports a bad step and range on a cc_dec push under encoder.push.', () => {
    const r = validateConfig(pushConfig({ type: 'cc_dec', cc_step: 0, cc_min: 90, cc_max: 20 }));
    expect(r.errors.get('encoder.push.cc_step')).toContain('between 1 and 127');
    expect(r.errors.get('encoder.push.cc_max')).toContain('greater than min');
  });

  it('ignores step fields on a plain cc push', () => {
    expect(validateConfig(pushConfig({ cc_step: 0 })).isValid).toBe(true);
  });

  it('push label: any characters (schema has no pattern), footswitch label keeps its pattern', () => {
    expect(validateConfig(pushConfig({ label: 'TAP/TMP' })).isValid).toBe(true);
    // Length is characters, not UTF-16 units / bytes (Rust and the schema agree).
    expect(validateConfig(pushConfig({ label: 'ÉCHO-MIX' })).isValid).toBe(true);
    expect(validateConfig(pushConfig({ label: 'TAP🎸TMP!' })).isValid).toBe(true);
    const fs = pushConfig({});
    fs.pages[0].buttons[0].label = 'A/B';
    expect(validateConfig(fs).errors.get('buttons[0].label')).toContain('invalid characters');
  });

  it('rejects fractional cc_on / cc_off (Rust save needs a whole MIDI byte)', () => {
    expect(validateConfig(pushConfig({ cc_on: 1.5 })).errors.get('encoder.push.cc_on')).toContain('integer');
    const fs = pushConfig({});
    (fs.pages[0].buttons[0] as { cc_off?: number }).cc_off = 2.5;
    expect(validateConfig(fs).errors.get('buttons[0].cc_off')).toContain('integer');
  });

  it('allows an 8-char label and rejects 9', () => {
    expect(validateConfig(pushConfig({ label: 'ABCDEFGH' })).isValid).toBe(true);
    expect(validateConfig(pushConfig({ label: 'ABCDEFGHI' })).errors.get('encoder.push.label')).toContain('8 characters');
  });

  it('needs no color (the push has no LED)', () => {
    const cfg = pushConfig({});
    expect('color' in cfg.pages[0].encoder!.push!).toBe(false);
    expect(validateConfig(cfg).isValid).toBe(true);
  });

  it('validates out-of-range CC ON/OFF values', () => {
    const r = validateConfig(pushConfig({ cc_on: 128, cc_off: -1 }));
    expect(r.errors.get('encoder.push.cc_on')).toContain('between 0 and 127');
    expect(r.errors.get('encoder.push.cc_off')).toContain('between 0 and 127');
  });

  it('validates extra messages and keytimes entries at push paths', () => {
    const extras = validateConfig(pushConfig({ messages_on: [{ type: 'cc_inc' }] }));
    expect(extras.errors.get('encoder.push.messages_on[0].cc')).toBe('Set the CC to step');
    const kt = validateConfig(pushConfig({ mode: 'keytimes', short: [{ down: [{ type: 'cc', cc: 200, value: 1 }] }] }));
    expect(kt.errors.get('encoder.push.short[0].down[0].cc')).toContain('between 0 and 127');
  });

  it('skips a disabled push', () => {
    expect(validateConfig(pushConfig({ enabled: false, label: '' })).isValid).toBe(true);
  });

  it('validates an enabled push even when the rotary is disabled (firmware still uses it)', () => {
    const cfg = pushConfig({ type: 'cc_inc', cc_step: 0 });
    cfg.pages[0].encoder!.enabled = false;
    expect(validateConfig(cfg).errors.get('encoder.push.cc_step')).toContain('between 1 and 127');
  });

  it('validateAllPages reports push errors on a non-active page', () => {
    const cfg = pushConfig({});
    cfg.pages.push({ name: 'Two', buttons: [{ label: 'OK', cc: 20, color: 'green' }],
      encoder: { enabled: true, cc: 11, label: 'ENC', push: { enabled: true, label: 'PUSH', type: 'cc_inc', cc_step: 0 } } });
    const lines = validateAllPages(cfg);
    expect(lines.some(l => l.includes('Page 2 (Two)') && l.includes('encoder.push.cc_step'))).toBe(true);
  });
});

describe('cc_inc / cc_dec fields (#11)', () => {
  function ccStepConfig(btn: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'VOL', color: 'green', type: 'cc_inc', cc: 7, ...btn } as never] }],
    };
  }

  it('accepts a full STEP-mode button', () => {
    const r = validateConfig(ccStepConfig({ cc_step: 5, cc_min: 10, cc_max: 100, cc_wrap: false, cc_initial: 50 }));
    expect(r.isValid).toBe(true);
  });

  it('accepts a full SLOT-mode button', () => {
    const r = validateConfig(ccStepConfig({ cc_slots: 4, cc_slot_colors: ['red', 'green', 'blue', 'yellow'],
                                             cc_slot_names: ['MARSH', 'FENDER', '', 'MESA'] }));
    expect(r.isValid).toBe(true);
  });

  it('rejects cc_step outside 1-127', () => {
    expect(validateConfig(ccStepConfig({ cc_step: 0 })).errors.get('buttons[0].cc_step')).toContain('between 1 and 127');
    expect(validateConfig(ccStepConfig({ cc_step: 128 })).errors.get('buttons[0].cc_step')).toContain('between 1 and 127');
  });

  it('rejects cc_slots outside 2-16', () => {
    expect(validateConfig(ccStepConfig({ cc_slots: 1 })).errors.get('buttons[0].cc_slots')).toContain('between 2 and 16');
    expect(validateConfig(ccStepConfig({ cc_slots: 17 })).errors.get('buttons[0].cc_slots')).toContain('between 2 and 16');
  });

  it('rejects min >= max on cc_max', () => {
    expect(validateConfig(ccStepConfig({ cc_min: 50, cc_max: 50 })).errors.get('buttons[0].cc_max')).toContain('greater than min');
  });

  it('rejects cc_initial outside min..max', () => {
    expect(validateConfig(ccStepConfig({ cc_min: 10, cc_max: 20, cc_initial: 64 })).errors.get('buttons[0].cc_initial')).toContain('between 10 and 20');
  });

  it('rejects a slot name over 6 chars or with bad characters, keyed per slot', () => {
    const r = validateConfig(ccStepConfig({ cc_slots: 2, cc_slot_names: ['TOOLONG', 'a+b'] }));
    expect(r.errors.get('buttons[0].cc_slot_names[0]')).toContain('6 characters');
    expect(r.errors.get('buttons[0].cc_slot_names[1]')).toContain('invalid characters');
  });

  it('validates the shared fields on a keytimes button with cc_inc entries', () => {
    const cfg: MidiCaptainConfig = {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'AMP', color: 'green', mode: 'keytimes', cc: 30, cc_slots: 1,
                             short: [{ down: [{ type: 'cc_inc' }] }] } as never] }],
    };
    const r = validateConfig(cfg);
    expect(r.errors.get('buttons[0].cc_slots')).toContain('between 2 and 16');
    // The direction-only entry itself has nothing to flag.
    expect([...r.errors.keys()].some(k => k.includes('short[0]'))).toBe(false);
  });

  it('ignores stale cc-step fields on a plain cc button (type-gated)', () => {
    const cfg: MidiCaptainConfig = {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'OK', cc: 20, color: 'green', cc_step: 0, cc_slots: 99, cc_min: 100, cc_max: 5 } as never] }],
    };
    expect(validateConfig(cfg).isValid).toBe(true);
  });
});

describe('mode flip away from keytimes', () => {
  it('does not flag stale short/long on a non-keytimes button (normalize strips them on save)', () => {
    const cfg: MidiCaptainConfig = {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'AMP', color: 'green', mode: 'flash', type: 'cc_inc', cc: 20,
                             short: [{ down: [{ type: 'cc_inc' }] }] } as never] }],
    };
    const r = validateConfig(cfg);
    expect(r.isValid).toBe(true);
    expect(r.errors.has('buttons[0].mode')).toBe(false);
  });
});

describe('keytimes host sync (#200)', () => {
  function syncConfig(btn: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'KT', color: 'green', mode: 'keytimes', ...btn }] as never }],
    } as never;
  }

  it('accepts listen CCs and receive values in range', () => {
    const cfg = syncConfig({ short_cc_receive: 20, long_cc_receive: 21, short: [{ rx_value: 0 }], long: [{ rx_value: 127 }] });
    expect(validateConfig(cfg).isValid).toBe(true);
  });

  it('rejects a listen CC above 127', () => {
    const result = validateConfig(syncConfig({ long_cc_receive: 128 }));
    expect(result.errors.get('buttons[0].long_cc_receive')).toContain('between 0 and 127');
  });

  it('rejects a receive value above 127', () => {
    const result = validateConfig(syncConfig({ short_cc_receive: 20, short: [{ rx_value: 0 }, { rx_value: 200 }] }));
    expect(result.errors.get('buttons[0].short[1].rx_value')).toContain('between 0 and 127');
  });
});

describe('extra messages (messages_on / messages_off)', () => {
  function withButton(btn: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'X', color: 'green', ...btn }] as never }],
    } as never;
  }

  it('buttonTurnsOff follows the firmware: toggle, momentary (not HID), CC select deselect', () => {
    const turnsOff = (btn: Record<string, unknown>) => buttonTurnsOff({ label: 'X', color: 'green', ...btn } as never);
    expect(turnsOff({})).toBe(true);                                  // cc, default toggle
    expect(turnsOff({ type: 'note', mode: 'momentary' })).toBe(true);
    expect(turnsOff({ type: 'pc' })).toBe(false);                     // pc defaults to flash
    expect(turnsOff({ type: 'pc', mode: 'momentary' })).toBe(true);
    expect(turnsOff({ type: 'hid', mode: 'momentary' })).toBe(false);
    expect(turnsOff({ type: 'hid', mode: 'toggle' })).toBe(true);
    expect(turnsOff({ type: 'page_inc', mode: 'toggle' })).toBe(false);
    expect(turnsOff({ type: 'cc', mode: 'select', select_repress: 'resend' })).toBe(false);
    expect(turnsOff({ type: 'cc', mode: 'select', select_repress: 'deselect' })).toBe(true);
  });

  it('validates each message like a keytimes entry', () => {
    const r = validateConfig(withButton({ cc: 20, messages_on: [{ type: 'pc', program: 5 }, { type: 'cc', cc: 200, value: 0 }] }));
    expect(r.errors.has('buttons[0].messages_on[0].program')).toBe(false);
    expect(r.errors.get('buttons[0].messages_on[1].cc')).toBeDefined();
  });

  it('requires a CC on a CC+/CC- extra (there are no shared settings to fall back on)', () => {
    const r = validateConfig(withButton({ cc: 20, messages_off: [{ type: 'cc_inc' }] }));
    expect(r.errors.get('buttons[0].messages_off[0].cc')).toContain('Set the CC');
  });

  it('validates a CC+/CC- with its own CC like a CC+ button', () => {
    const ok = validateConfig(withButton({ cc: 20, messages_on: [{ type: 'cc_dec', cc: 30, cc_step: 5, cc_min: 10, cc_max: 90 }] }));
    expect(ok.isValid).toBe(true);
    const bad = validateConfig(withButton({ cc: 20, messages_on: [{ type: 'cc_inc', cc: 30, cc_min: 90, cc_max: 10 }] }));
    expect(bad.errors.get('buttons[0].messages_on[0].cc_max')).toContain('greater than min');
  });

  it('a keytimes CC+/CC- with its own CC needs no shared settings', () => {
    const btn = (msg: Record<string, unknown>) =>
      ({ label: 'X', color: 'green', mode: 'keytimes', short: [{ down: [msg] }] }) as never;
    expect(keytimesUsesCcStep(btn({ type: 'cc_inc' }))).toBe(true);
    expect(keytimesUsesCcStep(btn({ type: 'cc_inc', cc: 30 }))).toBe(false);
  });

  it('ignores messages_off on a button that never turns off (save strips it)', () => {
    const r = validateConfig(withButton({ type: 'pc', program: 1, messages_off: [{ type: 'cc', cc: 200, value: 0 }] }));
    expect(r.isValid).toBe(true);
  });
});

describe('per-LED styles (led_on / led_off / entry led)', () => {
  function withButton(btn: Record<string, unknown>): MidiCaptainConfig {
    return {
      device: 'one1', active_page: 0,
      pages: [{ buttons: [{ label: 'X', color: 'green', cc: 20, ...btn }] as never }],
    } as never;
  }

  it('accepts a full style and the speed bounds', () => {
    const r = validateConfig(withButton({
      led_on: { pixels: ['red', 'off', 'white'], animation: 'spin', speed_ms: 50 },
      led_off: { animation: 'flash', speed_ms: 5000 },
    }));
    expect(r.isValid).toBe(true);
  });

  it('rejects speed_ms out of range on a moving animation', () => {
    const r = validateConfig(withButton({
      led_on: { animation: 'flash', speed_ms: 49 },
      led_off: { animation: 'spin', speed_ms: 5001 },
    }));
    expect(r.errors.get('buttons[0].led_on.speed_ms')).toContain('between 50 and 5000');
    expect(r.errors.get('buttons[0].led_off.speed_ms')).toContain('between 50 and 5000');
  });

  it('ignores a stale speed_ms on a solid style (save strips it)', () => {
    const r = validateConfig(withButton({ led_on: { speed_ms: 1 } }));
    expect(r.errors.has('buttons[0].led_on.speed_ms')).toBe(false);
  });

  it('rejects pixels that are not exactly 3 valid colors', () => {
    for (const pixels of [['red', 'blue'], ['red', 'blue', 'green', 'white'], ['red', 'pink', 'blue']]) {
      const r = validateConfig(withButton({ led_on: { pixels } }));
      expect(r.errors.get('buttons[0].led_on.pixels')).toContain('3 LEDs');
    }
  });

  it('rejects an unknown animation', () => {
    const r = validateConfig(withButton({ led_off: { animation: 'pulse' } }));
    expect(r.errors.has('buttons[0].led_off.animation')).toBe(true);
  });

  it('validates keytimes entry led under the entry path', () => {
    const r = validateConfig(withButton({
      mode: 'keytimes',
      short: [{ led: { pixels: ['red'] } }],
      long: [{ led: { animation: 'flash', speed_ms: 10 } }],
    }));
    expect(r.errors.has('buttons[0].short[0].led.pixels')).toBe(true);
    expect(r.errors.get('buttons[0].long[0].led.speed_ms')).toContain('between 50 and 5000');
  });

  it('skips led_on/led_off where the firmware ignores them', () => {
    const bad = { led_on: { pixels: ['red'] }, led_off: { animation: 'flash', speed_ms: 1 } };
    expect(validateConfig(withButton({ mode: 'keytimes', ...bad })).isValid).toBe(true);
    expect(validateConfig(withButton({ type: 'cc_inc', cc_slots: 4, ...bad })).isValid).toBe(true);
    // STEP-mode CC+ honors them.
    expect(validateConfig(withButton({ type: 'cc_inc', ...bad })).isValid).toBe(false);
  });

  it('ledStylesIgnored: keytimes and CC+/CC- slot buttons only', () => {
    expect(ledStylesIgnored({ label: 'X', mode: 'keytimes' } as never)).toBe(true);
    expect(ledStylesIgnored({ label: 'X', type: 'cc_dec', cc_slots: 3 } as never)).toBe(true);
    expect(ledStylesIgnored({ label: 'X', type: 'cc_dec' } as never)).toBe(false);
    expect(ledStylesIgnored({ label: 'X', type: 'pc', mode: 'flash' } as never)).toBe(false);
  });
});
