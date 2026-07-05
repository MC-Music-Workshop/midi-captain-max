import { test, expect } from '@playwright/test';
import { loadApp, oneButtonConfig } from './helpers';

// Frontend counterpart of the P4a manual smoke checklist (issue #15).

test('page bar renders with the loaded page and Add/Delete behave', async ({ page }) => {
  await loadApp(page, oneButtonConfig());
  const select = page.locator('#page-select');
  const del = page.getByRole('button', { name: 'Delete' });

  await expect(select).toHaveValue('0');
  await expect(del).toBeDisabled(); // never delete the last page (D3)

  await page.getByRole('button', { name: 'Add' }).click();
  await expect(select).toHaveValue('1'); // selection jumps to the new page
  await expect(del).toBeEnabled();

  await del.click();
  await expect(select).toHaveValue('0');
  await expect(del).toBeDisabled();
});
