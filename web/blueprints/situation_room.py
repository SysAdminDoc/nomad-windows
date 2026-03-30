"""Situation Room v2 — World Monitor-inspired global intelligence dashboard.

Data sources (all free, no API keys required):
  - 35+ curated RSS/Atom feeds across 12 categories
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

All data cached to SQLite for full offline access.
Background fetch workers with per-source cooldowns and thread safety.
"""

import json
import logging
import threading
import hashlib
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from flask import Blueprint, request, jsonify
from db import get_db, db_session, log_activity

situation_room_bp = Blueprint('situation_room', __name__)
log = logging.getLogger('nomad.situation_room')

# ─── Thread-Safe State ─────────────────────────────────────────────────
_state_lock = threading.Lock()
_last_fetch = {}  # source_key -> datetime
_fetch_running = False

_REQ_HEADERS = {'User-Agent': 'NOMAD-SitRoom/2.0'}
_REQ_TIMEOUT = 12


def _get_state(key=None):
    with _state_lock:
        if key:
            return _last_fetch.get(key)
        return dict(_last_fetch), _fetch_running


def _set_last_fetch(key):
    with _state_lock:
        _last_fetch[key] = datetime.now()


# Minimum interval between fetches per source (seconds)
FETCH_COOLDOWN = {
    'rss': 300, 'earthquakes': 120, 'weather_alerts': 300,
    'markets': 300, 'conflicts': 600, 'aviation': 180,
    'space_weather': 300, 'volcanoes': 3600, 'predictions': 600,
}


def _can_fetch(source_key):
    cooldown = FETCH_COOLDOWN.get(source_key, 300)
    last = _get_state(source_key)
    if last and (datetime.now() - last).total_seconds() < cooldown:
        return False
    return True


