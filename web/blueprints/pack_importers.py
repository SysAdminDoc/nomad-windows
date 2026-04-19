"""Data pack importers — download real datasets and load into SQLite tables.

Each importer fetches a public dataset, parses it, and bulk-inserts into
the corresponding table. Designed for background execution via threading.
"""

import csv
import io
import json
import logging
import os
import threading
import zipfile

import requests

from db import db_session, log_activity
from flask import Blueprint, jsonify
import config

pack_importers_bp = Blueprint('pack_importers', __name__)
_log = logging.getLogger('nomad.pack_importers')

# ─── Import state (polled by frontend) ────────────────────────────

_import_state = {}  # pack_id -> {status, progress, total, error, detail}
_import_lock = threading.Lock()


def _set_state(pack_id, **kwargs):
    with _import_lock:
        if pack_id not in _import_state:
            _import_state[pack_id] = {}
        _import_state[pack_id].update(kwargs)


def _get_packs_dir():
    data_dir = config.get_data_dir()
    packs_dir = os.path.join(data_dir, 'packs')
    os.makedirs(packs_dir, exist_ok=True)
    return packs_dir


# ─── Status / trigger routes ─────────────────────────────────────

@pack_importers_bp.route('/api/data-packs/<pack_id>/import', methods=['POST'])
def api_pack_import(pack_id):
    importers = {
        'fema_nri': _import_fema_nri,
        'usda_sr_legacy': _import_usda_sr_legacy,
    }
    fn = importers.get(pack_id)
    if not fn:
        return jsonify({'error': f'No importer for pack: {pack_id}'}), 400

    with _import_lock:
        state = _import_state.get(pack_id, {})
        if state.get('status') == 'importing':
            return jsonify({'error': 'Import already in progress'}), 409

    _set_state(pack_id, status='importing', progress=0, total=0, error=None, detail='Starting...')
    t = threading.Thread(target=fn, daemon=True)
    t.start()
    return jsonify({'status': 'started', 'pack_id': pack_id}), 202


@pack_importers_bp.route('/api/data-packs/<pack_id>/import/status')
def api_pack_import_status(pack_id):
    with _import_lock:
        state = _import_state.get(pack_id, {'status': 'idle'})
    return jsonify(state)


# ═══════════════════════════════════════════════════════════════════
# FEMA NRI Importer
# Source: https://hazards.fema.gov/nri/data-resources
# Format: CSV with one row per county, 18 hazard risk scores
# ═══════════════════════════════════════════════════════════════════

_FEMA_NRI_URL = 'https://hazards.fema.gov/nri/Content/StaticDocuments/DataDownload/NRI_Table_Counties/NRI_Table_Counties.zip'

# Column mapping: NRI CSV column → our hazard_scores JSON key
_NRI_HAZARD_COLS = {
    'AVLN_RISKR': 'avalanche',
    'CFLD_RISKR': 'coastal_flooding',
    'CWAV_RISKR': 'cold_wave',
    'DRGT_RISKR': 'drought',
    'ERQK_RISKR': 'earthquake',
    'HAIL_RISKR': 'hail',
    'HWAV_RISKR': 'heat_wave',
    'HRCN_RISKR': 'hurricane',
    'ISTM_RISKR': 'ice_storm',
    'LNDS_RISKR': 'landslide',
    'LTNG_RISKR': 'lightning',
    'RFLD_RISKR': 'riverine_flooding',
    'SWND_RISKR': 'strong_wind',
    'TRND_RISKR': 'tornado',
    'TSUN_RISKR': 'tsunami',
    'VLCN_RISKR': 'volcanic_activity',
    'WFIR_RISKR': 'wildfire',
    'WNTW_RISKR': 'winter_weather',
}

