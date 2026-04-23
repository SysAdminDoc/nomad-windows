"""Content-expansion seed tests — CE-02 / CE-06 / CE-07 / CE-16.

Each seed module in ``seeds/`` pairs with a ``_seed_*`` function in
``db.py``. These tests make sure:

1. ``init_db()`` runs the seeder (data lands in a fresh in-memory DB).
2. The seeder is idempotent — running it a second time doesn't duplicate.
3. The data has the expected structure (no NULLs in required columns).
4. The Python-only ``APPLIANCE_WATTAGE`` reference loads and the
   ``/api/power/appliance-wattage`` route returns the expected shape.

``freq_database`` (CE-05) is covered separately by ``test_radio.py`` —
it's lazy-seeded on first GET of ``/api/comms/frequencies`` by the
existing ``web.blueprints.comms._seed_frequencies()`` (~340 entries).
"""

from __future__ import annotations


class TestCompanionPlantsSeed:
    """CE-02: Companion + antagonist pairs."""

    def test_seed_populates_companion_plants(self, db):
        count = db.execute(
            'SELECT COUNT(*) FROM companion_plants'
        ).fetchone()[0]
        assert count >= 60

    def test_three_sisters_present(self, db):
        for a, b in [('Corn', 'Beans'), ('Corn', 'Squash'), ('Beans', 'Squash')]:
            row = db.execute(
                'SELECT relationship FROM companion_plants '
                'WHERE plant_a = ? AND plant_b = ?',
                (a, b),
            ).fetchone()
            assert row is not None, f'Missing Three Sisters pair: {a} ↔ {b}'
            assert row['relationship'] == 'companion'

    def test_universal_antagonist_fennel(self, db):
        row = db.execute(
            'SELECT relationship FROM companion_plants '
            "WHERE plant_a = 'Fennel' AND plant_b = 'All'"
        ).fetchone()
        assert row is not None, (
            "Fennel needs to be flagged as universal antagonist — it's the "
            "canonical 'never interplant' case in every companion-planting "
            "reference."
        )
        assert row['relationship'] == 'antagonist'

    def test_known_antagonism_tomato_brassica(self, db):
        row = db.execute(
            'SELECT relationship FROM companion_plants '
            "WHERE plant_a = 'Tomato' AND plant_b = 'Brassicas'"
        ).fetchone()
        assert row is not None
        assert row['relationship'] == 'antagonist'


class TestWeatherActionRulesSeed:
    """CE-07: Weather-triggered alert templates."""

    def test_seed_populates_rules(self, db):
        count = db.execute(
            'SELECT COUNT(*) FROM weather_action_rules'
        ).fetchone()[0]
        assert count >= 10

    def test_freeze_rule_threshold(self, db):
        row = db.execute(
            "SELECT threshold, comparison FROM weather_action_rules "
            "WHERE condition_type = 'temperature_below' AND threshold = 32"
        ).fetchone()
        assert row is not None, 'Missing 32°F freeze rule'
        assert row['comparison'] == 'lt'

    def test_action_data_is_valid_json(self, db):
        import json
        rows = db.execute(
            'SELECT name, action_data FROM weather_action_rules'
        ).fetchall()
        for r in rows:
            try:
                parsed = json.loads(r['action_data'])
            except ValueError as e:
                raise AssertionError(
                    f'Rule {r["name"]!r} has invalid action_data JSON: {e}'
                )
            assert 'severity' in parsed, f'{r["name"]!r} missing severity'
            assert 'message' in parsed, f'{r["name"]!r} missing message'


class TestPestGuideSeed:
    """CE-16: Garden pest / disease reference."""

    def test_seed_populates_pest_guide(self, db):
        count = db.execute('SELECT COUNT(*) FROM pest_guide').fetchone()[0]
        assert count >= 30

    def test_includes_core_pests(self, db):
        for name in [
            'Aphid', 'Cabbage White Butterfly / Cabbage Worm', 'Tomato Hornworm',
            'Squash Vine Borer', 'Colorado Potato Beetle', 'Japanese Beetle',
            'Late Blight (Phytophthora)', 'Powdery Mildew', 'Blossom-End Rot',
            'Deer',
        ]:
            row = db.execute(
                'SELECT pest_type, treatment FROM pest_guide WHERE name = ?',
                (name,),
            ).fetchone()
            assert row is not None, f'Missing pest_guide entry: {name}'
            assert row['treatment'], f'{name} has empty treatment field'

    def test_pest_types_are_sensible(self, db):
        rows = db.execute(
            'SELECT DISTINCT pest_type FROM pest_guide'
        ).fetchall()
        allowed = {'insect', 'mollusk', 'nematode', 'disease', 'vertebrate',
                   'disorder'}
        types = {r['pest_type'] for r in rows}
        bad = types - allowed
        assert not bad, f'Unknown pest_type values: {bad}'


