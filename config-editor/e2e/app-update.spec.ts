import { test, expect, type Page } from '@playwright/test';
import { loadApp, oneButtonConfig } from './helpers';

// #18: the editor offers a newer release of itself and installs it in place.
async function loadWithUpdate(page: Page, update: unknown, fails = false) {
  await page.addInitScript(({ update, fails }) => {
    (window as any).__E2E_UPDATE__ = update;
    (window as any).__E2E_UPDATE_FAILS__ = fails;
  }, { update, fails });
  await loadApp(page, oneButtonConfig());
}

const banner = (page: Page) => page.getByRole('status').filter({ hasText: 'is available' });
const offer = { current: '1.14.0', version: '1.15.0' };

test('a newer release shows a banner at startup', async ({ page }) => {
  await loadWithUpdate(page, offer);

  await expect(banner(page)).toContainText('Config Editor v1.15.0 is available (you have v1.14.0)');
});

test('Update & Restart shows progress while installing', async ({ page }) => {
  await loadWithUpdate(page, offer);

  await banner(page).getByRole('button', { name: 'Update & Restart' }).click();

  await expect(banner(page)).toContainText('Downloading…');
  await expect(banner(page).getByRole('button')).toHaveCount(0);
});

test('a failed install brings the buttons back', async ({ page }) => {
  await loadWithUpdate(page, offer, true);

  await banner(page).getByRole('button', { name: 'Update & Restart' }).click();

  await expect(banner(page).getByRole('button', { name: 'Update & Restart' })).toBeVisible();
});

test('Later hides the banner', async ({ page }) => {
  await loadWithUpdate(page, offer);

  await banner(page).getByRole('button', { name: 'Later' }).click();

  await expect(banner(page)).toHaveCount(0);
});

test('Check for Updates reports when the editor is up to date', async ({ page }) => {
  await loadWithUpdate(page, null);

  await page.getByRole('button', { name: 'Check for Updates' }).click();

  await expect(page.locator('footer .status')).toHaveText("You're on the latest version.");
  await expect(banner(page)).toHaveCount(0);
});
