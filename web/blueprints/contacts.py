"""Contacts CRUD, export/import CSV, and printable directory routes."""

import csv
import io
import logging
import time

from flask import Blueprint, request, jsonify, Response

from db import db_session, log_activity
from web.auth import require_auth
from web.print_templates import render_print_document
from web.sql_safety import safe_columns
from web.validation import validate_json
from web.utils import (
    csv_safe as _csv_safe,
    esc as _esc,
    require_json_body as _require_json_body,
    validate_bulk_ids as _validate_bulk_ids,
)

log = logging.getLogger('nomad.web')

contacts_bp = Blueprint('contacts', __name__)

CONTACT_SORT_FIELDS = {'name', 'callsign', 'role', 'created_at', 'updated_at'}

# Reusable validation schema — audit H2 rollout (v7.32.0).
_CONTACT_SCHEMA = {
    'name': {'type': str, 'max_length': 200},
    'callsign': {'type': str, 'max_length': 50},
    'role': {'type': str, 'max_length': 100},
    'skills': {'type': str, 'max_length': 2000},
    'phone': {'type': str, 'max_length': 50},
    'freq': {'type': str, 'max_length': 50},
    'email': {'type': str, 'max_length': 200},
    'address': {'type': str, 'max_length': 500},
    'rally_point': {'type': str, 'max_length': 200},
    'blood_type': {'type': str, 'max_length': 10},
    'medical_notes': {'type': str, 'max_length': 2000},
    'notes': {'type': str, 'max_length': 4000},
}
_CONTACT_CREATE_SCHEMA = dict(_CONTACT_SCHEMA, name={'type': str, 'required': True, 'max_length': 200})

_CONTACTS_ALLOWED_FIELDS = frozenset({'name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email', 'address', 'rally_point', 'blood_type', 'medical_notes', 'notes'})


# ─── Contacts CRUD ────────────────────────────────────────────────────

@contacts_bp.route('/api/contacts')
def api_contacts_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    sort_by = request.args.get('sort_by', 'name')
    sort_dir = 'DESC' if request.args.get('sort_dir', 'asc').lower() == 'desc' else 'ASC'
    if sort_by not in CONTACT_SORT_FIELDS:
        sort_by = 'name'
    with db_session() as db:
        search = request.args.get('q', '').strip()
        if search:
            rows = db.execute(
                f"SELECT * FROM contacts WHERE name LIKE ? OR callsign LIKE ? OR role LIKE ? OR skills LIKE ? ORDER BY {sort_by} {sort_dir} LIMIT ? OFFSET ?",
                tuple(f'%{search}%' for _ in range(4)) + (limit, offset)
            ).fetchall()
        else:
            rows = db.execute(f'SELECT * FROM contacts ORDER BY {sort_by} {sort_dir} LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@contacts_bp.route('/api/contacts', methods=['POST'])
@require_auth('admin')
@validate_json(_CONTACT_CREATE_SCHEMA)
def api_contacts_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO contacts (name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('callsign', ''), data.get('role', ''),
             data.get('skills', ''), data.get('phone', ''), data.get('freq', ''),
             data.get('email', ''), data.get('address', ''), data.get('rally_point', ''),
             data.get('blood_type', ''), data.get('medical_notes', ''), data.get('notes', '')))
        db.commit()
        cid = cur.lastrowid
        row = db.execute('SELECT * FROM contacts WHERE id = ?', (cid,)).fetchone()
    log_activity('contact_created', service='contacts', detail=data.get('name', '')[:80])
    return jsonify(dict(row)), 201


