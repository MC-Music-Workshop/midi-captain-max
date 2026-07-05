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
