"""Phase 16: Interoperability & Data Exchange — exports, imports, print docs, batch ops."""

import codecs
import csv
import io
import json
import logging
import os
from datetime import datetime
from html import escape as _esc

from flask import Blueprint, request, jsonify, Response

from db import db_session, log_activity
from web.print_templates import render_print_document

_log = logging.getLogger(__name__)

interoperability_bp = Blueprint('interoperability', __name__, url_prefix='/api/interop')

# ─── Supported format reference ──────────────────────────────────────

SUPPORTED_FORMATS = {
    'import': {
        'csv': {'extensions': ['.csv'], 'description': 'Comma-separated values'},
        'vcard': {'extensions': ['.vcf', '.vcard'], 'description': 'vCard contacts'},
        'gpx': {'extensions': ['.gpx'], 'description': 'GPS Exchange Format'},
        'geojson': {'extensions': ['.geojson', '.json'], 'description': 'GeoJSON features'},
        'kml': {'extensions': ['.kml'], 'description': 'Keyhole Markup Language'},
        'ics': {'extensions': ['.ics'], 'description': 'iCalendar events/tasks'},
        'chirp': {'extensions': ['.csv'], 'description': 'CHIRP radio programming CSV'},
    },
    'export': {
        'csv': 'Comma-separated values',
        'vcard': 'vCard 3.0 contacts',
        'gpx': 'GPS Exchange Format 1.1',
        'geojson': 'GeoJSON RFC 7946',
        'kml': 'KML 2.2',
        'ics': 'iCalendar RFC 5545',
        'chirp': 'CHIRP radio programming CSV',
        'adif': 'Amateur Data Interchange Format 3.1',
        'fhir': 'FHIR R4 Patient Bundle (simplified)',
        'markdown': 'Markdown text',
    },
}


# ─── Helpers ─────────────────────────────────────────────────────────

def _safe_str(val, default=''):
    if val is None:
        return default
    return str(val)


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=0):
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return default


def _safe_json_list(val, default=None):
    if default is None:
        default = []
    if isinstance(val, list):
        return val
    if not val:
        return default
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, list) else default
    except (json.JSONDecodeError, TypeError):
        return default


def _safe_json_obj(val, default=None):
    if default is None:
        default = {}
    if isinstance(val, dict):
        return val
    if not val:
        return default
    try:
        parsed = json.loads(val)
        return parsed if isinstance(parsed, dict) else default
    except (json.JSONDecodeError, TypeError):
        return default


def _now_iso():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def _log_export(db, export_type, fmt, source_table, count, status='completed'):
    """Record an export to data_exports table."""
    db.execute(
        'INSERT INTO data_exports (export_type, format, source_table, record_count, status, created_at, completed_at)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?)',
        (export_type, fmt, source_table, count, status, _now_iso(), _now_iso()),
    )
    db.commit()


def _log_import(db, import_type, fmt, target_table, source_filename,
                total, imported, skipped, errors, status='completed',
                column_mapping=None, validation_errors=None):
    """Record an import to batch_imports table."""
    db.execute(
        'INSERT INTO batch_imports (import_type, format, target_table, source_filename,'
        ' total_records, imported_records, skipped_records, error_records,'
        ' column_mapping, validation_errors, status, created_at, completed_at)'
        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (import_type, fmt, target_table, source_filename,
         total, imported, skipped, errors,
         json.dumps(column_mapping or {}), json.dumps(validation_errors or []),
         status, _now_iso(), _now_iso()),
    )
    db.commit()


def _csv_response(output, filename):
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def _xml_response(xml_str, mimetype, filename):
    return Response(
        xml_str,
        mimetype=mimetype,
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


def _get_upload_text():
    """Read uploaded file content from either request.files or request.data."""
    if request.files and 'file' in request.files:
        return request.files['file'].read().decode('utf-8', errors='replace')
    return request.get_data(as_text=True)


def _iter_upload_lines():
    """Yield decoded text lines from the upload without loading it all into memory.

    Used by CSV importers so multi-hundred-MB spreadsheet imports don't spike RAM.
    Falls back to the buffered `_get_upload_text()` path when no file stream is
    available (raw POST body).
    """
    if request.files and 'file' in request.files:
        stream = request.files['file'].stream
        decoder = codecs.getreader('utf-8')(stream, errors='replace')
        for line in decoder:
            yield line
        return
    # Raw POST body — already buffered; split in-memory (unavoidable for this path).
    for line in io.StringIO(request.get_data(as_text=True) or ''):
        yield line


def _get_upload_filename():
    if request.files and 'file' in request.files:
        return request.files['file'].filename or 'upload'
    return 'upload'


# ─── Formats endpoint ────────────────────────────────────────────────

@interoperability_bp.route('/formats', methods=['GET'])
def api_formats():
    return jsonify(SUPPORTED_FORMATS)


# ═══════════════════════════════════════════════════════════════════════
#  EXPORT ROUTES
# ═══════════════════════════════════════════════════════════════════════

# ─── Inventory CSV ───────────────────────────────────────────────────

@interoperability_bp.route('/export/inventory/csv', methods=['GET'])
def api_export_inventory_csv():
    with db_session() as db:
        rows = db.execute('SELECT * FROM inventory ORDER BY category, name').fetchall()
        if not rows:
            return jsonify({'error': 'No inventory records found'}), 404
        cols = rows[0].keys()
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
        _log_export(db, 'inventory', 'csv', 'inventory', len(rows))
        log_activity('export_inventory_csv', service='interoperability',
                     detail=f'Exported {len(rows)} inventory records as CSV')
    return _csv_response(buf, f'inventory-{datetime.now().strftime("%Y%m%d")}.csv')


# ─── Contacts CSV ────────────────────────────────────────────────────

@interoperability_bp.route('/export/contacts/csv', methods=['GET'])
def api_export_contacts_csv():
    with db_session() as db:
        rows = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No contacts found'}), 404
        cols = rows[0].keys()
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(dict(r))
        _log_export(db, 'contacts', 'csv', 'contacts', len(rows))
        log_activity('export_contacts_csv', service='interoperability',
                     detail=f'Exported {len(rows)} contacts as CSV')
    return _csv_response(buf, f'contacts-{datetime.now().strftime("%Y%m%d")}.csv')


# ─── Contacts vCard ──────────────────────────────────────────────────

@interoperability_bp.route('/export/contacts/vcard', methods=['GET'])
def api_export_contacts_vcard():
    with db_session() as db:
        rows = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No contacts found'}), 404
        vcards = []
        for r in rows:
            lines = ['BEGIN:VCARD', 'VERSION:3.0']
            lines.append(f'FN:{_safe_str(r["name"])}')
            if r['phone']:
                lines.append(f'TEL;TYPE=CELL:{_safe_str(r["phone"])}')
            if r['email']:
                lines.append(f'EMAIL:{_safe_str(r["email"])}')
            if r['address']:
                lines.append(f'ADR;TYPE=HOME:;;{_safe_str(r["address"])};;;;')
            if r['role']:
                lines.append(f'TITLE:{_safe_str(r["role"])}')
            if r['callsign']:
                lines.append(f'NOTE:Callsign: {_safe_str(r["callsign"])}')
            if r['notes']:
                note = _safe_str(r['notes']).replace('\n', '\\n')
                existing = next((l for l in lines if l.startswith('NOTE:')), None)
                if existing:
                    idx = lines.index(existing)
                    lines[idx] = existing + '\\n' + note
                else:
                    lines.append(f'NOTE:{note}')
            lines.append('END:VCARD')
            vcards.append('\r\n'.join(lines))
        body = '\r\n'.join(vcards)
        _log_export(db, 'contacts', 'vcard', 'contacts', len(rows))
        log_activity('export_contacts_vcard', service='interoperability',
                     detail=f'Exported {len(rows)} contacts as vCard')
    return Response(body, mimetype='text/vcard',
                    headers={'Content-Disposition': f'attachment; filename="contacts-{datetime.now().strftime("%Y%m%d")}.vcf"'})


# ─── Waypoints GPX ──────────────────────────────────────────────────

@interoperability_bp.route('/export/waypoints/gpx', methods=['GET'])
def api_export_waypoints_gpx():
    with db_session() as db:
        rows = db.execute('SELECT * FROM waypoints ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No waypoints found'}), 404
        gpx = '<?xml version="1.0" encoding="UTF-8"?>\n'
        gpx += '<gpx version="1.1" creator="NOMAD Field Desk"\n'
        gpx += '     xmlns="http://www.topografix.com/GPX/1/1">\n'
        for w in rows:
            gpx += f'  <wpt lat="{w["lat"]}" lon="{w["lng"]}">\n'
            gpx += f'    <name>{_esc(_safe_str(w["name"]))}</name>\n'
            if w['elevation_m']:
                gpx += f'    <ele>{w["elevation_m"]}</ele>\n'
            if w['notes']:
                gpx += f'    <desc>{_esc(_safe_str(w["notes"]))}</desc>\n'
            if w['category']:
                gpx += f'    <type>{_esc(_safe_str(w["category"]))}</type>\n'
            gpx += '  </wpt>\n'
        gpx += '</gpx>\n'
        _log_export(db, 'waypoints', 'gpx', 'waypoints', len(rows))
        log_activity('export_waypoints_gpx', service='interoperability',
                     detail=f'Exported {len(rows)} waypoints as GPX')
    return _xml_response(gpx, 'application/gpx+xml',
                         f'waypoints-{datetime.now().strftime("%Y%m%d")}.gpx')


