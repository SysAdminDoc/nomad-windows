import { test, expect } from '@playwright/test';

const THEME_TONES = {
  nomad: 'light',
  eink: 'light',
  nightops: 'dark',
  cyber: 'dark',
  redlight: 'dark',
};

const STABLE_CAPTURE_CSS = `
  *, *::before, *::after {
    animation: none !important;
    transition: none !important;
    caret-color: transparent !important;
  }
  .sr-ticker,
  .market-ribbon,
  .status-ticker,
  .live-clock,
  .network-status-inline,
  #sitroom-last-update,
  #sitroom-stat-news,
  #sitroom-stat-quakes,
  #sitroom-stat-weather,
  #sitroom-stat-conflicts,
  #sitroom-stat-markets,
  #sitroom-stat-aircraft,
  #sitroom-stat-volcanoes,
  #sitroom-stat-fires,
  #sitroom-stat-outages,
  #sitroom-stat-predictions {
    visibility: hidden !important;
  }
`;

function parseRgb(rgbText) {
  const matches = String(rgbText || '').match(/\d+(\.\d+)?/g) || [];
  const values = matches.slice(0, 3).map(Number);
  if (String(rgbText || '').includes('color(srgb')) {
    return values.map((value) => (value <= 1 ? value * 255 : value));
  }
  return values;
}

function relativeLuminance([r, g, b]) {
  const normalize = (channel) => {
    const value = channel / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  const [rr, gg, bb] = [normalize(r), normalize(g), normalize(b)];
  return (0.2126 * rr) + (0.7152 * gg) + (0.0722 * bb);
}

function overlaps(first, second) {
  return !(
    first.right <= second.left ||
    second.right <= first.left ||
    first.bottom <= second.top ||
    second.bottom <= first.top
  );
}

async function bootWorkspace(page, theme, path = '/') {
  await page.addInitScript((themeName) => {
    localStorage.setItem('nomad-theme', themeName);
  }, theme);
  await page.goto(path, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#main-content');
  await page.addStyleTag({ content: STABLE_CAPTURE_CSS });
  await page.waitForTimeout(250);
}

function normalizeRequestPath(url) {
  try {
    const parsed = new URL(url);
    return `${parsed.pathname}${parsed.search}`;
  } catch {
    return String(url);
  }
}

test('themes keep light and dark shells visually honest', async ({ page }, testInfo) => {
  for (const [theme, tone] of Object.entries(THEME_TONES)) {
    await bootWorkspace(page, theme);

    const metrics = await page.evaluate(() => {
      const bodyStyle = getComputedStyle(document.body);
      const sidebarStyle = getComputedStyle(document.getElementById('sidebar'));
      const utilities = ['lan-chat-panel', 'timer-panel']
        .reduce((acc, id) => {
          const el = document.getElementById(id);
          const style = el ? getComputedStyle(el) : null;
          acc[id] = !el || el.hidden || style.display === 'none' || style.visibility === 'hidden';
          return acc;
        }, {});

      return {
        bodyBackground: bodyStyle.backgroundColor,
        bodyText: bodyStyle.color,
        sidebarBackground: sidebarStyle.backgroundColor,
        utilities,
      };
    });

    const bgLum = relativeLuminance(parseRgb(metrics.bodyBackground));
    const textLum = relativeLuminance(parseRgb(metrics.bodyText));
    const sidebarLum = relativeLuminance(parseRgb(metrics.sidebarBackground));

    if (tone === 'dark') {
      expect(bgLum).toBeLessThan(0.18);
      expect(textLum).toBeGreaterThan(0.45);
      expect(sidebarLum).toBeLessThan(0.2);
    } else {
      expect(bgLum).toBeGreaterThan(0.72);
      expect(textLum).toBeLessThan(0.22);
      expect(sidebarLum).toBeGreaterThan(0.55);
    }

    expect(metrics.utilities['lan-chat-panel']).toBeTruthy();
    expect(metrics.utilities['timer-panel']).toBeTruthy();

    await testInfo.attach(`${theme}-shell`, {
      body: await page.screenshot({ fullPage: false }),
      contentType: 'image/png',
    });
  }
});

test('desktop shell layout stays ordered and command palette works globally', async ({ page }, testInfo) => {
  await bootWorkspace(page, 'nightops');

  const layout = await page.evaluate(() => {
    const isVisible = (selector) => {
      const element = document.querySelector(selector);
      if (!element) return false;
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return !element.hidden && style.display !== 'none' && style.visibility !== 'hidden' && rect.height > 0;
    };
    const boxFor = (selector) => {
      const rect = document.querySelector(selector)?.getBoundingClientRect();
      if (!rect) return null;
      return {
        left: rect.left,
        right: rect.right,
        top: rect.top,
        bottom: rect.bottom,
      };
    };
    return {
      sidebar: boxFor('#sidebar'),
      main: boxFor('#main-content'),
      statusStripVisible: isVisible('#status-strip'),
      contextVisible: isVisible('#workspace-context-bar'),
    };
  });

  expect(layout.sidebar).toBeTruthy();
  expect(layout.main).toBeTruthy();
  expect(layout.statusStripVisible).toBeFalsy();
  expect(layout.contextVisible).toBeFalsy();
  expect(layout.sidebar.right).toBeLessThan(layout.main.left + 12);

  await page.evaluate(() => {
    document.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'k',
      ctrlKey: true,
      bubbles: true,
    }));
  });
  await expect.poll(async () => !(await page.locator('#command-palette-overlay').evaluate((element) => element.hasAttribute('hidden')))).toBe(true);
  await expect(page.locator('#command-palette-input')).toBeFocused();

  await testInfo.attach('midnight-command-palette', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  });
});

