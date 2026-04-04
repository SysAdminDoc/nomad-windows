"""Medical module routes."""

import json
import os
import time
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify, Response

from db import db_session, log_activity
from config import get_data_dir
from web.print_templates import render_print_document

medical_bp = Blueprint('medical', __name__)


def _esc(s):
    # NOTE: duplicated in app.py, blueprints/inventory.py
    """Escape HTML for print output."""
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def _parse_json_list(value):
    """Decode a stored JSON list field with graceful fallback."""
    try:
        parsed = json.loads(value or '[]')
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, str):
            return [parsed] if parsed else []
    except (TypeError, ValueError):
        pass
    if not value:
        return []
    return [item.strip() for item in str(value).split(',') if item.strip()]


def _render_patient_card_html(patient, vitals, wounds, pid):
    """Render a printable patient care card with the shared document shell."""
    allergies = _parse_json_list(patient.get('allergies'))
    medications = _parse_json_list(patient.get('medications'))
    conditions = _parse_json_list(patient.get('conditions'))
    weight_kg = patient.get('weight_kg')
    weight_summary = f'{weight_kg} kg / {round(weight_kg * 2.205, 1)} lb' if weight_kg else '?'
    generated_at = time.strftime('%Y-%m-%d %H:%M')
    allergy_summary = ', '.join(_esc(str(a)) for a in allergies) if allergies else 'NKDA (No Known Drug Allergies)'
    allergy_chips = ''.join(
        f'<span class="doc-chip doc-chip-alert">{_esc(str(a))}</span>' for a in allergies
    ) or '<span class="doc-chip doc-chip-muted">NKDA</span>'
    medication_chips = ''.join(
        f'<span class="doc-chip">{_esc(str(m))}</span>' for m in medications
    ) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
    condition_chips = ''.join(
        f'<span class="doc-chip">{_esc(str(c))}</span>' for c in conditions
    ) or '<span class="doc-chip doc-chip-muted">None recorded</span>'

    vitals_rows = ''
    for entry in vitals:
        systolic = entry.get('bp_systolic')
        diastolic = entry.get('bp_diastolic')
        bp = f'{systolic}/{diastolic}' if systolic or diastolic else '-'
        heart_rate = entry.get('heart_rate') or entry.get('pulse') or '-'
        spo2 = f'{entry.get("spo2")}%' if entry.get('spo2') not in (None, '') else '-'
        pain = f'{entry.get("pain_level")}/10' if entry.get('pain_level') not in (None, '') else '-'
        vitals_rows += (
            f'<tr><td>{_esc(str(entry.get("created_at", "")))}</td><td>{_esc(bp)}</td>'
            f'<td>{_esc(str(heart_rate))}</td><td>{_esc(str(entry.get("resp_rate") or "-"))}</td>'
            f'<td>{_esc(str(entry.get("temp_f") or "-"))}</td><td>{_esc(spo2)}</td>'
            f'<td>{_esc(pain)}</td><td>{_esc(str(entry.get("gcs") or "-"))}</td>'
            f'<td>{_esc(entry.get("notes", "")) or "-"}</td></tr>'
        )
    vitals_html = (
        '<div class="doc-table-shell"><table><thead><tr><th>Time</th><th>BP</th><th>Heart Rate</th><th>Resp</th><th>Temp</th><th>SpO2</th><th>Pain</th><th>GCS</th><th>Notes</th></tr></thead>'
        f'<tbody>{vitals_rows}</tbody></table></div>'
        if vitals_rows else
        '<div class="doc-empty">No vital signs have been logged for this patient yet.</div>'
    )

    wound_rows = ''
    for wound in wounds:
        wound_rows += (
            f'<tr><td>{_esc(str(wound.get("created_at", "")))}</td>'
            f'<td>{_esc(wound.get("location", "")) or "-"}</td>'
            f'<td>{_esc(wound.get("wound_type", "")) or "-"}</td>'
            f'<td>{_esc(wound.get("severity", "")) or "-"}</td>'
            f'<td>{_esc(wound.get("description", "")) or "-"}</td>'
            f'<td>{_esc(wound.get("treatment", "")) or "-"}</td></tr>'
        )
    wounds_html = (
        '<div class="doc-table-shell"><table><thead><tr><th>Time</th><th>Location</th><th>Type</th><th>Severity</th><th>Description</th><th>Treatment</th></tr></thead>'
        f'<tbody>{wound_rows}</tbody></table></div>'
        if wound_rows else
        '<div class="doc-empty">No wound entries have been documented.</div>'
    )

    notes_html = (
        f'<section class="doc-section"><h2 class="doc-section-title">Clinical Notes</h2><div class="doc-note-box">{_esc(patient.get("notes", ""))}</div></section>'
        if patient.get('notes') else ''
    )

    body = f'''<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Immediate Alerts</h2>
      <div class="doc-note-box">{allergy_summary}</div>
      <div class="doc-chip-list" style="margin-top:12px;">{allergy_chips}</div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Patient Snapshot</h2>
      <div class="doc-chip-list">
        <span class="doc-chip">Age {patient.get("age") or "?"}</span>
        <span class="doc-chip">Sex { _esc(patient.get("sex") or "?") }</span>
        <span class="doc-chip">Weight { _esc(str(weight_summary)) }</span>
        <span class="doc-chip">Blood { _esc(patient.get("blood_type") or "?") }</span>
      </div>
      <div class="doc-note-box" style="margin-top:12px;">Portable patient care snapshot for treatment, transfer, and print use.</div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Current Medications</h2>
      <div class="doc-chip-list">{medication_chips}</div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Conditions</h2>
      <div class="doc-chip-list">{condition_chips}</div>
    </div>
  </div>
</section>
{notes_html}
<section class="doc-section">
  <h2 class="doc-section-title">Vital Signs History</h2>
  {vitals_html}
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Wound Log</h2>
  {wounds_html}
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Generated by NOMAD Field Desk.</span>
    <span>Prepared {generated_at}</span>
  </div>
</section>'''

    return render_print_document(
        f'Patient Care Card - {patient["name"]}',
        'Portable patient care snapshot for treatment, transfer, and print use.',
        body,
        eyebrow='NOMAD Field Desk Patient Care Card',
        meta_items=[f'Generated {generated_at}', f'Patient ID {patient.get("id") or pid}'],
        stat_items=[
            ('Age', patient.get('age') or '?'),
            ('Blood', patient.get('blood_type') or '?'),
            ('Vitals', len(vitals)),
            ('Wounds', len(wounds)),
        ],
        accent_start='#15324a',
        accent_end='#2e6480',
        max_width='980px',
    )


def _render_handoff_report_html(
    patient,
    vitals,
    wounds,
    *,
    from_provider,
    to_provider,
    situation,
    background,
    assessment,
    recommendation,
    generated_at,
):
    """Render a printable SBAR handoff report with the shared document shell."""
    allergies = _parse_json_list(patient.get('allergies'))
    conditions = _parse_json_list(patient.get('conditions'))
    medications = _parse_json_list(patient.get('medications'))
    recommendation_text = recommendation or 'Continue current treatment plan.'
    patient_meta_html = ''.join(
        f'<div class="doc-panel"><h2 class="doc-section-title">{_esc(str(label))}</h2><div class="doc-note-box">{_esc(str(value))}</div></div>'
        for label, value in [
            ('Triage', patient.get('triage_category') or 'Unassigned'),
            ('Age', patient.get('age') or '?'),
            ('Blood Type', patient.get('blood_type') or '?'),
            ('Allergies', ', '.join(str(a) for a in allergies) or 'NKDA'),
        ]
    )
    vitals_rows = ''.join(
        f'<tr><td>{_esc(str(v.get("created_at", "")))}</td><td>{_esc(str(v.get("heart_rate") or v.get("pulse") or "-"))}</td>'
        f'<td>{_esc((f"{v.get("bp_systolic") or ""}/{v.get("bp_diastolic") or ""}").strip("/") or "-")}</td>'
        f'<td>{_esc(str(v.get("resp_rate") or "-"))}</td><td>{_esc(str(v.get("spo2") or "-"))}</td><td>{_esc(str(v.get("temp_f") or "-"))}</td></tr>'
        for v in vitals[:5]
    )
    vitals_html = (
        '<div class="doc-table-shell"><table><thead><tr><th>Time</th><th>HR</th><th>BP</th><th>RR</th><th>SpO2</th><th>Temp</th></tr></thead>'
        f'<tbody>{vitals_rows}</tbody></table></div>'
        if vitals_rows else
        '<div class="doc-empty">No recent vitals are recorded in this handoff window.</div>'
    )
    wound_rows = ''.join(
        f'<tr><td>{_esc(str(w.get("created_at", "")))}</td><td>{_esc(str(w.get("wound_type", "")) or "-")}</td>'
        f'<td>{_esc(str(w.get("location", "")) or "-")}</td><td>{_esc(str(w.get("treatment", "")) or "-")}</td></tr>'
        for w in wounds
    )
    wounds_html = (
        '<div class="doc-table-shell"><table><thead><tr><th>Time</th><th>Type</th><th>Location</th><th>Treatment</th></tr></thead>'
        f'<tbody>{wound_rows}</tbody></table></div>'
        if wound_rows else
        '<div class="doc-empty">No wound entries are attached to this patient.</div>'
    )
    medication_chips = ''.join(f'<span class="doc-chip">{_esc(str(m))}</span>' for m in medications) or '<span class="doc-chip doc-chip-muted">None recorded</span>'
    condition_chips = ''.join(f'<span class="doc-chip">{_esc(str(c))}</span>' for c in conditions) or '<span class="doc-chip doc-chip-muted">None recorded</span>'

    body = f'''<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel doc-panel-strong">
      <h2 class="doc-section-title">Transfer Lane</h2>
      <div class="doc-note-box">From {_esc(from_provider)} to {_esc(to_provider)}</div>
      <div class="doc-chip-list" style="margin-top:12px;">
        <span class="doc-chip">Prepared {generated_at}</span>
        <span class="doc-chip">Patient {_esc(patient["name"])}</span>
      </div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Patient Snapshot</h2>
      <div class="doc-grid-2">{patient_meta_html}</div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel"><h2 class="doc-section-title">Situation</h2><div class="doc-note-box">{_esc(situation)}</div></div>
    <div class="doc-panel"><h2 class="doc-section-title">Background</h2><div class="doc-note-box">{_esc(background)}</div></div>
    <div class="doc-panel"><h2 class="doc-section-title">Assessment</h2><div class="doc-note-box">{_esc(assessment)}</div></div>
    <div class="doc-panel"><h2 class="doc-section-title">Recommendation</h2><div class="doc-note-box">{_esc(recommendation_text)}</div></div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Conditions</h2>
      <div class="doc-chip-list">{condition_chips}</div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Medications</h2>
      <div class="doc-chip-list">{medication_chips}</div>
    </div>
  </div>
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Recent Vitals</h2>
  {vitals_html}
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Wound Log</h2>
  {wounds_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Provider Signature</h2>
      <div class="doc-note-box" style="min-height:88px;"></div>
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Date / Time</h2>
      <div class="doc-note-box" style="min-height:88px;">__________________</div>
    </div>
  </div>
</section>'''

    return render_print_document(
        f'SBAR Handoff - {patient["name"]}',
        'Structured patient transfer summary for rapid briefing, print handoff, and chart carry-forward.',
        body,
        eyebrow='NOMAD Field Desk Transfer Brief',
        meta_items=[f'Prepared {generated_at}', f'From {from_provider} to {to_provider}'],
        stat_items=[
            ('Triage', patient.get('triage_category') or 'Unassigned'),
            ('Age', patient.get('age') or '?'),
            ('Blood', patient.get('blood_type') or '?'),
            ('Wounds', len(wounds)),
        ],
        accent_start='#10263d',
        accent_end='#255777',
        max_width='980px',
    )


