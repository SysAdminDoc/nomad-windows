"""Remaining features — compound alerts, AI recommendations, federation reports,
drill engine, barter ledger, curriculum tracker, pedigree tracker, NWS AFD,
perceptual hash, star map, foraging references.
"""

import hashlib
import json
import logging
import math
import re
from datetime import datetime, timezone, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

remaining_features_bp = Blueprint('remaining_features', __name__)
_log = logging.getLogger('nomad.remaining_features')


# ═══════════════════════════════════════════════════════════════════
# Compound Alert Conditions (AND/OR logic)
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/alert-rules/compound', methods=['POST'])
def api_compound_alert_create():
    """Create a compound alert rule with AND/OR logic across multiple conditions."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    conditions = data.get('conditions', [])
    logic = data.get('logic', 'AND').upper()

    if not name:
        return jsonify({'error': 'name required'}), 400
    if len(conditions) < 2:
        return jsonify({'error': 'At least 2 conditions required for compound rule'}), 400
    if logic not in ('AND', 'OR'):
        return jsonify({'error': 'logic must be AND or OR'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO compound_alert_rules
            (name, logic, conditions, actions, severity, cooldown_min, enabled, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            name, logic, json.dumps(conditions),
            json.dumps(data.get('actions', [{'type': 'alert'}])),
            data.get('severity', 'warning'),
            data.get('cooldown_min', 60),
            1 if data.get('enabled', True) else 0,
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM compound_alert_rules WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('compound_alert_created', detail=f'{name}: {logic} ({len(conditions)} conditions)')
    return jsonify(dict(row)), 201


@remaining_features_bp.route('/api/alert-rules/compound')
def api_compound_alerts_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM compound_alert_rules ORDER BY created_at DESC').fetchall()
    result = []
    for r in rows:
        d = dict(r)
        for f in ('conditions', 'actions'):
            try:
                d[f] = json.loads(d.get(f, '[]'))
            except (json.JSONDecodeError, TypeError):
                d[f] = []
        result.append(d)
    return jsonify(result)


@remaining_features_bp.route('/api/alert-rules/compound/<int:rid>', methods=['DELETE'])
def api_compound_alert_delete(rid):
    with db_session() as db:
        r = db.execute('DELETE FROM compound_alert_rules WHERE id = ?', (rid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@remaining_features_bp.route('/api/alert-rules/compound/evaluate', methods=['POST'])
def api_compound_evaluate():
    """Evaluate all enabled compound rules. Returns triggered rules."""
    triggered = []
    with db_session() as db:
        rules = db.execute(
            'SELECT * FROM compound_alert_rules WHERE enabled = 1'
        ).fetchall()

        for rule in rules:
            try:
                conditions = json.loads(rule['conditions'] or '[]')
                logic = rule['logic']
                results = []

                for cond in conditions:
                    met = _evaluate_single_condition(db, cond)
                    results.append(met)

                if logic == 'AND':
                    triggered_flag = all(results)
                else:
                    triggered_flag = any(results)

                if triggered_flag:
                    triggered.append({
                        'rule_id': rule['id'],
                        'name': rule['name'],
                        'logic': logic,
                        'conditions_met': sum(results),
                        'conditions_total': len(results),
                        'severity': rule['severity'],
                    })
            except Exception:
                _log.exception('Error evaluating compound rule %d', rule['id'])

    return jsonify({'triggered': triggered, 'rules_evaluated': len(rules)})


def _evaluate_single_condition(db, cond):
    """Evaluate a single condition dict against live data."""
    ctype = cond.get('type', '')
    comparison = cond.get('comparison', 'lt')
    threshold = cond.get('threshold', 0)

    try:
        if ctype == 'inventory_count':
            row = db.execute('SELECT COUNT(*) as c FROM inventory').fetchone()
            return _compare(row['c'], comparison, threshold)
        elif ctype == 'inventory_low':
            row = db.execute(
                'SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0'
            ).fetchone()
            return _compare(row['c'], comparison, threshold)
        elif ctype == 'water_days':
            row = db.execute('SELECT COALESCE(SUM(current_gallons), 0) as g FROM water_storage').fetchone()
            hh = db.execute("SELECT value FROM settings WHERE key = 'household_size'").fetchone()
            hh_size = int(hh['value']) if hh else 2
            days = row['g'] / (hh_size * 1) if hh_size > 0 else 0  # 1 gal/person/day drinking
            return _compare(days, comparison, threshold)
        elif ctype == 'active_alerts':
            row = db.execute('SELECT COUNT(*) as c FROM alerts WHERE dismissed = 0').fetchone()
            return _compare(row['c'], comparison, threshold)
        elif ctype == 'incidents_24h':
            row = db.execute(
                "SELECT COUNT(*) as c FROM incidents WHERE created_at >= datetime('now', '-24 hours')"
            ).fetchone()
            return _compare(row['c'], comparison, threshold)
        elif ctype == 'expired_items':
            row = db.execute(
                "SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= date('now')"
            ).fetchone()
            return _compare(row['c'], comparison, threshold)
    except Exception:
        pass
    return False


def _compare(value, op, threshold):
    try:
        v, t = float(value), float(threshold)
        if op == 'lt': return v < t
        if op == 'lte': return v <= t
        if op == 'gt': return v > t
        if op == 'gte': return v >= t
        if op == 'eq': return v == t
        if op == 'ne': return v != t
    except (TypeError, ValueError):
        pass
    return False


# ═══════════════════════════════════════════════════════════════════
# AI-Powered Recommendations Engine
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/ai/recommendations')
def api_ai_recommendations():
    """Generate readiness recommendations from inventory, regional threats, and season."""
    now = datetime.now(timezone.utc)
    month = now.month
    recommendations = []

    with db_session() as db:
        # Inventory gaps
        low = db.execute(
            'SELECT name, quantity, min_quantity, category FROM inventory '
            'WHERE quantity <= min_quantity AND min_quantity > 0 ORDER BY category LIMIT 20'
        ).fetchall()
        for item in low:
            recommendations.append({
                'priority': 'high',
                'category': 'supply',
                'action': f'Restock {item["name"]} ({item["category"]}) — currently {item["quantity"]}, minimum {item["min_quantity"]}',
            })

        # Expiring soon (next 30 days)
        expiring = db.execute(
            "SELECT name, expiration, quantity FROM inventory "
            "WHERE expiration != '' AND expiration <= date('now', '+30 days') AND expiration > date('now') "
            "ORDER BY expiration LIMIT 10"
        ).fetchall()
        for item in expiring:
            recommendations.append({
                'priority': 'medium',
                'category': 'rotation',
                'action': f'Use or rotate {item["name"]} — expires {item["expiration"]} (qty: {item["quantity"]})',
            })

        # Regional threat-based
        profile = db.execute(
            'SELECT fema_risk_scores FROM regional_profile WHERE is_active = 1 LIMIT 1'
        ).fetchone()
        if profile:
            try:
                scores = json.loads(profile['fema_risk_scores'] or '{}')
                top_threats = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:3]
                for threat, score in top_threats:
                    if score > 30:
                        recommendations.append({
                            'priority': 'medium',
                            'category': 'threat_prep',
                            'action': f'Regional threat: {threat.replace("_", " ").title()} (score: {score:.0f}) — review {threat} preparedness checklist',
                        })
            except (json.JSONDecodeError, TypeError):
                pass

        # Seasonal
        seasonal = _seasonal_recommendations(month)
        recommendations.extend(seasonal)

        # Water supply check
        water = db.execute('SELECT COALESCE(SUM(current_gallons), 0) as g FROM water_storage').fetchone()
        hh = db.execute("SELECT value FROM settings WHERE key = 'household_size'").fetchone()
        hh_size = int(hh['value']) if hh else 2
        water_days = water['g'] / max(1, hh_size) if water['g'] else 0
        if water_days < 3:
            recommendations.append({
                'priority': 'critical',
                'category': 'water',
                'action': f'Water supply critically low — {water_days:.1f} days for {hh_size} people. Refill storage immediately.',
            })
        elif water_days < 14:
            recommendations.append({
                'priority': 'medium',
                'category': 'water',
                'action': f'Water supply at {water_days:.1f} days. Target: 14+ days for {hh_size} people.',
            })

        # Overdue tasks
        overdue = db.execute(
            "SELECT COUNT(*) as c FROM scheduled_tasks WHERE due_date < date('now') AND status != 'completed'"
        ).fetchone()
        if overdue['c'] > 0:
            recommendations.append({
                'priority': 'medium',
                'category': 'tasks',
                'action': f'{overdue["c"]} overdue tasks — review and complete or reschedule',
            })

    recommendations.sort(key=lambda r: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(r['priority'], 9))
    return jsonify({'recommendations': recommendations, 'generated_at': now.isoformat()})


def _seasonal_recommendations(month):
    recs = []
    if month in (3, 4):  # Spring
        recs.append({'priority': 'low', 'category': 'seasonal', 'action': 'Spring: inspect/rotate stored water. Check garden seed inventory. Service generator.'})
    elif month in (5, 6):
        recs.append({'priority': 'low', 'category': 'seasonal', 'action': 'Early summer: review hurricane/storm supplies. Check cooling plans. Verify vehicle emergency kits.'})
    elif month in (8, 9):
        recs.append({'priority': 'low', 'category': 'seasonal', 'action': 'Late summer: harvest/preserve season. Stock up before winter. Service heating systems.'})
    elif month in (10, 11):
        recs.append({'priority': 'low', 'category': 'seasonal', 'action': 'Fall: winterize vehicles, pipes, home. Stock cold-weather gear. Check heating fuel.'})
    elif month in (12, 1, 2):
        recs.append({'priority': 'low', 'category': 'seasonal', 'action': 'Winter: monitor heating fuel. Check pipes for freezing risk. Review emergency kit accessibility.'})
    return recs


# ═══════════════════════════════════════════════════════════════════
# Auto-distribute Reports to Federation Peers
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/reports/distribute', methods=['POST'])
def api_report_distribute():
    """Push a report to all trusted federation peers."""
    data = request.get_json() or {}
    report_id = data.get('report_id')
    if not report_id:
        return jsonify({'error': 'report_id required'}), 400

    import requests as http_req

    with db_session() as db:
        report = db.execute('SELECT * FROM scheduled_reports WHERE id = ?', (report_id,)).fetchone()
        if not report:
            return jsonify({'error': 'Report not found'}), 404

        peers = db.execute(
            "SELECT * FROM federation_peers WHERE trust_level IN ('trusted', 'admin') AND auto_sync = 1"
        ).fetchall()

    sent = []
    failed = []
    payload = {
        'type': 'sitrep',
        'title': report['title'],
        'content': report['content'],
        'generated_at': report['generated_at'],
    }

    for peer in peers:
        try:
            import ipaddress
            ip = peer.get('peer_ip', '')
            if not ip:
                continue
            addr = ipaddress.ip_address(ip)
            if addr.is_loopback or addr.is_link_local or addr.is_reserved:
                continue

            resp = http_req.post(
                f"http://{ip}:8080/api/node/sync-receive",
                json={'report': payload},
                timeout=10,
            )
            if resp.ok:
                sent.append(peer['node_name'] or ip)
            else:
                failed.append(peer['node_name'] or ip)
        except Exception:
            failed.append(peer.get('node_name', '?'))

    log_activity('report_distributed', detail=f'Sent to {len(sent)} peers, {len(failed)} failed')
    return jsonify({'sent': sent, 'failed': failed})


# ═══════════════════════════════════════════════════════════════════
# Drill & Exercise Engine (V1-V5)
# ═══════════════════════════════════════════════════════════════════

DRILL_SCENARIOS = {
    'fire_evac': {
        'name': 'Structure Fire Evacuation',
        'type': 'tabletop',
        'duration_min': 30,
        'objectives': ['Test evacuation routes', 'Verify accountability procedure', 'Time egress'],
        'injects': [
            {'time_min': 0, 'event': 'Smoke alarm activates in kitchen. Flames visible.'},
            {'time_min': 5, 'event': 'Primary exit blocked by fire spread. Secondary exit viable.'},
            {'time_min': 10, 'event': 'One family member cannot be located. Last seen upstairs.'},
            {'time_min': 15, 'event': 'Fire department arrival delayed — 20 min ETA.'},
        ],
    },
    'medical_emergency': {
        'name': 'Medical Emergency (Cardiac Arrest)',
        'type': 'functional',
        'duration_min': 20,
        'objectives': ['Test CPR skills', 'Verify AED location known', 'Time to 911 call'],
        'injects': [
            {'time_min': 0, 'event': 'Adult male collapses, unresponsive. No pulse detected.'},
            {'time_min': 3, 'event': 'AED arrives. Follow voice prompts.'},
            {'time_min': 8, 'event': 'Patient has return of pulse but not breathing normally.'},
            {'time_min': 12, 'event': 'EMS arrives. Prepare handoff report (SBAR).'},
        ],
    },
    'power_outage_72h': {
        'name': '72-Hour Power Outage',
        'type': 'tabletop',
        'duration_min': 45,
        'objectives': ['Test generator startup', 'Verify food preservation plan', 'Communication plan'],
        'injects': [
            {'time_min': 0, 'event': 'Power goes out. Cell towers on backup — 4 hour battery.'},
            {'time_min': 10, 'event': 'Freezer temp rising. 24h until spoilage at current rate.'},
            {'time_min': 20, 'event': 'Neighbor asks to store insulin in your refrigerator.'},
            {'time_min': 30, 'event': 'Generator fuel at 40%. No gas stations operational.'},
        ],
    },
    'home_intrusion': {
        'name': 'Home Security Breach',
        'type': 'tabletop',
        'duration_min': 20,
        'objectives': ['Test safe room procedure', 'Verify communication plan', 'Review legal response'],
        'injects': [
            {'time_min': 0, 'event': 'Glass breaking sound from ground floor at 2 AM.'},
            {'time_min': 3, 'event': 'Unknown person visible on security camera in hallway.'},
            {'time_min': 8, 'event': 'Intruder attempting to open bedroom door.'},
            {'time_min': 12, 'event': 'Police dispatch confirms 8 minute ETA.'},
        ],
    },
    'water_contamination': {
        'name': 'Municipal Water Contamination',
        'type': 'tabletop',
        'duration_min': 30,
        'objectives': ['Test water purification capability', 'Verify stored water supply', 'Communication plan'],
        'injects': [
            {'time_min': 0, 'event': 'Boil water advisory issued. Chemical spill upstream.'},
            {'time_min': 10, 'event': 'Advisory extended to "do not use" — boiling insufficient.'},
            {'time_min': 15, 'event': 'Stores sold out of bottled water within 2 hours.'},
            {'time_min': 20, 'event': 'Duration estimated at 7-10 days minimum.'},
        ],
    },
    'comms_down': {
        'name': 'Communications Blackout',
        'type': 'functional',
        'duration_min': 30,
        'objectives': ['Test PACE comms plan', 'Verify radio equipment', 'Rally point procedure'],
        'injects': [
            {'time_min': 0, 'event': 'Cell service lost. Internet down. Landlines dead.'},
            {'time_min': 5, 'event': 'Family member is at work 15 miles away. No contact.'},
            {'time_min': 15, 'event': 'FRS/GMRS radio contact established with one neighbor.'},
            {'time_min': 20, 'event': 'Amateur radio net activating on local repeater.'},
        ],
    },
    'evacuation_wildfire': {
        'name': 'Wildfire Evacuation',
        'type': 'functional',
        'duration_min': 45,
        'objectives': ['Test bug-out bag readiness', 'Vehicle loading plan', 'Route selection'],
        'injects': [
            {'time_min': 0, 'event': 'SET alert — wildfire 10 miles away, moving toward your area.'},
            {'time_min': 10, 'event': 'Upgraded to GO — mandatory evacuation of your zone.'},
            {'time_min': 15, 'event': 'Primary evacuation route closed — traffic jam reported.'},
            {'time_min': 25, 'event': 'Smoke reducing visibility. Air quality hazardous.'},
            {'time_min': 35, 'event': 'Arrive at rally point. Account for all family members + pets.'},
        ],
    },
}


@remaining_features_bp.route('/api/drills/scenarios')
def api_drill_scenarios():
    scenario = request.args.get('scenario', '')
    if scenario:
        s = DRILL_SCENARIOS.get(scenario)
        if not s:
            return jsonify({'error': f'Unknown. Available: {", ".join(sorted(DRILL_SCENARIOS.keys()))}'}), 404
        return jsonify(s)
    return jsonify({k: {'name': v['name'], 'type': v['type'], 'duration_min': v['duration_min']}
                    for k, v in DRILL_SCENARIOS.items()})


@remaining_features_bp.route('/api/drills/run', methods=['POST'])
def api_drill_run():
    """Start a drill — log it and return the scenario with inject timeline."""
    data = request.get_json() or {}
    scenario_id = data.get('scenario', '')
    scenario = DRILL_SCENARIOS.get(scenario_id)
    if not scenario:
        return jsonify({'error': 'Unknown scenario'}), 400

    difficulty = data.get('difficulty', 'standard')
    difficulty_mods = {
        'easy': {'time_factor': 1.5, 'remove_injects': 1},
        'standard': {'time_factor': 1.0, 'remove_injects': 0},
        'hard': {'time_factor': 0.75, 'remove_injects': 0},
        'extreme': {'time_factor': 0.5, 'remove_injects': 0},
    }
    mod = difficulty_mods.get(difficulty, difficulty_mods['standard'])

    injects = scenario['injects']
    if mod['remove_injects'] > 0:
        injects = injects[:-mod['remove_injects']]

    adjusted = []
    for inj in injects:
        adjusted.append({**inj, 'time_min': round(inj['time_min'] * mod['time_factor'])})

    with db_session() as db:
        db.execute('''
            INSERT INTO drill_history (drill_type, title, duration_sec, score, notes)
            VALUES (?,?,?,?,?)
        ''', (scenario['type'], scenario['name'], scenario['duration_min'] * 60, 0,
              json.dumps({'scenario': scenario_id, 'difficulty': difficulty})))
        db.commit()

    log_activity('drill_started', detail=f'{scenario["name"]} ({difficulty})')
    return jsonify({
        'started': True,
        'scenario': scenario['name'],
        'difficulty': difficulty,
        'injects': adjusted,
        'objectives': scenario['objectives'],
        'duration_min': round(scenario['duration_min'] * mod['time_factor']),
    })


# ═══════════════════════════════════════════════════════════════════
# Pedigree + Breeding Cycle Tracker
# ═══════════════════════════════════════════════════════════════════

GESTATION_DAYS = {
    'cattle': 283, 'horse': 340, 'goat': 150, 'sheep': 150,
    'pig': 114, 'rabbit': 31, 'chicken': 21, 'duck': 28,
    'turkey': 28, 'dog': 63, 'cat': 65,
}


@remaining_features_bp.route('/api/livestock/pedigree')
def api_pedigree_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM livestock_pedigree ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@remaining_features_bp.route('/api/livestock/pedigree', methods=['POST'])
def api_pedigree_create():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name required'}), 400

    species = data.get('species', '').lower()
    bred_date = data.get('bred_date', '')
    gestation = GESTATION_DAYS.get(species, 0)
    due_date = ''
    if bred_date and gestation:
        try:
            bd = datetime.strptime(bred_date, '%Y-%m-%d')
            due_date = (bd + timedelta(days=gestation)).strftime('%Y-%m-%d')
        except ValueError:
            pass

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO livestock_pedigree
            (name, species, breed, sex, dob, sire_name, dam_name,
             registration_id, bred_date, due_date, gestation_days, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            name, species, data.get('breed', ''), data.get('sex', ''),
            data.get('dob', ''), data.get('sire_name', ''), data.get('dam_name', ''),
            data.get('registration_id', ''), bred_date, due_date, gestation,
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM livestock_pedigree WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('pedigree_added', detail=f'{species}: {name}')
    return jsonify(dict(row)), 201


@remaining_features_bp.route('/api/livestock/pedigree/<int:pid>', methods=['DELETE'])
def api_pedigree_delete(pid):
    with db_session() as db:
        r = db.execute('DELETE FROM livestock_pedigree WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@remaining_features_bp.route('/api/livestock/gestation-reference')
def api_gestation_reference():
    return jsonify(GESTATION_DAYS)


# ═══════════════════════════════════════════════════════════════════
# Homeschool Curriculum Tracker
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/education/curriculum')
def api_curriculum_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM curriculum_tracker ORDER BY student, subject').fetchall()
    return jsonify([dict(r) for r in rows])


@remaining_features_bp.route('/api/education/curriculum', methods=['POST'])
def api_curriculum_create():
    data = request.get_json() or {}
    student = data.get('student', '').strip()
    subject = data.get('subject', '').strip()
    if not student or not subject:
        return jsonify({'error': 'student and subject required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO curriculum_tracker
            (student, subject, grade_level, curriculum_name, current_lesson,
             total_lessons, completed_lessons, start_date, notes)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            student, subject, data.get('grade_level', ''),
            data.get('curriculum_name', ''), data.get('current_lesson', ''),
            data.get('total_lessons', 0), data.get('completed_lessons', 0),
            data.get('start_date', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM curriculum_tracker WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('curriculum_added', detail=f'{student}: {subject}')
    return jsonify(dict(row)), 201


@remaining_features_bp.route('/api/education/curriculum/<int:cid>/progress', methods=['POST'])
def api_curriculum_progress(cid):
    """Log a lesson completion."""
    data = request.get_json() or {}
    with db_session() as db:
        row = db.execute('SELECT * FROM curriculum_tracker WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404

        completed = (row['completed_lessons'] or 0) + 1
        current = data.get('current_lesson', row['current_lesson'])
        db.execute(
            'UPDATE curriculum_tracker SET completed_lessons = ?, current_lesson = ?, updated_at = datetime(\'now\') WHERE id = ?',
            (completed, current, cid)
        )
        db.commit()

    total = row['total_lessons'] or 1
    pct = round(completed / total * 100, 1) if total > 0 else 0
    return jsonify({'completed': completed, 'total': total, 'progress_pct': pct})


@remaining_features_bp.route('/api/education/curriculum/<int:cid>', methods=['DELETE'])
def api_curriculum_delete(cid):
    with db_session() as db:
        r = db.execute('DELETE FROM curriculum_tracker WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# Multi-Party Barter Network Ledger
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/barter/trades')
def api_barter_trades():
    with db_session() as db:
        rows = db.execute('SELECT * FROM barter_trades ORDER BY trade_date DESC LIMIT 200').fetchall()
    return jsonify([dict(r) for r in rows])


@remaining_features_bp.route('/api/barter/trades', methods=['POST'])
def api_barter_trade_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute('''
            INSERT INTO barter_trades
            (party_a, party_b, offered_items, received_items, fair_value_estimate, trade_date, witness, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            data.get('party_a', ''),
            data.get('party_b', ''),
            json.dumps(data.get('offered_items', [])),
            json.dumps(data.get('received_items', [])),
            data.get('fair_value_estimate', ''),
            data.get('trade_date', datetime.now(timezone.utc).strftime('%Y-%m-%d')),
            data.get('witness', ''),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM barter_trades WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('barter_trade', detail=f'{data.get("party_a","")} <-> {data.get("party_b","")}')
    return jsonify(dict(row)), 201


@remaining_features_bp.route('/api/barter/trades/<int:tid>', methods=['DELETE'])
def api_barter_trade_delete(tid):
    with db_session() as db:
        r = db.execute('DELETE FROM barter_trades WHERE id = ?', (tid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@remaining_features_bp.route('/api/barter/balance')
def api_barter_balance():
    """Show trade balance per party."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM barter_trades').fetchall()

    balances = {}
    for r in rows:
        for party in (r['party_a'], r['party_b']):
            if party and party not in balances:
                balances[party] = {'trades': 0, 'as_provider': 0, 'as_receiver': 0}
            if r['party_a']:
                balances[r['party_a']]['trades'] += 1
                balances[r['party_a']]['as_provider'] += 1
            if r['party_b']:
                balances[r['party_b']]['trades'] += 1
                balances[r['party_b']]['as_receiver'] += 1

    return jsonify(balances)


