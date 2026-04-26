"""Smoke tests for the movement_ops blueprint.

Covers all 15+ routes across:
  Movement Plans CRUD     — GET list, GET detail, POST, PUT, DELETE
  March Rate Calculator   — POST /api/movement/march-rate
  Pace Count Calculator   — POST /api/movement/pace-count
  Alt Vehicles CRUD       — GET, POST, PUT, DELETE
  Route Hazards CRUD      — GET, POST, PUT, DELETE
  Route Recon CRUD        — GET, POST, DELETE
  Vehicle Loading Plans   — GET, POST, PUT, DELETE
  Go/No-Go Matrix         — GET, POST, PUT, DELETE, evaluate
  Movement Summary        — GET /api/movement/summary
"""

import pytest
from db import db_session


# ─── helpers ──────────────────────────────────────────────────────────────────

def _seed_evac_plan(db, plan_id, name=None):
    """Insert a minimal evac_plans row so FK constraints pass."""
    db.execute(
        "INSERT OR IGNORE INTO evac_plans (id, name) VALUES (?, ?)",
        (plan_id, name or f'Test Evac Plan {plan_id}'),
    )
    db.commit()


def _create_plan(client, name='Route Alpha', **extra):
    payload = {'name': name, 'plan_type': 'vehicle', 'status': 'draft'}
    payload.update(extra)
    resp = client.post('/api/movement-plans', json=payload)
    assert resp.status_code == 201
    return resp.get_json()


def _create_alt_vehicle(client, name='Bike Rig'):
    resp = client.post('/api/alt-vehicles', json={'name': name, 'vehicle_type': 'bicycle'})
    assert resp.status_code == 201
    return resp.get_json()


def _create_hazard(client, name='River Ford', plan_id=None):
    payload = {'name': name, 'hazard_type': 'flood_zone', 'severity': 'moderate'}
    if plan_id:
        payload['movement_plan_id'] = plan_id
    resp = client.post('/api/route-hazards', json=payload)
    assert resp.status_code == 201
    return resp.get_json()


def _create_recon(client, recon_date='2025-06-01', plan_id=None):
    payload = {'recon_date': recon_date, 'observer': 'Alpha Team',
               'road_condition': 'passable', 'threat_level': 'low'}
    if plan_id:
        payload['movement_plan_id'] = plan_id
    resp = client.post('/api/route-recon', json=payload)
    assert resp.status_code == 201
    return resp.get_json()


def _create_loading(client, vehicle_name='Truck 1'):
    resp = client.post('/api/vehicle-loading', json={
        'vehicle_name': vehicle_name, 'load_order': 1,
        'max_weight_lb': 1000, 'fuel_level_pct': 90,
    })
    assert resp.status_code == 201
    return resp.get_json()


def _create_gonogo(client, criterion='Roads passable', evac_id=None):
    payload = {'criterion': criterion, 'category': 'infrastructure',
               'weight': 2.0, 'current_status': 'unknown'}
    if evac_id:
        payload['evac_plan_id'] = evac_id
    resp = client.post('/api/go-nogo', json=payload)
    assert resp.status_code == 201
    return resp.get_json()


# ─── Movement Plans ───────────────────────────────────────────────────────────

class TestMovementPlansList:
    def test_empty_returns_list(self, client):
        resp = client.get('/api/movement-plans')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_lists_created_plans(self, client):
        _create_plan(client, 'Plan 1')
        _create_plan(client, 'Plan 2')
        resp = client.get('/api/movement-plans')
        assert len(resp.get_json()) == 2

    def test_filter_by_status(self, client):
        _create_plan(client, 'Draft Plan', status='draft')
        _create_plan(client, 'Active Plan', status='active')
        resp = client.get('/api/movement-plans?status=active')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Active Plan'

    def test_filter_by_type(self, client):
        _create_plan(client, 'Foot March', plan_type='foot')
        _create_plan(client, 'Convoy Op', plan_type='convoy')
        resp = client.get('/api/movement-plans?type=foot')
        data = resp.get_json()
        assert all(p['plan_type'] == 'foot' for p in data)


