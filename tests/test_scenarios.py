"""Tests for scenarios/mission planning API routes."""

import json


class TestScenariosList:
    def test_list_scenarios(self, client):
        resp = client.get('/api/scenarios')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestScenariosCreate:
    def test_create_scenario(self, client):
        resp = client.post('/api/scenarios', json={
            'type': 'evacuation',
            'title': 'Bug Out Drill',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['id'] is not None

    def test_create_scenario_defaults(self, client):
        resp = client.post('/api/scenarios', json={})
        assert resp.status_code == 201


class TestScenariosUpdate:
    def test_update_scenario(self, client):
        create = client.post('/api/scenarios', json={
            'type': 'defense',
            'title': 'Perimeter Drill',
        })
        sid = create.get_json()['id']
        resp = client.put(f'/api/scenarios/{sid}', json={
            'current_phase': 2,
            'status': 'active',
            'decisions': [{'phase': 1, 'choice': 'fortify north'}],
            'score': 50,
        })
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'


class TestScenariosComplication:
    def test_complication_fallback(self, client):
        """When Ollama is not available, should return hardcoded complication."""
        create = client.post('/api/scenarios', json={
            'type': 'medical',
            'title': 'Mass Casualty',
        })
        sid = create.get_json()['id']
        resp = client.post(f'/api/scenarios/{sid}/complication', json={
            'phase_description': 'Triage setup',
            'decisions': [],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'title' in data
        assert 'description' in data
        assert 'choices' in data
        assert len(data['choices']) == 3


class TestScenariosAAR:
    def test_aar_fallback(self, client):
        """When Ollama is not available, should return formula-based score."""
        create = client.post('/api/scenarios', json={
            'type': 'evacuation',
            'title': 'AAR Test',
        })
        sid = create.get_json()['id']
        # Add some decisions first
        client.put(f'/api/scenarios/{sid}', json={
            'decisions': [{'phase': 1, 'choice': 'evacuate'}, {'phase': 2, 'choice': 'regroup'}],
            'complications': [{'title': 'Road blocked'}],
        })
        resp = client.post(f'/api/scenarios/{sid}/aar')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'score' in data
        assert 'aar' in data
        assert isinstance(data['score'], int)
        assert 0 <= data['score'] <= 100

    def test_aar_nonexistent_returns_404(self, client):
        resp = client.post('/api/scenarios/99999/aar')
        assert resp.status_code == 404


class TestScenariosUpdate404:
    def test_update_nonexistent_returns_404(self, client):
        resp = client.put('/api/scenarios/99999', json={
            'current_phase': 1,
            'status': 'active',
        })
        assert resp.status_code == 404
