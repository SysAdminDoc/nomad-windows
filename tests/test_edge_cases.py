"""Edge case tests — malformed input, empty bodies, special characters."""


class TestMalformedJSON:
    """Routes should handle None/malformed JSON gracefully."""

    def test_inventory_create_empty_body(self, client):
        resp = client.post('/api/inventory', json={})
        assert resp.status_code in (200, 201, 400)

    def test_contacts_create_empty_body(self, client):
        resp = client.post('/api/contacts', json={})
        assert resp.status_code in (200, 201, 400)

    def test_weather_create_empty_body(self, client):
        resp = client.post('/api/weather', json={})
        assert resp.status_code in (200, 201, 400)

    def test_notes_create_empty_body(self, client):
        resp = client.post('/api/notes', json={})
        assert resp.status_code in (200, 201, 400)

    def test_planner_calculate_rejects_malformed_json(self, client):
        resp = client.post('/api/planner/calculate', data='{bad', content_type='application/json')
        assert resp.status_code == 400
        data = resp.get_json()
        assert data['error'] == 'Request body must be valid JSON'


class TestSpecialCharacters:
    """Test that special characters in user input don't cause crashes."""

    def test_inventory_with_special_chars(self, client):
        resp = client.post('/api/inventory', json={
            'name': '<script>alert("xss")</script>',
            'category': 'test"\'&<>',
            'quantity': 1
        })
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        # Name should be stored literally (XSS prevention is in the frontend)
        assert data.get('id') or data.get('name')

    def test_contact_with_unicode(self, client):
        resp = client.post('/api/contacts', json={
            'name': 'Tëst Üsér',
            'callsign': 'KD2ABC',
        })
        assert resp.status_code in (200, 201)

    def test_notes_with_emoji(self, client):
        resp = client.post('/api/notes', json={
            'title': 'Test Note with emoji',
            'content': 'Content with special chars: <>&"\'',
        })
        assert resp.status_code in (200, 201)


class TestLongInput:
    """Test that very long input doesn't crash or cause issues."""

    def test_search_long_query(self, client):
        long_q = 'a' * 500
        resp = client.get('/api/search/all?q=' + long_q)
        assert resp.status_code == 200

    def test_note_long_content(self, client):
        long_content = 'x' * 50000
        resp = client.post('/api/notes', json={
            'title': 'Long Note',
            'content': long_content,
        })
        assert resp.status_code in (200, 201)


class TestPaginationEdgeCases:
    def test_negative_offset(self, client):
        resp = client.get('/api/inventory?offset=-1')
        assert resp.status_code == 200

    def test_zero_limit(self, client):
        resp = client.get('/api/inventory?limit=0')
        assert resp.status_code == 200

    def test_huge_limit(self, client):
        resp = client.get('/api/inventory?limit=999999')
        assert resp.status_code == 200

    def test_non_numeric_limit(self, client):
        resp = client.get('/api/inventory?limit=abc')
        assert resp.status_code == 200  # Should use default


class TestConcurrentSafety:
    """Test that DELETE+GET don't crash on missing resources."""

    def test_double_delete_contact(self, client):
        create = client.post('/api/contacts', json={'name': 'Double Delete'})
        cid = create.get_json()['id']
        # First delete succeeds
        resp1 = client.delete('/api/contacts/' + str(cid))
        assert resp1.status_code == 200
        # Second delete returns 404
        resp2 = client.delete('/api/contacts/' + str(cid))
        assert resp2.status_code == 404

    def test_update_deleted_contact(self, client):
        create = client.post('/api/contacts', json={'name': 'Update After Delete'})
        cid = create.get_json()['id']
        client.delete('/api/contacts/' + str(cid))
        resp = client.put('/api/contacts/' + str(cid), json={'name': 'Updated'})
        assert resp.status_code == 404

    def test_update_deleted_note(self, client):
        create = client.post('/api/notes', json={'title': 'Delete Then Update'})
        nid = create.get_json()['id']
        client.delete('/api/notes/' + str(nid))
        resp = client.put('/api/notes/' + str(nid), json={'title': 'Updated'})
        assert resp.status_code == 404