# ─── RSS Feed Sources ──────────────────────────────────────────────────
RSS_FEEDS = {
    'world_news': [
        {'name': 'Reuters World', 'url': 'https://feeds.reuters.com/Reuters/worldNews', 'category': 'World'},
        {'name': 'AP Top Headlines', 'url': 'https://rsshub.app/apnews/topics/apf-topnews', 'category': 'World'},
        {'name': 'BBC World', 'url': 'https://feeds.bbci.co.uk/news/world/rss.xml', 'category': 'World'},
        {'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml', 'category': 'World'},
    ],
    'us_news': [
        {'name': 'Reuters US', 'url': 'https://feeds.reuters.com/Reuters/domesticNews', 'category': 'US'},
        {'name': 'NPR Headlines', 'url': 'https://feeds.npr.org/1001/rss.xml', 'category': 'US'},
        {'name': 'PBS NewsHour', 'url': 'https://www.pbs.org/newshour/feeds/rss/headlines', 'category': 'US'},
    ],
    'technology': [
        {'name': 'Ars Technica', 'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab', 'category': 'Tech'},
        {'name': 'Hacker News', 'url': 'https://hnrss.org/frontpage', 'category': 'Tech'},
        {'name': 'The Verge', 'url': 'https://www.theverge.com/rss/index.xml', 'category': 'Tech'},
        {'name': 'TechCrunch', 'url': 'https://techcrunch.com/feed/', 'category': 'Tech'},
    ],
    'science': [
        {'name': 'Nature News', 'url': 'https://www.nature.com/nature.rss', 'category': 'Science'},
        {'name': 'NASA Breaking', 'url': 'https://www.nasa.gov/rss/dyn/breaking_news.rss', 'category': 'Science'},
        {'name': 'Science Daily', 'url': 'https://www.sciencedaily.com/rss/all.xml', 'category': 'Science'},
    ],
    'security': [
        {'name': 'Krebs on Security', 'url': 'https://krebsonsecurity.com/feed/', 'category': 'Cyber'},
        {'name': 'The Hacker News', 'url': 'https://feeds.feedburner.com/TheHackersNews', 'category': 'Cyber'},
        {'name': 'BleepingComputer', 'url': 'https://www.bleepingcomputer.com/feed/', 'category': 'Cyber'},
        {'name': 'Dark Reading', 'url': 'https://www.darkreading.com/rss_simple.asp', 'category': 'Cyber'},
    ],
    'military_defense': [
        {'name': 'Defense One', 'url': 'https://www.defenseone.com/rss/', 'category': 'Defense'},
        {'name': 'War on the Rocks', 'url': 'https://warontherocks.com/feed/', 'category': 'Defense'},
        {'name': 'Breaking Defense', 'url': 'https://breakingdefense.com/feed/', 'category': 'Defense'},
        {'name': 'The Drive - War Zone', 'url': 'https://www.thedrive.com/the-war-zone/feed', 'category': 'Defense'},
    ],
    'disasters': [
        {'name': 'GDACS Alerts', 'url': 'https://www.gdacs.org/xml/rss.xml', 'category': 'Disaster'},
        {'name': 'ReliefWeb Updates', 'url': 'https://reliefweb.int/updates/rss.xml', 'category': 'Disaster'},
        {'name': 'FEMA', 'url': 'https://www.fema.gov/feeds/disasters-702-702all.xml', 'category': 'Disaster'},
    ],
    'finance': [
        {'name': 'MarketWatch Top', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_topstories', 'category': 'Finance'},
        {'name': 'CNBC Top News', 'url': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114', 'category': 'Finance'},
        {'name': 'Bloomberg Markets', 'url': 'https://feeds.bloomberg.com/markets/news.rss', 'category': 'Finance'},
    ],
    'energy': [
        {'name': 'EIA Today in Energy', 'url': 'https://www.eia.gov/rss/todayinenergy.xml', 'category': 'Energy'},
        {'name': 'OilPrice.com', 'url': 'https://oilprice.com/rss/main', 'category': 'Energy'},
    ],
    'health': [
        {'name': 'WHO Disease Outbreaks', 'url': 'https://www.who.int/feeds/entity/don/en/rss.xml', 'category': 'Health'},
        {'name': 'CDC MMWR', 'url': 'https://tools.cdc.gov/api/v2/resources/media/316422.rss', 'category': 'Health'},
        {'name': 'CIDRAP News', 'url': 'https://www.cidrap.umn.edu/news/rss.xml', 'category': 'Health'},
    ],
    'geopolitics': [
        {'name': 'Foreign Affairs', 'url': 'https://www.foreignaffairs.com/rss.xml', 'category': 'Geopolitics'},
        {'name': 'The Diplomat', 'url': 'https://thediplomat.com/feed/', 'category': 'Geopolitics'},
    ],
}

ALL_FEEDS = []
for _cat_feeds in RSS_FEEDS.values():
    ALL_FEEDS.extend(_cat_feeds)
FEED_CATEGORIES = sorted(set(f['category'] for f in ALL_FEEDS))


# ─── RSS/Atom Parser ──────────────────────────────────────────────────
def _parse_feed(xml_text, feed_name, feed_category):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    ns = {'atom': 'http://www.w3.org/2005/Atom'}

    for item in root.findall('.//item'):
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        desc = (item.findtext('description') or '').strip()
        pub = (item.findtext('pubDate') or '').strip()
        if title:
            items.append({'title': title[:500], 'link': link[:2000], 'description': desc[:1000],
                          'published': pub[:100], 'source': feed_name, 'category': feed_category})

    if not items:
        for entry in root.findall('.//atom:entry', ns) or root.findall('.//entry'):
            t = entry.find('atom:title', ns) or entry.find('title')
            title = (t.text or '').strip() if t is not None else ''
            l = entry.find('atom:link', ns) or entry.find('link')
            link = (l.get('href', '') or (l.text or '')) if l is not None else ''
            s = entry.find('atom:summary', ns) or entry.find('summary') or entry.find('atom:content', ns) or entry.find('content')
            desc = (s.text or '').strip() if s is not None else ''
            p = entry.find('atom:updated', ns) or entry.find('updated') or entry.find('atom:published', ns) or entry.find('published')
            pub = (p.text or '').strip() if p is not None else ''
            if title:
                items.append({'title': title[:500], 'link': link[:2000], 'description': desc[:1000],
                              'published': pub[:100], 'source': feed_name, 'category': feed_category})

    return items[:50]


def _fetch_single_feed(feed):
    """Fetch a single RSS feed. Returns list of articles."""
    try:
        resp = requests.get(feed['url'], timeout=_REQ_TIMEOUT, headers={
            **_REQ_HEADERS, 'Accept': 'application/rss+xml, application/xml, text/xml'})
        if resp.ok:
            return _parse_feed(resp.text, feed['name'], feed['category'])
    except Exception as e:
        log.debug(f"RSS fetch failed for {feed['name']}: {e}")
    return []


# ─── Fetch Workers ─────────────────────────────────────────────────────

def _fetch_rss_feeds():
    """Fetch all RSS feeds in parallel and cache to DB."""
    if not _can_fetch('rss'):
        return
    _set_last_fetch('rss')

    # Build full feed list including custom feeds from DB
    feeds = list(ALL_FEEDS)
    try:
        with db_session() as db:
            custom = db.execute('SELECT name, url, category FROM sitroom_custom_feeds WHERE enabled = 1').fetchall()
            feeds.extend([{'name': r['name'], 'url': r['url'], 'category': r['category']} for r in custom])
    except Exception:
        pass

    # Parallel fetch with ThreadPoolExecutor
    articles = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_single_feed, f): f for f in feeds}
        for fut in as_completed(futures, timeout=90):
            try:
                articles.extend(fut.result())
            except Exception:
                pass

    if not articles:
        return

    # UPSERT pattern: insert new, keep existing (avoids data loss on partial failure)
    with db_session() as db:
        for a in articles:
            content_hash = hashlib.sha256((a['title'] + a['link']).encode()).hexdigest()[:32]
            db.execute('''INSERT OR REPLACE INTO sitroom_news
                (content_hash, title, link, description, published, source_name, category, source_type, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'rss', CURRENT_TIMESTAMP)''',
                (content_hash, a['title'], a['link'], a['description'],
                 a['published'], a['source'], a['category']))
        # Prune old articles (keep last 2000)
        db.execute('DELETE FROM sitroom_news WHERE id NOT IN (SELECT id FROM sitroom_news ORDER BY cached_at DESC LIMIT 2000)')
        db.commit()
    log.info(f"Situation Room: cached {len(articles)} RSS articles from {len(feeds)} feeds")


