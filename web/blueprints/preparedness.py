"""Preparedness blueprint — livestock, scenarios, drills, training, incidents, alerts."""

import json
import time
import logging
import threading
import queue
from datetime import datetime, timedelta, timezone
from flask import Blueprint, jsonify, request, Response

from db import get_db, db_session, log_activity
from web.auth import require_auth
from web.validation import validate_json
from web.utils import (
    clone_json_fallback as _clone_json_fallback,
    get_query_int as _get_query_int,
    require_json_body as _require_json_body,
    safe_json_value as _safe_json_value,
    safe_json_list as _safe_json_list,
    close_db_safely as _close_db_safely,
    validate_bulk_ids as _validate_bulk_ids,
)
from web.state import (
    broadcast_event,
    MAX_SSE_CLIENTS, _sse_clients, _sse_lock,
    sse_register_client, sse_unregister_client, sse_touch_client,
)
import web.state as _state
from services import ollama

log = logging.getLogger('nomad.web')

preparedness_bp = Blueprint('preparedness', __name__)


def _safe_response_json(response, fallback=None):
    if fallback is None:
        fallback = {}
    try:
        parsed = response.json()
    except Exception:
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)


# ─── Cross-module Preparedness Dashboard Snapshot ────────────────────
#
# Returns a single operational snapshot across inventory, medical, power,
# garden, contacts, tasks, incidents, and alerts so the Preparedness tab
# (or Home, or any embedded widget) can render a "daily standup" view
# without tab-hopping. Every section is wrapped in try/except so a
# missing table on a fresh install or partial migration never takes down
# the whole response — the section just returns `None` with an
# ``error`` hint.

def _safe_count(db, sql, params=()):
    try:
        row = db.execute(sql, params).fetchone()
        return row[0] if row else 0
    except Exception as exc:
        log.debug('dashboard safe_count failed: %s (%s)', sql, exc)
        return 0