class TestApplianceWattageReference:
    """CE-06: Static appliance-wattage lookup (no DB table)."""

    def test_module_loads_and_has_entries(self):
        from seeds.appliance_wattage import APPLIANCE_WATTAGE
        assert len(APPLIANCE_WATTAGE) >= 70
        # Each row has the expected 6-tuple shape.
        for row in APPLIANCE_WATTAGE:
            assert len(row) == 6, f'Bad row shape: {row}'
            name, cat, run_w, surge_w, hours, notes = row
            assert name and isinstance(name, str)
            assert cat and isinstance(cat, str)
            assert isinstance(run_w, int) and run_w >= 0
            assert surge_w is None or isinstance(surge_w, int)
            assert isinstance(hours, (int, float)) and hours >= 0

    def test_api_route_returns_items_and_categories(self, client):
        resp = client.get('/api/power/appliance-wattage')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] >= 70
        assert len(data['items']) == data['count']
        # Category list is unique and preserves first-seen order.
        assert len(data['categories']) == len(set(data['categories']))
        # First item carries required keys.
        first = data['items'][0]
        for key in ('name', 'category', 'running_watts',
                    'surge_watts', 'typical_hours_per_day', 'notes'):
            assert key in first, f'Missing key in item payload: {key}'

    def test_api_includes_canonical_loads(self, client):
        data = client.get('/api/power/appliance-wattage').get_json()
        names = {it['name'] for it in data['items']}
        for required in [
            'Refrigerator (20 cu ft, Energy Star)',
            'Well pump (1/2 HP submersible)',
            'CPAP (no humidifier / no heat)',
            'LED bulb 60 W equivalent',
            'Router / modem / switch',
        ]:
            assert required in names, f'Missing canonical load: {required}'


class TestPlantingCalendarSeed:
    """CE-01: USDA-zone planting calendar (45 crops × 8 zones)."""

    def test_seed_populates_rows(self, db):
        count = db.execute(
            'SELECT COUNT(*) FROM planting_calendar'
        ).fetchone()[0]
        # With zone skips (min_zone gating) + offset skips (month < 1 drops)
        # we expect substantially more than 500 rows.
        assert count >= 500, (
            f'planting_calendar under-seeded (got {count}). Expected ~1000.'
        )

    def test_all_expected_zones_present(self, db):
        zones = {
            r['zone']
            for r in db.execute(
                'SELECT DISTINCT zone FROM planting_calendar'
            ).fetchall()
        }
        for z in ('3', '4', '5', '6', '7', '8', '9', '10'):
            assert z in zones, f'Zone {z} missing from planting_calendar'

    def test_action_vocabulary_is_limited(self, db):
        actions = {
            r['action']
            for r in db.execute(
                'SELECT DISTINCT action FROM planting_calendar'
            ).fetchall()
        }
        allowed = {'start_indoor', 'transplant', 'direct_sow', 'harvest'}
        bad = actions - allowed
        assert not bad, f'Unexpected action values: {bad}'

    def test_long_season_crops_excluded_from_cold_zones(self, db):
        """Sweet Potato is min_zone=6 — must not appear in zones 3/4/5."""
        rows = db.execute(
            "SELECT zone FROM planting_calendar WHERE crop = 'Sweet Potato'"
        ).fetchall()
        cold = [r['zone'] for r in rows if r['zone'] in ('3', '4', '5')]
        assert not cold, f'Sweet Potato leaked into cold zones: {cold}'

    def test_cold_hardy_crops_in_all_zones(self, db):
        """Kale is cold-hardy (min_zone=3) — should appear in every zone."""
        zones = {
            r['zone']
            for r in db.execute(
                "SELECT DISTINCT zone FROM planting_calendar WHERE crop = 'Kale'"
            ).fetchall()
        }
        for z in ('3', '5', '7', '10'):
            assert z in zones, f'Kale missing from zone {z}'

    def test_months_in_valid_range(self, db):
        """All month values must be 1-12."""
        rows = db.execute(
            'SELECT month FROM planting_calendar WHERE month < 1 OR month > 12'
        ).fetchall()
        assert not rows, f'Found {len(rows)} rows with invalid months'

    def test_yield_and_calorie_data_present(self, db):
        """Every crop must have positive yield + calorie metadata."""
        bad = db.execute(
            'SELECT DISTINCT crop FROM planting_calendar '
            'WHERE yield_per_sqft <= 0 OR calories_per_lb <= 0 '
            'OR days_to_harvest <= 0'
        ).fetchall()
        assert not bad, f'Crops with missing yield/calorie/DTH: {[r["crop"] for r in bad]}'

    def test_zone_shift_is_correct_direction(self, db):
        """Zone 3 should plant tomato LATER than zone 9 (colder = later)."""
        z3 = db.execute(
            "SELECT MIN(month) FROM planting_calendar "
            "WHERE crop = 'Tomato' AND zone = '3' AND action = 'transplant'"
        ).fetchone()[0]
        z9 = db.execute(
            "SELECT MIN(month) FROM planting_calendar "
            "WHERE crop = 'Tomato' AND zone = '9' AND action = 'transplant'"
        ).fetchone()[0]
        assert z3 is not None and z9 is not None, (
            'Tomato transplant rows missing from zones 3 or 9'
        )
        assert z3 > z9, (
            f'Zone 3 tomato transplant month ({z3}) should be LATER than '
            f'zone 9 ({z9}) — offset logic inverted?'
        )


