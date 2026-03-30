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
    'fires': 600, 'disease_outbreaks': 1800,
    'internet_outages': 600,
    'radiation': 1800, 'gdelt_trending': 600, 'sanctions': 3600,
    'displacement': 7200, 'ucdp': 3600, 'cyber_threats': 1800,
    'yield_curve': 3600, 'stablecoins': 600, 'correlation': 300,
    'service_status': 300, 'social_velocity': 600,
    'renewable': 3600, 'bigmac': 86400,
    'github_trending': 3600, 'fuel_prices': 7200,
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
    'supply_chain': [
        {'name': 'Supply Chain Dive', 'url': 'https://www.supplychaindive.com/feeds/news/', 'category': 'Supply Chain'},
        {'name': 'Freightwaves', 'url': 'https://www.freightwaves.com/feed', 'category': 'Supply Chain'},
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
            resp = requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}',
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
            resp = requests.get(f'https://query1.finance.yahoo.com/v8/finance/chart/{sym}',
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
        resp = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana,binancecoin,ripple,cardano,dogecoin&vs_currencies=usd&include_24hr_change=true',
                            timeout=_REQ_TIMEOUT, headers=_REQ_HEADERS)
        if resp.ok:
            names = {'bitcoin': 'BTC', 'ethereum': 'ETH', 'solana': 'SOL',
                     'binancecoin': 'BNB', 'ripple': 'XRP', 'cardano': 'ADA', 'dogecoin': 'DOGE'}
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


