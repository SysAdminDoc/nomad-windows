"""Tests for the plugin manifest and permission boundary system."""

from web.plugins import _validate_manifest, _check_route_prefix


class TestManifestValidation:
    def test_valid_manifest(self):
        manifest = {
            'name': 'Test Plugin',
            'version': '1.0.0',
            'permissions': ['read'],
        }
        warnings = _validate_manifest(manifest, 'test_plugin')
        assert warnings == []

    def test_missing_name(self):
        manifest = {'version': '1.0.0', 'permissions': ['read']}
        warnings = _validate_manifest(manifest, 'test_plugin')
        assert any('name' in w for w in warnings)

    def test_missing_version(self):
        manifest = {'name': 'Test', 'permissions': ['read']}
        warnings = _validate_manifest(manifest, 'test_plugin')
        assert any('version' in w for w in warnings)

    def test_unknown_permission(self):
        manifest = {'name': 'Test', 'version': '1.0', 'permissions': ['read', 'destroy']}
        warnings = _validate_manifest(manifest, 'test_plugin')
        assert any('destroy' in w for w in warnings)

    def test_non_dict_manifest(self):
        warnings = _validate_manifest('not a dict', 'test_plugin')
        assert warnings == ['MANIFEST must be a dict']

    def test_non_list_permissions(self):
        manifest = {'name': 'T', 'version': '1', 'permissions': 'read'}
        warnings = _validate_manifest(manifest, 'test_plugin')
        assert any('list' in w for w in warnings)


class TestRoutePrefixCheck:
    def test_valid_routes(self):
        violations = _check_route_prefix(
            {'/api/plugins/my-plugin/hello', '/api/plugins/my-plugin/data'},
            'my_plugin',
        )
        assert violations == []

    def test_invalid_routes(self):
        violations = _check_route_prefix(
            {'/api/plugins/my-plugin/hello', '/api/system/backdoor'},
            'my_plugin',
        )
        assert '/api/system/backdoor' in violations
        assert '/api/plugins/my-plugin/hello' not in violations


class TestPluginsEndpoint:
    def test_plugins_endpoint_returns_list(self, client):
        resp = client.get('/api/plugins')
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'plugins' in data
        assert isinstance(data['plugins'], list)
