"""Tests for KB indexing budget, cancel, and purge controls."""

import web.state as ws


class TestKBCancel:
    def test_cancel_no_active_job(self, client):
        resp = client.post('/api/kb/cancel')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'no_active_job'

    def test_cancel_sets_flag_when_processing(self, client):
        ws.set_embed_state(status='processing', doc_id=1, progress=50)
        try:
            resp = client.post('/api/kb/cancel')
            assert resp.status_code == 200
            assert resp.get_json()['status'] == 'cancel_requested'
            assert ws.is_embed_cancelled()
        finally:
            ws.set_embed_state(status='idle', doc_id=None, progress=0)
            ws.clear_embed_cancel()


class TestKBEstimate:
    def test_estimate_text_file(self, client):
        resp = client.post('/api/kb/estimate', json={
            'file_size': 100000,
            'content_type': 'text/plain',
        })
        body = resp.get_json()
        assert body['estimated_chunks'] > 0
        assert body['estimated_seconds'] > 0
        assert body['estimated_vector_bytes'] > 0

    def test_estimate_pdf(self, client):
        resp = client.post('/api/kb/estimate', json={
            'file_size': 500000,
            'content_type': 'application/pdf',
        })
        body = resp.get_json()
        assert body['estimated_chunks'] > 0

    def test_estimate_zero_size(self, client):
        resp = client.post('/api/kb/estimate', json={
            'file_size': 0,
            'content_type': 'text/plain',
        })
        body = resp.get_json()
        assert body['estimated_chunks'] >= 0


class TestKBPurge:
    def test_purge_requires_target(self, client):
        resp = client.post('/api/kb/purge', json={})
        assert resp.status_code == 400

    def test_purge_nonexistent_doc(self, client):
        resp = client.post('/api/kb/purge', json={'doc_id': 99999})
        assert resp.status_code == 200
        assert resp.get_json()['count'] == 0

    def test_purge_all_empty(self, client):
        resp = client.post('/api/kb/purge', json={'all': True})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'purged'