test('setup wizard advances cleanly and restores from the mini banner', async ({ page }) => {
  await page.route('**/api/drives', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          path: 'D:\\',
          device: 'D:',
          fstype: 'NTFS',
          total: 1000,
          free: 700,
          used: 300,
          percent: 30,
          total_str: '1.0 TB',
          free_str: '700 GB',
        },
      ]),
    });
  });
  await page.route('**/api/content-tiers', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        essential: {
          name: 'Essential',
          desc: 'Fastest path to an offline-ready baseline.',
          services: ['ollama', 'kiwix'],
          zims: [{ filename: 'first-aid.zim', name: 'First Aid', size: '1.2 GB', category: 'Medical' }],
          models: ['qwen3:4b'],
          zim_count: 1,
          est_size: '10 GB',
        },
        standard: {
          name: 'Standard',
          desc: 'Balanced field kit.',
          services: ['ollama', 'kiwix', 'cyberchef'],
          zims: [{ filename: 'ops.zim', name: 'Ops', size: '8 GB', category: 'Reference' }],
          models: ['qwen3:4b'],
          zim_count: 1,
          est_size: '80 GB',
        },
        maximum: {
          name: 'Maximum',
          desc: 'Full offline desk.',
          services: ['ollama', 'kiwix', 'cyberchef', 'stirling'],
          zims: [
            { filename: 'ops.zim', name: 'Ops', size: '8 GB', category: 'Reference' },
            { filename: 'first-aid.zim', name: 'First Aid', size: '1.2 GB', category: 'Medical' },
          ],
          models: ['qwen3:4b', 'llama3.2:3b'],
          zim_count: 2,
          est_size: '500 GB',
        },
      }),
    });
  });

  await bootWorkspace(page, 'nightops', '/?wizard=1');

  await expect(page.locator('#wizard')).toBeVisible();
  await expect(page.locator('#wiz-page-1')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start Guided Setup' })).toBeVisible();

  await page.click('[data-shell-action="wiz-go-page"][data-wiz-page="2"]');
  await expect(page.locator('#wiz-page-2')).toBeVisible();
  await expect(page.locator('#wiz-storage-status')).toContainText('NOMADFieldDesk');

  await page.click('#wiz-storage-next');
  await expect(page.locator('#wiz-page-3')).toBeVisible();

  await page.click('[data-shell-action="wiz-select-tier"][data-tier-id="custom"]');
  await expect(page.locator('#wiz-custom-panel')).toBeVisible();

  await page.click('[data-shell-action="wiz-select-tier"][data-tier-id="essential"]');
  await expect(page.locator('#wiz-tier-detail')).toBeVisible();

  await page.evaluate(() => {
    wizGoPage(4);
  });
  await expect(page.locator('#wiz-page-4')).toBeVisible();

  await page.click('[data-shell-action="wiz-minimize"]');
  await expect(page.locator('#wiz-mini-banner')).toBeVisible();

  await page.click('#wiz-mini-banner');
  await expect(page.locator('#wizard')).toBeVisible();
  await expect(page.locator('#wiz-page-4')).toBeVisible();
});

test('guided tour stays interactive and restores shell focus when closed', async ({ page }) => {
  await bootWorkspace(page, 'nightops', '/?wizard=1');

  await page.evaluate(() => {
    wizGoPage(5);
  });
  await expect(page.locator('#wiz-page-5')).toBeVisible();
  await page.click('[data-shell-action="start-tour"]');

  const overlay = page.locator('#tour-overlay');
  const nextBtn = page.locator('#tour-next-btn');
  const servicesTab = page.locator('[data-tab="services"]');

  await expect(overlay).toBeVisible();
  await expect(overlay).toHaveAttribute('aria-hidden', 'false');
  await expect(nextBtn).toBeFocused();
  await expect(page.locator('#tour-step-num')).toContainText('1 of 6');

  await nextBtn.click();
  await expect(page.locator('#tour-step-num')).toContainText('2 of 6');

  await page.click('[data-shell-action="tour-skip"]');
  await expect(overlay).toBeHidden();
  await expect(overlay).toHaveAttribute('aria-hidden', 'true');
  await expect(servicesTab).toBeFocused();
});

