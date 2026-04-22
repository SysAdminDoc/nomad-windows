"""Tasks, timers, watch-schedules, and sun routes."""

import calendar
import json
import math
import logging
import time

from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, Response
from db import db_session, log_activity
from web.utils import esc as _esc, safe_json_list as _safe_json_list
from web.sql_safety import safe_columns, build_update
from web.print_templates import render_print_document
from web.state import broadcast_event

log = logging.getLogger('nomad.web')

tasks_bp = Blueprint('tasks', __name__)

_SCHEDULED_TASKS_ALLOWED_FIELDS = frozenset({'name', 'category', 'recurrence', 'next_due', 'assigned_to', 'notes'})


def _normalize_watch_personnel(value):
    personnel = []
    for person in _safe_json_list(value, []):
        label = str(person or '').strip()
        if label:
            personnel.append(label)
    return personnel


def _normalize_watch_schedule(value):
    schedule = []
    for shift in _safe_json_list(value, []):
        if not isinstance(shift, dict):
            continue
        schedule.append({
            'person': str(shift.get('person') or '').strip(),
            'start': str(shift.get('start') or '').strip(),
            'end': str(shift.get('end') or '').strip(),
            'position': shift.get('position'),
        })
    return schedule

# ─── Timers API ───────────────────────────────────────────────────


@tasks_bp.route('/api/timers')
def api_timers_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM timers ORDER BY created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    result = []
    now = datetime.now()
    for r in rows:
        try:
            started = datetime.fromisoformat(r['started_at'])
            elapsed = (now - started).total_seconds()
            remaining = max(0, r['duration_sec'] - elapsed)
            result.append({**dict(r), 'remaining_sec': remaining, 'done': remaining <= 0})
        except (ValueError, TypeError):
            continue
    return jsonify(result)


@tasks_bp.route('/api/timers', methods=['POST'])
def api_timers_create():
    data = request.get_json() or {}
    try:
        duration = int(data.get('duration_sec', 300))
        with db_session() as db:
            cur = db.execute('INSERT INTO timers (name, duration_sec, started_at) VALUES (?, ?, ?)',
                             (data.get('name', 'Timer'), duration,
                              datetime.now().isoformat()))
            db.commit()
            row = db.execute('SELECT * FROM timers WHERE id = ?', (cur.lastrowid,)).fetchone()
            result = dict(row)
        return jsonify(result), 201
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid duration value'}), 400
    except Exception as e:
        log.error('Request failed: %s', e)
        return jsonify({'error': 'Internal server error'}), 500


