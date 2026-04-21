"""Daily Operations Brief (v7.7.0).

NOMAD is a rich dashboard, but rich dashboards rely on users remembering
to look at them. A daily brief inverts the relationship — it compiles
the signal into one readable page every morning so users don't miss
anything material.

What the brief blends (all optional — each section gracefully degrades
to "no data" if the source isn't populated):

  - Weather — latest reading + Zambretti prediction
  - Sunrise / sunset for today (from home coordinates)
  - Situation Room proximity alerts within the user's radius
  - Inventory: expiring within 14 days, low stock
  - Tasks due today
  - Family check-in summary (from v7.6.0)
  - Emergency Mode banner if active

All data is read-only — the brief is pure composition. No background
scheduler in v7.7.0 (that would overlap with the existing tasks engine);
users open the brief on demand. A future release can wire the tasks
scheduler to broadcast the brief at a configurable time.
"""

import logging
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify, Response

from db import db_session
from web.print_templates import render_print_document
from web.utils import esc as _esc, safe_float as _safe_float

brief_bp = Blueprint('brief', __name__)
log = logging.getLogger('nomad.brief')


def _get_home_coords(db):
    rows = db.execute(
        "SELECT key, value FROM settings WHERE key IN ('latitude','longitude','node_name')"
    ).fetchall()
    s = {r['key']: r['value'] for r in rows}
    return (
        _safe_float(s.get('latitude'), None),
        _safe_float(s.get('longitude'), None),
        s.get('node_name') or 'NOMAD Node',
    )


def _haversine_km(lat1, lng1, lat2, lng2):
    from math import radians, sin, cos, asin, sqrt
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat/2)**2 + cos(p1)*cos(p2)*sin(dlng/2)**2
    return 2 * R * asin(sqrt(a))


def _compile_brief(db):
    """Compose the full brief payload. Pure DB reads, no external calls."""
    home_lat, home_lng, node_name = _get_home_coords(db)
    now = datetime.now(timezone.utc)
    today_iso = now.date().isoformat()

    brief = {
        'generated_at': now.isoformat(),
        'node_name': node_name,
        'date': today_iso,
        'sections': {},
    }

    # --- Weather ---
    try:
        row = db.execute(
            'SELECT * FROM weather_log ORDER BY created_at DESC LIMIT 1'
        ).fetchone()
        if row:
            brief['sections']['weather'] = {
                'temp_c': row['temp_c'] if 'temp_c' in row.keys() else None,
                'humidity': row['humidity'] if 'humidity' in row.keys() else None,
                'pressure': row['pressure'] if 'pressure' in row.keys() else None,
                'conditions': row['conditions'] if 'conditions' in row.keys() else '',
                'notes': row['notes'] if 'notes' in row.keys() else '',
                'recorded_at': row['created_at'],
            }
    except Exception as e:
        log.debug(f'weather section failed: {e}')

    # --- Proximity (Situation Room) ---
    if home_lat is not None and home_lng is not None:
        radius_row = db.execute(
            "SELECT value FROM settings WHERE key = 'proximity_radius_km'"
        ).fetchone()
        radius = _safe_float(radius_row['value'] if radius_row else None) or 500.0
        try:
            rows = db.execute(
                "SELECT event_type, title, magnitude, lat, lng "
                "FROM sitroom_events "
                "WHERE event_type IN ('earthquake','weather_alert','fire','disease','volcano','conflict','oref_alert') "
                "AND lat IS NOT NULL AND lng IS NOT NULL AND lat != 0 AND lng != 0 "
                "LIMIT 5000"
            ).fetchall()
            nearby = []
            for r in rows:
                try:
                    d = _haversine_km(home_lat, home_lng, float(r['lat']), float(r['lng']))
                except (TypeError, ValueError):
                    continue
                if d <= radius:
                    nearby.append({
                        'event_type': r['event_type'],
                        'title': r['title'] or '',
                        'magnitude': r['magnitude'],
                        'distance_km': round(d, 1),
                    })
            nearby.sort(key=lambda e: e['distance_km'])
            brief['sections']['proximity'] = {
                'count': len(nearby),
                'radius_km': radius,
                'events': nearby[:10],
            }
        except Exception as e:
            log.debug(f'proximity section failed: {e}')

    # --- Inventory: expiring + low stock ---
    try:
        threshold = (now + timedelta(days=14)).strftime('%Y-%m-%d')
        expiring = db.execute(
            "SELECT name, expiration, quantity, unit FROM inventory "
            "WHERE expiration != '' AND expiration <= ? "
            "ORDER BY expiration LIMIT 25",
            (threshold,)
        ).fetchall()
        low = db.execute(
            "SELECT name, quantity, min_quantity, unit FROM inventory "
            "WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 25"
        ).fetchall()
        brief['sections']['inventory'] = {
            'expiring_14d': [dict(r) for r in expiring],
            'low_stock': [dict(r) for r in low],
        }
    except Exception as e:
        log.debug(f'inventory section failed: {e}')

    # --- Tasks due today ---
    try:
        rows = db.execute(
            "SELECT id, title, priority, due_at FROM scheduled_tasks "
            "WHERE completed_at IS NULL AND due_at IS NOT NULL "
            "ORDER BY due_at LIMIT 25"
        ).fetchall()
        today_tasks = []
        for r in rows:
            due = r['due_at'] or ''
            if today_iso in due or due <= today_iso:
                today_tasks.append(dict(r))
        brief['sections']['tasks'] = {'due_today': today_tasks}
    except Exception as e:
        log.debug(f'tasks section failed: {e}')

    # --- Family check-in summary ---
    try:
        rows = db.execute(
            'SELECT status, COUNT(*) as c FROM family_checkins GROUP BY status'
        ).fetchall()
        summary = {r['status']: r['c'] for r in rows}
        total = sum(summary.values())
        brief['sections']['family'] = {
            'total': total,
            'summary': summary,
        }
    except Exception as e:
        log.debug(f'family section failed: {e}')

    # --- Emergency state ---
    try:
        rows = db.execute(
            "SELECT key, value FROM settings WHERE key IN "
            "('emergency_active','emergency_started_at','emergency_reason')"
        ).fetchall()
        got = {r['key']: r['value'] for r in rows}
        active = (got.get('emergency_active', 'False') or '').lower() == 'true'
        brief['sections']['emergency'] = {
            'active': active,
            'reason': got.get('emergency_reason') or '',
            'started_at': got.get('emergency_started_at') or None,
        }
    except Exception as e:
        log.debug(f'emergency section failed: {e}')

    return brief


