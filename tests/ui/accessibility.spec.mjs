/* Automated WCAG accessibility regression gate using axe-core.
 *
 * Scans the app shell plus core workspaces for critical/serious
 * WCAG 2.2 violations. Any new critical or serious violation fails
 * the test; justified suppressions must be explicit and selector-scoped
 * in the KNOWN_SUPPRESSIONS array below.
 *
 * Run:
 *   npx playwright test tests/ui/accessibility.spec.mjs
 *
 * Requires the app to be running at http://localhost:PORT.
 */

import { test, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const BASE = process.env.NOMAD_TEST_URL || 'http://localhost:8080';

const WORKSPACES = [
  ['app-shell', '/'],
  ['settings', '/settings'],
  ['services', '/services'],
  ['inventory', '/inventory'],
  ['medical', '/medical'],
  ['maps', '/maps'],
  ['situation-room', '/situation-room'],
];

const KNOWN_SUPPRESSIONS = [
  // Example: 'color-contrast' violations in the Situation Room's
  // intentionally dark theme are expected and documented.
  // { id: 'color-contrast', selector: '#tab-situation-room' },
];

function filterResults(results) {
  if (!KNOWN_SUPPRESSIONS.length) return results;
  const dominated = new Set(KNOWN_SUPPRESSIONS.map(s => s.id));
  return {
    ...results,
    violations: results.violations.filter(v => !dominated.has(v.id)),
  };
}

for (const [name, path] of WORKSPACES) {
  test(`accessibility: ${name} has no critical/serious violations`, async ({ page }) => {
    await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 15000 });
    await page.waitForTimeout(1000);

    const raw = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag22aa'])
      .analyze();

    const results = filterResults(raw);

    const critical = results.violations.filter(v =>
      v.impact === 'critical' || v.impact === 'serious'
    );

    if (critical.length > 0) {
      const summary = critical.map(v =>
        `[${v.impact}] ${v.id}: ${v.description} (${v.nodes.length} instance(s))`
      ).join('\n');
      expect.soft(critical, `Accessibility violations in ${name}:\n${summary}`).toHaveLength(0);
    }
  });
}
