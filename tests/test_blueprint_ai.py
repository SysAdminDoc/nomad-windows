"""Tests for AI-related routes: memory, training datasets, training jobs."""

import json


class TestAIMemory:
    def test_list_memory_empty(self, client):
        resp = client.get('/api/ai/memory')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'memories' in data

    def test_list_memory_recovers_from_corrupted_storage(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_memory', ?)", ('{broken',))
        db.commit()

        resp = client.get('/api/ai/memory')

        assert resp.status_code == 200
        assert resp.get_json()['memories'] == []

    def test_save_memory(self, client):
        resp = client.post('/api/ai/memory', json={
            'fact': 'The water filter needs replacing every 3 months'
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'saved'

    def test_save_and_list_memory(self, client):
        client.post('/api/ai/memory', json={
            'fact': 'Solar panels produce 200W peak'
        })
        resp = client.get('/api/ai/memory')
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data['memories']) >= 1

    def test_clear_memory(self, client):
        client.post('/api/ai/memory', json={'fact': 'temp fact'})
        resp = client.delete('/api/ai/memory')
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'cleared'

    def test_save_memory_recovers_from_corrupted_storage(self, client, db):
        db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('ai_memory', ?)", ('{\"fact\":\"not-a-list\"}',))
        db.commit()

        resp = client.post('/api/ai/memory', json={'fact': 'Fresh fact'})

        assert resp.status_code == 200
        assert resp.get_json()['count'] == 1

    def test_save_memory_no_fact_returns_400(self, client):
        resp = client.post('/api/ai/memory', json={})
        assert resp.status_code == 400

    def test_save_empty_fact_returns_400(self, client):
        resp = client.post('/api/ai/memory', json={'fact': ''})
        assert resp.status_code == 400


class TestAITrainingDatasets:
    def test_list_datasets(self, client):
        resp = client.get('/api/ai/training/datasets')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_create_dataset(self, client):
        resp = client.post('/api/ai/training/datasets', json={
            'name': 'Test Dataset',
            'source': 'upload',
        })
        assert resp.status_code in (200, 201)

    def test_create_dataset_skips_corrupted_conversation_messages(self, client, db):
        valid_messages = json.dumps([
            {'role': 'user', 'content': 'How do I purify water?'},
            {'role': 'assistant', 'content': 'Boil it first.'},
        ])
        db.execute(
            'INSERT INTO conversations (title, model, messages) VALUES (?, ?, ?)',
            ('Valid Conversation', 'llama3', valid_messages),
        )
        db.execute(
            'INSERT INTO conversations (title, model, messages) VALUES (?, ?, ?)',
            ('Broken Conversation', 'llama3', '{broken'),
        )
        db.commit()

        resp = client.post('/api/ai/training/datasets', json={
            'name': 'Recovered Dataset',
            'source': 'conversations',
        })

        assert resp.status_code in (200, 201)
        assert resp.get_json()['records'] == 1

    def test_list_training_jobs(self, client):
        resp = client.get('/api/ai/training/jobs')
        assert resp.status_code == 200


class TestAIHttpResilience:
    def test_context_usage_recovers_from_malformed_model_info(self, client, monkeypatch):
        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad model info payload')

        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _BadResponse())

        resp = client.post('/api/ai/context-usage', json={
            'model': 'broken-model',
            'messages': [{'role': 'user', 'content': 'Check context window'}],
            'system_prompt': 'Be concise.',
        })

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['max_tokens'] == 4096
        assert data['remaining'] >= 0

    def test_model_info_recovers_from_malformed_show_payload(self, client, monkeypatch):
        class _BadResponse:
            ok = True

            def json(self):
                raise ValueError('bad show payload')

        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _BadResponse())

        resp = client.get('/api/ai/model-info/demo-model')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['name'] == 'demo-model'
        assert data['parameters'] == 'Unknown'
        assert data['quantization'] == 'Unknown'
