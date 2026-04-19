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


# ═══════════════════════════════════════════════════════════════════════
# P2-16: Map Bookmark/Favorite Locations
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/maps/bookmarks')
def api_map_bookmarks_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM map_bookmarks ORDER BY name').fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/maps/bookmarks', methods=['POST'])
def api_map_bookmark_create():
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return error_response('Name is required')
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO map_bookmarks (name, lat, lng, zoom, icon, notes) VALUES (?, ?, ?, ?, ?, ?)',
            (name, d.get('lat', 0), d.get('lng', 0), d.get('zoom', 12), d.get('icon', 'star'), d.get('notes', ''))
        )
        db.commit()
        return jsonify({'id': cur.lastrowid}), 201


@roadmap_bp.route('/api/maps/bookmarks/<int:bid>', methods=['DELETE'])
def api_map_bookmark_delete(bid):
    with db_session() as db:
        if db.execute('DELETE FROM map_bookmarks WHERE id = ?', (bid,)).rowcount == 0:
            return error_response('Not found', 404)
        db.commit()
        return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════════
# P2-23: Per-Conversation Knowledge Scope
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/conversations/<int:cid>/kb-scope', methods=['PUT'])
def api_conversation_kb_scope(cid):
    """Set which KB workspaces are active for a conversation."""
    d = request.get_json() or {}
    scopes = d.get('kb_scopes', [])
    with db_session() as db:
        row = db.execute('SELECT id FROM conversations WHERE id = ?', (cid,)).fetchone()
        if not row:
            return error_response('Conversation not found', 404)
        db.execute('UPDATE conversations SET kb_scope = ? WHERE id = ?', (json.dumps(scopes), cid))
        db.commit()
        return jsonify({'status': 'updated', 'kb_scopes': scopes})


@roadmap_bp.route('/api/conversations/<int:cid>/kb-scope')
def api_conversation_kb_scope_get(cid):
    with db_session() as db:
        row = db.execute('SELECT kb_scope FROM conversations WHERE id = ?', (cid,)).fetchone()
        if not row:
            return error_response('Conversation not found', 404)
        try:
            scopes = json.loads(row['kb_scope'] or '[]')
        except (json.JSONDecodeError, TypeError):
            scopes = []
        return jsonify({'kb_scopes': scopes})


# ═══════════════════════════════════════════════════════════════════════
# P2-24: URL-Based Recipe Import
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/recipes/import-url', methods=['POST'])
def api_recipe_import_url():
    """Scrape recipe from URL using JSON-LD structured data."""
    d = request.get_json() or {}
    url = (d.get('url') or '').strip()
    if not url:
        return error_response('URL is required')
    import requests as _req
    try:
        resp = _req.get(url, timeout=15, headers={'User-Agent': 'NOMAD/1.0'})
        resp.raise_for_status()
        html = resp.text
    except Exception:
        return error_response('Failed to fetch URL')
    # Parse JSON-LD recipe
    import re
    recipe_data = None
    for match in re.finditer(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            ld = json.loads(match.group(1))
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if isinstance(item, dict) and item.get('@type') in ('Recipe', ['Recipe']):
                    recipe_data = item
                    break
                if isinstance(item, dict) and '@graph' in item:
                    for g in item['@graph']:
                        if isinstance(g, dict) and g.get('@type') in ('Recipe', ['Recipe']):
                            recipe_data = g
                            break
        except (json.JSONDecodeError, TypeError):
            continue
        if recipe_data:
            break
    if not recipe_data:
        return error_response('No recipe found in page structured data')
    name = recipe_data.get('name', 'Imported Recipe')[:200]
    ingredients = []
    for ing in recipe_data.get('recipeIngredient', []):
        if isinstance(ing, str):
            ingredients.append({'name': ing[:200], 'quantity': 1, 'unit': '', 'calories_per_unit': 0})
    instructions = ''
    inst = recipe_data.get('recipeInstructions', [])
    if isinstance(inst, list):
        steps = []
        for step in inst:
            if isinstance(step, str):
                steps.append(step)
            elif isinstance(step, dict):
                steps.append(step.get('text', ''))
        instructions = '\n'.join(f'{i+1}. {s}' for i, s in enumerate(steps) if s)
    elif isinstance(inst, str):
        instructions = inst
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO recipes (name, instructions, source_url, notes) VALUES (?, ?, ?, ?)',
            (name, instructions[:10000], url, f'Imported from {url}')
        )
        rid = cur.lastrowid
        for ing in ingredients[:100]:
            db.execute(
                'INSERT INTO recipe_ingredients (recipe_id, name, quantity, unit) VALUES (?, ?, ?, ?)',
                (rid, ing['name'], ing['quantity'], ing['unit'])
            )
        db.commit()
    log_activity('recipe_imported', name)
    return jsonify({'id': rid, 'name': name, 'ingredients_count': len(ingredients)})


