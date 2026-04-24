"""Smoke coverage for web/blueprints/roadmap_features.py.

The blueprint exposes 75 routes across ~16 resource families and previously
had no dedicated test file. These tests pin the highest-traffic resources
(recipes, batteries, warranties, ai_skills, url_monitors, personal_feeds)
with list + create + (update where supported) + delete patterns plus the
common error paths (missing-field 400, missing-id 404).

Tests use the per-function `client` fixture from conftest.py — each test
gets a fresh shared in-memory SQLite DB so state cannot bleed between cases.
"""


class TestRecipes:
    def test_list_empty(self, client):
        resp = client.get('/api/recipes')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_requires_name(self, client):
        resp = client.post('/api/recipes', json={})
        assert resp.status_code == 400

    def test_create_then_detail(self, client):
        create_resp = client.post('/api/recipes', json={
            'name': 'Three Bean Stew',
            'servings': 6,
            'prep_time_min': 15,
            'cook_time_min': 90,
            'instructions': 'Soak beans, simmer, season.',
            'ingredients': [
                {'name': 'kidney beans', 'quantity': 1, 'unit': 'cup'},
                {'name': 'pinto beans', 'quantity': 1, 'unit': 'cup'},
            ],
        })
        assert create_resp.status_code == 201
        rid = create_resp.get_json()['id']
        assert isinstance(rid, int)

        detail_resp = client.get(f'/api/recipes/{rid}')
        assert detail_resp.status_code == 200
        body = detail_resp.get_json()
        assert body['name'] == 'Three Bean Stew'
        assert body['servings'] == 6
        assert len(body['ingredients']) == 2

    def test_detail_404(self, client):
        resp = client.get('/api/recipes/999999')
        assert resp.status_code == 404

    def test_update(self, client):
        create_resp = client.post('/api/recipes', json={'name': 'Old Recipe', 'servings': 2})
        rid = create_resp.get_json()['id']
        upd_resp = client.put(f'/api/recipes/{rid}', json={'name': 'Renamed Recipe', 'servings': 4})
        assert upd_resp.status_code == 200
        detail = client.get(f'/api/recipes/{rid}').get_json()
        assert detail['name'] == 'Renamed Recipe'
        assert detail['servings'] == 4

    def test_delete(self, client):
        create_resp = client.post('/api/recipes', json={'name': 'Doomed Recipe'})
        rid = create_resp.get_json()['id']
        del_resp = client.delete(f'/api/recipes/{rid}')
        assert del_resp.status_code == 200
        assert client.get(f'/api/recipes/{rid}').status_code == 404

    def test_delete_missing_returns_404(self, client):
        resp = client.delete('/api/recipes/999999')
        assert resp.status_code == 404


class TestBatteries:
    def test_list_empty(self, client):
        resp = client.get('/api/batteries')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_requires_device_name(self, client):
        resp = client.post('/api/batteries', json={'battery_type': 'AA'})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        create_resp = client.post('/api/batteries', json={
            'device_name': 'Main flashlight',
            'battery_type': 'AA',
            'quantity': 4,
            'expected_life_days': 730,
        })
        assert create_resp.status_code == 201
        bid = create_resp.get_json()['id']
        assert isinstance(bid, int)

        list_resp = client.get('/api/batteries')
        rows = list_resp.get_json()
        assert len(rows) == 1
        assert rows[0]['device_name'] == 'Main flashlight'
        assert rows[0]['quantity'] == 4

    def test_update(self, client):
        bid = client.post('/api/batteries', json={'device_name': 'Radio'}).get_json()['id']
        upd = client.put(f'/api/batteries/{bid}', json={'quantity': 8, 'notes': 'replaced 2026-04-24'})
        assert upd.status_code == 200
        rows = client.get('/api/batteries').get_json()
        match = next((r for r in rows if r['id'] == bid), None)
        assert match is not None
        assert match['quantity'] == 8
        assert match['notes'] == 'replaced 2026-04-24'

    def test_update_missing_returns_404(self, client):
        resp = client.put('/api/batteries/999999', json={'quantity': 1})
        assert resp.status_code == 404

    def test_delete(self, client):
        bid = client.post('/api/batteries', json={'device_name': 'Headlamp'}).get_json()['id']
        assert client.delete(f'/api/batteries/{bid}').status_code == 200
        assert client.delete(f'/api/batteries/{bid}').status_code == 404


