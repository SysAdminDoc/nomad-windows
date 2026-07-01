"""Tests for storage relocation and migration preflight."""

import os
import tempfile


class TestStoragePreflight:
    def test_preflight_writable_target(self, client):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, 'new_data')
            resp = client.post('/api/storage/preflight', json={'target_path': target})
            assert resp.status_code == 200
            body = resp.get_json()
            assert body['writable'] is True
            assert body['current_size_bytes'] >= 0
            assert body['target_free_bytes'] > 0

    def test_preflight_same_as_current(self, client):
        from config import get_data_dir
        current = get_data_dir()
        resp = client.post('/api/storage/preflight', json={'target_path': current})
        assert resp.status_code == 400

    def test_preflight_rejects_malformed(self, client):
        resp = client.post('/api/storage/preflight',
                           data='{bad', content_type='application/json')
        assert resp.status_code == 400

    def test_preflight_requires_path(self, client):
        resp = client.post('/api/storage/preflight', json={})
        assert resp.status_code == 400
