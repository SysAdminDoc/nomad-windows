"""Plugin system -- auto-discovers and loads user plugins from the plugins/ directory.

Plugins are Python files or packages in <data_dir>/plugins/ that register Flask blueprints.
Each plugin must define a `register(app)` function that receives the Flask app.

Example plugin (my_plugin.py):
    from flask import Blueprint, jsonify
    bp = Blueprint('my_plugin', __name__)

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

# Loaded plugin metadata: list of dicts with name, path, status, error
_loaded_plugins = []


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

    from config import get_data_dir
    plugins_dir = os.path.join(get_data_dir(), 'plugins')

    if not os.path.isdir(plugins_dir):
        log.debug('Plugin directory does not exist (%s) -- skipping plugin load', plugins_dir)
        return

    # Snapshot built-in routes so we can detect conflicts
    existing_rules = _builtin_rules(app)

    # Add plugins dir to sys.path temporarily for imports
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
        plugin_name = filename[:-3]  # strip .py
        plugin_path = os.path.join(plugins_dir, filename)
        entry = {'name': plugin_name, 'path': plugin_path, 'status': 'error', 'error': None}

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

            register_fn = getattr(module, 'register', None)
            if register_fn is None:
                entry['error'] = 'No register(app) function found'
                log.warning('Plugin %s: no register(app) function -- skipped', plugin_name)
                _loaded_plugins.append(entry)
                continue

            register_fn(app)

            # Check for route conflicts with built-in routes
            new_rules = _builtin_rules(app)
            conflicts = new_rules - existing_rules
            for rule in sorted(conflicts):
                # Only warn if a plugin route shadows an existing built-in
                if rule in existing_rules:
                    log.warning(
                        'Plugin %s: route %s conflicts with a built-in route',
                        plugin_name, rule
                    )

            entry['status'] = 'loaded'
            log.info('Plugin loaded: %s (%s)', plugin_name, plugin_path)

        except Exception as exc:
            entry['error'] = str(exc)
            log.error('Plugin %s failed to load: %s', plugin_name, exc, exc_info=True)
            # Remove from sys.modules if it was partially loaded
            mod_key = f'nomad_plugin_{plugin_name}'
            sys.modules.pop(mod_key, None)

        _loaded_plugins.append(entry)

    loaded_count = sum(1 for p in _loaded_plugins if p['status'] == 'loaded')
    log.info('Plugin loading complete: %d/%d plugins loaded from %s',
             loaded_count, len(_loaded_plugins), plugins_dir)


def list_plugins():
    """Return metadata about all discovered plugins."""
    return list(_loaded_plugins)
