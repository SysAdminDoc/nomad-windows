"""Tests for the Family Check-in Board (v7.6.0)."""


class TestFamilyCheckins:
    def test_empty_list_has_zeroed_summary(self, client):
        resp = client.get('/api/family-checkins')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['members'] == []
        assert data['total'] == 0
        assert data['summary'] == {
            'ok': 0, 'needs_help': 0, 'en_route': 0, 'unaccounted': 0,
        }

    def test_create_member(self, client):
        resp = client.post('/api/family-checkins', json={'name': 'Alice', 'phone': '555-1234'})
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Alice'
        assert data['status'] == 'ok'
        assert data['phone'] == '555-1234'

    def test_create_rejects_empty_name(self, client):
        resp = client.post('/api/family-checkins', json={'name': ''})
        assert resp.status_code == 400

    def test_create_rejects_invalid_status(self, client):
        resp = client.post('/api/family-checkins', json={'name': 'Bob', 'status': 'dead'})
        assert resp.status_code == 400

    def test_duplicate_name_returns_409(self, client):
        client.post('/api/family-checkins', json={'name': 'Charlie'})
        resp = client.post('/api/family-checkins', json={'name': 'Charlie'})
        assert resp.status_code == 409

    def test_update_status(self, client):
        c = client.post('/api/family-checkins', json={'name': 'Dana'}).get_json()
        resp = client.put(f'/api/family-checkins/{c["id"]}', json={'status': 'en_route', 'location': 'Rally 1'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'en_route'
        assert data['location'] == 'Rally 1'

    def test_update_rejects_invalid_status(self, client):
        c = client.post('/api/family-checkins', json={'name': 'Eve'}).get_json()
        resp = client.put(f'/api/family-checkins/{c["id"]}', json={'status': 'panicking'})
        assert resp.status_code == 400

    def test_update_404_for_missing(self, client):
        resp = client.put('/api/family-checkins/99999', json={'status': 'ok'})
        assert resp.status_code == 404

    def test_delete(self, client):
        c = client.post('/api/family-checkins', json={'name': 'Frank'}).get_json()
        resp = client.delete(f'/api/family-checkins/{c["id"]}')
        assert resp.status_code == 200
        # Gone from list
        assert not any(m['name'] == 'Frank' for m in client.get('/api/family-checkins').get_json()['members'])

    def test_delete_404_for_missing(self, client):
        resp = client.delete('/api/family-checkins/99999')
        assert resp.status_code == 404

    def test_summary_counts_by_status(self, client):
        client.post('/api/family-checkins', json={'name': 'A', 'status': 'ok'})
        # Create in default=ok then update; covers the update path too
        b = client.post('/api/family-checkins', json={'name': 'B'}).get_json()
        client.put(f'/api/family-checkins/{b["id"]}', json={'status': 'unaccounted'})
        c = client.post('/api/family-checkins', json={'name': 'C'}).get_json()
        client.put(f'/api/family-checkins/{c["id"]}', json={'status': 'en_route'})
        data = client.get('/api/family-checkins').get_json()
        assert data['summary']['ok'] == 1
        assert data['summary']['unaccounted'] == 1
        assert data['summary']['en_route'] == 1
        # Unaccounted sorts first for the scary-first UI
        assert data['members'][0]['status'] == 'unaccounted'

    def test_reset_all(self, client):
        a = client.post('/api/family-checkins', json={'name': 'A'}).get_json()
        client.put(f'/api/family-checkins/{a["id"]}', json={'status': 'unaccounted'})
        resp = client.post('/api/family-checkins/reset-all', json={})
        assert resp.status_code == 200
        assert resp.get_json()['reset_count'] == 1
        # A is now OK again
        members = client.get('/api/family-checkins').get_json()['members']
        assert members[0]['status'] == 'ok'