class TestRadioReference:
    """CE-14: Static phonetic / Morse / proword / digital-mode reference."""

    def test_bundle_route_shape(self, client):
        resp = client.get('/api/radio/reference')
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ('phonetic', 'morse', 'prowords', 'rst', 'q_codes',
                    'digital_modes', 'hf_band_plan_us_general'):
            assert key in data, f'Missing key in reference bundle: {key}'

    def test_phonetic_nato_full_alphabet(self, client):
        data = client.get('/api/radio/phonetic').get_json()
        nato = data['nato']
        for ch in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
            assert ch in nato, f'NATO phonetic missing {ch}'
        assert nato['A'] == 'Alfa'  # ITU spelling ≠ "Alpha"
        assert nato['J'] == 'Juliett'  # two T's — ITU spelling
        assert nato['X'] == 'X-ray'

    def test_phonetic_has_digits(self, client):
        data = client.get('/api/radio/phonetic').get_json()
        for d in '0123456789':
            assert d in data['nato'], f'NATO phonetic missing digit {d}'

    def test_morse_translator_basic(self, client):
        resp = client.get('/api/radio/morse/SOS')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['morse'].strip() == '... --- ...'

    def test_morse_translator_with_spaces(self, client):
        resp = client.get('/api/radio/morse/HI MOM')
        data = resp.get_json()
        # Words separated by " / ", letters by " "
        assert '/' in data['morse']

    def test_morse_translator_rejects_long_input(self, client):
        resp = client.get('/api/radio/morse/' + 'A' * 600)
        assert resp.status_code == 400

    def test_prowords_include_core_vocabulary(self, client):
        data = client.get('/api/radio/reference').get_json()
        prowords = {p['proword'] for p in data['prowords']}
        for required in ['ROGER', 'WILCO', 'OVER', 'OUT', 'BREAK',
                         'SAY AGAIN', 'MAYDAY', 'AFFIRMATIVE', 'NEGATIVE']:
            assert required in prowords, f'Missing proword: {required}'

    def test_digital_modes_include_modern_essentials(self, client):
        data = client.get('/api/radio/reference').get_json()
        modes = {m['name'] for m in data['digital_modes']}
        for required in ['FT8', 'APRS (AX.25)', 'Winlink', 'DMR',
                         'Meshtastic (LoRa)']:
            assert required in modes, f'Missing digital mode: {required}'