test('escape closes visible shell surfaces without leaving stale utility state behind', async ({ page }) => {
  await bootWorkspace(page, 'nightops', '/?wizard=1');

  await expect(page.locator('#wizard')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#wizard')).toBeHidden();
  await expect(page.locator('#wiz-mini-banner')).toBeHidden();

  await page.evaluate(() => {
    wizGoPage(5);
    startTour();
  });
  await expect(page.locator('#tour-overlay')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#tour-overlay')).toBeHidden();
  await expect(page.locator('[data-tab="services"]')).toBeFocused();

  await page.evaluate(() => toggleShortcutsHelp(true));
  await expect(page.locator('#shortcuts-overlay')).toBeVisible();
  await expect(page.locator('.shortcuts-copy')).toContainText('Keep your hands on the keyboard');
  await page.keyboard.press('Escape');
  await expect(page.locator('#shortcuts-overlay')).toBeHidden();

  await page.evaluate(() => toggleShellHealth(true));
  await expect(page.locator('#shell-health-overlay')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.locator('#shell-health-overlay')).toBeHidden();

  await page.evaluate(() => toggleLanChat());
  await expect(page.locator('#lan-chat-panel')).toBeVisible();
  await expect(page.locator('#lan-chat-panel')).toHaveAttribute('role', 'complementary');
  await expect(page.locator('#lan-chat-subtitle')).toContainText('Local-only handoffs');
  await expect.poll(async () => page.evaluate(() => (typeof _lanChatOpen !== 'undefined' ? _lanChatOpen : null))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(page.locator('#lan-chat-panel')).toBeHidden();
  await expect.poll(async () => page.evaluate(() => (typeof _lanChatOpen !== 'undefined' ? _lanChatOpen : null))).toBe(false);

  await page.evaluate(() => toggleQuickActions());
  await expect(page.locator('#quick-actions-menu')).toBeVisible();
  await expect(page.locator('.utility-actions-menu-title')).toContainText('Quick Capture');
  await expect.poll(async () => page.evaluate(() => (typeof _qaOpen !== 'undefined' ? _qaOpen : null))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(page.locator('#quick-actions-menu')).toBeHidden();
  await expect.poll(async () => page.evaluate(() => (typeof _qaOpen !== 'undefined' ? _qaOpen : null))).toBe(false);

  await page.evaluate(() => toggleTimerPanel());
  await expect(page.locator('#timer-panel')).toBeVisible();
  await expect(page.locator('#timer-panel')).toHaveAttribute('role', 'complementary');
  await expect(page.locator('#timer-panel-subtitle')).toContainText('Start short operational reminders');
  await expect.poll(async () => page.evaluate(() => (typeof _timerPanelOpen !== 'undefined' ? _timerPanelOpen : null))).toBe(true);
  await page.keyboard.press('Escape');
  await expect(page.locator('#timer-panel')).toBeHidden();
  await expect.poll(async () => page.evaluate(() => (typeof _timerPanelOpen !== 'undefined' ? _timerPanelOpen : null))).toBe(false);
});

test('density customization persists without stretching the shell', async ({ page }) => {
  await bootWorkspace(page, 'nightops');

  await page.locator('.sidebar-customize-btn').click();
  await page.locator('#cust-density-ultra').click();
  await expect.poll(async () => page.evaluate(() => document.documentElement.getAttribute('data-density'))).toBe('ultra');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#main-content');
  await expect.poll(async () => page.evaluate(() => document.documentElement.getAttribute('data-density'))).toBe('ultra');
});

test('services home startup avoids legacy AI model bootstrap fetches', async ({ page }) => {
  const requests = [];
  page.on('request', (request) => {
    requests.push(normalizeRequestPath(request.url()));
  });

  await bootWorkspace(page, 'nightops', '/');
  await page.waitForTimeout(1400);

  expect(requests.some((requestUrl) => requestUrl.includes('/api/ai/models'))).toBeFalsy();
});

test('situation room opens as a stable analyst surface', async ({ page }, testInfo) => {
  await bootWorkspace(page, 'cyber');

  await page.locator('.tab[data-tab="situation-room"]').click();
  await expect(page.locator('#tab-situation-room')).toBeVisible();

  await expect.poll(async () => page.locator('[data-sitroom-view="topline"]').getAttribute('aria-pressed')).toBe('true');
  await expect(page.locator('#sr-posture-copy')).toContainText(/briefing|desk|view/i);
  await expect.poll(async () => page.locator('#workspace-context-detail').textContent()).toMatch(/Situation Room|Topline/i);
  await expect(page.locator('#sr-map-command-title')).toContainText(/map|canvas|watch/i);
  await expect(page.locator('#sitroom-map')).toBeVisible();

  await testInfo.attach('situation-room-news-desk', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  });
});

test('situation room runtime pauses desk-specific intervals after leaving the desk', async ({ page }) => {
  await bootWorkspace(page, 'cyber');

  await page.locator('.tab[data-tab="situation-room"]').click();
  await expect(page.locator('#tab-situation-room')).toBeVisible();
  await expect.poll(async () => page.evaluate(() =>
    window.NomadShellRuntime.snapshot().intervals.some((interval) => interval.name === 'sitroom.utc-clock')
  )).toBe(true);

  await page.waitForTimeout(1200);
  const before = await page.evaluate(() =>
    window.NomadShellRuntime.snapshot().intervals.find((interval) => interval.name === 'sitroom.utc-clock')?.runCount ?? 0
  );
  expect(before).toBeGreaterThan(0);

  await page.locator('.tab[data-tab="services"]').click();
  await expect(page.locator('#tab-services')).toBeVisible();
  await expect.poll(async () => page.evaluate(() => document.body.classList.contains('situation-room-active'))).toBe(false);

  const freezeBaseline = await page.evaluate(() =>
    window.NomadShellRuntime.snapshot().intervals.find((interval) => interval.name === 'sitroom.utc-clock')?.runCount ?? 0
  );
  await page.waitForTimeout(1300);
  const after = await page.evaluate(() => {
    const snapshot = window.NomadShellRuntime.snapshot();
    return {
      activeTab: snapshot.activeTab,
      runCount: snapshot.intervals.find((interval) => interval.name === 'sitroom.utc-clock')?.runCount ?? 0,
    };
  });

  expect(after.activeTab).toBe('services');
  expect(after.runCount).toBe(freezeBaseline);
});

test('knowledge workspaces stay usable without workspace guide chrome', async ({ page }, testInfo) => {
  await bootWorkspace(page, 'nomad');

  await page.locator('.tab[data-tab="notes"]').click();
  await expect(page.locator('#tab-notes')).toBeVisible();
  await expect(page.locator('[data-workspace-guide-target]')).toHaveCount(0);
  await expect(page.locator('#workspace-inspector')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'New Note' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Use Template' })).toBeVisible();
  await expect(page.locator('#notes-search')).toBeVisible();

  await testInfo.attach('notes-workspace-no-guide', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  });
});

test('workspace navigation uses dedicated routes instead of one giant mounted page', async ({ page }, testInfo) => {
  await bootWorkspace(page, 'nightops', '/preparedness?tab=preparedness');

  await expect(page.locator('#tab-preparedness')).toBeVisible();
  await expect(page.locator('#tab-services')).toHaveCount(0);
  await expect(page.locator('#tab-settings')).toHaveCount(0);

  await page.locator('.tab[data-tab="maps"]').click();
  await expect(page).toHaveURL(/\/maps(\?|$)/);
  await expect(page.locator('#tab-maps')).toBeVisible();
  await expect(page.locator('#tab-preparedness')).toHaveCount(0);

  await page.locator('.tab[data-tab="notes"]').click();
  await expect(page).toHaveURL(/\/notes(\?|$)/);
  await expect(page.locator('#tab-notes')).toBeVisible();
  await expect(page.locator('#tab-maps')).toHaveCount(0);

  await page.locator('.tab[data-tab="loadout"]').click();
  await expect(page).toHaveURL(/\/loadout(\?|$)/);
  await expect(page.locator('#tab-loadout')).toBeVisible();
  await expect(page.locator('#tab-notes')).toHaveCount(0);

  await testInfo.attach('segmented-workspace-routes', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  });
});

test('media channel browser renders the channel catalog instead of staying hidden', async ({ page }) => {
  await page.route('**/api/channels/catalog', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        {
          name: 'Primitive Technology',
          focus: 'Pure primitive builds',
          category: 'Wilderness Survival & Bushcraft',
          url: 'https://www.youtube.com/@primitivetechnology9550',
        },
        {
          name: 'Sensible Prepper',
          focus: 'Preparedness gear and drills',
          category: 'Preparedness',
          url: 'https://www.youtube.com/@SensiblePrepper',
        },
      ]),
    });
  });
  await page.route('**/api/channels/categories', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify([
        { name: 'Wilderness Survival & Bushcraft', count: 1 },
        { name: 'Preparedness', count: 1 },
      ]),
    });
  });

  await bootWorkspace(page, 'nightops', '/media?tab=media');

  await expect(page.locator('#tab-media')).toBeVisible();
  await expect(page.locator('#channel-browser')).toBeVisible();
  await expect(page.locator('#channel-list')).toBeVisible();
  await expect(page.locator('#yt-video-results')).toBeHidden();
  await expect.poll(async () => page.locator('#channel-list .channel-browser-card').count()).toBe(2);
  await expect(page.locator('#channel-list')).toContainText('Primitive Technology');
  await expect(page.locator('#channel-count')).toContainText('2 channels across 2 categories');

  const state = await page.evaluate(() => ({
    browserHidden: document.getElementById('channel-browser')?.classList.contains('is-hidden') ?? true,
    listHidden: document.getElementById('channel-list')?.classList.contains('is-hidden') ?? true,
    resultsHidden: document.getElementById('yt-video-results')?.classList.contains('is-hidden') ?? false,
  }));

  expect(state.browserHidden).toBeFalsy();
  expect(state.listHidden).toBeFalsy();
  expect(state.resultsHidden).toBeTruthy();
});

