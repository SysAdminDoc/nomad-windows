"""Tests for medical_phase2 — pregnancy/childbirth, dental, chronic
conditions, vaccinations, mental health, veterinary, herbal remedies,
and three clinical calculators (IV drip rate, burn BSA, APGAR).

Surfaced three production bugs while writing these (all now fixed):
  * PUT on pregnancies / chronic / vet used the CREATE schema, so every
    partial update returned 400 unless the caller re-sent the name.
    Split into _*_SCHEMA / _*_CREATE_SCHEMA.
  * Seven DELETE routes (pregnancies, dental, herbal, chronic,
    vaccinations, mental-health, vet) silently returned 200 for
    non-existent IDs. All now return 404 on rowcount==0."""


def _make_pregnancy(client, **overrides):
    body = {
        'patient_name': overrides.pop('patient_name', 'Jane'),
        'due_date':     overrides.pop('due_date', '2026-09-01'),
        'gravida':      overrides.pop('gravida', 1),
        'para':         overrides.pop('para', 0),
    }
    body.update(overrides)
    resp = client.post('/api/medical/pregnancies', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_chronic(client, **overrides):
    body = {
        'patient_name':  overrides.pop('patient_name', 'Alice'),
        'condition_name': overrides.pop('condition_name', 'Hypertension'),
        'severity':       overrides.pop('severity', 'moderate'),
        'medication_stockpile_days': overrides.pop('medication_stockpile_days', 60),
    }
    body.update(overrides)
    resp = client.post('/api/medical/chronic', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_vet(client, **overrides):
    body = {
        'animal_name': overrides.pop('animal_name', 'Rex'),
        'species':     overrides.pop('species', 'dog'),
        'breed':       overrides.pop('breed', 'Shepherd'),
        'weight_lb':   overrides.pop('weight_lb', 55),
    }
    body.update(overrides)
    resp = client.post('/api/medical/vet', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestPregnancies:
    def test_create_requires_patient_name(self, client):
        resp = client.post('/api/medical/pregnancies', json={'gravida': 1})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        _make_pregnancy(client)
        assert len(client.get('/api/medical/pregnancies').get_json()) == 1

    def test_filter_by_status(self, client):
        _make_pregnancy(client, patient_name='A')
        _make_pregnancy(client, patient_name='B', status='delivered')
        active = client.get('/api/medical/pregnancies?status=active').get_json()
        assert [p['patient_name'] for p in active] == ['A']

    def test_update_partial_does_not_require_name(self, client):
        # Regression: pre-v7.36 this returned 400 because the PUT shared
        # a schema with POST that marks patient_name required.
        preg = _make_pregnancy(client)
        resp = client.put(f'/api/medical/pregnancies/{preg["id"]}',
                          json={'status': 'delivered'})
        assert resp.status_code == 200
        assert resp.get_json()['status'] == 'delivered'

    def test_update_404_when_missing(self, client):
        resp = client.put('/api/medical/pregnancies/99999',
                          json={'status': 'delivered'})
        assert resp.status_code == 404

    def test_update_empty_body_is_400(self, client):
        preg = _make_pregnancy(client)
        resp = client.put(f'/api/medical/pregnancies/{preg["id"]}', json={})
        assert resp.status_code == 400

    def test_delete(self, client):
        preg = _make_pregnancy(client)
        resp = client.delete(f'/api/medical/pregnancies/{preg["id"]}')
        assert resp.status_code == 200

    def test_delete_404_when_missing(self, client):
        # Regression: pre-v7.36 this returned 200 silently.
        resp = client.delete('/api/medical/pregnancies/99999')
        assert resp.status_code == 404


class TestDentalRecords:
    def test_create_requires_patient_name(self, client):
        resp = client.post('/api/medical/dental', json={'tooth_number': 16})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        client.post('/api/medical/dental', json={
            'patient_name': 'Bob', 'tooth_number': 16,
            'condition': 'cavity', 'treatment_date': '2025-04-10',
        })
        rows = client.get('/api/medical/dental').get_json()
        assert len(rows) == 1
        assert rows[0]['tooth_number'] == 16

    def test_list_filter_by_patient(self, client):
        client.post('/api/medical/dental', json={'patient_name': 'Bob', 'tooth_number': 1})
        client.post('/api/medical/dental', json={'patient_name': 'Jane', 'tooth_number': 2})
        bobs = client.get('/api/medical/dental?patient=Bob').get_json()
        assert len(bobs) == 1

    def test_delete_404(self, client):
        assert client.delete('/api/medical/dental/99999').status_code == 404


class TestChronicConditions:
    def test_create_requires_both_names(self, client):
        resp = client.post('/api/medical/chronic',
                           json={'patient_name': 'Alice'})
        assert resp.status_code == 400
        resp2 = client.post('/api/medical/chronic',
                            json={'condition_name': 'Diabetes'})
        assert resp2.status_code == 400

    def test_create_and_list(self, client):
        _make_chronic(client)
        assert len(client.get('/api/medical/chronic').get_json()) == 1

    def test_update_partial_does_not_require_names(self, client):
        # Regression test: PUT previously required both patient_name + condition_name.
        c = _make_chronic(client)
        resp = client.put(f'/api/medical/chronic/{c["id"]}',
                          json={'medication_stockpile_days': 15})
        assert resp.status_code == 200
        assert resp.get_json()['medication_stockpile_days'] == 15

    def test_update_404(self, client):
        resp = client.put('/api/medical/chronic/99999',
                          json={'severity': 'severe'})
        assert resp.status_code == 404

    def test_stockpile_alerts_threshold(self, client):
        _make_chronic(client, patient_name='A', medication_stockpile_days=10)
        _make_chronic(client, patient_name='B', medication_stockpile_days=60)
        alerts = client.get('/api/medical/chronic/stockpile-alerts?days=30').get_json()
        assert len(alerts) == 1
        assert alerts[0]['patient_name'] == 'A'

    def test_delete_404(self, client):
        assert client.delete('/api/medical/chronic/99999').status_code == 404


class TestVaccinations:
    def test_create_requires_both_names(self, client):
        resp = client.post('/api/medical/vaccinations', json={'patient_name': 'X'})
        assert resp.status_code == 400

    def test_create_and_filter_by_patient(self, client):
        client.post('/api/medical/vaccinations', json={
            'patient_name': 'Alice', 'vaccine_name': 'Tetanus', 'next_due': '2030-01-01',
        })
        client.post('/api/medical/vaccinations', json={
            'patient_name': 'Bob', 'vaccine_name': 'Flu',
        })
        alice = client.get('/api/medical/vaccinations?patient=Alice').get_json()
        assert len(alice) == 1

    def test_due_lists_past_due(self, client):
        client.post('/api/medical/vaccinations', json={
            'patient_name': 'A', 'vaccine_name': 'Tetanus',
            'next_due': '2020-01-01',
        })
        client.post('/api/medical/vaccinations', json={
            'patient_name': 'B', 'vaccine_name': 'Flu',
            'next_due': '2099-01-01',
        })
        due = client.get('/api/medical/vaccinations/due').get_json()
        assert [v['patient_name'] for v in due] == ['A']

    def test_delete_404(self, client):
        assert client.delete('/api/medical/vaccinations/99999').status_code == 404


class TestMentalHealth:
    def test_create_requires_name_and_date(self, client):
        resp = client.post('/api/medical/mental-health',
                           json={'patient_name': 'X'})
        assert resp.status_code == 400

    def test_create_and_list(self, client):
        resp = client.post('/api/medical/mental-health', json={
            'patient_name': 'Alice', 'check_date': '2025-04-10',
            'mood_score': 7, 'anxiety_level': 3, 'sleep_hours': 8,
        })
        assert resp.status_code == 201
        rows = client.get('/api/medical/mental-health').get_json()
        assert len(rows) == 1

    def test_trends_requires_patient(self, client):
        resp = client.get('/api/medical/mental-health/trends')
        assert resp.status_code == 400

    def test_trends_empty_when_no_entries(self, client):
        data = client.get(
            '/api/medical/mental-health/trends?patient=Alice'
        ).get_json()
        assert data['entries'] == []
        assert data['avg_mood'] == 0

    def test_trends_averages_match(self, client):
        for score in (6, 8, 4):
            client.post('/api/medical/mental-health', json={
                'patient_name': 'Alice', 'check_date': f'2025-04-{10 + score:02d}',
                'mood_score': score, 'anxiety_level': 2, 'sleep_hours': 7,
            })
        data = client.get(
            '/api/medical/mental-health/trends?patient=Alice'
        ).get_json()
        assert data['total_entries'] == 3
        assert data['avg_mood'] == 6.0  # (6+8+4)/3

    def test_delete_404(self, client):
        assert client.delete('/api/medical/mental-health/99999').status_code == 404


class TestVetRecords:
    def test_create_requires_animal_name(self, client):
        resp = client.post('/api/medical/vet', json={'species': 'dog'})
        assert resp.status_code == 400

    def test_create_rejects_invalid_species(self, client):
        resp = client.post('/api/medical/vet',
                           json={'animal_name': 'X', 'species': 'dragon'})
        assert resp.status_code == 400

    def test_create_and_filter_by_species(self, client):
        _make_vet(client, animal_name='Rex', species='dog')
        _make_vet(client, animal_name='Bessie', species='cow')
        dogs = client.get('/api/medical/vet?species=dog').get_json()
        assert [v['animal_name'] for v in dogs] == ['Rex']

    def test_update_partial_does_not_require_name(self, client):
        # Regression test.
        v = _make_vet(client)
        resp = client.put(f'/api/medical/vet/{v["id"]}',
                          json={'weight_lb': 60})
        assert resp.status_code == 200
        assert resp.get_json()['weight_lb'] == 60.0

    def test_update_404(self, client):
        resp = client.put('/api/medical/vet/99999', json={'weight_lb': 20})
        assert resp.status_code == 404

    def test_delete_404(self, client):
        assert client.delete('/api/medical/vet/99999').status_code == 404


class TestHerbalRemedies:
    def test_seed_populates_builtin_set(self, client):
        resp = client.post('/api/medical/herbal/seed')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['seeded'] >= 10
        assert data['total_builtin'] == data['seeded']

    def test_seed_is_idempotent(self, client):
        client.post('/api/medical/herbal/seed')
        resp = client.post('/api/medical/herbal/seed')
        # On second seed, nothing new is added.
        assert resp.get_json()['seeded'] == 0

    def test_search_by_q(self, client):
        client.post('/api/medical/herbal/seed')
        results = client.get('/api/medical/herbal?q=willow').get_json()
        assert any('Willow' in r['name'] for r in results)

    def test_custom_create_and_delete_404(self, client):
        resp = client.post('/api/medical/herbal', json={
            'name': 'Custom Herb', 'uses': ['experimental'],
        })
        assert resp.status_code == 201
        hid = resp.get_json()['id']
        assert client.delete(f'/api/medical/herbal/{hid}').status_code == 200
        # 404 after delete
        assert client.delete(f'/api/medical/herbal/{hid}').status_code == 404

    def test_custom_requires_name(self, client):
        resp = client.post('/api/medical/herbal', json={'uses': ['none']})
        assert resp.status_code == 400

    def test_delete_404(self, client):
        assert client.delete('/api/medical/herbal/99999').status_code == 404


class TestClinicalCalculators:
    def test_iv_rate_standard(self, client):
        resp = client.post('/api/medical/calc/iv-rate', json={
            'volume_ml': 1000, 'hours': 8, 'drop_factor': 20,
        })
        data = resp.get_json()
        assert data['ml_per_hour'] == 125.0  # 1000 / 8
        assert data['drops_per_min'] == 41.7  # (1000 * 20) / (8 * 60)

    def test_iv_rate_rejects_zero_hours(self, client):
        resp = client.post('/api/medical/calc/iv-rate', json={'hours': 0})
        assert resp.status_code == 400

    def test_iv_rate_rejects_non_numeric(self, client):
        resp = client.post('/api/medical/calc/iv-rate', json={
            'volume_ml': 'a lot', 'hours': 'soon', 'drop_factor': 20,
        })
        # Coerces with default, so returns 200 with default values
        assert resp.status_code == 200

    def test_burns_bsa_rule_of_nines(self, client):
        resp = client.post('/api/medical/calc/burns-bsa', json={
            'chest': 1.0,  # Full chest burn = 18%
            'weight_kg': 70,
        })
        data = resp.get_json()
        assert data['total_bsa_pct'] == 18.0
        assert data['severity'] == 'moderate'  # >10% <= 20%
        # Parkland: 4 * 70 * 18 = 5040 mL
        assert data['parkland_fluid_ml_24h'] == 5040
        assert data['first_8h_ml'] == 2520

    def test_burns_bsa_critical_classification(self, client):
        resp = client.post('/api/medical/calc/burns-bsa', json={
            'chest': 1.0, 'back': 1.0, 'left_leg': 1.0,  # 54%
            'weight_kg': 80,
        })
        data = resp.get_json()
        assert data['severity'] == 'critical'

    def test_apgar_normal_score(self, client):
        resp = client.post('/api/medical/calc/apgar', json={
            'appearance': 2, 'pulse': 2, 'grimace': 2,
            'activity': 2, 'respiration': 2,
        })
        data = resp.get_json()
        assert data['total'] == 10
        assert 'Normal' in data['assessment']

    def test_apgar_severe_depression(self, client):
        resp = client.post('/api/medical/calc/apgar', json={
            'appearance': 0, 'pulse': 0, 'grimace': 0,
            'activity': 0, 'respiration': 0,
        })
        data = resp.get_json()
        assert data['total'] == 0
        assert 'Severe' in data['assessment']

    def test_apgar_clamps_invalid_inputs(self, client):
        resp = client.post('/api/medical/calc/apgar', json={
            'appearance': 99, 'pulse': -5,
        })
        data = resp.get_json()
        # Each component clamped to 0..2
        assert data['appearance'] == 2
        assert data['pulse'] == 0


class TestMedicalPhase2Summary:
    def test_summary_empty(self, client):
        data = client.get('/api/medical/phase2/summary').get_json()
        assert data['active_pregnancies'] == 0
        assert data['active_chronic'] == 0
        assert data['total_vaccinations'] == 0

    def test_summary_reflects_data(self, client):
        _make_pregnancy(client)
        _make_chronic(client, medication_stockpile_days=10)
        client.post('/api/medical/vaccinations', json={
            'patient_name': 'X', 'vaccine_name': 'Tetanus', 'next_due': '2020-01-01',
        })
        _make_vet(client)
        data = client.get('/api/medical/phase2/summary').get_json()
        assert data['active_pregnancies'] == 1
        assert data['active_chronic'] == 1
        assert data['low_medication_stockpile'] == 1
        assert data['vaccinations_due'] == 1
        assert data['animal_records'] == 1