class TestWaterPurificationReference:
    """CE-19: Water purification reference tables."""

    def test_bundle_route_shape(self, client):
        resp = client.get('/api/water/purification-reference')
        assert resp.status_code == 200
        data = resp.get_json()
        for key in ('methods', 'boil_times', 'bleach_dosing',
                    'iodine_dosing', 'iodine_contraindications',
                    'contaminant_response'):
            assert key in data

    def test_methods_include_core_techniques(self, client):
        data = client.get('/api/water/purification-reference').get_json()
        names = {m['name'] for m in data['methods']}
        for required in ['Rolling boil',
                         'Household bleach (unscented, 5-9 % NaOCl)',
                         'Chlorine dioxide tablets (Aquamira / Katadyn Micropur MP1)',
                         'Ceramic filter (0.2-0.5 µm, e.g. Berkey, Doulton)',
                         'Hollow-fiber filter (0.1-0.2 µm, e.g. Sawyer, LifeStraw)',
                         'Reverse osmosis (RO) membrane',
                         'Distillation',
                         'SODIS (solar disinfection)']:
            assert required in names, f'Missing method: {required}'

    def test_each_method_has_removes_and_does_not_remove(self, client):
        data = client.get('/api/water/purification-reference').get_json()
        for m in data['methods']:
            assert m['removes'], f'{m["name"]} has empty removes'
            assert 'does_not_remove' in m, (
                f'{m["name"]} missing does_not_remove'
            )

    def test_bleach_does_not_kill_crypto(self, client):
        data = client.get('/api/water/purification-reference').get_json()
        bleach = next(
            m for m in data['methods']
            if m['name'].startswith('Household bleach')
        )
        assert 'Cryptosporidium' in bleach['does_not_remove'], (
            'Bleach must be flagged as NOT killing Crypto — this is a '
            'life-safety data point (RV park + beaver-country exposure).'
        )

    def test_contaminant_response_covers_crypto_specifically(self, client):
        data = client.get('/api/water/purification-reference').get_json()
        classes = [c['class'] for c in data['contaminant_response']]
        assert any('Cryptosporidium' in c for c in classes)
        # Verify the Crypto entry explicitly calls out that bleach fails.
        crypto = next(
            c for c in data['contaminant_response']
            if 'Cryptosporidium' in c['class']
        )
        assert 'BLEACH' in crypto['notes'].upper() or \
               'do not' in crypto['notes'].lower()

    def test_altitude_boil_times_shift_at_6500_ft(self, client):
        data = client.get('/api/water/purification-reference').get_json()
        times = data['boil_times']
        low = next(t for t in times if t['altitude_ft'] == 0)
        high = next(t for t in times if t['altitude_ft'] == 10000)
        assert low['minutes_rolling_boil'] == 1
        assert high['minutes_rolling_boil'] == 3


