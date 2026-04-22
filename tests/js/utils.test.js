import { describe, it, expect, vi, beforeEach } from 'vitest';
import { escapeHtml, formatBytes, timeAgo, parseInventoryCommand, parseSearchBang } from './utils.js';

// ─── escapeHtml ────────────────────────────────────────────────────────────────

describe('escapeHtml', () => {
  it('returns empty string for null', () => {
    expect(escapeHtml(null)).toBe('');
  });

  it('returns empty string for undefined', () => {
    expect(escapeHtml(undefined)).toBe('');
  });

  it('passes plain text through unchanged', () => {
    expect(escapeHtml('hello world')).toBe('hello world');
  });

  it('escapes < and >', () => {
    expect(escapeHtml('<script>')).toBe('&lt;script&gt;');
  });

  it('escapes &', () => {
    expect(escapeHtml('a & b')).toBe('a &amp; b');
  });

  it('escapes double quotes', () => {
    expect(escapeHtml('"quoted"')).toBe('"quoted"');
  });

  it('escapes a full XSS payload', () => {
    const result = escapeHtml('<img src=x onerror=alert(1)>');
    expect(result).not.toContain('<img');
    expect(result).toContain('&lt;img');
  });

  it('handles numeric input', () => {
    expect(escapeHtml(42)).toBe('42');
  });
});

// ─── formatBytes ──────────────────────────────────────────────────────────────

describe('formatBytes', () => {
  it('formats bytes', () => {
    expect(formatBytes(512)).toBe('512 B');
  });

  it('formats kilobytes', () => {
    expect(formatBytes(2048)).toBe('2 KB');
  });

  it('formats megabytes', () => {
    expect(formatBytes(5 * 1048576)).toBe('5.0 MB');
  });

  it('formats gigabytes', () => {
    expect(formatBytes(2 * 1073741824)).toBe('2.0 GB');
  });

  it('handles 0 bytes', () => {
    expect(formatBytes(0)).toBe('0 B');
  });
});

// ─── timeAgo ──────────────────────────────────────────────────────────────────

describe('timeAgo', () => {
  it('returns "Just now" for timestamps less than 1 minute ago', () => {
    const recent = new Date(Date.now() - 30 * 1000).toISOString();
    expect(timeAgo(recent)).toBe('Just now');
  });

  it('returns minutes for timestamps under 1 hour', () => {
    const t = new Date(Date.now() - 15 * 60 * 1000).toISOString();
    expect(timeAgo(t)).toBe('15m ago');
  });

  it('returns hours for timestamps under 24 hours', () => {
    const t = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(t)).toBe('3h ago');
  });

  it('returns days for timestamps over 24 hours', () => {
    const t = new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString();
    expect(timeAgo(t)).toBe('2d ago');
  });

  it('returns exactly 1m ago at 60 seconds', () => {
    const t = new Date(Date.now() - 61 * 1000).toISOString();
    expect(timeAgo(t)).toBe('1m ago');
  });
});

// ─── parseInventoryCommand ────────────────────────────────────────────────────

describe('parseInventoryCommand', () => {
  it('defaults action to add', () => {
    const r = parseInventoryCommand('10 cans of beans');
    expect(r.action).toBe('add');
  });

  it('detects remove action', () => {
    expect(parseInventoryCommand('remove 5 batteries').action).toBe('remove');
  });

  it('detects delete as remove', () => {
    expect(parseInventoryCommand('delete 2 gallons water').action).toBe('remove');
  });

  it('detects subtract as remove', () => {
    expect(parseInventoryCommand('subtract 3 boxes of rice').action).toBe('remove');
  });

  it('strips "add" prefix from name', () => {
    const r = parseInventoryCommand('add 5 cans soup');
    expect(r.name).not.toMatch(/^add/);
  });

  it('parses quantity correctly', () => {
    expect(parseInventoryCommand('20 gallons of water').quantity).toBe(20);
  });

  it('defaults quantity to 1 when not specified', () => {
    expect(parseInventoryCommand('flashlight').quantity).toBe(1);
  });

  it('parses decimal quantities', () => {
    expect(parseInventoryCommand('2.5 gallons water').quantity).toBe(2.5);
  });

  it('parses unit from input', () => {
    const r = parseInventoryCommand('3 cans of beans');
    expect(r.unit).toBe('can');
  });

  it('defaults unit to "units"', () => {
    const r = parseInventoryCommand('5 aspirin');
    expect(r.unit).toBe('units');
  });

  it('extracts location with "to" keyword', () => {
    const r = parseInventoryCommand('10 cans of beans to pantry');
    expect(r.location).toBe('pantry');
  });

  it('extracts location with "in" keyword', () => {
    const r = parseInventoryCommand('2 gallons water in garage');
    expect(r.location).toBe('garage');
  });

  it('categorizes food correctly', () => {
    expect(parseInventoryCommand('5 cans of beans').category).toBe('food');
  });

  it('categorizes water correctly', () => {
    expect(parseInventoryCommand('10 gallons water').category).toBe('water');
  });

  it('categorizes medical correctly', () => {
    expect(parseInventoryCommand('4 bandage').category).toBe('medical');
  });

  it('categorizes electronics correctly', () => {
    expect(parseInventoryCommand('12 batteries').category).toBe('electronics');
  });

  it('categorizes fuel correctly', () => {
    expect(parseInventoryCommand('5 gallons propane').category).toBe('fuel');
  });

  it('defaults category to general for unknown items', () => {
    expect(parseInventoryCommand('3 widgets').category).toBe('general');
  });
});

// ─── parseSearchBang ──────────────────────────────────────────────────────────

describe('parseSearchBang', () => {
  it('returns null for plain queries', () => {
    expect(parseSearchBang('hello world')).toBeNull();
  });

  it('returns null for empty string', () => {
    expect(parseSearchBang('')).toBeNull();
  });

  it('parses /i bang to inventory', () => {
    const r = parseSearchBang('/i rice');
    expect(r).toEqual({ type: 'inventory', query: 'rice' });
  });

  it('parses /inv bang to inventory', () => {
    const r = parseSearchBang('/inv water');
    expect(r).toEqual({ type: 'inventory', query: 'water' });
  });

  it('parses /c bang to contact', () => {
    const r = parseSearchBang('/c John');
    expect(r).toEqual({ type: 'contact', query: 'John' });
  });

  it('parses /n bang to note', () => {
    const r = parseSearchBang('/n evacuation plan');
    expect(r).toEqual({ type: 'note', query: 'evacuation plan' });
  });

  it('parses /med bang to patient', () => {
    const r = parseSearchBang('/med aspirin');
    expect(r).toEqual({ type: 'patient', query: 'aspirin' });
  });

  it('parses /w bang to waypoint', () => {
    const r = parseSearchBang('/w cache');
    expect(r).toEqual({ type: 'waypoint', query: 'cache' });
  });

  it('parses /a bang to ammo', () => {
    const r = parseSearchBang('/a 9mm');
    expect(r).toEqual({ type: 'ammo', query: '9mm' });
  });

  it('is case-insensitive for bang prefix', () => {
    const r = parseSearchBang('/I rice');
    expect(r).not.toBeNull();
    expect(r.type).toBe('inventory');
  });

  it('trims whitespace from the extracted query', () => {
    const r = parseSearchBang('/i   extra spaces  ');
    expect(r.query).toBe('extra spaces');
  });

  it('does not match bang without trailing space', () => {
    // '/i' without a space after it is not a valid bang
    expect(parseSearchBang('/irice')).toBeNull();
  });
});
