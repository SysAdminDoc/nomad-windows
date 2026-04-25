"""Smoke tests for the kit_builder blueprint.

Covers all 2 routes:
  POST /api/kit-builder/plan                  — wizard input → tailored item
                                                list with reasons + inventory
                                                cross-reference + totals
  POST /api/kit-builder/add-to-shopping-list  — bulk-insert gap items into
                                                shopping_list

The route is a pure rule engine — no LLM, no network, no FS. All
assertion pins are hand-computed from the constants in
`web/blueprints/kit_builder.py`:

  Water (L/person/day):
    temperate bug_out = 3.0   |  hot bug_out = 6.0
    temperate shelter_in_place = 2.0  |  tropical bug_out = 5.0

  Calories (kcal/person/day):
    bug_out = 3500   |  shelter_in_place = 2200   |  vehicle = 2500
    medical_bag = 0  (food section skipped entirely)

  Clamps:
    people  → max 50, min 1   (defaults 1 on garbage input)
    duration_hrs → max 90×24=2160, min 1   (defaults 72 on garbage)

  Medical-bag baseline = 15 items; no water/food/shelter/comms.
"""

import pytest

from db import db_session


# ── /api/kit-builder/plan POST ────────────────────────────────────────────

class TestPlanInputValidation:
    def test_unknown_mission_400(self, client):
        resp = client.post('/api/kit-builder/plan',
                           json={'mission': 'space_walk'})
        assert resp.status_code == 400
        assert 'mission' in resp.get_json()['error'].lower()

    def test_unknown_climate_400(self, client):
        resp = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out', 'climate': 'arctic'})
        assert resp.status_code == 400

    def test_unknown_mobility_400(self, client):
        resp = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out', 'mobility': 'helicopter'})
        assert resp.status_code == 400

    def test_default_inputs_when_missing(self, client):
        """Empty body → mission=bug_out, climate=temperate, mobility=mixed,
        people=1, duration_hrs=72."""
        resp = client.post('/api/kit-builder/plan', json={})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['params']['mission'] == 'bug_out'
        assert body['params']['climate'] == 'temperate'
        assert body['params']['mobility'] == 'mixed'
        assert body['params']['people'] == 1
        assert body['params']['duration_hrs'] == 72

    def test_garbage_people_falls_back_to_one(self, client):
        body = client.post('/api/kit-builder/plan',
                           json={'people': 'NaN'}).get_json()
        assert body['params']['people'] == 1

    def test_people_clamps_to_max_50(self, client):
        body = client.post('/api/kit-builder/plan',
                           json={'people': 9999}).get_json()
        assert body['params']['people'] == 50

    def test_duration_clamps_to_90_days(self, client):
        body = client.post('/api/kit-builder/plan',
                           json={'duration_hrs': 999999}).get_json()
        assert body['params']['duration_hrs'] == 90 * 24  # 2160

    def test_mission_with_dash_normalizes(self, client):
        """'bug-out' → 'bug_out' via .lower().replace('-', '_')."""
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug-out'}).get_json()
        assert body['params']['mission'] == 'bug_out'


# ── Plan body composition (rule-engine outputs) ──────────────────────────