# ═══════════════════════════════════════════════════════════════════════
# P4-05: Custom API Widget Renderer
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/widgets/custom-api', methods=['POST'])
def api_custom_api_widget():
    """Fetch any JSON API and return the result for widget rendering."""
    d = request.get_json() or {}
    url = (d.get('url') or '').strip()
    if not url:
        return error_response('URL is required')
    from web.utils import is_loopback_addr
    import requests as _req
    try:
        r = _req.get(url, timeout=10, headers={'Accept': 'application/json'})
        data = r.json()
    except Exception:
        return error_response('Failed to fetch or parse API response')
    return jsonify({'status': r.status_code, 'data': data})


# ═══════════════════════════════════════════════════════════════════════
# P4-12: Favicon Auto-Fetch
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/favicon')
def api_favicon_fetch():
    """Fetch favicon for a given URL."""
    url = request.args.get('url', '').strip()
    if not url:
        return error_response('URL is required')
    from urllib.parse import urlparse
    parsed = urlparse(url)
    base = f'{parsed.scheme}://{parsed.netloc}'
    favicon_url = f'{base}/favicon.ico'
    import requests as _req
    try:
        r = _req.get(favicon_url, timeout=5, stream=True)
        if r.ok and r.headers.get('content-type', '').startswith('image'):
            import base64
            data = base64.b64encode(r.content[:100000]).decode()
            return jsonify({'favicon': f'data:{r.headers["content-type"]};base64,{data}'})
    except Exception:
        pass
    return jsonify({'favicon': None})


# ═══════════════════════════════════════════════════════════════════════
# P5-04: Prompt Version Control
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/ai/prompts/<int:pid>/versions')
def api_prompt_versions(pid):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM ai_prompt_versions WHERE prompt_id = ? ORDER BY version DESC', (pid,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@roadmap_bp.route('/api/ai/prompts/<int:pid>/versions', methods=['POST'])
def api_prompt_version_create(pid):
    d = request.get_json() or {}
    content = d.get('content', '')
    if not content:
        return error_response('Content is required')
    with db_session() as db:
        last = db.execute(
            'SELECT MAX(version) as v FROM ai_prompt_versions WHERE prompt_id = ?', (pid,)
        ).fetchone()
        next_ver = (last['v'] or 0) + 1
        db.execute(
            'INSERT INTO ai_prompt_versions (prompt_id, version, content, commit_message) VALUES (?, ?, ?, ?)',
            (pid, next_ver, content, d.get('commit_message', ''))
        )
        db.commit()
        return jsonify({'version': next_ver}), 201


@roadmap_bp.route('/api/ai/prompts/<int:pid>/versions/<int:ver>/rollback', methods=['POST'])
def api_prompt_version_rollback(pid, ver):
    with db_session() as db:
        row = db.execute(
            'SELECT content FROM ai_prompt_versions WHERE prompt_id = ? AND version = ?', (pid, ver)
        ).fetchone()
        if not row:
            return error_response('Version not found', 404)
        return jsonify({'content': row['content'], 'rolled_back_to': ver})


# ═══════════════════════════════════════════════════════════════════════
# ═══════════════════════════════════════════════════════════════════════
# V8-05: Encrypt secrets at rest via Fernet
# ═══════════════════════════════════════════════════════════════════════

def _get_fernet():
    """Get or create a Fernet instance for encrypting secrets at rest."""
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        return None
    from config import get_config_value, load_config
    import config as _cfg
    key = get_config_value('encryption_key', '')
    if not key:
        key = Fernet.generate_key().decode()
        data = load_config()
        data['encryption_key'] = key
        _cfg.save_config(data)
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt_secret(plaintext):
    f = _get_fernet()
    if not f:
        return plaintext  # graceful degradation
    return f.encrypt(plaintext.encode()).decode()


def _decrypt_secret(ciphertext):
    f = _get_fernet()
    if not f or not ciphertext:
        return ciphertext
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except Exception:
        return ciphertext  # not encrypted (legacy) — return as-is


