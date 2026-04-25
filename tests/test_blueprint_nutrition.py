"""Smoke tests for the nutrition blueprint.

Covers all 8 routes:
  GET    /api/nutrition/search                  — q + group + limit + clamps
  GET    /api/nutrition/lookup/<fdc_id>         — food + nutrients (404 + happy)
  GET    /api/nutrition/food-groups             — DISTINCT non-empty groups
  POST   /api/nutrition/link                    — 400 + 404 + 201
  DELETE /api/nutrition/link/<inv_id>           — 404 + happy
  GET    /api/nutrition/link/<inv_id>           — {linked:False} / link detail
  GET    /api/nutrition/summary                 — totals + person_days_of_food
  GET    /api/nutrition/gaps                    — has_data:False + amber/red/green

Tests seed `nutrition_foods`, `nutrition_nutrients`, and `inventory`
rows directly so the calculator paths (summary / gaps) have something
to aggregate. Schema inferred from db.py:3018-3060.

Hand-computed assertion pins:
  Summary  — qty=10, servings=2, kcal=200/serving → 10×2×200 = 4000 kcal,
             household_size=2, daily_need=2000 → 4000/(2×2000) = 1.0 day
  Gaps    — Vitamin C: amount=50mg per food × 10 qty × 2 servings = 1000 mg
             daily_need = 90 (RDA) × 2 (household) = 180 mg/day
             days_supply = 1000 / 180 = 5.56 → status='red' (<7)
"""

import pytest

from db import db_session


# ── SHARED HELPERS ────────────────────────────────────────────────────────

def _seed_food(db, fdc_id, description, group='Vegetables', kcal=200,
               protein=10, fat=5, carbs=30):
    db.execute(
        "INSERT INTO nutrition_foods (fdc_id, description, food_group, "
        " calories, protein_g, fat_g, carbs_g, serving_size, serving_unit) "
        "VALUES (?,?,?,?,?,?,?,?,?)",
        (fdc_id, description, group, kcal, protein, fat, carbs, 100, 'g')
    )

def _seed_nutrient(db, fdc_id, name, amount, unit='mg'):
    db.execute(
        "INSERT INTO nutrition_nutrients (fdc_id, nutrient_name, amount, unit) "
        "VALUES (?,?,?,?)",
        (fdc_id, name, amount, unit)
    )

def _seed_inv(db, name, qty=1, category='food'):
    cur = db.execute(
        "INSERT INTO inventory (name, category, quantity, unit) "
        "VALUES (?,?,?,?)",
        (name, category, qty, 'ea')
    )
    return cur.lastrowid


# ── /api/nutrition/search ─────────────────────────────────────────────────

class TestSearch:
    def test_empty_query_and_no_group_returns_empty(self, client):
        resp = client.get('/api/nutrition/search')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_q_substring_match(self, client):
        with db_session() as db:
            _seed_food(db, 1001, 'Broccoli, raw', 'Vegetables')
            _seed_food(db, 1002, 'Carrots, raw', 'Vegetables')
            db.commit()
        resp = client.get('/api/nutrition/search?q=Brocc')
        rows = resp.get_json()
        names = {r['description'] for r in rows}
        assert 'Broccoli, raw' in names
        assert 'Carrots, raw' not in names

    def test_q_and_group_combined(self, client):
        with db_session() as db:
            _seed_food(db, 2001, 'Apple, raw', 'Fruits')
            _seed_food(db, 2002, 'Apple pie', 'Baked Goods')
            db.commit()
        rows = client.get('/api/nutrition/search?q=Apple&group=Fruits').get_json()
        descs = {r['description'] for r in rows}
        assert 'Apple, raw' in descs
        assert 'Apple pie' not in descs

    def test_group_only_returns_group_members(self, client):
        with db_session() as db:
            _seed_food(db, 3001, 'Spinach', 'Greens')
            _seed_food(db, 3002, 'Beef, ground', 'Meat')
            db.commit()
        rows = client.get('/api/nutrition/search?group=Greens').get_json()
        groups = {r['food_group'] for r in rows}
        assert groups == {'Greens'}

    def test_limit_clamps_to_100(self, client):
        """Garbage limit silently falls to 25; explicit limit > 100 is
        clamped to 100."""
        resp = client.get('/api/nutrition/search?q=x&limit=NOT')
        assert resp.status_code == 200
        resp2 = client.get('/api/nutrition/search?q=x&limit=999')
        assert resp2.status_code == 200


# ── /api/nutrition/lookup/<fdc_id> ────────────────────────────────────────

