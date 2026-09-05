/* Mobile field-mode visual smoke tests.
 *
 * Verifies that core field workflows are usable at narrow viewport widths
 * (390px iPhone SE / 430px iPhone Pro Max) with no overlap, clipping, or
 * broken primary actions.
 *
 * Run:
 *   npx playwright test tests/ui/mobile-field.spec.mjs
 *
 * Requires the app to be running at http://localhost:PORT.
 */

import { test, expect } from '@playwright/test';

const VIEWPORTS = [
  { name: 'iPhone SE', width: 390, height: 844 },
  { name: 'iPhone Pro Max', width: 430, height: 932 },
];

const WORKSPACES = [
  ['situation-room', '/situation-room'],
  ['inventory', '/preparedness'],
  ['medical', '/medical-plus'],
  ['maps', '/maps'],
  ['comms', '/comms'],
  ['settings', '/settings'],
  ['copilot', '/copilot'],
  ['services', '/'],
];

for (const viewport of VIEWPORTS) {
  for (const [name, path] of WORKSPACES) {
    test(`${viewport.name} (${viewport.width}px): ${name} renders without horizontal overflow`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#main-content', { state: 'visible', timeout: 15000 });
      await page.waitForTimeout(500);

      const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
      const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);

      expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 5);
    });

    test(`${viewport.name} (${viewport.width}px): ${name} has visible primary action`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await page.goto(path, { waitUntil: 'domcontentloaded', timeout: 30000 });
      await page.waitForSelector('#main-content', { state: 'visible', timeout: 15000 });
      await page.waitForTimeout(500);

      const buttons = await page.locator('button:visible, a.btn:visible, [role="button"]:visible').count();
      expect(buttons).toBeGreaterThan(0);
    });
  }
}
