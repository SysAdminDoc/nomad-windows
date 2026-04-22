"""Regional profile system — location-based personalization and threat assessment."""

import json
import logging
from flask import Blueprint, request, jsonify
from db import get_db, db_session, log_activity

regional_profile_bp = Blueprint('regional_profile', __name__)
_log = logging.getLogger('nomad.regional_profile')

# ─── US States lookup for validation ──────────────────────────────

US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas',
    'CA': 'California', 'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho',
    'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas',
    'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada',
    'NH': 'New Hampshire', 'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York',
    'NC': 'North Carolina', 'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma',
    'OR': 'Oregon', 'PA': 'Pennsylvania', 'RI': 'Rhode Island', 'SC': 'South Carolina',
    'SD': 'South Dakota', 'TN': 'Tennessee', 'TX': 'Texas', 'UT': 'Utah',
    'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington', 'WV': 'West Virginia',
    'WI': 'Wisconsin', 'WY': 'Wyoming', 'DC': 'District of Columbia',
}

# 18 FEMA NRI hazard types
NRI_HAZARD_TYPES = [
    'avalanche', 'coastal_flooding', 'cold_wave', 'drought', 'earthquake',
    'hail', 'heat_wave', 'hurricane', 'ice_storm', 'landslide', 'lightning',
    'riverine_flooding', 'strong_wind', 'tornado', 'tsunami',
    'volcanic_activity', 'wildfire', 'winter_weather',
]

_REGIONAL_PROFILE_ALLOWED_FIELDS = frozenset({'name', 'country', 'state', 'county', 'zip_code', 'lat', 'lng',
                                              'usda_zone', 'frost_date_last', 'frost_date_first',
                                              'nearest_nws_station', 'nearest_nws_station_name', 'notes'})


# ─── Get active profile ──────────────────────────────────────────

