"""Smoke tests for land_assessment blueprint routes.

Covers: properties CRUD, property assessments (+seed + weighted score
recalc), property features, development plans, BOL comparison
aggregator, properties summary, criteria-defaults reference.

Pattern matches tests/test_blueprint_agriculture.py: one class per
resource, happy-path CRUD + 400/404 guards + specialty endpoints
that aggregate or compute.

Closes the land_assessment coverage gap flagged during the V8-04 / H-17
template migration earlier this session. `web/blueprints/land_assessment.py`
is 465 LOC with 21 routes and zero prior tests.
"""


# ── PROPERTIES ────────────────────────────────────────────────────────────

class TestProperties:
    def test_list_empty(self, client):
        resp = client.get('/api/properties')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_property(self, client):
        resp = client.post('/api/properties', json={
            'name': 'North Ridge', 'property_type': 'rural',
            'state': 'MT', 'acreage': 40, 'ownership': 'owned',
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'North Ridge'
        assert body['acreage'] == 40

    def test_create_requires_name(self, client):
        assert client.post('/api/properties', json={}).status_code == 400

    def test_get_property(self, client):
        pid = client.post('/api/properties', json={'name': 'P1'}).get_json()['id']
        resp = client.get(f'/api/properties/{pid}')
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'P1'

    def test_get_404(self, client):
        assert client.get('/api/properties/999999').status_code == 404

    def test_update_property(self, client):
        pid = client.post('/api/properties', json={'name': 'P2'}).get_json()['id']
        resp = client.put(f'/api/properties/{pid}',
                          json={'status': 'under_contract', 'acreage': 80})
        assert resp.status_code == 200
        assert resp.get_json()['acreage'] == 80

    def test_update_404(self, client):
        assert client.put('/api/properties/999999',
                          json={'status': 'owned'}).status_code == 404

    def test_update_empty_400(self, client):
        pid = client.post('/api/properties', json={'name': 'P3'}).get_json()['id']
        assert client.put(f'/api/properties/{pid}', json={}).status_code == 400

    def test_delete_property(self, client):
        pid = client.post('/api/properties', json={'name': 'DelMe'}).get_json()['id']
        assert client.delete(f'/api/properties/{pid}').status_code == 200
        assert client.delete(f'/api/properties/{pid}').status_code == 404

    def test_list_filter_by_status(self, client):
        client.post('/api/properties', json={'name': 'O1', 'status': 'owned'})
        client.post('/api/properties', json={'name': 'P1', 'status': 'prospect'})
        owned = client.get('/api/properties?status=owned').get_json()
        names = {p['name'] for p in owned}
        assert 'O1' in names
        assert 'P1' not in names


# ── ASSESSMENTS ───────────────────────────────────────────────────────────

class TestAssessments:
    def test_list_empty_assessments(self, client):
        pid = client.post('/api/properties', json={'name': 'A1'}).get_json()['id']
        resp = client.get(f'/api/properties/{pid}/assessments')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_seed_default_criteria(self, client):
        pid = client.post('/api/properties', json={'name': 'Seed'}).get_json()['id']
        resp = client.post(f'/api/properties/{pid}/assessments/seed')
        assert resp.status_code == 200
        # 23 canonical criteria defined in DEFAULT_CRITERIA
        assert resp.get_json()['seeded'] == 23
        # Re-seed is idempotent
        resp2 = client.post(f'/api/properties/{pid}/assessments/seed')
        assert resp2.get_json()['seeded'] == 0
        listing = client.get(f'/api/properties/{pid}/assessments').get_json()
        assert len(listing) == 23

    def test_create_assessment(self, client):
        pid = client.post('/api/properties', json={'name': 'AssessHost'}).get_json()['id']
        resp = client.post(f'/api/properties/{pid}/assessments', json={
            'criterion': 'Custom criterion', 'category': 'water',
            'score': 8, 'weight': 1.5,
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['criterion'] == 'Custom criterion'
        assert body['score'] == 8

    def test_create_requires_criterion(self, client):
        pid = client.post('/api/properties', json={'name': 'X'}).get_json()['id']
        assert client.post(f'/api/properties/{pid}/assessments',
                           json={}).status_code == 400

    def test_update_assessment(self, client):
        pid = client.post('/api/properties', json={'name': 'U'}).get_json()['id']
        aid = client.post(f'/api/properties/{pid}/assessments',
                          json={'criterion': 'C1', 'score': 3}).get_json()['id']
        resp = client.put(f'/api/property-assessments/{aid}', json={'score': 9})
        assert resp.status_code == 200
        assert resp.get_json()['score'] == 9

    def test_update_404(self, client):
        assert client.put('/api/property-assessments/999999',
                          json={'score': 7}).status_code == 404

    def test_update_empty_400(self, client):
        pid = client.post('/api/properties', json={'name': 'E'}).get_json()['id']
        aid = client.post(f'/api/properties/{pid}/assessments',
                          json={'criterion': 'C'}).get_json()['id']
        assert client.put(f'/api/property-assessments/{aid}', json={}).status_code == 400

    def test_delete_assessment(self, client):
        pid = client.post('/api/properties', json={'name': 'D'}).get_json()['id']
        aid = client.post(f'/api/properties/{pid}/assessments',
                          json={'criterion': 'DelC'}).get_json()['id']
        assert client.delete(f'/api/property-assessments/{aid}').status_code == 200


# ── WEIGHTED SCORE ────────────────────────────────────────────────────────

class TestWeightedScore:
    def test_score_empty_property(self, client):
        """Property with no assessments returns zero totals (no division)."""
        pid = client.post('/api/properties', json={'name': 'NoAssess'}).get_json()['id']
        resp = client.post(f'/api/properties/{pid}/score')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['total_score'] == 0
        assert body['max_possible'] == 0
        assert body['percentage'] == 0

    def test_score_weighted_math(self, client):
        """Verify the weighted-score formula against a hand-computed case.

        Two criteria: score=8/weight=2 + score=6/weight=1
          weighted_sum = 8*2 + 6*1 = 22
          max_possible = 10*2 + 10*1 = 30
          percentage   = 22/30 = 73.3%
          total_score  = (22/30)*10 = 7.33
        """
        pid = client.post('/api/properties', json={'name': 'Math'}).get_json()['id']
        client.post(f'/api/properties/{pid}/assessments',
                    json={'criterion': 'A', 'score': 8, 'weight': 2.0})
        client.post(f'/api/properties/{pid}/assessments',
                    json={'criterion': 'B', 'score': 6, 'weight': 1.0})
        resp = client.post(f'/api/properties/{pid}/score')
        body = resp.get_json()
        assert body['criteria_count'] == 2
        assert body['weighted_sum'] == 22.0
        assert body['max_possible'] == 30.0
        assert body['percentage'] == 73.3
        # 7.33 rounds with floating point; tolerate ±0.01
        assert abs(body['total_score'] - 7.33) < 0.01
        # Persisted back on the property record
        prop = client.get(f'/api/properties/{pid}').get_json()
        assert abs(prop['total_score'] - 7.33) < 0.01

    def test_score_perfect_10(self, client):
        """All criteria maxed → total_score=10.0, percentage=100."""
        pid = client.post('/api/properties', json={'name': 'Perfect'}).get_json()['id']
        client.post(f'/api/properties/{pid}/assessments',
                    json={'criterion': 'A', 'score': 10, 'weight': 1.0})
        client.post(f'/api/properties/{pid}/assessments',
                    json={'criterion': 'B', 'score': 10, 'weight': 1.5})
        body = client.post(f'/api/properties/{pid}/score').get_json()
        assert body['total_score'] == 10.0
        assert body['percentage'] == 100.0


# ── PROPERTY FEATURES ─────────────────────────────────────────────────────

class TestPropertyFeatures:
    def test_features_crud(self, client):
        pid = client.post('/api/properties', json={'name': 'F1'}).get_json()['id']
        resp = client.post(f'/api/properties/{pid}/features', json={
            'name': 'Well #1', 'feature_type': 'well',
            'condition': 'good', 'value_estimate': 5000,
        })
        assert resp.status_code == 201
        fid = resp.get_json()['id']
        listing = client.get(f'/api/properties/{pid}/features').get_json()
        assert any(f['id'] == fid for f in listing)
        assert client.delete(f'/api/property-features/{fid}').status_code == 200

    def test_features_create_requires_name(self, client):
        pid = client.post('/api/properties', json={'name': 'F2'}).get_json()['id']
        assert client.post(f'/api/properties/{pid}/features',
                           json={}).status_code == 400


# ── DEVELOPMENT PLANS ─────────────────────────────────────────────────────

class TestDevelopmentPlans:
    def test_plans_crud(self, client):
        pid = client.post('/api/properties', json={'name': 'PL'}).get_json()['id']
        resp = client.post(f'/api/properties/{pid}/plans', json={
            'name': 'Build barn', 'category': 'infrastructure',
            'priority': 'high', 'estimated_cost': 12000, 'impact_score': 8,
        })
        assert resp.status_code == 201
        did = resp.get_json()['id']
        resp2 = client.put(f'/api/development-plans/{did}',
                           json={'status': 'in_progress', 'actual_cost': 8000})
        assert resp2.status_code == 200
        assert resp2.get_json()['status'] == 'in_progress'
        assert client.delete(f'/api/development-plans/{did}').status_code == 200

    def test_plans_create_requires_name(self, client):
        pid = client.post('/api/properties', json={'name': 'PL2'}).get_json()['id']
        assert client.post(f'/api/properties/{pid}/plans',
                           json={}).status_code == 400

    def test_plans_update_404(self, client):
        assert client.put('/api/development-plans/999999',
                          json={'status': 'done'}).status_code == 404

    def test_plans_update_empty_400(self, client):
        pid = client.post('/api/properties', json={'name': 'PL3'}).get_json()['id']
        did = client.post(f'/api/properties/{pid}/plans',
                          json={'name': 'x'}).get_json()['id']
        assert client.put(f'/api/development-plans/{did}',
                          json={}).status_code == 400


# ── COMPARISON / SUMMARY / REFERENCE ──────────────────────────────────────

class TestComparisonAndSummary:
    def test_compare_includes_category_scores_and_counts(self, client):
        """BOL comparison aggregates per-property: category_scores (weighted
        mean per category), features_count, plans_count, total_dev_cost.
        Verify against a two-property scenario."""
        p1 = client.post('/api/properties',
                         json={'name': 'CmpA'}).get_json()['id']
        # Two water-category scores, 8/wt=2 and 6/wt=1 → (16+6)/3 = 7.33
        client.post(f'/api/properties/{p1}/assessments',
                    json={'criterion': 'W1', 'category': 'water',
                          'score': 8, 'weight': 2})
        client.post(f'/api/properties/{p1}/assessments',
                    json={'criterion': 'W2', 'category': 'water',
                          'score': 6, 'weight': 1})
        # One feature, one plan with $500 cost
        client.post(f'/api/properties/{p1}/features',
                    json={'name': 'Well', 'feature_type': 'well'})
        client.post(f'/api/properties/{p1}/plans',
                    json={'name': 'Fence', 'estimated_cost': 500})
        # Second property is sparse
        client.post('/api/properties', json={'name': 'CmpB'})
        cmp_rows = client.get('/api/properties/compare').get_json()
        by_name = {r['name']: r for r in cmp_rows}
        assert 'CmpA' in by_name and 'CmpB' in by_name
        a = by_name['CmpA']
        assert a['features_count'] == 1
        assert a['plans_count'] == 1
        assert a['total_dev_cost'] == 500
        # Weighted water avg: (8*2 + 6*1)/(2+1) = 22/3 = 7.33 → rounded to 7.3
        assert a['category_scores']['water'] == 7.3
        # CmpB has no assessments → category_scores is {}
        assert by_name['CmpB']['category_scores'] == {}

    def test_summary_empty_and_populated(self, client):
        empty = client.get('/api/properties/summary').get_json()
        # total_properties may reflect seeded data; snapshot before seeding
        base_total = empty['total_properties']
        base_features = empty['total_features']
        base_plans = empty['total_dev_plans']
        pid = client.post('/api/properties',
                          json={'name': 'SumHost', 'ownership': 'owned'}
                          ).get_json()['id']
        client.post(f'/api/properties/{pid}/features',
                    json={'name': 'Shed', 'feature_type': 'shed'})
        client.post(f'/api/properties/{pid}/plans',
                    json={'name': 'Road', 'status': 'in_progress'})
        later = client.get('/api/properties/summary').get_json()
        assert later['total_properties'] == base_total + 1
        assert later['owned'] >= 1
        assert later['total_features'] == base_features + 1
        assert later['total_dev_plans'] == base_plans + 1
        assert later['active_dev_plans'] >= 1

    def test_criteria_defaults_shape(self, client):
        resp = client.get('/api/properties/criteria-defaults')
        assert resp.status_code == 200
        rows = resp.get_json()
        # 23 canonical criteria
        assert len(rows) == 23
        # Every row has the expected shape
        for r in rows:
            assert 'criterion' in r and 'category' in r and 'weight' in r
        # Spot-check: 'Water availability' is in the water category with weight 1.5
        water_rows = [r for r in rows if r['category'] == 'water']
        assert any(r['criterion'] == 'Water availability' and r['weight'] == 1.5
                   for r in water_rows)
