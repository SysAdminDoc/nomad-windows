"""Tests for the Vehicles blueprint (CRUD, maintenance, fuel log,
range/MPG calculators, dashboard, summary). Includes 404 boundary checks
for every write path, enum validation on fuel_type/role/status, and the
cross-table integrity guarantee that deleting a vehicle clears its
maintenance + fuel-log rows."""


def _make_vehicle(client, **overrides):
    body = {
        'name':               overrides.pop('name', 'Primary F-150'),
        'year':               overrides.pop('year', 2018),
        'make':               overrides.pop('make', 'Ford'),
        'model':              overrides.pop('model', 'F-150'),
        'fuel_type':          overrides.pop('fuel_type', 'gasoline'),
        'tank_capacity_gal':  overrides.pop('tank_capacity_gal', 26),
        'mpg':                overrides.pop('mpg', 22),
        'odometer':           overrides.pop('odometer', 50000),
        'role':               overrides.pop('role', 'daily'),
    }
    body.update(overrides)
    resp = client.post('/api/vehicles', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestVehicleCRUD:
    def test_list_empty(self, client):
        assert client.get('/api/vehicles').get_json() == []

    def test_create_and_list(self, client):
        v = _make_vehicle(client)
        assert v['id'] > 0
        assert v['name'] == 'Primary F-150'
        assert v['fuel_type'] == 'gasoline'
        listing = client.get('/api/vehicles').get_json()
        assert len(listing) == 1
        assert listing[0]['id'] == v['id']

    def test_create_requires_name(self, client):
        resp = client.post('/api/vehicles', json={'fuel_type': 'gasoline'})
        # validate_json enforces required+non-empty before our own check
        assert resp.status_code == 400

    def test_create_rejects_unknown_fuel_type(self, client):
        resp = client.post('/api/vehicles', json={
            'name': 'Magic', 'fuel_type': 'dilithium',
        })
        assert resp.status_code == 400

    def test_create_rejects_unknown_role(self, client):
        resp = client.post('/api/vehicles', json={
            'name': 'M', 'fuel_type': 'gasoline', 'role': 'spy',
        })
        assert resp.status_code == 400

    def test_get_includes_maintenance_and_fuel_stats(self, client):
        v = _make_vehicle(client)
        full = client.get(f'/api/vehicles/{v["id"]}').get_json()
        assert full['name'] == v['name']
        assert full['maintenance'] == []
        assert full['fuel_stats'] == {
            'total_entries': 0, 'total_gallons': 0.0, 'total_cost': 0.0,
        }

    def test_get_404_when_missing(self, client):
        assert client.get('/api/vehicles/99999').status_code == 404

    def test_update_changes_field(self, client):
        v = _make_vehicle(client)
        resp = client.put(f'/api/vehicles/{v["id"]}', json={
            'mpg': 19, 'location': 'garage',
        })
        assert resp.status_code == 200
        assert resp.get_json()['mpg'] == 19
        assert resp.get_json()['location'] == 'garage'

    def test_update_404_when_missing(self, client):
        resp = client.put('/api/vehicles/99999', json={'mpg': 20})
        assert resp.status_code == 404

    def test_update_rejects_invalid_fuel_type(self, client):
        v = _make_vehicle(client)
        resp = client.put(f'/api/vehicles/{v["id"]}', json={'fuel_type': 'cold_fusion'})
        assert resp.status_code == 400

    def test_update_rejects_empty_body(self, client):
        v = _make_vehicle(client)
        resp = client.put(f'/api/vehicles/{v["id"]}', json={})
        assert resp.status_code == 400

    def test_delete_cascades_maintenance_and_fuel(self, client, db):
        v = _make_vehicle(client)
        client.post(f'/api/vehicles/{v["id"]}/maintenance', json={'service_type': 'Oil'})
        client.post(f'/api/vehicles/{v["id"]}/fuel', json={'gallons': 20})
        assert db.execute(
            'SELECT COUNT(*) FROM vehicle_maintenance WHERE vehicle_id = ?',
            (v['id'],),
        ).fetchone()[0] == 1
        assert db.execute(
            'SELECT COUNT(*) FROM vehicle_fuel_log WHERE vehicle_id = ?',
            (v['id'],),
        ).fetchone()[0] == 1

        resp = client.delete(f'/api/vehicles/{v["id"]}')
        assert resp.status_code == 200

        # Both child tables cleared
        assert db.execute(
            'SELECT COUNT(*) FROM vehicle_maintenance WHERE vehicle_id = ?',
            (v['id'],),
        ).fetchone()[0] == 0
        assert db.execute(
            'SELECT COUNT(*) FROM vehicle_fuel_log WHERE vehicle_id = ?',
            (v['id'],),
        ).fetchone()[0] == 0

    def test_delete_404_when_missing(self, client):
        assert client.delete('/api/vehicles/99999').status_code == 404

    def test_filter_by_role(self, client):
        _make_vehicle(client, name='Daily', role='daily')
        _make_vehicle(client, name='BugOut', role='bugout')
        daily = client.get('/api/vehicles?role=daily').get_json()
        bugout = client.get('/api/vehicles?role=bugout').get_json()
        assert [v['name'] for v in daily] == ['Daily']
        assert [v['name'] for v in bugout] == ['BugOut']


class TestVehicleMaintenance:
    def test_create_and_list(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/maintenance', json={
            'service_type': 'Oil change', 'mileage': 50100, 'cost': 65,
            'next_due_mileage': 55000, 'status': 'completed',
        })
        assert resp.status_code == 201
        maint = resp.get_json()
        assert maint['service_type'] == 'Oil change'
        assert maint['vehicle_id'] == v['id']

        listing = client.get(f'/api/vehicles/{v["id"]}/maintenance').get_json()
        assert len(listing) == 1

    def test_create_requires_service_type(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/maintenance', json={'cost': 40})
        assert resp.status_code == 400

    def test_create_rejects_unknown_status(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/maintenance', json={
            'service_type': 'Tire', 'status': 'mythical',
        })
        assert resp.status_code == 400

    def test_create_404_on_missing_vehicle(self, client):
        resp = client.post('/api/vehicles/99999/maintenance', json={
            'service_type': 'Oil',
        })
        assert resp.status_code == 404

    def test_list_404_on_missing_vehicle(self, client):
        assert client.get('/api/vehicles/99999/maintenance').status_code == 404

    def test_update_rejects_invalid_status(self, client):
        v = _make_vehicle(client)
        m = client.post(f'/api/vehicles/{v["id"]}/maintenance',
                        json={'service_type': 'Tires'}).get_json()
        resp = client.put(f'/api/vehicles/maintenance/{m["id"]}',
                          json={'status': 'unknown'})
        assert resp.status_code == 400

    def test_update_and_delete_round_trip(self, client):
        v = _make_vehicle(client)
        m = client.post(f'/api/vehicles/{v["id"]}/maintenance',
                        json={'service_type': 'Brakes', 'status': 'scheduled'}).get_json()
        resp = client.put(f'/api/vehicles/maintenance/{m["id"]}',
                          json={'status': 'completed', 'cost': 420})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'completed'
        assert resp.get_json()['cost'] == 420

        resp = client.delete(f'/api/vehicles/maintenance/{m["id"]}')
        assert resp.status_code == 200

    def test_delete_maintenance_404(self, client):
        assert client.delete('/api/vehicles/maintenance/99999').status_code == 404


