"""Garden & agriculture routes."""

import json
import time

from flask import Blueprint, request, jsonify
from db import db_session, log_activity

garden_bp = Blueprint('garden', __name__)

# USDA hardiness zones by approximate latitude (simplified offline lookup)
HARDINESS_ZONES = [
    (48, '3a', 'Apr 30 - May 15', 'Sep 15 - Sep 30'),
    (45, '4a', 'Apr 20 - May 10', 'Sep 20 - Oct 5'),
    (43, '5a', 'Apr 10 - May 1', 'Oct 1 - Oct 15'),
    (40, '6a', 'Apr 1 - Apr 20', 'Oct 10 - Oct 25'),
    (37, '7a', 'Mar 20 - Apr 10', 'Oct 20 - Nov 5'),
    (34, '8a', 'Mar 10 - Mar 25', 'Nov 1 - Nov 15'),
    (31, '9a', 'Feb 15 - Mar 10', 'Nov 15 - Dec 1'),
    (28, '10a', 'Jan 30 - Feb 15', 'Dec 1 - Dec 15'),
    (25, '11a', 'Year-round', 'Year-round'),
]

SEED_VIABILITY = {
    'onion': 1, 'parsnip': 1, 'parsley': 1, 'leek': 2, 'corn': 2, 'pepper': 2, 'spinach': 2,
    'lettuce': 3, 'pea': 3, 'bean': 3, 'carrot': 3, 'broccoli': 3, 'cauliflower': 3, 'kale': 3,
    'tomato': 4, 'squash': 4, 'pumpkin': 4, 'melon': 4, 'watermelon': 4, 'cucumber': 5,
    'radish': 5, 'beet': 4, 'cabbage': 4, 'turnip': 4, 'eggplant': 4,
}


