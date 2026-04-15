"""Financial preparedness tracker — cash, precious metals, barter goods, and documents."""

import logging
from datetime import datetime, timedelta

from flask import Blueprint, request, jsonify

from db import db_session, log_activity
from web.blueprints import get_pagination
from web.sql_safety import safe_columns
from web.validation import validate_json
from web.auth import require_auth

# Reusable validation schemas — audit H2.
_CASH_SCHEMA = {
    'denomination': {'type': str, 'max_length': 50},
    'amount': {'type': (int, float), 'min': 0, 'max': 1_000_000_000},
    'location': {'type': str, 'max_length': 200},
    'currency': {'type': str, 'max_length': 10},
    'notes': {'type': str, 'max_length': 2000},
}
_METALS_SCHEMA = {
    'metal_type': {'type': str, 'max_length': 50},
    'form': {'type': str, 'max_length': 50},
    'description': {'type': str, 'max_length': 500},
    'weight_oz': {'type': (int, float), 'min': 0, 'max': 1_000_000},
    'purity': {'type': (int, float), 'min': 0, 'max': 1},
    'purchase_price': {'type': (int, float), 'min': 0, 'max': 1_000_000_000},
    'location': {'type': str, 'max_length': 200},
    'notes': {'type': str, 'max_length': 2000},
}
_BARTER_SCHEMA = {
    'name': {'type': str, 'required': True, 'max_length': 200},
    'category': {'type': str, 'max_length': 50},
    'quantity': {'type': (int, float), 'min': 0, 'max': 1_000_000},
    'unit': {'type': str, 'max_length': 20},
    'estimated_value': {'type': (int, float), 'min': 0, 'max': 1_000_000_000},
    'location': {'type': str, 'max_length': 200},
    'notes': {'type': str, 'max_length': 2000},
}
_DOCUMENTS_SCHEMA = {
    'doc_type': {'type': str, 'max_length': 50},
    'description': {'type': str, 'max_length': 500},
    'account_number': {'type': str, 'max_length': 100},
    'institution': {'type': str, 'max_length': 200},
    'expiration': {'type': str, 'max_length': 50},
    'location': {'type': str, 'max_length': 200},
    'digital_copy': {'type': (str, int, bool), 'max_length': 500},
    'notes': {'type': str, 'max_length': 2000},
}

log = logging.getLogger('nomad.web')

financial_bp = Blueprint('financial', __name__)

# ─── Helpers ──────────────────────────────────────────────────────────

CASH_ALLOWED = ['denomination', 'amount', 'location', 'currency', 'notes']
METALS_ALLOWED = ['metal_type', 'form', 'description', 'weight_oz', 'purity',
                  'purchase_price', 'location', 'notes']
BARTER_ALLOWED = ['name', 'category', 'quantity', 'unit', 'estimated_value',
                  'location', 'notes']
DOCUMENTS_ALLOWED = ['doc_type', 'description', 'account_number', 'institution',
                     'expiration', 'location', 'digital_copy', 'notes']

BARTER_CATEGORIES = [
    'alcohol', 'tobacco', 'ammo', 'batteries', 'fuel',
    'medical', 'tools', 'food', 'hygiene', 'other',
]


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _get_setting(db, key, default=None):
    """Read a value from the settings table."""
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row['value'] if row else default


# ─── Cash CRUD ────────────────────────────────────────────────────────

