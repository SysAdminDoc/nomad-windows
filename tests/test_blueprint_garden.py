"""Tests for garden blueprint routes."""

import json

from db import db_session


class TestGardenPlotsCRUD:
    def test_list_plots(self, client):
        resp = client.get('/api/garden/plots')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_plot(self, client):
        resp = client.post('/api/garden/plots', json={
            'name': 'Raised Bed B',
            'width_ft': 4,
            'length_ft': 12,
            'sun_exposure': 'partial',
            'soil_type': 'clay',
        })
        assert resp.status_code == 201

    def test_update_plot(self, client):
        client.post('/api/garden/plots', json={'name': 'Update Test Plot'})
        plots = client.get('/api/garden/plots').get_json()
        plot = next((p for p in plots if p['name'] == 'Update Test Plot'), None)
        assert plot is not None
        resp = client.put(f'/api/garden/plots/{plot["id"]}', json={
            'name': 'Updated Plot Name',
            'soil_type': 'sandy',
        })
        assert resp.status_code == 200

    def test_delete_plot(self, client):
        client.post('/api/garden/plots', json={'name': 'Delete Me Plot'})
        plots = client.get('/api/garden/plots').get_json()
        plot = next((p for p in plots if p['name'] == 'Delete Me Plot'), None)
        assert plot is not None
        resp = client.delete(f'/api/garden/plots/{plot["id"]}')
        assert resp.status_code == 200

    def test_plots_geo(self, client):
        resp = client.get('/api/garden/plots/geo')
        assert resp.status_code == 200

    def test_plots_geo_recovers_from_corrupted_boundary_geojson(self, client):
        with db_session() as db:
            db.execute(
                'INSERT INTO garden_plots (name, lat, lng, boundary_geojson) VALUES (?, ?, ?, ?)',
                ('Broken Boundary Plot', 35.1, -80.8, '{broken'),
            )
            db.commit()

        resp = client.get('/api/garden/plots/geo')
        assert resp.status_code == 200
        data = resp.get_json()
        feature = next((f for f in data['features'] if f['properties']['name'] == 'Broken Boundary Plot'), None)
        assert feature is not None
        assert feature['geometry']['type'] == 'Point'
        assert feature['geometry']['coordinates'] == [-80.8, 35.1]

    def test_create_plot_normalizes_dict_boundary_geojson(self, client):
        resp = client.post('/api/garden/plots', json={
            'name': 'GeoJSON Plot',
            'lat': 34.5,
            'lng': -81.2,
            'boundary_geojson': {
                'type': 'Polygon',
                'coordinates': [[[-81.2, 34.5], [-81.1, 34.5], [-81.1, 34.6], [-81.2, 34.5]]],
            },
        })
        assert resp.status_code == 201

        with db_session() as db:
            row = db.execute('SELECT boundary_geojson FROM garden_plots WHERE name = ?', ('GeoJSON Plot',)).fetchone()
        assert row is not None
        stored = json.loads(row['boundary_geojson'])
        assert stored['type'] == 'Polygon'


class TestGardenSeedsCRUD:
    def test_list_seeds(self, client):
        resp = client.get('/api/garden/seeds')
        assert resp.status_code == 200

    def test_create_seed(self, client):
        resp = client.post('/api/garden/seeds', json={
            'species': 'Cucumber',
            'variety': 'English',
            'quantity': 30,
            'days_to_maturity': 60,
        })
        assert resp.status_code == 201

    def test_delete_seed(self, client):
        client.post('/api/garden/seeds', json={'species': 'Delete Seed'})
        seeds = client.get('/api/garden/seeds').get_json()
        seed = next((s for s in seeds if s['species'] == 'Delete Seed'), None)
        assert seed is not None
        resp = client.delete(f'/api/garden/seeds/{seed["id"]}')
        assert resp.status_code == 200


class TestGardenHarvests:
    def test_list_harvests(self, client):
        resp = client.get('/api/garden/harvests')
        assert resp.status_code == 200

    def test_create_harvest(self, client):
        resp = client.post('/api/garden/harvests', json={
            'crop': 'Zucchini',
            'quantity': 3.5,
            'unit': 'lbs',
        })
        assert resp.status_code == 201


class TestGardenZone:
    def test_get_zone(self, client):
        resp = client.get('/api/garden/zone')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'zone' in data


class TestPreservationLog:
    def test_list_preservation(self, client):
        resp = client.get('/api/garden/preservation')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_preservation(self, client):
        resp = client.post('/api/garden/preservation', json={
            'crop': 'Tomatoes',
            'method': 'canning',
            'quantity': 12,
            'unit': 'quarts',
            'shelf_life_months': 18,
        })
        assert resp.status_code in (200, 201)

    def test_delete_preservation(self, client):
        client.post('/api/garden/preservation', json={
            'crop': 'Delete Preserves',
            'method': 'drying',
        })
        items = client.get('/api/garden/preservation').get_json()
        target = next((i for i in items if i.get('crop') == 'Delete Preserves'), None)
        if target:
            resp = client.delete(f'/api/garden/preservation/{target["id"]}')
            assert resp.status_code == 200


class TestYieldAnalysis:
    def test_yield_analysis(self, client):
        resp = client.get('/api/garden/yield-analysis')
        assert resp.status_code == 200

    def test_calendar(self, client):
        resp = client.get('/api/garden/calendar')
        assert resp.status_code == 200
