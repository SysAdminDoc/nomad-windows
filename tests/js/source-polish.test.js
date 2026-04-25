import { describe, expect, it } from 'vitest';
import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';

const ROOT = process.cwd();
const SCAN_ROOTS = ['web/templates/index_partials', 'web/static/js'];

function walk(dir) {
  const entries = readdirSync(dir, { withFileTypes: true });
  return entries.flatMap(entry => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === 'dist' || entry.name === 'vendor') return [];
      return walk(path);
    }
    return /\.(html|js|mjs)$/.test(entry.name) ? [path] : [];
  });
}

describe('source polish guardrails', () => {
  it('keeps browser-native dialogs out of user-facing source', () => {
    const offenders = [];

    for (const root of SCAN_ROOTS) {
      for (const file of walk(join(ROOT, root))) {
        const lines = readFileSync(file, 'utf8').split(/\r?\n/);
        lines.forEach((line, index) => {
          if (/\b(?:window\.)?confirm\s*\(/.test(line) || /\b(?:window\.)?prompt\s*\(/.test(line)) {
            offenders.push(`${relative(ROOT, file)}:${index + 1}:${line.trim()}`);
          }
        });
      }
    }

    expect(offenders).toEqual([]);
  });

  it('keeps tab-local JSON helpers on the shared API client', () => {
    const offenders = [];
    const rawHelperPatterns = [
      /const api\s*=\s*\(url,\s*opts\)\s*=>\s*fetch\(url,\s*opts\)\.then\(r\s*=>\s*r\.json\(\)\)/,
      /const api=\(url,opts\)=>fetch\(url,opts\)\.then\(r=>r\.json\(\)\)/,
      /var api\s*=\s*function\(url,\s*opts\)\s*\{\s*return fetch\(url,\s*opts\)\.then/,
    ];

    for (const root of SCAN_ROOTS) {
      for (const file of walk(join(ROOT, root))) {
        const text = readFileSync(file, 'utf8');
        if (rawHelperPatterns.some(pattern => pattern.test(text))) {
          offenders.push(relative(ROOT, file));
        }
      }
    }

    expect(offenders).toEqual([]);
  });
});