class TestLoadoutTemplates:
    """CE-10: Curated bag templates — read-only reference + launch-to-bag."""

    def test_templates_route_returns_expected_count(self, client):
        resp = client.get('/api/loadout/templates')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] >= 12
        assert len(data['templates']) == data['count']

    def test_templates_cover_core_bag_types(self, client):
        data = client.get('/api/loadout/templates').get_json()
        names = {t['name'] for t in data['templates']}
        bag_types = {t['bag_type'] for t in data['templates']}
        for required in [
            '72-Hour Bag — Adult',
            '72-Hour Bag — Child (age 5-10)',
            'Everyday Carry (EDC) Pocket Kit',
            "I.N.C.H. Bag (I'm Never Coming Home)",
            'Vehicle Emergency Kit — Temperate',
            'Vehicle Emergency Kit — Winter',
            'IFAK+ (Individual First Aid Kit, Plus)',
            'Urban / Apartment 72-hr',
        ]:
            assert required in names, f'Missing canonical template: {required}'
        for bt in ['72hour', 'edc', 'get-home', 'inch', 'vehicle', 'medical']:
            assert bt in bag_types, f'Missing bag_type in templates: {bt}'

    def test_each_template_has_items_and_weight(self, client):
        data = client.get('/api/loadout/templates').get_json()
        for t in data['templates']:
            assert t['item_count'] > 0, f'{t["name"]} has no items'
            assert t['computed_weight_lb'] > 0, (
                f'{t["name"]} has zero computed weight'
            )
            # Items must have all 5 fields.
            for it in t['items']:
                for k in ('name', 'category', 'quantity',
                          'weight_oz', 'notes'):
                    assert k in it, (
                        f'{t["name"]} item missing key {k!r}: {it}'
                    )

    def test_item_categories_are_sensible(self, client):
        data = client.get('/api/loadout/templates').get_json()
        allowed = {'water', 'food', 'shelter', 'fire', 'medical', 'comms',
                   'navigation', 'tools', 'clothing', 'hygiene',
                   'documents', 'other'}
        bad = []
        for t in data['templates']:
            for it in t['items']:
                if it['category'] not in allowed:
                    bad.append((t['name'], it['name'], it['category']))
        assert not bad, f'Unknown item categories: {bad[:5]}'

    def test_launch_creates_bag_and_items(self, client):
        """POST /api/loadout/templates/launch must spin up a full bag."""
        resp = client.post('/api/loadout/templates/launch', json={
            'template_name': 'Everyday Carry (EDC) Pocket Kit',
            'owner': 'Test User',
        })
        assert resp.status_code == 201, resp.get_data(as_text=True)
        data = resp.get_json()
        assert data['status'] == 'created'
        assert data['bag_id'] > 0
        assert data['item_count'] >= 10
        # Verify the bag + items actually landed via the existing API.
        bag = client.get(f'/api/loadout/bags/{data["bag_id"]}').get_json()
        assert bag['name'] == 'Everyday Carry (EDC) Pocket Kit'
        assert bag['bag_type'] == 'edc'
        assert 'Created from template' in (bag.get('notes') or '')
        items = client.get(
            f'/api/loadout/bags/{data["bag_id"]}/items'
        ).get_json()
        assert len(items) == data['item_count']

    def test_launch_honors_rename_override(self, client):
        resp = client.post('/api/loadout/templates/launch', json={
            'template_name': 'IFAK+ (Individual First Aid Kit, Plus)',
            'rename_to': 'Jeff\'s trauma kit',
        })
        assert resp.status_code == 201
        bag_id = resp.get_json()['bag_id']
        bag = client.get(f'/api/loadout/bags/{bag_id}').get_json()
        assert bag['name'] == "Jeff's trauma kit"

    def test_launch_unknown_template_404s(self, client):
        resp = client.post('/api/loadout/templates/launch', json={
            'template_name': 'Totally-Fake-Template',
        })
        assert resp.status_code == 404

    def test_launch_requires_template_name(self, client):
        resp = client.post('/api/loadout/templates/launch', json={})
        assert resp.status_code == 400


