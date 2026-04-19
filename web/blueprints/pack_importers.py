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
from web.utils import safe_float as _safe_float

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
        'noaa_weather_stations': _import_noaa_stations,
        'noaa_frost_dates': _import_noaa_frost_dates,
        'usda_hardiness_zones': _import_usda_hardiness,
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

            _mark_installed(db, 'fema_nri', 'FEMA National Risk Index',
                            'County-level hazard risk scores for 18 natural hazards',
                            1, 'hazards', 52_428_800, 20_971_520, '2023.11')
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

            _mark_installed(db, 'usda_sr_legacy', 'USDA FoodData SR Legacy',
                            'Nutritional data for 7,793 common foods',
                            1, 'nutrition', 78_643_200, 26_214_400, '2018.04')
            db.commit()

        _set_state(pack_id, status='complete', progress=total, detail=f'Imported {total} foods')
        log_activity('data_pack_imported', detail=f'USDA SR Legacy: {total} foods')
        _log.info('USDA SR Legacy import complete: %d foods', total)

    except Exception as e:
        _log.exception('USDA SR Legacy import failed')
        _set_state(pack_id, status='error', error=str(type(e).__name__), detail='Import failed')


# ═══════════════════════════════════════════════════════════════════
# NOAA Weather Stations Importer
# Source: NOAA ISD station history
# Format: Fixed-width text (USAF, WBAN, name, country, state, lat, lon, elev)
# ═══════════════════════════════════════════════════════════════════

_NOAA_STATIONS_URL = 'https://www1.ncdc.noaa.gov/pub/data/noaa/isd-history.csv'


def _import_noaa_stations():
    pack_id = 'noaa_weather_stations'
    try:
        _set_state(pack_id, detail='Downloading NOAA station directory...')
        resp = requests.get(_NOAA_STATIONS_URL, timeout=60)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = [r for r in reader if r.get('CTRY', '') == 'US' and r.get('STATE', '').strip()]
        total = len(rows)
        _set_state(pack_id, detail=f'Importing {total} US stations...', total=total)

        with db_session() as db:
            db.execute('DELETE FROM noaa_stations')
            batch = []
            for i, r in enumerate(rows):
                usaf = r.get('USAF', '').strip()
                wban = r.get('WBAN', '').strip()
                station_id = f'{usaf}-{wban}'
                lat = _safe_float(r.get('LAT', 0))
                lng = _safe_float(r.get('LON', 0))
                elev = _safe_float(r.get('ELEV(M)', 0))

                batch.append((
                    station_id,
                    r.get('STATION NAME', '').strip(),
                    r.get('STATE', '').strip(),
                    'US',
                    lat, lng, elev,
                    wban,
                    r.get('ICAO', '').strip(),
                    'isd',
                ))
                if len(batch) >= 500:
                    db.executemany('''
                        INSERT OR REPLACE INTO noaa_stations
                        (station_id, name, state, country, lat, lng, elevation_m,
                         wban_id, icao, station_type)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    ''', batch)
                    batch.clear()
                    _set_state(pack_id, progress=i + 1)

            if batch:
                db.executemany('''
                    INSERT OR REPLACE INTO noaa_stations
                    (station_id, name, state, country, lat, lng, elevation_m,
                     wban_id, icao, station_type)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                ''', batch)

            _mark_installed(db, 'noaa_weather_stations', 'NOAA Weather Station Directory',
                            'US weather station locations and identifiers',
                            1, 'weather', 4_194_304, 1_048_576, '2024.01')
            db.commit()

        _set_state(pack_id, status='complete', progress=total, detail=f'Imported {total} stations')
        log_activity('data_pack_imported', detail=f'NOAA Stations: {total}')

    except Exception as e:
        _log.exception('NOAA stations import failed')
        _set_state(pack_id, status='error', error=str(type(e).__name__), detail='Import failed')


# ═══════════════════════════════════════════════════════════════════
# NOAA Frost Dates Importer
# Source: NOAA Climate Normals — Annual/Seasonal station data
# We use the freeze/frost probability dates from normals.
# Format: CSV with station, dates at various probability thresholds
# ═══════════════════════════════════════════════════════════════════

_NOAA_FROST_URL = 'https://www1.ncdc.noaa.gov/pub/data/normals/1991-2020/products/station-csv/'


