"""Hunting, Foraging & Wild Food — game logs, fishing, foraging, traps/snares,
wild edibles reference, trade skills, trade projects, preservation methods,
preservation batches, and hunting zones."""

import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from db import db_session, log_activity

_log = logging.getLogger(__name__)

hunting_foraging_bp = Blueprint('hunting_foraging', __name__, url_prefix='/api/hunting')


# ─── Helpers ─────────────────────────────────────────────────────────

def _now():
    return datetime.utcnow().isoformat()


def _row(r, json_cols=None):
    """Convert a row to dict, leaving JSON columns as-is on read."""
    d = dict(r)
    return d


def _json_dump(val):
    """Safely dump a value to JSON string for storage."""
    if isinstance(val, (list, dict)):
        return json.dumps(val)
    if isinstance(val, str):
        return val
    return json.dumps(val) if val is not None else '[]'


def _build_update(data, allowed, json_fields=None):
    """Build SET clause and values list from allowed keys."""
    json_fields = json_fields or []
    sets, vals = [], []
    for k in allowed:
        if k in data:
            sets.append(f'{k} = ?')
            v = data[k]
            vals.append(json.dumps(v) if k in json_fields and isinstance(v, (list, dict)) else v)
    return sets, vals


# ═══════════════════════════════════════════════════════════════════════
# HUNTING GAME LOG
# ═══════════════════════════════════════════════════════════════════════

GAME_FIELDS = ['date', 'species', 'game_type', 'location', 'gps_coords', 'method',
               'weapon_details', 'weight_lbs', 'meat_yield_lbs', 'field_dressed',
               'trophy', 'license_tag', 'season', 'weather_conditions', 'notes']


@hunting_foraging_bp.route('/game/stats')
def api_game_stats():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as cnt FROM hunting_game_log').fetchone()['cnt']
        total_meat = db.execute(
            'SELECT COALESCE(SUM(meat_yield_lbs), 0) as total FROM hunting_game_log'
        ).fetchone()['total']
        by_species = db.execute(
            '''SELECT species, COUNT(*) as cnt, COALESCE(SUM(meat_yield_lbs), 0) as meat
               FROM hunting_game_log GROUP BY species ORDER BY cnt DESC'''
        ).fetchall()
        by_method = db.execute(
            '''SELECT method, COUNT(*) as cnt, COALESCE(SUM(meat_yield_lbs), 0) as meat
               FROM hunting_game_log GROUP BY method ORDER BY cnt DESC'''
        ).fetchall()
        by_season = db.execute(
            '''SELECT season, COUNT(*) as cnt, COALESCE(SUM(meat_yield_lbs), 0) as meat
               FROM hunting_game_log GROUP BY season ORDER BY cnt DESC'''
        ).fetchall()
    return jsonify({
        'total_harvested': total,
        'total_meat_yield_lbs': total_meat,
        'by_species': [dict(r) for r in by_species],
        'by_method': [dict(r) for r in by_method],
        'by_season': [dict(r) for r in by_season],
    })


@hunting_foraging_bp.route('/game')
def api_game_list():
    game_type = request.args.get('type', '').strip()
    species = request.args.get('species', '').strip()
    season = request.args.get('season', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM hunting_game_log WHERE 1=1'
        params = []
        if game_type:
            q += ' AND game_type = ?'
            params.append(game_type)
        if species:
            q += ' AND species LIKE ?'
            params.append(f'%{species}%')
        if season:
            q += ' AND season = ?'
            params.append(season)
        q += ' ORDER BY id DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/game', methods=['POST'])
