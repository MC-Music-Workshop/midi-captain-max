import { Page, Locator, expect } from "@playwright/test";

// The keytimes long-press threshold in the page (LONG_MS). A "tap" must stay
// under it, a "hold" must exceed it.
export const LONG_MS = 500;

/** Wait for the MicroPython wasm firmware engine to finish booting. */
export async function waitForFirmwareEngine(page: Page) {
  await expect(page.locator("#kt-live")).toBeVisible({ timeout: 15000 });
}

/** Short press-and-release of a footswitch (below the long-press threshold). */
export async function tap(fs: Locator) {
  await fs.dispatchEvent("pointerdown", { pointerId: 1 });
  await fs.page().waitForTimeout(90);
  await fs.dispatchEvent("pointerup", { pointerId: 1 });
}

/** Long press-and-release of a footswitch (past the long-press threshold). */
export async function hold(fs: Locator) {
  await fs.dispatchEvent("pointerdown", { pointerId: 1 });
  await fs.page().waitForTimeout(LONG_MS + 200);
  await fs.dispatchEvent("pointerup", { pointerId: 1 });
}

/** Drag the encoder knob vertically by `dy` px (negative = up = increase). */
export async function turnEncoder(page: Page, dy: number) {
  const box = await page.locator("#encoder").boundingBox();
  if (!box) throw new Error("encoder not found");
  const cx = box.x + box.width / 2;
  const cy = box.y + box.height / 2;
  await page.mouse.move(cx, cy);
  await page.mouse.down();
  const steps = 12;
  for (let i = 1; i <= steps; i++) {
    await page.mouse.move(cx, cy + (dy * i) / steps);
  }
  await page.mouse.up();
}

/** Click the encoder without moving it (a push, not a turn). */
export async function pushEncoder(page: Page) {
  const box = await page.locator("#encoder").boundingBox();
  if (!box) throw new Error("encoder not found");
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.up();
}
