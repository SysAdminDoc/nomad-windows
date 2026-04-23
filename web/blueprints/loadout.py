"""Bug-Out Bag Loadout Manager — persistent bag profiles with full CRUD.

Complements the ephemeral kit_builder wizard by storing concrete bag
inventories that can be maintained, inspected, and cloned over time.

Tables (created in db.py):
    loadout_bags   — bag profiles (72hour, get-home, INCH, EDC, etc.)
    loadout_items  — items inside each bag with weight, packed status,
                     expiration tracking, and category tagging.
"""

import logging
from datetime import date, datetime, timedelta

from flask import Blueprint, request, jsonify
from db import get_db, db_session, log_activity

_log = logging.getLogger(__name__)

loadout_bp = Blueprint('loadout', __name__)

_BAG_TYPES = {'72hour', 'get-home', 'inch', 'edc', 'medical', 'vehicle'}
_SEASONS = {'all', 'summer', 'winter', 'spring', 'fall'}
_ITEM_CATEGORIES = {
    'water', 'food', 'shelter', 'fire', 'medical', 'comms',
    'navigation', 'tools', 'clothing', 'hygiene', 'documents', 'other',
}

# Fields allowed in PUT updates (allow-list pattern).
_BAG_ALLOWED = {
    'name', 'owner', 'bag_type', 'season', 'target_weight_lb',
    'location', 'last_inspected', 'photo_path', 'notes',
}
_ITEM_ALLOWED = {
    'name', 'category', 'quantity', 'weight_oz', 'packed',
    'expiration', 'notes',
}


# ─── helpers ──────────────────────────────────────────────────────────

def _row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def _today_iso():
    return date.today().isoformat()


def _ninety_days_from_now():
    return (date.today() + timedelta(days=90)).isoformat()


def _bag_not_found():
    return jsonify({'error': 'Bag not found'}), 404


def _item_not_found():
    return jsonify({'error': 'Item not found'}), 404


# ─── Loadout Templates (CE-10, v7.61) ──────────────────────────────

@loadout_bp.route('/api/loadout/templates')
def api_loadout_templates():
    """Return curated loadout bag templates (CE-10, v7.61).

    15 templates covering 72-hr adult/kid, EDC, get-home short/long, INCH,
    vehicle (temperate/winter/desert), IFAK+, canoe/boat, winter mountain,
    desert 72-hr, backcountry 3-day, urban/apartment. Each template has a
    bag-level config (name, type, season, target weight, description,
    use_case) and an item list (name, category, quantity, weight_oz, notes).

    The UI offers "create bag from template" — it reads this endpoint, lets
    the user pick one, then POSTs the bag to /api/loadout/bags and each item
    to /api/loadout/bags/<id>/items.
    """
    try:
        from seeds.loadout_templates import LOADOUT_TEMPLATES
    except Exception as exc:
        return jsonify({'error': f'loadout templates unavailable: {exc}'}), 500

    out = []
    for t in LOADOUT_TEMPLATES:
        total_oz = sum((it[2] or 1) * (it[3] or 0) for it in t['items'])
        out.append({
            'name': t['name'],
            'bag_type': t['bag_type'],
            'season': t['season'],
            'target_weight_lb': t['target_weight_lb'],
            'description': t['description'],
            'use_case': t['use_case'],
            'item_count': len(t['items']),
            'computed_weight_oz': round(total_oz, 1),
            'computed_weight_lb': round(total_oz / 16.0, 1),
            'items': [
                {
                    'name': name, 'category': cat, 'quantity': qty,
                    'weight_oz': w, 'notes': notes,
                }
                for (name, cat, qty, w, notes) in t['items']
            ],
        })
    return jsonify({'count': len(out), 'templates': out})


