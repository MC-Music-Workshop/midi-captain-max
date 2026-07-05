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
