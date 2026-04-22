"""Training, Education & Knowledge Preservation routes (Phase 10)."""

import json
import logging
from datetime import datetime, timedelta, date

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.blueprints import get_pagination
from web.utils import coerce_int as _ci, coerce_float as _cf

log = logging.getLogger(__name__)

training_knowledge_bp = Blueprint('training_knowledge', __name__, url_prefix='/api/training')


# ─── Helpers ──────────────────────────────────────────────────────

def _parse_json_col(value, default=None):
    """Safely decode a JSON column."""
    if default is None:
        default = []
    if not value:
        return default
    if isinstance(value, (list, dict)):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _today_str():
    return date.today().isoformat()


def _sm2_update(ease_factor, interval, quality):
    """SM-2 spaced repetition: quality 0-5, returns (new_ease, new_interval)."""
    quality = max(0, min(5, quality))
    new_ease = max(1.3, ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
    if quality < 3:
        new_interval = 1
    elif interval <= 1:
        new_interval = 1
    elif interval == 1:
        new_interval = 6
    else:
        new_interval = round(interval * new_ease)
    return new_ease, new_interval


BUILTIN_DRILLS = [
    {
        'name': 'Structure Fire Response',
        'drill_type': 'fire',
        'description': 'Residential fire evacuation and response drill',
        'phases': [
            {'name': 'Detection & Alert', 'duration_min': 2, 'actions': ['Detect fire/smoke', 'Sound alarm', 'Alert all occupants'], 'injects': []},
            {'name': 'Evacuation', 'duration_min': 5, 'actions': ['Account for all persons', 'Grab go-bags if safe', 'Exit via planned routes', 'Assist mobility-limited'], 'injects': ['Primary exit blocked']},
            {'name': 'Assembly & Accountability', 'duration_min': 3, 'actions': ['Rally at designated point', 'Head count', 'Report missing persons'], 'injects': []},
            {'name': 'Fire Suppression (optional)', 'duration_min': 5, 'actions': ['Assess if safe to fight', 'Deploy extinguisher', 'Establish water supply'], 'injects': ['Extinguisher empty']},
            {'name': 'After Action', 'duration_min': 10, 'actions': ['Debrief participants', 'Document timeline', 'Identify improvements'], 'injects': []}
        ],
        'grading_criteria': ['Evacuation time under 3 min', 'All persons accounted for', 'Go-bags retrieved', 'Communication clear', 'No re-entry without clearance'],
        'estimated_duration_minutes': 25,
        'personnel_required': 2,
        'equipment_needed': 'Fire extinguisher, stopwatch, accountability roster'
    },
    {
        'name': 'Security Lockdown',
        'drill_type': 'lockdown',
        'description': 'Perimeter security lockdown and threat response',
        'phases': [
            {'name': 'Threat Detection', 'duration_min': 2, 'actions': ['Identify threat type/direction', 'Sound lockdown signal', 'Establish comms'], 'injects': []},
            {'name': 'Secure Perimeter', 'duration_min': 5, 'actions': ['Lock all entry points', 'Close shutters/blinds', 'Arm defensive positions', 'Account for all persons'], 'injects': ['One entry point won\'t secure']},
            {'name': 'Observe & Report', 'duration_min': 10, 'actions': ['Monitor cameras/windows', 'Maintain radio discipline', 'Log observations'], 'injects': ['Unknown vehicle approaches']},
            {'name': 'Stand Down', 'duration_min': 3, 'actions': ['All clear signal', 'Systematic unlock', 'Debrief'], 'injects': []}
        ],
        'grading_criteria': ['Lockdown achieved under 5 min', 'All entry points secured', 'Comms maintained throughout', 'Proper observation protocol', 'Clean stand-down procedure'],
        'estimated_duration_minutes': 20,
        'personnel_required': 3,
        'equipment_needed': 'Radios, locks, observation equipment, stopwatch'
    },
    {
        'name': 'Mass Casualty Response',
        'drill_type': 'medical',
        'description': 'Multi-patient triage and treatment drill',
        'phases': [
            {'name': 'Scene Size-up', 'duration_min': 2, 'actions': ['Assess scene safety', 'Estimate patient count', 'Call for resources', 'Designate triage officer'], 'injects': []},
            {'name': 'Triage (START)', 'duration_min': 10, 'actions': ['RPM assessment all patients', 'Tag and categorize', 'Move walking wounded'], 'injects': ['Patient deteriorates during triage']},
            {'name': 'Treatment', 'duration_min': 15, 'actions': ['Treat immediate (red) first', 'Control hemorrhage', 'Maintain airways', 'Reassess delayed (yellow)'], 'injects': ['Supply shortage \u2014 improvise']},
            {'name': 'Transport/Evacuation', 'duration_min': 5, 'actions': ['Prioritize transport order', 'Document patient handoff', 'Track destination'], 'injects': []},
            {'name': 'After Action', 'duration_min': 10, 'actions': ['Review triage accuracy', 'Assess treatment times', 'Document lessons learned'], 'injects': []}
        ],
        'grading_criteria': ['Correct triage categories assigned', 'Hemorrhage controlled within 2 min', 'No immediate (red) patients untreated > 5 min', 'Proper patient tracking', 'Supply management'],
        'estimated_duration_minutes': 42,
        'personnel_required': 4,
        'equipment_needed': 'Triage tags, medical supplies, stretchers, patient tracking forms'
    },
    {
        'name': 'Communications Failure',
        'drill_type': 'comms_failure',
        'description': 'Respond to total communications infrastructure failure',
        'phases': [
            {'name': 'Detection', 'duration_min': 2, 'actions': ['Identify comms failure scope', 'Attempt all backup channels', 'Activate PACE plan'], 'injects': []},
            {'name': 'Alternate Comms', 'duration_min': 10, 'actions': ['Deploy backup radio', 'Establish visual signals', 'Send runner if needed', 'Test mesh network'], 'injects': ['Backup radio battery dead']},
            {'name': 'Information Relay', 'duration_min': 10, 'actions': ['Transmit critical message via alternate', 'Confirm receipt', 'Establish schedule'], 'injects': ['Message garbled \u2014 retransmit']},
            {'name': 'Recovery', 'duration_min': 5, 'actions': ['Restore primary comms', 'Sync information gaps', 'Document timeline'], 'injects': []}
        ],
        'grading_criteria': ['PACE plan activated within 3 min', 'Alternate comms established within 10 min', 'Critical message delivered accurately', 'All stations contacted', 'Proper radio procedure maintained'],
        'estimated_duration_minutes': 27,
        'personnel_required': 3,
        'equipment_needed': 'Primary and backup radios, signal flags/panels, PACE plan reference card'
    }
]


# ═══════════════════════════════════════════════════════════════════
# SKILL TREES
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/skills')
def api_skills_list():
    with db_session() as db:
        clauses, params = [], []
        person = request.args.get('person', '').strip()
        category = request.args.get('category', '').strip()
        if person:
            clauses.append('person_name LIKE ?')
            params.append(f'%{person}%')
        if category:
            clauses.append('category = ?')
            params.append(category)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = db.execute(f'SELECT * FROM skill_trees{where} ORDER BY category, skill_name', params).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['prerequisites'] = _parse_json_col(entry.get('prerequisites'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/skills/<int:sid>')
def api_skills_get(sid):
    with db_session() as db:
        row = db.execute('SELECT * FROM skill_trees WHERE id = ?', (sid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    entry = dict(row)
    entry['prerequisites'] = _parse_json_col(entry.get('prerequisites'))
    return jsonify(entry)


@training_knowledge_bp.route('/skills', methods=['POST'])
def api_skills_create():
    data = request.get_json() or {}
    if not data.get('person_name') or not data.get('skill_name'):
        return jsonify({'error': 'person_name and skill_name required'}), 400
    level = max(1, min(5, _ci(data.get('level', 1), 1, minimum=1, maximum=5)))
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO skill_trees (person_name, skill_name, category, level, prerequisites,
               certified, certified_date, instructor, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['person_name'], data['skill_name'], data.get('category', ''),
             level, json.dumps(data.get('prerequisites', [])),
             1 if data.get('certified') else 0, data.get('certified_date', ''),
             data.get('instructor', ''), data.get('notes', '')))
        db.commit()
        sid = cur.lastrowid
    log_activity('skill_created', service='training', detail=f'{data["person_name"]}: {data["skill_name"]}')
    return jsonify({'id': sid, 'status': 'created'}), 201


@training_knowledge_bp.route('/skills/<int:sid>', methods=['PUT'])
def api_skills_update(sid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM skill_trees WHERE id = ?', (sid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('person_name', 'skill_name', 'category', 'instructor', 'notes', 'certified_date'):
            if col in data:
                fields[col] = data[col]
        if 'level' in data:
            fields['level'] = max(1, min(5, int(data['level'])))
        if 'certified' in data:
            fields['certified'] = 1 if data['certified'] else 0
        if 'prerequisites' in data:
            fields['prerequisites'] = json.dumps(data['prerequisites'])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [sid]
        db.execute(f'UPDATE skill_trees SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    log_activity('skill_updated', service='training', detail=f'Skill {sid}')
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/skills/<int:sid>', methods=['DELETE'])
def api_skills_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM skill_trees WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    log_activity('skill_deleted', service='training', detail=f'Skill {sid}')
    return jsonify({'status': 'deleted'})


@training_knowledge_bp.route('/skills/matrix')
def api_skills_matrix():
    """Cross-training matrix: per skill/category who can do it and at what level.
    Highlights single points of failure (skills held by only 1 person)."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM skill_trees ORDER BY category, skill_name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    matrix = {}
    for r in rows:
        key = r['skill_name']
        if key not in matrix:
            matrix[key] = {'skill_name': key, 'category': r['category'], 'holders': []}
        matrix[key]['holders'].append({
            'person_name': r['person_name'],
            'level': r['level'],
            'certified': bool(r['certified']),
        })
    result = []
    spof = []
    for skill_name, info in matrix.items():
        info['holder_count'] = len(info['holders'])
        if info['holder_count'] == 1:
            spof.append({'skill_name': skill_name, 'category': info['category'],
                         'sole_holder': info['holders'][0]['person_name']})
        result.append(info)
    return jsonify({'matrix': result, 'single_points_of_failure': spof})


@training_knowledge_bp.route('/skills/summary')
def api_skills_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM skill_trees').fetchone()['c']
        by_category = db.execute(
            'SELECT category, COUNT(*) as c FROM skill_trees GROUP BY category ORDER BY c DESC').fetchall()
        certified = db.execute('SELECT COUNT(*) as c FROM skill_trees WHERE certified = 1').fetchone()['c']
        unique_people = db.execute('SELECT COUNT(DISTINCT person_name) as c FROM skill_trees').fetchone()['c']
    return jsonify({
        'total_skills': total,
        'certified': certified,
        'uncertified': total - certified,
        'unique_people': unique_people,
        'by_category': [dict(r) for r in by_category],
    })


# ═══════════════════════════════════════════════════════════════════
# TRAINING COURSES
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/courses')
def api_courses_list():
    with db_session() as db:
        status = request.args.get('status', '').strip()
        if status:
            rows = db.execute('SELECT * FROM training_courses WHERE status = ? ORDER BY title', (status,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM training_courses ORDER BY title LIMIT ? OFFSET ?', get_pagination()).fetchall()
    return jsonify([dict(r) for r in rows])


@training_knowledge_bp.route('/courses/<int:cid>')
def api_courses_get(cid):
    with db_session() as db:
        course = db.execute('SELECT * FROM training_courses WHERE id = ?', (cid,)).fetchone()
        if not course:
            return jsonify({'error': 'Not found'}), 404
        lessons = db.execute(
            'SELECT * FROM training_lessons WHERE course_id = ? ORDER BY lesson_number', (cid,)).fetchall()
    result = dict(course)
    lesson_list = []
    for l in lessons:
        entry = dict(l)
        entry['objectives'] = _parse_json_col(entry.get('objectives'))
        entry['completed_by'] = _parse_json_col(entry.get('completed_by'))
        lesson_list.append(entry)
    result['lessons'] = lesson_list
    return jsonify(result)


@training_knowledge_bp.route('/courses', methods=['POST'])
def api_courses_create():
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({'error': 'title required'}), 400
    status = data.get('status', 'draft')
    if status not in ('draft', 'active', 'archived'):
        status = 'draft'
    difficulty = data.get('difficulty', 'beginner')
    if difficulty not in ('beginner', 'intermediate', 'advanced', 'expert'):
        difficulty = 'beginner'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO training_courses (title, description, category, difficulty, estimated_hours,
               instructor, max_students, prerequisites_text, materials_needed, status)
               VALUES (?,?,?,?,?,?,?,?,?,?)''',
            (data['title'], data.get('description', ''), data.get('category', ''),
             difficulty, _cf(data.get('estimated_hours', 0), 0.0, minimum=0.0),
             data.get('instructor', ''), _ci(data.get('max_students', 0), 0, minimum=0),
             data.get('prerequisites_text', ''), data.get('materials_needed', ''), status))
        db.commit()
        cid = cur.lastrowid
    log_activity('course_created', service='training', detail=f'Course: {data["title"]}')
    return jsonify({'id': cid, 'status': 'created'}), 201


@training_knowledge_bp.route('/courses/<int:cid>', methods=['PUT'])
def api_courses_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM training_courses WHERE id = ?', (cid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('title', 'description', 'category', 'instructor', 'prerequisites_text', 'materials_needed'):
            if col in data:
                fields[col] = data[col]
        if 'difficulty' in data and data['difficulty'] in ('beginner', 'intermediate', 'advanced', 'expert'):
            fields['difficulty'] = data['difficulty']
        if 'status' in data and data['status'] in ('draft', 'active', 'archived'):
            fields['status'] = data['status']
        if 'estimated_hours' in data:
            fields['estimated_hours'] = float(data['estimated_hours'])
        if 'max_students' in data:
            fields['max_students'] = int(data['max_students'])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [cid]
        db.execute(f'UPDATE training_courses SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    log_activity('course_updated', service='training', detail=f'Course {cid}')
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/courses/<int:cid>', methods=['DELETE'])
def api_courses_delete(cid):
    with db_session() as db:
        db.execute('DELETE FROM training_lessons WHERE course_id = ?', (cid,))
        r = db.execute('DELETE FROM training_courses WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    log_activity('course_deleted', service='training', detail=f'Course {cid} and its lessons')
    return jsonify({'status': 'deleted'})


@training_knowledge_bp.route('/courses/<int:cid>/progress')
def api_courses_progress(cid):
    """Completion % based on completed_by in lessons."""
    with db_session() as db:
        course = db.execute('SELECT * FROM training_courses WHERE id = ?', (cid,)).fetchone()
        if not course:
            return jsonify({'error': 'Not found'}), 404
        lessons = db.execute(
            'SELECT * FROM training_lessons WHERE course_id = ? ORDER BY lesson_number', (cid,)).fetchall()
    if not lessons:
        return jsonify({'course_id': cid, 'total_lessons': 0, 'progress': []})
    # Collect all unique participants
    all_people = set()
    lesson_completions = []
    for l in lessons:
        completed = _parse_json_col(l['completed_by'])
        all_people.update(completed)
        lesson_completions.append({
            'lesson_id': l['id'], 'lesson_number': l['lesson_number'],
            'title': l['title'], 'completed_by': completed,
        })
    progress = []
    for person in sorted(all_people):
        completed_count = sum(1 for lc in lesson_completions if person in lc['completed_by'])
        progress.append({
            'person_name': person,
            'completed': completed_count,
            'total': len(lessons),
            'percent': round(completed_count / len(lessons) * 100, 1),
        })
    return jsonify({
        'course_id': cid, 'total_lessons': len(lessons),
        'lesson_completions': lesson_completions, 'progress': progress,
    })


# ═══════════════════════════════════════════════════════════════════
# TRAINING LESSONS
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/courses/<int:cid>/lessons')
def api_lessons_list(cid):
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM training_lessons WHERE course_id = ? ORDER BY lesson_number', (cid,)).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['objectives'] = _parse_json_col(entry.get('objectives'))
        entry['completed_by'] = _parse_json_col(entry.get('completed_by'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/courses/<int:cid>/lessons', methods=['POST'])
def api_lessons_create(cid):
    data = request.get_json() or {}
    if not data.get('title'):
        return jsonify({'error': 'title required'}), 400
    lesson_type = data.get('lesson_type', 'lecture')
    if lesson_type not in ('lecture', 'practical', 'assessment', 'field'):
        lesson_type = 'lecture'
    with db_session() as db:
        if not db.execute('SELECT 1 FROM training_courses WHERE id = ?', (cid,)).fetchone():
            return jsonify({'error': 'Course not found'}), 404
        # Auto-assign lesson_number if not given
        lesson_number = data.get('lesson_number')
        if lesson_number is None:
            last = db.execute(
                'SELECT MAX(lesson_number) as mx FROM training_lessons WHERE course_id = ?', (cid,)).fetchone()
            lesson_number = (last['mx'] or 0) + 1
        cur = db.execute(
            '''INSERT INTO training_lessons (course_id, lesson_number, title, content,
               duration_minutes, lesson_type, materials, objectives, completed_by)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (cid, int(lesson_number), data['title'], data.get('content', ''),
             _ci(data.get('duration_minutes', 0), 0, minimum=0), lesson_type,
             data.get('materials', ''), json.dumps(data.get('objectives', [])),
             json.dumps(data.get('completed_by', []))))
        db.commit()
        lid = cur.lastrowid
    log_activity('lesson_created', service='training', detail=f'Lesson "{data["title"]}" in course {cid}')
    return jsonify({'id': lid, 'status': 'created'}), 201


@training_knowledge_bp.route('/lessons/<int:lid>', methods=['PUT'])
def api_lessons_update(lid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM training_lessons WHERE id = ?', (lid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('title', 'content', 'materials'):
            if col in data:
                fields[col] = data[col]
        if 'lesson_number' in data:
            fields['lesson_number'] = int(data['lesson_number'])
        if 'duration_minutes' in data:
            fields['duration_minutes'] = int(data['duration_minutes'])
        if 'lesson_type' in data and data['lesson_type'] in ('lecture', 'practical', 'assessment', 'field'):
            fields['lesson_type'] = data['lesson_type']
        if 'objectives' in data:
            fields['objectives'] = json.dumps(data['objectives'])
        if 'completed_by' in data:
            fields['completed_by'] = json.dumps(data['completed_by'])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [lid]
        db.execute(f'UPDATE training_lessons SET {set_clause} WHERE id = ?', vals)
        db.commit()
    log_activity('lesson_updated', service='training', detail=f'Lesson {lid}')
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/lessons/<int:lid>/complete', methods=['POST'])
def api_lessons_complete(lid):
    """Mark a person as completed for a lesson (add to completed_by JSON)."""
    data = request.get_json() or {}
    person = (data.get('person_name') or '').strip()
    if not person:
        return jsonify({'error': 'person_name required'}), 400
    with db_session() as db:
        row = db.execute('SELECT completed_by FROM training_lessons WHERE id = ?', (lid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        completed = _parse_json_col(row['completed_by'])
        if person not in completed:
            completed.append(person)
            db.execute('UPDATE training_lessons SET completed_by = ? WHERE id = ?',
                       (json.dumps(completed), lid))
            db.commit()
    log_activity('lesson_completed', service='training', detail=f'{person} completed lesson {lid}')
    return jsonify({'status': 'completed', 'completed_by': completed})


# ═══════════════════════════════════════════════════════════════════
# CERTIFICATIONS
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/certifications')
def api_certifications_list():
    with db_session() as db:
        clauses, params = [], []
        person = request.args.get('person', '').strip()
        status = request.args.get('status', '').strip()
        if person:
            clauses.append('person_name LIKE ?')
            params.append(f'%{person}%')
        if status:
            clauses.append('status = ?')
            params.append(status)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = db.execute(f'SELECT * FROM certifications{where} ORDER BY person_name, certification_name', params).fetchall()
    return jsonify([dict(r) for r in rows])


@training_knowledge_bp.route('/certifications', methods=['POST'])
def api_certifications_create():
    data = request.get_json() or {}
    if not data.get('person_name') or not data.get('certification_name'):
        return jsonify({'error': 'person_name and certification_name required'}), 400
    status = data.get('status', 'active')
    if status not in ('active', 'expired', 'revoked'):
        status = 'active'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO certifications (person_name, certification_name, issuing_authority,
               date_earned, expiration_date, renewal_interval_days, status, document_ref, notes)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['person_name'], data['certification_name'],
             data.get('issuing_authority', ''), data.get('date_earned', ''),
             data.get('expiration_date', ''), _ci(data.get('renewal_interval_days', 0), 0, minimum=0),
             status, data.get('document_ref', ''), data.get('notes', '')))
        db.commit()
        cid = cur.lastrowid
    log_activity('certification_created', service='training',
                 detail=f'{data["person_name"]}: {data["certification_name"]}')
    return jsonify({'id': cid, 'status': 'created'}), 201


@training_knowledge_bp.route('/certifications/<int:cid>', methods=['PUT'])
def api_certifications_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM certifications WHERE id = ?', (cid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('person_name', 'certification_name', 'issuing_authority', 'date_earned',
                     'expiration_date', 'document_ref', 'notes'):
            if col in data:
                fields[col] = data[col]
        if 'renewal_interval_days' in data:
            fields['renewal_interval_days'] = int(data['renewal_interval_days'])
        if 'status' in data and data['status'] in ('active', 'expired', 'revoked'):
            fields['status'] = data['status']
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [cid]
        db.execute(f'UPDATE certifications SET {set_clause} WHERE id = ?', vals)
        db.commit()
    log_activity('certification_updated', service='training', detail=f'Cert {cid}')
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/certifications/<int:cid>', methods=['DELETE'])
def api_certifications_delete(cid):
    with db_session() as db:
        r = db.execute('DELETE FROM certifications WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    log_activity('certification_deleted', service='training', detail=f'Cert {cid}')
    return jsonify({'status': 'deleted'})


@training_knowledge_bp.route('/certifications/expiring')
def api_certifications_expiring():
    """Certs expiring within N days (default 30)."""
    try:
        days = int(request.args.get('days', 30))
    except (ValueError, TypeError):
        days = 30
    cutoff = (date.today() + timedelta(days=days)).isoformat()
    today_str = _today_str()
    with db_session() as db:
        rows = db.execute(
            '''SELECT * FROM certifications
               WHERE expiration_date != '' AND expiration_date IS NOT NULL
                 AND expiration_date <= ? AND expiration_date >= ?
                 AND status = 'active'
               ORDER BY expiration_date''',
            (cutoff, today_str)).fetchall()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════
# DRILL TEMPLATES & RESULTS
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/drills/templates')
def api_drill_templates_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM drill_templates ORDER BY name LIMIT ? OFFSET ?', get_pagination()).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['phases'] = _parse_json_col(entry.get('phases'))
        entry['grading_criteria'] = _parse_json_col(entry.get('grading_criteria'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/drills/templates', methods=['POST'])
def api_drill_templates_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'name required'}), 400
    drill_type = data.get('drill_type', 'custom')
    if drill_type not in ('fire', 'lockdown', 'medical', 'comms_failure', 'evacuation', 'shelter', 'custom'):
        drill_type = 'custom'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO drill_templates (name, drill_type, description, phases, grading_criteria,
               estimated_duration_minutes, personnel_required, equipment_needed, is_builtin)
               VALUES (?,?,?,?,?,?,?,?,?)''',
            (data['name'], drill_type, data.get('description', ''),
             json.dumps(data.get('phases', [])), json.dumps(data.get('grading_criteria', [])),
             _ci(data.get('estimated_duration_minutes', 0), 0, minimum=0),
             _ci(data.get('personnel_required', 0), 0, minimum=0),
             data.get('equipment_needed', ''), 0))
        db.commit()
        tid = cur.lastrowid
    log_activity('drill_template_created', service='training', detail=f'Template: {data["name"]}')
    return jsonify({'id': tid, 'status': 'created'}), 201


@training_knowledge_bp.route('/drills/templates/<int:tid>', methods=['PUT'])
def api_drill_templates_update(tid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM drill_templates WHERE id = ?', (tid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('name', 'description', 'equipment_needed'):
            if col in data:
                fields[col] = data[col]
        if 'drill_type' in data and data['drill_type'] in ('fire', 'lockdown', 'medical', 'comms_failure', 'evacuation', 'shelter', 'custom'):
            fields['drill_type'] = data['drill_type']
        if 'phases' in data:
            fields['phases'] = json.dumps(data['phases'])
        if 'grading_criteria' in data:
            fields['grading_criteria'] = json.dumps(data['grading_criteria'])
        if 'estimated_duration_minutes' in data:
            fields['estimated_duration_minutes'] = int(data['estimated_duration_minutes'])
        if 'personnel_required' in data:
            fields['personnel_required'] = int(data['personnel_required'])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [tid]
        db.execute(f'UPDATE drill_templates SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    log_activity('drill_template_updated', service='training', detail=f'Template {tid}')
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/drills/templates/seed', methods=['POST'])
def api_drill_templates_seed():
    """Seed 4 built-in drill templates. Skips any that already exist by name."""
    created = []
    with db_session() as db:
        for tmpl in BUILTIN_DRILLS:
            exists = db.execute('SELECT 1 FROM drill_templates WHERE name = ?', (tmpl['name'],)).fetchone()
            if exists:
                continue
            db.execute(
                '''INSERT INTO drill_templates (name, drill_type, description, phases, grading_criteria,
                   estimated_duration_minutes, personnel_required, equipment_needed, is_builtin)
                   VALUES (?,?,?,?,?,?,?,?,1)''',
                (tmpl['name'], tmpl['drill_type'], tmpl['description'],
                 json.dumps(tmpl['phases']), json.dumps(tmpl['grading_criteria']),
                 tmpl['estimated_duration_minutes'], tmpl['personnel_required'],
                 tmpl['equipment_needed']))
            created.append(tmpl['name'])
        db.commit()
    if created:
        log_activity('drill_templates_seeded', service='training',
                     detail=f'Seeded {len(created)} templates: {", ".join(created)}')
    return jsonify({'status': 'seeded', 'created': created, 'count': len(created)})


@training_knowledge_bp.route('/drills/run', methods=['POST'])
def api_drill_run():
    """Start a drill: create a drill_result from a template."""
    data = request.get_json() or {}
    template_id = data.get('template_id')
    if not template_id:
        return jsonify({'error': 'template_id required'}), 400
    with db_session() as db:
        tmpl = db.execute('SELECT * FROM drill_templates WHERE id = ?', (template_id,)).fetchone()
        if not tmpl:
            return jsonify({'error': 'Template not found'}), 404
        cur = db.execute(
            '''INSERT INTO drill_results (template_id, drill_date, participants, overall_grade,
               phase_scores, deficiencies, strengths, aar_notes, corrective_actions,
               next_drill_date, conducted_by, is_no_notice)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (template_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
             json.dumps(data.get('participants', [])), '',
             json.dumps({}), json.dumps([]), json.dumps([]),
             '', '', data.get('next_drill_date', ''),
             data.get('conducted_by', ''),
             1 if data.get('is_no_notice') else 0))
        db.commit()
        rid = cur.lastrowid
    log_activity('drill_started', service='training', detail=f'Drill from template {template_id}')
    return jsonify({'id': rid, 'status': 'started', 'template_name': tmpl['name']}), 201


@training_knowledge_bp.route('/drills/results')
def api_drill_results_list():
    with db_session() as db:
        template_id = request.args.get('template_id', '').strip()
        if template_id:
            rows = db.execute(
                '''SELECT dr.*, dt.name as template_name, dt.drill_type
                   FROM drill_results dr LEFT JOIN drill_templates dt ON dr.template_id = dt.id
                   WHERE dr.template_id = ? ORDER BY dr.drill_date DESC''',
                (int(template_id),)).fetchall()
        else:
            rows = db.execute(
                '''SELECT dr.*, dt.name as template_name, dt.drill_type
                   FROM drill_results dr LEFT JOIN drill_templates dt ON dr.template_id = dt.id
                   ORDER BY dr.drill_date DESC''').fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['participants'] = _parse_json_col(entry.get('participants'))
        entry['phase_scores'] = _parse_json_col(entry.get('phase_scores'), {})
        entry['deficiencies'] = _parse_json_col(entry.get('deficiencies'))
        entry['strengths'] = _parse_json_col(entry.get('strengths'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/drills/results/<int:rid>')
def api_drill_results_get(rid):
    with db_session() as db:
        row = db.execute(
            '''SELECT dr.*, dt.name as template_name, dt.drill_type, dt.phases as template_phases,
                      dt.grading_criteria as template_grading
               FROM drill_results dr LEFT JOIN drill_templates dt ON dr.template_id = dt.id
               WHERE dr.id = ?''', (rid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    entry = dict(row)
    entry['participants'] = _parse_json_col(entry.get('participants'))
    entry['phase_scores'] = _parse_json_col(entry.get('phase_scores'), {})
    entry['deficiencies'] = _parse_json_col(entry.get('deficiencies'))
    entry['strengths'] = _parse_json_col(entry.get('strengths'))
    entry['template_phases'] = _parse_json_col(entry.get('template_phases'))
    entry['template_grading'] = _parse_json_col(entry.get('template_grading'))
    return jsonify(entry)


@training_knowledge_bp.route('/drills/results/<int:rid>', methods=['PUT'])
def api_drill_results_update(rid):
    """Update drill result: grade, AAR, deficiencies, etc."""
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM drill_results WHERE id = ?', (rid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('overall_grade', 'aar_notes', 'corrective_actions', 'next_drill_date', 'conducted_by'):
            if col in data:
                fields[col] = data[col]
        if 'participants' in data:
            fields['participants'] = json.dumps(data['participants'])
        if 'phase_scores' in data:
            fields['phase_scores'] = json.dumps(data['phase_scores'])
        if 'deficiencies' in data:
            fields['deficiencies'] = json.dumps(data['deficiencies'])
        if 'strengths' in data:
            fields['strengths'] = json.dumps(data['strengths'])
        if 'is_no_notice' in data:
            fields['is_no_notice'] = 1 if data['is_no_notice'] else 0
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [rid]
        db.execute(f'UPDATE drill_results SET {set_clause} WHERE id = ?', vals)
        db.commit()
    log_activity('drill_result_updated', service='training', detail=f'Drill result {rid}')
    return jsonify({'status': 'updated'})


# ═══════════════════════════════════════════════════════════════════
# FLASHCARDS
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/flashcards')
def api_flashcards_list():
    with db_session() as db:
        clauses, params = [], []
        deck = request.args.get('deck', '').strip()
        category = request.args.get('category', '').strip()
        if deck:
            clauses.append('deck_name = ?')
            params.append(deck)
        if category:
            clauses.append('category = ?')
            params.append(category)
        where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        rows = db.execute(f'SELECT * FROM flashcards{where} ORDER BY deck_name, id', params).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['tags'] = _parse_json_col(entry.get('tags'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/flashcards', methods=['POST'])
def api_flashcards_create():
    data = request.get_json() or {}
    if not data.get('front_text') or not data.get('back_text'):
        return jsonify({'error': 'front_text and back_text required'}), 400
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO flashcards (deck_name, category, front_text, back_text, difficulty,
               interval_days, ease_factor, next_review, review_count, correct_count,
               last_reviewed, tags)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('deck_name', 'Default'), data.get('category', ''),
             data['front_text'], data['back_text'],
             max(1, min(5, _ci(data.get('difficulty', 1), 1, minimum=1, maximum=5))),
             _ci(data.get('interval_days', 1), 1, minimum=1), _cf(data.get('ease_factor', 2.5), 2.5),
             data.get('next_review', _today_str()),
             0, 0, None, json.dumps(data.get('tags', []))))
        db.commit()
        fid = cur.lastrowid
    log_activity('flashcard_created', service='training', detail=f'Card in deck "{data.get("deck_name", "Default")}"')
    return jsonify({'id': fid, 'status': 'created'}), 201


@training_knowledge_bp.route('/flashcards/<int:fid>', methods=['PUT'])
def api_flashcards_update(fid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM flashcards WHERE id = ?', (fid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('deck_name', 'category', 'front_text', 'back_text', 'next_review'):
            if col in data:
                fields[col] = data[col]
        if 'difficulty' in data:
            fields['difficulty'] = max(1, min(5, int(data['difficulty'])))
        if 'tags' in data:
            fields['tags'] = json.dumps(data['tags'])
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [fid]
        db.execute(f'UPDATE flashcards SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/flashcards/<int:fid>', methods=['DELETE'])
def api_flashcards_delete(fid):
    with db_session() as db:
        r = db.execute('DELETE FROM flashcards WHERE id = ?', (fid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@training_knowledge_bp.route('/flashcards/<int:fid>/review', methods=['POST'])
def api_flashcards_review(fid):
    """SM-2 spaced repetition review. Accepts {quality: 0-5}."""
    data = request.get_json() or {}
    try:
        quality = int(data.get('quality', 0))
    except (ValueError, TypeError):
        quality = 0
    quality = max(0, min(5, quality))
    with db_session() as db:
        row = db.execute('SELECT * FROM flashcards WHERE id = ?', (fid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        ease = float(row['ease_factor'] or 2.5)
        interval = int(row['interval_days'] or 1)
        review_count = int(row['review_count'] or 0) + 1
        correct_count = int(row['correct_count'] or 0) + (1 if quality >= 3 else 0)
        new_ease, new_interval = _sm2_update(ease, interval, quality)
        next_review = (date.today() + timedelta(days=new_interval)).isoformat()
        db.execute(
            '''UPDATE flashcards SET ease_factor = ?, interval_days = ?, next_review = ?,
               review_count = ?, correct_count = ?, last_reviewed = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (new_ease, new_interval, next_review, review_count, correct_count, _today_str(), fid))
        db.commit()
    return jsonify({
        'status': 'reviewed', 'quality': quality,
        'new_ease_factor': round(new_ease, 2), 'new_interval_days': new_interval,
        'next_review': next_review, 'review_count': review_count, 'correct_count': correct_count,
    })


@training_knowledge_bp.route('/flashcards/due')
def api_flashcards_due():
    """Cards due for review (next_review <= today)."""
    today = _today_str()
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM flashcards WHERE next_review <= ? ORDER BY next_review, id', (today,)).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['tags'] = _parse_json_col(entry.get('tags'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/flashcards/decks')
def api_flashcards_decks():
    """List distinct deck names with counts."""
    with db_session() as db:
        rows = db.execute(
            'SELECT deck_name, COUNT(*) as card_count FROM flashcards GROUP BY deck_name ORDER BY deck_name').fetchall()
    return jsonify([dict(r) for r in rows])


# ═══════════════════════════════════════════════════════════════════
# KNOWLEDGE PACKAGES
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/knowledge-packages')
def api_knowledge_packages_list():
    with db_session() as db:
        person = request.args.get('person', '').strip()
        if person:
            rows = db.execute(
                'SELECT * FROM knowledge_packages WHERE person_name LIKE ? ORDER BY person_name, title',
                (f'%{person}%',)).fetchall()
        else:
            rows = db.execute('SELECT * FROM knowledge_packages ORDER BY person_name, title LIMIT ? OFFSET ?', get_pagination()).fetchall()
    result = []
    for r in rows:
        entry = dict(r)
        entry['skills_documented'] = _parse_json_col(entry.get('skills_documented'))
        entry['procedures'] = _parse_json_col(entry.get('procedures'))
        entry['contacts_referenced'] = _parse_json_col(entry.get('contacts_referenced'))
        result.append(entry)
    return jsonify(result)


@training_knowledge_bp.route('/knowledge-packages', methods=['POST'])
def api_knowledge_packages_create():
    data = request.get_json() or {}
    if not data.get('person_name') or not data.get('title'):
        return jsonify({'error': 'person_name and title required'}), 400
    status = data.get('status', 'draft')
    if status not in ('draft', 'active', 'archived'):
        status = 'draft'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO knowledge_packages (person_name, title, description, category,
               skills_documented, procedures, contacts_referenced, critical_knowledge,
               contingency_plans, last_reviewed, review_interval_days, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data['person_name'], data['title'], data.get('description', ''),
             data.get('category', ''),
             json.dumps(data.get('skills_documented', [])),
             json.dumps(data.get('procedures', [])),
             json.dumps(data.get('contacts_referenced', [])),
             data.get('critical_knowledge', ''), data.get('contingency_plans', ''),
             data.get('last_reviewed', ''),
             _ci(data.get('review_interval_days', 90), 90, minimum=1), status))
        db.commit()
        kid = cur.lastrowid
    log_activity('knowledge_package_created', service='training',
                 detail=f'{data["person_name"]}: {data["title"]}')
    return jsonify({'id': kid, 'status': 'created'}), 201


@training_knowledge_bp.route('/knowledge-packages/<int:kid>', methods=['PUT'])
def api_knowledge_packages_update(kid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM knowledge_packages WHERE id = ?', (kid,)).fetchone():
            return jsonify({'error': 'Not found'}), 404
        fields = {}
        for col in ('person_name', 'title', 'description', 'category', 'critical_knowledge',
                     'contingency_plans', 'last_reviewed'):
            if col in data:
                fields[col] = data[col]
        if 'skills_documented' in data:
            fields['skills_documented'] = json.dumps(data['skills_documented'])
        if 'procedures' in data:
            fields['procedures'] = json.dumps(data['procedures'])
        if 'contacts_referenced' in data:
            fields['contacts_referenced'] = json.dumps(data['contacts_referenced'])
        if 'review_interval_days' in data:
            fields['review_interval_days'] = int(data['review_interval_days'])
        if 'status' in data and data['status'] in ('draft', 'active', 'archived'):
            fields['status'] = data['status']
        if not fields:
            return jsonify({'error': 'No fields to update'}), 400
        set_clause = ', '.join(f'{k} = ?' for k in fields)
        vals = list(fields.values()) + [kid]
        db.execute(f'UPDATE knowledge_packages SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    log_activity('knowledge_package_updated', service='training', detail=f'Package {kid}')
    return jsonify({'status': 'updated'})


@training_knowledge_bp.route('/knowledge-packages/<int:kid>', methods=['DELETE'])
def api_knowledge_packages_delete(kid):
    with db_session() as db:
        r = db.execute('DELETE FROM knowledge_packages WHERE id = ?', (kid,))
        if r.rowcount == 0:
            return jsonify({'error': 'Not found'}), 404
        db.commit()
    log_activity('knowledge_package_deleted', service='training', detail=f'Package {kid}')
    return jsonify({'status': 'deleted'})


@training_knowledge_bp.route('/knowledge-packages/bus-factor')
def api_knowledge_packages_bus_factor():
    """For each skill/category, count how many packages document it. Highlight gaps."""
    with db_session() as db:
        packages = db.execute('SELECT * FROM knowledge_packages WHERE status != "archived"').fetchall()
        skills = db.execute('SELECT DISTINCT skill_name, category FROM skill_trees ORDER BY category, skill_name').fetchall()
    # Build coverage map: skill -> list of people who documented it
    coverage = {}
    for pkg in packages:
        documented = _parse_json_col(pkg['skills_documented'])
        for skill in documented:
            if skill not in coverage:
                coverage[skill] = []
            coverage[skill].append(pkg['person_name'])
    # Check each known skill
    result = []
    gaps = []
    for s in skills:
        name = s['skill_name']
        holders = coverage.get(name, [])
        entry = {'skill_name': name, 'category': s['category'],
                 'documented_by': holders, 'package_count': len(holders)}
        result.append(entry)
        if len(holders) == 0:
            gaps.append({'skill_name': name, 'category': s['category']})
    return jsonify({'coverage': result, 'undocumented_gaps': gaps, 'total_gaps': len(gaps)})


# ═══════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════

@training_knowledge_bp.route('/summary')
def api_training_summary():
    """Overall training stats."""
    today = _today_str()
    expiry_cutoff = (date.today() + timedelta(days=30)).isoformat()
    with db_session() as db:
        total_skills = db.execute('SELECT COUNT(*) as c FROM skill_trees').fetchone()['c']
        certs_active = db.execute(
            "SELECT COUNT(*) as c FROM certifications WHERE status = 'active'").fetchone()['c']
        certs_expiring = db.execute(
            """SELECT COUNT(*) as c FROM certifications
               WHERE status = 'active' AND expiration_date != '' AND expiration_date IS NOT NULL
                 AND expiration_date <= ? AND expiration_date >= ?""",
            (expiry_cutoff, today)).fetchone()['c']
        total_courses = db.execute('SELECT COUNT(*) as c FROM training_courses').fetchone()['c']
        active_courses = db.execute(
            "SELECT COUNT(*) as c FROM training_courses WHERE status = 'active'").fetchone()['c']
        total_drills = db.execute('SELECT COUNT(*) as c FROM drill_results').fetchone()['c']
        total_flashcards = db.execute('SELECT COUNT(*) as c FROM flashcards').fetchone()['c']
        flashcards_due = db.execute(
            'SELECT COUNT(*) as c FROM flashcards WHERE next_review <= ?', (today,)).fetchone()['c']
        total_packages = db.execute('SELECT COUNT(*) as c FROM knowledge_packages').fetchone()['c']
        active_packages = db.execute(
            "SELECT COUNT(*) as c FROM knowledge_packages WHERE status = 'active'").fetchone()['c']
    return jsonify({
        'skills': {'total': total_skills},
        'certifications': {'active': certs_active, 'expiring_30d': certs_expiring},
        'courses': {'total': total_courses, 'active': active_courses},
        'drills': {'total_runs': total_drills},
        'flashcards': {'total': total_flashcards, 'due_today': flashcards_due},
        'knowledge_packages': {'total': total_packages, 'active': active_packages},
    })