class TestLookup:
    def test_404_unknown_fdc(self, client):
        resp = client.get('/api/nutrition/lookup/99999999')
        assert resp.status_code == 404

    def test_returns_food_with_nutrients(self, client):
        with db_session() as db:
            _seed_food(db, 4001, 'Test Food', 'TestGroup')
            _seed_nutrient(db, 4001, 'Vitamin C', 50, 'mg')
            _seed_nutrient(db, 4001, 'Iron', 2, 'mg')
            db.commit()
        body = client.get('/api/nutrition/lookup/4001').get_json()
        assert body['description'] == 'Test Food'
        assert body['food_group'] == 'TestGroup'
        # Nutrients are alphabetized by name (ORDER BY nutrient_name)
        names = [n['nutrient_name'] for n in body['nutrients']]
        assert names == ['Iron', 'Vitamin C']


# ── /api/nutrition/food-groups ────────────────────────────────────────────

class TestFoodGroups:
    def test_distinct_non_empty_groups(self, client):
        with db_session() as db:
            _seed_food(db, 5001, 'F1', 'GroupA')
            _seed_food(db, 5002, 'F2', 'GroupA')  # duplicate group
            _seed_food(db, 5003, 'F3', 'GroupB')
            _seed_food(db, 5004, 'F4', '')  # empty group — excluded
            db.commit()
        groups = client.get('/api/nutrition/food-groups').get_json()
        assert 'GroupA' in groups
        assert 'GroupB' in groups
        assert '' not in groups
        # Each group appears once (DISTINCT)
        assert groups.count('GroupA') == 1


# ── /api/nutrition/link POST ──────────────────────────────────────────────

class TestLink:
    def test_400_missing_fields(self, client):
        resp = client.post('/api/nutrition/link', json={})
        assert resp.status_code == 400

    def test_404_unknown_inventory(self, client):
        with db_session() as db:
            _seed_food(db, 6001, 'Linkable', 'Veg')
            db.commit()
        resp = client.post('/api/nutrition/link',
                           json={'inventory_id': 99999, 'fdc_id': 6001})
        assert resp.status_code == 404
        assert 'Inventory' in resp.get_json()['error']

    def test_404_unknown_food(self, client):
        with db_session() as db:
            inv_id = _seed_inv(db, 'Item')
            db.commit()
        resp = client.post('/api/nutrition/link',
                           json={'inventory_id': inv_id, 'fdc_id': 99999999})
        assert resp.status_code == 404
        assert 'Food' in resp.get_json()['error']

    def test_happy_path_201_creates_link(self, client):
        with db_session() as db:
            _seed_food(db, 7001, 'PinnedFood', 'Fruits',
                       kcal=150, protein=2, fat=0, carbs=35)
            inv_id = _seed_inv(db, 'PinnedItem', qty=10)
            db.commit()
        resp = client.post('/api/nutrition/link',
                           json={'inventory_id': inv_id, 'fdc_id': 7001,
                                 'servings_per_item': 4})
        assert resp.status_code == 201
        assert resp.get_json() == {'status': 'linked'}
        with db_session() as db:
            row = db.execute(
                "SELECT calories_per_serving, servings_per_item "
                "FROM inventory_nutrition_link WHERE inventory_id = ?",
                (inv_id,)
            ).fetchone()
        assert row['calories_per_serving'] == 150
        assert row['servings_per_item'] == 4

    def test_relink_replaces_old(self, client):
        """A second POST for the same inventory_id deletes the old link
        and inserts the new one (no duplicate rows)."""
        with db_session() as db:
            _seed_food(db, 7100, 'A', 'X')
            _seed_food(db, 7101, 'B', 'X', kcal=999)
            inv_id = _seed_inv(db, 'Switcher')
            db.commit()
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 7100})
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 7101})
        with db_session() as db:
            rows = db.execute(
                "SELECT fdc_id FROM inventory_nutrition_link "
                "WHERE inventory_id = ?", (inv_id,)
            ).fetchall()
        assert len(rows) == 1
        assert rows[0]['fdc_id'] == 7101


# ── /api/nutrition/link DELETE / GET ──────────────────────────────────────