class TestMovementPlansCreate:
    def test_create_minimal(self, client):
        resp = client.post('/api/movement-plans', json={'name': 'Bravo Route'})
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'Bravo Route'
        assert 'id' in body

    def test_create_missing_name_returns_400(self, client):
        resp = client.post('/api/movement-plans', json={'plan_type': 'foot'})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_create_with_full_fields(self, client):
        payload = {
            'name': 'Full Plan',
            'plan_type': 'convoy',
            'origin': 'Base Camp',
            'destination': 'Safe House',
            'distance_miles': 45.5,
            'march_rate_mph': 45.0,
            'notes': 'Night movement preferred',
            'status': 'active',
        }
        resp = client.post('/api/movement-plans', json=payload)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['distance_miles'] == 45.5
        assert body['status'] == 'active'


class TestMovementPlansDetail:
    def test_get_detail(self, client):
        plan = _create_plan(client, 'Detail Test Plan')
        resp = client.get(f"/api/movement-plans/{plan['id']}")
        assert resp.status_code == 200
        assert resp.get_json()['name'] == 'Detail Test Plan'

    def test_get_nonexistent_returns_404(self, client):
        resp = client.get('/api/movement-plans/99999')
        assert resp.status_code == 404

    def test_put_updates_fields(self, client):
        plan = _create_plan(client)
        resp = client.put(f"/api/movement-plans/{plan['id']}",
                          json={'status': 'active', 'notes': 'Updated'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['status'] == 'active'
        assert body['notes'] == 'Updated'

    def test_put_no_fields_returns_400(self, client):
        plan = _create_plan(client)
        resp = client.put(f"/api/movement-plans/{plan['id']}", json={})
        assert resp.status_code == 400

    def test_delete_removes_plan(self, client):
        plan = _create_plan(client)
        pid = plan['id']
        resp = client.delete(f'/api/movement-plans/{pid}')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True
        assert client.get(f'/api/movement-plans/{pid}').status_code == 404

    def test_delete_cascades_to_hazards_and_recon(self, client):
        plan = _create_plan(client)
        pid = plan['id']
        _create_hazard(client, plan_id=pid)
        _create_recon(client, plan_id=pid)
        client.delete(f'/api/movement-plans/{pid}')
        # Hazards and recon tied to the plan should be gone
        hazards = client.get(f'/api/route-hazards?movement_plan_id={pid}').get_json()
        recon = client.get(f'/api/route-recon?movement_plan_id={pid}').get_json()
        assert hazards == []
        assert recon == []

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete('/api/movement-plans/99999')
        assert resp.status_code == 404


# ─── March Rate Calculator ────────────────────────────────────────────────────

class TestMarchRateCalc:
    def test_basic_road_march(self, client):
        resp = client.post('/api/movement/march-rate', json={
            'distance_miles': 10,
            'march_rate_mph': 4.0,
            'rest_min_per_hour': 10,
            'terrain': 'road',
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['distance_miles'] == 10
        assert body['effective_rate_mph'] == 4.0
        assert body['terrain_multiplier'] == 1.0
        assert body['total_hours'] > body['moving_hours']  # rest adds time
        assert 'arrival_estimate' in body

    def test_terrain_multiplier_applied(self, client):
        resp = client.post('/api/movement/march-rate', json={
            'distance_miles': 10,
            'march_rate_mph': 4.0,
            'terrain': 'mountain',
        })
        body = resp.get_json()
        # mountain mult = 0.4 → effective_rate = 1.6
        assert body['effective_rate_mph'] == pytest.approx(1.6, abs=0.01)

    def test_load_penalty_applied(self, client):
        """Heavy load (70 lb) should reduce effective rate compared to no load."""
        no_load = client.post('/api/movement/march-rate', json={
            'distance_miles': 5, 'march_rate_mph': 3.0,
            'terrain': 'road', 'load_lb': 0,
        }).get_json()
        heavy_load = client.post('/api/movement/march-rate', json={
            'distance_miles': 5, 'march_rate_mph': 3.0,
            'terrain': 'road', 'load_lb': 70,
        }).get_json()
        assert heavy_load['effective_rate_mph'] < no_load['effective_rate_mph']

    def test_returns_arrival_estimate_string(self, client):
        resp = client.post('/api/movement/march-rate', json={
            'distance_miles': 20, 'march_rate_mph': 4.0,
        })
        body = resp.get_json()
        assert isinstance(body['arrival_estimate'], str)
        assert 'h' in body['arrival_estimate']


# ─── Pace Count Calculator ────────────────────────────────────────────────────

class TestPaceCountCalc:
    def test_standard_calculation(self, client):
        resp = client.post('/api/movement/pace-count', json={
            'pace_per_100m': 65,
            'distance_meters': 500,
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['distance_meters'] == 500
        assert body['pace_per_100m'] == 65
        assert body['total_paces'] == 325
        assert body['beads_dropped'] == 5

    def test_invalid_pace_count_returns_400(self, client):
        resp = client.post('/api/movement/pace-count', json={
            'pace_per_100m': 0,
            'distance_meters': 500,
        })
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_zero_distance(self, client):
        resp = client.post('/api/movement/pace-count', json={
            'pace_per_100m': 65,
            'distance_meters': 0,
        })
        body = resp.get_json()
        assert body['total_paces'] == 0
        assert body['beads_dropped'] == 0


# ─── Alternative Vehicles CRUD ────────────────────────────────────────────────

class TestAltVehicles:
    def test_empty_list(self, client):
        resp = client.get('/api/alt-vehicles')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_bicycle(self, client):
        resp = client.post('/api/alt-vehicles', json={
            'name': 'Trek 920',
            'vehicle_type': 'bicycle',
            'capacity_lb': 60,
            'range_miles': 80,
            'speed_mph': 12,
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'Trek 920'
        assert body['vehicle_type'] == 'bicycle'

    def test_create_missing_name_returns_400(self, client):
        resp = client.post('/api/alt-vehicles', json={'vehicle_type': 'boat'})
        assert resp.status_code == 400

    def test_filter_by_type(self, client):
        client.post('/api/alt-vehicles', json={'name': 'Horse 1', 'vehicle_type': 'horse'})
        client.post('/api/alt-vehicles', json={'name': 'Kayak 1', 'vehicle_type': 'kayak'})
        resp = client.get('/api/alt-vehicles?type=horse')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Horse 1'

    def test_put_updates_vehicle(self, client):
        vehicle = _create_alt_vehicle(client)
        resp = client.put(f"/api/alt-vehicles/{vehicle['id']}",
                          json={'condition': 'needs_repair', 'notes': 'Flat tire'})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['condition'] == 'needs_repair'

    def test_put_no_fields_returns_400(self, client):
        vehicle = _create_alt_vehicle(client)
        resp = client.put(f"/api/alt-vehicles/{vehicle['id']}", json={})
        assert resp.status_code == 400

    def test_delete_vehicle(self, client):
        vehicle = _create_alt_vehicle(client)
        vid = vehicle['id']
        resp = client.delete(f'/api/alt-vehicles/{vid}')
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete('/api/alt-vehicles/99999')
        assert resp.status_code == 404


# ─── Route Hazards CRUD ───────────────────────────────────────────────────────

class TestRouteHazards:
    def test_empty_list(self, client):
        resp = client.get('/api/route-hazards')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_hazard(self, client):
        resp = client.post('/api/route-hazards', json={
            'name': 'I-95 Checkpoint',
            'hazard_type': 'checkpoint',
            'severity': 'elevated',
            'description': 'National Guard checkpoint',
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'I-95 Checkpoint'
        assert body['hazard_type'] == 'checkpoint'

    def test_create_missing_name_returns_400(self, client):
        resp = client.post('/api/route-hazards', json={'hazard_type': 'bridge'})
        assert resp.status_code == 400

    def test_filter_by_plan_id(self, client):
        plan = _create_plan(client)
        pid = plan['id']
        _create_hazard(client, 'Hazard A', plan_id=pid)
        _create_hazard(client, 'Hazard B', plan_id=None)
        resp = client.get(f'/api/route-hazards?movement_plan_id={pid}')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['name'] == 'Hazard A'

    def test_put_updates_severity(self, client):
        hazard = _create_hazard(client)
        resp = client.put(f"/api/route-hazards/{hazard['id']}",
                          json={'severity': 'extreme', 'seasonal': 1})
        assert resp.status_code == 200
        assert resp.get_json()['severity'] == 'extreme'

    def test_put_no_fields_returns_400(self, client):
        hazard = _create_hazard(client)
        resp = client.put(f"/api/route-hazards/{hazard['id']}", json={})
        assert resp.status_code == 400

    def test_delete_hazard(self, client):
        hazard = _create_hazard(client)
        resp = client.delete(f"/api/route-hazards/{hazard['id']}")
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete('/api/route-hazards/99999')
        assert resp.status_code == 404


# ─── Route Recon CRUD ─────────────────────────────────────────────────────────

class TestRouteRecon:
    def test_empty_list(self, client):
        resp = client.get('/api/route-recon')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_recon_entry(self, client):
        resp = client.post('/api/route-recon', json={
            'recon_date': '2025-07-04',
            'observer': 'Scout Team',
            'road_condition': 'good',
            'threat_level': 'low',
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['recon_date'] == '2025-07-04'
        assert body['road_condition'] == 'good'

    def test_create_missing_recon_date_returns_400(self, client):
        resp = client.post('/api/route-recon', json={'observer': 'Team Alpha'})
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_filter_recon_by_plan_id(self, client):
        plan = _create_plan(client)
        pid = plan['id']
        _create_recon(client, recon_date='2025-06-01', plan_id=pid)
        _create_recon(client, recon_date='2025-06-02', plan_id=None)
        resp = client.get(f'/api/route-recon?movement_plan_id={pid}')
        data = resp.get_json()
        assert len(data) == 1

    def test_delete_recon(self, client):
        recon = _create_recon(client)
        resp = client.delete(f"/api/route-recon/{recon['id']}")
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

    def test_delete_nonexistent_recon_returns_404(self, client):
        resp = client.delete('/api/route-recon/99999')
        assert resp.status_code == 404


# ─── Vehicle Loading Plans CRUD ───────────────────────────────────────────────

class TestVehicleLoading:
    def test_empty_list(self, client):
        resp = client.get('/api/vehicle-loading')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_loading_plan(self, client):
        resp = client.post('/api/vehicle-loading', json={
            'vehicle_name': 'F-250',
            'load_order': 1,
            'max_weight_lb': 2000,
            'fuel_level_pct': 85,
            'assigned_persons': ['Alice', 'Bob'],
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['vehicle_name'] == 'F-250'
        assert body['max_weight_lb'] == 2000

    def test_filter_by_evac_plan_id(self, client, db):
        _seed_evac_plan(db, 42)
        _create_loading(client, 'Truck A')
        # Seed directly with an evac_plan_id
        client.post('/api/vehicle-loading', json={
            'vehicle_name': 'Truck B', 'evac_plan_id': 42, 'load_order': 1,
        })
        resp = client.get('/api/vehicle-loading?evac_plan_id=42')
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]['vehicle_name'] == 'Truck B'

    def test_put_updates_loading(self, client):
        plan = _create_loading(client)
        resp = client.put(f"/api/vehicle-loading/{plan['id']}",
                          json={'fuel_level_pct': 50, 'total_weight_lb': 1500})
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['fuel_level_pct'] == 50
        assert body['total_weight_lb'] == 1500

    def test_put_no_fields_returns_400(self, client):
        plan = _create_loading(client)
        resp = client.put(f"/api/vehicle-loading/{plan['id']}", json={})
        assert resp.status_code == 400

    def test_delete_loading(self, client):
        plan = _create_loading(client)
        resp = client.delete(f"/api/vehicle-loading/{plan['id']}")
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete('/api/vehicle-loading/99999')
        assert resp.status_code == 404


# ─── Go/No-Go Matrix ─────────────────────────────────────────────────────────

class TestGoNogo:
    def test_empty_list(self, client):
        resp = client.get('/api/go-nogo')
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_criterion(self, client):
        resp = client.post('/api/go-nogo', json={
            'criterion': 'Fuel available',
            'category': 'logistics',
            'weight': 3.0,
            'current_status': 'go',
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['criterion'] == 'Fuel available'
        assert body['current_status'] == 'go'

    def test_create_missing_criterion_returns_400(self, client):
        resp = client.post('/api/go-nogo', json={'category': 'security'})
        assert resp.status_code == 400

    def test_put_updates_status(self, client):
        item = _create_gonogo(client)
        resp = client.put(f"/api/go-nogo/{item['id']}",
                          json={'current_status': 'go', 'current_value': '87'})
        assert resp.status_code == 200
        assert resp.get_json()['current_status'] == 'go'

    def test_put_no_fields_returns_400(self, client):
        item = _create_gonogo(client)
        resp = client.put(f"/api/go-nogo/{item['id']}", json={})
        assert resp.status_code == 400

    def test_delete_criterion(self, client):
        item = _create_gonogo(client)
        resp = client.delete(f"/api/go-nogo/{item['id']}")
        assert resp.status_code == 200
        assert resp.get_json()['ok'] is True

    def test_delete_nonexistent_returns_404(self, client):
        resp = client.delete('/api/go-nogo/99999')
        assert resp.status_code == 404


class TestGoNogoEvaluate:
    def test_missing_evac_plan_id_returns_400(self, client):
        resp = client.get('/api/go-nogo/evaluate')
        assert resp.status_code == 400
        assert 'error' in resp.get_json()

    def test_no_criteria_returns_unknown(self, client):
        resp = client.get('/api/go-nogo/evaluate?evac_plan_id=99')
        body = resp.get_json()
        assert body['recommendation'] == 'unknown'

    def test_all_go_returns_GO(self, client, db):
        evac_id = 500
        _seed_evac_plan(db, evac_id)
        for crit in ('Roads clear', 'Fuel ready', 'Comms up'):
            client.post('/api/go-nogo', json={
                'criterion': crit, 'evac_plan_id': evac_id,
                'weight': 1.0, 'current_status': 'go',
            })
        resp = client.get(f'/api/go-nogo/evaluate?evac_plan_id={evac_id}')
        body = resp.get_json()
        assert body['recommendation'] == 'GO'
        assert body['go_percentage'] == pytest.approx(100.0, abs=0.5)

    def test_any_nogo_returns_NO_GO(self, client, db):
        evac_id = 501
        _seed_evac_plan(db, evac_id)
        client.post('/api/go-nogo', json={
            'criterion': 'Route clear', 'evac_plan_id': evac_id,
            'weight': 1.0, 'current_status': 'go',
        })
        client.post('/api/go-nogo', json={
            'criterion': 'Bridge intact', 'evac_plan_id': evac_id,
            'weight': 2.0, 'current_status': 'nogo',
        })
        resp = client.get(f'/api/go-nogo/evaluate?evac_plan_id={evac_id}')
        body = resp.get_json()
        assert body['recommendation'] == 'NO-GO'
        assert body['nogo_count'] == 1

    def test_many_unknowns_returns_HOLD(self, client, db):
        evac_id = 502
        _seed_evac_plan(db, evac_id)
        for i in range(5):
            client.post('/api/go-nogo', json={
                'criterion': f'Check {i}', 'evac_plan_id': evac_id,
                'weight': 1.0, 'current_status': 'unknown',
            })
        resp = client.get(f'/api/go-nogo/evaluate?evac_plan_id={evac_id}')
        body = resp.get_json()
        assert body['recommendation'] == 'HOLD'


# ─── Movement Summary ─────────────────────────────────────────────────────────

class TestMovementSummary:
    def test_summary_empty(self, client):
        resp = client.get('/api/movement/summary')
        assert resp.status_code == 200
        body = resp.get_json()
        for key in ('total_plans', 'active_plans', 'alt_vehicles',
                    'route_hazards', 'recon_entries', 'loading_plans'):
            assert key in body
            assert body[key] == 0

    def test_summary_reflects_created_data(self, client):
        plan = _create_plan(client, status='active')
        _create_alt_vehicle(client)
        _create_hazard(client)
        _create_recon(client)
        _create_loading(client)

        resp = client.get('/api/movement/summary')
        body = resp.get_json()
        assert body['total_plans'] >= 1
        assert body['active_plans'] >= 1
        assert body['alt_vehicles'] >= 1
        assert body['route_hazards'] >= 1
        assert body['recon_entries'] >= 1
        assert body['loading_plans'] >= 1
