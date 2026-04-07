"""Inventory management, barcode, shopping list, and receipt scanning routes."""

import io
import json
import logging
import os
import re
import time

from flask import Blueprint, request, jsonify, Response
from werkzeug.utils import secure_filename

from db import db_session, log_activity
from services import ollama
from services.manager import format_size
from web.print_templates import render_print_document
from web.sql_safety import safe_table, safe_columns, build_update, build_insert
from web.validation import validate_json, validate_file_upload
from config import get_data_dir
from web.state import broadcast_event
from web.utils import esc as _esc, clone_json_fallback as _clone_json_fallback, safe_json_value as _safe_json_value

log = logging.getLogger('nomad.web')


def _check_origin(req):
    """Block cross-origin state-changing requests (CSRF protection)."""
    origin = req.headers.get('Origin', '')
    if origin and not origin.startswith(('http://localhost:', 'http://127.0.0.1:')):
        from flask import abort
        abort(403, 'Cross-origin request blocked')


def _extract_json_array(raw_text):
    if not isinstance(raw_text, str) or '[' not in raw_text:
        return []
    json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
    if not json_match:
        return []
    try:
        parsed = json.loads(json_match.group())
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


inventory_bp = Blueprint('inventory', __name__)

# ─── Inventory API ────────────────────────────────────────────────

INVENTORY_CATEGORIES = [
    'water', 'food', 'medical', 'ammo', 'fuel', 'tools',
    'hygiene', 'comms', 'clothing', 'shelter', 'power', 'other',
]


@inventory_bp.route('/api/inventory')
def api_inventory_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        cat = request.args.get('category', '')
        search = request.args.get('q', '').strip()
        query = 'SELECT * FROM inventory'
        params = []
        clauses = []
        if cat:
            clauses.append('category = ?')
            params.append(cat)
        if search:
            clauses.append('(name LIKE ? OR location LIKE ? OR notes LIKE ?)')
            params.extend([f'%{search}%'] * 3)
        if clauses:
            query += ' WHERE ' + ' AND '.join(clauses)
        query += ' ORDER BY category, name LIMIT ? OFFSET ?'
        params.extend([limit, offset])
        rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])

@inventory_bp.route('/api/inventory', methods=['POST'])
@validate_json({
    'name': {'type': str, 'required': True, 'max_length': 500},
    'quantity': {'type': int, 'min': 0, 'max': 999999},
    'category': {'type': str, 'max_length': 100},
})
def api_inventory_create():
    data = request.get_json() or {}
    with db_session() as db:
        cur = db.execute(
            'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, barcode, cost, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (data.get('name', ''), data.get('category', 'other'), data.get('quantity', 0),
             data.get('unit', 'ea'), data.get('min_quantity', 0), data.get('daily_usage', 0),
             data.get('location', ''), data.get('expiration', ''), data.get('barcode', ''), data.get('cost', 0), data.get('notes', '')))
        db.commit()
        item_id = cur.lastrowid
        row = db.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
    broadcast_event('inventory_update', {'action': 'add', 'id': item_id})
    return jsonify(dict(row)), 201

