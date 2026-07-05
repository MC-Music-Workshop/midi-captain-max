import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { formState, loadConfig, normalizeConfig, setActivePage, isDirty, canUndo, undo, currentPage, addPage } from './formStore';
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

describe('setActivePage', () => {
  it('switches the rendered page and marks dirty (D2)', () => {
    loadConfig(makeConfig(3));
    setActivePage(2);
    expect(get(formState).config.active_page).toBe(2);
    expect(get(currentPage).name).toBe('P2');
    expect(get(isDirty)).toBe(true);
  });

  it('clamps out-of-range indices', () => {
    loadConfig(makeConfig(3));
    setActivePage(99);
    expect(get(formState).config.active_page).toBe(2);
    setActivePage(-5);
    expect(get(formState).config.active_page).toBe(0);
  });

  it('no-ops when selecting the already-active page', () => {
    loadConfig(makeConfig(2));
    setActivePage(0);
    expect(get(isDirty)).toBe(false);
    expect(get(canUndo)).toBe(false);
  });

  it('is a single undo checkpoint', () => {
    loadConfig(makeConfig(2));
    setActivePage(1);
    expect(get(canUndo)).toBe(true);
    undo();
    expect(get(formState).config.active_page).toBe(0);
  });
});

describe('addPage', () => {
  it('appends a device-sized page and switches to it', () => {
    loadConfig(makeConfig(1)); // one1 → 1 button per page
    addPage();
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(2);
    expect(cfg.active_page).toBe(1);
    expect(cfg.pages[1].buttons).toHaveLength(1);
    expect(get(isDirty)).toBe(true);
  });

  it('no-ops at the 20-page cap', () => {
    loadConfig(makeConfig(20));
    addPage();
    expect(get(formState).config.pages).toHaveLength(20);
    expect(get(isDirty)).toBe(false);
  });

  it('is undoable', () => {
    loadConfig(makeConfig(1));
    addPage();
    undo();
    expect(get(formState).config.pages).toHaveLength(1);
  });
});
