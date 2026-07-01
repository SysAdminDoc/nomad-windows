"""Tests for guidance source metadata and high-risk field guardrails."""

from db import db_session


class TestGuidanceSourcesCRUD:
    def test_list_empty(self, client):
        resp = client.get('/api/guidance-sources')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_and_retrieve(self, client):
        resp = client.post('/api/guidance-sources', json={
            'domain': 'medical',
            'content_key': 'vital_signs',
            'review_status': 'reviewed',
            'source_refs': ['ATLS 10th Edition', 'Tintinalli Emergency Medicine'],
            'last_reviewed': '2026-01-15',
            'reviewer_notes': 'Verified against current ATLS guidelines',
        })
        assert resp.status_code == 201

        detail = client.get('/api/guidance-sources/medical/vital_signs').get_json()
        assert detail['review_status'] == 'reviewed'
        assert 'ATLS 10th Edition' in detail['source_refs']
        assert detail['last_reviewed'] == '2026-01-15'

    def test_upsert_replaces(self, client):
        client.post('/api/guidance-sources', json={
            'domain': 'foraging', 'content_key': 'edibles',
            'review_status': 'unreviewed',
        })
        client.post('/api/guidance-sources', json={
            'domain': 'foraging', 'content_key': 'edibles',
            'review_status': 'reviewed',
            'last_reviewed': '2026-06-01',
        })
        detail = client.get('/api/guidance-sources/foraging/edibles').get_json()
        assert detail['review_status'] == 'reviewed'

    def test_unknown_returns_unreviewed(self, client):
        detail = client.get('/api/guidance-sources/nonexistent/key').get_json()
        assert detail['review_status'] == 'unreviewed'
        assert detail['source_refs'] == []

    def test_filter_by_domain(self, client):
        client.post('/api/guidance-sources', json={
            'domain': 'medical', 'content_key': 'a', 'review_status': 'reviewed',
        })
        client.post('/api/guidance-sources', json={
            'domain': 'foraging', 'content_key': 'b', 'review_status': 'unreviewed',
        })
        medical = client.get('/api/guidance-sources?domain=medical').get_json()
        assert all(r['domain'] == 'medical' for r in medical)

    def test_high_risk_domains_list(self, client):
        resp = client.get('/api/guidance-sources/high-risk-domains')
        domains = resp.get_json()
        assert 'medical' in domains
        assert 'foraging' in domains
        assert 'cbrn' in domains

    def test_create_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/guidance-sources',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400

    def test_create_rejects_invalid_status(self, client):
        resp = client.post('/api/guidance-sources', json={
            'domain': 'medical', 'content_key': 'test',
            'review_status': 'invalid_status',
        })
        assert resp.status_code == 400


class TestMedicalReferenceSourceMeta:
    def test_medical_reference_includes_source_metadata(self, client):
        resp = client.get('/api/medical/reference')
        body = resp.get_json()
        assert '_source' in body
        assert body['_source']['review_status'] == 'unreviewed'

    def test_medical_reference_category_includes_source(self, client):
        resp = client.get('/api/medical/reference?category=vital_signs')
        body = resp.get_json()
        assert '_source' in body


class TestHazmatSourceMeta:
    def test_hazmat_agents_include_source_metadata(self, client):
        resp = client.get('/api/hazmat/agents')
        body = resp.get_json()
        assert '_source' in body
        assert 'sources' in body
        assert 'disclaimer' in body