def _fetch_fires():
    """Fetch active fire detections from NASA FIRMS (MODIS/VIIRS CSV)."""
    if not _can_fetch('fires'):
        return
    _set_last_fetch('fires')
    try:
        # FIRMS VIIRS active fires (last 24h, CSV format, no API key for web service)
        resp = requests.get('https://firms.modaps.eosdis.nasa.gov/api/area/csv/DEMO_KEY/VIIRS_SNPP_NRT/world/1',
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

    with db_session() as db:
        db.execute("DELETE FROM sitroom_events WHERE event_type = 'fire'")
        for lat, lng, brightness, confidence, acq_date in fires:
            eid = hashlib.sha256(f"fire:{lat:.3f}:{lng:.3f}:{acq_date}".encode()).hexdigest()[:16]
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, magnitude, lat, lng, event_time, detail_json)
                VALUES (?, ?, ?, ?, ?, ?, 0, ?)''',
                (eid, 'fire', f"Fire detection ({confidence})" if confidence else 'Fire detection',
                 brightness, lat, lng,
                 json.dumps({'brightness': brightness, 'confidence': confidence, 'acq_date': acq_date})))
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
        resp = requests.get('https://radar.cloudflare.com/api/v1/annotations/outages?dateRange=1d&format=json',
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
            resp = requests.get('https://api.ioda.inetintel.cc.gatech.edu/v2/alerts/ongoing',
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


def _fetch_disease_outbreaks():
    """Fetch disease outbreak data from WHO RSS."""
    if not _can_fetch('disease_outbreaks'):
        return
    _set_last_fetch('disease_outbreaks')
    try:
        resp = requests.get('https://www.who.int/feeds/entity/don/en/rss.xml',
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
            db.execute('''INSERT OR IGNORE INTO sitroom_events
                (event_id, event_type, title, lat, lng, event_time, source_url, detail_json)
                VALUES (?, ?, ?, 0, 0, 0, ?, ?)''',
                (eid, 'disease', item['title'], item.get('link', ''),
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
        resp = requests.get('https://api.safecast.org/measurements.json',
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
        resp = requests.get('https://api.gdeltproject.org/api/v2/doc/doc',
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
        resp = requests.get('https://ucdpapi.pcr.uu.se/api/gedevents/24.1',
                            params={'pagesize': 50, 'page': 0},
                            timeout=15, headers=_REQ_HEADERS)
        if not resp.ok:
            return
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
        resp = requests.get('https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json',
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
        resp = requests.get('https://www.cisa.gov/cybersecurity-advisories/all.xml',
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
        resp = requests.get('https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/avg_interest_rates',
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
                 float(item.get('avg_interest_rate_amt', 0)),
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
        resp = requests.get('https://api.coingecko.com/api/v3/simple/price',
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
        for coin, vals in data.items():
            symbol = names.get(coin, coin.upper())
            price = vals.get('usd', 1.0)
            mcap = vals.get('usd_market_cap', 0)
            change = vals.get('usd_24h_change', 0)
            # Store as market entry
            db.execute('INSERT OR REPLACE INTO sitroom_markets (symbol, price, change_24h, market_type, label) VALUES (?, ?, ?, ?, ?)',
                       (symbol, price, round(change or 0, 4), 'stablecoin',
                        f"${mcap/1e9:.1f}B" if mcap else ''))
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
                            'detail': f'Oil at ${dict(oil)["price"]:.2f} with {me_news} Middle East headlines'})

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
        resp = requests.get('https://raw.githubusercontent.com/TheEconomist/big-mac-data/master/output-data/big-mac-raw-index.csv',
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


def _fetch_github_trending():
    """Fetch GitHub trending repositories."""
    if not _can_fetch('github_trending'):
        return
    _set_last_fetch('github_trending')
    try:
        resp = requests.get('https://api.github.com/search/repositories',
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
        resp = requests.get('https://api.eia.gov/v2/petroleum/pri/gnd/data/',
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
                             float(r.get('value', 0)),
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
            resp = requests.get(url, timeout=8, headers=_REQ_HEADERS)
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
            SELECT LOWER(SUBSTR(title, 1, 60)) as headline, COUNT(*) as cnt, GROUP_CONCAT(DISTINCT source_name) as sources
            FROM sitroom_news GROUP BY LOWER(SUBSTR(title, 1, 40))
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
        resp = requests.get('https://api.unhcr.org/population/v1/asylum-decisions/',
                            params={'limit': 20, 'yearFrom': 2024, 'sort': 'decisions_recognized desc'},
                            timeout=_REQ_TIMEOUT, headers={**_REQ_HEADERS, 'Accept': 'application/json'})
        if not resp.ok:
            # Fallback: use UNHCR RSS
            resp2 = requests.get('https://www.unhcr.org/rss/news.xml',
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
            _fetch_fires()
            _fetch_disease_outbreaks()
            _fetch_internet_outages()
            _fetch_radiation()
            _fetch_gdelt_trending()
            _fetch_sanctions()
            _fetch_displacement()
            _fetch_ucdp_conflicts()
            _fetch_cyber_threats()
            _fetch_yield_curve()
            _fetch_stablecoins()
            _fetch_service_status()
            _fetch_social_velocity()
            _fetch_renewable_energy()
            _fetch_bigmac_index()
            _fetch_github_trending()
            _fetch_fuel_prices()
            _compute_correlations()
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
    lines.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}')
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

@situation_room_bp.route('/api/sitroom/ai-briefing', methods=['POST'])
def api_sitroom_generate_ai_briefing():
    """Generate AI-powered strategic intelligence briefing from cached data."""
    with db_session() as db:
        news = db.execute("SELECT title, category FROM sitroom_news ORDER BY cached_at DESC LIMIT 20").fetchall()
        quakes = db.execute("SELECT title, magnitude FROM sitroom_events WHERE event_type = 'earthquake' AND magnitude >= 4 ORDER BY magnitude DESC LIMIT 5").fetchall()
        conflicts = db.execute("SELECT title FROM sitroom_events WHERE event_type IN ('conflict', 'ucdp_conflict') LIMIT 10").fetchall()
        markets = db.execute("SELECT symbol, price, change_24h FROM sitroom_markets WHERE market_type = 'index' LIMIT 5").fetchall()
        cyber = db.execute("SELECT title FROM sitroom_events WHERE event_type = 'cyber_threat' LIMIT 5").fetchall()

    # Build context for LLM
    context_parts = []
    if news:
        context_parts.append("TOP HEADLINES:\n" + "\n".join(f"- [{dict(n)['category']}] {dict(n)['title']}" for n in news[:15]))
    if quakes:
        context_parts.append("SEISMIC ACTIVITY:\n" + "\n".join(f"- M{dict(q)['magnitude']:.1f} {dict(q)['title']}" for q in quakes))
    if conflicts:
        context_parts.append("ACTIVE CONFLICTS:\n" + "\n".join(f"- {dict(c)['title']}" for c in conflicts))
    if markets:
        context_parts.append("MARKET INDICES:\n" + "\n".join(f"- {dict(m)['symbol']}: ${dict(m)['price']:.0f} ({dict(m)['change_24h']:+.1f}%)" for m in markets))
    if cyber:
        context_parts.append("CYBER THREATS:\n" + "\n".join(f"- {dict(c)['title']}" for c in cyber))

    context = "\n\n".join(context_parts)
    prompt = f"""You are an intelligence analyst. Based on the following situation data, produce a concise strategic intelligence briefing. Cover: key threats, geopolitical developments, market implications, and recommended watch items. Be specific, not generic.

{context}

Produce a briefing with sections: STRATEGIC OVERVIEW, KEY THREATS, MARKET OUTLOOK, WATCH ITEMS."""

    # Try Ollama first
    briefing = None
    try:
        resp = requests.post('http://localhost:11434/api/generate',
                             json={'model': 'llama3.2', 'prompt': prompt, 'stream': False},
                             timeout=60)
        if resp.ok:
            briefing = resp.json().get('response', '')
    except Exception:
        pass

    if not briefing:
        # Fallback: generate a structured summary without LLM
        briefing = "## STRATEGIC OVERVIEW\n"
        briefing += f"Monitoring {len(news)} news sources across multiple categories.\n\n"
        if quakes:
            briefing += "## SEISMIC ALERT\n"
            for q in quakes[:3]:
                briefing += f"- M{dict(q)['magnitude']:.1f} — {dict(q)['title']}\n"
            briefing += "\n"
        if conflicts:
            briefing += "## ACTIVE CONFLICTS\n"
            for c in conflicts[:5]:
                briefing += f"- {dict(c)['title']}\n"
            briefing += "\n"
        if markets:
            briefing += "## MARKET STATUS\n"
            for m in markets:
                ch = dict(m)['change_24h']
                briefing += f"- {dict(m)['symbol']}: {'UP' if ch >= 0 else 'DOWN'} {abs(ch):.1f}%\n"
            briefing += "\n"
        if cyber:
            briefing += "## CYBER THREATS\n"
            for c in cyber[:3]:
                briefing += f"- {dict(c)['title']}\n"

    # Cache the briefing
    with db_session() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS sitroom_briefings
            (id INTEGER PRIMARY KEY, content TEXT, generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        db.execute('INSERT INTO sitroom_briefings (content) VALUES (?)', (briefing,))
        db.commit()

    return jsonify({'briefing': briefing})


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
        resp = requests.get('https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v2/accounting/od/debt_to_penny',
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
