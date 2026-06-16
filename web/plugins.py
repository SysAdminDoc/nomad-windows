"""Plugin system -- auto-discovers and loads user plugins from the plugins/ directory.

Plugins are Python files or packages in <data_dir>/plugins/ that register Flask blueprints.
Each plugin must define a `register(app)` function and a `MANIFEST` dict.

MANIFEST format:
    MANIFEST = {
        'name': 'My Plugin',
        'version': '1.0.0',
        'description': 'What this plugin does',
        'routes': ['/api/plugins/my-plugin/hello'],
        'permissions': ['read'],  # read, write, admin
    }

Example plugin (my_plugin.py):
    from flask import Blueprint, jsonify
    bp = Blueprint('my_plugin', __name__)
    MANIFEST = {
        'name': 'My Plugin',
        'version': '1.0.0',
        'routes': ['/api/plugins/my-plugin/hello'],
        'permissions': ['read'],
    }

    @bp.route('/api/plugins/my-plugin/hello')
    def hello():
        return jsonify({'message': 'Hello from my plugin!'})

    def register(app):
        app.register_blueprint(bp)
"""

import importlib.util
import logging
import os
import sys

log = logging.getLogger('nomad.plugins')

_VALID_PERMISSIONS = {'read', 'write', 'admin'}
_ROUTE_PREFIX = '/api/plugins/'

# Loaded plugin metadata: list of dicts with name, path, status, error, manifest, warnings
_loaded_plugins = []
# Disabled plugin names (persisted in settings as JSON list)
_disabled_plugins = set()


def _load_disabled_set():
    """Load the set of disabled plugin names from the DB."""
    global _disabled_plugins
    try:
        from db import db_session
        from web.utils import safe_json_value as _safe_json_value
        with db_session() as db:
            row = db.execute("SELECT value FROM settings WHERE key = 'disabled_plugins'").fetchone()
        if row and row['value']:
            val = _safe_json_value(row['value'], [])
            _disabled_plugins = set(val) if isinstance(val, list) else set()
        else:
            _disabled_plugins = set()
    except Exception:
        _disabled_plugins = set()


def _validate_manifest(manifest, plugin_name):
    """Validate a plugin manifest dict. Returns list of warning strings."""
    warnings = []
    if not isinstance(manifest, dict):
        return ['MANIFEST must be a dict']
    if not manifest.get('name'):
        warnings.append('MANIFEST missing "name"')
    if not manifest.get('version'):
        warnings.append('MANIFEST missing "version"')
    perms = manifest.get('permissions', [])
    if not isinstance(perms, list):
        warnings.append('MANIFEST "permissions" must be a list')
    else:
        for p in perms:
            if p not in _VALID_PERMISSIONS:
                warnings.append(f'Unknown permission: {p}')
    return warnings


def _check_route_prefix(new_rules, plugin_name):
    """Check that all plugin routes are under the /api/plugins/ prefix."""
    violations = []
    for rule in new_rules:
        if not rule.startswith(_ROUTE_PREFIX):
            violations.append(rule)
    return violations


def _builtin_rules(app):
    """Snapshot the set of URL rules registered before plugins load."""
    return {rule.rule for rule in app.url_map.iter_rules()}


def load_plugins(app):
    """Discover and load plugins from <data_dir>/plugins/.

    Called once during app startup, after all built-in blueprints are registered.
    Catches all errors per-plugin so a broken plugin never crashes the app.
    """
    global _loaded_plugins
    _loaded_plugins = []

    _load_disabled_set()

    from config import get_data_dir
    plugins_dir = os.path.join(get_data_dir(), 'plugins')

    if not os.path.isdir(plugins_dir):
        log.debug('Plugin directory does not exist (%s) -- skipping plugin load', plugins_dir)
        return

    existing_rules = _builtin_rules(app)

    if plugins_dir not in sys.path:
        sys.path.insert(0, plugins_dir)

    py_files = sorted(
        f for f in os.listdir(plugins_dir)
        if f.endswith('.py') and not f.startswith('_')
    )

    if not py_files:
        log.debug('No plugin files found in %s', plugins_dir)
        return

    for filename in py_files:
        plugin_name = filename[:-3]
        plugin_path = os.path.join(plugins_dir, filename)
        entry = {
            'name': plugin_name, 'path': plugin_path,
            'status': 'error', 'error': None,
            'manifest': None, 'warnings': [],
        }

        if plugin_name in _disabled_plugins:
            entry['status'] = 'disabled'
            log.info('Plugin %s is disabled -- skipped', plugin_name)
            _loaded_plugins.append(entry)
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f'nomad_plugin_{plugin_name}', plugin_path
            )
            if spec is None or spec.loader is None:
                entry['error'] = 'Could not create module spec'
                log.warning('Plugin %s: could not create module spec', plugin_name)
                _loaded_plugins.append(entry)
                continue

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            manifest = getattr(module, 'MANIFEST', None)
            if manifest is None:
                entry['error'] = 'No MANIFEST dict found -- plugin not loaded'
                entry['warnings'].append('Plugins require a MANIFEST dict with name, version, and permissions')
                log.warning('Plugin %s: no MANIFEST -- refused to load', plugin_name)
                _loaded_plugins.append(entry)
                continue

            manifest_warnings = _validate_manifest(manifest, plugin_name)
            entry['warnings'].extend(manifest_warnings)
            entry['manifest'] = {
                'name': manifest.get('name', plugin_name),
                'version': manifest.get('version', 'unknown'),
                'description': manifest.get('description', ''),
                'routes': manifest.get('routes', []),
                'permissions': manifest.get('permissions', []),
            }

            register_fn = getattr(module, 'register', None)
            if register_fn is None:
                entry['error'] = 'No register(app) function found'
                log.warning('Plugin %s: no register(app) function -- skipped', plugin_name)
                _loaded_plugins.append(entry)
                continue

            register_fn(app)

            new_rules = _builtin_rules(app) - existing_rules
            route_violations = _check_route_prefix(new_rules, plugin_name)
            if route_violations:
                entry['warnings'].append(
                    f'Routes outside {_ROUTE_PREFIX}: {", ".join(sorted(route_violations))}'
                )
                log.warning(
                    'Plugin %s registered routes outside %s: %s',
                    plugin_name, _ROUTE_PREFIX, ', '.join(sorted(route_violations))
                )

            if new_rules:
                log.debug(
                    'Plugin %s added %d route(s): %s',
                    plugin_name, len(new_rules), ', '.join(sorted(new_rules))
                )
            existing_rules = _builtin_rules(app)

            entry['status'] = 'loaded'
            entry['routes_added'] = sorted(new_rules)
            log.info('Plugin loaded: %s (%s)', plugin_name, plugin_path)

        except Exception as exc:
            entry['error'] = str(exc)
            log.error('Plugin %s failed to load: %s', plugin_name, exc, exc_info=True)
            mod_key = f'nomad_plugin_{plugin_name}'
            sys.modules.pop(mod_key, None)

        _loaded_plugins.append(entry)

    loaded_count = sum(1 for p in _loaded_plugins if p['status'] == 'loaded')
    log.info('Plugin loading complete: %d/%d plugins loaded from %s',
             loaded_count, len(_loaded_plugins), plugins_dir)


def list_plugins():
    """Return metadata about all discovered plugins."""
    return list(_loaded_plugins)