# ─── Drug Interactions Database ──────────────────────────────────────

DRUG_INTERACTIONS = [
    ('Ibuprofen', 'Aspirin', 'major', 'Ibuprofen reduces aspirin\'s cardioprotective effect. Take aspirin 30 min before ibuprofen.'),
    ('Ibuprofen', 'Warfarin', 'major', 'Increased bleeding risk. Avoid combination or monitor closely.'),
    ('Ibuprofen', 'Lisinopril', 'moderate', 'NSAIDs reduce blood pressure medication effectiveness and risk kidney damage.'),
    ('Ibuprofen', 'Metformin', 'moderate', 'NSAIDs may impair kidney function, affecting metformin clearance.'),
    ('Acetaminophen', 'Warfarin', 'moderate', 'High-dose acetaminophen (>2g/day) can increase INR/bleeding risk.'),
    ('Acetaminophen', 'Alcohol', 'major', 'Combined liver toxicity. Avoid acetaminophen if >3 drinks/day.'),
    ('Aspirin', 'Warfarin', 'major', 'Significantly increased bleeding risk. Avoid unless directed by physician.'),
    ('Aspirin', 'Methotrexate', 'major', 'Aspirin reduces methotrexate clearance \u2014 toxicity risk.'),
    ('Amoxicillin', 'Methotrexate', 'major', 'Amoxicillin reduces methotrexate clearance \u2014 toxicity risk.'),
    ('Amoxicillin', 'Warfarin', 'moderate', 'May increase anticoagulant effect. Monitor for bleeding.'),
    ('Diphenhydramine', 'Alcohol', 'major', 'Extreme drowsiness and CNS depression. Do not combine.'),
    ('Diphenhydramine', 'Oxycodone', 'major', 'Additive CNS/respiratory depression. Life-threatening.'),
    ('Diphenhydramine', 'Tramadol', 'major', 'Seizure risk increased. Additive CNS depression.'),
    ('Metformin', 'Alcohol', 'major', 'Lactic acidosis risk. Limit alcohol with metformin.'),
    ('Lisinopril', 'Potassium', 'major', 'Hyperkalemia risk. Avoid potassium supplements unless directed.'),
    ('Lisinopril', 'Spironolactone', 'major', 'Dangerous hyperkalemia. Requires monitoring.'),
    ('Warfarin', 'Vitamin K', 'major', 'Vitamin K reverses warfarin effect. Keep dietary intake consistent.'),
    ('Warfarin', 'Ciprofloxacin', 'major', 'Dramatically increases warfarin effect \u2014 bleeding risk.'),
    ('Oxycodone', 'Alcohol', 'major', 'Fatal respiratory depression. Never combine.'),
    ('Oxycodone', 'Benzodiazepines', 'major', 'Fatal respiratory depression. FDA black box warning.'),
    ('Metoprolol', 'Verapamil', 'major', 'Severe bradycardia and heart block risk.'),
    ('Ciprofloxacin', 'Antacids', 'moderate', 'Antacids reduce ciprofloxacin absorption. Take 2h apart.'),
    ('Prednisone', 'Ibuprofen', 'moderate', 'Increased GI bleeding risk. Use with PPI if needed.'),
    ('Prednisone', 'Diabetes meds', 'moderate', 'Steroids raise blood sugar. May need dose adjustment.'),
    ('SSRIs', 'Tramadol', 'major', 'Serotonin syndrome risk. Potentially fatal.'),
    ('SSRIs', 'MAOIs', 'major', 'Serotonin syndrome \u2014 potentially fatal. 14-day washout required.'),
]

# ─── Dosage Guide ────────────────────────────────────────────────────

DOSAGE_GUIDE = [
    {'drug': 'Ibuprofen', 'class': 'NSAID', 'adult_dose': '200-400mg every 4-6h', 'adult_max': '1200mg/day OTC, 3200mg/day Rx',
     'pedi_dose': '10mg/kg every 6-8h', 'pedi_max': '40mg/kg/day', 'min_age': 6, 'min_weight_kg': 5,
     'contraindications': ['aspirin allergy', 'NSAID allergy', 'ibuprofen'], 'notes': 'Take with food. Avoid if kidney disease, GI bleed history, or 3rd trimester pregnancy.',
     'interval_hours': 6},
    {'drug': 'Acetaminophen', 'class': 'Analgesic', 'adult_dose': '500-1000mg every 4-6h', 'adult_max': '3000mg/day (healthy), 2000mg/day (liver disease)',
     'pedi_dose': '15mg/kg every 4-6h', 'pedi_max': '75mg/kg/day, max 4000mg', 'min_age': 0, 'min_weight_kg': 3,
     'contraindications': ['acetaminophen', 'tylenol'], 'interval_hours': 6, 'notes': 'Do NOT exceed max dose \u2014 liver failure risk. Avoid with alcohol (>3 drinks/day).'},
    {'drug': 'Diphenhydramine', 'class': 'Antihistamine', 'adult_dose': '25-50mg every 4-6h', 'adult_max': '300mg/day',
     'pedi_dose': '1.25mg/kg every 6h', 'pedi_max': '5mg/kg/day, max 300mg', 'min_age': 2, 'min_weight_kg': 10,
     'contraindications': ['diphenhydramine', 'benadryl'], 'notes': 'Causes drowsiness. Do not operate machinery. Avoid in elderly (fall risk).',
     'interval_hours': 6},
    {'drug': 'Amoxicillin', 'class': 'Antibiotic (Penicillin)', 'adult_dose': '500mg every 8h or 875mg every 12h', 'adult_max': '3000mg/day',
     'pedi_dose': '25mg/kg/day divided every 8h', 'pedi_max': '90mg/kg/day for severe', 'min_age': 0, 'min_weight_kg': 3,
     'contraindications': ['penicillin allergy', 'amoxicillin', 'ampicillin'], 'notes': 'Complete full course. Cross-reacts with penicillin allergy (~10% with cephalosporins).',
     'interval_hours': 8},
    {'drug': 'Loperamide', 'class': 'Antidiarrheal', 'adult_dose': '4mg initial, then 2mg after each loose stool', 'adult_max': '16mg/day',
     'pedi_dose': 'Not recommended under 2 years; 2-5yo: 1mg 3x/day; 6-8yo: 2mg 2x/day; 9-11yo: 2mg 3x/day', 'pedi_max': '6mg/day (6-8yo), 8mg/day (9-11yo)', 'min_age': 2, 'min_weight_kg': 10,
     'contraindications': ['loperamide', 'imodium'], 'notes': 'Do NOT use with bloody diarrhea or fever. Stay hydrated.',
     'interval_hours': 4},
    {'drug': 'Aspirin', 'class': 'NSAID/Antiplatelet', 'adult_dose': '325-650mg every 4h', 'adult_max': '4000mg/day',
     'pedi_dose': 'NOT recommended for children under 18 (Reye syndrome risk)', 'pedi_max': 'N/A', 'min_age': 18, 'min_weight_kg': 40,
     'contraindications': ['aspirin', 'NSAID allergy', 'salicylate'], 'notes': 'Do NOT give to children/teens (Reye syndrome). Avoid with warfarin. Low-dose (81mg) for cardiac.',
     'interval_hours': 4},
    {'drug': 'Oral Rehydration Salts', 'class': 'Electrolyte', 'adult_dose': '200-400ml after each loose stool', 'adult_max': 'As needed',
     'pedi_dose': '50-100ml after each loose stool (under 2yo), 100-200ml (2-10yo)', 'pedi_max': 'As needed, maintain hydration', 'min_age': 0, 'min_weight_kg': 0,
     'contraindications': [], 'notes': 'Mix per packet instructions. If vomiting, give small sips (5ml every 1-2 min).',
     'interval_hours': None},
    {'drug': 'Prednisone', 'class': 'Corticosteroid', 'adult_dose': '5-60mg/day depending on condition', 'adult_max': '60mg/day short-term',
     'pedi_dose': '1-2mg/kg/day', 'pedi_max': '60mg/day', 'min_age': 0, 'min_weight_kg': 3,
     'contraindications': ['prednisone'], 'notes': 'Taper if >7 days. Raises blood sugar. Weakens immune system. Take with food.',
     'interval_hours': 24},
]