def _fetch_earthquakes():
    if not _can_fetch('earthquakes'):
        return
    _set_last_fetch('earthquakes')
    try:
        resp = requests.get('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson',
                            timeout=15, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = resp.json()
    except Exception as e:
        log.debug(f"Earthquake fetch failed: {e}")
        return

    features = data.get('features', [])[:100]
    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'earthquake'")
        for f in features:
            props = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [0, 0, 0])
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, depth_km, event_time, source_url, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (f.get('id', ''), 'earthquake', props.get('place', ''),
                 props.get('mag'), coords[1] if len(coords) > 1 else 0,
                 coords[0] if coords else 0, coords[2] if len(coords) > 2 else 0,
                 props.get('time', 0), props.get('url', ''),
                 json.dumps({'tsunami': props.get('tsunami'), 'alert': props.get('alert'),
                             'felt': props.get('felt'), 'sig': props.get('sig')})))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} earthquakes")


def _fetch_weather_alerts():
    if not _can_fetch('weather_alerts'):
        return
    _set_last_fetch('weather_alerts')
    try:
        resp = requests.get('https://api.weather.gov/alerts/active?status=actual&severity=Extreme,Severe',
                            timeout=15, headers={**_REQ_HEADERS, 'Accept': 'application/geo+json'})
        if not resp.ok:
            return
        data = resp.json()
    except Exception as e:
        log.debug(f"Weather alerts fetch failed: {e}")
        return

    features = data.get('features', [])[:200]
    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'weather_alert'")
        for f in features:
            props = f.get('properties', {})
            event_id = props.get('id', '')
            geom = f.get('geometry')
            lat, lng = 0.0, 0.0
            if geom and geom.get('coordinates'):
                try:
                    coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
                    lat = sum(c[1] for c in coords) / len(coords)
                    lng = sum(c[0] for c in coords) / len(coords)
                except (IndexError, TypeError, ZeroDivisionError):
                    pass
            onset_ms = 0
            try:
                if props.get('onset'):
                    onset_ms = int(datetime.fromisoformat(props['onset'].replace('Z', '+00:00')).timestamp() * 1000)
            except (ValueError, TypeError):
                pass
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (event_id, 'weather_alert',
                 f"{props.get('event', '')} - {props.get('areaDesc', '')}",
                 lat, lng, onset_ms, props.get('id', ''),
                 json.dumps({
                     'severity': props.get('severity'), 'certainty': props.get('certainty'),
                     'urgency': props.get('urgency'), 'headline': (props.get('headline') or '')[:500],
                     'description': (props.get('description') or '')[:2000],
                     'instruction': (props.get('instruction') or '')[:1000],
                     'sender': props.get('senderName', ''), 'expires': props.get('expires', ''),
                 })))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} weather alerts")