# P5-07: 2FA/TOTP Authentication (V8-05: encrypted at rest)
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/auth/totp/setup', methods=['POST'])
def api_totp_setup():
    """Generate a TOTP secret and provisioning URI."""
    d = request.get_json() or {}
    user_id = d.get('user_id', 0)
    try:
        import pyotp
    except ImportError:
        return error_response('pyotp not installed — run: pip install pyotp')
    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=d.get('username', 'nomad'), issuer_name='NOMAD Field Desk')
    import secrets as _secrets
    backup_codes = [_secrets.token_hex(4).upper() for _ in range(8)]
    with db_session() as db:
        db.execute('DELETE FROM totp_secrets WHERE user_id = ?', (user_id,))
        db.execute(
            'INSERT INTO totp_secrets (user_id, secret, backup_codes) VALUES (?, ?, ?)',
            (user_id, _encrypt_secret(secret), json.dumps(backup_codes))
        )
        db.commit()
    return jsonify({'secret': secret, 'provisioning_uri': uri, 'backup_codes': backup_codes})


@roadmap_bp.route('/api/auth/totp/verify', methods=['POST'])
def api_totp_verify():
    """Verify a TOTP code."""
    d = request.get_json() or {}
    user_id = d.get('user_id', 0)
    code = (d.get('code') or '').strip()
    if not code:
        return error_response('Code is required')
    try:
        import pyotp
    except ImportError:
        return error_response('pyotp not installed')
    with db_session() as db:
        row = db.execute('SELECT * FROM totp_secrets WHERE user_id = ?', (user_id,)).fetchone()
        if not row:
            return error_response('TOTP not configured for this user', 404)
        totp = pyotp.TOTP(_decrypt_secret(row['secret']))
        if totp.verify(code, valid_window=1):
            if not row['verified']:
                db.execute('UPDATE totp_secrets SET verified = 1 WHERE user_id = ?', (user_id,))
                db.commit()
            return jsonify({'valid': True})
        # Check backup codes
        try:
            backups = json.loads(row['backup_codes'] or '[]')
        except (json.JSONDecodeError, TypeError):
            backups = []
        if code.upper() in backups:
            backups.remove(code.upper())
            db.execute('UPDATE totp_secrets SET backup_codes = ? WHERE user_id = ?',
                       (json.dumps(backups), user_id))
            db.commit()
            return jsonify({'valid': True, 'backup_code_used': True, 'remaining_backups': len(backups)})
        return jsonify({'valid': False}), 401


# ═══════════════════════════════════════════════════════════════════════
# P5-08: KB Archive Upload Auto-Extract
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/kb/upload-archive', methods=['POST'])
def api_kb_upload_archive():
    """Upload ZIP/TAR containing docs, auto-extract and index into KB."""
    if 'file' not in request.files:
        return error_response('No file provided')
    f = request.files['file']
    fname = f.filename or ''
    workspace = request.form.get('workspace', 'default')
    import tempfile
    import zipfile
    import tarfile
    from config import get_data_dir
    kb_dir = os.path.join(get_data_dir(), 'kb_uploads', workspace)
    os.makedirs(kb_dir, exist_ok=True)
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(fname)[1]) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name
    extracted = []
    try:
        if zipfile.is_zipfile(tmp_path):
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                for name in zf.namelist()[:500]:
                    if name.endswith('/'):
                        continue
                    safe_name = os.path.basename(name)
                    if not safe_name:
                        continue
                    dest = os.path.join(kb_dir, safe_name)
                    with zf.open(name) as src, open(dest, 'wb') as dst:
                        dst.write(src.read(50 * 1024 * 1024))  # 50MB per file cap
                    extracted.append(safe_name)
        elif tarfile.is_tarfile(tmp_path):
            with tarfile.open(tmp_path, 'r:*') as tf:
                for member in tf.getmembers()[:500]:
                    if not member.isfile():
                        continue
                    safe_name = os.path.basename(member.name)
                    if not safe_name:
                        continue
                    dest = os.path.join(kb_dir, safe_name)
                    src = tf.extractfile(member)
                    if src:
                        with open(dest, 'wb') as dst:
                            dst.write(src.read(50 * 1024 * 1024))
                    extracted.append(safe_name)
        else:
            return error_response('Unsupported archive format (use ZIP or TAR)')
    finally:
        os.unlink(tmp_path)
    # Register in documents table
    with db_session() as db:
        for name in extracted:
            db.execute(
                "INSERT INTO documents (filename, status, doc_category) VALUES (?, 'ready', ?)",
                (name, workspace)
            )
        db.commit()
    log_activity('kb_archive_imported', f'{len(extracted)} files to {workspace}')
    return jsonify({'extracted': len(extracted), 'files': extracted[:50], 'workspace': workspace})


