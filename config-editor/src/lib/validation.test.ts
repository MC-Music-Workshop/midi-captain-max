import { describe, it, expect } from 'vitest';
import { validateConfig, validateAllPages } from './validation';
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
