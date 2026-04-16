"""Medical Phase 2 — pregnancy/childbirth, dental, veterinary, chronic conditions,
vaccinations, mental health, herbal remedies, and clinical calculators."""

import json
import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.validation import validate_json
from web.utils import get_query_int as _get_query_int

_log = logging.getLogger(__name__)

medical_phase2_bp = Blueprint('medical_phase2', __name__)

CHRONIC_SEVERITIES = ['mild', 'moderate', 'severe', 'critical']
MOOD_LABELS = {1: 'Very Low', 2: 'Low', 3: 'Below Average', 4: 'Slightly Low',
               5: 'Neutral', 6: 'Slightly Good', 7: 'Good', 8: 'Very Good',
               9: 'Excellent', 10: 'Peak'}
SPECIES_LIST = ['dog', 'cat', 'horse', 'cow', 'goat', 'chicken', 'pig', 'sheep', 'rabbit', 'other']

# Audit H2 — schemas for high-sensitivity patient data routes.
_PREGNANCY_SCHEMA = {
    'patient_name': {'type': str, 'required': True, 'max_length': 200},
    'due_date': {'type': str, 'max_length': 50},
    'blood_type': {'type': str, 'max_length': 10},
    'gravida': {'type': int, 'min': 0, 'max': 30},
    'para': {'type': int, 'min': 0, 'max': 30},
    'status': {'type': str, 'choices': ['active', 'delivered', 'loss']},
    'notes': {'type': str, 'max_length': 5000},
}
_DENTAL_SCHEMA = {
    'patient_name': {'type': str, 'required': True, 'max_length': 200},
    'tooth_number': {'type': int, 'min': 1, 'max': 32},
    'condition': {'type': str, 'max_length': 200},
    'treatment': {'type': str, 'max_length': 500},
    'pain_level': {'type': int, 'min': 0, 'max': 10},
    'treatment_date': {'type': str, 'max_length': 50},
}
_CHRONIC_SCHEMA = {
    'patient_name': {'type': str, 'required': True, 'max_length': 200},
    'condition_name': {'type': str, 'required': True, 'max_length': 200},
    'severity': {'type': str, 'choices': CHRONIC_SEVERITIES},
    'medication_stockpile_days': {'type': int, 'min': 0, 'max': 36500},
}
_VAX_SCHEMA = {
    'patient_name': {'type': str, 'required': True, 'max_length': 200},
    'vaccine_name': {'type': str, 'required': True, 'max_length': 200},
    'date_administered': {'type': str, 'max_length': 50},
    'dose_number': {'type': int, 'min': 1, 'max': 20},
    'next_due': {'type': str, 'max_length': 50},
}
_VET_SCHEMA = {
    'animal_name': {'type': str, 'required': True, 'max_length': 200},
    'species': {'type': str, 'choices': SPECIES_LIST},
    'breed': {'type': str, 'max_length': 100},
    'weight_lb': {'type': (int, float), 'min': 0, 'max': 5000},
    'condition': {'type': str, 'max_length': 500},
    'treatment': {'type': str, 'max_length': 1000},
}
_MENTAL_SCHEMA = {
    'patient_name': {'type': str, 'required': True, 'max_length': 200},
    'check_date': {'type': str, 'max_length': 50},
    'mood_score': {'type': int, 'min': 0, 'max': 10},
    'anxiety_level': {'type': int, 'min': 0, 'max': 10},
    'sleep_hours': {'type': (int, float), 'min': 0, 'max': 24},
    'energy_level': {'type': int, 'min': 0, 'max': 10},
}