def _fetch_market_data():
    if not _can_fetch('markets'):
        return
    _set_last_fetch('markets')
    markets = []

    # Yahoo Finance — stock indices (S&P 500, NASDAQ, Dow Jones)
    yf_symbols = {'^GSPC': 'S&P 500', '^IXIC': 'NASDAQ', '^DJI': 'DOW JONES'}
    for sym, name in yf_symbols.items():
        try:
            resp = requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}',
                                params={'range': '1d', 'interval': '5m'}, timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
            if resp.ok:
                meta = resp.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                price = meta.get('regularMarketPrice', 0)
                prev = meta.get('previousClose', 0)
                change = ((price - prev) / prev * 100) if prev else 0
                markets.append({'symbol': name, 'price': price, 'change_24h': round(change, 2), 'market_type': 'index'})
        except Exception as e:
            log.debug(f"Yahoo Finance {sym} failed: {e}")

    # Crypto (CoinGecko)
    try:
        resp = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            names = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL'}
            for coin, vals in resp.json().items():
                markets.append({'symbol': names.get(coin, coin.upper()), 'price': vals.get('usd', 0),
                                'change_24h': round(vals.get('usd_24h_change') or 0, 2), 'market_type': 'crypto'})
    except Exception as e:
        log.debug(f"CoinGecko failed: {e}")

    # Gold/Silver (metals.dev)
    try:
        resp = requests.get('https://api.metals.dev/v1/latest?api_key=demo&currency=USD&unit=toz',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            metals = resp.json().get('metals', {})
            if 'gold' in metals:
                markets.append({'symbol': 'GOLD', 'price': metals['gold'], 'change_24h': 0, 'market_type': 'commodity'})
            if 'silver' in metals:
                markets.append({'symbol': 'SILVER', 'price': metals['silver'], 'change_24h': 0, 'market_type': 'commodity'})
    except Exception as e:
        log.debug(f"Metals failed: {e}")

    # Brent oil (EIA)
    try:
        resp = requests.get('https://api.eia.gov/v2/petroleum/pri/spt/data/',
                            params={'api_key': 'DEMO_KEY', 'frequency': 'daily', 'data[0]': 'value',
                                    'facets[product][]': 'EPCBRENT', 'sort[0][column]': 'period',
                                    'sort[0][direction]': 'desc', 'length': '1'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            rows = resp.json().get('response', {}).get('data', [])
            if rows:
                try:
                    markets.append({'symbol': 'OIL (BRENT)', 'price': float(rows[0].get('value', 0)),
                                    'change_24h': 0, 'market_type': 'commodity'})
                except (ValueError, TypeError):
                    pass
    except Exception as e:
        log.debug(f"EIA failed: {e}")

    # Fear & Greed Index
    try:
        resp = requests.get('https://api.alternative.me/fng/?limit=1', timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            fg = resp.json().get('data', [{}])[0]
            markets.append({'symbol': 'FEAR_GREED', 'price': int(fg.get('value', 50)),
                            'change_24h': 0, 'market_type': 'sentiment',
                            'label': fg.get('value_classification', 'Neutral')})
    except Exception as e:
        log.debug(f"Fear/Greed failed: {e}")

    if not markets:
        return

    with db_session() as db:
        db.execute('DELETE FROM sitroom_markets')
        for m in markets:
            db.execute('INSERT INTO sitroom_markets (symbol, price, change_24h, market_type, label) VALUES (?, ?, ?, ?, ?)',
                       (m['symbol'], m['price'], m.get('change_24h', 0), m.get('market_type', 'other'), m.get('label', '')))
        db.commit()
    log.info(f"Situation Room: cached {len(markets)} market entries")


def _fetch_conflict_data():
    if not _can_fetch('conflicts'):
        return
    _set_last_fetch('conflicts')
    # Dynamic 90-day window
    from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    try:
        resp = requests.get(
            f'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?alertlevel=Orange;Red&eventlist=EQ;TC;FL;VO;DR&from={from_date}',
            timeout=15, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
        if not resp.ok:
            return
        data = resp.json()
    except Exception as e:
        log.debug(f"GDACS failed: {e}")
        return

    features = data.get('features', [])[:50]
    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'conflict'")
        for f in features:
            props = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [0, 0])
            eid = str(props.get('eventid', hashlib.sha256(json.dumps(props, sort_keys=True).encode()).hexdigest()[:12]))
            sev = props.get('severity', {})
            mag = sev.get('severity_value') if isinstance(sev, dict) else None
            url_obj = props.get('url', {})
            source_url = url_obj.get('report', '') if isinstance(url_obj, dict) else ''
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (eid, 'conflict', props.get('name', props.get('eventtype', 'Unknown')),
                 mag, coords[1] if len(coords) > 1 else 0, coords[0] if coords else 0, 0, source_url,
                 json.dumps({'alert_level': props.get('alertlevel', ''), 'event_type': props.get('eventtype', ''),
                             'country': props.get('country', ''), 'description': (props.get('description') or '')[:2000]})))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} GDACS events")


def _fetch_aviation():
    """Fetch live aircraft positions from OpenSky Network."""
    if not _can_fetch('aviation'):
        return
    _set_last_fetch('aviation')
    try:
        # Fetch all aircraft (rate limited, ~10/day anonymous)
        resp = requests.get('https://opensky-network.org/api/states/all',
                            timeout=20, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = resp.json()
    except Exception as e:
        log.debug(f"OpenSky failed: {e}")
        return

    states = data.get('states', [])
    if not states:
        return

    # Only keep airborne aircraft with valid positions (cap at 500 for performance)
    valid = [s for s in states if s[6] is not None and s[5] is not None and not s[8]][:500]

    with db_session() as db:
        db.execute('DELETE FROM sitroom_aviation')
        for s in valid:
            db.execute('''INSERT INTO sitroom_aviation
                (icao24, callsign, origin_country, lat, lng, altitude_m, velocity_ms, heading, vertical_rate, on_ground, squawk)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (s[0] or '', (s[1] or '').strip(), s[2] or '',
                 s[6] or 0, s[5] or 0, s[7] or 0, s[9] or 0,
                 s[10] or 0, s[11] or 0, 1 if s[8] else 0, s[14] or ''))
        db.commit()
    log.info(f"Situation Room: cached {len(valid)} aircraft positions")


def _fetch_space_weather():
    """Fetch space weather data from NOAA SWPC."""
    if not _can_fetch('space_weather'):
        return
    _set_last_fetch('space_weather')

    datasets = {}

    # NOAA storm scales (G/S/R)
    try:
        resp = requests.get('https://services.swpc.noaa.gov/products/noaa-scales.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            scales = resp.json()
            datasets['noaa_scales'] = scales.get('0', {})  # Current conditions
    except Exception as e:
        log.debug(f"NOAA scales failed: {e}")

    # Kp index (geomagnetic activity)
    try:
        resp = requests.get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            kp_data = resp.json()
            if kp_data:
                datasets['kp_index'] = {'latest': kp_data[-1], 'recent': kp_data[-8:]}
    except Exception as e:
        log.debug(f"NOAA Kp failed: {e}")

    # Solar flare probabilities
    try:
        resp = requests.get('https://services.swpc.noaa.gov/json/solar_probabilities.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            probs = resp.json()
            if probs:
                datasets['solar_probs'] = probs[-1]
    except Exception as e:
        log.debug(f"NOAA solar probs failed: {e}")

    # Active space weather alerts
    try:
        resp = requests.get('https://services.swpc.noaa.gov/products/alerts.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            alerts = resp.json()
            datasets['sw_alerts'] = alerts[:10]
    except Exception as e:
        log.debug(f"NOAA alerts failed: {e}")

    if not datasets:
        return

    with db_session() as db:
        db.execute('DELETE FROM sitroom_space_weather')
        for dtype, data in datasets.items():
            db.execute('INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)',
                       (dtype, json.dumps(data)))
        db.commit()
    log.info(f"Situation Room: cached {len(datasets)} space weather datasets")


def _fetch_volcanoes():
    """Fetch recent volcanic activity from Smithsonian GVP."""
    if not _can_fetch('volcanoes'):
        return
    _set_last_fetch('volcanoes')
    try:
        resp = requests.get('https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows',
                            params={'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature',
                                    'typeName': 'GVP-VOTW:E3WebApp_Eruptions1960',
                                    'maxFeatures': '50', 'outputFormat': 'application/json',
                                    'sortBy': 'StartDate+D'},
                            timeout=20, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = resp.json()
    except Exception as e:
        log.debug(f"Volcano fetch failed: {e}")
        return

    features = data.get('features', [])[:50]
    with db_session() as db:
        db.execute('DELETE FROM sitroom_volcanoes')
        for f in features:
            p = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [0, 0])
            db.execute('''INSERT INTO sitroom_volcanoes
                (volcano_name, country, lat, lng, vei, start_date, end_date, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (p.get('VolcanoName', ''), p.get('Country', ''),
                 coords[1] if len(coords) > 1 else 0, coords[0] if coords else 0,
                 p.get('ExplosivityIndexMax') or 0, p.get('StartDate', ''), p.get('EndDate', ''),
                 json.dumps({'volcano_number': p.get('VolcanoNumber'),
                             'continuing': p.get('ContinuingEruption', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} volcanic eruptions")


def _fetch_predictions():
    """Fetch prediction markets from Polymarket."""
    if not _can_fetch('predictions'):
        return
    _set_last_fetch('predictions')
    try:
        resp = requests.get('https://gamma-api.polymarket.com/markets',
                            params={'limit': 20, 'active': 'true', 'closed': 'false'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        markets = resp.json()
    except Exception as e:
        log.debug(f"Polymarket failed: {e}")
        return

    if not markets:
        return

    with db_session() as db:
        db.execute('DELETE FROM sitroom_predictions')
        for m in markets:
            prices = m.get('outcomePrices', '[]')
            if isinstance(prices, str):
                try:
                    prices = json.loads(prices)
                except (json.JSONDecodeError, TypeError):
                    prices = []
            yes_price = float(prices[0]) if prices else 0
            no_price = float(prices[1]) if len(prices) > 1 else 0
            db.execute('''INSERT OR IGNORE INTO sitroom_predictions
                (market_id, question, category, outcome_yes, outcome_no, volume, end_date, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (str(m.get('id', '')), (m.get('question') or '')[:500],
                 m.get('category', ''), yes_price, no_price,
                 m.get('volumeNum') or m.get('volume') or 0,
                 m.get('endDate', ''), 1 if m.get('active') else 0))
        db.commit()
    log.info(f"Situation Room: cached {len(markets)} prediction markets")


# ─── Refresh Orchestrator ──────────────────────────────────────────────

def refresh_all_feeds():
    global _fetch_running
    with _state_lock:
        if _fetch_running:
            return False
        _fetch_running = True

    def _worker():
        global _fetch_running
        try:
            _fetch_rss_feeds()
            _fetch_earthquakes()
            _fetch_weather_alerts()
            _fetch_market_data()
            _fetch_conflict_data()
            _fetch_aviation()
            _fetch_space_weather()
            _fetch_volcanoes()
            _fetch_predictions()
        except Exception as e:
            log.exception(f"Situation Room refresh error: {e}")
        finally:
            with _state_lock:
                _fetch_running = False

    threading.Thread(target=_worker, daemon=True).start()
    return True


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
    limit = min(request.args.get('limit', 100, type=int), 500)
    offset = request.args.get('offset', 0, type=int)
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
    limit = min(request.args.get('limit', 200, type=int), 500)
    with db_session() as db:
        if event_type:
            rows = db.execute('SELECT * FROM sitroom_events WHERE event_type = ? ORDER BY cached_at DESC LIMIT ?',
                              (event_type, limit)).fetchall()
        else:
            rows = db.execute('SELECT * FROM sitroom_events ORDER BY cached_at DESC LIMIT ?', (limit,)).fetchall()
    return jsonify({'events': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/earthquakes')
def api_sitroom_earthquakes():
    min_mag = request.args.get('min_magnitude', 0, type=float)
    with db_session() as db:
        rows = db.execute(
            "SELECT * FROM sitroom_events WHERE event_type = 'earthquake' AND (magnitude IS NULL OR magnitude >= ?) ORDER BY event_time DESC LIMIT 100",
            (min_mag,)).fetchall()
    return jsonify({'earthquakes': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/weather-alerts')
def api_sitroom_weather_alerts():
    with db_session() as db:
        rows = db.execute("SELECT * FROM sitroom_events WHERE event_type = 'weather_alert' ORDER BY cached_at DESC LIMIT 100").fetchall()
    return jsonify({'alerts': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/markets')
def api_sitroom_markets():
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_markets ORDER BY market_type, symbol').fetchall()
    return jsonify({'markets': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/aviation')
def api_sitroom_aviation():
    """Return cached aircraft positions."""
    limit = min(request.args.get('limit', 200, type=int), 500)
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_aviation ORDER BY altitude_m DESC LIMIT ?', (limit,)).fetchall()
    return jsonify({'aircraft': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/space-weather')
def api_sitroom_space_weather():
    """Return cached space weather data."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_space_weather').fetchall()
    result = {}
    for r in rows:
        try:
            result[r['data_type']] = json.loads(r['value_json'])
        except (json.JSONDecodeError, TypeError):
            pass
    return jsonify(result)


@situation_room_bp.route('/api/sitroom/volcanoes')
def api_sitroom_volcanoes():
    """Return cached volcanic activity."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_volcanoes ORDER BY start_date DESC LIMIT 50').fetchall()
    return jsonify({'volcanoes': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/predictions')
def api_sitroom_predictions():
    """Return cached prediction markets."""
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_predictions WHERE active = 1 ORDER BY volume DESC LIMIT 20').fetchall()
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
            (SELECT COUNT(*) FROM sitroom_custom_feeds) as custom_feeds
        ''').fetchone()

        top_quakes = db.execute(
            "SELECT title, magnitude, lat, lng FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude IS NOT NULL ORDER BY magnitude DESC LIMIT 5"
        ).fetchall()

        market_rows = db.execute('SELECT * FROM sitroom_markets ORDER BY market_type, symbol').fetchall()

        # Space weather summary
        sw_row = db.execute("SELECT value_json FROM sitroom_space_weather WHERE data_type = 'noaa_scales'").fetchone()
        space_weather = json.loads(sw_row['value_json']) if sw_row else None

    return jsonify({
        'news_count': counts['news'], 'earthquake_count': counts['quakes'],
        'weather_alert_count': counts['weather'], 'conflict_count': counts['conflicts'],
        'market_count': counts['markets'], 'aircraft_count': counts['aircraft'],
        'volcano_count': counts['volcanoes'], 'prediction_count': counts['predictions'],
        'custom_feed_count': counts['custom_feeds'],
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
        custom = db.execute('SELECT * FROM sitroom_custom_feeds ORDER BY category, name').fetchall()
    return jsonify({
        'builtin': [{'name': f['name'], 'url': f['url'], 'category': f['category']} for f in ALL_FEEDS],
        'custom': [dict(r) for r in custom],
        'categories': FEED_CATEGORIES,
    })


@situation_room_bp.route('/api/sitroom/feeds', methods=['POST'])
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
        db.commit()
        if r.rowcount == 0:
            return jsonify({'error': 'Feed not found'}), 404
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
        try:
            sw = json.loads(sw_row['value_json'])
            parts.append(f"\n--- SPACE WEATHER ---")
            parts.append(f"Radio Blackout: R{sw.get('R', {}).get('Scale', 0)} | Solar Radiation: S{sw.get('S', {}).get('Scale', 0)} | Geomagnetic: G{sw.get('G', {}).get('Scale', 0)}")
        except Exception:
            pass

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
    limit = min(request.args.get('limit', 10, type=int), 50)
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_briefings ORDER BY generated_at DESC LIMIT ?', (limit,)).fetchall()
    return jsonify({'briefings': [dict(r) for r in rows]})