# ═══════════════════════════════════════════════════════════════════════
# P5-14: Self-Signed Cert Trust for Federation
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/federation/cert-trust', methods=['PUT'])
def api_federation_cert_trust():
    """Toggle self-signed cert trust for a federation peer."""
    d = request.get_json() or {}
    peer_id = d.get('peer_id')
    allow_insecure = d.get('allow_insecure', False)
    if not peer_id:
        return error_response('peer_id is required')
    with db_session() as db:
        db.execute(
            'UPDATE federation_peers SET allow_insecure = ? WHERE id = ?',
            (1 if allow_insecure else 0, peer_id)
        )
        db.commit()
        return jsonify({'status': 'updated', 'allow_insecure': allow_insecure})


# ═══════════════════════════════════════════════════════════════════════
# P5-15: Per-Page/Tab Access Control
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/settings/tab-permissions')
def api_tab_permissions():
    """Get per-tab access control config."""
    with db_session() as db:
        row = db.execute("SELECT value FROM settings WHERE key = 'tab_permissions'").fetchone()
        try:
            perms = json.loads(row['value']) if row else {}
        except (json.JSONDecodeError, TypeError):
            perms = {}
        return jsonify(perms)


@roadmap_bp.route('/api/settings/tab-permissions', methods=['PUT'])
def api_tab_permissions_update():
    """Set per-tab access control — {tab_name: [allowed_roles]}."""
    d = request.get_json() or {}
    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('tab_permissions', ?)",
            (json.dumps(d),)
        )
        db.commit()
        return jsonify({'status': 'updated'})


# ═══════════════════════════════════════════════════════════════════════
# P2-14: Multi-User Profiles
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/profiles')
def api_profiles_list():
    with db_session() as db:
        rows = db.execute('SELECT id, username, role, display_name, preferences FROM app_users ORDER BY username').fetchall()
        return jsonify([{**dict(r), 'preferences': json.loads(r['preferences'] or '{}') if r['preferences'] else {}} for r in rows])