def api_game_create():
    data = request.get_json() or {}
    species = (data.get('species') or '').strip()
    if not species:
        return jsonify({'error': 'species is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO hunting_game_log
               (date, species, game_type, location, gps_coords, method, weapon_details,
                weight_lbs, meat_yield_lbs, field_dressed, trophy, license_tag, season,
                weather_conditions, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('date', now[:10]), species, data.get('game_type', ''),
             data.get('location', ''), data.get('gps_coords', ''),
             data.get('method', ''), data.get('weapon_details', ''),
             data.get('weight_lbs', 0), data.get('meat_yield_lbs', 0),
             1 if data.get('field_dressed') else 0,
             1 if data.get('trophy') else 0,
             data.get('license_tag', ''), data.get('season', ''),
             data.get('weather_conditions', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM hunting_game_log WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('game_logged', service='hunting_foraging', detail=f'{species}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/game/<int:gid>')
def api_game_detail(gid):
    with db_session() as db:
        row = db.execute('SELECT * FROM hunting_game_log WHERE id = ?', (gid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/game/<int:gid>', methods=['PUT'])
def api_game_update(gid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, GAME_FIELDS)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(gid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM hunting_game_log WHERE id = ?', (gid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE hunting_game_log SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM hunting_game_log WHERE id = ?', (gid,)).fetchone()
    log_activity('game_updated', service='hunting_foraging', detail=f'id={gid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/game/<int:gid>', methods=['DELETE'])
def api_game_delete(gid):
    with db_session() as db:
        row = db.execute('SELECT species FROM hunting_game_log WHERE id = ?', (gid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM hunting_game_log WHERE id = ?', (gid,))
        db.commit()
    log_activity('game_deleted', service='hunting_foraging', detail=f'{row["species"]} id={gid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
# FISHING LOG
# ═══════════════════════════════════════════════════════════════════════

FISHING_FIELDS = ['date', 'species', 'location', 'gps_coords', 'method', 'bait_lure',
                  'weight_lbs', 'length_inches', 'kept', 'water_type', 'water_temp_f',
                  'weather_conditions', 'notes']


@hunting_foraging_bp.route('/fishing/stats')
def api_fishing_stats():
    with db_session() as db:
        total = db.execute('SELECT COUNT(*) as cnt FROM fishing_log').fetchone()['cnt']
        by_species = db.execute(
            '''SELECT species, COUNT(*) as cnt, COALESCE(SUM(weight_lbs), 0) as total_weight
               FROM fishing_log GROUP BY species ORDER BY cnt DESC'''
        ).fetchall()
        kept_vs_released = db.execute(
            '''SELECT
                 SUM(CASE WHEN kept = 1 THEN 1 ELSE 0 END) as kept,
                 SUM(CASE WHEN kept = 0 THEN 1 ELSE 0 END) as released
               FROM fishing_log'''
        ).fetchone()
        avg_weight = db.execute(
            'SELECT COALESCE(AVG(weight_lbs), 0) as avg FROM fishing_log WHERE weight_lbs > 0'
        ).fetchone()['avg']
    return jsonify({
        'total_catch': total,
        'by_species': [dict(r) for r in by_species],
        'kept': kept_vs_released['kept'] or 0,
        'released': kept_vs_released['released'] or 0,
        'average_weight_lbs': round(avg_weight, 2),
    })


@hunting_foraging_bp.route('/fishing')
def api_fishing_list():
    species = request.args.get('species', '').strip()
    water_type = request.args.get('water_type', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM fishing_log WHERE 1=1'
        params = []
        if species:
            q += ' AND species LIKE ?'
            params.append(f'%{species}%')
        if water_type:
            q += ' AND water_type = ?'
            params.append(water_type)
        q += ' ORDER BY id DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/fishing', methods=['POST'])
def api_fishing_create():
    data = request.get_json() or {}
    species = (data.get('species') or '').strip()
    if not species:
        return jsonify({'error': 'species is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO fishing_log
               (date, species, location, gps_coords, method, bait_lure, weight_lbs,
                length_inches, kept, water_type, water_temp_f, weather_conditions,
                notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('date', now[:10]), species, data.get('location', ''),
             data.get('gps_coords', ''), data.get('method', ''),
             data.get('bait_lure', ''), data.get('weight_lbs', 0),
             data.get('length_inches', 0),
             1 if data.get('kept') else 0,
             data.get('water_type', 'freshwater'), data.get('water_temp_f', 0),
             data.get('weather_conditions', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM fishing_log WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('fish_logged', service='hunting_foraging', detail=f'{species}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/fishing/<int:fid>')
def api_fishing_detail(fid):
    with db_session() as db:
        row = db.execute('SELECT * FROM fishing_log WHERE id = ?', (fid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/fishing/<int:fid>', methods=['PUT'])
def api_fishing_update(fid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, FISHING_FIELDS)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(fid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM fishing_log WHERE id = ?', (fid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE fishing_log SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM fishing_log WHERE id = ?', (fid,)).fetchone()
    log_activity('fish_updated', service='hunting_foraging', detail=f'id={fid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/fishing/<int:fid>', methods=['DELETE'])
def api_fishing_delete(fid):
    with db_session() as db:
        row = db.execute('SELECT species FROM fishing_log WHERE id = ?', (fid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM fishing_log WHERE id = ?', (fid,))
        db.commit()
    log_activity('fish_deleted', service='hunting_foraging', detail=f'{row["species"]} id={fid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
# FORAGING LOG
# ═══════════════════════════════════════════════════════════════════════

FORAGING_FIELDS = ['date', 'plant_name', 'scientific_name', 'category', 'location',
                   'gps_coords', 'quantity_harvested', 'unit', 'season', 'habitat',
                   'confidence_level', 'photo_ref', 'preparation_notes', 'warnings', 'notes']


@hunting_foraging_bp.route('/foraging')
def api_foraging_list():
    category = request.args.get('category', '').strip()
    confidence = request.args.get('confidence', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM foraging_log WHERE 1=1'
        params = []
        if category:
            q += ' AND category = ?'
            params.append(category)
        if confidence:
            q += ' AND confidence_level = ?'
            params.append(confidence)
        q += ' ORDER BY id DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/foraging', methods=['POST'])
def api_foraging_create():
    data = request.get_json() or {}
    plant = (data.get('plant_name') or '').strip()
    if not plant:
        return jsonify({'error': 'plant_name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO foraging_log
               (date, plant_name, scientific_name, category, location, gps_coords,
                quantity_harvested, unit, season, habitat, confidence_level, photo_ref,
                preparation_notes, warnings, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('date', now[:10]), plant, data.get('scientific_name', ''),
             data.get('category', 'edible_plant'), data.get('location', ''),
             data.get('gps_coords', ''), data.get('quantity_harvested', 0),
             data.get('unit', ''), data.get('season', ''), data.get('habitat', ''),
             data.get('confidence_level', 'probable'), data.get('photo_ref', ''),
             data.get('preparation_notes', ''), data.get('warnings', ''),
             data.get('notes', ''), now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM foraging_log WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('forage_logged', service='hunting_foraging', detail=f'{plant}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/foraging/<int:fid>')
def api_foraging_detail(fid):
    with db_session() as db:
        row = db.execute('SELECT * FROM foraging_log WHERE id = ?', (fid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/foraging/<int:fid>', methods=['PUT'])
def api_foraging_update(fid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, FORAGING_FIELDS)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(fid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM foraging_log WHERE id = ?', (fid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE foraging_log SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM foraging_log WHERE id = ?', (fid,)).fetchone()
    log_activity('forage_updated', service='hunting_foraging', detail=f'id={fid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/foraging/<int:fid>', methods=['DELETE'])
def api_foraging_delete(fid):
    with db_session() as db:
        row = db.execute('SELECT plant_name FROM foraging_log WHERE id = ?', (fid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM foraging_log WHERE id = ?', (fid,))
        db.commit()
    log_activity('forage_deleted', service='hunting_foraging',
                 detail=f'{row["plant_name"]} id={fid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
# TRAPS & SNARES
# ═══════════════════════════════════════════════════════════════════════

TRAP_FIELDS = ['name', 'trap_type', 'target_species', 'location', 'gps_coords',
               'set_date', 'check_date', 'check_frequency_hours', 'status', 'catches',
               'materials_used', 'bait', 'instructions', 'legal_notes', 'notes']
TRAP_JSON = ['materials_used']


@hunting_foraging_bp.route('/traps')
def api_traps_list():
    status = request.args.get('status', '').strip()
    trap_type = request.args.get('type', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM traps_snares WHERE 1=1'
        params = []
        if status:
            q += ' AND status = ?'
            params.append(status)
        if trap_type:
            q += ' AND trap_type = ?'
            params.append(trap_type)
        q += ' ORDER BY id DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/traps', methods=['POST'])
def api_traps_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO traps_snares
               (name, trap_type, target_species, location, gps_coords, set_date,
                check_date, check_frequency_hours, status, catches, materials_used,
                bait, instructions, legal_notes, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('trap_type', 'snare'), data.get('target_species', ''),
             data.get('location', ''), data.get('gps_coords', ''),
             data.get('set_date', now[:10]), data.get('check_date', ''),
             data.get('check_frequency_hours', 24), data.get('status', 'active'),
             data.get('catches', 0),
             json.dumps(data.get('materials_used', [])),
             data.get('bait', ''), data.get('instructions', ''),
             data.get('legal_notes', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM traps_snares WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('trap_created', service='hunting_foraging', detail=f'{name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/traps/<int:tid>')
def api_traps_detail(tid):
    with db_session() as db:
        row = db.execute('SELECT * FROM traps_snares WHERE id = ?', (tid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/traps/<int:tid>', methods=['PUT'])
def api_traps_update(tid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, TRAP_FIELDS, json_fields=TRAP_JSON)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(tid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM traps_snares WHERE id = ?', (tid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE traps_snares SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM traps_snares WHERE id = ?', (tid,)).fetchone()
    log_activity('trap_updated', service='hunting_foraging', detail=f'id={tid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/traps/<int:tid>', methods=['DELETE'])
def api_traps_delete(tid):
    with db_session() as db:
        row = db.execute('SELECT name FROM traps_snares WHERE id = ?', (tid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM traps_snares WHERE id = ?', (tid,))
        db.commit()
    log_activity('trap_deleted', service='hunting_foraging', detail=f'{row["name"]} id={tid}')
    return jsonify({'deleted': True})


@hunting_foraging_bp.route('/traps/<int:tid>/check', methods=['POST'])
def api_traps_check(tid):
    """Record a trap check — update check_date, optionally increment catches, update status."""
    data = request.get_json() or {}
    now = _now()
    with db_session() as db:
        row = db.execute('SELECT * FROM traps_snares WHERE id = ?', (tid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        new_catches = row['catches'] or 0
        if data.get('caught'):
            new_catches += 1
        new_status = data.get('status', row['status'])
        db.execute(
            '''UPDATE traps_snares
               SET check_date = ?, catches = ?, status = ?, updated_at = ?
               WHERE id = ?''',
            (now[:10], new_catches, new_status, now, tid)
        )
        db.commit()
        row = db.execute('SELECT * FROM traps_snares WHERE id = ?', (tid,)).fetchone()
    log_activity('trap_checked', service='hunting_foraging',
                 detail=f'{row["name"]} catches={new_catches}')
    return jsonify(dict(row))


# ═══════════════════════════════════════════════════════════════════════
# WILD EDIBLES REFERENCE
# ═══════════════════════════════════════════════════════════════════════

EDIBLE_FIELDS = ['common_name', 'scientific_name', 'category', 'edible_parts',
                 'season_available', 'habitat', 'identification_features', 'look_alikes',
                 'preparation_methods', 'nutritional_info', 'medicinal_uses',
                 'toxicity_warnings', 'image_ref', 'region', 'confidence_required']
EDIBLE_JSON = ['edible_parts', 'season_available', 'preparation_methods']

SEED_WILD_EDIBLES = [
    {
        'common_name': 'Dandelion',
        'scientific_name': 'Taraxacum officinale',
        'category': 'plant',
        'edible_parts': ['leaves', 'flowers', 'roots'],
        'season_available': ['spring', 'summer', 'fall'],
        'habitat': 'Lawns, fields, roadsides, disturbed soil',
        'identification_features': 'Rosette of deeply toothed leaves, hollow stems with milky sap, bright yellow composite flower heads, white puffball seed heads',
        'look_alikes': 'Cat\'s ear (Hypochaeris radicata) — hairy leaves, branching stems; Chicory — blue flowers; Hawkweed — similar but hairy stems',
        'preparation_methods': ['raw salad greens', 'sauteed greens', 'dried root tea', 'flower fritters', 'dandelion wine', 'roasted root coffee substitute'],
        'nutritional_info': 'High in vitamins A, C, K, calcium, potassium, iron. Leaves more nutritious than spinach.',
        'medicinal_uses': 'Diuretic, liver support, digestive aid, anti-inflammatory',
        'toxicity_warnings': 'Generally safe. Avoid if allergic to Asteraceae family. May interact with diuretics and blood thinners.',
        'region': 'North America — all regions',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Chicory',
        'scientific_name': 'Cichorium intybus',
        'category': 'plant',
        'edible_parts': ['leaves', 'roots', 'flowers'],
        'season_available': ['spring', 'summer', 'fall'],
        'habitat': 'Roadsides, fields, waste areas, disturbed soil',
        'identification_features': 'Bright blue daisy-like flowers on stiff branching stems, basal rosette of toothed leaves, deep taproot, milky sap',
        'look_alikes': 'Dandelion (basal leaves similar but chicory has branching stems); Blue lettuce — similar flowers but taller',
        'preparation_methods': ['young leaves raw in salads', 'boiled greens', 'roasted root coffee substitute', 'blanched hearts (chicons)'],
        'nutritional_info': 'Rich in inulin (prebiotic fiber), vitamins A, C, K, manganese, phosphorus',
        'medicinal_uses': 'Digestive aid (prebiotic), liver tonic, mild laxative, anti-parasitic',
        'toxicity_warnings': 'May cause allergic reactions in Asteraceae-sensitive individuals. Excessive consumption may cause gas/bloating from inulin.',
        'region': 'North America — all regions',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Cattail',
        'scientific_name': 'Typha latifolia',
        'category': 'plant',
        'edible_parts': ['shoots', 'roots', 'pollen', 'flower spikes', 'rhizomes'],
        'season_available': ['spring', 'summer', 'fall', 'winter'],
        'habitat': 'Marshes, pond edges, ditches, wet meadows, stream banks',
        'identification_features': 'Tall (6-10 ft) grass-like leaves, distinctive brown cigar-shaped seed heads, flat blade-like leaves in a fan arrangement',
        'look_alikes': 'Iris species (TOXIC — flattened fan leaves but no brown seed head); Sweet flag (Acorus calamus) — similar habitat but aromatic',
        'preparation_methods': ['young shoots raw or cooked like asparagus', 'rhizome flour', 'pollen as flour supplement', 'immature flower spikes boiled like corn'],
        'nutritional_info': 'Shoots high in starch and vitamins A/B/C. Pollen rich in protein. Rhizome starch comparable to potato.',
        'medicinal_uses': 'Wound dressing (seed fluff), burn treatment (gel from young shoots), anti-diarrheal',
        'toxicity_warnings': 'Ensure correct ID — do NOT confuse with toxic iris. Only harvest from clean water sources (cattails bioaccumulate pollutants).',
        'region': 'North America — all regions',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Plantain',
        'scientific_name': 'Plantago major',
        'category': 'plant',
        'edible_parts': ['leaves', 'seeds'],
        'season_available': ['spring', 'summer', 'fall'],
        'habitat': 'Lawns, paths, compacted soil, disturbed areas, trailsides',
        'identification_features': 'Broad oval leaves in basal rosette, prominent parallel veins (5-7), tough string-like fibers when leaf is torn, rat-tail flower spike',
        'look_alikes': 'Hosta (larger, shade garden plant — mildly toxic); Lily of the valley (TOXIC — similar broad leaves but fragrant flowers)',
        'preparation_methods': ['young leaves raw in salads', 'cooked greens', 'dried leaf tea', 'seed husk (psyllium relative) as fiber supplement'],
        'nutritional_info': 'High in calcium, vitamins A, C, K. Seeds contain mucilage fiber similar to psyllium.',
        'medicinal_uses': 'Poultice for insect bites/stings, wound healing, anti-inflammatory, cough/cold remedy (tea)',
        'toxicity_warnings': 'Very safe. One of the most reliable wild edibles for beginners. No significant look-alike danger.',
        'region': 'North America — all regions',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Wood Sorrel',
        'scientific_name': 'Oxalis stricta',
        'category': 'plant',
        'edible_parts': ['leaves', 'flowers', 'seed pods'],
        'season_available': ['spring', 'summer', 'fall'],
        'habitat': 'Woodlands, gardens, shaded lawns, forest edges, disturbed areas',
        'identification_features': 'Heart-shaped trifoliate leaves (clover-like but heart-shaped leaflets), small yellow 5-petaled flowers, leaves fold down at night, sour lemony taste',
        'look_alikes': 'Clover (Trifolium — round leaflets not heart-shaped); Shamrock/black medick — similar but no sour taste',
        'preparation_methods': ['raw snacking/trail nibble', 'salad green', 'lemonade substitute (cold infusion)', 'garnish'],
        'nutritional_info': 'Good source of vitamin C. Contains oxalic acid (gives sour taste).',
        'medicinal_uses': 'Cooling fever remedy, thirst quencher, mild diuretic',
        'toxicity_warnings': 'Contains oxalic acid — eat in moderation. Avoid large quantities if prone to kidney stones. Not recommended for those with gout or kidney disease.',
        'region': 'North America — all regions',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Black Walnut',
        'scientific_name': 'Juglans nigra',
        'category': 'nut',
        'edible_parts': ['nuts', 'sap'],
        'season_available': ['fall', 'winter'],
        'habitat': 'Deciduous forests, river bottoms, hillsides, open woodlands',
        'identification_features': 'Large compound leaves (15-23 leaflets), round green husks turning black, deeply furrowed dark bark, strong distinctive smell when husks crushed',
        'look_alikes': 'Tree of heaven (Ailanthus — similar leaves but foul smell, no nuts); Butternut (Juglans cinerea — edible cousin, oblong nuts)',
        'preparation_methods': ['cracked nuts eaten raw', 'baked goods', 'black walnut ice cream', 'hull tincture', 'sap boiled for syrup'],
        'nutritional_info': 'Rich in omega-3 fatty acids, protein, manganese, magnesium. Higher flavor intensity than English walnuts.',
        'medicinal_uses': 'Hull tincture as anti-parasitic and antifungal, bark tea for digestive issues',
        'toxicity_warnings': 'Hulls stain everything (wear gloves). Juglone compound toxic to some plants (allelopathic). Nut allergy risk for sensitive individuals.',
        'region': 'North America — Eastern and Central US/Canada',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Elderberry',
        'scientific_name': 'Sambucus nigra',
        'category': 'berry',
        'edible_parts': ['berries', 'flowers'],
        'season_available': ['summer', 'fall'],
        'habitat': 'Forest edges, hedgerows, stream banks, roadsides, disturbed areas',
        'identification_features': 'Compound leaves (5-7 serrated leaflets), flat-topped clusters of tiny white flowers, drooping clusters of small dark purple-black berries, pithy stems',
        'look_alikes': 'Water hemlock (DEADLY — similar habitat, compound leaves but different flower/berry clusters); Pokeweed (TOXIC — purple berries but alternate leaves, single stem)',
        'preparation_methods': ['cooked berries for syrup/jam/wine', 'elderflower cordial', 'elderflower fritters', 'dried berries for tea'],
        'nutritional_info': 'Very high in vitamin C, anthocyanins (antioxidants), vitamin A, potassium, iron',
        'medicinal_uses': 'Immune support (elderberry syrup), cold/flu remedy, anti-viral properties, fever reducer',
        'toxicity_warnings': 'NEVER eat raw berries, leaves, bark, or stems — contain cyanogenic glycosides. Must be cooked. Red elderberry species more toxic. Positive ID critical — water hemlock look-alike is deadly.',
        'region': 'North America — all regions',
        'confidence_required': 'probable',
    },
    {
        'common_name': 'Morel Mushroom',
        'scientific_name': 'Morchella esculenta',
        'category': 'mushroom',
        'edible_parts': ['fruiting body'],
        'season_available': ['spring'],
        'habitat': 'Deciduous forests near ash/elm/tulip poplar, old orchards, recently burned areas, river bottoms',
        'identification_features': 'Honeycomb-patterned cap with pits and ridges, hollow from cap to stem base (cut in half to verify), cap attached directly to stem at base',
        'look_alikes': 'False morel (Gyromitra — TOXIC, brain-like wrinkled cap not honeycomb, interior chambered not hollow); Verpa (cap attached only at top of stem)',
        'preparation_methods': ['sauteed in butter', 'cream sauce', 'breaded and fried', 'dried for storage and reconstituted'],
        'nutritional_info': 'Good source of iron, copper, manganese, phosphorus, vitamin D, B vitamins. High in protein for a mushroom.',
        'medicinal_uses': 'Immune support, anti-inflammatory, antioxidant',
        'toxicity_warnings': 'MUST cook thoroughly — raw morels cause GI distress. Positive ID critical — false morels contain gyromitrin (potentially fatal). Always slice in half to verify hollow interior.',
        'region': 'North America — Northern and Central US/Canada',
        'confidence_required': 'certain',
    },
    {
        'common_name': 'Chanterelle',
        'scientific_name': 'Cantharellus cibarius',
        'category': 'mushroom',
        'edible_parts': ['fruiting body'],
        'season_available': ['summer', 'fall'],
        'habitat': 'Mixed hardwood and conifer forests, mossy areas, near oak/beech/birch, well-drained slopes',
        'identification_features': 'Golden-yellow funnel shape, false gills (forked ridges running down stem, not blade-like), fruity/apricot aroma, white interior flesh, wavy cap margins',
        'look_alikes': 'Jack-o-lantern (Omphalotus — TOXIC, true gills, grows in clusters on wood, bioluminescent); False chanterelle (Hygrophoropsis — thinner, true gills, orange not golden)',
        'preparation_methods': ['sauteed in butter', 'cream sauces', 'risotto', 'dried for storage', 'pickled'],
        'nutritional_info': 'Excellent source of vitamin D, vitamin B complex, copper, potassium, selenium',
        'medicinal_uses': 'Anti-inflammatory, antibacterial, vitamin D source, immune support',
        'toxicity_warnings': 'Learn to distinguish false gills from true gills. Jack-o-lantern mushroom is the primary danger — it has true blade-like gills and grows on wood in clusters.',
        'region': 'North America — all forested regions',
        'confidence_required': 'probable',
    },
    {
        'common_name': 'Wild Garlic (Ramps)',
        'scientific_name': 'Allium tricoccum',
        'category': 'plant',
        'edible_parts': ['leaves', 'bulbs', 'stems'],
        'season_available': ['spring'],
        'habitat': 'Rich deciduous forests, moist shaded slopes, along streams, under sugar maple/beech/birch',
        'identification_features': 'Broad smooth elliptical leaves (1-2 per bulb), strong garlic/onion smell when crushed, reddish-purple stem base, small white bulb',
        'look_alikes': 'Lily of the valley (TOXIC — similar leaves but NO garlic smell, grows in denser colonies); False hellebore (TOXIC — pleated leaves, no garlic smell)',
        'preparation_methods': ['raw in salads/pesto', 'sauteed greens', 'pickled ramps', 'compound butter', 'kimchi', 'dehydrated ramp powder'],
        'nutritional_info': 'High in vitamins A and C, selenium, chromium. Rich in sulfur compounds similar to garlic.',
        'medicinal_uses': 'Antimicrobial, cardiovascular support, digestive aid, spring tonic',
        'toxicity_warnings': 'ALWAYS use smell test — crush leaf and confirm garlic/onion aroma. Lily of the valley look-alike is cardiac toxic and potentially fatal. Harvest sustainably — take no more than 10% of a colony.',
        'region': 'North America — Eastern US/Canada, Appalachian region',
        'confidence_required': 'certain',
    },
]


# ─── Seed Data: Preservation Methods ────────────────────────────────

SEED_PRESERVATION_METHODS = [
    {
        'name': 'Water Bath Canning',
        'method_type': 'canning',
        'input_item': 'High-acid foods (fruits, pickles, jams, tomatoes with added acid)',
        'output_item': 'Sealed canned jars',
        'equipment_needed': ['water bath canner or large stockpot', 'canning rack', 'jar lifter', 'bubble remover', 'wide-mouth funnel', 'magnetic lid lifter'],
        'supplies_needed': ['Mason jars (pint/quart)', 'new lids', 'bands/rings', 'pectin (for jams)', 'citric acid or lemon juice (for tomatoes)', 'sugar', 'vinegar (5% acidity)'],
        'process_steps': [
            'Sterilize jars in boiling water for 10 minutes',
            'Prepare food per tested recipe',
            'Fill hot jars leaving proper headspace (1/4" jams, 1/2" fruits/pickles)',
            'Remove air bubbles with bubble remover',
            'Wipe jar rims clean with damp cloth',
            'Apply lids and screw bands to fingertip-tight',
            'Submerge jars in boiling water (1-2" above lids)',
            'Process for time specified by recipe (adjust for altitude)',
            'Remove jars and cool 12-24 hours undisturbed',
            'Verify seal (lid does not flex), remove bands, label and date'
        ],
        'processing_time_hours': 2,
        'shelf_life_days': 548,
        'yield_ratio': 0.95,
        'safety_notes': 'ONLY use tested recipes from USDA, Ball, or NCHFP. Never water-bath can low-acid foods (meat, vegetables, soups) — requires pressure canning. Adjust processing time for altitude (+1 min per 1000 ft above sea level). Discard any jars that did not seal.',
        'temperature_requirements': 'Process at rolling boil (212F/100C at sea level)',
    },
    {
        'name': 'Pressure Canning',
        'method_type': 'canning',
        'input_item': 'Low-acid foods (vegetables, meats, soups, stocks, beans)',
        'output_item': 'Sealed pressure-canned jars',
        'equipment_needed': ['weighted-gauge or dial-gauge pressure canner', 'canning rack', 'jar lifter', 'bubble remover', 'wide-mouth funnel'],
        'supplies_needed': ['Mason jars (pint/quart)', 'new lids', 'bands/rings', 'salt (optional)', 'broth or water for packing liquid'],
        'process_steps': [
            'Place rack and 2-3 inches of hot water in canner',
            'Prepare food per tested recipe (raw pack or hot pack)',
            'Fill hot jars leaving 1" headspace',
            'Remove air bubbles and adjust headspace',
            'Wipe rims, apply lids and bands fingertip-tight',
            'Place jars on rack in canner, secure lid',
            'Heat until steam vents steadily for 10 minutes (exhaust air)',
            'Close vent/place weight, bring to correct pressure (10-15 PSI based on altitude)',
            'Process for recipe time at steady pressure',
            'Turn off heat, let pressure drop to zero naturally (do not quick-release)',
            'Wait 10 minutes, open lid away from face, remove jars',
            'Cool 12-24 hours, verify seals, label and date'
        ],
        'processing_time_hours': 3,
        'shelf_life_days': 730,
        'yield_ratio': 0.90,
        'safety_notes': 'MANDATORY for all low-acid foods to prevent botulism. Never open canner before pressure reaches zero. Have dial gauges tested annually. Adjust PSI for altitude. Only use tested USDA recipes. Discard any jars with broken seals or off odors.',
        'temperature_requirements': '240F/116C (achieved at 10 PSI at sea level)',
    },
    {
        'name': 'Dehydrating',
        'method_type': 'dehydrating',
        'input_item': 'Fruits, vegetables, herbs, jerky meats',
        'output_item': 'Dried/dehydrated food',
        'equipment_needed': ['food dehydrator (preferred) or oven', 'sharp knife or mandoline', 'parchment/silicone sheets for fruit leather', 'vacuum sealer (optional)'],
        'supplies_needed': ['lemon juice or ascorbic acid (anti-browning for fruits)', 'marinade ingredients (for jerky)', 'oxygen absorbers', 'mylar bags or mason jars for storage'],
        'process_steps': [
            'Wash and prepare food — slice uniformly thin (1/8" to 1/4")',
            'Pre-treat fruits with lemon juice or ascorbic acid dip to prevent browning',
            'For jerky: marinate sliced lean meat 4-24 hours, pat dry',
            'Arrange on dehydrator trays in single layer without overlapping',
            'Set temperature (125F herbs, 135F vegetables, 135F fruits, 160F meats)',
            'Dry until proper texture (fruits pliable, veggies brittle, jerky bends without breaking)',
            'Condition fruits: place in jar 7-10 days, shake daily, watch for moisture',
            'Package in airtight containers with oxygen absorbers',
            'Label with contents and date'
        ],
        'processing_time_hours': 12,
        'shelf_life_days': 365,
        'yield_ratio': 0.15,
        'safety_notes': 'Jerky must reach 160F internal temp to kill pathogens. Properly dried foods should show no moisture when squeezed. Store away from light and heat. Sulfite-treated fruits last longer but some people are sensitive.',
        'temperature_requirements': '125-160F depending on food type',
    },
    {
        'name': 'Smoking',
        'method_type': 'smoking',
        'input_item': 'Meats, fish, cheese, salt',
        'output_item': 'Smoked preserved food',
        'equipment_needed': ['smoker (offset, vertical, or cold-smoke generator)', 'meat thermometer', 'wood chips/chunks (hickory, apple, cherry, mesquite)', 'hanging hooks or racks'],
        'supplies_needed': ['curing salt (Prague powder #1 for short cure, #2 for long cure)', 'kosher salt', 'sugar/brown sugar', 'spices for rub/brine', 'butcher twine'],
        'process_steps': [
            'Cure meat with salt/curing salt mixture (dry rub or brine) for 1-14 days depending on thickness',
            'Rinse cured meat and pat dry',
            'Air dry in refrigerator uncovered 12-24 hours to form pellicle (tacky surface)',
            'Prepare smoker with chosen wood — soak chips if using charcoal smoker',
            'Cold smoke (68-86F) for flavor only, or hot smoke (200-275F) for cooking',
            'Maintain consistent temperature and thin blue smoke (not white billowy)',
            'Hot smoke until internal temp reaches safe level (145F fish, 165F poultry, 195F pork)',
            'Rest meat, then refrigerate or vacuum seal',
            'Label with date and smoking method'
        ],
        'processing_time_hours': 8,
        'shelf_life_days': 90,
        'yield_ratio': 0.70,
        'safety_notes': 'Use curing salt (sodium nitrite) for cold-smoked meats to prevent botulism. Never cold smoke without proper curing. Keep smoker temp consistent. Fully smoked products must still be refrigerated unless additionally dried.',
        'temperature_requirements': 'Cold smoke: 68-86F. Hot smoke: 200-275F',
    },
    {
        'name': 'Salt Curing',
        'method_type': 'salting',
        'input_item': 'Meats, fish, vegetables',
        'output_item': 'Salt-preserved food',
        'equipment_needed': ['food-grade container or crock', 'weight/press', 'cutting board', 'sharp knife'],
        'supplies_needed': ['kosher salt or sea salt (non-iodized)', 'curing salt #2 (for long-cure meats)', 'sugar', 'herbs and spices', 'cheesecloth'],
        'process_steps': [
            'Calculate salt amount: 3-5% of food weight for equilibrium cure, heavier for excess salt method',
            'Mix salt with curing salt and spices',
            'Apply cure evenly, rubbing into all surfaces',
            'Pack in container, cover with cheesecloth, weight down',
            'Refrigerate (or cool storage 36-40F for large pieces)',
            'Turn/redistribute cure every few days',
            'Cure time: 7 days per inch of thickness (approximate)',
            'Rinse excess salt, pat dry',
            'Air dry or smoke for additional preservation',
            'Store in cool, dry location or vacuum seal'
        ],
        'processing_time_hours': 168,
        'shelf_life_days': 180,
        'yield_ratio': 0.80,
        'safety_notes': 'Use precise measurements for curing salt — too little risks botulism, too much is toxic. Never use iodized table salt (off flavors). Maintain cold temperatures throughout curing. Curing salt #2 (sodium nitrate) is for long-aged products only.',
        'temperature_requirements': '36-40F during curing',
    },
    {
        'name': 'Lacto-Fermentation',
        'method_type': 'fermenting',
        'input_item': 'Vegetables (cabbage, cucumbers, carrots, peppers, garlic)',
        'output_item': 'Fermented vegetables (sauerkraut, kimchi, pickles)',
        'equipment_needed': ['wide-mouth mason jars or fermentation crock', 'fermentation weights (glass or ceramic)', 'airlock lids (optional but recommended)', 'mandoline or knife'],
        'supplies_needed': ['non-iodized salt (sea salt or kosher)', 'filtered water (no chlorine)', 'optional: whey, starter culture, spices, garlic, ginger'],
        'process_steps': [
            'Clean vegetables thoroughly, chop/shred as desired',
            'For sauerkraut/kimchi: massage 2% salt by weight into shredded vegetables until liquid releases',
            'For brine pickles: dissolve 3-5% salt in filtered water',
            'Pack vegetables tightly into jar, submerge under brine',
            'Place weight on top to keep vegetables below liquid line',
            'Apply airlock lid or loosely cover (must allow CO2 to escape)',
            'Ferment at room temperature (60-75F) for 3-14 days',
            'Taste daily after day 3 — ferment to desired tanginess',
            'Once ready, seal with tight lid and refrigerate to slow fermentation',
            'Label with date and ferment duration'
        ],
        'processing_time_hours': 72,
        'shelf_life_days': 180,
        'yield_ratio': 0.90,
        'safety_notes': 'Vegetables MUST stay submerged below brine — exposed food will mold. Use non-iodized salt and chlorine-free water (chlorine kills beneficial bacteria). Kahm yeast (white film) is harmless but skim off. Discard if pink, black, or fuzzy mold appears. Fermented foods are very safe — the lactic acid environment prevents pathogen growth.',
        'temperature_requirements': '60-75F ideal. Below 60F: very slow. Above 80F: too fast, mushy results',
    },
    {
        'name': 'Vinegar Pickling',
        'method_type': 'pickling',
        'input_item': 'Vegetables, fruits, eggs',
        'output_item': 'Pickled preserved food',
        'equipment_needed': ['stainless steel or enamel pot (non-reactive)', 'mason jars', 'water bath canner (for shelf-stable)', 'jar lifter', 'wide-mouth funnel'],
        'supplies_needed': ['white vinegar or apple cider vinegar (5% acidity minimum)', 'pickling salt', 'sugar', 'pickling spices (dill, mustard seed, peppercorns, garlic)', 'filtered water'],
        'process_steps': [
            'Prepare vegetables: wash, trim, slice or leave whole as desired',
            'Make brine: combine vinegar, water, salt, sugar — standard ratio 1:1 vinegar to water with 1 Tbsp salt per cup',
            'Bring brine to boil, stir until salt/sugar dissolve',
            'Pack raw vegetables tightly into hot jars with spices',
            'Pour hot brine over vegetables leaving 1/2" headspace',
            'Remove air bubbles, wipe rims, apply lids',
            'For refrigerator pickles: cool and refrigerate — ready in 48 hours',
            'For shelf-stable: process in water bath 10-15 minutes',
            'Cool, verify seals, label and date',
            'Best flavor develops after 2-4 weeks'
        ],
        'processing_time_hours': 1,
        'shelf_life_days': 365,
        'yield_ratio': 0.95,
        'safety_notes': 'Vinegar MUST be 5% acidity — never dilute below tested recipe ratios. Do not reduce vinegar to lower sourness (add sugar instead). Shelf-stable pickles must be water-bath processed. Refrigerator pickles are quick pickles and must stay refrigerated.',
        'temperature_requirements': 'Room temperature storage after water-bath processing. Refrigerator pickles: 35-40F',
    },
    {
        'name': 'Root Cellaring',
        'method_type': 'root_cellar',
        'input_item': 'Root vegetables, apples, pears, cabbage, winter squash',
        'output_item': 'Fresh-stored produce',
        'equipment_needed': ['root cellar, unheated basement, or cold storage space', 'shelving (wood preferred)', 'thermometer and hygrometer', 'bins or crates', 'sand or sawdust'],
        'supplies_needed': ['clean sand or damp sawdust (for root storage)', 'newspaper (for wrapping apples)', 'straw', 'burlap sacks', 'ventilation supplies if needed'],
        'process_steps': [
            'Harvest crops at peak maturity, handle gently to avoid bruising',
            'Cure storage crops: potatoes 2 weeks at 50-60F, squash 10 days at 80-85F, onions 2-4 weeks in dry warm area',
            'Sort: only store perfect specimens — eat bruised/damaged ones first',
            'Do NOT wash root vegetables — brush off loose soil',
            'Pack roots (carrots, beets, turnips, parsnips) in damp sand in bins',
            'Store potatoes in dark bins or burlap sacks — light causes greening',
            'Wrap apples individually in newspaper, store in single layers',
            'Keep apples separate from other produce (ethylene gas hastens ripening)',
            'Monitor temperature (32-40F ideal) and humidity (80-95% for most roots)',
            'Check stored food weekly, remove any spoiling items immediately'
        ],
        'processing_time_hours': 1,
        'shelf_life_days': 180,
        'yield_ratio': 0.98,
        'safety_notes': 'Ventilation prevents CO2 buildup and mold. Never store near chemicals or fuel. Check regularly for rot — one bad item spoils neighbors. Potatoes exposed to light produce toxic solanine (green skin). Keep humidity high for roots but low for squash and onions.',
        'temperature_requirements': '32-40F and 80-95% humidity for most roots. 50-55F and 50-60% for squash/pumpkins. 32-40F and 60-70% for onions/garlic',
    },
]


@hunting_foraging_bp.route('/edibles')
def api_edibles_list():
    category = request.args.get('category', '').strip()
    region = request.args.get('region', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM wild_edibles WHERE 1=1'
        params = []
        if category:
            q += ' AND category = ?'
            params.append(category)
        if region:
            q += ' AND region LIKE ?'
            params.append(f'%{region}%')
        q += ' ORDER BY common_name'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/edibles', methods=['POST'])
def api_edibles_create():
    data = request.get_json() or {}
    name = (data.get('common_name') or '').strip()
    if not name:
        return jsonify({'error': 'common_name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO wild_edibles
               (common_name, scientific_name, category, edible_parts, season_available,
                habitat, identification_features, look_alikes, preparation_methods,
                nutritional_info, medicinal_uses, toxicity_warnings, image_ref,
                region, confidence_required, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('scientific_name', ''), data.get('category', 'plant'),
             json.dumps(data.get('edible_parts', [])),
             json.dumps(data.get('season_available', [])),
             data.get('habitat', ''), data.get('identification_features', ''),
             data.get('look_alikes', ''),
             json.dumps(data.get('preparation_methods', [])),
             data.get('nutritional_info', ''), data.get('medicinal_uses', ''),
             data.get('toxicity_warnings', ''), data.get('image_ref', ''),
             data.get('region', ''), data.get('confidence_required', 'probable'),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM wild_edibles WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('edible_created', service='hunting_foraging', detail=f'{name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/edibles/<int:eid>')
def api_edibles_detail(eid):
    with db_session() as db:
        row = db.execute('SELECT * FROM wild_edibles WHERE id = ?', (eid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/edibles/<int:eid>', methods=['PUT'])
def api_edibles_update(eid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, EDIBLE_FIELDS, json_fields=EDIBLE_JSON)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(eid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM wild_edibles WHERE id = ?', (eid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE wild_edibles SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM wild_edibles WHERE id = ?', (eid,)).fetchone()
    log_activity('edible_updated', service='hunting_foraging', detail=f'id={eid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/edibles/<int:eid>', methods=['DELETE'])
def api_edibles_delete(eid):
    with db_session() as db:
        row = db.execute('SELECT common_name FROM wild_edibles WHERE id = ?', (eid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM wild_edibles WHERE id = ?', (eid,))
        db.commit()
    log_activity('edible_deleted', service='hunting_foraging',
                 detail=f'{row["common_name"]} id={eid}')
    return jsonify({'deleted': True})


@hunting_foraging_bp.route('/edibles/search')
def api_edibles_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify({'error': 'q parameter is required'}), 400
    with db_session() as db:
        rows = db.execute(
            '''SELECT * FROM wild_edibles
               WHERE common_name LIKE ? OR scientific_name LIKE ?
               ORDER BY common_name''',
            (f'%{q}%', f'%{q}%')
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/edibles/seed', methods=['POST'])
def api_edibles_seed():
    with db_session() as db:
        count = db.execute('SELECT COUNT(*) as cnt FROM wild_edibles').fetchone()['cnt']
        if count > 0:
            return jsonify({'status': 'skipped', 'message': f'Table already has {count} entries'}), 200
        now = _now()
        for e in SEED_WILD_EDIBLES:
            db.execute(
                '''INSERT INTO wild_edibles
                   (common_name, scientific_name, category, edible_parts, season_available,
                    habitat, identification_features, look_alikes, preparation_methods,
                    nutritional_info, medicinal_uses, toxicity_warnings, image_ref,
                    region, confidence_required, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (e['common_name'], e['scientific_name'], e['category'],
                 json.dumps(e['edible_parts']), json.dumps(e['season_available']),
                 e['habitat'], e['identification_features'], e['look_alikes'],
                 json.dumps(e['preparation_methods']), e['nutritional_info'],
                 e['medicinal_uses'], e['toxicity_warnings'], '',
                 e['region'], e['confidence_required'], now, now)
            )
        db.commit()
    log_activity('edibles_seeded', service='hunting_foraging', detail='10 wild edibles seeded')
    return jsonify({'status': 'seeded', 'count': len(SEED_WILD_EDIBLES)}), 201


# ═══════════════════════════════════════════════════════════════════════
# TRADE SKILLS
# ═══════════════════════════════════════════════════════════════════════

SKILL_FIELDS = ['skill_name', 'category', 'practitioner', 'skill_level',
                'tools_required', 'materials_required', 'description',
                'projects_completed', 'last_practiced', 'learning_resources', 'notes']
SKILL_JSON = ['tools_required', 'materials_required']


@hunting_foraging_bp.route('/skills')
def api_skills_list():
    category = request.args.get('category', '').strip()
    with db_session() as db:
        if category:
            rows = db.execute(
                'SELECT * FROM trade_skills WHERE category = ? ORDER BY skill_name',
                (category,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM trade_skills ORDER BY skill_name').fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/skills', methods=['POST'])
def api_skills_create():
    data = request.get_json() or {}
    name = (data.get('skill_name') or '').strip()
    if not name:
        return jsonify({'error': 'skill_name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO trade_skills
               (skill_name, category, practitioner, skill_level, tools_required,
                materials_required, description, projects_completed, last_practiced,
                learning_resources, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('category', 'other'), data.get('practitioner', ''),
             data.get('skill_level', 'beginner'),
             json.dumps(data.get('tools_required', [])),
             json.dumps(data.get('materials_required', [])),
             data.get('description', ''), data.get('projects_completed', 0),
             data.get('last_practiced', ''), data.get('learning_resources', ''),
             data.get('notes', ''), now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM trade_skills WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('skill_created', service='hunting_foraging', detail=f'{name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/skills/<int:sid>')
def api_skills_detail(sid):
    with db_session() as db:
        row = db.execute('SELECT * FROM trade_skills WHERE id = ?', (sid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/skills/<int:sid>', methods=['PUT'])
def api_skills_update(sid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, SKILL_FIELDS, json_fields=SKILL_JSON)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(sid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM trade_skills WHERE id = ?', (sid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE trade_skills SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM trade_skills WHERE id = ?', (sid,)).fetchone()
    log_activity('skill_updated', service='hunting_foraging', detail=f'id={sid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/skills/<int:sid>', methods=['DELETE'])
def api_skills_delete(sid):
    with db_session() as db:
        row = db.execute('SELECT skill_name FROM trade_skills WHERE id = ?', (sid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM trade_projects WHERE skill_id = ?', (sid,))
        db.execute('DELETE FROM trade_skills WHERE id = ?', (sid,))
        db.commit()
    log_activity('skill_deleted', service='hunting_foraging',
                 detail=f'{row["skill_name"]} id={sid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
# TRADE PROJECTS
# ═══════════════════════════════════════════════════════════════════════

PROJECT_FIELDS = ['skill_id', 'name', 'description', 'materials', 'tools', 'steps',
                  'time_hours', 'difficulty', 'output_item', 'output_quantity', 'status',
                  'started_date', 'completed_date', 'notes']
PROJECT_JSON = ['materials', 'tools', 'steps']


@hunting_foraging_bp.route('/projects')
def api_projects_list():
    skill_id = request.args.get('skill_id', '').strip()
    status = request.args.get('status', '').strip()
    with db_session() as db:
        q = 'SELECT * FROM trade_projects WHERE 1=1'
        params = []
        if skill_id:
            q += ' AND skill_id = ?'
            params.append(skill_id)
        if status:
            q += ' AND status = ?'
            params.append(status)
        q += ' ORDER BY id DESC'
        rows = db.execute(q, params).fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/projects', methods=['POST'])
def api_projects_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO trade_projects
               (skill_id, name, description, materials, tools, steps, time_hours,
                difficulty, output_item, output_quantity, status, started_date,
                completed_date, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('skill_id'), name, data.get('description', ''),
             json.dumps(data.get('materials', [])),
             json.dumps(data.get('tools', [])),
             json.dumps(data.get('steps', [])),
             data.get('time_hours', 0), data.get('difficulty', 'beginner'),
             data.get('output_item', ''), data.get('output_quantity', 1),
             data.get('status', 'planned'), data.get('started_date', ''),
             data.get('completed_date', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM trade_projects WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('project_created', service='hunting_foraging', detail=f'{name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/projects/<int:pid>')
def api_projects_detail(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM trade_projects WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/projects/<int:pid>', methods=['PUT'])
def api_projects_update(pid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, PROJECT_FIELDS, json_fields=PROJECT_JSON)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(pid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM trade_projects WHERE id = ?', (pid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE trade_projects SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM trade_projects WHERE id = ?', (pid,)).fetchone()
    log_activity('project_updated', service='hunting_foraging', detail=f'id={pid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/projects/<int:pid>', methods=['DELETE'])
def api_projects_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM trade_projects WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM trade_projects WHERE id = ?', (pid,))
        db.commit()
    log_activity('project_deleted', service='hunting_foraging',
                 detail=f'{row["name"]} id={pid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
# PRESERVATION METHODS
# ═══════════════════════════════════════════════════════════════════════

PRES_FIELDS = ['name', 'method_type', 'input_item', 'output_item', 'equipment_needed',
               'supplies_needed', 'process_steps', 'processing_time_hours', 'shelf_life_days',
               'yield_ratio', 'safety_notes', 'temperature_requirements', 'notes']
PRES_JSON = ['equipment_needed', 'supplies_needed', 'process_steps']


@hunting_foraging_bp.route('/preservation')
def api_preservation_list():
    method_type = request.args.get('type', '').strip()
    with db_session() as db:
        if method_type:
            rows = db.execute(
                'SELECT * FROM preservation_methods WHERE method_type = ? ORDER BY name',
                (method_type,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM preservation_methods ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/preservation', methods=['POST'])
def api_preservation_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO preservation_methods
               (name, method_type, input_item, output_item, equipment_needed,
                supplies_needed, process_steps, processing_time_hours, shelf_life_days,
                yield_ratio, safety_notes, temperature_requirements, notes,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('method_type', ''), data.get('input_item', ''),
             data.get('output_item', ''),
             json.dumps(data.get('equipment_needed', [])),
             json.dumps(data.get('supplies_needed', [])),
             json.dumps(data.get('process_steps', [])),
             data.get('processing_time_hours', 0), data.get('shelf_life_days', 0),
             data.get('yield_ratio', 0), data.get('safety_notes', ''),
             data.get('temperature_requirements', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM preservation_methods WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('preservation_created', service='hunting_foraging', detail=f'{name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/preservation/<int:pid>')
def api_preservation_detail(pid):
    with db_session() as db:
        row = db.execute('SELECT * FROM preservation_methods WHERE id = ?', (pid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/preservation/<int:pid>', methods=['PUT'])
def api_preservation_update(pid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, PRES_FIELDS, json_fields=PRES_JSON)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(pid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM preservation_methods WHERE id = ?', (pid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE preservation_methods SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM preservation_methods WHERE id = ?', (pid,)).fetchone()
    log_activity('preservation_updated', service='hunting_foraging', detail=f'id={pid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/preservation/<int:pid>', methods=['DELETE'])
def api_preservation_delete(pid):
    with db_session() as db:
        row = db.execute('SELECT name FROM preservation_methods WHERE id = ?', (pid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM preservation_batches WHERE method_id = ?', (pid,))
        db.execute('DELETE FROM preservation_methods WHERE id = ?', (pid,))
        db.commit()
    log_activity('preservation_deleted', service='hunting_foraging',
                 detail=f'{row["name"]} id={pid}')
    return jsonify({'deleted': True})


@hunting_foraging_bp.route('/preservation/seed', methods=['POST'])
def api_preservation_seed():
    with db_session() as db:
        count = db.execute('SELECT COUNT(*) as cnt FROM preservation_methods').fetchone()['cnt']
        if count > 0:
            return jsonify({'status': 'skipped',
                            'message': f'Table already has {count} entries'}), 200
        now = _now()
        for m in SEED_PRESERVATION_METHODS:
            db.execute(
                '''INSERT INTO preservation_methods
                   (name, method_type, input_item, output_item, equipment_needed,
                    supplies_needed, process_steps, processing_time_hours, shelf_life_days,
                    yield_ratio, safety_notes, temperature_requirements, notes,
                    created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (m['name'], m['method_type'], m['input_item'], m['output_item'],
                 json.dumps(m['equipment_needed']), json.dumps(m['supplies_needed']),
                 json.dumps(m['process_steps']), m['processing_time_hours'],
                 m['shelf_life_days'], m['yield_ratio'], m['safety_notes'],
                 m['temperature_requirements'], '',
                 now, now)
            )
        db.commit()
    log_activity('preservation_seeded', service='hunting_foraging',
                 detail='8 preservation methods seeded')
    return jsonify({'status': 'seeded', 'count': len(SEED_PRESERVATION_METHODS)}), 201


# ═══════════════════════════════════════════════════════════════════════
# PRESERVATION BATCHES
# ═══════════════════════════════════════════════════════════════════════

BATCH_FIELDS = ['method_id', 'batch_name', 'date_processed', 'input_quantity', 'input_unit',
                'output_quantity', 'output_unit', 'expiration_date', 'storage_location',
                'quality_check', 'processor', 'notes']


@hunting_foraging_bp.route('/batches')
def api_batches_list():
    method_id = request.args.get('method_id', '').strip()
    with db_session() as db:
        if method_id:
            rows = db.execute(
                'SELECT * FROM preservation_batches WHERE method_id = ? ORDER BY id DESC',
                (method_id,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM preservation_batches ORDER BY id DESC').fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/batches', methods=['POST'])
def api_batches_create():
    data = request.get_json() or {}
    batch_name = (data.get('batch_name') or '').strip()
    if not batch_name:
        return jsonify({'error': 'batch_name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO preservation_batches
               (method_id, batch_name, date_processed, input_quantity, input_unit,
                output_quantity, output_unit, expiration_date, storage_location,
                quality_check, processor, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (data.get('method_id'), batch_name,
             data.get('date_processed', now[:10]),
             data.get('input_quantity', 0), data.get('input_unit', ''),
             data.get('output_quantity', 0), data.get('output_unit', ''),
             data.get('expiration_date', ''), data.get('storage_location', ''),
             data.get('quality_check', ''), data.get('processor', ''),
             data.get('notes', ''), now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM preservation_batches WHERE id = ?',
                         (cur.lastrowid,)).fetchone()
    log_activity('batch_created', service='hunting_foraging', detail=f'{batch_name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/batches/<int:bid>')
def api_batches_detail(bid):
    with db_session() as db:
        row = db.execute('SELECT * FROM preservation_batches WHERE id = ?', (bid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/batches/<int:bid>', methods=['PUT'])
def api_batches_update(bid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, BATCH_FIELDS)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(bid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM preservation_batches WHERE id = ?', (bid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE preservation_batches SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM preservation_batches WHERE id = ?', (bid,)).fetchone()
    log_activity('batch_updated', service='hunting_foraging', detail=f'id={bid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/batches/<int:bid>', methods=['DELETE'])
def api_batches_delete(bid):
    with db_session() as db:
        row = db.execute('SELECT batch_name FROM preservation_batches WHERE id = ?',
                         (bid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM preservation_batches WHERE id = ?', (bid,))
        db.commit()
    log_activity('batch_deleted', service='hunting_foraging',
                 detail=f'{row["batch_name"]} id={bid}')
    return jsonify({'deleted': True})


# ═══════════════════════════════════════════════════════════════════════
# HUNTING ZONES
# ═══════════════════════════════════════════════════════════════════════

ZONE_FIELDS = ['name', 'zone_type', 'location', 'gps_bounds', 'terrain',
               'target_species', 'season_dates', 'regulations', 'access_notes',
               'blind_stand_locations', 'trail_cam_locations', 'last_scouted', 'notes']
ZONE_JSON = ['target_species', 'blind_stand_locations', 'trail_cam_locations']


@hunting_foraging_bp.route('/zones')
def api_zones_list():
    zone_type = request.args.get('type', '').strip()
    with db_session() as db:
        if zone_type:
            rows = db.execute(
                'SELECT * FROM hunting_zones WHERE zone_type = ? ORDER BY name',
                (zone_type,)
            ).fetchall()
        else:
            rows = db.execute('SELECT * FROM hunting_zones ORDER BY name').fetchall()
    return jsonify([dict(r) for r in rows])


@hunting_foraging_bp.route('/zones', methods=['POST'])
def api_zones_create():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'name is required'}), 400
    now = _now()
    with db_session() as db:
        cur = db.execute(
            '''INSERT INTO hunting_zones
               (name, zone_type, location, gps_bounds, terrain, target_species,
                season_dates, regulations, access_notes, blind_stand_locations,
                trail_cam_locations, last_scouted, notes, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (name, data.get('zone_type', 'hunting'), data.get('location', ''),
             data.get('gps_bounds', ''), data.get('terrain', ''),
             json.dumps(data.get('target_species', [])),
             data.get('season_dates', ''), data.get('regulations', ''),
             data.get('access_notes', ''),
             json.dumps(data.get('blind_stand_locations', [])),
             json.dumps(data.get('trail_cam_locations', [])),
             data.get('last_scouted', ''), data.get('notes', ''),
             now, now)
        )
        db.commit()
        row = db.execute('SELECT * FROM hunting_zones WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('zone_created', service='hunting_foraging', detail=f'{name}')
    return jsonify(dict(row)), 201


@hunting_foraging_bp.route('/zones/<int:zid>')
def api_zones_detail(zid):
    with db_session() as db:
        row = db.execute('SELECT * FROM hunting_zones WHERE id = ?', (zid,)).fetchone()
    if not row:
        return jsonify({'error': 'not found'}), 404
    return jsonify(dict(row))


@hunting_foraging_bp.route('/zones/<int:zid>', methods=['PUT'])
def api_zones_update(zid):
    data = request.get_json() or {}
    sets, vals = _build_update(data, ZONE_FIELDS, json_fields=ZONE_JSON)
    if not sets:
        return jsonify({'error': 'nothing to update'}), 400
    sets.append('updated_at = ?')
    vals.append(_now())
    vals.append(zid)
    with db_session() as db:
        if not db.execute('SELECT 1 FROM hunting_zones WHERE id = ?', (zid,)).fetchone():
            return jsonify({'error': 'not found'}), 404
        db.execute(f"UPDATE hunting_zones SET {','.join(sets)} WHERE id = ?", vals)
        db.commit()
        row = db.execute('SELECT * FROM hunting_zones WHERE id = ?', (zid,)).fetchone()
    log_activity('zone_updated', service='hunting_foraging', detail=f'id={zid}')
    return jsonify(dict(row))


@hunting_foraging_bp.route('/zones/<int:zid>', methods=['DELETE'])
def api_zones_delete(zid):
    with db_session() as db:
        row = db.execute('SELECT name FROM hunting_zones WHERE id = ?', (zid,)).fetchone()
        if not row:
            return jsonify({'error': 'not found'}), 404
        db.execute('DELETE FROM hunting_zones WHERE id = ?', (zid,))
        db.commit()
    log_activity('zone_deleted', service='hunting_foraging', detail=f'{row["name"]} id={zid}')
    return jsonify({'deleted': True})