@financial_bp.route('/api/financial/cash')
def api_cash_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM financial_cash ORDER BY location, denomination LIMIT ? OFFSET ?',
            get_pagination(),
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@financial_bp.route('/api/financial/cash', methods=['POST'])
@require_auth('admin')
@validate_json(_CASH_SCHEMA)
def api_cash_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO financial_cash
               (denomination, amount, location, currency, notes)
               VALUES (?, ?, ?, ?, ?)''',
            (data.get('denomination', ''),
             _safe_float(data.get('amount', 0)),
             data.get('location', ''),
             data.get('currency', 'USD'),
             data.get('notes', '')))
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_cash WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    log_activity('financial_cash_added', 'financial',
                 f"Cash: {data.get('denomination', '')} x {data.get('amount', 0)}")
    return jsonify(dict(row)), 201


@financial_bp.route('/api/financial/cash/<int:item_id>', methods=['PUT'])
@require_auth('admin')
@validate_json(_CASH_SCHEMA)
def api_cash_update(item_id):
    data = request.get_json() or {}
    filtered = safe_columns(data, CASH_ALLOWED)
    if not filtered:
        return jsonify({'error': 'No fields to update'}), 400
    if 'amount' in filtered:
        filtered['amount'] = _safe_float(filtered['amount'])
    with db_session() as db:
        if not db.execute(
            'SELECT 1 FROM financial_cash WHERE id = ?', (item_id,)
        ).fetchone():
            return jsonify({'error': 'not found'}), 404
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values()) + [item_id]
        db.execute(
            f'UPDATE financial_cash SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            vals)
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_cash WHERE id = ?', (item_id,)
        ).fetchone()
    return jsonify(dict(row))


@financial_bp.route('/api/financial/cash/<int:item_id>', methods=['DELETE'])
def api_cash_delete(item_id):
    with db_session() as db:
        r = db.execute('DELETE FROM financial_cash WHERE id = ?', (item_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Precious Metals CRUD ────────────────────────────────────────────

@financial_bp.route('/api/financial/metals')
def api_metals_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM financial_metals ORDER BY metal_type, form LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@financial_bp.route('/api/financial/metals', methods=['POST'])
@require_auth('admin')
@validate_json(_METALS_SCHEMA)
def api_metals_create():
    data = request.get_json() or {}
    metal_type = data.get('metal_type', 'gold')
    if metal_type not in ('gold', 'silver', 'platinum'):
        metal_type = 'gold'
    form = data.get('form', 'coin')
    if form not in ('coin', 'bar', 'round', 'jewelry'):
        form = 'coin'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO financial_metals
               (metal_type, form, description, weight_oz, purity,
                purchase_price, location, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (metal_type, form,
             data.get('description', ''),
             _safe_float(data.get('weight_oz', 0)),
             _safe_float(data.get('purity', 0.999)),
             _safe_float(data.get('purchase_price', 0)),
             data.get('location', ''),
             data.get('notes', '')))
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_metals WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    log_activity('financial_metal_added', 'financial',
                 f"{metal_type} {form}: {data.get('weight_oz', 0)} oz")
    return jsonify(dict(row)), 201


@financial_bp.route('/api/financial/metals/<int:item_id>', methods=['PUT'])
@require_auth('admin')
@validate_json(_METALS_SCHEMA)
def api_metals_update(item_id):
    data = request.get_json() or {}
    filtered = safe_columns(data, METALS_ALLOWED)
    if not filtered:
        return jsonify({'error': 'No fields to update'}), 400
    for num_field in ('weight_oz', 'purity', 'purchase_price'):
        if num_field in filtered:
            filtered[num_field] = _safe_float(filtered[num_field])
    if 'metal_type' in filtered and filtered['metal_type'] not in ('gold', 'silver', 'platinum'):
        filtered['metal_type'] = 'gold'
    if 'form' in filtered and filtered['form'] not in ('coin', 'bar', 'round', 'jewelry'):
        filtered['form'] = 'coin'
    with db_session() as db:
        if not db.execute(
            'SELECT 1 FROM financial_metals WHERE id = ?', (item_id,)
        ).fetchone():
            return jsonify({'error': 'not found'}), 404
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values()) + [item_id]
        db.execute(
            f'UPDATE financial_metals SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            vals)
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_metals WHERE id = ?', (item_id,)
        ).fetchone()
    return jsonify(dict(row))


@financial_bp.route('/api/financial/metals/<int:item_id>', methods=['DELETE'])
def api_metals_delete(item_id):
    with db_session() as db:
        r = db.execute('DELETE FROM financial_metals WHERE id = ?', (item_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Barter Goods CRUD ───────────────────────────────────────────────

@financial_bp.route('/api/financial/barter')
def api_barter_list():
    with db_session() as db:
        category = request.args.get('category', '').strip()
        limit, offset = get_pagination()
        if category and category in BARTER_CATEGORIES:
            rows = db.execute(
                'SELECT * FROM financial_barter WHERE category = ? ORDER BY category, name LIMIT ? OFFSET ?',
                (category, limit, offset)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM financial_barter ORDER BY category, name LIMIT ? OFFSET ?',
                (limit, offset)
            ).fetchall()
    return jsonify([dict(r) for r in rows])


@financial_bp.route('/api/financial/barter', methods=['POST'])
@require_auth('admin')
@validate_json(_BARTER_SCHEMA)
def api_barter_create():
    data = request.get_json() or {}
    category = data.get('category', 'other')
    if category not in BARTER_CATEGORIES:
        category = 'other'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO financial_barter
               (name, category, quantity, unit, estimated_value, location, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (data.get('name', ''),
             category,
             _safe_float(data.get('quantity', 0)),
             data.get('unit', 'ea'),
             _safe_float(data.get('estimated_value', 0)),
             data.get('location', ''),
             data.get('notes', '')))
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_barter WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    log_activity('financial_barter_added', 'financial',
                 f"Barter: {data.get('name', '')} x {data.get('quantity', 0)}")
    return jsonify(dict(row)), 201


@financial_bp.route('/api/financial/barter/<int:item_id>', methods=['PUT'])
@require_auth('admin')
@validate_json(_BARTER_SCHEMA)
def api_barter_update(item_id):
    data = request.get_json() or {}
    filtered = safe_columns(data, BARTER_ALLOWED)
    if not filtered:
        return jsonify({'error': 'No fields to update'}), 400
    for num_field in ('quantity', 'estimated_value'):
        if num_field in filtered:
            filtered[num_field] = _safe_float(filtered[num_field])
    if 'category' in filtered and filtered['category'] not in BARTER_CATEGORIES:
        filtered['category'] = 'other'
    with db_session() as db:
        if not db.execute(
            'SELECT 1 FROM financial_barter WHERE id = ?', (item_id,)
        ).fetchone():
            return jsonify({'error': 'not found'}), 404
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values()) + [item_id]
        db.execute(
            f'UPDATE financial_barter SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            vals)
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_barter WHERE id = ?', (item_id,)
        ).fetchone()
    return jsonify(dict(row))


@financial_bp.route('/api/financial/barter/<int:item_id>', methods=['DELETE'])
def api_barter_delete(item_id):
    with db_session() as db:
        r = db.execute('DELETE FROM financial_barter WHERE id = ?', (item_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Financial Documents CRUD ────────────────────────────────────────

DOCUMENT_TYPES = [
    'insurance', 'deed', 'title', 'account', 'id',
    'passport', 'license', 'other',
]


@financial_bp.route('/api/financial/documents')
def api_documents_list():
    with db_session() as db:
        rows = db.execute(
            'SELECT * FROM financial_documents ORDER BY doc_type, description LIMIT ? OFFSET ?',
            get_pagination()
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@financial_bp.route('/api/financial/documents', methods=['POST'])
@require_auth('admin')
@validate_json(_DOCUMENTS_SCHEMA)
def api_documents_create():
    data = request.get_json() or {}
    doc_type = data.get('doc_type', 'other')
    if doc_type not in DOCUMENT_TYPES:
        doc_type = 'other'
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO financial_documents
               (doc_type, description, account_number, institution,
                expiration, location, digital_copy, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (doc_type,
             data.get('description', ''),
             data.get('account_number', ''),
             data.get('institution', ''),
             data.get('expiration', ''),
             data.get('location', ''),
             1 if data.get('digital_copy') else 0,
             data.get('notes', '')))
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_documents WHERE id = ?', (cur.lastrowid,)
        ).fetchone()
    log_activity('financial_document_added', 'financial',
                 f"Document: {doc_type} — {data.get('description', '')}")
    return jsonify(dict(row)), 201


@financial_bp.route('/api/financial/documents/<int:item_id>', methods=['PUT'])
@require_auth('admin')
@validate_json(_DOCUMENTS_SCHEMA)
def api_documents_update(item_id):
    data = request.get_json() or {}
    filtered = safe_columns(data, DOCUMENTS_ALLOWED)
    if not filtered:
        return jsonify({'error': 'No fields to update'}), 400
    if 'doc_type' in filtered and filtered['doc_type'] not in DOCUMENT_TYPES:
        filtered['doc_type'] = 'other'
    if 'digital_copy' in filtered:
        filtered['digital_copy'] = 1 if filtered['digital_copy'] else 0
    with db_session() as db:
        if not db.execute(
            'SELECT 1 FROM financial_documents WHERE id = ?', (item_id,)
        ).fetchone():
            return jsonify({'error': 'not found'}), 404
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values()) + [item_id]
        db.execute(
            f'UPDATE financial_documents SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            vals)
        db.commit()
        row = db.execute(
            'SELECT * FROM financial_documents WHERE id = ?', (item_id,)
        ).fetchone()
    return jsonify(dict(row))


@financial_bp.route('/api/financial/documents/<int:item_id>', methods=['DELETE'])
def api_documents_delete(item_id):
    with db_session() as db:
        r = db.execute('DELETE FROM financial_documents WHERE id = ?', (item_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# ─── Dashboard ────────────────────────────────────────────────────────

@financial_bp.route('/api/financial/dashboard')
def api_financial_dashboard():
    with db_session() as db:
        # Cash totals
        total_cash = db.execute(
            'SELECT COALESCE(SUM(amount), 0) AS total FROM financial_cash'
        ).fetchone()['total']

        cash_by_location = db.execute(
            '''SELECT location, SUM(amount) AS total
               FROM financial_cash GROUP BY location ORDER BY total DESC'''
        ).fetchall()

        # Metals totals
        metals_by_type = db.execute(
            '''SELECT metal_type, SUM(weight_oz) AS total_oz,
                      SUM(purchase_price) AS total_value
               FROM financial_metals GROUP BY metal_type'''
        ).fetchall()

        total_metals_value = db.execute(
            'SELECT COALESCE(SUM(purchase_price), 0) AS total FROM financial_metals'
        ).fetchone()['total']

        # Barter totals
        barter_categories = db.execute(
            '''SELECT category, COUNT(*) AS count,
                      SUM(estimated_value) AS total_value
               FROM financial_barter GROUP BY category ORDER BY category'''
        ).fetchall()

        total_barter_value = db.execute(
            'SELECT COALESCE(SUM(estimated_value), 0) AS total FROM financial_barter'
        ).fetchone()['total']

        # Documents
        documents_count = db.execute(
            'SELECT COUNT(*) AS c FROM financial_documents'
        ).fetchone()['c']

        cutoff = (datetime.now() + timedelta(days=90)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        documents_expiring_soon = db.execute(
            """SELECT COUNT(*) AS c FROM financial_documents
               WHERE expiration != '' AND expiration <= ? AND expiration >= ?""",
            (cutoff, today)
        ).fetchone()['c']

    total_preparedness_value = total_cash + total_metals_value + total_barter_value

    return jsonify({
        'total_cash': round(total_cash, 2),
        'cash_by_location': [
            {'location': r['location'] or 'Unspecified', 'total': round(r['total'], 2)}
            for r in cash_by_location
        ],
        'total_metals_oz': {
            r['metal_type']: round(r['total_oz'], 4) for r in metals_by_type
        },
        'total_metals_value': round(total_metals_value, 2),
        'barter_categories': [
            {'category': r['category'], 'count': r['count'],
             'total_value': round(r['total_value'] or 0, 2)}
            for r in barter_categories
        ],
        'total_barter_value': round(total_barter_value, 2),
        'documents_count': documents_count,
        'documents_expiring_soon': documents_expiring_soon,
        'total_preparedness_value': round(total_preparedness_value, 2),
    })


# ─── Emergency Fund Tracker ──────────────────────────────────────────

@financial_bp.route('/api/financial/emergency-fund')
def api_emergency_fund():
    with db_session() as db:
        target = _safe_float(
            _get_setting(db, 'emergency_fund_target', '10000'), 10000
        )

        total_cash = db.execute(
            'SELECT COALESCE(SUM(amount), 0) AS total FROM financial_cash'
        ).fetchone()['total']

        total_metals_value = db.execute(
            'SELECT COALESCE(SUM(purchase_price), 0) AS total FROM financial_metals'
        ).fetchone()['total']

    current = total_cash + total_metals_value
    percentage = round((current / target * 100), 1) if target > 0 else 0
    remaining = max(target - current, 0)

    return jsonify({
        'target': round(target, 2),
        'current': round(current, 2),
        'percentage': percentage,
        'remaining': round(remaining, 2),
    })


# ─── Cost Per Day ────────────────────────────────────────────────────

@financial_bp.route('/api/financial/cost-per-day')
def api_cost_per_day():
    with db_session() as db:
        # Try query params first, fall back to computed / settings
        total_investment = request.args.get('total_investment')
        days_of_autonomy = request.args.get('days_of_autonomy')

        if total_investment is not None:
            total_investment = _safe_float(total_investment, 0)
        else:
            total_cash = db.execute(
                'SELECT COALESCE(SUM(amount), 0) AS total FROM financial_cash'
            ).fetchone()['total']
            total_metals = db.execute(
                'SELECT COALESCE(SUM(purchase_price), 0) AS total FROM financial_metals'
            ).fetchone()['total']
            total_barter = db.execute(
                'SELECT COALESCE(SUM(estimated_value), 0) AS total FROM financial_barter'
            ).fetchone()['total']
            total_investment = total_cash + total_metals + total_barter

        if days_of_autonomy is not None:
            days_of_autonomy = _safe_float(days_of_autonomy, 90)
        else:
            days_of_autonomy = _safe_float(
                _get_setting(db, 'autonomy_days_target', '90'), 90
            )

    if days_of_autonomy <= 0:
        days_of_autonomy = 90

    cost_per_day = total_investment / days_of_autonomy

    return jsonify({
        'total_investment': round(total_investment, 2),
        'days_of_autonomy': round(days_of_autonomy, 1),
        'cost_per_day': round(cost_per_day, 2),
    })


# ─── Summary ─────────────────────────────────────────────────────────

@financial_bp.route('/api/financial/summary')
def api_financial_summary():
    with db_session() as db:
        total_cash = db.execute(
            'SELECT COALESCE(SUM(amount), 0) AS total FROM financial_cash'
        ).fetchone()['total']

        metals_count = db.execute(
            'SELECT COUNT(*) AS c FROM financial_metals'
        ).fetchone()['c']

        barter_items_count = db.execute(
            'SELECT COUNT(*) AS c FROM financial_barter'
        ).fetchone()['c']

        documents_count = db.execute(
            'SELECT COUNT(*) AS c FROM financial_documents'
        ).fetchone()['c']

        total_metals_value = db.execute(
            'SELECT COALESCE(SUM(purchase_price), 0) AS total FROM financial_metals'
        ).fetchone()['total']

        total_barter_value = db.execute(
            'SELECT COALESCE(SUM(estimated_value), 0) AS total FROM financial_barter'
        ).fetchone()['total']

    total_value = total_cash + total_metals_value + total_barter_value

    return jsonify({
        'total_cash': round(total_cash, 2),
        'metals_count': metals_count,
        'barter_items_count': barter_items_count,
        'documents_count': documents_count,
        'total_value': round(total_value, 2),
    })
