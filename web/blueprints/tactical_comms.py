"""Tactical Communications — radio equipment, auth codes, net schedules,
comms checks, message templates (SITREP/MEDEVAC/SALUTE), and field weather calcs."""

import math
import logging
from datetime import datetime, date

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.utils import get_query_int as _get_query_int

_log = logging.getLogger(__name__)

tactical_comms_bp = Blueprint('tactical_comms', __name__)

RADIO_TYPES = ['handheld', 'mobile', 'base', 'repeater', 'sdr', 'satellite', 'hf', 'cb']
NET_TYPES = ['daily', 'weekly', 'emergency', 'convoy', 'guard']
SIGNAL_QUALITY = ['excellent', 'good', 'fair', 'poor', 'no_contact']

_RADIO_EQUIPMENT_ALLOWED_FIELDS = frozenset({
    'name', 'model', 'serial_number', 'radio_type', 'freq_range_low',
    'freq_range_high', 'power_watts', 'battery_type', 'battery_count',
    'antenna', 'firmware_version', 'programmed_channels', 'condition',
    'assigned_to', 'location', 'last_tested', 'notes',
})
_NET_SCHEDULES_ALLOWED_FIELDS = frozenset({
    'name', 'net_type', 'frequency', 'backup_frequency', 'day_of_week',
    'start_time', 'duration_min', 'net_control', 'call_order',
    'protocol', 'is_active', 'notes',
})
_AUTH_CODES_ALLOWED_FIELDS = frozenset({
    'code_set_name', 'valid_date', 'challenge', 'response',
    'running_password', 'number_combination', 'duress_code',
    'is_active', 'notes',
})

# Built-in military message format templates
BUILTIN_TEMPLATES = [
    {
        'name': 'SITREP',
        'template_type': 'SITREP',
        'fields': '["DTG","Unit","Location","Activity","Effective Strength","Situation (enemy)","Situation (friendly)","Logistics","Communications","Commander Intent"]',
        'example': 'Line 1: 141200ZAPR26\nLine 2: Alpha Team\nLine 3: Grid 12S AB 12345 67890\nLine 4: Consolidated at rally point\nLine 5: 4/4 PAX\nLine 6: No enemy contact\nLine 7: All elements accounted for\nLine 8: Class I/III adequate 48hrs\nLine 9: All comms operational\nLine 10: Continue movement to OBJ',
        'instructions': 'Situation Report — periodic update on unit status and operations.',
    },
    {
        'name': 'MEDEVAC 9-Line',
        'template_type': 'MEDEVAC',
        'fields': '["Location (grid)","Radio Freq/Callsign","# Patients by Precedence","Special Equipment","# Patients by Type (litter/ambulatory)","Security at Pickup","Method of Marking","Patient Nationality","NBC Contamination"]',
        'example': 'Line 1: Grid 12S AB 12345 67890\nLine 2: 152.400 / DUSTOFF\nLine 3: 1A (1 Urgent)\nLine 4: None\nLine 5: 1L (1 Litter)\nLine 6: No enemy\nLine 7: VS-17 Panel\nLine 8: US Military\nLine 9: None',
        'instructions': 'Request medical evacuation. Use MIST format for patient handoff.',
    },
    {
        'name': 'SALUTE',
        'template_type': 'SALUTE',
        'fields': '["Size","Activity","Location","Unit/Uniform","Time","Equipment"]',
        'example': 'S: 3 personnel\nA: Moving east on foot\nL: Grid 12S AB 123 678\nU: Civilian clothing, no markings\nT: 1430L\nE: 2 vehicles, no visible weapons',
        'instructions': 'Enemy/unknown contact report. Report what you observe.',
    },
    {
        'name': 'SPOT Report',
        'template_type': 'SPOT',
        'fields': '["Size","Position","Observation Time","Tactical Significance"]',
        'example': 'S: 5 vehicles\nP: Intersection of Hwy 10 and Route 5\nO: 0930L today\nT: Possible roadblock being established',
        'instructions': 'Quick contact/observation report — faster than SALUTE for time-critical info.',
    },
    {
        'name': 'ACE Report',
        'template_type': 'ACE',
        'fields': '["Ammo (% remaining)","Casualties (# and type)","Equipment (status)"]',
        'example': 'A: 80% rifle, 60% pistol, 100% water\nC: 0 casualties\nE: All vehicles operational, 1 radio degraded',
        'instructions': 'Ammo-Casualties-Equipment status. Quick readiness snapshot.',
    },
    {
        'name': 'LACE Report',
        'template_type': 'LACE',
        'fields': '["Liquid (water status)","Ammo (supply levels)","Casualties","Equipment"]',
        'example': 'L: 2 days water on hand\nA: 75% ammo baseline\nC: 1 minor (treated)\nE: Generator needs fuel in 6hrs',
        'instructions': 'Logistics status — Liquid, Ammo, Casualties, Equipment.',
    },
]

