"""Smoke tests for the consumption blueprint.

Covers all 8 routes:
  GET    /api/consumption/profiles                — list (pagination)
  GET    /api/consumption/profiles/<id>           — detail (404 + happy)
  POST   /api/consumption/profiles                — create (400 + 201)
  PUT    /api/consumption/profiles/<id>           — update (404 + happy + 400)
  DELETE /api/consumption/profiles/<id>           — delete (404 + happy)
  GET    /api/consumption/defaults                — PROFILE_DEFAULTS keys + dietary
  GET    /api/consumption/summary                 — household fallback + profile aggregation
  POST   /api/consumption/what-if                 — extra adults/children scenario
  GET    /api/consumption/caloric-gap             — 30-day gap analysis

Hand-pinned values:
  Defaults — adult_male_moderate=2400 kcal, adult_female_active=2400 kcal,
             child_4_8=1400 kcal.
  What-if  — 2 profiles × 2400 kcal = 4800 base; +1 adult (active=2400) +
             1 child (1400) = 8600 scenario kcal/day.
  Summary fallback — 2 (default household) × 2000 = 4000 kcal/day.
"""

import json
import pytest

from db import db_session


# ── /api/consumption/profiles GET ─────────────────────────────────────────

class TestProfilesList:
    def test_empty_returns_empty_list(self, client):
        resp = client.get('/api/consumption/profiles')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_inserted_rows_with_normalized_dietary(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO consumption_profiles (name, profile_type, "
                " activity_level, daily_calories, daily_water_gal, "
                " dietary_restrictions) VALUES (?,?,?,?,?,?)",
                ('Alice', 'adult_female', 'moderate', 2000, 0.55,
                 json.dumps(['vegetarian', 'gluten_free']))
            )
            db.commit()
        rows = client.get('/api/consumption/profiles').get_json()
        assert len(rows) == 1
        assert rows[0]['name'] == 'Alice'
        # dietary_restrictions deserialized in response
        assert rows[0]['dietary_restrictions'] == ['vegetarian', 'gluten_free']

    def test_invalid_dietary_json_falls_back_to_empty(self, client):
        """A malformed JSON string in dietary_restrictions doesn't 500 —
        _format_profile() catches and falls back to []."""
        with db_session() as db:
            db.execute(
                "INSERT INTO consumption_profiles (name, dietary_restrictions) "
                "VALUES (?, ?)",
                ('BadJson', '{not json')
            )
            db.commit()
        rows = client.get('/api/consumption/profiles').get_json()
        bad = next(r for r in rows if r['name'] == 'BadJson')
        assert bad['dietary_restrictions'] == []


# ── /api/consumption/profiles/<id> GET (detail) ───────────────────────────

class TestProfileDetail:
    def test_404_unknown(self, client):
        resp = client.get('/api/consumption/profiles/99999')
        assert resp.status_code == 404
        assert resp.get_json()['error'] == 'not found'

    def test_happy_path(self, client):
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO consumption_profiles (name) VALUES (?)",
                ('Detail',)
            )
            db.commit()
            pid = cur.lastrowid
        body = client.get(f'/api/consumption/profiles/{pid}').get_json()
        assert body['name'] == 'Detail'
        assert body['dietary_restrictions'] == []  # default empty


# ── /api/consumption/profiles POST ────────────────────────────────────────

