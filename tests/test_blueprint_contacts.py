"""Tests for contacts blueprint routes."""


class TestContactsCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/contacts')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_returns_id(self, client):
        resp = client.post('/api/contacts', json={'name': 'Alice'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None
        assert data['name'] == 'Alice'

    def test_create_and_list(self, client):
        client.post('/api/contacts', json={'name': 'Bob', 'role': 'medic'})
        resp = client.get('/api/contacts')
        assert resp.status_code == 200
        names = [c['name'] for c in resp.get_json()]
        assert 'Bob' in names

    def test_update_contact(self, client):
        create_resp = client.post('/api/contacts', json={'name': 'Carol'})
        cid = create_resp.get_json()['id']
        resp = client.put(f'/api/contacts/{cid}', json={'role': 'logistics'})
        assert resp.status_code == 200

    def test_delete_contact(self, client):
        create_resp = client.post('/api/contacts', json={'name': 'Dave'})
        cid = create_resp.get_json()['id']
        resp = client.delete(f'/api/contacts/{cid}')
        assert resp.status_code == 200

    def test_create_requires_name(self, client):
        resp = client.post('/api/contacts', json={'role': 'scout'})
        assert resp.status_code == 400


class TestContactsSearch:
    def test_search_by_name(self, client):
        client.post('/api/contacts', json={'name': 'Evelyn Scout'})
        resp = client.get('/api/contacts?q=evelyn')
        assert resp.status_code == 200
        data = resp.get_json()
        assert any('Evelyn' in c['name'] for c in data)

    def test_search_no_results(self, client):
        resp = client.get('/api/contacts?q=ZZZNOTEXIST')
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestContactsExport:
    def test_export_csv(self, client):
        resp = client.get('/api/contacts/export-csv')
        assert resp.status_code == 200
        assert 'text/csv' in resp.content_type
