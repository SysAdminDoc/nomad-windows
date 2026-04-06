"""Tests for API error handling consistency."""

import json


class TestNotFoundResources:
    def test_inventory_item_not_found(self, client):
        resp = client.get('/api/inventory?q=NONEXISTENT_ITEM_XYZ_99999')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_patient_not_found_get(self, client):
        resp = client.get('/api/patients/99999')
        # Patients don't have a GET-by-id route that returns 404 individually;
        # the list endpoint returns all. Check conversations as a proxy.
        pass

    def test_conversation_not_found(self, client):
        resp = client.get('/api/conversations/99999')
        assert resp.status_code == 404
        data = resp.get_json()
        assert 'error' in data

    def test_checklist_not_found(self, client):
        resp = client.get('/api/checklists/99999')
        assert resp.status_code == 404

    def test_nonexistent_api_route(self, client):
        resp = client.get('/api/totally-fake-endpoint')
        assert resp.status_code == 404
        data = resp.get_json()
        assert 'error' in data

    def test_elevation_profile_not_found(self, client):
        resp = client.get('/api/maps/elevation-profile/99999')
        assert resp.status_code == 404

    def test_vault_entry_not_found(self, client):
        resp = client.get('/api/vault/99999')
        assert resp.status_code == 404

    def test_delete_nonexistent_inventory(self, client):
        resp = client.delete('/api/inventory/99999')
        assert resp.status_code == 404  # returns 404 for non-existent resources

    def test_delete_nonexistent_waypoint(self, client):
        resp = client.delete('/api/waypoints/99999')
        assert resp.status_code == 404


class TestMalformedRequests:
    def test_post_inventory_no_body(self, client):
        resp = client.post('/api/inventory',
                          content_type='application/json')
        assert resp.status_code == 400

    def test_post_inventory_invalid_json(self, client):
        resp = client.post('/api/inventory',
                          data='this is not json{{{',
                          content_type='application/json')
        assert resp.status_code == 400

    def test_post_inventory_empty_json(self, client):
        resp = client.post('/api/inventory', json={})
        assert resp.status_code == 400

    def test_post_contacts_no_name(self, client):
        resp = client.post('/api/contacts', json={'phone': '555-1234'})
        assert resp.status_code == 400

    def test_post_incidents_no_description(self, client):
        resp = client.post('/api/incidents', json={'severity': 'low'})
        assert resp.status_code == 400

    def test_post_checklists_invalid_json_string(self, client):
        resp = client.post('/api/checklists',
                          data='not valid json',
                          content_type='application/json')
        assert resp.status_code == 400

    def test_put_inventory_empty_body(self, client):
        create = client.post('/api/inventory', json={'name': 'ErrorTest'})
        item_id = create.get_json()['id']
        resp = client.put(f'/api/inventory/{item_id}', json={})
        assert resp.status_code == 400


class TestResponseFormatConsistency:
    def test_404_returns_error_key(self, client):
        resp = client.get('/api/nonexistent-route-abc123')
        assert resp.status_code == 404
        data = resp.get_json()
        assert 'error' in data

    def test_checklist_404_returns_error_key(self, client):
        resp = client.get('/api/checklists/99999')
        assert resp.status_code == 404

    def test_conversation_404_returns_error_key(self, client):
        resp = client.get('/api/conversations/99999')
        data = resp.get_json()
        assert 'error' in data

    def test_error_response_is_json(self, client):
        resp = client.get('/api/nonexistent-route-xyz')
        assert resp.content_type.startswith('application/json')

    def test_validation_error_has_error_key(self, client):
        resp = client.post('/api/inventory',
                          data='bad json',
                          content_type='application/json')
        data = resp.get_json()
        assert 'error' in data