# Score columns (numeric 0-100) for hazard_scores JSON values
_NRI_SCORE_COLS = {
    'AVLN_RISKS': 'avalanche',
    'CFLD_RISKS': 'coastal_flooding',
    'CWAV_RISKS': 'cold_wave',
    'DRGT_RISKS': 'drought',
    'ERQK_RISKS': 'earthquake',
    'HAIL_RISKS': 'hail',
    'HWAV_RISKS': 'heat_wave',
    'HRCN_RISKS': 'hurricane',
    'ISTM_RISKS': 'ice_storm',
    'LNDS_RISKS': 'landslide',
    'LTNG_RISKS': 'lightning',
    'RFLD_RISKS': 'riverine_flooding',
    'SWND_RISKS': 'strong_wind',
    'TRND_RISKS': 'tornado',
    'TSUN_RISKS': 'tsunami',
    'VLCN_RISKS': 'volcanic_activity',
    'WFIR_RISKS': 'wildfire',
    'WNTW_RISKS': 'winter_weather',
}


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _import_fema_nri():
    pack_id = 'fema_nri'
    try:
        _set_state(pack_id, detail='Downloading FEMA NRI dataset...')
        _log.info('Downloading FEMA NRI from %s', _FEMA_NRI_URL)

        resp = requests.get(_FEMA_NRI_URL, timeout=120, stream=True)
        resp.raise_for_status()

        # Read into memory (ZIP is ~20 MB)
        zip_bytes = io.BytesIO(resp.content)
        _set_state(pack_id, detail='Extracting CSV from ZIP...')

        with zipfile.ZipFile(zip_bytes) as zf:
            csv_names = [n for n in zf.namelist() if n.lower().endswith('.csv')]
            if not csv_names:
                raise ValueError('No CSV found in NRI ZIP')
            csv_data = zf.read(csv_names[0]).decode('utf-8-sig')

        reader = csv.DictReader(io.StringIO(csv_data))
        rows = list(reader)
        total = len(rows)
        _set_state(pack_id, detail=f'Importing {total} counties...', total=total)
        _log.info('FEMA NRI: %d county rows to import', total)

        with db_session() as db:
            # Clear existing data for clean re-import
            db.execute('DELETE FROM fema_nri_counties')

            batch = []
            for i, row in enumerate(rows):
                # Skip non-county rows (state-level or territory summaries)
                county_fips = row.get('COUNTYFIPS', '').strip()
                state_fips = row.get('STATEFIPS', '').strip()
                if not county_fips or not state_fips:
                    continue

                # Build hazard scores JSON from numeric score columns
                hazard_scores = {}
                for col, key in _NRI_SCORE_COLS.items():
                    hazard_scores[key] = _safe_float(row.get(col, 0))

                # Overall risk
                risk_score = _safe_float(row.get('RISK_SCORE', 0))
                risk_rating = row.get('RISK_RATNG', '').strip()
                eal = _safe_float(row.get('EAL_VALT', 0))
                sovi = _safe_float(row.get('SOVI_SCORE', 0))
                resl = _safe_float(row.get('RESL_SCORE', 0))

                batch.append((
                    state_fips, county_fips,
                    row.get('STATE', '').strip(),
                    row.get('COUNTY', '').strip(),
                    risk_score, risk_rating, eal,
                    sovi, resl,
                    json.dumps(hazard_scores),
                ))

                if len(batch) >= 500:
                    db.executemany('''
                        INSERT OR REPLACE INTO fema_nri_counties
                        (state_fips, county_fips, state_name, county_name,
                         risk_score, risk_rating, expected_annual_loss,
                         social_vulnerability, community_resilience, hazard_scores)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    ''', batch)
                    batch.clear()
                    _set_state(pack_id, progress=i + 1)

            if batch:
                db.executemany('''
                    INSERT OR REPLACE INTO fema_nri_counties
                    (state_fips, county_fips, state_name, county_name,
                     risk_score, risk_rating, expected_annual_loss,
                     social_vulnerability, community_resilience, hazard_scores)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                ''', batch)

            # Mark pack as installed
            db.execute('''
                INSERT OR REPLACE INTO data_packs
                (pack_id, name, description, tier, category, size_bytes,
                 compressed_size_bytes, version, status, installed_at)
                VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
            ''', ('fema_nri', 'FEMA National Risk Index',
                  'County-level hazard risk scores for 18 natural hazards',
                  1, 'hazards', 52_428_800, 20_971_520, '2023.11', 'installed'))

            db.commit()

        county_count = total
        _set_state(pack_id, status='complete', progress=total, detail=f'Imported {county_count} counties')
        log_activity('data_pack_imported', detail=f'FEMA NRI: {county_count} counties')
        _log.info('FEMA NRI import complete: %d counties', county_count)

    except Exception as e:
        _log.exception('FEMA NRI import failed')
        _set_state(pack_id, status='error', error=str(type(e).__name__), detail='Import failed')


# ═══════════════════════════════════════════════════════════════════
# USDA FoodData SR Legacy Importer
# Source: https://fdc.nal.usda.gov/download-datasets
# Format: JSON (FoodData Central foundation/SR Legacy export)
# ═══════════════════════════════════════════════════════════════════

_USDA_SR_URL = 'https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip'


