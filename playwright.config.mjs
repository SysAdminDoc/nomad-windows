import { defineConfig } from '@playwright/test';

const PLAYWRIGHT_PORT = process.env.NOMAD_PLAYWRIGHT_PORT || '4317';
const PLAYWRIGHT_BASE_URL = process.env.NOMAD_PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${PLAYWRIGHT_PORT}`;

export default defineConfig({
  testDir: './tests/ui',
  timeout: 45_000,
  fullyParallel: false,
  retries: 0,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputFolder: 'playwright-report' }],
  ],
  outputDir: 'test-results/playwright',
  use: {
    baseURL: PLAYWRIGHT_BASE_URL,
    viewport: { width: 1600, height: 1000 },
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  webServer: {
    command: `py -3 -m flask --app web.app run --host 127.0.0.1 --port ${PLAYWRIGHT_PORT} --no-debugger --no-reload`,
    url: PLAYWRIGHT_BASE_URL,
    reuseExistingServer: false,
    stdout: 'pipe',
    stderr: 'pipe',
    timeout: 120_000,
  },
});
