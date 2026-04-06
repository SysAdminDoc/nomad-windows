"""Tests for PDF generation, contours, receipt-import, and vision-import API routes."""

import io
import json


class _FakeUrlopenResponse:
    def __init__(self, status=200, payload=b'{}'):
        self.status = status
        self._payload = payload if isinstance(payload, (bytes, bytearray)) else str(payload).encode('utf-8')

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class TestPdfGeneration:
    def test_pdf_binder_no_reportlab(self, client):
        resp = client.get('/api/print/pdf/operations-binder')
        # Without reportlab installed, should return JSON error 500
        if resp.status_code == 500:
            data = resp.get_json()
            assert 'reportlab' in data.get('error', '')
        else:
            # If reportlab IS installed, we get a PDF back
            assert resp.status_code == 200

    def test_pdf_wallet_no_reportlab(self, client):
        resp = client.get('/api/print/pdf/wallet-cards')
        if resp.status_code == 500:
            data = resp.get_json()
            assert 'reportlab' in data.get('error', '')
        else:
            assert resp.status_code == 200

    def test_pdf_soi_no_reportlab(self, client):
        resp = client.get('/api/print/pdf/soi')
        if resp.status_code == 500:
            data = resp.get_json()
            assert 'reportlab' in data.get('error', '')
        else:
            assert resp.status_code == 200


class TestContours:
    def test_contours_endpoint(self, client):
        resp = client.get('/api/maps/contours?lat=39.0&lng=-104.0&radius_km=10&interval=100')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['type'] == 'FeatureCollection'
        assert isinstance(data['features'], list)

    def test_contours_no_data(self, client):
        # With no elevation data in a fresh DB, should return an empty feature collection
        resp = client.get('/api/maps/contours?lat=0.0&lng=0.0')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['type'] == 'FeatureCollection'
        assert data['features'] == []


class TestReceiptImport:
    def test_receipt_import(self, client):
        resp = client.post('/api/inventory/receipt-import', json={
            'items': [
                {'name': 'Canned Tuna', 'quantity': 6, 'unit_price': 1.29, 'total_price': 7.74},
                {'name': 'Rice 5lb Bag', 'quantity': 2, 'unit_price': 4.99, 'total_price': 9.98},
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['count'] == 2

    def test_receipt_import_empty(self, client):
        resp = client.post('/api/inventory/receipt-import', json={'items': []})
        assert resp.status_code == 400
        assert 'No items' in resp.get_json()['error']

    def test_receipt_scan_recovers_from_malformed_ollama_payload(self, client, monkeypatch):
        import urllib.request

        def fake_urlopen(req, timeout=0):
            url = getattr(req, 'full_url', str(req))
            if url.endswith('/api/tags'):
                return _FakeUrlopenResponse(200, b'{}')
            if url.endswith('/api/generate'):
                return _FakeUrlopenResponse(200, b'{broken')
            raise AssertionError(f'unexpected urlopen request: {url}')

        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        resp = client.post(
            '/api/inventory/receipt-scan',
            data={'image': (io.BytesIO(b'not-a-real-image'), 'receipt.png')},
            content_type='multipart/form-data',
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['source'] == 'ollama'
        assert data['items'] == []


class TestVisionImport:
    def test_vision_import(self, client):
        resp = client.post('/api/inventory/vision-import', json={
            'items': [
                {'name': 'First Aid Kit', 'quantity': 1, 'category': 'Medical', 'condition': 'Good'},
                {'name': 'Flashlight', 'quantity': 3, 'category': 'Equipment', 'condition': 'New'},
            ]
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['count'] == 2

    def test_vision_scan_recovers_from_malformed_ollama_payload(self, client, monkeypatch):
        import urllib.request

        def fake_urlopen(req, timeout=0):
            url = getattr(req, 'full_url', str(req))
            if url.endswith('/api/tags'):
                return _FakeUrlopenResponse(200, b'{}')
            if url.endswith('/api/generate'):
                return _FakeUrlopenResponse(200, b'{broken')
            raise AssertionError(f'unexpected urlopen request: {url}')

        monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

        resp = client.post(
            '/api/inventory/vision-scan',
            data={'image': (io.BytesIO(b'not-a-real-image'), 'vision.png')},
            content_type='multipart/form-data',
        )

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['model_used'] == 'llava'
        assert data['items'] == []