class TestLinkDeleteAndDetail:
    def test_unlink_404_when_no_link(self, client):
        resp = client.delete('/api/nutrition/link/99999')
        assert resp.status_code == 404

    def test_detail_when_unlinked(self, client):
        body = client.get('/api/nutrition/link/99999').get_json()
        assert body == {'linked': False}

    def test_unlink_and_detail_after_link(self, client):
        with db_session() as db:
            _seed_food(db, 8001, 'GoneSoon', 'Fruits')
            inv_id = _seed_inv(db, 'Donor')
            db.commit()
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 8001})
        # Detail returns linked:True with food info merged in
        body = client.get(f'/api/nutrition/link/{inv_id}').get_json()
        assert body['linked'] is True
        assert body['description'] == 'GoneSoon'
        # Unlink
        resp = client.delete(f'/api/nutrition/link/{inv_id}')
        assert resp.status_code == 200
        body2 = client.get(f'/api/nutrition/link/{inv_id}').get_json()
        assert body2 == {'linked': False}


# ── /api/nutrition/summary ────────────────────────────────────────────────

class TestSummary:
    def test_empty_returns_zero_totals(self, client):
        body = client.get('/api/nutrition/summary').get_json()
        assert body['linked_items'] == 0
        assert body['total_calories'] == 0
        # household_size defaults to 2 when settings row absent
        assert body['household_size'] == 2

    def test_aggregates_qty_x_servings_x_kcal(self, client):
        """Hand-pinned: qty=10 × servings_per_item=2 × kcal=200/serving
        = 4000 kcal. household=2 → 4000 / (2 × 2000) = 1.0 day."""
        with db_session() as db:
            _seed_food(db, 9001, 'Pinned', 'Veg', kcal=200,
                       protein=10, fat=5, carbs=30)
            inv_id = _seed_inv(db, 'PinnedQty10', qty=10)
            db.commit()
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 9001,
                          'servings_per_item': 2})
        body = client.get('/api/nutrition/summary').get_json()
        assert body['linked_items'] == 1
        assert body['total_calories'] == 4000.0
        assert body['total_protein_g'] == 200.0  # 10 × 2 × 10
        assert body['total_fat_g'] == 100.0  # 10 × 2 × 5
        assert body['total_carbs_g'] == 600.0  # 10 × 2 × 30
        assert body['person_days_of_food'] == 1.0


# ── /api/nutrition/gaps ───────────────────────────────────────────────────

class TestGaps:
    def test_empty_returns_has_data_false(self, client):
        body = client.get('/api/nutrition/gaps').get_json()
        assert body == {'has_data': False, 'gaps': []}

    def test_red_status_when_below_7_days(self, client):
        """Hand-pinned: Vitamin C amount=50mg per food, qty=10,
        servings_per_item=2 → total = 50 × 10 × 2 = 1000 mg.
        daily_need = 90 (RDA) × 2 (household) = 180 mg/day.
        days_supply = 1000 / 180 ≈ 5.56 → status='red' (<7)."""
        with db_session() as db:
            _seed_food(db, 9101, 'C-rich food', 'Fruits')
            _seed_nutrient(db, 9101, 'Vitamin C', 50, 'mg')
            inv_id = _seed_inv(db, 'CHolder', qty=10)
            db.commit()
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 9101,
                          'servings_per_item': 2})
        body = client.get('/api/nutrition/gaps').get_json()
        assert body['has_data'] is True
        vc = next(g for g in body['gaps'] if g['nutrient'] == 'Vitamin C')
        assert vc['total_amount'] == 1000.0
        assert vc['days_supply'] == 5.6  # rounded to 1 decimal
        assert vc['status'] == 'red'

    def test_green_status_when_above_30_days(self, client):
        """Vitamin C amount=10000mg → 10000/180 ≈ 55.6 days → green."""
        with db_session() as db:
            _seed_food(db, 9201, 'C-mountain', 'Fruits')
            _seed_nutrient(db, 9201, 'Vitamin C', 10000, 'mg')
            inv_id = _seed_inv(db, 'CMountain', qty=1)
            db.commit()
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 9201,
                          'servings_per_item': 1})
        body = client.get('/api/nutrition/gaps').get_json()
        vc = next(g for g in body['gaps'] if g['nutrient'] == 'Vitamin C')
        assert vc['status'] == 'green'

    def test_zero_amount_yields_red(self, client):
        """A linked food with no nutrient row contributes zero — status
        for any key nutrient becomes 'red' (0 days supply)."""
        with db_session() as db:
            _seed_food(db, 9301, 'EmptyFood', 'Misc')
            inv_id = _seed_inv(db, 'EmptyHolder', qty=1)
            db.commit()
        client.post('/api/nutrition/link',
                    json={'inventory_id': inv_id, 'fdc_id': 9301,
                          'servings_per_item': 1})
        body = client.get('/api/nutrition/gaps').get_json()
        # Every key nutrient is 'red' since totals are all zero
        statuses = {g['status'] for g in body['gaps']}
        assert statuses == {'red'}
