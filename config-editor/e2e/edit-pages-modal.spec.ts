import { test, expect } from '@playwright/test';
import { loadApp, twoPageConfig } from './helpers';

// Edit Pages modal: reorder, duplicate, and inline rename (issue #15).

test('↑↓ reorder pages, selection follows, picker reflects the new order', async ({ page }) => {
  await loadApp(page, twoPageConfig()); // pages A (active), B
  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  const rows = dialog.locator('.page-row');

  await expect(rows.nth(0)).toHaveAttribute('aria-current', 'true');
  await dialog.getByRole('button', { name: 'Move page down' }).click();

  await expect(rows.nth(0)).toContainText('B');
  await expect(rows.nth(1)).toContainText('A');
  await expect(rows.nth(1)).toHaveAttribute('aria-current', 'true'); // A stays selected

  await dialog.getByRole('button', { name: 'Move page up' }).click();
  await expect(rows.nth(0)).toContainText('A');
  await expect(rows.nth(0)).toHaveAttribute('aria-current', 'true');

  await dialog.getByRole('button', { name: 'Done' }).click();
  const options = page.locator('#page-select option');
  await expect(options.nth(0)).toHaveText('1: A');
  await expect(options.nth(1)).toHaveText('2: B');
});

test('Duplicate inserts a copy after the selected page and selects it', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  const rows = dialog.locator('.page-row');

  await dialog.getByRole('button', { name: 'Duplicate page' }).click();
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(1)).toContainText('A'); // copy of A, right after it
  await expect(rows.nth(1)).toHaveAttribute('aria-current', 'true');
  await expect(rows.nth(2)).toContainText('B');
});

test('double-click renames a page inline; Enter commits, Escape cancels', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  const rows = dialog.locator('.page-row');

  await rows.nth(0).dblclick();
  const input = dialog.getByLabel('Page name');
  await input.fill('Loop');
  await input.press('Enter');
  await expect(rows.nth(0)).toContainText('Loop');

  // Escape cancels without committing (and keeps the modal open).
  await rows.nth(0).dblclick();
  await input.fill('Nope');
  await input.press('Escape');
  await expect(rows.nth(0)).toContainText('Loop');
  await expect(dialog).toBeVisible();

  await dialog.getByRole('button', { name: 'Done' }).click();
  await expect(page.locator('#page-select option').nth(0)).toHaveText('1: Loop');
});