@regional_profile_bp.route('/api/region/profile')
def api_region_profile():
    with db_session() as db:
        row = db.execute(
            'SELECT * FROM regional_profile WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()
    if not row:
        return jsonify({'configured': False, 'profile': None})
    profile = dict(row)
    profile['fema_risk_scores'] = _safe_json_parse(profile.get('fema_risk_scores', '{}'))
    profile['threat_weights'] = _safe_json_parse(profile.get('threat_weights', '{}'))
    profile['configured'] = True
    return jsonify(profile)


@regional_profile_bp.route('/api/region/profile', methods=['POST'])
def api_region_profile_save():
    data = request.get_json() or {}
    state = data.get('state', '').strip().upper()
    if state and state not in US_STATES:
        return jsonify({'error': f'Invalid state code: {state}'}), 400

    fema_scores = json.dumps(data.get('fema_risk_scores', {}))
    threat_weights = json.dumps(data.get('threat_weights', {}))

    with db_session() as db:
        # Deactivate any existing profiles
        db.execute('UPDATE regional_profile SET is_active = 0 WHERE is_active = 1')
        db.execute('''
            INSERT INTO regional_profile
            (name, country, state, county, zip_code, lat, lng,
             usda_zone, fema_risk_scores, frost_date_last, frost_date_first,
             nearest_nws_station, nearest_nws_station_name, threat_weights, notes, is_active)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
        ''', (
            data.get('name', 'primary'),
            data.get('country', 'US'),
            state,
            data.get('county', ''),
            data.get('zip_code', ''),
            data.get('lat'),
            data.get('lng'),
            data.get('usda_zone', ''),
            fema_scores,
            data.get('frost_date_last', ''),
            data.get('frost_date_first', ''),
            data.get('nearest_nws_station', ''),
            data.get('nearest_nws_station_name', ''),
            threat_weights,
            data.get('notes', ''),
        ))
        db.commit()

    # Auto-populate from data packs if available
    enriched = {}
    zip_code = data.get('zip_code', '').strip()
    county = data.get('county', '').strip()

    with db_session() as db:
        profile = db.execute(
            'SELECT id FROM regional_profile WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()
        if profile:
            profile_id = profile['id']

            # Auto-fill hardiness zone from ZIP
            if zip_code:
                hz = db.execute(
                    'SELECT zone, trange FROM usda_hardiness_zones WHERE zipcode = ?',
                    (zip_code,)
                ).fetchone()
                if hz:
                    db.execute('UPDATE regional_profile SET usda_zone = ? WHERE id = ?',
                               (hz['zone'], profile_id))
                    enriched['usda_zone'] = hz['zone']

            # Auto-fill FEMA risk scores from county
            if county and state:
                state_name = US_STATES.get(state, state)
                nri = db.execute(
                    'SELECT risk_score, risk_rating, hazard_scores FROM fema_nri_counties WHERE county_name = ? AND state_name = ? LIMIT 1',
                    (county, state_name)
                ).fetchone()
                if nri:
                    db.execute('UPDATE regional_profile SET fema_risk_scores = ? WHERE id = ?',
                               (nri['hazard_scores'], profile_id))
                    enriched['fema_risk_score'] = nri['risk_score']
                    enriched['fema_risk_rating'] = nri['risk_rating']

            # Auto-fill frost dates from nearest station
            if data.get('lat') and data.get('lng'):
                lat, lng = float(data['lat']), float(data['lng'])
                frost = db.execute(
                    '''SELECT station_name, last_spring_32f, first_fall_32f, growing_season_days,
                              lat, lng,
                              ((lat - ?) * (lat - ?) + (lng - ?) * (lng - ?)) AS dist2
                       FROM noaa_frost_dates
                       WHERE last_spring_32f != '' AND first_fall_32f != ''
                       ORDER BY dist2 LIMIT 1''',
                    (lat, lat, lng, lng)
                ).fetchone()
                if frost:
                    db.execute('''UPDATE regional_profile
                                  SET frost_date_last = ?, frost_date_first = ?
                                  WHERE id = ?''',
                               (frost['last_spring_32f'], frost['first_fall_32f'], profile_id))
                    enriched['frost_date_last'] = frost['last_spring_32f']
                    enriched['frost_date_first'] = frost['first_fall_32f']
                    enriched['growing_season_days'] = frost['growing_season_days']

            # Auto-fill nearest NWS station
            if data.get('lat') and data.get('lng'):
                station = db.execute(
                    '''SELECT station_id, name, state, lat, lng,
                              ((lat - ?) * (lat - ?) + (lng - ?) * (lng - ?)) AS dist2
                       FROM noaa_stations
                       ORDER BY dist2 LIMIT 1''',
                    (lat, lat, lng, lng)
                ).fetchone()
                if station:
                    db.execute('''UPDATE regional_profile
                                  SET nearest_nws_station = ?, nearest_nws_station_name = ?
                                  WHERE id = ?''',
                               (station['station_id'], station['name'], profile_id))
                    enriched['nearest_station'] = station['name']

            db.commit()

    log_activity('regional_profile_configured',
                 detail=f"Region: {state} {data.get('county', '')} {zip_code}")
    return jsonify({'status': 'saved', 'enriched': enriched}), 201


@regional_profile_bp.route('/api/region/profile', methods=['PUT'])
def api_region_profile_update():
    data = request.get_json() or {}
    with db_session() as db:
        row = db.execute(
            'SELECT id FROM regional_profile WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()
        if not row:
            return jsonify({'error': 'No active profile'}), 404

        allowed = _REGIONAL_PROFILE_ALLOWED_FIELDS
        updates = []
        values = []
        for key in allowed:
            if key in data:
                updates.append(f'{key} = ?')
                values.append(data[key])

        for json_field in ('fema_risk_scores', 'threat_weights'):
            if json_field in data:
                updates.append(f'{json_field} = ?')
                values.append(json.dumps(data[json_field]))

        if not updates:
            return jsonify({'error': 'No fields to update'}), 400

        updates.append("updated_at = datetime('now')")
        values.append(row['id'])
        db.execute(
            f"UPDATE regional_profile SET {', '.join(updates)} WHERE id = ?",
            values
        )
        db.commit()
    return jsonify({'status': 'updated'})


# ─── Regional threats (from FEMA NRI data) ────────────────────────

@regional_profile_bp.route('/api/region/threats')
def api_region_threats():
    with db_session() as db:
        profile = db.execute(
            'SELECT state, county, fema_risk_scores FROM regional_profile WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()
        if not profile:
            return jsonify({'configured': False, 'threats': []})

        # Try loading from FEMA NRI table first
        nri_row = None
        if profile['county']:
            nri_row = db.execute(
                'SELECT * FROM fema_nri_counties WHERE county_name = ? AND state_name = ? LIMIT 1',
                (profile['county'], US_STATES.get(profile['state'], profile['state']))
            ).fetchone()

        if nri_row:
            hazard_scores = _safe_json_parse(nri_row['hazard_scores'])
            threats = []
            for hazard, score in sorted(hazard_scores.items(), key=lambda x: x[1], reverse=True):
                if score > 0:
                    threats.append({
                        'hazard': hazard,
                        'score': score,
                        'rating': _score_to_rating(score),
                    })
            return jsonify({
                'configured': True,
                'source': 'fema_nri',
                'county': nri_row['county_name'],
                'state': nri_row['state_name'],
                'overall_risk_score': nri_row['risk_score'],
                'overall_risk_rating': nri_row['risk_rating'],
                'social_vulnerability': nri_row['social_vulnerability'],
                'community_resilience': nri_row['community_resilience'],
                'threats': threats,
            })

        # Fall back to profile-stored scores
        scores = _safe_json_parse(profile['fema_risk_scores'])
        threats = []
        for hazard, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
            if score > 0:
                threats.append({
                    'hazard': hazard,
                    'score': score,
                    'rating': _score_to_rating(score),
                })
        return jsonify({
            'configured': True,
            'source': 'profile',
            'threats': threats,
        })


# ─── US States list (for setup wizard dropdown) ──────────────────

@regional_profile_bp.route('/api/region/states')
def api_region_states():
    return jsonify([{'code': k, 'name': v} for k, v in sorted(US_STATES.items(), key=lambda x: x[1])])


# ─── FEMA NRI county lookup ──────────────────────────────────────

@regional_profile_bp.route('/api/region/nri/counties')
def api_region_nri_counties():
    state = request.args.get('state', '').strip()
    if not state:
        return jsonify({'error': 'state parameter required'}), 400
    state_name = US_STATES.get(state.upper(), state)
    with db_session() as db:
        rows = db.execute(
            'SELECT county_name, county_fips, risk_score, risk_rating FROM fema_nri_counties WHERE state_name = ? ORDER BY county_name',
            (state_name,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@regional_profile_bp.route('/api/region/nri/county/<county_fips>')
def api_region_nri_county_detail(county_fips):
    with db_session() as db:
        row = db.execute('SELECT * FROM fema_nri_counties WHERE county_fips = ?', (county_fips,)).fetchone()
    if not row:
        return jsonify({'error': 'County not found'}), 404
    result = dict(row)
    result['hazard_scores'] = _safe_json_parse(result.get('hazard_scores', '{}'))
    return jsonify(result)


# ─── Readiness weight adjustment based on regional threats ────────

@regional_profile_bp.route('/api/region/readiness-weights')
def api_region_readiness_weights():
    """Return readiness scoring weights adjusted by regional threat profile.
    Higher-risk hazards get more weight in the readiness score."""
    with db_session() as db:
        profile = db.execute(
            'SELECT fema_risk_scores, threat_weights FROM regional_profile WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()

    if not profile:
        return jsonify({'adjusted': False, 'weights': _default_readiness_weights()})

    custom_weights = _safe_json_parse(profile['threat_weights'])
    if custom_weights:
        return jsonify({'adjusted': True, 'source': 'custom', 'weights': custom_weights})

    scores = _safe_json_parse(profile['fema_risk_scores'])
    if not scores:
        return jsonify({'adjusted': False, 'weights': _default_readiness_weights()})

    # Auto-generate weights from FEMA scores
    weights = _default_readiness_weights()
    hazard_to_category = {
        'earthquake': 'structural_prep', 'tornado': 'shelter_prep',
        'hurricane': 'evacuation_prep', 'wildfire': 'evacuation_prep',
        'riverine_flooding': 'water_prep', 'coastal_flooding': 'water_prep',
        'drought': 'water_storage', 'cold_wave': 'heating_prep',
        'heat_wave': 'cooling_prep', 'winter_weather': 'winter_prep',
        'ice_storm': 'winter_prep',
    }
    for hazard, score in scores.items():
        cat = hazard_to_category.get(hazard)
        if cat and score > 50:
            weights[cat] = weights.get(cat, 1.0) + (score / 100.0)

    return jsonify({'adjusted': True, 'source': 'fema_auto', 'weights': weights})


# ─── First-run setup wizard ─────────────────────────────────────

@regional_profile_bp.route('/api/region/setup-status')
def api_region_setup_status():
    """Check if first-run setup is needed. Returns setup steps with completion status."""
    with db_session() as db:
        profile = db.execute(
            'SELECT * FROM regional_profile WHERE is_active = 1 ORDER BY id DESC LIMIT 1'
        ).fetchone()

        # Check data pack install status
        packs = db.execute(
            "SELECT pack_id, status FROM data_packs WHERE status = 'installed'"
        ).fetchall()
        installed_packs = {r['pack_id'] for r in packs}

        # Check if nutrition data is populated
        food_count = db.execute('SELECT COUNT(*) as c FROM nutrition_foods').fetchone()['c']
        nri_count = db.execute('SELECT COUNT(*) as c FROM fema_nri_counties').fetchone()['c']

    has_profile = profile is not None and profile['state']
    has_location = profile is not None and (profile['lat'] or profile['zip_code'])

    steps = [
        {
            'id': 'location',
            'title': 'Set your location',
            'description': 'Country, state, county, and ZIP code for regional personalization',
            'complete': has_location,
        },
        {
            'id': 'data_packs',
            'title': 'Install data packs',
            'description': 'Download FEMA hazard data and USDA nutrition database',
            'complete': 'fema_nri' in installed_packs and 'usda_sr_legacy' in installed_packs,
            'detail': {
                'fema_nri': nri_count > 0,
                'usda_sr_legacy': food_count > 0,
                'noaa_weather_stations': 'noaa_weather_stations' in installed_packs,
                'noaa_frost_dates': 'noaa_frost_dates' in installed_packs,
                'usda_hardiness_zones': 'usda_hardiness_zones' in installed_packs,
            },
        },
        {
            'id': 'threats',
            'title': 'Review regional threats',
            'description': 'See FEMA hazard scores for your county and adjust readiness weights',
            'complete': has_profile and bool(_safe_json_parse(profile.get('fema_risk_scores', '{}'))),
        },
        {
            'id': 'household',
            'title': 'Set household size',
            'description': 'Number of people for consumption calculations',
            'complete': True,  # Has a default, always "complete"
        },
    ]

    all_complete = all(s['complete'] for s in steps)

    return jsonify({
        'setup_needed': not all_complete,
        'all_complete': all_complete,
        'steps': steps,
        'profile_configured': has_profile,
    })


# ─── Hardiness zone lookup ────────────────────────────────────────

@regional_profile_bp.route('/api/region/hardiness/<zipcode>')
def api_region_hardiness(zipcode):
    with db_session() as db:
        row = db.execute(
            'SELECT zone, trange, state FROM usda_hardiness_zones WHERE zipcode = ?',
            (zipcode.strip(),)
        ).fetchone()
    if not row:
        return jsonify({'found': False})
    return jsonify({'found': True, 'zone': row['zone'], 'trange': row['trange'], 'state': row['state']})


# ─── Frost dates lookup (nearest to lat/lng) ─────────────────────

@regional_profile_bp.route('/api/region/frost-dates')
def api_region_frost_dates():
    try:
        lat = float(request.args.get('lat', 0))
        lng = float(request.args.get('lng', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'lat and lng required'}), 400
    if lat == 0 and lng == 0:
        return jsonify({'error': 'lat and lng required'}), 400

    with db_session() as db:
        row = db.execute(
            '''SELECT station_id, station_name, state, lat, lng,
                      last_spring_32f, first_fall_32f, growing_season_days
               FROM noaa_frost_dates
               WHERE last_spring_32f != ''
               ORDER BY ((lat - ?) * (lat - ?) + (lng - ?) * (lng - ?))
               LIMIT 1''',
            (lat, lat, lng, lng)
        ).fetchone()

    if not row:
        return jsonify({'found': False})
    return jsonify({'found': True, **dict(row)})


# ─── Nearest weather station lookup ──────────────────────────────

@regional_profile_bp.route('/api/region/nearest-station')
def api_region_nearest_station():
    try:
        lat = float(request.args.get('lat', 0))
        lng = float(request.args.get('lng', 0))
    except (TypeError, ValueError):
        return jsonify({'error': 'lat and lng required'}), 400
    if lat == 0 and lng == 0:
        return jsonify({'error': 'lat and lng required'}), 400

    with db_session() as db:
        row = db.execute(
            '''SELECT station_id, name, state, lat, lng, icao, elevation_m
               FROM noaa_stations
               ORDER BY ((lat - ?) * (lat - ?) + (lng - ?) * (lng - ?))
               LIMIT 1''',
            (lat, lat, lng, lng)
        ).fetchone()

    if not row:
        return jsonify({'found': False})
    return jsonify({'found': True, **dict(row)})


# ─── Helpers ──────────────────────────────────────────────────────

def _safe_json_parse(val):
    if not val:
        return {}
    try:
        return json.loads(val) if isinstance(val, str) else val
    except (json.JSONDecodeError, TypeError):
        return {}


def _score_to_rating(score):
    if score >= 80:
        return 'Very High'
    if score >= 60:
        return 'Relatively High'
    if score >= 40:
        return 'Relatively Moderate'
    if score >= 20:
        return 'Relatively Low'
    return 'Very Low'


def _default_readiness_weights():
    return {
        'food_storage': 1.0,
        'water_storage': 1.0,
        'medical_supplies': 1.0,
        'shelter_prep': 1.0,
        'evacuation_prep': 1.0,
        'communications': 1.0,
        'financial_prep': 1.0,
        'security': 1.0,
        'structural_prep': 1.0,
        'winter_prep': 1.0,
        'heating_prep': 1.0,
        'cooling_prep': 1.0,
        'water_prep': 1.0,
    }
