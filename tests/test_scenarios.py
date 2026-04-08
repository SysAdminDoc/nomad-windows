"""Tests for scenarios/mission planning API routes."""

import json

import web.blueprints.preparedness as preparedness_module


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

    def test_update_scenario_accepts_json_string_decisions_and_complications(self, client, db):
        create = client.post('/api/scenarios', json={
            'type': 'defense',
            'title': 'String Payload Drill',
        })
        sid = create.get_json()['id']

        resp = client.put(f'/api/scenarios/{sid}', json={
            'current_phase': 2,
            'status': 'active',
            'decisions': '[{"phase": 1, "choice": "fortify north"}]',
            'complications': '[{"title": "Road blocked", "response": "reroute"}]',
            'score': 50,
        })

        assert resp.status_code == 200

        row = db.execute('SELECT decisions, complications FROM scenarios WHERE id = ?', (sid,)).fetchone()
        assert json.loads(row['decisions']) == [{'phase': 1, 'choice': 'fortify north'}]
        assert json.loads(row['complications']) == [{'title': 'Road blocked', 'response': 'reroute'}]


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

    def test_complication_recovers_from_malformed_ai_payload(self, client, monkeypatch):
        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {'response': '{broken'}

        create = client.post('/api/scenarios', json={
            'type': 'medical',
            'title': 'Malformed AI Drill',
        })
        sid = create.get_json()['id']

        monkeypatch.setattr(preparedness_module.ollama, 'running', lambda: True)
        monkeypatch.setattr(preparedness_module.ollama, 'list_models', lambda: [{'name': 'test-model'}])
        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _FakeResponse())

        resp = client.post(f'/api/scenarios/{sid}/complication', json={
            'phase_description': 'Triage setup',
            'decisions': '[{"label":"stabilize"}]',
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['title'] == 'Unexpected Event'
        assert len(data['choices']) == 3

    def test_complication_recovers_from_unreadable_http_json(self, client, monkeypatch):
        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError('bad complication payload')

        create = client.post('/api/scenarios', json={
            'type': 'medical',
            'title': 'Unreadable AI Drill',
        })
        sid = create.get_json()['id']

        monkeypatch.setattr(preparedness_module.ollama, 'running', lambda: True)
        monkeypatch.setattr(preparedness_module.ollama, 'list_models', lambda: [{'name': 'test-model'}])
        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _FakeResponse())

        resp = client.post(f'/api/scenarios/{sid}/complication', json={
            'phase_description': 'Triage setup',
            'decisions': [],
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['title'] == 'Unexpected Event'
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

    def test_aar_recovers_from_corrupted_decisions_and_complications(self, client, db):
        create = client.post('/api/scenarios', json={
            'type': 'evacuation',
            'title': 'Corrupted AAR',
        })
        sid = create.get_json()['id']

        db.execute('UPDATE scenarios SET decisions = ?, complications = ? WHERE id = ?', ('{broken', '{broken', sid))
        db.commit()

        resp = client.post(f'/api/scenarios/{sid}/aar')

        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['score'], int)
        assert 'aar' in data

    def test_aar_recovers_from_unreadable_http_json(self, client, monkeypatch):
        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError('bad aar payload')

        create = client.post('/api/scenarios', json={
            'type': 'evacuation',
            'title': 'Unreadable AAR',
        })
        sid = create.get_json()['id']
        client.put(f'/api/scenarios/{sid}', json={
            'decisions': [{'phase': 1, 'choice': 'evacuate'}],
            'complications': [],
        })

        monkeypatch.setattr(preparedness_module.ollama, 'running', lambda: True)
        monkeypatch.setattr(preparedness_module.ollama, 'list_models', lambda: [{'name': 'test-model'}])
        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _FakeResponse())

        resp = client.post(f'/api/scenarios/{sid}/aar')

        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data['score'], int)
        assert 'aar' in data


class TestPreparednessAlertSummary:
    def test_alert_summary_recovers_from_unreadable_ai_payload(self, client, db, monkeypatch):
        class _FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError('bad summary payload')

        db.execute(
            'INSERT INTO alerts (alert_type, severity, title, message, dismissed) VALUES (?, ?, ?, ?, ?)',
            ('system', 'warning', 'Weather Alert', 'Heavy rain expected', 0),
        )
        db.commit()

        monkeypatch.setattr(preparedness_module.ollama, 'running', lambda: True)
        monkeypatch.setattr(preparedness_module.ollama, 'list_models', lambda: [{'name': 'test-model'}])
        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _FakeResponse())

        resp = client.post('/api/alerts/generate-summary')

        assert resp.status_code == 200
        data = resp.get_json()
        assert 'AI summary unavailable' in data['summary']

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
