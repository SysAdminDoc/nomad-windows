"""Threat intelligence dashboard — feed aggregation and threat tracking."""

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
import json
from web.utils import get_query_int as _get_query_int

threat_intel_bp = Blueprint('threat_intel', __name__)

SEVERITY_LEVELS = ['info', 'low', 'medium', 'high', 'critical']
THREAT_CATEGORIES = [
    'natural_disaster', 'civil_unrest', 'infrastructure', 'supply_chain',
    'cyber', 'pandemic', 'economic', 'military', 'environmental', 'other'
]


# ─── Threat Feeds CRUD ────────────────────────────────────────────

@threat_intel_bp.route('/api/threat-intel/feeds')
def api_threat_feeds_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM threat_feeds ORDER BY enabled DESC, name').fetchall()
    return jsonify([dict(r) for r in rows])


@threat_intel_bp.route('/api/threat-intel/feeds', methods=['POST'])
def api_threat_feeds_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO threat_feeds
               (name, feed_type, url, category, refresh_interval_min, enabled, notes)
               VALUES (?,?,?,?,?,?,?)''',
            (data['name'], data.get('feed_type', 'manual'),
             data.get('url', ''), data.get('category', 'other'),
             data.get('refresh_interval_min', 60),
             1 if data.get('enabled', True) else 0,
             data.get('notes', ''))
        )
        db.commit()
        log_activity('threat_feed_created', detail=data['name'])
        row = db.execute('SELECT * FROM threat_feeds WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@threat_intel_bp.route('/api/threat-intel/feeds/<int:fid>', methods=['PUT'])
def api_threat_feeds_update(fid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM threat_feeds WHERE id = ?', (fid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['name', 'feed_type', 'url', 'category', 'refresh_interval_min', 'enabled', 'notes']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(fid)
        db.execute(f'UPDATE threat_feeds SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        row = db.execute('SELECT * FROM threat_feeds WHERE id = ?', (fid,)).fetchone()
    return jsonify(dict(row))


@threat_intel_bp.route('/api/threat-intel/feeds/<int:fid>', methods=['DELETE'])
def api_threat_feeds_delete(fid):
    with db_session() as db:
        existing = db.execute('SELECT id, name FROM threat_feeds WHERE id = ?', (fid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM threat_entries WHERE feed_id = ?', (fid,))
        db.execute('DELETE FROM threat_feeds WHERE id = ?', (fid,))
        db.commit()
        log_activity('threat_feed_deleted', detail=existing['name'])
    return jsonify({'status': 'deleted'})


@threat_intel_bp.route('/api/threat-intel/feeds/<int:fid>/toggle', methods=['POST'])
def api_threat_feeds_toggle(fid):
    with db_session() as db:
        existing = db.execute('SELECT id, enabled FROM threat_feeds WHERE id = ?', (fid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        new_state = 0 if existing['enabled'] else 1
        db.execute('UPDATE threat_feeds SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_state, fid))
        db.commit()
        row = db.execute('SELECT * FROM threat_feeds WHERE id = ?', (fid,)).fetchone()
    return jsonify(dict(row))


# ─── Threat Entries CRUD ──────────────────────────────────────────

@threat_intel_bp.route('/api/threat-intel/entries')
def api_threat_entries_list():
    category = request.args.get('category')
    severity = request.args.get('severity')
    active_only = request.args.get('active', '1')
    limit = _get_query_int(request, 'limit', 100, minimum=1, maximum=500)

    clauses, params = [], []
    if category:
        clauses.append('category = ?')
        params.append(category)
    if severity:
        clauses.append('severity = ?')
        params.append(severity)
    if active_only == '1':
        clauses.append('resolved = 0')

    where = f'WHERE {" AND ".join(clauses)}' if clauses else ''
    with db_session() as db:
        rows = db.execute(
            f'SELECT * FROM threat_entries {where} ORDER BY severity_score DESC, created_at DESC LIMIT ?',
            tuple(params + [limit])
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@threat_intel_bp.route('/api/threat-intel/entries', methods=['POST'])
def api_threat_entries_create():
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({'error': 'Title required'}), 400
    severity = data.get('severity', 'medium')
    severity_score = SEVERITY_LEVELS.index(severity) if severity in SEVERITY_LEVELS else 2
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO threat_entries
               (feed_id, title, description, category, severity, severity_score,
                source_url, location, lat, lng, tags, impact_assessment, recommended_actions)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('feed_id'), data['title'], data.get('description', ''),
             data.get('category', 'other'), severity, severity_score,
             data.get('source_url', ''), data.get('location', ''),
             data.get('lat'), data.get('lng'),
             json.dumps(data.get('tags', [])) if isinstance(data.get('tags'), list) else data.get('tags', '[]'),
             data.get('impact_assessment', ''), data.get('recommended_actions', ''))
        )
        db.commit()
        log_activity('threat_entry_created', detail=data['title'])
        row = db.execute('SELECT * FROM threat_entries WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@threat_intel_bp.route('/api/threat-intel/entries/<int:eid>', methods=['PUT'])
def api_threat_entries_update(eid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM threat_entries WHERE id = ?', (eid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = ['title', 'description', 'category', 'severity', 'severity_score',
                    'source_url', 'location', 'lat', 'lng', 'tags',
                    'impact_assessment', 'recommended_actions', 'resolved']
        sets, vals = [], []
        for col in allowed:
            if col in data:
                val = data[col]
                if col == 'tags' and isinstance(val, list):
                    val = json.dumps(val)
                if col == 'severity' and val in SEVERITY_LEVELS:
                    sets.append('severity_score = ?')
                    vals.append(SEVERITY_LEVELS.index(val))
                sets.append(f'{col} = ?')
                vals.append(val)
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        sets.append('updated_at = CURRENT_TIMESTAMP')
        vals.append(eid)
        db.execute(f'UPDATE threat_entries SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        row = db.execute('SELECT * FROM threat_entries WHERE id = ?', (eid,)).fetchone()
    return jsonify(dict(row))


@threat_intel_bp.route('/api/threat-intel/entries/<int:eid>', methods=['DELETE'])
def api_threat_entries_delete(eid):
    with db_session() as db:
        existing = db.execute('SELECT id, title FROM threat_entries WHERE id = ?', (eid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM threat_entries WHERE id = ?', (eid,))
        db.commit()
        log_activity('threat_entry_deleted', detail=existing['title'])
    return jsonify({'status': 'deleted'})


@threat_intel_bp.route('/api/threat-intel/entries/<int:eid>/resolve', methods=['POST'])
def api_threat_entries_resolve(eid):
    with db_session() as db:
        existing = db.execute('SELECT id, resolved FROM threat_entries WHERE id = ?', (eid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        new_state = 0 if existing['resolved'] else 1
        db.execute('UPDATE threat_entries SET resolved = ?, resolved_at = CASE WHEN ? = 1 THEN CURRENT_TIMESTAMP ELSE NULL END, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (new_state, new_state, eid))
        db.commit()
        row = db.execute('SELECT * FROM threat_entries WHERE id = ?', (eid,)).fetchone()
    return jsonify(dict(row))


# ─── Dashboard ────────────────────────────────────────────────────

@threat_intel_bp.route('/api/threat-intel/dashboard')
def api_threat_intel_dashboard():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) FROM threat_entries WHERE resolved = 0').fetchone()[0]
        by_severity = db.execute(
            'SELECT severity, COUNT(*) AS count FROM threat_entries WHERE resolved = 0 GROUP BY severity'
        ).fetchall()
        by_category = db.execute(
            'SELECT category, COUNT(*) AS count FROM threat_entries WHERE resolved = 0 GROUP BY category ORDER BY count DESC'
        ).fetchall()
        recent = db.execute(
            'SELECT * FROM threat_entries WHERE resolved = 0 ORDER BY severity_score DESC, created_at DESC LIMIT 10'
        ).fetchall()
        feeds_count = db.execute('SELECT COUNT(*) FROM threat_feeds WHERE enabled = 1').fetchone()[0]

        # Threat level assessment
        critical = sum(1 for r in by_severity if dict(r)['severity'] == 'critical')
        high = sum(1 for r in by_severity if dict(r)['severity'] == 'high')
        if critical > 0:
            threat_level = 'CRITICAL'
        elif high > 0:
            threat_level = 'ELEVATED'
        elif total > 5:
            threat_level = 'GUARDED'
        elif total > 0:
            threat_level = 'LOW'
        else:
            threat_level = 'NORMAL'

    return jsonify({
        'active_threats': total,
        'threat_level': threat_level,
        'by_severity': {dict(r)['severity']: dict(r)['count'] for r in by_severity},
        'by_category': [dict(r) for r in by_category],
        'recent': [dict(r) for r in recent],
        'active_feeds': feeds_count,
    })


# ─── Threat Map Data ─────────────────────────────────────────────

@threat_intel_bp.route('/api/threat-intel/map-data')
def api_threat_intel_map_data():
    """Return geolocated threats for map overlay."""
    with db_session() as db:
        rows = db.execute(
            'SELECT id, title, category, severity, lat, lng, location FROM threat_entries WHERE resolved = 0 AND lat IS NOT NULL AND lng IS NOT NULL'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Categories ───────────────────────────────────────────────────

@threat_intel_bp.route('/api/threat-intel/categories')
def api_threat_intel_categories():
    return jsonify(THREAT_CATEGORIES)


# ─── Summary ──────────────────────────────────────────────────────

@threat_intel_bp.route('/api/threat-intel/summary')
def api_threat_intel_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) FROM threat_entries').fetchone()[0]
        active = db.execute('SELECT COUNT(*) FROM threat_entries WHERE resolved = 0').fetchone()[0]
        feeds = db.execute('SELECT COUNT(*) FROM threat_feeds').fetchone()[0]
    return jsonify({
        'threat_entries_total': total,
        'threat_entries_active': active,
        'threat_feeds': feeds,
    })