# ─── Waypoints GeoJSON ──────────────────────────────────────────────

@interoperability_bp.route('/export/waypoints/geojson', methods=['GET'])
def api_export_waypoints_geojson():
    with db_session() as db:
        rows = db.execute('SELECT * FROM waypoints ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No waypoints found'}), 404
        features = []
        for w in rows:
            feat = {
                'type': 'Feature',
                'geometry': {
                    'type': 'Point',
                    'coordinates': [w['lng'], w['lat']],
                },
                'properties': {
                    'name': _safe_str(w['name']),
                    'category': _safe_str(w['category']),
                    'icon': _safe_str(w['icon']),
                    'color': _safe_str(w['color']),
                    'notes': _safe_str(w['notes']),
                },
            }
            if w['elevation_m']:
                feat['geometry']['coordinates'].append(w['elevation_m'])
            features.append(feat)
        collection = {'type': 'FeatureCollection', 'features': features}
        body = json.dumps(collection, indent=2)
        _log_export(db, 'waypoints', 'geojson', 'waypoints', len(rows))
        log_activity('export_waypoints_geojson', service='interoperability',
                     detail=f'Exported {len(rows)} waypoints as GeoJSON')
    return Response(body, mimetype='application/geo+json',
                    headers={'Content-Disposition': f'attachment; filename="waypoints-{datetime.now().strftime("%Y%m%d")}.geojson"'})


# ─── Waypoints KML ──────────────────────────────────────────────────

@interoperability_bp.route('/export/waypoints/kml', methods=['GET'])
def api_export_waypoints_kml():
    with db_session() as db:
        rows = db.execute('SELECT * FROM waypoints ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No waypoints found'}), 404
        kml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        kml += '<kml xmlns="http://www.opengis.net/kml/2.2">\n'
        kml += '<Document>\n<name>NOMAD Export</name>\n'
        for w in rows:
            ele = w['elevation_m'] or 0
            kml += '<Placemark>\n'
            kml += f'  <name>{_esc(_safe_str(w["name"]))}</name>\n'
            if w['notes']:
                kml += f'  <description>{_esc(_safe_str(w["notes"]))}</description>\n'
            kml += f'  <Point><coordinates>{w["lng"]},{w["lat"]},{ele}</coordinates></Point>\n'
            kml += '</Placemark>\n'
        kml += '</Document>\n</kml>\n'
        _log_export(db, 'waypoints', 'kml', 'waypoints', len(rows))
        log_activity('export_waypoints_kml', service='interoperability',
                     detail=f'Exported {len(rows)} waypoints as KML')
    return _xml_response(kml, 'application/vnd.google-earth.kml+xml',
                         f'waypoints-{datetime.now().strftime("%Y%m%d")}.kml')


# ─── Tasks ICS ───────────────────────────────────────────────────────

@interoperability_bp.route('/export/tasks/ics', methods=['GET'])
def api_export_tasks_ics():
    with db_session() as db:
        rows = db.execute('SELECT * FROM scheduled_tasks ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No tasks found'}), 404
        lines = [
            'BEGIN:VCALENDAR',
            'VERSION:2.0',
            'PRODID:-//NOMAD Field Desk//EN',
        ]
        for t in rows:
            lines.append('BEGIN:VTODO')
            lines.append(f'SUMMARY:{_safe_str(t["name"])}')
            if t['category']:
                lines.append(f'CATEGORIES:{_safe_str(t["category"])}')
            if t['next_due']:
                try:
                    dt = datetime.strptime(str(t['next_due'])[:19], '%Y-%m-%d %H:%M:%S')
                    lines.append(f'DUE:{dt.strftime("%Y%m%dT%H%M%S")}')
                except (ValueError, TypeError):
                    pass
            if t['assigned_to']:
                lines.append(f'ATTENDEE;CN={_safe_str(t["assigned_to"])}:')
            completed = (t['completed_count'] or 0) > 0
            lines.append(f'STATUS:{"COMPLETED" if completed else "NEEDS-ACTION"}')
            if t['notes']:
                desc = _safe_str(t['notes']).replace('\n', '\\n')
                lines.append(f'DESCRIPTION:{desc}')
            lines.append('END:VTODO')
        lines.append('END:VCALENDAR')
        body = '\r\n'.join(lines) + '\r\n'
        _log_export(db, 'tasks', 'ics', 'scheduled_tasks', len(rows))
        log_activity('export_tasks_ics', service='interoperability',
                     detail=f'Exported {len(rows)} tasks as iCalendar')
    return Response(body, mimetype='text/calendar',
                    headers={'Content-Disposition': f'attachment; filename="tasks-{datetime.now().strftime("%Y%m%d")}.ics"'})


# ─── Checklists Markdown ────────────────────────────────────────────

@interoperability_bp.route('/export/checklists/markdown', methods=['GET'])
def api_export_checklists_md():
    with db_session() as db:
        rows = db.execute('SELECT * FROM checklists ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No checklists found'}), 404
        md_lines = [f'# NOMAD Field Desk Checklists\n',
                    f'_Exported {datetime.now().strftime("%Y-%m-%d %H:%M")}_\n']
        for cl in rows:
            md_lines.append(f'## {_safe_str(cl["name"])}\n')
            if cl['template']:
                md_lines.append(f'Template: {_safe_str(cl["template"])}\n')
            items = _safe_json_list(cl['items'])
            if items:
                for item in items:
                    if isinstance(item, dict):
                        name = item.get('name', item.get('text', str(item)))
                        checked = item.get('checked', item.get('done', False))
                    else:
                        name = str(item)
                        checked = False
                    mark = 'x' if checked else ' '
                    md_lines.append(f'- [{mark}] {name}')
            else:
                md_lines.append('_No items_')
            md_lines.append('')
        body = '\n'.join(md_lines)
        _log_export(db, 'checklists', 'markdown', 'checklists', len(rows))
        log_activity('export_checklists_md', service='interoperability',
                     detail=f'Exported {len(rows)} checklists as Markdown')
    return Response(body, mimetype='text/markdown',
                    headers={'Content-Disposition': f'attachment; filename="checklists-{datetime.now().strftime("%Y%m%d")}.md"'})


# ─── Medical FHIR ───────────────────────────────────────────────────