@loadout_bp.route('/api/loadout/templates/launch', methods=['POST'])
def api_loadout_templates_launch():
    """Create a bag + populate it from a template in a single transaction.

    Request body:
        {"template_name": "72-Hour Bag — Adult",
         "owner": "optional",
         "location": "optional",
         "rename_to": "optional override"}

    The newly-created bag's id is returned along with the count of items
    added. Items are created with packed=0 so the user can check them off
    as they assemble the bag.
    """
    data = request.get_json() or {}
    template_name = (data.get('template_name') or '').strip()
    if not template_name:
        return jsonify({'error': 'template_name is required'}), 400

    try:
        from seeds.loadout_templates import LOADOUT_TEMPLATES
    except Exception as exc:
        return jsonify({'error': f'loadout templates unavailable: {exc}'}), 500

    template = next(
        (t for t in LOADOUT_TEMPLATES if t['name'] == template_name),
        None,
    )
    if template is None:
        return jsonify({'error': f'template not found: {template_name}'}), 404

    bag_name = (data.get('rename_to') or '').strip() or template['name']
    owner = (data.get('owner') or '').strip()
    location = (data.get('location') or '').strip()

    with db_session() as db:
        cur = db.execute(
            'INSERT INTO loadout_bags (name, owner, bag_type, season, '
            'target_weight_lb, location, notes) '
            'VALUES (?, ?, ?, ?, ?, ?, ?)',
            (
                bag_name, owner, template['bag_type'], template['season'],
                template['target_weight_lb'], location,
                f"Created from template: {template['name']}\n\n"
                f"{template['description']}\n\nUse case: {template['use_case']}",
            ),
        )
        bag_id = cur.lastrowid
        for (name, cat, qty, w, notes) in template['items']:
            db.execute(
                'INSERT INTO loadout_items (bag_id, name, category, '
                'quantity, weight_oz, packed, notes) '
                'VALUES (?, ?, ?, ?, ?, 0, ?)',
                (bag_id, name, cat, qty, w, notes),
            )
        db.commit()

    try:
        log_activity('loadout_template_launched', template_name,
                     f'bag_id={bag_id}, items={len(template["items"])}')
    except Exception:
        pass

    return jsonify({
        'status': 'created',
        'bag_id': bag_id,
        'item_count': len(template['items']),
        'template_name': template['name'],
    }), 201


# ─── Bag CRUD ─────────────────────────────────────────────────────────

@loadout_bp.route('/api/loadout/bags')
def api_loadout_bags_list():
    """List all bags with computed item_count and total_weight."""
    with db_session() as db:
        rows = db.execute('''
            SELECT b.*,
                   COALESCE(s.item_count, 0) AS item_count,
                   COALESCE(s.total_weight_oz, 0) AS total_weight_oz,
                   ROUND(COALESCE(s.total_weight_oz, 0) / 16.0, 2) AS total_weight_lb
            FROM loadout_bags b
            LEFT JOIN (
                SELECT bag_id,
                       COUNT(*) AS item_count,
                       SUM(weight_oz * quantity) AS total_weight_oz
                FROM loadout_items
                GROUP BY bag_id
            ) s ON s.bag_id = b.id
            ORDER BY b.updated_at DESC
        ''').fetchall()
    return jsonify([dict(r) for r in rows])