BEAUFORT_SCALE = [
    (0, 'Calm', '<1', 'Smoke rises vertically'),
    (1, 'Light Air', '1-3', 'Smoke drift shows wind direction'),
    (2, 'Light Breeze', '4-7', 'Wind felt on face, leaves rustle'),
    (3, 'Gentle Breeze', '8-12', 'Leaves and small twigs move'),
    (4, 'Moderate Breeze', '13-18', 'Small branches move, dust rises'),
    (5, 'Fresh Breeze', '19-24', 'Small trees sway'),
    (6, 'Strong Breeze', '25-31', 'Large branches move, hard to use umbrella'),
    (7, 'Near Gale', '32-38', 'Whole trees move, hard to walk'),
    (8, 'Gale', '39-46', 'Twigs break off trees'),
    (9, 'Strong Gale', '47-54', 'Slight structural damage'),
    (10, 'Storm', '55-63', 'Trees uprooted, structural damage'),
    (11, 'Violent Storm', '64-72', 'Widespread damage'),
    (12, 'Hurricane', '73+', 'Devastating damage'),
]


# ─── Radio Reference Cards (CE-14, v7.61) ──────────────────────────

@tactical_comms_bp.route('/api/radio/reference')
def api_radio_reference():
    """Return static radio reference cards in one payload (CE-14).

    Phonetic alphabets (NATO + LAPD), full International Morse with prosigns,
    US voice prowords with usage examples, RST reporting, common Q-codes,
    digital-mode comparison card, and the US General-class HF band plan.
    All read-only — no DB round-trip.
    """
    try:
        from seeds import radio_reference as rr
    except Exception as exc:
        return jsonify({'error': f'radio reference unavailable: {exc}'}), 500

    return jsonify({
        'phonetic': {
            'nato': rr.NATO_PHONETIC,
            'lapd': rr.LAPD_PHONETIC,
        },
        'morse': {
            'code': rr.MORSE_CODE,
            'prosigns': [
                {'prosign': p, 'morse': m, 'meaning': meaning}
                for (p, m, meaning) in rr.MORSE_PROSIGNS
            ],
        },
        'prowords': [
            {'proword': p, 'meaning': m, 'example': ex}
            for (p, m, ex) in rr.PROWORDS
        ],
        'rst': {
            'readability': [{'score': s, 'meaning': m} for (s, m) in rr.RST_READABILITY],
            'strength':    [{'score': s, 'meaning': m} for (s, m) in rr.RST_STRENGTH],
            'tone':        [{'score': s, 'meaning': m} for (s, m) in rr.RST_TONE],
        },
        'q_codes': [
            {'code': c, 'meaning': m} for (c, m) in rr.Q_CODES
        ],
        'digital_modes': [
            {
                'name': n, 'category': cat, 'bandwidth': bw,
                'typical_frequency': tf, 'throughput': tp,
                'best_for': bf, 'notes': notes,
            }
            for (n, cat, bw, tf, tp, bf, notes) in rr.DIGITAL_MODES
        ],
        'hf_band_plan_us_general': [
            {'band': b, 'range_mhz': r, 'modes': m, 'notes': n}
            for (b, r, m, n) in rr.HF_BAND_PLAN_US_GEN
        ],
    })


@tactical_comms_bp.route('/api/radio/phonetic')
def api_radio_phonetic():
    """NATO + LAPD phonetic alphabets — quick lookup route."""
    try:
        from seeds.radio_reference import NATO_PHONETIC, LAPD_PHONETIC
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    return jsonify({'nato': NATO_PHONETIC, 'lapd': LAPD_PHONETIC})