# ═══════════════════════════════════════════════════════════════════════
# P2-18: CSV Export for All Entities
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/export/csv/<table_name>')
def api_generic_csv_export(table_name):
    """Export any table as CSV (uses safe_table validation)."""
    import csv
    from web.sql_safety import safe_table
    validated = safe_table(table_name)
    if not validated:
        return error_response('Invalid table name', 400)
    with db_session() as db:
        rows = db.execute(f'SELECT * FROM {validated} LIMIT 10000').fetchall()
        if not rows:
            return Response('', mimetype='text/csv',
                           headers={'Content-Disposition': f'attachment; filename="{validated}.csv"'})
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(rows[0].keys())
        for r in rows:
            writer.writerow([str(v) if v is not None else '' for v in tuple(r)])
        return Response(buf.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': f'attachment; filename="{validated}.csv"'})


# ═══════════════════════════════════════════════════════════════════════
# P3-18: Shopping List Aisle Grouping
# ═══════════════════════════════════════════════════════════════════════

AISLE_MAP = {
    'Produce': ['vegetable', 'fruit', 'lettuce', 'tomato', 'potato', 'onion', 'garlic', 'pepper', 'carrot', 'apple', 'banana'],
    'Dairy': ['milk', 'cheese', 'yogurt', 'butter', 'cream', 'egg'],
    'Meat & Protein': ['chicken', 'beef', 'pork', 'fish', 'turkey', 'sausage', 'bacon', 'protein'],
    'Canned & Dry Goods': ['canned', 'beans', 'rice', 'pasta', 'soup', 'cereal', 'oat', 'flour'],
    'Pharmacy': ['medicine', 'vitamin', 'bandage', 'ibuprofen', 'acetaminophen', 'antibiotic', 'gauze'],
    'Water & Beverages': ['water', 'juice', 'coffee', 'tea', 'drink'],
    'Batteries & Hardware': ['battery', 'flashlight', 'tool', 'tape', 'rope', 'wire'],
    'Hygiene': ['soap', 'shampoo', 'toothpaste', 'tissue', 'sanitizer', 'toilet'],
}

@roadmap_bp.route('/api/shopping-list/grouped')
def api_shopping_list_grouped():
    """Return shopping list items grouped by store aisle."""
    with db_session() as db:
        items = db.execute('SELECT * FROM shopping_list ORDER BY item_name').fetchall()
        grouped = {}
        for item in items:
            name_lower = (item['item_name'] or '').lower()
            aisle = 'Other'
            for aisle_name, keywords in AISLE_MAP.items():
                if any(kw in name_lower for kw in keywords):
                    aisle = aisle_name
                    break
            grouped.setdefault(aisle, []).append(dict(item))
        return jsonify(grouped)


# ═══════════════════════════════════════════════════════════════════════
# P5-09: KB Image Import with OCR
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/kb/import-image', methods=['POST'])
def api_kb_import_image():
    """Import image to KB with optional OCR text extraction."""
    if 'file' not in request.files:
        return error_response('No file provided')
    f = request.files['file']
    workspace = request.form.get('workspace', 'default')
    from config import get_data_dir
    kb_dir = os.path.join(get_data_dir(), 'kb_uploads', workspace)
    os.makedirs(kb_dir, exist_ok=True)
    fname = os.path.basename(f.filename or 'image.png')
    dest = os.path.join(kb_dir, fname)
    f.save(dest)
    # Try OCR
    extracted_text = ''
    try:
        from PIL import Image
        import pytesseract
        img = Image.open(dest)
        extracted_text = pytesseract.image_to_string(img)
    except ImportError:
        extracted_text = '[OCR unavailable — install Pillow + pytesseract]'
    except Exception as e:
        extracted_text = f'[OCR failed: {type(e).__name__}]'
    with db_session() as db:
        db.execute(
            "INSERT INTO documents (filename, status, doc_category, content) VALUES (?, 'ready', ?, ?)",
            (fname, workspace, extracted_text[:50000])
        )
        db.commit()
    log_activity('kb_image_imported', fname)
    return jsonify({'filename': fname, 'ocr_text_length': len(extracted_text), 'workspace': workspace})


# ═══════════════════════════════════════════════════════════════════════
# P5-12: Web Page Change Detection
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/monitors/<int:mid>/snapshot', methods=['POST'])
def api_monitor_snapshot(mid):
    """Fetch page content and compare to last snapshot for changes."""
    with db_session() as db:
        mon = db.execute('SELECT * FROM url_monitors WHERE id = ?', (mid,)).fetchone()
        if not mon:
            return error_response('Not found', 404)
    import requests as _req
    import hashlib
    try:
        r = _req.get(mon['url'], timeout=15)
        content = r.text[:500000]
        content_hash = hashlib.sha256(content.encode()).hexdigest()
    except Exception:
        return error_response('Failed to fetch page')
    # Compare to stored hash
    with db_session() as db:
        last = db.execute(
            "SELECT value FROM settings WHERE key = ?", (f'monitor_hash_{mid}',)
        ).fetchone()
        old_hash = last['value'] if last else None
        changed = old_hash is not None and old_hash != content_hash
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (f'monitor_hash_{mid}', content_hash)
        )
        db.commit()
    return jsonify({
        'changed': changed,
        'hash': content_hash,
        'previous_hash': old_hash,
        'content_length': len(content),
    })


# ═══════════════════════════════════════════════════════════════════════
# P5-23: Bcrypt Password Hashing (upgrade path)
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/auth/upgrade-hash', methods=['POST'])
def api_upgrade_password_hash():
    """Upgrade a user's password hash from PBKDF2 to bcrypt."""
    d = request.get_json() or {}
    user_id = d.get('user_id')
    password = d.get('password', '')
    if not user_id or not password:
        return error_response('user_id and password are required')
    try:
        import bcrypt
    except ImportError:
        return error_response('bcrypt not installed — run: pip install bcrypt')
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')
    with db_session() as db:
        db.execute('UPDATE app_users SET password_hash = ? WHERE id = ?', (hashed, user_id))
        db.commit()
    return jsonify({'status': 'upgraded', 'algorithm': 'bcrypt'})


# ═══════════════════════════════════════════════════════════════════════
# V8-18: Soft Delete / Trash Pattern
# ═══════════════════════════════════════════════════════════════════════

_TRASH_TABLES = frozenset({'inventory', 'contacts', 'notes', 'patients'})

@roadmap_bp.route('/api/trash')
def api_trash_list():
    """List soft-deleted items across all trashable tables."""
    with db_session() as db:
        results = {}
        for table in _TRASH_TABLES:
            try:
                rows = db.execute(
                    f'SELECT id, name, deleted_at FROM {table} WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC LIMIT 100'
                ).fetchall()
                if rows:
                    name_col = 'name' if table != 'patients' else 'name'
                    results[table] = [{'id': r['id'], 'name': r[name_col], 'deleted_at': r['deleted_at']} for r in rows]
            except Exception:
                pass  # deleted_at column may not exist yet
        return jsonify(results)