class TestPlanComposition:
    def _names(self, items):
        return {i['name'] for i in items}

    def _by_name(self, items, name):
        return next((i for i in items if i['name'] == name), None)

    def test_temperate_bug_out_3_days_1_person_water_math(self, client):
        """3.0 L/person/day × 1 × 3 days = 9.0 L total, 9.0 kg weight."""
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'temperate',
            'people': 1, 'duration_hrs': 72
        }).get_json()
        water = self._by_name(body['items'], 'Potable water')
        assert water['quantity'] == 9.0
        assert water['weight_kg'] == 9.0
        assert water['unit'] == 'L'
        assert '3.0 L/person/day' in water['reason']

    def test_hot_bug_out_4_people_72hr_water_math(self, client):
        """6.0 L × 4 people × 3 days = 72.0 L."""
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'hot', 'people': 4,
            'duration_hrs': 72
        }).get_json()
        water = self._by_name(body['items'], 'Potable water')
        assert water['quantity'] == 72.0

    def test_medical_bag_skips_water_food_shelter(self, client):
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'medical_bag'}).get_json()
        names = self._names(body['items'])
        assert 'Potable water' not in names
        assert 'Energy bars / trail mix' not in names
        assert 'Emergency blanket (mylar)' not in names
        # 15 medical items in the baseline list
        medical = [i for i in body['items'] if i['category'] == 'medical']
        assert len(medical) == 15

    def test_cold_climate_adds_sleeping_bag_and_base_layer(self, client):
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'cold'
        }).get_json()
        names = self._names(body['items'])
        assert 'Sleeping bag (rated to climate)' in names
        assert 'Insulated base layer + socks' in names

    def test_tropical_climate_adds_deet(self, client):
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'tropical'
        }).get_json()
        names = self._names(body['items'])
        assert 'Insect repellent (DEET)' in names
        assert 'Sun hat / UV buff' in names

    def test_hot_climate_no_deet(self, client):
        """DEET is tropical-only — hot climate does NOT add it but
        DOES add the sun hat."""
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'hot'
        }).get_json()
        names = self._names(body['items'])
        assert 'Insect repellent (DEET)' not in names
        assert 'Sun hat / UV buff' in names

    def test_foot_short_trip_uses_lightweight_food(self, client):
        """foot mobility + days <= 3 → energy bars + MRE split."""
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'mobility': 'foot', 'duration_hrs': 48
        }).get_json()
        names = self._names(body['items'])
        assert 'Energy bars / trail mix' in names
        assert 'MRE / freeze-dried meal' in names

    def test_shelter_uses_shelf_stable_food(self, client):
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'shelter_in_place'
        }).get_json()
        names = self._names(body['items'])
        assert 'Shelf-stable food (canned + dry)' in names
        # Bug-out specific items NOT present
        assert 'Tarp / bivy shelter' not in names

    def test_bug_out_includes_tarp_and_map(self, client):
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out'
        }).get_json()
        names = self._names(body['items'])
        assert 'Tarp / bivy shelter' in names
        assert 'Topographic map + compass' in names

    def test_bug_out_and_vehicle_include_cash(self, client):
        for mission in ('bug_out', 'vehicle'):
            body = client.post('/api/kit-builder/plan',
                               json={'mission': mission}).get_json()
            names = {i['name'] for i in body['items']}
            assert 'Cash (small bills)' in names, f'Cash missing for {mission}'

    def test_shelter_in_place_no_cash(self, client):
        body = client.post('/api/kit-builder/plan', json={
            'mission': 'shelter_in_place'
        }).get_json()
        names = self._names(body['items'])
        assert 'Cash (small bills)' not in names

    def test_every_item_has_reason(self, client):
        """Explainability contract — no item ships without a reason."""
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out',
                                 'climate': 'cold',
                                 'people': 3,
                                 'duration_hrs': 96}).get_json()
        for item in body['items']:
            assert item.get('reason'), f"Missing reason for {item['name']}"


# ── Plan totals + inventory cross-reference ───────────────────────────────

class TestPlanTotalsAndInventoryMatching:
    def test_no_inventory_all_gaps(self, client):
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out'}).get_json()
        gap_count = body['totals']['gaps']
        assert gap_count == body['totals']['item_count']
        assert body['totals']['have'] == 0
        assert body['totals']['partial'] == 0

    def test_have_when_owned_meets_recommended(self, client):
        """1 person × 3.0 L × 3 days = 9.0 L recommended. Seed 10.0 L
        of 'Potable water' inventory → status=have."""
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES ('Potable water', 'water', 10.0, 'L')"
            )
            db.commit()
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out'}).get_json()
        water = next(i for i in body['items'] if i['name'] == 'Potable water')
        assert water['status'] == 'have'
        assert water['owned_quantity'] == 10.0
        assert body['totals']['have'] >= 1

    def test_partial_when_owned_below_recommended(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES ('Potable water', 'water', 5.0, 'L')"
            )
            db.commit()
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out'}).get_json()
        water = next(i for i in body['items'] if i['name'] == 'Potable water')
        assert water['status'] == 'partial'
        assert body['totals']['partial'] >= 1

    def test_normalized_match_collapses_whitespace_and_case(self, client):
        """`_normalize_name` lowercases + collapses whitespace, so
        'POTABLE   WATER' (extra spaces, uppercase) matches the recommended
        'Potable water'."""
        with db_session() as db:
            db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES ('POTABLE   WATER', 'water', 99.0, 'L')"
            )
            db.commit()
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out'}).get_json()
        water = next(i for i in body['items'] if i['name'] == 'Potable water')
        assert water['status'] == 'have'

    def test_totals_weight_kg_is_a_positive_float(self, client):
        body = client.post('/api/kit-builder/plan',
                           json={'mission': 'bug_out',
                                 'people': 2,
                                 'duration_hrs': 72}).get_json()
        assert body['totals']['weight_kg'] > 0
        assert isinstance(body['totals']['weight_kg'], float)


