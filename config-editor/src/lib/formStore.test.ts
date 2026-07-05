import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { formState, loadConfig, normalizeConfig } from './formStore';
import type { MidiCaptainConfig, DeviceType, Page } from './types';

// Minimal valid config: one1 = 1 button per page, so validation stays green.
export function makeConfig(pageCount = 2, device: DeviceType = 'one1'): MidiCaptainConfig {
  const pages = Array.from({ length: pageCount }, (_, i) => ({
    name: `P${i}`,
    buttons: [{ label: `B${i}`, cc: 20 + i, color: 'green' as const }],
  }));
  return { device, active_page: 0, pages };
}

describe('page __uiId stamping', () => {
  it('loadConfig stamps a distinct __uiId on every page', () => {
    loadConfig(makeConfig(2));
    const pages = get(formState).config.pages as Page[];
    expect(typeof pages[0].__uiId).toBe('number');
    expect(typeof pages[1].__uiId).toBe('number');
    expect(pages[0].__uiId).not.toBe(pages[1].__uiId);
  });

  it('normalizeConfig strips page __uiIds from save output', () => {
    loadConfig(makeConfig(1));
    const out = normalizeConfig(get(formState).config);
    expect('__uiId' in out.pages[0]).toBe(false);
  });
});
