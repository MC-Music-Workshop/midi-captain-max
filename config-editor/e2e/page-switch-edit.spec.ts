import { test, expect } from '@playwright/test';
import { loadApp, readStoreJson, oneButtonConfig, twoPageConfig, duplicateCurrentPage } from './helpers';

// Regression tests for the P4a smoke-test bug: field edits use commit-on-blur,
// but in WebKit clicking a <select>/<button>/blank space does not blur the
// focused input. Switching pages with an edit still "in flight" must commit it
// to the page it was typed on and repaint the form with the new page's data —
// never leave stale text on screen or let the edit land on the wrong page.

test('in-flight edit commits to the page it was typed on when switching pages', async ({ page }) => {
  await loadApp(page, oneButtonConfig());
  await duplicateCurrentPage(page); // page 2 (copy) now active

  const cc = page.locator('#btn-0-cc');
  await cc.fill('99'); // typed, still focused — no blur yet
  await page.locator('#page-select').selectOption('0'); // switch to page 1

  // The typed edit belongs to page 2, where it was typed.
  const cfg = await readStoreJson(page);
  expect(cfg.pages[1].buttons[0].cc).toBe(99);
  expect(cfg.pages[0].buttons[0].cc).toBe(20);
  // The form shows page 1's data, not leftover typed text.
  await expect(cc).toHaveValue('20');
});

test('in-flight edit cannot leak into the destination page via a later blur', async ({ page }) => {
  await loadApp(page, oneButtonConfig());
  await duplicateCurrentPage(page);

  const cc = page.locator('#btn-0-cc');
  await cc.fill('99');
  await page.locator('#page-select').selectOption('0');
  await page.locator('#btn-0-label').click(); // focus another field — blur fires now

  const cfg = await readStoreJson(page);
  expect(cfg.pages[0].buttons[0].cc).toBe(20); // page 1 untouched
  expect(cfg.pages[1].buttons[0].cc).toBe(99); // edit stayed on page 2
});

test('in-flight edit commits before arrow navigation', async ({ page }) => {
  await loadApp(page, twoPageConfig());

  const cc = page.locator('#btn-0-cc');
  await cc.fill('99');
  await page.getByRole('button', { name: 'Next page' }).click();

  const cfg = await readStoreJson(page);
  expect(cfg.pages[0].buttons[0].cc).toBe(99); // committed to page A
  await expect(cc).toHaveValue('30'); // form shows page B
});