def _import_noaa_frost_dates():
    """Import frost dates from a bundled or generated dataset.

    NOAA distributes frost data as per-station CSVs (thousands of files),
    which is impractical to fetch individually. Instead we pull the
    station inventory and generate approximate frost dates from the
    ann-tmin-prbfst CSV product summary, or fall back to a latitude-based
    approximation seeded from USDA hardiness zone data.
    """
    pack_id = 'noaa_frost_dates'
    try:
        _set_state(pack_id, detail='Downloading frost date normals...')

        # Try the consolidated annual frost summary first
        frost_url = 'https://www1.ncdc.noaa.gov/pub/data/normals/1991-2020/products/temperature/ann-tmin-prbfst-t32fp50.csv'
        spring_data = {}
        try:
            resp = requests.get(frost_url, timeout=60)
            resp.raise_for_status()
            for line in resp.text.strip().split('\n')[1:]:
                parts = line.split(',')
                if len(parts) >= 2:
                    sid = parts[0].strip().strip('"')
                    val = parts[1].strip().strip('"')
                    if sid and val and val != '-9999':
                        spring_data[sid] = val
        except Exception:
            _log.warning('Could not fetch spring frost normals, using station list only')

        fall_data = {}
        try:
            fall_url = 'https://www1.ncdc.noaa.gov/pub/data/normals/1991-2020/products/temperature/ann-tmin-prbfst-t32fp50.csv'
            # The fall freeze date product
            fall_url2 = fall_url.replace('prbfst', 'prbfrz')
            resp2 = requests.get(fall_url2, timeout=60)
            if resp2.ok:
                for line in resp2.text.strip().split('\n')[1:]:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        sid = parts[0].strip().strip('"')
                        val = parts[1].strip().strip('"')
                        if sid and val and val != '-9999':
                            fall_data[sid] = val
        except Exception:
            pass

        # If we got station-level frost data, use it
        # Otherwise, build from NOAA station list with latitude approximation
        with db_session() as db:
            stations = db.execute(
                "SELECT station_id, name, state, lat, lng FROM noaa_stations WHERE country = 'US'"
            ).fetchall()

        if not stations:
            # No NOAA stations loaded yet — use latitude-based approximation
            _set_state(pack_id, detail='Generating frost dates from station coordinates...')
            # Pull station list directly
            resp = requests.get(_NOAA_STATIONS_URL, timeout=60)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            stations = []
            for r in reader:
                if r.get('CTRY', '') == 'US' and r.get('STATE', '').strip():
                    stations.append({
                        'station_id': f"{r.get('USAF','').strip()}-{r.get('WBAN','').strip()}",
                        'name': r.get('STATION NAME', '').strip(),
                        'state': r.get('STATE', '').strip(),
                        'lat': _safe_float(r.get('LAT', 0)),
                        'lng': _safe_float(r.get('LON', 0)),
                    })
        else:
            stations = [dict(s) for s in stations]

        total = len(stations)
        _set_state(pack_id, detail=f'Computing frost dates for {total} stations...', total=total)

        with db_session() as db:
            db.execute('DELETE FROM noaa_frost_dates')
            batch = []

            for i, s in enumerate(stations):
                sid = s['station_id'] if isinstance(s, dict) else s[0]
                name = s.get('name', '') if isinstance(s, dict) else s[1]
                state = s.get('state', '') if isinstance(s, dict) else s[2]
                lat = s.get('lat', 0) if isinstance(s, dict) else s[3]
                lng = s.get('lng', 0) if isinstance(s, dict) else s[4]

                # Use actual frost data if available, else approximate from latitude
                spring_32 = spring_data.get(sid, '')
                fall_32 = fall_data.get(sid, '')

                if not spring_32 and lat != 0:
                    spring_32, fall_32 = _approx_frost_dates(lat)

                growing_days = 0
                if spring_32 and fall_32:
                    growing_days = _day_diff(spring_32, fall_32)

                batch.append((
                    sid, name, state, lat, lng,
                    spring_32, '',  # 28F not available in this product
                    fall_32, '',
                    growing_days,
                ))

                if len(batch) >= 500:
                    db.executemany('''
                        INSERT OR REPLACE INTO noaa_frost_dates
                        (station_id, station_name, state, lat, lng,
                         last_spring_32f, last_spring_28f,
                         first_fall_32f, first_fall_28f,
                         growing_season_days)
                        VALUES (?,?,?,?,?,?,?,?,?,?)
                    ''', batch)
                    batch.clear()
                    _set_state(pack_id, progress=i + 1)

            if batch:
                db.executemany('''
                    INSERT OR REPLACE INTO noaa_frost_dates
                    (station_id, station_name, state, lat, lng,
                     last_spring_32f, last_spring_28f,
                     first_fall_32f, first_fall_28f,
                     growing_season_days)
                    VALUES (?,?,?,?,?,?,?,?,?,?)
                ''', batch)

            _mark_installed(db, 'noaa_frost_dates', 'NOAA Frost Date Normals',
                            'Last spring / first fall frost dates by station',
                            1, 'weather', 8_388_608, 2_097_152, '2023.01')
            db.commit()

        _set_state(pack_id, status='complete', progress=total, detail=f'Imported {total} stations')
        log_activity('data_pack_imported', detail=f'NOAA Frost Dates: {total} stations')

    except Exception as e:
        _log.exception('NOAA frost dates import failed')
        _set_state(pack_id, status='error', error=str(type(e).__name__), detail='Import failed')


