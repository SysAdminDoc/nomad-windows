"""Tests for the Kit Builder Wizard (v7.3.0).

Covers:
  - Rule-engine smoke test: water scales with climate + people + days
  - Input validation: bad mission rejected, duration/people clamped
  - Cross-reference against inventory: status flips have/partial/gap
  - Commit to shopping list: returns 201 + count
"""


class TestKitBuilderPlan:
    def test_plan_requires_valid_mission(self, client):
        resp = client.post('/api/kit-builder/plan', json={'mission': 'vacation'})
        assert resp.status_code == 400
        assert 'mission' in (resp.get_json().get('error') or '').lower()

    def test_plan_defaults_bug_out(self, client):
        """Empty body should pick sensible defaults (bug-out, 72hr, 1 person)."""
        resp = client.post('/api/kit-builder/plan', json={})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['params']['mission'] == 'bug_out'
        assert data['params']['people'] == 1
        assert data['params']['duration_hrs'] == 72
        assert len(data['items']) > 5

    def test_plan_people_count_scales_water(self, client):
        solo = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'temperate',
            'people': 1, 'duration_hrs': 72, 'mobility': 'foot',
        }).get_json()
        family = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'temperate',
            'people': 4, 'duration_hrs': 72, 'mobility': 'foot',
        }).get_json()
        solo_water = next(i for i in solo['items'] if i['name'] == 'Potable water')
        family_water = next(i for i in family['items'] if i['name'] == 'Potable water')
        # 4× people → 4× water (within rounding)
        assert family_water['quantity'] >= solo_water['quantity'] * 3.9

    def test_plan_hot_climate_more_water(self, client):
        """Hot climate should recommend more water than temperate for the
        same mission/people/duration."""
        temperate = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'temperate',
            'people': 2, 'duration_hrs': 48, 'mobility': 'foot',
        }).get_json()
        hot = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'hot',
            'people': 2, 'duration_hrs': 48, 'mobility': 'foot',
        }).get_json()
        t_water = next(i for i in temperate['items'] if i['name'] == 'Potable water')
        h_water = next(i for i in hot['items'] if i['name'] == 'Potable water')
        assert h_water['quantity'] > t_water['quantity']

    def test_plan_medical_bag_has_no_water(self, client):
        """Medical bag mission shouldn't include water or food."""
        resp = client.post('/api/kit-builder/plan', json={
            'mission': 'medical_bag', 'people': 1, 'duration_hrs': 1,
        })
        items = resp.get_json()['items']
        names = [i['name'] for i in items]
        assert 'Potable water' not in names
        assert all(i['category'] != 'food' for i in items)

    def test_plan_duration_clamped(self, client):
        """Duration > 90 days should be clamped to 90 days (2160 hours)."""
        resp = client.post('/api/kit-builder/plan', json={
            'mission': 'shelter_in_place', 'duration_hrs': 99999,
        })
        assert resp.status_code == 200
        assert resp.get_json()['params']['duration_hrs'] == 2160

    def test_plan_inventory_matches(self, client):
        """Items the user already owns should be marked ``have``."""
        client.post('/api/inventory', json={
            'name': 'Potable water', 'category': 'water',
            'quantity': 100, 'unit': 'L',
        })
        resp = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'people': 1, 'duration_hrs': 72,
        })
        items = resp.get_json()['items']
        water = next(i for i in items if i['name'] == 'Potable water')
        assert water['status'] == 'have'

    def test_every_item_has_reason(self, client):
        """Explainability contract: every recommended item must cite a reason."""
        resp = client.post('/api/kit-builder/plan', json={
            'mission': 'bug_out', 'climate': 'cold',
            'people': 3, 'duration_hrs': 120, 'mobility': 'vehicle',
        })
        items = resp.get_json()['items']
        assert all(i.get('reason') for i in items), 'Every item must carry a non-empty reason'


class TestKitBuilderCommit:
    def test_commit_adds_to_shopping(self, client):
        resp = client.post('/api/kit-builder/add-to-shopping-list', json={
            'items': [
                {'name': 'Paracord 50ft', 'category': 'tools', 'quantity': 2, 'unit': 'hank'},
                {'name': 'Flashlight', 'category': 'tools', 'quantity': 1, 'unit': 'ea'},
            ],
        })
        assert resp.status_code == 201
        assert resp.get_json()['added'] == 2

    def test_commit_rejects_non_list(self, client):
        resp = client.post('/api/kit-builder/add-to-shopping-list', json={'items': 'oops'})
        assert resp.status_code == 400

    def test_commit_empty_ok(self, client):
        resp = client.post('/api/kit-builder/add-to-shopping-list', json={'items': []})
        assert resp.status_code == 201
        assert resp.get_json()['added'] == 0
