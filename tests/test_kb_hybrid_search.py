"""Tests for hybrid lexical/vector KB retrieval with citations."""

from db import db_session


class TestHybridSearchMerge:
    def test_merge_deduplicates_by_doc_chunk(self):
        from web.blueprints.kb import _merge_results
        vec = [{'text': 'a', 'doc_id': 1, 'chunk_index': 0, 'score': 0.9, 'source': 'vector', 'filename': 'f'}]
        lex = [{'text': 'a', 'doc_id': 1, 'chunk_index': 0, 'score': 5.0, 'source': 'lexical', 'filename': 'f'}]
        merged = _merge_results(vec, lex, limit=5)
        assert len(merged) == 1
        assert merged[0]['source'] == 'hybrid'

    def test_merge_combines_different_chunks(self):
        from web.blueprints.kb import _merge_results
        vec = [{'text': 'a', 'doc_id': 1, 'chunk_index': 0, 'score': 0.9, 'source': 'vector', 'filename': 'f'}]
        lex = [{'text': 'b', 'doc_id': 1, 'chunk_index': 1, 'score': 5.0, 'source': 'lexical', 'filename': 'f'}]
        merged = _merge_results(vec, lex, limit=5)
        assert len(merged) == 2

    def test_merge_respects_limit(self):
        from web.blueprints.kb import _merge_results
        vec = [{'text': f'v{i}', 'doc_id': i, 'chunk_index': 0, 'score': 0.5, 'source': 'vector', 'filename': 'f'} for i in range(10)]
        merged = _merge_results(vec, [], limit=3)
        assert len(merged) == 3

    def test_merge_empty_inputs(self):
        from web.blueprints.kb import _merge_results
        assert _merge_results([], [], limit=5) == []

    def test_merge_does_not_collapse_null_doc_id_different_files(self):
        from web.blueprints.kb import _merge_results
        vec = [
            {'text': 'a', 'doc_id': None, 'chunk_index': 0, 'score': 0.9, 'source': 'vector', 'filename': 'a.pdf'},
            {'text': 'b', 'doc_id': None, 'chunk_index': 0, 'score': 0.8, 'source': 'vector', 'filename': 'b.pdf'},
        ]
        merged = _merge_results(vec, [], limit=5)
        assert len(merged) == 2


class TestLexicalSearch:
    def test_lexical_search_with_seeded_chunks(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO kb_chunks (doc_id, chunk_index, text, filename) VALUES (?, ?, ?, ?)',
                (99999, 0, 'Emergency preparedness involves stockpiling supplies and water', 'test.txt')
            )
            db.commit()
        from web.blueprints.kb import _lexical_search
        results = _lexical_search('preparedness', limit=5)
        assert len(results) >= 1
        assert any('preparedness' in r['text'].lower() for r in results)

    def test_lexical_search_no_results(self, client):
        from web.blueprints.kb import _lexical_search
        results = _lexical_search('xyzzynonexistentterm12345', limit=5)
        assert results == []


class TestHybridSearchEndpoint:
    def test_search_empty_query(self, client):
        resp = client.post('/api/kb/search', json={'query': ''})
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_search_lexical_mode(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO kb_chunks (doc_id, chunk_index, text, filename) VALUES (?, ?, ?, ?)',
                (88888, 0, 'Solar panel installation guide for off-grid homes', 'solar.pdf')
            )
            db.commit()
        resp = client.post('/api/kb/search', json={
            'query': 'solar panel',
            'mode': 'lexical',
            'limit': 5,
        })
        assert resp.status_code == 200
        results = resp.get_json()
        assert isinstance(results, list)

    def test_search_hybrid_mode_default(self, client):
        resp = client.post('/api/kb/search', json={'query': 'test', 'limit': 3})
        assert resp.status_code == 200
