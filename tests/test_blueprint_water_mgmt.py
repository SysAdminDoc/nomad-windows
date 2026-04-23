"""Tests for the water-management blueprint: storage / filters / sources
/ quality CRUD, dashboard aggregate, budget calculators, purification
reference, summary, filter-alerts, and the detailed water budget with
self-seeding default categories."""


def _make_storage(client, **overrides):
    body = {
        'name':              overrides.pop('name', '55-gal drum'),
        'capacity_gallons':  overrides.pop('capacity_gallons', 55),
        'current_gallons':   overrides.pop('current_gallons', 55),
        'location':          overrides.pop('location', 'garage'),
    }
    body.update(overrides)
    resp = client.post('/api/water/storage', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_filter(client, **overrides):
    body = {
        'name':              overrides.pop('name', 'Berkey'),
        'filter_type':       overrides.pop('filter_type', 'gravity'),
        'max_gallons':       overrides.pop('max_gallons', 3000),
        'gallons_processed': overrides.pop('gallons_processed', 0),
    }
    body.update(overrides)
    resp = client.post('/api/water/filters', json=body)
    assert resp.status_code == 201
    return resp.get_json()


def _make_source(client, **overrides):
    body = {
        'name':         overrides.pop('name', 'Creek'),
        'source_type':  overrides.pop('source_type', 'stream'),
        'potable':      overrides.pop('potable', False),
    }
    body.update(overrides)
    resp = client.post('/api/water/sources', json=body)
    assert resp.status_code == 201
    return resp.get_json()


class TestWaterStorage:
    def test_list_empty(self, client):
        assert client.get('/api/water/storage').get_json() == []

    def test_create_requires_name(self, client):
        resp = client.post('/api/water/storage', json={'capacity_gallons': 55})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        _make_storage(client)
        rows = client.get('/api/water/storage').get_json()
        assert len(rows) == 1
        assert rows[0]['name'] == '55-gal drum'
        assert rows[0]['current_gallons'] == 55

    def test_filter_by_location(self, client):
        _make_storage(client, name='garage-1', location='garage')
        _make_storage(client, name='basement-1', location='basement')
        garage = client.get('/api/water/storage?location=garage').get_json()
        assert [r['name'] for r in garage] == ['garage-1']

    def test_update(self, client):
        _make_storage(client)
        sid = client.get('/api/water/storage').get_json()[0]['id']
        resp = client.put(f'/api/water/storage/{sid}',
                          json={'current_gallons': 40})
        assert resp.status_code == 200
        updated = client.get('/api/water/storage').get_json()[0]
        assert updated['current_gallons'] == 40

    def test_update_404(self, client):
        resp = client.put('/api/water/storage/99999', json={'current_gallons': 1})
        assert resp.status_code == 404

    def test_update_empty_body(self, client):
        _make_storage(client)
        sid = client.get('/api/water/storage').get_json()[0]['id']
        resp = client.put(f'/api/water/storage/{sid}', json={})
        assert resp.status_code == 400

    def test_delete(self, client):
        _make_storage(client)
        sid = client.get('/api/water/storage').get_json()[0]['id']
        assert client.delete(f'/api/water/storage/{sid}').status_code == 200
        assert client.get('/api/water/storage').get_json() == []

    def test_delete_404(self, client):
        assert client.delete('/api/water/storage/99999').status_code == 404


class TestWaterFilters:
    def test_create_requires_name(self, client):
        resp = client.post('/api/water/filters', json={'filter_type': 'gravity'})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        _make_filter(client)
        rows = client.get('/api/water/filters').get_json()
        assert len(rows) == 1
        assert rows[0]['name'] == 'Berkey'

    def test_update(self, client):
        _make_filter(client)
        fid = client.get('/api/water/filters').get_json()[0]['id']
        resp = client.put(f'/api/water/filters/{fid}',
                          json={'gallons_processed': 1500})
        assert resp.status_code == 200
        assert client.get('/api/water/filters').get_json()[0]['gallons_processed'] == 1500

    def test_update_404(self, client):
        assert client.put('/api/water/filters/99999',
                          json={'gallons_processed': 1}).status_code == 404

    def test_delete(self, client):
        _make_filter(client)
        fid = client.get('/api/water/filters').get_json()[0]['id']
        assert client.delete(f'/api/water/filters/{fid}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/water/filters/99999').status_code == 404


class TestWaterSources:
    def test_create_requires_name(self, client):
        resp = client.post('/api/water/sources',
                           json={'source_type': 'well'})
        assert resp.status_code == 400

    def test_create_normalizes_bool_fields(self, client):
        _make_source(client, potable='yes', treatment_required=False, seasonal=1)
        rows = client.get('/api/water/sources').get_json()
        assert rows[0]['potable'] == 1
        assert rows[0]['treatment_required'] == 0
        assert rows[0]['seasonal'] == 1

    def test_update_normalizes_bool_fields(self, client):
        _make_source(client)
        sid = client.get('/api/water/sources').get_json()[0]['id']
        resp = client.put(f'/api/water/sources/{sid}',
                          json={'potable': True, 'seasonal': False})
        assert resp.status_code == 200
        row = client.get('/api/water/sources').get_json()[0]
        assert row['potable'] == 1
        assert row['seasonal'] == 0

    def test_update_404(self, client):
        assert client.put('/api/water/sources/99999',
                          json={'potable': True}).status_code == 404

    def test_delete(self, client):
        _make_source(client)
        sid = client.get('/api/water/sources').get_json()[0]['id']
        assert client.delete(f'/api/water/sources/{sid}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/water/sources/99999').status_code == 404


class TestWaterQuality:
    def test_create_requires_source_id(self, client):
        resp = client.post('/api/water/quality', json={'ph': 7.0})
        assert resp.status_code == 400

    def test_create_validates_source_exists(self, client):
        resp = client.post('/api/water/quality',
                           json={'source_id': 99999, 'ph': 7.0})
        assert resp.status_code == 404

    def test_create_and_list(self, client):
        _make_source(client)
        sid = client.get('/api/water/sources').get_json()[0]['id']
        resp = client.post('/api/water/quality', json={
            'source_id': sid, 'ph': 7.2, 'tds_ppm': 150, 'coliform': False,
        })
        assert resp.status_code == 201
        rows = client.get('/api/water/quality').get_json()
        assert len(rows) == 1
        assert rows[0]['ph'] == 7.2
        # NOTE: `water_quality_tests.coliform` is declared TEXT in db.py but
        # the blueprint writes an integer boolean. SQLite's TEXT affinity
        # coerces on insert, so the value comes back as the string '0' / '1'.
        # This is a schema/code mismatch worth fixing in a dedicated
        # migration pass; for now the test tolerates either representation.
        assert rows[0]['coliform'] in (0, '0', False, '')
        # source_name joined in
        assert rows[0]['source_name'] == 'Creek'

    def test_list_filter_by_source(self, client):
        _make_source(client, name='Creek A')
        _make_source(client, name='Creek B')
        sid_a = client.get('/api/water/sources').get_json()[0]['id']
        sid_b = client.get('/api/water/sources').get_json()[1]['id']
        client.post('/api/water/quality', json={'source_id': sid_a, 'ph': 6.5})
        client.post('/api/water/quality', json={'source_id': sid_b, 'ph': 7.5})
        only_a = client.get(f'/api/water/quality?source_id={sid_a}').get_json()
        assert len(only_a) == 1
        assert only_a[0]['ph'] == 6.5


class TestWaterDashboardAndSummary:
    def test_dashboard_empty(self, client):
        data = client.get('/api/water/dashboard').get_json()
        assert data['total_capacity'] == 0
        assert data['total_current'] == 0
        assert data['total_sources'] == 0
        assert data['filters_needing_replacement'] == 0
        assert data['latest_quality_tests'] == []
        # Default household size 4, 1 gal/person/day → 0 days
        assert data['days_of_water'] == 0

    def test_dashboard_computes_days_of_water(self, client, db):
        # Household size from settings defaults to 4 → 4 gal/day
        _make_storage(client, name='A', capacity_gallons=40, current_gallons=40)
        data = client.get('/api/water/dashboard').get_json()
        assert data['total_current'] == 40
        # 40 gal / (4 people * 1 gal/day) = 10 days
        assert data['days_of_water'] == 10.0

    def test_dashboard_flags_filters_over_80_percent(self, client):
        _make_filter(client, name='Old', max_gallons=1000, gallons_processed=900)
        _make_filter(client, name='Fresh', max_gallons=1000, gallons_processed=100)
        data = client.get('/api/water/dashboard').get_json()
        assert data['filters_needing_replacement'] == 1

    def test_summary(self, client):
        _make_storage(client, capacity_gallons=55, current_gallons=20)
        _make_filter(client)
        _make_source(client)
        data = client.get('/api/water/summary').get_json()
        assert data['total_gallons_stored'] == 20
        assert data['filter_count'] == 1
        assert data['source_count'] == 1
        assert data['days_of_water_estimate'] == 5.0  # 20 / (4 * 1)


class TestWaterBudgetCalculators:
    def test_simple_budget_math(self, client):
        data = client.get('/api/water/budget?people=4&days=14').get_json()
        assert data['people'] == 4
        assert data['days'] == 14
        assert data['breakdown']['drinking'] == 28.0   # 0.5 * 4 * 14
        assert data['breakdown']['cooking'] == 14.0    # 0.25 * 4 * 14
        assert data['breakdown']['hygiene'] == 14.0
        assert data['breakdown']['medical'] == 5.6     # 0.1 * 4 * 14
        assert data['total_needed'] == 61.6

    def test_budget_reports_surplus_vs_deficit(self, client):
        data = client.get('/api/water/budget?people=4&days=14').get_json()
        assert data['status'] == 'deficit'  # 0 stored vs 61.6 needed

        _make_storage(client, capacity_gallons=100, current_gallons=100)
        data2 = client.get('/api/water/budget?people=4&days=14').get_json()
        assert data2['total_available'] == 100
        assert data2['status'] == 'surplus'

    def test_budget_handles_bad_query_params(self, client):
        data = client.get('/api/water/budget?people=all&days=lots').get_json()
        assert data['people'] == 4
        assert data['days'] == 14

    def test_budget_detailed_seeds_defaults_on_first_access(self, client):
        data = client.get('/api/water/budget/detailed').get_json()
        cats = {c['category'] for c in data['categories']}
        assert {'drinking', 'cooking', 'hygiene', 'medical'}.issubset(cats)
        assert data['household_size'] == 4
        assert data['total_daily_gallons'] > 0

    def test_budget_detailed_is_idempotent(self, client):
        first = client.get('/api/water/budget/detailed').get_json()
        second = client.get('/api/water/budget/detailed').get_json()
        assert len(first['categories']) == len(second['categories'])

    def test_budget_update_requires_id(self, client):
        resp = client.post('/api/water/budget', json={'daily_gallons': 0.75})
        assert resp.status_code == 400

    def test_budget_update_404(self, client):
        resp = client.post('/api/water/budget',
                           json={'id': 99999, 'daily_gallons': 0.75})
        assert resp.status_code == 404

    def test_budget_update_roundtrip(self, client):
        # Seed defaults first so there is a row to update
        data = client.get('/api/water/budget/detailed').get_json()
        drinking = next(c for c in data['categories'] if c['category'] == 'drinking')
        resp = client.post('/api/water/budget', json={
            'id': drinking['id'], 'daily_gallons': 1.0,
        })
        assert resp.status_code == 200
        after = client.get('/api/water/budget/detailed').get_json()
        updated = next(c for c in after['categories'] if c['category'] == 'drinking')
        assert updated['daily_gallons'] == 1.0

    def test_budget_add_new_category(self, client):
        resp = client.post('/api/water/budget/add', json={
            'category': 'livestock', 'daily_gallons': 2.5, 'per_person': False,
        })
        assert resp.status_code == 201
        data = client.get('/api/water/budget/detailed').get_json()
        assert any(c['category'] == 'livestock' for c in data['categories'])

    def test_budget_add_requires_category(self, client):
        resp = client.post('/api/water/budget/add', json={'daily_gallons': 1})
        assert resp.status_code == 400


class TestWaterPurificationReference:
    def test_purification_reference_payload_shape(self, client):
        # CE-19 (v7.61): response is now a dict {methods: [...], boil_times,
        # bleach_dosing, iodine_dosing, ...}. Each method row preserves the
        # legacy method / instructions / kills / limitations keys alongside
        # richer fields (removes, does_not_remove, equipment, time_to_treat).
        data = client.get('/api/water/purification-reference').get_json()
        assert isinstance(data, dict)
        methods_list = data['methods']
        assert isinstance(methods_list, list)
        assert len(methods_list) >= 5
        for entry in methods_list:
            assert 'method' in entry
            assert 'instructions' in entry
            assert 'kills' in entry
            assert 'limitations' in entry
        methods = {e['method'] for e in methods_list}
        # v7.61 renamed methods to richer labels — match by prefix.
        assert any(m.lower().startswith(('boil', 'rolling boil')) for m in methods)


class TestWaterFilterAlerts:
    def test_no_alerts_when_filters_fresh(self, client):
        _make_filter(client, name='Fresh', max_gallons=1000, gallons_processed=100)
        assert client.get('/api/water/filter-alerts').get_json() == []

    def test_warning_vs_critical_thresholds(self, client):
        _make_filter(client, name='Warning', max_gallons=1000, gallons_processed=850)   # 85%
        _make_filter(client, name='Critical', max_gallons=1000, gallons_processed=960)  # 96%
        alerts = client.get('/api/water/filter-alerts').get_json()
        by_name = {a['name']: a for a in alerts}
        assert by_name['Critical']['status'] == 'critical'
        assert by_name['Warning']['status'] == 'warning'
        # Sorted by percent_used DESC
        assert alerts[0]['name'] == 'Critical'
