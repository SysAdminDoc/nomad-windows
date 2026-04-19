"""Health, community & family tools (Tier 7).

7.1  Pediatric Broselow-equivalent dose engine
7.2  Chronic condition grid-down playbooks
7.3  Wilderness medicine decision trees
7.5  Grief protocol + age-banded explainer cards
7.6  Sustained-ops sleep hygiene tracker
7.7  NCMEC-style child ID packet generator
7.8  Reunification cascade
7.10 Skill-transfer ledger
7.11 State-specific legal doc vault
"""

import json
import logging
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

health_family_bp = Blueprint('health_family', __name__)
_log = logging.getLogger('nomad.health_family')


# ═══════════════════════════════════════════════════════════════════
# 7.1 — Pediatric Broselow-Equivalent Dose Engine
# Weight-based pediatric dosing from height/color zone.
# ═══════════════════════════════════════════════════════════════════

BROSELOW_ZONES = [
    {'color': 'grey',   'length_cm': (46, 54),  'weight_kg': 3,   'age_range': 'Newborn'},
    {'color': 'pink',   'length_cm': (54, 67),  'weight_kg': 6,   'age_range': '3-6 months'},
    {'color': 'red',    'length_cm': (67, 75),  'weight_kg': 8,   'age_range': '6-9 months'},
    {'color': 'purple', 'length_cm': (75, 85),  'weight_kg': 10,  'age_range': '9-18 months'},
    {'color': 'yellow', 'length_cm': (85, 95),  'weight_kg': 12,  'age_range': '18-36 months'},
    {'color': 'white',  'length_cm': (95, 107),  'weight_kg': 15, 'age_range': '3-4 years'},
    {'color': 'blue',   'length_cm': (107, 115), 'weight_kg': 18, 'age_range': '4-5 years'},
    {'color': 'orange', 'length_cm': (115, 122), 'weight_kg': 21, 'age_range': '6-7 years'},
    {'color': 'green',  'length_cm': (122, 131), 'weight_kg': 25, 'age_range': '7-9 years'},
    {'color': 'tan',    'length_cm': (131, 143), 'weight_kg': 30, 'age_range': '9-11 years'},
]

PEDS_DRUGS = {
    'epinephrine':     {'dose_mg_kg': 0.01,  'route': 'IM', 'max_mg': 0.3,  'concentration': '1:1000', 'notes': 'Anaphylaxis'},
    'diphenhydramine': {'dose_mg_kg': 1.25,  'route': 'PO/IM', 'max_mg': 50, 'concentration': '12.5mg/5mL', 'notes': 'Allergic reaction'},
    'ibuprofen':       {'dose_mg_kg': 10,    'route': 'PO', 'max_mg': 400,   'concentration': '100mg/5mL', 'notes': 'Pain/fever, >6 months'},
    'acetaminophen':   {'dose_mg_kg': 15,    'route': 'PO', 'max_mg': 1000,  'concentration': '160mg/5mL', 'notes': 'Pain/fever'},
    'amoxicillin':     {'dose_mg_kg': 25,    'route': 'PO', 'max_mg': 500,   'concentration': '250mg/5mL', 'notes': 'Bacterial infection'},
    'ondansetron':     {'dose_mg_kg': 0.15,  'route': 'PO/IV', 'max_mg': 4,  'concentration': '4mg/5mL', 'notes': 'Anti-nausea'},
    'albuterol':       {'dose_mg_kg': 0,     'route': 'INH', 'max_mg': 0,    'concentration': 'MDI', 'notes': '2-4 puffs via spacer, any weight'},
}


