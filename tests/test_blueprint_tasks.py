"""Tests for tasks blueprint routes."""


class TestTasksCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/tasks')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_returns_id(self, client):
        resp = client.post('/api/tasks', json={'name': 'Refill water tanks'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['name'] == 'Refill water tanks'

    def test_create_and_list(self, client):
        client.post('/api/tasks', json={'name': 'Check perimeter'})
        resp = client.get('/api/tasks')
        assert resp.status_code == 200
        names = [t['name'] for t in resp.get_json()]
        assert 'Check perimeter' in names

    def test_create_requires_name(self, client):
        resp = client.post('/api/tasks', json={'category': 'security'})
        assert resp.status_code == 400

    def test_update_task(self, client):
        create_resp = client.post('/api/tasks', json={'name': 'Inventory audit'})
        task_id = create_resp.get_json()['id']
        resp = client.put(f'/api/tasks/{task_id}', json={'category': 'logistics'})
        assert resp.status_code == 200

    def test_delete_task(self, client):
        create_resp = client.post('/api/tasks', json={'name': 'Temp task'})
        task_id = create_resp.get_json()['id']
        resp = client.delete(f'/api/tasks/{task_id}')
        assert resp.status_code == 200

    def test_complete_task(self, client):
        create_resp = client.post('/api/tasks', json={'name': 'Complete me'})
        task_id = create_resp.get_json()['id']
        resp = client.post(f'/api/tasks/{task_id}/complete', json={})
        assert resp.status_code == 200


class TestTasksFilter:
    def test_filter_by_category(self, client):
        client.post('/api/tasks', json={'name': 'Med task', 'category': 'medical'})
        resp = client.get('/api/tasks?category=medical')
        assert resp.status_code == 200
        data = resp.get_json()
        assert all(t['category'] == 'medical' for t in data)

    def test_due_tasks_endpoint(self, client):
        resp = client.get('/api/tasks/due')
        assert resp.status_code == 200
