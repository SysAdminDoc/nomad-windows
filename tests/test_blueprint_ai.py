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


class TestRAGScope:
    """Phase A3: RAG scope manager.

    Covers: seeding, list/update/reset/preview endpoints, scope-driven context
    builder, SQL-identifier validation, delete-builtin rejection, custom table
    inserts, and summary-level row-capping."""

    def test_seed_populates_builtin_entries(self, client):
        resp = client.get('/api/ai/rag/scope')
        assert resp.status_code == 200
        data = resp.get_json()
        names = {r['table_name'] for r in data['scope']}
        for t in ('inventory', 'contacts', 'patients', 'fuel_storage',
                  'ammo_inventory', 'equipment_log', 'alerts',
                  'weather_log', 'power_log', 'incidents'):
            assert t in names, f'missing builtin scope entry: {t}'
        weights = [r['weight'] for r in data['scope']]
        assert weights == sorted(weights, reverse=True)

    def test_builtins_enabled_by_default(self, client):
        resp = client.get('/api/ai/rag/scope')
        entries = {r['table_name']: r for r in resp.get_json()['scope']}
        assert entries['inventory']['enabled'] is True
        assert entries['contacts']['enabled'] is True
        assert entries['vehicles']['enabled'] is False
        assert entries['waypoints']['enabled'] is False

    def test_update_scope_toggle_enabled(self, client):
        resp = client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'enabled': False,
        })
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'updated'
        after = client.get('/api/ai/rag/scope').get_json()
        entries = {r['table_name']: r for r in after['scope']}
        assert entries['inventory']['enabled'] is False

    def test_update_scope_weight_and_max_rows(self, client):
        resp = client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'weight': 999, 'max_rows': 25,
        })
        assert resp.status_code == 200
        entries = {r['table_name']: r for r in client.get('/api/ai/rag/scope').get_json()['scope']}
        assert entries['inventory']['weight'] == 999
        assert entries['inventory']['max_rows'] == 25

    def test_max_rows_is_clamped_to_500(self, client):
        client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'max_rows': 99999,
        })
        entries = {r['table_name']: r for r in client.get('/api/ai/rag/scope').get_json()['scope']}
        assert entries['inventory']['max_rows'] == 500

    def test_rejects_invalid_table_name(self, client):
        resp = client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory; DROP TABLE inventory', 'enabled': True,
        })
        assert resp.status_code == 400

    def test_rejects_non_integer_weight(self, client):
        resp = client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'weight': 'high',
        })
        assert resp.status_code == 400

    def test_update_requires_at_least_one_field(self, client):
        resp = client.post('/api/ai/rag/scope', json={'table_name': 'inventory'})
        assert resp.status_code == 400

    def test_custom_entry_requires_label(self, client):
        resp = client.post('/api/ai/rag/scope', json={
            'table_name': 'activity_log', 'enabled': True,
        })
        assert resp.status_code == 400

    def test_custom_entry_rejects_unknown_table(self, client):
        resp = client.post('/api/ai/rag/scope', json={
            'table_name': 'no_such_table_anywhere',
            'label': 'MYSTERY', 'enabled': True,
        })
        assert resp.status_code == 400

    def test_custom_entry_insert_and_delete(self, client):
        create = client.post('/api/ai/rag/scope', json={
            'table_name': 'activity_log',
            'label': 'ACTIVITY LOG',
            'formatter': 'generic',
            'columns_json': ['event', 'service', 'created_at'],
            'weight': 10, 'max_rows': 5, 'enabled': True,
        })
        assert create.status_code == 200
        assert create.get_json()['status'] == 'created'
        names = {r['table_name'] for r in client.get('/api/ai/rag/scope').get_json()['scope']}
        assert 'activity_log' in names
        rm = client.delete('/api/ai/rag/scope/activity_log')
        assert rm.status_code == 200
        assert rm.get_json()['status'] == 'deleted'
        names2 = {r['table_name'] for r in client.get('/api/ai/rag/scope').get_json()['scope']}
        assert 'activity_log' not in names2

    def test_delete_builtin_rejected(self, client):
        resp = client.delete('/api/ai/rag/scope/inventory')
        assert resp.status_code == 400
        assert 'disable' in resp.get_json()['error'].lower()

    def test_reset_restores_defaults(self, client):
        client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'enabled': False, 'weight': 0, 'max_rows': 1,
        })
        reset = client.post('/api/ai/rag/scope/reset', json={})
        assert reset.status_code == 200
        entries = {r['table_name']: r for r in client.get('/api/ai/rag/scope').get_json()['scope']}
        assert entries['inventory']['enabled'] is True
        assert entries['inventory']['weight'] == 100
        assert entries['inventory']['max_rows'] == 10

    def test_preview_shape(self, client):
        resp = client.get('/api/ai/rag/preview')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['detail_level'] == 'full'
        assert 'sections' in data
        assert 'payload' in data
        assert data['section_count'] == len(data['sections'])
        assert data['char_count'] == len(data['payload'])

    def test_preview_summary_level(self, client):
        resp = client.get('/api/ai/rag/preview?detail_level=summary')
        assert resp.status_code == 200
        assert resp.get_json()['detail_level'] == 'summary'

    def test_preview_unknown_detail_level_falls_back_to_full(self, client):
        resp = client.get('/api/ai/rag/preview?detail_level=junk')
        assert resp.status_code == 200
        assert resp.get_json()['detail_level'] == 'full'

    def test_disabled_table_excluded_from_context(self, client, db):
        db.execute(
            "INSERT INTO inventory (name, quantity, unit, category) "
            "VALUES ('Rice', 50, 'lbs', 'Food')"
        )
        db.commit()
        with_it = client.get('/api/ai/rag/preview').get_json()
        assert any('INVENTORY:' in s for s in with_it['sections'])
        client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'enabled': False,
        })
        after = client.get('/api/ai/rag/preview').get_json()
        assert not any('INVENTORY:' in s for s in after['sections'])

    def test_generic_formatter_works_on_custom_entry(self, client, db):
        db.execute(
            "INSERT INTO activity_log (event, service, created_at) "
            "VALUES ('test_event', 'test_service', datetime('now'))"
        )
        db.commit()
        client.post('/api/ai/rag/scope', json={
            'table_name': 'activity_log',
            'label': 'ACTIVITY',
            'formatter': 'generic',
            'columns_json': ['event', 'service'],
            'weight': 15, 'max_rows': 5, 'enabled': True,
        })
        preview = client.get('/api/ai/rag/preview').get_json()
        activity_sections = [s for s in preview['sections'] if s.startswith('ACTIVITY:')]
        assert activity_sections, 'generic-formatter section not emitted'
        assert 'event=test_event' in activity_sections[0]
        assert 'service=test_service' in activity_sections[0]

    def test_summary_level_caps_rows(self, client, db):
        for i in range(25):
            db.execute(
                "INSERT INTO inventory (name, quantity, unit, category) VALUES (?, ?, 'ea', 'Food')",
                (f'Item{i:03d}', i + 1),
            )
        db.commit()
        client.post('/api/ai/rag/scope', json={
            'table_name': 'inventory', 'max_rows': 50,
        })
        full = client.get('/api/ai/rag/preview?detail_level=full').get_json()
        summary = client.get('/api/ai/rag/preview?detail_level=summary').get_json()
        assert full['char_count'] > summary['char_count']

    def test_rag_scope_missing_table_returns_empty_scope(self, client, db):
        db.execute('DROP TABLE IF EXISTS rag_scope')
        db.commit()
        resp = client.get('/api/ai/rag/scope')
        assert resp.status_code == 200
        assert resp.get_json()['scope'] == []
        preview = client.get('/api/ai/rag/preview')
        assert preview.status_code == 200
        assert preview.get_json()['sections'] == []