@health_family_bp.route('/api/medical/pediatric-dose', methods=['POST'])
def api_pediatric_dose():
    """Calculate pediatric drug doses from weight or Broselow length.

    Input: weight_kg OR length_cm, drug (optional — returns all if omitted)
    """
    data = request.get_json() or {}

    weight_kg = None
    zone = None

    if 'weight_kg' in data:
        try:
            weight_kg = float(data['weight_kg'])
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid weight'}), 400
    elif 'length_cm' in data:
        try:
            length = float(data['length_cm'])
        except (TypeError, ValueError):
            return jsonify({'error': 'Invalid length'}), 400
        for z in BROSELOW_ZONES:
            if z['length_cm'][0] <= length < z['length_cm'][1]:
                zone = z
                weight_kg = z['weight_kg']
                break
        if not weight_kg:
            return jsonify({'error': 'Length outside Broselow range (46-143 cm)'}), 400
    else:
        return jsonify({'error': 'weight_kg or length_cm required'}), 400

    drug_filter = data.get('drug', '')
    drugs = {drug_filter: PEDS_DRUGS[drug_filter]} if drug_filter and drug_filter in PEDS_DRUGS else PEDS_DRUGS

    doses = []
    for name, drug in drugs.items():
        if drug['dose_mg_kg'] == 0:
            doses.append({
                'drug': name,
                'dose': drug['notes'],
                'route': drug['route'],
                'notes': drug['notes'],
            })
            continue

        dose_mg = min(drug['dose_mg_kg'] * weight_kg, drug['max_mg'])
        volume_ml = None
        if 'mg/' in drug['concentration']:
            try:
                conc_parts = drug['concentration'].replace('mg/', '/').split('/')
                mg_per = float(conc_parts[0])
                ml_per = float(conc_parts[1].replace('mL', ''))
                volume_ml = round(dose_mg / mg_per * ml_per, 2)
            except (ValueError, IndexError):
                pass

        doses.append({
            'drug': name,
            'dose_mg': round(dose_mg, 2),
            'volume_ml': volume_ml,
            'route': drug['route'],
            'concentration': drug['concentration'],
            'max_mg': drug['max_mg'],
            'notes': drug['notes'],
        })

    return jsonify({
        'weight_kg': weight_kg,
        'broselow_zone': zone,
        'doses': doses,
        'warning': 'Reference only. Verify all pediatric doses with medical professional.',
        'drugs_available': list(PEDS_DRUGS.keys()),
    })


# ═══════════════════════════════════════════════════════════════════
# 7.2 — Chronic Condition Grid-Down Playbooks
# ═══════════════════════════════════════════════════════════════════

GRID_DOWN_PLAYBOOKS = {
    'diabetes_type1': {
        'condition': 'Type 1 Diabetes',
        'critical_supplies': ['Insulin (refrigerate!)', 'Syringes/pen needles', 'Glucose meter + strips', 'Glucagon kit', 'Glucose tablets/juice'],
        'grid_down_protocol': [
            'Reduce insulin dose 20-30% if food intake drops',
            'Monitor blood sugar every 4 hours minimum',
            'Keep insulin cool: bury in ground, evaporative cooler, creek water',
            'Unopened insulin viable 28 days at room temp (<86°F)',
            'Signs of DKA: fruity breath, deep breathing, confusion → EMERGENCY',
        ],
        'rationing_strategy': 'Prioritize basal insulin over bolus. Switch to conservative carb diet. NPH + Regular if pump fails.',
        'substitutions': 'Walmart ReliOn insulin ($25/vial, no Rx in many states) as emergency backup.',
    },
    'diabetes_type2': {
        'condition': 'Type 2 Diabetes',
        'critical_supplies': ['Metformin', 'Glucose meter + strips', 'Low-carb food stores'],
        'grid_down_protocol': [
            'Strict carb restriction (<50g/day) reduces medication need',
            'Walking 30+ min/day improves insulin sensitivity',
            'Monitor blood sugar daily minimum',
            'Cinnamon (1-6g/day) has modest glucose-lowering evidence',
        ],
        'rationing_strategy': 'Metformin can be halved with strict diet control. Extended-release can be split to IR dosing.',
    },
    'hypertension': {
        'condition': 'Hypertension',
        'critical_supplies': ['BP medications (90-day supply)', 'Manual BP cuff', 'Stethoscope', 'Low-sodium food'],
        'grid_down_protocol': [
            'Strict sodium restriction (<1500mg/day)',
            'Daily walking/exercise',
            'Stress management critical — BP spikes under stress',
            'Taper off beta-blockers (never stop abruptly — rebound risk)',
            'Monitor BP twice daily, log readings',
        ],
        'rationing_strategy': 'ACE inhibitors/ARBs can often be halved with strict low-sodium diet. Never abruptly stop beta-blockers.',
    },
    'asthma': {
        'condition': 'Asthma',
        'critical_supplies': ['Rescue inhaler (albuterol)', 'Controller inhaler', 'Spacer/chamber', 'Peak flow meter', 'Oral prednisone burst pack'],
        'grid_down_protocol': [
            'Avoid triggers: smoke, dust, mold, cold air',
            'Wet bandana over face in dusty/smoky conditions',
            'Caffeine (strong coffee) has mild bronchodilator effect in emergency',
            'Pursed-lip breathing for acute episodes',
            'Peak flow <50% personal best = serious attack',
        ],
        'rationing_strategy': 'Prioritize rescue inhaler. Controller can be reduced to once daily in stable patients. Prednisone: reserve for severe exacerbations only.',
    },
    'epilepsy': {
        'condition': 'Epilepsy',
        'critical_supplies': ['Anti-epileptic drugs (180-day supply)', 'Rectal diazepam or midazolam', 'Medical ID bracelet'],
        'grid_down_protocol': [
            'NEVER abruptly stop seizure medications — withdrawal seizures can be fatal',
            'Maintain sleep schedule (sleep deprivation lowers seizure threshold)',
            'Avoid alcohol completely',
            'Taper gradually if supply runs low (25% reduction per week)',
            'Status epilepticus (>5 min seizure) = life threat, benzodiazepine needed',
        ],
        'rationing_strategy': 'Can sometimes reduce to minimum effective dose. Never skip doses — take at consistent times.',
    },
    'hypothyroidism': {
        'condition': 'Hypothyroidism',
        'critical_supplies': ['Levothyroxine (180-day supply)'],
        'grid_down_protocol': [
            'Take on empty stomach, 30-60 min before food',
            'Stable at room temperature for years (very shelf-stable)',
            'Symptoms of deficiency develop slowly over weeks',
            'Iodized salt ensures dietary iodine if medication runs out',
        ],
        'rationing_strategy': 'Can reduce dose 25-50% for months without crisis. Symptoms (fatigue, cold) uncomfortable but rarely dangerous in adults.',
    },
}