class TestFieldMedicineReference:
    """CE-03 / CE-04 / CE-13 / CE-15 (v7.62) — expanded meds, interactions,
    pediatric dosing helper, and medicinal herbs."""

    # ─── CE-03: expanded DOSAGE_GUIDE ─────────────────────────
    def test_dosage_guide_has_expanded_list(self):
        from web.blueprints.medical import DOSAGE_GUIDE
        assert len(DOSAGE_GUIDE) >= 40, (
            f'DOSAGE_GUIDE under-expanded (got {len(DOSAGE_GUIDE)}). '
            'CE-03 target is 40+ meds.'
        )

    def test_dosage_guide_has_core_field_meds(self):
        from web.blueprints.medical import DOSAGE_GUIDE
        names = {d['drug'] for d in DOSAGE_GUIDE}
        for required in [
            'Ibuprofen', 'Acetaminophen (Paracetamol)', 'Aspirin',
            'Naproxen', 'Diphenhydramine', 'Cetirizine', 'Loratadine',
            'Epinephrine (1:1000)', 'Amoxicillin', 'Doxycycline',
            'Azithromycin', 'Ciprofloxacin', 'Metronidazole',
            'Tranexamic Acid (TXA)', 'Naloxone', 'Potassium Iodide (KI)',
            'Albuterol MDI', 'Glucagon',
        ]:
            assert required in names, f'DOSAGE_GUIDE missing {required}'

    def test_dosage_guide_entries_have_pregnancy_category(self):
        """New CE-03 rows must carry FDA pregnancy category."""
        from web.blueprints.medical import DOSAGE_GUIDE
        # At least the new seed rows carry pregnancy_category.
        with_preg = [d for d in DOSAGE_GUIDE if 'pregnancy_category' in d]
        assert len(with_preg) >= 30, (
            f'Expected 30+ rows with pregnancy_category, got {len(with_preg)}'
        )

    # ─── CE-04: expanded DRUG_INTERACTIONS ────────────────────
    def test_interactions_expanded(self):
        from web.blueprints.medical import DRUG_INTERACTIONS
        assert len(DRUG_INTERACTIONS) >= 60, (
            f'DRUG_INTERACTIONS under-expanded (got {len(DRUG_INTERACTIONS)}). '
            'CE-04 target is 60+ pairs.'
        )

    def test_interactions_include_major_life_safety_pairs(self):
        from web.blueprints.medical import DRUG_INTERACTIONS
        pairs = {
            (d1.lower(), d2.lower(), sev)
            for (d1, d2, sev, _) in DRUG_INTERACTIONS
        }
        # Core life-safety pairs
        assertions = [
            ('Warfarin', 'Ciprofloxacin', 'major'),
            ('Oxycodone', 'Alcohol', 'major'),
            ('Oxycodone', 'Benzodiazepines', 'major'),
            ('SSRIs', 'MAOIs', 'major'),
            ('SSRIs', 'Tramadol', 'major'),
            ('Metronidazole', 'Alcohol', 'major'),
            ('Nitroglycerin', 'Sildenafil', 'major'),
        ]
        missing = []
        for d1, d2, sev in assertions:
            forward = (d1.lower(), d2.lower(), sev)
            backward = (d2.lower(), d1.lower(), sev)
            if forward not in pairs and backward not in pairs:
                missing.append(f'{d1} ↔ {d2} [{sev}]')
        assert not missing, (
            f'Missing critical interaction pairs: {missing}'
        )

    def test_interactions_endpoint_returns_hits(self, client):
        resp = client.post('/api/medical/interactions', json={
            'medications': ['Warfarin', 'Ciprofloxacin'],
        })
        assert resp.status_code == 200
        hits = resp.get_json()
        assert any(
            'Warfarin' in (h['drug1'] + h['drug2'])
            and 'Ciprofloxacin' in (h['drug1'] + h['drug2'])
            for h in hits
        ), f'Warfarin + Cipro interaction not flagged: {hits}'

    # ─── CE-13: pediatric dosing ──────────────────────────────
    def test_pediatric_growth_chart_endpoint(self, client):
        resp = client.get('/api/medical/pediatric-growth')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'rows' in data
        assert len(data['rows']) >= 20
        # First row is newborn.
        assert data['rows'][0]['age_label'] == 'Newborn'
        assert 2.5 <= data['rows'][0]['weight_p50_kg'] <= 4.0
        # Last row covers 18 yr.
        last = data['rows'][-1]
        assert '18' in last['age_label']
        assert last['weight_p50_kg'] > 50

    def test_pediatric_weight_estimate_endpoint(self, client):
        """Age → weight estimate in kg."""
        resp = client.get('/api/medical/pediatric-weight-estimate?age_years=5')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['age_years'] == 5.0
        assert 15 <= data['estimated_weight_kg'] <= 25
        assert 'band_label' in data

    def test_pediatric_weight_estimate_rejects_adult(self, client):
        resp = client.get('/api/medical/pediatric-weight-estimate?age_years=25')
        assert resp.status_code == 400

    def test_pediatric_weight_estimate_rejects_negative(self, client):
        resp = client.get('/api/medical/pediatric-weight-estimate?age_years=-1')
        assert resp.status_code == 400

    def test_pediatric_weight_estimate_rejects_missing(self, client):
        resp = client.get('/api/medical/pediatric-weight-estimate')
        assert resp.status_code == 400

    def test_estimate_pediatric_weight_helper(self):
        from seeds.medications import estimate_pediatric_weight
        # Sanity — infant should estimate low, teen high.
        assert estimate_pediatric_weight(0.5) < 12
        assert estimate_pediatric_weight(10) > 20
        assert estimate_pediatric_weight(15) > 40
        # Out of range → None
        assert estimate_pediatric_weight(25) is None
        assert estimate_pediatric_weight(-5) is None

    # ─── CE-15: expanded herbs ────────────────────────────────
    def test_herbal_remedies_expanded(self, db):
        count = db.execute(
            'SELECT COUNT(*) FROM herbal_remedies WHERE is_builtin = 1'
        ).fetchone()[0]
        assert count >= 40, (
            f'Herbal remedies under-seeded (got {count}). CE-15 target is 40+.'
        )

    def test_herbs_include_canonical_species(self, db):
        rows = db.execute(
            'SELECT name FROM herbal_remedies WHERE is_builtin = 1'
        ).fetchall()
        names = {r['name'] for r in rows}
        for required in [
            'Yarrow', 'Plantain', 'Elderberry', 'Echinacea',  # original 10
            'Peppermint', 'Sage', 'Thyme', 'Lavender', 'Lemon Balm',
            'Valerian', 'Passionflower', 'Dandelion (root + leaf)',
            'Nettle (stinging)', 'Mullein', 'Goldenseal', 'Uva Ursi',
            'Raspberry Leaf', 'Black Cohosh', 'Red Clover',
            "St. John's Wort", 'Turmeric', 'Ashwagandha',
        ]:
            assert required in names, (
                f'Herbal remedies missing canonical species: {required}'
            )

    def test_herbs_have_safety_data(self, db):
        """Every built-in herb must carry non-empty contraindications
        OR explicitly empty list (not NULL)."""
        rows = db.execute(
            'SELECT name, contraindications FROM herbal_remedies '
            'WHERE is_builtin = 1'
        ).fetchall()
        for r in rows:
            contra = r['contraindications']
            assert contra is not None, f'{r["name"]} has NULL contraindications'
            # Must be parseable JSON.
            import json
            try:
                json.loads(contra)
            except ValueError:
                raise AssertionError(
                    f'{r["name"]} has invalid contraindications JSON'
                )


