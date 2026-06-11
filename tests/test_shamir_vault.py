"""Tests for Shamir vault and warrant canary routes."""


class TestShamirVault:
    def test_split_and_reconstruct_secret(self, client):
        split = client.post('/api/shamir/split', json={
            'secret': 'winter radio code',
            'threshold': 2,
            'num_shares': 3,
            'label': 'Radio code',
        })
        assert split.status_code == 200
        payload = split.get_json()
        assert payload['threshold'] == 2
        assert payload['num_shares'] == 3
        assert len(payload['shares']) == 3

        reconstruct = client.post('/api/shamir/reconstruct', json={
            'share_id': payload['share_id'],
            'shares': payload['shares'][:2],
        })
        assert reconstruct.status_code == 200
        data = reconstruct.get_json()
        assert data['secret'] == 'winter radio code'
        assert data['verified'] is True

    def test_split_rejects_malformed_json(self, client):
        resp = client.post('/api/shamir/split', data='not-json', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_split_rejects_container_secret(self, client):
        resp = client.post('/api/shamir/split', json={'secret': ['bad']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_reconstruct_rejects_non_object_body(self, client):
        resp = client.post('/api/shamir/reconstruct', json=['share-a'])
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_reconstruct_rejects_non_object_share_items(self, client):
        resp = client.post('/api/shamir/reconstruct', json={'shares': ['not-a-share', 'still-bad']})
        assert resp.status_code == 400
        assert 'Invalid share format' in resp.get_json()['error']


class TestCanary:
    def test_canary_configure_rejects_container_statement(self, client):
        resp = client.post('/api/canary', json={'statement': ['all clear']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_canary_configure_preserves_missing_statement_error(self, client):
        resp = client.post('/api/canary', json={'interval_hours': 24})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'statement is required'

    def test_deadman_actions_rejects_container_actions(self, client):
        resp = client.post('/api/canary/deadman-actions', json={'actions': {'type': 'lock_vault'}})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'
