import { test, expect, type Page } from '@playwright/test';
import { loadApp, oneButtonConfig } from './helpers';

// #192: the main screen warns when the pedal's firmware is behind the editor's.
async function loadWithFirmware(page: Page, device: string | null, bundled: string) {
  await page.addInitScript((fw) => {
    (window as any).__E2E_FW__ = fw;
  }, { device, bundled });
  await loadApp(page, oneButtonConfig());
}

const olderNotice = (page: Page) => page.getByRole('status').filter({ hasText: 'is older than this editor' });

test('older pedal firmware shows a notice that Update Firmware clears', async ({ page }) => {
  await loadWithFirmware(page, 'v1.14.0', 'v1.15.0');

  await expect(olderNotice(page)).toContainText('Pedal firmware v1.14.0 is older than this editor (v1.15.0)');
  await olderNotice(page).getByRole('button', { name: 'Update Firmware' }).click();

  await expect(olderNotice(page)).toHaveCount(0);
  // The post-install reload remounts the panel, so check its version badge.
  await expect(page.locator('.installer')).toContainText('up to date');
});

test('saving to an out-of-date pedal says so in the footer', async ({ page }) => {
  await loadWithFirmware(page, 'v1.14.0', 'v1.15.0');

  await page.getByRole('button', { name: 'Save to Device', exact: true }).click();

  await expect(page.locator('footer .status')).toContainText(
    "Pedal firmware v1.14.0 is older than this editor's v1.15.0",
  );
});

test('Dismiss hides the notice', async ({ page }) => {
  await loadWithFirmware(page, 'v1.14.0', 'v1.15.0');

  await olderNotice(page).getByRole('button', { name: 'Dismiss' }).click();

  await expect(olderNotice(page)).toHaveCount(0);
});

test('no notice when the pedal is ahead of the editor', async ({ page }) => {
  await loadWithFirmware(page, 'v1.15.0-3-gfcf10e3', 'v1.15.0');

  await expect(page.locator('.installer')).toContainText('v1.15.0-3-gfcf10e3');
  await expect(page.getByRole('status').filter({ hasText: 'Firmware' })).toHaveCount(0);
});

test('a pedal without MIDI Captain MAX firmware is offered an install', async ({ page }) => {
  await loadWithFirmware(page, null, 'v1.15.0');

  const banner = page.getByRole('status').filter({ hasText: "isn't running MIDI Captain MAX firmware" });
  await expect(banner.getByRole('button', { name: 'Install Firmware' })).toBeVisible();
});