@roadmap_bp.route('/api/trash/<table>/<int:item_id>/restore', methods=['POST'])
def api_trash_restore(table, item_id):
    """Restore a soft-deleted item."""
    if table not in _TRASH_TABLES:
        return error_response('Invalid table', 400)
    with db_session() as db:
        rc = db.execute(f'UPDATE {table} SET deleted_at = NULL WHERE id = ? AND deleted_at IS NOT NULL', (item_id,)).rowcount
        if rc == 0:
            return error_response('Item not found in trash', 404)
        db.commit()
        log_activity('trash_restored', f'{table}:{item_id}')
        return jsonify({'status': 'restored'})


@roadmap_bp.route('/api/trash/purge', methods=['POST'])
def api_trash_purge():
    """Permanently delete all trashed items older than 30 days."""
    with db_session() as db:
        total = 0
        for table in _TRASH_TABLES:
            try:
                rc = db.execute(
                    f"DELETE FROM {table} WHERE deleted_at IS NOT NULL AND deleted_at < datetime('now', '-30 days')"
                ).rowcount
                total += rc
            except Exception:
                pass
        db.commit()
        return jsonify({'purged': total})


# ═══════════════════════════════════════════════════════════════════════
# P2-07: OpenAPI/Swagger Spec (auto-generated)
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/docs')
def api_docs_redirect():
    """Redirect to Swagger UI."""
    return '''<!DOCTYPE html><html><head><title>NOMAD API Docs</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    </head><body><div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>SwaggerUIBundle({url:"/api/openapi.json",dom_id:"#swagger-ui"})</script>
    </body></html>'''


@roadmap_bp.route('/api/openapi.json')
def api_openapi_spec():
    """Auto-generate OpenAPI 3.0 spec from registered Flask routes."""
    from flask import current_app
    paths = {}
    for rule in current_app.url_map.iter_rules():
        if not rule.rule.startswith('/api/'):
            continue
        if rule.rule in ('/api/openapi.json', '/api/docs'):
            continue
        path = rule.rule.replace('<int:', '{').replace('<', '{').replace('>', '}')
        methods = {}
        for method in rule.methods - {'OPTIONS', 'HEAD'}:
            methods[method.lower()] = {
                'summary': rule.endpoint.replace('_', ' ').title(),
                'responses': {'200': {'description': 'Success'}},
                'tags': [rule.endpoint.split('.')[0] if '.' in rule.endpoint else 'general'],
            }
        if methods:
            paths[path] = methods
    spec = {
        'openapi': '3.0.3',
        'info': {
            'title': 'NOMAD Field Desk API',
            'version': '7.50.0',
            'description': 'Offline-first preparedness command center API',
        },
        'paths': paths,
    }
    return jsonify(spec)


# ═══════════════════════════════════════════════════════════════════════
# P2-13: Inline Survival Quick-Reference Cards
# ═══════════════════════════════════════════════════════════════════════

