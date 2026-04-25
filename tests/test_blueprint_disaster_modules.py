"""Smoke tests for disaster_modules blueprint routes.

Covers: disaster plans (+reference), disaster checklists (+seed + auto
percent/status), energy systems (+summary aggregator), construction
projects (+materials drill-down), building materials (+low-stock
trigger), fortifications (+assessment aggregator with condition scoring),
heating calculator, sandbag calculator, disaster summary dashboard.

Pattern matches tests/test_blueprint_agriculture.py: one class per
resource, happy-path CRUD + 400/404 guards + the specialty endpoints
that aggregate or compute.
"""

# ── DISASTER PLANS ────────────────────────────────────────────────────────

class TestDisasterPlans:
    def test_list_empty(self, client):
        resp = client.get('/api/disaster/plans')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_plan(self, client):
        resp = client.post('/api/disaster/plans', json={
            'name': 'Quake Plan',
            'disaster_type': 'earthquake',
            'environment_type': 'urban',
            'immediate_actions': ['Drop/Cover/Hold', 'Assess injuries'],
            'resources_required': ['helmet', 'whistle'],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'Quake Plan'
        assert body['immediate_actions'] == ['Drop/Cover/Hold', 'Assess injuries']

    def test_create_requires_name(self, client):
        assert client.post('/api/disaster/plans', json={}).status_code == 400

    def test_update_plan(self, client):
        pid = client.post('/api/disaster/plans', json={'name': 'P1'}).get_json()['id']
        resp = client.put(f'/api/disaster/plans/{pid}', json={'status': 'active'})
        assert resp.status_code == 200

    def test_update_404(self, client):
        assert client.put('/api/disaster/plans/999999',
                          json={'status': 'active'}).status_code == 404

    def test_update_empty_payload_400(self, client):
        pid = client.post('/api/disaster/plans', json={'name': 'Empty'}).get_json()['id']
        assert client.put(f'/api/disaster/plans/{pid}', json={}).status_code == 400

    def test_delete_plan(self, client):
        pid = client.post('/api/disaster/plans', json={'name': 'DelMe'}).get_json()['id']
        assert client.delete(f'/api/disaster/plans/{pid}').status_code == 200
        assert client.delete(f'/api/disaster/plans/{pid}').status_code == 404

    def test_reference_endpoint(self, client):
        resp = client.get('/api/disaster/plans/reference')
        assert resp.status_code == 200
        ref = resp.get_json()
        for key in ('earthquake', 'hurricane', 'tornado', 'wildfire', 'flood',
                    'pandemic', 'emp_solar', 'economic_collapse', 'volcanic', 'drought'):
            assert key in ref
            assert 'name' in ref[key]
            assert isinstance(ref[key]['key_actions'], list)


# ── DISASTER CHECKLISTS ───────────────────────────────────────────────────

class TestDisasterChecklists:
    def test_create_checklist_computes_pct(self, client):
        resp = client.post('/api/disaster/checklists', json={
            'title': 'Quake Pre-Event',
            'category': 'pre_event',
            'items': [
                {'item': 'Secure water', 'checked': True},
                {'item': 'Gas wrench', 'checked': True},
                {'item': 'Practice drill', 'checked': False},
            ],
        })
        assert resp.status_code == 201
        assert resp.get_json()['completion_pct'] == 66

    def test_create_requires_title(self, client):
        assert client.post('/api/disaster/checklists', json={}).status_code == 400

    def test_update_auto_computes_status_complete(self, client):
        cid = client.post('/api/disaster/checklists',
                          json={'title': 'Auto', 'items': [{'item': 'x', 'checked': False}]}
                          ).get_json()['id']
        resp = client.put(f'/api/disaster/checklists/{cid}',
                          json={'items': [{'item': 'x', 'checked': True}]})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['completion_pct'] == 100
        assert body['status'] == 'complete'

    def test_update_404(self, client):
        assert client.put('/api/disaster/checklists/999999',
                          json={'items': []}).status_code == 404

    def test_seed_creates_defaults(self, client):
        resp = client.post('/api/disaster/checklists/seed')
        assert resp.status_code in (200, 201)
        listing = client.get('/api/disaster/checklists').get_json()
        titles = {c['title'] for c in listing}
        assert any('Earthquake' in t for t in titles)
        assert any('Hurricane' in t for t in titles)
        client.post('/api/disaster/checklists/seed')
        listing2 = client.get('/api/disaster/checklists').get_json()
        assert len(listing2) == len(listing)

    def test_filter_by_category(self, client):
        client.post('/api/disaster/checklists',
                    json={'title': 'Pre', 'category': 'pre_event'})
        client.post('/api/disaster/checklists',
                    json={'title': 'During', 'category': 'during_event'})
        pre_only = client.get('/api/disaster/checklists?category=pre_event').get_json()
        titles = {c['title'] for c in pre_only}
        assert 'Pre' in titles
        assert 'During' not in titles


# ── ENERGY SYSTEMS ────────────────────────────────────────────────────────

class TestEnergySystems:
    def test_crud(self, client):
        resp = client.post('/api/disaster/energy', json={
            'name': 'Wood Stove', 'energy_type': 'wood',
            'location': 'Main cabin', 'condition': 'operational',
        })
        assert resp.status_code == 201
        eid = resp.get_json()['id']
        assert client.put(f'/api/disaster/energy/{eid}',
                          json={'condition': 'degraded'}).status_code == 200

    def test_create_requires_name(self, client):
        assert client.post('/api/disaster/energy', json={}).status_code == 400

    def test_update_404(self, client):
        assert client.put('/api/disaster/energy/999999',
                          json={'condition': 'operational'}).status_code == 404

    def test_summary_aggregates_by_type_and_condition(self, client):
        client.post('/api/disaster/energy',
                    json={'name': 'W1', 'energy_type': 'wood', 'condition': 'operational'})
        client.post('/api/disaster/energy',
                    json={'name': 'W2', 'energy_type': 'wood', 'condition': 'offline'})
        client.post('/api/disaster/energy',
                    json={'name': 'S1', 'energy_type': 'solar', 'condition': 'operational'})
        summary = client.get('/api/disaster/energy/summary').get_json()
        assert summary['wood']['total'] == 2
        assert summary['wood']['operational'] == 1
        assert summary['wood']['offline'] == 1
        assert summary['solar']['operational'] == 1


# ── CONSTRUCTION PROJECTS ─────────────────────────────────────────────────

class TestConstructionProjects:
    def test_crud(self, client):
        resp = client.post('/api/disaster/construction', json={
            'name': 'Root Cellar',
            'project_type': 'storage',
            'materials': [
                {'item': '2x4', 'qty': 20, 'acquired': True},
                {'item': 'plywood', 'qty': 6, 'acquired': False},
            ],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['materials'][0]['item'] == '2x4'
        cid = body['id']
        assert client.put(f'/api/disaster/construction/{cid}',
                          json={'status': 'in_progress'}).status_code == 200
        assert client.delete(f'/api/disaster/construction/{cid}').status_code == 200
        assert client.delete(f'/api/disaster/construction/{cid}').status_code == 404

    def test_create_requires_name(self, client):
        assert client.post('/api/disaster/construction', json={}).status_code == 400

    def test_materials_drill_down(self, client):
        cid = client.post('/api/disaster/construction', json={
            'name': 'Shed',
            'materials': [
                {'item': 'nails', 'qty': 1, 'acquired': True},
                {'item': 'screws', 'qty': 1, 'acquired': True},
                {'item': 'siding', 'qty': 1, 'acquired': False},
                {'item': 'roof', 'qty': 1, 'acquired': False},
            ],
        }).get_json()['id']
        resp = client.get(f'/api/disaster/construction/{cid}/materials')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['project'] == 'Shed'
        assert body['total_items'] == 4
        assert body['acquired'] == 2
        assert body['needed'] == 2
        assert body['completion_pct'] == 50

    def test_materials_drill_down_404(self, client):
        assert client.get('/api/disaster/construction/999999/materials').status_code == 404


# ── BUILDING MATERIALS ────────────────────────────────────────────────────

class TestBuildingMaterials:
    def test_create_and_low_stock(self, client):
        client.post('/api/disaster/materials', json={
            'name': 'Plywood Sheet', 'category': 'lumber',
            'quantity': 20, 'unit': 'sheet', 'min_stock': 5,
        })
        client.post('/api/disaster/materials', json={
            'name': 'Roofing Nails', 'category': 'fasteners',
            'quantity': 3, 'unit': 'lb', 'min_stock': 10,
        })
        low = client.get('/api/disaster/materials/low-stock').get_json()
        names = {m['name'] for m in low}
        assert 'Roofing Nails' in names
        assert 'Plywood Sheet' not in names

    def test_create_requires_name(self, client):
        assert client.post('/api/disaster/materials', json={}).status_code == 400

    def test_update_404(self, client):
        assert client.put('/api/disaster/materials/999999',
                          json={'quantity': 5}).status_code == 404

    def test_filter_by_category(self, client):
        client.post('/api/disaster/materials', json={'name': 'A', 'category': 'lumber'})
        client.post('/api/disaster/materials', json={'name': 'B', 'category': 'fasteners'})
        lumber_only = client.get('/api/disaster/materials?category=lumber').get_json()
        names = {m['name'] for m in lumber_only}
        assert 'A' in names
        assert 'B' not in names


# ── FORTIFICATIONS ────────────────────────────────────────────────────────

class TestFortifications:
    def test_crud(self, client):
        resp = client.post('/api/disaster/fortifications', json={
            'name': 'Safe Room A', 'fortification_type': 'safe_room',
            'protection_level': 'advanced', 'condition': 'good',
            'materials_used': ['steel door', 'concrete block'],
        })
        assert resp.status_code == 201
        fid = resp.get_json()['id']
        assert client.put(f'/api/disaster/fortifications/{fid}',
                          json={'status': 'operational'}).status_code == 200

    def test_create_requires_name(self, client):
        assert client.post('/api/disaster/fortifications', json={}).status_code == 400

    def test_assessment_empty_state(self, client):
        resp = client.get('/api/disaster/fortifications/assessment')
        assert resp.status_code == 200
        assert resp.get_json()['total'] == 0

    def test_assessment_condition_aggregates(self, client):
        client.post('/api/disaster/fortifications',
                    json={'name': 'Good1', 'condition': 'good',
                          'fortification_type': 'safe_room',
                          'protection_level': 'advanced'})
        client.post('/api/disaster/fortifications',
                    json={'name': 'Good2', 'condition': 'good',
                          'fortification_type': 'safe_room',
                          'protection_level': 'advanced'})
        client.post('/api/disaster/fortifications',
                    json={'name': 'Excellent1', 'condition': 'excellent',
                          'fortification_type': 'bunker',
                          'protection_level': 'max'})
        assess = client.get('/api/disaster/fortifications/assessment').get_json()
        assert assess['total'] == 3
        assert assess['by_type']['safe_room'] == 2
        assert assess['by_type']['bunker'] == 1
        assert assess['by_level']['advanced'] == 2
        assert assess['by_level']['max'] == 1
        # (good=3, good=3, excellent=4) / 3 = 3.33 → round = 3 → 'good'
        assert assess['avg_condition'] == 'good'


# ── CALCULATORS ───────────────────────────────────────────────────────────

class TestHeatingCalculator:
    def test_heating_happy_path(self, client):
        resp = client.get('/api/disaster/calculators/heating'
                          '?sq_ft=1500&insulation_rating=average'
                          '&target_temp=68&outside_temp=30')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['sq_ft'] == 1500
        assert body['delta_t'] == 38
        assert body['cords_needed'] > 0
        import math
        assert body['cords_rounded_up'] == math.ceil(body['cords_needed'])

    def test_heating_insulation_rating_lowers_demand(self, client):
        poor = client.get('/api/disaster/calculators/heating'
                          '?sq_ft=1500&insulation_rating=poor'
                          '&target_temp=68&outside_temp=30').get_json()
        excellent = client.get('/api/disaster/calculators/heating'
                               '?sq_ft=1500&insulation_rating=excellent'
                               '&target_temp=68&outside_temp=30').get_json()
        assert excellent['cords_needed'] < poor['cords_needed']

    def test_heating_delta_t_clamped_at_zero(self, client):
        resp = client.get('/api/disaster/calculators/heating'
                          '?sq_ft=1000&target_temp=60&outside_temp=75').get_json()
        assert resp['delta_t'] == 0
        assert resp['cords_needed'] == 0

    def test_heating_invalid_numeric(self, client):
        resp = client.get('/api/disaster/calculators/heating?sq_ft=notanumber')
        assert resp.status_code == 400


class TestSandbagCalculator:
    def test_sandbag_happy_path(self, client):
        resp = client.get('/api/disaster/calculators/sandbag'
                          '?wall_length_ft=100&wall_height_ft=3')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['courses'] == 6
        assert body['sandbags_needed'] == 960
        assert body['estimated_weight_lbs'] == 960 * 40

    def test_sandbag_invalid_numeric(self, client):
        resp = client.get('/api/disaster/calculators/sandbag?wall_length_ft=bogus')
        assert resp.status_code == 400


# ── SUMMARY ───────────────────────────────────────────────────────────────

class TestDisasterSummary:
    def test_summary_shape(self, client):
        resp = client.get('/api/disaster/summary')
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ('plans', 'checklists', 'energy', 'construction',
                    'materials', 'fortifications'):
            assert key in body
        assert 'total' in body['plans']

    def test_summary_reflects_seeded_data(self, client):
        client.post('/api/disaster/plans',
                    json={'name': 'P1', 'disaster_type': 'earthquake'})
        client.post('/api/disaster/plans',
                    json={'name': 'P2', 'disaster_type': 'earthquake'})
        client.post('/api/disaster/plans',
                    json={'name': 'P3', 'disaster_type': 'flood'})
        body = client.get('/api/disaster/summary').get_json()
        assert body['plans']['total'] == 3
        assert body['plans']['by_disaster_type']['earthquake'] == 2
        assert body['plans']['by_disaster_type']['flood'] == 1