@health_family_bp.route('/api/medical/grid-down-playbooks')
def api_grid_down_playbooks():
    condition = request.args.get('condition', '')
    if condition:
        pb = GRID_DOWN_PLAYBOOKS.get(condition)
        if not pb:
            return jsonify({'error': f'Unknown. Available: {", ".join(sorted(GRID_DOWN_PLAYBOOKS.keys()))}'}), 404
        return jsonify(pb)
    return jsonify({k: v['condition'] for k, v in GRID_DOWN_PLAYBOOKS.items()})


@health_family_bp.route('/api/medical/grid-down-playbooks/<condition>')
def api_grid_down_playbook_detail(condition):
    pb = GRID_DOWN_PLAYBOOKS.get(condition)
    if not pb:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(pb)


# ═══════════════════════════════════════════════════════════════════
# 7.3 — Wilderness Medicine Decision Trees
# ═══════════════════════════════════════════════════════════════════

WILDERNESS_TREES = {
    'wound_assessment': {
        'title': 'Wound Assessment Decision Tree',
        'steps': [
            {'q': 'Is there life-threatening hemorrhage?', 'yes': 'Apply tourniquet/wound packing → CASEVAC', 'no': 'Continue assessment'},
            {'q': 'Is the wound >6 hours old?', 'yes': 'Do NOT close — irrigate, pack open, antibiotics', 'no': 'May close if clean'},
            {'q': 'Can you see bone, tendon, or joint capsule?', 'yes': 'Do not close — splint, irrigate, antibiotics, evacuate', 'no': 'Continue'},
            {'q': 'Is the wound contaminated (dirt, debris, animal)?', 'yes': 'Irrigate with 1L clean water per inch, debride', 'no': 'Clean and close'},
            {'q': 'Does patient have sensation distal to wound?', 'yes': 'Nerve intact — close and dress', 'no': 'Possible nerve injury — evacuate'},
        ],
    },
    'chest_injury': {
        'title': 'Chest Injury Decision Tree',
        'steps': [
            {'q': 'Is there a sucking chest wound (air moving through)?', 'yes': 'Seal 3 sides with occlusive dressing, monitor for tension pneumo', 'no': 'Continue'},
            {'q': 'Tracheal deviation + absent breath sounds + JVD?', 'yes': 'TENSION PNEUMOTHORAX — needle decompression 2nd ICS MCL', 'no': 'Continue'},
            {'q': 'Paradoxical chest wall movement (flail segment)?', 'yes': 'Stabilize with padding, position injured side down', 'no': 'Continue'},
            {'q': 'Decreasing consciousness + Beck triad?', 'yes': 'Suspect cardiac tamponade — immediate evacuation', 'no': 'Monitor vitals q15min'},
        ],
    },
    'anaphylaxis': {
        'title': 'Anaphylaxis Decision Tree',
        'steps': [
            {'q': 'Hives + breathing difficulty or hypotension?', 'yes': 'ANAPHYLAXIS — epinephrine 0.3mg IM lateral thigh NOW', 'no': 'Minor allergic reaction — diphenhydramine 50mg PO'},
            {'q': 'Symptoms improving after 5-15 minutes?', 'yes': 'Monitor 4 hours — biphasic reaction possible', 'no': 'Repeat epinephrine in 5-15 min (up to 3 doses)'},
            {'q': 'Airway swelling (stridor, inability to swallow)?', 'yes': 'Position upright, prepare for surgical airway if complete obstruction', 'no': 'Maintain position of comfort'},
        ],
    },
    'hypothermia': {
        'title': 'Hypothermia Decision Tree',
        'steps': [
            {'q': 'Is the patient shivering?', 'yes': 'MILD (90-95°F) — remove wet clothes, insulate, warm fluids', 'no': 'MODERATE-SEVERE — continue'},
            {'q': 'Is the patient responsive and coherent?', 'yes': 'MODERATE (82-90°F) — handle gently, insulate, warm core', 'no': 'SEVERE — continue'},
            {'q': 'Is there a pulse? (check for 60 seconds)', 'yes': 'Handle VERY gently — cardiac irritability. Slow rewarming only', 'no': 'Begin CPR if <60 min cold exposure. "Not dead until warm and dead"'},
        ],
    },
    'snakebite': {
        'title': 'Snakebite Decision Tree (North America)',
        'steps': [
            {'q': 'Was the snake identified as non-venomous?', 'yes': 'Wash wound, tetanus prophylaxis, monitor 8h', 'no': 'Treat as venomous — continue'},
            {'q': 'Are there fang marks + swelling/pain?', 'yes': 'Likely envenomation — immobilize limb, mark swelling border with time', 'no': 'Possible dry bite — still evacuate'},
            {'q': 'Do NOT: tourniquet, cut, suck, ice', 'yes': 'Remove jewelry/tight clothing before swelling', 'no': ''},
            {'q': 'Evacuate to antivenom facility', 'yes': 'Keep calm, minimize movement, carry if possible', 'no': ''},
        ],
    },
}