class TestWarranties:
    def test_list_empty(self, client):
        resp = client.get('/api/warranties')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_requires_item_name(self, client):
        resp = client.post('/api/warranties', json={'category': 'tool'})
        assert resp.status_code == 400

    def test_full_lifecycle(self, client):
        create_resp = client.post('/api/warranties', json={
            'item_name': 'DeWalt drill',
            'category': 'tool',
            'purchase_date': '2024-08-15',
            'expiry_date': '2027-08-15',
            'provider': 'DeWalt',
            'policy_number': 'W12345',
        })
        assert create_resp.status_code == 201
        wid = create_resp.get_json()['id']

        upd_resp = client.put(f'/api/warranties/{wid}', json={'notes': 'Receipt scanned to docs/'})
        assert upd_resp.status_code == 200

        list_rows = client.get('/api/warranties').get_json()
        assert any(r['id'] == wid and r['notes'] == 'Receipt scanned to docs/' for r in list_rows)

        del_resp = client.delete(f'/api/warranties/{wid}')
        assert del_resp.status_code == 200
        assert client.delete(f'/api/warranties/{wid}').status_code == 404


class TestAISkills:
    def test_list_empty(self, client):
        resp = client.get('/api/ai/skills')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_requires_name(self, client):
        resp = client.post('/api/ai/skills', json={})
        assert resp.status_code == 400

    def test_create_update_delete(self, client):
        sid = client.post('/api/ai/skills', json={
            'name': 'Trauma triage',
            'description': 'Field-care decision support',
            'system_prompt': 'You are a TCCC-trained corpsman.',
        }).get_json()['id']

        upd = client.put(f'/api/ai/skills/{sid}', json={'description': 'Updated description'})
        assert upd.status_code == 200

        rows = client.get('/api/ai/skills').get_json()
        match = next((r for r in rows if r['id'] == sid), None)
        assert match is not None
        assert match['description'] == 'Updated description'

        assert client.delete(f'/api/ai/skills/{sid}').status_code == 200
        assert client.delete(f'/api/ai/skills/{sid}').status_code == 404


class TestURLMonitors:
    def test_list_empty(self, client):
        resp = client.get('/api/monitors')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_requires_url(self, client):
        resp = client.post('/api/monitors', json={'name': 'No URL'})
        assert resp.status_code == 400

    def test_create_and_delete(self, client):
        create_resp = client.post('/api/monitors', json={
            'name': 'Loopback',
            'url': 'http://127.0.0.1:65535/never',
            'method': 'GET',
            'expected_status': 200,
            'check_interval_sec': 600,
        })
        assert create_resp.status_code == 201
        mid = create_resp.get_json()['id']

        rows = client.get('/api/monitors').get_json()
        assert any(r['id'] == mid for r in rows)

        assert client.delete(f'/api/monitors/{mid}').status_code == 200
        assert client.delete(f'/api/monitors/{mid}').status_code == 404


class TestPersonalFeeds:
    def test_list_empty(self, client):
        resp = client.get('/api/feeds')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_requires_url(self, client):
        resp = client.post('/api/feeds', json={'title': 'No URL'})
        assert resp.status_code == 400

    def test_create_and_delete(self, client):
        fid = client.post('/api/feeds', json={
            'title': 'Test Feed',
            'url': 'https://example.invalid/feed.xml',
            'category': 'preparedness',
        }).get_json()['id']
        assert isinstance(fid, int)

        rows = client.get('/api/feeds').get_json()
        assert any(r['id'] == fid for r in rows)

        # /items on an empty feed should still 200 with an empty list
        items_resp = client.get(f'/api/feeds/{fid}/items')
        assert items_resp.status_code == 200
        assert items_resp.get_json() == []

        assert client.delete(f'/api/feeds/{fid}').status_code == 200
        assert client.delete(f'/api/feeds/{fid}').status_code == 404
