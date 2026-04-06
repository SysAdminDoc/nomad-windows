"""Extended tests for federation blueprint — peers, offers, requests, sync."""


class TestNodeIdentity:
    def test_get_identity(self, client):
        resp = client.get('/api/node/identity')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'node_id' in data
        assert 'node_name' in data

    def test_set_identity(self, client):
        resp = client.put('/api/node/identity', json={'name': 'Test Node'})
        assert resp.status_code == 200


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


class TestSyncLog:
    def test_sync_log(self, client):
        resp = client.get('/api/node/sync-log')
        assert resp.status_code == 200

    def test_vector_clock(self, client):
        resp = client.get('/api/node/vector-clock')
        assert resp.status_code == 200


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

    def test_mutual_aid_delete_nonexistent(self, client):
        resp = client.delete('/api/federation/mutual-aid/999999')
        assert resp.status_code == 404