test('nukemap fills the wide workspace frame and follows the active shell theme', async ({ page }, testInfo) => {
  const pageErrors = [];
  const requests = [];
  page.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });
  page.on('request', (request) => {
    requests.push(normalizeRequestPath(request.url()));
  });
  await page.addInitScript(() => {
    localStorage.removeItem('nukemap-welcomed');
    localStorage.removeItem('nomad-offline-atlas-cache');
    if ('serviceWorker' in navigator && !navigator.serviceWorker.__nomadWrappedRegister) {
      const originalRegister = navigator.serviceWorker.register.bind(navigator.serviceWorker);
      navigator.serviceWorker.__nomadWrappedRegister = true;
      navigator.serviceWorker.register = (...args) => {
        window.__nukemapSwRegisterCalls = window.__nukemapSwRegisterCalls || [];
        window.__nukemapSwRegisterCalls.push(String(args[0] || ''));
        return originalRegister(...args);
      };
    }
  });

  const expectations = [
    { theme: 'nomad', label: 'Atlas (Light)', layer: 'offlineAtlas', panelMinLum: 0.35 },
    { theme: 'nightops', label: 'Midnight (Dark)', layer: 'offlineAtlas', panelMaxLum: 0.12 },
  ];

  for (const expectation of expectations) {
    pageErrors.length = 0;
    requests.length = 0;
    await bootWorkspace(page, expectation.theme, '/nukemap-tab?tab=nukemap');
    await page.waitForSelector('#nukemap-stage');
    await page.waitForFunction(() => document.getElementById('welcome-atlas-status')?.dataset.state === 'ready');
    await page.waitForTimeout(1800);

    const metrics = await page.evaluate(() => {
      const stage = document.getElementById('nukemap-stage');
      const map = document.getElementById('map');
      const stageRect = stage?.getBoundingClientRect();
      const mapRect = map?.getBoundingClientRect();
      return {
        stageWidth: Math.round(stageRect?.width || 0),
        stageHeight: Math.round(stageRect?.height || 0),
        mapWidth: Math.round(mapRect?.width || 0),
        mapHeight: Math.round(mapRect?.height || 0),
        left: Math.round(stageRect?.left || 0),
        rightGap: Math.round((window.innerWidth - (stageRect?.right || 0))),
        themeLabel: document.getElementById('nukemap-theme-label')?.textContent || '',
        activeLayer: document.querySelector('#layer-switcher .layer-btn.active')?.dataset.layer || '',
        panelBackground: getComputedStyle(document.getElementById('panel')).backgroundColor,
        welcomeVisible: !document.getElementById('welcome-overlay')?.classList.contains('hidden'),
        atlasState: document.getElementById('welcome-atlas-status')?.dataset.state || '',
        atlasStatus: document.getElementById('welcome-atlas-status')?.textContent || '',
        welcomeButtonLabel: document.getElementById('welcome-dismiss')?.textContent || '',
        welcomeOffsetRatio: (() => {
          const welcomeRect = document.querySelector('#welcome-overlay .welcome-card')?.getBoundingClientRect();
          if (!stageRect || !welcomeRect || !stageRect.width) return 0;
          return (welcomeRect.left - stageRect.left) / stageRect.width;
        })(),
        welcomeWidthRatio: (() => {
          const welcomeRect = document.querySelector('#welcome-overlay .welcome-card')?.getBoundingClientRect();
          if (!stageRect || !welcomeRect || !stageRect.width) return 0;
          return welcomeRect.width / stageRect.width;
        })(),
        swRegisterCalls: window.__nukemapSwRegisterCalls || [],
      };
    });
    const panelLum = relativeLuminance(parseRgb(metrics.panelBackground));

    expect(pageErrors).toEqual([]);
    expect(metrics.stageWidth).toBeGreaterThan(1100);
    expect(metrics.stageHeight).toBeGreaterThan(700);
    expect(Math.abs(metrics.stageWidth - metrics.mapWidth)).toBeLessThanOrEqual(4);
    expect(Math.abs(metrics.stageHeight - metrics.mapHeight)).toBeLessThanOrEqual(4);
    expect(metrics.left).toBeGreaterThan(8);
    expect(metrics.rightGap).toBeGreaterThan(8);
    expect(metrics.themeLabel).toBe(expectation.label);
    expect(metrics.activeLayer).toBe(expectation.layer);
    expect(metrics.welcomeVisible).toBeTruthy();
    expect(metrics.atlasState).toBe('ready');
    expect(metrics.atlasStatus).toContain('Enhanced offline basemap ready');
    expect(metrics.welcomeButtonLabel).toContain('Start Exploring');
    expect(metrics.welcomeOffsetRatio).toBeLessThan(0.18);
    expect(metrics.welcomeWidthRatio).toBeLessThan(0.34);
    expect(metrics.swRegisterCalls.some((call) => call.includes('/nukemap/sw.js') || call.includes('./sw.js'))).toBeFalsy();
    expect(requests.some((requestUrl) => requestUrl === '/nukemap/data/offline_atlas.json')).toBeTruthy();
    expect(requests.some((requestUrl) => requestUrl === '/js/zipcodes.js')).toBeFalsy();
    expect(requests.some((requestUrl) => requestUrl === '/nukemap/js/zipcodes.js')).toBeTruthy();
    if (typeof expectation.panelMinLum === 'number') {
      expect(panelLum).toBeGreaterThan(expectation.panelMinLum);
    }
    if (typeof expectation.panelMaxLum === 'number') {
      expect(panelLum).toBeLessThan(expectation.panelMaxLum);
    }

    await page.locator('#welcome-dismiss').click();
    await page.waitForTimeout(2400);

    const multiToggle = page.locator('#tab-nukemap .toggle-row').first();
    const toggleFocusState = await multiToggle.evaluate((toggleRow) => ({
      toggleInput: toggleRow?.dataset?.toggleInput || '',
      activeRole: toggleRow?.getAttribute?.('role') || '',
      activeAriaChecked: toggleRow?.getAttribute?.('aria-checked') || '',
      tabIndex: toggleRow?.tabIndex ?? -1,
    }));

    expect(toggleFocusState.toggleInput).toBe('multi-check');
    expect(toggleFocusState.activeRole).toBe('switch');
    expect(toggleFocusState.activeAriaChecked).toBe('false');
    expect(toggleFocusState.tabIndex).toBe(0);

    await multiToggle.evaluate((toggleRow) => {
      toggleRow.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', code: 'Space', bubbles: true }));
    });
    const multiCheckEnabled = await page.evaluate(() => ({
      checked: document.getElementById('multi-check')?.checked ?? false,
      ariaChecked: document.querySelector('#tab-nukemap .toggle-row')?.getAttribute?.('aria-checked') || '',
    }));
    expect(multiCheckEnabled.checked).toBeTruthy();
    expect(multiCheckEnabled.ariaChecked).toBe('true');

    const postDemoState = await page.evaluate(() => ({
      shellStillVisible: document.getElementById('tab-nukemap')?.classList.contains('active') ?? false,
      stageVisible: !!document.getElementById('nukemap-stage')?.getBoundingClientRect().width,
      mapVisible: !!document.getElementById('map')?.getBoundingClientRect().width,
      activeInnerPane: document.querySelector('#tab-nukemap .nk-tab.active')?.dataset.nktab || '',
      detonationCount: document.getElementById('det-counter-num')?.textContent || '0',
      search: window.location.search,
    }));

    expect(pageErrors).toEqual([]);
    expect(postDemoState.shellStillVisible).toBeTruthy();
    expect(postDemoState.stageVisible).toBeTruthy();
    expect(postDemoState.mapVisible).toBeTruthy();
    expect(postDemoState.activeInnerPane).toBe('effects');
    expect(Number(postDemoState.detonationCount)).toBeGreaterThan(0);
    expect(postDemoState.search).toContain('tab=nukemap');
    expect(postDemoState.search).toContain('d=');
  }

  await testInfo.attach('nukemap-workspace', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  });
});

