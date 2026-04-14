"""Data Pack manager — download, install, and manage offline datasets."""

import json
import os
import logging
from flask import Blueprint, request, jsonify
from db import get_db, db_session, log_activity
import config

data_packs_bp = Blueprint('data_packs', __name__)
_log = logging.getLogger('nomad.data_packs')

# ─── Pack Catalog (built-in manifest of available packs) ────────────

PACK_CATALOG = [
    {
        'pack_id': 'usda_sr_legacy',
        'name': 'USDA FoodData SR Legacy',
        'description': 'Nutritional data for 7,793 common foods — calories, macros, vitamins, minerals. Powers inventory nutrition tracking and meal planning.',
        'tier': 1,
        'category': 'nutrition',
        'compressed_size_bytes': 26_214_400,
        'size_bytes': 78_643_200,
        'version': '2018.04',
        'source_url': '',
    },
    {
        'pack_id': 'fema_nri',
        'name': 'FEMA National Risk Index',
        'description': 'County-level hazard risk scores for 18 natural hazards. Powers regional threat assessment and readiness weighting.',
        'tier': 1,
        'category': 'hazards',
        'compressed_size_bytes': 20_971_520,
        'size_bytes': 52_428_800,
        'version': '2023.11',
        'source_url': '',
    },
    {
        'pack_id': 'noaa_frost_dates',
        'name': 'NOAA Frost Date Normals',
        'description': 'Last spring / first fall frost dates by station. Powers garden planning and growing season calculation.',
        'tier': 1,
        'category': 'weather',
        'compressed_size_bytes': 2_097_152,
        'size_bytes': 8_388_608,
        'version': '2023.01',
        'source_url': '',
    },
    {
        'pack_id': 'noaa_weather_stations',
        'name': 'NOAA Weather Station Directory',
        'description': 'US weather station locations and identifiers. Auto-configures nearest station for forecasts and alerts.',
        'tier': 1,
        'category': 'weather',
        'compressed_size_bytes': 1_048_576,
        'size_bytes': 4_194_304,
        'version': '2024.01',
        'source_url': '',
    },
    {
        'pack_id': 'usda_hardiness_zones',
        'name': 'USDA Plant Hardiness Zones',
        'description': 'ZIP-code-level hardiness zone lookup. Powers garden planning and regional plant recommendations.',
        'tier': 1,
        'category': 'agriculture',
        'compressed_size_bytes': 1_048_576,
        'size_bytes': 3_145_728,
        'version': '2023.11',
        'source_url': '',
    },
    {
        'pack_id': 'epa_fuel_economy',
        'name': 'EPA Fuel Economy Guide',
        'description': 'Vehicle fuel economy data by year/make/model. Powers vehicle range calculations and fuel planning.',
        'tier': 1,
        'category': 'vehicles',
        'compressed_size_bytes': 5_242_880,
        'size_bytes': 15_728_640,
        'version': '2024.01',
        'source_url': '',
    },
    {
        'pack_id': 'repeaterbook_us',
        'name': 'RepeaterBook US Directory',
        'description': 'Amateur radio repeater listings for the US. Powers comms planning and repeater lookup.',
        'tier': 2,
        'category': 'communications',
        'compressed_size_bytes': 10_485_760,
        'size_bytes': 31_457_280,
        'version': '2024.03',
        'source_url': '',
    },
    {
        'pack_id': 'usgs_topo_index',
        'name': 'USGS Topo Map Index',
        'description': 'Index of USGS topographic map tiles. Powers offline map tile downloads for route planning.',
        'tier': 3,
        'category': 'maps',
        'compressed_size_bytes': 3_145_728,
        'size_bytes': 10_485_760,
        'version': '2024.01',
        'source_url': '',
    },
]


def _get_packs_dir():
    data_dir = config.get_data_dir()
    packs_dir = os.path.join(data_dir, 'packs')
    os.makedirs(packs_dir, exist_ok=True)
    return packs_dir


def _format_bytes(b):
    if b >= 1_073_741_824:
        return f'{b / 1_073_741_824:.1f} GB'
    if b >= 1_048_576:
        return f'{b / 1_048_576:.1f} MB'
    if b >= 1024:
        return f'{b / 1024:.1f} KB'
    return f'{b} B'


# ─── List all packs (catalog merged with install status) ───────────