@tasks_bp.route('/api/timers/<int:tid>', methods=['DELETE'])
def api_timers_delete(tid):
    with db_session() as db:
        r = db.execute('DELETE FROM timers WHERE id = ?', (tid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Tasks API ────────────────────────────────────────────────────


@tasks_bp.route('/api/tasks')
def api_tasks_list():
    with db_session() as db:
        cat = request.args.get('category', '')
        assigned = request.args.get('assigned_to', '')
        query = 'SELECT * FROM scheduled_tasks'
        params = []
        clauses = []
        if cat:
            clauses.append('category = ?')
            params.append(cat)
        if assigned:
            clauses.append('assigned_to = ?')
            params.append(assigned)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY next_due ASC LIMIT 500'
        rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@tasks_bp.route('/api/tasks', methods=['POST'])
def api_tasks_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO scheduled_tasks (name, category, recurrence, next_due, assigned_to, notes) VALUES (?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('category', 'custom'), data.get('recurrence', 'once'),
             data.get('next_due', ''), data.get('assigned_to', ''), data.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('task_created', 'scheduler', data.get('name', ''))
    return jsonify(dict(row)), 201


@tasks_bp.route('/api/tasks/<int:task_id>', methods=['PUT'])
def api_tasks_update(task_id):
    data = request.get_json() or {}
    with db_session() as db:
        allowed = _SCHEDULED_TASKS_ALLOWED_FIELDS
        filtered = safe_columns(data, allowed)
        if not filtered:
            return jsonify({'error': 'No fields to update'}), 400
        sql, params = build_update('scheduled_tasks', filtered, allowed, where_val=task_id)
        db.execute(sql, params)
        db.commit()
        row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
    if not row:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(dict(row))


@tasks_bp.route('/api/tasks/<int:task_id>', methods=['DELETE'])
def api_tasks_delete(task_id):
    with db_session() as db:
        r = db.execute('DELETE FROM scheduled_tasks WHERE id = ?', (task_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@tasks_bp.route('/api/tasks/<int:task_id>/complete', methods=['POST'])
def api_tasks_complete(task_id):
    with db_session() as db:
        row = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Task not found'}), 404
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_count = (row['completed_count'] or 0) + 1
        # Calculate next_due for recurring tasks (anchored to previous due date to prevent drift)
        next_due = None
        rec = row['recurrence']
        current_next_due = row['next_due']
        if current_next_due:
            try:
                base = datetime.fromisoformat(current_next_due)
            except (ValueError, TypeError):
                base = datetime.now()
        else:
            base = datetime.now()
        if rec == 'daily':
            next_due = (base + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        elif rec == 'weekly':
            next_due = (base + timedelta(weeks=1)).strftime('%Y-%m-%d %H:%M:%S')
        elif rec == 'monthly':
            y = base.year + (base.month // 12)
            m = (base.month % 12) + 1
            d = min(base.day, calendar.monthrange(y, m)[1])
            next_due = base.replace(year=y, month=m, day=d).strftime('%Y-%m-%d %H:%M:%S')
        else:
            next_due = None  # one-time task stays completed
        db.execute('UPDATE scheduled_tasks SET completed_count = ?, last_completed = ?, next_due = ? WHERE id = ?',
                   (new_count, now, next_due, task_id))
        db.commit()
        updated = db.execute('SELECT * FROM scheduled_tasks WHERE id = ?', (task_id,)).fetchone()
        task_name = row['name']
    log_activity('task_completed', 'scheduler', task_name)
    broadcast_event('task_update', {'id': task_id, 'status': 'completed'})
    return jsonify(dict(updated))


@tasks_bp.route('/api/tasks/due')
def api_tasks_due():
    with db_session() as db:
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        rows = db.execute(
            'SELECT * FROM scheduled_tasks WHERE next_due IS NOT NULL AND next_due <= ? ORDER BY next_due ASC',
            (now,)).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Watch/Shift Rotation Planner (Phase 15) ─────────────────────


@tasks_bp.route('/api/watch-schedules')
def api_watch_schedules():
    with db_session() as db:
        rows = db.execute('SELECT * FROM watch_schedules ORDER BY start_date DESC LIMIT 10000').fetchall()
        return jsonify([
            {
                **dict(r),
                'personnel': _normalize_watch_personnel(r['personnel']),
                'schedule_json': _normalize_watch_schedule(r['schedule_json']),
            }
            for r in rows
        ])


@tasks_bp.route('/api/watch-schedules', methods=['POST'])
def api_watch_schedules_create():
    data = request.get_json() or {}
    name = data.get('name', 'Watch Schedule').strip()
    start_date = data.get('start_date', '')
    end_date = data.get('end_date', '')
    try:
        shift_hours = int(data.get('shift_duration_hours', 4))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid shift_duration_hours'}), 400
    personnel = _normalize_watch_personnel(data.get('personnel', []))
    notes = data.get('notes', '')

    if not start_date:
        return jsonify({'error': 'start_date is required'}), 400
    if shift_hours < 1 or shift_hours > 24:
        return jsonify({'error': 'shift_duration_hours must be 1-24'}), 400
    if not personnel or len(personnel) < 2:
        return jsonify({'error': 'At least 2 personnel required'}), 400

    # Auto-generate rotation schedule
    schedule = []
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d') if end_date else start + timedelta(days=7)
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    current = start
    person_idx = 0
    while current < end:
        shift_end = current + timedelta(hours=shift_hours)
        if shift_end > end:
            shift_end = end
        schedule.append({
            'person': personnel[person_idx % len(personnel)],
            'start': current.strftime('%Y-%m-%d %H:%M'),
            'end': shift_end.strftime('%Y-%m-%d %H:%M'),
            'position': person_idx % len(personnel) + 1,
        })
        current = shift_end
        person_idx += 1

    with db_session() as db:
        cur = db.execute(
            'INSERT INTO watch_schedules (name, start_date, end_date, shift_duration_hours, personnel, schedule_json, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (name, start_date, end_date or (start + timedelta(days=7)).strftime('%Y-%m-%d'), shift_hours, json.dumps(personnel), json.dumps(schedule), notes)
        )
        db.commit()
        sid = cur.lastrowid
    log_activity('watch_schedule_created', 'operations', f'{name}: {len(personnel)} personnel, {shift_hours}h shifts')
    return jsonify({'id': sid, 'name': name, 'shifts': len(schedule), 'schedule': schedule}), 201


@tasks_bp.route('/api/watch-schedules/<int:sid>', methods=['PUT'])
def api_watch_schedules_update(sid):
    data = request.get_json() or {}
    if len(data.get('name', '') or '') > 200:
        return jsonify({'error': 'name too long (max 200)'}), 400
    with db_session() as db:
        sets = []
        vals = []
        if 'name' in data:
            sets.append('name=?')
            vals.append(data['name'])
        if 'start_date' in data:
            sets.append('start_date=?')
            vals.append(data['start_date'])
        if 'end_date' in data:
            sets.append('end_date=?')
            vals.append(data['end_date'])
        if 'shift_duration_hours' in data:
            sets.append('shift_duration_hours=?')
            try:
                vals.append(int(data['shift_duration_hours']))
            except (ValueError, TypeError):
                return jsonify({'error': 'shift_duration_hours must be a number'}), 400
        if 'personnel' in data:
            sets.append('personnel=?')
            vals.append(json.dumps(_normalize_watch_personnel(data['personnel'])))
        if 'schedule_json' in data:
            sets.append('schedule_json=?')
            vals.append(json.dumps(_normalize_watch_schedule(data['schedule_json'])))
        if 'notes' in data:
            sets.append('notes=?')
            vals.append(data['notes'])
        if not sets:
            return jsonify({'status': 'no changes'})
        sets.append('updated_at=CURRENT_TIMESTAMP')
        vals.append(sid)
        r = db.execute(f'UPDATE watch_schedules SET {", ".join(sets)} WHERE id=?', tuple(vals))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'updated'})


@tasks_bp.route('/api/watch-schedules/<int:sid>', methods=['DELETE'])
def api_watch_schedules_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM watch_schedules WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@tasks_bp.route('/api/watch-schedules/<int:sid>')
def api_watch_schedule_detail(sid):
    with db_session() as db:
        row = db.execute('SELECT * FROM watch_schedules WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({
            **dict(row),
            'personnel': _normalize_watch_personnel(row['personnel']),
            'schedule_json': _normalize_watch_schedule(row['schedule_json']),
        })


@tasks_bp.route('/api/watch-schedules/<int:sid>/print')
def api_watch_schedule_print(sid):
    """Generate a printable HTML watch schedule."""
    with db_session() as db:
        row = db.execute('SELECT * FROM watch_schedules WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        sched = row
        schedule = _safe_json_list(sched['schedule_json'], [])
        personnel = _safe_json_list(sched['personnel'], [])

    generated_at = time.strftime('%Y-%m-%d %H:%M')
    cadence = f'{sched["shift_duration_hours"]}h'
    period_label = f'{sched["start_date"]} to {sched["end_date"] or "ongoing"}'

    roster_html = ''.join(
        f'<span class="doc-chip">{_esc(str(person))}</span>'
        for person in personnel
        if str(person).strip()
    ) or '<span class="doc-chip doc-chip-muted">No personnel listed</span>'

    shift_rows = ''
    daily_counts = {}
    for idx, shift in enumerate(schedule, start=1):
        if not isinstance(shift, dict):
            continue
        person = str(shift.get('person') or 'Unassigned')
        start_value = str(shift.get('start') or '')
        end_value = str(shift.get('end') or '')
        duration_label = cadence
        start_day = ''
        try:
            start_dt = datetime.strptime(start_value, '%Y-%m-%d %H:%M')
            end_dt = datetime.strptime(end_value, '%Y-%m-%d %H:%M')
            duration_hours = max((end_dt - start_dt).total_seconds() / 3600, 0)
            duration_label = f'{duration_hours:g}h'
            start_day = start_dt.strftime('%Y-%m-%d')
        except (TypeError, ValueError):
            if start_value:
                start_day = start_value.split(' ')[0]
        if start_day:
            daily_counts[start_day] = daily_counts.get(start_day, 0) + 1
        shift_rows += (
            f'<tr><td class="doc-strong">{idx}</td><td>{_esc(person)}</td>'
            f'<td>{_esc(start_value or "-")}</td><td>{_esc(end_value or "-")}</td>'
            f'<td>{_esc(duration_label)}</td></tr>'
        )

    schedule_html = (
        '<div class="doc-table-shell"><table><thead><tr><th>#</th><th>Person</th><th>Start</th><th>End</th><th>Length</th></tr></thead>'
        f'<tbody>{shift_rows}</tbody></table></div>'
        if shift_rows else
        '<div class="doc-empty">No shifts were generated for this rotation window.</div>'
    )

    coverage_rows = ''.join(
        f'<tr><td class="doc-strong">{_esc(day)}</td><td>{count}</td><td>{_esc(cadence)} cadence</td></tr>'
        for day, count in sorted(daily_counts.items())
    )
    coverage_html = (
        '<div class="doc-table-shell"><table><thead><tr><th>Date</th><th>Scheduled Shifts</th><th>Notes</th></tr></thead>'
        f'<tbody>{coverage_rows}</tbody></table></div>'
        if coverage_rows else
        '<div class="doc-empty">Daily coverage will appear once shifts include valid start times.</div>'
    )

    notes_value = str(sched['notes'] or '').strip()
    notes_html = (
        f'<div class="doc-note-box">{_esc(notes_value)}</div>'
        if notes_value else
        '<div class="doc-empty">No operator notes were saved for this watch rotation.</div>'
    )

    body = f'''<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Rotation Overview</h2>
      <div class="doc-note-box">Printable watch bill for checkpoint handoffs, command-post rosters, and overnight rotation boards. Keep the current copy posted where the next relief can verify assignment order quickly.</div>
      <div class="doc-chip-list" style="margin-top:12px;">
        <span class="doc-chip">Period { _esc(period_label) }</span>
        <span class="doc-chip">Cadence { _esc(cadence) }</span>
        <span class="doc-chip">Personnel {len(personnel)}</span>
      </div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Watch Team</h2>
      <div class="doc-chip-list">{roster_html}</div>
      <div class="doc-note-box" style="margin-top:12px;">Relief handoff should include radio status, current incidents, perimeter notes, and any pending tasks before the next operator takes over.</div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-panel">
    <h2 class="doc-section-title">Shift Assignments</h2>
    {schedule_html}
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Daily Coverage</h2>
      {coverage_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Operator Notes</h2>
      {notes_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Watch Schedule - {_esc(str(sched["name"]))}</span>
    <span>Generated {generated_at}</span>
  </div>
</section>'''

    html = render_print_document(
        f'Watch Schedule - {sched["name"]}',
        'Structured roster for guard rotations, post coverage, and handoff planning.',
        body,
        eyebrow='NOMAD Field Desk Watch Rotation',
        meta_items=[f'Generated {generated_at}', _esc(period_label)],
        stat_items=[
            ('Personnel', len(personnel)),
            ('Shifts', len(schedule)),
            ('Cadence', cadence),
            ('Days', len(daily_counts) or 0),
        ],
        accent_start='#1a2e46',
        accent_end='#395a73',
        max_width='1100px',
    )
    return Response(html, mimetype='text/html')


# ─── Sunrise/Sunset Engine (Phase 15) ─────────────────────────────


@tasks_bp.route('/api/sun')
def api_sun():
    """NOAA solar calculator — returns sunrise, sunset, civil twilight, golden hour."""

    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    date_str = request.args.get('date', '')
    if lat is None or lng is None:
        return jsonify({'error': 'lat and lng are required'}), 400
    try:
        if date_str:
            dt = datetime.strptime(date_str, '%Y-%m-%d')
        else:
            dt = datetime.now()
    except ValueError:
        return jsonify({'error': 'Invalid date format. Use YYYY-MM-DD'}), 400

    # NOAA Solar Calculator implementation
    def _julian_day(year, month, day):
        if month <= 2:
            year -= 1
            month += 12
        A = int(year / 100)
        B = 2 - A + int(A / 4)
        return int(365.25 * (year + 4716)) + int(30.6001 * (month + 1)) + day + B - 1524.5

    def _sun_times(latitude, longitude, jd, zenith):
        """Calculate sunrise/sunset for a given zenith angle."""
        n = jd - 2451545.0 + 0.0008
        Jstar = n - longitude / 360.0
        M = (357.5291 + 0.98560028 * Jstar) % 360
        M_rad = math.radians(M)
        C = 1.9148 * math.sin(M_rad) + 0.02 * math.sin(2 * M_rad) + 0.0003 * math.sin(3 * M_rad)
        lam = (M + C + 180 + 102.9372) % 360
        lam_rad = math.radians(lam)
        Jtransit = 2451545.0 + Jstar + 0.0053 * math.sin(M_rad) - 0.0069 * math.sin(2 * lam_rad)
        sin_dec = math.sin(lam_rad) * math.sin(math.radians(23.4397))
        cos_dec = math.cos(math.asin(sin_dec))
        cos_ha = (math.cos(math.radians(zenith)) - math.sin(math.radians(latitude)) * sin_dec) / (math.cos(math.radians(latitude)) * cos_dec)
        if cos_ha < -1 or cos_ha > 1:
            return None, None  # no sunrise/sunset (polar)
        ha = math.degrees(math.acos(cos_ha))
        J_rise = Jtransit - ha / 360.0
        J_set = Jtransit + ha / 360.0
        return J_rise, J_set

    def _jd_to_time(jd_val):
        """Convert Julian Day to HH:MM time string."""
        jd_val += 0.5
        Z = int(jd_val)
        F = jd_val - Z
        if Z < 2299161:
            A = Z
        else:
            alpha = int((Z - 1867216.25) / 36524.25)
            A = Z + 1 + alpha - int(alpha / 4)
        B = A + 1524
        C = int((B - 122.1) / 365.25)
        D = int(365.25 * C)
        E = int((B - D) / 30.6001)
        day_frac = B - D - int(30.6001 * E) + F
        hours = (day_frac - int(day_frac)) * 24
        h = int(hours)
        m = int((hours - h) * 60)
        return f'{h:02d}:{m:02d}'

    year, month, day = dt.year, dt.month, dt.day
    jd = _julian_day(year, month, day)

    result = {'date': dt.strftime('%Y-%m-%d'), 'lat': lat, 'lng': lng}

    # Standard sunrise/sunset (zenith 90.833)
    rise_jd, set_jd = _sun_times(lat, lng, jd, 90.833)
    if rise_jd and set_jd:
        result['sunrise'] = _jd_to_time(rise_jd)
        result['sunset'] = _jd_to_time(set_jd)
    else:
        result['sunrise'] = None
        result['sunset'] = None

    # Civil twilight (zenith 96)
    civ_rise, civ_set = _sun_times(lat, lng, jd, 96.0)
    if civ_rise and civ_set:
        result['civil_twilight_begin'] = _jd_to_time(civ_rise)
        result['civil_twilight_end'] = _jd_to_time(civ_set)
    else:
        result['civil_twilight_begin'] = None
        result['civil_twilight_end'] = None

    # Golden hour (approximately when sun is 6 degrees above horizon -> zenith 84)
    gold_rise, gold_set = _sun_times(lat, lng, jd, 84.0)
    if gold_rise and gold_set and rise_jd and set_jd:
        result['golden_hour_morning_end'] = _jd_to_time(gold_rise)
        result['golden_hour_evening_start'] = _jd_to_time(gold_set)
    else:
        result['golden_hour_morning_end'] = None
        result['golden_hour_evening_start'] = None

    # Day length
    if rise_jd and set_jd:
        day_len_hours = (set_jd - rise_jd) * 24
        h = int(day_len_hours)
        m = int((day_len_hours - h) * 60)
        result['day_length'] = f'{h}h {m}m'
    else:
        result['day_length'] = None

    return jsonify(result)
