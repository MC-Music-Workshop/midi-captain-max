import { test, expect } from '@playwright/test';
import { loadApp, oneButtonConfig, twoPageConfig } from './helpers';

// Frontend counterpart of the P4a manual smoke checklist (issue #15), updated
// for the slim PageBar: ◀▶ navigate; add/delete live in the Edit Pages modal.

test('bar arrows navigate between pages and disable at the ends', async ({ page }) => {
  await loadApp(page, twoPageConfig());
  const select = page.locator('#page-select');
  const prev = page.getByRole('button', { name: 'Previous page' });
  const next = page.getByRole('button', { name: 'Next page' });
  const cc = page.locator('#btn-0-cc');

  await expect(select).toHaveValue('0');
  await expect(prev).toBeDisabled();

  await next.click();
  await expect(select).toHaveValue('1');
  await expect(cc).toHaveValue('30'); // page B's data
  await expect(next).toBeDisabled();

  await prev.click();
  await expect(select).toHaveValue('0');
  await expect(cc).toHaveValue('20'); // back to page A
});

test('Edit Pages modal adds and deletes pages', async ({ page }) => {
  await loadApp(page, oneButtonConfig());
  await page.getByRole('button', { name: 'Edit Pages…' }).click();
  const dialog = page.getByRole('dialog', { name: 'Edit Pages' });
  const rows = dialog.locator('.page-row');
  const del = dialog.getByRole('button', { name: 'Delete page' });

  await expect(rows).toHaveCount(1);
  await expect(del).toBeDisabled(); // never delete the last page (D3)

  await dialog.getByRole('button', { name: 'Add page' }).click();
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(1)).toHaveAttribute('aria-current', 'true'); // selection follows

  await del.click();
  await expect(rows).toHaveCount(1);
  await expect(del).toBeDisabled();

  await dialog.getByRole('button', { name: 'Done' }).click();
  await expect(dialog).not.toBeVisible();
  await expect(page.locator('#page-select')).toHaveValue('0');
});