BUILTIN_HERBS = [
    ('Yarrow', 'Achillea millefolium', '["wound healing","fever reduction","anti-inflammatory"]',
     'Poultice for wounds; tea for fever', 'Tea: 1-2 tsp dried herb per cup, 3x daily',
     '["blood thinners","pregnancy"]', 'summer', 'Fields, roadsides'),
    ('Plantain', 'Plantago major', '["insect bites","wound healing","anti-inflammatory"]',
     'Chew leaf and apply as poultice', 'Apply fresh leaf directly to wound',
     '[]', 'all', 'Lawns, disturbed soil'),
    ('Elderberry', 'Sambucus nigra', '["immune support","cold/flu","antiviral"]',
     'Syrup from cooked berries; DO NOT eat raw', '1 tbsp syrup 4x daily during illness',
     '["autoimmune conditions","raw berries are toxic"]', 'fall', 'Hedgerows, woodland edges'),
    ('Echinacea', 'Echinacea purpurea', '["immune stimulant","wound healing","anti-inflammatory"]',
     'Tincture or tea from root/flower', 'Tincture: 1-2ml 3x daily; Tea: 1-2 tsp per cup',
     '["autoimmune disorders","ragweed allergy"]', 'summer', 'Prairies, gardens'),
    ('Willow Bark', 'Salix alba', '["pain relief","fever reduction","anti-inflammatory"]',
     'Decoction of inner bark', '1-2 tsp bark per cup, simmer 10min, 3x daily',
     '["aspirin allergy","blood thinners","children under 16","pregnancy"]', 'spring', 'Near water'),
    ('Chamomile', 'Matricaria chamomilla', '["sleep aid","digestive","anti-anxiety","anti-inflammatory"]',
     'Tea from dried flowers', '1-2 tsp per cup, steep 5-10min, up to 4x daily',
     '["ragweed allergy"]', 'summer', 'Fields, gardens'),
    ('Calendula', 'Calendula officinalis', '["wound healing","anti-fungal","skin conditions"]',
     'Salve or poultice from flowers', 'Apply salve to affected area 2-3x daily',
     '["ragweed allergy","pregnancy"]', 'summer', 'Gardens'),
    ('Comfrey', 'Symphytum officinale', '["bone healing","sprains","bruises"]',
     'Poultice from leaves; EXTERNAL USE ONLY', 'Apply poultice to area, wrap, 2-3x daily',
     '["never ingest","liver damage if eaten","do not apply to open wounds"]', 'summer', 'Damp areas, gardens'),
    ('Garlic', 'Allium sativum', '["antibiotic","antiviral","blood pressure","immune support"]',
     'Raw cloves, crushed and rested 10min', '2-3 raw cloves daily; poultice for infections',
     '["blood thinners","surgery within 2 weeks"]', 'all', 'Gardens'),
    ('Ginger', 'Zingiber officinale', '["nausea","digestive","anti-inflammatory","circulation"]',
     'Tea from fresh root; candied', 'Tea: 1 inch fresh root per cup; Nausea: 250mg 4x daily',
     '["blood thinners","gallstones"]', 'all', 'Tropical, container gardens'),
]


# ─── Pregnancy & Childbirth CRUD ────────────────────────────────────

