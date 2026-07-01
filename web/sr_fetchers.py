"""Situation Room data fetchers — constants, helpers, and background workers.

Extracted from ``web.blueprints.situation_room`` to keep the blueprint file
focused on Flask routes. Everything here is pure data-fetching logic with
no Flask route registrations.
"""

import json
import logging
import sqlite3
import threading
import hashlib
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from flask import current_app
from db import db_session
from web.utils import (
    clone_json_fallback as _clone_json_fallback,
    safe_float as _safe_float,
    safe_json_value as _safe_json_value,
)

log = logging.getLogger('nomad.situation_room')

# ─── Thread-Safe State ─────────────────────────────────────────────────
_state_lock = threading.Lock()
_last_fetch = {}  # source_key -> datetime
_fetch_running = False

_REQ_HEADERS = {'User-Agent': 'NOMAD-SitRoom/2.0'}
_REQ_TIMEOUT = 12

# Reusable session for connection pooling across 40+ feeds per refresh cycle
_http_session = requests.Session()
_http_session.headers.update(_REQ_HEADERS)


def _fetch_with_retry(url, timeout=10, retries=2, **kwargs):
    """Fetch URL with exponential backoff retry (uses pooled session).

    Narrowed to the real network failure surface — ``requests.RequestException``
    covers ConnectionError / Timeout / HTTPError / ChunkedEncodingError /
    ContentDecodingError / TooManyRedirects. A bug elsewhere (NameError,
    TypeError) should propagate, not be masked by a retry loop.
    """
    import time
    kwargs.setdefault('headers', _REQ_HEADERS)
    for attempt in range(retries + 1):
        try:
            r = _http_session.get(url, timeout=timeout, **kwargs)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(0.5 * (2 ** attempt))
    return None


def _safe_response_json(response, fallback=None):
    """Parse a Response body as JSON with a caller-supplied fallback.

    ``response.json()`` raises ``ValueError`` (incl. ``json.JSONDecodeError``
    and ``requests.exceptions.JSONDecodeError`` subclasses) on parse failures,
    ``AttributeError`` if the caller passes something that isn't a Response,
    and ``TypeError`` when the body decoder chokes on the content-type. Those
    are the only failures we want to swallow; a programming error should
    still surface.
    """
    if fallback is None:
        fallback = {}
    if response is None:
        return _clone_json_fallback(fallback)
    try:
        parsed = response.json()
    except (ValueError, TypeError, AttributeError):
        return _clone_json_fallback(fallback)
    if isinstance(parsed, (dict, list)):
        return parsed
    return _clone_json_fallback(fallback)


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
    'fires': 600, 'disease_outbreaks': 1800,
    'internet_outages': 600,
    'radiation': 1800, 'gdelt_trending': 600, 'sanctions': 3600,
    'displacement': 7200, 'ucdp': 3600, 'cyber_threats': 1800,
    'yield_curve': 3600, 'stablecoins': 600, 'correlation': 300,
    'service_status': 300, 'social_velocity': 600,
    'renewable': 3600, 'bigmac': 86400,
    'github_trending': 3600, 'fuel_prices': 7200,
    'product_hunt': 3600, 'macro_stress': 3600,
    'central_banks': 3600, 'arxiv_papers': 7200,
    'ais_ships': 300, 'oref_alerts': 60, 'gdelt_events': 1800,
    'cot_positioning': 86400,
}