@health_family_bp.route('/api/medical/wilderness-trees')
def api_wilderness_trees():
    tree = request.args.get('tree', '')
    if tree:
        t = WILDERNESS_TREES.get(tree)
        if not t:
            return jsonify({'error': f'Unknown. Available: {", ".join(sorted(WILDERNESS_TREES.keys()))}'}), 404
        return jsonify(t)
    return jsonify({k: v['title'] for k, v in WILDERNESS_TREES.items()})


@health_family_bp.route('/api/medical/wilderness-trees/<tree_id>')
def api_wilderness_tree_detail(tree_id):
    t = WILDERNESS_TREES.get(tree_id)
    if not t:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(t)


# ═══════════════════════════════════════════════════════════════════
# 7.7 — NCMEC-style Child ID Packet Generator
# ═══════════════════════════════════════════════════════════════════

@health_family_bp.route('/api/family/child-id')
def api_child_id_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT id, name, dob, last_updated FROM child_id_packets ORDER BY name'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@health_family_bp.route('/api/family/child-id', methods=['POST'])
def api_child_id_create():
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO child_id_packets
            (name, dob, height_in, weight_lb, hair_color, eye_color,
             blood_type, allergies, medications, identifying_marks,
             fingerprint_ref, photo_ref, emergency_contacts, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            name,
            data.get('dob', ''),
            data.get('height_in'),
            data.get('weight_lb'),
            data.get('hair_color', ''),
            data.get('eye_color', ''),
            data.get('blood_type', ''),
            data.get('allergies', ''),
            data.get('medications', ''),
            data.get('identifying_marks', ''),
            data.get('fingerprint_ref', ''),
            data.get('photo_ref', ''),
            json.dumps(data.get('emergency_contacts', [])),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM child_id_packets WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('child_id_created', detail=name)
    return jsonify(dict(row)), 201


@health_family_bp.route('/api/family/child-id/<int:cid>', methods=['PUT'])
def api_child_id_update(cid):
    data = request.get_json() or {}
    allowed = ['name', 'dob', 'height_in', 'weight_lb', 'hair_color', 'eye_color',
               'blood_type', 'allergies', 'medications', 'identifying_marks',
               'fingerprint_ref', 'photo_ref', 'notes']
    updates = []
    values = []
    for k in allowed:
        if k in data:
            updates.append(f'{k} = ?')
            values.append(data[k])
    if 'emergency_contacts' in data:
        updates.append('emergency_contacts = ?')
        values.append(json.dumps(data['emergency_contacts']))

    if not updates:
        return jsonify({'error': 'No fields'}), 400

    updates.append("last_updated = datetime('now')")
    values.append(cid)
    with db_session() as db:
        r = db.execute(f"UPDATE child_id_packets SET {', '.join(updates)} WHERE id = ?", values)
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'updated'})


