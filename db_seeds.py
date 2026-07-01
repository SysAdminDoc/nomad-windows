"""Seed data functions extracted from db.py."""

import logging

_log = logging.getLogger('nomad.db')

__all__ = [
    '_RAG_SCOPE_DEFAULTS',
    '_seed_rag_scope',
    '_seed_upc_database',
    '_seed_freq_database',
    '_seed_companion_plants',
    '_seed_weather_action_rules',
    '_seed_pest_guide',
    '_seed_medicinal_herbs',
    '_seed_planting_calendar',
]


# v7.33.0 — Phase A3: RAG scope manager
#
# Before A3, build_situation_context() in web/blueprints/ai.py hard-coded 10
# tables. Financial, vehicles, loadouts, water, garden, tasks, checklists,
# waypoints and ~80 others were invisible to the LLM. A3 makes the scope
# data-driven: every table the LLM can see lives in rag_scope, with per-table
# enabled/weight/max_rows configurable from Settings.
#
# The 10 pre-existing tables are seeded as builtins with their previous
# behaviour preserved (enabled=1, weight mirrors the old emission order).
# Additional high-value tables are seeded disabled so users opt them in.
# ═══════════════════════════════════════════════════════════════════════════

# (table_name, label, enabled, weight, max_rows, formatter, columns_json)
# weight is the emission order — higher ranks first in the RAG payload.
_RAG_SCOPE_DEFAULTS = [
    # Pre-A3 builtins — order matches the original build_situation_context()
    ('inventory',       'INVENTORY',             1, 100, 10, 'builtin', None),
    ('contacts',        'TEAM CONTACTS',         1,  95, 10, 'builtin', None),
    ('patients',        'PATIENTS',              1,  90, 10, 'builtin', None),
    ('fuel_storage',    'FUEL',                  1,  85, 10, 'builtin', None),
    ('ammo_inventory',  'AMMO',                  1,  80, 10, 'builtin', None),
    ('equipment_log',   'EQUIPMENT',             1,  75, 10, 'builtin', None),
    ('alerts',          'ACTIVE ALERTS',         1,  70, 10, 'builtin', None),
    ('weather_log',     'WEATHER',               1,  65,  1, 'builtin', None),
    ('power_log',       'POWER',                 1,  60,  1, 'builtin', None),
    ('incidents',       'RECENT INCIDENTS (24h)',1,  55,  5, 'builtin', None),
    # High-value tables seeded disabled; user opts in via Settings
    ('scheduled_tasks', 'SCHEDULED TASKS',       0,  50, 10, 'generic',
        '["title","due_date","priority","category","status"]'),
    ('checklists',      'CHECKLISTS',            0,  48, 10, 'generic',
        '["name","category","completed"]'),
    ('waypoints',       'WAYPOINTS',             0,  46, 15, 'generic',
        '["name","category","lat","lng","elevation"]'),
    ('vehicles',        'VEHICLES',              0,  44, 10, 'generic',
        '["name","make","model","year","fuel_type","tank_gal","mpg","status"]'),
    ('loadouts',        'LOADOUTS',              0,  42, 10, 'generic',
        '["name","type","person_id","last_inspected"]'),
    ('water_storage',   'WATER STORAGE',         0,  40, 10, 'generic',
        '["container","capacity_gal","fill_date","treatment_method","location"]'),
    ('garden_plots',    'GARDEN PLOTS',          0,  38, 10, 'generic',
        '["name","crop","planted_date","harvest_date","status"]'),
    ('livestock',       'LIVESTOCK',             0,  36, 10, 'generic',
        '["name","species","breed","birth_date","status"]'),
    ('financial_reserves','FINANCIAL RESERVES',  0,  34, 10, 'generic',
        '["type","denomination","amount","location","value_estimate"]'),
    ('preservation_batches','PRESERVATION',      0,  32, 10, 'generic',
        '["method","contents","date","quantity","status"]'),
    ('evacuation_plans','EVAC PLANS',            0,  30, 10, 'generic',
        '["name","tier","is_active"]'),
    ('watch_schedules', 'WATCH SCHEDULE',        0,  28, 10, 'generic',
        '["name","start_time","end_time","assigned_to"]'),
    ('family_checkins', 'FAMILY CHECK-INS',      0,  26, 10, 'generic',
        '["member_name","status","last_contact"]'),
    ('comms_log',       'COMMS LOG',             0,  24, 15, 'generic',
        '["from_callsign","to_callsign","frequency","timestamp","message"]'),
    ('skills',          'SKILLS',                0,  22, 20, 'generic',
        '["name","proficiency","person","last_practiced"]'),
]


