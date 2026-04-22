/**
 * Pure utility functions extracted from template JS for unit testing.
 * Functions here are identical in logic to their template counterparts
 * in _app_core_shell.js, _app_dashboard_readiness.js, _app_workspace_memory.js.
 */

// ─── escapeHtml (_app_core_shell.js) ──────────────────────────────────────────
// Uses a throwaway <div> to leverage the browser's own HTML escaping.
let _escDiv = null;
export function escapeHtml(s) {
  if (s == null) return '';
  if (!_escDiv) _escDiv = document.createElement('div');
  _escDiv.textContent = s;
  return _escDiv.innerHTML;
}

// ─── formatBytes (_app_core_shell.js) ─────────────────────────────────────────
export function formatBytes(b) {
  if (b >= 1073741824) return (b / 1073741824).toFixed(1) + ' GB';
  if (b >= 1048576) return (b / 1048576).toFixed(1) + ' MB';
  if (b >= 1024) return (b / 1024).toFixed(0) + ' KB';
  return b + ' B';
}

// ─── timeAgo (_app_dashboard_readiness.js) ────────────────────────────────────
export function timeAgo(dateStr) {
  const d = new Date(dateStr);
  const now = new Date();
  const diffMs = now - d;
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'Just now';
  if (mins < 60) return mins + 'm ago';
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  const days = Math.floor(hrs / 24);
  return days + 'd ago';
}

// ─── parseInventoryCommand (VoiceInput.parseInventoryCommand, _app_core_shell.js) ──
export function parseInventoryCommand(text) {
  const t = text.toLowerCase().trim();
  let action = 'add';
  let cleaned = t;
  if (t.startsWith('remove ') || t.startsWith('delete ') || t.startsWith('subtract ')) {
    action = 'remove';
    cleaned = t.replace(/^(remove|delete|subtract)\s+/, '');
  } else if (t.startsWith('add ')) {
    cleaned = t.replace(/^add\s+/, '');
  }

  const qtyMatch = cleaned.match(/^(\d+(?:\.\d+)?)\s+/);
  let quantity = 1;
  if (qtyMatch) {
    quantity = parseFloat(qtyMatch[1]);
    cleaned = cleaned.slice(qtyMatch[0].length);
  }

  const unitMatch = cleaned.match(/^(cans?|bottles?|gallons?|liters?|pounds?|lbs?|boxes?|bags?|packs?|rolls?|pairs?|units?|pieces?|each|dozen)\s+(of\s+)?/i);
  let unit = 'units';
  if (unitMatch) {
    unit = unitMatch[1].replace(/s$/, '');
    cleaned = cleaned.slice(unitMatch[0].length);
  }

  const locMatch = cleaned.match(/\s+(to|in|at|for)\s+(.+?)$/i);
  let location = '';
  if (locMatch) {
    location = locMatch[2].trim();
    cleaned = cleaned.slice(0, locMatch.index);
  }

  let category = 'general';
  const catMap = {
    food: ['bean', 'rice', 'pasta', 'flour', 'sugar', 'salt', 'canned', 'meat', 'fruit', 'vegetable', 'soup', 'coffee', 'tea', 'oil', 'honey', 'oat'],
    water: ['water', 'purif', 'filter'],
    medical: ['bandage', 'gauze', 'aspirin', 'ibuprofen', 'antibiotic', 'medicine', 'med ', 'first aid', 'tourniquet'],
    tools: ['knife', 'saw', 'hammer', 'wrench', 'tape', 'rope', 'cord', 'wire', 'tool'],
    fuel: ['gas', 'diesel', 'propane', 'kerosene', 'fuel', 'butane', 'charcoal'],
    ammo: ['ammo', 'ammunition', 'round', 'bullet', 'shell', 'cartridge'],
    hygiene: ['soap', 'shampoo', 'toothpaste', 'toilet paper', 'sanitizer', 'wipes'],
    electronics: ['battery', 'batteries', 'radio', 'flashlight', 'lantern', 'solar', 'charger'],
  };
  for (const [cat, keywords] of Object.entries(catMap)) {
    if (keywords.some(k => cleaned.includes(k))) { category = cat; break; }
  }

  return { action, name: cleaned.trim(), quantity, unit, category, location };
}

// ─── _parseSearchBang (_app_workspace_memory.js) ──────────────────────────────
const _SEARCH_BANGS = {
  '/i ': 'inventory', '/inv ': 'inventory',
  '/c ': 'contact', '/con ': 'contact',
  '/n ': 'note', '/not ': 'note',
  '/m ': 'patient', '/med ': 'patient',
  '/w ': 'waypoint', '/map ': 'waypoint',
  '/f ': 'frequency', '/freq ': 'frequency',
  '/d ': 'document', '/doc ': 'document',
  '/t ': 'checklist', '/task ': 'checklist',
  '/e ': 'equipment', '/eq ': 'equipment',
  '/a ': 'ammo',
  '/s ': 'skill',
};

export function parseSearchBang(q) {
  const lower = q.toLowerCase();
  for (const [prefix, type] of Object.entries(_SEARCH_BANGS)) {
    if (lower.startsWith(prefix)) return { type, query: q.slice(prefix.length).trim() };
  }
  return null;
}
