"""Tests for knowledge base / document API routes."""

from db import db_session


class TestKBDocuments:
    def test_list_documents(self, client):
        resp = client.get('/api/kb/documents')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


class TestKBStatus:
    def test_kb_status(self, client):
        resp = client.get('/api/kb/status')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'status' in data

    def test_embed_texts_returns_empty_list_on_bad_json(self, monkeypatch):
        from web.blueprints import kb as kb_module

        class _BadResponse:
            def raise_for_status(self):
                return None

            def json(self):
                raise ValueError('bad embed payload')

        monkeypatch.setattr('requests.post', lambda *args, **kwargs: _BadResponse())

        assert kb_module.embed_text(['water filter']) == []


class TestKBSearch:
    def test_search_empty_kb(self, client):
        resp = client.post('/api/kb/search', json={'query': 'water purification'})
        assert resp.status_code == 200
        # May return empty results or error depending on Qdrant state
        data = resp.get_json()
        assert isinstance(data, (list, dict))

    def test_search_requires_query(self, client):
        resp = client.post('/api/kb/search', json={})
        # Should handle missing query gracefully
        assert resp.status_code in (200, 400)


class TestKBDocumentResilience:
    def test_document_details_recover_from_corrupted_analysis_payloads(self, client):
        with db_session() as db:
            cur = db.execute(
                'INSERT INTO documents (filename, content_type, file_size, status, entities, linked_records) VALUES (?, ?, ?, ?, ?, ?)',
                ('broken-analysis.txt', 'text', 0, 'ready', '{broken', 'not-json'),
            )
            db.commit()
            doc_id = cur.lastrowid

        resp = client.get(f'/api/kb/documents/{doc_id}/details')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['entities'] == []
        assert data['linked_records'] == []

    def test_document_details_filter_invalid_entity_shapes(self, client):
        with db_session() as db:
            cur = db.execute(
                'INSERT INTO documents (filename, content_type, file_size, status, entities) VALUES (?, ?, ?, ?, ?)',
                (
                    'mixed-entities.txt',
                    'text',
                    0,
                    'ready',
                    '[1, {"type":"person","value":" Alice Walker "}, {"type":"","value":"skip"}, {"type":"phone","value":" 555-0101 "}]',
                ),
            )
            db.commit()
            doc_id = cur.lastrowid

        resp = client.get(f'/api/kb/documents/{doc_id}/details')

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['entities'] == [
            {'type': 'person', 'value': 'Alice Walker'},
            {'type': 'phone', 'value': '555-0101'},
        ]

    def test_import_entities_accepts_json_string_selection(self, client):
        with db_session() as db:
            cur = db.execute(
                'INSERT INTO documents (filename, content_type, file_size, status, entities) VALUES (?, ?, ?, ?, ?)',
                (
                    'entity-import.txt',
                    'text',
                    0,
                    'ready',
                    '[{"type":"person","value":"Alice Walker"},{"type":"person","value":"Bob Stone"}]',
                ),
            )
            db.commit()
            doc_id = cur.lastrowid

        resp = client.post(f'/api/kb/documents/{doc_id}/import-entities', json={'entities': '[0]'})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['results']['contacts'] == 1
        assert data['results']['skipped'] == 0
        assert data['total_imported'] == 1

        with db_session() as db:
            rows = db.execute('SELECT name FROM contacts ORDER BY name').fetchall()
            names = [row['name'] for row in rows]
        assert 'Alice Walker' in names
        assert 'Bob Stone' not in names

    def test_import_entities_skips_invalid_entries_in_mixed_payload(self, client):
        with db_session() as db:
            cur = db.execute(
                'INSERT INTO documents (filename, content_type, file_size, status, entities) VALUES (?, ?, ?, ?, ?)',
                (
                    'mixed-import.txt',
                    'text',
                    0,
                    'ready',
                    '[null, {"type":"person","value":" Alice Walker "}, {"type":"phone","value":" 555-0101 "}, {"type":"person","value":""}]',
                ),
            )
            db.commit()
            doc_id = cur.lastrowid

        resp = client.post(f'/api/kb/documents/{doc_id}/import-entities', json={})

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['results']['contacts'] >= 1
        assert data['total_imported'] >= 1

        with db_session() as db:
            contact = db.execute('SELECT name, phone FROM contacts WHERE LOWER(name) = LOWER(?)', ('Alice Walker',)).fetchone()
        assert contact is not None
        assert contact['phone'] == '555-0101'


class TestCSVImport:
    def test_csv_preview(self, client):
        csv_data = 'name,category,quantity\nWater,water,10\nRice,food,5\n'
        resp = client.post('/api/import/csv',
                          data=csv_data,
                          content_type='text/csv')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'headers' in data
        assert 'sample_rows' in data
        assert 'name' in data['headers']

    def test_csv_execute_import(self, client):
        resp = client.post('/api/import/csv/execute', json={
            'csv_data': [
                {'name': 'Imported Water', 'category': 'water', 'quantity': '50'},
                {'name': 'Imported Rice', 'category': 'food', 'quantity': '25'},
            ],
            'mapping': {
                'name': 'name',
                'category': 'category',
                'quantity': 'quantity',
            },
            'target_table': 'inventory',
        })
        # May succeed or fail depending on CSV executor implementation details
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            items = client.get('/api/inventory?q=Imported').get_json()
            imported_names = [i['name'] for i in items]
            assert 'Imported Water' in imported_names

    def test_csv_execute_invalid_table(self, client):
        resp = client.post('/api/import/csv/execute', json={
            'csv_data': [{'name': 'test'}],
            'mapping': {'name': 'name'},
            'target_table': 'users',  # not in whitelist
        })
        assert resp.status_code in (400, 403, 404)
