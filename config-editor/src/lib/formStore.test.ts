import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { formState, loadConfig, normalizeConfig, setActivePage, isDirty, canUndo, undo, currentPage, addPage, duplicatePage, deletePage, movePage, updatePageField, PAGE_CAP, addPageFromTemplate } from './formStore';
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

describe('duplicatePage', () => {
  it('inserts a deep copy after the source and switches to it', () => {
    loadConfig(makeConfig(2));
    duplicatePage(0);
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(3);
    expect(cfg.pages[1].name).toBe('P0');
    expect(cfg.active_page).toBe(1);
    // Deep copy: editing the duplicate must not touch the source.
    cfg.pages[1].buttons[0].label = 'EDIT';
    expect(cfg.pages[0].buttons[0].label).toBe('B0');
  });

  it('gives the duplicate a fresh __uiId (no shared {#each} keys)', () => {
    loadConfig(makeConfig(1));
    duplicatePage(0);
    const pages = get(formState).config.pages as Page[];
    expect(typeof pages[1].__uiId).toBe('number');
    expect(pages[1].__uiId).not.toBe(pages[0].__uiId);
  });

  it('no-ops at the cap', () => {
    loadConfig(makeConfig(20));
    duplicatePage(0);
    expect(get(formState).config.pages).toHaveLength(20);
    expect(get(isDirty)).toBe(false);
  });
});

describe('deletePage', () => {
  it('refuses to delete the last page (D3)', () => {
    loadConfig(makeConfig(1));
    deletePage(0);
    expect(get(formState).config.pages).toHaveLength(1);
    expect(get(isDirty)).toBe(false);
  });

  it('re-clamps active_page when deleting the active last page', () => {
    loadConfig(makeConfig(3));
    setActivePage(2);
    deletePage(2);
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(2);
    expect(cfg.active_page).toBe(1);
  });

  it('keeps the active page stable when deleting an earlier page', () => {
    loadConfig(makeConfig(3));
    setActivePage(2);
    deletePage(0);
    expect(get(formState).config.active_page).toBe(1);
    expect(get(currentPage).name).toBe('P2');
  });
});

describe('movePage', () => {
  it('reorders pages', () => {
    loadConfig(makeConfig(3));
    movePage(0, 2);
    expect(get(formState).config.pages.map(p => p.name)).toEqual(['P1', 'P2', 'P0']);
  });

  it('active_page follows the moved page', () => {
    loadConfig(makeConfig(3)); // active = 0 (P0)
    movePage(0, 2);
    expect(get(formState).config.active_page).toBe(2);
    expect(get(currentPage).name).toBe('P0');
  });

  it('active_page follows when another page moves across it', () => {
    loadConfig(makeConfig(3));
    setActivePage(1); // P1
    movePage(2, 0);   // P2 jumps to front; P1 shifts right
    expect(get(currentPage).name).toBe('P1');
    expect(get(formState).config.active_page).toBe(2);
  });

  it('no-ops on invalid indices', () => {
    loadConfig(makeConfig(2));
    movePage(0, 5);
    expect(get(isDirty)).toBe(false);
  });
});

describe('updatePageField (D6)', () => {
  it('writes to the active page only', () => {
    loadConfig(makeConfig(2));
    setActivePage(1);
    updatePageField('name', 'Solo');
    const cfg = get(formState).config;
    expect(cfg.pages[1].name).toBe('Solo');
    expect(cfg.pages[0].name).toBe('P0');
    expect(get(isDirty)).toBe(true);
  });
});

describe('normalizeConfig page fields', () => {
  it('strips empty page names from save output', () => {
    loadConfig(makeConfig(1));
    updatePageField('name', '');
    const out = normalizeConfig(get(formState).config);
    expect('name' in out.pages[0]).toBe(false);
  });

  it('normalizeConfig drops a per-page global_channel that was cleared to undefined', () => {
    const cfg = {
      device: 'one1', active_page: 0,
      pages: [{ name: 'Home', global_channel: undefined, buttons: [{ label: 'B0', cc: 20, color: 'green' }] }],
    } as never;
    const out = normalizeConfig(cfg);
    expect('global_channel' in out.pages[0]).toBe(false);
  });
});

describe('addPageFromTemplate (P4d)', () => {
  it('inserts the page after the active page, stamps a fresh __uiId, and switches to it', () => {
    // Seed a 1-page one1 config via the same load path the other CRUD tests use.
    loadConfig({ device: 'one1', active_page: 0,
      pages: [{ name: 'Home', buttons: [{ label: 'B0', cc: 20, color: 'green' }] }] } as never);
    addPageFromTemplate({ name: 'Tmpl', buttons: [{ label: 'T0', cc: 30, color: 'red' }] });
    const cfg = get(formState).config;
    expect(cfg.pages).toHaveLength(2);
    expect(cfg.pages[1].name).toBe('Tmpl');
    expect(cfg.active_page).toBe(1);
    expect(typeof (cfg.pages[1] as any).__uiId).toBe('number');
  });

  it('is a no-op at the 20-page cap', () => {
    const pages = Array.from({ length: PAGE_CAP }, (_, i) =>
      ({ name: `P${i}`, buttons: [{ label: 'B', cc: 20, color: 'green' }] }));
    loadConfig({ device: 'one1', active_page: 0, pages } as never);
    addPageFromTemplate({ buttons: [{ label: 'X', cc: 1, color: 'green' }] });
    expect(get(formState).config.pages).toHaveLength(PAGE_CAP);
  });
});