class TestHazmatAgentReference:
    """CE-12: Hazmat / CBRN agent reference (v7.60)."""

    def test_list_route_returns_agents(self, client):
        r = client.get('/api/hazmat/agents')
        assert r.status_code == 200
        data = r.get_json()
        assert data['total'] >= 10
        assert data['count'] == len(data['agents'])
        assert 'chemical' in data['categories']

    def test_category_filter(self, client):
        r = client.get('/api/hazmat/agents?category=chemical')
        assert r.status_code == 200
        data = r.get_json()
        assert all(a['category'] == 'chemical' for a in data['agents'])

    def test_invalid_category_returns_all(self, client):
        r = client.get('/api/hazmat/agents?category=bogus')
        assert r.status_code == 200
        data = r.get_json()
        assert data['count'] == data['total']

    def test_search_query(self, client):
        r = client.get('/api/hazmat/agents?q=chlorine')
        assert r.status_code == 200
        data = r.get_json()
        assert data['count'] >= 1
        assert any('chlorine' in a['name'].lower() for a in data['agents'])

    def test_detail_route(self, client):
        r = client.get('/api/hazmat/agents/chlorine')
        assert r.status_code == 200
        data = r.get_json()
        assert data['id'] == 'chlorine'
        assert data['category'] == 'chemical'
        assert 'ppe_level' in data

    def test_detail_route_404s_unknown(self, client):
        r = client.get('/api/hazmat/agents/nonexistent_agent')
        assert r.status_code == 404


class TestSeedIdempotency:
    """Re-running seeders on an already-populated DB must not duplicate."""

    def test_companion_plants_idempotent(self, db):
        from db import _seed_companion_plants
        before = db.execute(
            'SELECT COUNT(*) FROM companion_plants'
        ).fetchone()[0]
        _seed_companion_plants(db)
        after = db.execute(
            'SELECT COUNT(*) FROM companion_plants'
        ).fetchone()[0]
        assert after == before

    def test_weather_action_rules_idempotent(self, db):
        from db import _seed_weather_action_rules
        before = db.execute(
            'SELECT COUNT(*) FROM weather_action_rules'
        ).fetchone()[0]
        _seed_weather_action_rules(db)
        after = db.execute(
            'SELECT COUNT(*) FROM weather_action_rules'
        ).fetchone()[0]
        assert after == before

    def test_pest_guide_idempotent(self, db):
        from db import _seed_pest_guide
        before = db.execute('SELECT COUNT(*) FROM pest_guide').fetchone()[0]
        _seed_pest_guide(db)
        after = db.execute('SELECT COUNT(*) FROM pest_guide').fetchone()[0]
        assert after == before

    def test_medicinal_herbs_idempotent(self, db):
        from db import _seed_medicinal_herbs
        before = db.execute(
            'SELECT COUNT(*) FROM herbal_remedies WHERE is_builtin=1'
        ).fetchone()[0]
        _seed_medicinal_herbs(db)
        after = db.execute(
            'SELECT COUNT(*) FROM herbal_remedies WHERE is_builtin=1'
        ).fetchone()[0]
        assert after == before
