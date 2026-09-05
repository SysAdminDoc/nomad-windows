#!/usr/bin/env node

import { spawn, spawnSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';

const toolDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.dirname(toolDir);
const outputDir = path.join(repoRoot, 'docs', 'media');
const externalBaseUrl = (process.env.NOMAD_CAPTURE_BASE_URL || '').replace(/\/+$/, '');
if (externalBaseUrl) {
  const externalUrl = new URL(externalBaseUrl);
  const loopbackHosts = new Set(['127.0.0.1', 'localhost', '::1']);
  if (!loopbackHosts.has(externalUrl.hostname)) {
    throw new Error('NOMAD_CAPTURE_BASE_URL must use a loopback host');
  }
  if (process.env.NOMAD_CAPTURE_ISOLATED !== '1') {
    throw new Error('Set NOMAD_CAPTURE_ISOLATED=1 only after confirming the packaged build uses a disposable profile');
  }
}
const runtimeDir = externalBaseUrl ? null : fs.mkdtempSync(path.join(os.tmpdir(), 'nomad-marketing-'));
const appDataDir = runtimeDir ? path.join(runtimeDir, 'appdata') : null;
const localAppDataDir = runtimeDir ? path.join(runtimeDir, 'localappdata') : null;
const serverLog = [];

fs.mkdirSync(outputDir, { recursive: true });
if (runtimeDir) {
  fs.mkdirSync(appDataDir, { recursive: true });
  fs.mkdirSync(localAppDataDir, { recursive: true });
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const listener = net.createServer();
    listener.unref();
    listener.on('error', reject);
    listener.listen(0, '127.0.0.1', () => {
      const address = listener.address();
      listener.close(() => resolve(address.port));
    });
  });
}