@contacts_bp.route('/api/contacts/<int:cid>', methods=['PUT'])
@require_auth('admin')
@validate_json(_CONTACT_SCHEMA)
def api_contacts_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM contacts WHERE id = ?', (cid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        allowed = _CONTACTS_ALLOWED_FIELDS
        filtered = safe_columns(data, allowed)
        if not filtered:
            return jsonify({'error': 'No fields'}), 400
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values())
        vals.append(cid)
        db.execute(f'UPDATE contacts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    log_activity('contact_updated', service='contacts', detail=f'id={cid}')
    return jsonify({'status': 'saved'})


@contacts_bp.route('/api/contacts/<int:cid>', methods=['DELETE'])
@require_auth('admin')
def api_contacts_delete(cid):
    with db_session() as db:
        r = db.execute('DELETE FROM contacts WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    log_activity('contact_deleted', service='contacts', detail=f'id={cid}')
    return jsonify({'status': 'deleted'})


@contacts_bp.route('/api/contacts/bulk-delete', methods=['POST'])
@require_auth('admin')
def api_contacts_bulk_delete():
    data, error = _require_json_body(request)
    if error:
        return error
    ids = _validate_bulk_ids(data)
    if ids is None:
        return jsonify({'error': 'ids array of integers required (max 100)'}), 400
    with db_session() as db:
        placeholders = ','.join('?' * len(ids))
        r = db.execute(f'DELETE FROM contacts WHERE id IN ({placeholders})', ids)
        db.commit()
    return jsonify({'status': 'deleted', 'count': r.rowcount})


# ─── Contacts Export/Import ───────────────────────────────────────────

_CONTACTS_CSV_COLUMNS = [
    'name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email',
    'address', 'rally_point', 'blood_type', 'medical_notes', 'notes',
]
_CONTACTS_CSV_HEADERS = [
    'Name', 'Callsign', 'Role', 'Skills', 'Phone', 'Frequency', 'Email',
    'Address', 'Rally Point', 'Blood Type', 'Medical Notes', 'Notes',
]


def _write_contacts_csv(rows, filename):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(_CONTACTS_CSV_HEADERS)
    for r in rows:
        # Neutralize CSV formula injection — a contact name like "=1+1" is
        # stored as data but becomes a live formula in Excel/Sheets unless
        # prefixed with a single quote.
        w.writerow([_csv_safe(r[col]) for col in _CONTACTS_CSV_COLUMNS])
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )


@contacts_bp.route('/api/contacts/export-csv')
def api_contacts_csv():
    with db_session() as db:
        rows = db.execute(
            'SELECT name, callsign, role, skills, phone, freq, email, address, '
            'rally_point, blood_type, medical_notes, notes FROM contacts '
            'ORDER BY name LIMIT 10000'
        ).fetchall()
    return _write_contacts_csv(rows, 'nomad-contacts.csv')


@contacts_bp.route('/api/contacts/export')
def api_contacts_export():
    """Export all contacts as CSV with Content-Disposition."""
    try:
        with db_session() as db:
            rows = db.execute(
                'SELECT name, callsign, role, skills, phone, freq, email, address, '
                'rally_point, blood_type, medical_notes, notes FROM contacts '
                'ORDER BY name LIMIT 10000'
            ).fetchall()
        return _write_contacts_csv(rows, 'nomad_contacts_export.csv')
    except Exception:
        log.exception('Contact export failed')
        return jsonify({'error': 'Export failed'}), 500


@contacts_bp.route('/api/contacts/import-csv', methods=['POST'])
@require_auth('admin')
def api_contacts_import_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    file = request.files['file']
    try:
        raw = file.read()
        if len(raw) > 10 * 1024 * 1024:
            return jsonify({'error': 'File too large (max 10 MB)'}), 400
        try:
            content = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            content = raw.decode('latin-1')
        reader = csv.DictReader(io.StringIO(content))
        with db_session() as db:
            imported = 0
            for row in reader:
                name = row.get('Name', row.get('name', '')).strip()
                if not name:
                    continue
                db.execute(
                    'INSERT INTO contacts (name, callsign, role, skills, phone, freq, email, address, rally_point, blood_type, medical_notes, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (name, row.get('Callsign', row.get('callsign', '')),
                     row.get('Role', row.get('role', '')),
                     row.get('Skills', row.get('skills', '')),
                     row.get('Phone', row.get('phone', '')),
                     row.get('Frequency', row.get('freq', '')),
                     row.get('Email', row.get('email', '')),
                     row.get('Address', row.get('address', '')),
                     row.get('Rally Point', row.get('rally_point', '')),
                     row.get('Blood Type', row.get('blood_type', '')),
                     row.get('Medical Notes', row.get('medical_notes', '')),
                     row.get('Notes', row.get('notes', ''))))
                imported += 1
            db.commit()
        return jsonify({'status': 'imported', 'count': imported})
    except Exception as e:
        log.error(f'CSV import failed: {e}')
        return jsonify({'error': 'Import failed. Check server logs for details.'}), 500