@brief_bp.route('/api/brief/daily')
def api_brief_daily():
    with db_session() as db:
        return jsonify(_compile_brief(db))


@brief_bp.route('/api/brief/daily/print')
def api_brief_daily_print():
    """Printable HTML version of the daily brief."""
    with db_session() as db:
        brief = _compile_brief(db)

    esc = _esc
    sections = brief.get('sections', {})

    # Compose body sections ---------------------------------------------------
    body_parts = []

    emer = sections.get('emergency') or {}
    if emer.get('active'):
        body_parts.append(f'''<section class="doc-section">
  <div class="doc-note-box" style="border-color:#c92a2a;background:#ffe5e5;color:#7a1d1d;">
    <div class="doc-strong" style="letter-spacing:0.12em;text-transform:uppercase;">Emergency Mode Active</div>
    <div style="margin-top:6px;">{esc(emer.get("reason", ""))}</div>
  </div>
</section>''')

    weather = sections.get('weather')
    if weather:
        rows = []
        if weather.get('temp_c') is not None:
            rows.append(f'<div class="doc-kv-row"><div class="doc-kv-key">Temperature</div><div>{esc(str(weather["temp_c"]))} °C</div></div>')
        if weather.get('humidity') is not None:
            rows.append(f'<div class="doc-kv-row"><div class="doc-kv-key">Humidity</div><div>{esc(str(weather["humidity"]))}%</div></div>')
        if weather.get('pressure') is not None:
            rows.append(f'<div class="doc-kv-row"><div class="doc-kv-key">Pressure</div><div>{esc(str(weather["pressure"]))} hPa</div></div>')
        if weather.get('conditions'):
            rows.append(f'<div class="doc-kv-row"><div class="doc-kv-key">Conditions</div><div>{esc(weather["conditions"])}</div></div>')
        body_parts.append(f'''<section class="doc-section">
  <h2 class="doc-section-title">Weather</h2>
  <div class="doc-panel"><div class="doc-kv">{"".join(rows) or '<div class="doc-empty">No recent reading.</div>'}</div></div>
</section>''')
    else:
        body_parts.append('<section class="doc-section"><h2 class="doc-section-title">Weather</h2><div class="doc-empty">No weather data. Log a reading in the Weather tab.</div></section>')

    prox = sections.get('proximity')
    if prox:
        if prox['count'] == 0:
            body_parts.append(f'''<section class="doc-section">
  <h2 class="doc-section-title">Proximity Alerts (within {int(prox["radius_km"])} km)</h2>
  <div class="doc-empty">All clear — no active threats within radius.</div>
</section>''')
        else:
            rows = ''.join(
                f'<tr><td class="doc-strong">{esc(e["event_type"].replace("_", " ").title())}</td>'
                f'<td>{esc(e["title"] or "")}</td>'
                f'<td>{e["distance_km"]} km</td></tr>'
                for e in prox['events']
            )
            body_parts.append(f'''<section class="doc-section">
  <h2 class="doc-section-title">Proximity Alerts (within {int(prox["radius_km"])} km)</h2>
  <div class="doc-table-shell"><table><thead><tr><th>Type</th><th>Title</th><th>Distance</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>''')

    inv = sections.get('inventory') or {}
    exp = inv.get('expiring_14d') or []
    low = inv.get('low_stock') or []
    if exp or low:
        exp_html = ''.join(
            f'<tr><td class="doc-strong">{esc(r["name"])}</td><td>{esc(str(r.get("expiration","")))}</td>'
            f'<td>{esc(str(r.get("quantity","") or ""))} {esc(str(r.get("unit","") or ""))}</td></tr>'
            for r in exp
        )
        low_html = ''.join(
            f'<tr><td class="doc-alert">{esc(r["name"])}</td>'
            f'<td>{esc(str(r.get("quantity","") or ""))} / {esc(str(r.get("min_quantity","") or ""))} {esc(str(r.get("unit","") or ""))}</td></tr>'
            for r in low
        )
        _exp_inner = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Expires</th><th>Qty</th></tr></thead><tbody>' + exp_html + '</tbody></table></div>' if exp else '<div class="doc-empty">Nothing expiring.</div>'
        exp_section = f'<div class="doc-panel"><h2 class="doc-section-title">Expiring (14 days)</h2>{_exp_inner}</div>'
        _low_inner = '<div class="doc-table-shell"><table><thead><tr><th>Item</th><th>Qty / Min</th></tr></thead><tbody>' + low_html + '</tbody></table></div>' if low else '<div class="doc-empty">All above minimum.</div>'
        low_section = f'<div class="doc-panel"><h2 class="doc-section-title">Low Stock</h2>{_low_inner}</div>'
        body_parts.append(f'<section class="doc-section"><div class="doc-grid-2">{exp_section}{low_section}</div></section>')

    tasks = (sections.get('tasks') or {}).get('due_today') or []
    if tasks:
        rows = ''.join(
            f'<tr><td class="doc-strong">{esc(t.get("title","") or "")}</td>'
            f'<td>{esc(t.get("priority","") or "")}</td>'
            f'<td>{esc(str(t.get("due_at","") or ""))}</td></tr>'
            for t in tasks
        )
        body_parts.append(f'''<section class="doc-section">
  <h2 class="doc-section-title">Tasks Due Today</h2>
  <div class="doc-table-shell"><table><thead><tr><th>Task</th><th>Priority</th><th>Due</th></tr></thead><tbody>{rows}</tbody></table></div>
</section>''')

    family = sections.get('family') or {}
    if family.get('total', 0) > 0:
        summary = family.get('summary', {})
        chips = []
        for status, label in [('ok', 'OK'), ('en_route', 'En route'), ('needs_help', 'Needs help'), ('unaccounted', 'Unaccounted')]:
            count = summary.get(status, 0)
            if count > 0:
                chips.append(f'<span class="doc-chip">{label}: {count}</span>')
        body_parts.append(f'''<section class="doc-section">
  <h2 class="doc-section-title">Family Check-in ({family["total"]} tracked)</h2>
  <div class="doc-chip-list">{"".join(chips)}</div>
</section>''')

    now_stamp = datetime.now().strftime('%Y-%m-%d %H:%M')
    body_parts.append(f'''<section class="doc-section">
  <div class="doc-footer">
    <span>Compiled from your current NOMAD data. Open-time brief.</span>
    <span>Generated {esc(now_stamp)}.</span>
  </div>
</section>''')

    # Stats for the header strip
    stat_items = []
    if prox:
        stat_items.append(('Proximity events', prox.get('count', 0)))
    if inv:
        stat_items.append(('Expiring (14d)', len(exp)))
    if inv:
        stat_items.append(('Low stock', len(low)))
    stat_items.append(('Tasks today', len(tasks)))
    if family:
        stat_items.append(('Family', family.get('total', 0)))

    html = render_print_document(
        'Daily Operations Brief',
        'One-page compiled snapshot — weather, proximity alerts, inventory gaps, tasks, and household status.',
        '\n'.join(body_parts),
        eyebrow=f'NOMAD Daily Brief — {brief["node_name"]}',
        meta_items=[f'Generated {esc(now_stamp)}', f'Node {esc(brief["node_name"])}'],
        stat_items=stat_items,
        accent_start='#1d3557',
        accent_end='#3b6e99',
    )
    return Response(html, mimetype='text/html')
