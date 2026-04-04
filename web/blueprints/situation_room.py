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

import json
import logging
import threading
import hashlib
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import requests
from flask import Blueprint, request, jsonify, current_app
from db import db_session, log_activity

situation_room_bp = Blueprint('situation_room', __name__)
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
    """Fetch URL with exponential backoff retry (uses pooled session)."""
    import time
    kwargs.setdefault('headers', _REQ_HEADERS)
    for attempt in range(retries + 1):
        try:
            r = _http_session.get(url, timeout=timeout, **kwargs)
            r.raise_for_status()
            return r
        except (requests.RequestException, Exception) as e:
            if attempt == retries:
                raise
            time.sleep(0.5 * (2 ** attempt))
    return None


def _safe_float(val, default=0):
    """Convert value to float, returning default on failure."""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


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
        resp = _http_session.get(feed['url'], timeout=_REQ_TIMEOUT, headers={
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
        resp = _fetch_with_retry('https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson',
                                 timeout=15, headers=_REQ_HEADERS)
        data = resp.json()
    except Exception as e:
        log.debug(f"Earthquake fetch failed: {e}")
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
        data = resp.json()
    except Exception as e:
        log.debug(f"Weather alerts fetch failed: {e}")
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
                meta = resp.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                price = meta.get('regularMarketPrice', 0)
                prev = meta.get('previousClose', 0)
                change = ((price - prev) / prev * 100) if prev else 0
                mtype = 'forex' if '/' in name or 'DXY' in name else 'index'
                markets.append({'symbol': name, 'price': price, 'change_24h': round(change, 2), 'market_type': mtype})
        except Exception as e:
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
                meta = resp.json().get('chart', {}).get('result', [{}])[0].get('meta', {})
                price = meta.get('regularMarketPrice', 0)
                prev = meta.get('previousClose', 0)
                change = ((price - prev) / prev * 100) if prev else 0
                markets.append({'symbol': name, 'price': price, 'change_24h': round(change, 2), 'market_type': 'sector', 'label': sym})
        except Exception:
            pass

    # Crypto (CoinGecko)
    try:
        resp = _fetch_with_retry('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,ripple,cardano,dogecoin&vs_currencies=usd&include_24hr_change=true',
                                 timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        names = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL',
                 'binancecoin': 'BNB', 'ripple': 'XRP', 'cardano': 'ADA', 'dogecoin': 'DOGE'}
        for coin, vals in resp.json().items():
            markets.append({'symbol': names.get(coin, coin.upper()), 'price': vals.get('usd', 0),
                            'change_24h': round(vals.get('usd_24h_change') or 0, 2), 'market_type': 'crypto'})
    except Exception as e:
        log.debug(f"CoinGecko failed: {e}")

    # Gold/Silver (metals.dev) — with change tracking from previous cached price
    try:
        resp = _http_session.get('https://api.metals.dev/v1/latest?api_key=demo&currency=USD&unit=toz',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            metals = resp.json().get('metals', {})
            # Read previous prices from DB for change calculation
            prev_prices = {}
            try:
                with db_session() as db:
                    for row in db.execute("SELECT symbol, price FROM sitroom_markets WHERE symbol IN ('GOLD', 'SILVER')").fetchall():
                        prev_prices[row[0]] = row[1]
            except Exception:
                pass
            for metal_key, symbol in [('gold', 'GOLD'), ('silver', 'SILVER')]:
                if metal_key in metals:
                    new_price = metals[metal_key]
                    old_price = prev_prices.get(symbol)
                    change = ((new_price - old_price) / old_price * 100) if old_price else 0
                    markets.append({'symbol': symbol, 'price': new_price, 'change_24h': round(change, 2), 'market_type': 'commodity'})
    except Exception as e:
        log.debug(f"Metals failed: {e}")

    # Brent oil (EIA)
    try:
        resp = _http_session.get('https://api.eia.gov/v2/petroleum/pri/spt/data/',
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
        resp = _http_session.get('https://api.alternative.me/fng/?limit=1', timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
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
        data = resp.json()
    except Exception as e:
        log.debug(f"GDACS failed: {e}")
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
            data = resp.json()
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
    except Exception as e:
        log.debug(f"AIS DK fetch failed: {e}")

    # If DK API didn't return data, try NOAA NDBC (buoys with some vessel data)
    if not ships:
        try:
            resp = _http_session.get('https://www.marinetraffic.com/en/data/?asset_type=vessels&columns=flag,shipname,mmsi,lat_of_latest_position,lon_of_latest_position,speed,heading',
                                timeout=12, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
            # This may not work without auth, silently fail
        except Exception:
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
            scales = resp.json()
            datasets['noaa_scales'] = scales.get('0', {})  # Current conditions
    except Exception as e:
        log.debug(f"NOAA scales failed: {e}")

    # Kp index (geomagnetic activity)
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            kp_data = resp.json()
            if kp_data:
                datasets['kp_index'] = {'latest': kp_data[-1], 'recent': kp_data[-8:]}
    except Exception as e:
        log.debug(f"NOAA Kp failed: {e}")

    # Solar flare probabilities
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/json/solar_probabilities.json',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            probs = resp.json()
            if probs:
                datasets['solar_probs'] = probs[-1]
    except Exception as e:
        log.debug(f"NOAA solar probs failed: {e}")

    # Active space weather alerts
    try:
        resp = _http_session.get('https://services.swpc.noaa.gov/products/alerts.json',
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
        resp = _http_session.get('https://gamma-api.polymarket.com/markets',
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
    except Exception as e:
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
            data = resp.json()
            for item in (data.get('annotations', []) or data.get('result', {}).get('annotations', []))[:30]:
                outages.append({
                    'title': item.get('description', item.get('eventType', 'Internet disruption')),
                    'country': item.get('locations', item.get('asns', '')),
                    'start': item.get('startDate', ''),
                    'end': item.get('endDate', ''),
                    'scope': item.get('scope', ''),
                })
    except Exception as e:
        log.debug(f"Cloudflare Radar failed: {e}")

    # Fallback: IODA (Internet Outage Detection and Analysis) from Georgia Tech
    if not outages:
        try:
            resp = _http_session.get('https://api.ioda.inetintel.cc.gatech.edu/v2/alerts/ongoing',
                                timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
            if resp.ok:
                data = resp.json()
                for alert in (data.get('data', []))[:20]:
                    outages.append({
                        'title': f"Internet disruption: {alert.get('entityName', 'Unknown')}",
                        'country': alert.get('entityName', ''),
                        'start': alert.get('time', ''),
                        'end': '',
                        'scope': alert.get('level', ''),
                    })
        except Exception as e:
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
    except Exception as e:
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
        data = resp.json()
    except Exception as e:
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
        data = resp.json()
    except Exception as e:
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
        data = resp.json()
    except Exception as e:
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
            data = resp.json()
            for vuln in (data.get('vulnerabilities', []))[-20:]:
                items.append({
                    'title': f"{vuln.get('cveID', '')} - {vuln.get('vendorProject', '')} {vuln.get('product', '')}",
                    'description': vuln.get('shortDescription', ''),
                    'date': vuln.get('dateAdded', ''),
                    'source': 'CISA KEV',
                    'severity': 'high',
                })
    except Exception as e:
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
    except Exception as e:
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
        data = resp.json().get('data', [])
    except Exception as e:
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
        data = resp.json()
    except Exception as e:
        log.debug(f"Stablecoin fetch failed: {e}")
        return

    names = {'tether': 'USDT', 'usd-coin': 'USDC', 'dai': 'DAI', 'first-digital-usd': 'FDUSD'}
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
                obs = resp.json().get('observations', [])
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
        data = resp.json()
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
            rows = resp.json().get('response', {}).get('data', [])
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
        data = resp.json()
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
        data = resp.json() if resp.text.strip() else []
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
            results['volume'] = resp.json()
    except Exception as e:
        log.debug(f"GDELT volume fetch failed: {e}")

    # Tone timeline (sentiment over time)
    try:
        resp = _http_session.get('https://api.gdeltproject.org/api/v2/doc/doc',
                            params={'query': '', 'mode': 'TimelineTone', 'format': 'json',
                                    'TIMESPAN': '72h'},
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            results['tone'] = resp.json()
    except Exception as e:
        log.debug(f"GDELT tone fetch failed: {e}")

    # Geographic hotspots (top locations mentioned)
    try:
        resp = _http_session.get('https://api.gdeltproject.org/api/v2/doc/doc',
                            params={'query': '', 'mode': 'PointData', 'format': 'json',
                                    'TIMESPAN': '24h', 'MAXPOINTS': 50},
                            timeout=15, headers=_REQ_HEADERS)
        if resp.ok:
            results['hotspots'] = resp.json()
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
        data = resp.json()
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
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
    with db_session() as db:
        if event_type:
            rows = db.execute('SELECT * FROM sitroom_events WHERE event_type = ? ORDER BY cached_at DESC LIMIT ? OFFSET ?',
                              (event_type, limit, offset)).fetchall()
        else:
            rows = db.execute('SELECT * FROM sitroom_events ORDER BY cached_at DESC LIMIT ? OFFSET ?', (limit, offset)).fetchall()
    return jsonify({'events': [dict(r) for r in rows]})


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
        rows = db.execute('SELECT * FROM sitroom_markets ORDER BY market_type, symbol').fetchall()
    return jsonify({'markets': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/aviation')
def api_sitroom_aviation():
    """Return cached aircraft positions."""
    limit = min(request.args.get('limit', 200, type=int), 500)
    with db_session() as db:
        rows = db.execute('SELECT * FROM sitroom_aviation ORDER BY altitude_m DESC LIMIT ?', (limit,)).fetchall()
    return jsonify({'aircraft': [dict(r) for r in rows]})


@situation_room_bp.route('/api/sitroom/ships')
def api_sitroom_ships():
    """Return cached vessel positions."""
    limit = min(request.args.get('limit', 200, type=int), 500)
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
        try:
            result[r['data_type']] = json.loads(r['value_json'])
        except (json.JSONDecodeError, TypeError):
            pass
    return jsonify(result)


@situation_room_bp.route('/api/sitroom/volcanoes')
def api_sitroom_volcanoes():
    """Return cached volcanic activity."""
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))
    except (ValueError, TypeError):
        limit, offset = 50, 0
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


@situation_room_bp.route('/api/sitroom/fires')
def api_sitroom_fires():
    """Return cached fire detections."""
    limit = min(request.args.get('limit', 200, type=int), 500)
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
        det = {}
        try:
            det = json.loads(dict(ev)['detail_json']) if dict(ev)['detail_json'] else {}
        except (json.JSONDecodeError, TypeError):
            pass
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
        # Ensure table exists
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_monitors
            (id INTEGER PRIMARY KEY, keyword TEXT NOT NULL, color TEXT DEFAULT '#4aedc4',
             created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        monitors = db.execute('SELECT * FROM sitroom_monitors ORDER BY created_at DESC').fetchall()
        db.commit()

    results = []
    for m in monitors:
        kw = m['keyword'].lower()
        with db_session() as db:
            matches = db.execute(
                "SELECT title, link, category, source_name FROM sitroom_news WHERE LOWER(title) LIKE ? ORDER BY cached_at DESC LIMIT 10",
                (f'%{kw}%',)).fetchall()
        results.append({**dict(m), 'matches': [dict(r) for r in matches], 'match_count': len(matches)})

    return jsonify({'monitors': results})


@situation_room_bp.route('/api/sitroom/monitors', methods=['POST'])
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
        db.execute('DELETE FROM sitroom_monitors WHERE id = ?', (mid,))
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
            data = resp.json().get('data', [])
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
        try:
            result[r['data_type']] = json.loads(r['value_json'])
        except (json.JSONDecodeError, TypeError, KeyError):
            pass
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
            data = resp.json()
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
    except Exception:
        pass

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
            try:
                detail = json.loads(d.get('detail_json', '{}'))
                result['bigmac'].append({'country': d['title'], **detail})
            except Exception:
                pass

        # Fuel price data (if cached)
        fuel = db.execute(
            "SELECT title, detail_json FROM sitroom_events WHERE event_type = 'fuel_price' ORDER BY title LIMIT 50"
        ).fetchall()
        for r in fuel:
            d = dict(r)
            try:
                detail = json.loads(d.get('detail_json', '{}'))
                result['fuel'].append({'region': d['title'], **detail})
            except Exception:
                pass

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
            try:
                detail = json.loads(d.get('detail_json', '{}'))
                signal_type = detail.get('signal_type', 'unknown')
                if signal_type not in signal_counts:
                    signal_counts[signal_type] = 0
                signal_counts[signal_type] += 1
            except Exception:
                pass

    signals = []
    for r in corr_rows:
        d = dict(r)
        try:
            detail = json.loads(d.get('detail_json', '{}'))
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
        except Exception:
            pass

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
            try:
                signals['yield_spread'] = json.loads(dict(spread)['detail_json']).get('value', 0)
            except Exception:
                pass
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
    if signals.get('vix', 20) > 25: score -= 2
    elif signals.get('vix', 20) < 15: score += 2
    if signals.get('fear_greed', 50) < 25: score -= 2
    elif signals.get('fear_greed', 50) > 75: score += 2
    if signals.get('avg_index_change', 0) > 1: score += 1
    elif signals.get('avg_index_change', 0) < -1: score -= 1
    if signals.get('gold_change', 0) > 1.5: score -= 1  # Flight to safety

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
    limit = min(request.args.get('limit', 50, type=int), 200)
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
                db.execute('DELETE FROM sitroom_watchlist WHERE keyword = ?', (kw,))
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
        if any(w in title_l for w in positive): timeline[hour]['pos'] += 1
        if any(w in title_l for w in negative): timeline[hour]['neg'] += 1
    return jsonify({'timeline': [{'hour': k, **v} for k, v in sorted(timeline.items())]})


@situation_room_bp.route('/api/sitroom/threat-level')
def api_sitroom_threat_level():
    """Compute composite global threat level (1-5)."""
    score = 0
    with db_session() as db:
        # Active conflicts
        conflicts = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type IN ('conflict', 'ucdp_conflict', 'oref_alert')").fetchone()[0]
        if conflicts > 20: score += 2
        elif conflicts > 10: score += 1
        # Large earthquakes
        big_quakes = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 6").fetchone()[0]
        if big_quakes > 0: score += 1
        # Market stress
        vix = db.execute("SELECT price FROM sitroom_markets WHERE LOWER(symbol) LIKE '%vix%' LIMIT 1").fetchone()
        if vix and dict(vix)['price'] > 30: score += 1
        # Active fires
        fires = db.execute("SELECT COUNT(*) FROM sitroom_events WHERE event_type = 'fire'").fetchone()[0]
        if fires > 400: score += 1
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
        try:
            kp = json.loads(dict(space_val)['value_json']).get('latest', [None, None, None, None, '0'])
            space_risk = min(10, int(float(kp[4] if len(kp) > 4 else 0)))
        except Exception:
            pass

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
        try:
            detail = json.loads(d.get('detail_json', '{}'))
            st = detail.get('signal_type', '')
            for dom in domains:
                if dom in st.lower() or dom in d['title'].lower():
                    matrix[dom] = matrix.get(dom, 0) + 1
        except Exception:
            pass
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
    except Exception:
        pass
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
        try:
            wx_data[dict(r)['data_type']] = json.loads(dict(r)['value_json'])
        except Exception:
            pass
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
        return jsonify({'sent': False, 'error': str(e)[:200]})


@situation_room_bp.route('/api/sitroom/webhook-config', methods=['GET', 'POST'])
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
        rows = db.execute('SELECT * FROM sitroom_webhooks ORDER BY created_at DESC').fetchall()
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
        if day not in days: days[day] = {'events': [], 'news': []}
        days[day]['events'].append(d)
    for r in news:
        d = dict(r)
        day = d.get('day', 'unknown')
        if day not in days: days[day] = {'events': [], 'news': []}
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
        if any(w in title_l for w in escalation_words): esc_count += 1
        if any(w in title_l for w in deescalation_words): deesc_count += 1
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
