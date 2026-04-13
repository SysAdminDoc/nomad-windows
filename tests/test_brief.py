"""Tests for the Daily Operations Brief (v7.7.0)."""


class TestDailyBrief:
    def test_empty_brief_renders(self, client):
        """A fresh install with no data should still return a usable brief
        — every section is optional and gracefully degrades."""
        resp = client.get('/api/brief/daily')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'generated_at' in data
        assert 'date' in data
        assert 'sections' in data

    def test_empty_brief_print_renders_html(self, client):
        resp = client.get('/api/brief/daily/print')
        assert resp.status_code == 200
        assert 'text/html' in resp.headers.get('Content-Type', '')
        body = resp.data.decode('utf-8')
        assert 'Daily Operations Brief' in body

    def test_brief_includes_inventory_when_available(self, client):
        # Create a low-stock item
        client.post('/api/inventory', json={
            'name': 'Bandages', 'category': 'medical',
            'quantity': 2, 'min_quantity': 20, 'unit': 'ea',
        })
        data = client.get('/api/brief/daily').get_json()
        inv = data['sections'].get('inventory', {})
        names = [i['name'] for i in inv.get('low_stock', [])]
        assert 'Bandages' in names

    def test_brief_includes_family_summary(self, client):
        client.post('/api/family-checkins', json={'name': 'Alice'})
        b = client.post('/api/family-checkins', json={'name': 'Bob'}).get_json()
        client.put(f'/api/family-checkins/{b["id"]}', json={'status': 'unaccounted'})
        data = client.get('/api/brief/daily').get_json()
        fam = data['sections'].get('family', {})
        assert fam.get('total') == 2
        assert fam.get('summary', {}).get('unaccounted') == 1

    def test_brief_reflects_emergency_state(self, client):
        client.post('/api/emergency/enter', json={'reason': 'Test'})
        data = client.get('/api/brief/daily').get_json()
        assert data['sections']['emergency']['active'] is True
        assert data['sections']['emergency']['reason'] == 'Test'

    def test_brief_proximity_when_coords_set(self, client):
        """With home coords set, the proximity section should appear even
        when there are zero events (count=0, all clear)."""
        client.put('/api/settings', json={'latitude': '40.0', 'longitude': '-74.0'})
        data = client.get('/api/brief/daily').get_json()
        prox = data['sections'].get('proximity')
        assert prox is not None
        assert prox['count'] == 0

    def test_brief_no_proximity_when_coords_unset(self, client):
        """Proximity section intentionally absent when user hasn't saved
        coordinates — keeps the brief honest rather than showing misleading
        'all clear' for a user in Tokyo without coordinates."""
        data = client.get('/api/brief/daily').get_json()
        assert 'proximity' not in data['sections']
