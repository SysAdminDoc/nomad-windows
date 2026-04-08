"""Tests for checklists API routes."""

import io
import json


class TestChecklistsList:
    def test_empty_list(self, client):
        resp = client.get('/api/checklists')
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestChecklistsCreate:
    def test_create_custom(self, client):
        resp = client.post('/api/checklists', json={
            'name': 'Bug Out Bag',
            'items': [
                {'text': 'Water (3L)', 'checked': False},
                {'text': 'First aid kit', 'checked': True},
                {'text': 'Knife', 'checked': False},
            ]
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['name'] == 'Bug Out Bag'
        items = data.get('items', json.loads(data.get('items', '[]')) if isinstance(data.get('items'), str) else [])
        if isinstance(items, str):
            items = json.loads(items)
        assert len(items) == 3

    def test_create_accepts_json_string_items(self, client):
        resp = client.post('/api/checklists', json={
            'name': 'String Items',
            'items': '[{"text":"Water","checked":false},{"text":"Radio","checked":true}]',
        })

        assert resp.status_code == 201
        data = resp.get_json()
        assert isinstance(data['items'], list)
        assert len(data['items']) == 2

    def test_create_from_template(self, client):
        resp = client.post('/api/checklists', json={'template': 'bug-out'})
        # Template may or may not exist, either way should not crash
        assert resp.status_code in (200, 201)

    def test_create_empty(self, client):
        resp = client.post('/api/checklists', json={'name': 'Empty List'})
        assert resp.status_code == 201


class TestChecklistsGet:
    def test_get_checklist(self, client):
        create = client.post('/api/checklists', json={
            'name': 'Test',
            'items': [{'text': 'Item 1', 'checked': False}]
        })
        cid = create.get_json()['id']
        resp = client.get(f'/api/checklists/{cid}')
        assert resp.status_code == 200


class TestChecklistsUpdate:
    def test_update_items(self, client):
        create = client.post('/api/checklists', json={
            'name': 'Checklist',
            'items': [{'text': 'Todo', 'checked': False}]
        })
        cid = create.get_json()['id']
        resp = client.put(f'/api/checklists/{cid}', json={
            'items': [{'text': 'Todo', 'checked': True}]
        })
        assert resp.status_code == 200

    def test_update_accepts_json_string_items(self, client):
        create = client.post('/api/checklists', json={
            'name': 'Checklist',
            'items': [{'text': 'Todo', 'checked': False}]
        })
        cid = create.get_json()['id']

        resp = client.put(f'/api/checklists/{cid}', json={
            'items': '[{"text":"Todo","checked":true}]'
        })

        assert resp.status_code == 200
        detail = client.get(f'/api/checklists/{cid}')
        assert detail.status_code == 200
        assert detail.get_json()['items'] == [{'text': 'Todo', 'checked': True}]


class TestChecklistsDelete:
    def test_delete_checklist(self, client):
        create = client.post('/api/checklists', json={'name': 'To Delete XYZ'})
        cid = create.get_json()['id']
        resp = client.delete(f'/api/checklists/{cid}')
        assert resp.status_code == 200
        checklists = client.get('/api/checklists').get_json()
        assert not any(c['id'] == cid for c in checklists)


class TestChecklistSummary:
    def test_summary_counts(self, client):
        client.post('/api/checklists', json={
            'name': 'Mix',
            'items': [
                {'text': 'Done', 'checked': True},
                {'text': 'Not done', 'checked': False},
            ]
        })
        resp = client.get('/api/checklists')
        data = resp.get_json()
        mix = next(c for c in data if c['name'] == 'Mix')
        assert mix['item_count'] == 2
        assert mix['checked_count'] == 1


class TestChecklistImport:
    def test_import_normalizes_string_items(self, client):
        payload = {
            'type': 'nomad_checklist',
            'version': 1,
            'name': 'Imported Strings',
            'template': 'imported',
            'items': '[{"text":"Flashlight","checked":false}]',
        }

        resp = client.post(
            '/api/checklists/import-json',
            data={'file': (io.BytesIO(json.dumps(payload).encode('utf-8')), 'checklist.json')},
            content_type='multipart/form-data',
        )

        assert resp.status_code == 200
        cid = resp.get_json()['id']
        detail = client.get(f'/api/checklists/{cid}')
        assert detail.status_code == 200
        assert detail.get_json()['items'] == [{'text': 'Flashlight', 'checked': False}]
