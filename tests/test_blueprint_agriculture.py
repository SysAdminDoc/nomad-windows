"""Tests for agriculture blueprint routes."""


class TestFoodForestGuilds:
    def test_list_guilds(self, client):
        resp = client.get('/api/agriculture/food-forest/guilds')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_guild(self, client):
        resp = client.post('/api/agriculture/food-forest/guilds', json={
            'name': 'Three Sisters Guild', 'central_species': 'Corn'
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_requires_name(self, client):
        resp = client.post('/api/agriculture/food-forest/guilds', json={})
        assert resp.status_code == 400

    def test_update_guild(self, client):
        create_resp = client.post('/api/agriculture/food-forest/guilds', json={'name': 'Old Guild'})
        gid = create_resp.get_json()['id']
        resp = client.put(f'/api/agriculture/food-forest/guilds/{gid}', json={'description': 'Updated'})
        assert resp.status_code == 200

    def test_delete_guild(self, client):
        create_resp = client.post('/api/agriculture/food-forest/guilds', json={'name': 'Delete Guild'})
        gid = create_resp.get_json()['id']
        resp = client.delete(f'/api/agriculture/food-forest/guilds/{gid}')
        assert resp.status_code == 200


class TestSoilProjects:
    def test_list_soil(self, client):
        resp = client.get('/api/agriculture/soil')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_soil_project(self, client):
        resp = client.post('/api/agriculture/soil', json={
            'name': 'Raised Bed 1', 'project_type': 'raised_bed'
        })
        assert resp.status_code == 201


class TestAgricultureSummary:
    def test_summary_endpoint(self, client):
        resp = client.get('/api/agriculture/summary')
        assert resp.status_code == 200
