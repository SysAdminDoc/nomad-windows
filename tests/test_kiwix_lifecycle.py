"""Tests for Kiwix/OpenZIM content lifecycle controls."""

from web.blueprints.kiwix import _parse_zim_filename


class TestZimFilenameParsing:
    def test_standard_filename(self):
        result = _parse_zim_filename('wikipedia_en_all_maxi_2026-02.zim')
        assert result['base_name'] == 'wikipedia_en_all_maxi'
        assert result['date'] == '2026-02'

    def test_simple_filename(self):
        result = _parse_zim_filename('gutenberg_en_2025-06.zim')
        assert result['base_name'] == 'gutenberg_en'
        assert result['date'] == '2025-06'

    def test_no_date(self):
        result = _parse_zim_filename('custom_content.zim')
        assert result['base_name'] == 'custom_content'
        assert result['date'] == ''


class TestKiwixLifecycleEndpoint:
    def test_lifecycle_when_not_installed(self, client):
        resp = client.get('/api/kiwix/lifecycle')
        assert resp.status_code == 200
        body = resp.get_json()
        assert body['installed'] == []
        assert body['summary']['total_count'] == 0
        assert body['summary']['searchable'] is False


class TestKiwixZimsLifecycleParam:
    def test_zims_without_lifecycle(self, client):
        resp = client.get('/api/kiwix/zims')
        assert resp.status_code == 200

    def test_zims_with_lifecycle_param(self, client):
        resp = client.get('/api/kiwix/zims?lifecycle=1')
        assert resp.status_code == 200