@data_packs_bp.route('/api/data-packs')
def api_data_packs_list():
    with db_session() as db:
        installed = {}
        for row in db.execute('SELECT * FROM data_packs').fetchall():
            installed[row['pack_id']] = dict(row)

    result = []
    for pack in PACK_CATALOG:
        entry = dict(pack)
        entry['size_display'] = _format_bytes(pack['size_bytes'])
        entry['compressed_size_display'] = _format_bytes(pack['compressed_size_bytes'])
        if pack['pack_id'] in installed:
            entry['status'] = installed[pack['pack_id']]['status']
            entry['installed_at'] = installed[pack['pack_id']]['installed_at']
            entry['installed_version'] = installed[pack['pack_id']]['version']
        else:
            entry['status'] = 'available'
            entry['installed_at'] = ''
            entry['installed_version'] = ''
        result.append(entry)

    return jsonify(result)


@data_packs_bp.route('/api/data-packs/<pack_id>')
def api_data_pack_detail(pack_id):
    pack = next((p for p in PACK_CATALOG if p['pack_id'] == pack_id), None)
    if not pack:
        return jsonify({'error': 'Pack not found'}), 404
    entry = dict(pack)
    entry['size_display'] = _format_bytes(pack['size_bytes'])
    with db_session() as db:
        row = db.execute('SELECT * FROM data_packs WHERE pack_id = ?', (pack_id,)).fetchone()
        if row:
            entry['status'] = row['status']
            entry['installed_at'] = row['installed_at']
        else:
            entry['status'] = 'available'
    return jsonify(entry)


# ─── Install / uninstall packs ────────────────────────────────────

@data_packs_bp.route('/api/data-packs/<pack_id>/install', methods=['POST'])
def api_data_pack_install(pack_id):
    """Mark a data pack as installed. Actual data loading is handled by
    pack-specific importers (nutrition, FEMA NRI, etc.)."""
    pack = next((p for p in PACK_CATALOG if p['pack_id'] == pack_id), None)
    if not pack:
        return jsonify({'error': 'Pack not found'}), 404

    with db_session() as db:
        existing = db.execute('SELECT status FROM data_packs WHERE pack_id = ?', (pack_id,)).fetchone()
        if existing and existing['status'] == 'installed':
            return jsonify({'status': 'already_installed'})

        db.execute('''
            INSERT OR REPLACE INTO data_packs
            (pack_id, name, description, tier, category, size_bytes, compressed_size_bytes,
             version, status, installed_at, manifest, source_url)
            VALUES (?,?,?,?,?,?,?,?,?,datetime('now'),?,?)
        ''', (pack_id, pack['name'], pack['description'], pack['tier'], pack['category'],
              pack['size_bytes'], pack['compressed_size_bytes'], pack['version'],
              'installed', '{}', pack.get('source_url', '')))
        db.commit()

    log_activity('data_pack_installed', detail=f"Installed {pack['name']}")
    return jsonify({'status': 'installed', 'pack_id': pack_id}), 201


@data_packs_bp.route('/api/data-packs/<pack_id>/uninstall', methods=['POST'])
def api_data_pack_uninstall(pack_id):
    with db_session() as db:
        row = db.execute('SELECT id FROM data_packs WHERE pack_id = ?', (pack_id,)).fetchone()
        if not row:
            return jsonify({'error': 'Pack not installed'}), 404
        db.execute('DELETE FROM data_packs WHERE pack_id = ?', (pack_id,))
        db.commit()

    log_activity('data_pack_uninstalled', detail=f"Uninstalled {pack_id}")
    return jsonify({'status': 'uninstalled'})


# ─── Summary stats ────────────────────────────────────────────────

@data_packs_bp.route('/api/data-packs/summary')
def api_data_packs_summary():
    with db_session() as db:
        installed = db.execute(
            "SELECT COUNT(*) as cnt, COALESCE(SUM(size_bytes),0) as total_size FROM data_packs WHERE status = 'installed'"
        ).fetchone()
    total_available = len(PACK_CATALOG)
    return jsonify({
        'installed_count': installed['cnt'],
        'total_available': total_available,
        'installed_size_bytes': installed['total_size'],
        'installed_size_display': _format_bytes(installed['total_size']),
        'tier1_total': sum(1 for p in PACK_CATALOG if p['tier'] == 1),
    })