test('viptrack fills the wide workspace frame and keeps embedded controls stateful', async ({ page }, testInfo) => {
  const pageErrors = [];
  page.on('pageerror', (error) => {
    pageErrors.push(error.message);
  });

  await page.addInitScript(() => {
    window.localStorage.removeItem('viptrack_onboarded');
    window.localStorage.removeItem('nomad-offline-atlas-cache');
    window.localStorage.removeItem('viptrack_settings_v3');
  });

  await bootWorkspace(page, 'nightops', '/viptrack-tab?tab=viptrack');
  await page.waitForSelector('#viptrack-stage');

  const stageMetrics = await page.evaluate(() => {
    const stageRect = document.getElementById('viptrack-stage')?.getBoundingClientRect();
    return {
      stageWidth: Math.round(stageRect?.width || 0),
      stageHeight: Math.round(stageRect?.height || 0),
      left: Math.round(stageRect?.left || 0),
      rightGap: Math.round(window.innerWidth - (stageRect?.right || 0)),
      themeLabel: document.getElementById('viptrack-theme-label')?.textContent || '',
    };
  });

  expect(stageMetrics.stageWidth).toBeGreaterThan(1100);
  expect(stageMetrics.stageHeight).toBeGreaterThan(700);
  expect(stageMetrics.left).toBeGreaterThan(8);
  expect(stageMetrics.rightGap).toBeGreaterThan(8);
  expect(stageMetrics.themeLabel).toBe('Midnight (Dark)');

  const embedded = page.frameLocator('#viptrack-frame');
  await expect(embedded.locator('#map')).toBeVisible();
  await expect(embedded.locator('#onboardAtlasStatus')).toHaveAttribute('data-state', 'ready');
  if (await embedded.locator('#onboardDismiss').isVisible()) {
    await embedded.locator('#onboardDismiss').evaluate((button) => button.click());
  }
  await expect(embedded.locator('#searchFilterBtn')).toHaveAttribute('aria-expanded', 'false');
  await expect(embedded.locator('#settingsBtn')).toHaveAttribute('aria-expanded', 'false');
  await expect(embedded.locator('#panelsBtn')).toHaveAttribute('aria-expanded', 'false');
  await expect(embedded.locator('#trailStatus')).toHaveAttribute('role', 'status');
  await expect(embedded.locator('#dataSource')).toHaveAttribute('role', 'status');
  await expect(embedded.locator('#connectivityIndicator')).toHaveAttribute('role', 'status');

  await embedded.locator('#searchInput').fill('VIP');
  await expect(embedded.locator('#searchInput')).toHaveValue('VIP');

  await embedded.locator('#searchFilterBtn').evaluate((button) => button.click());
  await expect(embedded.locator('#searchFilterBtn')).toHaveAttribute('aria-expanded', 'true');
  await expect(embedded.locator('#searchDropdown')).toHaveAttribute('aria-hidden', 'false');
  await expect(embedded.locator('#searchTabFilters')).toHaveAttribute('aria-selected', 'true');
  await expect(embedded.locator('#tabFilters')).not.toHaveAttribute('hidden', '');

  await embedded.locator('#settingsBtn').evaluate((button) => button.click());
  await expect(embedded.locator('#settingsBtn')).toHaveAttribute('aria-expanded', 'true');
  await expect(embedded.locator('#settingsPanel')).toHaveAttribute('aria-hidden', 'false');
  await expect(embedded.locator('#toggleTrailArrows')).toHaveAttribute('role', 'switch');
  await expect(embedded.locator('#toggleTrailArrows')).toHaveAttribute('aria-checked', 'true');
  await embedded.locator('#toggleTrailArrows').evaluate((button) => button.click());
  await expect(embedded.locator('#toggleTrailArrows')).toHaveAttribute('aria-checked', 'false');
  await expect(embedded.locator('#toggleAlerts')).toHaveAttribute('role', 'switch');

  await embedded.locator('#panelsBtn').evaluate((button) => button.click());
  await expect(embedded.locator('#panelsBtn')).toHaveAttribute('aria-expanded', 'true');
  await expect(embedded.locator('#bottomPanels')).toHaveAttribute('aria-hidden', 'false');

  await embedded.locator('.filter-btn[data-filter="military"]').evaluate((button) => button.click());
  const embeddedUrlState = await page.evaluate(() => {
    const frame = document.getElementById('viptrack-frame');
    return {
      href: frame?.contentWindow?.location.href || '',
      search: frame?.contentWindow?.location.search || '',
    };
  });
  expect(embeddedUrlState.search).toContain('embed=nomad');
  expect(embeddedUrlState.search).toContain('filter=military');

  const embeddedSnapshot = await page.evaluate(() => {
    const frame = document.getElementById('viptrack-frame');
    return frame?.contentWindow?.VIPTrackHost?.getSnapshot?.() || null;
  });
  expect(embeddedSnapshot?.offlineAtlasReady).toBe(true);
  expect(embeddedSnapshot?.mapStyle).toBe('offline-atlas');

  expect(pageErrors).toEqual([]);

  await testInfo.attach('viptrack-workspace', {
    body: await page.screenshot({ fullPage: false }),
    contentType: 'image/png',
  });
});