# ── /api/kit-builder/add-to-shopping-list POST ───────────────────────────

class TestAddToShopping:
    def test_400_when_items_not_a_list(self, client):
        resp = client.post('/api/kit-builder/add-to-shopping-list',
                           json={'items': 'not a list'})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'items must be a list'

    def test_empty_body_returns_added_zero(self, client):
        """Missing 'items' key + non-list both fall to []. Empty input
        commits zero rows but still returns 201 'ok'."""
        resp = client.post('/api/kit-builder/add-to-shopping-list',
                           json={})
        assert resp.status_code == 201
        assert resp.get_json() == {'status': 'ok', 'added': 0}

    def test_happy_path_inserts_rows(self, client):
        items = [
            {'name': 'Potable water', 'category': 'water',
             'quantity': 9, 'unit': 'L'},
            {'name': 'Multi-tool', 'category': 'tools',
             'quantity': 1, 'unit': 'ea'},
            {'name': 'Tarp / bivy shelter', 'category': 'shelter',
             'quantity': 1, 'unit': 'ea'},
        ]
        resp = client.post('/api/kit-builder/add-to-shopping-list',
                           json={'items': items})
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['status'] == 'ok'
        assert body['added'] == 3
        with db_session() as db:
            rows = db.execute(
                'SELECT name FROM shopping_list ORDER BY name'
            ).fetchall()
        names = [r['name'] for r in rows]
        assert 'Potable water' in names
        assert 'Multi-tool' in names
        assert 'Tarp / bivy shelter' in names

    def test_skips_items_without_name(self, client):
        """Empty / whitespace name → skipped; non-dict entries → skipped."""
        items = [
            {'name': '', 'quantity': 1},  # empty name → skip
            {'name': '   ', 'quantity': 1},  # whitespace → skip
            'not a dict',  # non-dict → skip
            {'name': 'KeptOne', 'quantity': 2},  # actually inserted
        ]
        resp = client.post('/api/kit-builder/add-to-shopping-list',
                           json={'items': items})
        body = resp.get_json()
        # Only 1 actually inserted (3 skipped)
        assert body['added'] == 1

    def test_garbage_quantity_falls_back_to_one(self, client):
        """`float('not-a-number')` raises ValueError → caught, qty=1.0.
        Note: `float('NaN')` actually succeeds in Python (returns nan),
        so use a string that genuinely fails the float coerce."""
        items = [{'name': 'BadQty', 'quantity': 'not-a-number'}]
        resp = client.post('/api/kit-builder/add-to-shopping-list',
                           json={'items': items})
        assert resp.status_code == 201
        with db_session() as db:
            row = db.execute(
                "SELECT quantity_needed FROM shopping_list WHERE name = 'BadQty'"
            ).fetchone()
        assert row['quantity_needed'] == 1.0

    def test_input_capped_at_200(self, client):
        """A 250-item list should silently truncate to 200 — no DoS."""
        items = [{'name': f'Item {i}', 'quantity': 1} for i in range(250)]
        resp = client.post('/api/kit-builder/add-to-shopping-list',
                           json={'items': items})
        assert resp.status_code == 201
        assert resp.get_json()['added'] == 200

    def test_matched_inventory_id_persists_when_int(self, client):
        """`matched_inventory_id` is the cross-reference back to the
        inventory row; int values should round-trip into shopping_list."""
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES ('XRefItem', 'tools', 0, 'ea')"
            )
            db.commit()
            inv_id = cur.lastrowid
        client.post('/api/kit-builder/add-to-shopping-list',
                    json={'items': [{'name': 'XRefItem', 'quantity': 1,
                                     'matched_inventory_id': inv_id}]})
        with db_session() as db:
            row = db.execute(
                "SELECT inventory_id FROM shopping_list WHERE name = 'XRefItem'"
            ).fetchone()
        assert row['inventory_id'] == inv_id