def _seed_rag_scope(conn):
    """Idempotent seed — INSERT OR IGNORE preserves user-edited rows.
    New defaults added in later releases land on upgrade automatically."""
    rows = [
        (table_name, label, enabled, weight, max_rows, formatter, columns_json, 'builtin')
        for (table_name, label, enabled, weight, max_rows, formatter, columns_json)
        in _RAG_SCOPE_DEFAULTS
    ]
    conn.executemany(
        '''INSERT OR IGNORE INTO rag_scope
           (table_name, label, enabled, weight, max_rows, formatter, columns_json, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
        rows,
    )
    conn.commit()


def _seed_upc_database(conn):
    """Seed the UPC database with common survival/prep items if empty."""
    count = conn.execute('SELECT COUNT(*) FROM upc_database').fetchone()[0]
    if count > 0:
        return  # Already seeded

    # (upc, name, category, brand, size, unit, default_shelf_life_days)
    items = [
        # ─── Food (27 items) ───
        ('041331024266', 'Black Beans (canned)', 'Food', 'Bush\'s', '15 oz', 'can', 1825),
        ('041331025744', 'Pinto Beans (canned)', 'Food', 'Bush\'s', '15 oz', 'can', 1825),
        ('080000525734', 'Chunk Light Tuna', 'Food', 'Bumble Bee', '5 oz', 'can', 1825),
        ('017400100083', 'Long Grain White Rice', 'Food', 'Riceland', '2 lb', 'bag', 3650),
        ('017400100106', 'Long Grain White Rice', 'Food', 'Riceland', '5 lb', 'bag', 3650),
        ('076808006131', 'Spaghetti Pasta', 'Food', 'Barilla', '16 oz', 'box', 1095),
        ('051500255162', 'Creamy Peanut Butter', 'Food', 'Jif', '16 oz', 'jar', 730),
        ('030000065730', 'Old Fashioned Oats', 'Food', 'Quaker', '42 oz', 'canister', 730),
        ('024300061363', 'Pure Honey', 'Food', 'Sue Bee', '16 oz', 'bottle', 36500),
        ('050000340712', 'Instant Nonfat Dry Milk', 'Food', 'Carnation', '9.6 oz', 'box', 1095),
        ('021130126026', 'MRE Meal Ready to Eat', 'Food', 'Sopakco', '1 meal', 'each', 1825),
        ('020000124407', 'Sweet Peas (canned)', 'Food', 'Del Monte', '15 oz', 'can', 1825),
        ('024000163695', 'Fruit Cocktail (canned)', 'Food', 'Del Monte', '15 oz', 'can', 1825),
        ('044000003319', 'Original Beef Jerky', 'Food', 'Jack Link\'s', '2.85 oz', 'bag', 365),
        ('041789002113', 'Ramen Noodle Soup - Chicken', 'Food', 'Maruchan', '3 oz', 'pack', 365),
        ('051000025111', 'Condensed Chicken Noodle Soup', 'Food', 'Campbell\'s', '10.75 oz', 'can', 1825),
        ('041129070574', 'Extra Virgin Olive Oil', 'Food', 'Bertolli', '17 oz', 'bottle', 730),
        ('024600010603', 'Iodized Salt', 'Food', 'Morton', '26 oz', 'canister', 36500),
        ('049800110069', 'Granulated White Sugar', 'Food', 'Domino', '4 lb', 'bag', 36500),
        ('051500280058', 'All Purpose Flour', 'Food', 'Pillsbury', '5 lb', 'bag', 365),
        ('071524017126', 'Great Northern Beans (dried)', 'Food', 'Goya', '1 lb', 'bag', 3650),
        ('054100003324', 'Chunk Chicken Breast', 'Food', 'Hormel', '10 oz', 'can', 1825),
        ('037600215114', 'Spam Classic', 'Food', 'Spam', '12 oz', 'can', 1825),
        ('016000264601', 'Nature Valley Oats \'N Honey Granola Bars', 'Food', 'Nature Valley', '12 ct', 'box', 365),
        ('021000658756', 'Kraft Mac & Cheese Original', 'Food', 'Kraft', '7.25 oz', 'box', 730),
        ('020000122540', 'Whole Kernel Corn (canned)', 'Food', 'Green Giant', '15.25 oz', 'can', 1825),
        ('020000124674', 'Diced Tomatoes (canned)', 'Food', 'Hunt\'s', '14.5 oz', 'can', 1825),

        # ─── Water (8 items) ───
        ('012000001024', 'Purified Drinking Water', 'Water', 'Aquafina', '16.9 oz', 'bottle', 730),
        ('049000028904', 'Purified Water', 'Water', 'Dasani', '16.9 oz', 'bottle', 730),
        ('078742225654', 'Spring Water Gallon Jug', 'Water', 'Great Value', '1 gal', 'jug', 730),
        ('855801005048', 'LifeStraw Personal Water Filter', 'Water', 'LifeStraw', '1 unit', 'each', 1825),
        ('891274000103', 'Water Purification Tablets', 'Water', 'Potable Aqua', '50 ct', 'bottle', 1460),
        ('050716002041', 'Sawyer Mini Water Filter', 'Water', 'Sawyer', '1 unit', 'each', 3650),
        ('044600010281', 'Regular Bleach (purification)', 'Water', 'Clorox', '64 oz', 'bottle', 365),
        ('071254002019', 'WaterBOB Emergency Water Storage', 'Water', 'WaterBOB', '100 gal', 'each', 3650),

        # ─── Medical (15 items) ───
        ('381370044314', 'Adhesive Bandages Assorted', 'Medical', 'Band-Aid', '100 ct', 'box', 1825),
        ('191565880708', 'Sterile Gauze Pads 4x4', 'Medical', 'Dynarex', '25 ct', 'box', 1825),
        ('381370048060', 'Waterproof Medical Tape', 'Medical', 'Johnson & Johnson', '1 in x 10 yd', 'roll', 1825),
        ('305730169301', 'Ibuprofen 200mg Tablets', 'Medical', 'Advil', '200 ct', 'bottle', 1095),
        ('300450449108', 'Acetaminophen 500mg Extra Strength', 'Medical', 'Tylenol', '100 ct', 'bottle', 1095),
        ('312547781183', 'Triple Antibiotic Ointment', 'Medical', 'Neosporin', '1 oz', 'tube', 1095),
        ('305210016323', 'Hydrogen Peroxide 3%', 'Medical', 'Equate', '32 oz', 'bottle', 1095),
        ('305212530161', '91% Isopropyl Alcohol', 'Medical', 'Equate', '32 oz', 'bottle', 1095),
        ('819731011037', 'CAT Tourniquet Gen 7', 'Medical', 'NAR', '1 unit', 'each', 1825),
        ('819731010078', 'HyFin Vent Chest Seal Twin Pack', 'Medical', 'NAR', '2 ct', 'pack', 1825),
        ('819731010481', 'SAM Splint 36 inch', 'Medical', 'SAM Medical', '1 unit', 'each', 3650),
        ('034197002059', 'Moleskin Plus Padding', 'Medical', 'Dr. Scholl\'s', '3 ct', 'pack', 1825),
        ('816140010838', 'Oral Rehydration Salts', 'Medical', 'DripDrop', '8 ct', 'box', 730),
        ('300450170125', 'Benadryl Allergy 25mg', 'Medical', 'Benadryl', '100 ct', 'bottle', 1095),
        ('041167100103', 'Imodium A-D Anti-Diarrheal', 'Medical', 'Imodium', '24 ct', 'box', 1095),

        # ─── Batteries/Power (8 items) ───
        ('041333030012', 'AA Batteries (Duracell)', 'Batteries/Power', 'Duracell', '20 pk', 'pack', 3650),
        ('039800011329', 'AA Batteries (Energizer)', 'Batteries/Power', 'Energizer', '20 pk', 'pack', 3650),
        ('041333044002', 'AAA Batteries (Duracell)', 'Batteries/Power', 'Duracell', '16 pk', 'pack', 3650),
        ('041333000060', 'D Cell Batteries (Duracell)', 'Batteries/Power', 'Duracell', '4 pk', 'pack', 3650),
        ('041333016016', '9V Battery (Duracell)', 'Batteries/Power', 'Duracell', '2 pk', 'pack', 3650),
        ('039800040985', 'CR123A Lithium Battery', 'Batteries/Power', 'Energizer', '2 pk', 'pack', 3650),
        ('708431100251', '18650 Rechargeable Battery 3500mAh', 'Batteries/Power', 'Panasonic', '2 pk', 'pack', 1825),
        ('840101202015', 'USB Power Bank 20000mAh', 'Batteries/Power', 'Anker', '1 unit', 'each', 1825),

        # ─── Gear (10 items) ───
        ('024099002318', '550 Paracord 100ft', 'Gear', 'Paracord Planet', '100 ft', 'hank', 3650),
        ('075353091012', 'Duct Tape Heavy Duty', 'Gear', '3M', '1.88 in x 60 yd', 'roll', 3650),
        ('078628080056', 'Cable Ties 8 inch (100 ct)', 'Gear', 'Gardner Bender', '100 ct', 'bag', 3650),
        ('044600315409', 'Strike Anywhere Matches', 'Gear', 'Diamond', '250 ct', 'box', 3650),
        ('070330624115', 'BIC Classic Lighter', 'Gear', 'BIC', '1 unit', 'each', 3650),
        ('783583961554', 'Ferro Rod Fire Starter', 'Gear', 'bayite', '6 in', 'each', 36500),
        ('816511010009', 'Heavy Duty Tarp 8x10', 'Gear', 'Everbilt', '8 x 10 ft', 'each', 1825),
        ('091444200203', 'Emergency Mylar Blanket', 'Gear', 'Swiss Safe', '2 pk', 'pack', 3650),
        ('079340687042', 'Glow Sticks 12 hr (12 pk)', 'Gear', 'Cyalume', '12 ct', 'pack', 1460),
        ('013700835414', 'Contractor Trash Bags 42 gal', 'Gear', 'Glad', '20 ct', 'box', 3650),

        # ─── Hygiene (8 items) ───
        ('037000388876', 'Ivory Bar Soap', 'Hygiene', 'Ivory', '10 pk', 'pack', 1095),
        ('037000449652', 'Crest Cavity Protection Toothpaste', 'Hygiene', 'Crest', '5.7 oz', 'tube', 730),
        ('021130235018', 'Hand Sanitizer 8 oz', 'Hygiene', 'Purell', '8 oz', 'bottle', 1095),
        ('037000862376', 'Charmin Toilet Paper', 'Hygiene', 'Charmin', '12 mega rolls', 'pack', 3650),
        ('036000431063', 'Huggies Simply Clean Wipes', 'Hygiene', 'Huggies', '64 ct', 'pack', 730),
        ('036000196207', 'U by Kotex Security Maxi Pads', 'Hygiene', 'Kotex', '36 ct', 'box', 1825),
        ('044600010502', 'Clorox Disinfecting Bleach', 'Hygiene', 'Clorox', '81 oz', 'bottle', 365),
        ('013700835216', 'ForceFlex Tall Kitchen Trash Bags', 'Hygiene', 'Glad', '80 ct', 'box', 3650),
    ]

    for upc, name, category, brand, size, unit, shelf_life in items:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO upc_database (upc, name, category, brand, size, unit, default_shelf_life_days) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (upc, name, category, brand, size, unit, shelf_life)
            )
        except Exception:
            pass
    conn.commit()
    _log.info(f'Seeded UPC database with {len(items)} items')


# ─── Content-Expansion Seeds (CE-tier 1, v7.60) ──────────────────────
# Reference data lives in ``seeds/*.py`` modules so db.py doesn't balloon.
# Each seeder is idempotent — INSERT OR IGNORE + COUNT-based early exit.

def _seed_freq_database(conn):
    """Seed freq_database with ~70 canonical field frequencies (CE-05)."""
    count = conn.execute('SELECT COUNT(*) FROM freq_database').fetchone()[0]
    if count > 0:
        return
    try:
        from seeds.frequencies import FREQUENCIES
    except Exception as e:
        _log.warning('Frequency seed module unavailable — skipping: %s', e)
        return
    for row in FREQUENCIES:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO freq_database '
                '(frequency, mode, bandwidth, service, description, region, '
                'license_required, priority, notes) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)',
                row,
            )
        except Exception as exc:
            _log.debug('freq_database seed row skipped (%s): %s', row[0], exc)
    conn.commit()
    _log.info('Seeded freq_database with %d frequencies', len(FREQUENCIES))


def _seed_companion_plants(conn):
    """Seed companion_plants with ~100 directed pairs (CE-02)."""
    count = conn.execute('SELECT COUNT(*) FROM companion_plants').fetchone()[0]
    if count > 0:
        return
    try:
        from seeds.companion_plants import COMPANION_PLANTS
    except Exception as e:
        _log.warning('Companion-plants seed module unavailable — skipping: %s', e)
        return
    for row in COMPANION_PLANTS:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO companion_plants '
                '(plant_a, plant_b, relationship, notes) VALUES (?, ?, ?, ?)',
                row,
            )
        except Exception as exc:
            _log.debug('companion_plants seed row skipped (%s↔%s): %s',
                       row[0], row[1], exc)
    conn.commit()
    _log.info('Seeded companion_plants with %d pairs', len(COMPANION_PLANTS))


def _seed_weather_action_rules(conn):
    """Seed weather_action_rules with 15 default thresholds (CE-07)."""
    count = conn.execute(
        'SELECT COUNT(*) FROM weather_action_rules'
    ).fetchone()[0]
    if count > 0:
        return
    try:
        from seeds.weather_action_rules import rules_for_insert
    except Exception as e:
        _log.warning('Weather-rule seed module unavailable — skipping: %s', e)
        return
    rows = rules_for_insert()
    for row in rows:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO weather_action_rules '
                '(name, condition_type, threshold, comparison, action_type, '
                'action_data, enabled, cooldown_minutes) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                row,
            )
        except Exception as exc:
            _log.debug('weather_action_rules seed row skipped (%s): %s',
                       row[0], exc)
    conn.commit()
    _log.info('Seeded weather_action_rules with %d templates', len(rows))


def _seed_pest_guide(conn):
    """Seed pest_guide with ~40 pests + diseases + disorders (CE-16)."""
    count = conn.execute('SELECT COUNT(*) FROM pest_guide').fetchone()[0]
    if count > 0:
        return
    try:
        from seeds.pest_guide import PESTS
    except Exception as e:
        _log.warning('Pest-guide seed module unavailable — skipping: %s', e)
        return
    for row in PESTS:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO pest_guide '
                '(name, pest_type, affects, symptoms, treatment, prevention, '
                'image_url) VALUES (?, ?, ?, ?, ?, ?, ?)',
                row,
            )
        except Exception as exc:
            _log.debug('pest_guide seed row skipped (%s): %s', row[0], exc)
    conn.commit()
    _log.info('Seeded pest_guide with %d entries', len(PESTS))


def _seed_medicinal_herbs(conn):
    """Seed herbal_remedies with 50 common herbs (CE-15, v7.62).

    Pulls from both the inline BUILTIN_HERBS (original 10) and the
    seeds.medicinal_herbs.HERBS module (40 more), deduplicated by name.
    Idempotent: skip-if-name-already-exists rather than INSERT OR IGNORE,
    because herbal_remedies has no UNIQUE(name) constraint (user-added
    herbs allowed to share names).
    """
    # If there are already built-in herbs seeded, assume prior seeding.
    count = conn.execute(
        "SELECT COUNT(*) FROM herbal_remedies WHERE is_builtin = 1"
    ).fetchone()[0]
    if count >= 40:
        return
    combined = []
    seen = set()
    try:
        from web.blueprints.medical_phase2 import BUILTIN_HERBS
        for row in BUILTIN_HERBS:
            if row[0] not in seen:
                combined.append(row)
                seen.add(row[0])
    except Exception as e:
        _log.warning('Inline BUILTIN_HERBS unavailable — skipping: %s', e)
    try:
        from seeds.medicinal_herbs import HERBS as _SEED_HERBS
        for row in _SEED_HERBS:
            if row[0] not in seen:
                combined.append(row)
                seen.add(row[0])
    except Exception as e:
        _log.warning('Medicinal-herbs seed module unavailable: %s', e)

    if not combined:
        return

    inserted = 0
    for (name, common, uses, prep, dose, contra, season, habitat) in combined:
        existing = conn.execute(
            'SELECT id FROM herbal_remedies WHERE name = ? AND is_builtin = 1',
            (name,),
        ).fetchone()
        if existing:
            continue
        try:
            conn.execute(
                'INSERT INTO herbal_remedies '
                '(name, common_names, uses, preparation, dosage, '
                'contraindications, season, habitat, is_builtin) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)',
                (name, common, uses, prep, dose, contra, season, habitat),
            )
            inserted += 1
        except Exception as exc:
            _log.debug('herbal_remedies seed row skipped (%s): %s', name, exc)
    conn.commit()
    _log.info('Seeded herbal_remedies with %d entries (total %d built-in)',
              inserted, len(combined))


def _seed_planting_calendar(conn):
    """Seed planting_calendar — 45 crops × 8 USDA zones (CE-01)."""
    count = conn.execute(
        'SELECT COUNT(*) FROM planting_calendar'
    ).fetchone()[0]
    if count > 0:
        return
    try:
        from seeds.planting_calendar import planting_rows
    except Exception as e:
        _log.warning('Planting-calendar seed module unavailable — skipping: %s', e)
        return
    inserted = 0
    for row in planting_rows():
        try:
            conn.execute(
                'INSERT OR IGNORE INTO planting_calendar '
                '(crop, zone, month, action, notes, yield_per_sqft, '
                'calories_per_lb, days_to_harvest) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                row,
            )
            inserted += 1
        except Exception as exc:
            _log.debug('planting_calendar seed row skipped (%s z%s m%s): %s',
                       row[0], row[1], row[2], exc)
    conn.commit()
    _log.info('Seeded planting_calendar with %d rows', inserted)
