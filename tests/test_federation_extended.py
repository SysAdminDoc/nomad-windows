"""Extended tests for federation blueprint — peers, offers, requests, sync."""


class TestNodeIdentity:
    def test_get_identity(self, client):
        resp = client.get('/api/node/identity')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'node_id' in data
        assert 'node_name' in data
        assert len(data.get('public_key', '')) == 64

    def test_set_identity(self, client):
        resp = client.put('/api/node/identity', json={'name': 'Test Node'})
        assert resp.status_code == 200

    def test_set_identity_allows_empty_body_noop(self, client):
        resp = client.put('/api/node/identity')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'

    def test_set_identity_rejects_malformed_json(self, client):
        resp = client.put('/api/node/identity', data='not-json', content_type='application/json')
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'


class TestFederationPeers:
    def test_peers_list(self, client):
        resp = client.get('/api/federation/peers')
        assert resp.status_code == 200

    def test_add_peer(self, client):
        resp = client.post('/api/federation/peers', json={
            'node_id': 'test-node-123',
            'node_name': 'Remote Base',
            'trust_level': 'observer',
            'ip': '192.168.1.100',
        })
        assert resp.status_code in (200, 201)

    def test_add_peer_blocked_ip(self, client):
        """SSRF protection: loopback IPs should be rejected."""
        resp = client.post('/api/federation/peers', json={
            'node_id': 'evil-node',
            'ip': '127.0.0.1',
        })
        assert resp.status_code == 400

    def test_add_peer_link_local(self, client):
        """SSRF protection: link-local IPs should be rejected."""
        resp = client.post('/api/federation/peers', json={
            'node_id': 'evil-node-2',
            'ip': '169.254.1.1',
        })
        assert resp.status_code == 400

    def test_add_peer_missing_node_id(self, client):
        resp = client.post('/api/federation/peers', json={
            'node_name': 'No ID'
        })
        assert resp.status_code == 400

    def test_add_peer_rejects_non_object_body(self, client):
        resp = client.post('/api/federation/peers', json=['node-a'])
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_add_peer_rejects_wrong_type_node_id(self, client):
        resp = client.post('/api/federation/peers', json={'node_id': ['node-a']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_add_peer_rejects_bad_public_key(self, client):
        resp = client.post('/api/federation/peers', json={
            'node_id': 'bad-key-node',
            'public_key': 'not-hex',
            'ip': '192.168.1.101',
        })
        assert resp.status_code == 400

    def test_add_peer_preserves_existing_public_key(self, client, db):
        public_key = 'd' * 64
        first = client.post('/api/federation/peers', json={
            'node_id': 'keyed-node',
            'node_name': 'Keyed Node',
            'trust_level': 'member',
            'ip': '192.168.1.102',
            'public_key': public_key,
        })
        assert first.status_code in (200, 201)

        second = client.post('/api/federation/peers', json={
            'node_id': 'keyed-node',
            'node_name': 'Renamed Keyed Node',
            'trust_level': 'trusted',
            'ip': '192.168.1.103',
        })
        assert second.status_code in (200, 201)

        row = db.execute('SELECT node_name, trust_level, ip, public_key FROM federation_peers WHERE node_id = ?', ('keyed-node',)).fetchone()
        assert row['node_name'] == 'Renamed Keyed Node'
        assert row['trust_level'] == 'trusted'
        assert row['ip'] == '192.168.1.103'
        assert row['public_key'] == public_key

    def test_peer_trust_rejects_wrong_type_level(self, client):
        resp = client.put('/api/federation/peers/test-node-123/trust', json={'trust_level': ['trusted']})
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_peer_verify_allows_empty_body_challenge(self, client, db):
        db.execute(
            "INSERT INTO federation_peers (node_id, node_name, trust_level) VALUES (?, ?, ?)",
            ('verify-node', 'Verify Node', 'member'),
        )
        db.commit()

        resp = client.post('/api/federation/peers/verify-node/verify')
        assert resp.status_code == 200
        assert 'challenge' in resp.get_json()

    def test_delete_peer_nonexistent(self, client):
        resp = client.delete('/api/federation/peers/nonexistent-node')
        assert resp.status_code == 404


class TestFederationOffers:
    def test_offers_list(self, client):
        resp = client.get('/api/federation/offers')
        assert resp.status_code == 200

    def test_offer_create(self, client):
        resp = client.post('/api/federation/offers', json={
            'item_type': 'diesel', 'quantity': 50, 'notes': 'Available'
        })
        assert resp.status_code in (200, 201)

    def test_offer_create_rejects_container_quantity(self, client):
        resp = client.post('/api/federation/offers', json={
            'item_type': 'diesel',
            'quantity': ['50'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'


class TestFederationRequests:
    def test_requests_list(self, client):
        resp = client.get('/api/federation/requests')
        assert resp.status_code == 200

    def test_request_create(self, client):
        resp = client.post('/api/federation/requests', json={
            'item_type': 'antibiotics', 'description': 'Need amoxicillin',
            'urgency': 'urgent'
        })
        assert resp.status_code in (200, 201)

    def test_request_create_rejects_container_description(self, client):
        resp = client.post('/api/federation/requests', json={
            'item_type': 'antibiotics',
            'description': ['Need amoxicillin'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'


class TestSyncLog:
    def test_sync_log(self, client):
        resp = client.get('/api/node/sync-log')
        assert resp.status_code == 200

    def test_vector_clock(self, client):
        resp = client.get('/api/node/vector-clock')
        assert resp.status_code == 200


class TestFederationTransactions:
    def test_transaction_create_rejects_container_item_type(self, client):
        resp = client.post('/api/federation/transactions', json={
            'from_node_id': 'node-a',
            'to_node_id': 'node-b',
            'item_type': ['diesel'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'


class TestMutualAid:
    def test_mutual_aid_list(self, client):
        resp = client.get('/api/federation/mutual-aid')
        assert resp.status_code == 200

    def test_mutual_aid_create(self, client):
        resp = client.post('/api/federation/mutual-aid', json={
            'title': 'Mutual Aid Agreement',
            'peer_node_id': 'test-node-456',
            'peer_name': 'Neighbor Base',
            'our_commitments': ['medical support', 'water sharing'],
            'their_commitments': ['fuel supply', 'communications'],
        })
        assert resp.status_code in (200, 201)

    def test_mutual_aid_create_rejects_wrong_type_title(self, client):
        resp = client.post('/api/federation/mutual-aid', json={
            'title': ['Mutual Aid Agreement'],
        })
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Validation failed'

    def test_mutual_aid_delete_nonexistent(self, client):
        resp = client.delete('/api/federation/mutual-aid/999999')
        assert resp.status_code == 404
