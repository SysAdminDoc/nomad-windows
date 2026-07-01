"""Payload validation tests for the training_knowledge blueprint.

Covers /api/training/skills POST, /api/training/courses POST,
and /api/training/flashcards POST.
"""


class TestTrainingKnowledgePayloadValidation:
    """Verify the validate_json decorator rejects malformed, non-object,
    and wrong-shape payloads on representative training POST routes."""

    # -- /api/training/skills POST --

    def test_skills_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/training/skills',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_skills_rejects_non_object_json(self, client):
        resp = client.post(
            '/api/training/skills',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_skills_rejects_wrong_shape_fields(self, client):
        cases = [
            {'person_name': 123},
            {'level': 'expert'},
            {'certified': 'yes'},
        ]
        for payload in cases:
            resp = client.post('/api/training/skills', json=payload)
            assert resp.status_code == 400, payload
            assert resp.get_json()['error'] == 'Validation failed'

    # -- /api/training/courses POST --

    def test_courses_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/training/courses',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_courses_rejects_non_object_json(self, client):
        resp = client.post(
            '/api/training/courses',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_courses_rejects_wrong_shape_fields(self, client):
        cases = [
            {'title': []},
            {'estimated_hours': 'many'},
            {'max_students': True},
        ]
        for payload in cases:
            resp = client.post('/api/training/courses', json=payload)
            assert resp.status_code == 400, payload
            assert resp.get_json()['error'] == 'Validation failed'

    # -- /api/training/flashcards POST --

    def test_flashcards_rejects_malformed_json(self, client):
        resp = client.post(
            '/api/training/flashcards',
            data='{bad',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be valid JSON'

    def test_flashcards_rejects_non_object_json(self, client):
        resp = client.post(
            '/api/training/flashcards',
            data='[]',
            content_type='application/json',
        )
        assert resp.status_code == 400
        assert resp.get_json()['error'] == 'Request body must be a JSON object'

    def test_flashcards_rejects_wrong_shape_fields(self, client):
        cases = [
            {'front_text': 99},
            {'difficulty': 'hard'},
            {'tags': 'science,math'},
        ]
        for payload in cases:
            resp = client.post('/api/training/flashcards', json=payload)
            assert resp.status_code == 400, payload
            assert resp.get_json()['error'] == 'Validation failed'