@interoperability_bp.route('/export/medical/fhir', methods=['GET'])
def api_export_medical_fhir():
    with db_session() as db:
        rows = db.execute('SELECT * FROM patients ORDER BY name').fetchall()
        if not rows:
            return jsonify({'error': 'No patients found'}), 404
        entries = []
        for p in rows:
            resource = {
                'resourceType': 'Patient',
                'id': str(p['id']),
                'name': [{'use': 'official', 'text': _safe_str(p['name'])}],
                'gender': _safe_str(p['sex']).lower() or 'unknown',
            }
            if p['age']:
                resource['birthDate'] = f'est-age-{p["age"]}'
            telecom = []
            # Pull phone from linked contact if available
            if p['contact_id']:
                contact = db.execute('SELECT phone, email FROM contacts WHERE id = ?',
                                     (p['contact_id'],)).fetchone()
                if contact:
                    if contact['phone']:
                        telecom.append({'system': 'phone', 'value': contact['phone']})
                    if contact['email']:
                        telecom.append({'system': 'email', 'value': contact['email']})
            if telecom:
                resource['telecom'] = telecom
            if p['blood_type']:
                resource['extension'] = [{
                    'url': 'http://nomad.local/fhir/blood-type',
                    'valueString': _safe_str(p['blood_type']),
                }]
            entries.append({
                'fullUrl': f'urn:uuid:patient-{p["id"]}',
                'resource': resource,
            })
        bundle = {
            'resourceType': 'Bundle',
            'type': 'collection',
            'total': len(entries),
            'entry': entries,
        }
        body = json.dumps(bundle, indent=2)
        _log_export(db, 'medical', 'fhir', 'patients', len(rows))
        log_activity('export_medical_fhir', service='interoperability',
                     detail=f'Exported {len(rows)} patients as FHIR bundle')
    return Response(body, mimetype='application/fhir+json',
                    headers={'Content-Disposition': f'attachment; filename="patients-fhir-{datetime.now().strftime("%Y%m%d")}.json"'})


# ─── Radio CHIRP CSV ────────────────────────────────────────────────

CHIRP_COLUMNS = [
    'Location', 'Name', 'Frequency', 'Duplex', 'Offset', 'Tone',
    'rToneFreq', 'cToneFreq', 'DtcsCode', 'DtcsPolarity', 'Mode',
    'TStep', 'Skip', 'Comment', 'URCALL', 'RPT1CALL', 'RPT2CALL', 'DVCODE',
]


@interoperability_bp.route('/export/radio/chirp', methods=['GET'])
def api_export_radio_chirp():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM freq_database ORDER BY frequency'
        ).fetchall()
        if not rows:
            return jsonify({'error': 'No frequencies found'}), 404
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=CHIRP_COLUMNS)
        w.writeheader()
        for idx, r in enumerate(rows):
            w.writerow({
                'Location': idx,
                'Name': _safe_str(r['service'])[:7],
                'Frequency': f'{r["frequency"]:.6f}',
                'Duplex': '',
                'Offset': '0.000000',
                'Tone': '',
                'rToneFreq': '88.5',
                'cToneFreq': '88.5',
                'DtcsCode': '023',
                'DtcsPolarity': 'NN',
                'Mode': _safe_str(r['mode']) or 'FM',
                'TStep': '5.00',
                'Skip': '',
                'Comment': _safe_str(r['description'])[:32],
                'URCALL': '',
                'RPT1CALL': '',
                'RPT2CALL': '',
                'DVCODE': '',
            })
        _log_export(db, 'radio', 'chirp', 'freq_database', len(rows))
        log_activity('export_radio_chirp', service='interoperability',
                     detail=f'Exported {len(rows)} frequencies as CHIRP CSV')
    return _csv_response(buf, f'chirp-{datetime.now().strftime("%Y%m%d")}.csv')


# ─── Radio ADIF ─────────────────────────────────────────────────────

@interoperability_bp.route('/export/radio/adif', methods=['GET'])
def api_export_radio_adif():
    with db_session() as db:
        rows = db.execute('SELECT * FROM sent_messages ORDER BY sent_at DESC').fetchall()
        if not rows:
            return jsonify({'error': 'No sent messages found'}), 404
        lines = [
            'ADIF Export from NOMAD Field Desk',
            f'<ADIF_VER:3>3.1',
            f'<PROGRAMID:15>NOMADFieldDesk',
            '<EOH>',
            '',
        ]
        count = 0
        for m in rows:
            if _safe_str(m['sent_via']).lower() != 'radio':
                continue
            count += 1
            content = _safe_json_obj(m['content'])
            callsign = _safe_str(m['sent_to']) or 'UNKNOWN'
            freq = _safe_str(content.get('frequency', ''))
            mode = _safe_str(content.get('mode', 'SSB'))
            try:
                dt = datetime.strptime(str(m['sent_at'])[:19], '%Y-%m-%d %H:%M:%S')
                qso_date = dt.strftime('%Y%m%d')
                qso_time = dt.strftime('%H%M%S')
            except (ValueError, TypeError):
                qso_date = datetime.now().strftime('%Y%m%d')
                qso_time = '000000'
            rec = ''
            rec += f'<CALL:{len(callsign)}>{callsign} '
            if freq:
                rec += f'<FREQ:{len(freq)}>{freq} '
            rec += f'<MODE:{len(mode)}>{mode} '
            rec += f'<QSO_DATE:{len(qso_date)}>{qso_date} '
            rec += f'<TIME_ON:{len(qso_time)}>{qso_time} '
            rec += '<EOR>'
            lines.append(rec)
        body = '\n'.join(lines) + '\n'
        _log_export(db, 'radio', 'adif', 'sent_messages', count)
        log_activity('export_radio_adif', service='interoperability',
                     detail=f'Exported {count} radio contacts as ADIF')
    return Response(body, mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename="radio-log-{datetime.now().strftime("%Y%m%d")}.adi"'})


# ─── Custom table CSV export ────────────────────────────────────────

ALLOWED_EXPORT_TABLES = {
    'inventory', 'contacts', 'waypoints', 'checklists', 'scheduled_tasks',
    'freq_database', 'patients', 'vehicles', 'family_checkins',
    'evac_plans', 'rally_points', 'sent_messages', 'radio_profiles',
}


@interoperability_bp.route('/export/custom', methods=['GET'])
def api_export_custom_csv():
    table = request.args.get('table', '').strip()
    if not table or table not in ALLOWED_EXPORT_TABLES:
        return jsonify({'error': f'Invalid table. Allowed: {sorted(ALLOWED_EXPORT_TABLES)}'}), 400
    columns_param = request.args.get('columns', '').strip()
    with db_session() as db:
        # Validate columns exist
        schema_cols = [r[1] for r in db.execute(f"PRAGMA table_info({table})").fetchall()]
        if not schema_cols:
            return jsonify({'error': f'Table {table} has no columns'}), 404
        if columns_param:
            requested = [c.strip() for c in columns_param.split(',') if c.strip()]
            valid_cols = [c for c in requested if c in schema_cols]
            if not valid_cols:
                return jsonify({'error': 'None of the requested columns exist',
                                'available': schema_cols}), 400
            select_cols = ', '.join(valid_cols)
        else:
            valid_cols = schema_cols
            select_cols = '*'
        rows = db.execute(f'SELECT {select_cols} FROM {table} ORDER BY id DESC').fetchall()
        if not rows:
            return jsonify({'error': f'No records in {table}'}), 404
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=valid_cols)
        w.writeheader()
        for r in rows:
            w.writerow({c: r[c] for c in valid_cols})
        _log_export(db, 'custom', 'csv', table, len(rows))
        log_activity('export_custom_csv', service='interoperability',
                     detail=f'Exported {len(rows)} rows from {table}')
    return _csv_response(buf, f'{table}-{datetime.now().strftime("%Y%m%d")}.csv')


# ═══════════════════════════════════════════════════════════════════════
#  IMPORT ROUTES
# ═══════════════════════════════════════════════════════════════════════

