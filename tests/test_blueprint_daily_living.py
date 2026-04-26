"""Tests for daily_living blueprint routes.

Covers schedules, chores/rotation, clothing readiness, sanitation projections,
morale trends, sleep debt/watch optimization, performance risk summaries,
grid-down recipe seed/search/fuel math, and work/rest reference data.
"""

import json
from datetime import date, timedelta


def _today(offset_days=0):
    return (date.today() + timedelta(days=offset_days)).isoformat()


class TestDailySchedules:
    def test_list_schedules(self, client):
        resp = client.get('/api/daily-living/schedules')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_schedule(self, client):
        resp = client.post('/api/daily-living/schedules', json={
            'name': 'Morning Routine', 'schedule_type': 'daily'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_requires_name(self, client):
        resp = client.post('/api/daily-living/schedules', json={'schedule_type': 'weekly'})
        assert resp.status_code == 400

    def test_get_schedule_by_id(self, client):
        create_resp = client.post('/api/daily-living/schedules', json={'name': 'Evening Routine'})
        sid = create_resp.get_json()['id']
        resp = client.get(f'/api/daily-living/schedules/{sid}')
        assert resp.status_code == 200
        assert resp.get_json()['id'] == sid

    def test_update_schedule(self, client):
        create_resp = client.post('/api/daily-living/schedules', json={'name': 'Old Schedule'})
        sid = create_resp.get_json()['id']
        resp = client.put(f'/api/daily-living/schedules/{sid}', json={'name': 'New Schedule'})
        assert resp.status_code == 200

    def test_delete_schedule(self, client):
        create_resp = client.post('/api/daily-living/schedules', json={'name': 'Temp Schedule'})
        sid = create_resp.get_json()['id']
        resp = client.delete(f'/api/daily-living/schedules/{sid}')
        assert resp.status_code == 200

    def test_templates_endpoint_returns_template_schedules(self, client):
        resp = client.post('/api/daily-living/schedules', json={
            'name': 'Storm Watch',
            'schedule_type': 'operations',
            'is_template': True,
            'time_blocks': [{'start': '18:00', 'task': 'radio watch'}],
            'active_days': ['mon', 'tue'],
        })
        assert resp.status_code == 201

        templates = client.get('/api/daily-living/schedules/templates').get_json()
        assert [row['name'] for row in templates] == ['Storm Watch']
        assert json.loads(templates[0]['time_blocks']) == [{'start': '18:00', 'task': 'radio watch'}]
        assert json.loads(templates[0]['active_days']) == ['mon', 'tue']


class TestChoreAssignments:
    def test_list_chores(self, client):
        resp = client.get('/api/daily-living/chores')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_chore(self, client):
        resp = client.post('/api/daily-living/chores', json={
            'chore_name': 'Wash dishes', 'frequency': 'daily'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_requires_chore_name(self, client):
        resp = client.post('/api/daily-living/chores', json={'frequency': 'weekly'})
        assert resp.status_code == 400

    def test_get_chore_by_id(self, client):
        create_resp = client.post('/api/daily-living/chores', json={'chore_name': 'Sweep floor'})
        cid = create_resp.get_json()['id']
        resp = client.get(f'/api/daily-living/chores/{cid}')
        assert resp.status_code == 200

    def test_complete_chore(self, client):
        create_resp = client.post('/api/daily-living/chores', json={'chore_name': 'Feed animals'})
        cid = create_resp.get_json()['id']
        resp = client.post(f'/api/daily-living/chores/{cid}/complete')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'completed'

    def test_delete_chore(self, client):
        create_resp = client.post('/api/daily-living/chores', json={'chore_name': 'Temp Chore'})
        cid = create_resp.get_json()['id']
        resp = client.delete(f'/api/daily-living/chores/{cid}')
        assert resp.status_code == 200

    def test_rotate_chore_assignments_by_group(self, client):
        first = client.post('/api/daily-living/chores', json={
            'chore_name': 'Water filter',
            'assigned_to': 'Alex',
            'rotation_group': 'ops',
        }).get_json()['id']
        second = client.post('/api/daily-living/chores', json={
            'chore_name': 'Radio check',
            'assigned_to': 'Sam',
            'rotation_group': 'ops',
        }).get_json()['id']

        resp = client.post('/api/daily-living/chores/rotate')
        assert resp.status_code == 200
        assert resp.get_json()['assignments_rotated'] == 2

        assert client.get(f'/api/daily-living/chores/{first}').get_json()['assigned_to'] == 'Sam'
        assert client.get(f'/api/daily-living/chores/{second}').get_json()['assigned_to'] == 'Alex'

    def test_update_chore_empty_body_and_404(self, client):
        cid = client.post('/api/daily-living/chores', json={'chore_name': 'Inventory count'}).get_json()['id']
        assert client.put(f'/api/daily-living/chores/{cid}', json={}).status_code == 400
        assert client.put('/api/daily-living/chores/99999', json={'status': 'paused'}).status_code == 404


class TestClothingInventory:
    def test_clothing_assessment_flags_person_gaps(self, client):
        for payload in [
            {'person': 'Alex', 'item_name': 'Shell jacket', 'category': 'jacket',
             'quantity': 1, 'warmth_rating': 9, 'waterproof': True},
            {'person': 'Alex', 'item_name': 'Winter boots', 'category': 'boots',
             'quantity': 1, 'warmth_rating': 8, 'waterproof': True},
            {'person': 'Sam', 'item_name': 'Wool hat', 'category': 'hat',
             'quantity': 1, 'warmth_rating': 6},
        ]:
            assert client.post('/api/daily-living/clothing', json=payload).status_code == 201

        alex = client.get('/api/daily-living/clothing?person=Alex').get_json()
        assert {row['item_name'] for row in alex} == {'Shell jacket', 'Winter boots'}

        assessment = client.get('/api/daily-living/clothing/assessment').get_json()
        assert assessment['by_person']['Alex']['waterproof_count'] == 2
        assert 'Missing category: gloves' in assessment['by_person']['Alex']['gaps']
        assert 'No waterproof items' in assessment['by_person']['Sam']['gaps']
        assert 'No high-warmth items (rating >= 8)' in assessment['by_person']['Sam']['gaps']

    def test_clothing_update_delete_and_validation(self, client):
        assert client.post('/api/daily-living/clothing', json={}).status_code == 400

        cid = client.post('/api/daily-living/clothing', json={
            'person': 'Alex',
            'item_name': 'Work gloves',
            'category': 'gloves',
        }).get_json()['id']
        assert client.put(f'/api/daily-living/clothing/{cid}', json={}).status_code == 400
        assert client.put(f'/api/daily-living/clothing/{cid}',
                          json={'condition': 'worn'}).status_code == 200
        assert client.get(f'/api/daily-living/clothing/{cid}').get_json()['condition'] == 'worn'
        assert client.delete(f'/api/daily-living/clothing/{cid}').status_code == 200
        assert client.get(f'/api/daily-living/clothing/{cid}').status_code == 404


class TestSanitationSupplies:
    def test_sanitation_projections_classify_supply_statuses(self, client):
        rows = [
            {'name': 'Hand soap', 'category': 'hygiene', 'quantity': 20,
             'unit': 'oz', 'daily_usage_rate': 2, 'min_stock': 4},
            {'name': 'Bleach', 'category': 'disinfection', 'quantity': 2,
             'unit': 'gal', 'daily_usage_rate': 0, 'min_stock': 1},
            {'name': 'Trash bags', 'category': 'waste', 'quantity': 0,
             'unit': 'bags', 'daily_usage_rate': 1, 'min_stock': 5},
        ]
        for row in rows:
            assert client.post('/api/daily-living/sanitation', json=row).status_code == 201

        hygiene = client.get('/api/daily-living/sanitation?category=hygiene').get_json()
        assert [row['name'] for row in hygiene] == ['Hand soap']

        projections = {row['name']: row for row in client.get('/api/daily-living/sanitation/projections').get_json()}
        assert projections['Hand soap']['days_remaining'] == 10.0
        assert projections['Hand soap']['status'] == 'monitor'
        assert projections['Bleach']['status'] == 'no_usage_rate'
        assert projections['Trash bags']['status'] == 'critical'

    def test_sanitation_update_delete_and_validation(self, client):
        assert client.post('/api/daily-living/sanitation', json={}).status_code == 400

        sid = client.post('/api/daily-living/sanitation', json={'name': 'Toothpaste'}).get_json()['id']
        assert client.put(f'/api/daily-living/sanitation/{sid}', json={}).status_code == 400
        assert client.put(f'/api/daily-living/sanitation/{sid}',
                          json={'quantity': 12}).status_code == 200
        assert client.get(f'/api/daily-living/sanitation/{sid}').get_json()['quantity'] == 12
        assert client.delete(f'/api/daily-living/sanitation/{sid}').status_code == 200


class TestMoraleSleepAndPerformance:
    def test_morale_trends_average_recent_entries(self, client):
        client.post('/api/daily-living/morale', json={
            'person': 'Alex',
            'date': _today(),
            'morale_score': 6,
            'stress_level': 4,
            'sleep_quality': 5,
            'physical_health': 7,
            'social_connection': 8,
            'activities': ['cards'],
        })
        client.post('/api/daily-living/morale', json={
            'person': 'Alex',
            'date': _today(-1),
            'morale_score': 8,
            'stress_level': 2,
            'sleep_quality': 7,
            'physical_health': 7,
            'social_connection': 6,
        })

        trends = client.get('/api/daily-living/morale/trends').get_json()
        assert trends['Alex']['7d']['entries'] == 2
        assert trends['Alex']['7d']['morale'] == 7.0
        assert trends['Alex']['7d']['stress'] == 3.0

        rows = client.get('/api/daily-living/morale?person=Alex').get_json()
        assert len(rows) == 2
        assert json.loads(rows[0]['activities']) in (['cards'], [])

    def test_morale_validation_and_delete(self, client):
        assert client.post('/api/daily-living/morale', json={}).status_code == 400
        mid = client.post('/api/daily-living/morale', json={'person': 'Sam'}).get_json()['id']
        assert client.delete(f'/api/daily-living/morale/{mid}').status_code == 200
        assert client.delete(f'/api/daily-living/morale/{mid}').status_code == 404

    def test_sleep_debt_and_watch_optimizer(self, client):
        client.post('/api/daily-living/sleep', json={
            'person': 'Alex',
            'date': _today(),
            'duration_hours': 6,
        })
        client.post('/api/daily-living/sleep', json={
            'person': 'Sam',
            'date': _today(),
            'duration_hours': 8,
        })

        debt = client.get('/api/daily-living/sleep/debt').get_json()
        assert debt[0]['person'] == 'Alex'
        assert debt[0]['cumulative_debt_hours'] == 2.0
        assert debt[1]['person'] == 'Sam'

        optimizer = client.get('/api/daily-living/sleep/watch-optimizer').get_json()
        assert optimizer['personnel_by_readiness'][0] == {'person': 'Sam', 'debt_hours': 0.0}
        assert optimizer['schedule'][0]['assigned_to'] == 'Sam'

    def test_sleep_validation_and_empty_optimizer(self, client):
        assert client.post('/api/daily-living/sleep', json={}).status_code == 400
        empty = client.get('/api/daily-living/sleep/watch-optimizer').get_json()
        assert empty == {'schedule': [], 'note': 'No sleep data available'}

    def test_performance_risk_summary_uses_latest_checks(self, client):
        first = client.post('/api/daily-living/performance', json={
            'person': 'Alex',
            'date': _today(-1),
            'fatigue_level': 2,
            'hours_awake': 6,
        })
        assert first.status_code == 201
        assert first.get_json()['risk_assessment'] == 'low'

        second = client.post('/api/daily-living/performance', json={
            'person': 'Alex',
            'date': _today(),
            'fatigue_level': 8,
            'hours_awake': 19,
        })
        assert second.get_json()['risk_assessment'] == 'critical'

        summary = client.get('/api/daily-living/performance/risk-summary').get_json()
        assert summary['counts']['critical'] == 1
        assert summary['counts']['low'] == 0
        assert 'Immediate rest required' in summary['summary']['critical'][0]['recommendations']

    def test_performance_validation_and_delete(self, client):
        assert client.post('/api/daily-living/performance', json={}).status_code == 400
        pid = client.post('/api/daily-living/performance', json={'person': 'Sam'}).get_json()['id']
        assert client.delete(f'/api/daily-living/performance/{pid}').status_code == 200
        assert client.get(f'/api/daily-living/performance/{pid}').status_code == 404


class TestGridDownRecipes:
    def test_recipe_seed_search_update_and_fuel_calculation(self, client):
        seed = client.post('/api/daily-living/recipes/seed')
        assert seed.status_code == 201
        assert seed.get_json()['count'] == 5

        search = client.get('/api/daily-living/recipes/search?q=rice').get_json()
        names = [row['name'] for row in search]
        assert 'Campfire Rice & Beans' in names
        recipe = next(row for row in search if row['name'] == 'Campfire Rice & Beans')
        assert json.loads(recipe['tags']) == ['shelf-stable', 'high-protein', 'easy']

        resp = client.put(f'/api/daily-living/recipes/{recipe["id"]}', json={
            'ingredients': [{'item': 'rice', 'amount': '4 cups'}],
            'rating': 5,
        })
        assert resp.status_code == 200
        updated = client.get(f'/api/daily-living/recipes/{recipe["id"]}').get_json()
        assert json.loads(updated['ingredients']) == [{'item': 'rice', 'amount': '4 cups'}]

        calc = client.post('/api/daily-living/recipes/calculate-fuel', json={
            'recipe_id': recipe['id'],
            'servings': 8,
        }).get_json()
        assert calc['multiplier'] == 2.0
        assert calc['water_required_ml'] == 1900
        assert calc['total_calories'] == 3040

        skipped = client.post('/api/daily-living/recipes/seed')
        assert skipped.status_code == 200
        assert skipped.get_json()['status'] == 'skipped'

    def test_recipe_filters_validation_and_reference(self, client):
        assert client.post('/api/daily-living/recipes', json={}).status_code == 400
        assert client.get('/api/daily-living/recipes/search').status_code == 400
        assert client.post('/api/daily-living/recipes/calculate-fuel', json={}).status_code == 400

        client.post('/api/daily-living/recipes', json={
            'name': 'Cold oats',
            'category': 'breakfast',
            'cooking_method': 'no_cook',
            'shelf_stable_only': True,
        })
        rows = client.get('/api/daily-living/recipes?method=no_cook&shelf_stable=true').get_json()
        assert [row['name'] for row in rows] == ['Cold oats']

        reference = client.get('/api/daily-living/reference/work-rest').get_json()
        assert reference['heavy_work']['work_minutes'] == 30
        assert reference['night_ops']['rest_minutes'] == 15