# ─── Live YouTube Channels ────────────────────────────────────────────
LIVE_CHANNELS = [
    {'name': 'Al Jazeera English', 'handle': '@aborigi', 'video_id': 'bNyUyrR0PHo', 'region': 'World'},
    {'name': 'France 24 English', 'handle': '@FRANCE24English', 'video_id': 'h3MuIUNCCzI', 'region': 'World'},
    {'name': 'DW News', 'handle': '@DWNews', 'video_id': '', 'region': 'Europe'},
    {'name': 'Sky News', 'handle': '@SkyNews', 'video_id': '9Auq9mYxFEE', 'region': 'UK'},
    {'name': 'NBC News NOW', 'handle': '@NBCNews', 'video_id': '', 'region': 'US'},
    {'name': 'ABC News Live', 'handle': '@ABCNews', 'video_id': '', 'region': 'US'},
    {'name': 'Reuters', 'handle': '@Reuters', 'video_id': '', 'region': 'World'},
    {'name': 'WION', 'handle': '@ABORIG', 'video_id': '', 'region': 'Asia'},
    {'name': 'NHK World', 'handle': '@NHKWORLDJAPAN', 'video_id': '', 'region': 'Asia'},
    {'name': 'TRT World', 'handle': '@taborig', 'video_id': '', 'region': 'Middle East'},
    {'name': 'CGTN', 'handle': '@CGTNOfficial', 'video_id': '', 'region': 'Asia'},
    {'name': 'Euronews', 'handle': '@euronews', 'video_id': '', 'region': 'Europe'},
]


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
        {'name': 'The Guardian World', 'url': 'https://www.theguardian.com/world/rss', 'category': 'World'},
        {'name': 'France 24', 'url': 'https://www.france24.com/en/rss', 'category': 'World'},
        {'name': 'DW News', 'url': 'https://rss.dw.com/xml/rss-en-all', 'category': 'World'},
        {'name': 'Euronews', 'url': 'https://www.euronews.com/rss', 'category': 'World'},
        {'name': 'UN News', 'url': 'https://news.un.org/feed/subscribe/en/news/all/rss.xml', 'category': 'World'},
    ],
    'us_news': [
        {'name': 'Reuters US', 'url': 'https://feeds.reuters.com/Reuters/domesticNews', 'category': 'US'},
        {'name': 'NPR Headlines', 'url': 'https://feeds.npr.org/1001/rss.xml', 'category': 'US'},
        {'name': 'PBS NewsHour', 'url': 'https://www.pbs.org/newshour/feeds/rss/headlines', 'category': 'US'},
        {'name': 'ABC News', 'url': 'https://feeds.abcnews.com/abcnews/topstories', 'category': 'US'},
        {'name': 'CBS News', 'url': 'https://www.cbsnews.com/latest/rss/main', 'category': 'US'},
        {'name': 'Politico', 'url': 'https://rss.politico.com/politics-news.xml', 'category': 'US'},
        {'name': 'The Hill', 'url': 'https://thehill.com/news/feed', 'category': 'US'},
        {'name': 'Axios', 'url': 'https://api.axios.com/feed/', 'category': 'US'},
    ],
    'europe': [
        {'name': 'BBC Europe', 'url': 'https://feeds.bbci.co.uk/news/world/europe/rss.xml', 'category': 'Europe'},
        {'name': 'Guardian Europe', 'url': 'https://www.theguardian.com/world/europe-news/rss', 'category': 'Europe'},
        {'name': 'EUobserver', 'url': 'https://euobserver.com/rss.xml', 'category': 'Europe'},
    ],
    'middle_east': [
        {'name': 'BBC Middle East', 'url': 'https://feeds.bbci.co.uk/news/world/middle_east/rss.xml', 'category': 'Middle East'},
        {'name': 'Al Monitor', 'url': 'https://www.al-monitor.com/rss', 'category': 'Middle East'},
        {'name': 'Middle East Eye', 'url': 'https://www.middleeasteye.net/rss', 'category': 'Middle East'},
    ],
    'asia_pacific': [
        {'name': 'BBC Asia', 'url': 'https://feeds.bbci.co.uk/news/world/asia/rss.xml', 'category': 'Asia-Pacific'},
        {'name': 'South China Morning Post', 'url': 'https://www.scmp.com/rss/91/feed', 'category': 'Asia-Pacific'},
        {'name': 'Nikkei Asia', 'url': 'https://asia.nikkei.com/rss', 'category': 'Asia-Pacific'},
    ],
    'africa': [
        {'name': 'BBC Africa', 'url': 'https://feeds.bbci.co.uk/news/world/africa/rss.xml', 'category': 'Africa'},
        {'name': 'AllAfrica', 'url': 'https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf', 'category': 'Africa'},
    ],
    'latin_america': [
        {'name': 'BBC Latin America', 'url': 'https://feeds.bbci.co.uk/news/world/latin_america/rss.xml', 'category': 'Latin America'},
        {'name': 'Reuters LatAm', 'url': 'https://feeds.reuters.com/reuters/latAmNews', 'category': 'Latin America'},
    ],
    'technology': [
        {'name': 'Ars Technica', 'url': 'https://feeds.arstechnica.com/arstechnica/technology-lab', 'category': 'Tech'},
        {'name': 'Hacker News', 'url': 'https://hnrss.org/frontpage', 'category': 'Tech'},
        {'name': 'The Verge', 'url': 'https://www.theverge.com/rss/index.xml', 'category': 'Tech'},
        {'name': 'TechCrunch', 'url': 'https://techcrunch.com/feed/', 'category': 'Tech'},
        {'name': 'VentureBeat', 'url': 'https://venturebeat.com/feed/', 'category': 'Tech'},
        {'name': 'MIT Tech Review', 'url': 'https://www.technologyreview.com/feed/', 'category': 'Tech'},
        {'name': 'Wired', 'url': 'https://www.wired.com/feed/rss', 'category': 'Tech'},
    ],
    'ai_ml': [
        {'name': 'ArXiv AI', 'url': 'https://export.arxiv.org/rss/cs.AI', 'category': 'AI/ML'},
        {'name': 'Google AI Blog', 'url': 'https://blog.google/technology/ai/rss/', 'category': 'AI/ML'},
        {'name': 'OpenAI Blog', 'url': 'https://openai.com/blog/rss.xml', 'category': 'AI/ML'},
    ],
    'science': [
        {'name': 'Nature News', 'url': 'https://www.nature.com/nature.rss', 'category': 'Science'},
        {'name': 'NASA Breaking', 'url': 'https://www.nasa.gov/rss/dyn/breaking_news.rss', 'category': 'Science'},
        {'name': 'Science Daily', 'url': 'https://www.sciencedaily.com/rss/all.xml', 'category': 'Science'},
        {'name': 'New Scientist', 'url': 'https://www.newscientist.com/feed/home', 'category': 'Science'},
    ],
    'security': [
        {'name': 'Krebs on Security', 'url': 'https://krebsonsecurity.com/feed/', 'category': 'Cyber'},
        {'name': 'The Hacker News', 'url': 'https://feeds.feedburner.com/TheHackersNews', 'category': 'Cyber'},
        {'name': 'BleepingComputer', 'url': 'https://www.bleepingcomputer.com/feed/', 'category': 'Cyber'},
        {'name': 'Dark Reading', 'url': 'https://www.darkreading.com/rss_simple.asp', 'category': 'Cyber'},
        {'name': 'CISA Advisories', 'url': 'https://www.cisa.gov/cybersecurity-advisories/all.xml', 'category': 'Cyber'},
        {'name': 'Threatpost', 'url': 'https://threatpost.com/feed/', 'category': 'Cyber'},
    ],
    'military_defense': [
        {'name': 'Defense One', 'url': 'https://www.defenseone.com/rss/', 'category': 'Defense'},
        {'name': 'War on the Rocks', 'url': 'https://warontherocks.com/feed/', 'category': 'Defense'},
        {'name': 'Breaking Defense', 'url': 'https://breakingdefense.com/feed/', 'category': 'Defense'},
        {'name': 'The Drive - War Zone', 'url': 'https://www.thedrive.com/the-war-zone/feed', 'category': 'Defense'},
        {'name': 'Defense News', 'url': 'https://www.defensenews.com/arc/outboundfeeds/rss/', 'category': 'Defense'},
        {'name': 'Task & Purpose', 'url': 'https://taskandpurpose.com/feed/', 'category': 'Defense'},
        {'name': 'gCaptain', 'url': 'https://gcaptain.com/feed/', 'category': 'Defense'},
        {'name': 'Oryx', 'url': 'https://www.oryxspioenkop.com/feeds/posts/default?alt=rss', 'category': 'Defense'},
    ],
    'disasters': [
        {'name': 'GDACS Alerts', 'url': 'https://www.gdacs.org/xml/rss.xml', 'category': 'Disaster'},
        {'name': 'ReliefWeb Updates', 'url': 'https://reliefweb.int/updates/rss.xml', 'category': 'Disaster'},
        {'name': 'FEMA', 'url': 'https://www.fema.gov/feeds/disasters-702-702all.xml', 'category': 'Disaster'},
        {'name': 'USGS Earthquake Hazards', 'url': 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.atom', 'category': 'Disaster'},
    ],
    'finance': [
        {'name': 'MarketWatch Top', 'url': 'https://feeds.content.dowjones.io/public/rss/mw_topstories', 'category': 'Finance'},
        {'name': 'CNBC Top News', 'url': 'https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114', 'category': 'Finance'},
        {'name': 'Bloomberg Markets', 'url': 'https://feeds.bloomberg.com/markets/news.rss', 'category': 'Finance'},
        {'name': 'Yahoo Finance', 'url': 'https://finance.yahoo.com/news/rssindex', 'category': 'Finance'},
        {'name': 'Seeking Alpha', 'url': 'https://seekingalpha.com/market_currents.xml', 'category': 'Finance'},
        {'name': 'Fed Reserve', 'url': 'https://www.federalreserve.gov/feeds/press_all.xml', 'category': 'Finance'},
        {'name': 'SEC Press', 'url': 'https://www.sec.gov/news/pressreleases.rss', 'category': 'Finance'},
    ],
    'crypto': [
        {'name': 'CoinDesk', 'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/', 'category': 'Crypto'},
        {'name': 'CoinTelegraph', 'url': 'https://cointelegraph.com/rss', 'category': 'Crypto'},
        {'name': 'Decrypt', 'url': 'https://decrypt.co/feed', 'category': 'Crypto'},
        {'name': 'The Defiant', 'url': 'https://thedefiant.io/feed', 'category': 'Crypto'},
        {'name': 'Bitcoin Magazine', 'url': 'https://bitcoinmagazine.com/feed', 'category': 'Crypto'},
    ],
    'energy': [
        {'name': 'EIA Today in Energy', 'url': 'https://www.eia.gov/rss/todayinenergy.xml', 'category': 'Energy'},
        {'name': 'OilPrice.com', 'url': 'https://oilprice.com/rss/main', 'category': 'Energy'},
        {'name': 'Rigzone', 'url': 'https://www.rigzone.com/news/rss/rigzone_latest.aspx', 'category': 'Energy'},
    ],
    'health': [
        {'name': 'WHO Disease Outbreaks', 'url': 'https://www.who.int/feeds/entity/don/en/rss.xml', 'category': 'Health'},
        {'name': 'CDC MMWR', 'url': 'https://tools.cdc.gov/api/v2/resources/media/316422.rss', 'category': 'Health'},
        {'name': 'CIDRAP News', 'url': 'https://www.cidrap.umn.edu/news/rss.xml', 'category': 'Health'},
        {'name': 'WHO News', 'url': 'https://www.who.int/rss-feeds/news-english.xml', 'category': 'Health'},
        {'name': 'IAEA', 'url': 'https://www.iaea.org/feeds/topnews', 'category': 'Health'},
    ],
    'geopolitics': [
        {'name': 'Foreign Affairs', 'url': 'https://www.foreignaffairs.com/rss.xml', 'category': 'Geopolitics'},
        {'name': 'The Diplomat', 'url': 'https://thediplomat.com/feed/', 'category': 'Geopolitics'},
        {'name': 'Foreign Policy', 'url': 'https://foreignpolicy.com/feed/', 'category': 'Geopolitics'},
        {'name': 'IISS', 'url': 'https://www.iiss.org/rss', 'category': 'Geopolitics'},
    ],
    'government': [
        {'name': 'White House', 'url': 'https://www.whitehouse.gov/feed/', 'category': 'Government'},
        {'name': 'State Dept', 'url': 'https://www.state.gov/rss-feed/press-releases/feed/', 'category': 'Government'},
        {'name': 'FAO News', 'url': 'https://www.fao.org/feeds/fao-newsroom-rss', 'category': 'Government'},
        {'name': 'DOD News', 'url': 'https://www.defense.gov/News/rss/', 'category': 'Government'},
        {'name': 'Treasury', 'url': 'https://home.treasury.gov/system/files/press-releases.xml', 'category': 'Government'},
        {'name': 'CISA News', 'url': 'https://www.cisa.gov/news.xml', 'category': 'Government'},
        {'name': 'UK MOD', 'url': 'https://www.gov.uk/government/organisations/ministry-of-defence.atom', 'category': 'Government'},
        {'name': 'EU External Action', 'url': 'https://www.eeas.europa.eu/eeas/rss_en', 'category': 'Government'},
    ],
    'startups_vc': [
        {'name': 'TechCrunch Startups', 'url': 'https://techcrunch.com/category/startups/feed/', 'category': 'Startups'},
        {'name': 'Crunchbase News', 'url': 'https://news.crunchbase.com/feed/', 'category': 'Startups'},
        {'name': 'Y Combinator Blog', 'url': 'https://www.ycombinator.com/blog/rss/', 'category': 'Startups'},
        {'name': 'PitchBook News', 'url': 'https://pitchbook.com/news/feed', 'category': 'Startups'},
        {'name': 'Sifted', 'url': 'https://sifted.eu/feed', 'category': 'Startups'},
    ],
    'osint': [
        {'name': 'BNO News', 'url': 'https://rsshub.app/telegram/channel/BNONews', 'category': 'OSINT'},
        {'name': 'NEXTA', 'url': 'https://rsshub.app/telegram/channel/nexta_live', 'category': 'OSINT'},
        {'name': 'OSINTdefender', 'url': 'https://rsshub.app/telegram/channel/OSINTdefender', 'category': 'OSINT'},
        {'name': 'Aurora Intel', 'url': 'https://rsshub.app/telegram/channel/AuroraIntel', 'category': 'OSINT'},
        {'name': 'Liveuamap', 'url': 'https://rsshub.app/telegram/channel/liveuamap', 'category': 'OSINT'},
        {'name': 'War Monitor', 'url': 'https://rsshub.app/telegram/channel/WarMonitors', 'category': 'OSINT'},
        {'name': 'Spectator Index', 'url': 'https://rsshub.app/telegram/channel/spectaborig', 'category': 'OSINT'},
        {'name': 'DeepState UA', 'url': 'https://rsshub.app/telegram/channel/DeepStateUA', 'category': 'OSINT'},
        {'name': 'Bellingcat', 'url': 'https://rsshub.app/telegram/channel/belaborig', 'category': 'OSINT'},
        {'name': 'Clash Report', 'url': 'https://rsshub.app/telegram/channel/claborig', 'category': 'OSINT'},
        {'name': 'ME Spectator', 'url': 'https://rsshub.app/telegram/channel/maborig', 'category': 'OSINT'},
        {'name': 'Osint Updates', 'url': 'https://rsshub.app/telegram/channel/OsintUpdates', 'category': 'OSINT'},
        {'name': 'DD Geopolitics', 'url': 'https://rsshub.app/telegram/channel/DDGeopolitics', 'category': 'OSINT'},
        {'name': 'The Hacker News TG', 'url': 'https://rsshub.app/telegram/channel/thehaborig', 'category': 'OSINT'},
        {'name': 'CyberWar', 'url': 'https://rsshub.app/telegram/channel/cyberaborig', 'category': 'OSINT'},
        {'name': 'FalconFeeds', 'url': 'https://rsshub.app/telegram/channel/FalconFeedsio', 'category': 'OSINT'},
        {'name': 'Geopolitics Prime', 'url': 'https://rsshub.app/telegram/channel/GeopoliticsPrime', 'category': 'OSINT'},
        {'name': 'OSINT Live', 'url': 'https://rsshub.app/telegram/channel/osaborig', 'category': 'OSINT'},
        {'name': 'Dragon Watch', 'url': 'https://rsshub.app/telegram/channel/DragonWatch', 'category': 'OSINT'},
        {'name': 'Dark Web Informer', 'url': 'https://rsshub.app/telegram/channel/DarkWebInformer', 'category': 'OSINT'},
        {'name': 'vx-underground', 'url': 'https://rsshub.app/telegram/channel/vaborig', 'category': 'OSINT'},
        {'name': 'Securelist', 'url': 'https://rsshub.app/telegram/channel/securelist', 'category': 'OSINT'},
        {'name': 'Middle East Observer', 'url': 'https://rsshub.app/telegram/channel/maborig', 'category': 'OSINT'},
        {'name': 'Lebanon Update', 'url': 'https://rsshub.app/telegram/channel/LebanonUpdate', 'category': 'OSINT'},
        {'name': 'Air Force Ukraine', 'url': 'https://rsshub.app/telegram/channel/kpszsu', 'category': 'OSINT'},
        {'name': 'Naya Iraq', 'url': 'https://rsshub.app/telegram/channel/NayaForIraq', 'category': 'OSINT'},
        {'name': 'Defender Dome', 'url': 'https://rsshub.app/telegram/channel/DefenderDome', 'category': 'OSINT'},
        {'name': 'OSINT Industries', 'url': 'https://rsshub.app/telegram/channel/OSINTIndustries', 'category': 'OSINT'},
        {'name': 'Iran Intl EN', 'url': 'https://rsshub.app/telegram/channel/IranIntlEN', 'category': 'OSINT'},
        {'name': 'Abu Ali Express', 'url': 'https://rsshub.app/telegram/channel/AbuAliExpress', 'category': 'OSINT'},
        {'name': 'Vahid Online', 'url': 'https://rsshub.app/telegram/channel/vahaborig', 'category': 'OSINT'},
        {'name': 'Witness', 'url': 'https://rsshub.app/telegram/channel/WitnessChannel', 'category': 'OSINT'},
        {'name': 'Yedioth News', 'url': 'https://rsshub.app/telegram/channel/yaborig', 'category': 'OSINT'},
        {'name': 'Fotros Resistance', 'url': 'https://rsshub.app/telegram/channel/fotaborig', 'category': 'OSINT'},
        {'name': 'Resistance Trench', 'url': 'https://rsshub.app/telegram/channel/ResistanceTrench', 'category': 'OSINT'},
        {'name': 'OsintTV', 'url': 'https://rsshub.app/telegram/channel/OsintTV', 'category': 'OSINT'},
        {'name': 'The Cradle', 'url': 'https://rsshub.app/telegram/channel/TheCradleMedia', 'category': 'OSINT'},
        {'name': 'Middle East Eye TG', 'url': 'https://rsshub.app/telegram/channel/MiddleEastEye', 'category': 'OSINT'},
        {'name': 'Cybersecurity Boardroom', 'url': 'https://rsshub.app/telegram/channel/CyberBoardroom', 'category': 'OSINT'},
        {'name': 'The CyberWire TG', 'url': 'https://rsshub.app/telegram/channel/thecyberwire', 'category': 'OSINT'},
        {'name': 'war_monitor UA', 'url': 'https://rsshub.app/telegram/channel/war_monitor_ua', 'category': 'OSINT'},
        {'name': 'Intel Slava Z', 'url': 'https://rsshub.app/telegram/channel/intelslava', 'category': 'OSINT'},
        {'name': 'Rybar', 'url': 'https://rsshub.app/telegram/channel/rybar', 'category': 'OSINT'},
    ],
    'think_tanks': [
        {'name': 'Atlantic Council', 'url': 'https://www.atlanticcouncil.org/feed/', 'category': 'Think Tanks'},
        {'name': 'CSIS Analysis', 'url': 'https://www.csis.org/analysis/feed', 'category': 'Think Tanks'},
        {'name': 'Brookings', 'url': 'https://www.brookings.edu/feed/', 'category': 'Think Tanks'},
        {'name': 'Carnegie', 'url': 'https://carnegieendowment.org/rss/solr/?lang=en', 'category': 'Think Tanks'},
        {'name': 'RAND', 'url': 'https://www.rand.org/blog.xml', 'category': 'Think Tanks'},
        {'name': 'CrisisWatch (ICG)', 'url': 'https://www.crisisgroup.org/crisiswatch/feed', 'category': 'Think Tanks'},
        {'name': 'Chatham House', 'url': 'https://www.chathamhouse.org/rss', 'category': 'Think Tanks'},
        {'name': 'Council on Foreign Relations', 'url': 'https://www.cfr.org/rss/news', 'category': 'Think Tanks'},
    ],
    'commodities': [
        {'name': 'Mining.com', 'url': 'https://www.mining.com/feed/', 'category': 'Commodities'},
        {'name': 'Mining Technology', 'url': 'https://www.mining-technology.com/feed/', 'category': 'Commodities'},
        {'name': 'Australian Mining', 'url': 'https://www.australianmining.com.au/feed/', 'category': 'Commodities'},
    ],
    'regional_intl': [
        {'name': 'BBC Mundo', 'url': 'https://feeds.bbci.co.uk/mundo/rss.xml', 'category': 'Latin America'},
        {'name': 'El Pais', 'url': 'https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada', 'category': 'Latin America'},
        {'name': 'Tagesschau', 'url': 'https://www.tagesschau.de/xml/rss2/', 'category': 'Europe'},
        {'name': 'NOS Nieuws', 'url': 'https://feeds.nos.nl/nosnieuwsalgemeen', 'category': 'Europe'},
        {'name': 'SVT Nyheter', 'url': 'https://www.svt.se/nyheter/rss.xml', 'category': 'Europe'},
        {'name': 'BBC Turkce', 'url': 'https://feeds.bbci.co.uk/turkce/rss.xml', 'category': 'Middle East'},
        {'name': 'Meduza EN', 'url': 'https://meduza.io/rss/en/all', 'category': 'Europe'},
        {'name': 'Kyiv Independent', 'url': 'https://kyivindependent.com/feed/', 'category': 'Europe'},
        {'name': 'Japan Times', 'url': 'https://www.japantimes.co.jp/feed/', 'category': 'Asia-Pacific'},
        {'name': 'Straits Times', 'url': 'https://www.straitstimes.com/news/asia/rss.xml', 'category': 'Asia-Pacific'},
        {'name': 'Times of India', 'url': 'https://timesofindia.indiatimes.com/rssfeedstopstories.cms', 'category': 'Asia-Pacific'},
        {'name': 'News24 SA', 'url': 'https://feeds.24.com/articles/news24/TopStories/rss', 'category': 'Africa'},
        {'name': 'Punch Nigeria', 'url': 'https://punchng.com/feed/', 'category': 'Africa'},
        {'name': 'Buenos Aires Times', 'url': 'https://www.batimes.com.ar/feed', 'category': 'Latin America'},
        # Expanded regional language feeds (P7)
        {'name': 'Le Monde', 'url': 'https://www.lemonde.fr/rss/une.xml', 'category': 'Europe'},
        {'name': 'Die Welt', 'url': 'https://www.welt.de/feeds/latest.rss', 'category': 'Europe'},
        {'name': 'Corriere della Sera', 'url': 'https://xml2.corrieredellasera.it/rss/homepage.xml', 'category': 'Europe'},
        {'name': 'Asahi Shimbun', 'url': 'https://www.asahi.com/ajw/rss.xml', 'category': 'Asia-Pacific'},
        {'name': 'Yonhap (Korea)', 'url': 'https://en.yna.co.kr/RSS/news.xml', 'category': 'Asia-Pacific'},
        {'name': 'NDTV India', 'url': 'https://feeds.feedburner.com/ndtvnews-top-stories', 'category': 'Asia-Pacific'},
        {'name': 'Dawn Pakistan', 'url': 'https://www.dawn.com/feed', 'category': 'Asia-Pacific'},
        {'name': 'Bangkok Post', 'url': 'https://www.bangkokpost.com/rss/data/topstories.xml', 'category': 'Asia-Pacific'},
        {'name': 'VnExpress Intl', 'url': 'https://e.vnexpress.net/rss/news/latest.rss', 'category': 'Asia-Pacific'},
        {'name': 'Haaretz', 'url': 'https://www.haaretz.com/cmlink/1.628765', 'category': 'Middle East'},
        {'name': 'Arab News', 'url': 'https://www.arabnews.com/rss.xml', 'category': 'Middle East'},
        {'name': 'Tehran Times', 'url': 'https://www.tehrantimes.com/rss', 'category': 'Middle East'},
        {'name': 'Daily Sabah', 'url': 'https://www.dailysabah.com/rssFeed/todays-headlines', 'category': 'Middle East'},
        {'name': 'Folha de S.Paulo', 'url': 'https://feeds.folha.uol.com.br/mundo/rss091.xml', 'category': 'Latin America'},
        {'name': 'Mexico News Daily', 'url': 'https://mexiconewsdaily.com/feed/', 'category': 'Latin America'},
        {'name': 'Daily Nation Kenya', 'url': 'https://nation.africa/rss/news', 'category': 'Africa'},
        {'name': 'The East African', 'url': 'https://www.theeastafrican.co.ke/rss', 'category': 'Africa'},
        {'name': 'Mail & Guardian SA', 'url': 'https://mg.co.za/feed/', 'category': 'Africa'},
        {'name': 'Nikkei Asia', 'url': 'https://asia.nikkei.com/rss', 'category': 'Asia-Pacific'},
        {'name': 'South China Morning Post', 'url': 'https://www.scmp.com/rss/91/feed', 'category': 'Asia-Pacific'},
        {'name': 'Kathimerini (Greece)', 'url': 'https://www.ekathimerini.com/rss', 'category': 'Europe'},
        {'name': 'Aftenposten (Norway)', 'url': 'https://www.aftenposten.no/rss', 'category': 'Europe'},
        {'name': 'RBC (Russia)', 'url': 'https://rssexport.rbc.ru/rbcnews/news/30/full.rss', 'category': 'Europe'},
        {'name': 'Globo (Brazil)', 'url': 'https://g1.globo.com/rss/g1/', 'category': 'Latin America'},
    ],
    'layoffs': [
        {'name': 'Layoffs.fyi', 'url': 'https://layoffs.fyi/feed/', 'category': 'Layoffs'},
    ],
    'semiconductors': [
        {'name': 'SemiEngineering', 'url': 'https://semiengineering.com/feed/', 'category': 'Semiconductors'},
        {'name': 'EE Times', 'url': 'https://www.eetimes.com/feed/', 'category': 'Semiconductors'},
        {'name': 'AnandTech', 'url': 'https://www.anandtech.com/rss/', 'category': 'Semiconductors'},
    ],
    'nuclear_energy': [
        {'name': 'World Nuclear News', 'url': 'https://www.world-nuclear-news.org/rss', 'category': 'Nuclear'},
        {'name': 'IAEA News', 'url': 'https://www.iaea.org/feeds/topnews', 'category': 'Nuclear'},
    ],
    'maritime': [
        {'name': 'gCaptain', 'url': 'https://gcaptain.com/feed/', 'category': 'Maritime'},
        {'name': 'Maritime Executive', 'url': 'https://maritime-executive.com/rss', 'category': 'Maritime'},
        {'name': 'Splash247', 'url': 'https://splash247.com/feed/', 'category': 'Maritime'},
    ],
    'space': [
        {'name': 'SpaceNews', 'url': 'https://spacenews.com/feed/', 'category': 'Space'},
        {'name': 'Spaceflight Now', 'url': 'https://spaceflightnow.com/feed/', 'category': 'Space'},
        {'name': 'NASA Spaceflight', 'url': 'https://www.nasaspaceflight.com/feed/', 'category': 'Space'},
    ],
    'good_news': [
        {'name': 'Good News Network', 'url': 'https://www.goodnewsnetwork.org/feed/', 'category': 'Good News'},
        {'name': 'Positive News', 'url': 'https://www.positive.news/feed/', 'category': 'Good News'},
        {'name': 'Reasons to be Cheerful', 'url': 'https://reasonstobecheerful.world/feed/', 'category': 'Good News'},
    ],
    'conservation': [
        {'name': 'Mongabay', 'url': 'https://news.mongabay.com/feed/', 'category': 'Conservation'},
        {'name': 'Conservation Intl', 'url': 'https://www.conservation.org/blog/rss', 'category': 'Conservation'},
    ],
    'cloud_infra': [
        {'name': 'The New Stack', 'url': 'https://thenewstack.io/feed/', 'category': 'Cloud'},
        {'name': 'InfoQ', 'url': 'https://feed.infoq.com/', 'category': 'Cloud'},
        {'name': 'DevOps.com', 'url': 'https://devops.com/feed/', 'category': 'Cloud'},
    ],
    'developer': [
        {'name': 'Dev.to', 'url': 'https://dev.to/feed', 'category': 'Developer'},
        {'name': 'Lobsters', 'url': 'https://lobste.rs/rss', 'category': 'Developer'},
        {'name': 'GitHub Blog', 'url': 'https://github.blog/feed/', 'category': 'Developer'},
    ],
    'supply_chain': [
        {'name': 'Supply Chain Dive', 'url': 'https://www.supplychaindive.com/feeds/news/', 'category': 'Supply Chain'},
        {'name': 'Freightwaves', 'url': 'https://www.freightwaves.com/feed', 'category': 'Supply Chain'},
    ],
    # ─── Google News RSS Proxies (WM-style, ~100 additional feeds) ───
    'gn_world': [
        {'name': 'GN World', 'url': 'https://news.google.com/rss/search?q=world+news&hl=en-US&gl=US&ceid=US:en', 'category': 'World'},
        {'name': 'GN Ukraine', 'url': 'https://news.google.com/rss/search?q=ukraine+war&hl=en-US', 'category': 'World'},
        {'name': 'GN China', 'url': 'https://news.google.com/rss/search?q=china+geopolitics&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Russia', 'url': 'https://news.google.com/rss/search?q=russia+news&hl=en-US', 'category': 'Europe'},
        {'name': 'GN Iran', 'url': 'https://news.google.com/rss/search?q=iran+news&hl=en-US', 'category': 'Middle East'},
        {'name': 'GN India', 'url': 'https://news.google.com/rss/search?q=india+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Taiwan', 'url': 'https://news.google.com/rss/search?q=taiwan+strait&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN North Korea', 'url': 'https://news.google.com/rss/search?q=north+korea&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Israel Palestine', 'url': 'https://news.google.com/rss/search?q=israel+palestine&hl=en-US', 'category': 'Middle East'},
        {'name': 'GN Syria', 'url': 'https://news.google.com/rss/search?q=syria+news&hl=en-US', 'category': 'Middle East'},
        {'name': 'GN Sudan', 'url': 'https://news.google.com/rss/search?q=sudan+conflict&hl=en-US', 'category': 'Africa'},
        {'name': 'GN Yemen', 'url': 'https://news.google.com/rss/search?q=yemen+houthi&hl=en-US', 'category': 'Middle East'},
    ],
    'gn_defense': [
        {'name': 'GN NATO', 'url': 'https://news.google.com/rss/search?q=NATO+military&hl=en-US', 'category': 'Defense'},
        {'name': 'GN Pentagon', 'url': 'https://news.google.com/rss/search?q=pentagon+defense&hl=en-US', 'category': 'Defense'},
        {'name': 'GN Missile Defense', 'url': 'https://news.google.com/rss/search?q=missile+defense+system&hl=en-US', 'category': 'Defense'},
        {'name': 'GN Navy', 'url': 'https://news.google.com/rss/search?q=navy+warship+fleet&hl=en-US', 'category': 'Defense'},
        {'name': 'GN Air Force', 'url': 'https://news.google.com/rss/search?q=air+force+fighter+jet&hl=en-US', 'category': 'Defense'},
        {'name': 'GN Arms Trade', 'url': 'https://news.google.com/rss/search?q=arms+deal+weapons+sale&hl=en-US', 'category': 'Defense'},
        {'name': 'GN Cyber Warfare', 'url': 'https://news.google.com/rss/search?q=cyber+warfare+state+sponsored&hl=en-US', 'category': 'Cyber'},
        {'name': 'GN Nuclear Weapons', 'url': 'https://news.google.com/rss/search?q=nuclear+weapons+treaty&hl=en-US', 'category': 'Nuclear'},
    ],
    'gn_finance': [
        {'name': 'GN Fed Reserve', 'url': 'https://news.google.com/rss/search?q=federal+reserve+interest+rate&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Stock Market', 'url': 'https://news.google.com/rss/search?q=stock+market+wall+street&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Recession', 'url': 'https://news.google.com/rss/search?q=recession+economy&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Inflation', 'url': 'https://news.google.com/rss/search?q=inflation+cpi+prices&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Crypto Market', 'url': 'https://news.google.com/rss/search?q=cryptocurrency+bitcoin+ethereum&hl=en-US', 'category': 'Crypto'},
        {'name': 'GN Oil Price', 'url': 'https://news.google.com/rss/search?q=oil+price+opec+crude&hl=en-US', 'category': 'Energy'},
        {'name': 'GN Gold Price', 'url': 'https://news.google.com/rss/search?q=gold+price+precious+metals&hl=en-US', 'category': 'Commodities'},
        {'name': 'GN Trade War', 'url': 'https://news.google.com/rss/search?q=trade+war+tariffs&hl=en-US', 'category': 'Finance'},
    ],
    'gn_tech': [
        {'name': 'GN AI News', 'url': 'https://news.google.com/rss/search?q=artificial+intelligence+AI&hl=en-US', 'category': 'AI/ML'},
        {'name': 'GN Semiconductors', 'url': 'https://news.google.com/rss/search?q=semiconductor+chip+TSMC+nvidia&hl=en-US', 'category': 'Semiconductors'},
        {'name': 'GN SpaceX', 'url': 'https://news.google.com/rss/search?q=spacex+starship+rocket+launch&hl=en-US', 'category': 'Space'},
        {'name': 'GN Quantum', 'url': 'https://news.google.com/rss/search?q=quantum+computing&hl=en-US', 'category': 'Tech'},
        {'name': 'GN Robotics', 'url': 'https://news.google.com/rss/search?q=robotics+autonomous&hl=en-US', 'category': 'Tech'},
        {'name': 'GN EV', 'url': 'https://news.google.com/rss/search?q=electric+vehicle+tesla+ev&hl=en-US', 'category': 'Tech'},
        {'name': 'GN Cybersecurity', 'url': 'https://news.google.com/rss/search?q=cybersecurity+breach+ransomware&hl=en-US', 'category': 'Cyber'},
        {'name': 'GN Data Privacy', 'url': 'https://news.google.com/rss/search?q=data+privacy+gdpr+surveillance&hl=en-US', 'category': 'Tech'},
    ],
    'gn_disaster': [
        {'name': 'GN Earthquake', 'url': 'https://news.google.com/rss/search?q=earthquake+magnitude&hl=en-US', 'category': 'Disaster'},
        {'name': 'GN Hurricane', 'url': 'https://news.google.com/rss/search?q=hurricane+typhoon+cyclone&hl=en-US', 'category': 'Disaster'},
        {'name': 'GN Wildfire', 'url': 'https://news.google.com/rss/search?q=wildfire+forest+fire&hl=en-US', 'category': 'Disaster'},
        {'name': 'GN Flood', 'url': 'https://news.google.com/rss/search?q=flood+flooding+dam&hl=en-US', 'category': 'Disaster'},
        {'name': 'GN Volcano', 'url': 'https://news.google.com/rss/search?q=volcano+eruption&hl=en-US', 'category': 'Disaster'},
        {'name': 'GN Tsunami', 'url': 'https://news.google.com/rss/search?q=tsunami+warning&hl=en-US', 'category': 'Disaster'},
        {'name': 'GN Pandemic', 'url': 'https://news.google.com/rss/search?q=pandemic+outbreak+virus&hl=en-US', 'category': 'Health'},
        {'name': 'GN Climate', 'url': 'https://news.google.com/rss/search?q=climate+change+global+warming&hl=en-US', 'category': 'Science'},
    ],
    'gn_energy': [
        {'name': 'GN Solar', 'url': 'https://news.google.com/rss/search?q=solar+energy+panel&hl=en-US', 'category': 'Renewable'},
        {'name': 'GN Wind Power', 'url': 'https://news.google.com/rss/search?q=wind+energy+turbine&hl=en-US', 'category': 'Renewable'},
        {'name': 'GN Nuclear Power', 'url': 'https://news.google.com/rss/search?q=nuclear+power+plant+reactor&hl=en-US', 'category': 'Nuclear'},
        {'name': 'GN Natural Gas', 'url': 'https://news.google.com/rss/search?q=natural+gas+LNG&hl=en-US', 'category': 'Energy'},
        {'name': 'GN Hydrogen', 'url': 'https://news.google.com/rss/search?q=hydrogen+fuel+cell&hl=en-US', 'category': 'Renewable'},
        {'name': 'GN Battery', 'url': 'https://news.google.com/rss/search?q=battery+storage+lithium&hl=en-US', 'category': 'Tech'},
    ],
    'gn_health': [
        {'name': 'GN Vaccine', 'url': 'https://news.google.com/rss/search?q=vaccine+immunization&hl=en-US', 'category': 'Health'},
        {'name': 'GN WHO', 'url': 'https://news.google.com/rss/search?q=world+health+organization&hl=en-US', 'category': 'Health'},
        {'name': 'GN Drug Discovery', 'url': 'https://news.google.com/rss/search?q=drug+discovery+fda+approval&hl=en-US', 'category': 'Health'},
        {'name': 'GN Mental Health', 'url': 'https://news.google.com/rss/search?q=mental+health+wellbeing&hl=en-US', 'category': 'Health'},
    ],
    'gn_regions': [
        {'name': 'GN Japan', 'url': 'https://news.google.com/rss/search?q=japan+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN South Korea', 'url': 'https://news.google.com/rss/search?q=south+korea+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Australia', 'url': 'https://news.google.com/rss/search?q=australia+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Brazil', 'url': 'https://news.google.com/rss/search?q=brazil+news&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Mexico', 'url': 'https://news.google.com/rss/search?q=mexico+news&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Turkey', 'url': 'https://news.google.com/rss/search?q=turkey+erdogan&hl=en-US', 'category': 'Middle East'},
        {'name': 'GN Pakistan', 'url': 'https://news.google.com/rss/search?q=pakistan+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Nigeria', 'url': 'https://news.google.com/rss/search?q=nigeria+news&hl=en-US', 'category': 'Africa'},
        {'name': 'GN South Africa', 'url': 'https://news.google.com/rss/search?q=south+africa+news&hl=en-US', 'category': 'Africa'},
        {'name': 'GN Egypt', 'url': 'https://news.google.com/rss/search?q=egypt+news&hl=en-US', 'category': 'Middle East'},
        {'name': 'GN Germany', 'url': 'https://news.google.com/rss/search?q=germany+news&hl=en-US', 'category': 'Europe'},
        {'name': 'GN France', 'url': 'https://news.google.com/rss/search?q=france+news&hl=en-US', 'category': 'Europe'},
        {'name': 'GN UK Politics', 'url': 'https://news.google.com/rss/search?q=UK+politics+parliament&hl=en-US', 'category': 'Europe'},
        {'name': 'GN Poland', 'url': 'https://news.google.com/rss/search?q=poland+news&hl=en-US', 'category': 'Europe'},
        {'name': 'GN Indonesia', 'url': 'https://news.google.com/rss/search?q=indonesia+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Philippines', 'url': 'https://news.google.com/rss/search?q=philippines+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Vietnam', 'url': 'https://news.google.com/rss/search?q=vietnam+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Thailand', 'url': 'https://news.google.com/rss/search?q=thailand+news&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Ethiopia', 'url': 'https://news.google.com/rss/search?q=ethiopia+news&hl=en-US', 'category': 'Africa'},
        {'name': 'GN Congo', 'url': 'https://news.google.com/rss/search?q=congo+DRC+news&hl=en-US', 'category': 'Africa'},
        {'name': 'GN Venezuela', 'url': 'https://news.google.com/rss/search?q=venezuela+news&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Colombia', 'url': 'https://news.google.com/rss/search?q=colombia+news&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Argentina', 'url': 'https://news.google.com/rss/search?q=argentina+milei&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Bangladesh', 'url': 'https://news.google.com/rss/search?q=bangladesh+news&hl=en-US', 'category': 'Asia-Pacific'},
    ],
    'gn_sectors': [
        {'name': 'GN Biotech', 'url': 'https://news.google.com/rss/search?q=biotech+pharmaceutical&hl=en-US', 'category': 'Health'},
        {'name': 'GN Real Estate', 'url': 'https://news.google.com/rss/search?q=real+estate+housing+market&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Insurance', 'url': 'https://news.google.com/rss/search?q=insurance+industry&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Retail', 'url': 'https://news.google.com/rss/search?q=retail+consumer+spending&hl=en-US', 'category': 'Finance'},
        {'name': 'GN Agriculture', 'url': 'https://news.google.com/rss/search?q=agriculture+farming+crop&hl=en-US', 'category': 'Commodities'},
        {'name': 'GN Rare Earth', 'url': 'https://news.google.com/rss/search?q=rare+earth+minerals+mining&hl=en-US', 'category': 'Commodities'},
        {'name': 'GN Shipping', 'url': 'https://news.google.com/rss/search?q=shipping+container+freight&hl=en-US', 'category': 'Maritime'},
        {'name': 'GN Telecom', 'url': 'https://news.google.com/rss/search?q=telecom+5G+broadband&hl=en-US', 'category': 'Tech'},
        {'name': 'GN Cloud', 'url': 'https://news.google.com/rss/search?q=cloud+computing+AWS+Azure&hl=en-US', 'category': 'Cloud'},
        {'name': 'GN Gaming', 'url': 'https://news.google.com/rss/search?q=gaming+industry+console&hl=en-US', 'category': 'Tech'},
    ],
    'gn_misc': [
        {'name': 'GN Immigration', 'url': 'https://news.google.com/rss/search?q=immigration+border+refugee&hl=en-US', 'category': 'World'},
        {'name': 'GN Election', 'url': 'https://news.google.com/rss/search?q=election+vote+democracy&hl=en-US', 'category': 'Geopolitics'},
        {'name': 'GN Corruption', 'url': 'https://news.google.com/rss/search?q=corruption+scandal+investigation&hl=en-US', 'category': 'Geopolitics'},
        {'name': 'GN Human Rights', 'url': 'https://news.google.com/rss/search?q=human+rights+violation&hl=en-US', 'category': 'World'},
        {'name': 'GN Sanctions', 'url': 'https://news.google.com/rss/search?q=sanctions+embargo&hl=en-US', 'category': 'Geopolitics'},
        {'name': 'GN Supply Chain', 'url': 'https://news.google.com/rss/search?q=supply+chain+disruption+shortage&hl=en-US', 'category': 'Supply Chain'},
        {'name': 'GN Food Security', 'url': 'https://news.google.com/rss/search?q=food+security+famine+hunger&hl=en-US', 'category': 'World'},
        {'name': 'GN Water Crisis', 'url': 'https://news.google.com/rss/search?q=water+crisis+drought&hl=en-US', 'category': 'World'},
    ],
    'gn_final': [
        {'name': 'GN Myanmar', 'url': 'https://news.google.com/rss/search?q=myanmar+military+junta&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Afghanistan', 'url': 'https://news.google.com/rss/search?q=afghanistan+taliban&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Libya', 'url': 'https://news.google.com/rss/search?q=libya+news&hl=en-US', 'category': 'Africa'},
        {'name': 'GN Somalia', 'url': 'https://news.google.com/rss/search?q=somalia+al+shabaab&hl=en-US', 'category': 'Africa'},
        {'name': 'GN Haiti', 'url': 'https://news.google.com/rss/search?q=haiti+crisis&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Cuba', 'url': 'https://news.google.com/rss/search?q=cuba+news&hl=en-US', 'category': 'Latin America'},
        {'name': 'GN Kazakhstan', 'url': 'https://news.google.com/rss/search?q=kazakhstan+central+asia&hl=en-US', 'category': 'Asia-Pacific'},
        {'name': 'GN Arctic', 'url': 'https://news.google.com/rss/search?q=arctic+ice+polar&hl=en-US', 'category': 'Science'},
        {'name': 'GN Disinformation', 'url': 'https://news.google.com/rss/search?q=disinformation+misinformation+deepfake&hl=en-US', 'category': 'Cyber'},
        {'name': 'GN Space Debris', 'url': 'https://news.google.com/rss/search?q=space+debris+satellite+orbit&hl=en-US', 'category': 'Space'},
        {'name': 'GN Drones', 'url': 'https://news.google.com/rss/search?q=drone+UAV+unmanned&hl=en-US', 'category': 'Defense'},
        {'name': 'GN AUKUS', 'url': 'https://news.google.com/rss/search?q=AUKUS+submarine&hl=en-US', 'category': 'Defense'},
        {'name': 'GN BRICS', 'url': 'https://news.google.com/rss/search?q=BRICS+summit+expansion&hl=en-US', 'category': 'Geopolitics'},
        {'name': 'GN Belt Road', 'url': 'https://news.google.com/rss/search?q=belt+road+initiative+BRI&hl=en-US', 'category': 'Geopolitics'},
        {'name': 'GN Lithium', 'url': 'https://news.google.com/rss/search?q=lithium+cobalt+critical+mineral&hl=en-US', 'category': 'Commodities'},
        {'name': 'GN Uranium', 'url': 'https://news.google.com/rss/search?q=uranium+price+nuclear+fuel&hl=en-US', 'category': 'Commodities'},
        {'name': 'GN Central Bank Digital', 'url': 'https://news.google.com/rss/search?q=CBDC+digital+currency+central+bank&hl=en-US', 'category': 'Crypto'},
        {'name': 'GN Defi', 'url': 'https://news.google.com/rss/search?q=defi+decentralized+finance&hl=en-US', 'category': 'Crypto'},
        {'name': 'GN NFT Web3', 'url': 'https://news.google.com/rss/search?q=NFT+web3+metaverse&hl=en-US', 'category': 'Crypto'},
        {'name': 'GN Medical AI', 'url': 'https://news.google.com/rss/search?q=medical+AI+diagnosis+healthcare+AI&hl=en-US', 'category': 'AI/ML'},
        {'name': 'GN Autonomous', 'url': 'https://news.google.com/rss/search?q=autonomous+vehicle+self+driving&hl=en-US', 'category': 'Tech'},
        {'name': 'GN 3D Printing', 'url': 'https://news.google.com/rss/search?q=3D+printing+additive+manufacturing&hl=en-US', 'category': 'Tech'},
        {'name': 'GN Lab Meat', 'url': 'https://news.google.com/rss/search?q=lab+grown+meat+cultivated&hl=en-US', 'category': 'Science'},
        {'name': 'GN Gene Therapy', 'url': 'https://news.google.com/rss/search?q=gene+therapy+CRISPR+genome&hl=en-US', 'category': 'Health'},
        {'name': 'GN Antimicrobial', 'url': 'https://news.google.com/rss/search?q=antimicrobial+resistance+superbug&hl=en-US', 'category': 'Health'},
        {'name': 'GN Education', 'url': 'https://news.google.com/rss/search?q=education+reform+university&hl=en-US', 'category': 'World'},
        {'name': 'GN Poverty', 'url': 'https://news.google.com/rss/search?q=poverty+inequality+wealth+gap&hl=en-US', 'category': 'World'},
        {'name': 'GN Deforestation', 'url': 'https://news.google.com/rss/search?q=deforestation+rainforest+amazon&hl=en-US', 'category': 'Conservation'},
        {'name': 'GN Ocean', 'url': 'https://news.google.com/rss/search?q=ocean+pollution+marine&hl=en-US', 'category': 'Conservation'},
        {'name': 'GN Extinction', 'url': 'https://news.google.com/rss/search?q=endangered+species+extinction&hl=en-US', 'category': 'Conservation'},
    ],
}