@health_family_bp.route('/api/family/child-id/<int:cid>', methods=['DELETE'])
def api_child_id_delete(cid):
    with db_session() as db:
        r = db.execute('DELETE FROM child_id_packets WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ═══════════════════════════════════════════════════════════════════
# 7.8 — Reunification Cascade
# ═══════════════════════════════════════════════════════════════════

@health_family_bp.route('/api/family/reunification')
def api_reunification():
    with db_session() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE key = 'reunification_plan'"
        ).fetchone()
    if not row:
        return jsonify({'configured': False, 'plan': _default_reunification()})
    try:
        return jsonify({'configured': True, 'plan': json.loads(row['value'])})
    except (json.JSONDecodeError, TypeError):
        return jsonify({'configured': False, 'plan': _default_reunification()})


@health_family_bp.route('/api/family/reunification', methods=['POST'])
def api_reunification_save():
    data = request.get_json() or {}
    plan = {
        'primary_rally': data.get('primary_rally', ''),
        'secondary_rally': data.get('secondary_rally', ''),
        'out_of_area_contact': data.get('out_of_area_contact', ''),
        'communication_schedule': data.get('communication_schedule', ''),
        'code_words': data.get('code_words', {}),
        'cascade_order': data.get('cascade_order', []),
        'meeting_times': data.get('meeting_times', ['08:00', '12:00', '17:00']),
        'duration_days': data.get('duration_days', 7),
        'notes': data.get('notes', ''),
    }

    with db_session() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('reunification_plan', ?)",
            (json.dumps(plan),)
        )
        db.commit()

    log_activity('reunification_plan_saved')
    return jsonify({'status': 'saved', 'plan': plan})


def _default_reunification():
    return {
        'primary_rally': '',
        'secondary_rally': '',
        'out_of_area_contact': '',
        'communication_schedule': 'Check in at 08:00, 12:00, 17:00 daily',
        'code_words': {
            'safe': '',
            'duress': '',
            'evacuating': '',
        },
        'cascade_order': [],
        'meeting_times': ['08:00', '12:00', '17:00'],
        'duration_days': 7,
    }


# ═══════════════════════════════════════════════════════════════════
# 7.10 — Skill-Transfer Ledger
# ═══════════════════════════════════════════════════════════════════

@health_family_bp.route('/api/community/skill-transfers')
def api_skill_transfers():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM skill_transfers ORDER BY created_at DESC LIMIT 200'
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@health_family_bp.route('/api/community/skill-transfers', methods=['POST'])
def api_skill_transfer_create():
    data = request.get_json() or {}
    skill = data.get('skill', '').strip()
    teacher = data.get('teacher', '').strip()
    student = data.get('student', '').strip()

    if not skill or not teacher or not student:
        return jsonify({'error': 'skill, teacher, and student required'}), 400

    with db_session() as db:
        cur = db.execute('''
            INSERT INTO skill_transfers
            (skill, teacher, student, proficiency_before, proficiency_after, hours, method, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            skill, teacher, student,
            data.get('proficiency_before', 'none'),
            data.get('proficiency_after', 'basic'),
            data.get('hours', 0),
            data.get('method', 'hands-on'),
            data.get('notes', ''),
        ))
        db.commit()
        row = db.execute('SELECT * FROM skill_transfers WHERE id = ?', (cur.lastrowid,)).fetchone()

    log_activity('skill_transfer', detail=f'{skill}: {teacher} → {student}')
    return jsonify(dict(row)), 201


@health_family_bp.route('/api/community/skill-transfers/<int:sid>', methods=['DELETE'])
def api_skill_transfer_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM skill_transfers WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@health_family_bp.route('/api/community/bus-factor')
def api_bus_factor():
    """Knowledge bus factor — skills held by only one person."""
    with db_session() as db:
        # From skill_transfers: skills taught to only 1 student
        singles = db.execute('''
            SELECT skill, teacher, COUNT(DISTINCT student) as student_count
            FROM skill_transfers
            GROUP BY skill
            HAVING student_count = 1
        ''').fetchall()

        # From contacts skills
        skill_holders = db.execute('''
            SELECT skills, COUNT(*) as holders
            FROM (SELECT DISTINCT skills FROM contacts WHERE skills != '')
        ''').fetchall()

    return jsonify({
        'single_point_skills': [dict(r) for r in singles],
        'recommendation': 'Cross-train any skill held by only one person',
    })