# ─── Import Contacts vCard ───────────────────────────────────────────

@interoperability_bp.route('/import/contacts/vcard', methods=['POST'])
def api_import_contacts_vcard():
    text = _get_upload_text()
    if not text or 'BEGIN:VCARD' not in text:
        return jsonify({'error': 'No valid vCard data found'}), 400
    cards = text.split('BEGIN:VCARD')
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        for card in cards:
            card = card.strip()
            if not card:
                continue
            props = {}
            for line in card.splitlines():
                line = line.strip()
                if line.startswith('FN:'):
                    props['name'] = line[3:]
                elif line.upper().startswith('TEL'):
                    props['phone'] = line.split(':', 1)[-1]
                elif line.upper().startswith('EMAIL'):
                    props['email'] = line.split(':', 1)[-1]
                elif line.upper().startswith('ADR'):
                    props['address'] = line.split(':', 1)[-1].replace(';', ' ').strip()
                elif line.upper().startswith('TITLE:'):
                    props['role'] = line.split(':', 1)[-1]
                elif line.upper().startswith('NOTE:'):
                    props['notes'] = line.split(':', 1)[-1].replace('\\n', '\n')
            name = props.get('name', '').strip()
            if not name:
                skipped += 1
                continue
            try:
                db.execute(
                    'INSERT INTO contacts (name, phone, email, address, role, notes) VALUES (?, ?, ?, ?, ?, ?)',
                    (name, props.get('phone', ''), props.get('email', ''),
                     props.get('address', ''), props.get('role', ''),
                     props.get('notes', '')),
                )
                imported += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'contacts', 'vcard', 'contacts', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('import_contacts_vcard', service='interoperability',
                     detail=f'Imported {imported}/{total} contacts from vCard')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Import Contacts CSV ────────────────────────────────────────────

@interoperability_bp.route('/import/contacts/csv', methods=['POST'])
def api_import_contacts_csv():
    col_map = {}
    if request.form and request.form.get('column_mapping'):
        try:
            col_map = json.loads(request.form.get('column_mapping') or '{}')
        except (ValueError, TypeError):
            col_map = {}
    elif not (request.files and 'file' in request.files):
        col_map = (request.get_json(silent=True) or {}).get('column_mapping', {})
    reader = csv.DictReader(_iter_upload_lines())
    if not reader.fieldnames:
        return jsonify({'error': 'No CSV data found'}), 400
    imported = 0
    skipped = 0
    errors = []
    BATCH = 500
    with db_session() as db:
        contact_cols = {r[1] for r in db.execute("PRAGMA table_info(contacts)").fetchall()}
        contact_cols -= {'id', 'created_at', 'updated_at'}
        for row_num, row in enumerate(reader, 1):
            mapped = {}
            for src, dest in col_map.items():
                if dest in contact_cols and src in row:
                    mapped[dest] = row[src]
            if not col_map:
                for k, v in row.items():
                    if k in contact_cols:
                        mapped[k] = v
            if 'name' not in mapped or not mapped['name'].strip():
                skipped += 1
                errors.append(f'Row {row_num}: missing name')
                continue
            try:
                cols_str = ', '.join(mapped.keys())
                placeholders = ', '.join(['?'] * len(mapped))
                db.execute(f'INSERT INTO contacts ({cols_str}) VALUES ({placeholders})',
                           tuple(mapped.values()))
                imported += 1
            except Exception as e:
                errors.append(f'Row {row_num}: {e}')
                skipped += 1
            if imported and imported % BATCH == 0:
                db.commit()
        db.commit()
        total = imported + skipped
        _log_import(db, 'contacts', 'csv', 'contacts', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    column_mapping=col_map, validation_errors=errors[:50])
        log_activity('import_contacts_csv', service='interoperability',
                     detail=f'Imported {imported}/{total} contacts from CSV')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Import Waypoints GPX ───────────────────────────────────────────

def _parse_xml_simple(text, tag):
    """Minimal XML tag content extractor (no lxml dependency)."""
    results = []
    search = f'<{tag}'
    idx = 0
    while True:
        start = text.find(search, idx)
        if start == -1:
            break
        end_tag = text.find(f'</{tag}>', start)
        if end_tag == -1:
            close = text.find('/>', start)
            if close == -1:
                break
            results.append(text[start:close + 2])
            idx = close + 2
        else:
            results.append(text[start:end_tag + len(f'</{tag}>')])
            idx = end_tag + len(f'</{tag}>')
    return results


def _xml_attr(element, attr):
    """Extract attribute value from an XML element string."""
    search = f'{attr}="'
    idx = element.find(search)
    if idx == -1:
        search = f"{attr}='"
        idx = element.find(search)
        if idx == -1:
            return ''
    start = idx + len(search)
    quote = element[idx + len(attr) + 1]
    end = element.find(quote, start)
    return element[start:end] if end != -1 else ''


def _xml_tag_content(element, tag):
    """Extract content of a child tag from an XML element string."""
    start_tag = f'<{tag}>'
    idx = element.find(start_tag)
    if idx == -1:
        start_tag = f'<{tag} '
        idx = element.find(start_tag)
        if idx == -1:
            return ''
        close_bracket = element.find('>', idx)
        if close_bracket == -1:
            return ''
        idx = close_bracket + 1
    else:
        idx += len(start_tag)
    end_tag = f'</{tag}>'
    end = element.find(end_tag, idx)
    return element[idx:end].strip() if end != -1 else ''


@interoperability_bp.route('/import/waypoints/gpx', methods=['POST'])
def api_import_waypoints_gpx():
    text = _get_upload_text()
    if not text or '<gpx' not in text.lower():
        return jsonify({'error': 'No valid GPX data found'}), 400
    wpts = _parse_xml_simple(text, 'wpt')
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        for wpt in wpts:
            lat = _safe_float(_xml_attr(wpt, 'lat'))
            lon = _safe_float(_xml_attr(wpt, 'lon'))
            name = _xml_tag_content(wpt, 'name') or f'GPX {lat:.4f},{lon:.4f}'
            if lat == 0.0 and lon == 0.0:
                skipped += 1
                errors.append(f'{name}: invalid coordinates')
                continue
            ele = _safe_float(_xml_tag_content(wpt, 'ele')) or None
            desc = _xml_tag_content(wpt, 'desc')
            cat = _xml_tag_content(wpt, 'type') or 'general'
            try:
                db.execute(
                    'INSERT INTO waypoints (name, lat, lng, category, elevation_m, notes) VALUES (?, ?, ?, ?, ?, ?)',
                    (name, lat, lon, cat, ele, desc),
                )
                imported += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'waypoints', 'gpx', 'waypoints', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('import_waypoints_gpx', service='interoperability',
                     detail=f'Imported {imported}/{total} waypoints from GPX')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Import Waypoints GeoJSON ───────────────────────────────────────

@interoperability_bp.route('/import/waypoints/geojson', methods=['POST'])
def api_import_waypoints_geojson():
    text = _get_upload_text()
    if not text:
        return jsonify({'error': 'No GeoJSON data found'}), 400
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Invalid JSON: {e}'}), 400
    features = []
    if data.get('type') == 'FeatureCollection':
        features = data.get('features', [])
    elif data.get('type') == 'Feature':
        features = [data]
    else:
        return jsonify({'error': 'Expected FeatureCollection or Feature'}), 400
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        for feat in features:
            geom = feat.get('geometry', {})
            props = feat.get('properties', {})
            if geom.get('type') != 'Point':
                skipped += 1
                errors.append(f'Skipped non-Point geometry: {geom.get("type")}')
                continue
            coords = geom.get('coordinates', [])
            if len(coords) < 2:
                skipped += 1
                continue
            lon, lat = _safe_float(coords[0]), _safe_float(coords[1])
            ele = _safe_float(coords[2]) if len(coords) > 2 else None
            name = props.get('name', f'GeoJSON {lat:.4f},{lon:.4f}')
            try:
                db.execute(
                    'INSERT INTO waypoints (name, lat, lng, category, elevation_m, notes, icon, color)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                    (name, lat, lon,
                     props.get('category', 'general'), ele,
                     props.get('notes', ''), props.get('icon', 'pin'),
                     props.get('color', '#5b9fff')),
                )
                imported += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'waypoints', 'geojson', 'waypoints', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('import_waypoints_geojson', service='interoperability',
                     detail=f'Imported {imported}/{total} waypoints from GeoJSON')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Import Waypoints KML ───────────────────────────────────────────

