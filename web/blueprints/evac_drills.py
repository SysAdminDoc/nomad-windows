"""Evacuation drill system with live timing — performance tracking for evac plans."""

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination

evac_drills_bp = Blueprint('evac_drills', __name__)

_EVAC_DRILL_RUNS_ALLOWED_FIELDS = frozenset({'name', 'drill_type', 'status', 'participants', 'target_time_sec',
                                              'weather_conditions', 'notes', 'score', 'after_action_notes'})


# ─── Drill Runs CRUD ──────────────────────────────────────────────

@evac_drills_bp.route('/api/evac-drills')
def api_evac_drills_list():
    evac_plan_id = request.args.get('evac_plan_id', type=int)
    with db_session() as db:
        if evac_plan_id:
            rows = db.execute(
                'SELECT * FROM evac_drill_runs WHERE evac_plan_id = ? ORDER BY started_at DESC',
                (evac_plan_id,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM evac_drill_runs ORDER BY started_at DESC LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@evac_drills_bp.route('/api/evac-drills', methods=['POST'])
def api_evac_drills_create():
    """Create a new drill run (manual entry or start a live drill)."""
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO evac_drill_runs
               (evac_plan_id, name, drill_type, status, participants,
                target_time_sec, weather_conditions, notes)
               VALUES (?,?,?,?,?,?,?,?)''',
            (data.get('evac_plan_id'), data['name'],
             data.get('drill_type', 'full_evacuation'),
             data.get('status', 'pending'),
             data.get('participants', 0),
             data.get('target_time_sec', 0),
             data.get('weather_conditions', ''),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('evac_drill_created', detail=data['name'])
        row = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@evac_drills_bp.route('/api/evac-drills/<int:did>', methods=['PUT'])
def api_evac_drills_update(did):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        allowed = _EVAC_DRILL_RUNS_ALLOWED_FIELDS
        sets, vals = [], []
        for col in allowed:
            if col in data:
                sets.append(f'{col} = ?')
                vals.append(data[col])
        if not sets:
            return jsonify({'error': 'No fields to update'}), 400
        vals.append(did)
        db.execute(f'UPDATE evac_drill_runs SET {", ".join(sets)} WHERE id = ?', vals)
        db.commit()
        row = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
    return jsonify(dict(row))


@evac_drills_bp.route('/api/evac-drills/<int:did>', methods=['DELETE'])
def api_evac_drills_delete(did):
    with db_session() as db:
        existing = db.execute('SELECT id, name FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute('DELETE FROM evac_drill_laps WHERE drill_run_id = ?', (did,))
        db.execute('DELETE FROM evac_drill_runs WHERE id = ?', (did,))
        db.commit()
        log_activity('evac_drill_deleted', detail=existing['name'])
    return jsonify({'status': 'deleted'})


# ─── Live Timer Controls ──────────────────────────────────────────

@evac_drills_bp.route('/api/evac-drills/<int:did>/start', methods=['POST'])
def api_evac_drills_start(did):
    """Start the drill timer."""
    with db_session() as db:
        existing = db.execute('SELECT id, status FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        if existing['status'] == 'running':
            return jsonify({'error': 'Drill already running'}), 400
        db.execute(
            "UPDATE evac_drill_runs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (did,)
        )
        db.commit()
        log_activity('evac_drill_started', detail=f'Drill #{did}')
        row = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
    return jsonify(dict(row))


@evac_drills_bp.route('/api/evac-drills/<int:did>/stop', methods=['POST'])
def api_evac_drills_stop(did):
    """Stop the drill timer, calculate total elapsed."""
    with db_session() as db:
        existing = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        if existing['status'] != 'running':
            return jsonify({'error': 'Drill not running'}), 400

        # Calculate elapsed seconds
        elapsed = db.execute(
            "SELECT CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER) AS elapsed FROM evac_drill_runs WHERE id = ?",
            (did,)
        ).fetchone()
        elapsed_sec = elapsed['elapsed'] if elapsed else 0

        # Score: percentage of target time (under target = better score, capped at 100)
        target = existing['target_time_sec']
        score = 0
        if target > 0 and elapsed_sec > 0:
            ratio = target / elapsed_sec
            score = min(round(ratio * 100), 100)

        db.execute(
            '''UPDATE evac_drill_runs
               SET status = 'completed', completed_at = CURRENT_TIMESTAMP,
                   total_time_sec = ?, score = ?
               WHERE id = ?''',
            (elapsed_sec, score, did)
        )
        db.commit()
        log_activity('evac_drill_completed', detail=f'Drill #{did}: {elapsed_sec}s')
        row = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
    return jsonify(dict(row))


@evac_drills_bp.route('/api/evac-drills/<int:did>/status')
def api_evac_drills_status(did):
    """Get current drill status and elapsed time (for live polling)."""
    with db_session() as db:
        existing = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        result = dict(existing)
        if result['status'] == 'running' and result.get('started_at'):
            elapsed = db.execute(
                "SELECT CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER) AS elapsed FROM evac_drill_runs WHERE id = ?",
                (did,)
            ).fetchone()
            result['elapsed_sec'] = elapsed['elapsed'] if elapsed else 0
        laps = db.execute(
            'SELECT * FROM evac_drill_laps WHERE drill_run_id = ? ORDER BY lap_number',
            (did,)
        ).fetchall()
        result['laps'] = [dict(l) for l in laps]
    return jsonify(result)


# ─── Lap / Checkpoint Tracking ────────────────────────────────────

@evac_drills_bp.route('/api/evac-drills/<int:did>/lap', methods=['POST'])
def api_evac_drills_lap(did):
    """Record a lap / checkpoint during a running drill."""
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id, status, started_at FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        if existing['status'] != 'running':
            return jsonify({'error': 'Drill not running'}), 400

        # Get current elapsed
        elapsed = db.execute(
            "SELECT CAST((julianday(CURRENT_TIMESTAMP) - julianday(started_at)) * 86400 AS INTEGER) AS elapsed FROM evac_drill_runs WHERE id = ?",
            (did,)
        ).fetchone()
        elapsed_sec = elapsed['elapsed'] if elapsed else 0

        # Get next lap number
        last_lap = db.execute(
            'SELECT MAX(lap_number) AS max_lap FROM evac_drill_laps WHERE drill_run_id = ?',
            (did,)
        ).fetchone()
        lap_number = (last_lap['max_lap'] or 0) + 1

        cur = db.execute(
            '''INSERT INTO evac_drill_laps
               (drill_run_id, lap_number, checkpoint_name, elapsed_sec, notes)
               VALUES (?,?,?,?,?)''',
            (did, lap_number,
             data.get('checkpoint_name', f'Checkpoint {lap_number}'),
             elapsed_sec,
             data.get('notes', ''))
        )
        db.commit()
        row = db.execute('SELECT * FROM evac_drill_laps WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@evac_drills_bp.route('/api/evac-drills/<int:did>/laps')
def api_evac_drills_laps(did):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM evac_drill_laps WHERE drill_run_id = ? ORDER BY lap_number',
            (did,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Performance Analytics ────────────────────────────────────────

@evac_drills_bp.route('/api/evac-drills/performance')
def api_evac_drills_performance():
    """Aggregate drill performance stats."""
    evac_plan_id = request.args.get('evac_plan_id', type=int)
    with db_session() as db:
        if evac_plan_id:
            drills = db.execute(
                "SELECT * FROM evac_drill_runs WHERE evac_plan_id = ? AND status = 'completed' ORDER BY completed_at DESC",
                (evac_plan_id,)
            ).fetchall()
        else:
            drills = db.execute(
                "SELECT * FROM evac_drill_runs WHERE status = 'completed' ORDER BY completed_at DESC"
            ).fetchall()

        if not drills:
            return jsonify({'drills': 0, 'avg_time_sec': 0, 'best_time_sec': 0, 'avg_score': 0, 'trend': []})

        times = [d['total_time_sec'] for d in drills if d['total_time_sec']]
        scores = [d['score'] for d in drills if d['score']]

        # Trend: last 10 drills
        trend = [{'date': d['completed_at'][:10] if d['completed_at'] else '',
                   'time_sec': d['total_time_sec'] or 0,
                   'score': d['score'] or 0}
                 for d in drills[:10]]

    return jsonify({
        'drills': len(drills),
        'avg_time_sec': round(sum(times) / len(times)) if times else 0,
        'best_time_sec': min(times) if times else 0,
        'worst_time_sec': max(times) if times else 0,
        'avg_score': round(sum(scores) / len(scores)) if scores else 0,
        'trend': trend,
    })


@evac_drills_bp.route('/api/evac-drills/<int:did>/after-action', methods=['POST'])
def api_evac_drills_after_action(did):
    """Submit after-action review for a completed drill."""
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT id FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
        if not existing:
            return jsonify({'error': 'Not found'}), 404
        db.execute(
            '''UPDATE evac_drill_runs
               SET after_action_notes = ?, score = COALESCE(?, score)
               WHERE id = ?''',
            (data.get('after_action_notes', ''), data.get('score'), did)
        )
        db.commit()
        log_activity('evac_drill_aar', detail=f'AAR for drill #{did}')
        row = db.execute('SELECT * FROM evac_drill_runs WHERE id = ?', (did,)).fetchone()
    return jsonify(dict(row))


# ─── Summary ──────────────────────────────────────────────────────

@evac_drills_bp.route('/api/evac-drills/summary')
def api_evac_drills_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) FROM evac_drill_runs').fetchone()[0]
        completed = db.execute("SELECT COUNT(*) FROM evac_drill_runs WHERE status = 'completed'").fetchone()[0]
    return jsonify({'evac_drills_total': total, 'evac_drills_completed': completed})