# ═══════════════════════════════════════════════════════════════════
# NWS Area Forecast Discussion Parser
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/weather/afd')
def api_nws_afd():
    """Fetch and parse NWS Area Forecast Discussion for a WFO."""
    wfo = request.args.get('wfo', 'OKX').upper().strip()
    if not re.match(r'^[A-Z]{3}$', wfo):
        return jsonify({'error': 'Invalid WFO code (3 uppercase letters)'}), 400

    import requests as http_req
    try:
        resp = http_req.get(
            f'https://api.weather.gov/products/types/AFD/locations/{wfo}',
            headers={'User-Agent': 'NOMAD-FieldDesk/7.44'},
            timeout=15,
        )
        if not resp.ok:
            return jsonify({'error': 'NWS API unavailable'}), 503

        products = resp.json().get('@graph', [])
        if not products:
            return jsonify({'error': 'No AFD found for this WFO'}), 404

        # Get latest
        latest_url = products[0].get('@id', '')
        if not latest_url:
            return jsonify({'error': 'No AFD URL'}), 404

        detail = http_req.get(latest_url, headers={'User-Agent': 'NOMAD-FieldDesk/7.44'}, timeout=15)
        if not detail.ok:
            return jsonify({'error': 'Could not fetch AFD detail'}), 503

        afd_data = detail.json()
        text = afd_data.get('productText', '')

        # Extract key phrases
        key_phrases = []
        for pattern in [r'(?i)(tornado|severe|warning|watch|hurricane|blizzard|ice storm|flash flood)',
                        r'(?i)(record|unprecedented|historic|extreme|dangerous)',
                        r'(?i)(snow\s+\d+)', r'(?i)(wind\s+\d+\s*mph)', r'(?i)(rain\s+\d+\s*inch)']:
            for match in re.finditer(pattern, text):
                phrase = text[max(0, match.start() - 30):match.end() + 30].strip()
                key_phrases.append(phrase)

        return jsonify({
            'wfo': wfo,
            'issued': afd_data.get('issuanceTime', ''),
            'text': text[:5000],
            'key_phrases': key_phrases[:20],
            'word_count': len(text.split()),
        })

    except Exception as e:
        _log.exception('NWS AFD fetch failed')
        return jsonify({'error': 'AFD fetch failed'}), 503


