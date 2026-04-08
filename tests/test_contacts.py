"""Tests for contacts API routes."""


class TestContactsList:
    def test_empty_list(self, client):
        resp = client.get('/api/contacts')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_list_sorted_by_name(self, client):
        client.post('/api/contacts', json={'name': 'Zoe'})
        client.post('/api/contacts', json={'name': 'Alice'})
        resp = client.get('/api/contacts')
        data = resp.get_json()
        assert data[0]['name'] == 'Alice'
        assert data[1]['name'] == 'Zoe'

    def test_search_contacts(self, client):
        client.post('/api/contacts', json={'name': 'Dr. Smith', 'role': 'Medic'})
        client.post('/api/contacts', json={'name': 'John Doe', 'role': 'Scout'})
        resp = client.get('/api/contacts?q=medic')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Dr. Smith'

    def test_search_by_callsign(self, client):
        client.post('/api/contacts', json={'name': 'Mike', 'callsign': 'BRAVO-6'})
        resp = client.get('/api/contacts?q=BRAVO')
        assert len(resp.get_json()) == 1


class TestContactsCreate:
    def test_create_contact(self, client):
        resp = client.post('/api/contacts', json={
            'name': 'Jane',
            'callsign': 'ALPHA-1',
            'role': 'Team Lead',
            'blood_type': 'O+',
            'freq': '146.520',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Jane'
        assert data['callsign'] == 'ALPHA-1'
        assert data['blood_type'] == 'O+'
        assert data['id'] is not None

    def test_create_minimal(self, client):
        resp = client.post('/api/contacts', json={'name': 'Unknown'})
        assert resp.status_code == 201


class TestContactsUpdate:
    def test_update_contact(self, client):
        create = client.post('/api/contacts', json={'name': 'Bob', 'role': 'Scout'})
        cid = create.get_json()['id']
        resp = client.put(f'/api/contacts/{cid}', json={'role': 'Medic', 'freq': '462.5625'})
        assert resp.status_code == 200


class TestContactsDelete:
    def test_delete_contact(self, client):
        create = client.post('/api/contacts', json={'name': 'Temp Contact XYZ'})
        cid = create.get_json()['id']
        resp = client.delete(f'/api/contacts/{cid}')
        assert resp.status_code == 200
        contacts = client.get('/api/contacts').get_json()
        assert not any(c['id'] == cid for c in contacts)

    def test_bulk_delete_rejects_malformed_json(self, client):
        resp = client.post('/api/contacts/bulk-delete', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'