test('shared shell pauses VIPTrack activity after switching away from the tab', async ({ page }) => {
  await bootWorkspace(page, 'nightops', '/?tab=viptrack');
  await page.waitForSelector('#tab-viptrack.active');
  const embedded = page.frameLocator('#viptrack-frame');
  await expect(embedded.locator('#map')).toBeVisible();
  await page.waitForFunction(() => {
    const frame = document.getElementById('viptrack-frame');
    const snapshot = frame?.contentWindow?.VIPTrackHost?.getSnapshot?.();
    return !!snapshot && snapshot.pausableActive > 0 && snapshot.tabPaused === false;
  });

  const activeState = await page.evaluate(() => {
    const frame = document.getElementById('viptrack-frame');
    return frame?.contentWindow?.VIPTrackHost?.getSnapshot?.() || null;
  });
  expect(activeState?.pausableActive).toBeGreaterThan(0);
  expect(activeState?.tabPaused).toBeFalsy();

  await page.click('.tab[data-tab="services"]');
  await page.waitForURL(/\/\?tab=services$/);
  await page.waitForSelector('#tab-services.active');
  await page.waitForFunction(() => {
    return !!window.NomadEmbeddedWorkspaceState?.get?.('viptrack')?.tabPaused;
  });

  const hiddenState = await page.evaluate(() => {
    return window.NomadEmbeddedWorkspaceState?.get?.('viptrack') || null;
  });
  expect(hiddenState?.fetchIntervalActive).toBeFalsy();
  expect(hiddenState?.pausableActive).toBe(0);
  expect(hiddenState?.tabPaused).toBeTruthy();
  expect(hiddenState?.reason).toBe('tab-hidden');
});