def _import_usda_sr_legacy():
    pack_id = 'usda_sr_legacy'
    try:
        _set_state(pack_id, detail='Downloading USDA FoodData SR Legacy...')
        _log.info('Downloading USDA SR Legacy from %s', _USDA_SR_URL)

        resp = requests.get(_USDA_SR_URL, timeout=180, stream=True)
        resp.raise_for_status()

        zip_bytes = io.BytesIO(resp.content)
        _set_state(pack_id, detail='Extracting JSON from ZIP...')

        with zipfile.ZipFile(zip_bytes) as zf:
            json_names = [n for n in zf.namelist() if n.lower().endswith('.json')]
            if not json_names:
                raise ValueError('No JSON found in USDA ZIP')
            raw = zf.read(json_names[0]).decode('utf-8')

        _set_state(pack_id, detail='Parsing food data...')
        data = json.loads(raw)

        # SR Legacy JSON has {"SRLegacyFoods": [...]} or {"FoundationFoods": [...]}
        foods = data.get('SRLegacyFoods', data.get('FoundationFoods', []))
        if not foods:
            raise ValueError('No food data found in JSON')

        total = len(foods)
        _set_state(pack_id, detail=f'Importing {total} foods...', total=total)
        _log.info('USDA SR Legacy: %d foods to import', total)

        with db_session() as db:
            db.execute('DELETE FROM nutrition_nutrients')
            db.execute('DELETE FROM nutrition_foods')

            food_batch = []
            nutrient_batch = []

            for i, food in enumerate(foods):
                fdc_id = food.get('fdcId', 0)
                desc = food.get('description', '').strip()
                group = food.get('foodCategory', {}).get('description', '') if isinstance(food.get('foodCategory'), dict) else ''

                # Extract key macros from nutrient list
                nutrients = food.get('foodNutrients', [])
                cals = prot = fat = carbs = fiber = sugar = sodium = 0.0
                serving_size = ''
                serving_unit = ''

                for n in nutrients:
                    nu = n.get('nutrient', {})
                    name = nu.get('name', '')
                    amt = _safe_float(n.get('amount', 0))
                    unit = nu.get('unitName', '')
                    nu_number = nu.get('number', '')

                    if name == 'Energy' and unit in ('kcal', 'KCAL'):
                        cals = amt
                    elif name == 'Protein':
                        prot = amt
                    elif name == 'Total lipid (fat)':
                        fat = amt
                    elif name == 'Carbohydrate, by difference':
                        carbs = amt
                    elif name == 'Fiber, total dietary':
                        fiber = amt
                    elif name == 'Sugars, total including NLEA':
                        sugar = amt
                    elif name == 'Sodium, Na':
                        sodium = amt

                    # Store individual nutrients for micronutrient gap analysis
                    if amt > 0 and name:
                        nutrient_batch.append((fdc_id, name, nu_number, amt, unit))

                # Serving info from foodPortions if available
                portions = food.get('foodPortions', [])
                if portions:
                    p = portions[0]
                    serving_size = str(p.get('gramWeight', '100'))
                    serving_unit = p.get('modifier', 'g') or 'g'
                else:
                    serving_size = '100'
                    serving_unit = 'g'

                food_batch.append((
                    fdc_id, desc, group,
                    cals, prot, fat, carbs, fiber, sugar, sodium,
                    serving_size, serving_unit, 'sr_legacy'
                ))

                # Flush in batches
                if len(food_batch) >= 500:
                    db.executemany('''
                        INSERT OR REPLACE INTO nutrition_foods
                        (fdc_id, description, food_group,
                         calories, protein_g, fat_g, carbs_g, fiber_g, sugar_g, sodium_mg,
                         serving_size, serving_unit, data_source)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ''', food_batch)
                    food_batch.clear()

                if len(nutrient_batch) >= 5000:
                    db.executemany('''
                        INSERT OR REPLACE INTO nutrition_nutrients
                        (fdc_id, nutrient_name, nutrient_number, amount, unit)
                        VALUES (?,?,?,?,?)
                    ''', nutrient_batch)
                    nutrient_batch.clear()

                if (i + 1) % 200 == 0:
                    _set_state(pack_id, progress=i + 1)

            # Flush remaining
            if food_batch:
                db.executemany('''
                    INSERT OR REPLACE INTO nutrition_foods
                    (fdc_id, description, food_group,
                     calories, protein_g, fat_g, carbs_g, fiber_g, sugar_g, sodium_mg,
                     serving_size, serving_unit, data_source)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ''', food_batch)
            if nutrient_batch:
                db.executemany('''
                    INSERT OR REPLACE INTO nutrition_nutrients
                    (fdc_id, nutrient_name, nutrient_number, amount, unit)
                    VALUES (?,?,?,?,?)
                ''', nutrient_batch)

            # Mark pack as installed
            db.execute('''
                INSERT OR REPLACE INTO data_packs
                (pack_id, name, description, tier, category, size_bytes,
                 compressed_size_bytes, version, status, installed_at)
                VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
            ''', ('usda_sr_legacy', 'USDA FoodData SR Legacy',
                  'Nutritional data for 7,793 common foods',
                  1, 'nutrition', 78_643_200, 26_214_400, '2018.04', 'installed'))

            db.commit()

        _set_state(pack_id, status='complete', progress=total, detail=f'Imported {total} foods')
        log_activity('data_pack_imported', detail=f'USDA SR Legacy: {total} foods')
        _log.info('USDA SR Legacy import complete: %d foods', total)

    except Exception as e:
        _log.exception('USDA SR Legacy import failed')
        _set_state(pack_id, status='error', error=str(type(e).__name__), detail='Import failed')