# ─── Contacts Print ──────────────────────────────────────────────────

@contacts_bp.route('/api/contacts/print')
def api_contacts_print():
    """Printable contacts directory."""
    with db_session() as db:
        contacts = db.execute('SELECT * FROM contacts ORDER BY name LIMIT 10000').fetchall()
    now = time.strftime('%Y-%m-%d %H:%M')
    rally_points = sorted({dict(c).get('rally_point', '').strip() for c in contacts if dict(c).get('rally_point', '').strip()})
    callsign_count = sum(1 for c in contacts if dict(c).get('callsign'))
    phone_count = sum(1 for c in contacts if dict(c).get('phone'))

    directory_html = '<div class="doc-empty">No contacts have been entered yet.</div>'
    if contacts:
        directory_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Role</th><th>Phone</th><th>Callsign</th><th>Radio Freq</th><th>Blood</th><th>Rally Point</th><th>Skills</th><th>Medical Notes</th></tr></thead><tbody>'
        for c in contacts:
            d = dict(c)
            directory_html += (
                f"<tr><td class=\"doc-strong\">{_esc(d['name'])}</td><td>{_esc(d.get('role','')) or '-'}</td>"
                f"<td>{_esc(d.get('phone','')) or '-'}</td><td>{_esc(d.get('callsign','')) or '-'}</td>"
                f"<td>{_esc(d.get('freq','')) or '-'}</td><td>{_esc(d.get('blood_type','')) or '-'}</td>"
                f"<td>{_esc(d.get('rally_point','')) or '-'}</td><td>{_esc(d.get('skills','')) or '-'}</td>"
                f"<td>{_esc(d.get('medical_notes','')) or '-'}</td></tr>"
            )
        directory_html += '</tbody></table></div>'

    rally_html = '<div class="doc-empty">No rally points are assigned to contacts yet.</div>'
    if rally_points:
        rally_html = '<div class="doc-chip-list">' + ''.join(f'<span class="doc-chip">{_esc(point)}</span>' for point in rally_points) + '</div>'

    body = f'''<section class="doc-section">
  <h2 class="doc-section-title">Contact Directory</h2>
  {directory_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Known Rally Points</h2>
      {rally_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Use Notes</h2>
      <div class="doc-kv">
        <div class="doc-kv-row"><div class="doc-kv-key">Carry Copy</div><div>Keep one printed copy in the go-bag and one near radios or the exit route.</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Priority Fields</div><div>Name, role, phone, callsign, rally point, and key medical notes should stay current.</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Review Cadence</div><div>Verify numbers, channels, and rally points after every plan change or quarterly at minimum.</div></div>
      </div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Printable contact reference for quick retrieval during movement, comms checks, or handoff.</span>
    <span>Generated by NOMAD Field Desk.</span>
  </div>
</section>'''
    html = render_print_document(
        'Contact Directory',
        'Printable roster for emergency contacts, radio identifiers, rally points, and critical notes.',
        body,
        eyebrow='NOMAD Field Desk Contacts',
        meta_items=[f'Generated {now}', 'Letter print layout'],
        stat_items=[
            ('Contacts', len(contacts)),
            ('With Callsigns', callsign_count),
            ('With Phones', phone_count),
            ('Rally Points', len(rally_points)),
        ],
        accent_start='#163049',
        accent_end='#43607a',
        max_width='1120px',
    )
    return html