# ═══════════════════════════════════════════════════════════════════
# Offline Star Map Reference
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/reference/star-map')
def api_star_map():
    """Offline reference for navigation stars and constellations."""
    return jsonify({
        'navigation_stars': {
            'polaris': {'constellation': 'Ursa Minor', 'magnitude': 2.0, 'use': 'True north (N hemisphere). Altitude = latitude.',
                        'finding': 'Follow Dubhe + Merak (Big Dipper pointer stars) 5× their separation'},
            'sirius': {'constellation': 'Canis Major', 'magnitude': -1.46, 'use': 'Brightest star. Rises in SE, sets in SW.',
                       'finding': 'Follow Orion\'s belt down-left'},
            'canopus': {'constellation': 'Carina', 'magnitude': -0.72, 'use': 'Southern navigation star. Second brightest.',
                        'finding': 'Due south of Sirius, low on horizon from mid-latitudes'},
            'vega': {'constellation': 'Lyra', 'magnitude': 0.03, 'use': 'Summer triangle anchor. Nearly overhead in summer.',
                     'finding': 'Brightest star nearly overhead in northern summer'},
            'arcturus': {'constellation': 'Bootes', 'magnitude': -0.05, 'use': 'Spring/summer guide star.',
                         'finding': '"Arc to Arcturus" — follow the arc of the Big Dipper handle'},
            'southern_cross': {'constellation': 'Crux', 'magnitude': '0.8-1.3', 'use': 'South Celestial Pole indicator (S hemisphere)',
                                'finding': 'Extend long axis 4.5× toward horizon = south'},
        },
        'seasonal_constellations': {
            'winter_north': ['Orion (belt → Sirius/Aldebaran)', 'Taurus', 'Gemini', 'Canis Major'],
            'spring_north': ['Leo', 'Virgo', 'Bootes (Arcturus)', 'Big Dipper high'],
            'summer_north': ['Summer Triangle (Vega/Deneb/Altair)', 'Scorpius', 'Sagittarius (Milky Way center)'],
            'fall_north': ['Pegasus (Great Square)', 'Andromeda', 'Cassiopeia (W-shape, circumpolar)'],
        },
        'time_from_stars': 'Stars rise ~4 minutes earlier each night (2 hours earlier each month). A constellation\'s position tells approximate time if you know the date.',
    })


