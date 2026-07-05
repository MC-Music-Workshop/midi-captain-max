import type { Page } from '@playwright/test';

// Minimal valid config: one1 = 1 button per page, so validation stays green.
// Mirrors makeConfig in src/lib/formStore.test.ts.
export function oneButtonConfig() {
  return {
    device: 'one1',
    active_page: 0,
    pages: [{ buttons: [{ label: 'B0', cc: 20, color: 'green' }] }],
  };
}

// Two pages with distinct button data, so tests can tell which page the form
// is rendering.
export function twoPageConfig() {
  return {
    device: 'one1',
    active_page: 0,
    pages: [
      { name: 'A', buttons: [{ label: 'B0', cc: 20, color: 'green' }] },
      { name: 'B', buttons: [{ label: 'B1', cc: 30, color: 'red' }] },
    ],
  };
}

// Duplicate the active page through the Edit Pages modal (the bar itself has
// no management buttons).
export async function duplicateCurrentPage(page: Page) {
  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  await dialog.getByRole('button', { name: 'Duplicate page' }).click();
  await dialog.getByRole('button', { name: 'Done' }).click();
}

// Install a window.__TAURI_INTERNALS__ mock before any app code runs, then
// load the app and wait for the form to render. invoke() calls that would hit
// the Rust backend are answered from the given config; config writes are
// recorded on window.__E2E_WRITES__ for assertions. Unknown commands reject,
// which callers of optional features (e.g. firmware versions) already handle.
export async function loadApp(page: Page, config: unknown) {
  await page.addInitScript((cfg) => {
    let nextId = 0;
    const callbacks = new Map<number, unknown>();
    (window as any).__E2E_WRITES__ = [];
    (window as any).__TAURI_INTERNALS__ = {
      metadata: { currentWindow: { label: 'main' }, currentWebview: { label: 'main' } },
      transformCallback(cb: unknown) {
        callbacks.set(++nextId, cb);
        return nextId;
      },
      unregisterCallback(id: number) {
        callbacks.delete(id);
      },
      convertFileSrc(p: string) {
        return p;
      },
      async invoke(cmd: string, args: unknown) {
        switch (cmd) {
          case 'plugin:app|version': return '0.0.0-e2e';
          case 'plugin:event|listen': return ++nextId;
          case 'plugin:event|unlisten': return null;
          case 'plugin:dialog|message': return null;
          case 'plugin:dialog|ask': return false;
          case 'scan_devices':
            return [{
              name: 'MIDICAPTAIN',
              path: '/e2e/MIDICAPTAIN',
              config_path: '/e2e/MIDICAPTAIN/config.json',
              has_config: true,
            }];
          case 'start_device_watcher': return null;
          case 'rpi_rp2_mount_path': return null;
          case 'read_config_raw': return JSON.stringify(cfg);
          case 'write_config_raw':
            (window as any).__E2E_WRITES__.push(args);
            return null;
          default:
            throw new Error(`e2e Tauri mock: unhandled command "${cmd}"`);
        }
      },
    };
  }, config);
  await page.goto('/');
  await page.locator('.page-bar').waitFor();
}

// Read the form store's current config through the View JSON modal — the same
// normalized JSON that Save would write. Closes the modal before returning.
// Note: in WebKit, clicking a button does NOT blur a focused input, so an
// in-flight (uncommitted) field edit stays uncommitted — which is exactly what
// these tests need to observe.
export async function readStoreJson(page: Page): Promise<any> {
  await page.getByRole('button', { name: 'View JSON' }).click();
  const text = await page.locator('.json-display').textContent();
  await page.locator('.modal-footer').getByRole('button', { name: 'Close' }).click();
  return JSON.parse(text ?? 'null');
}
