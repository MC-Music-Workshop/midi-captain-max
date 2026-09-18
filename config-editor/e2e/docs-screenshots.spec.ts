import { test } from '@playwright/test';
import { loadApp } from './helpers';

// Not a test: a generator for the screenshots embedded in docs/user/*.md.
// Run it when the editor UI changes and the images go stale:
//   cd config-editor && npx playwright test docs-screenshots
// Each shot is an element capture of the button row(s) that demonstrate one
// feature, seeded from a config so the fields are already filled in.
const OUT = '../docs/user/img/inbound-midi';

// std10 = 10 buttons per page; only the rows we shoot need to be meaningful.
function config(buttons: Record<string, unknown>[]) {
  const padded = [...buttons];
  while (padded.length < 10) padded.push({ label: `B${padded.length}`, cc: 60 + padded.length, color: 'white' });
  return { device: 'std10', active_page: 0, pages: [{ buttons: padded }] };
}

async function shoot(page: any, rows: number[], path: string) {
  const all = page.locator('.button-row');
  if (rows.length === 1) {
    await all.nth(rows[0]).screenshot({ path });
    return;
  }
  // Multi-row shot: a clip must fit the viewport, so grow it to fit the rows first.
  await page.setViewportSize({ width: 1280, height: 1400 });
  const first = await all.nth(rows[0]).boundingBox();
  const last = await all.nth(rows[rows.length - 1]).boundingBox();
  await page.screenshot({
    path,
    clip: { x: first!.x, y: first!.y, width: first!.width, height: last!.y + last!.height - first!.y },
  });
}

test('state sync: a plain toggle button', async ({ page }) => {
  await loadApp(page, config([
    { label: 'DRIVE', cc: 20, cc_on: 127, cc_off: 0, mode: 'toggle', color: 'green' },
  ]));
  await shoot(page, [0], `${OUT}/state-sync-toggle.png`);
});

test('listen CC: send on one CC, listen on another', async ({ page }) => {
  await loadApp(page, config([
    { label: 'LOOP', cc: 20, cc_receive: 21, mode: 'toggle', color: 'blue' },
  ]));
  await shoot(page, [0], `${OUT}/listen-cc.png`);
});

test('select group: four snapshot buttons on one CC', async ({ page }) => {
  await loadApp(page, config([
    { label: 'SNAP1', cc: 69, cc_on: 0, mode: 'select', select_group: 'snap', color: 'red' },
    { label: 'SNAP2', cc: 69, cc_on: 1, mode: 'select', select_group: 'snap', color: 'green' },
    { label: 'SNAP3', cc: 69, cc_on: 2, mode: 'select', select_group: 'snap', color: 'blue' },
    { label: 'SNAP4', cc: 69, cc_on: 3, mode: 'select', select_group: 'snap', color: 'yellow' },
  ]));
  await shoot(page, [0, 1], `${OUT}/select-group.png`);
});

test('CC+ button: host sets the shared value', async ({ page }) => {
  await loadApp(page, config([
    { label: 'GAIN', type: 'cc_inc', cc: 30, cc_step: 8, cc_min: 0, cc_max: 127, color: 'cyan' },
  ]));
  await shoot(page, [0], `${OUT}/cc-plus.png`);
});
