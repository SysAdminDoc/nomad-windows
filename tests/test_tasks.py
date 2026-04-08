"""Tests for scheduled tasks API routes."""


class TestWatchSchedulePrint:
    def test_watch_schedule_print_recovers_from_corrupted_schedule_and_personnel(self, client, db):
        create = client.post('/api/watch-schedules', json={
            'name': 'Broken Rotation',
            'start_date': '2026-03-20',
            'end_date': '2026-03-21',
            'shift_duration_hours': 6,
            'personnel': ['Alex', 'Riley'],
            'notes': 'Maintain radio checks at each relief.',
        })
        sid = create.get_json()['id']

        db.execute(
            'UPDATE watch_schedules SET schedule_json = ?, personnel = ? WHERE id = ?',
            ('{broken', '{broken', sid),
        )
        db.commit()

        resp = client.get(f'/api/watch-schedules/{sid}/print')

        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert 'Watch Schedule - Broken Rotation' in html
        assert 'No personnel listed' in html
        assert 'No shifts were generated for this rotation window.' in html

    def test_watch_schedule_create_accepts_json_string_personnel(self, client):
        resp = client.post('/api/watch-schedules', json={
            'name': 'String Personnel',
            'start_date': '2026-03-20',
            'end_date': '2026-03-21',
            'shift_duration_hours': 6,
            'personnel': '["Alex","Riley","Sage"]',
            'notes': 'Rotate sectors.',
        })

        assert resp.status_code == 201
        data = resp.get_json()
        assert data['shifts'] > 0

    def test_watch_schedule_detail_normalizes_corrupted_json_fields(self, client, db):
        create = client.post('/api/watch-schedules', json={
            'name': 'Detail Recovery',
            'start_date': '2026-03-20',
            'end_date': '2026-03-21',
            'shift_duration_hours': 6,
            'personnel': ['Alex', 'Riley'],
            'notes': 'Rotate sectors.',
        })
        sid = create.get_json()['id']

        db.execute(
            'UPDATE watch_schedules SET schedule_json = ?, personnel = ? WHERE id = ?',
            ('{broken', '{broken', sid),
        )
        db.commit()

        resp = client.get(f'/api/watch-schedules/{sid}')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['schedule_json'] == []
        assert data['personnel'] == []

    def test_watch_schedule_update_accepts_json_string_fields(self, client):
        create = client.post('/api/watch-schedules', json={
            'name': 'Update Recovery',
            'start_date': '2026-03-20',
            'end_date': '2026-03-21',
            'shift_duration_hours': 6,
            'personnel': ['Alex', 'Riley'],
            'notes': 'Rotate sectors.',
        })
        sid = create.get_json()['id']

        resp = client.put(f'/api/watch-schedules/{sid}', json={
            'personnel': '["Alex","Riley","Sage"]',
            'schedule_json': '[{"person":"Alex","start":"2026-03-20 00:00","end":"2026-03-20 06:00","position":1}]',
        })

        assert resp.status_code == 200
        detail = client.get(f'/api/watch-schedules/{sid}')
        assert detail.status_code == 200
        data = detail.get_json()
        assert data['personnel'] == ['Alex', 'Riley', 'Sage']
        assert data['schedule_json'][0]['person'] == 'Alex'


class TestTasksList:
    def test_list_tasks(self, client):
        resp = client.get('/api/tasks')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_filter_by_category(self, client):
        client.post('/api/tasks', json={'name': 'Check water', 'category': 'maintenance'})
        client.post('/api/tasks', json={'name': 'Radio check', 'category': 'comms'})
        resp = client.get('/api/tasks?category=maintenance')
        data = resp.get_json()
        assert any(t['name'] == 'Check water' for t in data)

    def test_filter_by_assigned(self, client):
        client.post('/api/tasks', json={'name': 'Patrol', 'assigned_to': 'John'})
        resp = client.get('/api/tasks?assigned_to=John')
        data = resp.get_json()
        assert any(t['assigned_to'] == 'John' for t in data)


class TestTasksCreate:
    def test_create_task(self, client):
        resp = client.post('/api/tasks', json={
            'name': 'Rotate food supplies',
            'category': 'maintenance',
            'recurrence': 'monthly',
            'assigned_to': 'Alice',
            'notes': 'Check expiration dates',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Rotate food supplies'
        assert data['recurrence'] == 'monthly'

    def test_create_requires_name(self, client):
        resp = client.post('/api/tasks', json={'category': 'maintenance'})
        assert resp.status_code == 400

    def test_create_defaults(self, client):
        resp = client.post('/api/tasks', json={'name': 'Simple task'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['category'] == 'custom'
        assert data['recurrence'] == 'once'


class TestTasksUpdate:
    def test_update_task(self, client):
        create = client.post('/api/tasks', json={'name': 'Old name'})
        tid = create.get_json()['id']
        resp = client.put(f'/api/tasks/{tid}', json={
            'name': 'New name',
            'notes': 'Updated notes',
        })
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'New name'

    def test_update_no_fields_rejected(self, client):
        create = client.post('/api/tasks', json={'name': 'Test'})
        tid = create.get_json()['id']
        resp = client.put(f'/api/tasks/{tid}', json={})
        assert resp.status_code == 400


class TestTasksDelete:
    def test_delete_task(self, client):
        create = client.post('/api/tasks', json={'name': 'Delete me'})
        tid = create.get_json()['id']
        resp = client.delete(f'/api/tasks/{tid}')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'deleted'


class TestTasksComplete:
    def test_complete_once_task(self, client):
        create = client.post('/api/tasks', json={
            'name': 'One-time task',
            'recurrence': 'once',
            'next_due': '2026-03-20',
        })
        tid = create.get_json()['id']
        resp = client.post(f'/api/tasks/{tid}/complete')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['completed_count'] == 1

    def test_complete_recurring_reschedules(self, client):
        create = client.post('/api/tasks', json={
            'name': 'Daily patrol',
            'recurrence': 'daily',
            'next_due': '2026-03-20',
        })
        tid = create.get_json()['id']
        resp = client.post(f'/api/tasks/{tid}/complete')
        data = resp.get_json()
        assert data['completed_count'] == 1
        assert data['next_due'] is not None

    def test_complete_nonexistent_returns_404(self, client):
        resp = client.post('/api/tasks/99999/complete')
        assert resp.status_code == 404


class TestTasksDue:
    def test_due_tasks(self, client):
        resp = client.get('/api/tasks/due')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)
