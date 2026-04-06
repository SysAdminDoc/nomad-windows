"""Tests for auto-OCR pipeline API routes."""


class TestOCRPipelineStatus:
    def test_pipeline_status(self, client):
        resp = client.get('/api/kb/ocr-pipeline/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'running' in data
        assert 'processed' in data
        assert 'errors' in data

    def test_pipeline_start(self, client):
        resp = client.post('/api/kb/ocr-pipeline/start')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] in ('started', 'already_running')

    def test_pipeline_stop(self, client):
        resp = client.post('/api/kb/ocr-pipeline/stop')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'stopped'

    def test_pipeline_scan_now(self, client):
        resp = client.post('/api/kb/ocr-pipeline/scan')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'scanned'
        assert 'processed' in data


class TestKBWorkspaces:
    def test_list_workspaces(self, client):
        resp = client.get('/api/kb/workspaces')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_workspace(self, client):
        resp = client.post('/api/kb/workspaces', json={
            'name': 'Medical KB',
            'description': 'Medical reference documents',
            'auto_index': 0,
        })
        assert resp.status_code == 201
        assert resp.get_json()['id'] is not None

    def test_create_workspace_requires_name(self, client):
        resp = client.post('/api/kb/workspaces', json={'description': 'No name'})
        assert resp.status_code == 400

    def test_delete_workspace(self, client):
        create = client.post('/api/kb/workspaces', json={'name': 'Temp WS'})
        wid = create.get_json()['id']
        resp = client.delete(f'/api/kb/workspaces/{wid}')
        assert resp.status_code == 200
