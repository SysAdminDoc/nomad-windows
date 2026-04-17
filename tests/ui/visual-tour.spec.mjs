/* Opt-in screenshot tour across the major workspaces × all five themes.
 *
 * Run only when NOMAD_VISUAL_TOUR=1 — otherwise this file skips, so it
 * doesn't bloat the default 30-spec suite. Each route in each theme is
 * captured as a PNG attached to the test report so reviewers can scan
 * the gallery for layout breaks, theme bleed, or contrast regressions
 * after a polish pass without having to drive the app by hand.
 *
 *   NOMAD_VISUAL_TOUR=1 npx playwright test tests/ui/visual-tour.spec.mjs
 */

import { test, expect } from '@playwright/test';

const ENABLED = process.env.NOMAD_VISUAL_TOUR === '1';

const THEMES = ['nomad', 'nightops', 'cyber', 'redlight', 'eink'];
const ROUTES = [
  ['briefing', '/briefing'],
  ['home', '/home'],
  ['readiness', '/readiness'],
  ['operations', '/operations'],
  ['maps', '/maps'],
  ['tools', '/tools'],
  ['loadout', '/loadout'],
  ['knowledge', '/knowledge'],
  ['notes', '/notes'],
  ['media', '/media'],
  ['assistant', '/assistant'],
  ['diagnostics', '/diagnostics'],
  ['system', '/system'],
  ['nukemap', '/nukemap-tab'],
  ['viptrack', '/viptrack-tab'],
  ['training', '/training'],
  ['data-exchange', '/data-exchange'],
];

const STILL_FRAME_CSS = `
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
  }
`;

test.describe('visual tour', () => {
  test.skip(!ENABLED, 'Set NOMAD_VISUAL_TOUR=1 to capture the gallery.');

  for (const theme of THEMES) {
    for (const [name, path] of ROUTES) {
      test(`${theme} · ${name}`, async ({ page }, testInfo) => {
        await page.addInitScript((themeName) => {
          localStorage.setItem('nomad-theme', themeName);
        }, theme);

        await page.goto(path, { waitUntil: 'domcontentloaded' });
        await page.waitForSelector('#main-content', { timeout: 15000 });
        await page.addStyleTag({ content: STILL_FRAME_CSS });
        await page.waitForTimeout(400);

        // Sanity check — each workspace must render its main shell.
        const main = await page.evaluate(() => {
          const el = document.getElementById('main-content');
          if (!el) return null;
          const rect = el.getBoundingClientRect();
          return { width: rect.width, height: rect.height };
        });
        expect(main).not.toBeNull();
        expect(main.width).toBeGreaterThan(400);
        expect(main.height).toBeGreaterThan(200);

        const buf = await page.screenshot({ fullPage: false });
        await testInfo.attach(`${theme}-${name}.png`, {
          body: buf,
          contentType: 'image/png',
        });
      });
    }
  }
});