class TestProfileCreate:
    def test_400_when_name_missing(self, client):
        resp = client.post('/api/consumption/profiles', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Name required'

    def test_400_when_name_empty(self, client):
        resp = client.post('/api/consumption/profiles', json={'name': ''})
        assert resp.status_code == 400

    def test_uses_defaults_when_kcal_omitted(self, client):
        """profile_type='adult_male' + activity_level='moderate' resolves
        to PROFILE_DEFAULTS['adult_male_moderate'] = 2400 kcal."""
        resp = client.post('/api/consumption/profiles',
                           json={'name': 'DefaultsTest',
                                 'profile_type': 'adult_male',
                                 'activity_level': 'moderate'})
        assert resp.status_code == 201
        with db_session() as db:
            row = db.execute(
                "SELECT daily_calories, daily_water_gal "
                "FROM consumption_profiles WHERE name = ?",
                ('DefaultsTest',)
            ).fetchone()
        assert row['daily_calories'] == 2400
        assert row['daily_water_gal'] == 0.65

    def test_unknown_profile_type_falls_back_to_2000(self, client):
        """An unknown profile_type+activity combo falls back to the
        2000 kcal / 0.5 gal default."""
        resp = client.post('/api/consumption/profiles',
                           json={'name': 'Unknown',
                                 'profile_type': 'martian',
                                 'activity_level': 'lunar'})
        assert resp.status_code == 201
        with db_session() as db:
            row = db.execute(
                "SELECT daily_calories FROM consumption_profiles WHERE name = ?",
                ('Unknown',)
            ).fetchone()
        assert row['daily_calories'] == 2000

    def test_dietary_list_is_json_serialized(self, client):
        client.post('/api/consumption/profiles',
                    json={'name': 'Dietary',
                          'dietary_restrictions': ['vegan', 'kosher']})
        with db_session() as db:
            row = db.execute(
                "SELECT dietary_restrictions FROM consumption_profiles WHERE name = ?",
                ('Dietary',)
            ).fetchone()
        # Stored as JSON string
        assert json.loads(row['dietary_restrictions']) == ['vegan', 'kosher']

    def test_dietary_string_passthrough(self, client):
        """If the client sends a pre-serialized string instead of a list,
        the route accepts it as-is (no double-encode)."""
        client.post('/api/consumption/profiles',
                    json={'name': 'Pre',
                          'dietary_restrictions': '["paleo"]'})
        with db_session() as db:
            row = db.execute(
                "SELECT dietary_restrictions FROM consumption_profiles WHERE name = ?",
                ('Pre',)
            ).fetchone()
        assert row['dietary_restrictions'] == '["paleo"]'


# ── /api/consumption/profiles/<id> PUT ────────────────────────────────────

class TestProfileUpdate:
    def test_404_when_unknown_id_with_valid_field(self, client):
        resp = client.put('/api/consumption/profiles/99999',
                          json={'daily_calories': 2500})
        assert resp.status_code == 404

    def test_400_when_no_fields(self, client):
        # Create first so we don't trip 404
        client.post('/api/consumption/profiles', json={'name': 'PutEmpty'})
        with db_session() as db:
            row = db.execute(
                "SELECT id FROM consumption_profiles WHERE name = ?",
                ('PutEmpty',)
            ).fetchone()
        resp = client.put(f'/api/consumption/profiles/{row["id"]}', json={})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'No fields to update'

    def test_happy_path_updates_fields(self, client):
        client.post('/api/consumption/profiles',
                    json={'name': 'UpdateMe', 'daily_calories': 2000})
        with db_session() as db:
            pid = db.execute(
                "SELECT id FROM consumption_profiles WHERE name = ?",
                ('UpdateMe',)
            ).fetchone()['id']
        resp = client.put(f'/api/consumption/profiles/{pid}',
                          json={'daily_calories': 3500,
                                'notes': 'heavy labor'})
        assert resp.status_code == 200
        with db_session() as db:
            row = db.execute(
                "SELECT daily_calories, notes FROM consumption_profiles WHERE id = ?",
                (pid,)
            ).fetchone()
        assert row['daily_calories'] == 3500
        assert row['notes'] == 'heavy labor'

    def test_dietary_list_serializes_on_update(self, client):
        client.post('/api/consumption/profiles', json={'name': 'DietPut'})
        with db_session() as db:
            pid = db.execute(
                "SELECT id FROM consumption_profiles WHERE name = ?",
                ('DietPut',)
            ).fetchone()['id']
        client.put(f'/api/consumption/profiles/{pid}',
                   json={'dietary_restrictions': ['halal', 'low_sodium']})
        with db_session() as db:
            row = db.execute(
                "SELECT dietary_restrictions FROM consumption_profiles WHERE id = ?",
                (pid,)
            ).fetchone()
        assert json.loads(row['dietary_restrictions']) == ['halal', 'low_sodium']


# ── /api/consumption/profiles/<id> DELETE ─────────────────────────────────

class TestProfileDelete:
    def test_404_when_unknown(self, client):
        resp = client.delete('/api/consumption/profiles/99999')
        assert resp.status_code == 404

    def test_happy_path(self, client):
        client.post('/api/consumption/profiles', json={'name': 'GoneSoon'})
        with db_session() as db:
            pid = db.execute(
                "SELECT id FROM consumption_profiles WHERE name = ?",
                ('GoneSoon',)
            ).fetchone()['id']
        resp = client.delete(f'/api/consumption/profiles/{pid}')
        assert resp.status_code == 200
        with db_session() as db:
            row = db.execute(
                "SELECT id FROM consumption_profiles WHERE id = ?", (pid,)
            ).fetchone()
        assert row is None


# ── /api/consumption/defaults ─────────────────────────────────────────────

class TestDefaults:
    def test_includes_known_profile_types(self, client):
        body = client.get('/api/consumption/defaults').get_json()
        assert 'adult_male_sedentary' in body['profile_types']
        assert 'adult_female_active' in body['profile_types']
        assert 'child_1_3' in body['profile_types']
        # Hand-pinned values
        assert body['defaults']['adult_male_moderate']['calories'] == 2400
        assert body['defaults']['child_4_8']['calories'] == 1400
        # Dietary options are an array of >= 14 entries
        assert 'vegan' in body['dietary_options']
        assert 'gluten_free' in body['dietary_options']


# ── /api/consumption/summary ──────────────────────────────────────────────

class TestSummary:
    def test_no_profiles_uses_household_size_default(self, client):
        body = client.get('/api/consumption/summary').get_json()
        assert body['source'] == 'setting'
        # Default household_size = 2 → 2 × 2000 = 4000
        assert body['people'] == 2
        assert body['total_daily_calories'] == 4000
        assert body['total_daily_water_gal'] == 1.0
        assert body['profiles'] == []

    def test_household_size_setting_respected(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO settings (key, value) VALUES ('household_size', '5')"
            )
            db.commit()
        body = client.get('/api/consumption/summary').get_json()
        assert body['people'] == 5
        assert body['total_daily_calories'] == 10000

    def test_garbage_household_size_falls_back_to_2(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO settings (key, value) VALUES ('household_size', 'NaN')"
            )
            db.commit()
        body = client.get('/api/consumption/summary').get_json()
        assert body['people'] == 2  # int('NaN') trapped

    def test_profiles_aggregate(self, client):
        """Two profiles: 2400 + 1800 = 4200 kcal, 0.65 + 0.45 = 1.10 gal."""
        with db_session() as db:
            db.execute(
                "INSERT INTO consumption_profiles (name, daily_calories, "
                " daily_water_gal) VALUES (?,?,?)",
                ('A', 2400, 0.65)
            )
            db.execute(
                "INSERT INTO consumption_profiles (name, daily_calories, "
                " daily_water_gal) VALUES (?,?,?)",
                ('B', 1800, 0.45)
            )
            db.commit()
        body = client.get('/api/consumption/summary').get_json()
        assert body['source'] == 'profiles'
        assert body['people'] == 2
        assert body['total_daily_calories'] == 4200
        assert body['total_daily_water_gal'] == 1.10
        assert len(body['profiles']) == 2


# ── /api/consumption/what-if ──────────────────────────────────────────────

class TestWhatIf:
    def test_no_extras_baseline_equals_scenario(self, client):
        """With zero extra people and no profiles, baseline + scenario
        both equal household_size × 2000 = 4000 kcal/day."""
        body = client.post('/api/consumption/what-if', json={}).get_json()
        assert body['baseline']['daily_calories'] == 4000
        assert body['scenario']['daily_calories'] == 4000

    def test_extra_adults_and_children(self, client):
        """No profiles → fallback household=2. Add 1 adult (active=2400)
        + 1 child (1400) → scenario = 4000 + 2400 + 1400 = 7800."""
        body = client.post('/api/consumption/what-if',
                           json={'extra_adults': 1,
                                 'extra_children': 1,
                                 'activity_level': 'active'}).get_json()
        assert body['baseline']['daily_calories'] == 4000
        assert body['scenario']['daily_calories'] == 7800
        assert body['scenario']['extra_adults'] == 1
        assert body['scenario']['extra_children'] == 1

    def test_extra_adults_default_2000(self, client):
        """Without activity_level='active', extra adult = 2000 kcal/day."""
        body = client.post('/api/consumption/what-if',
                           json={'extra_adults': 2}).get_json()
        assert body['scenario']['daily_calories'] == 4000 + 2 * 2000

    def test_baseline_food_days_uses_inventory_link(self, client):
        """Add an inventory→nutrition link with 10000 kcal stored.
        baseline daily need = 4000, so food_days = 10000 / 4000 = 2.5."""
        with db_session() as db:
            cur = db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES (?,?,?,?)",
                ('FoodItem', 'food', 1, 'ea')
            )
            inv_id = cur.lastrowid
            db.execute(
                "INSERT INTO nutrition_foods (fdc_id, description) "
                "VALUES (?, ?)", (5001, 'PinFood')
            )
            db.execute(
                "INSERT INTO inventory_nutrition_link "
                " (inventory_id, fdc_id, servings_per_item, calories_per_serving) "
                "VALUES (?,?,?,?)",
                (inv_id, 5001, 1, 10000)
            )
            db.commit()
        body = client.post('/api/consumption/what-if', json={}).get_json()
        assert body['total_food_calories'] == 10000
        assert body['baseline']['food_days'] == 2.5


