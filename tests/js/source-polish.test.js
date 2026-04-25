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
});