@medical_phase2_bp.route('/api/medical/pregnancies')
def api_pregnancies_list():
    status = request.args.get('status', '').strip()
    with db_session() as db:
        if status:
            rows = db.execute(
                'SELECT * FROM pregnancies WHERE status = ? ORDER BY due_date', (status,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM pregnancies ORDER BY due_date').fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/pregnancies', methods=['POST'])
@validate_json(_PREGNANCY_SCHEMA)
def api_pregnancies_create():
    data = request.get_json() or {}
    name = (data.get('patient_name') or '').strip()
    if not name:
        return jsonify({'error': 'patient_name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO pregnancies
               (patient_name, due_date, conception_date, blood_type, rh_factor,
                gravida, para, risk_factors, birth_plan, supply_checklist,
                status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('due_date', ''), data.get('conception_date', ''),
             data.get('blood_type', ''), data.get('rh_factor', ''),
             data.get('gravida', 1), data.get('para', 0),
             str(data.get('risk_factors', '[]')),
             data.get('birth_plan', ''),
             str(data.get('supply_checklist', '[]')),
             data.get('status', 'active'), data.get('notes', ''))
        )
        db.commit()
        log_activity('pregnancy_created', detail=name)
        row = db.execute('SELECT * FROM pregnancies WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/pregnancies/<int:pid>', methods=['PUT'])
@validate_json(_PREGNANCY_SCHEMA)
def api_pregnancies_update(pid):
    data = request.get_json() or {}
    allowed = [
        'patient_name', 'due_date', 'conception_date', 'blood_type', 'rh_factor',
        'gravida', 'para', 'risk_factors', 'prenatal_visits', 'birth_plan',
        'supply_checklist', 'status', 'outcome', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(pid)
    with db_session() as db:
        db.execute(f"UPDATE pregnancies SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM pregnancies WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@medical_phase2_bp.route('/api/medical/pregnancies/<int:pid>', methods=['DELETE'])
def api_pregnancies_delete(pid):
    with db_session() as db:
        db.execute('DELETE FROM pregnancies WHERE id = ?', (pid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Dental Records CRUD ───────────────────────────────────────────

@medical_phase2_bp.route('/api/medical/dental')
def api_dental_list():
    patient = request.args.get('patient', '').strip()
    with db_session() as db:
        if patient:
            rows = db.execute(
                'SELECT * FROM dental_records WHERE patient_name = ? ORDER BY treatment_date DESC',
                (patient,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM dental_records ORDER BY treatment_date DESC'
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/dental', methods=['POST'])
@validate_json(_DENTAL_SCHEMA)
def api_dental_create():
    data = request.get_json() or {}
    name = (data.get('patient_name') or '').strip()
    if not name:
        return jsonify({'error': 'patient_name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO dental_records
               (patient_name, tooth_number, condition, treatment,
                treatment_date, pain_level, provider, follow_up_date, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (name, data.get('tooth_number'), data.get('condition', ''),
             data.get('treatment', ''), data.get('treatment_date', ''),
             data.get('pain_level', 0), data.get('provider', ''),
             data.get('follow_up_date', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('dental_record_created', detail=name)
        row = db.execute('SELECT * FROM dental_records WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/dental/<int:did>', methods=['DELETE'])
def api_dental_delete(did):
    with db_session() as db:
        db.execute('DELETE FROM dental_records WHERE id = ?', (did,))
        db.commit()
    return jsonify({'ok': True})


# ─── Herbal Remedies CRUD + Seed ────────────────────────────────────

@medical_phase2_bp.route('/api/medical/herbal')
def api_herbal_list():
    q = request.args.get('q', '').strip().lower()
    with db_session() as db:
        if q:
            rows = db.execute(
                "SELECT * FROM herbal_remedies WHERE LOWER(name) LIKE ? OR LOWER(common_names) LIKE ? OR LOWER(uses) LIKE ? ORDER BY name",
                (f'%{q}%', f'%{q}%', f'%{q}%')
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM herbal_remedies ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/herbal/seed', methods=['POST'])
def api_herbal_seed():
    """Seed built-in herbal remedies reference database."""
    seeded = 0
    with db_session() as db:
        for name, common, uses, prep, dose, contra, season, habitat in BUILTIN_HERBS:
            exists = db.execute(
                'SELECT id FROM herbal_remedies WHERE name = ? AND is_builtin = 1',
                (name,)
            ).fetchone()
            if not exists:
                db.execute(
                    '''INSERT INTO herbal_remedies
                       (name, common_names, uses, preparation, dosage,
                        contraindications, season, habitat, is_builtin)
                       VALUES (?,?,?,?,?,?,?,?,1)''',
                    (name, common, uses, prep, dose, contra, season, habitat)
                )
                seeded += 1
        db.commit()
    return jsonify({'seeded': seeded, 'total_builtin': len(BUILTIN_HERBS)})


@medical_phase2_bp.route('/api/medical/herbal', methods=['POST'])
def api_herbal_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO herbal_remedies
               (name, common_names, uses, preparation, dosage,
                contraindications, interactions, season, habitat,
                identification, is_builtin, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,0,?)''',
            (name, data.get('common_names', ''),
             str(data.get('uses', '[]')),
             data.get('preparation', ''), data.get('dosage', ''),
             str(data.get('contraindications', '[]')),
             str(data.get('interactions', '[]')),
             data.get('season', 'all'), data.get('habitat', ''),
             data.get('identification', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('herbal_remedy_created', detail=name)
        row = db.execute('SELECT * FROM herbal_remedies WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/herbal/<int:hid>', methods=['DELETE'])
def api_herbal_delete(hid):
    with db_session() as db:
        db.execute('DELETE FROM herbal_remedies WHERE id = ?', (hid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Chronic Conditions CRUD ───────────────────────────────────────

@medical_phase2_bp.route('/api/medical/chronic')
def api_chronic_list():
    patient = request.args.get('patient', '').strip()
    with db_session() as db:
        if patient:
            rows = db.execute(
                'SELECT * FROM chronic_conditions WHERE patient_name = ? ORDER BY condition_name',
                (patient,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM chronic_conditions ORDER BY patient_name, condition_name').fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/chronic', methods=['POST'])
@validate_json(_CHRONIC_SCHEMA)
def api_chronic_create():
    data = request.get_json() or {}
    name = (data.get('patient_name') or '').strip()
    condition = (data.get('condition_name') or '').strip()
    if not name or not condition:
        return jsonify({'error': 'patient_name and condition_name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO chronic_conditions
               (patient_name, condition_name, severity, diagnosed_date,
                medications, medication_stockpile_days, weaning_protocol,
                alternative_treatments, monitoring_schedule, emergency_protocol,
                status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, condition, data.get('severity', 'moderate'),
             data.get('diagnosed_date', ''),
             str(data.get('medications', '[]')),
             data.get('medication_stockpile_days', 0),
             data.get('weaning_protocol', ''),
             str(data.get('alternative_treatments', '[]')),
             data.get('monitoring_schedule', ''),
             data.get('emergency_protocol', ''),
             data.get('status', 'active'), data.get('notes', ''))
        )
        db.commit()
        log_activity('chronic_condition_created', detail=f"{name}: {condition}")
        row = db.execute('SELECT * FROM chronic_conditions WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/chronic/<int:cid>', methods=['PUT'])
@validate_json(_CHRONIC_SCHEMA)
def api_chronic_update(cid):
    data = request.get_json() or {}
    allowed = [
        'patient_name', 'condition_name', 'severity', 'diagnosed_date',
        'medications', 'medication_stockpile_days', 'weaning_protocol',
        'alternative_treatments', 'monitoring_schedule', 'emergency_protocol',
        'last_checkup', 'status', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(cid)
    with db_session() as db:
        db.execute(f"UPDATE chronic_conditions SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM chronic_conditions WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@medical_phase2_bp.route('/api/medical/chronic/<int:cid>', methods=['DELETE'])
def api_chronic_delete(cid):
    with db_session() as db:
        db.execute('DELETE FROM chronic_conditions WHERE id = ?', (cid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Medication Stockpile Alerts ────────────────────────────────────

@medical_phase2_bp.route('/api/medical/chronic/stockpile-alerts')
def api_chronic_stockpile_alerts():
    """List conditions where medication stockpile is running low (<30 days)."""
    threshold = request.args.get('days', 30, type=int)
    with db_session() as db:
        rows = db.execute(
            '''SELECT * FROM chronic_conditions
               WHERE status = 'active' AND medication_stockpile_days < ? AND medication_stockpile_days >= 0
               ORDER BY medication_stockpile_days ASC''',
            (threshold,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Vaccinations CRUD ─────────────────────────────────────────────

@medical_phase2_bp.route('/api/medical/vaccinations')
def api_vaccinations_list():
    patient = request.args.get('patient', '').strip()
    with db_session() as db:
        if patient:
            rows = db.execute(
                'SELECT * FROM vaccinations WHERE patient_name = ? ORDER BY date_administered DESC',
                (patient,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM vaccinations ORDER BY date_administered DESC').fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/vaccinations', methods=['POST'])
@validate_json(_VAX_SCHEMA)
def api_vaccinations_create():
    data = request.get_json() or {}
    name = (data.get('patient_name') or '').strip()
    vaccine = (data.get('vaccine_name') or '').strip()
    if not name or not vaccine:
        return jsonify({'error': 'patient_name and vaccine_name required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO vaccinations
               (patient_name, vaccine_name, date_administered, dose_number,
                lot_number, provider, next_due, reaction, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (name, vaccine, data.get('date_administered', ''),
             data.get('dose_number', 1), data.get('lot_number', ''),
             data.get('provider', ''), data.get('next_due', ''),
             data.get('reaction', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('vaccination_logged', detail=f"{name}: {vaccine}")
        row = db.execute('SELECT * FROM vaccinations WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/vaccinations/<int:vid>', methods=['DELETE'])
def api_vaccinations_delete(vid):
    with db_session() as db:
        db.execute('DELETE FROM vaccinations WHERE id = ?', (vid,))
        db.commit()
    return jsonify({'ok': True})


@medical_phase2_bp.route('/api/medical/vaccinations/due')
def api_vaccinations_due():
    """List vaccinations that are due or overdue."""
    today = date.today().isoformat()
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM vaccinations WHERE next_due != '' AND next_due <= ? ORDER BY next_due",
            (today,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Mental Health Check-in CRUD ───────────────────────────────────

@medical_phase2_bp.route('/api/medical/mental-health')
def api_mental_health_list():
    patient = request.args.get('patient', '').strip()
    limit = _get_query_int(request, 'limit', 50, minimum=1, maximum=200)
    with db_session() as db:
        if patient:
            rows = db.execute(
                'SELECT * FROM mental_health_logs WHERE patient_name = ? ORDER BY check_date DESC LIMIT ?',
                (patient, limit)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM mental_health_logs ORDER BY check_date DESC LIMIT ?', (limit,)
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/mental-health', methods=['POST'])
@validate_json(_MENTAL_SCHEMA)
def api_mental_health_create():
    data = request.get_json() or {}
    name = (data.get('patient_name') or '').strip()
    check_date = (data.get('check_date') or '').strip()
    if not name or not check_date:
        return jsonify({'error': 'patient_name and check_date required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO mental_health_logs
               (patient_name, check_date, mood_score, anxiety_level,
                sleep_hours, sleep_quality, appetite, energy_level,
                stress_sources, coping_strategies, warning_signs,
                provider_notes, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, check_date, data.get('mood_score', 5),
             data.get('anxiety_level', 0),
             data.get('sleep_hours', 7), data.get('sleep_quality', 'fair'),
             data.get('appetite', 'normal'), data.get('energy_level', 5),
             str(data.get('stress_sources', '[]')),
             str(data.get('coping_strategies', '[]')),
             str(data.get('warning_signs', '[]')),
             data.get('provider_notes', ''), data.get('notes', ''))
        )
        db.commit()
        log_activity('mental_health_checkin', detail=f"{name} {check_date}")
        row = db.execute('SELECT * FROM mental_health_logs WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/mental-health/<int:mid>', methods=['DELETE'])
def api_mental_health_delete(mid):
    with db_session() as db:
        db.execute('DELETE FROM mental_health_logs WHERE id = ?', (mid,))
        db.commit()
    return jsonify({'ok': True})


@medical_phase2_bp.route('/api/medical/mental-health/trends')
def api_mental_health_trends():
    """Get mood/anxiety trends for a patient over last 30 entries."""
    patient = request.args.get('patient', '').strip()
    if not patient:
        return jsonify({'error': 'patient param required'}), 400
    with db_session() as db:
        rows = db.execute(
            '''SELECT check_date, mood_score, anxiety_level, sleep_hours, energy_level
               FROM mental_health_logs WHERE patient_name = ?
               ORDER BY check_date DESC LIMIT 30''',
            (patient,)
        ).fetchall()
    entries = [dict(r) for r in rows]
    if not entries:
        return jsonify({'entries': [], 'avg_mood': 0, 'avg_anxiety': 0})
    avg_mood = sum(e['mood_score'] for e in entries) / len(entries)
    avg_anxiety = sum(e['anxiety_level'] for e in entries) / len(entries)
    avg_sleep = sum(e['sleep_hours'] for e in entries) / len(entries)
    return jsonify({
        'entries': list(reversed(entries)),
        'avg_mood': round(avg_mood, 1),
        'avg_anxiety': round(avg_anxiety, 1),
        'avg_sleep': round(avg_sleep, 1),
        'total_entries': len(entries),
    })


# ─── Veterinary Records CRUD ──────────────────────────────────────

@medical_phase2_bp.route('/api/medical/vet')
def api_vet_list():
    species = request.args.get('species', '').strip()
    with db_session() as db:
        if species:
            rows = db.execute(
                'SELECT * FROM vet_records WHERE species = ? ORDER BY animal_name', (species,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM vet_records ORDER BY animal_name').fetchall()
    return jsonify([dict(r) for r in rows])


@medical_phase2_bp.route('/api/medical/vet', methods=['POST'])
@validate_json(_VET_SCHEMA)
def api_vet_create():
    data = request.get_json() or {}
    name = (data.get('animal_name') or '').strip()
    if not name:
        return jsonify({'error': 'animal_name is required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO vet_records
               (animal_name, species, breed, weight_lb, age_years,
                condition, treatment, treatment_date, medications,
                vaccinations, provider, next_due, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('species', 'dog'), data.get('breed', ''),
             data.get('weight_lb', 0), data.get('age_years', 0),
             data.get('condition', ''), data.get('treatment', ''),
             data.get('treatment_date', ''),
             str(data.get('medications', '[]')),
             str(data.get('vaccinations', '[]')),
             data.get('provider', ''), data.get('next_due', ''),
             data.get('notes', ''))
        )
        db.commit()
        log_activity('vet_record_created', detail=name)
        row = db.execute('SELECT * FROM vet_records WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@medical_phase2_bp.route('/api/medical/vet/<int:vid>', methods=['PUT'])
@validate_json(_VET_SCHEMA)
def api_vet_update(vid):
    data = request.get_json() or {}
    allowed = [
        'animal_name', 'species', 'breed', 'weight_lb', 'age_years',
        'condition', 'treatment', 'treatment_date', 'medications',
        'vaccinations', 'provider', 'next_due', 'notes',
    ]
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(str(v) if isinstance(v, (list, dict)) else v)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append("updated_at = CURRENT_TIMESTAMP")
    vals.append(vid)
    with db_session() as db:
        db.execute(f"UPDATE vet_records SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM vet_records WHERE id = ?', (vid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@medical_phase2_bp.route('/api/medical/vet/<int:vid>', methods=['DELETE'])
def api_vet_delete(vid):
    with db_session() as db:
        db.execute('DELETE FROM vet_records WHERE id = ?', (vid,))
        db.commit()
    return jsonify({'ok': True})


# ─── Clinical Calculators ──────────────────────────────────────────

@medical_phase2_bp.route('/api/medical/calc/iv-rate', methods=['POST'])
def api_calc_iv_rate():
    """Calculate IV drip rate: volume / time = rate."""
    data = request.get_json() or {}
    volume_ml = float(data.get('volume_ml', 1000))
    hours = float(data.get('hours', 8))
    drop_factor = int(data.get('drop_factor', 20))  # drops per mL
    if hours <= 0:
        return jsonify({'error': 'hours must be positive'}), 400
    ml_per_hour = volume_ml / hours
    drops_per_min = (volume_ml * drop_factor) / (hours * 60)
    return jsonify({
        'volume_ml': volume_ml,
        'hours': hours,
        'drop_factor': drop_factor,
        'ml_per_hour': round(ml_per_hour, 1),
        'drops_per_min': round(drops_per_min, 1),
    })


@medical_phase2_bp.route('/api/medical/calc/burns-bsa', methods=['POST'])
def api_calc_burns_bsa():
    """Calculate burn BSA using Rule of Nines (adult)."""
    data = request.get_json() or {}
    # Body regions: head=9, chest=18, back=18, each_arm=9, each_leg=18, groin=1
    regions = {
        'head': 9, 'chest': 18, 'back': 18,
        'left_arm': 9, 'right_arm': 9,
        'left_leg': 18, 'right_leg': 18, 'groin': 1,
    }
    total_bsa = 0
    affected = {}
    for region, pct in regions.items():
        if data.get(region):
            fraction = float(data[region])  # 0-1 how much of that region is burned
            area = pct * min(fraction, 1.0)
            affected[region] = round(area, 1)
            total_bsa += area
    fluid_ml = 0
    weight_kg = float(data.get('weight_kg', 70))
    if total_bsa > 0:
        # Parkland formula: 4 mL × weight(kg) × %BSA
        fluid_ml = 4 * weight_kg * total_bsa
    severity = 'minor'
    if total_bsa > 50:
        severity = 'critical'
    elif total_bsa > 20:
        severity = 'major'
    elif total_bsa > 10:
        severity = 'moderate'
    return jsonify({
        'total_bsa_pct': round(total_bsa, 1),
        'affected_regions': affected,
        'severity': severity,
        'parkland_fluid_ml_24h': round(fluid_ml),
        'first_8h_ml': round(fluid_ml / 2),
        'next_16h_ml': round(fluid_ml / 2),
        'weight_kg': weight_kg,
    })


@medical_phase2_bp.route('/api/medical/calc/apgar', methods=['POST'])
def api_calc_apgar():
    """Calculate APGAR score for newborn assessment."""
    data = request.get_json() or {}
    appearance = int(data.get('appearance', 0))  # 0=blue, 1=extremities blue, 2=pink
    pulse = int(data.get('pulse', 0))  # 0=absent, 1=<100, 2=>100
    grimace = int(data.get('grimace', 0))  # 0=none, 1=grimace, 2=cry
    activity = int(data.get('activity', 0))  # 0=limp, 1=some flexion, 2=active
    respiration = int(data.get('respiration', 0))  # 0=absent, 1=slow, 2=crying
    total = appearance + pulse + grimace + activity + respiration
    if total >= 7:
        assessment = 'Normal — routine care'
    elif total >= 4:
        assessment = 'Moderate depression — stimulation and possible oxygen'
    else:
        assessment = 'Severe depression — immediate resuscitation'
    return jsonify({
        'appearance': appearance,
        'pulse': pulse,
        'grimace': grimace,
        'activity': activity,
        'respiration': respiration,
        'total': total,
        'assessment': assessment,
    })


# ─── Medical Phase 2 Summary ──────────────────────────────────────

@medical_phase2_bp.route('/api/medical/phase2/summary')
def api_medical_phase2_summary():
    with db_session() as db:
        pregnancies = db.execute("SELECT COUNT(*) FROM pregnancies WHERE status = 'active'").fetchone()[0]
        dental = db.execute('SELECT COUNT(*) FROM dental_records').fetchone()[0]
        herbs = db.execute('SELECT COUNT(*) FROM herbal_remedies').fetchone()[0]
        chronic = db.execute("SELECT COUNT(*) FROM chronic_conditions WHERE status = 'active'").fetchone()[0]
        low_stockpile = db.execute(
            "SELECT COUNT(*) FROM chronic_conditions WHERE status = 'active' AND medication_stockpile_days < 30"
        ).fetchone()[0]
        vaccinations = db.execute('SELECT COUNT(*) FROM vaccinations').fetchone()[0]
        vacc_due = db.execute(
            "SELECT COUNT(*) FROM vaccinations WHERE next_due != '' AND next_due <= date('now')"
        ).fetchone()[0]
        mental_entries = db.execute('SELECT COUNT(*) FROM mental_health_logs').fetchone()[0]
        animals = db.execute('SELECT COUNT(*) FROM vet_records').fetchone()[0]
    return jsonify({
        'active_pregnancies': pregnancies,
        'dental_records': dental,
        'herbal_remedies': herbs,
        'active_chronic': chronic,
        'low_medication_stockpile': low_stockpile,
        'total_vaccinations': vaccinations,
        'vaccinations_due': vacc_due,
        'mental_health_entries': mental_entries,
        'animal_records': animals,
    })