@inventory_bp.route('/api/inventory/<int:item_id>', methods=['PUT'])
@validate_json({
    'name': {'type': str, 'max_length': 500},
    'quantity': {'type': int, 'min': 0, 'max': 999999},
    'category': {'type': str, 'max_length': 100},
})
def api_inventory_update(item_id):
    data = request.get_json() or {}
    allowed = ['name', 'category', 'quantity', 'unit', 'min_quantity', 'daily_usage', 'location', 'expiration', 'barcode', 'cost', 'notes']
    filtered = safe_columns(data, allowed)
    if not filtered:
        return jsonify({'error': 'No fields to update'}), 400
    with db_session() as db:
        if not db.execute('SELECT 1 FROM inventory WHERE id = ?', (item_id,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        set_clause = ', '.join(f'{col} = ?' for col in filtered)
        vals = list(filtered.values())
        vals.append(item_id)
        db.execute(f'UPDATE inventory SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?', vals)
        db.commit()
    broadcast_event('inventory_update', {'action': 'edit', 'id': item_id})
    return jsonify({'status': 'saved'})

@inventory_bp.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def api_inventory_delete(item_id):
    with db_session() as db:
        db.execute('DELETE FROM inventory_photos WHERE inventory_id = ?', (item_id,))
        db.execute('DELETE FROM inventory_checkouts WHERE inventory_id = ?', (item_id,))
        db.execute('DELETE FROM shopping_list WHERE inventory_id = ?', (item_id,))
        r = db.execute('DELETE FROM inventory WHERE id = ?', (item_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    broadcast_event('inventory_update', {'action': 'delete', 'id': item_id})
    return jsonify({'status': 'deleted'})

@inventory_bp.route('/api/inventory/summary')
def api_inventory_summary():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as c FROM inventory').fetchone()['c']
        low_stock = db.execute('SELECT COUNT(*) as c FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0').fetchone()['c']
        # Expiring within 30 days
        from datetime import datetime, timedelta
        soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')
        today = datetime.now().strftime('%Y-%m-%d')
        expiring = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration <= ? AND expiration >= ?", (soon, today)).fetchone()['c']
        expired = db.execute("SELECT COUNT(*) as c FROM inventory WHERE expiration != '' AND expiration < ?", (today,)).fetchone()['c']
        cats = db.execute('SELECT category, COUNT(*) as c, SUM(quantity) as qty FROM inventory GROUP BY category ORDER BY category').fetchall()
    return jsonify({
        'total': total, 'low_stock': low_stock, 'expiring_soon': expiring, 'expired': expired,
        'categories': [{'category': r['category'], 'count': r['c'], 'total_qty': r['qty'] or 0} for r in cats],
    })

@inventory_bp.route('/api/inventory/categories')
def api_inventory_categories():
    return jsonify(INVENTORY_CATEGORIES)

@inventory_bp.route('/api/inventory/burn-rate')
def api_inventory_burn_rate():
    """Calculate days of supply remaining per category."""
    with db_session() as db:
        rows = db.execute('SELECT category, name, quantity, unit, daily_usage FROM inventory WHERE daily_usage > 0 ORDER BY category, name LIMIT 10000').fetchall()
    cats = {}
    for r in rows:
        cat = r['category']
        if cat not in cats:
            cats[cat] = {'items': [], 'min_days': float('inf')}
        days = r['quantity'] / r['daily_usage'] if r['daily_usage'] > 0 else float('inf')
        cats[cat]['items'].append({
            'name': r['name'], 'quantity': r['quantity'], 'unit': r['unit'],
            'daily_usage': r['daily_usage'], 'days_remaining': round(days, 1),
        })
        if days < cats[cat]['min_days']:
            cats[cat]['min_days'] = round(days, 1)
    # Convert inf
    for cat in cats.values():
        if cat['min_days'] == float('inf'):
            cat['min_days'] = None
    return jsonify(cats)

# ─── Receipt Scanner ─────────────────────────────────────────────
@inventory_bp.route('/api/inventory/receipt-scan', methods=['POST'])
def api_inventory_receipt_scan():
    """Accept a receipt image, OCR it, and extract line items."""
    _check_origin(request)
    import tempfile
    import base64

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Save to temp file
    suffix = os.path.splitext(secure_filename(file.filename))[1] or '.jpg'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        file.save(tmp.name)
        tmp.close()

        items = []
        raw_text = ''
        source = ''

        # --- Try Ollama vision model first ---
        ollama_available = False
        try:
            import urllib.request
            req_check = urllib.request.Request('http://localhost:11434/api/tags', method='GET')
            with urllib.request.urlopen(req_check, timeout=3) as resp:
                if resp.status == 200:
                    ollama_available = True
        except Exception:
            pass

        if ollama_available:
            try:
                with open(tmp.name, 'rb') as f:
                    img_b64 = base64.b64encode(f.read()).decode('utf-8')

                prompt = (
                    "Extract all line items from this receipt. For each item, return a JSON array "
                    "of objects with keys: name, quantity (number, default 1), unit_price (number), "
                    "total_price (number). Only return the JSON array, nothing else."
                )
                payload = json.dumps({
                    'model': 'llava',
                    'prompt': prompt,
                    'images': [img_b64],
                    'stream': False,
                })

                req_ollama = urllib.request.Request(
                    'http://localhost:11434/api/generate',
                    data=payload.encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(req_ollama, timeout=120) as resp:
                    result = _safe_json_value(resp.read(), {})

                raw_text = result.get('response', '') if isinstance(result, dict) else ''
                for item in _extract_json_array(raw_text):
                    if not isinstance(item, dict):
                        continue
                    items.append({
                        'name': str(item.get('name', 'Unknown')).strip(),
                        'quantity': _safe_float(item.get('quantity', 1), 1),
                        'unit_price': _safe_float(item.get('unit_price', 0), 0),
                        'total_price': _safe_float(item.get('total_price', 0), 0),
                    })
                source = 'ollama'
            except Exception as e:
                log.warning('Ollama receipt scan failed: %s', e)
                ollama_available = False  # fall through to Tesseract

        # --- Fallback: Tesseract OCR ---
        if not ollama_available and not items:
            try:
                import pytesseract
                from PIL import Image as PILImage

                img = PILImage.open(tmp.name)
                raw_text = pytesseract.image_to_string(img)
                source = 'tesseract'

                # Parse receipt lines — look for price patterns like $X.XX or X.XX at end of line
                for line in raw_text.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    # Match lines with a price at the end: "Item name   $12.34" or "Item name 12.34"
                    price_match = re.search(r'[$]?\s*(\d+\.\d{2})\s*$', line)
                    if price_match:
                        price = float(price_match.group(1))
                        name = line[:price_match.start()].strip()
                        # Clean up common receipt artifacts
                        name = re.sub(r'^[\d\s*#]+', '', name).strip()
                        name = re.sub(r'\s{2,}', ' ', name)
                        if name and len(name) > 1 and price > 0:
                            items.append({
                                'name': name,
                                'quantity': 1,
                                'unit_price': price,
                                'total_price': price,
                            })
            except ImportError:
                pass
            except Exception as e:
                log.warning('Tesseract receipt scan failed: %s', e)

        # --- Neither available ---
        if not source:
            return jsonify({
                'error': 'No OCR engine available. Install one of:\n'
                         '1. Ollama with a vision model: ollama pull llava\n'
                         '2. Tesseract OCR: pip install pytesseract Pillow (and install Tesseract binary)',
            }), 503

        return jsonify({
            'items': items,
            'raw_text': raw_text,
            'source': source,
        })
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

@inventory_bp.route('/api/inventory/receipt-import', methods=['POST'])
def api_inventory_receipt_import():
    """Bulk-add parsed receipt items to inventory."""
    _check_origin(request)
    data = request.get_json() or {}
    items = data.get('items', [])[:500]
    if not items:
        return jsonify({'error': 'No items provided'}), 400

    added = 0
    with db_session() as db:
        for item in items:
            name = str(item.get('name', '')).strip()
            if not name:
                continue
            try:
                qty = float(item.get('quantity', 1))
                unit_price = float(item.get('unit_price', 0))
                total_price = float(item.get('total_price', 0))
            except (ValueError, TypeError):
                qty, unit_price, total_price = 1, 0, 0
            notes = f'Receipt import — unit price: ${unit_price:.2f}, total: ${total_price:.2f}'

            db.execute(
                'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, barcode, cost, notes) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (name, 'General', qty, 'ea', 0, 0, '', '', '', unit_price, notes),
            )
            added += 1
        db.commit()
    log_activity('receipt_import', f'Imported {added} items from receipt scan')
    return jsonify({'status': 'ok', 'count': added}), 201

# ─── AI Vision Inventory Scanner ─────────────────────────────────
@inventory_bp.route('/api/inventory/vision-scan', methods=['POST'])
def api_inventory_vision_scan():
    """Accept an image, analyze with Ollama vision model, and identify inventory items."""
    _check_origin(request)
    import tempfile
    import base64

    if 'image' not in request.files:
        return jsonify({'error': 'No image file provided'}), 400

    file = request.files['image']
    if not file.filename:
        return jsonify({'error': 'Empty filename'}), 400

    # Save to temp file
    suffix = os.path.splitext(secure_filename(file.filename))[1] or '.jpg'
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    try:
        file.save(tmp.name)
        tmp.close()

        # Get image dimensions for response
        image_size = 'unknown'
        try:
            from PIL import Image as PILImage
            with PILImage.open(tmp.name) as img:
                image_size = f'{img.width}x{img.height}'
        except Exception:
            pass

        # Check if Ollama is running
        import urllib.request
        ollama_available = False
        try:
            req_check = urllib.request.Request('http://localhost:11434/api/tags', method='GET')
            with urllib.request.urlopen(req_check, timeout=3) as resp:
                if resp.status == 200:
                    ollama_available = True
        except Exception:
            pass

        if not ollama_available:
            return jsonify({
                'error': 'Ollama is not running. To use AI Vision Inventory:\n'
                         '1. Install Ollama from https://ollama.com\n'
                         '2. Start Ollama\n'
                         '3. Pull a vision model: ollama pull llava',
            }), 503

        # Base64-encode the image
        with open(tmp.name, 'rb') as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')

        prompt = (
            "Analyze this image of supplies/inventory items. For each distinct item you can identify, "
            "return a JSON array of objects with these keys:\n"
            "- name: item name (be specific, e.g., \"Campbell's Chicken Noodle Soup\" not just \"can\")\n"
            "- quantity: estimated count visible (number)\n"
            "- category: one of [Food, Water, Medical, Ammunition, Fuel, Equipment, Batteries, Hygiene, Clothing, Tools, Communication, Documents, Seeds, General]\n"
            "- condition: one of [New, Good, Fair, Poor]\n"
            "- notes: brief description (brand, size, any visible details)\n"
            "Only return the JSON array, no other text."
        )

        # Try vision models in order
        models_to_try = ['llava', 'llava:13b', 'moondream', 'bakllava']
        model_used = None
        raw_response = ''
        last_error = None

        for model in models_to_try:
            try:
                payload = json.dumps({
                    'model': model,
                    'prompt': prompt,
                    'images': [img_b64],
                    'stream': False,
                })

                req_ollama = urllib.request.Request(
                    'http://localhost:11434/api/generate',
                    data=payload.encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST',
                )
                with urllib.request.urlopen(req_ollama, timeout=120) as resp:
                    result = _safe_json_value(resp.read(), {})

                raw_response = result.get('response', '') if isinstance(result, dict) else ''
                model_used = model
                break
            except Exception as e:
                last_error = e
                log.debug('Vision model %s failed: %s', model, e)
                continue

        if not model_used:
            return jsonify({
                'error': 'No vision model available. Pull one with:\n'
                         '  ollama pull llava\n'
                         f'Last error: {last_error}',
            }), 503

        # Parse JSON array from response
        items = []
        valid_categories = {'Food', 'Water', 'Medical', 'Ammunition', 'Fuel', 'Equipment',
                            'Batteries', 'Hygiene', 'Clothing', 'Tools', 'Communication',
                            'Documents', 'Seeds', 'General'}
        valid_conditions = {'New', 'Good', 'Fair', 'Poor'}
        for item in _extract_json_array(raw_response):
            if not isinstance(item, dict):
                continue
            cat = str(item.get('category', 'General')).strip()
            cond = str(item.get('condition', 'Good')).strip()
            items.append({
                'name': str(item.get('name', 'Unknown')).strip(),
                'quantity': max(1, _safe_int(item.get('quantity', 1), 1)),
                'category': cat if cat in valid_categories else 'General',
                'condition': cond if cond in valid_conditions else 'Good',
                'notes': str(item.get('notes', '')).strip(),
            })

        return jsonify({
            'items': items,
            'model_used': model_used,
            'image_size': image_size,
        })
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass

@inventory_bp.route('/api/inventory/vision-import', methods=['POST'])
def api_inventory_vision_import():
    """Bulk-add AI-identified items to inventory."""
    _check_origin(request)
    data = request.get_json() or {}
    items = data.get('items', [])[:500]
    if not items:
        return jsonify({'error': 'No items provided'}), 400

    valid_categories = {'Food', 'Water', 'Medical', 'Ammunition', 'Fuel', 'Equipment',
                        'Batteries', 'Hygiene', 'Clothing', 'Tools', 'Communication',
                        'Documents', 'Seeds', 'General'}
    valid_conditions = {'New', 'Good', 'Fair', 'Poor'}

    added = 0
    with db_session() as db:
        for item in items:
            name = str(item.get('name', '')).strip()
            if not name:
                continue
            qty = max(1, int(float(item.get('quantity', 1))))
            cat = str(item.get('category', 'General')).strip()
            cat = cat if cat in valid_categories else 'General'
            cond = str(item.get('condition', 'Good')).strip()
            cond = cond if cond in valid_conditions else 'Good'
            notes_text = str(item.get('notes', '')).strip()
            notes = f'AI Vision import — condition: {cond}'
            if notes_text:
                notes += f', {notes_text}'

            db.execute(
                'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, barcode, cost, notes) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                (name, cat, qty, 'ea', 0, 0, '', '', '', 0, notes),
            )
            added += 1
        db.commit()
    log_activity('vision_import', f'Imported {added} items from AI vision scan')
    return jsonify({'status': 'ok', 'count': added}), 201


@inventory_bp.route('/api/inventory/export-csv')
def api_inventory_csv():
    with db_session() as db:
        rows = db.execute('SELECT name, category, quantity, unit, min_quantity, daily_usage, location, expiration, notes FROM inventory ORDER BY category, name LIMIT 50000').fetchall()
    import csv, io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Name', 'Category', 'Quantity', 'Unit', 'Min Qty', 'Daily Usage', 'Location', 'Expiration', 'Notes'])
    for r in rows:
        w.writerow([r['name'], r['category'], r['quantity'], r['unit'], r['min_quantity'], r['daily_usage'], r['location'], r['expiration'], r['notes']])
    return Response(buf.getvalue(), mimetype='text/csv',
                   headers={'Content-Disposition': 'attachment; filename="nomad-inventory.csv"'})


@inventory_bp.route('/api/inventory/export')
def api_inventory_export():
    """Export all inventory items as CSV."""
    try:
        import csv
        with db_session() as db:
            rows = db.execute(
                'SELECT name, category, quantity, unit, min_quantity, daily_usage, location, expiration, notes '
                'FROM inventory ORDER BY category, name LIMIT 50000'
            ).fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Name', 'Category', 'Quantity', 'Unit', 'Min Qty', 'Daily Usage', 'Location', 'Expiration', 'Notes'])
        for r in rows:
            w.writerow([r['name'], r['category'], r['quantity'], r['unit'], r['min_quantity'],
                        r['daily_usage'], r['location'], r['expiration'], r['notes']])
        return Response(buf.getvalue(), mimetype='text/csv',
                       headers={'Content-Disposition': 'attachment; filename="nomad_inventory_export.csv"'})
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Inventory export failed')
        return jsonify({'error': 'Export failed'}), 500


@inventory_bp.route('/api/inventory/import-csv', methods=['POST'])
def api_inventory_import_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    import csv, io
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
                    'INSERT INTO inventory (name, category, quantity, unit, min_quantity, daily_usage, location, expiration, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                    (name, row.get('Category', row.get('category', 'other')),
                     float(row.get('Quantity', row.get('quantity', 0)) or 0),
                     row.get('Unit', row.get('unit', 'ea')),
                     float(row.get('Min Qty', row.get('min_quantity', 0)) or 0),
                     float(row.get('Daily Usage', row.get('daily_usage', 0)) or 0),
                     row.get('Location', row.get('location', '')),
                     row.get('Expiration', row.get('expiration', '')),
                     row.get('Notes', row.get('notes', ''))))
                imported += 1
            db.commit()
        return jsonify({'status': 'imported', 'count': imported})
    except Exception as e:
        log.exception('Inventory CSV import failed')
        return jsonify({'error': 'Import failed — check file format'}), 500

@inventory_bp.route('/api/inventory/shopping-list')
def api_shopping_list():
    from datetime import datetime, timedelta
    today = datetime.now().strftime('%Y-%m-%d')
    soon = (datetime.now() + timedelta(days=30)).strftime('%Y-%m-%d')

    with db_session() as db:
        # Low stock items — need to restock
        low = db.execute('SELECT name, quantity, unit, min_quantity, category FROM inventory WHERE quantity <= min_quantity AND min_quantity > 0 LIMIT 10000').fetchall()
        low_items = [{'name': r['name'], 'need': round(r['min_quantity'] - r['quantity'], 1), 'unit': r['unit'],
                      'category': r['category'], 'reason': 'below minimum'} for r in low]

        # Expiring items — need replacement
        expiring = db.execute("SELECT name, unit, category, expiration FROM inventory WHERE expiration != '' AND expiration <= ? LIMIT 10000", (soon,)).fetchall()
        exp_items = [{'name': r['name'], 'need': 1, 'unit': r['unit'], 'category': r['category'],
                      'reason': f'expires {r["expiration"]}'} for r in expiring]

        # Critical burn rate — running out within 14 days
        burn = db.execute("SELECT name, quantity, daily_usage, unit, category FROM inventory WHERE daily_usage > 0 AND (quantity / daily_usage) < 14 LIMIT 10000").fetchall()
        burn_items = [{'name': r['name'], 'need': round(r['daily_usage'] * 30 - r['quantity'], 1), 'unit': r['unit'],
                       'category': r['category'], 'reason': f'{round(r["quantity"]/r["daily_usage"],1)} days left'}
                      for r in burn if r['daily_usage'] * 30 > r['quantity']]

    # Deduplicate by name
    seen = set()
    all_items = []
    for item in low_items + exp_items + burn_items:
        if item['name'] not in seen:
            seen.add(item['name'])
            all_items.append(item)

    return jsonify(sorted(all_items, key=lambda x: x['category']))

# ─── Inventory Upgrades (v5.0 Phase 3) ──────────────────────────

@inventory_bp.route('/api/inventory/shopping-list/save', methods=['POST'])
def api_shopping_list_save():
    """Save current shopping list snapshot."""
    with db_session() as db:
        rows = db.execute(
            'SELECT id, name, category, quantity, min_quantity, unit FROM inventory WHERE min_quantity > 0 AND quantity < min_quantity'
        ).fetchall()
        for r in rows:
            needed = round(r['min_quantity'] - r['quantity'], 2)
            db.execute(
                'INSERT OR IGNORE INTO shopping_list (name, category, quantity_needed, unit, inventory_id) VALUES (?, ?, ?, ?, ?)',
                (r['name'], r['category'], needed, r['unit'], r['id'])
            )
        db.commit()
        return jsonify({'status': 'ok', 'count': len(rows)}), 201
@inventory_bp.route('/api/inventory/<int:item_id>/checkout', methods=['POST'])
def api_inventory_checkout(item_id):
    """Check out an inventory item to a person."""
    d = request.json or {}
    person = d.get('person', '').strip()
    qty = d.get('quantity', 1)
    reason = d.get('reason', '')
    if not person:
        return jsonify({'error': 'person required'}), 400
    with db_session() as db:
        db.execute(
            'INSERT INTO inventory_checkouts (inventory_id, checked_out_to, quantity, reason) VALUES (?, ?, ?, ?)',
            (item_id, person, qty, reason)
        )
        db.execute('UPDATE inventory SET checked_out_to = ? WHERE id = ?', (person, item_id))
        db.commit()
        log_activity('checkout', detail=f'{person} checked out item #{item_id}')
        return jsonify({'status': 'ok'}), 201
@inventory_bp.route('/api/inventory/<int:item_id>/checkin', methods=['POST'])
def api_inventory_checkin(item_id):
    """Return a checked-out inventory item."""
    with db_session() as db:
        db.execute(
            "UPDATE inventory_checkouts SET returned_at = CURRENT_TIMESTAMP WHERE inventory_id = ? AND returned_at IS NULL",
            (item_id,)
        )
        db.execute("UPDATE inventory SET checked_out_to = '' WHERE id = ?", (item_id,))
        db.commit()
        log_activity('checkin', detail=f'Item #{item_id} returned')
        return jsonify({'status': 'ok'})
@inventory_bp.route('/api/inventory/checkouts')
def api_inventory_checkouts():
    """List all currently checked-out items."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute(
            '''SELECT c.*, i.name as item_name, i.category
               FROM inventory_checkouts c
               JOIN inventory i ON c.inventory_id = i.id
               WHERE c.returned_at IS NULL
               ORDER BY c.checked_out_at DESC
               LIMIT ? OFFSET ?''',
            (limit, offset)
        ).fetchall()
        return jsonify([dict(r) for r in rows])
@inventory_bp.route('/api/inventory/<int:item_id>/photos', methods=['GET'])
def api_inventory_photos(item_id):
    """List photos for an inventory item."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM inventory_photos WHERE inventory_id = ? ORDER BY created_at DESC', (item_id,)).fetchall()
        return jsonify([dict(r) for r in rows])
@inventory_bp.route('/api/inventory/<int:item_id>/photos', methods=['POST'])
def api_inventory_photo_upload(item_id):
    """Upload a photo for an inventory item."""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo provided'}), 400
    photo = request.files['photo']
    if not photo.filename:
        return jsonify({'error': 'Empty filename'}), 400

    photos_dir = os.path.join(get_data_dir(), 'photos', 'inventory')
    os.makedirs(photos_dir, exist_ok=True)
    filename = f'{item_id}_{int(time.time())}_{secure_filename(photo.filename)}'
    filepath = os.path.join(photos_dir, filename)
    photo.save(filepath)

    with db_session() as db:
        caption = request.form.get('caption', '')
        db.execute('INSERT INTO inventory_photos (inventory_id, filename, caption) VALUES (?, ?, ?)',
                   (item_id, filename, caption))
        db.commit()
        return jsonify({'status': 'ok', 'filename': filename})
@inventory_bp.route('/api/inventory/locations')
def api_inventory_locations():
    """Get unique inventory locations for filtering."""
    with db_session() as db:
        rows = db.execute("SELECT DISTINCT location FROM inventory WHERE location != '' ORDER BY location").fetchall()
        return jsonify([r['location'] for r in rows])
@inventory_bp.route('/api/inventory/scan/<barcode>')
def api_inventory_scan(barcode):
    """Look up inventory item by barcode."""
    with db_session() as db:
        row = db.execute('SELECT * FROM inventory WHERE barcode = ?', (barcode,)).fetchone()
        if row:
            return jsonify(dict(row))
        return jsonify({'found': False, 'barcode': barcode}), 404
# ─── Barcode / UPC Database ──────────────────────────────────────

@inventory_bp.route('/api/barcode/lookup/<upc>')
def api_barcode_lookup(upc):
    """Look up a UPC in the local barcode database."""
    import re
    upc = re.sub(r'[^0-9]', '', str(upc))
    if not upc or len(upc) not in (8, 12, 13):
        return jsonify({'error': 'Invalid UPC format — must be 8, 12, or 13 digits'}), 400
    with db_session() as db:
        row = db.execute('SELECT * FROM upc_database WHERE upc = ?', (upc,)).fetchone()
        if row:
            return jsonify({'found': True, **dict(row)})
        return jsonify({'found': False, 'upc': upc})
@inventory_bp.route('/api/barcode/add', methods=['POST'])
def api_barcode_add():
    """Add a new UPC to the local barcode database."""
    _check_origin(request)
    data = request.get_json() or {}
    import re
    upc = re.sub(r'[^0-9]', '', str(data.get('upc', '')))
    name = str(data.get('name', '')).strip()
    if not upc or len(upc) not in (8, 12, 13):
        return jsonify({'error': 'Invalid UPC format — must be 8, 12, or 13 digits'}), 400
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    with db_session() as db:
        db.execute(
            'INSERT OR REPLACE INTO upc_database (upc, name, category, brand, size, unit, default_shelf_life_days) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (upc, name, data.get('category', 'General'), data.get('brand', ''),
             data.get('size', ''), data.get('unit', 'each'),
             _safe_int(data.get('default_shelf_life_days', 0)))

        )
        db.commit()
        row = db.execute('SELECT * FROM upc_database WHERE upc = ?', (upc,)).fetchone()
        return jsonify({'status': 'saved', **dict(row)}), 201
@inventory_bp.route('/api/barcode/scan-to-inventory', methods=['POST'])
def api_barcode_scan_to_inventory():
    """Look up UPC and add to inventory with auto-filled details."""
    _check_origin(request)
    data = request.get_json() or {}
    import re
    from datetime import datetime, timedelta
    upc = re.sub(r'[^0-9]', '', str(data.get('upc', '')))
    try:
        quantity = max(0, float(data.get('quantity', 1)))
    except (ValueError, TypeError):
        quantity = 1
    if not upc or len(upc) not in (8, 12, 13):
        return jsonify({'error': 'Invalid UPC format — must be 8, 12, or 13 digits'}), 400
    with db_session() as db:
        upc_row = db.execute('SELECT * FROM upc_database WHERE upc = ?', (upc,)).fetchone()
        if not upc_row:
            return jsonify({'error': 'UPC not found in database — add it first'}), 404

        # Calculate expiration from shelf life
        expiration = ''
        if upc_row['default_shelf_life_days'] and upc_row['default_shelf_life_days'] > 0:
            exp_date = datetime.now() + timedelta(days=upc_row['default_shelf_life_days'])
            expiration = exp_date.strftime('%Y-%m-%d')

        # Map UPC category to inventory category (lowercase)
        cat_map = {
            'Food': 'food', 'Water': 'water', 'Medical': 'medical',
            'Batteries/Power': 'power', 'Gear': 'gear', 'Hygiene': 'hygiene',
        }
        inv_category = cat_map.get(upc_row['category'], 'other')

        cur = db.execute(
            'INSERT INTO inventory (name, category, quantity, unit, expiration, barcode, notes) VALUES (?, ?, ?, ?, ?, ?, ?)',
            (upc_row['name'], inv_category, quantity, upc_row['unit'], expiration, upc,
             f"{upc_row['brand']} {upc_row['size']}".strip())
        )
        db.commit()
        item_id = cur.lastrowid
        inv_row = db.execute('SELECT * FROM inventory WHERE id = ?', (item_id,)).fetchone()
        log_activity('barcode_scan_add', 'inventory', f'Added {upc_row["name"]} x{quantity} via barcode {upc}')
        return jsonify({'status': 'added', 'item': dict(inv_row)}), 201
@inventory_bp.route('/api/barcode/database/stats')
def api_barcode_stats():
    """Return count of UPCs in database by category."""
    with db_session() as db:
        rows = db.execute('SELECT category, COUNT(*) as count FROM upc_database GROUP BY category ORDER BY count DESC').fetchall()
        total = sum(r['count'] for r in rows)
        return jsonify({'total': total, 'categories': [dict(r) for r in rows]})
# ─── Inventory Consume (quick daily use) ──────────────────────────

@inventory_bp.route('/api/inventory/<int:item_id>/consume', methods=['POST'])
def api_inventory_consume(item_id):
    """Decrement item by daily_usage or specified amount. Logs consumption."""
    data = request.get_json() or {}
    with db_session() as db:
        row = db.execute('SELECT id, name, quantity, daily_usage, unit FROM inventory WHERE id = ?', (item_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        amount = data.get('amount', row['daily_usage'] or 1)
        new_qty = max(0, row['quantity'] - amount)
        db.execute('UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_qty, item_id))
        db.commit()
    log_activity('inventory_consumed', row['name'], f'-{amount} {row["unit"]} (was {row["quantity"]}, now {new_qty})')
    return jsonify({'status': 'consumed', 'name': row['name'], 'consumed': amount, 'remaining': new_qty})

@inventory_bp.route('/api/inventory/batch-consume', methods=['POST'])
def api_inventory_batch_consume():
    """Consume daily usage for all items that have daily_usage set."""
    with db_session() as db:
        rows = db.execute('SELECT id, name, quantity, daily_usage, unit FROM inventory WHERE daily_usage > 0 AND quantity > 0').fetchall()
        consumed = []
        for r in rows:
            new_qty = max(0, r['quantity'] - r['daily_usage'])
            db.execute('UPDATE inventory SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?', (new_qty, r['id']))
            consumed.append({'name': r['name'], 'used': r['daily_usage'], 'remaining': new_qty, 'unit': r['unit']})
        db.commit()
    if consumed:
        log_activity('daily_consumption', detail=f'Updated {len(consumed)} items')
    return jsonify({'status': 'consumed', 'items': consumed})

@inventory_bp.route('/api/inventory/print')
def api_inventory_print():
    """Printable inventory list."""
    with db_session() as db:
        items = db.execute('SELECT name, category, quantity, unit, min_quantity, daily_usage, expiration, location FROM inventory ORDER BY category, name LIMIT 50000').fetchall()
    now = time.strftime('%Y-%m-%d %H:%M')
    categories = {}
    low_count = 0
    tracked_count = 0
    table_html = '<div class="doc-empty">No inventory items have been added yet.</div>'
    if items:
        table_html = '<div class="doc-table-shell"><table><thead><tr><th>Name</th><th>Category</th><th>Qty</th><th>Unit</th><th>Min</th><th>Daily Use</th><th>Days Left</th><th>Expires</th><th>Location</th></tr></thead><tbody>'
        for i in items:
            d = dict(i)
            category = d.get('category') or 'other'
            categories[category] = categories.get(category, 0) + 1
            days = round(d['quantity'] / d['daily_usage'], 1) if d.get('daily_usage') and d['daily_usage'] > 0 else '-'
            low = d['quantity'] <= d['min_quantity'] and d['min_quantity'] > 0 if d.get('min_quantity') else False
            if low:
                low_count += 1
            if d.get('daily_usage'):
                tracked_count += 1
            name_class = ' class="doc-alert"' if low else ' class="doc-strong"'
            days_cell = f' class="doc-alert"' if isinstance(days, (int, float)) and days < 7 else ''
            table_html += (
                f"<tr><td{name_class}>{_esc(d['name'])}</td><td>{_esc(category)}</td><td>{d['quantity']}</td>"
                f"<td>{_esc(d.get('unit','')) or '-'}</td><td>{d.get('min_quantity','') or '-'}</td>"
                f"<td>{d.get('daily_usage','') or '-'}</td><td{days_cell}>{days}</td>"
                f"<td>{d.get('expiration','') or '-'}</td><td>{_esc(d.get('location','')) or '-'}</td></tr>"
            )
        table_html += '</tbody></table></div>'

    category_html = '<div class="doc-empty">Category breakdown will appear once inventory is populated.</div>'
    if categories:
        category_html = '<div class="doc-chip-list">' + ''.join(
            f'<span class="doc-chip">{_esc(cat)}: {count}</span>'
            for cat, count in sorted(categories.items())
        ) + '</div>'

    body = f'''<section class="doc-section">
  <h2 class="doc-section-title">Inventory Report</h2>
  {table_html}
</section>
<section class="doc-section">
  <div class="doc-grid-2">
    <div class="doc-panel">
      <h2 class="doc-section-title">Category Breakdown</h2>
      {category_html}
    </div>
    <div class="doc-panel">
      <h2 class="doc-section-title">Use Notes</h2>
      <div class="doc-kv">
        <div class="doc-kv-row"><div class="doc-kv-key">Low Stock</div><div>Highlighted rows are at or below their configured minimum quantity.</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Burn Tracking</div><div>Days Left is calculated from quantity divided by daily usage when a burn rate exists.</div></div>
        <div class="doc-kv-row"><div class="doc-kv-key">Review Cadence</div><div>Print after audits, resupply runs, or before rotating staged gear and caches.</div></div>
      </div>
    </div>
  </div>
</section>
<section class="doc-section">
  <div class="doc-footer">
    <span>Printable supply ledger for resupply planning, cache reviews, and readiness checks.</span>
    <span>Generated by NOMAD Field Desk.</span>
  </div>
</section>'''
    html = render_print_document(
        'Inventory Report',
        'Printable supply ledger showing quantities, minimums, burn tracking, expiration dates, and storage locations.',
        body,
        eyebrow='NOMAD Field Desk Inventory',
        meta_items=[f'Generated {now}', 'Letter print layout'],
        stat_items=[
            ('Items', len(items)),
            ('Categories', len(categories)),
            ('Low Stock', low_count),
            ('Burn Tracked', tracked_count),
        ],
        accent_start='#19354a',
        accent_end='#4a6b5f',
        max_width='1160px',
    )
    return html

@inventory_bp.route('/api/import/csv', methods=['POST'])
def api_import_csv_preview():
    """Upload CSV, return headers + sample rows for column mapping."""
    import csv
    import io
    if 'file' not in request.files:
        # Try raw body
        raw = request.get_data(as_text=True)
        if not raw:
            return jsonify({'error': 'No CSV file provided'}), 400
    else:
        raw = request.files['file'].read().decode('utf-8', errors='replace')
    reader = csv.reader(io.StringIO(raw))
    rows_data = []
    for i, row in enumerate(reader):
        rows_data.append(row)
        if i >= 10:  # headers + 10 sample rows
            break
    if not rows_data:
        return jsonify({'error': 'CSV is empty'}), 400
    headers = rows_data[0]
    samples = rows_data[1:]
    # Target table columns
    table_columns = {
        'inventory': ['name', 'category', 'quantity', 'unit', 'min_quantity', 'location', 'expiration', 'notes', 'daily_usage', 'barcode', 'cost'],
        'contacts': ['name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email', 'address', 'rally_point', 'blood_type', 'medical_notes', 'notes'],
        'waypoints': ['name', 'lat', 'lng', 'category', 'color', 'icon', 'elevation_m', 'notes'],
        'seeds': ['species', 'variety', 'quantity', 'unit', 'year_harvested', 'source', 'days_to_maturity', 'planting_season', 'notes'],
        'ammo_inventory': ['caliber', 'brand', 'bullet_weight', 'bullet_type', 'quantity', 'location', 'notes'],
        'fuel_storage': ['fuel_type', 'quantity', 'unit', 'container', 'location', 'stabilizer_added', 'date_stored', 'expires', 'notes'],
        'equipment_log': ['name', 'category', 'last_service', 'next_service', 'service_notes', 'status', 'location', 'notes'],
    }
    return jsonify({
        'headers': headers,
        'sample_rows': samples,
        'row_count': len(rows_data) - 1,
        'target_tables': list(table_columns.keys()),
        'table_columns': table_columns,
    })

@inventory_bp.route('/api/import/csv/execute', methods=['POST'])
def api_import_csv_execute():
    """Execute CSV import with column mapping."""
    import csv
    import io
    data = request.get_json() or {}
    csv_data = data.get('csv_data', '')
    mapping = data.get('mapping', {})  # {csv_header: db_column}
    target = data.get('target_table', '')
    allowed_tables = ['inventory', 'contacts', 'waypoints', 'seeds', 'ammo_inventory', 'fuel_storage', 'equipment_log']
    _CSV_ALLOWED_TABLES = set(allowed_tables)
    if target not in _CSV_ALLOWED_TABLES:
        return jsonify({'error': f'Invalid target table. Must be one of: {", ".join(allowed_tables)}'}), 400
    safe_table(target, _CSV_ALLOWED_TABLES)
    if not mapping:
        return jsonify({'error': 'Column mapping is required'}), 400
    if not csv_data:
        return jsonify({'error': 'csv_data is required'}), 400

    # Validate column names against known schema to prevent injection
    table_columns = {
        'inventory': ['name', 'category', 'quantity', 'unit', 'min_quantity', 'location', 'expiration', 'notes', 'daily_usage', 'barcode', 'cost'],
        'contacts': ['name', 'callsign', 'role', 'skills', 'phone', 'freq', 'email', 'address', 'rally_point', 'blood_type', 'medical_notes', 'notes'],
        'waypoints': ['name', 'lat', 'lng', 'category', 'color', 'icon', 'elevation_m', 'notes'],
        'seeds': ['species', 'variety', 'quantity', 'unit', 'year_harvested', 'source', 'days_to_maturity', 'planting_season', 'notes'],
        'ammo_inventory': ['caliber', 'brand', 'bullet_weight', 'bullet_type', 'quantity', 'location', 'notes'],
        'fuel_storage': ['fuel_type', 'quantity', 'unit', 'container', 'location', 'stabilizer_added', 'date_stored', 'expires', 'notes'],
        'equipment_log': ['name', 'category', 'last_service', 'next_service', 'service_notes', 'status', 'location', 'notes'],
    }
    valid_cols = set(table_columns.get(target, []))
    for db_col in mapping.values():
        if db_col and db_col not in valid_cols:
            return jsonify({'error': f'Invalid column name: {db_col}'}), 400

    if isinstance(csv_data, list):
        # csv_data is already a list of dicts
        rows_to_process = csv_data
    else:
        reader = csv.DictReader(io.StringIO(csv_data))
        rows_to_process = list(reader)
    with db_session() as db:
        inserted = 0
        errors = []
        for i, row in enumerate(rows_to_process):
            try:
                mapped = {}
                for csv_col, db_col in mapping.items():
                    if csv_col in row and db_col:
                        mapped[db_col] = row[csv_col]
                if not mapped:
                    continue
                sql, params = build_insert(target, mapped, valid_cols)
                db.execute(sql, params)
                inserted += 1
            except Exception as e:
                errors.append(f'Row {i + 1}: {str(e)}')
        db.commit()
    log_activity('csv_import', 'import', f'{inserted} rows into {target}')
    return jsonify({'status': 'complete', 'inserted': inserted, 'errors': errors, 'target_table': target})

# ─── Template Quick Entry (Phase 17) ──────────────────────────────

_INVENTORY_TEMPLATES = {
    '72-hour-kit': {
        'name': '72-Hour Kit',
        'description': 'Essential supplies for 72 hours of self-sufficiency',
        'items': [
            {'name': 'Water (1L bottles)', 'category': 'water', 'quantity': 9, 'unit': 'bottles'},
            {'name': 'Water purification tablets', 'category': 'water', 'quantity': 1, 'unit': 'pack'},
            {'name': 'MRE - Beef Stew', 'category': 'food', 'quantity': 3, 'unit': 'ea'},
            {'name': 'MRE - Chicken Noodle', 'category': 'food', 'quantity': 3, 'unit': 'ea'},
            {'name': 'Energy bars', 'category': 'food', 'quantity': 6, 'unit': 'ea'},
            {'name': 'Trail mix', 'category': 'food', 'quantity': 3, 'unit': 'bags'},
            {'name': 'First aid kit (compact)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Flashlight (LED)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'AA Batteries', 'category': 'tools', 'quantity': 8, 'unit': 'ea'},
            {'name': 'Emergency blanket (mylar)', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Poncho (disposable)', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Duct tape (small roll)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Multi-tool', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Paracord 50ft', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Lighter (BIC)', 'category': 'tools', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Waterproof matches', 'category': 'tools', 'quantity': 1, 'unit': 'box'},
            {'name': 'N95 masks', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
            {'name': 'Work gloves', 'category': 'tools', 'quantity': 1, 'unit': 'pair'},
            {'name': 'Whistle (emergency)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'AM/FM radio (hand-crank)', 'category': 'comms', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Cash (small bills)', 'category': 'other', 'quantity': 200, 'unit': 'USD'},
            {'name': 'Document copies (waterproof bag)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Toilet paper (travel roll)', 'category': 'hygiene', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Hand sanitizer', 'category': 'hygiene', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Wet wipes', 'category': 'hygiene', 'quantity': 1, 'unit': 'pack'},
            {'name': 'Garbage bags (heavy duty)', 'category': 'tools', 'quantity': 4, 'unit': 'ea'},
            {'name': 'Zip-lock bags (gallon)', 'category': 'tools', 'quantity': 10, 'unit': 'ea'},
            {'name': 'Notebook + pencil', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Local map (paper)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Compass', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
        ],
    },
    'family-30-days': {
        'name': 'Family of 4 - 30 Days',
        'description': 'Extended supply for a family of four',
        'items': [
            {'name': 'Rice (long grain)', 'category': 'food', 'quantity': 50, 'unit': 'lbs'},
            {'name': 'Dried beans (pinto)', 'category': 'food', 'quantity': 25, 'unit': 'lbs'},
            {'name': 'Dried beans (black)', 'category': 'food', 'quantity': 15, 'unit': 'lbs'},
            {'name': 'Oats (rolled)', 'category': 'food', 'quantity': 20, 'unit': 'lbs'},
            {'name': 'Canned vegetables (mixed)', 'category': 'food', 'quantity': 48, 'unit': 'cans'},
            {'name': 'Canned fruit', 'category': 'food', 'quantity': 24, 'unit': 'cans'},
            {'name': 'Canned tuna', 'category': 'food', 'quantity': 24, 'unit': 'cans'},
            {'name': 'Canned chicken', 'category': 'food', 'quantity': 12, 'unit': 'cans'},
            {'name': 'Peanut butter', 'category': 'food', 'quantity': 6, 'unit': 'jars'},
            {'name': 'Honey', 'category': 'food', 'quantity': 3, 'unit': 'lbs'},
            {'name': 'Salt', 'category': 'food', 'quantity': 5, 'unit': 'lbs'},
            {'name': 'Sugar', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
            {'name': 'Cooking oil', 'category': 'food', 'quantity': 2, 'unit': 'gallons'},
            {'name': 'Powdered milk', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
            {'name': 'Flour (all-purpose)', 'category': 'food', 'quantity': 25, 'unit': 'lbs'},
            {'name': 'Baking soda', 'category': 'food', 'quantity': 2, 'unit': 'lbs'},
            {'name': 'Instant coffee', 'category': 'food', 'quantity': 2, 'unit': 'lbs'},
            {'name': 'Vitamins (multivitamin)', 'category': 'medical', 'quantity': 120, 'unit': 'tablets'},
            {'name': 'Water storage (5-gal jugs)', 'category': 'water', 'quantity': 12, 'unit': 'jugs'},
            {'name': 'Bleach (unscented)', 'category': 'water', 'quantity': 1, 'unit': 'gallon'},
            {'name': 'Water filter (gravity)', 'category': 'water', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Propane canisters', 'category': 'fuel', 'quantity': 8, 'unit': 'ea'},
            {'name': 'Camp stove', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Toilet paper', 'category': 'hygiene', 'quantity': 24, 'unit': 'rolls'},
            {'name': 'Bar soap', 'category': 'hygiene', 'quantity': 12, 'unit': 'bars'},
            {'name': 'Toothpaste', 'category': 'hygiene', 'quantity': 4, 'unit': 'tubes'},
            {'name': 'Laundry detergent', 'category': 'hygiene', 'quantity': 1, 'unit': 'jug'},
            {'name': 'Trash bags (13-gal)', 'category': 'tools', 'quantity': 60, 'unit': 'ea'},
            {'name': 'Candles (long-burn)', 'category': 'tools', 'quantity': 12, 'unit': 'ea'},
            {'name': 'D Batteries', 'category': 'tools', 'quantity': 16, 'unit': 'ea'},
            {'name': 'First aid kit (family)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Ibuprofen (200mg)', 'category': 'medical', 'quantity': 200, 'unit': 'tablets'},
            {'name': 'Acetaminophen (500mg)', 'category': 'medical', 'quantity': 200, 'unit': 'tablets'},
            {'name': 'Anti-diarrheal', 'category': 'medical', 'quantity': 1, 'unit': 'box'},
            {'name': 'Antibiotic ointment', 'category': 'medical', 'quantity': 3, 'unit': 'tubes'},
            {'name': 'Canned soup', 'category': 'food', 'quantity': 24, 'unit': 'cans'},
            {'name': 'Pasta (spaghetti)', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
            {'name': 'Pasta sauce', 'category': 'food', 'quantity': 8, 'unit': 'jars'},
            {'name': 'Dried lentils', 'category': 'food', 'quantity': 10, 'unit': 'lbs'},
            {'name': 'Cornmeal', 'category': 'food', 'quantity': 5, 'unit': 'lbs'},
            {'name': 'Bouillon cubes', 'category': 'food', 'quantity': 2, 'unit': 'boxes'},
            {'name': 'Spice kit (basics)', 'category': 'food', 'quantity': 1, 'unit': 'set'},
            {'name': 'Yeast (active dry)', 'category': 'food', 'quantity': 4, 'unit': 'packets'},
            {'name': 'Vinegar (white)', 'category': 'food', 'quantity': 1, 'unit': 'gallon'},
            {'name': 'Canned tomatoes', 'category': 'food', 'quantity': 12, 'unit': 'cans'},
        ],
    },
    'bug-out-bag': {
        'name': 'Bug-Out Bag',
        'description': 'Lightweight go-bag for rapid evacuation',
        'items': [
            {'name': 'Backpack (65L)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Water bottle (Nalgene 1L)', 'category': 'water', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Water filter (Sawyer Squeeze)', 'category': 'water', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Tarp (8x10)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Sleeping bag (compact)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Sleeping pad (inflatable)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Fire starter (ferro rod)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Lighter (windproof)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Tinder (fatwood sticks)', 'category': 'tools', 'quantity': 1, 'unit': 'bag'},
            {'name': 'Fixed-blade knife', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Folding saw', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Headlamp (200 lumen)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Spare batteries (AAA)', 'category': 'tools', 'quantity': 6, 'unit': 'ea'},
            {'name': 'Paracord (100ft)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Compass (lensatic)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Topographic map (local)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Freeze-dried meals', 'category': 'food', 'quantity': 6, 'unit': 'ea'},
            {'name': 'Beef jerky', 'category': 'food', 'quantity': 4, 'unit': 'bags'},
            {'name': 'Cliff bars', 'category': 'food', 'quantity': 12, 'unit': 'ea'},
            {'name': 'Electrolyte packets', 'category': 'food', 'quantity': 10, 'unit': 'ea'},
            {'name': 'IFAK (trauma kit)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Tourniquet (CAT)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Ibuprofen (travel pack)', 'category': 'medical', 'quantity': 1, 'unit': 'pack'},
            {'name': 'Bandana/shemagh', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Change of socks (wool)', 'category': 'other', 'quantity': 2, 'unit': 'pair'},
            {'name': 'Rain jacket (packable)', 'category': 'shelter', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Cordage (bank line 100ft)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Signal mirror', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Handheld radio (Baofeng UV-5R)', 'category': 'comms', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Notepad (Rite-in-Rain)', 'category': 'other', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Carabiners (locking)', 'category': 'tools', 'quantity': 4, 'unit': 'ea'},
            {'name': 'Zip ties (assorted)', 'category': 'tools', 'quantity': 20, 'unit': 'ea'},
            {'name': 'Cash (small bills)', 'category': 'other', 'quantity': 300, 'unit': 'USD'},
            {'name': 'Cooking pot (titanium)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Spork (titanium)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
        ],
    },
    'first-aid-kit': {
        'name': 'First Aid Kit',
        'description': 'Comprehensive first aid and trauma supplies',
        'items': [
            {'name': 'Adhesive bandages (assorted)', 'category': 'medical', 'quantity': 100, 'unit': 'ea'},
            {'name': 'Gauze pads (4x4)', 'category': 'medical', 'quantity': 25, 'unit': 'ea'},
            {'name': 'Gauze roll (3 inch)', 'category': 'medical', 'quantity': 6, 'unit': 'rolls'},
            {'name': 'Medical tape (1 inch)', 'category': 'medical', 'quantity': 3, 'unit': 'rolls'},
            {'name': 'Elastic bandage (ACE wrap)', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
            {'name': 'Triangular bandage', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
            {'name': 'Tourniquet (CAT Gen 7)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Israeli bandage (6 inch)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'QuikClot hemostatic gauze', 'category': 'medical', 'quantity': 2, 'unit': 'packs'},
            {'name': 'Chest seal (vented)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'NPA airway (28Fr)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Nitrile gloves (pairs)', 'category': 'medical', 'quantity': 20, 'unit': 'pairs'},
            {'name': 'Alcohol prep pads', 'category': 'medical', 'quantity': 50, 'unit': 'ea'},
            {'name': 'Povidone-iodine swabs', 'category': 'medical', 'quantity': 25, 'unit': 'ea'},
            {'name': 'Antibiotic ointment (packets)', 'category': 'medical', 'quantity': 25, 'unit': 'ea'},
            {'name': 'Butterfly closures', 'category': 'medical', 'quantity': 20, 'unit': 'ea'},
            {'name': 'Splint (SAM splint)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Trauma shears', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Tweezers (fine point)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'CPR face shield', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Ibuprofen (200mg tablets)', 'category': 'medical', 'quantity': 50, 'unit': 'tablets'},
            {'name': 'Diphenhydramine (25mg)', 'category': 'medical', 'quantity': 25, 'unit': 'tablets'},
            {'name': 'Oral rehydration salts', 'category': 'medical', 'quantity': 10, 'unit': 'packets'},
            {'name': 'Burn gel packets', 'category': 'medical', 'quantity': 10, 'unit': 'ea'},
            {'name': 'Cold pack (instant)', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
        ],
    },
    'vehicle-emergency-kit': {
        'name': 'Vehicle Emergency Kit',
        'description': 'Roadside and vehicle emergency supplies',
        'items': [
            {'name': 'Jumper cables (20ft)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Tow strap (20ft, 20k lbs)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Tire plug kit', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Portable air compressor (12V)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Fix-a-Flat', 'category': 'tools', 'quantity': 2, 'unit': 'cans'},
            {'name': 'Reflective triangles', 'category': 'tools', 'quantity': 3, 'unit': 'ea'},
            {'name': 'Road flares', 'category': 'tools', 'quantity': 6, 'unit': 'ea'},
            {'name': 'Fire extinguisher (2.5 lb)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Flashlight (heavy duty)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Multi-tool (vehicle)', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Duct tape', 'category': 'tools', 'quantity': 1, 'unit': 'roll'},
            {'name': 'WD-40', 'category': 'tools', 'quantity': 1, 'unit': 'can'},
            {'name': 'Zip ties (large)', 'category': 'tools', 'quantity': 20, 'unit': 'ea'},
            {'name': 'Bungee cords (assorted)', 'category': 'tools', 'quantity': 6, 'unit': 'ea'},
            {'name': 'Emergency blanket (wool)', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Rain poncho', 'category': 'shelter', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Water bottles (16oz)', 'category': 'water', 'quantity': 6, 'unit': 'ea'},
            {'name': 'Energy bars (vehicle pack)', 'category': 'food', 'quantity': 6, 'unit': 'ea'},
            {'name': 'First aid kit (vehicle)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Seatbelt cutter / window breaker', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
        ],
    },
    'medical-bag': {
        'name': 'Medical Bag (IFAK+)',
        'description': 'Enhanced Individual First Aid Kit plus field medic supplies',
        'items': [
            {'name': 'CAT Tourniquet (Gen 7)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Israeli Bandage (6")', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Chest Seal (vented)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'NPA (28Fr) with lube', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Compressed Gauze (Z-fold)', 'category': 'medical', 'quantity': 4, 'unit': 'ea'},
            {'name': 'Hemostatic Gauze (QuikClot)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Ace Bandage (4")', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Triangular Bandage', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Medical Tape (1")', 'category': 'medical', 'quantity': 2, 'unit': 'rolls'},
            {'name': 'Nitrile Gloves (pairs)', 'category': 'medical', 'quantity': 10, 'unit': 'pairs'},
            {'name': 'Trauma Shears', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'SAM Splint (36")', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Emergency Blanket (mylar)', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
            {'name': 'Ibuprofen 200mg', 'category': 'medical', 'quantity': 50, 'unit': 'tablets'},
            {'name': 'Acetaminophen 500mg', 'category': 'medical', 'quantity': 50, 'unit': 'tablets'},
            {'name': 'Diphenhydramine 25mg', 'category': 'medical', 'quantity': 24, 'unit': 'tablets'},
            {'name': 'Loperamide 2mg', 'category': 'medical', 'quantity': 12, 'unit': 'tablets'},
            {'name': 'Electrolyte packets', 'category': 'medical', 'quantity': 10, 'unit': 'ea'},
            {'name': 'Povidone-iodine swabs', 'category': 'medical', 'quantity': 20, 'unit': 'ea'},
            {'name': 'Steri-Strips (1/4"x3")', 'category': 'medical', 'quantity': 2, 'unit': 'packs'},
            {'name': 'Irrigation syringe (60ml)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Pulse oximeter', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Digital thermometer', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Blood pressure cuff (manual)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Stethoscope', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Penlight', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Burn gel packets', 'category': 'medical', 'quantity': 5, 'unit': 'ea'},
            {'name': 'Eye wash (4oz)', 'category': 'medical', 'quantity': 1, 'unit': 'ea'},
            {'name': 'Casualty card (TCCC)', 'category': 'medical', 'quantity': 10, 'unit': 'ea'},
            {'name': 'Sharpie marker', 'category': 'medical', 'quantity': 2, 'unit': 'ea'},
        ],
    },
}

@inventory_bp.route('/api/templates/inventory')
def api_templates_inventory():
    result = []
    for key, tpl in _INVENTORY_TEMPLATES.items():
        result.append({
            'id': key,
            'name': tpl['name'],
            'description': tpl['description'],
            'item_count': len(tpl['items']),
        })
    return jsonify(result)

@inventory_bp.route('/api/templates/inventory/apply', methods=['POST'])
def api_templates_inventory_apply():
    data = request.get_json() or {}
    template_id = data.get('template_id', '')
    if template_id not in _INVENTORY_TEMPLATES:
        return jsonify({'error': f'Unknown template: {template_id}. Available: {", ".join(_INVENTORY_TEMPLATES.keys())}'}), 400
    tpl = _INVENTORY_TEMPLATES[template_id]
    location = data.get('location', '')
    with db_session() as db:
        inserted = 0
        for item in tpl['items']:
            db.execute(
                'INSERT INTO inventory (name, category, quantity, unit, location, notes) VALUES (?, ?, ?, ?, ?, ?)',
                (item['name'], item.get('category', 'other'), item.get('quantity', 0),
                 item.get('unit', 'ea'), location, f'From template: {tpl["name"]}'))
            inserted += 1
        db.commit()
    log_activity('template_applied', 'inventory', f'{tpl["name"]} ({inserted} items)')
    return jsonify({'status': 'applied', 'template': tpl['name'], 'items_inserted': inserted})
