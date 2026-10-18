import { test, expect } from '@playwright/test';
import { loadApp, readStoreJson } from './helpers';

// Keytimes host sync (#200, editor fields #211): each cycle gets a Listen CC, and
// once it's set each entry gets a Receive value.
function keytimesConfig() {
  return {
    device: 'one1',
    active_page: 0,
    pages: [
      {
        buttons: [{
          label: 'KT', color: 'green', mode: 'keytimes',
          short: [{ color: 'red' }, { color: 'blue' }],
          long: [{ color: 'yellow' }],
        }],
      },
    ],
  };
}

const shortCycle = (page: import('@playwright/test').Page) => page.locator('.kt-cycle').first();

test('Receive value appears only once the cycle has a Listen CC', async ({ page }) => {
  await loadApp(page, keytimesConfig());

  await expect(shortCycle(page).getByLabel('Receive value:')).toHaveCount(0);

  await shortCycle(page).getByLabel('Listen CC:').fill('20');
  await expect(shortCycle(page).getByLabel('Receive value:')).toHaveCount(2);
  // The long cycle has no Listen CC, so its entry stays without the field.
  await expect(page.locator('.kt-cycle').nth(1).getByLabel('Receive value:')).toHaveCount(0);

  await shortCycle(page).getByLabel('Receive value:').nth(0).fill('0');
  await shortCycle(page).getByLabel('Receive value:').nth(1).fill('127');

  const btn = (await readStoreJson(page)).pages[0].buttons[0];
  expect(btn.short_cc_receive).toBe(20);
  expect(btn.short[0].rx_value).toBe(0);
  expect(btn.short[1].rx_value).toBe(127);
  expect(btn.long_cc_receive).toBeUndefined();
});

test('a repeated receive value is flagged on the later entry', async ({ page }) => {
  await loadApp(page, keytimesConfig());

  await shortCycle(page).getByLabel('Listen CC:').fill('20');
  await shortCycle(page).getByLabel('Receive value:').nth(0).fill('64');
  await shortCycle(page).getByLabel('Receive value:').nth(1).fill('64');

  await expect(shortCycle(page).locator('.kt-warn')).toHaveText('Same value as #1, which wins');
});

test('an out-of-range Listen CC is an error', async ({ page }) => {
  await loadApp(page, keytimesConfig());

  const listen = shortCycle(page).getByLabel('Listen CC:');
  await listen.fill('200');

  await expect(listen).toHaveClass(/error/);
  await expect(shortCycle(page).locator('.kt-error')).toContainText('between 0 and 127');
});
