"""Tests for the hunting_foraging blueprint.

Covers representative route families: game and fishing stats, foraging filters,
trap checks, wild edible reference search/seed flows, trade skill/project
cascades, preservation seed/batch cascades, and zone JSON updates.
"""

import json


def _make_game(client, **overrides):
    body = {
        'species': overrides.pop('species', 'Whitetail Deer'),
        'game_type': overrides.pop('game_type', 'big_game'),
        'method': overrides.pop('method', 'rifle'),
        'season': overrides.pop('season', 'fall'),
        'meat_yield_lbs': overrides.pop('meat_yield_lbs', 45),
    }
    body.update(overrides)
    resp = client.post('/api/hunting/game', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_fish(client, **overrides):
    body = {
        'species': overrides.pop('species', 'Rainbow Trout'),
        'water_type': overrides.pop('water_type', 'freshwater'),
        'weight_lbs': overrides.pop('weight_lbs', 2.0),
        'kept': overrides.pop('kept', True),
    }
    body.update(overrides)
    resp = client.post('/api/hunting/fishing', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_skill(client, **overrides):
    body = {
        'skill_name': overrides.pop('skill_name', 'Hide Tanning'),
        'category': overrides.pop('category', 'preservation'),
        'tools_required': overrides.pop('tools_required', ['scraper']),
    }
    body.update(overrides)
    resp = client.post('/api/hunting/skills', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_preservation(client, **overrides):
    body = {
        'name': overrides.pop('name', 'Smoke drying'),
        'method_type': overrides.pop('method_type', 'smoking'),
        'equipment_needed': overrides.pop('equipment_needed', ['smoker']),
    }
    body.update(overrides)
    resp = client.post('/api/hunting/preservation', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestHuntingGameAndFishing:
    def test_game_crud_filters_and_stats(self, client):
        deer = _make_game(client)
        _make_game(client, species='Rabbit', game_type='small_game',
                   method='snare', season='winter', meat_yield_lbs=4)

        fall = client.get('/api/hunting/game?season=fall').get_json()
        assert [row['species'] for row in fall] == ['Whitetail Deer']

        deer_update = client.put(f'/api/hunting/game/{deer["id"]}',
                                 json={'meat_yield_lbs': 50, 'trophy': 1})
        assert deer_update.status_code == 200
        assert deer_update.get_json()['meat_yield_lbs'] == 50.0

        stats = client.get('/api/hunting/game/stats').get_json()
        assert stats['total_harvested'] == 2
        assert stats['total_meat_yield_lbs'] == 54.0
        assert stats['by_species'][0]['species'] in {'Whitetail Deer', 'Rabbit'}

        assert client.delete(f'/api/hunting/game/{deer["id"]}').status_code == 200
        assert client.get(f'/api/hunting/game/{deer["id"]}').status_code == 404

    def test_game_validation_and_update_edges(self, client):
        assert client.post('/api/hunting/game', json={}).status_code == 400
        game = _make_game(client)
        assert client.put(f'/api/hunting/game/{game["id"]}', json={}).status_code == 400
        assert client.put('/api/hunting/game/99999', json={'season': 'fall'}).status_code == 404
        assert client.delete('/api/hunting/game/99999').status_code == 404

    def test_fishing_filters_stats_and_delete(self, client):
        trout = _make_fish(client)
        _make_fish(client, species='Channel Catfish', water_type='river',
                   weight_lbs=8.0, kept=False)

        freshwater = client.get('/api/hunting/fishing?water_type=freshwater').get_json()
        assert [row['species'] for row in freshwater] == ['Rainbow Trout']

        stats = client.get('/api/hunting/fishing/stats').get_json()
        assert stats['total_catch'] == 2
        assert stats['kept'] == 1
        assert stats['released'] == 1
        assert stats['average_weight_lbs'] == 5.0

        resp = client.put(f'/api/hunting/fishing/{trout["id"]}',
                          json={'length_inches': 16})
        assert resp.status_code == 200
        assert resp.get_json()['length_inches'] == 16.0
        assert client.delete(f'/api/hunting/fishing/{trout["id"]}').status_code == 200

    def test_fishing_validation(self, client):
        assert client.post('/api/hunting/fishing', json={}).status_code == 400
        assert client.get('/api/hunting/fishing/99999').status_code == 404


class TestForagingTrapsAndEdibles:
    def test_foraging_crud_and_filters(self, client):
        nettle = client.post('/api/hunting/foraging', json={
            'plant_name': 'Stinging Nettle',
            'category': 'edible_plant',
            'confidence_level': 'certain',
            'quantity_harvested': 3,
            'unit': 'lbs',
        }).get_json()
        client.post('/api/hunting/foraging', json={
            'plant_name': 'Turkey Tail',
            'category': 'fungus',
            'confidence_level': 'probable',
        })

        certain = client.get('/api/hunting/foraging?confidence=certain').get_json()
        assert [row['plant_name'] for row in certain] == ['Stinging Nettle']

        resp = client.put(f'/api/hunting/foraging/{nettle["id"]}',
                          json={'warnings': 'Use gloves while harvesting'})
        assert resp.status_code == 200
        assert 'gloves' in resp.get_json()['warnings']
        assert client.delete(f'/api/hunting/foraging/{nettle["id"]}').status_code == 200

    def test_foraging_validation(self, client):
        assert client.post('/api/hunting/foraging', json={}).status_code == 400
        assert client.put('/api/hunting/foraging/99999',
                          json={'season': 'spring'}).status_code == 404

    def test_trap_check_increments_catches_and_updates_status(self, client):
        created = client.post('/api/hunting/traps', json={
            'name': 'Creek snare',
            'trap_type': 'snare',
            'materials_used': ['wire', 'stake'],
        })
        assert created.status_code == 201
        trap = created.get_json()
        assert json.loads(trap['materials_used']) == ['wire', 'stake']

        checked = client.post(f'/api/hunting/traps/{trap["id"]}/check',
                              json={'caught': True, 'status': 'reset'})
        assert checked.status_code == 200
        body = checked.get_json()
        assert body['catches'] == 1
        assert body['status'] == 'reset'

        active = client.get('/api/hunting/traps?status=reset').get_json()
        assert [row['name'] for row in active] == ['Creek snare']

    def test_trap_validation(self, client):
        assert client.post('/api/hunting/traps', json={}).status_code == 400
        assert client.post('/api/hunting/traps/99999/check', json={}).status_code == 404

    def test_wild_edibles_seed_search_update_and_skip(self, client):
        seed = client.post('/api/hunting/edibles/seed')
        assert seed.status_code == 201
        assert seed.get_json()['count'] == 10

        dandelion = client.get('/api/hunting/edibles/search?q=dandelion').get_json()
        assert len(dandelion) == 1
        assert dandelion[0]['common_name'] == 'Dandelion'
        assert json.loads(dandelion[0]['edible_parts']) == ['leaves', 'flowers', 'roots']

        resp = client.put(f'/api/hunting/edibles/{dandelion[0]["id"]}',
                          json={'season_available': ['spring']})
        assert resp.status_code == 200
        assert json.loads(resp.get_json()['season_available']) == ['spring']

        skipped = client.post('/api/hunting/edibles/seed')
        assert skipped.status_code == 200
        assert skipped.get_json()['status'] == 'skipped'

    def test_wild_edibles_validation_and_search_guard(self, client):
        assert client.post('/api/hunting/edibles', json={}).status_code == 400
        assert client.get('/api/hunting/edibles/search').status_code == 400
        assert client.get('/api/hunting/edibles/99999').status_code == 404


class TestSkillsPreservationAndZones:
    def test_skill_project_cascade_delete(self, client):
        skill = _make_skill(client)
        assert json.loads(skill['tools_required']) == ['scraper']

        project = client.post('/api/hunting/projects', json={
            'skill_id': skill['id'],
            'name': 'Brain tan deer hide',
            'materials': ['hide', 'brain solution'],
            'status': 'active',
        })
        assert project.status_code == 201
        project_id = project.get_json()['id']

        filtered = client.get(f'/api/hunting/projects?skill_id={skill["id"]}').get_json()
        assert [row['name'] for row in filtered] == ['Brain tan deer hide']

        assert client.delete(f'/api/hunting/skills/{skill["id"]}').status_code == 200
        assert client.get(f'/api/hunting/projects/{project_id}').status_code == 404

    def test_skill_and_project_validation(self, client):
        assert client.post('/api/hunting/skills', json={}).status_code == 400
        assert client.post('/api/hunting/projects', json={}).status_code == 400
        assert client.put('/api/hunting/projects/99999',
                          json={'status': 'done'}).status_code == 404

    def test_preservation_seed_filter_batch_and_cascade_delete(self, client):
        seeded = client.post('/api/hunting/preservation/seed')
        assert seeded.status_code == 201
        assert seeded.get_json()['count'] == 8

        canning = client.get('/api/hunting/preservation?type=canning').get_json()
        assert [row['name'] for row in canning] == [
            'Pressure Canning',
            'Water Bath Canning',
        ]

        method_id = canning[0]['id']
        batch = client.post('/api/hunting/batches', json={
            'method_id': method_id,
            'batch_name': 'Venison stew jars',
            'output_quantity': 12,
            'output_unit': 'quart jars',
        })
        assert batch.status_code == 201
        batch_id = batch.get_json()['id']

        filtered = client.get(f'/api/hunting/batches?method_id={method_id}').get_json()
        assert [row['batch_name'] for row in filtered] == ['Venison stew jars']

        assert client.delete(f'/api/hunting/preservation/{method_id}').status_code == 200
        assert client.get(f'/api/hunting/batches/{batch_id}').status_code == 404

    def test_preservation_and_batch_validation(self, client):
        assert client.post('/api/hunting/preservation', json={}).status_code == 400
        assert client.post('/api/hunting/batches', json={}).status_code == 400
        assert client.put('/api/hunting/preservation/99999',
                          json={'notes': 'missing'}).status_code == 404
        assert client.delete('/api/hunting/batches/99999').status_code == 404

    def test_zones_crud_filter_and_json_update(self, client):
        created = client.post('/api/hunting/zones', json={
            'name': 'North Ridge',
            'zone_type': 'scouting',
            'target_species': ['deer', 'turkey'],
            'blind_stand_locations': ['old oak'],
        })
        assert created.status_code == 201
        zone = created.get_json()
        assert json.loads(zone['target_species']) == ['deer', 'turkey']

        filtered = client.get('/api/hunting/zones?type=scouting').get_json()
        assert [row['name'] for row in filtered] == ['North Ridge']

        resp = client.put(f'/api/hunting/zones/{zone["id"]}',
                          json={'trail_cam_locations': ['gate cam']})
        assert resp.status_code == 200
        assert json.loads(resp.get_json()['trail_cam_locations']) == ['gate cam']

        assert client.delete(f'/api/hunting/zones/{zone["id"]}').status_code == 200

    def test_zone_validation(self, client):
        assert client.post('/api/hunting/zones', json={}).status_code == 400
        assert client.put('/api/hunting/zones/99999',
                          json={'terrain': 'ridge'}).status_code == 404