@loadout_bp.route('/api/loadout/bags', methods=['POST'])
def api_loadout_bags_create():
    """Create a new bag profile."""
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    bag_type = (d.get('bag_type') or '72hour').lower()
    if bag_type not in _BAG_TYPES:
        return jsonify({'error': f'Invalid bag_type. Expected one of {sorted(_BAG_TYPES)}'}), 400
    season = (d.get('season') or 'all').lower()
    if season not in _SEASONS:
        return jsonify({'error': f'Invalid season. Expected one of {sorted(_SEASONS)}'}), 400
    try:
        target_weight = float(d.get('target_weight_lb', 0)) if d.get('target_weight_lb') is not None else None
    except (ValueError, TypeError):
        target_weight = None

    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO loadout_bags
               (name, owner, bag_type, season, target_weight_lb,
                location, last_inspected, photo_path, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (name,
             (d.get('owner') or '').strip(),
             bag_type, season, target_weight,
             (d.get('location') or '').strip(),
             (d.get('last_inspected') or '').strip() or None,
             (d.get('photo_path') or '').strip() or None,
             (d.get('notes') or '').strip()))
        db.commit()
        row = db.execute('SELECT * FROM loadout_bags WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('loadout_bag_created', 'loadout', f'Bag "{name}" ({bag_type})')
    return jsonify(dict(row)), 201


@loadout_bp.route('/api/loadout/bags/<int:bag_id>')
def api_loadout_bags_get(bag_id):
    """Get a single bag with all items and computed stats."""
    with db_session() as db:
        bag = db.execute('SELECT * FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        items = db.execute(
            'SELECT * FROM loadout_items WHERE bag_id = ? ORDER BY category, name',
            (bag_id,)).fetchall()

    items_list = [dict(i) for i in items]
    total_weight_oz = sum((i['weight_oz'] or 0) * (i['quantity'] or 1) for i in items_list)
    packed_count = sum(1 for i in items_list if i.get('packed'))
    unpacked_count = len(items_list) - packed_count

    # Weight by category
    cat_weights = {}
    for i in items_list:
        cat = i.get('category') or 'other'
        cat_weights[cat] = cat_weights.get(cat, 0) + (i['weight_oz'] or 0) * (i['quantity'] or 1)

    weight_by_category = {cat: round(w, 2) for cat, w in sorted(cat_weights.items())}

    result = dict(bag)
    result['items'] = items_list
    result['total_weight_oz'] = round(total_weight_oz, 2)
    result['total_weight_lb'] = round(total_weight_oz / 16.0, 2)
    result['packed_count'] = packed_count
    result['unpacked_count'] = unpacked_count
    result['item_count'] = len(items_list)
    result['weight_by_category'] = weight_by_category
    return jsonify(result)


@loadout_bp.route('/api/loadout/bags/<int:bag_id>', methods=['PUT'])
def api_loadout_bags_update(bag_id):
    """Update bag profile fields (allow-list pattern)."""
    d = request.get_json() or {}
    fields = []
    values = []
    for key in _BAG_ALLOWED:
        if key in d:
            val = d[key]
            if key == 'bag_type' and val and str(val).lower() not in _BAG_TYPES:
                return jsonify({'error': f'Invalid bag_type. Expected one of {sorted(_BAG_TYPES)}'}), 400
            if key == 'season' and val and str(val).lower() not in _SEASONS:
                return jsonify({'error': f'Invalid season. Expected one of {sorted(_SEASONS)}'}), 400
            if key == 'target_weight_lb' and val is not None:
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    return jsonify({'error': 'target_weight_lb must be a number'}), 400
            if isinstance(val, str):
                val = val.strip()
            fields.append(f'{key} = ?')
            values.append(val)
    if not fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    fields.append('updated_at = CURRENT_TIMESTAMP')
    values.append(bag_id)
    with db_session() as db:
        r = db.execute(
            f'UPDATE loadout_bags SET {", ".join(fields)} WHERE id = ?', values)
        if r.rowcount == 0:
            return _bag_not_found()
        db.commit()
        row = db.execute('SELECT * FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
    return jsonify(dict(row))


@loadout_bp.route('/api/loadout/bags/<int:bag_id>', methods=['DELETE'])
def api_loadout_bags_delete(bag_id):
    """Delete a bag and cascade-delete all its items."""
    with db_session() as db:
        bag = db.execute('SELECT name FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        db.execute('DELETE FROM loadout_items WHERE bag_id = ?', (bag_id,))
        db.execute('DELETE FROM loadout_bags WHERE id = ?', (bag_id,))
        db.commit()
    log_activity('loadout_bag_deleted', 'loadout', f'Bag "{bag["name"]}" deleted')
    return jsonify({'status': 'deleted'})


# ─── Item CRUD ────────────────────────────────────────────────────────

@loadout_bp.route('/api/loadout/bags/<int:bag_id>/items')
def api_loadout_items_list(bag_id):
    """List items for a bag. Supports ?category= filter."""
    with db_session() as db:
        bag = db.execute('SELECT id FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        category = request.args.get('category', '').strip().lower()
        if category:
            rows = db.execute(
                'SELECT * FROM loadout_items WHERE bag_id = ? AND category = ? ORDER BY name',
                (bag_id, category)).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM loadout_items WHERE bag_id = ? ORDER BY category, name',
                (bag_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@loadout_bp.route('/api/loadout/bags/<int:bag_id>/items', methods=['POST'])
def api_loadout_items_create(bag_id):
    """Add an item to a bag."""
    d = request.get_json() or {}
    name = (d.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    category = (d.get('category') or 'other').lower()
    if category not in _ITEM_CATEGORIES:
        return jsonify({'error': f'Invalid category. Expected one of {sorted(_ITEM_CATEGORIES)}'}), 400
    try:
        quantity = max(1, int(d.get('quantity', 1)))
    except (ValueError, TypeError):
        quantity = 1
    try:
        weight_oz = max(0, float(d.get('weight_oz', 0)))
    except (ValueError, TypeError):
        weight_oz = 0.0
    packed = 1 if d.get('packed') else 0

    with db_session() as db:
        bag = db.execute('SELECT id FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        cur = db.execute(
            '''INSERT INTO loadout_items
               (bag_id, name, category, quantity, weight_oz, packed, expiration, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (bag_id, name, category, quantity, weight_oz, packed,
             (d.get('expiration') or '').strip() or None,
             (d.get('notes') or '').strip()))
        db.commit()
        row = db.execute('SELECT * FROM loadout_items WHERE id = ?', (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@loadout_bp.route('/api/loadout/items/<int:item_id>', methods=['PUT'])
def api_loadout_items_update(item_id):
    """Update an item (allow-list pattern)."""
    d = request.get_json() or {}
    fields = []
    values = []
    for key in _ITEM_ALLOWED:
        if key in d:
            val = d[key]
            if key == 'category' and val and str(val).lower() not in _ITEM_CATEGORIES:
                return jsonify({'error': f'Invalid category. Expected one of {sorted(_ITEM_CATEGORIES)}'}), 400
            if key == 'quantity':
                try:
                    val = max(1, int(val))
                except (ValueError, TypeError):
                    continue
            if key == 'weight_oz':
                try:
                    val = max(0, float(val))
                except (ValueError, TypeError):
                    continue
            if key == 'packed':
                val = 1 if val else 0
            if isinstance(val, str):
                val = val.strip()
            fields.append(f'{key} = ?')
            values.append(val)
    if not fields:
        return jsonify({'error': 'No valid fields to update'}), 400

    fields.append('updated_at = CURRENT_TIMESTAMP')
    values.append(item_id)
    with db_session() as db:
        r = db.execute(
            f'UPDATE loadout_items SET {", ".join(fields)} WHERE id = ?', values)
        if r.rowcount == 0:
            return _item_not_found()
        db.commit()
        row = db.execute('SELECT * FROM loadout_items WHERE id = ?', (item_id,)).fetchone()
    return jsonify(dict(row))


@loadout_bp.route('/api/loadout/items/<int:item_id>', methods=['DELETE'])
def api_loadout_items_delete(item_id):
    """Delete a single item."""
    with db_session() as db:
        r = db.execute('DELETE FROM loadout_items WHERE id = ?', (item_id,))
        if r.rowcount == 0:
            return _item_not_found()
        db.commit()
    return jsonify({'status': 'deleted'})


@loadout_bp.route('/api/loadout/items/<int:item_id>/toggle-packed', methods=['PUT'])
def api_loadout_items_toggle_packed(item_id):
    """Toggle packed status (0 <-> 1)."""
    with db_session() as db:
        row = db.execute('SELECT id, packed FROM loadout_items WHERE id = ?', (item_id,)).fetchone()
        if not row:
            return _item_not_found()
        new_val = 0 if row['packed'] else 1
        db.execute(
            'UPDATE loadout_items SET packed = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (new_val, item_id))
        db.commit()
        updated = db.execute('SELECT * FROM loadout_items WHERE id = ?', (item_id,)).fetchone()
    return jsonify(dict(updated))


# ─── Bulk Operations ──────────────────────────────────────────────────

@loadout_bp.route('/api/loadout/bags/<int:bag_id>/clone', methods=['POST'])
def api_loadout_bags_clone(bag_id):
    """Clone a bag with all items. Accepts optional new name and owner."""
    d = request.get_json() or {}
    with db_session() as db:
        bag = db.execute('SELECT * FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        bag_dict = dict(bag)
        new_name = (d.get('name') or '').strip() or f"{bag_dict['name']} (copy)"
        new_owner = (d.get('owner') or '').strip() or bag_dict.get('owner', '')

        cur = db.execute(
            '''INSERT INTO loadout_bags
               (name, owner, bag_type, season, target_weight_lb,
                location, last_inspected, photo_path, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (new_name, new_owner, bag_dict['bag_type'], bag_dict['season'],
             bag_dict['target_weight_lb'], bag_dict['location'],
             None, bag_dict['photo_path'], bag_dict['notes']))
        new_bag_id = cur.lastrowid

        items = db.execute('SELECT * FROM loadout_items WHERE bag_id = ?', (bag_id,)).fetchall()
        for item in items:
            db.execute(
                '''INSERT INTO loadout_items
                   (bag_id, name, category, quantity, weight_oz, packed, expiration, notes)
                   VALUES (?, ?, ?, ?, ?, 0, ?, ?)''',
                (new_bag_id, item['name'], item['category'], item['quantity'],
                 item['weight_oz'], item['expiration'], item['notes']))
        db.commit()
        new_bag = db.execute('SELECT * FROM loadout_bags WHERE id = ?', (new_bag_id,)).fetchone()
        item_count = db.execute(
            'SELECT COUNT(*) AS cnt FROM loadout_items WHERE bag_id = ?',
            (new_bag_id,)).fetchone()['cnt']
    log_activity('loadout_bag_cloned', 'loadout',
                 f'Cloned "{bag_dict["name"]}" -> "{new_name}" ({item_count} items)')
    result = dict(new_bag)
    result['item_count'] = item_count
    return jsonify(result), 201


@loadout_bp.route('/api/loadout/bags/<int:bag_id>/mark-inspected', methods=['POST'])
def api_loadout_bags_mark_inspected(bag_id):
    """Set last_inspected to today."""
    today = _today_iso()
    with db_session() as db:
        r = db.execute(
            'UPDATE loadout_bags SET last_inspected = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
            (today, bag_id))
        if r.rowcount == 0:
            return _bag_not_found()
        db.commit()
    log_activity('loadout_bag_inspected', 'loadout', f'Bag {bag_id} inspected')
    return jsonify({'status': 'inspected', 'last_inspected': today})


@loadout_bp.route('/api/loadout/bags/<int:bag_id>/pack-all', methods=['POST'])
def api_loadout_bags_pack_all(bag_id):
    """Mark all items in bag as packed."""
    with db_session() as db:
        bag = db.execute('SELECT id FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        r = db.execute(
            'UPDATE loadout_items SET packed = 1, updated_at = CURRENT_TIMESTAMP WHERE bag_id = ?',
            (bag_id,))
        db.commit()
    return jsonify({'status': 'packed', 'items_updated': r.rowcount})


@loadout_bp.route('/api/loadout/bags/<int:bag_id>/unpack-all', methods=['POST'])
def api_loadout_bags_unpack_all(bag_id):
    """Mark all items in bag as unpacked."""
    with db_session() as db:
        bag = db.execute('SELECT id FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        r = db.execute(
            'UPDATE loadout_items SET packed = 0, updated_at = CURRENT_TIMESTAMP WHERE bag_id = ?',
            (bag_id,))
        db.commit()
    return jsonify({'status': 'unpacked', 'items_updated': r.rowcount})


# ─── Analytics ────────────────────────────────────────────────────────

@loadout_bp.route('/api/loadout/bags/<int:bag_id>/weight-breakdown')
def api_loadout_weight_breakdown(bag_id):
    """Weight by category: [{category, count, total_weight_oz, percentage}]."""
    with db_session() as db:
        bag = db.execute('SELECT id FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        rows = db.execute('''
            SELECT category,
                   COUNT(*) AS count,
                   COALESCE(SUM(weight_oz * quantity), 0) AS total_weight_oz
            FROM loadout_items
            WHERE bag_id = ?
            GROUP BY category
            ORDER BY total_weight_oz DESC
        ''', (bag_id,)).fetchall()

    items = [dict(r) for r in rows]
    grand_total = sum(i['total_weight_oz'] for i in items)
    for i in items:
        i['total_weight_oz'] = round(i['total_weight_oz'], 2)
        i['percentage'] = round(i['total_weight_oz'] / grand_total * 100, 1) if grand_total else 0
    return jsonify(items)


@loadout_bp.route('/api/loadout/bags/<int:bag_id>/checklist')
def api_loadout_checklist(bag_id):
    """Printable checklist: items grouped by category with packed status."""
    with db_session() as db:
        bag = db.execute('SELECT * FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        items = db.execute(
            'SELECT * FROM loadout_items WHERE bag_id = ? ORDER BY category, name',
            (bag_id,)).fetchall()

    grouped = {}
    total_weight_oz = 0
    for item in items:
        d = dict(item)
        cat = d.get('category') or 'other'
        grouped.setdefault(cat, []).append(d)
        total_weight_oz += (d['weight_oz'] or 0) * (d['quantity'] or 1)

    bag_dict = dict(bag)
    return jsonify({
        'bag_name': bag_dict['name'],
        'owner': bag_dict['owner'],
        'bag_type': bag_dict['bag_type'],
        'last_inspected': bag_dict['last_inspected'],
        'total_weight_oz': round(total_weight_oz, 2),
        'total_weight_lb': round(total_weight_oz / 16.0, 2),
        'categories': grouped,
    })


@loadout_bp.route('/api/loadout/bags/<int:bag_id>/expiring')
def api_loadout_expiring(bag_id):
    """Items with expiration dates in the next 90 days."""
    cutoff = _ninety_days_from_now()
    today = _today_iso()
    with db_session() as db:
        bag = db.execute('SELECT id FROM loadout_bags WHERE id = ?', (bag_id,)).fetchone()
        if not bag:
            return _bag_not_found()
        rows = db.execute('''
            SELECT * FROM loadout_items
            WHERE bag_id = ?
              AND expiration IS NOT NULL
              AND expiration != ''
              AND expiration <= ?
              AND expiration >= ?
            ORDER BY expiration
        ''', (bag_id, cutoff, today)).fetchall()
    return jsonify([dict(r) for r in rows])


# ─── Dashboard ────────────────────────────────────────────────────────

@loadout_bp.route('/api/loadout/dashboard')
def api_loadout_dashboard():
    """Aggregate dashboard across all bags."""
    today = _today_iso()
    cutoff_90 = _ninety_days_from_now()
    inspection_cutoff = (date.today() - timedelta(days=90)).isoformat()

    with db_session() as db:
        # Totals
        total_bags = db.execute('SELECT COUNT(*) AS cnt FROM loadout_bags').fetchone()['cnt']
        total_items = db.execute('SELECT COUNT(*) AS cnt FROM loadout_items').fetchone()['cnt']

        # Bags by type
        type_rows = db.execute(
            'SELECT bag_type, COUNT(*) AS count FROM loadout_bags GROUP BY bag_type ORDER BY count DESC'
        ).fetchall()
        bags_by_type = {r['bag_type']: r['count'] for r in type_rows}

        # Bags by owner
        owner_rows = db.execute(
            "SELECT COALESCE(NULLIF(owner, ''), 'Unassigned') AS owner, COUNT(*) AS count "
            "FROM loadout_bags GROUP BY owner ORDER BY count DESC"
        ).fetchall()
        bags_by_owner = {r['owner']: r['count'] for r in owner_rows}

        # Heaviest bag
        heaviest = db.execute('''
            SELECT b.id, b.name,
                   COALESCE(SUM(i.weight_oz * i.quantity), 0) AS total_weight_oz
            FROM loadout_bags b
            LEFT JOIN loadout_items i ON i.bag_id = b.id
            GROUP BY b.id
            ORDER BY total_weight_oz DESC
            LIMIT 1
        ''').fetchone()
        heaviest_bag = None
        if heaviest and heaviest['total_weight_oz'] > 0:
            heaviest_bag = {
                'id': heaviest['id'],
                'name': heaviest['name'],
                'total_weight_oz': round(heaviest['total_weight_oz'], 2),
                'total_weight_lb': round(heaviest['total_weight_oz'] / 16.0, 2),
            }

        # Overweight bags
        overweight_rows = db.execute('''
            SELECT b.id, b.name, b.target_weight_lb,
                   COALESCE(SUM(i.weight_oz * i.quantity), 0) / 16.0 AS actual_weight_lb
            FROM loadout_bags b
            LEFT JOIN loadout_items i ON i.bag_id = b.id
            WHERE b.target_weight_lb IS NOT NULL AND b.target_weight_lb > 0
            GROUP BY b.id
            HAVING actual_weight_lb > b.target_weight_lb
            ORDER BY actual_weight_lb DESC
        ''').fetchall()
        overweight_bags = [{
            'id': r['id'], 'name': r['name'],
            'target_weight_lb': r['target_weight_lb'],
            'actual_weight_lb': round(r['actual_weight_lb'], 2),
        } for r in overweight_rows]

        # Items expiring soon
        items_expiring_soon = db.execute('''
            SELECT COUNT(*) AS cnt FROM loadout_items
            WHERE expiration IS NOT NULL
              AND expiration != ''
              AND expiration <= ?
              AND expiration >= ?
        ''', (cutoff_90, today)).fetchone()['cnt']

        # Bags needing inspection
        bags_needing_inspection = db.execute('''
            SELECT COUNT(*) AS cnt FROM loadout_bags
            WHERE last_inspected IS NULL
               OR last_inspected = ''
               OR last_inspected < ?
        ''', (inspection_cutoff,)).fetchone()['cnt']

        # Overall pack status
        pack_row = db.execute('''
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN packed = 1 THEN 1 ELSE 0 END) AS packed,
                   SUM(CASE WHEN packed = 0 OR packed IS NULL THEN 1 ELSE 0 END) AS unpacked
            FROM loadout_items
        ''').fetchone()
        total = pack_row['total']
        packed = pack_row['packed'] or 0
        overall_pack_status = {
            'total_items': total,
            'packed': packed,
            'unpacked': pack_row['unpacked'] or 0,
            'percentage': round(packed / total * 100, 1) if total else 0,
        }

    return jsonify({
        'total_bags': total_bags,
        'total_items': total_items,
        'bags_by_type': bags_by_type,
        'bags_by_owner': bags_by_owner,
        'heaviest_bag': heaviest_bag,
        'overweight_bags': overweight_bags,
        'items_expiring_soon': items_expiring_soon,
        'bags_needing_inspection': bags_needing_inspection,
        'overall_pack_status': overall_pack_status,
    })


# ─── Summary ──────────────────────────────────────────────────────────

@loadout_bp.route('/api/loadout/summary')
def api_loadout_summary():
    """Compact summary for sidebar / widget display."""
    today = _today_iso()
    cutoff_90 = _ninety_days_from_now()
    inspection_cutoff = (date.today() - timedelta(days=90)).isoformat()

    with db_session() as db:
        total_bags = db.execute('SELECT COUNT(*) AS cnt FROM loadout_bags').fetchone()['cnt']
        total_items = db.execute('SELECT COUNT(*) AS cnt FROM loadout_items').fetchone()['cnt']

        # Bags ready = all items packed AND inspected within 90 days
        bags_ready = db.execute('''
            SELECT COUNT(*) AS cnt FROM loadout_bags b
            WHERE b.last_inspected IS NOT NULL
              AND b.last_inspected != ''
              AND b.last_inspected >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM loadout_items i
                  WHERE i.bag_id = b.id AND (i.packed = 0 OR i.packed IS NULL)
              )
              AND EXISTS (
                  SELECT 1 FROM loadout_items i2 WHERE i2.bag_id = b.id
              )
        ''', (inspection_cutoff,)).fetchone()['cnt']

        items_expiring_soon = db.execute('''
            SELECT COUNT(*) AS cnt FROM loadout_items
            WHERE expiration IS NOT NULL
              AND expiration != ''
              AND expiration <= ?
              AND expiration >= ?
        ''', (cutoff_90, today)).fetchone()['cnt']

    return jsonify({
        'total_bags': total_bags,
        'total_items': total_items,
        'bags_ready': bags_ready,
        'items_expiring_soon': items_expiring_soon,
    })
