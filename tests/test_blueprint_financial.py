"""Tests for the Financial preparedness blueprint (cash, precious
metals, barter goods, documents) — CRUD, enum coercion, category
filters, dashboard, emergency-fund tracker, cost-per-day, summary,
and the PUT partial-update bug fix (barter)."""


def _make_cash(client, **overrides):
    body = {
        'denomination': overrides.pop('denomination', '$20'),
        'amount':       overrides.pop('amount', 500),
        'location':     overrides.pop('location', 'home safe'),
    }
    body.update(overrides)
    resp = client.post('/api/financial/cash', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_metal(client, **overrides):
    body = {
        'metal_type':     overrides.pop('metal_type', 'gold'),
        'form':           overrides.pop('form', 'coin'),
        'weight_oz':      overrides.pop('weight_oz', 1.0),
        'purity':         overrides.pop('purity', 0.999),
        'purchase_price': overrides.pop('purchase_price', 2000),
    }
    body.update(overrides)
    resp = client.post('/api/financial/metals', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_barter(client, **overrides):
    body = {
        'name':            overrides.pop('name', '.22lr ammo'),
        'category':        overrides.pop('category', 'ammo'),
        'quantity':        overrides.pop('quantity', 500),
        'unit':            overrides.pop('unit', 'rounds'),
        'estimated_value': overrides.pop('estimated_value', 50),
    }
    body.update(overrides)
    resp = client.post('/api/financial/barter', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


def _make_doc(client, **overrides):
    body = {
        'doc_type':    overrides.pop('doc_type', 'insurance'),
        'description': overrides.pop('description', 'Homeowners policy'),
        'institution': overrides.pop('institution', 'State Farm'),
        'expiration':  overrides.pop('expiration', '2030-01-01'),
    }
    body.update(overrides)
    resp = client.post('/api/financial/documents', json=body)
    assert resp.status_code == 201, resp.get_data(as_text=True)
    return resp.get_json()


class TestFinancialCash:
    def test_create_and_list(self, client):
        cash = _make_cash(client)
        assert cash['id'] > 0
        assert cash['amount'] == 500.0
        assert cash['denomination'] == '$20'
        listing = client.get('/api/financial/cash').get_json()
        assert len(listing) == 1

    def test_update_partial(self, client):
        cash = _make_cash(client)
        resp = client.put(f'/api/financial/cash/{cash["id"]}',
                          json={'location': 'truck cache'})
        assert resp.status_code == 200
        assert resp.get_json()['location'] == 'truck cache'
        # amount unchanged
        assert resp.get_json()['amount'] == 500.0

    def test_update_404_when_missing(self, client):
        resp = client.put('/api/financial/cash/99999', json={'amount': 1})
        assert resp.status_code == 404

    def test_update_empty_body_is_400(self, client):
        cash = _make_cash(client)
        resp = client.put(f'/api/financial/cash/{cash["id"]}', json={})
        assert resp.status_code == 400

    def test_delete(self, client):
        cash = _make_cash(client)
        assert client.delete(f'/api/financial/cash/{cash["id"]}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/financial/cash/99999').status_code == 404


class TestFinancialMetals:
    def test_create_and_list(self, client):
        m = _make_metal(client)
        assert m['metal_type'] == 'gold'
        assert m['weight_oz'] == 1.0
        assert len(client.get('/api/financial/metals').get_json()) == 1

    def test_create_coerces_invalid_metal_type(self, client):
        m = _make_metal(client, metal_type='adamantium')
        assert m['metal_type'] == 'gold'  # Coerced to default

    def test_create_coerces_invalid_form(self, client):
        m = _make_metal(client, form='necklace')
        assert m['form'] == 'coin'

    def test_update_partial(self, client):
        m = _make_metal(client)
        resp = client.put(f'/api/financial/metals/{m["id"]}',
                          json={'purchase_price': 2500})
        assert resp.status_code == 200
        assert resp.get_json()['purchase_price'] == 2500.0

    def test_update_coerces_invalid_metal_type(self, client):
        m = _make_metal(client)
        resp = client.put(f'/api/financial/metals/{m["id"]}',
                          json={'metal_type': 'mithril'})
        assert resp.status_code == 200
        assert resp.get_json()['metal_type'] == 'gold'

    def test_update_404(self, client):
        resp = client.put('/api/financial/metals/99999', json={'weight_oz': 2})
        assert resp.status_code == 404

    def test_delete(self, client):
        m = _make_metal(client)
        assert client.delete(f'/api/financial/metals/{m["id"]}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/financial/metals/99999').status_code == 404


class TestFinancialBarter:
    def test_create_and_list(self, client):
        b = _make_barter(client)
        assert b['name'] == '.22lr ammo'
        assert len(client.get('/api/financial/barter').get_json()) == 1

    def test_create_requires_name(self, client):
        resp = client.post('/api/financial/barter', json={'category': 'ammo'})
        assert resp.status_code == 400

    def test_create_coerces_unknown_category(self, client):
        b = _make_barter(client, category='weapons_grade_uranium')
        assert b['category'] == 'other'

    def test_list_filter_by_category(self, client):
        _make_barter(client, name='Ammo', category='ammo')
        _make_barter(client, name='Flashlight', category='tools')
        ammo = client.get('/api/financial/barter?category=ammo').get_json()
        assert [b['name'] for b in ammo] == ['Ammo']

    def test_list_ignores_unknown_category_filter(self, client):
        _make_barter(client, name='A', category='ammo')
        _make_barter(client, name='B', category='tools')
        # Unknown category falls back to full listing
        data = client.get('/api/financial/barter?category=nonsense').get_json()
        assert len(data) == 2

    def test_update_partial_without_name(self, client):
        # Regression: pre-fix this returned 400 because name was marked
        # required on the shared schema.
        b = _make_barter(client)
        resp = client.put(f'/api/financial/barter/{b["id"]}',
                          json={'quantity': 1000})
        assert resp.status_code == 200
        assert resp.get_json()['quantity'] == 1000.0

    def test_update_coerces_unknown_category(self, client):
        b = _make_barter(client)
        resp = client.put(f'/api/financial/barter/{b["id"]}',
                          json={'category': 'plasma'})
        assert resp.status_code == 200
        assert resp.get_json()['category'] == 'other'

    def test_update_404(self, client):
        resp = client.put('/api/financial/barter/99999', json={'quantity': 1})
        assert resp.status_code == 404

    def test_delete(self, client):
        b = _make_barter(client)
        assert client.delete(f'/api/financial/barter/{b["id"]}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/financial/barter/99999').status_code == 404


class TestFinancialDocuments:
    def test_create_and_list(self, client):
        d = _make_doc(client)
        assert d['doc_type'] == 'insurance'
        assert len(client.get('/api/financial/documents').get_json()) == 1

    def test_create_coerces_invalid_doc_type(self, client):
        d = _make_doc(client, doc_type='manifesto')
        assert d['doc_type'] == 'other'

    def test_create_normalizes_digital_copy_to_bool(self, client):
        d = _make_doc(client, digital_copy=True)
        assert d['digital_copy'] == 1
        d2 = _make_doc(client, digital_copy=0)
        assert d2['digital_copy'] == 0

    def test_update_partial(self, client):
        d = _make_doc(client)
        resp = client.put(f'/api/financial/documents/{d["id"]}',
                          json={'institution': 'Allstate'})
        assert resp.status_code == 200
        assert resp.get_json()['institution'] == 'Allstate'

    def test_update_404(self, client):
        resp = client.put('/api/financial/documents/99999',
                          json={'description': 'x'})
        assert resp.status_code == 404

    def test_delete(self, client):
        d = _make_doc(client)
        assert client.delete(f'/api/financial/documents/{d["id"]}').status_code == 200

    def test_delete_404(self, client):
        assert client.delete('/api/financial/documents/99999').status_code == 404


class TestFinancialDashboard:
    def test_dashboard_empty(self, client):
        data = client.get('/api/financial/dashboard').get_json()
        assert data['total_cash'] == 0.0
        assert data['total_metals_oz'] == {}
        assert data['total_barter_value'] == 0.0
        assert data['documents_count'] == 0
        assert data['total_preparedness_value'] == 0.0

    def test_dashboard_rolls_up_all_sources(self, client):
        _make_cash(client, amount=1000)
        _make_cash(client, amount=500, location='truck')
        _make_metal(client, weight_oz=2, purchase_price=3000)
        _make_metal(client, metal_type='silver', weight_oz=10, purchase_price=300)
        _make_barter(client, estimated_value=200)
        _make_doc(client)
        data = client.get('/api/financial/dashboard').get_json()
        assert data['total_cash'] == 1500.0
        assert data['total_metals_oz'] == {'gold': 2.0, 'silver': 10.0}
        assert data['total_metals_value'] == 3300.0
        assert data['total_barter_value'] == 200.0
        assert data['documents_count'] == 1
        assert data['total_preparedness_value'] == 5000.0

    def test_dashboard_flags_expiring_docs(self, client, db):
        db.execute(
            "INSERT INTO financial_documents (doc_type, description, expiration) "
            "VALUES ('insurance', 'Soon', date('now', '+30 days'))"
        )
        db.execute(
            "INSERT INTO financial_documents (doc_type, description, expiration) "
            "VALUES ('insurance', 'Later', date('now', '+200 days'))"
        )
        db.commit()
        data = client.get('/api/financial/dashboard').get_json()
        assert data['documents_expiring_soon'] == 1


class TestFinancialEmergencyFund:
    def test_defaults_to_10000_target(self, client):
        data = client.get('/api/financial/emergency-fund').get_json()
        assert data['target'] == 10000.0
        assert data['current'] == 0.0
        assert data['percentage'] == 0
        assert data['remaining'] == 10000.0

    def test_includes_cash_and_metals(self, client):
        _make_cash(client, amount=2000)
        _make_metal(client, purchase_price=3000)
        data = client.get('/api/financial/emergency-fund').get_json()
        assert data['current'] == 5000.0
        assert data['percentage'] == 50.0
        assert data['remaining'] == 5000.0

    def test_respects_custom_target_via_settings(self, client, db):
        db.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('emergency_fund_target', '5000')"
        )
        db.commit()
        _make_cash(client, amount=2500)
        data = client.get('/api/financial/emergency-fund').get_json()
        assert data['target'] == 5000.0
        assert data['percentage'] == 50.0


class TestFinancialCostPerDay:
    def test_query_params_override_db(self, client):
        _make_cash(client, amount=9000)  # Would contribute if not overridden
        data = client.get(
            '/api/financial/cost-per-day?total_investment=3650&days_of_autonomy=365'
        ).get_json()
        assert data['total_investment'] == 3650.0
        assert data['days_of_autonomy'] == 365.0
        assert data['cost_per_day'] == 10.0

    def test_zero_days_falls_back_to_90(self, client):
        data = client.get(
            '/api/financial/cost-per-day?total_investment=900&days_of_autonomy=0'
        ).get_json()
        assert data['days_of_autonomy'] == 90.0
        assert data['cost_per_day'] == 10.0

    def test_pulls_from_db_when_no_params(self, client):
        _make_cash(client, amount=4500)
        _make_barter(client, estimated_value=4500)
        data = client.get('/api/financial/cost-per-day').get_json()
        # Total 9000 / 90 default days = 100/day
        assert data['total_investment'] == 9000.0
        assert data['cost_per_day'] == 100.0


class TestFinancialSummary:
    def test_summary_shape(self, client):
        _make_cash(client, amount=800)
        _make_metal(client, purchase_price=1200)
        _make_barter(client, estimated_value=150)
        _make_doc(client)
        data = client.get('/api/financial/summary').get_json()
        assert data['total_cash'] == 800.0
        assert data['metals_count'] == 1
        assert data['barter_items_count'] == 1
        assert data['documents_count'] == 1
        assert data['total_value'] == 2150.0