class TestVehicleFuelLog:
    def test_create_with_gallons_only(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/fuel', json={'gallons': 15})
        assert resp.status_code == 201
        assert resp.get_json()['gallons'] == 15.0

    def test_create_auto_computes_total_cost(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/fuel', json={
            'gallons': 10, 'cost_per_gallon': 3.50,
        })
        body = resp.get_json()
        assert body['total_cost'] == 35.00

    def test_create_requires_gallons(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/fuel', json={})
        assert resp.status_code == 400

    def test_create_rejects_non_numeric_gallons(self, client):
        v = _make_vehicle(client)
        resp = client.post(f'/api/vehicles/{v["id"]}/fuel', json={'gallons': 'a lot'})
        assert resp.status_code == 400

    def test_create_404_on_missing_vehicle(self, client):
        resp = client.post('/api/vehicles/99999/fuel', json={'gallons': 10})
        assert resp.status_code == 404

    def test_list_404_on_missing_vehicle(self, client):
        assert client.get('/api/vehicles/99999/fuel').status_code == 404


class TestVehicleCalculators:
    def test_range_uses_tank_times_mpg(self, client):
        v = _make_vehicle(client, tank_capacity_gal=20, mpg=25)
        data = client.get(f'/api/vehicles/{v["id"]}/range').get_json()
        assert data['max_range_miles'] == 500.0

    def test_range_estimates_current_fuel_after_fill(self, client):
        v = _make_vehicle(client, tank_capacity_gal=20, mpg=20, odometer=10_500)
        # Fill-up at odometer=10,000 gives 500 miles driven since
        client.post(f'/api/vehicles/{v["id"]}/fuel', json={
            'gallons': 20, 'odometer': 10_000, 'fuel_date': '2025-01-01',
        })
        data = client.get(f'/api/vehicles/{v["id"]}/range').get_json()
        assert data['miles_since_last_fill'] == 500
        # 500 miles at 20 mpg = 25 gallons used; tank capped at 20 gal → 0 left
        assert data['current_fuel_estimate_gal'] == 0.0

    def test_range_404_on_missing_vehicle(self, client):
        assert client.get('/api/vehicles/99999/range').status_code == 404

    def test_fuel_economy_computes_between_fill_ups(self, client):
        v = _make_vehicle(client, tank_capacity_gal=20, mpg=25)
        client.post(f'/api/vehicles/{v["id"]}/fuel', json={
            'gallons': 15, 'odometer': 10_000, 'fuel_date': '2025-01-01',
        })
        client.post(f'/api/vehicles/{v["id"]}/fuel', json={
            'gallons': 15, 'odometer': 10_400, 'fuel_date': '2025-01-15',
        })
        data = client.get(f'/api/vehicles/{v["id"]}/fuel-economy').get_json()
        # 400 miles / 15 gallons ≈ 26.67
        assert data['average_computed_mpg'] == 26.67
        assert len(data['entries']) == 1

    def test_fuel_economy_404_on_missing_vehicle(self, client):
        assert client.get('/api/vehicles/99999/fuel-economy').status_code == 404


class TestVehicleDashboardAndSummary:
    def test_dashboard_empty(self, client):
        data = client.get('/api/vehicles/dashboard').get_json()
        assert data['total_vehicles'] == 0
        assert data['vehicles_by_role'] == {}
        assert data['maintenance_overdue'] == []
        assert data['upcoming_maintenance'] == []
        assert data['total_fuel_cost_30d'] == 0.0

    def test_dashboard_flags_overdue_maintenance_by_date(self, client):
        v = _make_vehicle(client)
        # Due yesterday, still pending
        client.post(f'/api/vehicles/{v["id"]}/maintenance', json={
            'service_type': 'Oil',
            'next_due_date': '2020-01-01',
            'status': 'scheduled',
        })
        data = client.get('/api/vehicles/dashboard').get_json()
        assert len(data['maintenance_overdue']) == 1
        assert data['maintenance_overdue'][0]['service_type'] == 'Oil'

    def test_summary_counts_bugout_vs_total(self, client):
        _make_vehicle(client, name='A', role='daily')
        _make_vehicle(client, name='B', role='bugout')
        _make_vehicle(client, name='C', role='bugout')
        data = client.get('/api/vehicles/summary').get_json()
        assert data['total_vehicles'] == 3
        assert data['bugout_vehicles'] == 2
        # Sum(tank * mpg) = 3 * (26 * 22) = 1716
        assert data['total_range_miles'] == 1716.0
