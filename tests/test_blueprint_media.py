"""Tests for KB (knowledge base) documents and media-related routes."""

from db import db_session


class TestKBDocuments:
    def test_list_documents(self, client):
        resp = client.get('/api/kb/documents')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_kb_status(self, client):
        resp = client.get('/api/kb/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, dict)


class TestKBWorkspaces:
    def test_list_workspaces(self, client):
        resp = client.get('/api/kb/workspaces')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_workspace(self, client):
        resp = client.post('/api/kb/workspaces', json={
            'name': 'Test Workspace',
        })
        assert resp.status_code in (200, 201)

    def test_delete_workspace(self, client):
        create = client.post('/api/kb/workspaces', json={'name': 'Delete WS'})
        data = create.get_json()
        if 'id' in data:
            resp = client.delete(f'/api/kb/workspaces/{data["id"]}')
            assert resp.status_code == 200


class TestOCRPipeline:
    def test_ocr_pipeline_status(self, client):
        resp = client.get('/api/kb/ocr-pipeline/status')
        assert resp.status_code == 200

    def test_ocr_pipeline_stop(self, client):
        resp = client.post('/api/kb/ocr-pipeline/stop')
        assert resp.status_code == 200


class TestKiwixCatalog:
    def test_kiwix_catalog(self, client):
        resp = client.get('/api/kiwix/catalog')
        assert resp.status_code == 200

    def test_kiwix_zims(self, client):
        resp = client.get('/api/kiwix/zims')
        assert resp.status_code == 200

    def test_kiwix_check_updates(self, client):
        resp = client.get('/api/kiwix/check-updates')
        assert resp.status_code == 200

    def test_kiwix_wikipedia_options(self, client):
        resp = client.get('/api/kiwix/wikipedia-options')
        assert resp.status_code == 200


class TestChannelCatalogResilience:
    def test_channels_catalog_recovers_from_corrupted_dead_channels(self, client):
        with db_session() as db:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('dead_channels', ?)", ('{broken',))
            db.commit()

        resp = client.get('/api/channels/catalog')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)

    def test_channels_validate_normalizes_corrupted_dead_channels_setting(self, client, monkeypatch):
        with db_session() as db:
            db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('dead_channels', ?)", ('{broken',))
            db.commit()

        monkeypatch.setattr('web.blueprints.media.get_ytdlp_path', lambda: __file__)

        class _Result:
            returncode = 1
            stdout = ''

        monkeypatch.setattr('web.blueprints.media.subprocess.run', lambda *args, **kwargs: _Result())

        resp = client.post('/api/channels/validate', json={'url': 'https://example.com/channel/test'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['alive'] is False

        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'dead_channels'").fetchone()
        assert row is not None
        assert row['value'] == '["https://example.com/channel/test"]'