# ── /api/consumption/caloric-gap ──────────────────────────────────────────

class TestCaloricGap:
    def test_no_profiles_no_inventory_zero_coverage(self, client):
        body = client.get('/api/consumption/caloric-gap').get_json()
        assert body['people'] == 2
        assert body['daily_calories_needed'] == 4000
        assert body['total_stored_calories'] == 0
        assert body['food_coverage_days'] == 0
        # 30-day gap = 4000 × 30 - 0 = 120000
        assert body['gap_calories'] == 120000

    def test_categorized_inventory_breakdown(self, client):
        """Two food items, both linked. category='food' and category='medical'.
        Verify per-category caloric breakdown."""
        with db_session() as db:
            db.execute(
                "INSERT INTO nutrition_foods (fdc_id, description) "
                "VALUES (?, ?)", (6001, 'Calorie Bar')
            )
            cur = db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES (?,?,?,?)",
                ('Bar', 'food', 5, 'ea')
            )
            inv_id = cur.lastrowid
            db.execute(
                "INSERT INTO inventory_nutrition_link "
                " (inventory_id, fdc_id, servings_per_item, calories_per_serving) "
                "VALUES (?,?,?,?)",
                (inv_id, 6001, 2, 250)  # 5 × 2 × 250 = 2500 kcal
            )
            db.commit()
        body = client.get('/api/consumption/caloric-gap').get_json()
        assert body['total_stored_calories'] == 2500
        # daily_need = 4000 → 2500/4000 = 0.6 days (rounded to 1 decimal)
        assert body['food_coverage_days'] == 0.6
        # categories list non-empty
        food_cat = next(c for c in body['categories'] if c['category'] == 'food')
        assert food_cat['total_calories'] == 2500

    def test_surplus_path_when_30_days_covered(self, client):
        """Need 4000/day × 30 = 120000. Stored = 200000 → surplus."""
        with db_session() as db:
            db.execute(
                "INSERT INTO nutrition_foods (fdc_id, description) "
                "VALUES (?, ?)", (7001, 'Megafood')
            )
            cur = db.execute(
                "INSERT INTO inventory (name, category, quantity, unit) "
                "VALUES (?,?,?,?)",
                ('Mega', 'food', 1, 'ea')
            )
            db.execute(
                "INSERT INTO inventory_nutrition_link "
                " (inventory_id, fdc_id, servings_per_item, calories_per_serving) "
                "VALUES (?,?,?,?)",
                (cur.lastrowid, 7001, 1, 200000)
            )
            db.commit()
        body = client.get('/api/consumption/caloric-gap').get_json()
        assert 'Surplus' in body['gap_description']
        assert body['gap_calories'] == 0

    def test_uses_profiles_when_present(self, client):
        with db_session() as db:
            db.execute(
                "INSERT INTO consumption_profiles (name, daily_calories, "
                " daily_water_gal) VALUES (?,?,?)",
                ('OnlyMe', 2200, 0.6)
            )
            db.commit()
        body = client.get('/api/consumption/caloric-gap').get_json()
        assert body['people'] == 1
        assert body['daily_calories_needed'] == 2200
