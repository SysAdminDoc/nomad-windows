/* Network-disconnect field readiness drill.
 *
 * Blocks outbound network access and verifies that core workflows remain
 * usable without unhandled errors. This proves the "offline after setup"
 * promise documented in README.md.
 *
 * Run:
 *   NOMAD_OFFLINE_DRILL=1 npx playwright test tests/ui/network-disconnect.spec.mjs
 *
 * Requires the app to be running at http://localhost:PORT.
 */

import { test, expect } from '@playwright/test';

const ENABLED = process.env.NOMAD_OFFLINE_DRILL === '1';
const BASE = process.env.NOMAD_TEST_URL || 'http://localhost:8080';

const WORKSPACES = [
  ['home', '/'],
  ['situation-room', '/situation-room'],
  ['inventory', '/inventory'],
  ['medical', '/medical'],
  ['maps', '/maps'],
  ['library', '/library'],
  ['services', '/services'],
  ['settings', '/settings'],
  ['copilot', '/copilot'],
  ['backup', '/backup'],
];

for (const [name, path] of WORKSPACES) {
  test(`offline drill: ${name} loads without console errors`, async ({ page, context }) => {
    test.skip(!ENABLED, 'Set NOMAD_OFFLINE_DRILL=1 to run offline drill tests');

    await context.route('**/*', (route) => {
      const url = route.request().url();
      if (url.startsWith(BASE) || url.startsWith('data:') || url.startsWith('blob:')) {
        return route.continue();
      }
      return route.abort('connectionrefused');
    });

    const consoleErrors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });

    await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(2000);

    const unhandled = consoleErrors.filter(e =>
      !e.includes('net::ERR_') &&
      !e.includes('Failed to fetch') &&
      !e.includes('NetworkError') &&
      !e.includes('offline')
    );

    expect(unhandled, `Unhandled console errors on ${name} while offline`).toHaveLength(0);
  });
}