@interoperability_bp.route('/import/waypoints/kml', methods=['POST'])
def api_import_waypoints_kml():
    text = _get_upload_text()
    if not text or '<kml' not in text.lower():
        return jsonify({'error': 'No valid KML data found'}), 400
    placemarks = _parse_xml_simple(text, 'Placemark')
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        for pm in placemarks:
            name = _xml_tag_content(pm, 'name') or 'KML Import'
            desc = _xml_tag_content(pm, 'description')
            coords_str = _xml_tag_content(pm, 'coordinates').strip()
            if not coords_str:
                skipped += 1
                errors.append(f'{name}: no coordinates')
                continue
            parts = coords_str.split(',')
            if len(parts) < 2:
                skipped += 1
                errors.append(f'{name}: invalid coordinates')
                continue
            lon = _safe_float(parts[0])
            lat = _safe_float(parts[1])
            ele = _safe_float(parts[2]) if len(parts) > 2 else None
            try:
                db.execute(
                    'INSERT INTO waypoints (name, lat, lng, category, elevation_m, notes) VALUES (?, ?, ?, ?, ?, ?)',
                    (name, lat, lon, 'general', ele, desc),
                )
                imported += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'waypoints', 'kml', 'waypoints', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('import_waypoints_kml', service='interoperability',
                     detail=f'Imported {imported}/{total} waypoints from KML')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Import Tasks ICS ───────────────────────────────────────────────

@interoperability_bp.route('/import/tasks/ics', methods=['POST'])
def api_import_tasks_ics():
    text = _get_upload_text()
    if not text or 'BEGIN:VCALENDAR' not in text:
        return jsonify({'error': 'No valid iCalendar data found'}), 400
    # Split into VTODO blocks
    vtodos = text.split('BEGIN:VTODO')
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        for block in vtodos[1:]:  # skip preamble
            props = {}
            for line in block.splitlines():
                line = line.strip()
                if line.startswith('SUMMARY:'):
                    props['name'] = line[8:]
                elif line.startswith('CATEGORIES:'):
                    props['category'] = line[11:]
                elif line.startswith('DESCRIPTION:'):
                    props['notes'] = line[12:].replace('\\n', '\n')
                elif line.startswith('DUE:') or line.startswith('DUE;'):
                    raw = line.split(':', 1)[-1].strip()
                    try:
                        if 'T' in raw:
                            dt = datetime.strptime(raw[:15], '%Y%m%dT%H%M%S')
                        else:
                            dt = datetime.strptime(raw[:8], '%Y%m%d')
                        props['next_due'] = dt.strftime('%Y-%m-%d %H:%M:%S')
                    except (ValueError, TypeError):
                        pass
                elif line.startswith('ATTENDEE'):
                    cn_start = line.find('CN=')
                    if cn_start != -1:
                        rest = line[cn_start + 3:]
                        end = rest.find(':')
                        if end == -1:
                            end = rest.find(';')
                        props['assigned_to'] = rest[:end] if end != -1 else rest
            name = props.get('name', '').strip()
            if not name:
                skipped += 1
                continue
            try:
                db.execute(
                    'INSERT INTO scheduled_tasks (name, category, next_due, assigned_to, notes)'
                    ' VALUES (?, ?, ?, ?, ?)',
                    (name, props.get('category', 'custom'),
                     props.get('next_due'), props.get('assigned_to', ''),
                     props.get('notes', '')),
                )
                imported += 1
            except Exception as e:
                errors.append(f'{name}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'tasks', 'ics', 'scheduled_tasks', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('import_tasks_ics', service='interoperability',
                     detail=f'Imported {imported}/{total} tasks from iCalendar')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Import Radio CHIRP CSV ─────────────────────────────────────────

