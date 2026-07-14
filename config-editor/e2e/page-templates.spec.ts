import { test, expect } from '@playwright/test';
import { loadApp, oneButtonConfig, readStoreJson } from './helpers';

test('export a page then add it back as a template', async ({ page }) => {
  await loadApp(page, oneButtonConfig()); // 1 page

  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });

  // Export the active page (mock records it + registers it in the list).
  await dialog.getByRole('button', { name: 'Save as template…' }).click();

  // Add from template -> the picker lists "Exported"; click it.
  await dialog.getByRole('button', { name: 'Add from template…' }).click();
  await dialog.getByRole('button', { name: 'Exported' }).click();
  await dialog.getByRole('button', { name: 'Done' }).click();

  const json = await readStoreJson(page);
  expect(json.pages).toHaveLength(2);
  // Inserted page carries the exported button data.
  expect(json.pages[1].buttons[0].label).toBe('B0');
  expect(json.active_page).toBe(1);
});

test('a template with an out-of-range jump imports and flags the button (not rejected)', async ({ page }) => {
  await loadApp(page, oneButtonConfig()); // 1 page -> only index 0 is valid
  // Stage the "imported" page: its button jumps to page 9, which won't exist.
  await page.evaluate(() => {
    (window as any).__E2E_IMPORT__ = { buttons: [{ label: 'GO', type: 'page_jump', page: 9, color: 'green' }] };
    (window as any).__E2E_TEMPLATES__ = [{ name: 'Jumper', path: '/e2e/templates/Jumper.json' }];
  });

  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  await dialog.getByRole('button', { name: 'Add from template…' }).click();
  await dialog.getByRole('button', { name: 'Jumper' }).click();
  await dialog.getByRole('button', { name: 'Done' }).click();

  // The page landed (2 pages, newly-added one active) even though the jump is bad.
  const json = await readStoreJson(page);
  expect(json.pages).toHaveLength(2);
  expect(json.active_page).toBe(1);

  // And the bad target is flagged inline like any other validation error
  // (P4b renders the page_jump error near the button's target input).
  await expect(page.locator('.error-text, .error').filter({ hasText: /page/i }).first()).toBeVisible();
});