# ═══════════════════════════════════════════════════════════════════
# Foraging Calendar + Game Processing References
# ═══════════════════════════════════════════════════════════════════

@remaining_features_bp.route('/api/reference/foraging-calendar')
def api_foraging_calendar():
    """Regional foraging calendar — temperate North America."""
    return jsonify({
        'spring': {
            'march_april': ['Ramps/wild leeks', 'Dandelion greens', 'Chickweed', 'Violets', 'Nettles'],
            'may': ['Morel mushrooms', 'Fiddleheads', 'Wild garlic/ramsons', 'Clover', 'Elderflower'],
        },
        'summer': {
            'june_july': ['Wild strawberries', 'Serviceberries', 'Mulberries', 'Lamb\'s quarters', 'Purslane', 'Chanterelle mushrooms'],
            'august': ['Blackberries', 'Blueberries (wild)', 'Elderberries', 'Wild plums', 'Sumac (lemonade)'],
        },
        'fall': {
            'september': ['Pawpaw', 'Persimmon (after frost)', 'Black walnuts', 'Hickory nuts', 'Hen of the woods mushroom'],
            'october_november': ['Acorns (leach tannins)', 'Rose hips', 'Burdock root', 'Cattail roots', 'Chicken of the woods'],
        },
        'winter': {
            'december_february': ['Pine needle tea (Vitamin C)', 'Birch bark tea', 'Turkey tail mushroom', 'Cattail root starch', 'Inner bark (cambium) of pine/birch'],
        },
        'deadly_lookalikes': {
            'morel_vs_false_morel': 'True morels are hollow inside (cut lengthwise). False morels have chambered/cottony interior. False morels contain gyromitrin (toxic).',
            'wild_carrot_vs_poison_hemlock': 'Wild carrot (Queen Anne\'s lace): hairy stem, red flower in center. Poison hemlock: smooth stem with purple blotches, no hair. FATAL.',
            'elderberry_vs_water_hemlock': 'Elderberry: compound leaves, flat-topped flower clusters. Water hemlock: similar but grows in wet areas, smells different. MOST TOXIC plant in North America.',
            'chanterelle_vs_jack_o_lantern': 'Chanterelles: false gills (ridges), fruity smell. Jack-o-lantern: true gills, grows on wood, bioluminescent. Causes severe GI distress.',
        },
        'universal_rules': [
            'NEVER eat anything you cannot 100% identify',
            'Use at least 2 field guides to cross-reference',
            'Start with a small amount and wait 24 hours',
            'Learn 5 plants well rather than 50 poorly',
            'Avoid foraging near roads, industrial sites, or treated lawns',
        ],
    })


