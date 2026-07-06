import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig, readStoreJson } from './helpers';

// P4b MIDI Page Control section. Writes replace the whole page_control object
// (store paths can't create missing intermediates), so the JSON shape after
// each edit is the contract to pin down.

test('configuring jump and inc slots lands the P3b shape in the store', async ({ page }) => {
  await loadApp(page, twoPageConfig());

  const jumpCc = page.locator('#page-control-jump-cc');
  await jumpCc.fill('20');
  await jumpCc.blur();

  const incCc = page.locator('#page-control-inc-cc');
  await incCc.fill('21');
  await incCc.blur();

  const incStep = page.locator('#page-control-inc-step');
  await expect(incStep).toBeEnabled(); // unlocked once the slot has a CC
  await incStep.fill('2');
  await incStep.blur();

  const json = await readStoreJson(page);
  expect(json.page_control).toEqual({ jump: { cc: 20 }, inc: { cc: 21, page_step: 2 } });
});

test('clearing a slot CC removes the slot; Enabled reflects the block', async ({ page }) => {
  await loadApp(page, { ...twoPageConfig(), page_control: { enabled: true, jump: { cc: 20 } } });

  const enabledBox = page.locator('.page-control-section input[type="checkbox"]');
  await expect(enabledBox).toBeChecked();
  await expect(page.locator('#page-control-inc-value')).toBeDisabled(); // no inc slot yet

  const jumpCc = page.locator('#page-control-jump-cc');
  await jumpCc.fill('');
  await jumpCc.blur();

  const json = await readStoreJson(page);
  expect(json.page_control.jump).toBeUndefined();
  expect(json.page_control.enabled).toBe(true);
});

test('out-of-range CC shows an inline error', async ({ page }) => {
  await loadApp(page, twoPageConfig());

  const jumpCc = page.locator('#page-control-jump-cc');
  await jumpCc.fill('200');
  await jumpCc.blur();

  await expect(page.locator('.page-control-section .error-text')).toHaveText(/0 and 127/);
});
