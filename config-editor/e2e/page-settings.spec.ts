import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig, readStoreJson } from './helpers';

test('per-page MIDI channel writes to the active page, blank inherits', async ({ page }) => {
  await loadApp(page, twoPageConfig()); // page 0 = 'A', page 1 = 'B'

  const channel = page.getByLabel('Page MIDI Channel:');
  await channel.fill('10');
  await channel.blur(); // WebKit doesn't blur on click — commit explicitly

  let json = await readStoreJson(page);
  expect(json.pages[0].global_channel).toBe(9); // 10 displayed -> 9 stored

  // Switch to page B: the field must NOT show page A's value.
  // `exact: true` — the new "Page MIDI Channel:" label also contains "Page",
  // so a substring match would resolve to two elements (strict-mode violation).
  await page.getByLabel('Page', { exact: true }).selectOption('1');
  await expect(page.getByLabel('Page MIDI Channel:')).toHaveValue('');

  json = await readStoreJson(page);
  expect(json.pages[1].global_channel).toBeUndefined();
});