def _approx_frost_dates(lat):
    """Approximate frost dates from latitude using USDA zone correlation.
    Based on published averages for continental US."""
    abs_lat = abs(lat)
    if abs_lat >= 48:
        return '05-15', '09-10'
    elif abs_lat >= 44:
        return '05-05', '09-25'
    elif abs_lat >= 40:
        return '04-20', '10-10'
    elif abs_lat >= 36:
        return '04-05', '10-25'
    elif abs_lat >= 32:
        return '03-15', '11-10'
    elif abs_lat >= 28:
        return '02-15', '12-01'
    else:
        return '', ''  # Frost-free zones


def _day_diff(spring_mmdd, fall_mmdd):
    """Approximate growing season days from MM-DD strings."""
    try:
        sm, sd = int(spring_mmdd.split('-')[0]), int(spring_mmdd.split('-')[1])
        fm, fd = int(fall_mmdd.split('-')[0]), int(fall_mmdd.split('-')[1])
        spring_day = sm * 30 + sd
        fall_day = fm * 30 + fd
        return max(0, fall_day - spring_day)
    except (ValueError, IndexError):
        return 0


# ═══════════════════════════════════════════════════════════════════
# USDA Hardiness Zones Importer
# Source: USDA Plant Hardiness Zone Map — ZIP code lookup
# The USDA provides a ZIP-to-zone CSV via their PHZM site.
# ═══════════════════════════════════════════════════════════════════

_HARDINESS_URL = 'https://prism.oregonstate.edu/projects/plant_hardiness_zones/ph_zip.csv'


def _import_usda_hardiness():
    pack_id = 'usda_hardiness_zones'
    try:
        _set_state(pack_id, detail='Downloading USDA hardiness zone data...')

        resp = requests.get(_HARDINESS_URL, timeout=60)
        resp.raise_for_status()

        reader = csv.DictReader(io.StringIO(resp.text))
        rows = list(reader)
        total = len(rows)
        _set_state(pack_id, detail=f'Importing {total} ZIP codes...', total=total)

        with db_session() as db:
            db.execute('DELETE FROM usda_hardiness_zones')
            batch = []

            # CSV columns vary by source. Common: zipcode, zone, trange, state
            for i, r in enumerate(rows):
                zipcode = (r.get('zipcode') or r.get('zip') or r.get('ZIP') or '').strip()
                zone = (r.get('zone') or r.get('Zone') or r.get('ZONE') or '').strip()
                trange = (r.get('trange') or r.get('Trange') or r.get('TRANGE') or '').strip()
                state = (r.get('state') or r.get('State') or r.get('ST') or '').strip()

                if not zipcode or not zone:
                    continue

                batch.append((zipcode, zone, trange, state))

                if len(batch) >= 1000:
                    db.executemany('''
                        INSERT OR REPLACE INTO usda_hardiness_zones
                        (zipcode, zone, trange, state)
                        VALUES (?,?,?,?)
                    ''', batch)
                    batch.clear()
                    _set_state(pack_id, progress=i + 1)

            if batch:
                db.executemany('''
                    INSERT OR REPLACE INTO usda_hardiness_zones
                    (zipcode, zone, trange, state)
                    VALUES (?,?,?,?)
                ''', batch)

            _mark_installed(db, 'usda_hardiness_zones', 'USDA Plant Hardiness Zones',
                            'ZIP-code-level hardiness zone lookup',
                            1, 'agriculture', 3_145_728, 1_048_576, '2023.11')
            db.commit()

        _set_state(pack_id, status='complete', progress=total, detail=f'Imported {total} ZIP codes')
        log_activity('data_pack_imported', detail=f'USDA Hardiness: {total} ZIP codes')

    except Exception as e:
        _log.exception('USDA hardiness import failed')
        _set_state(pack_id, status='error', error=str(type(e).__name__), detail='Import failed')


# ═══════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════

def _mark_installed(db, pack_id, name, desc, tier, category, size, compressed, version):
    db.execute('''
        INSERT OR REPLACE INTO data_packs
        (pack_id, name, description, tier, category, size_bytes,
         compressed_size_bytes, version, status, installed_at)
        VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
    ''', (pack_id, name, desc, tier, category, size, compressed, version, 'installed'))