@preparedness_bp.route('/api/preparedness/dashboard')
def api_preparedness_dashboard():
    """Aggregated cross-module snapshot of field readiness.

    Shape::

        {
          "generated_at": "2026-04-11T10:00:00Z",
          "inventory": {"total": 0, "low_stock": 0, "expiring_30d": 0,
                        "categories": {"food": 12, ...}},
          "medical":   {"patients": 0, "with_allergies": 0, "expiring_meds": 0},
          "power":     {"devices": 0, "latest_soc_pct": null},
          "garden":    {"plots": 0, "active_plantings": 0},
          "contacts":  {"total": 0, "with_callsign": 0, "with_skills": 0},
          "tasks":     {"total": 0, "overdue": 0, "due_today": 0},
          "incidents": {"total": 0, "last_24h": 0, "open_critical": 0},
          "alerts":    {"active": 0, "critical": 0},
          "readiness_hint": "B" | "needs-attention"
        }

    Callers on Home and the Preparedness Overview can render one of the
    listed sections as a card without issuing seven separate fetches.
    """
    today = datetime.now().strftime('%Y-%m-%d')
    soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
    # generated_at must be a real UTC timestamp — the previous version
    # used datetime.now() (naive local time) with a trailing 'Z', so any
    # client comparing it against SQLite's datetime('now') (which IS UTC)
    # saw a drift equal to the machine's timezone offset.
    payload = {
        'generated_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }

    with db_session() as db:
        # Inventory
        try:
            total = _safe_count(db, 'SELECT COUNT(*) FROM inventory')
            low = _safe_count(
                db,
                'SELECT COUNT(*) FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0',
            )
            expiring = _safe_count(
                db,
                "SELECT COUNT(*) FROM inventory WHERE expiration != '' AND expiration <= ?",
                (soon,),
            )
            cats = {}
            for r in db.execute(
                'SELECT category, COUNT(*) AS c FROM inventory GROUP BY category ORDER BY c DESC LIMIT 20'
            ).fetchall():
                cats[r['category'] or 'uncategorized'] = r['c']
            payload['inventory'] = {
                'total': total,
                'low_stock': low,
                'expiring_30d': expiring,
                'categories': cats,
            }
        except Exception as exc:
            log.debug('dashboard inventory section failed: %s', exc)
            payload['inventory'] = {'error': 'unavailable'}

        # Medical
        try:
            patients = _safe_count(db, 'SELECT COUNT(*) FROM patients')
            with_allergies = _safe_count(
                db,
                "SELECT COUNT(*) FROM patients WHERE allergies IS NOT NULL "
                "AND allergies != '' AND allergies != '[]'",
            )
            # Expiring meds come from the `inventory` table with a
            # medical category — there is no standalone `medical_supplies`
            # table in the schema, so the previous query silently caught
            # the "no such table" error and always returned 0.
            # Category casing varies across seed templates (some use
            # 'Medical', others 'medical'), so match case-insensitively.
            expiring_meds = _safe_count(
                db,
                "SELECT COUNT(*) FROM inventory "
                "WHERE LOWER(category) = 'medical' "
                "AND expiration IS NOT NULL AND expiration != '' "
                "AND expiration <= ?",
                (soon,),
            )
            payload['medical'] = {
                'patients': patients,
                'with_allergies': with_allergies,
                'expiring_meds': expiring_meds,
            }
        except Exception as exc:
            log.debug('dashboard medical section failed: %s', exc)
            payload['medical'] = {'error': 'unavailable'}

        # Power
        try:
            devices = _safe_count(db, 'SELECT COUNT(*) FROM power_devices')
            latest_soc = None
            try:
                row = db.execute(
                    'SELECT soc_pct FROM power_log ORDER BY created_at DESC LIMIT 1'
                ).fetchone()
                if row and row['soc_pct'] is not None:
                    latest_soc = row['soc_pct']
            except Exception:
                pass
            payload['power'] = {
                'devices': devices,
                'latest_soc_pct': latest_soc,
            }
        except Exception as exc:
            log.debug('dashboard power section failed: %s', exc)
            payload['power'] = {'error': 'unavailable'}

        # Garden
        try:
            plots = _safe_count(db, 'SELECT COUNT(*) FROM garden_plots')
            active = _safe_count(
                db,
                "SELECT COUNT(*) FROM garden_plots WHERE status = 'active' OR status = 'planted'",
            )
            payload['garden'] = {
                'plots': plots,
                'active_plantings': active,
            }
        except Exception as exc:
            log.debug('dashboard garden section failed: %s', exc)
            payload['garden'] = {'error': 'unavailable'}

        # Contacts
        try:
            total_c = _safe_count(db, 'SELECT COUNT(*) FROM contacts')
            with_cs = _safe_count(
                db, "SELECT COUNT(*) FROM contacts WHERE callsign IS NOT NULL AND callsign != ''",
            )
            with_skills = _safe_count(
                db, "SELECT COUNT(*) FROM contacts WHERE skills IS NOT NULL AND skills != ''",
            )
            payload['contacts'] = {
                'total': total_c,
                'with_callsign': with_cs,
                'with_skills': with_skills,
            }
        except Exception as exc:
            log.debug('dashboard contacts section failed: %s', exc)
            payload['contacts'] = {'error': 'unavailable'}

        # Tasks (scheduled)
        try:
            total_t = _safe_count(db, 'SELECT COUNT(*) FROM scheduled_tasks')
            overdue = _safe_count(
                db,
                "SELECT COUNT(*) FROM scheduled_tasks WHERE next_due IS NOT NULL "
                "AND next_due < ? AND (completed IS NULL OR completed = 0)",
                (today,),
            )
            due_today = _safe_count(
                db,
                "SELECT COUNT(*) FROM scheduled_tasks WHERE next_due = ? "
                "AND (completed IS NULL OR completed = 0)",
                (today,),
            )
            payload['tasks'] = {
                'total': total_t,
                'overdue': overdue,
                'due_today': due_today,
            }
        except Exception as exc:
            log.debug('dashboard tasks section failed: %s', exc)
            payload['tasks'] = {'error': 'unavailable'}

        # Incidents
        try:
            total_i = _safe_count(db, 'SELECT COUNT(*) FROM incidents')
            last_24h = _safe_count(
                db,
                "SELECT COUNT(*) FROM incidents WHERE created_at >= datetime('now', '-24 hours')",
            )
            open_critical = _safe_count(
                db,
                "SELECT COUNT(*) FROM incidents WHERE severity = 'critical'",
            )
            payload['incidents'] = {
                'total': total_i,
                'last_24h': last_24h,
                'open_critical': open_critical,
            }
        except Exception as exc:
            log.debug('dashboard incidents section failed: %s', exc)
            payload['incidents'] = {'error': 'unavailable'}

        # Alerts (active proactive alerts stored by the alert engine)
        try:
            active_alerts = _safe_count(
                db,
                "SELECT COUNT(*) FROM alerts WHERE dismissed IS NULL OR dismissed = 0",
            )
            critical_alerts = _safe_count(
                db,
                "SELECT COUNT(*) FROM alerts WHERE severity = 'critical' "
                "AND (dismissed IS NULL OR dismissed = 0)",
            )
            payload['alerts'] = {
                'active': active_alerts,
                'critical': critical_alerts,
            }
        except Exception as exc:
            log.debug('dashboard alerts section failed: %s', exc)
            payload['alerts'] = {'error': 'unavailable'}

    # Coarse readiness hint: red flags raise 'needs-attention', otherwise
    # we defer to the full readiness-score endpoint for the letter grade.
    needs_attention = (
        payload.get('inventory', {}).get('low_stock', 0) > 0
        or payload.get('inventory', {}).get('expiring_30d', 0) > 0
        or payload.get('tasks', {}).get('overdue', 0) > 0
        or payload.get('alerts', {}).get('critical', 0) > 0
        or payload.get('incidents', {}).get('open_critical', 0) > 0
    )
    payload['readiness_hint'] = 'needs-attention' if needs_attention else 'ok'

    return jsonify(payload)


# ─── Incident Log API ────────────────────────────────────────────────

@preparedness_bp.route('/api/incidents')
def api_incidents_list():
    with db_session() as db:
        limit = _get_query_int(request, 'limit', 100, minimum=1, maximum=500)
        cat = request.args.get('category', '')
        query = 'SELECT * FROM incidents'
        params = []
        if cat:
            query += ' WHERE category = ?'
            params.append(cat)
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@preparedness_bp.route('/api/incidents', methods=['POST'])
@validate_json({
    'description': {'type': str, 'required': True, 'max_length': 2000},
    'severity': {'type': str, 'max_length': 50},
    'category': {'type': str, 'max_length': 100},
})
def api_incidents_create():
    data = request.get_json() or {}
    desc = (data.get('description', '') or '').strip()
    if not desc:
        return jsonify({'error': 'Description required'}), 400
    with db_session() as db:
        cur = db.execute('INSERT INTO incidents (severity, category, description) VALUES (?, ?, ?)',
                         (data.get('severity', 'info'), data.get('category', 'other'), desc))
        db.commit()
        row = db.execute('SELECT * FROM incidents WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@preparedness_bp.route('/api/incidents/<int:iid>', methods=['DELETE'])
def api_incidents_delete(iid):
    with db_session() as db:
        r = db.execute('DELETE FROM incidents WHERE id = ?', (iid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})

@preparedness_bp.route('/api/incidents/clear', methods=['POST'])
def api_incidents_clear():
    with db_session() as db:
        db.execute('DELETE FROM incidents')
        db.commit()
    return jsonify({'status': 'cleared'})


# ─── Proactive Alert System ─────────────────────────────────────────

# Event signalled on app shutdown to break the alert engine loop cleanly,
# rather than sleeping 300s and being force-killed by the daemon flag.
_alert_stop_event = threading.Event()


def stop_alert_engine():
    """Signal the alert engine to exit its loop on next wake."""
    _alert_stop_event.set()


def _run_alert_checks():
    """Background alert engine — checks inventory, weather, incidents every 5 minutes."""
    if not _state.try_begin_alert_check():
        return
    try:
        if _alert_stop_event.wait(timeout=30):  # Wait for app to initialize
            return
        while not _alert_stop_event.is_set():
            db = None
            try:
                alerts = []
                db = get_db()
                now = datetime.now()
                today = now.strftime('%Y-%m-%d')
                soon = (now + timedelta(days=14)).strftime('%Y-%m-%d')

                # 1. Critical burn rate items (<7 days supply)
                burn_items = db.execute(
                    'SELECT name, quantity, daily_usage, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 7 ORDER BY (quantity / daily_usage) LIMIT 50'
                ).fetchall()
                for item in burn_items:
                    days = round(item['quantity'] / item['daily_usage'], 1)
                    sev = 'critical' if days < 3 else 'warning'
                    alerts.append({
                        'type': 'burn_rate', 'severity': sev,
                        'title': f'{item["name"]} running low',
                        'message': f'{item["name"]}: {days} days remaining at current usage ({item["quantity"]} {item.get("category", "")} left, using {item["daily_usage"]}/day). Reduce consumption or resupply.',
                    })

                # 2. Expiring items (within 14 days)
                expiring = db.execute(
                    "SELECT name, expiration FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ? ORDER BY expiration",
                    (soon, today)
                ).fetchall()
                for item in expiring:
                    try:
                        exp_days = (datetime.strptime(item['expiration'], '%Y-%m-%d') - now).days
                    except (ValueError, TypeError):
                        continue
                    sev = 'critical' if exp_days <= 3 else 'warning'
                    alerts.append({
                        'type': 'expiration', 'severity': sev,
                        'title': f'{item["name"]} expiring',
                        'message': f'{item["name"]} expires in {exp_days} day{"s" if exp_days != 1 else ""} ({item["expiration"]}). Use, rotate, or replace.',
                    })

                # 3. Barometric pressure drop (>4mb in recent readings)
                pressure_rows = db.execute(
                    'SELECT pressure_hpa, created_at FROM weather_log WHERE pressure_hpa IS NOT NULL ORDER BY created_at DESC LIMIT 10'
                ).fetchall()
                if len(pressure_rows) >= 2:
                    newest = pressure_rows[0]['pressure_hpa']
                    oldest = pressure_rows[-1]['pressure_hpa']
                    diff = newest - oldest
                    if diff < -4:
                        alerts.append({
                            'type': 'weather', 'severity': 'warning',
                            'title': 'Rapid pressure drop detected',
                            'message': f'Barometric pressure dropped {abs(round(diff, 1))} hPa ({round(oldest, 1)} to {round(newest, 1)}). Storm likely within 12-24 hours. Secure shelter, fill water containers, charge devices.',
                        })

                # 4. Incident cluster (3+ in same category within 48h)
                cutoff = (now - timedelta(hours=48)).strftime('%Y-%m-%d %H:%M:%S')
                incident_clusters = db.execute(
                    "SELECT category, COUNT(*) as cnt FROM incidents WHERE created_at >= ? GROUP BY category HAVING cnt >= 3",
                    (cutoff,)
                ).fetchall()
                for cluster in incident_clusters:
                    alerts.append({
                        'type': 'incident_cluster', 'severity': 'warning',
                        'title': f'{cluster["category"].title()} incidents escalating',
                        'message': f'{cluster["cnt"]} {cluster["category"]} incidents in the last 48 hours. Review incident log and consider elevating threat level.',
                    })

                # 5. Low stock items (quantity <= min_quantity)
                low_stock = db.execute(
                    'SELECT name, quantity, unit, min_quantity FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 50'
                ).fetchall()
                for item in low_stock:
                    alerts.append({
                        'type': 'low_stock', 'severity': 'warning',
                        'title': f'{item["name"]} below minimum',
                        'message': f'{item["name"]}: {item["quantity"]} {item["unit"]} remaining (minimum: {item["min_quantity"]}). Add to shopping list or resupply.',
                    })

                # 6. Equipment overdue for service
                try:
                    overdue_equip = db.execute(
                        "SELECT name, category, next_service FROM equipment_log WHERE next_service != '' AND next_service < ? AND status != 'non-operational'",
                        (today,)
                    ).fetchall()
                    for eq in overdue_equip:
                        alerts.append({
                            'type': 'equipment_service', 'severity': 'warning',
                            'title': f'{eq["name"]} service overdue',
                            'message': f'{eq["name"]} ({eq["category"]}) was due for service on {eq["next_service"]}. Service overdue equipment may fail when needed most.',
                        })
                except Exception as exc:
                    log.debug('Alert engine skipped equipment service check: %s', exc)

                # 7. Expiring fuel (within 30 days)
                try:
                    fuel_expiry = (now + timedelta(days=30)).strftime('%Y-%m-%d')
                    expiring_fuel = db.execute(
                        "SELECT fuel_type, quantity, unit, expires FROM fuel_storage WHERE expires != '' AND expires <= ? AND expires >= ?",
                        (fuel_expiry, today)
                    ).fetchall()
                    for f in expiring_fuel:
                        days_left = (datetime.strptime(f['expires'], '%Y-%m-%d') - now).days
                        sev = 'warning' if days_left > 7 else 'critical'
                        alerts.append({
                            'type': 'fuel_expiry', 'severity': sev,
                            'title': f'{f["fuel_type"]} expiring soon',
                            'message': f'{f["quantity"]} {f["unit"]} of {f["fuel_type"]} expires in {days_left} days ({f["expires"]}). Use, rotate, or add stabilizer to extend shelf life.',
                        })
                except Exception as exc:
                    log.debug('Alert engine skipped fuel expiry check: %s', exc)

                # 8. High cumulative radiation dose
                try:
                    rad_row = db.execute('SELECT MAX(cumulative_rem) as max_rem FROM radiation_log').fetchone()
                    if rad_row and rad_row['max_rem'] and rad_row['max_rem'] >= 25:
                        sev = 'critical' if rad_row['max_rem'] >= 75 else 'warning'
                        alerts.append({
                            'type': 'radiation', 'severity': sev,
                            'title': f'Cumulative radiation dose: {round(rad_row["max_rem"], 1)} rem',
                            'message': f'Cumulative radiation exposure has reached {round(rad_row["max_rem"], 1)} rem. {">75 rem: Acute Radiation Syndrome risk." if rad_row["max_rem"] >= 75 else "25-75 rem: Increased cancer risk. Minimize further exposure. Take KI if thyroid threat."} Seek shelter with highest available Protection Factor.',
                        })
                except Exception as exc:
                    log.debug('Alert engine skipped radiation check: %s', exc)

                # Deduplicate against existing active alerts (don't re-create dismissed ones within 24h)
                # Reuse the same connection for writes to avoid opening 2 more connections per cycle
                if alerts:
                    for alert in alerts:
                        existing = db.execute(
                            "SELECT id, dismissed FROM alerts WHERE alert_type = ? AND title = ? AND created_at >= ? ORDER BY created_at DESC LIMIT 1",
                            (alert['type'], alert['title'], (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'))
                        ).fetchone()
                        if not existing:
                            db.execute(
                                'INSERT INTO alerts (alert_type, severity, title, message) VALUES (?, ?, ?, ?)',
                                (alert['type'], alert['severity'], alert['title'], alert['message'])
                            )
                    db.commit()
                    broadcast_event('alert_check', {'event': 'new_alerts'})

                # Prune old dismissed alerts (>7 days)
                db.execute("DELETE FROM alerts WHERE dismissed = 1 AND created_at < ?",
                           ((now - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S'),))
                db.commit()

            except Exception as e:
                log.error(f'Alert engine error: {e}')
            finally:
                _close_db_safely(db, 'alert engine')
            # Check every 5 minutes; Event.wait returns True if stop was signalled.
            if _alert_stop_event.wait(timeout=300):
                return
    finally:
        _state.set_alert_check_running(False)


def start_alert_engine():
    """Start the background alert engine thread."""
    threading.Thread(target=_run_alert_checks, daemon=True).start()


@preparedness_bp.route('/api/alerts')
def api_alerts():
    """Get active (non-dismissed) alerts."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM alerts WHERE dismissed = 0 ORDER BY severity DESC, created_at DESC LIMIT 50').fetchall()
    return jsonify([dict(r) for r in rows])

@preparedness_bp.route('/api/alerts/<int:alert_id>/dismiss', methods=['POST'])
def api_alert_dismiss(alert_id):
    with db_session() as db:
        db.execute('UPDATE alerts SET dismissed = 1 WHERE id = ?', (alert_id,))
        db.commit()
    broadcast_event('alert_check', {'event': 'dismissed', 'alert_id': alert_id})
    broadcast_event('alert', {'level': 'info', 'message': f'Alert {alert_id} dismissed'})
    return jsonify({'status': 'dismissed'})

@preparedness_bp.route('/api/alerts/dismiss-all', methods=['POST'])
def api_alerts_dismiss_all():
    with db_session() as db:
        db.execute('UPDATE alerts SET dismissed = 1 WHERE dismissed = 0')
        db.commit()
    broadcast_event('alert_check', {'event': 'dismissed_all'})
    return jsonify({'status': 'dismissed'})

@preparedness_bp.route('/api/alerts/stream')
def api_alerts_stream():
    """Deprecated: Use /api/events/stream instead. Kept for backward compat."""
    # Re-implement SSE stream for backward compatibility
    q = queue.Queue(maxsize=50)
    if not sse_register_client(q):
        return jsonify({'error': 'Too many SSE connections'}), 429
    def generate():
        try:
            yield ": connected\n\n"
            while True:
                try:
                    msg = q.get(timeout=30)
                    from web.state import sse_touch_client as _touch
                    _touch(q)
                    yield msg
                except queue.Empty:
                    from web.state import sse_touch_client as _touch
                    _touch(q)
                    yield ": keepalive\n\n"
        finally:
            sse_unregister_client(q)
    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@preparedness_bp.route('/api/alerts/generate-summary', methods=['POST'])
def api_alerts_generate_summary():
    """Use AI to generate a natural language situation summary from active alerts."""
    with db_session() as db:
        alerts = db.execute('SELECT * FROM alerts WHERE dismissed = 0 ORDER BY severity DESC').fetchall()
    if not alerts:
        return jsonify({'summary': 'All clear. No active alerts.'})
    # Build a concise prompt for Ollama
    alert_text = '\n'.join([f'- [{a["severity"].upper()}] {a["title"]}: {a["message"]}' for a in alerts])
    prompt = f'You are a survival operations officer. Summarize these alerts into a brief, actionable situation report (3-5 sentences max). Be direct and practical.\n\nActive Alerts:\n{alert_text}'
    try:
        if not ollama.running():
            return jsonify({'summary': f'{len(alerts)} active alert(s). Start the AI service for an intelligent situation summary.'})
        models = ollama.list_models()
        if not models:
            return jsonify({'summary': f'{len(alerts)} active alert(s). Download an AI model for intelligent summaries.'})
        model = models[0]['name']
        import requests as req
        resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                       json={'model': model, 'prompt': prompt, 'stream': False},
                       timeout=30)
        resp.raise_for_status()
        result = _safe_response_json(resp, {})
        summary = str(result.get('response', '') or '').strip()
        if not summary:
            raise ValueError('Malformed alert summary payload')
        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'summary': f'{len(alerts)} active alert(s). AI summary unavailable: {e}'})


# ─── Livestock API ───────────────────────────────────────────────────

@preparedness_bp.route('/api/livestock')
def api_livestock_list():
    LIVESTOCK_SORT_FIELDS = {'name', 'species', 'breed', 'status', 'created_at', 'updated_at'}
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    sort_by = request.args.get('sort_by', 'species')
    sort_dir = 'DESC' if request.args.get('sort_dir', 'asc').lower() == 'desc' else 'ASC'
    if sort_by not in LIVESTOCK_SORT_FIELDS:
        sort_by = 'species'
    with db_session() as db:
        rows = db.execute(f'SELECT * FROM livestock ORDER BY {sort_by} {sort_dir}, name ASC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([{**dict(r), 'health_log': _safe_json_list(r['health_log']),
                     'vaccinations': _safe_json_list(r['vaccinations'])} for r in rows])

@preparedness_bp.route('/api/livestock', methods=['POST'])
def api_livestock_create():
    data = request.get_json() or {}
    if len(data.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    if len(data.get('species', '') or '') > 200:
        return jsonify({'error': 'species too long (max 200)'}), 400
    if not data.get('species'):
        return jsonify({'error': 'Species required'}), 400
    with db_session() as db:
        cur = db.execute('INSERT INTO livestock (species, name, tag, dob, sex, weight_lbs, notes) VALUES (?,?,?,?,?,?,?)',
                   (data['species'], data.get('name', ''), data.get('tag', ''), data.get('dob', ''),
                    data.get('sex', ''), data.get('weight_lbs'), data.get('notes', '')))
        db.commit()
        lid = cur.lastrowid
    return jsonify({'status': 'created', 'id': lid}), 201

@preparedness_bp.route('/api/livestock/<int:lid>', methods=['PUT'])
def api_livestock_update(lid):
    data = request.get_json() or {}
    if len(data.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    if len(data.get('species', '') or '') > 200:
        return jsonify({'error': 'species too long (max 200)'}), 400
    field_map = {
        'species': lambda d: d['species'],
        'name': lambda d: d['name'],
        'tag': lambda d: d['tag'],
        'dob': lambda d: d['dob'],
        'sex': lambda d: d['sex'],
        'weight_lbs': lambda d: d['weight_lbs'],
        'status': lambda d: d['status'],
        'health_log': lambda d: json.dumps(_safe_json_list(d['health_log'], [])),
        'vaccinations': lambda d: json.dumps(_safe_json_list(d['vaccinations'], [])),
        'notes': lambda d: d['notes'],
    }
    sets = []
    vals = []
    for col, fn in field_map.items():
        if col in data:
            sets.append(f'{col}=?')
            vals.append(fn(data))
    if not sets:
        return jsonify({'status': 'no changes'})
    sets.append('updated_at=CURRENT_TIMESTAMP')
    vals.append(lid)
    with db_session() as db:
        r = db.execute(f'UPDATE livestock SET {", ".join(sets)} WHERE id=?', tuple(vals))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'updated'})

@preparedness_bp.route('/api/livestock/<int:lid>', methods=['DELETE'])
def api_livestock_delete(lid):
    with db_session() as db:
        r = db.execute('DELETE FROM livestock WHERE id = ?', (lid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})

@preparedness_bp.route('/api/livestock/bulk-delete', methods=['POST'])
@require_auth('admin')
def api_livestock_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as db:
        placeholders = ','.join('?' * len(ids))
        r = db.execute(f'DELETE FROM livestock WHERE id IN ({placeholders})', ids)
        db.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})

@preparedness_bp.route('/api/livestock/<int:lid>/health', methods=['POST'])
def api_livestock_health_event(lid):
    """Add a health event to an animal's log."""
    data = request.get_json() or {}
    with db_session() as db:
        animal = db.execute('SELECT health_log FROM livestock WHERE id = ?', (lid,)).fetchone()
        if not animal:
            return jsonify({'error': 'Not found'}), 404
        log_entries = _safe_json_list(animal['health_log'], [])
        log_entries.append({'date': time.strftime('%Y-%m-%d'), 'event': data.get('event', ''), 'notes': data.get('notes', '')})
        db.execute('UPDATE livestock SET health_log = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                   (json.dumps(log_entries), lid))
        db.commit()
        return jsonify({'status': 'logged'}), 201


# ─── Scenario Training Engine ───────────────────────────────────────

def _calculate_scenario_score(decisions, scenario_type, duration_sec=None):
    """Calculate structured scenario score with category breakdown."""
    score = 0
    breakdown = {}

    # Decision quality (40 points max)
    decision_count = len(decisions) if isinstance(decisions, list) else 0
    breakdown['decisions'] = min(40, decision_count * 8)
    score += breakdown['decisions']

    # Speed (20 points max) - faster is better
    if duration_sec and duration_sec > 0:
        if duration_sec < 300: breakdown['speed'] = 20       # Under 5 min
        elif duration_sec < 600: breakdown['speed'] = 15     # Under 10 min
        elif duration_sec < 900: breakdown['speed'] = 10     # Under 15 min
        else: breakdown['speed'] = 5
    else:
        breakdown['speed'] = 10  # No timer, middle score
    score += breakdown['speed']

    # Completeness (20 points) - did all phases get addressed
    breakdown['completeness'] = min(20, decision_count * 5)
    score += breakdown['completeness']

    # Base score (20 points) - just for attempting
    breakdown['participation'] = 20
    score += breakdown['participation']

    return min(100, score), breakdown

@preparedness_bp.route('/api/scenarios')
def api_scenarios_list():
    try:
        limit = min(int(request.args.get('limit', 20)), 200)
    except (ValueError, TypeError):
        limit = 20
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM scenarios ORDER BY started_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([{**dict(r), 'decisions': _safe_json_list(r['decisions']),
                     'complications': _safe_json_list(r['complications'])} for r in rows])

@preparedness_bp.route('/api/scenarios', methods=['POST'])
def api_scenarios_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute('INSERT INTO scenarios (scenario_type, title) VALUES (?, ?)',
                         (data.get('type', ''), data.get('title', '')))
        db.commit()
        sid = cur.lastrowid
    return jsonify({'id': sid}), 201

@preparedness_bp.route('/api/scenarios/<int:sid>', methods=['PUT'])
def api_scenarios_update(sid):
    data = request.get_json() or {}
    decisions = _safe_json_list(data.get('decisions', []), [])
    complications = _safe_json_list(data.get('complications', []), [])
    with db_session() as db:
        r = db.execute('UPDATE scenarios SET current_phase=?, status=?, decisions=?, complications=?, score=?, aar_text=?, completed_at=? WHERE id=?',
                   (data.get('current_phase', 0), data.get('status', 'active'),
                    json.dumps(decisions), json.dumps(complications),
                    data.get('score', 0), data.get('aar_text', ''), data.get('completed_at', ''), sid))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'updated'})

@preparedness_bp.route('/api/scenarios/<int:sid>/complication', methods=['POST'])
def api_scenario_complication(sid):
    """AI generates a context-aware complication based on current scenario state + user's real data."""
    data = request.get_json() or {}
    phase_desc = data.get('phase_description', '')
    decisions_so_far = _safe_json_list(data.get('decisions', []), [])

    # Gather real situation context
    with db_session() as db:
        inv_items = db.execute('SELECT name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY (quantity/daily_usage) LIMIT 5').fetchall()
        contacts_count = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
        sit_raw = db.execute("SELECT value FROM settings WHERE key='sit_board'").fetchone()

    inv_str = ', '.join(f"{r['name']}: {r['quantity']} {r['unit']}" for r in inv_items) or 'unknown'
    context = f"Inventory: {inv_str}\n"
    context += f"Group size: {contacts_count} contacts\n"
    sit = _safe_json_value(sit_raw['value'] if sit_raw else None, {})
    if sit:
        context += f"Situation: {', '.join(f'{k}={v}' for k,v in sit.items())}\n"

    prompt = f"""You are a survival training instructor running a disaster scenario. Generate ONE realistic complication for the current phase of the scenario. The complication should force a difficult decision.

Scenario phase: {phase_desc}
Decisions made so far: {', '.join(d.get('label','') for d in decisions_so_far[-3:] if isinstance(d, dict)) if decisions_so_far else 'none yet'}
Real situation data: {context}

Respond with ONLY a JSON object (no markdown, no explanation):
{{"title": "short complication title", "description": "2-3 sentence description of the complication", "choices": ["choice A text", "choice B text", "choice C text"]}}"""

    try:
        if not ollama.running():
            return jsonify({'title': 'Equipment Failure', 'description': 'Your primary water filter has cracked. You need to switch to backup purification methods.',
                            'choices': ['Use bleach purification', 'Boil all water', 'Ration existing clean water']})
        models = ollama.list_models()
        if not models:
            return jsonify({'title': 'Supply Shortage', 'description': 'You discover your food supply is 30% less than expected. Some items were damaged.',
                            'choices': ['Implement strict rationing', 'Forage for supplemental food', 'Send a team to resupply']})
        import requests as req
        resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                       json={'model': models[0]['name'], 'prompt': prompt, 'stream': False, 'format': 'json'}, timeout=30)
        resp.raise_for_status()
        result = _safe_response_json(resp, {}).get('response', '{}')
        complication = _safe_json_value(result, {})
        choices = [str(choice).strip() for choice in _safe_json_list(complication.get('choices'), []) if str(choice or '').strip()]
        if not isinstance(complication, dict) or not str(complication.get('title', '') or '').strip() or not str(complication.get('description', '') or '').strip() or len(choices) < 2:
            raise ValueError('Malformed complication payload')
        complication = {
            'title': str(complication.get('title', '')).strip(),
            'description': str(complication.get('description', '')).strip(),
            'choices': choices[:3],
        }
        return jsonify(complication)
    except Exception as e:
        log.error(f'Complication generation failed: {e}')
        return jsonify({'title': 'Unexpected Event', 'description': 'Weather conditions have changed rapidly. High winds are approaching your position.',
                        'choices': ['Shelter in place', 'Relocate to secondary position', 'Reinforce current shelter']})

@preparedness_bp.route('/api/scenarios/<int:sid>/aar', methods=['POST'])
def api_scenario_aar(sid):
    """AI generates an After-Action Review scoring the user's decisions."""
    with db_session() as db:
        scenario = db.execute('SELECT * FROM scenarios WHERE id = ?', (sid,)).fetchone()
    if not scenario:
        return jsonify({'error': 'Not found'}), 404

    decisions = _safe_json_list(scenario['decisions'], [])
    complications = _safe_json_list(scenario['complications'], [])

    decision_summary = '\n'.join([f"Phase {d.get('phase',0)+1}: {d.get('label','')} (chose: {d.get('choice','')})" for d in decisions if isinstance(d, dict)])
    complication_summary = '\n'.join([f"- {c.get('title','')}: chose {c.get('response','')}" for c in complications if isinstance(c, dict)])

    prompt = f"""You are a survival training evaluator. Score this scenario performance and write a brief After-Action Review.

Scenario: {scenario['title']}
Decisions made:
{decision_summary or 'None recorded'}

Complications encountered and responses:
{complication_summary or 'None'}

Provide:
1. An overall score 0-100
2. A 3-5 sentence assessment of strengths and weaknesses
3. 2-3 specific improvement recommendations

Respond as plain text, not JSON. Start with "Score: XX/100" on the first line."""

    scenario_type = scenario['scenario_type'] if scenario else ''

    try:
        _models = ollama.list_models() if ollama.running() else []
        if not _models:
            score, breakdown = _calculate_scenario_score(decisions, scenario_type)
            # Record skill progression
            with db_session() as db:
                db.execute('INSERT INTO skill_progression (skill_tag, score, scenario_type, drill_type) VALUES (?, ?, ?, ?)',
                           (scenario_type or 'general', score, scenario_type, None))
                db.commit()
            return jsonify({'score': score, 'breakdown': breakdown, 'aar': f'Score: {score}/100\n\nCompleted {len(decisions)} phases with {len(complications)} complications handled. Practice regularly to improve response times and decision quality.'})
        import requests as req
        resp = req.post(f'http://localhost:{ollama.OLLAMA_PORT}/api/generate',
                       json={'model': _models[0]['name'], 'prompt': prompt, 'stream': False}, timeout=45)
        resp.raise_for_status()
        aar_text = str(_safe_response_json(resp, {}).get('response', '') or '').strip()
        # Try to extract score
        score = 50
        import re
        score_match = re.search(r'Score:\s*(\d+)', aar_text)
        if score_match:
            score = min(100, max(0, int(score_match.group(1))))
        # Record skill progression
        with db_session() as db:
            db.execute('INSERT INTO skill_progression (skill_tag, score, scenario_type, drill_type) VALUES (?, ?, ?, ?)',
                       (scenario_type or 'general', score, scenario_type, None))
            db.commit()
        return jsonify({'score': score, 'aar': aar_text})
    except Exception as e:
        score, breakdown = _calculate_scenario_score(decisions, scenario_type)
        # Record skill progression
        try:
            with db_session() as db:
                db.execute('INSERT INTO skill_progression (skill_tag, score, scenario_type, drill_type) VALUES (?, ?, ?, ?)',
                           (scenario_type or 'general', score, scenario_type, None))
                db.commit()
        except Exception:
            pass
        return jsonify({'score': score, 'breakdown': breakdown, 'aar': f'Score: {score}/100\n\nAI review unavailable. Completed {len(decisions)} decision phases. Review your choices and consider alternative approaches for future training.'})


# ─── Drill History ───────────────────────────────────────────────────

@preparedness_bp.route('/api/drills/history')
def api_drill_history():
    with db_session() as db:
        rows = db.execute('SELECT * FROM drill_history ORDER BY created_at DESC LIMIT 50').fetchall()
    return jsonify([dict(r) for r in rows])

@preparedness_bp.route('/api/drills/history', methods=['POST'])
def api_drill_history_save():
    data, error = _require_json_body(request)
    if error:
        return error
    if len(data.get('drill_type', '') or '') > 200:
        return jsonify({'error': 'drill_type too long'}), 400
    if len(data.get('title', '') or '') > 200:
        return jsonify({'error': 'title too long'}), 400
    try:
        drill_type = data.get('drill_type', '')
        tasks_total = int(data.get('tasks_total', 0))
        tasks_completed = int(data.get('tasks_completed', 0))
        duration_sec = int(data.get('duration_sec', 0))
        with db_session() as db:
            db.execute('INSERT INTO drill_history (drill_type, title, duration_sec, tasks_total, tasks_completed, notes) VALUES (?, ?, ?, ?, ?, ?)',
                       (drill_type, data.get('title', ''), duration_sec,
                        tasks_total, tasks_completed, data.get('notes', '')))
            # Record skill progression for drill completion
            drill_score = round((tasks_completed / max(tasks_total, 1)) * 100) if tasks_total > 0 else 50
            db.execute('INSERT INTO skill_progression (skill_tag, score, scenario_type, drill_type) VALUES (?, ?, ?, ?)',
                       (drill_type or 'general_drill', drill_score, None, drill_type))
            db.commit()
        return jsonify({'status': 'saved'}), 201
    except Exception as e:
        log.error('Request failed: %s', e)
        return jsonify({'error': 'Internal server error'}), 500


# ─── Skill Progression Tracking ─────────────────────────────────────

@preparedness_bp.route('/api/training/progression', methods=['GET'])
def api_training_progression():
    """Get skill progression data with trends."""
    with db_session() as db:
        rows = db.execute("""
            SELECT skill_tag, scenario_type, score, recorded_at
            FROM skill_progression
            ORDER BY recorded_at DESC
            LIMIT 200
        """).fetchall()

        # Group by skill_tag, compute trend
        from collections import defaultdict as _defaultdict
        by_skill = _defaultdict(list)
        for r in rows:
            by_skill[r['skill_tag']].append({
                'score': r['score'],
                'date': r['recorded_at'],
                'type': r['scenario_type']
            })

        result = []
        for skill, entries in by_skill.items():
            scores = [e['score'] for e in entries if e['score'] is not None]
            if len(scores) >= 2:
                trend = 'improving' if scores[0] > scores[-1] else 'declining'
            else:
                trend = 'stable'
            result.append({
                'skill': skill,
                'latest_score': scores[0] if scores else None,
                'avg_score': round(sum(scores) / len(scores)) if scores else None,
                'attempts': len(entries),
                'trend': trend,
                'history': entries[:10]
            })
        return jsonify(sorted(result, key=lambda x: x.get('avg_score') or 0))


# ─── Predictive Alerts ──────────────────────────────────────────────

@preparedness_bp.route('/api/alerts/predictive')
def api_alerts_predictive():
    """Analyze trends and return predictions: burn rates, fuel expiry, equipment overdue, medication schedules."""
    alerts = []
    today = datetime.now()
    today_str = today.strftime('%Y-%m-%d')
    with db_session() as db:

        # 1. Inventory burn rate — items that will run out
        burn_rows = db.execute('SELECT id, name, category, quantity, unit, daily_usage, expiration FROM inventory WHERE daily_usage > 0 LIMIT 200').fetchall()
        for r in burn_rows:
            days_left = r['quantity'] / r['daily_usage'] if r['daily_usage'] > 0 else float('inf')
            if days_left <= 30:
                severity = 'critical' if days_left <= 7 else 'warning'
                alerts.append({
                    'type': 'inventory_depletion',
                    'severity': severity,
                    'title': f'{r["name"]} running low',
                    'message': f'{r["quantity"]} {r["unit"]} remaining at {r["daily_usage"]}/day — ~{round(days_left, 1)} days left',
                    'item_id': r['id'],
                    'days_remaining': round(days_left, 1),
                    'category': r['category'],
                })

        # 2. Inventory expiration
        exp_rows = db.execute("SELECT id, name, category, quantity, unit, expiration FROM inventory WHERE expiration != '' AND expiration IS NOT NULL LIMIT 200").fetchall()
        for r in exp_rows:
            try:
                exp_date = datetime.strptime(r['expiration'], '%Y-%m-%d')
                days_until = (exp_date - today).days
                if days_until <= 90:
                    if days_until < 0:
                        severity = 'critical'
                        msg = f'Expired {abs(days_until)} days ago'
                    elif days_until <= 14:
                        severity = 'critical'
                        msg = f'Expires in {days_until} days'
                    else:
                        severity = 'warning'
                        msg = f'Expires in {days_until} days'
                    alerts.append({
                        'type': 'inventory_expiration',
                        'severity': severity,
                        'title': f'{r["name"]} expiring',
                        'message': f'{msg} ({r["expiration"]})',
                        'item_id': r['id'],
                        'days_until_expiry': days_until,
                        'category': r['category'],
                    })
            except (ValueError, TypeError):
                pass

        # 3. Fuel expiry
        fuel_rows = db.execute("SELECT id, fuel_type, quantity, unit, expires FROM fuel_storage WHERE expires != '' AND expires IS NOT NULL LIMIT 100").fetchall()
        for r in fuel_rows:
            try:
                exp_date = datetime.strptime(r['expires'], '%Y-%m-%d')
                days_until = (exp_date - today).days
                if days_until <= 90:
                    severity = 'critical' if days_until <= 14 else 'warning'
                    alerts.append({
                        'type': 'fuel_expiry',
                        'severity': severity,
                        'title': f'{r["fuel_type"]} fuel expiring',
                        'message': f'{r["quantity"]} {r["unit"]} expires in {days_until} days ({r["expires"]})',
                        'item_id': r['id'],
                        'days_until_expiry': days_until,
                    })
            except (ValueError, TypeError):
                pass

        # 4. Equipment maintenance overdue
        equip_rows = db.execute("SELECT id, name, category, next_service, status FROM equipment_log WHERE next_service != '' AND next_service IS NOT NULL LIMIT 100").fetchall()
        for r in equip_rows:
            try:
                svc_date = datetime.strptime(r['next_service'], '%Y-%m-%d')
                days_until = (svc_date - today).days
                if days_until <= 14:
                    severity = 'critical' if days_until < 0 else 'warning'
                    if days_until < 0:
                        msg = f'Maintenance overdue by {abs(days_until)} days'
                    else:
                        msg = f'Maintenance due in {days_until} days'
                    alerts.append({
                        'type': 'equipment_maintenance',
                        'severity': severity,
                        'title': f'{r["name"]} maintenance {"overdue" if days_until < 0 else "due"}',
                        'message': msg,
                        'item_id': r['id'],
                        'days_until_service': days_until,
                    })
            except (ValueError, TypeError):
                pass

        # 5. Scheduled tasks overdue
        task_rows = db.execute("SELECT id, name, category, next_due, assigned_to FROM scheduled_tasks WHERE next_due IS NOT NULL AND next_due <= ?",
                               (today.strftime('%Y-%m-%d %H:%M:%S'),)).fetchall()
        for r in task_rows:
            alerts.append({
                'type': 'task_overdue',
                'severity': 'warning',
                'title': f'Task overdue: {r["name"]}',
                'message': f'Category: {r["category"]}, Assigned to: {r["assigned_to"] or "unassigned"}',
                'item_id': r['id'],
                'category': r['category'],
            })

    # Optional filters
    filter_type = request.args.get('type', '').strip()
    filter_severity = request.args.get('severity', '').strip().lower()
    if filter_type:
        alerts = [a for a in alerts if a['type'] == filter_type]
    if filter_severity in ('critical', 'warning'):
        alerts = [a for a in alerts if a['severity'] == filter_severity]

    # Sort: critical first, then warning
    alerts.sort(key=lambda a: (0 if a['severity'] == 'critical' else 1, a.get('days_remaining', a.get('days_until_expiry', a.get('days_until_service', 999)))))
    return jsonify({'alerts': alerts, 'count': len(alerts), 'generated_at': today.strftime('%Y-%m-%d %H:%M:%S')})