@interoperability_bp.route('/import/radio/chirp', methods=['POST'])
def api_import_radio_chirp():
    text = _get_upload_text()
    if not text:
        return jsonify({'error': 'No CHIRP CSV data found'}), 400
    reader = csv.DictReader(io.StringIO(text))
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        for row_num, row in enumerate(reader, 1):
            freq_str = row.get('Frequency', '').strip()
            if not freq_str:
                skipped += 1
                errors.append(f'Row {row_num}: missing Frequency')
                continue
            freq = _safe_float(freq_str)
            if freq <= 0:
                skipped += 1
                errors.append(f'Row {row_num}: invalid frequency {freq_str}')
                continue
            name = row.get('Name', '').strip() or f'CH{row_num}'
            mode = row.get('Mode', 'FM').strip() or 'FM'
            comment = row.get('Comment', '').strip()
            try:
                db.execute(
                    'INSERT INTO freq_database (frequency, mode, service, description, notes)'
                    ' VALUES (?, ?, ?, ?, ?)',
                    (freq, mode, name, comment, f'CHIRP import row {row_num}'),
                )
                imported += 1
            except Exception as e:
                errors.append(f'Row {row_num}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'radio', 'chirp', 'freq_database', _get_upload_filename(),
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('import_radio_chirp', service='interoperability',
                     detail=f'Imported {imported}/{total} frequencies from CHIRP CSV')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ─── Generic CSV Import ─────────────────────────────────────────────

ALLOWED_IMPORT_TABLES = {
    'inventory', 'contacts', 'waypoints', 'checklists', 'scheduled_tasks',
    'freq_database', 'patients', 'vehicles', 'family_checkins',
}


@interoperability_bp.route('/import/generic', methods=['POST'])
def api_import_generic_csv():
    data = request.get_json(silent=True) or {}
    target_table = data.get('target_table', '').strip()
    col_map = data.get('column_mapping', {})
    csv_data = data.get('csv_data', '')
    if not target_table or target_table not in ALLOWED_IMPORT_TABLES:
        return jsonify({'error': f'Invalid target_table. Allowed: {sorted(ALLOWED_IMPORT_TABLES)}'}), 400
    if not csv_data:
        return jsonify({'error': 'csv_data is required'}), 400
    with db_session() as db:
        schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({target_table})").fetchall()}
        schema_cols -= {'id', 'created_at', 'updated_at'}
        reader = csv.DictReader(io.StringIO(csv_data))
        imported = 0
        skipped = 0
        errors = []
        for row_num, row in enumerate(reader, 1):
            mapped = {}
            if col_map:
                for src, dest in col_map.items():
                    if dest in schema_cols and src in row:
                        mapped[dest] = row[src]
            else:
                for k, v in row.items():
                    if k in schema_cols:
                        mapped[k] = v
            if not mapped:
                skipped += 1
                errors.append(f'Row {row_num}: no mappable columns')
                continue
            try:
                cols_str = ', '.join(mapped.keys())
                placeholders = ', '.join(['?'] * len(mapped))
                db.execute(f'INSERT INTO {target_table} ({cols_str}) VALUES ({placeholders})',
                           tuple(mapped.values()))
                imported += 1
            except Exception as e:
                errors.append(f'Row {row_num}: {e}')
                skipped += 1
        db.commit()
        total = imported + skipped
        _log_import(db, 'generic', 'csv', target_table, 'api-upload',
                    total, imported, skipped, len(errors),
                    column_mapping=col_map, validation_errors=errors[:50])
        log_activity('import_generic_csv', service='interoperability',
                     detail=f'Imported {imported}/{total} rows into {target_table}')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ═══════════════════════════════════════════════════════════════════════
#  PRINT ROUTES
# ═══════════════════════════════════════════════════════════════════════

# ─── FEMA Household Emergency Plan ──────────────────────────────────

@interoperability_bp.route('/print/fema-household-plan', methods=['GET'])
def api_print_fema_household_plan():
    with db_session() as db:
        contacts = db.execute('SELECT * FROM contacts ORDER BY name').fetchall()
        family = db.execute('SELECT * FROM family_checkins ORDER BY name').fetchall()
        rally = db.execute(
            'SELECT rp.*, ep.name as plan_name FROM rally_points rp'
            ' LEFT JOIN evac_plans ep ON rp.evac_plan_id = ep.id'
            ' ORDER BY rp.sequence_order'
        ).fetchall()
        supply_summary = db.execute(
            'SELECT category, COUNT(*) as cnt, SUM(quantity) as total_qty'
            ' FROM inventory GROUP BY category ORDER BY category'
        ).fetchall()
        low_stock = db.execute(
            'SELECT name, quantity, min_quantity, unit FROM inventory'
            ' WHERE quantity <= min_quantity AND min_quantity > 0'
            ' ORDER BY name LIMIT 20'
        ).fetchall()

    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    # Emergency contacts table
    ec_rows = ''
    for c in contacts[:30]:
        ec_rows += (
            f'<tr><td>{_esc(_safe_str(c["name"]))}</td>'
            f'<td>{_esc(_safe_str(c["role"]))}</td>'
            f'<td>{_esc(_safe_str(c["phone"]))}</td>'
            f'<td>{_esc(_safe_str(c["email"]))}</td></tr>\n'
        )
    contacts_html = f'''<table class="doc-table">
<thead><tr><th>Name</th><th>Role</th><th>Phone</th><th>Email</th></tr></thead>
<tbody>{ec_rows}</tbody>
</table>''' if ec_rows else '<div class="doc-empty">No contacts registered</div>'

    # Family members
    fam_rows = ''
    for f in family:
        fam_rows += (
            f'<tr><td>{_esc(_safe_str(f["name"]))}</td>'
            f'<td>{_esc(_safe_str(f["status"]))}</td>'
            f'<td>{_esc(_safe_str(f["phone"]))}</td>'
            f'<td>{_esc(_safe_str(f["location"]))}</td></tr>\n'
        )
    family_html = f'''<table class="doc-table">
<thead><tr><th>Name</th><th>Status</th><th>Phone</th><th>Location</th></tr></thead>
<tbody>{fam_rows}</tbody>
</table>''' if fam_rows else '<div class="doc-empty">No family members registered</div>'

    # Meeting points
    rally_rows = ''
    for r in rally:
        rally_rows += (
            f'<tr><td>{_esc(_safe_str(r["name"]))}</td>'
            f'<td>{_esc(_safe_str(r["point_type"]))}</td>'
            f'<td>{_esc(_safe_str(r["location"]))}</td>'
            f'<td>{_esc(_safe_str(r.get("plan_name", "")))}</td></tr>\n'
        )
    rally_html = f'''<table class="doc-table">
<thead><tr><th>Point Name</th><th>Type</th><th>Location</th><th>Evac Plan</th></tr></thead>
<tbody>{rally_rows}</tbody>
</table>''' if rally_rows else '<div class="doc-empty">No rally/meeting points defined</div>'

    # Supply summary
    supply_rows = ''
    for s in supply_summary:
        supply_rows += (
            f'<tr><td>{_esc(_safe_str(s["category"]))}</td>'
            f'<td>{s["cnt"]}</td>'
            f'<td>{s["total_qty"] or 0:.0f}</td></tr>\n'
        )
    supply_html = f'''<table class="doc-table">
<thead><tr><th>Category</th><th>Items</th><th>Total Qty</th></tr></thead>
<tbody>{supply_rows}</tbody>
</table>''' if supply_rows else '<div class="doc-empty">No inventory</div>'

    # Low stock alerts
    low_rows = ''
    for l in low_stock:
        low_rows += (
            f'<tr><td>{_esc(_safe_str(l["name"]))}</td>'
            f'<td>{l["quantity"]:.1f} {_esc(_safe_str(l["unit"]))}</td>'
            f'<td>{l["min_quantity"]:.1f}</td></tr>\n'
        )
    low_html = f'''<table class="doc-table">
<thead><tr><th>Item</th><th>Current</th><th>Minimum</th></tr></thead>
<tbody>{low_rows}</tbody>
</table>''' if low_rows else '<div class="doc-empty">No low-stock items</div>'

    body = f'''
<button onclick="window.print()" style="margin-bottom:12px;padding:8px 18px;background:#255777;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Print</button>
<section class="doc-section">
  <h2 class="doc-section-title">Family / Household Members</h2>
  {family_html}
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Emergency Contacts</h2>
  {contacts_html}
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Meeting Points &amp; Rally Locations</h2>
  {rally_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Supply Summary</h2>
      {supply_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Low Stock Alerts</h2>
      {low_html}
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Family Emergency Plan</span>
    <span>NOMAD Field Desk</span>
  </div>
</section>'''

    html = render_print_document(
        'FEMA Household Emergency Plan',
        'Family emergency contacts, meeting points, and supply readiness overview.',
        body,
        eyebrow='NOMAD Field Desk',
        meta_items=[f'Generated {now}', 'Keep accessible for all household members'],
        stat_items=[
            ('Contacts', len(contacts)),
            ('Family', len(family)),
            ('Rally Points', len(rally)),
            ('Supply Categories', len(supply_summary)),
        ],
        accent_start='#1a3553',
        accent_end='#2d6480',
    )
    return Response(html, mimetype='text/html')


# ─── Vehicle Wallet Cards ───────────────────────────────────────────

@interoperability_bp.route('/print/vehicle-cards', methods=['GET'])
def api_print_vehicle_cards():
    with db_session() as db:
        vehicles = db.execute('SELECT * FROM vehicles ORDER BY name').fetchall()

    if not vehicles:
        body = '<div class="doc-empty">No vehicles registered</div>'
    else:
        cards = []
        for v in vehicles:
            card = f'''<div style="border:1px solid #ccc;border-radius:10px;padding:14px 18px;margin-bottom:14px;
                page-break-inside:avoid;max-width:400px;display:inline-block;vertical-align:top;margin-right:14px;">
  <div style="font-weight:700;font-size:14px;margin-bottom:6px;">{_esc(_safe_str(v["name"]))}</div>
  <table style="font-size:11px;width:100%;border-collapse:collapse;">
    <tr><td style="padding:2px 6px;color:#666;">Year/Make/Model</td><td style="padding:2px 6px;">{_safe_str(v["year"])} {_esc(_safe_str(v["make"]))} {_esc(_safe_str(v["model"]))}</td></tr>
    <tr><td style="padding:2px 6px;color:#666;">VIN</td><td style="padding:2px 6px;font-family:monospace;">{_esc(_safe_str(v["vin"]))}</td></tr>
    <tr><td style="padding:2px 6px;color:#666;">Plate</td><td style="padding:2px 6px;">{_esc(_safe_str(v["plate"]))}</td></tr>
    <tr><td style="padding:2px 6px;color:#666;">Color</td><td style="padding:2px 6px;">{_esc(_safe_str(v["color"]))}</td></tr>
    <tr><td style="padding:2px 6px;color:#666;">Fuel</td><td style="padding:2px 6px;">{_esc(_safe_str(v["fuel_type"]))} / {_safe_float(v["tank_capacity_gal"]):.1f} gal / {_safe_float(v["mpg"]):.0f} mpg</td></tr>
    <tr><td style="padding:2px 6px;color:#666;">Insurance Exp</td><td style="padding:2px 6px;">{_esc(_safe_str(v["insurance_exp"]))}</td></tr>
    <tr><td style="padding:2px 6px;color:#666;">Registration Exp</td><td style="padding:2px 6px;">{_esc(_safe_str(v["registration_exp"]))}</td></tr>
  </table>
</div>'''
            cards.append(card)
        body = f'''
<button onclick="window.print()" style="margin-bottom:12px;padding:8px 18px;background:#255777;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Print</button>
<section class="doc-section">
  <h2 class="doc-section-title">Wallet-Size Vehicle Cards</h2>
  <p style="color:#666;font-size:11px;margin-bottom:12px;">Cut along borders. Each card fits in a standard wallet.</p>
  {"".join(cards)}
</section>'''

    html = render_print_document(
        'Vehicle Info Cards',
        'Wallet-size reference cards with VIN, insurance, registration, and fuel details.',
        body,
        eyebrow='NOMAD Field Desk',
        meta_items=[f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}'],
        stat_items=[('Vehicles', len(vehicles))],
        accent_start='#1e3a4f',
        accent_end='#2c6178',
    )
    return Response(html, mimetype='text/html')


# ─── Medication Wallet Cards ────────────────────────────────────────

@interoperability_bp.route('/print/medication-cards', methods=['GET'])
def api_print_medication_cards():
    with db_session() as db:
        patients = db.execute('SELECT * FROM patients ORDER BY name').fetchall()
        med_logs = {}
        for p in patients:
            meds = db.execute(
                'SELECT DISTINCT drug_name, dose, route FROM medication_log'
                ' WHERE patient_id = ? ORDER BY drug_name',
                (p['id'],)
            ).fetchall()
            med_logs[p['id']] = meds

    if not patients:
        body = '<div class="doc-empty">No patients registered</div>'
    else:
        cards = []
        for p in patients:
            allergies = _safe_json_list(p['allergies'])
            medications = _safe_json_list(p['medications'])
            conditions = _safe_json_list(p['conditions'])
            logged_meds = med_logs.get(p['id'], [])
            allergy_str = ', '.join(str(a) for a in allergies) if allergies else 'None known'
            condition_str = ', '.join(str(c) for c in conditions) if conditions else 'None'

            med_rows = ''
            # Show current medications from patient record
            for m in medications:
                if isinstance(m, dict):
                    med_rows += f'<tr><td style="padding:2px 6px;">{_esc(str(m.get("name", m)))}</td><td style="padding:2px 6px;">{_esc(str(m.get("dose", "")))}</td></tr>'
                else:
                    med_rows += f'<tr><td style="padding:2px 6px;" colspan="2">{_esc(str(m))}</td></tr>'
            # Also show from medication_log
            for ml in logged_meds:
                med_rows += f'<tr><td style="padding:2px 6px;">{_esc(_safe_str(ml["drug_name"]))}</td><td style="padding:2px 6px;">{_esc(_safe_str(ml["dose"]))}</td></tr>'

            card = f'''<div style="border:1px solid #ccc;border-radius:10px;padding:14px 18px;margin-bottom:14px;
                page-break-inside:avoid;max-width:400px;display:inline-block;vertical-align:top;margin-right:14px;">
  <div style="font-weight:700;font-size:14px;margin-bottom:4px;">{_esc(_safe_str(p["name"]))}</div>
  <div style="font-size:11px;color:#666;margin-bottom:8px;">
    {_safe_str(p["sex"])} | Age: {_safe_str(p["age"])} | Blood: {_esc(_safe_str(p["blood_type"]))}
  </div>
  <div style="font-size:11px;margin-bottom:4px;"><strong>Allergies:</strong> <span style="color:#c33;">{_esc(allergy_str)}</span></div>
  <div style="font-size:11px;margin-bottom:6px;"><strong>Conditions:</strong> {_esc(condition_str)}</div>
  {f'<table style="font-size:11px;width:100%;border-collapse:collapse;"><thead><tr><th style="text-align:left;padding:2px 6px;">Medication</th><th style="text-align:left;padding:2px 6px;">Dose</th></tr></thead><tbody>{med_rows}</tbody></table>' if med_rows else '<div style="font-size:11px;color:#888;">No medications on record</div>'}
</div>'''
            cards.append(card)
        body = f'''
<button onclick="window.print()" style="margin-bottom:12px;padding:8px 18px;background:#255777;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Print</button>
<section class="doc-section">
  <h2 class="doc-section-title">Medication Cards</h2>
  <p style="color:#666;font-size:11px;margin-bottom:12px;">One card per person. Includes allergies, conditions, and active medications.</p>
  {"".join(cards)}
</section>'''

    html = render_print_document(
        'Medication Cards',
        'Wallet-size medication and allergy cards per patient.',
        body,
        eyebrow='NOMAD Field Desk',
        meta_items=[f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}'],
        stat_items=[('Patients', len(patients))],
        accent_start='#3d1a1a',
        accent_end='#6e3535',
    )
    return Response(html, mimetype='text/html')


# ─── Skills Gap Report ──────────────────────────────────────────────

@interoperability_bp.route('/print/skills-gap-report', methods=['GET'])
def api_print_skills_gap_report():
    with db_session() as db:
        contacts = db.execute('SELECT id, name, skills FROM contacts ORDER BY name').fetchall()
        certs = db.execute('SELECT person_name, certification_name, status, expiration_date FROM certifications ORDER BY person_name').fetchall()

    # Build skills matrix
    all_skills = set()
    person_skills = {}
    for c in contacts:
        name = c['name']
        raw_skills = _safe_str(c['skills'])
        skills = [s.strip() for s in raw_skills.split(',') if s.strip()] if raw_skills else []
        person_skills[name] = set(skills)
        all_skills.update(skills)

    all_skills = sorted(all_skills)

    # Cert map
    cert_map = {}
    for cr in certs:
        pn = cr['person_name']
        if pn not in cert_map:
            cert_map[pn] = []
        cert_map[pn].append(cr)

    if not contacts:
        body = '<div class="doc-empty">No contacts with skills data</div>'
    else:
        # Skills matrix table
        header = '<th style="padding:4px 6px;">Person</th>'
        for sk in all_skills[:20]:  # cap at 20 columns for readability
            header += f'<th style="padding:4px 6px;writing-mode:vertical-lr;text-align:left;font-size:10px;">{_esc(sk)}</th>'

        matrix_rows = ''
        for c in contacts:
            name = c['name']
            row = f'<td style="padding:4px 6px;font-weight:600;">{_esc(name)}</td>'
            for sk in all_skills[:20]:
                has = sk in person_skills.get(name, set())
                row += f'<td style="padding:4px 6px;text-align:center;{"background:#d4edda;" if has else "background:#f8d7da;"}">' \
                       f'{"Y" if has else "-"}</td>'
            matrix_rows += f'<tr>{row}</tr>\n'

        matrix_html = f'''<div style="overflow-x:auto;">
<table class="doc-table" style="font-size:11px;">
<thead><tr>{header}</tr></thead>
<tbody>{matrix_rows}</tbody>
</table></div>'''

        # Gap analysis
        skill_coverage = {}
        total_people = len(contacts)
        for sk in all_skills:
            count = sum(1 for ps in person_skills.values() if sk in ps)
            skill_coverage[sk] = count
        gaps = [(sk, cnt) for sk, cnt in skill_coverage.items() if cnt <= 1]
        gaps.sort(key=lambda x: x[1])

        gap_rows = ''
        for sk, cnt in gaps[:15]:
            who = [name for name, skills in person_skills.items() if sk in skills]
            gap_rows += (
                f'<tr><td style="padding:4px 6px;">{_esc(sk)}</td>'
                f'<td style="padding:4px 6px;text-align:center;">{cnt}/{total_people}</td>'
                f'<td style="padding:4px 6px;font-size:10px;">{_esc(", ".join(who)) if who else "None"}</td></tr>\n'
            )
        gap_html = f'''<table class="doc-table" style="font-size:11px;">
<thead><tr><th>Skill</th><th>Coverage</th><th>Held By</th></tr></thead>
<tbody>{gap_rows}</tbody>
</table>''' if gap_rows else '<div class="doc-empty">No critical skill gaps detected</div>'

        # Certifications summary
        cert_rows = ''
        for cr in certs[:30]:
            exp_style = ''
            if cr['expiration_date']:
                try:
                    exp_dt = datetime.strptime(cr['expiration_date'][:10], '%Y-%m-%d')
                    if exp_dt < datetime.now():
                        exp_style = 'color:#c33;font-weight:600;'
                except (ValueError, TypeError):
                    pass
            cert_rows += (
                f'<tr><td style="padding:4px 6px;">{_esc(_safe_str(cr["person_name"]))}</td>'
                f'<td style="padding:4px 6px;">{_esc(_safe_str(cr["certification_name"]))}</td>'
                f'<td style="padding:4px 6px;">{_esc(_safe_str(cr["status"]))}</td>'
                f'<td style="padding:4px 6px;{exp_style}">{_esc(_safe_str(cr["expiration_date"]))}</td></tr>\n'
            )
        cert_html = f'''<table class="doc-table" style="font-size:11px;">
<thead><tr><th>Person</th><th>Certification</th><th>Status</th><th>Expires</th></tr></thead>
<tbody>{cert_rows}</tbody>
</table>''' if cert_rows else '<div class="doc-empty">No certifications recorded</div>'

        body = f'''
<button onclick="window.print()" style="margin-bottom:12px;padding:8px 18px;background:#255777;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:13px;">Print</button>
<section class="doc-section">
  <h2 class="doc-section-title">Skills Matrix</h2>
  {matrix_html}
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Critical Skill Gaps (1 or fewer holders)</h2>
  {gap_html}
</section>
<section class="doc-section">
  <h2 class="doc-section-title">Certifications</h2>
  {cert_html}
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Skills Gap Analysis</span>
    <span>NOMAD Field Desk</span>
  </div>
</section>'''

    html = render_print_document(
        'Skills Gap Report',
        'Skills matrix showing coverage and gaps across group members.',
        body,
        eyebrow='NOMAD Field Desk',
        meta_items=[f'Generated {datetime.now().strftime("%Y-%m-%d %H:%M")}',
                    f'{len(contacts)} members', f'{len(all_skills)} tracked skills'],
        stat_items=[
            ('Members', len(contacts)),
            ('Unique Skills', len(all_skills)),
            ('Gaps', len(gaps) if contacts else 0),
            ('Certifications', len(certs)),
        ],
        accent_start='#1a2e44',
        accent_end='#2a5570',
    )
    return Response(html, mimetype='text/html')


# ═══════════════════════════════════════════════════════════════════════
#  BATCH DATA ENTRY
# ═══════════════════════════════════════════════════════════════════════

@interoperability_bp.route('/batch/validate', methods=['POST'])
def api_batch_validate():
    """Validate batch JSON data against a target table schema."""
    data = request.get_json(silent=True) or {}
    target_table = data.get('target_table', '').strip()
    records = data.get('records', [])
    if not target_table or target_table not in ALLOWED_IMPORT_TABLES:
        return jsonify({'error': f'Invalid target_table. Allowed: {sorted(ALLOWED_IMPORT_TABLES)}'}), 400
    if not isinstance(records, list) or not records:
        return jsonify({'error': 'records must be a non-empty list'}), 400
    with db_session() as db:
        schema = db.execute(f"PRAGMA table_info({target_table})").fetchall()
        col_info = {}
        for col in schema:
            col_info[col[1]] = {
                'type': col[2],
                'notnull': bool(col[3]),
                'default': col[4],
                'pk': bool(col[5]),
            }
        writable_cols = {c for c in col_info if not col_info[c]['pk']}
    errors = []
    valid_count = 0
    for idx, rec in enumerate(records):
        if not isinstance(rec, dict):
            errors.append({'row': idx, 'error': 'Record must be an object'})
            continue
        row_errors = []
        for col_name, info in col_info.items():
            if info['pk']:
                continue
            if info['notnull'] and info['default'] is None and col_name not in rec:
                row_errors.append(f'Missing required field: {col_name}')
        unknown = [k for k in rec if k not in writable_cols]
        if unknown:
            row_errors.append(f'Unknown columns: {", ".join(unknown)}')
        if row_errors:
            errors.append({'row': idx, 'errors': row_errors})
        else:
            valid_count += 1
    return jsonify({
        'valid': valid_count,
        'invalid': len(errors),
        'total': len(records),
        'errors': errors[:100],
        'target_table': target_table,
        'writable_columns': sorted(writable_cols),
    })


@interoperability_bp.route('/batch/execute', methods=['POST'])
def api_batch_execute():
    """Execute validated batch insert into target table."""
    data = request.get_json(silent=True) or {}
    target_table = data.get('target_table', '').strip()
    records = data.get('records', [])
    if not target_table or target_table not in ALLOWED_IMPORT_TABLES:
        return jsonify({'error': f'Invalid target_table. Allowed: {sorted(ALLOWED_IMPORT_TABLES)}'}), 400
    if not isinstance(records, list) or not records:
        return jsonify({'error': 'records must be a non-empty list'}), 400
    imported = 0
    skipped = 0
    errors = []
    with db_session() as db:
        schema_cols = {r[1] for r in db.execute(f"PRAGMA table_info({target_table})").fetchall()}
        schema_cols -= {'id'}
        for idx, rec in enumerate(records):
            if not isinstance(rec, dict):
                skipped += 1
                errors.append(f'Row {idx}: not an object')
                continue
            mapped = {k: v for k, v in rec.items() if k in schema_cols}
            if not mapped:
                skipped += 1
                errors.append(f'Row {idx}: no valid columns')
                continue
            try:
                cols_str = ', '.join(mapped.keys())
                placeholders = ', '.join(['?'] * len(mapped))
                db.execute(f'INSERT INTO {target_table} ({cols_str}) VALUES ({placeholders})',
                           tuple(mapped.values()))
                imported += 1
            except Exception as e:
                skipped += 1
                errors.append(f'Row {idx}: {e}')
        db.commit()
        total = imported + skipped
        _log_import(db, 'batch', 'json', target_table, 'batch-api',
                    total, imported, skipped, len(errors),
                    validation_errors=errors[:50])
        log_activity('batch_execute', service='interoperability',
                     detail=f'Batch inserted {imported}/{total} rows into {target_table}')
    return jsonify({'imported': imported, 'skipped': skipped, 'errors': errors[:50], 'total': total})


# ═══════════════════════════════════════════════════════════════════════
#  EXPORT / IMPORT HISTORY
# ═══════════════════════════════════════════════════════════════════════

@interoperability_bp.route('/exports', methods=['GET'])
def api_exports_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM data_exports ORDER BY id DESC').fetchall()
        return jsonify([dict(r) for r in rows])


@interoperability_bp.route('/imports', methods=['GET'])
def api_imports_list():
    with db_session() as db:
        rows = db.execute('SELECT * FROM batch_imports ORDER BY id DESC').fetchall()
        return jsonify([dict(r) for r in rows])


@interoperability_bp.route('/exports/<int:export_id>', methods=['DELETE'])
def api_export_delete(export_id):
    with db_session() as db:
        row = db.execute('SELECT id FROM data_exports WHERE id = ?', (export_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Export record not found'}), 404
        db.execute('DELETE FROM data_exports WHERE id = ?', (export_id,))
        db.commit()
        log_activity('delete_export', service='interoperability',
                     detail=f'Deleted export record {export_id}')
    return jsonify({'deleted': True})


@interoperability_bp.route('/imports/<int:import_id>', methods=['DELETE'])
def api_import_delete(import_id):
    with db_session() as db:
        row = db.execute('SELECT id FROM batch_imports WHERE id = ?', (import_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Import record not found'}), 404
        db.execute('DELETE FROM batch_imports WHERE id = ?', (import_id,))
        db.commit()
        log_activity('delete_import', service='interoperability',
                     detail=f'Deleted import record {import_id}')
    return jsonify({'deleted': True})
