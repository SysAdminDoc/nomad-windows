"""Tests for daily_living blueprint routes (schedules, chores)."""


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
