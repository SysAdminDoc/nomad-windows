"""Roadmap P2-P5 features — recipes, batteries, warranties, AI skills,
AI usage analytics, URL monitors, personal RSS feeds, calendar events,
dashboard templates, service health history, inventory locations,
per-conversation KB scope, ICS import, OPML import, dashboard config
export/import, minimal mode, env var injection in config."""

import json
import io
import os
import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response
from db import db_session, log_activity
from web.blueprints import get_pagination, error_response

roadmap_bp = Blueprint('roadmap_features', __name__)
_log = logging.getLogger('nomad.roadmap')


# ═══════════════════════════════════════════════════════════════════════
# P2-04: Recipe-Driven Consumption
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/recipes')
def api_recipes_list():
    limit, offset = get_pagination()
    with db_session() as db:
        rows = db.execute('SELECT * FROM recipes ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/recipes/<int:rid>')
def api_recipe_detail(rid):
    with db_session() as db:
        r = db.execute('SELECT * FROM recipes WHERE id = ?', (rid,)).fetchone()
        if not r:
            return error_response('Recipe not found', 404)
        ingredients = db.execute(
            'SELECT * FROM recipe_ingredients WHERE recipe_id = ? ORDER BY id', (rid,)
        ).fetchall()
        result = dict(r)
        result['ingredients'] = [dict(i) for i in ingredients]
        return jsonify(result)


@roadmap_bp.route('/api/recipes', methods=['POST'])
def api_recipe_create():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return error_response('Name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO recipes (name, servings, prep_time_min, cook_time_min, instructions, source_url, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, d.get('servings', 4), d.get('prep_time_min', 0), d.get('cook_time_min', 0),
             d.get('instructions', ''), d.get('source_url', ''), d.get('notes', ''))
        )
        rid = cur.lastrowid
        for ing in d.get('ingredients', []):
            db.execute(
                'INSERT INTO recipe_ingredients (recipe_id, inventory_id, name, quantity, unit, calories_per_unit) VALUES (?, ?, ?, ?, ?, ?)',
                (rid, ing.get('inventory_id'), ing.get('name', ''), ing.get('quantity', 1),
                 ing.get('unit', ''), ing.get('calories_per_unit', 0))
            )
        db.commit()
        log_activity('recipe_created', d.get('name', ''))
        return jsonify({'id': rid}), 201


@roadmap_bp.route('/api/recipes/<int:rid>', methods=['PUT'])
def api_recipe_update(rid):
    d = request.get_json() or {}
    with db_session() as db:
        row = db.execute('SELECT id FROM recipes WHERE id = ?', (rid,)).fetchone()
        if not row:
            return error_response('Recipe not found', 404)
        allowed = ['name', 'servings', 'prep_time_min', 'cook_time_min', 'instructions', 'source_url', 'notes']
        sets = []
        vals = []
        for col in allowed:
            if col in d:
                sets.append(f'{col} = ?')
                vals.append(d[col])
        if sets:
            vals.append(rid)
            db.execute(f'UPDATE recipes SET {", ".join(sets)} WHERE id = ?', vals)
        if 'ingredients' in d:
            db.execute('DELETE FROM recipe_ingredients WHERE recipe_id = ?', (rid,))
            for ing in d['ingredients']:
                db.execute(
                    'INSERT INTO recipe_ingredients (recipe_id, inventory_id, name, quantity, unit, calories_per_unit) VALUES (?, ?, ?, ?, ?, ?)',
                    (rid, ing.get('inventory_id'), ing.get('name', ''), ing.get('quantity', 1),
                     ing.get('unit', ''), ing.get('calories_per_unit', 0))
                )
        db.commit()
        return jsonify({'status': 'updated'})


