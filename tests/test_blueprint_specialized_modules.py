"""Smoke tests for specialized_modules blueprint routes.

Covers: supply caches, pets (+food-status), youth programs, end-of-life plans,
procurement (+budget-summary), intelligence reports, fabrication projects,
badges (+seed), awards (+leaderboard), calendar events (+upcoming), legal
documents (+expiring), drones, flight logs (+stats), fitness workouts
(+stats), content packs.

Pattern matches tests/test_blueprint_agriculture.py: one class per resource,
one method per canonical happy-path CRUD transition plus a small number of
404 + 400 guards. Intentionally NOT exhaustive — closes the "no tests at
all" gap flagged during the V8-04/H-17 specialized_modules template
migration (factory-loop session, 2026-04-24).
"""


# ── SUPPLY CACHES ─────────────────────────────────────────────────────────

class TestSupplyCaches:
    def test_list_empty(self, client):
        resp = client.get('/api/specialized/caches')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_cache(self, client):
        resp = client.post('/api/specialized/caches', json={
            'name': 'North Ridge Cache', 'cache_type': 'supply',
            'location_description': 'Buried at tree line', 'security_level': 'high',
            'contents': ['water', 'mres'], 'known_by': ['alice']
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['id'] and body['name'] == 'North Ridge Cache'
        # JSON array columns round-trip
        assert body['contents'] == ['water', 'mres']
        assert body['known_by'] == ['alice']

    def test_create_requires_name(self, client):
        resp = client.post('/api/specialized/caches', json={})
        assert resp.status_code == 400

    def test_update_cache(self, client):
        cid = client.post('/api/specialized/caches', json={'name': 'X'}).get_json()['id']
        resp = client.put(f'/api/specialized/caches/{cid}', json={'condition': 'damaged'})
        assert resp.status_code == 200
        assert resp.get_json()['condition'] == 'damaged'

    def test_update_404(self, client):
        resp = client.put('/api/specialized/caches/999999', json={'condition': 'damaged'})
        assert resp.status_code == 404

    def test_delete_cache(self, client):
        cid = client.post('/api/specialized/caches', json={'name': 'DelMe'}).get_json()['id']
        resp = client.delete(f'/api/specialized/caches/{cid}')
        assert resp.status_code == 200
        # Second delete returns 404
        assert client.delete(f'/api/specialized/caches/{cid}').status_code == 404


# ── PETS ──────────────────────────────────────────────────────────────────

class TestPets:
    def test_create_pet(self, client):
        resp = client.post('/api/specialized/pets', json={
            'name': 'Rex', 'species': 'dog', 'breed': 'GSD', 'age_years': 4,
            'weight_lbs': 75, 'food_supply_days': 21
        })
        assert resp.status_code == 201
        body = resp.get_json()
        assert body['name'] == 'Rex' and body['species'] == 'dog'

    def test_create_requires_name(self, client):
        assert client.post('/api/specialized/pets', json={}).status_code == 400

    def test_update_pet(self, client):
        pid = client.post('/api/specialized/pets', json={'name': 'P1'}).get_json()['id']
        resp = client.put(f'/api/specialized/pets/{pid}', json={'weight_lbs': 80})
        assert resp.status_code == 200

    def test_delete_pet_404(self, client):
        assert client.delete('/api/specialized/pets/999999').status_code == 404

    def test_food_status_tiers(self, client):
        # Seed one pet in each urgency tier to validate classifier
        client.post('/api/specialized/pets', json={'name': 'Critical', 'food_supply_days': 3})
        client.post('/api/specialized/pets', json={'name': 'Low', 'food_supply_days': 10})
        client.post('/api/specialized/pets', json={'name': 'OK', 'food_supply_days': 60})
        resp = client.get('/api/specialized/pets/food-status')
        assert resp.status_code == 200
        rows = resp.get_json()
        tiers = {r['name']: r['urgency'] for r in rows}
        assert tiers.get('Critical') == 'critical'
        assert tiers.get('Low') == 'low'
        assert tiers.get('OK') == 'ok'


# ── YOUTH PROGRAMS ────────────────────────────────────────────────────────

class TestYouthPrograms:
    def test_crud(self, client):
        resp = client.post('/api/specialized/youth', json={
            'name': 'Navigation Basics', 'program_type': 'education',
            'age_range': '10-14', 'instructor': 'Alice'
        })
        assert resp.status_code == 201
        yid = resp.get_json()['id']
        assert client.get(f'/api/specialized/youth/{yid}').status_code == 200
        assert client.put(f'/api/specialized/youth/{yid}', json={'status': 'completed'}).status_code == 200
        assert client.delete(f'/api/specialized/youth/{yid}').status_code == 200
        assert client.get(f'/api/specialized/youth/{yid}').status_code == 404

    def test_create_requires_name(self, client):
        assert client.post('/api/specialized/youth', json={}).status_code == 400


# ── END-OF-LIFE PLANS ─────────────────────────────────────────────────────

class TestEndOfLifePlans:
    def test_crud(self, client):
        resp = client.post('/api/specialized/eol', json={
            'person': 'Jane Doe', 'plan_type': 'advance_directive',
            'status': 'draft', 'organ_donor': True
        })
        assert resp.status_code == 201
        eid = resp.get_json()['id']
        assert client.put(f'/api/specialized/eol/{eid}',
                          json={'status': 'complete'}).status_code == 200
        assert client.delete(f'/api/specialized/eol/{eid}').status_code == 200

    def test_create_requires_person(self, client):
        assert client.post('/api/specialized/eol', json={}).status_code == 400


# ── PROCUREMENT ───────────────────────────────────────────────────────────

class TestProcurement:
    def test_crud_and_budget_summary(self, client):
        resp = client.post('/api/specialized/procurement', json={
            'name': 'Winter Prep', 'priority': 'high', 'budget': 500, 'spent': 120
        })
        assert resp.status_code == 201
        pid = resp.get_json()['id']
        # Budget summary aggregates across all lists
        summary = client.get('/api/specialized/procurement/budget-summary').get_json()
        assert summary['total_budget'] >= 500
        assert summary['total_spent'] >= 120
        # Update + delete round-trip
        assert client.put(f'/api/specialized/procurement/{pid}',
                          json={'spent': 200}).status_code == 200
        assert client.delete(f'/api/specialized/procurement/{pid}').status_code == 200

    def test_create_requires_name(self, client):
        assert client.post('/api/specialized/procurement', json={}).status_code == 400


# ── INTEL ─────────────────────────────────────────────────────────────────

class TestIntel:
    def test_crud(self, client):
        resp = client.post('/api/specialized/intel', json={
            'title': 'OSINT: route advisory',
            'intel_type': 'osint', 'classification': 'unclassified',
            'summary': 'Road closure north highway'
        })
        assert resp.status_code == 201
        iid = resp.get_json()['id']
        assert client.put(f'/api/specialized/intel/{iid}',
                          json={'actionable': True}).status_code == 200
        assert client.delete(f'/api/specialized/intel/{iid}').status_code == 200

    def test_create_requires_title(self, client):
        assert client.post('/api/specialized/intel', json={}).status_code == 400


# ── FABRICATION ───────────────────────────────────────────────────────────

class TestFabrication:
    def test_crud(self, client):
        resp = client.post('/api/specialized/fabrication', json={
            'name': 'Handle Replacement',
            'project_type': '3d_print', 'material': 'PLA',
            'estimated_time_hours': 3
        })
        assert resp.status_code == 201
        fid = resp.get_json()['id']
        assert client.put(f'/api/specialized/fabrication/{fid}',
                          json={'status': 'in_progress'}).status_code == 200
        assert client.delete(f'/api/specialized/fabrication/{fid}').status_code == 200

    def test_create_requires_name(self, client):
        assert client.post('/api/specialized/fabrication', json={}).status_code == 400


# ── BADGES & AWARDS ───────────────────────────────────────────────────────

class TestBadgesAndAwards:
    def test_seed_and_list(self, client):
        resp = client.post('/api/specialized/badges/seed')
        assert resp.status_code in (200, 201)
        listing = client.get('/api/specialized/badges').get_json()
        assert len(listing) > 0

    def test_badge_crud(self, client):
        resp = client.post('/api/specialized/badges', json={
            'name': 'Navigator', 'category': 'skill', 'rarity': 'common', 'points': 10
        })
        assert resp.status_code == 201
        bid = resp.get_json()['id']
        assert client.put(f'/api/specialized/badges/{bid}',
                          json={'points': 20}).status_code == 200
        assert client.delete(f'/api/specialized/badges/{bid}').status_code == 200

    def test_award_flow_and_leaderboard(self, client):
        # Create badge, award to two people, verify leaderboard ranks them
        b1 = client.post('/api/specialized/badges',
                         json={'name': 'B1', 'points': 50}).get_json()['id']
        b2 = client.post('/api/specialized/badges',
                         json={'name': 'B2', 'points': 30}).get_json()['id']
        assert client.post('/api/specialized/awards',
                           json={'badge_id': b1, 'person': 'Alice'}).status_code == 201
        assert client.post('/api/specialized/awards',
                           json={'badge_id': b2, 'person': 'Alice'}).status_code == 201
        assert client.post('/api/specialized/awards',
                           json={'badge_id': b2, 'person': 'Bob'}).status_code == 201
        lb = client.get('/api/specialized/awards/leaderboard').get_json()
        assert isinstance(lb, list)
        # Alice should lead with 80 points, Bob with 30
        by_person = {row['person']: row for row in lb}
        assert by_person['Alice']['total_points'] == 80
        assert by_person['Bob']['total_points'] == 30

    def test_award_requires_badge_and_person(self, client):
        assert client.post('/api/specialized/awards', json={}).status_code == 400


# ── CALENDAR / SEASONAL EVENTS ────────────────────────────────────────────

class TestCalendar:
    def test_crud(self, client):
        resp = client.post('/api/specialized/calendar', json={
            'name': 'Generator Maintenance', 'event_type': 'maintenance',
            'recurrence': 'monthly', 'category': 'power'
        })
        assert resp.status_code == 201
        eid = resp.get_json()['id']
        assert client.put(f'/api/specialized/calendar/{eid}',
                          json={'completed': True}).status_code == 200
        assert client.delete(f'/api/specialized/calendar/{eid}').status_code == 200

    def test_upcoming_returns_list(self, client):
        resp = client.get('/api/specialized/calendar/upcoming')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


# ── LEGAL DOCUMENTS ───────────────────────────────────────────────────────

class TestLegalDocuments:
    def test_crud(self, client):
        resp = client.post('/api/specialized/legal', json={
            'title': 'Passport', 'doc_type': 'id', 'person': 'Self',
            'issue_date': '2024-01-01', 'expiry_date': '2034-01-01'
        })
        assert resp.status_code == 201
        lid = resp.get_json()['id']
        assert client.put(f'/api/specialized/legal/{lid}',
                          json={'notes': 'stored in safe'}).status_code == 200
        assert client.delete(f'/api/specialized/legal/{lid}').status_code == 200

    def test_expiring_endpoint(self, client):
        resp = client.get('/api/specialized/legal/expiring')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_create_requires_title(self, client):
        assert client.post('/api/specialized/legal', json={}).status_code == 400


# ── DRONES & FLIGHTS ──────────────────────────────────────────────────────

class TestDronesAndFlights:
    def test_drone_crud(self, client):
        resp = client.post('/api/specialized/drones', json={
            'name': 'DJI-01', 'drone_type': 'quadcopter',
            'manufacturer': 'DJI', 'model': 'Mavic 3'
        })
        assert resp.status_code == 201
        did = resp.get_json()['id']
        assert client.put(f'/api/specialized/drones/{did}',
                          json={'condition': 'needs_repair'}).status_code == 200
        assert client.delete(f'/api/specialized/drones/{did}').status_code == 200

    def test_flight_log_crud_and_stats(self, client):
        did = client.post('/api/specialized/drones',
                          json={'name': 'Fleet-01'}).get_json()['id']
        resp = client.post('/api/specialized/flights', json={
            'drone_id': did, 'date': '2026-04-24', 'mission_type': 'recon',
            'duration_min': 25
        })
        assert resp.status_code == 201
        fid = resp.get_json()['id']
        # drone_id filter on list
        listing = client.get(f'/api/specialized/flights?drone_id={did}').get_json()
        assert any(f['id'] == fid for f in listing)
        # Stats endpoint returns per-drone aggregates (list of dicts)
        stats = client.get('/api/specialized/flights/stats').get_json()
        assert isinstance(stats, list)
        by_id = {s['id']: s for s in stats}
        assert did in by_id
        assert by_id[did]['total_flights'] == 1
        assert client.delete(f'/api/specialized/flights/{fid}').status_code == 200

    def test_flight_requires_drone_id(self, client):
        assert client.post('/api/specialized/flights', json={}).status_code == 400


# ── FITNESS ───────────────────────────────────────────────────────────────

class TestFitness:
    def test_workout_crud(self, client):
        resp = client.post('/api/specialized/fitness', json={
            'person': 'Alice', 'exercise_type': 'cardio',
            'activity': 'run', 'duration_min': 30, 'calories_burned': 250
        })
        assert resp.status_code == 201
        wid = resp.get_json()['id']
        assert client.delete(f'/api/specialized/fitness/{wid}').status_code == 200

    def test_workout_delete_404(self, client):
        assert client.delete('/api/specialized/fitness/999999').status_code == 404

    def test_stats_endpoint(self, client):
        # Seed a couple of workouts to exercise the aggregator
        client.post('/api/specialized/fitness',
                    json={'person': 'Bob', 'activity': 'walk', 'duration_min': 20})
        resp = client.get('/api/specialized/fitness/stats?person=Bob')
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), dict)


# ── CONTENT PACKS ─────────────────────────────────────────────────────────

class TestContentPacks:
    def test_crud(self, client):
        resp = client.post('/api/specialized/content-packs', json={
            'name': 'Survival Library', 'pack_type': 'books',
            'version': '1.0', 'size_bytes': 1024000
        })
        assert resp.status_code == 201
        pid = resp.get_json()['id']
        assert client.put(f'/api/specialized/content-packs/{pid}',
                          json={'status': 'installed'}).status_code == 200
        assert client.delete(f'/api/specialized/content-packs/{pid}').status_code == 200

    def test_create_requires_name(self, client):
        assert client.post('/api/specialized/content-packs', json={}).status_code == 400
