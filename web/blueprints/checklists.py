"""Checklists CRUD, templates, import/export, and dashboard progress routes."""

import json
import logging

from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename

from db import get_db, db_session
from web.utils import safe_json_list as _safe_json_list, close_db_safely as _close_db_safely
from web.sql_safety import safe_columns
from web.validation import validate_json
from web.checklist_templates_data import CHECKLIST_TEMPLATES

log = logging.getLogger('nomad.web')

checklists_bp = Blueprint('checklists', __name__)


@checklists_bp.route('/api/checklists')
def api_checklists_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    try:
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        offset = 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM checklists ORDER BY updated_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    result = []
    for r in rows:
        items = _safe_json_list(r['items'])
        result.append({
            'id': r['id'], 'name': r['name'], 'template': r['template'],
            'item_count': len(items),
            'checked_count': sum(1 for i in items if isinstance(i, dict) and i.get('checked')),
            'created_at': r['created_at'], 'updated_at': r['updated_at'],
        })
    return jsonify(result)


@checklists_bp.route('/api/checklists/templates')
def api_checklists_templates():
    return jsonify({k: {'name': v['name'], 'item_count': len(v['items'])} for k, v in CHECKLIST_TEMPLATES.items()})


@checklists_bp.route('/api/checklists', methods=['POST'])
@validate_json({
    'name': {'type': str, 'max_length': 300},
    'template': {'type': str, 'max_length': 100},
})
def api_checklists_create():
    data = request.get_json() or {}
    template_id = data.get('template', '')
    tmpl = CHECKLIST_TEMPLATES.get(template_id)
    if tmpl:
        name = tmpl['name']
        items = json.dumps(tmpl['items'])
    else:
        name = data.get('name', 'Custom Checklist')
        items = json.dumps(data.get('items', []))
    with db_session() as db:
        cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?, ?, ?)',
                         (name, template_id, items))
        db.commit()
        cid = cur.lastrowid
        row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
    return jsonify({**dict(row), 'items': _safe_json_list(row['items'])}), 201


@checklists_bp.route('/api/checklists/<int:cid>')
def api_checklists_get(cid):
    with db_session() as db:
        row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
    if not row:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({**dict(row), 'items': _safe_json_list(row['items'])})


@checklists_bp.route('/api/checklists/<int:cid>', methods=['PUT'])
def api_checklists_update(cid):
    data = request.get_json() or {}
    with db_session() as db:
        if not db.execute('SELECT 1 FROM checklists WHERE id = ?', (cid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        update_data = {}
        if 'name' in data:
            update_data['name'] = data['name']
        if 'items' in data:
            update_data['items'] = json.dumps(data['items'])
        filtered = safe_columns(update_data, ['name', 'items'])
        if filtered:
            set_clause = ', '.join(f'{col} = ?' for col in filtered)
            vals = list(filtered.values())
            vals.append(cid)
            db.execute(f'UPDATE checklists SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    return jsonify({'status': 'saved'})


@checklists_bp.route('/api/checklists/<int:cid>', methods=['DELETE'])
def api_checklists_delete(cid):
    with db_session() as db:
        r = db.execute('DELETE FROM checklists WHERE id = ?', (cid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@checklists_bp.route('/api/checklists/<int:cid>/clone', methods=['POST'])
def api_checklist_clone(cid):
    with db_session() as db:
        row = db.execute('SELECT * FROM checklists WHERE id=?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        d = dict(row)
        cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?,?,?)',
            (d.get('name', '') + ' (copy)', d.get('template', ''), d.get('items', '[]')))
        db.commit()
        new_id = cur.lastrowid
    return jsonify({'status': 'cloned', 'id': new_id})


@checklists_bp.route('/api/checklists/<int:cid>/export-json')
def api_checklist_export_json(cid):
    db = None
    try:
        db = get_db()
        row = db.execute('SELECT * FROM checklists WHERE id = ?', (cid,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        export = {'type': 'nomad_checklist', 'version': 1,
                  'name': row['name'], 'template': row['template'],
                  'items': _safe_json_list(row['items'])}
        safe_name = secure_filename(row['name']) or 'checklist'
        return Response(json.dumps(export, indent=2), mimetype='application/json',
                       headers={'Content-Disposition': f'attachment; filename="{safe_name}.json"'})
    except Exception as e:
        log.error('Request failed: %s', e)
        return jsonify({'error': 'Internal server error'}), 500
    finally:
        _close_db_safely(db, 'checklist export')


@checklists_bp.route('/api/checklists/import-json', methods=['POST'])
def api_checklist_import_json():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    db = None
    try:
        raw = file.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            return jsonify({'error': 'File exceeds 2MB limit'}), 400
        try:
            data = json.loads(raw.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return jsonify({'error': 'Invalid JSON file'}), 400
        if data.get('type') != 'nomad_checklist':
            return jsonify({'error': 'Invalid checklist file'}), 400
        db = get_db()
        cur = db.execute('INSERT INTO checklists (name, template, items) VALUES (?, ?, ?)',
                         (data['name'], data.get('template', 'imported'), json.dumps(data['items'])))
        db.commit()
        return jsonify({'status': 'imported', 'id': cur.lastrowid})
    except Exception as e:
        log.warning('Checklist import failed: %s', e)
        return jsonify({'error': 'Import failed -- check file format'}), 400
    finally:
        _close_db_safely(db, 'checklist import')


@checklists_bp.route('/api/dashboard/checklists')
def api_dashboard_checklists():
    with db_session() as db:
        rows = db.execute('SELECT id, name, items FROM checklists ORDER BY updated_at DESC LIMIT 5').fetchall()
    result = []
    for r in rows:
        items = _safe_json_list(r['items'])
        total = len(items)
        checked = sum(1 for i in items if isinstance(i, dict) and i.get('checked'))
        result.append({'id': r['id'], 'name': r['name'], 'total': total, 'checked': checked,
                      'pct': round(checked / total * 100) if total > 0 else 0})
    return jsonify(result)