def _normalize_boundary_geojson(value):
    if value in (None, ''):
        return ''
    if isinstance(value, dict):
        return json.dumps(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return ''
        try:
            parsed = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return ''
        return json.dumps(parsed) if isinstance(parsed, dict) else ''
    return ''


def _safe_plot_geometry(value, lng, lat):
    fallback = {'type': 'Point', 'coordinates': [lng, lat]}
    if value in (None, ''):
        return fallback
    if isinstance(value, dict):
        geometry = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return fallback
        try:
            geometry = json.loads(text)
        except (TypeError, ValueError, json.JSONDecodeError):
            return fallback
    else:
        return fallback
    return geometry if isinstance(geometry, dict) and geometry.get('type') else fallback


@garden_bp.route('/api/garden/zone')
def api_garden_zone():
    lat = request.args.get('lat', type=float)
    if lat is None:
        return jsonify({'zone': 'Unknown', 'last_frost': 'Unknown', 'first_frost': 'Unknown'})
    for min_lat, zone, last_frost, first_frost in HARDINESS_ZONES:
        if lat >= min_lat:
            return jsonify({'zone': zone, 'last_frost': last_frost, 'first_frost': first_frost, 'latitude': lat})
    return jsonify({'zone': '11a+', 'last_frost': 'Year-round', 'first_frost': 'Year-round', 'latitude': lat})


@garden_bp.route('/api/garden/plots')
def api_garden_plots():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM garden_plots ORDER BY name LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@garden_bp.route('/api/garden/plots', methods=['POST'])
def api_garden_plots_create():
    data = request.get_json() or {}
    if not data.get('name'):
        return jsonify({'error': 'Name required'}), 400
    with db_session() as db:
        db.execute('INSERT INTO garden_plots (name, width_ft, length_ft, sun_exposure, soil_type, notes, lat, lng, boundary_geojson) VALUES (?,?,?,?,?,?,?,?,?)',
                   (data['name'], data.get('width_ft', 0), data.get('length_ft', 0),
                    data.get('sun_exposure', 'full'), data.get('soil_type', ''), data.get('notes', ''),
                    data.get('lat'), data.get('lng'), _normalize_boundary_geojson(data.get('boundary_geojson'))))
        db.commit()
    return jsonify({'status': 'created'}), 201


@garden_bp.route('/api/garden/plots/<int:pid>', methods=['PUT'])
def api_garden_plots_update(pid):
    data = request.get_json() or {}
    with db_session() as db:
        fields, vals = [], []
        for k in ('name', 'width_ft', 'length_ft', 'sun_exposure', 'soil_type', 'notes', 'lat', 'lng', 'boundary_geojson'):
            if k in data:
                fields.append(f'{k} = ?')
                vals.append(_normalize_boundary_geojson(data[k]) if k == 'boundary_geojson' else data[k])
        if fields:
            vals.append(pid)
            db.execute(f'UPDATE garden_plots SET {", ".join(fields)} WHERE id = ?', vals)
            db.commit()
    return jsonify({'status': 'updated'})


@garden_bp.route('/api/garden/plots/geo')
def api_garden_plots_geo():
    """Return garden plots as GeoJSON for map overlay."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM garden_plots WHERE lat IS NOT NULL AND lng IS NOT NULL ORDER BY name').fetchall()
    features = []
    for r in rows:
        d = dict(r)
        geometry = _safe_plot_geometry(d.get('boundary_geojson'), d['lng'], d['lat'])
        features.append({
            'type': 'Feature',
            'geometry': geometry,
            'properties': {
                'id': d['id'], 'name': d['name'],
                'width_ft': d.get('width_ft', 0), 'length_ft': d.get('length_ft', 0),
                'sun_exposure': d.get('sun_exposure', ''), 'soil_type': d.get('soil_type', ''),
                'notes': d.get('notes', ''),
            }
        })
    return jsonify({'type': 'FeatureCollection', 'features': features})


@garden_bp.route('/api/garden/plots/<int:pid>', methods=['DELETE'])
def api_garden_plots_delete(pid):
    with db_session() as db:
        r = db.execute('DELETE FROM garden_plots WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@garden_bp.route('/api/garden/seeds')
def api_garden_seeds():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM seeds ORDER BY species LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    result = []
    current_year = int(time.strftime('%Y'))
    for r in rows:
        d = dict(r)
        species_key = r['species'].lower().strip()
        max_years = SEED_VIABILITY.get(species_key, 3)
        if r['year_harvested']:
            age = current_year - r['year_harvested']
            d['viability_pct'] = max(0, min(100, int(100 * (1 - age / (max_years + 1)))))
            d['viable'] = age <= max_years
        else:
            d['viability_pct'] = None
            d['viable'] = None
        result.append(d)
    return jsonify(result)


@garden_bp.route('/api/garden/seeds', methods=['POST'])
def api_garden_seeds_create():
    data = request.get_json() or {}
    if not data.get('species'):
        return jsonify({'error': 'Species required'}), 400
    with db_session() as db:
        db.execute('INSERT INTO seeds (species, variety, quantity, unit, year_harvested, source, days_to_maturity, planting_season, notes) VALUES (?,?,?,?,?,?,?,?,?)',
                   (data['species'], data.get('variety', ''), data.get('quantity', 0), data.get('unit', 'seeds'),
                    data.get('year_harvested'), data.get('source', ''), data.get('days_to_maturity'),
                    data.get('planting_season', 'spring'), data.get('notes', '')))
        db.commit()
    return jsonify({'status': 'created'}), 201


@garden_bp.route('/api/garden/seeds/<int:sid>', methods=['DELETE'])
def api_garden_seeds_delete(sid):
    with db_session() as db:
        r = db.execute('DELETE FROM seeds WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


@garden_bp.route('/api/garden/harvests')
def api_garden_harvests():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT h.*, g.name as plot_name FROM harvest_log h LEFT JOIN garden_plots g ON h.plot_id = g.id ORDER BY h.created_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@garden_bp.route('/api/garden/harvests', methods=['POST'])
def api_garden_harvests_create():
    data = request.get_json() or {}
    if not data.get('crop'):
        return jsonify({'error': 'Crop name required'}), 400
    try:
        qty = max(0, float(data.get('quantity', 0)))
    except (ValueError, TypeError):
        qty = 0
    with db_session() as db:
        db.execute('INSERT INTO harvest_log (crop, quantity, unit, plot_id, notes) VALUES (?,?,?,?,?)',
                   (data['crop'], qty, data.get('unit', 'lbs'),
                    data.get('plot_id'), data.get('notes', '')))
        existing = db.execute('SELECT id, quantity FROM inventory WHERE name = ? AND category = ?', (data['crop'], 'food')).fetchone()
        if existing:
            db.execute('UPDATE inventory SET quantity = quantity + ? WHERE id = ?', (qty, existing['id']))
        else:
            db.execute('INSERT INTO inventory (name, category, quantity, unit) VALUES (?, ?, ?, ?)',
                       (data['crop'], 'food', qty, data.get('unit', 'lbs')))
        db.commit()
    log_activity('harvest_logged', detail=f'{qty} {data.get("unit", "lbs")} of {data["crop"]}')
    return jsonify({'status': 'created', 'inventory_updated': True}), 201


# --- Garden Calendar & Yield Analysis ---

@garden_bp.route('/api/garden/calendar')
def api_garden_calendar():
    """Planting calendar based on configured USDA zone."""
    with db_session() as db:
        zone_row = db.execute("SELECT value FROM settings WHERE key = 'usda_zone'").fetchone()
        zone = zone_row['value'] if zone_row else '7'
        rows = db.execute('SELECT * FROM planting_calendar WHERE zone = ? ORDER BY month, crop', (zone,)).fetchall()
    if not rows:
        _seed_planting_calendar()
        with db_session() as db:
            rows = db.execute('SELECT * FROM planting_calendar WHERE zone = ? ORDER BY month, crop', (zone,)).fetchall()
    return jsonify([dict(r) for r in rows])


def _seed_planting_calendar():
    """Seed zone 7 planting calendar (mid-Atlantic/Southeast US default)."""
    with db_session() as db:
        entries = [
            ('Tomato','7',3,'start_indoor','Start seeds indoors 6-8 weeks before last frost',0.8,80,75),
            ('Tomato','7',5,'transplant','Transplant after last frost',0.8,80,75),
            ('Tomato','7',7,'harvest','Begin harvesting',0.8,80,0),
            ('Pepper','7',3,'start_indoor','Start seeds indoors',0.4,90,80),
            ('Pepper','7',5,'transplant','Transplant after soil warms',0.4,90,80),
            ('Squash','7',5,'direct_sow','Direct sow after frost',0.6,70,55),
            ('Squash','7',7,'harvest','Summer squash harvest begins',0.6,70,0),
            ('Beans','7',4,'direct_sow','Direct sow bush beans',0.5,130,55),
            ('Beans','7',7,'direct_sow','Succession plant for fall',0.5,130,55),
            ('Corn','7',4,'direct_sow','Direct sow when soil > 60F',0.3,365,75),
            ('Lettuce','7',3,'direct_sow','Cool season \u2014 direct sow early',1.0,65,45),
            ('Lettuce','7',9,'direct_sow','Fall planting',1.0,65,45),
            ('Peas','7',2,'direct_sow','Cool season \u2014 plant early',0.3,120,60),
            ('Garlic','7',10,'plant','Plant cloves 2" deep',0.4,600,240),
            ('Onion','7',2,'start_indoor','Start sets indoors',0.5,180,100),
            ('Potato','7',3,'plant','Plant seed potatoes after light frost',1.2,340,90),
            ('Potato','7',7,'harvest','Harvest when tops die back',1.2,340,0),
            ('Carrot','7',3,'direct_sow','Direct sow in loose soil',0.6,190,70),
            ('Carrot','7',8,'direct_sow','Fall crop',0.6,190,70),
            ('Kale','7',3,'direct_sow','Very cold hardy \u2014 early start',0.5,130,55),
            ('Kale','7',8,'direct_sow','Fall/winter crop \u2014 improves with frost',0.5,130,55),
            ('Cabbage','7',3,'start_indoor','Start indoors',0.6,100,80),
            ('Cabbage','7',8,'transplant','Fall crop transplant',0.6,100,80),
            ('Radish','7',3,'direct_sow','Quick crop \u2014 25 days',1.5,66,25),
            ('Radish','7',9,'direct_sow','Fall planting',1.5,66,25),
            ('Sweet Potato','7',5,'plant','Plant slips after warm soil',0.8,390,100),
            ('Turnip','7',3,'direct_sow','Spring crop',0.7,130,50),
            ('Turnip','7',8,'direct_sow','Best as fall crop',0.7,130,50),
            ('Beet','7',3,'direct_sow','Spring planting',0.5,180,55),
            ('Cucumber','7',5,'direct_sow','After last frost',0.6,65,55),
            ('Zucchini','7',5,'direct_sow','Very productive',0.8,80,50),
            ('Watermelon','7',5,'direct_sow','Needs heat and space',0.3,140,85),
        ]
        db.executemany('INSERT OR IGNORE INTO planting_calendar (crop, zone, month, action, notes, yield_per_sqft, calories_per_lb, days_to_harvest) VALUES (?,?,?,?,?,?,?,?)', entries)
        db.commit()


@garden_bp.route('/api/garden/yield-analysis')
def api_garden_yield_analysis():
    """Yield per crop and caloric output analysis."""
    with db_session() as db:
        harvests = db.execute('''SELECT crop, SUM(quantity) as total_lbs, COUNT(*) as harvests,
                                 AVG(yield_per_sqft) as avg_yield
                                 FROM harvest_log GROUP BY crop ORDER BY total_lbs DESC''').fetchall()
        plots = db.execute('SELECT SUM(CASE WHEN width_ft > 0 AND length_ft > 0 THEN width_ft * length_ft ELSE 0 END) as total_sqft FROM garden_plots').fetchone()
        total_sqft = plots['total_sqft'] or 0

        # Caloric analysis from planting calendar
        cal_data = db.execute('SELECT crop, calories_per_lb FROM planting_calendar WHERE calories_per_lb > 0 GROUP BY crop').fetchall()
        cal_map = {r['crop']: r['calories_per_lb'] for r in cal_data}

        result = []
        total_calories = 0
        for h in harvests:
            cal_per_lb = cal_map.get(h['crop'], 200)  # default 200 cal/lb
            total_cal = (h['total_lbs'] or 0) * cal_per_lb
            total_calories += total_cal
            result.append({
                'crop': h['crop'], 'total_lbs': round(h['total_lbs'] or 0, 1),
                'harvests': h['harvests'], 'avg_yield_sqft': round(h['avg_yield'] or 0, 2),
                'calories': round(total_cal),
            })

        # Person-days of food (2000 cal/day)
        person_days = round(total_calories / 2000, 1) if total_calories > 0 else 0

        return jsonify({
            'crops': result, 'total_sqft': round(total_sqft, 1),
            'total_calories': round(total_calories),
            'person_days': person_days,
        })
@garden_bp.route('/api/garden/preservation')
def api_preservation_list():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM preservation_log ORDER BY batch_date DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify([dict(r) for r in rows])


@garden_bp.route('/api/garden/preservation', methods=['POST'])
def api_preservation_create():
    data = request.get_json() or {}
    with db_session() as db:
        db.execute('INSERT INTO preservation_log (crop, method, quantity, unit, batch_date, shelf_life_months, notes) VALUES (?,?,?,?,?,?,?)',
                   (data.get('crop', ''), data.get('method', 'canning'), data.get('quantity', 0),
                    data.get('unit', 'quarts'), data.get('batch_date', ''), data.get('shelf_life_months', 12), data.get('notes', '')))
        db.commit()
    return jsonify({'status': 'created'})


@garden_bp.route('/api/garden/preservation/<int:pid>', methods=['DELETE'])
def api_preservation_delete(pid):
    with db_session() as db:
        r = db.execute('DELETE FROM preservation_log WHERE id = ?', (pid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'status': 'deleted'})


# --- Garden Enhancements (v5.0 Phase 11) ---

@garden_bp.route('/api/garden/companions')
def api_companion_plants():
    """Get companion planting guide."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM companion_plants ORDER BY plant_a LIMIT 10000').fetchall()
        companions = [dict(r) for r in rows]
        if not companions:
            # Seed with common companion planting data
            pairs = [
                ('Tomato', 'Basil', 'companion', 'Basil repels pests and improves tomato flavor'),
                ('Tomato', 'Carrot', 'companion', 'Carrots loosen soil for tomato roots'),
                ('Tomato', 'Fennel', 'antagonist', 'Fennel inhibits tomato growth'),
                ('Corn', 'Bean', 'companion', 'Three Sisters: beans fix nitrogen for corn'),
                ('Corn', 'Squash', 'companion', 'Three Sisters: squash shades soil'),
                ('Bean', 'Onion', 'antagonist', 'Onions inhibit bean growth'),
                ('Carrot', 'Onion', 'companion', 'Onions repel carrot fly'),
                ('Lettuce', 'Radish', 'companion', 'Quick radish harvest makes room'),
                ('Cucumber', 'Dill', 'companion', 'Dill attracts beneficial insects'),
                ('Pepper', 'Basil', 'companion', 'Basil repels aphids and spider mites'),
                ('Potato', 'Horseradish', 'companion', 'Horseradish deters potato beetles'),
                ('Potato', 'Tomato', 'antagonist', 'Both susceptible to blight \u2014 spread disease'),
                ('Cabbage', 'Dill', 'companion', 'Dill attracts wasps that prey on cabbage worms'),
                ('Cabbage', 'Strawberry', 'antagonist', 'Compete for nutrients'),
                ('Garlic', 'Rose', 'companion', 'Garlic repels aphids from roses'),
                ('Marigold', 'Tomato', 'companion', 'Marigolds repel nematodes'),
                ('Sunflower', 'Cucumber', 'companion', 'Sunflowers attract pollinators'),
                ('Pea', 'Carrot', 'companion', 'Peas fix nitrogen for carrots'),
                ('Spinach', 'Strawberry', 'companion', 'Good ground cover pairing'),
                ('Zucchini', 'Nasturtium', 'companion', 'Nasturtiums trap squash bugs'),
            ]
            db.executemany('INSERT INTO companion_plants (plant_a, plant_b, relationship, notes) VALUES (?, ?, ?, ?)', pairs)
            db.commit()
            companions = [{'plant_a': a, 'plant_b': b, 'relationship': rel, 'notes': note} for a, b, rel, note in pairs]
        return jsonify(companions)
@garden_bp.route('/api/garden/planting-calendar')
def api_planting_calendar():
    """Get planting calendar with multi-zone offset support."""
    zone = request.args.get('zone', '7')
    with db_session() as db:
        # Try to fetch data for the exact zone first
        rows = db.execute('SELECT * FROM planting_calendar WHERE zone = ? ORDER BY month, crop', (zone,)).fetchall()
        if rows:
            return jsonify([dict(r) for r in rows])

        # Fall back to zone 7 base data with month offset
        rows = db.execute("SELECT * FROM planting_calendar WHERE zone = '7' ORDER BY month, crop").fetchall()
        results = [dict(r) for r in rows]

        # Apply zone offset: each zone difference from 7 shifts by ~1 month
        base_zone = 7
        try:
            target_zone = int(zone[0]) if zone and zone[0].isdigit() else 7
        except (ValueError, IndexError):
            target_zone = 7
        offset_months = target_zone - base_zone  # Positive = warmer = earlier

        for r in results:
            if r.get('month') is not None:
                new_month = max(1, min(12, r['month'] - offset_months))
                r['month'] = new_month
            r['zone'] = zone  # Label results with requested zone

        return jsonify(results)
@garden_bp.route('/api/garden/seeds/inventory')
def api_seed_inventory():
    """List seed inventory."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM seed_inventory ORDER BY species, variety LIMIT 10000').fetchall()
        return jsonify([dict(r) for r in rows])
@garden_bp.route('/api/garden/seeds/inventory', methods=['POST'])
def api_seed_add():
    """Add seeds to inventory."""
    d = request.json or {}
    with db_session() as db:
        db.execute(
            '''INSERT INTO seed_inventory (species, variety, quantity, unit, viability_pct, year_acquired, source, days_to_maturity, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (d.get('species', ''), d.get('variety', ''), d.get('quantity', 0), d.get('unit', 'seeds'),
             d.get('viability_pct', 90), d.get('year_acquired'), d.get('source', ''),
             d.get('days_to_maturity'), d.get('notes', ''))
        )
        db.commit()
        return jsonify({'status': 'ok'})
@garden_bp.route('/api/garden/seeds/inventory/<int:sid>', methods=['DELETE'])
def api_seed_delete(sid):
    """Delete a seed inventory entry."""
    with db_session() as db:
        r = db.execute('DELETE FROM seed_inventory WHERE id = ?', (sid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
        return jsonify({'status': 'ok'})
@garden_bp.route('/api/garden/pests')
def api_pest_guide():
    """Get pest/disease reference guide."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM pest_guide ORDER BY name LIMIT 10000').fetchall()
        pests = [dict(r) for r in rows]
        if not pests:
            guide = [
                ('Aphids', 'insect', 'Most vegetables, roses', 'Curled leaves, sticky residue, stunted growth', 'Spray with soapy water, neem oil, introduce ladybugs', 'Companion plant with marigolds, avoid over-fertilizing'),
                ('Tomato Hornworm', 'insect', 'Tomatoes, peppers, eggplant', 'Large holes in leaves, stripped stems, dark droppings', 'Hand-pick, BT spray, introduce parasitic wasps', 'Till soil in fall, rotate crops, plant dill to attract wasps'),
                ('Powdery Mildew', 'fungus', 'Squash, cucumber, melon, peas', 'White powdery coating on leaves', 'Baking soda spray (1 tbsp/gal), neem oil, remove affected leaves', 'Space plants for airflow, water at base not leaves, resistant varieties'),
                ('Slugs & Snails', 'mollusk', 'Lettuce, cabbage, strawberries, hostas', 'Irregular holes in leaves, slime trails', 'Beer traps, diatomaceous earth, copper tape around beds', 'Remove hiding spots, water in morning not evening'),
                ('Colorado Potato Beetle', 'insect', 'Potatoes, eggplant, tomatoes', 'Stripped leaves, orange larvae on undersides', 'Hand-pick, neem oil, spinosad spray', 'Rotate crops, mulch with straw, plant resistant varieties'),
                ('Blight (Early/Late)', 'fungus', 'Tomatoes, potatoes', 'Brown spots on leaves, fruit rot, rapid wilting', 'Copper fungicide, remove affected plants immediately', 'Rotate crops 3yr, resistant varieties, avoid overhead watering'),
                ('Cabbage Worm', 'insect', 'Cabbage, broccoli, kale, cauliflower', 'Holes in leaves, green caterpillars, dark droppings', 'BT spray, hand-pick, row covers', 'Plant dill/thyme nearby, use floating row covers from transplant'),
                ('Spider Mites', 'arachnid', 'Beans, tomatoes, strawberries, cucumbers', 'Yellow stippling on leaves, fine webs, leaf drop', 'Strong water spray, neem oil, insecticidal soap', 'Maintain humidity, avoid dusty conditions, introduce predatory mites'),
                ('Root Rot', 'fungus', 'Most plants in poorly drained soil', 'Wilting despite moist soil, yellow leaves, mushy roots', 'Remove affected plants, improve drainage, fungicide drench', 'Ensure good drainage, avoid overwatering, raise beds'),
                ('Japanese Beetle', 'insect', 'Roses, grapes, beans, raspberries', 'Skeletonized leaves (veins intact), damaged flowers', 'Hand-pick into soapy water, neem oil, milky spore for grubs', 'Treat lawn for grubs in fall, avoid traps near garden'),
            ]
            db.executemany('INSERT INTO pest_guide (name, pest_type, affects, symptoms, treatment, prevention) VALUES (?, ?, ?, ?, ?, ?)', guide)
            db.commit()
            pests = [{'name': n, 'pest_type': p, 'affects': a, 'symptoms': s, 'treatment': t, 'prevention': pr}
                     for n, p, a, s, t, pr in guide]
        return jsonify(pests)
# --- Water Tracking ---

@garden_bp.route('/api/garden/water-log', methods=['GET'])
def api_water_log():
    with db_session() as db:
        plot_id = request.args.get('plot_id')
        if plot_id:
            rows = db.execute('SELECT * FROM water_log WHERE plot_id = ? ORDER BY date DESC LIMIT 100', (plot_id,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM water_log ORDER BY date DESC LIMIT 100').fetchall()
        return jsonify([dict(r) for r in rows])
@garden_bp.route('/api/garden/water-log', methods=['POST'])
def api_water_log_create():
    d = request.json or {}
    with db_session() as db:
        cur = db.execute('INSERT INTO water_log (plot_id, source, gallons, date, notes) VALUES (?,?,?,?,?)',
            (d.get('plot_id'), d.get('source', 'manual'), d.get('gallons', 0), d.get('date'), d.get('notes', '')))
        db.commit()
        row = db.execute('SELECT * FROM water_log WHERE id = ?', (cur.lastrowid,)).fetchone()
        return jsonify(dict(row)), 201
@garden_bp.route('/api/garden/water-needs', methods=['GET'])
def api_water_needs():
    """Calculate water needs per plot based on crops and temperature."""
    with db_session() as db:
        plots = db.execute('SELECT * FROM garden_plots LIMIT 500').fetchall()
        results = []
        # Get latest temp from weather
        latest_temp = None
        try:
            w = db.execute('SELECT temp_f FROM weather_log ORDER BY created_at DESC LIMIT 1').fetchone()
            if w:
                latest_temp = w['temp_f']
        except Exception:
            pass

        for p in plots:
            area_sqft = (p['width_ft'] or 1) * (p['length_ft'] or 1)
            # Base: 1 inch/week = 0.623 gal/sq ft/week
            weekly_gal = area_sqft * 0.623
            # Adjust for heat: +25% per 10F above 80
            if latest_temp and latest_temp > 80:
                heat_factor = 1 + ((latest_temp - 80) / 10) * 0.25
                weekly_gal *= heat_factor
            daily_need = round(weekly_gal / 7, 2)

            # Get water applied this week
            applied = db.execute(
                "SELECT COALESCE(SUM(gallons), 0) as total FROM water_log WHERE plot_id = ? AND date >= date('now', '-7 days')",
                (p['id'],)).fetchone()['total']

            weekly_need = round(weekly_gal, 2)
            total_received = round(applied, 2)
            deficit = round(max(0, weekly_need - total_received), 2)

            results.append({
                'plot_id': p['id'], 'plot_name': p['name'],
                'area_sqft': area_sqft, 'daily_need_gal': daily_need,
                'weekly_need_gal': weekly_need, 'water_applied_gal': round(applied, 2),
                'deficit_gal': deficit,
                'status': 'ok' if deficit == 0 else 'needs_water'
            })
        return jsonify(results)
# --- Crop Rotation Planning ---

PLANT_FAMILIES = {
    'Solanaceae': ['tomato', 'pepper', 'eggplant', 'potato'],
    'Brassicaceae': ['cabbage', 'kale', 'broccoli', 'cauliflower', 'brussels sprouts', 'radish'],
    'Cucurbitaceae': ['squash', 'cucumber', 'melon', 'pumpkin', 'zucchini'],
    'Fabaceae': ['beans', 'peas', 'lentils'],
    'Allium': ['onion', 'garlic', 'leek', 'shallot'],
    'Apiaceae': ['carrot', 'celery', 'parsley', 'dill'],
    'Poaceae': ['corn', 'wheat', 'oats'],
}


def _get_plant_family(crop):
    crop_lower = crop.lower()
    for family, crops in PLANT_FAMILIES.items():
        if any(c in crop_lower for c in crops):
            return family
    return 'Other'


@garden_bp.route('/api/garden/plots/<int:pid>/rotation-history', methods=['GET'])
def api_rotation_history(pid):
    with db_session() as db:
        harvests = db.execute(
            'SELECT crop, MIN(created_at) as first, MAX(created_at) as last FROM harvest_log WHERE plot_id = ? GROUP BY crop ORDER BY last DESC',
            (pid,)).fetchall()
        results = []
        for h in harvests:
            results.append({
                'crop': h['crop'], 'family': _get_plant_family(h['crop']),
                'first_planted': h['first'], 'last_harvested': h['last']
            })
        return jsonify(results)
@garden_bp.route('/api/garden/plots/<int:pid>/rotation-suggestions', methods=['GET'])
def api_rotation_suggestions(pid):
    with db_session() as db:
        # Get families planted in this plot in last 3 years
        recent = db.execute(
            "SELECT DISTINCT crop FROM harvest_log WHERE plot_id = ? AND created_at >= datetime('now', '-3 years')",
            (pid,)).fetchall()
        recent_families = set(_get_plant_family(r['crop']) for r in recent)

        # Suggest crops from families NOT recently used
        suggestions = []
        for family, crops in PLANT_FAMILIES.items():
            if family not in recent_families:
                suggestions.append({'family': family, 'suggested_crops': crops})

        warnings = []
        for r in recent:
            family = _get_plant_family(r['crop'])
            if family != 'Other':
                warnings.append(f"Avoid {family} family ({', '.join(PLANT_FAMILIES.get(family, []))}) - planted recently")

        return jsonify({'suggestions': suggestions, 'warnings': warnings})
