"""Situation Room v4 — World Monitor-inspired global intelligence dashboard.

Data sources (all free, no API keys required):
  - 100+ curated RSS/Atom feeds across 20 categories
  - USGS earthquakes (M2.5+ GeoJSON)
  - NWS severe weather alerts (Extreme/Severe)
  - GDACS crisis events (Orange/Red alert)
  - CoinGecko crypto prices (BTC/ETH/SOL)
  - Yahoo Finance stock indices (S&P 500, NASDAQ, Dow Jones)
  - metals.dev gold/silver prices
  - EIA Brent oil price
  - Fear & Greed Index
  - OpenSky Network aircraft positions (ADS-B)
  - NOAA SWPC space weather (Kp index, storm scales, solar flares)
  - Smithsonian GVP volcanic activity
  - Polymarket prediction markets
  - NASA FIRMS satellite fire detection (VIIRS)
  - WHO disease outbreak notifications
  - 12 live YouTube news channel embeds

All data cached to SQLite for full offline access.
Background fetch workers with per-source cooldowns and thread safety.
"""

import re
import logging
from datetime import datetime

import requests
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.utils import (
    get_query_int as _get_query_int,
    safe_json_object as _safe_json_object,
    safe_json_value as _safe_json_value,
    safe_float as _safe_float,
)
from web.validation import validate_json, validate_optional_json

# ─── Fetcher imports (extracted to web.sr_fetchers) ──────────────────
from web.sr_fetchers import (
    # Thread-safe state
    _state_lock, _last_fetch, _fetch_running,
    _get_state, _set_last_fetch,
    # HTTP helpers (used by some inline route fetches)
    _http_session, _REQ_HEADERS, _REQ_TIMEOUT,
    _fetch_with_retry, _safe_response_json,
    # Data constants
    RSS_FEEDS, ALL_FEEDS, FEED_CATEGORIES, LIVE_CHANNELS,
    FETCH_COOLDOWN,
    # Country geocoding (used by top-entities and pandemic-watch routes)
    _COUNTRY_COORDS,
    # Refresh orchestrator
    refresh_all_feeds,
)

situation_room_bp = Blueprint('situation_room', __name__)
log = logging.getLogger('nomad.situation_room')

# ─── API Routes ────────────────────────────────────────────────────────

@situation_room_bp.route('/api/sitroom/refresh', methods=['POST'])
def api_sitroom_refresh():
    started = refresh_all_feeds()
    return jsonify({'started': started, 'message': 'Refresh started' if started else 'Already refreshing'})


@situation_room_bp.route('/api/sitroom/status')
def api_sitroom_status():
    last, running = _get_state()
    return jsonify({
        'refreshing': running,
        'last_fetch': {k: v.isoformat() if v else None for k, v in last.items()},
        'feed_categories': FEED_CATEGORIES,
        'feed_count': len(ALL_FEEDS),
    })


@situation_room_bp.route('/api/sitroom/news')
def api_sitroom_news():
    category = request.args.get('category', '')
    limit = _get_query_int(request, 'limit', 100, minimum=1, maximum=500)
    offset = _get_query_int(request, 'offset', 0, minimum=0)
    with db_session() as db:
        if category:
            rows = db.execute('SELECT * FROM sitroom_news WHERE category = ? ORDER BY cached_at DESC LIMIT ? OFFSET ?',
                              (category, limit, offset)).fetchall()
            total = db.execute('SELECT COUNT(*) FROM sitroom_news WHERE category = ?', (category,)).fetchone()[0]
        else:
            rows = db.execute('SELECT * FROM sitroom_news ORDER BY cached_at DESC LIMIT ? OFFSET ?',
                              (limit, offset)).fetchall()
            total = db.execute('SELECT COUNT(*) FROM sitroom_news').fetchone()[0]
    return jsonify({'articles': [dict(r) for r in rows], 'total': total})