# ─── TCCC Protocol ───────────────────────────────────────────────────

TCCC_MARCH = [
    {'step': 'M', 'name': 'Massive Hemorrhage', 'actions': ['Apply tourniquet high and tight', 'Pack wound with hemostatic gauze', 'Apply direct pressure', 'Note tourniquet time']},
    {'step': 'A', 'name': 'Airway', 'actions': ['Head-tilt chin-lift (if no C-spine concern)', 'Jaw thrust (if C-spine concern)', 'Insert NPA if unconscious with gag reflex', 'Recovery position if breathing']},
    {'step': 'R', 'name': 'Respiration', 'actions': ['Expose chest \u2014 look for wounds', 'Seal open chest wounds (3-sided occlusive)', 'Needle decompression if tension pneumothorax', 'Monitor rate and quality']},
    {'step': 'C', 'name': 'Circulation', 'actions': ['Reassess tourniquets', 'Start IV/IO if available and trained', 'Elevate legs for shock', 'Keep warm \u2014 prevent hypothermia']},
    {'step': 'H', 'name': 'Hypothermia/Head', 'actions': ['Wrap in blanket/sleeping bag', 'Insulate from ground', 'Assess for TBI (AVPU/GCS)', 'Monitor pupils and consciousness']},
]


# ─── Patient CRUD ────────────────────────────────────────────────────

@medical_bp.route('/api/patients')
def api_patients_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM patients ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([{**dict(r), 'allergies': _parse_json_list(r['allergies']),
                     'medications': _parse_json_list(r['medications']),
                     'conditions': _parse_json_list(r['conditions'])} for r in rows])


@medical_bp.route('/api/patients', methods=['POST'])
def api_patients_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO patients (contact_id, name, age, weight_kg, sex, blood_type, allergies, medications, conditions, notes) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (data.get('contact_id'), data['name'], data.get('age'), data.get('weight_kg'),
             data.get('sex', ''), data.get('blood_type', ''),
             json.dumps(data.get('allergies', [])), json.dumps(data.get('medications', [])),
             json.dumps(data.get('conditions', [])), data.get('notes', '')))
        db.commit()
        pid = cur.lastrowid
    return jsonify({'id': pid, 'status': 'created'}), 201


@medical_bp.route('/api/patients/<int:pid>', methods=['PUT'])
def api_patients_update(pid):
    data = request.get_json() or {}
    with db_session() as db:
        existing = db.execute('SELECT * FROM patients WHERE id = ?', (pid,)).fetchone()
        if not existing:
            return jsonify({'error': 'Patient not found'}), 404
        existing = dict(existing)
        name = data.get('name', existing['name'])
        age = data.get('age', existing['age'])
        weight_kg = data.get('weight_kg', existing['weight_kg'])
        sex = data.get('sex', existing['sex'])
        blood_type = data.get('blood_type', existing['blood_type'])
        try:
            allergies_default = json.loads(existing['allergies'] or '[]')
        except json.JSONDecodeError:
            allergies_default = existing['allergies'] or []
        allergies = json.dumps(data.get('allergies', allergies_default))
        try:
            medications_default = json.loads(existing['medications'] or '[]')
        except json.JSONDecodeError:
            medications_default = existing['medications'] or []
        medications = json.dumps(data.get('medications', medications_default))
        try:
            conditions_default = json.loads(existing['conditions'] or '[]')
        except json.JSONDecodeError:
            conditions_default = existing['conditions'] or []
        conditions = json.dumps(data.get('conditions', conditions_default))
        notes_val = data.get('notes', existing['notes'])
        contact_id = data.get('contact_id', existing['contact_id'])
        db.execute(
            'UPDATE patients SET name=?, age=?, weight_kg=?, sex=?, blood_type=?, allergies=?, medications=?, conditions=?, notes=?, contact_id=?, updated_at=CURRENT_TIMESTAMP WHERE id=?',
            (name, age, weight_kg, sex, blood_type, allergies, medications, conditions, notes_val, contact_id, pid))
        db.commit()
    return jsonify({'status': 'updated'})


@medical_bp.route('/api/patients/<int:pid>', methods=['DELETE'])
def api_patients_delete(pid):
    with db_session() as db:
        db.execute('DELETE FROM handoff_reports WHERE patient_id = ?', (pid,))
        db.execute('DELETE FROM wound_photos WHERE wound_id IN (SELECT id FROM wound_log WHERE patient_id = ?)', (pid,))
        db.execute('DELETE FROM vitals_log WHERE patient_id = ?', (pid,))
        db.execute('DELETE FROM wound_log WHERE patient_id = ?', (pid,))
        db.execute('DELETE FROM patients WHERE id = ?', (pid,))
        db.commit()
    return jsonify({'status': 'deleted'})


