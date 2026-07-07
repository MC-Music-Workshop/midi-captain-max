import { test, expect } from '@playwright/test';
import { loadApp, readStoreJson } from './helpers';

// Regression: in keytimes mode, a page-switch message must render its
// Target Page / Step field (the KeytimesMessageEditor originally had no branch
// for page_jump/page_inc/page_dec, so the field was missing and the target was
// stuck at page 0). Seed the button already in keytimes mode with the message
// present, so the editor renders it inline.
function keytimesJumpConfig(page: number) {
  return {
    device: 'one1',
    active_page: 0,
    pages: [
      { name: 'A', buttons: [{ label: 'GO', color: 'green', mode: 'keytimes', short: [{ down: [{ type: 'page_jump', page }] }] }] },
      { name: 'B', buttons: [{ label: 'OK', cc: 20, color: 'green' }] },
    ],
  };
}

test('keytimes page_jump message exposes a Target Page field with a named hint', async ({ page }) => {
  await loadApp(page, keytimesJumpConfig(0));

  const target = page.locator('.kt-message input[type="number"]');
  await expect(target).toHaveValue('0');

  await target.fill('1');
  await expect(page.locator('.kt-hint')).toHaveText('→ “B”');

  const json = await readStoreJson(page);
  expect(json.pages[0].buttons[0].short[0].down[0]).toMatchObject({ type: 'page_jump', page: 1 });
});

test('keytimes page_jump target outside the page list is flagged', async ({ page }) => {
  await loadApp(page, keytimesJumpConfig(0));

  const target = page.locator('.kt-message input[type="number"]');
  await target.fill('5');

  await expect(target).toHaveClass(/error/);
});