test('interoperability sub-tabs expose correct ARIA tablist semantics and toggle aria-selected', async ({ page }) => {
  await bootWorkspace(page, 'nightops', '/interoperability');
  const tablist = page.locator('#tab-interoperability [role="tablist"]');
  await expect(tablist).toBeVisible();
  await expect(tablist).toHaveAttribute('aria-label', 'Data exchange sections');

  // Default: export tab is selected
  const exportTab = page.locator('#io-tab-export');
  await expect(exportTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#io-panel-export')).toBeVisible();

  // Click import tab — aria-selected should shift
  await page.locator('#io-tab-import').click();
  await expect(page.locator('#io-tab-export')).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#io-tab-import')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#io-panel-import')).toBeVisible();
  await expect(page.locator('#io-panel-export')).not.toBeVisible();

  // Click history tab
  await page.locator('#io-tab-history').click();
  await expect(page.locator('#io-tab-import')).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#io-tab-history')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#io-panel-history')).toBeVisible();
});

test('training-knowledge sub-tabs expose correct ARIA tablist semantics and toggle aria-selected', async ({ page }) => {
  await bootWorkspace(page, 'nightops', '/training-knowledge');
  const tablist = page.locator('#tab-training-knowledge [role="tablist"]');
  await expect(tablist).toBeVisible();
  await expect(tablist).toHaveAttribute('aria-label', 'Training and knowledge sections');

  // Default: skills tab is selected
  const skillsTab = page.locator('#tk-tab-skills');
  await expect(skillsTab).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#tk-panel-skills')).toBeVisible();

  // Click courses tab — aria-selected should shift
  await page.locator('#tk-tab-courses').click();
  await expect(page.locator('#tk-tab-skills')).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#tk-tab-courses')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#tk-panel-courses')).toBeVisible();
  await expect(page.locator('#tk-panel-skills')).not.toBeVisible();

  // Click flashcards tab
  await page.locator('#tk-tab-flashcards').click();
  await expect(page.locator('#tk-tab-courses')).toHaveAttribute('aria-selected', 'false');
  await expect(page.locator('#tk-tab-flashcards')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('#tk-panel-flashcards')).toBeVisible();
});

test('training-knowledge cross-training matrix modal has dialog semantics and receives focus on open', async ({ page }) => {
  await bootWorkspace(page, 'nightops', '/training-knowledge');

  // Modal should be hidden initially
  const modal = page.locator('#tk-matrix-modal');
  await expect(modal).toHaveClass(/is-hidden/);
  await expect(modal).toHaveAttribute('role', 'dialog');
  await expect(modal).toHaveAttribute('aria-modal', 'true');
  await expect(modal).toHaveAttribute('aria-labelledby', 'tk-matrix-title');

  // Open the modal
  await page.locator('button', { hasText: 'Cross-Training Matrix' }).click();
  await expect(modal).not.toHaveClass(/is-hidden/);

  // Close button should have focus after open
  const closeBtn = page.locator('#tk-matrix-close');
  await expect(closeBtn).toBeFocused();
  await expect(closeBtn).toHaveAttribute('aria-label', 'Close cross-training matrix');

  // Close via the close button
  await closeBtn.click();
  await expect(modal).toHaveClass(/is-hidden/);
});

[
  { name: 'notes', path: '/notes?tab=notes', visibleSelector: '#tab-notes', allowedEndpoints: [] },
  { name: 'settings', path: '/settings?tab=settings', visibleSelector: '#tab-settings', allowedEndpoints: ['/api/content-summary'] },
  { name: 'maps', path: '/maps?tab=maps', visibleSelector: '#tab-maps', allowedEndpoints: [] },
  { name: 'loadout', path: '/loadout?tab=loadout', visibleSelector: '#tab-loadout', allowedEndpoints: [] },
].forEach(({ name, path, visibleSelector, allowedEndpoints }) => {
  test(`non-services route ${name} avoids home-dashboard fetches and tolerates LAN status updates`, async ({ page }) => {
    const requests = [];
    const pageErrors = [];
    const servicesOnlyEndpoints = [
      '/api/dashboard/widgets',
      '/api/needs',
      '/api/system/getting-started',
      '/api/dashboard/overview',
      '/api/dashboard/critical',
      '/api/dashboard/checklists',
      '/api/dashboard/live',
      '/api/content-summary',
      '/api/activity?limit=30',
      '/api/downloads/active',
    ];

    page.on('request', (request) => {
      requests.push(normalizeRequestPath(request.url()));
    });
    page.on('pageerror', (error) => {
      pageErrors.push(error.message);
    });

    await page.route('**/api/network', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          online: true,
          lan_ip: '192.168.50.24',
          dashboard_url: 'http://192.168.50.24:8080',
        }),
      });
    });

    await bootWorkspace(page, 'nightops', path);
    await page.waitForTimeout(1400);

    await expect(page.locator(visibleSelector)).toBeVisible();
    await expect(page.locator('#lan-banner')).toHaveCount(0);
    expect(pageErrors).toEqual([]);

    const leakedEndpoints = servicesOnlyEndpoints.filter((endpoint) =>
      !allowedEndpoints.includes(endpoint) &&
      requests.some((requestUrl) => requestUrl.includes(endpoint))
    );
    expect(leakedEndpoints).toEqual([]);
  });
});