@tactical_comms_bp.route('/api/radio/morse/<text>')
def api_radio_morse_translate(text):
    """Translate text → Morse (letters, digits, basic punctuation)."""
    try:
        from seeds.radio_reference import MORSE_CODE
    except Exception as exc:
        return jsonify({'error': str(exc)}), 500
    upper = (text or '').upper()
    if len(upper) > 500:
        return jsonify({'error': 'Text too long (500 char max)'}), 400
    # Words separated by " / ", letters by " "
    words = upper.split(' ')
    encoded = []
    unknown = []
    for word in words:
        letters = []
        for ch in word:
            if ch in MORSE_CODE:
                letters.append(MORSE_CODE[ch])
            elif ch.strip():
                unknown.append(ch)
        encoded.append(' '.join(letters))
    return jsonify({
        'input': text,
        'morse': ' / '.join(encoded),
        'unknown_chars': sorted(set(unknown)),
    })


# ─── Radio Equipment CRUD ───────────────────────────────────────────

@tactical_comms_bp.route('/api/radio-equipment')
def api_radio_equipment_list():
    rtype = request.args.get('type', '').strip()
    with db_session() as db:
        if rtype:
            rows = db.execute(
                'SELECT * FROM radio_equipment WHERE radio_type = ? ORDER BY name', (rtype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM radio_equipment ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@tactical_comms_bp.route('/api/radio-equipment', methods=['POST'])
def api_radio_equipment_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO radio_equipment
               (name, model, serial_number, radio_type, freq_range_low,
                freq_range_high, power_watts, battery_type, battery_count,
                antenna, firmware_version, programmed_channels, condition,
                assigned_to, location, last_tested, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('model', ''), data.get('serial_number', ''),
             data.get('radio_type', 'handheld'),
             data.get('freq_range_low', 0), data.get('freq_range_high', 0),
             data.get('power_watts', 5), data.get('battery_type', ''),
             data.get('battery_count', 1), data.get('antenna', ''),
             data.get('firmware_version', ''),
             str(data.get('programmed_channels', '[]')),
             data.get('condition', 'good'), data.get('assigned_to', ''),
             data.get('location', ''), data.get('last_tested', ''),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('radio_equipment_created', detail=name)
        row = db.execute('SELECT * FROM radio_equipment WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@tactical_comms_bp.route('/api/radio-equipment/<int:rid>', methods=['PUT'])
def api_radio_equipment_update(rid):
    data = request.get_json() or {}
    allowed = _RADIO_EQUIPMENT_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(rid)
    with db_session() as db:
        db.execute(f"UPDATE radio_equipment SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM radio_equipment WHERE id = ?', (rid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('radio_equipment_updated', detail=row['name'])
    return jsonify(dict(row))


@tactical_comms_bp.route('/api/radio-equipment/<int:rid>', methods=['DELETE'])
def api_radio_equipment_delete(rid):
    with db_session() as db:
        row = db.execute('SELECT name FROM radio_equipment WHERE id = ?', (rid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM radio_equipment WHERE id = ?', (rid,))
        db.commit()
        log_activity('radio_equipment_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── Auth Codes CRUD ────────────────────────────────────────────────

@tactical_comms_bp.route('/api/auth-codes')
def api_auth_codes_list():
    code_set = request.args.get('code_set', '').strip()
    active_only = request.args.get('active', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM auth_codes WHERE 1=1'
        params = []
        if code_set:
            q += ' AND code_set_name = ?'
            params.append(code_set)
        if active_only == '1':
            q += ' AND is_active = 1'
        q += ' ORDER BY valid_date DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@tactical_comms_bp.route('/api/auth-codes', methods=['POST'])
def api_auth_codes_create():
    data = request.get_json() or {}
    code_set = (data.get('code_set_name') or '').strip()
    valid_date = (data.get('valid_date') or '').strip()
    challenge = (data.get('challenge') or '').strip()
    response = (data.get('response') or '').strip()
    if not all([code_set, valid_date, challenge, response]):
        return jsonify({'error': 'code_set_name, valid_date, challenge, response required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO auth_codes
               (code_set_name, valid_date, challenge, response,
                running_password, number_combination, duress_code,
                is_active, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (code_set, valid_date, challenge, response,
             data.get('running_password', ''),
             data.get('number_combination', ''),
             data.get('duress_code', ''),
             data.get('is_active', 1), data.get('notes', ''))
        )
        db.commit()
        log_activity('auth_code_created', detail=f"{code_set} {valid_date}")
        row = db.execute('SELECT * FROM auth_codes WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@tactical_comms_bp.route('/api/auth-codes/<int:aid>', methods=['PUT'])
def api_auth_codes_update(aid):
    data = request.get_json() or {}
    allowed = _AUTH_CODES_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            vals.append(data[k])
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    vals.append(aid)
    with db_session() as db:
        db.execute(f"UPDATE auth_codes SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM auth_codes WHERE id = ?', (aid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@tactical_comms_bp.route('/api/auth-codes/<int:aid>', methods=['DELETE'])
def api_auth_codes_delete(aid):
    with db_session() as db:
        row = db.execute('SELECT id FROM auth_codes WHERE id = ?', (aid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM auth_codes WHERE id = ?', (aid,))
        db.commit()
        log_activity('auth_code_deleted', detail=str(aid))
    return jsonify({'ok': True})


@tactical_comms_bp.route('/api/auth-codes/today')
def api_auth_codes_today():
    """Get today's active authentication codes."""
    today = date.today().isoformat()
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM auth_codes WHERE valid_date = ? AND is_active = 1',
            (today,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Net Schedules CRUD ─────────────────────────────────────────────

@tactical_comms_bp.route('/api/net-schedules')
def api_net_schedules_list():
    active_only = request.args.get('active', '').strip()
    with db_session() as db:
        if active_only == '1':
            rows = db.execute(
                'SELECT * FROM net_schedules WHERE is_active = 1 ORDER BY start_time'
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM net_schedules ORDER BY start_time').fetchall()
    return jsonify([dict(r) for r in rows])


@tactical_comms_bp.route('/api/net-schedules', methods=['POST'])
def api_net_schedules_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO net_schedules
               (name, net_type, frequency, backup_frequency, day_of_week,
                start_time, duration_min, net_control, call_order,
                protocol, is_active, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('net_type', 'daily'),
             data.get('frequency', ''), data.get('backup_frequency', ''),
             data.get('day_of_week', 'daily'),
             data.get('start_time', '0800'), data.get('duration_min', 30),
             data.get('net_control', ''),
             str(data.get('call_order', '[]')),
             data.get('protocol', 'voice'),
             data.get('is_active', 1), data.get('notes', ''))
        )
        db.commit()
        log_activity('net_schedule_created', detail=name)
        row = db.execute('SELECT * FROM net_schedules WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@tactical_comms_bp.route('/api/net-schedules/<int:nid>', methods=['PUT'])
def api_net_schedules_update(nid):
    data = request.get_json() or {}
    allowed = _NET_SCHEDULES_ALLOWED_FIELDS
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(nid)
    with db_session() as db:
        db.execute(f"UPDATE net_schedules SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM net_schedules WHERE id = ?', (nid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    log_activity('net_schedule_updated', detail=row['name'])
    return jsonify(dict(row))


@tactical_comms_bp.route('/api/net-schedules/<int:nid>', methods=['DELETE'])
def api_net_schedules_delete(nid):
    with db_session() as db:
        row = db.execute('SELECT name FROM net_schedules WHERE id = ?', (nid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM comms_checks WHERE net_schedule_id = ?', (nid,))
        db.execute('DELETE FROM net_schedules WHERE id = ?', (nid,))
        db.commit()
        log_activity('net_schedule_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── Comms Checks Log ──────────────────────────────────────────────

@tactical_comms_bp.route('/api/comms-checks')
def api_comms_checks_list():
    schedule_id = request.args.get('net_schedule_id', type=int)
    with db_session() as db:
        if schedule_id:
            rows = db.execute(
                'SELECT * FROM comms_checks WHERE net_schedule_id = ? ORDER BY check_date DESC',
                (schedule_id,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM comms_checks ORDER BY check_date DESC LIMIT 100'
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@tactical_comms_bp.route('/api/comms-checks', methods=['POST'])
def api_comms_checks_create():
    data = request.get_json() or {}
    check_date = (data.get('check_date') or '').strip()
    if not check_date:
        return jsonify({'error': 'check_date is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO comms_checks
               (net_schedule_id, check_date, check_time, operator,
                stations_checked, stations_missed, signal_quality,
                propagation_notes, issues, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data.get('net_schedule_id'), check_date,
             data.get('check_time', ''), data.get('operator', ''),
             str(data.get('stations_checked', '[]')),
             str(data.get('stations_missed', '[]')),
             data.get('signal_quality', 'good'),
             data.get('propagation_notes', ''),
             data.get('issues', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('comms_check_logged', detail=check_date)
        row = db.execute('SELECT * FROM comms_checks WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@tactical_comms_bp.route('/api/comms-checks/<int:cid>', methods=['DELETE'])
def api_comms_checks_delete(cid):
    with db_session() as db:
        row = db.execute('SELECT id FROM comms_checks WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM comms_checks WHERE id = ?', (cid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Message Templates CRUD ─────────────────────────────────────────

@tactical_comms_bp.route('/api/message-templates')
def api_message_templates_list():
    ttype = request.args.get('type', '').strip()
    with db_session() as db:
        if ttype:
            rows = db.execute(
                'SELECT * FROM message_templates WHERE template_type = ? ORDER BY name',
                (ttype,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM message_templates ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@tactical_comms_bp.route('/api/message-templates/seed', methods=['POST'])
def api_message_templates_seed():
    """Seed built-in military message format templates if not present."""
    seeded = 0
    with db_session() as db:
        for tpl in BUILTIN_TEMPLATES:
            exists = db.execute(
                'SELECT id FROM message_templates WHERE name = ? AND is_builtin = 1',
                (tpl['name'],)
            ).fetchone()
            if not exists:
                db.execute(
                    '''INSERT INTO message_templates
                       (name, template_type, fields, example, instructions, is_builtin)
                       VALUES (?,?,?,?,?,1)''',
                    (tpl['name'], tpl['template_type'], tpl['fields'],
                     tpl['example'], tpl['instructions'])
                )
                seeded += 1
        db.commit()
    return jsonify({'seeded': seeded, 'total_builtin': len(BUILTIN_TEMPLATES)})


@tactical_comms_bp.route('/api/message-templates', methods=['POST'])
def api_message_templates_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO message_templates
               (name, template_type, fields, example, instructions, is_builtin, notes)
               VALUES (?,?,?,?,?,0,?)''',
            (name, data.get('template_type', 'CUSTOM'),
             str(data.get('fields', '[]')),
             data.get('example', ''), data.get('instructions', ''),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('message_template_created', detail=name)
        row = db.execute('SELECT * FROM message_templates WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@tactical_comms_bp.route('/api/message-templates/<int:tid>', methods=['DELETE'])
def api_message_templates_delete(tid):
    with db_session() as db:
        row = db.execute('SELECT name FROM message_templates WHERE id = ?', (tid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM message_templates WHERE id = ?', (tid,))
        db.commit()
        log_activity('message_template_deleted', detail=row['name'])
    return jsonify({'ok': True})


# ─── Sent Messages Log ──────────────────────────────────────────────

@tactical_comms_bp.route('/api/sent-messages')
def api_sent_messages_list():
    ttype = request.args.get('type', '').strip()
    limit = _get_query_int(request, 'limit', 50, minimum=1, maximum=200)
    with db_session() as db:
        if ttype:
            rows = db.execute(
                'SELECT * FROM sent_messages WHERE template_type = ? ORDER BY sent_at DESC LIMIT ?',
                (ttype, limit)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM sent_messages ORDER BY sent_at DESC LIMIT ?', (limit,)
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@tactical_comms_bp.route('/api/sent-messages', methods=['POST'])
def api_sent_messages_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO sent_messages
               (template_id, template_type, content, formatted_text,
                sent_via, sent_to, acknowledged, notes)
               VALUES (?,?,?,?,?,?,0,?)''',
            (data.get('template_id'), data.get('template_type', ''),
             str(data.get('content', '{}')),
             data.get('formatted_text', ''),
             data.get('sent_via', 'radio'),
             data.get('sent_to', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('message_sent', detail=data.get('template_type', 'message'))
        row = db.execute('SELECT * FROM sent_messages WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@tactical_comms_bp.route('/api/sent-messages/<int:sid>/ack', methods=['POST'])
def api_sent_messages_ack(sid):
    with db_session() as db:
        if not db.execute('SELECT id FROM sent_messages WHERE id = ?', (sid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(
            "UPDATE sent_messages SET acknowledged = 1, acknowledged_at = CURRENT_TIMESTAMP WHERE id = ?",
            (sid,)
        )
        db.commit()
        row = db.execute('SELECT * FROM sent_messages WHERE id = ?', (sid,)).fetchone()
    return jsonify(dict(row))


# ─── Weather Calculators ────────────────────────────────────────────

@tactical_comms_bp.route('/api/weather/moon-phase')
def api_moon_phase():
    """Calculate moon phase for a given date (or today)."""
    date_str = request.args.get('date', '')
    if date_str:
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            return jsonify({'error': 'invalid date format, use YYYY-MM-DD'}), 400
    else:
        d = datetime.now()
    # Simplified moon phase calculation (Conway's method)
    year, month, day = d.year, d.month, d.day
    r = year % 100
    r %= 19
    if r > 9:
        r -= 19
    r = ((r * 11) % 30) + month + day
    if month < 3:
        r += 2
    r -= ((year < 2000) + 0) * 0  # no-op kept for clarity
    r = (r + 30) % 30
    # Phase names
    if r == 0 or r == 29:
        phase = 'New Moon'
    elif 1 <= r <= 6:
        phase = 'Waxing Crescent'
    elif r == 7:
        phase = 'First Quarter'
    elif 8 <= r <= 13:
        phase = 'Waxing Gibbous'
    elif r == 14 or r == 15:
        phase = 'Full Moon'
    elif 16 <= r <= 21:
        phase = 'Waning Gibbous'
    elif r == 22:
        phase = 'Last Quarter'
    else:
        phase = 'Waning Crescent'
    illumination = round(abs(15 - r) / 15.0 * 100, 1)
    return jsonify({
        'date': d.strftime('%Y-%m-%d'),
        'day_of_cycle': r,
        'phase': phase,
        'illumination_pct': illumination,
        'good_for_night_ops': illumination < 25,
    })


@tactical_comms_bp.route('/api/weather/lightning-distance', methods=['POST'])
def api_lightning_distance():
    """Calculate lightning distance from flash-to-bang time."""
    data = request.get_json() or {}
    try:
        seconds = float(data.get('seconds', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'seconds must be a number'}), 400
    if seconds < 0:
        return jsonify({'error': 'seconds must be positive'}), 400
    miles = seconds / 5.0
    km = seconds / 3.0
    return jsonify({
        'flash_bang_seconds': seconds,
        'distance_miles': round(miles, 2),
        'distance_km': round(km, 2),
        'danger_zone': miles < 6,
        'recommendation': 'SEEK SHELTER IMMEDIATELY' if miles < 6 else 'Monitor and be prepared to shelter',
    })


@tactical_comms_bp.route('/api/weather/beaufort')
def api_beaufort_scale():
    """Return the Beaufort wind scale reference."""
    scale = []
    for force, desc, mph, obs in BEAUFORT_SCALE:
        scale.append({
            'force': force,
            'description': desc,
            'mph_range': mph,
            'observation': obs,
        })
    return jsonify(scale)


@tactical_comms_bp.route('/api/weather/growing-degree-days', methods=['POST'])
def api_growing_degree_days():
    """Calculate Growing Degree Days (GDD) from daily temps."""
    data = request.get_json() or {}
    try:
        high_f = float(data.get('high_f', 0))
        low_f = float(data.get('low_f', 0))
        base_f = float(data.get('base_f', 50))
    except (TypeError, ValueError):
        return jsonify({'error': 'high_f, low_f, base_f must be numbers'}), 400
    avg = (high_f + low_f) / 2.0
    gdd = max(0, avg - base_f)
    return jsonify({
        'high_f': high_f,
        'low_f': low_f,
        'base_f': base_f,
        'average_f': round(avg, 1),
        'gdd': round(gdd, 1),
    })


@tactical_comms_bp.route('/api/weather/wind-chill', methods=['POST'])
def api_wind_chill():
    """Calculate wind chill index."""
    data = request.get_json() or {}
    try:
        temp_f = float(data.get('temp_f', 32))
        wind_mph = float(data.get('wind_mph', 10))
    except (TypeError, ValueError):
        return jsonify({'error': 'temp_f and wind_mph must be numbers'}), 400
    if temp_f > 50 or wind_mph < 3:
        return jsonify({'wind_chill_f': temp_f, 'note': 'Wind chill not applicable above 50F or below 3mph wind'})
    wc = (35.74 + 0.6215 * temp_f
          - 35.75 * (wind_mph ** 0.16)
          + 0.4275 * temp_f * (wind_mph ** 0.16))
    frostbite_min = None
    if wc <= -18:
        frostbite_min = 30
    if wc <= -32:
        frostbite_min = 10
    if wc <= -48:
        frostbite_min = 5
    return jsonify({
        'temp_f': temp_f,
        'wind_mph': wind_mph,
        'wind_chill_f': round(wc, 1),
        'frostbite_risk_minutes': frostbite_min,
        'danger_level': 'extreme' if wc <= -40 else 'high' if wc <= -20 else 'moderate' if wc <= 0 else 'low',
    })


@tactical_comms_bp.route('/api/weather/heat-index', methods=['POST'])
def api_heat_index():
    """Calculate heat index from temperature and humidity."""
    data = request.get_json() or {}
    try:
        temp_f = float(data.get('temp_f', 80))
        humidity = float(data.get('humidity_pct', 50))
    except (TypeError, ValueError):
        return jsonify({'error': 'temp_f and humidity_pct must be numbers'}), 400
    if temp_f < 80:
        return jsonify({'heat_index_f': temp_f, 'note': 'Heat index not significant below 80F'})
    # Rothfusz regression
    hi = (-42.379 + 2.04901523 * temp_f + 10.14333127 * humidity
          - 0.22475541 * temp_f * humidity - 0.00683783 * temp_f ** 2
          - 0.05481717 * humidity ** 2 + 0.00122874 * temp_f ** 2 * humidity
          + 0.00085282 * temp_f * humidity ** 2
          - 0.00000199 * temp_f ** 2 * humidity ** 2)
    if humidity < 13 and 80 <= temp_f <= 112:
        hi -= ((13 - humidity) / 4) * math.sqrt((17 - abs(temp_f - 95)) / 17)
    elif humidity > 85 and 80 <= temp_f <= 87:
        hi += ((humidity - 85) / 10) * ((87 - temp_f) / 5)
    if hi < 80:
        hi = 0.5 * (temp_f + 61.0 + (temp_f - 68.0) * 1.2 + humidity * 0.094)
    danger = 'low'
    if hi >= 130:
        danger = 'extreme'
    elif hi >= 105:
        danger = 'danger'
    elif hi >= 90:
        danger = 'caution'
    return jsonify({
        'temp_f': temp_f,
        'humidity_pct': humidity,
        'heat_index_f': round(hi, 1),
        'danger_level': danger,
    })


# ─── Tactical Comms Summary ────────────────────────────────────────

@tactical_comms_bp.route('/api/tactical-comms/summary')
def api_tactical_comms_summary():
    with db_session() as db:
        radios = db.execute('SELECT COUNT(*) FROM radio_equipment').fetchone()[0]
        radios_good = db.execute(
            "SELECT COUNT(*) FROM radio_equipment WHERE condition = 'good'"
        ).fetchone()[0]
        nets = db.execute(
            'SELECT COUNT(*) FROM net_schedules WHERE is_active = 1'
        ).fetchone()[0]
        auth_today = db.execute(
            'SELECT COUNT(*) FROM auth_codes WHERE valid_date = ? AND is_active = 1',
            (date.today().isoformat(),)
        ).fetchone()[0]
        templates = db.execute('SELECT COUNT(*) FROM message_templates').fetchone()[0]
        recent_checks = db.execute(
            'SELECT COUNT(*) FROM comms_checks WHERE check_date >= date("now", "-7 days")'
        ).fetchone()[0]
        messages_sent = db.execute('SELECT COUNT(*) FROM sent_messages').fetchone()[0]
    return jsonify({
        'total_radios': radios,
        'radios_good': radios_good,
        'active_nets': nets,
        'auth_codes_today': auth_today,
        'message_templates': templates,
        'checks_last_7d': recent_checks,
        'total_messages_sent': messages_sent,
    })
