"""Scheduled reports — automated SITREP generation, report history, and delivery."""

import json
import logging
import threading
import time
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, current_app
from db import db_session, log_activity

scheduled_reports_bp = Blueprint('scheduled_reports', __name__)
_log = logging.getLogger('nomad.scheduled_reports')

_report_thread = None
_report_stop = threading.Event()


# ─── Report history (CRUD) ───────────────────────────────────────

@scheduled_reports_bp.route('/api/reports')
def api_reports_list():
    try:
        limit = min(max(1, int(request.args.get('limit', 20))), 100)
        offset = max(0, int(request.args.get('offset', 0)))
    except (TypeError, ValueError):
        limit, offset = 20, 0
    report_type = request.args.get('type', '')

    with db_session() as db:
        if report_type:
            rows = db.execute(
                'SELECT id, report_type, title, generated_at, model, status, word_count '
                'FROM scheduled_reports WHERE report_type = ? '
                'ORDER BY generated_at DESC LIMIT ? OFFSET ?',
                (report_type, limit, offset)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT id, report_type, title, generated_at, model, status, word_count '
                'FROM scheduled_reports ORDER BY generated_at DESC LIMIT ? OFFSET ?',
                (limit, offset)
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@scheduled_reports_bp.route('/api/reports/<int:report_id>')
def api_report_detail(report_id):
    with db_session() as db:
        row = db.execute('SELECT * FROM scheduled_reports WHERE id = ?', (report_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Report not found'}), 404
    return jsonify(dict(row))


@scheduled_reports_bp.route('/api/reports/<int:report_id>', methods=['DELETE'])
def api_report_delete(report_id):
    with db_session() as db:
        r = db.execute('DELETE FROM scheduled_reports WHERE id = ?', (report_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Report not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Generate on demand ──────────────────────────────────────────

@scheduled_reports_bp.route('/api/reports/generate', methods=['POST'])
def api_report_generate():
    """Generate a SITREP now and save to history."""
    data = request.get_json() or {}
    report_type = data.get('type', 'sitrep')

    if report_type != 'sitrep':
        return jsonify({'error': 'Only sitrep type supported'}), 400

    report_id = _generate_sitrep(
        model=data.get('model', ''),
        trigger='manual',
    )
    if report_id:
        return jsonify({'status': 'generated', 'report_id': report_id}), 201
    return jsonify({'error': 'Generation failed — AI service may not be running'}), 503


# ─── Schedule config ─────────────────────────────────────────────

@scheduled_reports_bp.route('/api/reports/schedule')
def api_report_schedule():
    with db_session() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'report_schedule'"
        ).fetchone()
    if not row:
        return jsonify(_default_schedule())
    try:
        return jsonify(json.loads(row['value']))
    except (json.JSONDecodeError, TypeError):
        return jsonify(_default_schedule())


@scheduled_reports_bp.route('/api/reports/schedule', methods=['POST'])
def api_report_schedule_save():
    data = request.get_json() or {}
    schedule = {
        'enabled': bool(data.get('enabled', False)),
        'model': data.get('model', ''),
        'last_run': data.get('last_run', ''),
    }
    try:
        schedule['interval_hours'] = max(1, min(168, int(data.get('interval_hours', 24))))
    except (TypeError, ValueError):
        return jsonify({'error': 'interval_hours must be an integer between 1 and 168'}), 400
    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('report_schedule', ?)",
            (json.dumps(schedule),)
        )
        db.commit()

    # Restart the scheduler thread if config changed
    _ensure_scheduler()

    log_activity('report_schedule_updated',
                 detail=f"{'Enabled' if schedule['enabled'] else 'Disabled'}, every {schedule['interval_hours']}h")
    return jsonify({'status': 'saved', **schedule})


@scheduled_reports_bp.route('/api/reports/summary')
def api_report_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM scheduled_reports').fetchone()['c']
        latest = db.execute(
            'SELECT id, title, generated_at, status FROM scheduled_reports ORDER BY generated_at DESC LIMIT 1'
        ).fetchone()
    return jsonify({
        'total_reports': total,
        'latest': dict(latest) if latest else None,
    })


# ─── Background scheduler ────────────────────────────────────────

def _default_schedule():
    return {
        'enabled': False,
        'interval_hours': 24,
        'model': '',
        'last_run': '',
    }


def _get_schedule():
    try:
        with db_session() as db:
            row = db.execute(
                "SELECT value FROM settings WHERE key = 'report_schedule'"
            ).fetchone()
        if row:
            return json.loads(row['value'])
    except Exception:
        _log.warning('Failed to read report schedule from DB; using defaults', exc_info=True)
    return _default_schedule()


def _ensure_scheduler():
    global _report_thread
    if _report_thread and _report_thread.is_alive():
        return
    _report_stop.clear()
    _report_thread = threading.Thread(target=_scheduler_loop, daemon=True, name='report-scheduler')
    _report_thread.start()
    _log.info('Report scheduler thread started')


def _scheduler_loop():
    """Check every 5 minutes if a scheduled report is due."""
    while not _report_stop.is_set():
        try:
            schedule = _get_schedule()
            if schedule.get('enabled'):
                last_run = schedule.get('last_run', '')
                interval_h = schedule.get('interval_hours', 24)

                should_run = False
                if not last_run:
                    should_run = True
                else:
                    try:
                        last_dt = datetime.fromisoformat(last_run.replace('Z', '+00:00'))
                        elapsed_h = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                        if elapsed_h >= interval_h:
                            should_run = True
                    except (ValueError, TypeError):
                        should_run = True

                if should_run:
                    _log.info('Scheduled SITREP due — generating...')
                    report_id = _generate_sitrep(
                        model=schedule.get('model', ''),
                        trigger='scheduled',
                    )
                    if report_id:
                        # Update last_run timestamp
                        schedule['last_run'] = datetime.now(timezone.utc).isoformat()
                        with db_session() as db:
                            db.execute(
                                "INSERT OR REPLACE INTO settings (key, value) VALUES ('report_schedule', ?)",
                                (json.dumps(schedule),)
                            )
                            db.commit()

        except Exception:
            _log.exception('Scheduler loop error')

        _report_stop.wait(300)  # Check every 5 minutes


def stop_scheduler():
    _report_stop.set()


# ─── SITREP generator (reuses ai.py logic without HTTP) ──────────

def _generate_sitrep(model='', trigger='manual'):
    """Generate a SITREP and save to scheduled_reports table.
    Returns report ID on success, None on failure."""
    try:
        from services import ollama as ollama_svc
        if not ollama_svc.running():
            _log.warning('Cannot generate SITREP — AI service not running')
            return None

        if not model:
            model = ollama_svc.DEFAULT_MODEL

        # Build context (same logic as ai.py api_ai_sitrep)
        with db_session() as db:
            ctx_parts = _build_sitrep_context(db)

        context = '\n\n'.join(ctx_parts) if ctx_parts else 'No operational data recorded yet.'
        now_str = datetime.now(timezone.utc).strftime('%d %b %Y %H%M')

        system_prompt = f"""You are a military-style intelligence officer generating a SITREP (Situation Report) for a preparedness and field-operations workspace called NOMAD Field Desk.

Generate a formatted SITREP in markdown using this exact structure:

# SITREP — {now_str}Z

## 1. SITUATION
(Overall assessment — 2-3 sentences summarizing current conditions)

## 2. SUPPLY STATUS
(Inventory highlights, low stock, expired items — use exact numbers from data)

## 3. PERSONNEL & MEDICAL
(Team count, any medical alerts, patient status)

## 4. INFRASTRUCTURE
(Power, weather, comms status)

## 5. INCIDENTS & ALERTS
(Any incidents in last 24h, active alerts)

## 6. RECOMMENDED ACTIONS
(3-5 prioritized actionable items based on the data — be specific)

RULES:
- Use ONLY the data provided below. Never fabricate information.
- Use exact quantities and names from the data.
- If a section has no relevant data, write "No data available."
- Be concise, direct, military-style briefing tone.

--- OPERATIONAL DATA ---
{context}
--- END DATA ---"""

        result = ollama_svc.chat(model, [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': 'Generate the daily SITREP.'}
        ], stream=False)

        sitrep_text = result.get('message', {}).get('content', '') if isinstance(result, dict) else ''
        if not sitrep_text:
            return None

        title = f'SITREP — {now_str}Z'
        word_count = len(sitrep_text.split())

        with db_session() as db:
            cur = db.execute('''
                INSERT INTO scheduled_reports
                (report_type, title, content, context_snapshot, model, trigger, status, word_count)
                VALUES (?,?,?,?,?,?,?,?)
            ''', ('sitrep', title, sitrep_text.strip(), context[:5000], model, trigger, 'complete', word_count))
            report_id = cur.lastrowid
            db.commit()

        log_activity('sitrep_generated', 'ai', f'{trigger.title()} SITREP generated ({word_count} words)')
        _log.info('SITREP generated: id=%d, %d words, trigger=%s', report_id, word_count, trigger)
        return report_id

    except Exception:
        _log.exception('SITREP generation failed')
        # Save failed report for visibility
        try:
            with db_session() as db:
                db.execute('''
                    INSERT INTO scheduled_reports
                    (report_type, title, content, model, trigger, status, word_count)
                    VALUES (?,?,?,?,?,?,?)
                ''', ('sitrep', f'SITREP — FAILED', 'Generation failed', model, trigger, 'failed', 0))
                db.commit()
        except Exception:
            _log.warning('Failed to save failure record for SITREP generation', exc_info=True)
        return None


def _build_sitrep_context(db):
    """Build context sections for SITREP — mirrors ai.py logic.

    NOTE (v7.65.1+): this function existed as orphan dead code inside
    `_generate_sitrep` after `return None` for an unknown number of
    versions. The `def` line had been lost, leaving the body unreachable
    at indent=4 of the parent function, while line 239's call site
    NameError'd into the broad `except Exception:` and returned None.
    Net effect: every manual + scheduled SITREP returned 503 'AI service
    may not be running' regardless of ollama state. Restored as a
    proper module-level def. Surfaced by V8-06 test authoring.
    """
    parts = []

    # Activity log (24h)
    activity = db.execute(
        "SELECT event, service, detail, level FROM activity_log "
        "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    if activity:
        lines = [f'[{a["level"]}] {a["event"]}' + (f' — {a["detail"][:80]}' if a["detail"] else '')
                 for a in activity]
        parts.append('ACTIVITY LOG (24h):\n' + '\n'.join(lines))

    # Low stock
    low = db.execute(
        'SELECT name, quantity, unit, category, min_quantity FROM inventory '
        'WHERE quantity <= min_quantity AND min_quantity > 0 ORDER BY category LIMIT 50'
    ).fetchall()
    if low:
        parts.append('LOW STOCK ALERTS:\n' + '\n'.join(
            f'  {r["name"]} ({r["category"]}): {r["quantity"]} {r["unit"]} (min: {r["min_quantity"]})'
            for r in low))

    # Expired
    expired = db.execute(
        "SELECT name, quantity, unit, expiration FROM inventory "
        "WHERE expiration != '' AND expiration <= date('now') ORDER BY expiration LIMIT 50"
    ).fetchall()
    if expired:
        parts.append('EXPIRED ITEMS:\n' + '\n'.join(
            f'  {r["name"]}: {r["quantity"]} {r["unit"]} (expired {r["expiration"]})' for r in expired))

    # Incidents (24h)
    incidents = db.execute(
        "SELECT severity, category, description FROM incidents "
        "WHERE created_at >= datetime('now', '-24 hours') ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    if incidents:
        parts.append('INCIDENTS (24h):\n' + '\n'.join(
            f'  [{r["severity"]}] {r["category"]}: {r["description"][:100]}' for r in incidents))

    # Active alerts
    alerts = db.execute(
        'SELECT title, severity, message FROM alerts WHERE dismissed = 0 ORDER BY severity DESC LIMIT 10'
    ).fetchall()
    if alerts:
        parts.append('ACTIVE ALERTS:\n' + '\n'.join(
            f'  [{a["severity"]}] {a["title"]}: {a["message"][:100]}' for a in alerts))

    # Inventory summary
    inv = db.execute(
        'SELECT category, COUNT(*) as cnt, SUM(quantity) as total FROM inventory GROUP BY category LIMIT 50'
    ).fetchall()
    if inv:
        parts.append('INVENTORY SUMMARY: ' + ', '.join(f'{r["category"]}: {r["cnt"]} items' for r in inv))

    # Team count
    team = db.execute('SELECT COUNT(*) as c FROM contacts').fetchone()['c']
    if team:
        parts.append(f'TEAM: {team} contacts registered')

    return parts