ALL_FEEDS = []
for _cat_feeds in RSS_FEEDS.values():
    ALL_FEEDS.extend(_cat_feeds)
FEED_CATEGORIES = sorted(set(f['category'] for f in ALL_FEEDS))


# ─── RSS/Atom Parser ──────────────────────────────────────────────────
def _parse_feed(xml_text, feed_name, feed_category):
    items = []
    # Defuse against billion-laughs — stdlib ElementTree still expands
    # internal entity declarations. RSS/Atom never legitimately ships
    # with a DOCTYPE, so refusing one up-front closes a memory-blowup
    # vector for feeds that are user-configurable. Same guard pattern
    # as the GPX importers in maps.py + interoperability.py.
    if isinstance(xml_text, str):
        head = xml_text.lstrip()[:1024].lower()
        if '<!doctype' in head or '<!entity' in head:
            log.debug('Refusing RSS feed %s — contains DOCTYPE/ENTITY declaration', feed_name)
            return items
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
    """Fetch a single RSS feed. Returns list of articles.

    Narrowed from bare ``Exception`` to the real fetch+parse surface:
    ``requests.RequestException`` for network/HTTP issues, ``ET.ParseError``
    bubbles up from ``_parse_feed`` on malformed XML, ``ValueError`` for text
    decode errors, and ``KeyError``/``AttributeError`` cover feeds with
    missing/unexpected fields. A bug elsewhere (e.g. a NameError in our own
    parser) will surface loudly instead of being swallowed per-feed.
    """
    resp = None
    try:
        resp = _http_session.get(feed['url'], timeout=_REQ_TIMEOUT, headers={
            **_REQ_HEADERS, 'Accept': 'application/rss+xml, application/xml, text/xml'})
        if resp.ok:
            return _parse_feed(resp.text, feed['name'], feed['category'])
    except (requests.RequestException, ET.ParseError, ValueError,
            KeyError, AttributeError) as e:
        log.debug(f"RSS fetch failed for {feed['name']}: {e}")
    finally:
        # Explicit close — the pooled ``requests.Session`` normally returns
        # the connection to the pool on GC, but on an import-day storm of
        # 50+ feeds per refresh that can leak sockets for seconds before
        # GC runs. close() itself should never raise meaningfully, but we
        # keep the broad except here because a socket-shutdown error must
        # not mask a real fetch error from the caller above.
        if resp is not None:
            try:
                resp.close()
            except Exception:
                pass
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
    except Exception as e:
        log.warning('Failed to load custom feeds from DB: %s', e)
    articles = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_single_feed, f): f for f in feeds}
        for fut in as_completed(futures, timeout=90):
            try:
                articles.extend(fut.result())
            except Exception as e:
                feed = futures.get(fut)
                feed_name = feed.get('name', '?') if feed else '?'
                log.debug('RSS fetch worker failed for %s: %s', feed_name, e)

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
        resp = _fetch_with_retry('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson',
                                 timeout=15, headers=_REQ_HEADERS)
        data = _safe_response_json(resp, {})
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"Earthquake fetch failed: {e}")
        return

    if not isinstance(data, dict):
        return
    features = data.get('features', [])[:100]
    batch_ts = datetime.now().isoformat()
    with db_session() as db:
        for f in features:
            props = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [0, 0, 0])
            db.execute('''INSERT OR REPLACE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, depth_km, event_time, source_url, detail_json, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (f.get('id', ''), 'earthquake', props.get('place', ''),
                 props.get('mag'), coords[1] if len(coords) > 1 else 0,
                 coords[0] if coords else 0, coords[2] if len(coords) > 2 else 0,
                 props.get('time', 0), props.get('url', ''),
                 json.dumps({'tsunami': props.get('tsunami'), 'alert': props.get('alert'),
                             'felt': props.get('felt'), 'sig': props.get('sig')}),
                 batch_ts))
        db.commit()
        # Remove stale rows from previous batches
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'earthquake' AND (cached_at IS NULL OR cached_at < ?)", (batch_ts,))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} earthquakes")


def _fetch_weather_alerts():
    if not _can_fetch('weather_alerts'):
        return
    _set_last_fetch('weather_alerts')
    try:
        resp = _fetch_with_retry('https://api.weather.gov/alerts/active?status=actual&severity=Extreme,Severe',
                                 timeout=15, headers={**_REQ_HEADERS, 'Accept': 'application/geo+json'})
        data = _safe_response_json(resp, {})
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"Weather alerts fetch failed: {e}")
        return

    if not isinstance(data, dict):
        return
    features = data.get('features', [])[:200]
    batch_ts = datetime.now().isoformat()
    with db_session() as db:
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
            db.execute('''INSERT OR REPLACE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (event_id, 'weather_alert',
                 f"{props.get('event', '')} - {props.get('areaDesc', '')}",
                 lat, lng, onset_ms, props.get('id', ''),
                 json.dumps({
                     'severity': props.get('severity'), 'certainty': props.get('certainty'),
                     'urgency': props.get('urgency'), 'headline': (props.get('headline') or '')[:500],
                     'description': (props.get('description') or '')[:2000],
                     'instruction': (props.get('instruction') or '')[:1000],
                     'sender': props.get('senderName', ''), 'expires': props.get('expires', ''),
                 }),
                 batch_ts))
        db.commit()
        # Remove stale rows from previous batches
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'weather_alert' AND (cached_at IS NULL OR cached_at < ?)", (batch_ts,))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} weather alerts")