@roadmap_bp.route('/api/recipes/<int:rid>', methods=['DELETE'])
def api_recipe_delete(rid):
    with db_session() as db:
        if db.execute('DELETE FROM recipes WHERE id = ?', (rid,)).rowcount == 0:
            return error_response('Recipe not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


@roadmap_bp.route('/api/recipes/<int:rid>/cook', methods=['POST'])
def api_recipe_cook(rid):
    """Cook a recipe: deduct ingredient quantities from inventory."""
    d = request.get_json() or {}
    servings_mult = max(0.1, d.get('servings_multiplier', 1.0))
    with db_session() as db:
        recipe = db.execute('SELECT * FROM recipes WHERE id = ?', (rid,)).fetchone()
        if not recipe:
            return error_response('Recipe not found', 404)
        ingredients = db.execute(
            'SELECT * FROM recipe_ingredients WHERE recipe_id = ?', (rid,)
        ).fetchall()
        deducted = []
        for ing in ingredients:
            if not ing['inventory_id']:
                continue
            qty_needed = (ing['quantity'] or 1) * servings_mult
            inv = db.execute('SELECT id, name, quantity FROM inventory WHERE id = ?', (ing['inventory_id'],)).fetchone()
            if inv:
                new_qty = max(0, (inv['quantity'] or 0) - qty_needed)
                db.execute('UPDATE inventory SET quantity = ? WHERE id = ?', (new_qty, inv['id']))
                deducted.append({'item': inv['name'], 'deducted': round(qty_needed, 2), 'remaining': round(new_qty, 2)})
        db.commit()
        log_activity('recipe_cooked', recipe['name'])
        return jsonify({'recipe': recipe['name'], 'deducted': deducted})


# ═══════════════════════════════════════════════════════════════════════
# P2-09: Inventory Location Hierarchy
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/inventory/locations')
def api_locations_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM inventory_locations ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/inventory/locations', methods=['POST'])
def api_location_create():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return error_response('Name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO inventory_locations (name, parent_id, description) VALUES (?, ?, ?)',
            (name, d.get('parent_id'), d.get('description', ''))
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/inventory/locations/<int:lid>', methods=['DELETE'])
def api_location_delete(lid):
    with db_session() as db:
        if db.execute('DELETE FROM inventory_locations WHERE id = ?', (lid,)).rowcount == 0:
            return error_response('Location not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


@roadmap_bp.route('/api/inventory/locations/tree')
def api_location_tree():
    """Return locations as a nested tree."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM inventory_locations ORDER BY name').fetchall()
        nodes = {r['id']: {**dict(r), 'children': []} for r in rows}
        roots = []
        for n in nodes.values():
            pid = n.get('parent_id')
            if pid and pid in nodes:
                nodes[pid]['children'].append(n)
            else:
                roots.append(n)
        return jsonify(roots)


# ═══════════════════════════════════════════════════════════════════════
# P2-12: Service Health History
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/services/health-history/<service_id>')
def api_service_health_history(service_id):
    hours = request.args.get('hours', '24')
    try:
        hours = min(720, max(1, int(hours)))
    except (ValueError, TypeError):
        hours = 24
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM service_health_log WHERE service_id = ? AND checked_at > datetime('now', ? || ' hours') ORDER BY checked_at",
            (service_id, f'-{hours}')
        ).fetchall()
        return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════════
# P2-21: Battery/Consumable Tracker
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/batteries')
def api_batteries_list():
    limit, offset = get_pagination()
    with db_session() as db:
        rows = db.execute('SELECT * FROM battery_tracker ORDER BY device_name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/batteries', methods=['POST'])
def api_battery_create():
    d = request.get_json() or {}
    name = (d.get('device_name') or '').strip()
    if not name:
        return error_response('Device name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO battery_tracker (device_name, battery_type, quantity, installed_date, expected_life_days, notes) VALUES (?, ?, ?, ?, ?, ?)',
            (name, d.get('battery_type', ''), d.get('quantity', 1), d.get('installed_date', ''),
             d.get('expected_life_days', 365), d.get('notes', ''))
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/batteries/<int:bid>', methods=['PUT'])
def api_battery_update(bid):
    d = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT id FROM battery_tracker WHERE id = ?', (bid,)).fetchone():
            return error_response('Not found', 404)
        allowed = ['device_name', 'battery_type', 'quantity', 'installed_date', 'expected_life_days', 'last_checked', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in d:
                sets.append(f'{col} = ?')
                vals.append(d[col])
        if sets:
            vals.append(bid)
            db.execute(f'UPDATE battery_tracker SET {", ".join(sets)} WHERE id = ?', vals)
            db.commit()
        return jsonify({'status': 'updated'})


@roadmap_bp.route('/api/batteries/<int:bid>', methods=['DELETE'])
def api_battery_delete(bid):
    with db_session() as db:
        if db.execute('DELETE FROM battery_tracker WHERE id = ?', (bid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════════
# P3-08: Insurance & Warranty Tracker
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/warranties')
def api_warranties_list():
    limit, offset = get_pagination()
    with db_session() as db:
        rows = db.execute('SELECT * FROM warranties ORDER BY expiry_date LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/warranties', methods=['POST'])
def api_warranty_create():
    d = request.get_json() or {}
    name = (d.get('item_name') or '').strip()
    if not name:
        return error_response('Item name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO warranties (item_name, category, purchase_date, expiry_date, provider, policy_number, coverage, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            (name, d.get('category', 'equipment'), d.get('purchase_date', ''), d.get('expiry_date', ''),
             d.get('provider', ''), d.get('policy_number', ''), d.get('coverage', ''), d.get('notes', ''))
        )
        db.commit()
        log_activity('warranty_created', name)
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/warranties/<int:wid>', methods=['PUT'])
def api_warranty_update(wid):
    d = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT id FROM warranties WHERE id = ?', (wid,)).fetchone():
            return error_response('Not found', 404)
        allowed = ['item_name', 'category', 'purchase_date', 'expiry_date', 'provider', 'policy_number', 'coverage', 'document_path', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in d:
                sets.append(f'{col} = ?')
                vals.append(d[col])
        if sets:
            vals.append(wid)
            db.execute(f'UPDATE warranties SET {", ".join(sets)} WHERE id = ?', vals)
            db.commit()
        return jsonify({'status': 'updated'})


@roadmap_bp.route('/api/warranties/<int:wid>', methods=['DELETE'])
def api_warranty_delete(wid):
    with db_session() as db:
        if db.execute('DELETE FROM warranties WHERE id = ?', (wid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════════
# P5-01: AI Skills / Domain Expertise Profiles
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/ai/skills')
def api_ai_skills_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM ai_skills ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/ai/skills', methods=['POST'])
def api_ai_skill_create():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return error_response('Name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO ai_skills (name, description, system_prompt, kb_scope, icon) VALUES (?, ?, ?, ?, ?)',
            (name, d.get('description', ''), d.get('system_prompt', ''), d.get('kb_scope', ''), d.get('icon', ''))
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/ai/skills/<int:sid>', methods=['PUT'])
def api_ai_skill_update(sid):
    d = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT id FROM ai_skills WHERE id = ?', (sid,)).fetchone():
            return error_response('Not found', 404)
        allowed = ['name', 'description', 'system_prompt', 'kb_scope', 'icon']
        sets, vals = [], []
        for col in allowed:
            if col in d:
                sets.append(f'{col} = ?')
                vals.append(d[col])
        if sets:
            vals.append(sid)
            db.execute(f'UPDATE ai_skills SET {", ".join(sets)} WHERE id = ?', vals)
            db.commit()
        return jsonify({'status': 'updated'})


@roadmap_bp.route('/api/ai/skills/<int:sid>', methods=['DELETE'])
def api_ai_skill_delete(sid):
    with db_session() as db:
        if db.execute('DELETE FROM ai_skills WHERE id = ?', (sid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════════
# P5-03: AI Usage Analytics
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/ai/usage')
def api_ai_usage():
    days = request.args.get('days', '30')
    try:
        days = min(365, max(1, int(days)))
    except (ValueError, TypeError):
        days = 30
    with db_session() as db:
        summary = db.execute(f'''
            SELECT model,
                   COUNT(*) as queries,
                   SUM(tokens_in) as total_in,
                   SUM(tokens_out) as total_out,
                   AVG(duration_ms) as avg_duration_ms
            FROM ai_usage_log
            WHERE created_at > datetime('now', '-{days} days')
            GROUP BY model ORDER BY queries DESC
        ''').fetchall()
        daily = db.execute(f'''
            SELECT DATE(created_at) as day, COUNT(*) as queries, SUM(tokens_in + tokens_out) as tokens
            FROM ai_usage_log
            WHERE created_at > datetime('now', '-{days} days')
            GROUP BY DATE(created_at) ORDER BY day
        ''').fetchall()
        return jsonify({
            'period_days': days,
            'models': [dict(r) for r in summary],
            'daily': [dict(r) for r in daily],
        })


@roadmap_bp.route('/api/ai/usage/log', methods=['POST'])
def api_ai_usage_log():
    d = request.get_json() or {}
    with db_session() as db:
        db.execute(
            'INSERT INTO ai_usage_log (model, tokens_in, tokens_out, duration_ms, rating, conversation_id) VALUES (?, ?, ?, ?, ?, ?)',
            (d.get('model', ''), d.get('tokens_in', 0), d.get('tokens_out', 0),
             d.get('duration_ms', 0), d.get('rating', 0), d.get('conversation_id'))
        )
        db.commit()
        return jsonify({'status': 'logged'}), 201


# ═══════════════════════════════════════════════════════════════════════
# P5-10: URL Monitor Widget
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/monitors')
def api_monitors_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM url_monitors ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/monitors', methods=['POST'])
def api_monitor_create():
    d = request.get_json() or {}
    url = (d.get('url') or '').strip()
    if not url:
        return error_response('URL is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO url_monitors (name, url, method, expected_status, check_interval_sec, enabled) VALUES (?, ?, ?, ?, ?, ?)',
            (d.get('name', url), url, d.get('method', 'GET'), d.get('expected_status', 200),
             d.get('check_interval_sec', 300), 1)
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/monitors/<int:mid>', methods=['DELETE'])
def api_monitor_delete(mid):
    with db_session() as db:
        if db.execute('DELETE FROM url_monitors WHERE id = ?', (mid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


@roadmap_bp.route('/api/monitors/<int:mid>/check', methods=['POST'])
def api_monitor_check(mid):
    """Manually trigger a health check on a monitor."""
    with db_session() as db:
        mon = db.execute('SELECT * FROM url_monitors WHERE id = ?', (mid,)).fetchone()
        if not mon:
            return error_response('Not found', 404)
    import requests as _req
    try:
        start = time.time()
        r = _req.request(mon['method'] or 'GET', mon['url'], timeout=15)
        elapsed = int((time.time() - start) * 1000)
        status = r.status_code
    except Exception:
        elapsed = 0
        status = 0
    with db_session() as db:
        ok = status == (mon['expected_status'] or 200)
        fails = 0 if ok else (mon['consecutive_failures'] or 0) + 1
        db.execute(
            'UPDATE url_monitors SET last_status = ?, last_checked = CURRENT_TIMESTAMP, last_response_ms = ?, consecutive_failures = ? WHERE id = ?',
            (status, elapsed, fails, mid)
        )
        db.commit()
    return jsonify({'status': status, 'response_ms': elapsed, 'ok': ok})


# ═══════════════════════════════════════════════════════════════════════
# P5-24: Personal RSS Feed Reader
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/feeds')
def api_feeds_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM personal_feeds ORDER BY title').fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/feeds', methods=['POST'])
def api_feed_create():
    d = request.get_json() or {}
    url = (d.get('url') or '').strip()
    if not url:
        return error_response('URL is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO personal_feeds (title, url, category) VALUES (?, ?, ?)',
            (d.get('title', url), url, d.get('category', 'general'))
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/feeds/<int:fid>', methods=['DELETE'])
def api_feed_delete(fid):
    with db_session() as db:
        if db.execute('DELETE FROM personal_feeds WHERE id = ?', (fid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


@roadmap_bp.route('/api/feeds/<int:fid>/items')
def api_feed_items(fid):
    limit, offset = get_pagination(default_limit=50)
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM personal_feed_items WHERE feed_id = ? ORDER BY published DESC LIMIT ? OFFSET ?',
            (fid, limit, offset)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/feeds/<int:fid>/refresh', methods=['POST'])
def api_feed_refresh(fid):
    """Fetch and cache RSS feed items."""
    with db_session() as db:
        feed = db.execute('SELECT * FROM personal_feeds WHERE id = ?', (fid,)).fetchone()
        if not feed:
            return error_response('Not found', 404)
    import requests as _req
    try:
        r = _req.get(feed['url'], timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as e:
        return error_response('Failed to fetch feed')
    items = []
    # RSS 2.0
    for item in root.iter('item'):
        items.append({
            'title': (item.findtext('title') or '')[:500],
            'link': (item.findtext('link') or '')[:2000],
            'summary': (item.findtext('description') or '')[:5000],
            'published': item.findtext('pubDate') or '',
        })
    # Atom
    if not items:
        ns = {'a': 'http://www.w3.org/2005/Atom'}
        for entry in root.findall('.//a:entry', ns):
            link_el = entry.find('a:link', ns)
            items.append({
                'title': (entry.findtext('a:title', '', ns) or '')[:500],
                'link': (link_el.get('href', '') if link_el is not None else '')[:2000],
                'summary': (entry.findtext('a:summary', '', ns) or '')[:5000],
                'published': entry.findtext('a:published', '', ns) or entry.findtext('a:updated', '', ns) or '',
            })
    with db_session() as db:
        db.execute('DELETE FROM personal_feed_items WHERE feed_id = ?', (fid,))
        for item in items[:200]:
            db.execute(
                'INSERT INTO personal_feed_items (feed_id, title, link, summary, published) VALUES (?, ?, ?, ?, ?)',
                (fid, item['title'], item['link'], item['summary'], item['published'])
            )
        db.execute('UPDATE personal_feeds SET last_fetched = CURRENT_TIMESTAMP, item_count = ? WHERE id = ?',
                   (len(items), fid))
        db.commit()
    return jsonify({'items_fetched': len(items)})


@roadmap_bp.route('/api/feeds/import-opml', methods=['POST'])
def api_import_opml():
    """P5-13: Import OPML file to bulk-add RSS feeds."""
    if 'file' not in request.files:
        d = request.get_json() or {}
        content = d.get('content', '')
        if not content:
            return error_response('No OPML content provided')
        raw = content.encode('utf-8')
    else:
        raw = request.files['file'].read(1024 * 1024)  # 1MB max
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return error_response('Invalid OPML XML')
    feeds = []
    for outline in root.iter('outline'):
        url = outline.get('xmlUrl') or outline.get('xmlurl') or ''
        if url:
            feeds.append({
                'title': outline.get('title') or outline.get('text') or url,
                'url': url,
                'category': outline.get('category', 'imported'),
            })
    with db_session() as db:
        added = 0
        for f in feeds:
            existing = db.execute('SELECT id FROM personal_feeds WHERE url = ?', (f['url'],)).fetchone()
            if not existing:
                db.execute('INSERT INTO personal_feeds (title, url, category) VALUES (?, ?, ?)',
                           (f['title'], f['url'], f['category']))
                added += 1
        db.commit()
    log_activity('opml_imported', f'{added} feeds')
    return jsonify({'imported': added, 'skipped_duplicates': len(feeds) - added})


# ═══════════════════════════════════════════════════════════════════════
# P4-04: Calendar Events (ICS Import)
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/calendar')
def api_calendar_list():
    limit, offset = get_pagination()
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM calendar_events ORDER BY start_time LIMIT ? OFFSET ?', (limit, offset)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/calendar', methods=['POST'])
def api_calendar_create():
    d = request.get_json() or {}
    title = (d.get('title') or '').strip()
    if not title:
        return error_response('Title is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO calendar_events (title, start_time, end_time, all_day, location, description, source) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (title, d.get('start_time', ''), d.get('end_time', ''), d.get('all_day', 0),
             d.get('location', ''), d.get('description', ''), 'manual')
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/calendar/<int:eid>', methods=['DELETE'])
def api_calendar_delete(eid):
    with db_session() as db:
        if db.execute('DELETE FROM calendar_events WHERE id = ?', (eid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


@roadmap_bp.route('/api/calendar/import-ics', methods=['POST'])
def api_calendar_import_ics():
    """Import events from an ICS file (simplified VCALENDAR parser)."""
    if 'file' not in request.files:
        return error_response('No ICS file provided')
    raw = request.files['file'].read(2 * 1024 * 1024).decode('utf-8', errors='replace')
    events = []
    current = {}
    for line in raw.splitlines():
        line = line.strip()
        if line == 'BEGIN:VEVENT':
            current = {}
        elif line == 'END:VEVENT':
            if current.get('SUMMARY'):
                events.append(current)
            current = {}
        elif ':' in line and current is not None:
            key, _, val = line.partition(':')
            key = key.split(';')[0]  # strip params like DTSTART;VALUE=DATE
            current[key] = val
    with db_session() as db:
        added = 0
        for ev in events[:500]:
            db.execute(
                'INSERT INTO calendar_events (title, start_time, end_time, location, description, source) VALUES (?, ?, ?, ?, ?, ?)',
                (ev.get('SUMMARY', '')[:200], ev.get('DTSTART', ''), ev.get('DTEND', ''),
                 ev.get('LOCATION', '')[:500], ev.get('DESCRIPTION', '')[:5000], 'ics')
            )
            added += 1
        db.commit()
    log_activity('ics_imported', f'{added} events')
    return jsonify({'imported': added})


# ═══════════════════════════════════════════════════════════════════════
# P4-02/P4-03: Dashboard Templates + Config Export/Import
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/dashboard/templates')
def api_dashboard_templates():
    with db_session() as db:
        rows = db.execute('SELECT * FROM dashboard_templates ORDER BY is_builtin DESC, name').fetchall()
        results = [dict(r) for r in rows]
        for r in results:
            try:
                r['config'] = json.loads(r.get('config_json', '{}'))
            except (json.JSONDecodeError, TypeError):
                r['config'] = {}
        return jsonify(results)


@roadmap_bp.route('/api/dashboard/templates', methods=['POST'])
def api_dashboard_template_create():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return error_response('Name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO dashboard_templates (name, description, config_json) VALUES (?, ?, ?)',
            (name, d.get('description', ''), json.dumps(d.get('config', {})))
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/dashboard/config/export')
def api_dashboard_config_export():
    """P4-03: Export dashboard configuration as JSON."""
    with db_session() as db:
        settings = {}
        for row in db.execute("SELECT key, value FROM settings WHERE key LIKE 'dashboard_%' OR key LIKE 'theme%' OR key LIKE 'sidebar%'").fetchall():
            settings[row['key']] = row['value']
        widgets = db.execute('SELECT * FROM dashboard_templates WHERE is_builtin = 0').fetchall()
    config = {
        'version': '1.0',
        'exported_at': datetime.now(timezone.utc).isoformat(),
        'settings': settings,
        'templates': [dict(w) for w in widgets],
    }
    return Response(
        json.dumps(config, indent=2),
        mimetype='application/json',
        headers={'Content-Disposition': 'attachment; filename="nomad-dashboard-config.json"'}
    )


@roadmap_bp.route('/api/dashboard/config/import', methods=['POST'])
def api_dashboard_config_import():
    """P4-03: Import dashboard configuration from JSON."""
    d = request.get_json() or {}
    if 'settings' not in d:
        return error_response('Invalid config format')
    with db_session() as db:
        imported = 0
        for key, value in d.get('settings', {}).items():
            db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)', (key, value))
            imported += 1
        for tmpl in d.get('templates', []):
            if tmpl.get('name'):
                db.execute(
                    'INSERT INTO dashboard_templates (name, description, config_json) VALUES (?, ?, ?)',
                    (tmpl['name'], tmpl.get('description', ''), tmpl.get('config_json', '{}'))
                )
                imported += 1
        db.commit()
    log_activity('dashboard_config_imported', f'{imported} items')
    return jsonify({'imported': imported})


# ═══════════════════════════════════════════════════════════════════════
# P5-11: Todo/Task Dashboard Widget
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/dashboard/tasks-widget')
def api_tasks_widget():
    """Quick task summary for home dashboard widget."""
    with db_session() as db:
        overdue = db.execute(
            "SELECT id, name, category, next_due FROM scheduled_tasks WHERE next_due < datetime('now') AND next_due != '' ORDER BY next_due LIMIT 10"
        ).fetchall()
        upcoming = db.execute(
            "SELECT id, name, category, next_due FROM scheduled_tasks WHERE next_due >= datetime('now') ORDER BY next_due LIMIT 10"
        ).fetchall()
        return jsonify({
            'overdue': [dict(r) for r in overdue],
            'upcoming': [dict(r) for r in upcoming],
            'overdue_count': len(overdue),
        })


# ═══════════════════════════════════════════════════════════════════════
# P4-14: Torrent Status Dashboard Widget
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/dashboard/torrent-widget')
def api_torrent_widget():
    """Quick torrent status for home dashboard widget."""
    try:
        from services.torrent import TorrentManager
        mgr = TorrentManager()
        torrents = mgr.list_torrents()
        active = [t for t in torrents if t.get('state') in ('downloading', 'seeding')]
        return jsonify({
            'total': len(torrents),
            'active': len(active),
            'downloading': sum(1 for t in active if t.get('state') == 'downloading'),
            'seeding': sum(1 for t in active if t.get('state') == 'seeding'),
        })
    except Exception:
        return jsonify({'total': 0, 'active': 0, 'downloading': 0, 'seeding': 0})