@situation_room_bp.route('/api/sitroom/events')
def api_sitroom_events():
    event_type = request.args.get('type', '')
    limit = _get_query_int(request, 'limit', 50, minimum=1, maximum=200)
    offset = _get_query_int(request, 'offset', 0, minimum=0)
    with db_session() as db:
        if event_type:
            rows = db.execute('SELECT * FROM sitroom_events WHERE event_type = ? ORDER BY cached_at DESC LIMIT ? OFFSET ?',
                              (event_type, limit, offset)).fetchall()
        else:
            rows = db.execute('SELECT * FROM sitroom_events ORDER BY cached_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify({'events': [dict(r) for r in rows]})


# ─── Proximity Board (location-aware threat filter) ────────────────────
#
# Takes the same sitroom_events table used by the global feeds and filters
# it against the user's home coordinates (stored in settings.latitude /
# .longitude). Produces a "Near You" view that ranks real threats to
# *your* location over global noise — a magnitude-4 quake 200km away is
# far more relevant than a magnitude-6 quake on the other side of the
# planet, but the default Situation Room view ranks by raw magnitude.

# Event types that have usable coordinates in sitroom_events
_PROXIMITY_EVENT_TYPES = (
    'earthquake', 'weather_alert', 'fire', 'disease', 'volcano',
    'conflict', 'ucdp_conflict', 'oref_alert',
)

# Labels shown in the proximity board — keeps the UI from having to know
# about every internal event_type string.
_PROXIMITY_LABELS = {
    'earthquake': 'Seismic',
    'weather_alert': 'Severe Weather',
    'fire': 'Fire',
    'disease': 'Disease Outbreak',
    'volcano': 'Volcanic Activity',
    'conflict': 'Armed Conflict',
    'ucdp_conflict': 'Armed Conflict',
    'oref_alert': 'Siren/Rocket Alert',
}

# Default distance rings (km) used both for bucket counts and the UI pills.
_PROXIMITY_RINGS = (50, 200, 500, 2000)


def _haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in kilometres.

    Uses the standard haversine formula. Returns a float. Callers must
    guarantee non-None floats — this helper does no input coercion so it
    stays fast in tight loops over thousands of events.
    """
    from math import radians, sin, cos, asin, sqrt
    R = 6371.0
    p1, p2 = radians(lat1), radians(lat2)
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(p1) * cos(p2) * sin(dlng / 2) ** 2
    return 2 * R * asin(sqrt(a))


def _bearing_deg(lat1, lng1, lat2, lng2):
    """Initial-bearing from (lat1,lng1) to (lat2,lng2), degrees 0–360."""
    from math import radians, sin, cos, atan2, degrees
    p1, p2 = radians(lat1), radians(lat2)
    dlng = radians(lng2 - lng1)
    x = sin(dlng) * cos(p2)
    y = cos(p1) * sin(p2) - sin(p1) * cos(p2) * cos(dlng)
    return (degrees(atan2(x, y)) + 360) % 360


def _compass_from_bearing(deg):
    """Compact 8-point compass label for a bearing in degrees."""
    dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
    return dirs[int((deg + 22.5) // 45) % 8]


def _get_home_coords(db):
    """Read the user's home coordinates + radius preference from settings.

    Returns ``(lat, lng, radius_km)`` as floats, or ``(None, None, default)``
    if coordinates haven't been configured. Radius defaults to 500 km — a
    "regional situational awareness" span that covers local weather, nearby
    fires, and neighbouring-state seismic events without being so wide that
    it collapses into the unfiltered global view.
    """
    rows = db.execute(
        "SELECT key, value FROM settings WHERE key IN ('latitude','longitude','proximity_radius_km')"
    ).fetchall()
    s = {r['key']: r['value'] for r in rows}
    def _f(v):
        try:
            return float(v) if v not in (None, '') else None
        except (TypeError, ValueError):
            return None
    radius = _f(s.get('proximity_radius_km')) or 500.0
    return _f(s.get('latitude')), _f(s.get('longitude')), radius


@situation_room_bp.route('/api/sitroom/proximity')
def api_sitroom_proximity():
    """Events within user-configured radius, nearest first, plus ring counts.

    Query params (optional):
      ?radius=<km>   override the stored proximity_radius_km
      ?limit=<n>     cap events returned (default 40, max 200)
    """
    try:
        override_radius = request.args.get('radius', type=float)
    except (TypeError, ValueError):
        override_radius = None
    try:
        limit = min(int(request.args.get('limit', 40)), 200)
    except (TypeError, ValueError):
        limit = 40

    with db_session() as db:
        home_lat, home_lng, default_radius = _get_home_coords(db)
        if home_lat is None or home_lng is None:
            # Return a structured "not configured" payload so the UI can
            # prompt the user to set their home coordinates without having
            # to distinguish a 404 from an empty result.
            return jsonify({
                'configured': False,
                'home_lat': None,
                'home_lng': None,
                'radius_km': default_radius,
                'events': [],
                'rings': {str(r): 0 for r in _PROXIMITY_RINGS},
                'by_type': {},
                'message': 'Set home coordinates in Settings to enable proximity alerts.',
            })

        radius_km = override_radius if override_radius and override_radius > 0 else default_radius
        placeholders = ','.join('?' * len(_PROXIMITY_EVENT_TYPES))
        rows = db.execute(
            f"SELECT event_id, event_type, title, magnitude, lat, lng, event_time, source_url "
            f"FROM sitroom_events WHERE event_type IN ({placeholders}) "
            f"AND lat IS NOT NULL AND lng IS NOT NULL "
            f"AND lat != 0 AND lng != 0 LIMIT 5000",
            _PROXIMITY_EVENT_TYPES,
        ).fetchall()

    events = []
    rings = {str(r): 0 for r in _PROXIMITY_RINGS}
    by_type = {}
    for r in rows:
        try:
            lat = float(r['lat'])
            lng = float(r['lng'])
        except (TypeError, ValueError):
            continue
        dist = _haversine_km(home_lat, home_lng, lat, lng)
        if dist > radius_km:
            continue
        for ring in _PROXIMITY_RINGS:
            if dist <= ring:
                rings[str(ring)] += 1
        etype = r['event_type']
        by_type[etype] = by_type.get(etype, 0) + 1
        bearing = _bearing_deg(home_lat, home_lng, lat, lng)
        events.append({
            'event_id': r['event_id'],
            'event_type': etype,
            'label': _PROXIMITY_LABELS.get(etype, etype.replace('_', ' ').title()),
            'title': r['title'] or '',
            'magnitude': r['magnitude'],
            'lat': lat,
            'lng': lng,
            'distance_km': round(dist, 1),
            'bearing_deg': round(bearing),
            'bearing_compass': _compass_from_bearing(bearing),
            'event_time': r['event_time'],
            'source_url': r['source_url'] or '',
        })
    events.sort(key=lambda e: e['distance_km'])
    return jsonify({
        'configured': True,
        'home_lat': home_lat,
        'home_lng': home_lng,
        'radius_km': radius_km,
        'events': events[:limit],
        'total_in_radius': len(events),
        'rings': rings,
        'by_type': by_type,
        'ring_labels': [str(r) for r in _PROXIMITY_RINGS],
    })


@situation_room_bp.route('/api/sitroom/earthquakes')
def api_sitroom_earthquakes():
    min_mag = request.args.get('min_magnitude', 0, type=float)
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'earthquake' AND (magnitude IS NULL OR magnitude >= ?) ORDER BY event_time DESC LIMIT ? OFFSET ?",
            (min_mag, limit, offset)).fetchall()
    return jsonify({'earthquakes': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/markets')
def api_sitroom_markets():
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_markets ORDER BY market_type, symbol LIMIT 500').fetchall()
    return jsonify({'markets': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/aviation')
def api_sitroom_aviation():
    """Return cached aircraft positions."""
    limit = _get_query_int(request, 'limit', 200, minimum=1, maximum=500)
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_aviation ORDER BY altitude_m DESC LIMIT ?', (limit,)).fetchall()
    return jsonify({'aircraft': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/ships')
def api_sitroom_ships():
    """Return cached vessel positions."""
    limit = _get_query_int(request, 'limit', 200, minimum=1, maximum=500)
    with db_session() as db:
        try:
            rows = db.execute('SELECT * FROM sitroom_ships ORDER BY speed_kn DESC LIMIT ?', (limit,)).fetchall()
        except Exception:
            rows = []
    return jsonify({'ships': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/space-weather')
def api_sitroom_space_weather():
    """Return cached space weather data."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_space_weather').fetchall()
    result = {}
    for r in rows:
        parsed = _safe_json_value(r['value_json'], None)
        if parsed is not None:
            result[r['data_type']] = parsed
    return jsonify(result)


@situation_room_bp.route('/api/sitroom/volcanoes')
def api_sitroom_volcanoes():
    """Return cached volcanic activity."""
    limit = _get_query_int(request, 'limit', 50, minimum=1, maximum=200)
    offset = _get_query_int(request, 'offset', 0, minimum=0)
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_volcanoes ORDER BY start_date DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify({'volcanoes': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/predictions')
def api_sitroom_predictions():
    """Return cached prediction markets."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_predictions WHERE active = 1 ORDER BY volume DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify({'predictions': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/summary')
def api_sitroom_summary():
    with _state_lock:
        running = _fetch_running
        last = dict(_last_fetch)

    with db_session() as db:
        counts = db.execute('''SELECT
            (SELECT COUNT(*) FROM sitroom_news) as news,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake') as quakes,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'weather_alert') as weather,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'conflict') as conflicts,
            (SELECT COUNT(*) FROM sitroom_markets) as markets,
            (SELECT COUNT(*) FROM sitroom_aviation) as aircraft,
            (SELECT COUNT(*) FROM sitroom_volcanoes) as volcanoes,
            (SELECT COUNT(*) FROM sitroom_predictions WHERE active = 1) as predictions,
            (SELECT COUNT(*) FROM sitroom_custom_feeds) as custom_feeds,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire') as fires,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'disease') as diseases,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'internet_outage') as outages,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'ucdp_conflict') as ucdp,
            (SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'cyber_threat') as cyber
        ''').fetchone()

        top_quakes = db.execute(
            "SELECT title, magnitude, lat, lng FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude IS NOT NULL ORDER BY magnitude DESC LIMIT 5"
        ).fetchall()

        market_rows = db.execute('SELECT * FROM sitroom_markets ORDER BY market_type, symbol LIMIT 500').fetchall()

        # Space weather summary
        sw_row = db.execute("SELECT value_json FROM sitroom_space_weather WHERE data_type = 'noaa_scales'").fetchone()
        space_weather = _safe_json_value(sw_row['value_json'] if sw_row else None, None)

    return jsonify({
        'news_count': counts['news'], 'earthquake_count': counts['quakes'],
        'weather_alert_count': counts['weather'], 'conflict_count': counts['conflicts'],
        'market_count': counts['markets'], 'aircraft_count': counts['aircraft'],
        'volcano_count': counts['volcanoes'], 'prediction_count': counts['predictions'],
        'custom_feed_count': counts['custom_feeds'],
        'fire_count': counts['fires'], 'disease_count': counts['diseases'],
        'outage_count': counts['outages'],
        'ucdp_count': counts['ucdp'], 'cyber_count': counts['cyber'],
        'top_earthquakes': [dict(r) for r in top_quakes],
        'markets': [dict(r) for r in market_rows],
        'space_weather': space_weather,
        'refreshing': running,
        'last_fetch': {k: v.isoformat() if v else None for k, v in last.items()},
    })


# ─── Custom Feed Management ───────────────────────────────────────────

@situation_room_bp.route('/api/sitroom/feeds')
def api_sitroom_feeds():
    with db_session() as db:
        custom = db.execute('SELECT * FROM sitroom_custom_feeds ORDER BY category, name LIMIT 200').fetchall()
    return jsonify({
        'builtin': [{'name': f['name'], 'url': f['url'], 'category': f['category']} for f in ALL_FEEDS],
        'custom': [dict(r) for r in custom],
        'categories': FEED_CATEGORIES,
    })


@situation_room_bp.route('/api/sitroom/feeds', methods=['POST'])
@validate_json({
    'name': {'type': str, 'required': True, 'max_length': 200},
    'url': {'type': str, 'required': True, 'max_length': 2000},
    'category': {'type': str, 'max_length': 100},
})
def api_sitroom_add_feed():
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()[:200]
    url = (data.get('url') or '').strip()[:2000]
    category = (data.get('category') or 'Custom').strip()[:100]
    if not name or not url:
        return jsonify({'error': 'Name and URL required'}), 400
    # URL validation — must be http/https
    if not re.match(r'^https?://', url, re.IGNORECASE):
        return jsonify({'error': 'URL must start with http:// or https://'}), 400

    with db_session() as db:
        existing = db.execute('SELECT id FROM sitroom_custom_feeds WHERE url = ?', (url,)).fetchone()
        if existing:
            return jsonify({'error': 'Feed URL already exists'}), 409
        cur = db.execute('INSERT INTO sitroom_custom_feeds (name, url, category) VALUES (?, ?, ?)', (name, url, category))
        db.commit()
        row = db.execute('SELECT * FROM sitroom_custom_feeds WHERE id = ?', (cur.lastrowid,)).fetchone()
    log_activity('Custom feed added', 'situation_room', name)
    return jsonify(dict(row)), 201


@situation_room_bp.route('/api/sitroom/feeds/<int:feed_id>', methods=['DELETE'])
def api_sitroom_delete_feed(feed_id):
    with db_session() as db:
        r = db.execute('DELETE FROM sitroom_custom_feeds WHERE id = ?', (feed_id,))
        if r.rowcount == 0:
            return jsonify({'error': 'Feed not found'}), 404
        db.commit()
    return jsonify({'deleted': True})


# ─── AI Briefing ───────────────────────────────────────────────────────

@situation_room_bp.route('/api/sitroom/ai-briefing', methods=['POST'])
def api_sitroom_ai_briefing():
    try:
        from services import ollama
    except ImportError:
        return jsonify({'error': 'AI service not available'}), 503

    with db_session() as db:
        news = db.execute('SELECT title, category, source_name FROM sitroom_news ORDER BY cached_at DESC LIMIT 30').fetchall()
        quakes = db.execute("SELECT title, magnitude FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 4.0 ORDER BY magnitude DESC LIMIT 10").fetchall()
        weather = db.execute("SELECT title FROM sitroom_events WHERE event_type = 'weather_alert' ORDER BY cached_at DESC LIMIT 10").fetchall()
        markets = db.execute('SELECT symbol, price, change_24h, market_type FROM sitroom_markets').fetchall()
        sw_row = db.execute("SELECT value_json FROM sitroom_space_weather WHERE data_type = 'noaa_scales'").fetchone()

    parts = ['You are a concise intelligence analyst. Generate a brief situation report based on the following real-time data.\n']

    if news:
        parts.append('--- TOP HEADLINES ---')
        for n in news:
            parts.append(f"[{n['category']}] {n['title']} ({n['source_name']})")

    if quakes:
        parts.append('\n--- SEISMIC ACTIVITY ---')
        for q in quakes:
            parts.append(f"M{q['magnitude']} - {q['title']}")

    if weather:
        parts.append('\n--- SEVERE WEATHER ---')
        for w in weather:
            parts.append(f"- {w['title']}")

    if markets:
        parts.append('\n--- MARKETS ---')
        for m in markets:
            d = '+' if (m['change_24h'] or 0) >= 0 else ''
            parts.append(f"{m['symbol']}: ${m['price']:,.2f} ({d}{m['change_24h'] or 0:.1f}%)")

    if sw_row:
        sw = _safe_json_object(sw_row['value_json'], {})
        if sw:
            parts.append(f"\n--- SPACE WEATHER ---")
            parts.append(f"Radio Blackout: R{sw.get('R', {}).get('Scale', 0)} | Solar Radiation: S{sw.get('S', {}).get('Scale', 0)} | Geomagnetic: G{sw.get('G', {}).get('Scale', 0)}")

    parts.append('\nProvide a concise 3-5 paragraph intelligence briefing. Use professional military-style format. Start with "SITUATION REPORT" header and current date/time.')

    try:
        result = ollama.chat('\n'.join(parts), model=None, stream=False)
        if isinstance(result, dict):
            briefing = result.get('message', {}).get('content', '') or result.get('response', '')
        else:
            briefing = str(result)
    except Exception:
        return jsonify({'error': 'AI briefing generation failed — ensure AI service is running'}), 503

    with db_session() as db:
        db.execute('INSERT INTO sitroom_briefings (content, generated_at) VALUES (?, CURRENT_TIMESTAMP)', (briefing,))
        db.commit()

    return jsonify({'briefing': briefing})


@situation_room_bp.route('/api/sitroom/briefings')
def api_sitroom_briefings():
    limit = _get_query_int(request, 'limit', 10, minimum=1, maximum=50)
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_briefings ORDER BY generated_at DESC LIMIT ?', (limit,)).fetchall()
    return jsonify({'briefings': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/fires')
def api_sitroom_fires():
    """Return cached fire detections."""
    limit = _get_query_int(request, 'limit', 200, minimum=1, maximum=500)
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'fire' ORDER BY magnitude DESC LIMIT ?",
                          (limit,)).fetchall()
    return jsonify({'fires': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/diseases')
def api_sitroom_diseases():
    """Return cached disease outbreak data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'disease' ORDER BY cached_at DESC LIMIT 30").fetchall()
    return jsonify({'outbreaks': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/category-feed/<category>')
def api_sitroom_category_feed(category):
    """Return news for a specific category."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_news WHERE category = ? ORDER BY cached_at DESC LIMIT 15",
                          (category,)).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/keyword-search/<path:keywords>')
def api_sitroom_keyword_search(keywords):
    """Search news by pipe-separated keywords."""
    kws = [k.strip() for k in keywords.split('|') if k.strip()]
    if not kws:
        return jsonify({'articles': [], 'count': 0})
    conditions = ' OR '.join(['LOWER(title) LIKE ?' for _ in kws])
    params = [f'%{k.lower()}%' for k in kws]
    with db_session() as db:
        rows = db.execute(f"SELECT title, link, source_name FROM sitroom_news WHERE {conditions} ORDER BY cached_at DESC LIMIT 15", params).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/pop-exposure')
def api_sitroom_pop_exposure():
    """Estimate population exposure to major events."""
    # Rough population density estimates for earthquake regions
    with db_session() as db:
        quakes = db.execute(
            "SELECT title, magnitude, lat, lng FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 5 ORDER BY magnitude DESC LIMIT 5"
        ).fetchall()
    exposures = []
    for q in quakes:
        mag = dict(q)['magnitude'] or 0
        # Very rough estimate: radius in km ~ 10^(mag-3), pop density ~50/km2 average
        radius_km = min(500, 10 ** max(0, mag - 3))
        area = 3.14159 * radius_km * radius_km
        est_pop = int(area * 50)  # rough global average density
        exposures.append({'title': dict(q)['title'], 'magnitude': mag,
                          'radius_km': round(radius_km), 'estimated_population': est_pop})
    return jsonify({'exposures': exposures, 'count': len(exposures)})


@situation_room_bp.route('/api/sitroom/market-brief', methods=['POST'])
def api_sitroom_market_brief():
    """Generate daily market brief."""
    with db_session() as db:
        markets = db.execute("SELECT symbol, price, change_24h, market_type FROM sitroom_markets ORDER BY market_type, symbol").fetchall()
        fin_news = db.execute("SELECT title FROM sitroom_news WHERE category IN ('Finance', 'Crypto') ORDER BY cached_at DESC LIMIT 10").fetchall()

    brief = "## DAILY MARKET BRIEF\n\n"
    # Group by type
    by_type = {}
    for m in markets:
        t = dict(m)['market_type']
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(dict(m))

    for mtype, items in by_type.items():
        brief += f"### {mtype.upper()}\n"
        for m in items:
            ch = m['change_24h'] or 0
            arrow = '+' if ch >= 0 else ''
            brief += f"- {m['symbol']}: ${m['price']:.2f} ({arrow}{ch:.1f}%)\n"
        brief += "\n"

    if fin_news:
        brief += "### KEY HEADLINES\n"
        for n in fin_news[:5]:
            brief += f"- {dict(n)['title']}\n"

    return jsonify({'brief': brief})


@situation_room_bp.route('/api/sitroom/rd-signal')
def api_sitroom_rd_signal():
    """Return defense R&D / patent signal news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%patent%' OR LOWER(title) LIKE '%darpa%' OR LOWER(title) LIKE '%defense research%' OR LOWER(title) LIKE '%hypersonic%' OR LOWER(title) LIKE '%weapons system%' OR LOWER(title) LIKE '%defense contract%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/chokepoints')
def api_sitroom_chokepoints():
    """Return strategic chokepoint / shipping lane news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%hormuz%' OR LOWER(title) LIKE '%suez%' OR LOWER(title) LIKE '%malacca%' OR LOWER(title) LIKE '%bosphorus%' OR LOWER(title) LIKE '%panama canal%' OR LOWER(title) LIKE '%red sea%' OR LOWER(title) LIKE '%houthi%' OR LOWER(title) LIKE '%chokepoint%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/ai-regulation')
def api_sitroom_ai_regulation():
    """Return AI policy and regulation news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%ai regulation%' OR LOWER(title) LIKE '%ai policy%' OR LOWER(title) LIKE '%ai act%' OR LOWER(title) LIKE '%ai safety%' OR LOWER(title) LIKE '%ai governance%' OR LOWER(title) LIKE '%artificial intelligence law%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/fin-regulation')
def api_sitroom_fin_regulation():
    """Return financial regulation news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%sec %' OR LOWER(title) LIKE '%regulation%' OR LOWER(title) LIKE '%compliance%' OR LOWER(title) LIKE '%banking regulation%' OR LOWER(title) LIKE '%dodd-frank%' OR LOWER(title) LIKE '%financial regulation%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/security-advisories')
def api_sitroom_security_advisories():
    """Return security/travel advisories from news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%advisory%' OR LOWER(title) LIKE '%travel warning%' OR LOWER(title) LIKE '%travel ban%' OR LOWER(title) LIKE '%evacuation%' OR LOWER(title) LIKE '%embassy%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'advisories': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/central-banks')
def api_sitroom_central_banks():
    """Return central bank news and policy."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_news WHERE category = 'Central Banks' ORDER BY cached_at DESC LIMIT 15").fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/ai-research')
def api_sitroom_ai_research():
    """Return AI research papers from ArXiv."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_news WHERE category = 'AI Research' ORDER BY cached_at DESC LIMIT 15").fetchall()
    return jsonify({'papers': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/macro-stress')
def api_sitroom_macro_stress():
    """Return macro stress indicators from FRED."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'macro_indicator' ORDER BY title").fetchall()
    return jsonify({'indicators': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/forex')
def api_sitroom_forex():
    """Return forex-specific market data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_markets WHERE market_type = 'forex' ORDER BY symbol").fetchall()
    return jsonify({'pairs': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/crypto-sectors')
def api_sitroom_crypto_sectors():
    """Return crypto data grouped by type."""
    with db_session() as db:
        crypto = db.execute("SELECT * FROM sitroom_markets WHERE market_type = 'crypto' ORDER BY price DESC").fetchall()
        stables = db.execute("SELECT * FROM sitroom_markets WHERE market_type = 'stablecoin' ORDER BY symbol").fetchall()
    return jsonify({'crypto': [dict(r) for r in crypto], 'stablecoins': [dict(r) for r in stables]})


@situation_room_bp.route('/api/sitroom/layoffs')
def api_sitroom_layoffs():
    """Return layoff-related news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE category = 'Layoffs' OR LOWER(title) LIKE '%layoff%' OR LOWER(title) LIKE '%job cuts%' OR LOWER(title) LIKE '%workforce reduction%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'layoffs': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/airline-intel')
def api_sitroom_airline_intel():
    """Return aviation intelligence from news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%airline%' OR LOWER(title) LIKE '%airport%' OR LOWER(title) LIKE '%flight%' OR LOWER(title) LIKE '%aviation%' OR LOWER(title) LIKE '%boeing%' OR LOWER(title) LIKE '%airbus%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/supply-chain')
def api_sitroom_supply_chain():
    """Return supply chain intelligence."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE category = 'Supply Chain' OR LOWER(title) LIKE '%supply chain%' OR LOWER(title) LIKE '%shipping%' OR LOWER(title) LIKE '%freight%' OR LOWER(title) LIKE '%port%' OR LOWER(title) LIKE '%logistics%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/news-sentiment')
def api_sitroom_news_sentiment():
    """Compute simple sentiment distribution from news headlines."""
    negative_words = {'war', 'attack', 'crisis', 'crash', 'death', 'killed', 'bomb', 'threat', 'sanctions', 'collapse', 'recession', 'disaster', 'emergency', 'conflict', 'strike', 'protest', 'violence', 'terror', 'fraud'}
    positive_words = {'growth', 'recovery', 'peace', 'deal', 'agreement', 'breakthrough', 'record', 'surge', 'rally', 'boost', 'innovation', 'success', 'win', 'progress', 'advance'}
    with db_session() as db:
        rows = db.execute("SELECT title FROM sitroom_news ORDER BY cached_at DESC LIMIT 100").fetchall()
    pos = neg = neu = 0
    for r in rows:
        words = set(dict(r)['title'].lower().split())
        if words & negative_words:
            neg += 1
        elif words & positive_words:
            pos += 1
        else:
            neu += 1
    total = pos + neg + neu or 1
    return jsonify({'positive': pos, 'negative': neg, 'neutral': neu, 'total': total,
                    'sentiment_score': round((pos - neg) / total * 100, 1)})


@situation_room_bp.route('/api/sitroom/cii-geo')
def api_sitroom_cii_geo():
    """Return CII scores per country for choropleth rendering."""
    with db_session() as db:
        events = db.execute("SELECT detail_json, event_type, magnitude FROM sitroom_events").fetchall()
    scores = {}
    for ev in events:
        det = _safe_json_object(dict(ev).get('detail_json'), {})
        country = det.get('country', '')
        if not country or country == 'Unknown':
            continue
        if country not in scores:
            scores[country] = 0
        scores[country] += 1
        if dict(ev)['magnitude']:
            scores[country] += float(dict(ev)['magnitude'])
    # Normalize to 0-100
    max_score = max(scores.values()) if scores else 1
    result = {c: min(100, round(s / max_score * 100)) for c, s in scores.items()}
    return jsonify({'scores': result})


@situation_room_bp.route('/api/sitroom/product-hunt')
def api_sitroom_product_hunt():
    """Return Product Hunt trending products."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_news WHERE category = 'Product Hunt' ORDER BY cached_at DESC LIMIT 10").fetchall()
    return jsonify({'products': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/earnings')
def api_sitroom_earnings():
    """Return upcoming earnings from news headlines."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%earnings%' OR LOWER(title) LIKE '%quarterly%' OR LOWER(title) LIKE '%revenue%' OR LOWER(title) LIKE '%profit%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'earnings': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/github-trending')
def api_sitroom_github_trending():
    """Return GitHub trending repositories."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'github_trending' ORDER BY magnitude DESC LIMIT 15").fetchall()
    return jsonify({'repos': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/fuel-prices')
def api_sitroom_fuel_prices():
    """Return fuel price data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'fuel_price' ORDER BY cached_at DESC LIMIT 5").fetchall()
    return jsonify({'prices': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/intelligence-gap')
def api_sitroom_intelligence_gap():
    """Detect which data sources are stale or missing."""
    gaps = []
    last, _ = _get_state()
    now = datetime.now()
    source_labels = {
        'rss': 'News Feeds', 'earthquakes': 'Seismic Data', 'weather_alerts': 'Weather Alerts',
        'markets': 'Market Data', 'conflicts': 'Crisis Events', 'aviation': 'Aircraft Tracking',
        'space_weather': 'Space Weather', 'volcanoes': 'Volcanic Activity', 'predictions': 'Prediction Markets',
        'fires': 'Fire Detection', 'disease_outbreaks': 'Disease Outbreaks', 'internet_outages': 'Internet Outages',
        'radiation': 'Radiation Monitoring', 'gdelt_trending': 'GDELT Intelligence', 'sanctions': 'Sanctions Data',
        'displacement': 'Displacement Data', 'ucdp': 'Armed Conflicts', 'cyber_threats': 'Cyber Threats',
        'yield_curve': 'Yield Curve', 'stablecoins': 'Stablecoins', 'correlation': 'Correlation Engine',
        'service_status': 'Service Status', 'social_velocity': 'Social Velocity',
        'renewable': 'Renewable Energy', 'bigmac': 'Big Mac Index',
        'github_trending': 'GitHub Trending', 'fuel_prices': 'Fuel Prices',
    }
    for source, label in source_labels.items():
        last_time = last.get(source)
        cooldown = FETCH_COOLDOWN.get(source, 300)
        if not last_time:
            gaps.append({'source': source, 'label': label, 'status': 'missing', 'age': None})
        else:
            age_sec = (now - last_time).total_seconds()
            status = 'fresh' if age_sec < cooldown * 2 else 'stale' if age_sec < cooldown * 5 else 'old'
            gaps.append({'source': source, 'label': label, 'status': status, 'age': int(age_sec)})
    return jsonify({'gaps': gaps, 'total': len(gaps),
                    'missing': sum(1 for g in gaps if g['status'] == 'missing'),
                    'stale': sum(1 for g in gaps if g['status'] == 'stale')})


@situation_room_bp.route('/api/sitroom/humanitarian-summary')
def api_sitroom_humanitarian_summary():
    """Return aggregate humanitarian statistics."""
    with db_session() as db:
        displacement = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'displacement'").fetchone()[0]
        disease = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'disease'").fetchone()[0]
        conflicts = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type IN ('conflict', 'ucdp_conflict')").fetchone()[0]
        fires = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'").fetchone()[0]
        weather = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'weather_alert'").fetchone()[0]
        quakes_big = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 5").fetchone()[0]
    return jsonify({
        'displacement_records': displacement, 'disease_outbreaks': disease,
        'active_conflicts': conflicts, 'active_fires': fires,
        'severe_weather': weather, 'significant_quakes': quakes_big,
    })


@situation_room_bp.route('/api/sitroom/renewable')
def api_sitroom_renewable():
    """Return renewable energy news."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_news WHERE category = 'Renewable' ORDER BY cached_at DESC LIMIT 15").fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/bigmac')
def api_sitroom_bigmac():
    """Return Big Mac Index data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'bigmac' ORDER BY magnitude DESC LIMIT 30").fetchall()
    return jsonify({'countries': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/service-status')
def api_sitroom_service_status():
    """Return cloud service status."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'service_status' ORDER BY cached_at DESC LIMIT 20").fetchall()
    return jsonify({'services': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/social-velocity')
def api_sitroom_social_velocity():
    """Return social velocity — fast-spreading stories."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'social_velocity' ORDER BY magnitude DESC LIMIT 15").fetchall()
    return jsonify({'stories': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/correlations')
def api_sitroom_correlations():
    """Return cross-domain correlation signals."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'correlation' ORDER BY cached_at DESC").fetchall()
    return jsonify({'signals': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/yield-curve')
def api_sitroom_yield_curve():
    """Return Treasury yield curve data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'yield_curve' ORDER BY magnitude DESC LIMIT 20").fetchall()
    return jsonify({'rates': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/stablecoins')
def api_sitroom_stablecoins():
    """Return stablecoin market data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_markets WHERE market_type = 'stablecoin' ORDER BY symbol").fetchall()
    return jsonify({'stablecoins': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/ucdp')
def api_sitroom_ucdp():
    """Return UCDP armed conflict events."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'ucdp_conflict' ORDER BY magnitude DESC LIMIT 50").fetchall()
    return jsonify({'conflicts': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/protests')
def api_sitroom_protests():
    """Return protest/unrest events from UCDP + news keyword matching."""
    with db_session() as db:
        # UCDP violence type 2 = one-sided (protests), type 3 = non-state
        ucdp_rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'ucdp_conflict' AND "
            "(LOWER(title) LIKE '%protest%' OR LOWER(title) LIKE '%unrest%' OR LOWER(title) LIKE '%demonstration%' "
            "OR LOWER(title) LIKE '%riot%' OR LOWER(title) LIKE '%uprising%' OR LOWER(title) LIKE '%civil%') "
            "ORDER BY cached_at DESC LIMIT 30"
        ).fetchall()
        # Also check news for protest keywords with geocodable locations
        news_rows = db.execute(
            "SELECT title, link, source_name, published FROM sitroom_news WHERE "
            "(LOWER(title) LIKE '%protest%' OR LOWER(title) LIKE '%riot%' OR LOWER(title) LIKE '%demonstration%' "
            "OR LOWER(title) LIKE '%unrest%' OR LOWER(title) LIKE '%uprising%' OR LOWER(title) LIKE '%strike %') "
            "ORDER BY cached_at DESC LIMIT 20"
        ).fetchall()
    events = [dict(r) for r in ucdp_rows]
    # News items don't have coordinates but we return them for the card
    news_items = [dict(r) for r in news_rows]
    return jsonify({'events': events, 'news': news_items, 'count': len(events) + len(news_items)})


@situation_room_bp.route('/api/sitroom/cyber-threats')
def api_sitroom_cyber_threats():
    """Return cyber threat data (CISA KEV + advisories)."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'cyber_threat' ORDER BY cached_at DESC LIMIT 30").fetchall()
    return jsonify({'threats': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/osint')
def api_sitroom_osint():
    """Return OSINT-categorized news articles."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_news WHERE category = 'OSINT' ORDER BY cached_at DESC LIMIT 50").fetchall()
    return jsonify({'articles': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/export')
def api_sitroom_export():
    """Export current intelligence as a text report."""
    with db_session() as db:
        news = db.execute("SELECT title, category, source_name FROM sitroom_news ORDER BY cached_at DESC LIMIT 30").fetchall()
        quakes = db.execute("SELECT title, magnitude FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 4 ORDER BY magnitude DESC LIMIT 10").fetchall()
        weather = db.execute("SELECT title FROM sitroom_events WHERE event_type = 'weather_alert' LIMIT 10").fetchall()
        markets = db.execute("SELECT symbol, price, change_24h, market_type FROM sitroom_markets ORDER BY market_type, symbol").fetchall()
        crises = db.execute("SELECT title FROM sitroom_events WHERE event_type = 'conflict' LIMIT 10").fetchall()
        fires_ct = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'").fetchone()[0]

    lines = []
    lines.append('=' * 60)
    lines.append('SITUATION ROOM — INTELLIGENCE REPORT')
    lines.append(f'Generated: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}')
    lines.append('=' * 60)
    lines.append('')

    if markets:
        lines.append('--- MARKETS ---')
        for m in markets:
            ch = m['change_24h'] or 0
            arrow = '+' if ch >= 0 else ''
            lines.append(f"  {m['symbol']}: ${m['price']:.2f} ({arrow}{ch:.1f}%)")
        lines.append('')

    if quakes:
        lines.append('--- SEISMIC ACTIVITY ---')
        for q in quakes:
            lines.append(f"  M{q['magnitude']:.1f} - {q['title']}")
        lines.append('')

    if weather:
        lines.append('--- SEVERE WEATHER ---')
        for w in weather:
            lines.append(f"  {w['title']}")
        lines.append('')

    if crises:
        lines.append('--- CRISIS EVENTS ---')
        for c in crises:
            lines.append(f"  {c['title']}")
        lines.append('')

    lines.append(f'--- SATELLITE FIRES: {fires_ct} active detections ---')
    lines.append('')

    if news:
        lines.append('--- TOP HEADLINES ---')
        for n in news:
            lines.append(f"  [{n['category']}] {n['title']} ({n['source_name']})")
        lines.append('')

    lines.append('=' * 60)
    lines.append('END OF REPORT')

    from flask import Response
    report = '\n'.join(lines)
    return Response(report, mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename=sitroom-report-{datetime.now().strftime("%Y%m%d-%H%M")}.txt'})


@situation_room_bp.route('/api/sitroom/radiation')
def api_sitroom_radiation():
    """Return cached radiation monitoring data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'radiation' ORDER BY magnitude DESC LIMIT 50").fetchall()
    return jsonify({'readings': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/trending')
def api_sitroom_trending():
    """Return GDELT trending topics."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'gdelt_trend' ORDER BY cached_at DESC LIMIT 30").fetchall()
    return jsonify({'topics': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/sanctions')
def api_sitroom_sanctions():
    """Return sanctions and trade policy data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'sanctions' ORDER BY cached_at DESC LIMIT 20").fetchall()
    return jsonify({'items': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/displacement')
def api_sitroom_displacement():
    """Return UNHCR displacement data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'displacement' ORDER BY magnitude DESC LIMIT 20").fetchall()
    return jsonify({'records': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/country/<country>')
def api_sitroom_country_deep_dive(country):
    """Return aggregated intelligence for a specific country."""
    with db_session() as db:
        # Events mentioning this country
        events = db.execute(
            "SELECT event_type, COUNT(*) as cnt FROM sitroom_events WHERE detail_json LIKE ? GROUP BY event_type",
            (f'%{country}%',)).fetchall()

        # News mentioning this country
        news = db.execute(
            "SELECT title, link, category, source_name FROM sitroom_news WHERE title LIKE ? OR description LIKE ? ORDER BY cached_at DESC LIMIT 15",
            (f'%{country}%', f'%{country}%')).fetchall()

        # Earthquakes near this country
        quakes = db.execute(
            "SELECT title, magnitude FROM sitroom_events WHERE event_type = 'earthquake' AND title LIKE ? ORDER BY magnitude DESC LIMIT 5",
            (f'%{country}%',)).fetchall()

        # Market data for context
        markets = db.execute('SELECT symbol, price, change_24h FROM sitroom_markets ORDER BY market_type LIMIT 10').fetchall()

        # Total event count
        total_events = db.execute(
            "SELECT COUNT(*) FROM sitroom_events WHERE detail_json LIKE ?",
            (f'%{country}%',)).fetchone()[0]

    return jsonify({
        'country': country,
        'total_events': total_events,
        'event_summary': {dict(e)['event_type']: dict(e)['cnt'] for e in events},
        'recent_news': [dict(r) for r in news],
        'recent_quakes': [dict(r) for r in quakes],
        'global_markets': [dict(r) for r in markets[:5]],
    })


@situation_room_bp.route('/api/sitroom/internet-outages')
def api_sitroom_internet_outages():
    """Return cached internet outage data."""
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'internet_outage' ORDER BY cached_at DESC LIMIT 30").fetchall()
    return jsonify({'outages': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/live-channels')
def api_sitroom_live_channels():
    """Return list of live YouTube news channels."""
    return jsonify({'channels': LIVE_CHANNELS})


# ─── Keyword Monitors ────────────────────────────────────────────────

@situation_room_bp.route('/api/sitroom/monitors')
def api_sitroom_monitors():
    """Return keyword monitor list and matches."""
    with db_session() as db:
        # Ensure table exists on first access before POST has ever been called
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_monitors
            (id INTEGER PRIMARY KEY, keyword TEXT NOT NULL, color TEXT DEFAULT '#4aedc4',
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        monitors = db.execute('SELECT * FROM sitroom_monitors ORDER BY created_at DESC LIMIT 200').fetchall()
        # Resolve matches within the same session to avoid N+1 connections
        results = []
        for m in monitors:
            kw = m['keyword'].lower()
            matches = db.execute(
                "SELECT title, link, category, source_name FROM sitroom_news "
                "WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 10",
                (f'%{kw}%',),
            ).fetchall()
            results.append({**dict(m), 'matches': [dict(r) for r in matches], 'match_count': len(matches)})

    return jsonify({'monitors': results})


@situation_room_bp.route('/api/sitroom/monitors', methods=['POST'])
@validate_json({
    'keyword': {'type': str, 'required': True, 'max_length': 100},
    'color': {'type': str, 'max_length': 20},
})
def api_sitroom_add_monitor():
    data = request.get_json() or {}
    keyword = (data.get('keyword') or '').strip()[:100]
    color = (data.get('color') or '#4aedc4').strip()[:20]
    if not keyword:
        return jsonify({'error': 'Keyword required'}), 400
    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_monitors
            (id INTEGER PRIMARY KEY, keyword TEXT NOT NULL, color TEXT DEFAULT '#4aedc4',
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('INSERT INTO sitroom_monitors (keyword, color) VALUES (?, ?)', (keyword, color))
        db.commit()
    return jsonify({'ok': True}), 201


@situation_room_bp.route('/api/sitroom/monitors/<int:mid>', methods=['DELETE'])
def api_sitroom_delete_monitor(mid):
    with db_session() as db:
        r = db.execute('DELETE FROM sitroom_monitors WHERE id = ?', (mid,))
        if r.rowcount == 0:
            return jsonify({'error': 'not found'}), 404
        db.commit()
    return jsonify({'ok': True})


# ─── AI Intelligence Briefing (uses Ollama if available) ─────────────

# Duplicate route removed — api_sitroom_ai_briefing above handles POST /api/sitroom/ai-briefing


# ─── Economic Data (FRED-style) ──────────────────────────────────────

@situation_room_bp.route('/api/sitroom/economic-calendar')
def api_sitroom_economic_calendar():
    """Return upcoming economic events from news."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name, published FROM sitroom_news WHERE category IN ('Finance', 'Government') AND (LOWER(title) LIKE '%fed%' OR LOWER(title) LIKE '%rate%' OR LOWER(title) LIKE '%gdp%' OR LOWER(title) LIKE '%inflation%' OR LOWER(title) LIKE '%employment%' OR LOWER(title) LIKE '%treasury%' OR LOWER(title) LIKE '%ecb%' OR LOWER(title) LIKE '%boj%') ORDER BY cached_at DESC LIMIT 20"
        ).fetchall()
    return jsonify({'events': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/national-debt')
def api_sitroom_national_debt():
    """Return estimated national debt figures."""
    # US national debt from Treasury API (fiscal data)
    debt = {}
    try:
        resp = _http_session.get('https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny',
                            params={'sort': '-record_date', 'page[size]': 1},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            payload = _safe_response_json(resp, {})
            data = payload.get('data', []) if isinstance(payload, dict) else []
            if data:
                debt['us'] = {'total': float(data[0].get('tot_pub_debt_out_amt', 0)),
                              'date': data[0].get('record_date', '')}
    except Exception as e:
        log.debug(f"Treasury debt fetch failed: {e}")
    return jsonify({'debt': debt})


# ─── P3: New API Routes ───────────────────────────────────────────────

@situation_room_bp.route('/api/sitroom/oref-alerts')
def api_sitroom_oref_alerts():
    """Return cached Israel OREF rocket/siren alerts."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'oref_alert' ORDER BY event_time DESC LIMIT 50"
        ).fetchall()
    return jsonify({'alerts': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/gdelt-full')
def api_sitroom_gdelt_full():
    """Return full GDELT data (volume, tone timeline, hotspots)."""
    with db_session() as db:
        try:
            rows = db.execute('SELECT * FROM sitroom_gdelt').fetchall()
        except Exception:
            return jsonify({'volume': None, 'tone': None, 'hotspots': None})
    result = {}
    for r in rows:
        parsed = _safe_json_value(r['value_json'], None)
        if parsed is not None:
            result[r['data_type']] = parsed
    return jsonify(result)


@situation_room_bp.route('/api/sitroom/cot-positioning')
def api_sitroom_cot_positioning():
    """Return CFTC Commitments of Traders positioning data."""
    with db_session() as db:
        try:
            rows = db.execute(
                'SELECT * FROM sitroom_cot ORDER BY report_date DESC LIMIT 50'
            ).fetchall()
        except Exception:
            rows = []
    return jsonify({'positions': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/breaking-news')
def api_sitroom_breaking_news():
    """Detect breaking news from cached articles using urgency scoring."""
    with db_session() as db:
        # Get recent articles (last 2 hours)
        rows = db.execute(
            "SELECT title, link, source_name, category, published, cached_at FROM sitroom_news "
            "WHERE cached_at > datetime('now', '-2 hours') ORDER BY cached_at DESC LIMIT 200"
        ).fetchall()

    if not rows:
        return jsonify({'breaking': [], 'count': 0})

    breaking_keywords = {
        'breaking': 5, 'just in': 5, 'developing': 4, 'urgent': 5, 'alert': 4,
        'explosion': 4, 'attack': 3, 'killed': 3, 'shooting': 4, 'missile': 4,
        'earthquake': 3, 'tsunami': 5, 'invasion': 5, 'war': 3, 'coup': 5,
        'nuclear': 4, 'crash': 3, 'emergency': 3, 'evacuation': 3, 'hostage': 4,
        'ceasefire': 3, 'surrender': 4, 'declaration': 3, 'sanctions': 2,
    }

    scored = []
    for r in rows:
        d = dict(r)
        title_lower = d['title'].lower()
        score = 0
        matched = []
        for kw, weight in breaking_keywords.items():
            if kw in title_lower:
                score += weight
                matched.append(kw)
        # Boost OSINT and conflict categories
        if d.get('category') in ('OSINT', 'Conflict', 'Security'):
            score += 2
        # Boost if multiple sources cover same topic (crude check)
        if score > 0:
            d['urgency_score'] = score
            d['matched_keywords'] = matched
            scored.append(d)

    # Sort by urgency score descending, take top 10
    scored.sort(key=lambda x: x['urgency_score'], reverse=True)
    return jsonify({'breaking': scored[:10], 'count': len(scored)})


@situation_room_bp.route('/api/sitroom/country-brief/<country>')
def api_sitroom_country_brief(country):
    """Generate an AI intelligence brief for a specific country using cached data."""
    # Collect all data mentioning this country
    country_lower = country.lower()

    with db_session() as db:
        news = db.execute(
            "SELECT title, source_name, category FROM sitroom_news WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 20",
            (f'%{country_lower}%',)
        ).fetchall()
        events = db.execute(
            "SELECT title, event_type, magnitude FROM sitroom_events WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 15",
            (f'%{country_lower}%',)
        ).fetchall()

    news_items = [dict(r) for r in news]
    event_items = [dict(r) for r in events]

    # Build context for AI or structured brief
    brief = {
        'country': country,
        'news_count': len(news_items),
        'event_count': len(event_items),
        'recent_news': news_items[:10],
        'recent_events': event_items[:10],
        'categories': list(set(n.get('category', '') for n in news_items if n.get('category'))),
        'event_types': list(set(e.get('event_type', '') for e in event_items if e.get('event_type'))),
    }

    # Try AI-generated summary if Ollama available
    try:
        from services import ollama as _ollama_svc
        context = f"Country: {country}\n\nRecent headlines:\n"
        for n in news_items[:10]:
            context += f"- [{n.get('category', '')}] {n['title']} ({n.get('source_name', '')})\n"
        for e in event_items[:5]:
            context += f"- [Event: {e.get('event_type', '')}] {e['title']}"
            if e.get('magnitude'):
                context += f" (magnitude: {e['magnitude']})"
            context += "\n"

        prompt = (f"You are an intelligence analyst. Based on the following recent data about {country}, "
                  f"write a concise 3-paragraph intelligence brief covering: "
                  f"(1) Current situation overview, (2) Key risks and developments, "
                  f"(3) Outlook and watch items.\n\n{context}")

        result = _ollama_svc.chat(prompt, model=None, stream=False)
        if isinstance(result, dict):
            brief['ai_summary'] = result.get('message', {}).get('content', '') or result.get('response', '')
        else:
            brief['ai_summary'] = str(result)
    except Exception:
        brief['ai_summary'] = None

    return jsonify(brief)


@situation_room_bp.route('/api/sitroom/news-clusters')
def api_sitroom_news_clusters():
    """Cluster related news stories using word-level Jaccard similarity."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name, category FROM sitroom_news ORDER BY cached_at DESC LIMIT 200"
        ).fetchall()

    if not rows:
        return jsonify({'clusters': [], 'count': 0})

    articles = [dict(r) for r in rows]

    # Tokenize titles into word sets
    def _words(title):
        return set(re.sub(r'[^\w\s]', '', title.lower()).split())

    word_sets = [_words(a['title']) for a in articles]
    used = set()
    clusters = []

    for i, a in enumerate(articles):
        if i in used:
            continue
        cluster = [a]
        used.add(i)
        for j in range(i + 1, len(articles)):
            if j in used:
                continue
            # Jaccard similarity
            intersection = len(word_sets[i] & word_sets[j])
            union = len(word_sets[i] | word_sets[j])
            if union > 0 and intersection / union > 0.35:
                cluster.append(articles[j])
                used.add(j)
                if len(cluster) >= 8:
                    break
        if len(cluster) >= 2:
            # Use first article's title as cluster label
            clusters.append({
                'label': cluster[0]['title'],
                'count': len(cluster),
                'sources': list(set(c.get('source_name', '') for c in cluster)),
                'category': cluster[0].get('category', ''),
                'articles': cluster[:5],
            })

    clusters.sort(key=lambda c: c['count'], reverse=True)
    return jsonify({'clusters': clusters[:20], 'count': len(clusters)})


@situation_room_bp.route('/api/sitroom/deduction', methods=['POST'])
@validate_optional_json({
    'focus': {'type': str, 'max_length': 500},
})
def api_sitroom_deduction():
    """AI-powered situation deduction from current evidence."""
    req_data = request.get_json(silent=True) or {}
    focus = req_data.get('focus', 'global situation')

    # Gather current intelligence
    with db_session() as db:
        news = db.execute(
            "SELECT title, category, source_name FROM sitroom_news ORDER BY cached_at DESC LIMIT 30"
        ).fetchall()
        events = db.execute(
            "SELECT title, event_type, magnitude FROM sitroom_events "
            "WHERE event_type IN ('earthquake', 'conflict', 'oref_alert', 'ucdp_conflict', 'fire') "
            "ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
        markets = db.execute(
            "SELECT symbol, price, change_24h FROM sitroom_markets ORDER BY ABS(change_24h) DESC LIMIT 10"
        ).fetchall()

    context = f"Focus: {focus}\n\nRecent Headlines:\n"
    for r in news:
        d = dict(r)
        context += f"- [{d.get('category', '')}] {d['title']} ({d.get('source_name', '')})\n"
    context += "\nActive Events:\n"
    for r in events:
        d = dict(r)
        context += f"- [{d.get('event_type', '')}] {d['title']}"
        if d.get('magnitude'):
            context += f" (magnitude: {d['magnitude']})"
        context += "\n"
    context += "\nMarket Movers:\n"
    for r in markets:
        d = dict(r)
        chg = d.get('change_24h', 0)
        context += f"- {d['symbol']}: ${d.get('price', '?')} ({'+' if chg > 0 else ''}{chg:.1f}%)\n"

    try:
        from services import ollama as _ollama_svc
        prompt = (f"You are a senior intelligence analyst. Based on the following current data, "
                  f"provide a structured deduction covering:\n"
                  f"1. SITUATION ASSESSMENT — What is happening right now?\n"
                  f"2. KEY INDICATORS — What signals are most significant?\n"
                  f"3. LIKELY DEVELOPMENTS — What will probably happen in the next 24-72 hours?\n"
                  f"4. WATCH ITEMS — What should we monitor closely?\n"
                  f"5. CONFIDENCE LEVEL — How reliable is this assessment (Low/Medium/High)?\n\n"
                  f"{context}")
        result = _ollama_svc.chat(prompt, model=None, stream=False)
        if isinstance(result, dict):
            deduction = result.get('message', {}).get('content', '') or result.get('response', '')
        else:
            deduction = str(result)
    except Exception:
        # Fallback: structured summary without AI
        deduction = None

    return jsonify({
        'deduction': deduction,
        'focus': focus,
        'data_points': len(list(news)) + len(list(events)) + len(list(markets)),
        'ai_available': deduction is not None,
    })


@situation_room_bp.route('/api/sitroom/source-health')
def api_sitroom_source_health():
    """Return health status of all data sources (circuit breaker pattern)."""
    last_fetch, is_running = _get_state()
    now = datetime.now()
    sources = []
    for key, cooldown in FETCH_COOLDOWN.items():
        last = last_fetch.get(key)
        if last:
            age_sec = (now - last).total_seconds()
            status = 'live' if age_sec < cooldown * 3 else 'stale' if age_sec < cooldown * 10 else 'unavailable'
            sources.append({
                'source': key,
                'last_fetch': last.isoformat(),
                'age_seconds': int(age_sec),
                'cooldown': cooldown,
                'status': status,
            })
        else:
            sources.append({'source': key, 'last_fetch': None, 'status': 'never_fetched', 'cooldown': cooldown})

    live = sum(1 for s in sources if s['status'] == 'live')
    stale = sum(1 for s in sources if s['status'] == 'stale')
    down = sum(1 for s in sources if s['status'] in ('unavailable', 'never_fetched'))

    return jsonify({
        'sources': sources,
        'summary': {'live': live, 'stale': stale, 'unavailable': down, 'total': len(sources)},
        'is_refreshing': is_running,
    })


@situation_room_bp.route('/api/sitroom/cable-health')
def api_sitroom_cable_health():
    """Monitor undersea cable health from outage data and news."""
    with db_session() as db:
        # Check for cable-related news
        cable_news = db.execute(
            "SELECT title, link, source_name, cached_at FROM sitroom_news "
            "WHERE LOWER(title) LIKE '%undersea cable%' OR LOWER(title) LIKE '%submarine cable%' "
            "OR LOWER(title) LIKE '%internet cable%' OR LOWER(title) LIKE '%fiber optic%' "
            "OR LOWER(title) LIKE '%cable cut%' OR LOWER(title) LIKE '%cable damage%' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
        # Check internet outage data for cable-related incidents
        outages = db.execute(
            "SELECT title, detail_json FROM sitroom_events WHERE event_type = 'internet_outage' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()

    # Major cable systems and their status (based on news)
    cables = [
        {'name': 'AAE-1 (Asia-Africa-Europe)', 'route': 'Singapore-Marseille', 'status': 'operational'},
        {'name': 'SEACOM', 'route': 'Mumbai-Marseille via SA', 'status': 'operational'},
        {'name': 'FLAG Europe-Asia', 'route': 'UK-Japan', 'status': 'operational'},
        {'name': 'TAT-14', 'route': 'US-Europe (Atlantic)', 'status': 'operational'},
        {'name': 'APG', 'route': 'Japan-Singapore', 'status': 'operational'},
        {'name': 'PEACE Cable', 'route': 'Pakistan-France via Egypt', 'status': 'operational'},
        {'name': 'EASSy', 'route': 'East Africa coast', 'status': 'operational'},
        {'name': 'SAT-3/WASC', 'route': 'West Africa-Europe', 'status': 'operational'},
        {'name': 'SEA-ME-WE 6', 'route': 'Singapore-Marseille (new)', 'status': 'operational'},
        {'name': 'Google Equiano', 'route': 'Portugal-South Africa', 'status': 'operational'},
        {'name': 'META 2Africa', 'route': 'Africa circumnavigation', 'status': 'operational'},
        {'name': 'Hawaiki', 'route': 'Australia-US via NZ', 'status': 'operational'},
    ]

    # Mark any as degraded if relevant news exists
    for c in cables:
        for n in cable_news:
            if any(part.lower() in dict(n)['title'].lower() for part in c['name'].split()):
                c['status'] = 'alert'
                c['alert_title'] = dict(n)['title']

    return jsonify({
        'cables': cables,
        'related_news': [dict(r) for r in cable_news],
        'outage_count': len(list(outages)),
    })


@situation_room_bp.route('/api/sitroom/anomalies')
def api_sitroom_anomalies():
    """Detect temporal anomalies across all metrics (deviation from baseline)."""
    anomalies = []

    with db_session() as db:
        # Check for unusual earthquake activity (more than 5 M4+ in last 6h)
        quake_count = db.execute(
            "SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 4 "
            "AND cached_at > datetime('now', '-6 hours')"
        ).fetchone()[0]
        if quake_count > 5:
            anomalies.append({'type': 'seismic', 'severity': 'high',
                              'message': f'{quake_count} M4+ earthquakes in last 6 hours (baseline: 2-3)',
                              'value': quake_count, 'baseline': 3})

        # Check for unusual fire activity
        fire_count = db.execute(
            "SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'"
        ).fetchone()[0]
        if fire_count > 400:
            anomalies.append({'type': 'fire', 'severity': 'medium',
                              'message': f'{fire_count} active fires detected (baseline: 200-300)',
                              'value': fire_count, 'baseline': 250})

        # Check for market anomalies (any index >3% move)
        market_anomalies = db.execute(
            "SELECT symbol, change_24h FROM sitroom_markets WHERE ABS(change_24h) > 3 "
            "AND market_type = 'index'"
        ).fetchall()
        for m in market_anomalies:
            d = dict(m)
            anomalies.append({'type': 'market', 'severity': 'high' if abs(d['change_24h']) > 5 else 'medium',
                              'message': f"{d['symbol']} moved {d['change_24h']:+.1f}% (threshold: 3%)",
                              'value': d['change_24h'], 'baseline': 0})

        # Check stablecoin depeg
        stables = db.execute(
            "SELECT symbol, price FROM sitroom_markets WHERE market_type = 'stablecoin' AND ABS(price - 1.0) > 0.005"
        ).fetchall()
        for s in stables:
            d = dict(s)
            anomalies.append({'type': 'stablecoin', 'severity': 'high' if abs(d['price'] - 1.0) > 0.02 else 'medium',
                              'message': f"{d['symbol']} at ${d['price']:.4f} (depeg threshold: $0.005)",
                              'value': d['price'], 'baseline': 1.0})

        # Check for OREF alert surge
        oref_count = db.execute(
            "SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'oref_alert' "
            "AND cached_at > datetime('now', '-1 hours')"
        ).fetchone()[0]
        if oref_count > 10:
            anomalies.append({'type': 'oref', 'severity': 'critical',
                              'message': f'{oref_count} OREF alerts in last hour (surge detected)',
                              'value': oref_count, 'baseline': 0})

    anomalies.sort(key=lambda a: {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}.get(a['severity'], 4))
    return jsonify({'anomalies': anomalies, 'count': len(anomalies)})


@situation_room_bp.route('/api/sitroom/stock-analysis/<symbol>')
def api_sitroom_stock_analysis(symbol):
    """Return analysis data for a specific stock/index symbol."""
    # Sanitize symbol
    symbol = re.sub(r'[^A-Z0-9.=^-]', '', symbol.upper())[:20]
    if not symbol:
        return jsonify({'error': 'Invalid symbol'}), 400

    result = {'symbol': symbol}

    # Check cached market data
    with db_session() as db:
        row = db.execute("SELECT * FROM sitroom_markets WHERE UPPER(symbol) = ?", (symbol,)).fetchone()
        if row:
            result['current'] = dict(row)

        # Related news
        news = db.execute(
            "SELECT title, link, source_name FROM sitroom_news "
            "WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 10",
            (f'%{symbol.lower()}%',)
        ).fetchall()
        result['news'] = [dict(r) for r in news]

    # Try Yahoo Finance for more data
    try:
        resp = _http_session.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{symbol}',
                            params={'interval': '1d', 'range': '1mo'},
                            timeout=10, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
        if resp.ok:
            data = _safe_response_json(resp, {})
            meta = data.get('chart', {}).get('result', [{}])[0].get('meta', {})
            result['name'] = meta.get('shortName', meta.get('symbol', symbol))
            result['exchange'] = meta.get('exchangeName', '')
            result['currency'] = meta.get('currency', 'USD')
            result['prev_close'] = meta.get('chartPreviousClose', 0)
            result['regular_price'] = meta.get('regularMarketPrice', 0)
            # Get price history
            ts = data.get('chart', {}).get('result', [{}])[0]
            closes = (ts.get('indicators', {}).get('quote', [{}])[0].get('close') or [])
            result['price_history'] = [round(c, 2) if c else None for c in closes[-30:]]
    except Exception as e:
        log.debug('Yahoo Finance chart fetch for %s failed: %s', symbol, e)

    return jsonify(result)


@situation_room_bp.route('/api/sitroom/consumer-prices')
def api_sitroom_consumer_prices():
    """Return consumer price comparison data (Big Mac + fuel)."""
    result = {'bigmac': [], 'fuel': []}

    with db_session() as db:
        # Big Mac data (if cached)
        bm = db.execute(
            "SELECT title, detail_json FROM sitroom_events WHERE event_type = 'bigmac' ORDER BY title LIMIT 50"
        ).fetchall()
        for r in bm:
            d = dict(r)
            detail = _safe_json_object(d.get('detail_json'), None)
            if detail:
                result['bigmac'].append({'country': d['title'], **detail})

        # Fuel price data (if cached)
        fuel = db.execute(
            "SELECT title, detail_json FROM sitroom_events WHERE event_type = 'fuel_price' ORDER BY title LIMIT 50"
        ).fetchall()
        for r in fuel:
            d = dict(r)
            detail = _safe_json_object(d.get('detail_json'), None)
            if detail:
                result['fuel'].append({'region': d['title'], **detail})

    return jsonify(result)


@situation_room_bp.route('/api/sitroom/gulf-economies')
def api_sitroom_gulf_economies():
    """Return GCC economic indicators from cached data."""
    gcc_countries = ['saudi', 'uae', 'qatar', 'kuwait', 'bahrain', 'oman']

    with db_session() as db:
        placeholders = ' OR '.join(['LOWER(title) LIKE ?' for _ in gcc_countries])
        params = [f'%{c}%' for c in gcc_countries]
        news = db.execute(
            f"SELECT title, link, source_name, category FROM sitroom_news WHERE {placeholders} ORDER BY cached_at DESC LIMIT 30",
            params
        ).fetchall()
        # Oil-related market data
        oil = db.execute(
            "SELECT symbol, price, change_24h FROM sitroom_markets WHERE LOWER(symbol) LIKE '%oil%' OR LOWER(symbol) LIKE '%brent%'"
        ).fetchall()

    return jsonify({
        'news': [dict(r) for r in news],
        'oil_markets': [dict(r) for r in oil],
        'gcc_countries': ['Saudi Arabia', 'UAE', 'Qatar', 'Kuwait', 'Bahrain', 'Oman'],
    })


@situation_room_bp.route('/api/sitroom/enhanced-signals')
def api_sitroom_enhanced_signals():
    """Enhanced cross-source signal detection with confidence scoring."""
    with db_session() as db:
        # Get correlation data
        corr_rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'correlation' ORDER BY magnitude DESC LIMIT 20"
        ).fetchall()

        # Count data points per signal type for confidence
        signal_counts = {}
        for r in corr_rows:
            d = dict(r)
            detail = _safe_json_object(d.get('detail_json'), None)
            if not detail:
                continue
            signal_type = detail.get('signal_type', 'unknown')
            if signal_type not in signal_counts:
                signal_counts[signal_type] = 0
            signal_counts[signal_type] += 1

    signals = []
    for r in corr_rows:
        d = dict(r)
        detail = _safe_json_object(d.get('detail_json'), None)
        if not detail:
            continue
        signal_type = detail.get('signal_type', 'unknown')
        count = signal_counts.get(signal_type, 1)
        # Confidence based on number of corroborating signals
        confidence = 'high' if count >= 3 else 'medium' if count >= 2 else 'low'
        signals.append({
            'title': d['title'],
            'signal_type': signal_type,
            'strength': d.get('magnitude', 0),
            'confidence': confidence,
            'corroborating_signals': count,
            'detail': detail,
        })

    return jsonify({'signals': signals[:15], 'count': len(signals)})


@situation_room_bp.route('/api/sitroom/timeline/<country>')
def api_sitroom_country_timeline(country):
    """Return a chronological timeline of events for a specific country."""
    country_lower = country.lower()
    with db_session() as db:
        events = db.execute(
            "SELECT title, event_type, magnitude, cached_at FROM sitroom_events "
            "WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 50",
            (f'%{country_lower}%',)
        ).fetchall()
        news = db.execute(
            "SELECT title, category, source_name, cached_at FROM sitroom_news "
            "WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 50",
            (f'%{country_lower}%',)
        ).fetchall()

    timeline = []
    for r in events:
        d = dict(r)
        timeline.append({'type': 'event', 'event_type': d.get('event_type', ''),
                         'title': d['title'], 'time': d.get('cached_at', ''),
                         'magnitude': d.get('magnitude')})
    for r in news:
        d = dict(r)
        timeline.append({'type': 'news', 'category': d.get('category', ''),
                         'title': d['title'], 'time': d.get('cached_at', ''),
                         'source': d.get('source_name', '')})

    timeline.sort(key=lambda x: x.get('time', ''), reverse=True)
    return jsonify({'country': country, 'timeline': timeline[:50], 'count': len(timeline)})


@situation_room_bp.route('/api/sitroom/alert-history')
def api_sitroom_alert_history():
    """Return historical alert data for trend analysis."""
    with db_session() as db:
        # Earthquake history (last 7 days, grouped by day)
        quakes = db.execute(
            "SELECT DATE(cached_at) as day, COUNT(*) as count, MAX(magnitude) as max_mag "
            "FROM sitroom_events WHERE event_type = 'earthquake' "
            "GROUP BY DATE(cached_at) ORDER BY day DESC LIMIT 7"
        ).fetchall()
        # Fire history
        fires = db.execute(
            "SELECT DATE(cached_at) as day, COUNT(*) as count "
            "FROM sitroom_events WHERE event_type = 'fire' "
            "GROUP BY DATE(cached_at) ORDER BY day DESC LIMIT 7"
        ).fetchall()
        # News volume by category
        news_vol = db.execute(
            "SELECT category, COUNT(*) as count FROM sitroom_news "
            "WHERE cached_at > datetime('now', '-24 hours') "
            "GROUP BY category ORDER BY count DESC LIMIT 15"
        ).fetchall()

    return jsonify({
        'earthquake_history': [dict(r) for r in quakes],
        'fire_history': [dict(r) for r in fires],
        'news_volume_24h': [dict(r) for r in news_vol],
    })


@situation_room_bp.route('/api/sitroom/market-regime')
def api_sitroom_market_regime():
    """Multi-signal market regime indicator (risk-on/risk-off/neutral)."""
    signals = {}
    with db_session() as db:
        # VIX
        vix = db.execute("SELECT price FROM sitroom_markets WHERE LOWER(symbol) LIKE '%vix%' LIMIT 1").fetchone()
        if vix:
            signals['vix'] = dict(vix)['price']
        # Fear & Greed
        fg = db.execute("SELECT price FROM sitroom_markets WHERE symbol = 'FEAR_GREED' LIMIT 1").fetchone()
        if fg:
            signals['fear_greed'] = dict(fg)['price']
        # Yield spread (from FRED cache)
        spread = db.execute(
            "SELECT detail_json FROM sitroom_events WHERE event_type = 'macro_indicator' AND title LIKE '%T10Y2Y%' LIMIT 1"
        ).fetchone()
        if spread:
            detail = _safe_json_object(dict(spread).get('detail_json'), None)
            if detail:
                signals['yield_spread'] = detail.get('value', 0)
        # Market moves
        indices = db.execute(
            "SELECT symbol, change_24h FROM sitroom_markets WHERE market_type = 'index'"
        ).fetchall()
        if indices:
            avg_chg = sum(dict(r)['change_24h'] or 0 for r in indices) / len(indices)
            signals['avg_index_change'] = round(avg_chg, 2)
        # Gold (safe haven)
        gold = db.execute("SELECT change_24h FROM sitroom_markets WHERE LOWER(symbol) LIKE '%gold%' LIMIT 1").fetchone()
        if gold:
            signals['gold_change'] = dict(gold)['change_24h']

    # Compute regime
    score = 0
    if signals.get('vix', 20) > 25:
        score -= 2
    elif signals.get('vix', 20) < 15:
        score += 2
    if signals.get('fear_greed', 50) < 25:
        score -= 2
    elif signals.get('fear_greed', 50) > 75:
        score += 2
    if signals.get('avg_index_change', 0) > 1:
        score += 1
    elif signals.get('avg_index_change', 0) < -1:
        score -= 1
    if signals.get('gold_change', 0) > 1.5:
        score -= 1  # Flight to safety

    regime = 'RISK-ON' if score >= 2 else 'RISK-OFF' if score <= -2 else 'NEUTRAL'
    return jsonify({'regime': regime, 'score': score, 'signals': signals})


@situation_room_bp.route('/api/sitroom/live-counters')
def api_sitroom_live_counters():
    """Real-time positive event counters (Happy variant)."""
    now = datetime.now()
    day_of_year = now.timetuple().tm_yday
    hour = now.hour

    # Estimated daily global rates (conservative, sourced from various orgs)
    counters = {
        'trees_planted': {'label': 'Trees Planted Today', 'rate_per_day': 14_000_000,
                          'source': 'Trillion Trees Campaign estimate'},
        'vaccines_given': {'label': 'Vaccines Administered', 'rate_per_day': 30_000_000,
                           'source': 'WHO global average'},
        'babies_born': {'label': 'Babies Born Today', 'rate_per_day': 385_000,
                        'source': 'UN Population Division'},
        'clean_water_access': {'label': 'People Gaining Clean Water', 'rate_per_day': 250_000,
                               'source': 'WHO/UNICEF JMP'},
        'solar_panels': {'label': 'Solar Panels Installed', 'rate_per_day': 500_000,
                         'source': 'IEA Solar PV estimate'},
        'books_published': {'label': 'Books Published', 'rate_per_day': 7_500,
                            'source': 'UNESCO/Bowker'},
    }

    # Scale by time of day
    fraction = (hour * 3600 + now.minute * 60) / 86400
    result = {}
    for key, info in counters.items():
        est = int(info['rate_per_day'] * fraction)
        result[key] = {'label': info['label'], 'value': est, 'source': info['source']}

    return jsonify({'counters': result, 'day_of_year': day_of_year, 'fraction': round(fraction, 3)})


@situation_room_bp.route('/api/sitroom/species-tracker')
def api_sitroom_species_tracker():
    """Track species conservation wins from news and IUCN data."""
    with db_session() as db:
        # Conservation news
        news = db.execute(
            "SELECT title, link, source_name FROM sitroom_news "
            "WHERE LOWER(title) LIKE '%species%' OR LOWER(title) LIKE '%conservation%' "
            "OR LOWER(title) LIKE '%endangered%' OR LOWER(title) LIKE '%wildlife%' "
            "OR LOWER(title) LIKE '%extinction%' OR LOWER(title) LIKE '%rewilding%' "
            "OR LOWER(title) LIKE '%biodiversity%' OR LOWER(title) LIKE '%habitat%' "
            "ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()

    # Notable recent comebacks (curated)
    comebacks = [
        {'species': 'Humpback Whale', 'status': 'Recovered', 'change': 'From ~5,000 to 80,000+'},
        {'species': 'Bald Eagle', 'status': 'Recovered', 'change': 'Delisted 2007, 300K+ in US'},
        {'species': 'Giant Panda', 'status': 'Vulnerable', 'change': 'Downlisted from Endangered 2016'},
        {'species': 'Southern White Rhino', 'status': 'Near Threatened', 'change': 'From ~50 to 20,000+'},
        {'species': 'Gray Wolf', 'status': 'Recovering', 'change': 'Reintroduced across Europe/US'},
        {'species': 'Iberian Lynx', 'status': 'Vulnerable', 'change': 'From 94 to 1,600+ (2023)'},
        {'species': 'California Condor', 'status': 'Recovering', 'change': 'From 27 to 500+'},
        {'species': 'Mountain Gorilla', 'status': 'Endangered', 'change': 'From 620 to 1,000+ (2018)'},
    ]

    return jsonify({
        'comebacks': comebacks,
        'news': [dict(r) for r in news],
        'news_count': len(list(news)),
    })


@situation_room_bp.route('/api/sitroom/data-freshness')
def api_sitroom_data_freshness():
    """Return per-card data freshness status (LIVE/CACHED/UNAVAILABLE)."""
    freshness = {}
    now = datetime.now()
    last_fetch_state, _ = _get_state()

    thresholds = {
        'rss': (600, 1800), 'earthquakes': (300, 900), 'markets': (600, 1800),
        'aviation': (360, 1200), 'fires': (1200, 3600), 'radiation': (3600, 7200),
        'oref_alerts': (120, 600), 'ais_ships': (600, 1800),
    }

    for key, (live_max, cached_max) in thresholds.items():
        last = last_fetch_state.get(key)
        if last:
            age = (now - last).total_seconds()
            if age < live_max:
                freshness[key] = 'LIVE'
            elif age < cached_max:
                freshness[key] = 'CACHED'
            else:
                freshness[key] = 'STALE'
        else:
            freshness[key] = 'UNAVAILABLE'

    return jsonify({'freshness': freshness})


@situation_room_bp.route('/api/sitroom/search', methods=['POST'])
@validate_optional_json({
    'query': {'type': str, 'max_length': 200},
})
def api_sitroom_search():
    """Full-text search across all cached news and events."""
    req = request.get_json(silent=True) or {}
    query = (req.get('query', '') or '')[:200]
    if not query:
        return jsonify({'results': [], 'count': 0})

    terms = [f'%{t.strip().lower()}%' for t in query.split() if t.strip()]
    if not terms:
        return jsonify({'results': [], 'count': 0})

    with db_session() as db:
        # Search news
        conditions = ' AND '.join(['LOWER(title) LIKE ?' for _ in terms])
        news = db.execute(
            f"SELECT title, link, source_name, category, 'news' as result_type FROM sitroom_news "
            f"WHERE {conditions} ORDER BY cached_at DESC LIMIT 20", terms
        ).fetchall()
        # Search events
        events = db.execute(
            f"SELECT title, source_url as link, event_type as source_name, event_type as category, "
            f"'event' as result_type FROM sitroom_events "
            f"WHERE {conditions} ORDER BY cached_at DESC LIMIT 20", terms
        ).fetchall()

    results = [dict(r) for r in news] + [dict(r) for r in events]
    results.sort(key=lambda x: x.get('title', ''))
    return jsonify({'results': results[:30], 'count': len(results), 'query': query})


# ─── Batch: Additional API Routes to close WM gap ─────────────────────

@situation_room_bp.route('/api/sitroom/news-by-source')
def api_sitroom_news_by_source():
    """Return news grouped by source."""
    with db_session() as db:
        rows = db.execute(
            "SELECT source_name, COUNT(*) as count FROM sitroom_news "
            "GROUP BY source_name ORDER BY count DESC LIMIT 30"
        ).fetchall()
    return jsonify({'sources': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/news-by-hour')
def api_sitroom_news_by_hour():
    """Return news volume by hour for last 24h."""
    with db_session() as db:
        rows = db.execute(
            "SELECT strftime('%H', cached_at) as hour, COUNT(*) as count FROM sitroom_news "
            "WHERE cached_at > datetime('now', '-24 hours') GROUP BY hour ORDER BY hour"
        ).fetchall()
    return jsonify({'hours': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/top-entities')
def api_sitroom_top_entities():
    """Extract top mentioned entities (countries/orgs) from recent news."""
    entity_counts = {}
    with db_session() as db:
        rows = db.execute("SELECT title FROM sitroom_news ORDER BY cached_at DESC LIMIT 300").fetchall()

    for r in rows:
        title = dict(r)['title']
        for country, _ in _COUNTRY_COORDS.items():
            if country in title.lower():
                entity_counts[country.title()] = entity_counts.get(country.title(), 0) + 1

    sorted_entities = sorted(entity_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    return jsonify({'entities': [{'name': k, 'count': v} for k, v in sorted_entities]})


@situation_room_bp.route('/api/sitroom/category-summary')
def api_sitroom_category_summary():
    """Return article count by category."""
    with db_session() as db:
        rows = db.execute(
            "SELECT category, COUNT(*) as count FROM sitroom_news GROUP BY category ORDER BY count DESC"
        ).fetchall()
    return jsonify({'categories': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/event-summary')
def api_sitroom_event_summary():
    """Return event counts by type."""
    with db_session() as db:
        rows = db.execute(
            "SELECT event_type, COUNT(*) as count FROM sitroom_events GROUP BY event_type ORDER BY count DESC"
        ).fetchall()
    return jsonify({'event_types': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/market-movers')
def api_sitroom_market_movers():
    """Return top market movers (biggest absolute changes)."""
    with db_session() as db:
        rows = db.execute(
            "SELECT symbol, price, change_24h, market_type FROM sitroom_markets "
            "ORDER BY ABS(change_24h) DESC LIMIT 15"
        ).fetchall()
    return jsonify({'movers': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/crypto-overview')
def api_sitroom_crypto_overview():
    """Return crypto market overview with dominance and volume."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_markets WHERE market_type = 'crypto' ORDER BY price DESC"
        ).fetchall()
    coins = [dict(r) for r in rows]
    total_cap = sum(c.get('price', 0) for c in coins)  # simplified
    return jsonify({'coins': coins, 'count': len(coins)})


@situation_room_bp.route('/api/sitroom/forex-matrix')
def api_sitroom_forex_matrix():
    """Return forex currency pairs with changes."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_markets WHERE market_type = 'forex' ORDER BY symbol"
        ).fetchall()
    return jsonify({'pairs': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/commodity-overview')
def api_sitroom_commodity_overview():
    """Return commodity prices overview."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_markets WHERE market_type = 'commodity' ORDER BY symbol"
        ).fetchall()
    return jsonify({'commodities': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/sector-performance')
def api_sitroom_sector_performance():
    """Return sector ETF performance ranked."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_markets WHERE market_type = 'sector' ORDER BY change_24h DESC"
        ).fetchall()
    return jsonify({'sectors': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/recent-earthquakes')
def api_sitroom_recent_earthquakes():
    """Return recent earthquakes with filtering."""
    min_mag = request.args.get('min_mag', 0, type=float)
    limit = _get_query_int(request, 'limit', 50, minimum=1, maximum=200)
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= ? "
            "ORDER BY magnitude DESC LIMIT ?", (min_mag, limit)
        ).fetchall()
    return jsonify({'earthquakes': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/weather-alerts')
def api_sitroom_weather_alerts():
    """Return active weather alerts."""
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'weather_alert' ORDER BY cached_at DESC LIMIT 30"
        ).fetchall()
    return jsonify({'alerts': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/conflict-map')
def api_sitroom_conflict_map():
    """Return all conflict events with coordinates for map overlay."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, lat, lng, magnitude, event_type, detail_json FROM sitroom_events "
            "WHERE event_type IN ('conflict', 'ucdp_conflict', 'oref_alert') AND lat != 0 "
            "ORDER BY cached_at DESC LIMIT 100"
        ).fetchall()
    return jsonify({'conflicts': [dict(r) for r in rows], 'count': len(rows)})


@situation_room_bp.route('/api/sitroom/export-csv')
def api_sitroom_export_csv():
    """Export cached news as CSV."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, category, source_name, published, link FROM sitroom_news ORDER BY cached_at DESC LIMIT 500"
        ).fetchall()
    lines = ['title,category,source,published,link']
    for r in rows:
        d = dict(r)
        line = ','.join(f'"{(d.get(k, "") or "").replace(chr(34), chr(34)+chr(34))}"'
                        for k in ['title', 'category', 'source_name', 'published', 'link'])
        lines.append(line)
    from flask import Response
    return Response('\n'.join(lines), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=sitroom_news.csv'})


@situation_room_bp.route('/api/sitroom/export-json')
def api_sitroom_export_json():
    """Export all cached data as JSON bundle."""
    with db_session() as db:
        news = db.execute("SELECT title, category, source_name, published, link FROM sitroom_news ORDER BY cached_at DESC LIMIT 200").fetchall()
        events = db.execute("SELECT title, event_type, magnitude, lat, lng FROM sitroom_events ORDER BY cached_at DESC LIMIT 200").fetchall()
        markets = db.execute("SELECT symbol, price, change_24h, market_type FROM sitroom_markets").fetchall()
    return jsonify({
        'exported_at': datetime.now().isoformat(),
        'news': [dict(r) for r in news],
        'events': [dict(r) for r in events],
        'markets': [dict(r) for r in markets],
    })


@situation_room_bp.route('/api/sitroom/gps-jamming')
def api_sitroom_gps_jamming():
    """Return GPS jamming zone data with any related news."""
    with db_session() as db:
        news = db.execute(
            "SELECT title, link, source_name FROM sitroom_news "
            "WHERE LOWER(title) LIKE '%gps%' OR LOWER(title) LIKE '%jamming%' "
            "OR LOWER(title) LIKE '%spoofing%' OR LOWER(title) LIKE '%navigation%interference%' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
    zones = [
        {'region': 'Eastern Mediterranean', 'severity': 'high', 'lat': 34.7, 'lng': 33.0},
        {'region': 'Moscow/Kremlin', 'severity': 'high', 'lat': 55.75, 'lng': 37.62},
        {'region': 'Kaliningrad', 'severity': 'high', 'lat': 54.7, 'lng': 20.5},
        {'region': 'Northern Israel/Golan', 'severity': 'high', 'lat': 32.9, 'lng': 35.3},
        {'region': 'Persian Gulf', 'severity': 'medium', 'lat': 26.2, 'lng': 50.5},
        {'region': 'Crimea/Black Sea', 'severity': 'high', 'lat': 44.6, 'lng': 33.5},
        {'region': 'North Korea border', 'severity': 'medium', 'lat': 37.9, 'lng': 126.5},
        {'region': 'South China Sea', 'severity': 'low', 'lat': 15.0, 'lng': 114.0},
    ]
    return jsonify({'zones': zones, 'news': [dict(r) for r in news]})


@situation_room_bp.route('/api/sitroom/intel-digest')
def api_sitroom_intel_digest():
    """Compile a structured intelligence digest from all sources."""
    with db_session() as db:
        news_count = db.execute("SELECT COUNT(*) FROM sitroom_news").fetchone()[0]
        event_count = db.execute("SELECT COUNT(*) FROM sitroom_events").fetchone()[0]
        top_cats = db.execute(
            "SELECT category, COUNT(*) as c FROM sitroom_news GROUP BY category ORDER BY c DESC LIMIT 5"
        ).fetchall()
        top_events = db.execute(
            "SELECT event_type, COUNT(*) as c FROM sitroom_events GROUP BY event_type ORDER BY c DESC LIMIT 5"
        ).fetchall()
        breaking = db.execute(
            "SELECT title FROM sitroom_news WHERE LOWER(title) LIKE '%breaking%' ORDER BY cached_at DESC LIMIT 3"
        ).fetchall()

    return jsonify({
        'total_articles': news_count,
        'total_events': event_count,
        'top_categories': [dict(r) for r in top_cats],
        'top_event_types': [dict(r) for r in top_events],
        'breaking': [dict(r)['title'] for r in breaking],
        'generated_at': datetime.now().isoformat(),
    })


@situation_room_bp.route('/api/sitroom/watchlist', methods=['GET', 'POST', 'DELETE'])
@validate_optional_json({
    'keyword': {'type': str, 'max_length': 100},
})
def api_sitroom_watchlist():
    """Manage a keyword watchlist for personalized alerts."""
    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_watchlist
            (id INTEGER PRIMARY KEY, keyword TEXT UNIQUE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')

        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            kw = (data.get('keyword', '') or '')[:100].strip()
            if kw:
                db.execute('INSERT OR IGNORE INTO sitroom_watchlist (keyword) VALUES (?)', (kw,))
                db.commit()
            return jsonify({'added': kw})

        if request.method == 'DELETE':
            data = request.get_json(silent=True) or {}
            kw = data.get('keyword', '')
            if kw:
                r = db.execute('DELETE FROM sitroom_watchlist WHERE keyword = ?', (kw,))
                if r.rowcount == 0:
                    return jsonify({'error': 'not found'}), 404
                db.commit()
            return jsonify({'deleted': kw})

        # GET — return watchlist with match counts
        rows = db.execute('SELECT keyword FROM sitroom_watchlist ORDER BY created_at DESC').fetchall()
        watchlist = []
        for r in rows:
            kw = dict(r)['keyword']
            count = db.execute(
                "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE ?",
                (f'%{kw.lower()}%',)
            ).fetchone()[0]
            watchlist.append({'keyword': kw, 'matches': count})
        return jsonify({'watchlist': watchlist})


@situation_room_bp.route('/api/sitroom/heatmap-data')
def api_sitroom_heatmap_data():
    """Return event density data for heatmap visualization."""
    with db_session() as db:
        rows = db.execute(
            "SELECT lat, lng, event_type, magnitude FROM sitroom_events "
            "WHERE lat != 0 AND lng != 0 ORDER BY cached_at DESC LIMIT 500"
        ).fetchall()
    points = []
    for r in rows:
        d = dict(r)
        weight = max(1, (d.get('magnitude') or 1))
        points.append({'lat': d['lat'], 'lng': d['lng'], 'weight': weight, 'type': d.get('event_type', '')})
    return jsonify({'points': points, 'count': len(points)})


@situation_room_bp.route('/api/sitroom/sentiment-timeline')
def api_sitroom_sentiment_timeline():
    """Return news sentiment over time (positive/negative keyword ratio)."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, strftime('%Y-%m-%d %H:00', cached_at) as hour FROM sitroom_news "
            "WHERE cached_at > datetime('now', '-48 hours') ORDER BY cached_at"
        ).fetchall()
    positive = ['peace', 'agreement', 'growth', 'recovery', 'ceasefire', 'breakthrough', 'deal', 'progress']
    negative = ['attack', 'killed', 'war', 'crisis', 'crash', 'explosion', 'collapse', 'sanctions']
    timeline = {}
    for r in rows:
        d = dict(r)
        hour = d['hour']
        if hour not in timeline:
            timeline[hour] = {'pos': 0, 'neg': 0, 'total': 0}
        title_l = d['title'].lower()
        timeline[hour]['total'] += 1
        if any(w in title_l for w in positive):
            timeline[hour]['pos'] += 1
        if any(w in title_l for w in negative):
            timeline[hour]['neg'] += 1
    return jsonify({'timeline': [{'hour': k, **v} for k, v in sorted(timeline.items())]})


@situation_room_bp.route('/api/sitroom/threat-level')
def api_sitroom_threat_level():
    """Compute composite global threat level (1-5)."""
    score = 0
    with db_session() as db:
        # Active conflicts
        conflicts = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type IN ('conflict', 'ucdp_conflict', 'oref_alert')").fetchone()[0]
        if conflicts > 20:
            score += 2
        elif conflicts > 10:
            score += 1
        # Large earthquakes
        big_quakes = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 6").fetchone()[0]
        if big_quakes > 0:
            score += 1
        # Market stress
        vix = db.execute("SELECT price FROM sitroom_markets WHERE LOWER(symbol) LIKE '%vix%' LIMIT 1").fetchone()
        if vix and dict(vix)['price'] > 30:
            score += 1
        # Active fires
        fires = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'").fetchone()[0]
        if fires > 400:
            score += 1
    level = min(5, max(1, score))
    labels = {1: 'LOW', 2: 'GUARDED', 3: 'ELEVATED', 4: 'HIGH', 5: 'SEVERE'}
    return jsonify({'level': level, 'label': labels[level], 'score': score})


@situation_room_bp.route('/api/sitroom/region-overview/<region>')
def api_sitroom_region_overview(region):
    """Return intelligence overview for a geographic region."""
    region_countries = {
        'middle-east': ['israel', 'iran', 'iraq', 'syria', 'yemen', 'lebanon', 'jordan', 'saudi', 'uae', 'qatar', 'kuwait', 'bahrain', 'oman'],
        'europe': ['ukraine', 'russia', 'germany', 'france', 'uk', 'poland', 'romania', 'turkey', 'greece', 'italy', 'spain'],
        'asia-pacific': ['china', 'taiwan', 'japan', 'korea', 'india', 'pakistan', 'myanmar', 'philippines', 'indonesia', 'vietnam', 'thailand'],
        'africa': ['nigeria', 'sudan', 'ethiopia', 'kenya', 'congo', 'south africa', 'somalia', 'mali', 'libya', 'egypt', 'morocco'],
        'americas': ['united states', 'mexico', 'brazil', 'colombia', 'venezuela', 'argentina', 'chile', 'cuba', 'haiti', 'canada'],
    }
    countries = region_countries.get(region.lower(), [])
    if not countries:
        return jsonify({'error': 'Unknown region', 'valid': list(region_countries.keys())}), 400

    placeholders = ' OR '.join(['LOWER(title) LIKE ?' for _ in countries])
    params = [f'%{c}%' for c in countries]
    with db_session() as db:
        news = db.execute(f"SELECT title, category, source_name FROM sitroom_news WHERE {placeholders} ORDER BY cached_at DESC LIMIT 30", params).fetchall()
        events = db.execute(f"SELECT title, event_type, magnitude FROM sitroom_events WHERE {placeholders} ORDER BY cached_at DESC LIMIT 20", params).fetchall()
    return jsonify({
        'region': region, 'countries': countries,
        'news': [dict(r) for r in news], 'events': [dict(r) for r in events],
        'news_count': len(list(news)), 'event_count': len(list(events)),
    })


@situation_room_bp.route('/api/sitroom/daily-summary')
def api_sitroom_daily_summary():
    """Return a structured daily intelligence summary."""
    with db_session() as db:
        total_news = db.execute("SELECT COUNT(*) FROM sitroom_news WHERE cached_at > datetime('now', '-24 hours')").fetchone()[0]
        total_events = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE cached_at > datetime('now', '-24 hours')").fetchone()[0]
        top_stories = db.execute("SELECT title, category, source_name FROM sitroom_news ORDER BY cached_at DESC LIMIT 5").fetchall()
        major_events = db.execute(
            "SELECT title, event_type, magnitude FROM sitroom_events WHERE magnitude IS NOT NULL "
            "ORDER BY magnitude DESC LIMIT 5"
        ).fetchall()
        market_summary = db.execute(
            "SELECT symbol, price, change_24h FROM sitroom_markets WHERE market_type = 'index'"
        ).fetchall()
    return jsonify({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'articles_24h': total_news,
        'events_24h': total_events,
        'top_stories': [dict(r) for r in top_stories],
        'major_events': [dict(r) for r in major_events],
        'market_indices': [dict(r) for r in market_summary],
    })


@situation_room_bp.route('/api/sitroom/compare-markets')
def api_sitroom_compare_markets():
    """Compare performance across all market types."""
    with db_session() as db:
        rows = db.execute(
            "SELECT market_type, AVG(change_24h) as avg_change, COUNT(*) as count, "
            "MIN(change_24h) as worst, MAX(change_24h) as best "
            "FROM sitroom_markets GROUP BY market_type"
        ).fetchall()
    return jsonify({'comparison': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/hot-topics')
def api_sitroom_hot_topics():
    """Identify hot topics by counting keyword frequency across recent headlines."""
    from collections import Counter
    stopwords = {'the','a','an','in','on','at','to','for','of','and','is','are','was','were',
                 'has','have','had','be','been','will','with','from','by','as','that','this',
                 'it','not','but','or','if','all','no','its','their','than','they','he','she',
                 'we','our','my','new','over','after','into','up','out','about','more','says',
                 'could','would','may','also','us','how','what','who','which','can','do','said'}
    with db_session() as db:
        rows = db.execute("SELECT title FROM sitroom_news WHERE cached_at > datetime('now', '-12 hours')").fetchall()
    words = Counter()
    for r in rows:
        tokens = re.sub(r'[^\w\s]', '', dict(r)['title'].lower()).split()
        for t in tokens:
            if len(t) > 2 and t not in stopwords:
                words[t] += 1
    top = words.most_common(30)
    return jsonify({'topics': [{'word': w, 'count': c} for w, c in top]})


@situation_room_bp.route('/api/sitroom/feed-stats')
def api_sitroom_feed_stats():
    """Return detailed feed statistics."""
    with db_session() as db:
        total = db.execute("SELECT COUNT(*) FROM sitroom_news").fetchone()[0]
        by_type = db.execute(
            "SELECT source_type, COUNT(*) as c FROM sitroom_news GROUP BY source_type ORDER BY c DESC"
        ).fetchall()
        oldest = db.execute("SELECT MIN(cached_at) FROM sitroom_news").fetchone()[0]
        newest = db.execute("SELECT MAX(cached_at) FROM sitroom_news").fetchone()[0]
        custom = db.execute("SELECT COUNT(*) FROM sitroom_custom_feeds").fetchone()[0]
    return jsonify({
        'total_articles': total,
        'by_source_type': [dict(r) for r in by_type],
        'oldest_article': oldest,
        'newest_article': newest,
        'custom_feeds': custom,
    })


@situation_room_bp.route('/api/sitroom/map-stats')
def api_sitroom_map_stats():
    """Return statistics about map data layers."""
    with db_session() as db:
        event_counts = db.execute(
            "SELECT event_type, COUNT(*) as c FROM sitroom_events WHERE lat != 0 AND lng != 0 "
            "GROUP BY event_type ORDER BY c DESC"
        ).fetchall()
    # Static layer counts
    static_layers = {
        'military_bases': 149, 'nuclear_sites': 106, 'data_centers': 129,
        'pipelines': 98, 'cables': 54, 'shipping': 44, 'airports': 62,
        'financial_centers': 30, 'mining': 40, 'tech_hqs': 20,
        'waterways': 26, 'spaceports': 26, 'cloud_regions': 63,
        'stock_exchanges': 51, 'commodity_hubs': 37, 'startup_hubs': 32,
        'gps_jamming': 26, 'trade_routes': 24, 'accelerators': 26,
        'refugee_camps': 20, 'un_missions': 16, 'internet_exchanges': 28,
        'embassies': 14, 'desalination': 18, 'weather_stations': 20,
        'space_tracking': 16, 'rare_earths': 12,
    }
    return jsonify({
        'live_events': [dict(r) for r in event_counts],
        'static_layers': static_layers,
        'total_static': sum(static_layers.values()),
    })


@situation_room_bp.route('/api/sitroom/risk-radar')
def api_sitroom_risk_radar():
    """Multi-dimensional risk assessment across 6 domains."""
    with db_session() as db:
        geo = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type IN ('conflict','ucdp_conflict','oref_alert')").fetchone()[0]
        eco = db.execute("SELECT COUNT(*) FROM sitroom_markets WHERE ABS(change_24h) > 2").fetchone()[0]
        cyber = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'cyber_threat'").fetchone()[0]
        env = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type IN ('earthquake','fire','volcano') AND (magnitude IS NULL OR magnitude >= 4)").fetchone()[0]
        health = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'disease'").fetchone()[0]
        space_val = db.execute("SELECT value_json FROM sitroom_space_weather WHERE data_type = 'kp_index' LIMIT 1").fetchone()

    space_risk = 0
    if space_val:
        payload = _safe_json_object(dict(space_val).get('value_json'), None)
        if payload:
            try:
                kp = payload.get('latest', [None, None, None, None, '0'])
                space_risk = min(10, int(float(kp[4] if len(kp) > 4 else 0)))
            except Exception as e:
                log.debug('Failed to parse KP index for risk radar: %s', e)

    def _scale(val, low, high):
        return min(10, max(0, int((val - low) / max(1, high - low) * 10)))

    return jsonify({
        'domains': {
            'geopolitical': {'score': _scale(geo, 0, 30), 'events': geo},
            'economic': {'score': _scale(eco, 0, 15), 'volatiles': eco},
            'cyber': {'score': _scale(cyber, 0, 10), 'threats': cyber},
            'environmental': {'score': _scale(env, 0, 20), 'events': env},
            'health': {'score': _scale(health, 0, 10), 'outbreaks': health},
            'space_weather': {'score': space_risk, 'kp': space_risk},
        }
    })


@situation_room_bp.route('/api/sitroom/version')
def api_sitroom_version():
    """Return Situation Room version and capabilities."""
    return jsonify({
        'version': '6.18',
        'api_routes': 126,
        'map_layers': 40,
        'static_points': 1187,
        'data_sources': 36,
        'fetch_workers': 34,
        'telegram_channels': 43,
        'ui_cards': 102,
        'features': ['smart_polling', 'notification_sounds', 'data_freshness',
                      'news_clustering', 'ai_deduction', 'breaking_detection',
                      'country_briefs', 'watchlist', 'export_csv_json',
                      'full_text_search', 'anomaly_detection', 'circuit_breaker'],
    })


@situation_room_bp.route('/api/sitroom/correlation-matrix')
def api_sitroom_correlation_matrix():
    """Return cross-signal correlation strength between domains."""
    domains = ['geopolitical', 'economic', 'cyber', 'energy', 'climate', 'health']
    matrix = {}
    with db_session() as db:
        corr = db.execute(
            "SELECT title, detail_json FROM sitroom_events WHERE event_type = 'correlation' ORDER BY magnitude DESC LIMIT 30"
        ).fetchall()
    for r in corr:
        d = dict(r)
        detail = _safe_json_object(d.get('detail_json'), None)
        if not detail:
            continue
        st = detail.get('signal_type', '')
        for dom in domains:
            if dom in st.lower() or dom in d['title'].lower():
                matrix[dom] = matrix.get(dom, 0) + 1
    return jsonify({'matrix': matrix, 'domains': domains})


@situation_room_bp.route('/api/sitroom/infrastructure-risk')
def api_sitroom_infrastructure_risk():
    """Assess critical infrastructure risk from events + news."""
    risks = {}
    with db_session() as db:
        # Energy
        energy_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%pipeline%' OR LOWER(title) LIKE '%power grid%' OR LOWER(title) LIKE '%blackout%' OR LOWER(title) LIKE '%refinery%'"
        ).fetchone()[0]
        risks['energy'] = {'news_count': energy_news, 'risk': 'elevated' if energy_news > 5 else 'normal'}
        # Telecom
        telecom = db.execute(
            "SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'internet_outage'"
        ).fetchone()[0]
        risks['telecom'] = {'outages': telecom, 'risk': 'elevated' if telecom > 3 else 'normal'}
        # Transport
        transport = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%port%closure%' OR LOWER(title) LIKE '%airport%shut%' OR LOWER(title) LIKE '%shipping%disrupt%'"
        ).fetchone()[0]
        risks['transport'] = {'disruptions': transport, 'risk': 'elevated' if transport > 2 else 'normal'}
        # Water
        water = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%water%crisis%' OR LOWER(title) LIKE '%drought%' OR LOWER(title) LIKE '%flood%'"
        ).fetchone()[0]
        risks['water'] = {'events': water, 'risk': 'elevated' if water > 3 else 'normal'}
    return jsonify({'infrastructure': risks})


@situation_room_bp.route('/api/sitroom/supply-chain-risk')
def api_sitroom_supply_chain_risk():
    """Assess global supply chain disruption risk."""
    with db_session() as db:
        chokepoint_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%suez%' OR LOWER(title) LIKE '%panama canal%' OR LOWER(title) LIKE '%hormuz%' OR LOWER(title) LIKE '%malacca%' OR LOWER(title) LIKE '%bab el%'"
        ).fetchone()[0]
        shipping_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%shipping%' OR LOWER(title) LIKE '%container%' OR LOWER(title) LIKE '%freight%' OR LOWER(title) LIKE '%supply chain%'"
        ).fetchone()[0]
        semiconductor_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%chip%shortage%' OR LOWER(title) LIKE '%semiconductor%' OR LOWER(title) LIKE '%tsmc%'"
        ).fetchone()[0]
    risk_score = min(10, chokepoint_news + shipping_news // 3 + semiconductor_news)
    return jsonify({
        'risk_score': risk_score,
        'chokepoint_mentions': chokepoint_news,
        'shipping_mentions': shipping_news,
        'semiconductor_mentions': semiconductor_news,
        'level': 'critical' if risk_score > 7 else 'elevated' if risk_score > 4 else 'normal',
    })


@situation_room_bp.route('/api/sitroom/ai-models')
def api_sitroom_ai_models():
    """Check which AI models are available for Situation Room features."""
    models = []
    try:
        from services import ollama as _ollama_svc
        model_list = _ollama_svc.list_models()
        models = [m.get('name', m.get('model', '')) for m in (model_list if isinstance(model_list, list) else [])]
    except Exception as e:
        log.debug('Failed to list Ollama models for sitroom: %s', e)
    ai_features = {
        'strategic_briefing': bool(models),
        'country_brief': bool(models),
        'deduction_panel': bool(models),
        'market_brief': bool(models),
    }
    return jsonify({'models': models, 'features': ai_features})


@situation_room_bp.route('/api/sitroom/events-geojson')
def api_sitroom_events_geojson():
    """Return all geocoded events as GeoJSON FeatureCollection."""
    with db_session() as db:
        rows = db.execute(
            "SELECT title, event_type, magnitude, lat, lng, cached_at FROM sitroom_events "
            "WHERE lat != 0 AND lng != 0 ORDER BY cached_at DESC LIMIT 500"
        ).fetchall()
    features = []
    for r in rows:
        d = dict(r)
        features.append({
            'type': 'Feature',
            'geometry': {'type': 'Point', 'coordinates': [d['lng'], d['lat']]},
            'properties': {
                'title': d['title'], 'event_type': d.get('event_type', ''),
                'magnitude': d.get('magnitude'), 'time': d.get('cached_at', ''),
            }
        })
    return jsonify({'type': 'FeatureCollection', 'features': features})


@situation_room_bp.route('/api/sitroom/nuclear-risk')
def api_sitroom_nuclear_risk():
    """Assess nuclear threat level from news + OREF + conflict data."""
    with db_session() as db:
        nuke_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%nuclear%' OR LOWER(title) LIKE '%atomic%' "
            "OR LOWER(title) LIKE '%warhead%' OR LOWER(title) LIKE '%icbm%' OR LOWER(title) LIKE '%enrichment%'"
        ).fetchone()[0]
        missile_events = db.execute(
            "SELECT COUNT(*) FROM sitroom_events WHERE LOWER(title) LIKE '%missile%' OR LOWER(title) LIKE '%ballistic%'"
        ).fetchone()[0]
        headlines = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%nuclear%' ORDER BY cached_at DESC LIMIT 5"
        ).fetchall()
    risk = min(5, nuke_news // 3 + missile_events)
    labels = {0: 'NOMINAL', 1: 'LOW', 2: 'GUARDED', 3: 'ELEVATED', 4: 'HIGH', 5: 'CRITICAL'}
    return jsonify({
        'risk_level': risk, 'label': labels.get(risk, 'UNKNOWN'),
        'nuclear_mentions': nuke_news, 'missile_events': missile_events,
        'headlines': [dict(r) for r in headlines],
    })


@situation_room_bp.route('/api/sitroom/energy-security')
def api_sitroom_energy_security():
    """Energy security assessment — oil, gas, renewable mix."""
    with db_session() as db:
        oil = db.execute("SELECT price, change_24h FROM sitroom_markets WHERE LOWER(symbol) LIKE '%brent%' OR LOWER(symbol) LIKE '%oil%' LIMIT 2").fetchall()
        energy_news = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%energy%' "
            "OR LOWER(title) LIKE '%oil%price%' OR LOWER(title) LIKE '%opec%' "
            "OR LOWER(title) LIKE '%natural gas%' OR LOWER(title) LIKE '%lng%' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
        renewable_news = db.execute(
            "SELECT title FROM sitroom_news WHERE category = 'Renewable Energy' ORDER BY cached_at DESC LIMIT 5"
        ).fetchall()
    return jsonify({
        'oil_prices': [dict(r) for r in oil],
        'energy_news': [dict(r) for r in energy_news],
        'renewable_news': [dict(r) for r in renewable_news],
    })


@situation_room_bp.route('/api/sitroom/pandemic-watch')
def api_sitroom_pandemic_watch():
    """Pandemic early warning — disease outbreaks + WHO data."""
    with db_session() as db:
        outbreaks = db.execute(
            "SELECT title, lat, lng, detail_json FROM sitroom_events WHERE event_type = 'disease' ORDER BY cached_at DESC LIMIT 20"
        ).fetchall()
        health_news = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%pandemic%' "
            "OR LOWER(title) LIKE '%outbreak%' OR LOWER(title) LIKE '%epidemic%' "
            "OR LOWER(title) LIKE '%virus%' OR LOWER(title) LIKE '%who %' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
    # Count unique countries affected
    countries = set()
    for r in outbreaks:
        title = dict(r)['title'].lower()
        for country in _COUNTRY_COORDS:
            if country in title:
                countries.add(country)
    return jsonify({
        'outbreaks': [dict(r) for r in outbreaks],
        'health_news': [dict(r) for r in health_news],
        'countries_affected': len(countries),
        'alert_level': 'elevated' if len(countries) > 5 else 'normal',
    })


@situation_room_bp.route('/api/sitroom/migration-flows')
def api_sitroom_migration_flows():
    """Migration and displacement flow analysis."""
    with db_session() as db:
        displacement = db.execute(
            "SELECT title, magnitude, detail_json FROM sitroom_events WHERE event_type = 'displacement' ORDER BY magnitude DESC LIMIT 20"
        ).fetchall()
        refugee_news = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%refugee%' "
            "OR LOWER(title) LIKE '%migrant%' OR LOWER(title) LIKE '%asylum%' "
            "OR LOWER(title) LIKE '%displacement%' OR LOWER(title) LIKE '%border%crisis%' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
    total_displaced = sum(dict(r).get('magnitude', 0) or 0 for r in displacement)
    return jsonify({
        'displacement_data': [dict(r) for r in displacement],
        'news': [dict(r) for r in refugee_news],
        'total_displaced': total_displaced,
    })


@situation_room_bp.route('/api/sitroom/space-situational')
def api_sitroom_space_situational():
    """Space situational awareness — debris, launches, weather."""
    with db_session() as db:
        space_wx = db.execute("SELECT * FROM sitroom_space_weather").fetchall()
        space_news = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE category = 'Space' ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
        launches = db.execute(
            "SELECT title FROM sitroom_news WHERE LOWER(title) LIKE '%launch%' AND "
            "(LOWER(title) LIKE '%rocket%' OR LOWER(title) LIKE '%spacex%' OR LOWER(title) LIKE '%satellite%') "
            "ORDER BY cached_at DESC LIMIT 5"
        ).fetchall()
    wx_data = {}
    for r in space_wx:
        parsed = _safe_json_value(dict(r).get('value_json'), None)
        if parsed is not None:
            wx_data[dict(r)['data_type']] = parsed
    return jsonify({
        'space_weather': wx_data,
        'space_news': [dict(r) for r in space_news],
        'recent_launches': [dict(r)['title'] for r in launches],
    })


# ─── P6/P7: Advanced Features ──────────────────────────────────────────

@situation_room_bp.route('/api/sitroom/apt-groups')
def api_sitroom_apt_groups():
    """Return known Advanced Persistent Threat group profiles."""
    apt_groups = [
        {'name': 'APT28 (Fancy Bear)', 'origin': 'Russia/GRU', 'targets': 'NATO, elections, defense',
         'notable': 'DNC hack 2016, Bundestag breach', 'active': True},
        {'name': 'APT29 (Cozy Bear)', 'origin': 'Russia/SVR', 'targets': 'Government, think tanks',
         'notable': 'SolarWinds supply chain attack', 'active': True},
        {'name': 'APT41 (Double Dragon)', 'origin': 'China/MSS', 'targets': 'Healthcare, telecom, gaming',
         'notable': 'Dual espionage + financial crime', 'active': True},
        {'name': 'Lazarus Group', 'origin': 'North Korea/RGB', 'targets': 'Finance, crypto, defense',
         'notable': 'Sony hack, WannaCry, $625M Ronin theft', 'active': True},
        {'name': 'APT33 (Elfin)', 'origin': 'Iran/IRGC', 'targets': 'Aviation, energy, petrochemical',
         'notable': 'Shamoon wiper attacks', 'active': True},
        {'name': 'Sandworm (Voodoo Bear)', 'origin': 'Russia/GRU Unit 74455', 'targets': 'Critical infrastructure',
         'notable': 'NotPetya, Ukraine grid attacks', 'active': True},
        {'name': 'APT1 (Comment Crew)', 'origin': 'China/PLA Unit 61398', 'targets': 'US defense, IP theft',
         'notable': 'Mandiant 2013 report, 141+ targets', 'active': False},
        {'name': 'Equation Group', 'origin': 'USA/NSA TAO', 'targets': 'Nation-state targets globally',
         'notable': 'Stuxnet co-developer, Shadow Brokers leak', 'active': True},
        {'name': 'Turla (Snake)', 'origin': 'Russia/FSB Center 16', 'targets': 'Government, military, embassies',
         'notable': 'Agent.BTZ, satellite C2', 'active': True},
        {'name': 'Charming Kitten (APT35)', 'origin': 'Iran/IRGC', 'targets': 'Journalists, academics, dissidents',
         'notable': 'Credential harvesting, social engineering', 'active': True},
        {'name': 'Hafnium', 'origin': 'China/MSS', 'targets': 'US organizations via Exchange',
         'notable': 'ProxyLogon zero-day campaign', 'active': True},
        {'name': 'DarkSide/BlackMatter', 'origin': 'Russia (criminal)', 'targets': 'Critical infrastructure',
         'notable': 'Colonial Pipeline ransomware', 'active': False},
        {'name': 'REvil/Sodinokibi', 'origin': 'Russia (criminal)', 'targets': 'Enterprise ransomware',
         'notable': 'Kaseya, JBS Foods attacks', 'active': False},
        {'name': 'Mustang Panda', 'origin': 'China', 'targets': 'Southeast Asia, Europe, Mongolia',
         'notable': 'PlugX malware, COVID-19 lures', 'active': True},
        {'name': 'Kimsuky', 'origin': 'North Korea/RGB', 'targets': 'South Korea, US, Japan think tanks',
         'notable': 'Nuclear/defense espionage', 'active': True},
    ]
    # Enrich with recent cyber threat news
    with db_session() as db:
        cyber = db.execute(
            "SELECT title FROM sitroom_events WHERE event_type = 'cyber_threat' ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
    return jsonify({
        'groups': apt_groups,
        'active_count': sum(1 for g in apt_groups if g['active']),
        'recent_threats': [dict(r) for r in cyber],
    })


@situation_room_bp.route('/api/sitroom/webhook-test', methods=['POST'])
@validate_json({
    'url': {'type': str, 'required': True, 'max_length': 500},
})
def api_sitroom_webhook_test():
    """Test webhook notification delivery (POST to external URL)."""
    data = request.get_json(silent=True) or {}
    url = (data.get('url', '') or '')[:500]
    if not url or not url.startswith('http'):
        return jsonify({'error': 'Valid URL required'}), 400
    # Validate URL is not internal
    import ipaddress
    import socket
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            return jsonify({'error': 'Invalid URL'}), 400
        try:
            resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            for _, _, _, _, addr in resolved:
                ip = ipaddress.ip_address(addr[0])
                if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                    return jsonify({'error': 'Internal/private URLs not allowed'}), 400
        except socket.gaierror:
            return jsonify({'error': 'Cannot resolve hostname'}), 400
    except Exception:
        return jsonify({'error': 'Invalid URL'}), 400
    # Send test payload
    try:
        payload = {
            'event': 'test',
            'source': 'NOMAD Situation Room',
            'message': 'Webhook test notification',
            'timestamp': datetime.now().isoformat(),
        }
        resp = _http_session.post(url, json=payload, timeout=10, headers=_REQ_HEADERS)
        return jsonify({'sent': True, 'status_code': resp.status_code})
    except Exception as e:
        log.exception('Webhook test failed')
        return jsonify({'sent': False, 'error': 'Webhook request failed'})


@situation_room_bp.route('/api/sitroom/webhook-config', methods=['GET', 'POST'])
@validate_optional_json({
    'url': {'type': str, 'max_length': 500},
    'event_types': {'type': str, 'max_length': 200},
})
def api_sitroom_webhook_config():
    """Manage webhook notification configuration."""
    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_webhooks
            (id INTEGER PRIMARY KEY, url TEXT, event_types TEXT, enabled INTEGER DEFAULT 1,
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
            url = (data.get('url', '') or '')[:500]
            events = data.get('event_types', 'all')
            if not url or not url.startswith('http'):
                return jsonify({'error': 'Valid URL required'}), 400
            # SSRF protection — reject private/loopback URLs
            import ipaddress as _ipa
            import socket as _sock
            from urllib.parse import urlparse as _urlparse
            try:
                parsed = _urlparse(url)
                hostname = parsed.hostname
                if not hostname:
                    return jsonify({'error': 'Invalid URL'}), 400
                resolved = _sock.getaddrinfo(hostname, None, _sock.AF_UNSPEC, _sock.SOCK_STREAM)
                for _, _, _, _, addr in resolved:
                    ip = _ipa.ip_address(addr[0])
                    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                        return jsonify({'error': 'Internal/private URLs not allowed'}), 400
            except _sock.gaierror:
                return jsonify({'error': 'Cannot resolve hostname'}), 400
            db.execute('INSERT INTO sitroom_webhooks (url, event_types) VALUES (?, ?)',
                       (url, events))
            db.commit()
            return jsonify({'added': True})
        rows = db.execute('SELECT * FROM sitroom_webhooks ORDER BY created_at DESC LIMIT 100').fetchall()
        return jsonify({'webhooks': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/trend-comparison')
def api_sitroom_trend_comparison():
    """Compare news volume trends between two topics."""
    topic1 = request.args.get('t1', 'ukraine')[:50]
    topic2 = request.args.get('t2', 'israel')[:50]
    with db_session() as db:
        t1_count = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE ?",
            (f'%{topic1.lower()}%',)
        ).fetchone()[0]
        t2_count = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE ?",
            (f'%{topic2.lower()}%',)
        ).fetchone()[0]
        # 24h counts
        t1_24h = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE ? AND cached_at > datetime('now', '-24 hours')",
            (f'%{topic1.lower()}%',)
        ).fetchone()[0]
        t2_24h = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE ? AND cached_at > datetime('now', '-24 hours')",
            (f'%{topic2.lower()}%',)
        ).fetchone()[0]
    return jsonify({
        'topic1': {'name': topic1, 'total': t1_count, 'last_24h': t1_24h},
        'topic2': {'name': topic2, 'total': t2_count, 'last_24h': t2_24h},
        'dominant': topic1 if t1_count > t2_count else topic2,
    })


@situation_room_bp.route('/api/sitroom/situation-snapshot')
def api_sitroom_situation_snapshot():
    """Complete situation snapshot — all key metrics in one call."""
    with db_session() as db:
        news = db.execute("SELECT COUNT(*) FROM sitroom_news").fetchone()[0]
        events = db.execute("SELECT COUNT(*) FROM sitroom_events").fetchone()[0]
        quakes = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake'").fetchone()[0]
        fires = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'").fetchone()[0]
        conflicts = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type IN ('conflict','ucdp_conflict')").fetchone()[0]
        cyber = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'cyber_threat'").fetchone()[0]
        oref = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'oref_alert'").fetchone()[0]
        markets = db.execute("SELECT COUNT(*) FROM sitroom_markets").fetchone()[0]
        big_quake = db.execute("SELECT MAX(magnitude) FROM sitroom_events WHERE event_type = 'earthquake'").fetchone()[0]
    last_fetch_state, is_running = _get_state()
    live_sources = sum(1 for k, v in last_fetch_state.items() if v and (datetime.now() - v).total_seconds() < 3600)
    return jsonify({
        'total_articles': news, 'total_events': events,
        'earthquakes': quakes, 'max_magnitude': big_quake,
        'active_fires': fires, 'conflicts': conflicts,
        'cyber_threats': cyber, 'oref_alerts': oref,
        'market_symbols': markets, 'live_sources': live_sources,
        'is_refreshing': is_running,
        'snapshot_time': datetime.now().isoformat(),
    })


# ─── P5: Variant Panel Endpoints ────────────────────────────────────

@situation_room_bp.route('/api/sitroom/tech-readiness')
def api_sitroom_tech_readiness():
    """Tech Readiness Index — composite score from tech signals."""
    with db_session() as db:
        github_count = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE category = 'Developer' OR category = 'AI Research'"
        ).fetchone()[0]
        cyber_count = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'cyber_threat'").fetchone()[0]
        outage_count = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'internet_outage'").fetchone()[0]
        ai_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%ai %' OR LOWER(title) LIKE '%artificial intelligence%' OR LOWER(title) LIKE '%machine learning%'"
        ).fetchone()[0]
    # Compute readiness (higher = more active tech sector)
    innovation = min(10, github_count // 5 + ai_news // 3)
    security = max(0, 10 - cyber_count)
    stability = max(0, 10 - outage_count * 2)
    overall = round((innovation * 0.4 + security * 0.3 + stability * 0.3), 1)
    return jsonify({
        'overall': overall,
        'dimensions': {
            'innovation': innovation, 'security': security, 'stability': stability,
        },
        'raw': {'github_trending': github_count, 'cyber_threats': cyber_count,
                'outages': outage_count, 'ai_mentions': ai_news},
    })


@situation_room_bp.route('/api/sitroom/todays-hero')
def api_sitroom_todays_hero():
    """Today's Hero spotlight — find the most positive story."""
    positive_words = ['hero', 'rescue', 'saved', 'donated', 'volunteer', 'miracle',
                      'recovery', 'survived', 'breakthrough', 'peace', 'reunited',
                      'discovered', 'cured', 'freed', 'restored']
    with db_session() as db:
        rows = db.execute(
            "SELECT title, link, source_name FROM sitroom_news ORDER BY cached_at DESC LIMIT 500"
        ).fetchall()
    best = None
    best_score = 0
    for r in rows:
        d = dict(r)
        title_l = d['title'].lower()
        score = sum(1 for w in positive_words if w in title_l)
        if score > best_score:
            best_score = score
            best = d
    return jsonify({'hero': best, 'score': best_score})


@situation_room_bp.route('/api/sitroom/five-good-things')
def api_sitroom_five_good_things():
    """5 Good Things digest — curated positive news stories."""
    positive_kw = ['breakthrough', 'peace', 'record', 'milestone', 'saved',
                   'recovered', 'donated', 'clean energy', 'cure', 'growth',
                   'progress', 'achievement', 'conservation', 'restored', 'renewable',
                   'vaccine', 'rescued', 'volunteered', 'invented', 'discovery']
    placeholders = ' OR '.join(['LOWER(title) LIKE ?' for _ in positive_kw])
    params = [f'%{w}%' for w in positive_kw]
    with db_session() as db:
        rows = db.execute(
            f"SELECT title, link, source_name, category FROM sitroom_news WHERE {placeholders} "
            f"ORDER BY cached_at DESC LIMIT 20",
            params
        ).fetchall()
    # Score and pick top 5
    results = []
    for r in rows:
        d = dict(r)
        score = sum(1 for w in positive_kw if w in d['title'].lower())
        results.append({**d, 'positivity_score': score})
    results.sort(key=lambda x: x['positivity_score'], reverse=True)
    return jsonify({'good_things': results[:5], 'total_positive': len(results)})


@situation_room_bp.route('/api/sitroom/central-bank-calendar')
def api_sitroom_central_bank_calendar():
    """Enhanced Central Bank Watch with rate decision calendar."""
    # Major central bank meetings (approximate schedule)
    calendar = [
        {'bank': 'Federal Reserve (FOMC)', 'frequency': '8x/year', 'next_approx': 'See fed.gov'},
        {'bank': 'European Central Bank', 'frequency': '8x/year', 'next_approx': 'See ecb.europa.eu'},
        {'bank': 'Bank of England', 'frequency': '8x/year', 'next_approx': 'See bankofengland.co.uk'},
        {'bank': 'Bank of Japan', 'frequency': '8x/year', 'next_approx': 'See boj.or.jp'},
        {'bank': 'People\'s Bank of China', 'frequency': 'Monthly', 'next_approx': 'See pbc.gov.cn'},
        {'bank': 'Reserve Bank of Australia', 'frequency': '11x/year', 'next_approx': 'See rba.gov.au'},
        {'bank': 'Reserve Bank of India', 'frequency': '6x/year', 'next_approx': 'See rbi.org.in'},
        {'bank': 'Swiss National Bank', 'frequency': '4x/year', 'next_approx': 'See snb.ch'},
    ]
    with db_session() as db:
        cb_news = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE "
            "LOWER(title) LIKE '%rate decision%' OR LOWER(title) LIKE '%rate cut%' "
            "OR LOWER(title) LIKE '%rate hike%' OR LOWER(title) LIKE '%interest rate%' "
            "OR LOWER(title) LIKE '%monetary policy%' OR LOWER(title) LIKE '%central bank%' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
    return jsonify({'calendar': calendar, 'news': [dict(r) for r in cb_news]})


@situation_room_bp.route('/api/sitroom/country-timeline-visual/<country>')
def api_sitroom_country_timeline_visual(country):
    """Visual timeline data for a country — events + news binned by day."""
    country_lower = country.lower()
    with db_session() as db:
        events = db.execute(
            "SELECT title, event_type, magnitude, DATE(cached_at) as day FROM sitroom_events "
            "WHERE LOWER(title) LIKE ? GROUP BY title ORDER BY cached_at DESC LIMIT 100",
            (f'%{country_lower}%',)
        ).fetchall()
        news = db.execute(
            "SELECT title, category, source_name, DATE(cached_at) as day FROM sitroom_news "
            "WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 100",
            (f'%{country_lower}%',)
        ).fetchall()
    # Bin by day
    days = {}
    for r in events:
        d = dict(r)
        day = d.get('day', 'unknown')
        if day not in days:
            days[day] = {'events': [], 'news': []}
        days[day]['events'].append(d)
    for r in news:
        d = dict(r)
        day = d.get('day', 'unknown')
        if day not in days:
            days[day] = {'events': [], 'news': []}
        days[day]['news'].append(d)
    timeline = [{'date': k, 'events': v['events'][:5], 'news': v['news'][:5],
                  'event_count': len(v['events']), 'news_count': len(v['news'])}
                 for k, v in sorted(days.items(), reverse=True)]
    return jsonify({'country': country, 'timeline': timeline[:14]})


@situation_room_bp.route('/api/sitroom/commands')
def api_sitroom_commands():
    """Return available command palette entries for power users."""
    commands = [
        {'cmd': '/refresh', 'desc': 'Refresh all data feeds', 'action': 'refreshSitroomFeeds()'},
        {'cmd': '/search <query>', 'desc': 'Search all cached data', 'action': 'openSitroomSearch()'},
        {'cmd': '/country <name>', 'desc': 'Open country deep dive', 'action': 'openCountryDeepDive(name)'},
        {'cmd': '/brief <country>', 'desc': 'Generate AI country brief', 'action': 'loadSitroomCountryBrief(country)'},
        {'cmd': '/deduction', 'desc': 'Run AI situation deduction', 'action': 'runSitroomDeduction()'},
        {'cmd': '/export csv', 'desc': 'Export news as CSV', 'action': 'window.open("/api/sitroom/export-csv")'},
        {'cmd': '/export json', 'desc': 'Export all data as JSON', 'action': 'window.open("/api/sitroom/export-json")'},
        {'cmd': '/fullscreen', 'desc': 'Toggle map fullscreen', 'action': 'toggleMapFullscreen()'},
        {'cmd': '/globe', 'desc': 'Toggle 3D globe view', 'action': 'toggleSitroomGlobe()'},
        {'cmd': '/layers', 'desc': 'Open layer panel', 'action': 'toggleLayerPanel()'},
        {'cmd': '/threat', 'desc': 'Show threat level', 'action': 'loadSitroomThreatLevel()'},
        {'cmd': '/anomalies', 'desc': 'Check for anomalies', 'action': 'loadSitroomAnomalies()'},
        {'cmd': '/watch <keyword>', 'desc': 'Add keyword to watchlist', 'action': 'addToWatchlist(keyword)'},
        {'cmd': '/sources', 'desc': 'Show source health', 'action': 'loadSitroomSourceHealth()'},
        {'cmd': '/version', 'desc': 'Show version info', 'action': 'showSitroomVersion()'},
    ]
    return jsonify({'commands': commands, 'count': len(commands)})


@situation_room_bp.route('/api/sitroom/mcp-capabilities')
def api_sitroom_mcp_capabilities():
    """MCP-compatible capability manifest for AI agent integration."""
    return jsonify({
        'name': 'NOMAD Situation Room',
        'version': '6.21',
        'protocol': 'mcp-v1',
        'capabilities': {
            'news': {'search': True, 'cluster': True, 'export': True, 'categories': True},
            'events': {'geojson': True, 'filter_by_type': True, 'timeline': True},
            'markets': {'realtime': True, 'sectors': True, 'forex': True, 'crypto': True},
            'intelligence': {'country_brief': True, 'deduction': True, 'breaking': True, 'signals': True},
            'maps': {'layers': 45, 'static_points': 1275, 'geojson_export': True},
            'analysis': {'clustering': True, 'anomaly_detection': True, 'sentiment': True, 'correlation': True},
            'alerts': {'oref': True, 'earthquakes': True, 'weather': True, 'cyber': True},
        },
        'endpoints': {
            'search': '/api/sitroom/search',
            'news': '/api/sitroom/news',
            'events': '/api/sitroom/events',
            'country_brief': '/api/sitroom/country-brief/<country>',
            'deduction': '/api/sitroom/deduction',
            'snapshot': '/api/sitroom/situation-snapshot',
            'export_json': '/api/sitroom/export-json',
            'geojson': '/api/sitroom/events-geojson',
        },
    })


@situation_room_bp.route('/api/sitroom/conflict-intensity')
def api_sitroom_conflict_intensity():
    """Conflict intensity scoring per active conflict zone."""
    with db_session() as db:
        conflicts = db.execute(
            "SELECT title, magnitude, lat, lng, detail_json FROM sitroom_events "
            "WHERE event_type = 'ucdp_conflict' ORDER BY magnitude DESC LIMIT 30"
        ).fetchall()
    zones = {}
    for r in conflicts:
        d = dict(r)
        # Group by approximate region (round to 2 degrees)
        key = f"{round(d.get('lat', 0) / 2) * 2},{round(d.get('lng', 0) / 2) * 2}"
        if key not in zones:
            zones[key] = {'title': d['title'], 'lat': d.get('lat'), 'lng': d.get('lng'),
                          'events': 0, 'total_magnitude': 0}
        zones[key]['events'] += 1
        zones[key]['total_magnitude'] += d.get('magnitude', 0) or 0
    ranked = sorted(zones.values(), key=lambda z: z['total_magnitude'], reverse=True)
    for z in ranked:
        z['intensity'] = 'critical' if z['total_magnitude'] > 50 else 'high' if z['total_magnitude'] > 20 else 'medium' if z['total_magnitude'] > 5 else 'low'
    return jsonify({'zones': ranked[:15], 'count': len(ranked)})


@situation_room_bp.route('/api/sitroom/media-bias')
def api_sitroom_media_bias():
    """Analyze source diversity — how many unique sources cover each topic."""
    with db_session() as db:
        rows = db.execute(
            "SELECT category, COUNT(DISTINCT source_name) as source_count, COUNT(*) as article_count "
            "FROM sitroom_news GROUP BY category ORDER BY source_count DESC"
        ).fetchall()
    return jsonify({'diversity': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/language-coverage')
def api_sitroom_language_coverage():
    """Return news coverage by language/region source."""
    regions = {'World': 0, 'Europe': 0, 'Asia-Pacific': 0, 'Middle East': 0,
               'Latin America': 0, 'Africa': 0, 'OSINT': 0, 'Think Tanks': 0}
    with db_session() as db:
        rows = db.execute(
            "SELECT category, COUNT(*) as c FROM sitroom_news GROUP BY category"
        ).fetchall()
    for r in rows:
        d = dict(r)
        cat = d.get('category', '')
        if cat in regions:
            regions[cat] = d['c']
    return jsonify({'coverage': regions, 'total': sum(regions.values())})


@situation_room_bp.route('/api/sitroom/escalation-tracker')
def api_sitroom_escalation_tracker():
    """Track escalation/de-escalation signals in active conflicts."""
    escalation_words = ['escalat', 'mobiliz', 'deploy', 'launch', 'invad', 'annex', 'nuclear',
                        'ultimatum', 'threat', 'sanction', 'blockade', 'siege']
    deescalation_words = ['ceasefire', 'negotiate', 'peace', 'withdraw', 'truce', 'de-escalat',
                          'diplomatic', 'agreement', 'compromise', 'humanitarian corridor']
    with db_session() as db:
        rows = db.execute(
            "SELECT title FROM sitroom_news WHERE cached_at > datetime('now', '-24 hours')"
        ).fetchall()
    esc_count = 0
    deesc_count = 0
    for r in rows:
        title_l = dict(r)['title'].lower()
        if any(w in title_l for w in escalation_words):
            esc_count += 1
        if any(w in title_l for w in deescalation_words):
            deesc_count += 1
    direction = 'escalating' if esc_count > deesc_count * 1.5 else 'de-escalating' if deesc_count > esc_count * 1.5 else 'stable'
    return jsonify({
        'direction': direction,
        'escalation_signals': esc_count,
        'deescalation_signals': deesc_count,
        'ratio': round(esc_count / max(1, deesc_count), 2),
    })


@situation_room_bp.route('/api/sitroom/food-security')
def api_sitroom_food_security():
    """Food security assessment from commodity + news data."""
    with db_session() as db:
        grain_news = db.execute(
            "SELECT COUNT(*) FROM sitroom_news WHERE LOWER(title) LIKE '%wheat%' OR LOWER(title) LIKE '%grain%' "
            "OR LOWER(title) LIKE '%famine%' OR LOWER(title) LIKE '%food crisis%' OR LOWER(title) LIKE '%hunger%'"
        ).fetchone()[0]
        commodity_prices = db.execute(
            "SELECT symbol, price, change_24h FROM sitroom_markets WHERE LOWER(symbol) LIKE '%wheat%' "
            "OR LOWER(symbol) LIKE '%corn%' OR LOWER(symbol) LIKE '%soybean%'"
        ).fetchall()
        food_headlines = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%food%' "
            "OR LOWER(title) LIKE '%wheat%' OR LOWER(title) LIKE '%grain%' OR LOWER(title) LIKE '%famine%' "
            "ORDER BY cached_at DESC LIMIT 10"
        ).fetchall()
    risk = 'elevated' if grain_news > 5 else 'normal'
    return jsonify({
        'risk_level': risk, 'food_mentions': grain_news,
        'commodity_prices': [dict(r) for r in commodity_prices],
        'headlines': [dict(r) for r in food_headlines],
    })


@situation_room_bp.route('/api/sitroom/water-stress')
def api_sitroom_water_stress():
    """Water stress assessment from drought/flood/dam news."""
    with db_session() as db:
        water_news = db.execute(
            "SELECT title, source_name FROM sitroom_news WHERE LOWER(title) LIKE '%drought%' "
            "OR LOWER(title) LIKE '%flood%' OR LOWER(title) LIKE '%water crisis%' "
            "OR LOWER(title) LIKE '%dam %' OR LOWER(title) LIKE '%reservoir%' "
            "OR LOWER(title) LIKE '%desalination%' ORDER BY cached_at DESC LIMIT 15"
        ).fetchall()
    return jsonify({'news': [dict(r) for r in water_news], 'count': len(list(water_news))})


@situation_room_bp.route('/api/sitroom/climate-signals')
def api_sitroom_climate_signals():
    """Climate change signal detection from environmental news + data."""
    with db_session() as db:
        climate_news = db.execute(
            "SELECT title, source_name, category FROM sitroom_news WHERE "
            "LOWER(title) LIKE '%climate%' OR LOWER(title) LIKE '%global warming%' "
            "OR LOWER(title) LIKE '%carbon%emission%' OR LOWER(title) LIKE '%glacier%' "
            "OR LOWER(title) LIKE '%sea level%' OR LOWER(title) LIKE '%extreme weather%' "
            "OR LOWER(title) LIKE '%record temperature%' OR LOWER(title) LIKE '%wildfire%' "
            "ORDER BY cached_at DESC LIMIT 20"
        ).fetchall()
        fire_count = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'").fetchone()[0]
        weather_count = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'weather_alert'").fetchone()[0]
    return jsonify({
        'climate_news': [dict(r) for r in climate_news],
        'active_fires': fire_count,
        'weather_alerts': weather_count,
        'signal_strength': 'strong' if len(list(climate_news)) > 10 else 'moderate' if len(list(climate_news)) > 5 else 'weak',
    })