def _fetch_market_data():
    if not _can_fetch('markets'):
        return
    _set_last_fetch('markets')
    markets = []

    # Yahoo Finance — stock indices + forex pairs
    yf_symbols = {
        '^GSPC': 'S&P 500', '^IXIC': 'NASDAQ', '^DJI': 'DOW JONES',
        '^FTSE': 'FTSE 100', '^GDAXI': 'DAX', '^N225': 'NIKKEI 225',
        '^HSI': 'HANG SENG', '^STOXX50E': 'EURO STOXX 50',
        'EURUSD=X': 'EUR/USD', 'GBPUSD=X': 'GBP/USD', 'USDJPY=X': 'USD/JPY',
        'DX-Y.NYB': 'DXY (USD)',
    }
    for sym, name in yf_symbols.items():
        try:
            resp = _http_session.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}',
                                params={'range': '1d', 'interval': '5m'}, timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
            if resp.ok:
                payload = _safe_response_json(resp, {})
                meta = payload.get('chart', {}).get('result', [{}])[0].get('meta', {}) if isinstance(payload, dict) else {}
                if not isinstance(meta, dict) or not meta:
                    continue
                price = meta.get('regularMarketPrice', 0)
                prev = meta.get('previousClose', 0)
                change = ((price - prev) / prev * 100) if prev else 0
                mtype = 'forex' if '/' in name or 'DXY' in name else 'index'
                markets.append({'symbol': name, 'price': price, 'change_24h': round(change, 2), 'market_type': mtype})
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
            log.debug(f"Yahoo Finance {sym} failed: {e}")

    # Sector ETFs via Yahoo Finance
    sector_symbols = {
        'XLK': 'Tech', 'XLF': 'Finance', 'XLE': 'Energy', 'XLV': 'Health',
        'XLI': 'Industrial', 'XLP': 'Staples', 'XLY': 'Discretion.',
        'XLU': 'Utilities', 'XLRE': 'Real Est.', 'XLB': 'Materials', 'XLC': 'Comms',
    }
    for sym, name in sector_symbols.items():
        try:
            resp = _http_session.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}',
                                params={'range': '1d', 'interval': '5m'}, timeout=8, headers=_REQ_HEADERS)
            if resp.ok:
                payload = _safe_response_json(resp, {})
                meta = payload.get('chart', {}).get('result', [{}])[0].get('meta', {}) if isinstance(payload, dict) else {}
                if not isinstance(meta, dict) or not meta:
                    continue
                price = meta.get('regularMarketPrice', 0)
                prev = meta.get('previousClose', 0)
                change = ((price - prev) / prev * 100) if prev else 0
                markets.append({'symbol': name, 'price': price, 'change_24h': round(change, 2), 'market_type': 'sector', 'label': sym})
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
            log.debug('Yahoo Finance sector ETF %s failed: %s', sym, e)
    try:
        resp = _fetch_with_retry('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,ripple,cardano,dogecoin&vs_currencies=usd&include_24hr_change=true',
                                 timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        names = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL',
                 'binancecoin': 'BNB', 'ripple': 'XRP', 'cardano': 'ADA', 'dogecoin': 'DOGE'}
        coin_data = _safe_response_json(resp, {})
        if not isinstance(coin_data, dict):
            coin_data = {}
        for coin, vals in coin_data.items():
            if not isinstance(vals, dict):
                continue
            markets.append({'symbol': names.get(coin, coin.upper()), 'price': vals.get('usd', 0),
                            'change_24h': round(vals.get('usd_24h_change') or 0, 2), 'market_type': 'crypto'})
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        log.debug(f"CoinGecko failed: {e}")

    # Gold/Silver (metals.dev) — with change tracking from previous cached price
    try:
        resp = _http_session.get('https://api.metals.dev/v1/latest?api_key=demo&currency=USD&unit=toz',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            payload = _safe_response_json(resp, {})
            metals = payload.get('metals', {}) if isinstance(payload, dict) else {}
            # Read previous prices from DB for change calculation
            prev_prices = {}
            try:
                with db_session() as db:
                    for row in db.execute("SELECT symbol, price FROM sitroom_markets WHERE symbol IN ('GOLD', 'SILVER')").fetchall():
                        prev_prices[row[0]] = row[1]
            except sqlite3.Error:
                # Fresh schemas may not have the table populated yet; treat as no baseline.
                pass
            for metal_key, symbol in [('gold', 'GOLD'), ('silver', 'SILVER')]:
                if metal_key in metals:
                    new_price = metals[metal_key]
                    old_price = prev_prices.get(symbol)
                    change = ((new_price - old_price) / old_price * 100) if old_price else 0
                    markets.append({'symbol': symbol, 'price': new_price, 'change_24h': round(change, 2), 'market_type': 'commodity'})
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        log.debug(f"Metals failed: {e}")

    # Brent oil (EIA)
    try:
        resp = _http_session.get('https://api.eia.gov/v2/petroleum/pri/spt/data/',
                            params={'api_key': 'DEMO_KEY', 'frequency': 'daily', 'data[0]': 'value',
                                    'facets[product][]': 'EPCBRENT', 'sort[0][column]': 'period',
                                    'sort[0][direction]': 'desc', 'length': '1'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            payload = _safe_response_json(resp, {})
            rows = payload.get('response', {}).get('data', []) if isinstance(payload, dict) else []
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
        resp = _http_session.get('https://api.alternative.me/fng/?limit=1', timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            payload = _safe_response_json(resp, {})
            fg_rows = payload.get('data', [{}]) if isinstance(payload, dict) else [{}]
            fg = fg_rows[0] if fg_rows else {}
            if not isinstance(fg, dict) or 'value' not in fg:
                raise ValueError('Fear/Greed payload missing value')
            markets.append({'symbol': 'FEAR_GREED', 'price': int(fg.get('value', 50)),
                            'change_24h': 0, 'market_type': 'sentiment',
                            'label': fg.get('value_classification', 'Neutral')})
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        log.debug(f"Fear/Greed failed: {e}")

    if not markets:
        return

    with db_session() as db:
        db.execute('DELETE FROM sitroom_markets')
        db.executemany('INSERT INTO sitroom_markets (symbol, price, change_24h, market_type, label) VALUES (?, ?, ?, ?, ?)',
                      [(m['symbol'], m['price'], m.get('change_24h', 0), m.get('market_type', 'other'), m.get('label', '')) for m in markets])
        db.commit()
    log.info(f"Situation Room: cached {len(markets)} market entries")


def _fetch_conflict_data():
    if not _can_fetch('conflicts'):
        return
    _set_last_fetch('conflicts')
    # Dynamic 90-day window
    from_date = (datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d')
    try:
        resp = _http_session.get(
            f'https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?alertlevel=Orange;Red&eventlist=EQ;TC;FL;VO;DR&from={from_date}',
            timeout=15, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
        if not resp.ok:
            return
        data = _safe_response_json(resp, {})
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"GDACS failed: {e}")
        return

    if not isinstance(data, dict):
        return
    features = data.get('features', [])[:50]
    batch_ts = datetime.now().isoformat()
    with db_session() as db:
        for f in features:
            props = f.get('properties', {})
            geom = f.get('geometry', {})
            coords = geom.get('coordinates', [0, 0])
            eid = str(props.get('eventid', hashlib.sha256(json.dumps(props, sort_keys=True).encode()).hexdigest()[:12]))
            sev = props.get('severity', {})
            mag = sev.get('severity_value') if isinstance(sev, dict) else None
            url_obj = props.get('url', {})
            source_url = url_obj.get('report', '') if isinstance(url_obj, dict) else ''
            db.execute('''INSERT OR REPLACE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, source_url, detail_json, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (eid, 'conflict', props.get('name', props.get('eventtype', 'Unknown')),
                 mag, coords[1] if len(coords) > 1 else 0, coords[0] if coords else 0, 0, source_url,
                 json.dumps({'alert_level': props.get('alertlevel', ''), 'event_type': props.get('eventtype', ''),
                             'country': props.get('country', ''), 'description': (props.get('description') or '')[:2000]}),
                 batch_ts))
        db.commit()
        # Remove stale rows from previous batches
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'conflict' AND (cached_at IS NULL OR cached_at < ?)", (batch_ts,))
        db.commit()
    log.info(f"Situation Room: cached {len(features)} GDACS events")


def _fetch_aviation():
    """Fetch live aircraft positions from OpenSky Network."""
    if not _can_fetch('aviation'):
        return
    _set_last_fetch('aviation')
    try:
        # Fetch all aircraft (rate limited, ~10/day anonymous)
        resp = _http_session.get('https://opensky-network.org/api/states/all',
                            timeout=20, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = _safe_response_json(resp, {})
    except Exception as e:
        log.debug(f"OpenSky failed: {e}")
        return

    if not isinstance(data, dict):
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


def _fetch_ais_ships():
    """Fetch live vessel positions from free AIS sources.

    Primary: BarentsWatch open AIS (Norwegian waters, no key).
    Fallback: Parse major shipping chokepoint positions from cached events.
    """
    if not _can_fetch('ais_ships'):
        return
    _set_last_fetch('ais_ships')
    ships = []

    # Try Danish Maritime Authority AIS (free, no key, covers Danish/Baltic waters)
    try:
        resp = _http_session.get('https://ais.dk/api/ais/latest',
                            params={'limit': 200},
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            data = _safe_response_json(resp, [])
            for s in (data if isinstance(data, list) else data.get('features', data.get('data', []))):
                # Handle GeoJSON or flat format
                if isinstance(s, dict):
                    props = s.get('properties', s)
                    geom = s.get('geometry', {})
                    coords = geom.get('coordinates', [])
                    lat = coords[1] if len(coords) > 1 else props.get('latitude', props.get('lat', 0))
                    lng = coords[0] if coords else props.get('longitude', props.get('lng', 0))
                    if lat and lng:
                        ships.append({
                            'mmsi': str(props.get('mmsi', props.get('MMSI', ''))),
                            'name': props.get('shipName', props.get('name', props.get('shipname', ''))),
                            'lat': float(lat), 'lng': float(lng),
                            'speed': float(props.get('sog', props.get('speed', 0)) or 0),
                            'heading': float(props.get('cog', props.get('heading', 0)) or 0),
                            'type': props.get('shipType', props.get('type', '')),
                            'flag': props.get('flagCountry', props.get('flag', '')),
                        })
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as e:
        log.debug(f"AIS DK fetch failed: {e}")

    # If DK API didn't return data, try NOAA NDBC (buoys with some vessel data)
    if not ships:
        try:
            resp = _http_session.get('https://www.marinetraffic.com/en/data/?asset_type=vessels&columns=flag,shipname,mmsi,lat_of_latest_position,lon_of_latest_position,speed,heading',
                                timeout=12, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
            # This may not work without auth, silently fail
        except requests.RequestException:
            pass

    if not ships:
        return

    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_ships
            (id INTEGER PRIMARY KEY, mmsi TEXT, ship_name TEXT, lat REAL, lng REAL,
             speed_kn REAL, heading REAL, ship_type TEXT, flag TEXT,
             cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('DELETE FROM sitroom_ships')
        for s in ships[:300]:
            db.execute('''INSERT INTO sitroom_ships
                (mmsi, ship_name, lat, lng, speed_kn, heading, ship_type, flag)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (s['mmsi'], s['name'], s['lat'], s['lng'],
                 s['speed'], s['heading'], s['type'], s['flag']))
        db.commit()
    log.info(f"Situation Room: cached {len(ships)} vessel positions")


def _fetch_space_weather():
    """Fetch space weather data from NOAA SWPC."""
    if not _can_fetch('space_weather'):
        return
    _set_last_fetch('space_weather')

    datasets = {}

    # NOAA storm scales (G/S/R)
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/products/noaa-scales.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            scales = _safe_response_json(resp, {})
            current_scales = scales.get('0', {}) if isinstance(scales, dict) else {}
            if isinstance(current_scales, dict) and current_scales:
                datasets['noaa_scales'] = current_scales  # Current conditions
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"NOAA scales failed: {e}")

    # Kp index (geomagnetic activity)
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            kp_data = _safe_response_json(resp, [])
            if kp_data:
                datasets['kp_index'] = {'latest': kp_data[-1], 'recent': kp_data[-8:]}
    except (requests.RequestException, ValueError, IndexError, TypeError) as e:
        log.debug(f"NOAA Kp failed: {e}")

    # Solar flare probabilities
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/json/solar_probabilities.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            probs = _safe_response_json(resp, [])
            if probs:
                datasets['solar_probs'] = probs[-1]
    except (requests.RequestException, ValueError, IndexError, TypeError) as e:
        log.debug(f"NOAA solar probs failed: {e}")

    # Active space weather alerts
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/products/alerts.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            alerts = _safe_response_json(resp, [])
            if isinstance(alerts, list) and alerts:
                datasets['sw_alerts'] = alerts[:10]
    except (requests.RequestException, ValueError) as e:
        log.debug(f"NOAA alerts failed: {e}")

    if not datasets:
        return

    with db_session() as db:
        db.execute('DELETE FROM sitroom_space_weather')
        db.executemany('INSERT INTO sitroom_space_weather (data_type, value_json) VALUES (?, ?)',
                      [(dtype, json.dumps(data)) for dtype, data in datasets.items()])
        db.commit()
    log.info(f"Situation Room: cached {len(datasets)} space weather datasets")


def _fetch_volcanoes():
    """Fetch recent volcanic activity from Smithsonian GVP."""
    if not _can_fetch('volcanoes'):
        return
    _set_last_fetch('volcanoes')
    try:
        resp = _http_session.get('https://webservices.volcano.si.edu/geoserver/GVP-VOTW/ows',
                            params={'service': 'WFS', 'version': '1.0.0', 'request': 'GetFeature',
                                    'typeName': 'GVP-VOTW:E3WebApp_Eruptions1960',
                                    'maxFeatures': '50', 'outputFormat': 'application/json',
                                    'sortBy': 'StartDate+D'},
                            timeout=20, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = _safe_response_json(resp, {})
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"Volcano fetch failed: {e}")
        return

    if not isinstance(data, dict):
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
        resp = _http_session.get('https://gamma-api.polymarket.com/markets',
                            params={'limit': 20, 'active': 'true', 'closed': 'false'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        markets = _safe_response_json(resp, [])
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"Polymarket failed: {e}")
        return

    if not isinstance(markets, list):
        return
    if not markets:
        return

    with db_session() as db:
        db.execute('DELETE FROM sitroom_predictions')
        for m in markets:
            prices = _safe_json_value(m.get('outcomePrices', '[]'), [])
            try:
                yes_price = float(prices[0]) if prices else 0
                no_price = float(prices[1]) if len(prices) > 1 else 0
            except (ValueError, TypeError):
                yes_price, no_price = 0, 0
            db.execute('''INSERT OR IGNORE INTO sitroom_predictions
                (market_id, question, category, outcome_yes, outcome_no, volume, end_date, active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (str(m.get('id', '')), (m.get('question') or '')[:500],
                 m.get('category', ''), yes_price, no_price,
                 m.get('volumeNum') or m.get('volume') or 0,
                 m.get('endDate', ''), 1 if m.get('active') else 0))
        db.commit()
    log.info(f"Situation Room: cached {len(markets)} prediction markets")


def _fetch_fires():
    """Fetch active fire detections from NASA FIRMS (MODIS/VIIRS CSV)."""
    if not _can_fetch('fires'):
        return
    _set_last_fetch('fires')
    try:
        # FIRMS VIIRS active fires (last 24h, CSV format, no API key for web service)
        resp = _http_session.get('https://firms.modaps.eosdis.nasa.gov/api/area/csv/DEMO_KEY/VIIRS_SNPP_NRT/world/1',
                            timeout=30, headers=_REQ_HEADERS)
        if not resp.ok:
            return
    except requests.RequestException as e:
        log.debug(f"NASA FIRMS fetch failed: {e}")
        return

    lines = resp.text.strip().split('\n')
    if len(lines) < 2:
        return

    header = lines[0].split(',')
    lat_i = header.index('latitude') if 'latitude' in header else 0
    lng_i = header.index('longitude') if 'longitude' in header else 1
    bright_i = header.index('bright_ti4') if 'bright_ti4' in header else -1
    conf_i = header.index('confidence') if 'confidence' in header else -1
    acq_date_i = header.index('acq_date') if 'acq_date' in header else -1

    fires = []
    for line in lines[1:501]:  # Cap at 500 fire points
        cols = line.split(',')
        if len(cols) < max(lat_i, lng_i) + 1:
            continue
        try:
            lat = float(cols[lat_i])
            lng = float(cols[lng_i])
            brightness = float(cols[bright_i]) if bright_i >= 0 and cols[bright_i] else 0
            confidence = cols[conf_i] if conf_i >= 0 else ''
            acq_date = cols[acq_date_i] if acq_date_i >= 0 else ''
            fires.append((lat, lng, brightness, confidence, acq_date))
        except (ValueError, IndexError):
            continue

    if not fires:
        return

    batch_ts = datetime.now().isoformat()
    with db_session() as db:
        for lat, lng, brightness, confidence, acq_date in fires:
            eid = hashlib.sha256(f"fire:{lat:.3f}:{lng:.3f}:{acq_date}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR REPLACE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json, cached_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?)''',
                (eid, 'fire', f"Fire detection ({confidence})" if confidence else 'Fire detection',
                 brightness, lat, lng,
                 json.dumps({'brightness': brightness, 'confidence': confidence, 'acq_date': acq_date}),
                 batch_ts))
        db.commit()
        # Remove stale rows from previous batches
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'fire' AND (cached_at IS NULL OR cached_at < ?)", (batch_ts,))
        db.commit()
    log.info(f"Situation Room: cached {len(fires)} fire detections")


def _fetch_internet_outages():
    """Fetch internet outage/disruption data from public sources."""
    if not _can_fetch('internet_outages'):
        return
    _set_last_fetch('internet_outages')

    outages = []

    # Cloudflare Radar - public outage summary (no auth for basic data)
    try:
        resp = _http_session.get('https://radar.cloudflare.com/api/v1/annotations/outages?dateRange=1d&format=json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            data = _safe_response_json(resp, {})
            for item in (data.get('annotations', []) or data.get('result', {}).get('annotations', []))[:30]:
                outages.append({
                    'title': item.get('description', item.get('eventType', 'Internet disruption')),
                    'country': item.get('locations', item.get('asns', '')),
                    'start': item.get('startDate', ''),
                    'end': item.get('endDate', ''),
                    'scope': item.get('scope', ''),
                })
    except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
        log.debug(f"Cloudflare Radar failed: {e}")

    # Fallback: IODA (Internet Outage Detection and Analysis) from Georgia Tech
    if not outages:
        try:
            resp = _http_session.get('https://api.ioda.inetintel.cc.gatech.edu/v2/alerts/ongoing',
                                timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
            if resp.ok:
                data = _safe_response_json(resp, {})
                for alert in (data.get('data', []))[:20]:
                    outages.append({
                        'title': f"Internet disruption: {alert.get('entityName', 'Unknown')}",
                        'country': alert.get('entityName', ''),
                        'start': alert.get('time', ''),
                        'end': '',
                        'scope': alert.get('level', ''),
                    })
        except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
            log.debug(f"IODA fallback failed: {e}")

    if not outages:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'internet_outage'")
        for o in outages:
            eid = hashlib.sha256((o['title'] + o.get('start', '')).encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'internet_outage', o['title'][:500],
                 json.dumps({'country': o.get('country', ''), 'start': o.get('start', ''),
                             'end': o.get('end', ''), 'scope': o.get('scope', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(outages)} internet outages")


_COUNTRY_COORDS = {
    'afghanistan': (33.0, 65.0), 'albania': (41.0, 20.0), 'algeria': (28.0, 3.0),
    'angola': (-12.5, 18.5), 'argentina': (-34.0, -64.0), 'australia': (-25.0, 135.0),
    'austria': (47.3, 13.3), 'azerbaijan': (40.5, 47.5), 'bangladesh': (24.0, 90.0),
    'belarus': (53.0, 28.0), 'belgium': (50.8, 4.0), 'benin': (9.5, 2.3),
    'bolivia': (-17.0, -65.0), 'bosnia': (44.0, 18.0), 'botswana': (-22.0, 24.0),
    'brazil': (-10.0, -55.0), 'brunei': (4.5, 114.7), 'bulgaria': (43.0, 25.0),
    'burkina faso': (13.0, -1.5), 'burundi': (-3.5, 29.9), 'cambodia': (13.0, 105.0),
    'cameroon': (6.0, 12.0), 'canada': (56.0, -106.0), 'chad': (15.0, 19.0),
    'chile': (-30.0, -71.0), 'china': (35.0, 105.0), 'colombia': (4.0, -72.0),
    'congo': (-4.0, 22.0), 'costa rica': (10.0, -84.0), 'croatia': (45.2, 15.5),
    'cuba': (22.0, -80.0), 'cyprus': (35.0, 33.0), 'czech': (49.8, 15.5),
    'democratic republic': (-4.0, 22.0), 'denmark': (56.0, 10.0), 'djibouti': (11.5, 43.1),
    'dominican': (19.0, -70.0), 'drc': (-4.0, 22.0), 'ecuador': (-1.0, -78.0),
    'egypt': (27.0, 30.0), 'el salvador': (13.8, -88.9), 'eritrea': (15.0, 39.0),
    'ethiopia': (8.0, 38.0), 'finland': (64.0, 26.0), 'france': (46.0, 2.0),
    'gabon': (-1.0, 11.5), 'georgia': (42.0, 43.5), 'germany': (51.0, 9.0),
    'ghana': (8.0, -1.2), 'greece': (39.0, 22.0), 'guatemala': (15.5, -90.3),
    'guinea': (11.0, -10.0), 'haiti': (19.0, -72.4), 'honduras': (15.0, -86.5),
    'hungary': (47.0, 20.0), 'india': (20.0, 77.0), 'indonesia': (-5.0, 120.0),
    'iran': (32.0, 53.0), 'iraq': (33.0, 44.0), 'ireland': (53.0, -8.0),
    'israel': (31.5, 34.8), 'italy': (42.8, 12.8), 'ivory coast': (7.5, -5.5),
    'japan': (36.0, 138.0), 'jordan': (31.0, 36.0), 'kazakhstan': (48.0, 68.0),
    'kenya': (-1.0, 38.0), 'korea': (36.0, 128.0), 'kuwait': (29.5, 47.5),
    'laos': (18.0, 105.0), 'lebanon': (33.8, 35.8), 'liberia': (6.5, -9.5),
    'libya': (27.0, 17.0), 'madagascar': (-20.0, 47.0), 'malawi': (-13.5, 34.0),
    'malaysia': (2.5, 112.5), 'mali': (17.0, -4.0), 'mauritania': (20.0, -10.0),
    'mexico': (23.0, -102.0), 'mongolia': (46.0, 105.0), 'morocco': (32.0, -5.0),
    'mozambique': (-18.3, 35.0), 'myanmar': (22.0, 98.0), 'namibia': (-22.0, 17.0),
    'nepal': (28.0, 84.0), 'netherlands': (52.5, 5.8), 'new zealand': (-41.0, 174.0),
    'nicaragua': (13.0, -85.0), 'niger': (16.0, 8.0), 'nigeria': (10.0, 8.0),
    'norway': (62.0, 10.0), 'oman': (21.0, 57.0), 'pakistan': (30.0, 70.0),
    'palestine': (31.9, 35.2), 'panama': (9.0, -80.0), 'papua': (-6.0, 147.0),
    'paraguay': (-23.0, -58.0), 'peru': (-10.0, -76.0), 'philippines': (13.0, 122.0),
    'poland': (52.0, 20.0), 'portugal': (39.5, -8.0), 'qatar': (25.5, 51.3),
    'romania': (46.0, 25.0), 'russia': (60.0, 100.0), 'rwanda': (-2.0, 29.9),
    'saudi': (24.0, 45.0), 'senegal': (14.0, -14.5), 'serbia': (44.0, 21.0),
    'sierra leone': (8.5, -11.8), 'singapore': (1.4, 103.8), 'slovakia': (48.7, 19.5),
    'somalia': (5.0, 46.0), 'south africa': (-29.0, 24.0), 'south sudan': (7.0, 30.0),
    'spain': (40.0, -4.0), 'sri lanka': (7.0, 81.0), 'sudan': (15.0, 30.0),
    'sweden': (62.0, 15.0), 'switzerland': (47.0, 8.0), 'syria': (35.0, 38.0),
    'taiwan': (23.5, 121.0), 'tajikistan': (39.0, 71.0), 'tanzania': (-6.0, 35.0),
    'thailand': (15.0, 100.0), 'togo': (8.6, 1.2), 'tunisia': (34.0, 9.0),
    'turkey': (39.0, 35.0), 'turkmenistan': (40.0, 60.0), 'uganda': (1.0, 32.0),
    'ukraine': (49.0, 32.0), 'united arab': (24.0, 54.0), 'united kingdom': (54.0, -2.0),
    'united states': (38.0, -97.0), 'uruguay': (-33.0, -56.0), 'uzbekistan': (41.0, 64.0),
    'venezuela': (8.0, -66.0), 'vietnam': (16.0, 106.0), 'yemen': (15.0, 48.0),
    'zambia': (-15.0, 28.0), 'zimbabwe': (-20.0, 30.0),
}


def _geocode_title(title):
    """Extract country coordinates from a title string using keyword matching."""
    title_lower = title.lower()
    for country, (lat, lng) in _COUNTRY_COORDS.items():
        if country in title_lower:
            return lat, lng
    return 0, 0


def _fetch_disease_outbreaks():
    """Fetch disease outbreak data from WHO RSS."""
    if not _can_fetch('disease_outbreaks'):
        return
    _set_last_fetch('disease_outbreaks')
    try:
        resp = _http_session.get('https://www.who.int/feeds/entity/don/en/rss.xml',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        items = _parse_feed(resp.text, 'WHO DON', 'Health')
    except (requests.RequestException, ET.ParseError, ValueError) as e:
        log.debug(f"WHO outbreaks fetch failed: {e}")
        return

    if not items:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'disease'")
        for item in items[:30]:
            eid = hashlib.sha256((item['title'] + item.get('link', '')).encode()).hexdigest()[:16]
            lat, lng = _geocode_title(item['title'])
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, ?, ?, 0, ?, ?)''',
                (eid, 'disease', item['title'], lat, lng, item.get('link', ''),
                 json.dumps({'description': item.get('description', ''), 'published': item.get('published', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(items)} disease outbreak entries")


def _fetch_radiation():
    """Fetch radiation monitoring data from Safecast API."""
    if not _can_fetch('radiation'):
        return
    _set_last_fetch('radiation')
    try:
        # Safecast public API — recent measurements
        resp = _http_session.get('https://api.safecast.org/measurements.json',
                            params={'order': 'created_at desc', 'per_page': 50},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = _safe_response_json(resp, [])
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"Safecast radiation fetch failed: {e}")
        return

    if not data:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'radiation'")
        for m in data[:50]:
            lat = m.get('latitude') or 0
            lng = m.get('longitude') or 0
            value = m.get('value') or 0
            unit = m.get('unit', 'cpm')
            loc = m.get('location_name', '')
            eid = hashlib.sha256(f"rad:{m.get('id', '')}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)''',
                (eid, 'radiation', f"{value} {unit} - {loc}" if loc else f"{value} {unit}",
                 value, lat, lng,
                 json.dumps({'value': value, 'unit': unit, 'location': loc,
                             'device_id': m.get('device_id', ''), 'captured_at': m.get('captured_at', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(data)} radiation measurements")


def _fetch_gdelt_trending():
    """Fetch trending topics from GDELT GKG (Global Knowledge Graph)."""
    if not _can_fetch('gdelt_trending'):
        return
    _set_last_fetch('gdelt_trending')
    try:
        # GDELT DOC API — top themes in last 24 hours
        resp = _http_session.get('https://api.gdeltproject.org/api/v2/doc/doc',
                            params={'query': '', 'mode': 'ToneChart', 'format': 'json',
                                    'maxrecords': '30', 'timespan': '24h', 'sort': 'ToneDesc'},
                            timeout=15, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = _safe_response_json(resp, {})
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"GDELT trending fetch failed: {e}")
        return

    articles = data.get('articles', [])
    if not articles:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'gdelt_trend'")
        for a in articles[:30]:
            eid = hashlib.sha256((a.get('title', '') + a.get('url', '')).encode()).hexdigest()[:16]
            tone = a.get('tone', 0)
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?)''',
                (eid, 'gdelt_trend', (a.get('title', '') or '')[:500], tone,
                 a.get('url', ''),
                 json.dumps({'domain': a.get('domain', ''), 'language': a.get('language', ''),
                             'seendate': a.get('seendate', ''), 'socialimage': a.get('socialimage', ''),
                             'tone': tone})))
        db.commit()
    log.info(f"Situation Room: cached {len(articles)} GDELT trending articles")


def _fetch_sanctions():
    """Fetch sanctions/trade policy news via RSS."""
    if not _can_fetch('sanctions'):
        return
    _set_last_fetch('sanctions')
    articles = []
    sanction_feeds = [
        {'name': 'OFAC Updates', 'url': 'https://home.treasury.gov/system/files/126/sdn_feed.xml', 'category': 'Sanctions'},
        {'name': 'Trade Policy', 'url': 'https://www.trade.gov/rss/press-releases', 'category': 'Trade'},
    ]
    for feed in sanction_feeds:
        items = _fetch_single_feed(feed)
        articles.extend(items)

    if not articles:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'sanctions'")
        for a in articles[:20]:
            eid = hashlib.sha256((a['title'] + a.get('link', '')).encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, 0, 0, 0, ?, ?)''',
                (eid, 'sanctions', a['title'][:500], a.get('link', ''),
                 json.dumps({'source': a.get('source', ''), 'category': a.get('category', ''),
                             'published': a.get('published', ''), 'description': a.get('description', '')[:500]})))
        db.commit()
    log.info(f"Situation Room: cached {len(articles)} sanctions/trade items")


def _fetch_ucdp_conflicts():
    """Fetch armed conflict events from UCDP GED API."""
    if not _can_fetch('ucdp'):
        return
    _set_last_fetch('ucdp')
    try:
        # UCDP Georeferenced Event Dataset - recent events
        resp = _fetch_with_retry('https://ucdpapi.pcr.uu.se/api/gedevents/24.1',
                                  timeout=15, headers=_REQ_HEADERS,
                                  params={'pagesize': 50, 'page': 0})
        data = _safe_response_json(resp, {})
    except (requests.RequestException, ValueError, KeyError) as e:
        log.debug(f"UCDP fetch failed: {e}")
        return

    results = data.get('Result', [])
    if not results:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'ucdp_conflict'")
        for ev in results[:50]:
            lat = ev.get('latitude') or 0
            lng = ev.get('longitude') or 0
            deaths = (ev.get('best') or 0)
            eid = str(ev.get('id', hashlib.sha256(json.dumps(ev, sort_keys=True, default=str).encode()).hexdigest()[:12]))
            country = ev.get('country', '')
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)''',
                (eid, 'ucdp_conflict',
                 f"{ev.get('type_of_violence_str', 'Armed conflict')} - {ev.get('side_a', '')} vs {ev.get('side_b', '')}",
                 deaths, lat, lng,
                 json.dumps({'country': country, 'region': ev.get('region', ''),
                             'deaths_best': deaths, 'deaths_low': ev.get('low', 0), 'deaths_high': ev.get('high', 0),
                             'year': ev.get('year', ''), 'source': ev.get('source_article', ''),
                             'side_a': ev.get('side_a', ''), 'side_b': ev.get('side_b', ''),
                             'violence_type': ev.get('type_of_violence_str', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(results)} UCDP conflict events")


def _fetch_cyber_threats():
    """Fetch cybersecurity threat data from CISA KEV + NVD."""
    if not _can_fetch('cyber_threats'):
        return
    _set_last_fetch('cyber_threats')

    items = []

    # CISA Known Exploited Vulnerabilities (KEV)
    try:
        resp = _http_session.get('https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json',
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            data = _safe_response_json(resp, {})
            for vuln in (data.get('vulnerabilities', []))[-20:]:
                items.append({
                    'title': f"{vuln.get('cveID', '')} - {vuln.get('vendorProject', '')} {vuln.get('product', '')}",
                    'description': vuln.get('shortDescription', ''),
                    'date': vuln.get('dateAdded', ''),
                    'source': 'CISA KEV',
                    'severity': 'high',
                })
    except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
        log.debug(f"CISA KEV fetch failed: {e}")

    # CISA advisories RSS
    try:
        resp = _http_session.get('https://www.cisa.gov/cybersecurity-advisories/all.xml',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            adv = _parse_feed(resp.text, 'CISA', 'Cyber')
            for a in adv[:10]:
                items.append({
                    'title': a['title'],
                    'description': a.get('description', ''),
                    'date': a.get('published', ''),
                    'source': 'CISA Advisory',
                    'severity': 'medium',
                    'link': a.get('link', ''),
                })
    except (requests.RequestException, ET.ParseError, ValueError, KeyError) as e:
        log.debug(f"CISA advisories fetch failed: {e}")

    if not items:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'cyber_threat'")
        for item in items:
            eid = hashlib.sha256((item['title']).encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, 0, 0, 0, ?, ?)''',
                (eid, 'cyber_threat', item['title'][:500], item.get('link', ''),
                 json.dumps({'description': item.get('description', '')[:500], 'date': item.get('date', ''),
                             'source': item.get('source', ''), 'severity': item.get('severity', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(items)} cyber threats")


def _fetch_yield_curve():
    """Fetch US Treasury yield curve data."""
    if not _can_fetch('yield_curve'):
        return
    _set_last_fetch('yield_curve')
    try:
        resp = _http_session.get('https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates',
                            params={'sort': '-record_date', 'page[size]': 20,
                                    'filter': 'security_type_desc:eq:Treasury Bills,Treasury Notes,Treasury Bonds'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        payload = _safe_response_json(resp, {})
        data = payload.get('data', []) if isinstance(payload, dict) else []
    except (requests.RequestException, ValueError, KeyError, AttributeError) as e:
        log.debug(f"Yield curve fetch failed: {e}")
        return

    if not data:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'yield_curve'")
        for item in data[:20]:
            eid = hashlib.sha256(f"yc:{item.get('security_desc','')}:{item.get('record_date','')}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'yield_curve', item.get('security_desc', ''),
                 _safe_float(item.get('avg_interest_rate_amt', 0)),
                 json.dumps({'rate': item.get('avg_interest_rate_amt', ''),
                             'security': item.get('security_desc', ''),
                             'type': item.get('security_type_desc', ''),
                             'date': item.get('record_date', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(data)} yield curve entries")


def _fetch_stablecoins():
    """Fetch stablecoin market cap data from CoinGecko."""
    if not _can_fetch('stablecoins'):
        return
    _set_last_fetch('stablecoins')
    try:
        resp = _http_session.get('https://api.coingecko.com/api/v3/simple/price',
                            params={'ids': 'tether,usd-coin,dai,first-digital-usd', 'vs_currencies': 'usd',
                                    'include_market_cap': 'true', 'include_24hr_change': 'true'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = _safe_response_json(resp, {})
    except Exception as e:
        log.debug(f"Stablecoin fetch failed: {e}")
        return

    names = {'tether': 'USDT', 'usd-coin': 'USDC', 'dai': 'DAI', 'first-digital-usd': 'FDUSD'}
    if not data or not isinstance(data, dict):
        return

    with db_session() as db:
        rows = []
        for coin, vals in data.items():
            symbol = names.get(coin, coin.upper())
            price = vals.get('usd', 1.0)
            mcap = vals.get('usd_market_cap', 0)
            change = vals.get('usd_24h_change', 0)
            rows.append((symbol, price, round(change or 0, 4), 'stablecoin',
                         f"${mcap/1e9:.1f}B" if mcap else ''))
        db.executemany('INSERT OR REPLACE INTO sitroom_markets (symbol, price, change_24h, market_type, label) VALUES (?, ?, ?, ?, ?)', rows)
        db.commit()
    log.info(f"Situation Room: cached {len(data)} stablecoin entries")


def _compute_correlations():
    """Cross-domain correlation engine — detects convergent signals."""
    if not _can_fetch('correlation'):
        return
    _set_last_fetch('correlation')

    with db_session() as db:
        # Count events by type in last fetch
        counts = {}
        for row in db.execute("SELECT event_type, COUNT(*) as cnt FROM sitroom_events GROUP BY event_type").fetchall():
            counts[dict(row)['event_type']] = dict(row)['cnt']

        # Count news by category
        news_counts = {}
        for row in db.execute("SELECT category, COUNT(*) as cnt FROM sitroom_news GROUP BY category").fetchall():
            news_counts[dict(row)['category']] = dict(row)['cnt']

        # Detect correlations
        signals = []

        # Military-Economic: conflicts + market drops
        market_change = db.execute("SELECT AVG(change_24h) FROM sitroom_markets WHERE market_type = 'index'").fetchone()[0] or 0
        conflict_count = counts.get('conflict', 0) + counts.get('ucdp_conflict', 0)
        if conflict_count > 5 and market_change < -1:
            signals.append({'type': 'military_economic', 'severity': 'high',
                            'title': 'Military-Economic Convergence',
                            'detail': f'{conflict_count} active conflicts coincide with market decline ({market_change:.1f}%)'})

        # Disaster-Humanitarian: quakes/weather + displacement
        disaster_count = counts.get('earthquake', 0) + counts.get('weather_alert', 0) + counts.get('fire', 0)
        if disaster_count > 20:
            signals.append({'type': 'disaster_cascade', 'severity': 'elevated',
                            'title': 'Disaster Cascade Warning',
                            'detail': f'{disaster_count} concurrent natural events detected across multiple regions'})

        # Cyber-Infrastructure: cyber threats + internet outages
        cyber_count = counts.get('cyber_threat', 0)
        outage_count = counts.get('internet_outage', 0)
        if cyber_count > 5 and outage_count > 2:
            signals.append({'type': 'cyber_infrastructure', 'severity': 'high',
                            'title': 'Cyber-Infrastructure Convergence',
                            'detail': f'{cyber_count} cyber threats + {outage_count} internet outages — possible coordinated attack'})

        # Escalation: high news volume in Defense + conflicts rising
        defense_news = news_counts.get('Defense', 0)
        if defense_news > 10 and conflict_count > 3:
            signals.append({'type': 'escalation', 'severity': 'elevated',
                            'title': 'Escalation Monitor',
                            'detail': f'{defense_news} defense news items + {conflict_count} active conflicts'})

        # Energy-Geopolitical: oil price + Middle East news
        oil = db.execute("SELECT price FROM sitroom_markets WHERE symbol LIKE '%OIL%' OR symbol LIKE '%BRENT%'").fetchone()
        me_news = news_counts.get('Middle East', 0)
        if oil and me_news > 5:
            signals.append({'type': 'energy_geopolitical', 'severity': 'normal',
                            'title': 'Energy-Geopolitical Signal',
                            'detail': f'Oil at ${dict(oil).get("price") or 0:.2f} with {me_news} Middle East headlines'})

        # Space Weather: high Kp index
        if counts.get('radiation', 0) > 10:
            signals.append({'type': 'radiation', 'severity': 'elevated',
                            'title': 'Radiation Monitoring Alert',
                            'detail': f'{counts["radiation"]} elevated radiation readings detected'})

        # Store signals
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'correlation'")
        for sig in signals:
            eid = hashlib.sha256(sig['type'].encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'correlation', sig['title'],
                 json.dumps({'type': sig['type'], 'severity': sig['severity'], 'detail': sig['detail']})))
        db.commit()
    log.info(f"Situation Room: computed {len(signals)} cross-domain correlations")


def _fetch_renewable_energy():
    """Fetch renewable energy news and data."""
    if not _can_fetch('renewable'):
        return
    _set_last_fetch('renewable')
    articles = []
    renewable_feeds = [
        {'name': 'CleanTechnica', 'url': 'https://cleantechnica.com/feed/', 'category': 'Renewable'},
        {'name': 'Renewable Energy World', 'url': 'https://www.renewableenergyworld.com/feed/', 'category': 'Renewable'},
        {'name': 'PV Magazine', 'url': 'https://www.pv-magazine.com/feed/', 'category': 'Renewable'},
    ]
    for feed in renewable_feeds:
        items = _fetch_single_feed(feed)
        articles.extend(items)

    if articles:
        with db_session() as db:
            for a in articles[:15]:
                content_hash = hashlib.sha256((a['title'] + a['link']).encode()).hexdigest()[:32]
                db.execute('''INSERT OR REPLACE INTO sitroom_news
                    (content_hash, title, link, description, published, source_name, category, source_type, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'rss', CURRENT_TIMESTAMP)''',
                    (content_hash, a['title'], a['link'], a['description'],
                     a['published'], a['source'], 'Renewable'))
            db.commit()
        log.info(f"Situation Room: cached {len(articles)} renewable energy articles")


def _fetch_bigmac_index():
    """Fetch Big Mac Index from The Economist (cached, daily)."""
    if not _can_fetch('bigmac'):
        return
    _set_last_fetch('bigmac')
    # Big Mac Index from GitHub (The Economist publishes data there)
    try:
        resp = _http_session.get('https://raw.githubusercontent.com/TheEconomist/big-mac-data/master/output-data/big-mac-raw-index.csv',
                            timeout=15, headers=_REQ_HEADERS)
        if not resp.ok:
            return
    except Exception as e:
        log.debug(f"Big Mac Index fetch failed: {e}")
        return

    lines = resp.text.strip().split('\n')
    if len(lines) < 2:
        return

    # Parse CSV — get latest entries per country
    header = lines[0].split(',')
    try:
        name_i = header.index('name')
        price_i = header.index('dollar_price')
        date_i = header.index('date')
    except ValueError:
        return

    latest = {}
    for line in lines[1:]:
        cols = line.split(',')
        if len(cols) <= max(name_i, price_i, date_i):
            continue
        country = cols[name_i].strip('"')
        try:
            price = float(cols[price_i])
        except ValueError:
            continue
        date = cols[date_i].strip('"')
        if country not in latest or date > latest[country]['date']:
            latest[country] = {'price': price, 'date': date}

    if not latest:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'bigmac'")
        for country, data in list(latest.items())[:30]:
            eid = hashlib.sha256(f"bm:{country}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'bigmac', country, data['price'],
                 json.dumps({'country': country, 'dollar_price': data['price'], 'date': data['date']})))
        db.commit()
    log.info(f"Situation Room: cached {len(latest)} Big Mac Index entries")


def _fetch_central_banks():
    """Fetch central bank news and policy updates."""
    if not _can_fetch('central_banks'):
        return
    _set_last_fetch('central_banks')
    articles = []
    cb_feeds = [
        {'name': 'Federal Reserve', 'url': 'https://www.federalreserve.gov/feeds/press_all.xml', 'category': 'Central Banks'},
        {'name': 'ECB Press', 'url': 'https://www.ecb.europa.eu/rss/press.html', 'category': 'Central Banks'},
        {'name': 'BOE News', 'url': 'https://www.bankofengland.co.uk/rss/news', 'category': 'Central Banks'},
    ]
    for feed in cb_feeds:
        items = _fetch_single_feed(feed)
        articles.extend(items)
    if articles:
        with db_session() as db:
            for a in articles[:15]:
                content_hash = hashlib.sha256((a['title'] + a['link']).encode()).hexdigest()[:32]
                db.execute('''INSERT OR REPLACE INTO sitroom_news
                    (content_hash, title, link, description, published, source_name, category, source_type, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'rss', CURRENT_TIMESTAMP)''',
                    (content_hash, a['title'], a['link'], a['description'], a['published'], a['source'], 'Central Banks'))
            db.commit()
        log.info(f"Situation Room: cached {len(articles)} central bank items")


def _fetch_arxiv_papers():
    """Fetch latest AI research papers from ArXiv."""
    if not _can_fetch('arxiv_papers'):
        return
    _set_last_fetch('arxiv_papers')
    try:
        resp = _http_session.get('https://export.arxiv.org/api/query',
                            params={'search_query': 'cat:cs.AI+OR+cat:cs.LG', 'start': 0,
                                    'max_results': 15, 'sortBy': 'submittedDate', 'sortOrder': 'descending'},
                            timeout=15, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        items = _parse_feed(resp.text, 'ArXiv', 'AI Research')
        if items:
            with db_session() as db:
                for a in items[:15]:
                    content_hash = hashlib.sha256((a['title'] + a['link']).encode()).hexdigest()[:32]
                    db.execute('''INSERT OR REPLACE INTO sitroom_news
                        (content_hash, title, link, description, published, source_name, category, source_type, cached_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, 'rss', CURRENT_TIMESTAMP)''',
                        (content_hash, a['title'][:300], a['link'], a['description'][:500], a['published'], 'ArXiv', 'AI Research'))
                db.commit()
            log.info(f"Situation Room: cached {len(items)} ArXiv papers")
    except Exception as e:
        log.debug(f"ArXiv fetch failed: {e}")


def _fetch_macro_stress():
    """Fetch macro stress indicators from FRED (St. Louis Fed)."""
    if not _can_fetch('macro_stress'):
        return
    _set_last_fetch('macro_stress')

    indicators = {}

    # FRED series (all public, DEMO_KEY or no key needed for low volume)
    fred_series = {
        'STLFSI2': 'Financial Stress Index',
        'T10Y2Y': '10Y-2Y Yield Spread',
        'VIXCLS': 'VIX Volatility',
        'BAMLH0A0HYM2': 'High Yield Spread',
        'DCOILBRENTEU': 'Brent Crude Oil',
        'UNRATE': 'Unemployment Rate',
        'CPIAUCSL': 'CPI (All Urban)',
    }
    for series_id, label in fred_series.items():
        try:
            resp = _http_session.get(f'https://api.stlouisfed.org/fred/series/observations',
                                params={'series_id': series_id, 'api_key': 'DEMO_KEY',
                                        'sort_order': 'desc', 'limit': 1, 'file_type': 'json'},
                                timeout=8, headers=_REQ_HEADERS)
            if resp.ok:
                payload = _safe_response_json(resp, {})
                obs = payload.get('observations', []) if isinstance(payload, dict) else []
                if obs and obs[0].get('value', '.') != '.':
                    indicators[series_id] = {'label': label, 'value': float(obs[0]['value']),
                                              'date': obs[0].get('date', '')}
        except Exception:
            pass

    if not indicators:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'macro_indicator'")
        for sid, data in indicators.items():
            eid = hashlib.sha256(f"macro:{sid}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'macro_indicator', data['label'], data['value'],
                 json.dumps({'series': sid, 'value': data['value'], 'date': data['date']})))
        db.commit()
    log.info(f"Situation Room: cached {len(indicators)} macro stress indicators")


def _fetch_product_hunt():
    """Fetch Product Hunt trending products via RSS."""
    if not _can_fetch('product_hunt'):
        return
    _set_last_fetch('product_hunt')
    try:
        items = _fetch_single_feed({'name': 'Product Hunt', 'url': 'https://www.producthunt.com/feed', 'category': 'Product Hunt'})
        if not items:
            return
        with db_session() as db:
            for a in items[:10]:
                content_hash = hashlib.sha256((a['title'] + a['link']).encode()).hexdigest()[:32]
                db.execute('''INSERT OR REPLACE INTO sitroom_news
                    (content_hash, title, link, description, published, source_name, category, source_type, cached_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'rss', CURRENT_TIMESTAMP)''',
                    (content_hash, a['title'], a['link'], a['description'],
                     a['published'], 'Product Hunt', 'Product Hunt'))
            db.commit()
        log.info(f"Situation Room: cached {len(items)} Product Hunt items")
    except Exception as e:
        log.debug(f"Product Hunt fetch failed: {e}")


def _fetch_github_trending():
    """Fetch GitHub trending repositories."""
    if not _can_fetch('github_trending'):
        return
    _set_last_fetch('github_trending')
    try:
        resp = _http_session.get('https://api.github.com/search/repositories',
                            params={'q': 'created:>' + (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                                    'sort': 'stars', 'order': 'desc', 'per_page': 15},
                            timeout=15, headers={**_REQ_HEADERS, 'Accept': 'application/vnd.github.v3+json'})
        if not resp.ok:
            return
        data = _safe_response_json(resp, {})
    except Exception as e:
        log.debug(f"GitHub trending fetch failed: {e}")
        return

    items = data.get('items', [])
    if not items:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'github_trending'")
        for repo in items[:15]:
            eid = hashlib.sha256(str(repo.get('id', '')).encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?, ?)''',
                (eid, 'github_trending', repo.get('full_name', ''),
                 repo.get('stargazers_count', 0), repo.get('html_url', ''),
                 json.dumps({'description': (repo.get('description') or '')[:300],
                             'language': repo.get('language', ''), 'stars': repo.get('stargazers_count', 0),
                             'forks': repo.get('forks_count', 0), 'created': repo.get('created_at', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(items)} GitHub trending repos")


def _fetch_fuel_prices():
    """Fetch fuel/gas price data from EIA."""
    if not _can_fetch('fuel_prices'):
        return
    _set_last_fetch('fuel_prices')
    try:
        # US gasoline prices from EIA
        resp = _http_session.get('https://api.eia.gov/v2/petroleum/pri/gnd/data/',
                            params={'api_key': 'DEMO_KEY', 'frequency': 'weekly', 'data[0]': 'value',
                                    'facets[product][]': 'EPM0', 'facets[duession][]': 'NUS',
                                    'sort[0][column]': 'period', 'sort[0][direction]': 'desc', 'length': '1'},
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            payload = _safe_response_json(resp, {})
            rows = payload.get('response', {}).get('data', []) if isinstance(payload, dict) else []
            if rows:
                with db_session() as db:
                    db.execute("DELETE FROM sitroom_events WHERE event_type = 'fuel_price'")
                    for r in rows[:5]:
                        eid = hashlib.sha256(f"fuel:{r.get('period','')}".encode()).hexdigest()[:16]
                        db.execute('''INSERT OR IGNORE INTO sitroom_events
                            (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                            VALUES (?, ?, ?, ?, 0, 0, 0, ?)''',
                            (eid, 'fuel_price', f"US Gasoline ({r.get('area-name', 'National')})",
                             _safe_float(r.get('value', 0)),
                             json.dumps({'price': r.get('value', ''), 'period': r.get('period', ''),
                                         'product': r.get('product-name', ''), 'area': r.get('area-name', '')})))
                    db.commit()
                log.info(f"Situation Room: cached fuel price data")
    except Exception as e:
        log.debug(f"Fuel prices fetch failed: {e}")


def _fetch_service_status():
    """Fetch cloud service status from public status pages."""
    if not _can_fetch('service_status'):
        return
    _set_last_fetch('service_status')

    services = []
    status_feeds = [
        ('AWS', 'https://status.aws.amazon.com/rss/all.rss'),
        ('GitHub', 'https://www.githubstatus.com/history.rss'),
        ('Cloudflare', 'https://www.cloudflarestatus.com/history.rss'),
        ('Google Cloud', 'https://status.cloud.google.com/en/feed.atom'),
        ('Azure', 'https://azure.status.microsoft/en-us/status/feed/'),
    ]
    for name, url in status_feeds:
        try:
            resp = _http_session.get(url, timeout=8, headers=_REQ_HEADERS)
            if resp.ok:
                items = _parse_feed(resp.text, name, 'Status')
                for item in items[:3]:
                    services.append({'service': name, 'title': item['title'],
                                     'published': item.get('published', ''), 'link': item.get('link', '')})
        except Exception:
            pass

    if not services:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'service_status'")
        for s in services:
            eid = hashlib.sha256((s['service'] + s['title']).encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, 0, 0, 0, ?, ?)''',
                (eid, 'service_status', f"[{s['service']}] {s['title'][:400]}", s.get('link', ''),
                 json.dumps({'service': s['service'], 'published': s.get('published', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(services)} service status items")


def _fetch_social_velocity():
    """Track news velocity — how fast stories spread across sources."""
    if not _can_fetch('social_velocity'):
        return
    _set_last_fetch('social_velocity')

    with db_session() as db:
        # Find keywords that appear in many articles (high velocity)
        rows = db.execute('''
            SELECT LOWER(SUBSTR(title, 1, 50)) as headline, COUNT(*) as cnt, GROUP_CONCAT(DISTINCT source_name) as sources
            FROM sitroom_news GROUP BY LOWER(SUBSTR(title, 1, 50))
            HAVING cnt >= 3 ORDER BY cnt DESC LIMIT 15
        ''').fetchall()

        db.execute("DELETE FROM sitroom_events WHERE event_type = 'social_velocity'")
        for r in rows:
            eid = hashlib.sha256(dict(r)['headline'].encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'social_velocity', dict(r)['headline'][:500], dict(r)['cnt'],
                 json.dumps({'count': dict(r)['cnt'], 'sources': dict(r)['sources']})))
        db.commit()
    log.info(f"Situation Room: computed {len(rows)} social velocity entries")


def _fetch_displacement():
    """Fetch UNHCR displacement/refugee data."""
    if not _can_fetch('displacement'):
        return
    _set_last_fetch('displacement')
    try:
        # UNHCR population statistics API (public, CC BY 4.0)
        resp = _http_session.get('https://api.unhcr.org/population/v1/asylum-decisions/',
                            params={'limit': 20, 'yearFrom': 2024, 'sort': 'decisions_recognized desc'},
                            timeout=_REQ_TIMEOUT, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
        if not resp.ok:
            # Fallback: use UNHCR RSS
            resp2 = _http_session.get('https://www.unhcr.org/rss/news.xml',
                                 timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
            if resp2.ok:
                items = _parse_feed(resp2.text, 'UNHCR', 'Displacement')
                with db_session() as db:
                    db.execute("DELETE FROM sitroom_events WHERE event_type = 'displacement'")
                    for a in items[:20]:
                        eid = hashlib.sha256((a['title'] + a.get('link', '')).encode()).hexdigest()[:16]
                        db.execute('''INSERT OR IGNORE INTO sitroom_events
                            (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                            VALUES (?, ?, ?, 0, 0, 0, ?, ?)''',
                            (eid, 'displacement', a['title'][:500], a.get('link', ''),
                             json.dumps({'published': a.get('published', ''), 'source': 'UNHCR'})))
                    db.commit()
                log.info(f"Situation Room: cached {len(items)} displacement items (RSS fallback)")
            return
        data = _safe_response_json(resp, {})
    except Exception as e:
        log.debug(f"UNHCR fetch failed: {e}")
        return

    items = data.get('items', [])
    if not items:
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'displacement'")
        for item in items[:20]:
            country = item.get('country_of_origin_en', item.get('country_of_origin', ''))
            asylum = item.get('country_of_asylum_en', item.get('country_of_asylum', ''))
            recognized = item.get('decisions_recognized', 0)
            total = item.get('decisions_total', 0)
            eid = hashlib.sha256(f"disp:{country}:{asylum}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, 0, 0, 0, ?)''',
                (eid, 'displacement', f"{country} -> {asylum}",
                 recognized or 0,
                 json.dumps({'origin': country, 'asylum': asylum, 'recognized': recognized,
                             'total': total, 'year': item.get('year', '')})))
        db.commit()
    log.info(f"Situation Room: cached {len(items)} displacement records")


# ─── Israel OREF Alerts ─────────────────────────────────────────────

def _fetch_oref_alerts():
    """Fetch Israel Home Front Command (OREF) real-time alerts."""
    if not _can_fetch('oref_alerts'):
        return
    _set_last_fetch('oref_alerts')
    try:
        # OREF public API — real-time rocket/siren alerts
        resp = _http_session.get('https://www.oref.org.il/WarningMessages/History/AlertsHistory.json',
                            timeout=_REQ_TIMEOUT,
                            headers={**_REQ_HEADERS, 'Referer': 'https://www.oref.org.il/',
                                     'X-Requested-With': 'XMLHttpRequest'})
        if not resp.ok:
            return
        data = _safe_response_json(resp, []) if resp.text.strip() else []
    except Exception as e:
        log.debug(f"OREF fetch failed: {e}")
        return

    if not data or not isinstance(data, list):
        return

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'oref_alert'")
        for alert in data[:50]:
            title = alert.get('data', alert.get('title', 'Alert'))
            cat = alert.get('category', '')
            alert_date = alert.get('alertDate', '')
            # Geocode common Israeli areas
            area = title.lower()
            lat, lng = 31.5, 34.8  # Default: central Israel
            if 'tel aviv' in area or 'gush dan' in area:
                lat, lng = 32.07, 34.78
            elif 'haifa' in area:
                lat, lng = 32.79, 34.99
            elif 'jerusalem' in area:
                lat, lng = 31.77, 35.23
            elif 'beer sheva' in area or 'negev' in area:
                lat, lng = 31.25, 34.79
            elif 'ashkelon' in area or 'sderot' in area:
                lat, lng = 31.67, 34.57
            elif 'eilat' in area:
                lat, lng = 29.56, 34.95
            elif 'galil' in area or 'tiberias' in area:
                lat, lng = 32.79, 35.53
            eid = hashlib.sha256(f"oref:{title}:{alert_date}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (eid, 'oref_alert', f"OREF: {title}", lat, lng, alert_date,
                 json.dumps({'category': cat, 'date': alert_date, 'raw': title})))
        db.commit()
    log.info(f"Situation Room: cached {len(data)} OREF alerts")


# ─── GDELT Full Events ─────────────────────────────────────────────

def _fetch_gdelt_events():
    """Fetch GDELT event counts and tone timeline (beyond just trending)."""
    if not _can_fetch('gdelt_events'):
        return
    _set_last_fetch('gdelt_events')

    results = {}
    # GDELT DOC API — event counts by theme in last 24h
    try:
        resp = _http_session.get('https://api.gdeltproject.org/api/v2/doc/doc',
                            params={'query': '', 'mode': 'TimelineVolInfo', 'format': 'json',
                                    'TIMESPAN': '24h'},
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            data = _safe_response_json(resp, {})
            if data:
                results['volume'] = data
    except Exception as e:
        log.debug(f"GDELT volume fetch failed: {e}")

    # Tone timeline (sentiment over time)
    try:
        resp = _http_session.get('https://api.gdeltproject.org/api/v2/doc/doc',
                            params={'query': '', 'mode': 'TimelineTone', 'format': 'json',
                                    'TIMESPAN': '72h'},
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            data = _safe_response_json(resp, {})
            if data:
                results['tone'] = data
    except Exception as e:
        log.debug(f"GDELT tone fetch failed: {e}")

    # Geographic hotspots (top locations mentioned)
    try:
        resp = _http_session.get('https://api.gdeltproject.org/api/v2/doc/doc',
                            params={'query': '', 'mode': 'PointData', 'format': 'json',
                                    'TIMESPAN': '24h', 'MAXPOINTS': 50},
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            data = _safe_response_json(resp, {})
            if data:
                results['hotspots'] = data
    except Exception as e:
        log.debug(f"GDELT hotspots fetch failed: {e}")

    if not results:
        return

    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_gdelt
            (id INTEGER PRIMARY KEY, data_type TEXT UNIQUE, value_json TEXT,
             cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        db.executemany('INSERT OR REPLACE INTO sitroom_gdelt (data_type, value_json) VALUES (?, ?)',
                      [(dtype, json.dumps(data)) for dtype, data in results.items()])
        db.commit()
    log.info(f"Situation Room: cached {len(results)} GDELT datasets")


# ─── COT Positioning (CFTC) ────────────────────────────────────────

def _fetch_cot_positioning():
    """Fetch CFTC Commitments of Traders positioning data."""
    if not _can_fetch('cot_positioning'):
        return
    _set_last_fetch('cot_positioning')
    try:
        # CFTC Disaggregated Futures — top commodities
        # Using the open data API (Socrata-compatible)
        resp = _http_session.get('https://publicreporting.cftc.gov/resource/jun7-fc8e.json',
                            params={'$limit': 50, '$order': 'report_date_as_yyyy_mm_dd DESC',
                                    '$where': "market_and_exchange_names LIKE '%CRUDE OIL%' OR "
                                              "market_and_exchange_names LIKE '%GOLD%' OR "
                                              "market_and_exchange_names LIKE '%S&P 500%' OR "
                                              "market_and_exchange_names LIKE '%EURO FX%' OR "
                                              "market_and_exchange_names LIKE '%NATURAL GAS%' OR "
                                              "market_and_exchange_names LIKE '%CORN%' OR "
                                              "market_and_exchange_names LIKE '%WHEAT%' OR "
                                              "market_and_exchange_names LIKE '%SILVER%'"},
                            timeout=15, headers=_REQ_HEADERS)
        if not resp.ok:
            return
        data = _safe_response_json(resp, [])
    except Exception as e:
        log.debug(f"CFTC COT fetch failed: {e}")
        return

    if not data:
        return

    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_cot
            (id INTEGER PRIMARY KEY, market TEXT, report_date TEXT,
             long_positions REAL, short_positions REAL, net_positions REAL,
             change_long REAL, change_short REAL,
             cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             UNIQUE(market, report_date))''')
        for row in data[:50]:
            market = row.get('market_and_exchange_names', '')[:100]
            report_date = row.get('report_date_as_yyyy_mm_dd', '')
            long_pos = float(row.get('noncomm_positions_long_all', 0) or 0)
            short_pos = float(row.get('noncomm_positions_short_all', 0) or 0)
            chg_long = float(row.get('change_in_noncomm_long_all', 0) or 0)
            chg_short = float(row.get('change_in_noncomm_short_all', 0) or 0)
            db.execute('''INSERT OR REPLACE INTO sitroom_cot
                (market, report_date, long_positions, short_positions, net_positions,
                 change_long, change_short) VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (market, report_date, long_pos, short_pos, long_pos - short_pos,
                 chg_long, chg_short))
        db.commit()
    log.info(f"Situation Room: cached {len(data)} COT positioning entries")


# ─── Refresh Orchestrator ──────────────────────────────────────────────

_REFRESH_TIERS = {
    'critical': [_fetch_earthquakes, _fetch_weather_alerts, _fetch_oref_alerts, _fetch_fires],
    'standard': [_fetch_rss_feeds, _fetch_market_data, _fetch_stablecoins,
                 _fetch_conflict_data, _compute_correlations,
                 _fetch_aviation, _fetch_space_weather, _fetch_volcanoes,
                 _fetch_predictions, _fetch_disease_outbreaks, _fetch_internet_outages,
                 _fetch_radiation, _fetch_sanctions, _fetch_displacement,
                 _fetch_ucdp_conflicts, _fetch_cyber_threats, _fetch_yield_curve,
                 _fetch_service_status, _fetch_social_velocity, _fetch_renewable_energy,
                 _fetch_fuel_prices, _fetch_product_hunt, _fetch_macro_stress,
                 _fetch_central_banks],
    'background': [_fetch_bigmac_index, _fetch_arxiv_papers, _fetch_github_trending,
                   _fetch_ais_ships, _fetch_cot_positioning, _fetch_gdelt_trending,
                   _fetch_gdelt_events],
}


def _safe_worker(func, app):
    """Run a single fetch worker with error isolation and app context."""
    try:
        with app.app_context():
            func()
    except Exception as e:
        log.warning(f'Fetch worker {func.__name__} failed: {e}')


def refresh_all_feeds():
    global _fetch_running
    with _state_lock:
        if _fetch_running:
            return False
        _fetch_running = True

    app = current_app._get_current_object()

    def _worker():
        global _fetch_running
        try:
            for tier_name in ('critical', 'standard', 'background'):
                tier_funcs = _REFRESH_TIERS[tier_name]
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {}
                    for worker_func in tier_funcs:
                        futures[executor.submit(_safe_worker, worker_func, app)] = worker_func.__name__
                    for future in as_completed(futures, timeout=120):
                        try:
                            future.result()
                        except Exception as e:
                            log.warning(f'Worker {futures[future]} failed: {e}')
        except Exception as e:
            log.exception(f"Situation Room refresh error: {e}")
        finally:
            with _state_lock:
                _fetch_running = False

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        with _state_lock:
            _fetch_running = False
        raise
    return True

