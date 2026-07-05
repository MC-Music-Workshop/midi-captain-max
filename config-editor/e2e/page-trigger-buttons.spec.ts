import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig, readStoreJson } from './helpers';

// P4b button page-trigger inputs: type-specific fields commit on blur and land
// in the store JSON exactly as the firmware expects them.

test('page_jump gets a target input with a named-page hint', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.locator('#btn-0-type').selectOption('page_jump');

  const target = page.locator('#btn-0-page');
  await target.fill('1');
  await target.blur();

  await expect(page.locator('.button-row .hint-text')).toHaveText('→ “B”');
  const json = await readStoreJson(page);
  expect(json.pages[0].buttons[0]).toMatchObject({ type: 'page_jump', page: 1 });
});

test('page_jump target outside the page list shows an inline error', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.locator('#btn-0-type').selectOption('page_jump');

  const target = page.locator('#btn-0-page');
  await target.fill('5');
  await target.blur();

  await expect(page.locator('.button-row .error-text')).toHaveText(/between 0 and 1/);
});

test('page_inc gets a step input', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.locator('#btn-0-type').selectOption('page_inc');

  const step = page.locator('#btn-0-page-step');
  await step.fill('2');
  await step.blur();

  const json = await readStoreJson(page);
  expect(json.pages[0].buttons[0]).toMatchObject({ type: 'page_inc', page_step: 2 });
});