@remaining_features_bp.route('/api/reference/game-processing')
def api_game_processing():
    """Field dressing and yield reference by species."""
    return jsonify({
        'yield_table': {
            'white_tail_deer': {'live_lb': 150, 'field_dressed_pct': 78, 'boneless_meat_pct': 40, 'boneless_lb': 60,
                                'aging': '3-7 days at 34-38°F', 'notes': 'Remove tenderloins and backstraps first — best cuts'},
            'elk': {'live_lb': 700, 'field_dressed_pct': 75, 'boneless_meat_pct': 38, 'boneless_lb': 266,
                    'aging': '7-14 days at 34-38°F', 'notes': 'Quarter in field if remote — too heavy to drag whole'},
            'wild_hog': {'live_lb': 200, 'field_dressed_pct': 70, 'boneless_meat_pct': 45, 'boneless_lb': 90,
                         'aging': 'None — process immediately', 'notes': 'Wear gloves — brucellosis risk. Cook to 160°F.'},
            'wild_turkey': {'live_lb': 20, 'field_dressed_pct': 80, 'boneless_meat_pct': 50, 'boneless_lb': 10,
                            'aging': '1-2 days refrigerated', 'notes': 'Breast meat is 70% of yield. Dark meat is tougher.'},
            'rabbit': {'live_lb': 4, 'field_dressed_pct': 50, 'boneless_meat_pct': 35, 'boneless_lb': 1.4,
                       'aging': 'None needed', 'notes': 'Process same day. Check for tularemia (white spots on liver = discard).'},
            'squirrel': {'live_lb': 1.5, 'field_dressed_pct': 50, 'boneless_meat_pct': 30, 'boneless_lb': 0.45,
                         'aging': 'None needed', 'notes': '2-3 squirrels per meal. Slow cook older animals.'},
        },
        'field_dressing_priorities': [
            '1. Cool the meat ASAP — gut within 30 minutes of harvest',
            '2. Avoid puncturing intestines or bladder',
            '3. Remove tenderloins immediately (inside the cavity against the spine)',
            '4. Prop cavity open for air circulation',
            '5. Keep hide on if temp >40°F (insect barrier) or off if <40°F (cooling)',
            '6. Hang in shade, never in direct sunlight',
        ],
        'bone_sour_risk': {
            'temp_threshold': '40°F+ internal meat temperature',
            'signs': ['Greenish discoloration near bone', 'Sour/off smell at joints', 'Slimy texture near bones'],
            'prevention': ['Cool carcass to <40°F within 4 hours', 'Bone out in warm weather rather than hanging whole',
                           'Pack with ice bags in body cavity', 'Don\'t stack quarters — allow air circulation'],
        },
    })