async function waitForServer(baseUrl, timeoutMs = 90000) {
  const deadline = Date.now() + timeoutMs;
  let lastError;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${baseUrl}/api/health`);
      if (response.ok) return;
      lastError = new Error(`Health endpoint returned ${response.status}`);
    } catch (error) {
      lastError = error;
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error(`NOMAD did not start: ${lastError?.message || 'timeout'}`);
}

async function postJson(baseUrl, route, payload = {}) {
  const response = await fetch(`${baseUrl}${route}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${route} returned ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

async function seedRepresentativeData(baseUrl) {
  const inventory = [
    { name: 'Drinking Water, 1 gal', category: 'water', quantity: 84, unit: 'gal', min_quantity: 56, daily_usage: 4, location: 'Utility Room' },
    { name: 'Black Beans, 15 oz', category: 'food', quantity: 24, unit: 'cans', min_quantity: 12, daily_usage: 1, location: 'Pantry A' },
    { name: 'Long Grain Rice', category: 'food', quantity: 30, unit: 'lb', min_quantity: 15, daily_usage: 0.5, location: 'Pantry A' },
    { name: 'Rolled Oats', category: 'food', quantity: 12, unit: 'lb', min_quantity: 6, daily_usage: 0.25, location: 'Pantry B' },
    { name: 'Peanut Butter', category: 'food', quantity: 10, unit: 'jars', min_quantity: 4, daily_usage: 0.15, location: 'Pantry B' },
    { name: 'Canned Chicken', category: 'food', quantity: 18, unit: 'cans', min_quantity: 8, daily_usage: 0.5, location: 'Pantry B' },
    { name: 'Powdered Milk', category: 'food', quantity: 8, unit: 'pouches', min_quantity: 4, daily_usage: 0.2, location: 'Pantry C' },
    { name: 'Electrolyte Mix', category: 'food', quantity: 36, unit: 'packets', min_quantity: 16, daily_usage: 1, location: 'Pantry C' },
    { name: 'Trauma Dressings', category: 'medical', quantity: 12, unit: 'ea', min_quantity: 6, location: 'Medical Case' },
    { name: 'Sterile Gauze, 4 x 4', category: 'medical', quantity: 40, unit: 'packs', min_quantity: 20, location: 'Medical Case' },
    { name: 'Nitrile Gloves', category: 'medical', quantity: 100, unit: 'pairs', min_quantity: 50, location: 'Medical Case' },
    { name: 'Saline Wash', category: 'medical', quantity: 8, unit: 'bottles', min_quantity: 4, location: 'Medical Case' },
    { name: 'Elastic Bandages', category: 'medical', quantity: 10, unit: 'ea', min_quantity: 5, location: 'Medical Case' },
    { name: 'Burn Dressings', category: 'medical', quantity: 6, unit: 'ea', min_quantity: 3, location: 'Medical Case' },
    { name: 'Instant Cold Packs', category: 'medical', quantity: 8, unit: 'ea', min_quantity: 4, location: 'Medical Case' },
    { name: 'CPR Face Shield', category: 'medical', quantity: 4, unit: 'ea', min_quantity: 2, location: 'Medical Case' },
  ];
  for (const item of inventory) await postJson(baseUrl, '/api/inventory', item);

  const contacts = [
    { name: 'Household Lead', callsign: 'BASE', role: 'Coordinator', skills: 'Planning, logistics', blood_type: 'O+' },
    { name: 'Medical Contact', callsign: 'MEDIC', role: 'First Aid', skills: 'EMT, first aid', blood_type: 'A+' },
    { name: 'Neighbor Team', callsign: 'NORTH', role: 'Mutual Aid', skills: 'Radio, utilities', blood_type: 'O-' },
    { name: 'County Emergency Management', callsign: 'EOC', role: 'Public Safety', freq: '155.475 MHz' },
    { name: 'Utility Dispatch', callsign: 'POWER', role: 'Utilities' },
  ];
  for (const contact of contacts) await postJson(baseUrl, '/api/contacts', contact);

  await postJson(baseUrl, '/api/checklists', {
    name: '72 Hour Readiness Review',
    items: [
      { text: 'Confirm water reserve', checked: true },
      { text: 'Rotate pantry stock', checked: true },
      { text: 'Test radios', checked: true },
      { text: 'Review contact plan', checked: true },
    ],
  });
  await postJson(baseUrl, '/api/settings/wizard-complete');
}

async function capturePage(context, baseUrl, route, filename, readySelector, prepare) {
  const page = await context.newPage();
  const errors = [];
  const onPageError = (error) => errors.push(`pageerror: ${error.message}`);
  const onConsole = (message) => {
    if (message.type() === 'error') errors.push(`console: ${message.text()}`);
  };
  page.on('pageerror', onPageError);
  page.on('console', onConsole);
  try {
    await page.goto(`${baseUrl}${route}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForSelector('#main-content', { state: 'visible', timeout: 30000 });
    if (prepare) await prepare(page);
    await page.waitForSelector(readySelector, { state: 'visible', timeout: 30000 });
    await page.addStyleTag({ content: '* { caret-color: transparent !important; } html { scroll-behavior: auto !important; }' });
    await page.waitForTimeout(700);
    await page.screenshot({ path: path.join(outputDir, filename), animations: 'disabled' });
    if (errors.length) throw new Error(`${filename} emitted browser errors:\n${errors.join('\n')}`);
    console.log(`Captured ${filename}`);
  } finally {
    page.off('pageerror', onPageError);
    page.off('console', onConsole);
    await page.close();
  }
}

const port = externalBaseUrl ? null : await findFreePort();
const baseUrl = externalBaseUrl || `http://127.0.0.1:${port}`;
let server;

if (!externalBaseUrl) {
  const python = process.platform === 'win32'
    ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoRoot, '.venv', 'bin', 'python');
  if (!fs.existsSync(python)) throw new Error(`Project virtual environment not found: ${python}`);

  server = spawn(python, [
    '-m', 'flask', '--app', 'web.app', 'run',
    '--host', '127.0.0.1', '--port', String(port), '--no-debugger', '--no-reload',
  ], {
    cwd: repoRoot,
    env: {
      ...process.env,
      APPDATA: appDataDir,
      LOCALAPPDATA: localAppDataDir,
      NOMAD_AUTH_REQUIRED: '0',
      PYTHONUNBUFFERED: '1',
    },
    windowsHide: true,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout.on('data', (chunk) => serverLog.push(chunk.toString()));
  server.stderr.on('data', (chunk) => serverLog.push(chunk.toString()));
} else {
  console.log(`Capturing from packaged NOMAD server at ${baseUrl}`);
}

let browser;
try {
  await waitForServer(baseUrl);
  await seedRepresentativeData(baseUrl);
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1600, height: 1000 },
    deviceScaleFactor: 1,
    colorScheme: 'dark',
    reducedMotion: 'reduce',
  });
  await context.addInitScript(() => {
    localStorage.setItem('nomad-theme', 'nightops');
    localStorage.setItem('nomad-density', 'compact');
  });
  await capturePage(context, baseUrl, '/readiness', 'readiness-dashboard.png', '#readiness-score-panel', async (currentPage) => {
    await currentPage.waitForFunction(() => document.querySelector('#readiness-score-panel')?.textContent?.includes('/100'));
  });
  await capturePage(context, baseUrl, '/preparedness', 'preparedness-workflows.png', '.prep-scenario-card');
  await capturePage(context, baseUrl, '/preparedness', 'inventory-planning.png', '#psub-inventory', async (currentPage) => {
    await currentPage.waitForFunction(() => typeof switchPrepSub === 'function');
    await currentPage.waitForTimeout(800);
    await currentPage.evaluate(() => switchPrepSub('inventory'));
    await currentPage.waitForFunction(() => document.querySelectorAll('#inv-tbody tr').length >= 10);
    await currentPage.waitForFunction(() => document.querySelector('#psub-inventory')?.classList.contains('active'));
    await currentPage.locator('#psub-inventory .prep-heading').evaluate((element) => {
      element.scrollIntoView({ block: 'start', inline: 'nearest' });
      let parent = element.parentElement;
      while (parent && parent.scrollHeight <= parent.clientHeight) parent = parent.parentElement;
      if (parent) parent.scrollTop = Math.max(0, parent.scrollTop - 120);
    });
  });
  await capturePage(context, baseUrl, '/maps', 'offline-maps.png', '#tab-maps');
  await capturePage(context, baseUrl, '/library', 'offline-library.png', '#tab-kiwix-library');

  await context.close();
} catch (error) {
  const tail = serverLog.join('').split(/\r?\n/).slice(-30).join('\n');
  if (tail) console.error(`Server log tail:\n${tail}`);
  throw error;
} finally {
  if (browser) await browser.close();
  if (server && server.exitCode === null) {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(server.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' });
    } else {
      server.kill('SIGTERM');
    }
  }
  if (server) {
    await new Promise((resolve) => {
      if (server.exitCode !== null) return resolve();
      server.once('exit', resolve);
      setTimeout(resolve, 5000).unref();
    });
  }
  if (runtimeDir) {
    await new Promise((resolve) => setTimeout(resolve, 1000));
    try {
      fs.rmSync(runtimeDir, { recursive: true, force: true, maxRetries: 60, retryDelay: 250 });
    } catch (error) {
      console.warn(`Could not remove temporary capture data: ${error.message}`);
    }
  }
}
