"""Tests for notes blueprint routes."""


class TestNotesCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/notes')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_returns_id(self, client):
        resp = client.post('/api/notes', json={'title': 'Patrol Log', 'content': 'All clear.'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['title'] == 'Patrol Log'

    def test_create_and_list(self, client):
        client.post('/api/notes', json={'title': 'Supply Count'})
        resp = client.get('/api/notes')
        assert resp.status_code == 200
        titles = [n['title'] for n in resp.get_json()]
        assert 'Supply Count' in titles

    def test_update_note(self, client):
        create_resp = client.post('/api/notes', json={'title': 'Draft'})
        note_id = create_resp.get_json()['id']
        resp = client.put(f'/api/notes/{note_id}', json={'title': 'Final', 'content': 'Done'})
        assert resp.status_code == 200
        assert resp.get_json()['title'] == 'Final'

    def test_delete_note(self, client):
        create_resp = client.post('/api/notes', json={'title': 'Temp Note'})
        note_id = create_resp.get_json()['id']
        resp = client.delete(f'/api/notes/{note_id}')
        assert resp.status_code == 200

    def test_default_title(self, client):
        resp = client.post('/api/notes', json={})
        assert resp.status_code == 201
        assert resp.get_json()['title'] == 'Untitled'


class TestNotesExtras:
    def test_tags_endpoint(self, client):
        resp = client.get('/api/notes/tags')
        assert resp.status_code == 200

    def test_graph_endpoint(self, client):
        resp = client.get('/api/notes/graph')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'nodes' in data and 'edges' in data

    def test_orphans_endpoint(self, client):
        resp = client.get('/api/notes/orphans')
        assert resp.status_code == 200