SURVIVAL_REFERENCE = [
    {'id': 'water', 'title': 'Water Purification', 'category': 'essentials', 'content': 'BOILING: Rolling boil for 1 minute (3 min above 6,500 ft). CHEMICAL: 2 drops bleach per quart, wait 30 min. FILTER: 0.2 micron ceramic/hollow fiber. SOLAR: SODIS in clear PET bottles, 6 hours full sun. SIGNS OF BAD WATER: cloudiness, odor, surface film, algae.'},
    {'id': 'fire', 'title': 'Fire Starting', 'category': 'essentials', 'content': 'TINDER: dry grass, birch bark, dryer lint, cotton balls with petroleum jelly. KINDLING: pencil-thick dry sticks. FUEL: wrist-thick dry wood. METHODS: ferro rod + scraper, magnifying lens, bow drill (spindle + fireboard + socket + bow), hand drill. FIRE LAY: teepee for quick light, log cabin for coals, star fire for long burn.'},
    {'id': 'shelter', 'title': 'Emergency Shelter', 'category': 'essentials', 'content': 'PRIORITIES: protection from wind/rain/cold > comfort. DEBRIS HUT: frame of ridge pole + ribs, 3ft thick debris insulation, small entrance. TARP: A-frame with 550 cord ridge line, stake corners. SNOW: quinzhee (pile snow 5ft, let sinter 2hrs, hollow out), snow trench with tarp cover. LOCATION: avoid hilltops (wind), valley floors (cold air pools), dead trees, flood zones.'},
    {'id': 'firstaid', 'title': 'First Aid Essentials', 'category': 'medical', 'content': 'BLEEDING: Direct pressure 10 min, elevate, tourniquet 2-3 inches above wound if life-threatening. BURNS: Cool running water 10-20 min, cover with clean cloth, never pop blisters. FRACTURE: Splint above and below break, pad bony prominences. CPR: 30 compressions (2 inch depth) : 2 breaths, 100-120/min. CHOKING: 5 back blows, 5 abdominal thrusts (Heimlich).'},
    {'id': 'navigation', 'title': 'GPS-Denied Navigation', 'category': 'skills', 'content': 'COMPASS: Hold level, align needle to N, orient map to match. SHADOW STICK: Plant stick, mark tip, wait 15 min, mark again. Line between marks = E-W (first mark is W). SUN: Rises roughly E, sets roughly W. At solar noon, shadows point N (northern hemisphere). STARS: Polaris = tip of Little Dipper handle, always due north. Southern Cross: extend long axis 4.5x to find south celestial pole.'},
    {'id': 'signals', 'title': 'Signaling & Rescue', 'category': 'skills', 'content': 'INTERNATIONAL DISTRESS: 3 of anything (3 fires, 3 whistle blasts, 3 gunshots). GROUND-TO-AIR: V = need assistance, X = need medical, I = need supplies, arrow = traveling this direction. SIGNAL MIRROR: Flash toward aircraft/rescue, sweep horizon. WHISTLE: 3 short blasts, pause, repeat. SMOKE: Green branches on fire for white smoke (day), bright fire for night.'},
    {'id': 'food', 'title': 'Wild Edibles & Foraging', 'category': 'food', 'content': 'UNIVERSAL EDIBILITY TEST: 8-hour fast, skin contact test (15 min), lip test (15 min), tongue test (15 min), chew test (15 min), swallow small amount, wait 8 hours. SAFE BETS: dandelion (all parts), cattail (shoots, pollen, roots), pine (needles for tea, inner bark), acorns (leach tannins in water). NEVER EAT: white/yellow berries, mushrooms without 100% ID, plants with milky sap (except dandelion).'},
    {'id': 'knots', 'title': 'Essential Knots', 'category': 'skills', 'content': 'BOWLINE: fixed loop that won\'t slip. CLOVE HITCH: quick temporary attachment to pole. TAUT-LINE HITCH: adjustable tension on guy lines. TRUCKER\'S HITCH: 3:1 mechanical advantage for securing loads. FIGURE-8 ON A BIGHT: strong fixed loop for climbing/rescue. SQUARE KNOT: joining two ropes of equal diameter (not for critical loads). PRUSIK: friction hitch for ascending rope.'},
    {'id': 'weather', 'title': 'Weather Prediction', 'category': 'skills', 'content': 'PRESSURE FALLING: storm approaching (barometer drops >3mb/3hr = severe). WIND SHIFT: backing wind (counterclockwise) = approaching low. CLOUDS: cirrus → cirrostratus → altostratus → nimbostratus = rain in 24-36 hrs. RED SKY: morning = moisture + approaching weather; evening = clearing. ANIMALS: birds flying low, insects close to ground = low pressure/rain coming.'},
    {'id': 'radio', 'title': 'Emergency Radio Frequencies', 'category': 'comms', 'content': 'FRS CH1: 462.5625 MHz (license-free, 2W). GMRS CH1: 462.5625 MHz (license required, 50W). 2M CALL: 146.520 MHz (national simplex). 70CM CALL: 446.000 MHz. MARINE CH16: 156.800 MHz (distress). CB CH9: 27.065 MHz (emergency). CB CH19: 27.185 MHz (trucker/travel). NOAA WX: 162.400-162.550 MHz (7 channels). MURS CH1: 151.820 MHz (license-free, 2W).'},
]

@roadmap_bp.route('/api/reference/survival')
def api_survival_reference():
    """Return built-in survival quick-reference cards."""
    category = request.args.get('category', '')
    q = request.args.get('q', '').lower()
    cards = SURVIVAL_REFERENCE
    if category:
        cards = [c for c in cards if c['category'] == category]
    if q:
        cards = [c for c in cards if q in c['title'].lower() or q in c['content'].lower()]
    return jsonify(cards)


