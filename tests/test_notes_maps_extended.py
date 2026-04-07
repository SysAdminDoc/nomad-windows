"""Extended tests for notes and maps blueprints."""

import json


class TestNotesJournal:
    def test_journal_list(self, client):
        resp = client.get('/api/journal')
        assert resp.status_code == 200

    def test_journal_create(self, client):
        resp = client.post('/api/journal', json={
            'entry': 'Day 1: Systems operational.',
            'mood': 'hopeful',
            'tags': 'day1,operations',
        })
        assert resp.status_code in (200, 201)

    def test_journal_delete_nonexistent(self, client):
        resp = client.delete('/api/journal/999999')
        assert resp.status_code == 404


class TestNotesTemplates:
    def test_templates_list(self, client):
        resp = client.get('/api/notes/templates')
        assert resp.status_code == 200


class TestNotesSearch:
    def test_search_notes_titles(self, client):
        client.post('/api/notes', json={
            'title': 'Searchable Note XYZ', 'content': 'body text'
        })
        resp = client.get('/api/notes/search-titles?q=Searchable')
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)


class TestMapsRoutes:
    def test_routes_list(self, client):
        resp = client.get('/api/maps/routes')
        assert resp.status_code == 200

    def test_route_create(self, client):
        resp = client.post('/api/maps/routes', json={
            'name': 'Bug-Out Route Alpha',
            'waypoint_ids': '[]',
        })
        assert resp.status_code in (200, 201)

    def test_route_delete_nonexistent(self, client):
        resp = client.delete('/api/maps/routes/999999')
        assert resp.status_code == 404


class TestMapsAnnotations:
    def test_annotations_list(self, client):
        resp = client.get('/api/maps/annotations')
        assert resp.status_code == 200

    def test_annotation_create(self, client):
        resp = client.post('/api/maps/annotations', json={
            'type': 'marker', 'lat': 40.0, 'lng': -74.0,
            'title': 'Observation Point', 'color': '#ff0000',
        })
        assert resp.status_code in (200, 201)

    def test_annotation_delete_nonexistent(self, client):
        resp = client.delete('/api/maps/annotations/999999')
        assert resp.status_code == 404


class TestMapsContours:
    def test_contours_endpoint(self, client):
        resp = client.get('/api/maps/contours?lat=40&lng=-74&radius_km=10&interval=100')
        assert resp.status_code == 200


class TestMapsMinimapData:
    def test_minimap_data(self, client):
        resp = client.get('/api/maps/minimap-data')
        assert resp.status_code == 200


class TestMapsGPSTracks:
    def test_tracks_list(self, client):
        resp = client.get('/api/tracks')
        assert resp.status_code == 200


class TestGeocode:
    def test_geocode_search(self, client):
        resp = client.get('/api/geocode/search?q=test')
        assert resp.status_code == 200

    def test_geocode_reverse(self, client):
        resp = client.get('/api/geocode/reverse?lat=40.0&lng=-74.0')
        assert resp.status_code == 200