@medical_bp.route('/api/medical/patients/export')
def api_medical_patients_export():
    """Export all patients as CSV."""
    try:
        import csv
        import io
        with db_session() as db:
            rows = db.execute(
                'SELECT name, age, sex, blood_type, weight_kg, allergies, medications, conditions, notes '
                'FROM patients ORDER BY name LIMIT 50000'
            ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Name', 'Age', 'Sex', 'Blood Type', 'Weight (kg)', 'Allergies', 'Medications', 'Conditions', 'Notes'])
        for r in rows:
            w.writerow([r['name'], r['age'] or '', r['sex'] or '', r['blood_type'] or '',
                        r['weight_kg'] or '', r['allergies'] or '', r['medications'] or '',
                        r['conditions'] or '', r['notes'] or ''])
        return Response(buf.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': 'attachment; filename="nomad_patients_export.csv"'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ─── Vitals CRUD ─────────────────────────────────────────────────────

@medical_bp.route('/api/patients/<int:pid>/vitals')
def api_vitals_list(pid):
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?', (pid, limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@medical_bp.route('/api/patients/<int:pid>/vitals', methods=['POST'])
def api_vitals_create(pid):
    data = request.get_json() or {}
    with db_session() as db:
        db.execute(
            'INSERT INTO vitals_log (patient_id, bp_systolic, bp_diastolic, pulse, resp_rate, temp_f, spo2, pain_level, gcs, notes) VALUES (?,?,?,?,?,?,?,?,?,?)',
            (pid, data.get('bp_systolic'), data.get('bp_diastolic'), data.get('pulse'),
             data.get('resp_rate'), data.get('temp_f'), data.get('spo2'),
             data.get('pain_level'), data.get('gcs'), data.get('notes', '')))
        db.commit()

    # Evaluate vitals against thresholds and build warnings
    warnings = []
    heart_rate = data.get('pulse')
    if heart_rate is not None:
        try:
            hr = float(heart_rate)
            if hr < 40 or hr > 150:
                warnings.append({'vital': 'heart_rate', 'value': hr, 'severity': 'critical', 'message': f'Heart rate {hr} bpm is critically abnormal'})
            elif hr < 50 or hr > 120:
                warnings.append({'vital': 'heart_rate', 'value': hr, 'severity': 'concern', 'message': f'Heart rate {hr} bpm is outside normal range'})
        except (ValueError, TypeError):
            pass

    bp_systolic = data.get('bp_systolic')
    if bp_systolic is not None:
        try:
            sbp = float(bp_systolic)
            if sbp < 80 or sbp > 200:
                warnings.append({'vital': 'bp_systolic', 'value': sbp, 'severity': 'critical', 'message': f'Systolic BP {sbp} mmHg is critically abnormal'})
            elif sbp < 90 or sbp > 160:
                warnings.append({'vital': 'bp_systolic', 'value': sbp, 'severity': 'concern', 'message': f'Systolic BP {sbp} mmHg is outside normal range'})
        except (ValueError, TypeError):
            pass

    spo2 = data.get('spo2')
    if spo2 is not None:
        try:
            sp = float(spo2)
            if sp < 85:
                warnings.append({'vital': 'spo2', 'value': sp, 'severity': 'critical', 'message': f'SpO2 {sp}% is critically low'})
            elif sp < 92:
                warnings.append({'vital': 'spo2', 'value': sp, 'severity': 'concern', 'message': f'SpO2 {sp}% is below normal range'})
        except (ValueError, TypeError):
            pass

    temp_f = data.get('temp_f')
    if temp_f is not None:
        try:
            t = float(temp_f)
            if t < 94 or t > 104:
                warnings.append({'vital': 'temp_f', 'value': t, 'severity': 'critical', 'message': f'Temperature {t}\u00b0F is critically abnormal'})
            elif t < 96 or t > 101:
                warnings.append({'vital': 'temp_f', 'value': t, 'severity': 'concern', 'message': f'Temperature {t}\u00b0F is outside normal range'})
        except (ValueError, TypeError):
            pass

    resp_rate = data.get('resp_rate')
    if resp_rate is not None:
        try:
            rr = float(resp_rate)
            if rr < 8 or rr > 35:
                warnings.append({'vital': 'resp_rate', 'value': rr, 'severity': 'critical', 'message': f'Respiratory rate {rr}/min is critically abnormal'})
            elif rr < 10 or rr > 25:
                warnings.append({'vital': 'resp_rate', 'value': rr, 'severity': 'concern', 'message': f'Respiratory rate {rr}/min is outside normal range'})
        except (ValueError, TypeError):
            pass

    return jsonify({'status': 'logged', 'warnings': warnings}), 201


# ─── Wound CRUD + Photos ────────────────────────────────────────────

@medical_bp.route('/api/patients/<int:pid>/wounds')
def api_wounds_list(pid):
    with db_session() as db:
        rows = db.execute('SELECT * FROM wound_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 100', (pid,)).fetchall()
    return jsonify([dict(r) for r in rows])


@medical_bp.route('/api/patients/<int:pid>/wounds', methods=['POST'])
def api_wounds_create(pid):
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO wound_log (patient_id, location, wound_type, severity, description, treatment) VALUES (?,?,?,?,?,?)',
            (pid, data.get('location', ''), data.get('wound_type', ''), data.get('severity', 'minor'),
             data.get('description', ''), data.get('treatment', '')))
        wid = cur.lastrowid
        db.commit()
    return jsonify({'status': 'logged', 'id': wid}), 201


@medical_bp.route('/api/patients/<int:pid>/wounds/<int:wid>/photo', methods=['POST'])
def api_wound_photo_upload(pid, wid):
    """Upload a photo for a wound record."""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400
    file = request.files['photo']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Validate file type
    allowed = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        return jsonify({'error': f'File type {ext} not allowed. Use: {", ".join(allowed)}'}), 400

    # Save to data dir
    photos_dir = os.path.join(get_data_dir(), 'wound_photos')
    os.makedirs(photos_dir, exist_ok=True)
    safe_name = f'wound_{pid}_{wid}_{int(time.time())}{ext}'
    filepath = os.path.join(photos_dir, safe_name)
    file.save(filepath)

    # Update wound record
    with db_session() as db:
        # Append to existing photos (JSON array of paths)
        existing = db.execute('SELECT photo_path FROM wound_log WHERE id = ? AND patient_id = ?', (wid, pid)).fetchone()
        if not existing:
            os.remove(filepath)
            return jsonify({'error': 'Wound record not found'}), 404

        photos = []
        if existing['photo_path']:
            try:
                photos = json.loads(existing['photo_path'])
                if isinstance(photos, str):
                    photos = [photos] if photos else []
            except (ValueError, TypeError):
                photos = [existing['photo_path']] if existing['photo_path'] else []

        photos.append(safe_name)
        db.execute('UPDATE wound_log SET photo_path = ? WHERE id = ?', (json.dumps(photos), wid))
        db.commit()
    return jsonify({'status': 'uploaded', 'filename': safe_name, 'photos': photos}), 201


@medical_bp.route('/api/wound-photos/<path:filename>')
def api_wound_photo_serve(filename):
    """Serve a wound photo."""
    photos_dir = os.path.join(get_data_dir(), 'wound_photos')
    safe_path = os.path.normcase(os.path.normpath(os.path.join(photos_dir, filename)))
    if not safe_path.startswith(os.path.normcase(os.path.normpath(photos_dir))):
        return jsonify({'error': 'Invalid path'}), 403
    if not os.path.isfile(safe_path):
        return jsonify({'error': 'Not found'}), 404
    from flask import send_file
    return send_file(safe_path)


@medical_bp.route('/api/patients/<int:pid>/wounds/<int:wid>/photos')
def api_wound_photos_list(pid, wid):
    """List photos for a wound record."""
    with db_session() as db:
        row = db.execute('SELECT photo_path FROM wound_log WHERE id = ? AND patient_id = ?', (wid, pid)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        photos = []
        if row['photo_path']:
            try:
                photos = json.loads(row['photo_path'])
                if isinstance(photos, str):
                    photos = [photos] if photos else []
            except (ValueError, TypeError):
                photos = [row['photo_path']] if row['photo_path'] else []
        return jsonify({'wound_id': wid, 'photos': photos})
# ─── Patient Care Card ──────────────────────────────────────────────

@medical_bp.route('/api/patients/<int:pid>/card')
def api_patient_card(pid):
    """Generate a printable patient care card."""
    with db_session() as db:
        patient = db.execute('SELECT * FROM patients WHERE id = ?', (pid,)).fetchone()
        if not patient:
            return jsonify({'error': 'Not found'}), 404
        vitals = [dict(r) for r in db.execute('SELECT * FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 20', (pid,)).fetchall()]
        wounds = [dict(r) for r in db.execute('SELECT * FROM wound_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 100', (pid,)).fetchall()]
    html = _render_patient_card_html(dict(patient), vitals, wounds, pid)
    return Response(html, mimetype='text/html')


# ─── Drug Interactions Check ────────────────────────────────────────

@medical_bp.route('/api/medical/interactions', methods=['POST'])
def api_drug_interactions():
    """Check drug interactions for a list of medications."""
    data = request.get_json() or {}
    meds = [m.strip().lower() for m in data.get('medications', []) if m.strip()]
    if len(meds) < 2:
        return jsonify([])
    meds_set = set(meds)
    found = []
    seen = set()
    for drug1, drug2, severity, detail in DRUG_INTERACTIONS:
        d1, d2 = drug1.lower(), drug2.lower()
        # Check if any med matches d1 and a *different* med matches d2
        match_d1 = [m for m in meds_set if d1 in m or m in d1]
        match_d2 = [m for m in meds_set if d2 in m or m in d2]
        if match_d1 and match_d2:
            # Ensure at least one pair involves two distinct meds
            if set(match_d1) != set(match_d2) or len(match_d1) > 1:
                key = (drug1, drug2, severity)
                if key not in seen:
                    seen.add(key)
                    found.append({'drug1': drug1, 'drug2': drug2, 'severity': severity, 'detail': detail})
    return jsonify(found)


# ─── Dosage Calculator ──────────────────────────────────────────────

@medical_bp.route('/api/medical/dosage-calculator', methods=['POST'])
def api_dosage_calculator():
    """Allergy-aware dosage calculator. Checks patient allergies and drug contraindications."""
    data = request.get_json() or {}
    drug_name = data.get('drug', '').strip()
    patient_id = data.get('patient_id')
    weight_kg = data.get('weight_kg')
    age = data.get('age')

    # Find the drug
    drug = None
    for d in DOSAGE_GUIDE:
        if d['drug'].lower() == drug_name.lower():
            drug = d
            break
    if not drug:
        available = [d['drug'] for d in DOSAGE_GUIDE]
        return jsonify({'error': f'Drug not found. Available: {", ".join(available)}'}), 400

    warnings = []
    blocked = False

    # Check patient allergies if patient_id provided
    if patient_id:
        with db_session() as db:
            patient = db.execute('SELECT allergies, medications, age, weight_kg, name FROM patients WHERE id = ?', (patient_id,)).fetchone()
            if patient:
                # Use patient age/weight if not explicitly provided
                if age is None and patient['age']:
                    age = patient['age']
                if weight_kg is None and patient['weight_kg']:
                    weight_kg = patient['weight_kg']

                # Check allergies
                import json as _json
                try:
                    allergies = _json.loads(patient['allergies']) if patient['allergies'] else []
                except (ValueError, TypeError):
                    allergies = [a.strip() for a in (patient['allergies'] or '').split(',') if a.strip()]

                for allergy in allergies:
                    allergy_lower = allergy.lower()
                    for contra in drug['contraindications']:
                        if contra.lower() in allergy_lower or allergy_lower in contra.lower():
                            warnings.append({'type': 'ALLERGY_BLOCK', 'message': f'CONTRAINDICATED: Patient {patient["name"]} has allergy to "{allergy}" \u2014 {drug["drug"]} is contraindicated.'})
                            blocked = True

                # Check current medications for interactions
                try:
                    current_meds = _json.loads(patient['medications']) if patient['medications'] else []
                except (ValueError, TypeError):
                    current_meds = [m.strip() for m in (patient['medications'] or '').split(',') if m.strip()]

                for med in current_meds:
                    med_lower = med.lower()
                    for d1, d2, sev, detail in DRUG_INTERACTIONS:
                        if (d1.lower() in drug_name.lower() or drug_name.lower() in d1.lower()) and (d2.lower() in med_lower or med_lower in d2.lower()):
                            warnings.append({'type': f'INTERACTION_{sev.upper()}', 'message': f'{drug["drug"]} + {med}: {detail}'})
                        elif (d2.lower() in drug_name.lower() or drug_name.lower() in d2.lower()) and (d1.lower() in med_lower or med_lower in d1.lower()):
                            warnings.append({'type': f'INTERACTION_{sev.upper()}', 'message': f'{drug["drug"]} + {med}: {detail}'})
    # Age check
    if age is not None and age < drug['min_age']:
        warnings.append({'type': 'AGE_BLOCK', 'message': f'{drug["drug"]} is not recommended for patients under {drug["min_age"]} years old.'})
        blocked = True

    # Calculate dose
    is_pediatric = age is not None and age < 18
    if is_pediatric and weight_kg:
        dose_info = drug['pedi_dose']
        max_info = drug['pedi_max']
    else:
        dose_info = drug['adult_dose']
        max_info = drug['adult_max']

    # Weight-based calculation for pediatric
    calc_dose = None
    if is_pediatric and weight_kg and 'mg/kg' in drug['pedi_dose']:
        import re
        match = re.search(r'(\d+(?:\.\d+)?)mg/kg', drug['pedi_dose'])
        if match:
            per_kg = float(match.group(1))
            calc_dose = round(per_kg * weight_kg, 1)

    return jsonify({
        'drug': drug['drug'],
        'drug_class': drug['class'],
        'dose': dose_info,
        'max_dose': max_info,
        'calculated_mg': calc_dose,
        'weight_kg': weight_kg,
        'age': age,
        'is_pediatric': is_pediatric,
        'blocked': blocked,
        'warnings': warnings,
        'notes': drug['notes'],
    })


@medical_bp.route('/api/medical/dosage-drugs')
def api_dosage_drugs():
    """List available drugs for the dosage calculator."""
    return jsonify([{'drug': d['drug'], 'class': d['class']} for d in DOSAGE_GUIDE])


# ─── Triage & TCCC ──────────────────────────────────────────────────

@medical_bp.route('/api/medical/triage-board')
def api_triage_board():
    """Returns all patients sorted by triage category for MCI management."""
    with db_session() as db:
        patients = [dict(r) for r in db.execute('SELECT id, name, age, blood_type, triage_category, care_phase, allergies, conditions, medications FROM patients ORDER BY name LIMIT 10000').fetchall()]
        # Group by triage category
        categories = {'immediate': [], 'delayed': [], 'minimal': [], 'expectant': [], 'unassigned': []}
        for p in patients:
            cat = p.get('triage_category', '') or 'unassigned'
            if cat in categories:
                categories[cat].append(p)
            else:
                categories['unassigned'].append(p)
        return jsonify({
            'categories': categories,
            'total': len(patients),
            'counts': {k: len(v) for k, v in categories.items()},
        })
@medical_bp.route('/api/medical/triage/<int:pid>', methods=['PUT'])
def api_triage_update(pid):
    """Update a patient's triage category and care phase."""
    data = request.get_json() or {}
    with db_session() as db:
        if 'triage_category' in data:
            # Fetch old category for history logging
            old_row = db.execute('SELECT triage_category FROM patients WHERE id = ?', (pid,)).fetchone()
            old_category = old_row['triage_category'] if old_row else ''
            new_category = data['triage_category']
            db.execute('UPDATE patients SET triage_category = ? WHERE id = ?', (new_category, pid))
            # Log to triage_history
            reason = data.get('reason', '')
            changed_by = data.get('changed_by', '')
            db.execute(
                'INSERT INTO triage_history (patient_id, old_category, new_category, reason, changed_by) VALUES (?,?,?,?,?)',
                (pid, old_category or '', new_category, reason, changed_by))
        if 'care_phase' in data:
            db.execute('UPDATE patients SET care_phase = ? WHERE id = ?', (data['care_phase'], pid))
        db.commit()
        return jsonify({'status': 'updated'})


# ─── SBAR Handoff Reports ───────────────────────────────────────────

@medical_bp.route('/api/medical/handoff/<int:pid>', methods=['POST'])
def api_medical_handoff(pid):
    """Generate an SBAR handoff report for a patient."""
    with db_session() as db:
        patient = db.execute('SELECT * FROM patients WHERE id = ?', (pid,)).fetchone()
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        vitals = [dict(r) for r in db.execute('SELECT * FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 5', (pid,)).fetchall()]
        wounds = [dict(r) for r in db.execute('SELECT * FROM wound_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT 100', (pid,)).fetchall()]

        p = dict(patient)
        allergies = _parse_json_list(p.get('allergies'))
        conditions = _parse_json_list(p.get('conditions'))
        medications = _parse_json_list(p.get('medications'))

        data = request.get_json() or {}
        now = time.strftime('%Y-%m-%d %H:%M')

        from_provider = data.get('from_provider') or data.get('sending_provider') or '___'
        to_provider = data.get('to_provider') or data.get('receiving_provider') or '___'
        situation = data.get('situation') or data.get('chief_concern') or f'Patient {p["name"]}, triage: {p.get("triage_category","unassigned")}'
        background = data.get('background') or data.get('history') or f'Age: {p.get("age","?")}. Blood type: {p.get("blood_type","?")}. Allergies: {", ".join(allergies) or "NKDA"}. Conditions: {", ".join(conditions) or "None"}. Medications: {", ".join(medications) or "None"}.'
        assessment = data.get('assessment') or data.get('condition_summary') or f'{len(wounds)} wounds documented. Latest vitals: {"available" if vitals else "none recorded"}.'
        recommendation = data.get('recommendation') or data.get('plan') or ''
        report_html = _render_handoff_report_html(
            p,
            vitals,
            wounds,
            from_provider=from_provider,
            to_provider=to_provider,
            situation=situation,
            background=background,
            assessment=assessment,
            recommendation=recommendation,
            generated_at=now,
        )

        # Save to DB
        db.execute('INSERT INTO handoff_reports (patient_id, from_provider, to_provider, situation, background, assessment, recommendation, report_html) VALUES (?,?,?,?,?,?,?,?)',
                   (pid, from_provider, to_provider, situation, background, assessment, recommendation, report_html))
        db.commit()
        rid = db.execute('SELECT last_insert_rowid()').fetchone()[0]

        return jsonify({'status': 'created', 'id': rid, 'html': report_html})
@medical_bp.route('/api/medical/handoff/<int:rid>/print')
def api_medical_handoff_print(rid):
    with db_session() as db:
        row = db.execute('SELECT report_html FROM handoff_reports WHERE id = ?', (rid,)).fetchone()
    if not row:
        return jsonify({'error': 'Report not found'}), 404
    return Response(row['report_html'], mimetype='text/html')


@medical_bp.route('/api/medical/tccc-protocol')
def api_tccc_protocol():
    return jsonify(TCCC_MARCH)


# ─── Vital Signs Trending ───────────────────────────────────────────

@medical_bp.route('/api/medical/vitals-trend/<int:patient_id>')
def api_vitals_trend(patient_id):
    """Get vital signs history for trending chart."""
    limit = request.args.get('limit', 50, type=int)
    with db_session() as db:
        rows = db.execute(
            'SELECT bp_systolic, bp_diastolic, pulse, resp_rate, temp_f, spo2, pain_level, gcs, created_at FROM vitals_log WHERE patient_id = ? ORDER BY created_at DESC LIMIT ?',
            (patient_id, limit)
        ).fetchall()
        return jsonify(list(reversed([dict(r) for r in rows])))
# ─── Medication Expiry Cross-Reference ──────────────────────────────

@medical_bp.route('/api/medical/expiring-meds')
def api_expiring_meds():
    """Cross-reference medication inventory with expiry dates."""
    from datetime import datetime, timedelta
    with db_session() as db:
        soon = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        rows = db.execute(
            "SELECT id, name, quantity, unit, expiration, category FROM inventory WHERE LOWER(category) IN ('medical', 'first aid', 'medicine', 'medications') AND expiration != '' AND expiration <= ? ORDER BY expiration ASC",
            (soon,)
        ).fetchall()
        today = datetime.now().strftime('%Y-%m-%d')
        result = []
        for r in rows:
            item = dict(r)
            item['expired'] = r['expiration'] < today
            item['days_until'] = (datetime.strptime(r['expiration'], '%Y-%m-%d') - datetime.now()).days if r['expiration'] else None
            result.append(item)
        return jsonify(result)
# ─── Medical Reference ──────────────────────────────────────────────

@medical_bp.route('/api/medical/reference')
def api_medical_reference():
    """Get offline medical quick-reference data."""
    category = request.args.get('category', '')
    references = {
        'vital_signs': {
            'title': 'Normal Vital Signs (Adult)',
            'items': [
                {'name': 'Heart Rate', 'normal': '60-100 bpm', 'concern': '<50 or >120', 'critical': '<40 or >150'},
                {'name': 'Blood Pressure', 'normal': '90/60 - 120/80', 'concern': '>140/90 or <90/60', 'critical': '>180/120 or <80/50'},
                {'name': 'Respiratory Rate', 'normal': '12-20 breaths/min', 'concern': '<10 or >24', 'critical': '<8 or >30'},
                {'name': 'Temperature', 'normal': '97.8-99.1\u00b0F', 'concern': '>100.4\u00b0F or <96\u00b0F', 'critical': '>104\u00b0F or <95\u00b0F'},
                {'name': 'SpO2', 'normal': '95-100%', 'concern': '90-94%', 'critical': '<90%'},
                {'name': 'GCS', 'normal': '15', 'concern': '9-14', 'critical': '<9'},
            ]
        },
        'drug_dosages': {
            'title': 'Common Emergency Drug Dosages (Adult)',
            'items': [
                {'drug': 'Epinephrine (anaphylaxis)', 'dose': '0.3-0.5 mg IM', 'route': 'Intramuscular (thigh)', 'repeat': 'q5-15 min'},
                {'drug': 'Aspirin (chest pain)', 'dose': '325 mg', 'route': 'Chew and swallow', 'repeat': 'Once'},
                {'drug': 'Ibuprofen (pain/fever)', 'dose': '400-800 mg', 'route': 'Oral', 'repeat': 'q6-8h, max 3200mg/day'},
                {'drug': 'Acetaminophen (pain/fever)', 'dose': '500-1000 mg', 'route': 'Oral', 'repeat': 'q4-6h, max 4000mg/day'},
                {'drug': 'Diphenhydramine (allergy)', 'dose': '25-50 mg', 'route': 'Oral or IM', 'repeat': 'q6h'},
                {'drug': 'Loperamide (diarrhea)', 'dose': '4 mg then 2 mg', 'route': 'Oral', 'repeat': 'After each loose stool, max 16mg/day'},
                {'drug': 'Ondansetron (nausea)', 'dose': '4-8 mg', 'route': 'Oral/sublingual', 'repeat': 'q8h'},
                {'drug': 'Amoxicillin (infection)', 'dose': '500 mg', 'route': 'Oral', 'repeat': 'q8h x 7-10 days'},
                {'drug': 'TXA (hemorrhage)', 'dose': '1g IV over 10min', 'route': 'Intravenous', 'repeat': 'May repeat x1 after 3h'},
                {'drug': 'Naloxone (opioid OD)', 'dose': '0.4-2 mg', 'route': 'IN/IM/IV', 'repeat': 'q2-3 min'},
            ]
        },
        'triage': {
            'title': 'START Triage Algorithm',
            'items': [
                {'step': '1', 'check': 'Can they walk?', 'yes': 'MINOR (Green)', 'no': 'Continue'},
                {'step': '2', 'check': 'Are they breathing?', 'yes': 'Check rate', 'no': 'Open airway \u2192 if still no: EXPECTANT (Black)'},
                {'step': '3', 'check': 'Resp rate >30?', 'yes': 'IMMEDIATE (Red)', 'no': 'Continue'},
                {'step': '4', 'check': 'Radial pulse present?', 'yes': 'Continue', 'no': 'IMMEDIATE (Red)'},
                {'step': '5', 'check': 'Can follow commands?', 'yes': 'DELAYED (Yellow)', 'no': 'IMMEDIATE (Red)'},
            ]
        },
        'burns': {
            'title': 'Burn Assessment \u2014 Rule of Nines (Adult)',
            'items': [
                {'area': 'Head/Neck', 'pct': '9%'},
                {'area': 'Each Arm', 'pct': '9% each'},
                {'area': 'Chest (front)', 'pct': '9%'},
                {'area': 'Abdomen (front)', 'pct': '9%'},
                {'area': 'Upper Back', 'pct': '9%'},
                {'area': 'Lower Back', 'pct': '9%'},
                {'area': 'Each Leg (front)', 'pct': '9% each'},
                {'area': 'Each Leg (back)', 'pct': '9% each'},
                {'area': 'Groin', 'pct': '1%'},
            ]
        },
        'bleeding': {
            'title': 'Hemorrhage Control Priorities',
            'items': [
                {'priority': '1', 'action': 'Direct Pressure', 'when': 'All bleeding', 'notes': 'Apply firm pressure with dressing for 10+ min'},
                {'priority': '2', 'action': 'Tourniquet', 'when': 'Extremity, life-threatening', 'notes': 'HIGH and TIGHT, note time, do NOT remove'},
                {'priority': '3', 'action': 'Wound Packing', 'when': 'Junctional (groin/axilla/neck)', 'notes': 'Pack with hemostatic gauze, apply pressure'},
                {'priority': '4', 'action': 'Pressure Dressing', 'when': 'After direct pressure controls bleeding', 'notes': 'Israeli bandage or similar'},
                {'priority': '5', 'action': 'Elevation', 'when': 'Adjunct to above methods', 'notes': 'Elevate injured extremity above heart'},
            ]
        },
        'fractures': {
            'title': 'Fracture Management',
            'items': [
                {'type': 'Closed', 'signs': 'Pain, swelling, deformity, loss of function', 'treatment': 'Splint in position found, ice, elevate', 'danger_signs': 'Loss of distal pulse/sensation'},
                {'type': 'Open/Compound', 'signs': 'Bone visible through wound', 'treatment': 'Control bleeding, irrigate, cover with moist sterile dressing, splint', 'danger_signs': 'Infection risk HIGH; do NOT push bone back in'},
                {'type': 'Femur', 'signs': 'Shortened/rotated leg, severe pain, large blood loss', 'treatment': 'Traction splint if available; treat for shock (1-2L blood loss)', 'danger_signs': 'Hypovolemic shock; life-threatening'},
                {'type': 'Pelvis', 'signs': 'Pain on compression, inability to bear weight', 'treatment': 'Pelvic binder/sheet wrap, DO NOT log roll, treat for shock', 'danger_signs': 'Massive internal hemorrhage; up to 3L blood loss'},
                {'type': 'Spine', 'signs': 'Midline tenderness, numbness/tingling, mechanism of injury', 'treatment': 'Full spinal immobilization, log roll only, C-collar', 'danger_signs': 'ANY neurological deficit = urgent evacuation'},
                {'type': 'Rib', 'signs': 'Pain on breathing, point tenderness, crepitus', 'treatment': 'Upright position, deep breathing exercises, pain management', 'danger_signs': 'Flail chest (3+ ribs, 2+ places) = paradoxical breathing'},
            ]
        },
        'poisoning': {
            'title': 'Poisoning & Toxic Exposure',
            'items': [
                {'agent': 'Ingested (unknown)', 'symptoms': 'Nausea, vomiting, altered mental status', 'treatment': 'Do NOT induce vomiting unless directed; activated charcoal if <1hr; save container/sample', 'notes': 'Call Poison Control: 1-800-222-1222'},
                {'agent': 'Carbon Monoxide', 'symptoms': 'Headache, confusion, cherry-red skin, unconsciousness', 'treatment': 'Remove from source, 100% O2, ventilate area', 'notes': 'Generator/fire/vehicle exhaust in enclosed space'},
                {'agent': 'Organophosphate (pesticide)', 'symptoms': 'SLUDGE: Salivation, Lacrimation, Urination, Defecation, GI distress, Emesis', 'treatment': 'Decontaminate (remove clothes, wash skin), atropine if available', 'notes': 'Pinpoint pupils; muscle fasciculations'},
                {'agent': 'Plant ingestion (unknown)', 'symptoms': 'Variable \u2014 GI, cardiac, neurological', 'treatment': 'Identify plant if possible; activated charcoal; supportive care', 'notes': 'Save plant sample; photograph for ID'},
                {'agent': 'Snakebite', 'symptoms': 'Pain, swelling, fang marks, possible systemic effects', 'treatment': 'Immobilize limb, keep below heart, mark swelling edge with time, evacuate', 'notes': 'Do NOT cut, suck, tourniquet, or ice'},
                {'agent': 'Mushroom ingestion', 'symptoms': 'GI symptoms 6-24hr post = dangerous (amatoxins)', 'treatment': 'Activated charcoal if early; supportive care; evacuate urgently if delayed onset', 'notes': 'Early GI (30min-2hr) = usually less dangerous; late onset = liver failure risk'},
            ]
        },
        'environmental': {
            'title': 'Environmental Emergencies',
            'items': [
                {'condition': 'Hypothermia (Mild)', 'temp': '90-95\u00b0F', 'signs': 'Shivering, impaired judgment, clumsy', 'treatment': 'Remove wet clothes, insulate, warm fluids, body-to-body heat'},
                {'condition': 'Hypothermia (Severe)', 'temp': '<90\u00b0F', 'signs': 'No shivering, confusion, slow pulse, unconscious', 'treatment': 'Handle GENTLY (cardiac irritability), insulate, warm core first, NO rubbing', 'danger': 'Cardiac arrest risk with rough handling'},
                {'condition': 'Heat Exhaustion', 'temp': '<104\u00b0F', 'signs': 'Heavy sweating, weakness, nausea, headache, cool/clammy skin', 'treatment': 'Move to shade, remove excess clothing, cool with water, oral electrolytes'},
                {'condition': 'Heat Stroke', 'temp': '>104\u00b0F', 'signs': 'Hot/dry skin (may still sweat), altered mental status, seizures', 'treatment': 'COOL RAPIDLY \u2014 ice packs to neck/groin/axilla, wet sheets + fan, cold water immersion', 'danger': 'Life-threatening; organ damage begins rapidly'},
                {'condition': 'Frostbite', 'temp': 'Tissue <32\u00b0F', 'signs': 'White/gray waxy skin, hard texture, numbness', 'treatment': 'Warm in 98-102\u00b0F water for 20-30 min; do NOT rub, do NOT rewarm if risk of refreezing', 'danger': 'Refreezing causes worse damage than staying frozen'},
                {'condition': 'Lightning Strike', 'temp': 'N/A', 'signs': 'Burns, cardiac arrest, confusion, ruptured eardrums', 'treatment': 'CPR immediately if no pulse (good prognosis with early CPR); treat burns', 'danger': 'Safe to touch patient; no residual charge'},
                {'condition': 'Drowning/Near-Drowning', 'temp': 'N/A', 'signs': 'Unconscious, not breathing, water in lungs', 'treatment': 'C-spine precaution, CPR (rescue breaths critical), suction if possible', 'danger': 'Delayed pulmonary edema up to 24hr post-rescue'},
                {'condition': 'Altitude Sickness (AMS)', 'temp': '>8000 ft', 'signs': 'Headache, nausea, fatigue, insomnia', 'treatment': 'Descend 1000-3000 ft; acetazolamide 125-250mg BID; ibuprofen; hydrate', 'danger': 'If ataxia or altered mental status = HACE; descend immediately'},
            ]
        },
        'allergic': {
            'title': 'Allergic Reactions & Anaphylaxis',
            'items': [
                {'severity': 'Mild', 'signs': 'Localized hives, itching, minor swelling', 'treatment': 'Diphenhydramine 25-50mg PO; monitor for 4 hours', 'notes': 'Watch for progression'},
                {'severity': 'Moderate', 'signs': 'Widespread hives, facial swelling, GI symptoms', 'treatment': 'Diphenhydramine 50mg + consider epinephrine if worsening', 'notes': 'Prepare epi; stay near patient'},
                {'severity': 'Anaphylaxis', 'signs': 'Throat swelling, wheezing, hypotension, altered consciousness', 'treatment': 'Epinephrine 0.3mg IM (thigh) IMMEDIATELY; repeat q5-15min; position supine with legs elevated', 'notes': 'Biphasic reaction possible 4-12hr later; evacuate'},
                {'severity': 'Insect Sting', 'signs': 'Local pain/swelling normal; systemic = anaphylaxis risk', 'treatment': 'Remove stinger (scrape, don\'t squeeze); ice; antihistamine; epi if systemic', 'notes': 'Multiple stings = toxic dose even without allergy'},
            ]
        },
        'cardiac': {
            'title': 'Cardiac Emergencies',
            'items': [
                {'condition': 'Suspected Heart Attack', 'signs': 'Chest pain/pressure, jaw/arm pain, shortness of breath, sweating, nausea', 'treatment': 'Aspirin 325mg (chew), nitroglycerin if prescribed, position of comfort, calm/reassure', 'notes': 'Women may have atypical symptoms: fatigue, back pain, indigestion'},
                {'condition': 'Cardiac Arrest', 'signs': 'Unresponsive, no pulse, no breathing (or agonal gasps)', 'treatment': 'CPR: 30 compressions (2 inches deep, 100-120/min) : 2 breaths; AED ASAP', 'notes': 'Push hard, push fast, minimize interruptions; switch compressor q2min'},
                {'condition': 'Stroke (FAST)', 'signs': 'Face drooping, Arm weakness, Speech slurred, Time to act', 'treatment': 'Note exact time of onset; position head elevated 30\u00b0; nothing by mouth; evacuate urgently', 'notes': 'tPA window = 3-4.5 hours from onset'},
                {'condition': 'Severe Bleeding + Shock', 'signs': 'Rapid weak pulse, pale/cool skin, altered mental status, thirst', 'treatment': 'Control bleeding, elevate legs, keep warm, small sips of fluid if conscious', 'notes': 'Class III shock (30-40% blood loss) = altered mental status'},
            ]
        },
        'respiratory': {
            'title': 'Respiratory Emergencies',
            'items': [
                {'condition': 'Asthma Attack', 'signs': 'Wheezing, difficulty breathing, tripod position, speaking in short phrases', 'treatment': 'Bronchodilator inhaler (albuterol) 2-4 puffs q20min x3; upright position; calm', 'notes': 'Silent chest = critical; no air movement'},
                {'condition': 'Tension Pneumothorax', 'signs': 'Chest trauma + worsening respiratory distress, tracheal deviation, distended neck veins', 'treatment': 'Needle decompression: 14ga needle, 2nd intercostal space, midclavicular line', 'notes': 'Life-threatening; immediate intervention required'},
                {'condition': 'Sucking Chest Wound', 'signs': 'Open wound with air bubbling on breathing', 'treatment': 'Occlusive dressing taped on 3 sides (valve effect); monitor for tension pneumo', 'notes': 'Commercial chest seals preferred; improvise with plastic wrap + tape'},
                {'condition': 'Choking (Adult)', 'signs': 'Cannot speak/cough, hands at throat, cyanosis', 'treatment': 'Abdominal thrusts (Heimlich); if unconscious: CPR with visual airway check', 'notes': 'Pregnant/obese: chest thrusts instead'},
            ]
        },
        'dental': {
            'title': 'Dental Emergencies',
            'items': [
                {'condition': 'Knocked-Out Tooth', 'treatment': 'Handle by crown only; rinse gently (no scrubbing); reimplant if possible or store in milk/saliva; time-critical (<60 min)', 'pain': 'Ibuprofen 400-600mg'},
                {'condition': 'Toothache/Abscess', 'treatment': 'Ibuprofen + acetaminophen alternating; warm salt water rinse; clove oil on cotton for local relief; antibiotics if abscess (amoxicillin 500mg TID)', 'pain': 'Can be severe; combined NSAID+acetaminophen most effective'},
                {'condition': 'Broken/Cracked Tooth', 'treatment': 'Rinse mouth, cold compress; temporary filling material (dental cement/wax) to cover sharp edges; avoid hot/cold', 'pain': 'Ibuprofen; avoid chewing on affected side'},
                {'condition': 'Lost Filling/Crown', 'treatment': 'Temporary dental cement or sugar-free gum over cavity; clove oil for pain', 'pain': 'Sensitivity to air/temperature until covered'},
                {'condition': 'Jaw Fracture', 'treatment': 'Immobilize with bandage around head; liquid diet only; evacuate', 'pain': 'Significant; manage with available analgesics'},
            ]
        },
        'wound_closure': {
            'title': 'Wound Closure & Care',
            'items': [
                {'method': 'Butterfly Strips/Steri-Strips', 'when': 'Clean, straight cuts <6hr old; low tension', 'technique': 'Clean wound, dry skin, apply perpendicular to wound edges pulling together', 'notes': 'Best first-line closure in austere settings'},
                {'method': 'Wound Glue (Dermabond)', 'when': 'Clean lacerations; face/scalp; low-tension areas', 'technique': 'Hold edges together, apply thin layer over top; 3-4 coats', 'notes': 'Do NOT use inside wound; avoid joints'},
                {'method': 'Sutures', 'when': 'Deep wounds, high-tension areas, >6hr if clean', 'technique': 'Simple interrupted: enter 3-5mm from edge, equal depth both sides, square knots', 'notes': 'Face 3-5 days removal; scalp 7; trunk 7-10; extremity 10-14 days'},
                {'method': 'Wound Irrigation', 'when': 'ALL contaminated/dirty wounds before closure', 'technique': 'Pressure irrigate with clean water \u2014 syringe + 18ga needle or squeeze bottle; 250mL minimum', 'notes': 'Most important infection prevention step'},
                {'method': 'Do NOT Close', 'when': 'Animal bites (except face), puncture wounds, infected wounds, >12hr old (>24hr face)', 'technique': 'Irrigate thoroughly, pack loosely, dress, antibiotics, delayed primary closure in 3-5 days if clean', 'notes': 'Closing contaminated wounds traps bacteria'},
            ]
        },
        'pediatric': {
            'title': 'Pediatric Vital Signs & Dosing',
            'items': [
                {'age': 'Newborn', 'hr': '120-160', 'rr': '30-60', 'bp': '60-80/40-50', 'weight_kg': '3-4'},
                {'age': 'Infant (1-12mo)', 'hr': '100-150', 'rr': '25-40', 'bp': '70-100/50-70', 'weight_kg': '4-10'},
                {'age': 'Toddler (1-3yr)', 'hr': '90-130', 'rr': '20-30', 'bp': '80-110/50-80', 'weight_kg': '10-15'},
                {'age': 'Preschool (4-5yr)', 'hr': '80-120', 'rr': '20-25', 'bp': '80-110/50-80', 'weight_kg': '15-20'},
                {'age': 'School Age (6-12yr)', 'hr': '70-110', 'rr': '15-20', 'bp': '90-120/60-80', 'weight_kg': '20-40'},
                {'age': 'Adolescent (13+)', 'hr': '60-100', 'rr': '12-20', 'bp': '100-130/60-85', 'weight_kg': '40-70'},
                {'age': 'Dosing Rule', 'hr': 'N/A', 'rr': 'N/A', 'bp': 'N/A', 'weight_kg': 'Ibuprofen: 10mg/kg q6-8h; Acetaminophen: 15mg/kg q4-6h; Amoxicillin: 25mg/kg/dose TID'},
            ]
        },
        'eye_injuries': {
            'title': 'Eye Injuries',
            'items': [
                {'injury': 'Chemical Splash', 'treatment': 'Irrigate IMMEDIATELY with clean water for 20+ minutes; tilt head so water flows away from uninjured eye', 'urgency': 'EMERGENCY \u2014 seconds count; irrigate before anything else'},
                {'injury': 'Foreign Body (surface)', 'treatment': 'Flush with clean water; pull upper lid over lower to use lashes as brush; do NOT rub', 'urgency': 'Moderate \u2014 remove if visible; patch if unable'},
                {'injury': 'Penetrating Object', 'treatment': 'Do NOT remove object; stabilize with cup/padding; cover BOTH eyes (reduces movement); evacuate', 'urgency': 'EMERGENCY \u2014 surgical removal only'},
                {'injury': 'Blunt Trauma', 'treatment': 'Ice pack (no pressure on globe); check vision; evacuate if vision changes, severe pain, or blood in anterior chamber', 'urgency': 'Urgent if vision affected'},
                {'injury': 'Snow Blindness (UV)', 'treatment': 'Cool compresses, rest in dark, oral pain meds; resolves 24-48hr; prevention: sunglasses/goggles', 'urgency': 'Painful but self-limiting'},
            ]
        },
    }

    if category and category in references:
        return jsonify(references[category])
    return jsonify({'categories': list(references.keys()), 'data': references})


@medical_bp.route('/api/medical/reference/search')
def api_medical_reference_search():
    """Full-text search across all medical reference categories."""
    q = request.args.get('q', '').strip().lower()
    if not q:
        return jsonify([])
    # Get the reference data by calling the endpoint logic
    ref_resp = api_medical_reference()
    ref_json = ref_resp.get_json() if hasattr(ref_resp, 'get_json') else json.loads(ref_resp.data)
    ref_data = ref_json.get('data', ref_json)
    results = []
    for cat_key, cat_data in ref_data.items():
        if not isinstance(cat_data, dict):
            continue
        title = cat_data.get('title', cat_key)
        for item in cat_data.get('items', []):
            searchable = ' '.join(str(v) for v in item.values()).lower()
            if q in searchable:
                results.append({
                    'category': cat_key,
                    'category_title': title,
                    'item': item,
                })
    return jsonify(results)


# ─── Medication Dose Scheduling & Tracking ─────────────────────────

@medical_bp.route('/api/patients/<int:pid>/medication-log', methods=['GET'])
def api_medication_log_list(pid):
    """Return all medication log entries for patient, ordered by administered_at DESC."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM medication_log WHERE patient_id = ? ORDER BY administered_at DESC',
            (pid,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@medical_bp.route('/api/patients/<int:pid>/medication-log', methods=['POST'])
def api_medication_log_create(pid):
    """Record a medication dose. Looks up drug in DOSAGE_GUIDE for interval to calculate next_dose_due."""
    data = request.get_json() or {}
    drug_name = data.get('drug_name', '').strip()
    if not drug_name:
        return jsonify({'error': 'drug_name is required'}), 400

    dose = data.get('dose', '')
    route = data.get('route', '')
    administered_by = data.get('administered_by', '')
    notes = data.get('notes', '')
    now = datetime.utcnow()

    # Look up interval from DOSAGE_GUIDE
    next_dose_due = None
    interval_hours = None
    for d in DOSAGE_GUIDE:
        if d['drug'].lower() == drug_name.lower():
            interval_hours = d.get('interval_hours')
            break
    if interval_hours:
        next_dose_due = (now + timedelta(hours=interval_hours)).strftime('%Y-%m-%d %H:%M:%S')

    with db_session() as db:
        cur = db.execute(
            'INSERT INTO medication_log (patient_id, drug_name, dose, route, administered_by, notes, next_dose_due, administered_at) VALUES (?,?,?,?,?,?,?,?)',
            (pid, drug_name, dose, route, administered_by, notes, next_dose_due,
             now.strftime('%Y-%m-%d %H:%M:%S')))
        db.commit()
        entry_id = cur.lastrowid
        return jsonify({
            'id': entry_id,
            'status': 'logged',
            'drug_name': drug_name,
            'dose': dose,
            'route': route,
            'administered_by': administered_by,
            'administered_at': now.strftime('%Y-%m-%d %H:%M:%S'),
            'next_dose_due': next_dose_due,
            'interval_hours': interval_hours,
        }), 201


@medical_bp.route('/api/medical/overdue-doses', methods=['GET'])
def api_overdue_doses():
    """Query medication_log for entries where next_dose_due < now and no newer entry for same patient+drug."""
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    with db_session() as db:
        rows = db.execute('''
            SELECT ml.*, p.name AS patient_name, p.triage_category
            FROM medication_log ml
            JOIN patients p ON p.id = ml.patient_id
            WHERE ml.next_dose_due IS NOT NULL
              AND ml.next_dose_due < ?
              AND ml.id = (
                  SELECT ml2.id FROM medication_log ml2
                  WHERE ml2.patient_id = ml.patient_id AND ml2.drug_name = ml.drug_name
                  ORDER BY ml2.administered_at DESC LIMIT 1
              )
            ORDER BY ml.next_dose_due ASC
        ''', (now,)).fetchall()

        result = []
        for r in rows:
            entry = dict(r)
            if entry.get('next_dose_due'):
                try:
                    due_dt = datetime.strptime(entry['next_dose_due'], '%Y-%m-%d %H:%M:%S')
                    overdue_minutes = int((datetime.utcnow() - due_dt).total_seconds() / 60)
                    entry['overdue_minutes'] = overdue_minutes
                    entry['overdue_display'] = f'{overdue_minutes // 60}h {overdue_minutes % 60}m' if overdue_minutes >= 60 else f'{overdue_minutes}m'
                except (ValueError, TypeError):
                    entry['overdue_minutes'] = None
                    entry['overdue_display'] = 'unknown'
            result.append(entry)
        return jsonify(result)


# ─── Triage Reassessment Workflow ──────────────────────────────────

@medical_bp.route('/api/patients/<int:pid>/triage-history', methods=['GET'])
def api_triage_history(pid):
    """Return all triage_history entries for patient."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM triage_history WHERE patient_id = ? ORDER BY created_at DESC',
            (pid,)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@medical_bp.route('/api/triage/reassessment-due', methods=['GET'])
def api_triage_reassessment_due():
    """Return patients overdue for triage reassessment based on their category."""
    reassess_intervals = {
        'immediate': 15,
        'delayed': 60,
        'minimal': 120,
    }
    now = datetime.utcnow()
    with db_session() as db:
        patients = db.execute(
            "SELECT id, name, triage_category, age, blood_type FROM patients WHERE triage_category IN ('immediate', 'delayed', 'minimal')"
        ).fetchall()

        overdue = []
        for p in patients:
            patient = dict(p)
            pid = patient['id']
            category = patient['triage_category']
            interval_min = reassess_intervals.get(category)
            if not interval_min:
                continue

            # Check last triage_history entry first, then triage_events
            last_assess = db.execute(
                'SELECT created_at FROM triage_history WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1',
                (pid,)
            ).fetchone()
            if not last_assess:
                last_assess = db.execute(
                    'SELECT created_at FROM triage_events ORDER BY created_at DESC LIMIT 1'
                ).fetchone()

            if last_assess and last_assess['created_at']:
                try:
                    last_time = datetime.strptime(last_assess['created_at'], '%Y-%m-%d %H:%M:%S')
                except (ValueError, TypeError):
                    try:
                        last_time = datetime.strptime(last_assess['created_at'][:19], '%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        continue
                deadline = last_time + timedelta(minutes=interval_min)
                if now > deadline:
                    overdue_min = int((now - deadline).total_seconds() / 60)
                    patient['last_assessed'] = last_assess['created_at']
                    patient['reassess_interval_min'] = interval_min
                    patient['overdue_minutes'] = overdue_min
                    patient['overdue_display'] = f'{overdue_min // 60}h {overdue_min % 60}m' if overdue_min >= 60 else f'{overdue_min}m'
                    overdue.append(patient)

        return jsonify(overdue)


# ─── Wound Healing Timeline ───────────────────────────────────────

@medical_bp.route('/api/patients/<int:pid>/wounds/<int:wid>/updates', methods=['GET'])
def api_wound_updates_list(pid, wid):
    """Return wound_updates for this wound."""
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM wound_updates WHERE wound_id = ? AND patient_id = ? ORDER BY created_at DESC',
            (wid, pid)
        ).fetchall()
        return jsonify([dict(r) for r in rows])


@medical_bp.route('/api/patients/<int:pid>/wounds/<int:wid>/updates', methods=['POST'])
def api_wound_updates_create(pid, wid):
    """Create a wound update entry. If status is 'closed', also updates the wound_log entry."""
    data = request.get_json() or {}
    status = data.get('status', '')
    treatment = data.get('treatment', '')
    size_cm = data.get('size_cm')
    notes = data.get('notes', '')

    with db_session() as db:
        # Verify wound exists
        wound = db.execute(
            'SELECT id FROM wound_log WHERE id = ? AND patient_id = ?', (wid, pid)
        ).fetchone()
        if not wound:
            return jsonify({'error': 'Wound not found'}), 404

        cur = db.execute(
            'INSERT INTO wound_updates (wound_id, patient_id, status, treatment, size_cm, notes) VALUES (?,?,?,?,?,?)',
            (wid, pid, status, treatment, size_cm, notes))
        update_id = cur.lastrowid

        # If wound is closed, update the wound_log entry
        if status == 'closed':
            db.execute(
                'UPDATE wound_log SET severity = ?, treatment = ? WHERE id = ? AND patient_id = ?',
                ('closed', treatment or 'Wound closed', wid, pid))

        db.commit()
        return jsonify({
            'id': update_id,
            'status': 'logged',
            'wound_id': wid,
            'wound_status': status,
            'treatment': treatment,
            'size_cm': size_cm,
        }), 201