@roadmap_bp.route('/api/reference/survival/<card_id>')
def api_survival_reference_card(card_id):
    for card in SURVIVAL_REFERENCE:
        if card['id'] == card_id:
            return jsonify(card)
    return error_response('Card not found', 404)


# ═══════════════════════════════════════════════════════════════════════
# P3-16: AI Model Comparison View
# ═══════════════════════════════════════════════════════════════════════

@roadmap_bp.route('/api/ai/compare', methods=['POST'])
def api_ai_compare():
    """Send same prompt to two models and return both responses."""
    d = request.get_json() or {}
    model_a = d.get('model_a', '')
    model_b = d.get('model_b', '')
    prompt = d.get('prompt', '')
    if not model_a or not model_b or not prompt:
        return error_response('model_a, model_b, and prompt are required')
    from services import ollama
    results = {}
    for label, model in [('a', model_a), ('b', model_b)]:
        try:
            resp = ollama.chat(model=model, messages=[{'role': 'user', 'content': prompt}], stream=False)
            results[label] = {
                'model': model,
                'response': resp.get('message', {}).get('content', '') if isinstance(resp, dict) else str(resp),
                'error': None,
            }
        except Exception as e:
            results[label] = {'model': model, 'response': '', 'error': str(type(e).__name__)}
    return jsonify(results)


# ═══════════════════════════════════════════════════════════════════════
# P3-17: AI Function/Tool Calling
# ═══════════════════════════════════════════════════════════════════════

AI_TOOLS = {
    'query_inventory': {
        'description': 'Search inventory items by name or category',
        'params': ['query'],
        'handler': lambda db, p: [dict(r) for r in db.execute(
            "SELECT id, name, category, quantity, expiration FROM inventory WHERE name LIKE ? OR category LIKE ? LIMIT 20",
            (f'%{p["query"]}%', f'%{p["query"]}%')
        ).fetchall()],
    },
    'check_weather': {
        'description': 'Get latest weather readings',
        'params': [],
        'handler': lambda db, p: [dict(r) for r in db.execute(
            'SELECT * FROM weather_log ORDER BY created_at DESC LIMIT 5'
        ).fetchall()],
    },
    'count_contacts': {
        'description': 'Count contacts by role',
        'params': [],
        'handler': lambda db, p: [dict(r) for r in db.execute(
            'SELECT role, COUNT(*) as count FROM contacts GROUP BY role ORDER BY count DESC'
        ).fetchall()],
    },
    'get_alerts': {
        'description': 'Get active alerts',
        'params': [],
        'handler': lambda db, p: [dict(r) for r in db.execute(
            'SELECT * FROM alerts WHERE dismissed = 0 ORDER BY created_at DESC LIMIT 20'
        ).fetchall()],
    },
    'search_notes': {
        'description': 'Search notes by title or content',
        'params': ['query'],
        'handler': lambda db, p: [dict(r) for r in db.execute(
            "SELECT id, title, SUBSTR(content, 1, 200) as excerpt FROM notes WHERE title LIKE ? OR content LIKE ? LIMIT 10",
            (f'%{p["query"]}%', f'%{p["query"]}%')
        ).fetchall()],
    },
    'calculate_dosage': {
        'description': 'Calculate medication dosage by weight',
        'params': ['drug', 'weight_kg'],
        'handler': lambda db, p: {'drug': p.get('drug', ''), 'weight_kg': float(p.get('weight_kg', 70)),
                                   'note': 'Consult medical professional. This is reference only.'},
    },
}

@roadmap_bp.route('/api/ai/tools')
def api_ai_tools_list():
    """List available AI function tools."""
    return jsonify([{
        'name': name,
        'description': tool['description'],
        'params': tool['params'],
    } for name, tool in AI_TOOLS.items()])


@roadmap_bp.route('/api/ai/tools/<tool_name>', methods=['POST'])
def api_ai_tool_call(tool_name):
    """Execute an AI tool/function call."""
    if tool_name not in AI_TOOLS:
        return error_response(f'Unknown tool: {tool_name}', 404)
    d = request.get_json() or {}
    tool = AI_TOOLS[tool_name]
    for param in tool['params']:
        if param not in d:
            return error_response(f'Missing required parameter: {param}')
    with db_session() as db:
        try:
            result = tool['handler'](db, d)
            return jsonify({'tool': tool_name, 'result': result})
        except Exception as e:
            return error_response(f'Tool execution failed')
