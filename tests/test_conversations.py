"""Tests for AI conversation API routes."""

import json


class TestConversationsList:
    def test_empty_list(self, client):
        resp = client.get('/api/conversations')
        assert resp.status_code == 200
        assert resp.get_json() == []


class TestConversationsCreate:
    def test_create_conversation(self, client):
        resp = client.post('/api/conversations', json={
            'title': 'Water Purification Help',
            'model': 'llama3',
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data['title'] == 'Water Purification Help'
        assert data['model'] == 'llama3'
        assert data['id'] is not None

    def test_create_with_defaults(self, client):
        resp = client.post('/api/conversations', json={})
        assert resp.status_code == 201
        assert resp.get_json()['title'] == 'New Chat'


class TestConversationsGet:
    def test_get_conversation(self, client):
        create = client.post('/api/conversations', json={'title': 'Test Chat'})
        cid = create.get_json()['id']
        resp = client.get(f'/api/conversations/{cid}')
        assert resp.status_code == 200
        assert resp.get_json()['title'] == 'Test Chat'

    def test_get_nonexistent(self, client):
        resp = client.get('/api/conversations/99999')
        assert resp.status_code == 404


class TestConversationsUpdate:
    def test_update_messages(self, client):
        create = client.post('/api/conversations', json={'title': 'Chat'})
        cid = create.get_json()['id']
        messages = json.dumps([
            {'role': 'user', 'content': 'How do I purify water?'},
            {'role': 'assistant', 'content': 'Boiling is the most reliable method.'},
        ])
        resp = client.put(f'/api/conversations/{cid}', json={'messages': messages})
        assert resp.status_code == 200
        saved = client.get(f'/api/conversations/{cid}').get_json()
        stored_messages = json.loads(saved['messages'])
        assert isinstance(stored_messages, list)
        assert stored_messages[0]['content'] == 'How do I purify water?'

    def test_rename_conversation(self, client):
        create = client.post('/api/conversations', json={'title': 'Old Title'})
        cid = create.get_json()['id']
        resp = client.patch(f'/api/conversations/{cid}', json={'title': 'New Title'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'renamed'
        # Verify via GET
        convo = client.get(f'/api/conversations/{cid}').get_json()
        assert convo['title'] == 'New Title'


class TestConversationsDelete:
    def test_delete_conversation(self, client):
        create = client.post('/api/conversations', json={'title': 'TempConvoDelete'})
        cid = create.get_json()['id']
        resp = client.delete(f'/api/conversations/{cid}')
        assert resp.status_code == 200
        convos = client.get('/api/conversations').get_json()
        assert not any(c['id'] == cid for c in convos)

    def test_delete_all(self, client):
        client.post('/api/conversations', json={'title': 'A'})
        client.post('/api/conversations', json={'title': 'B'})
        resp = client.delete('/api/conversations/all')
        assert resp.status_code == 200
        assert client.get('/api/conversations').get_json() == []


class TestConversationsSearch:
    def test_search_by_title(self, client):
        client.post('/api/conversations', json={'title': 'Water purification guide'})
        client.post('/api/conversations', json={'title': 'Radio setup help'})
        resp = client.get('/api/conversations/search?q=water')
        data = resp.get_json()
        assert len(data) == 1
        assert 'Water' in data[0]['title']

    def test_search_empty_query(self, client):
        resp = client.get('/api/conversations/search?q=')
        assert resp.status_code == 200


class TestConversationBranching:
    def test_branch_conversation(self, client):
        create = client.post('/api/conversations', json={'title': 'Main Chat'})
        cid = create.get_json()['id']
        messages = json.dumps([
            {'role': 'user', 'content': 'Q1'},
            {'role': 'assistant', 'content': 'A1'},
            {'role': 'user', 'content': 'Q2'},
        ])
        client.put(f'/api/conversations/{cid}', json={'messages': messages})
        resp = client.post(f'/api/conversations/{cid}/branch', json={'from_index': 1})
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        assert [m['content'] for m in data['messages']] == ['Q1', 'A1']

    def test_list_branches(self, client):
        create = client.post('/api/conversations', json={'title': 'Branch Test'})
        cid = create.get_json()['id']
        resp = client.get(f'/api/conversations/{cid}/branches')
        assert resp.status_code == 200

    def test_branch_conversation_recovers_from_corrupted_messages(self, client, db):
        create = client.post('/api/conversations', json={'title': 'Broken Chat'})
        cid = create.get_json()['id']
        db.execute('UPDATE conversations SET messages = ? WHERE id = ?', ('{broken', cid))
        db.commit()

        resp = client.post(f'/api/conversations/{cid}/branch', json={'from_index': 2})

        assert resp.status_code in (200, 201)
        assert resp.get_json()['messages'] == []


class TestConversationExport:
    def test_export_conversation(self, client):
        create = client.post('/api/conversations', json={'title': 'Export Test'})
        cid = create.get_json()['id']
        resp = client.get(f'/api/conversations/{cid}/export')
        assert resp.status_code == 200

    def test_export_conversation_recovers_from_corrupted_messages(self, client, db):
        create = client.post('/api/conversations', json={'title': 'Broken Export'})
        cid = create.get_json()['id']
        db.execute('UPDATE conversations SET messages = ? WHERE id = ?', ('{broken', cid))
        db.commit()

        resp = client.get(f'/api/conversations/{cid}/export')

        assert resp.status_code == 200
        assert '# Broken Export' in resp.get_data(as_text=True)
