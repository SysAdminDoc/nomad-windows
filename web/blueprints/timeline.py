"""Unified calendar/timeline view — aggregates all dated events across modules."""

from flask import Blueprint, request, jsonify
from db import db_session
from web.utils import get_query_int as _get_query_int

timeline_bp = Blueprint('timeline', __name__)


@timeline_bp.route('/api/timeline')
def api_timeline():
    """Aggregate all dates from across modules into one timeline.

    Query params:
      start  — ISO date (default: today - 30 days)
      end    — ISO date (default: today + 90 days)
      types  — comma-separated filter (e.g. 'expiration,maintenance,task')
    """
    start = request.args.get('start', '')
    end = request.args.get('end', '')
    type_filter = request.args.get('types', '')
    type_set = set(type_filter.split(',')) if type_filter else set()

    with db_session() as db:
        events = []

        # ── Inventory Expirations ──
        if not type_set or 'expiration' in type_set:
            rows = db.execute(
                '''SELECT id, name, category, expiration AS event_date, quantity, unit
                   FROM inventory
                   WHERE expiration != '' AND expiration IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'expiration',
                        'source': 'inventory',
                        'source_id': r['id'],
                        'title': f'{r["name"]} expires',
                        'date': r['event_date'],
                        'detail': f'{r["quantity"]} {r.get("unit", "")} — {r["category"]}',
                        'severity': _expiration_severity(r['event_date']),
                    })

        # ── Medical Supply Expirations ──
        if not type_set or 'expiration' in type_set:
            rows = db.execute(
                '''SELECT id, name, expiration AS event_date, quantity
                   FROM inventory
                   WHERE category = 'Medical' AND expiration != '' AND expiration IS NOT NULL'''
            ).fetchall()
            # Already captured above, skip duplicate

        # ── Vehicle Maintenance Due ──
        if not type_set or 'maintenance' in type_set:
            rows = db.execute(
                '''SELECT m.id, m.service_type, m.next_due_date AS event_date, m.status,
                          v.make, v.model, v.year
                   FROM vehicle_maintenance m
                   LEFT JOIN vehicles v ON v.id = m.vehicle_id
                   WHERE m.next_due_date != '' AND m.next_due_date IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    vehicle_name = f'{r.get("year", "")} {r.get("make", "")} {r.get("model", "")}'.strip()
                    events.append({
                        'type': 'maintenance',
                        'source': 'vehicle_maintenance',
                        'source_id': r['id'],
                        'title': f'{r["service_type"]} — {vehicle_name}',
                        'date': r['event_date'],
                        'detail': f'Status: {r["status"]}',
                        'severity': 'warning' if r['status'] == 'pending' else 'info',
                    })

        # ── Scheduled Tasks ──
        if not type_set or 'task' in type_set:
            rows = db.execute(
                '''SELECT id, name AS title, next_due AS event_date, category, assigned_to
                   FROM scheduled_tasks
                   WHERE next_due != '' AND next_due IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'task',
                        'source': 'scheduled_tasks',
                        'source_id': r['id'],
                        'title': r['title'],
                        'date': r['event_date'],
                        'detail': f'{r.get("category", "")} — {r.get("assigned_to", "")}',
                        'severity': _task_severity(r.get('priority', 'medium')),
                    })

        # ── Financial Document Expirations ──
        if not type_set or 'expiration' in type_set or 'financial' in type_set:
            rows = db.execute(
                '''SELECT id, description AS name, doc_type, expiration AS event_date
                   FROM financial_documents
                   WHERE expiration != '' AND expiration IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'financial_expiration',
                        'source': 'financial_documents',
                        'source_id': r['id'],
                        'title': f'{r["name"]} ({r["doc_type"]}) expires',
                        'date': r['event_date'],
                        'detail': 'Financial document',
                        'severity': _expiration_severity(r['event_date']),
                    })

        # ── Water Storage Expirations ──
        if not type_set or 'expiration' in type_set or 'water' in type_set:
            rows = db.execute(
                '''SELECT id, name, expiration AS event_date, current_gallons
                   FROM water_storage
                   WHERE expiration != '' AND expiration IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'water_expiration',
                        'source': 'water_storage',
                        'source_id': r['id'],
                        'title': f'{r["name"]} water expires',
                        'date': r['event_date'],
                        'detail': f'{r["current_gallons"]} gal',
                        'severity': _expiration_severity(r['event_date']),
                    })

        # ── Loadout Item Expirations ──
        if not type_set or 'expiration' in type_set or 'loadout' in type_set:
            rows = db.execute(
                '''SELECT i.id, i.name, i.expiration AS event_date, b.name AS bag_name
                   FROM loadout_items i
                   LEFT JOIN loadout_bags b ON b.id = i.bag_id
                   WHERE i.expiration != '' AND i.expiration IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'loadout_expiration',
                        'source': 'loadout_items',
                        'source_id': r['id'],
                        'title': f'{r["name"]} in {r.get("bag_name", "bag")} expires',
                        'date': r['event_date'],
                        'detail': 'Loadout item',
                        'severity': _expiration_severity(r['event_date']),
                    })

        # ── Filter Replacement Due ──
        if not type_set or 'maintenance' in type_set or 'water' in type_set:
            rows = db.execute(
                '''SELECT id, name, replacement_date AS event_date, status
                   FROM water_filters
                   WHERE replacement_date != '' AND replacement_date IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'filter_replacement',
                        'source': 'water_filters',
                        'source_id': r['id'],
                        'title': f'{r["name"]} filter replacement',
                        'date': r['event_date'],
                        'detail': f'Status: {r["status"]}',
                        'severity': 'warning',
                    })

        # ── Fuel Storage Expirations ──
        if not type_set or 'expiration' in type_set or 'fuel' in type_set:
            rows = db.execute(
                '''SELECT id, fuel_type, quantity, expires AS event_date
                   FROM fuel_storage
                   WHERE expires != '' AND expires IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'fuel_expiration',
                        'source': 'fuel_storage',
                        'source_id': r['id'],
                        'title': f'{r["fuel_type"]} fuel expires',
                        'date': r['event_date'],
                        'detail': f'{r["quantity"]} gal',
                        'severity': _expiration_severity(r['event_date']),
                    })

        # ── Equipment Service Due ──
        if not type_set or 'maintenance' in type_set:
            rows = db.execute(
                '''SELECT id, name, category, next_service AS event_date, status
                   FROM equipment_log
                   WHERE next_service != '' AND next_service IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'equipment_service',
                        'source': 'equipment_log',
                        'source_id': r['id'],
                        'title': f'{r["name"]} service due',
                        'date': r['event_date'],
                        'detail': f'{r["category"]} — {r["status"]}',
                        'severity': 'warning',
                    })

        # ── Drill / Exercise History ──
        if not type_set or 'drill' in type_set:
            rows = db.execute(
                '''SELECT id, title, drill_type, created_at AS event_date, duration_sec
                   FROM drill_history
                   ORDER BY created_at DESC LIMIT 100'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                date_str = r['event_date'][:10] if r['event_date'] else ''
                if _in_range(date_str, start, end):
                    events.append({
                        'type': 'drill',
                        'source': 'drill_history',
                        'source_id': r['id'],
                        'title': f'{r["title"]} ({r["drill_type"]})',
                        'date': date_str,
                        'detail': f'{r["duration_sec"]}s',
                        'severity': 'info',
                    })

        # ── Preservation Batch Dates ──
        if not type_set or 'preservation' in type_set:
            rows = db.execute(
                '''SELECT id, crop, method, batch_date AS event_date
                   FROM preservation_log
                   WHERE batch_date != '' AND batch_date IS NOT NULL'''
            ).fetchall()
            for r in rows:
                r = dict(r)
                if _in_range(r['event_date'], start, end):
                    events.append({
                        'type': 'preservation',
                        'source': 'preservation_log',
                        'source_id': r['id'],
                        'title': f'{r["crop"]} — {r["method"]}',
                        'date': r['event_date'],
                        'detail': 'Preservation batch',
                        'severity': 'info',
                    })

        # Sort all events by date
        events.sort(key=lambda e: e.get('date', ''))

    return jsonify({
        'events': events,
        'total': len(events),
        'start': start,
        'end': end,
    })


@timeline_bp.route('/api/timeline/upcoming')
def api_timeline_upcoming():
    """Get the next N upcoming events from today forward."""
    limit = _get_query_int(request, 'limit', 20, minimum=1, maximum=200)
    from datetime import date, timedelta
    today = date.today().isoformat()
    future = (date.today() + timedelta(days=180)).isoformat()

    # Re-use the main timeline endpoint logic
    with db_session() as db:
        events = []
        _collect_upcoming(db, events, today, future)
        events.sort(key=lambda e: e.get('date', ''))
        events = events[:limit]

    return jsonify({'events': events, 'total': len(events)})


@timeline_bp.route('/api/timeline/overdue')
def api_timeline_overdue():
    """Get all overdue items (past date, still active)."""
    from datetime import date
    today = date.today().isoformat()

    with db_session() as db:
        events = []

        # Overdue tasks
        rows = db.execute(
            "SELECT id, name AS title, next_due, category FROM scheduled_tasks WHERE next_due != '' AND next_due < ?",
            (today,)
        ).fetchall()
        for r in rows:
            r = dict(r)
            events.append({
                'type': 'task_overdue',
                'source': 'scheduled_tasks',
                'source_id': r['id'],
                'title': r['title'],
                'date': r['next_due'],
                'detail': r.get('category', ''),
                'severity': 'critical',
            })

        # Overdue maintenance
        rows = db.execute(
            "SELECT m.id, m.service_type, m.next_due_date, v.make, v.model FROM vehicle_maintenance m LEFT JOIN vehicles v ON v.id = m.vehicle_id WHERE m.status = 'pending' AND m.next_due_date != '' AND m.next_due_date < ?",
            (today,)
        ).fetchall()
        for r in rows:
            r = dict(r)
            events.append({
                'type': 'maintenance_overdue',
                'source': 'vehicle_maintenance',
                'source_id': r['id'],
                'title': f'{r["service_type"]} — {r.get("make", "")} {r.get("model", "")}',
                'date': r['next_due_date'],
                'detail': 'Overdue maintenance',
                'severity': 'critical',
            })

        # Expired inventory still in stock
        rows = db.execute(
            "SELECT id, name, category, expiration, quantity FROM inventory WHERE expiration != '' AND expiration < ? AND quantity > 0",
            (today,)
        ).fetchall()
        for r in rows:
            r = dict(r)
            events.append({
                'type': 'expired_inventory',
                'source': 'inventory',
                'source_id': r['id'],
                'title': f'{r["name"]} EXPIRED',
                'date': r['expiration'],
                'detail': f'{r["quantity"]} still in stock — {r["category"]}',
                'severity': 'critical',
            })

        events.sort(key=lambda e: e.get('date', ''))

    return jsonify({'events': events, 'total': len(events)})


@timeline_bp.route('/api/timeline/summary')
def api_timeline_summary():
    from datetime import date, timedelta
    today = date.today().isoformat()
    week = (date.today() + timedelta(days=7)).isoformat()
    month = (date.today() + timedelta(days=30)).isoformat()

    with db_session() as db:
        overdue_tasks = db.execute("SELECT COUNT(*) FROM scheduled_tasks WHERE next_due != '' AND next_due < ?", (today,)).fetchone()[0]
        expiring_week = db.execute("SELECT COUNT(*) FROM inventory WHERE expiration != '' AND expiration BETWEEN ? AND ?", (today, week)).fetchone()[0]
        expiring_month = db.execute("SELECT COUNT(*) FROM inventory WHERE expiration != '' AND expiration BETWEEN ? AND ?", (today, month)).fetchone()[0]
        maint_due_week = db.execute("SELECT COUNT(*) FROM vehicle_maintenance WHERE status = 'pending' AND next_due_date != '' AND next_due_date BETWEEN ? AND ?", (today, week)).fetchone()[0]

    return jsonify({
        'overdue_tasks': overdue_tasks,
        'expiring_this_week': expiring_week,
        'expiring_this_month': expiring_month,
        'maintenance_due_this_week': maint_due_week,
    })


def _collect_upcoming(db, events, start, end):
    """Collect upcoming events into the events list."""
    # Inventory expirations
    rows = db.execute(
        "SELECT id, name, category, expiration, quantity, unit FROM inventory WHERE expiration != '' AND expiration BETWEEN ? AND ?",
        (start, end)
    ).fetchall()
    for r in rows:
        r = dict(r)
        events.append({
            'type': 'expiration', 'source': 'inventory', 'source_id': r['id'],
            'title': f'{r["name"]} expires', 'date': r['expiration'],
            'detail': f'{r["quantity"]} {r.get("unit", "")} — {r["category"]}',
            'severity': _expiration_severity(r['expiration']),
        })
    # Scheduled tasks
    rows = db.execute(
        "SELECT id, name AS title, next_due, category FROM scheduled_tasks WHERE next_due != '' AND next_due BETWEEN ? AND ?",
        (start, end)
    ).fetchall()
    for r in rows:
        r = dict(r)
        events.append({
            'type': 'task', 'source': 'scheduled_tasks', 'source_id': r['id'],
            'title': r['title'], 'date': r['next_due'],
            'detail': r.get('category', ''),
            'severity': _task_severity(r.get('priority', 'medium')),
        })
    # Vehicle maintenance
    rows = db.execute(
        "SELECT m.id, m.service_type, m.next_due_date, v.make, v.model FROM vehicle_maintenance m LEFT JOIN vehicles v ON v.id = m.vehicle_id WHERE m.next_due_date != '' AND m.next_due_date BETWEEN ? AND ?",
        (start, end)
    ).fetchall()
    for r in rows:
        r = dict(r)
        events.append({
            'type': 'maintenance', 'source': 'vehicle_maintenance', 'source_id': r['id'],
            'title': f'{r["service_type"]} — {r.get("make", "")} {r.get("model", "")}',
            'date': r['next_due_date'], 'detail': 'Vehicle maintenance',
            'severity': 'warning',
        })


def _in_range(date_str, start, end):
    if not date_str:
        return False
    d = date_str[:10]
    if start and d < start:
        return False
    if end and d > end:
        return False
    return True


def _expiration_severity(date_str):
    from datetime import date, timedelta
    try:
        exp = date.fromisoformat(date_str[:10])
        today = date.today()
        if exp < today:
            return 'critical'
        elif exp < today + timedelta(days=7):
            return 'warning'
        elif exp < today + timedelta(days=30):
            return 'info'
        return 'low'
    except (ValueError, TypeError):
        return 'info'


def _task_severity(priority):
    return {'critical': 'critical', 'high': 'warning', 'medium': 'info', 'low': 'low'}.get(priority, 'info')
