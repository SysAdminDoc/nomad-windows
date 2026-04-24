"""Root-level routes that don't fit a blueprint.

- ``/sw.js`` — service worker bootstrap
- ``/favicon.ico`` — inline SVG diamond (no on-disk asset needed)
- ``/api/offline/snapshot`` — IndexedDB warm-up payload (critical-data snapshot)
- ``/api/offline/changes-since`` — incremental delta for offline sync

Previously inline in ``create_app()``. The ``Response`` import was
missing in the original location, which would have crashed ``/favicon.ico``
on first hit — fixed here by importing it explicitly.
"""

import time

from flask import Response, jsonify, request

from db import db_session
from web.utils import get_node_id as _get_node_id


def register_root_routes(app):
    """Register /sw.js, /favicon.ico, /api/offline/* on ``app``."""

    @app.route('/sw.js')
    def service_worker():
        return app.send_static_file('sw.js')

    @app.route('/favicon.ico')
    def favicon():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><polygon points="32,4 60,32 32,60 4,32" fill="#4f9cf7"/><polygon points="32,14 50,32 32,50 14,32" fill="#0d0d0d"/><polygon points="32,22 42,32 32,42 22,32" fill="#4f9cf7"/></svg>'
        return Response(svg, mimetype='image/svg+xml')

    @app.route('/api/offline/snapshot')
    def api_offline_snapshot():
        """Return a snapshot of critical data for IndexedDB offline cache."""
        with db_session() as db:
            snapshot = {}
            OFFLINE_TABLES = {
                'inventory': 'SELECT id, name, category, quantity, unit, location, expiration, notes FROM inventory ORDER BY name LIMIT 5000',
                'contacts': 'SELECT id, name, callsign, role, phone, email, notes FROM contacts ORDER BY name LIMIT 2000',
                'patients': 'SELECT id, contact_id, blood_type, allergies, medications, conditions FROM patients LIMIT 1000',
                'waypoints': 'SELECT id, name, lat, lng, category, icon, notes FROM waypoints ORDER BY name LIMIT 5000',
                'checklists': 'SELECT id, name, items FROM checklists ORDER BY name LIMIT 500',
                'freq_database': 'SELECT id, frequency, service, mode, notes, channel_name FROM freq_database ORDER BY frequency LIMIT 2000',
            }
            for table, query in OFFLINE_TABLES.items():
                try:
                    rows = db.execute(query).fetchall()
                    snapshot[table] = [dict(r) for r in rows]
                except Exception:
                    snapshot[table] = []
        snapshot['_timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        snapshot['_node_id'] = _get_node_id()
        return jsonify(snapshot)

    @app.route('/api/offline/changes-since')
    def api_offline_changes_since():
        """Return rows changed since a given timestamp (for incremental sync)."""
        since = request.args.get('since', '2000-01-01T00:00:00')
        with db_session() as db:
            changes = {}
            TRACKED = {
                'inventory': "SELECT * FROM inventory WHERE created_at > ? OR updated_at > ? ORDER BY updated_at DESC LIMIT 1000",
                'contacts': "SELECT * FROM contacts WHERE created_at > ? OR updated_at > ? ORDER BY created_at DESC LIMIT 500",
                'waypoints': "SELECT * FROM waypoints WHERE created_at > ? ORDER BY created_at DESC LIMIT 500",
            }
            for table, query in TRACKED.items():
                try:
                    if 'updated_at' in query and query.count('?') == 2:
                        rows = db.execute(query, (since, since)).fetchall()
                    else:
                        rows = db.execute(query, (since,)).fetchall()
                    changes[table] = [dict(r) for r in rows]
                except Exception:
                    changes[table] = []
        changes['_timestamp'] = time.strftime('%Y-%m-%dT%H:%M:%S')
        return jsonify(changes)
