# Project N.O.M.A.D. for Windows

## Overview
Native Windows port of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — the most comprehensive offline survival command center available. No Docker required. 6 managed services, proactive AI alerts, interactive decision guides, medical module, training scenarios, food production, multi-node federation, power management, security cameras, and AI document intelligence. All 10 roadmap phases complete.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2) embedded browser
- **SQLite** — 30+ tables, WAL mode, auto-backups, performance indexes
- **Native process management** — subprocess for Ollama, kiwix-serve, Kolibri; threading HTTP server for CyberChef
- **pystray** — system tray icon for background operation
- **psutil** — system info (CPU via background monitor thread, RAM, GPU detection, disk devices)
- **MapLibre GL JS + PMTiles** — bundled locally (no CDN dependencies)
- **NukeMap v3.2.0** — 18 JS modules + Leaflet (bundled locally)

## Project Structure
```
nomad.py              # Entry point — Flask + WebView2 + tray + health monitor + service autostart
db.py                 # SQLite init (30+ tables), indexes, migrations
config.py             # Data directory management
build.spec            # PyInstaller spec for portable exe
icon.ico              # App icon (multi-size, 16-256px)
installer.iss         # Inno Setup installer script (v1.0.0)
ROADMAP.md            # 10-phase implementation plan (all complete)
.github/workflows/
  build.yml           # CI/CD — PyInstaller + Inno Setup, dual artifact release on tag push
web/
  app.py              # Flask routes (221 endpoints) — services, AI, ZIM, maps, alerts, medical, scenarios, garden, power, security, federation, documents
  static/             # logo.png, maplibre-gl.js, maplibre-gl.css, pmtiles.js (all local)
  templates/
    index.html        # Single-file dark dashboard (~11,500 lines, inline CSS/JS) — 9 tabs, 18 prep sub-tabs
  nukemap/            # NukeMap v3.2.0 — index.html, 18 JS modules, CSS, data/, lib/leaflet
services/
  manager.py          # Process manager — download (with resume), start, stop, track, uninstall
  ollama.py           # Ollama AI (download, model management, streaming chat, pull queue)
  kiwix.py            # Kiwix (kiwix-serve + tiered ZIM catalog)
  cyberchef.py        # CyberChef (GitHub Releases API + static HTTP server)
  kolibri.py          # Kolibri education (pip install + subprocess)
  qdrant.py           # Qdrant vector DB (GitHub Releases binary + REST API)
  stirling.py         # Stirling PDF (GitHub Releases jar + Java runtime)
```

## Key Paths
- **Data dir**: `%APPDATA%\ProjectNOMAD\` (configurable via wizard)
- **SQLite DB**: `{data_dir}\nomad.db`
- **Log file**: `{data_dir}\logs\nomad.log`
- **Services**: `{data_dir}\services\{ollama,kiwix,cyberchef,kolibri,qdrant,stirling}\`
- **Maps**: `{data_dir}\maps\`
- **Videos**: `{data_dir}\videos\`
- **KB uploads**: `{data_dir}\kb_uploads\`

## Run / Build
```bash
# Run from source
python nomad.py

# Build portable exe
pip install pyinstaller
pyinstaller build.spec
# Output: dist/ProjectNOMAD.exe

# Build installer (requires Inno Setup)
iscc installer.iss
# Output: ProjectNOMAD-Setup.exe
```

## Service URLs
| Service | Port |
|---------|------|
| Dashboard | 8080 |
| Ollama API | 11434 |
| Kiwix | 8888 |
| CyberChef | 8889 |
| Kolibri | 8300 |
| Qdrant | 6333 |
| Stirling PDF | 8443 |
| Node Discovery | UDP 18080 |

## Version
v1.0.0 — 32,000+ lines, 221 API routes, 30+ DB tables

## 9 Main Tabs
Services (Home), AI Chat, Library, Maps, Notes, Benchmark, Tools, Preparedness (18 sub-tabs), Settings

## 18 Preparedness Sub-Tabs
Checklists, Incidents, Inventory, Contacts, Security, Power, Garden, Medical, Calculators, Guides, Radio Ref, Quick Ref, Protocols, Vault, Weather, Signals, Operations, Family Plan

## 10 Completed Feature Phases

### Phase 1: Proactive AI Situational Awareness
- Background alert engine (5-min cycle) checks: burn rates <7d, expiring items <14d, pressure drop >4hPa, incident clusters 3+ in 48h, low stock
- Alert bar with bell icon + badge count, auto-opens on critical
- AI situation summary via Ollama (natural language)
- Browser notifications + alert sound on critical
- Alert dedup (24h) + auto-prune (7d)
- Tables: `alerts`
- Endpoints: `/api/alerts`, `/api/alerts/<id>/dismiss`, `/api/alerts/dismiss-all`, `/api/alerts/generate-summary`

### Phase 2: Interactive Decision Guides
- 7 JSON decision trees: water purification, wound assessment, fire starting, shelter construction, radio setup, food preservation, START triage
- Card-based UI with back/forward, breadcrumb trail
- "Ask AI" at any step, printable procedure cards
- Pure JS — works fully offline without Ollama
- New prep sub-tab: Guides

### Phase 3: Medical Module
- Patients table (linked to contacts): weight, age, sex, blood type, allergies[], medications[], conditions[]
- Vitals: BP, pulse, resp, temp, SpO2, pain (0-10), GCS (3-15) — color-coded abnormals
- Wound log: 8 types, 4 severities, location, description, treatment
- Drug interaction checker: 26 pairs (NSAIDs, anticoagulants, opioids, SSRIs, etc)
- Printable patient care card (HTML)
- Import patients from contacts with one click
- Tables: `patients`, `vitals_log`, `wound_log`
- New prep sub-tab: Medical

### Phase 4: Immersive Training Scenarios
- 4 scenarios: Grid Down (7 phases), Medical Crisis (5), Evacuation (5), Winter Storm (5)
- AI complication injector (50% chance between phases, uses real inventory/contacts data)
- Fallback complications when Ollama unavailable
- Decision logging with timestamps
- AI-scored After-Action Review (0-100)
- Scenario history with score tracking
- Table: `scenarios`
- Located in Tools tab

### Phase 5: Food Production Module
- Garden plots: name, dimensions (sq ft), sun exposure, soil type, total area calc
- Seed inventory: 25 species with auto-calculated viability by age
- Harvest log: crop, quantity, unit, plot source — auto-creates/updates inventory items
- Livestock: 10 species, per-animal health event logging
- USDA hardiness zone lookup (offline latitude-based, zones 3a-11a+)
- Tables: `garden_plots`, `seeds`, `harvest_log`, `livestock`
- New prep sub-tab: Garden

### Phase 6: Advanced Offline Maps
- Property boundary tool: polygon drawing, area (acres), perimeter (ft/miles)
- Print layout: PNG capture → HTML page with title, coordinates, compass, scale
- Map bookmarks: save/recall views
- Bearing & distance calculator: degrees + 16-point cardinal + km/mi with line
- 10 map tools total in toolbar

### Phase 7: Multi-Node Federation
- Auto-generated node UUID + customizable name
- UDP discovery on port 18080 (background listener daemon)
- One-click push/pull sync (inventory, contacts, checklists, notes, incidents, waypoints)
- Merge mode — no overwrites, strips IDs on import
- Sync log with direction, peer identity, item counts, timestamps
- Manual IP entry for cross-subnet connections
- Table: `sync_log`
- Located in Settings tab

### Phase 8: Power Management
- Device registry: 5 types (solar panel, battery, charge controller, inverter, generator) with type-specific specs
- Power log: battery voltage, SOC%, solar watts, solar Wh/day, load watts, load Wh/day, generator status
- Autonomy projection dashboard: net daily balance, color-coded gauges (green >7d, orange >3d, red <3d)
- Tables: `power_devices`, `power_log`
- New prep sub-tab: Power

### Phase 9: Security Module
- Camera registry + viewer: MJPEG (live), snapshot (5s auto-refresh), HLS
- Common camera URL examples (Reolink, Amcrest, Wyze, ONVIF)
- Access log: person, direction (entry/exit/patrol), location, method (visual/camera/sensor/radio)
- Security dashboard: threat level (from sit board), cameras count, 24h access, 48h incidents
- Tables: `cameras`, `access_log`
- New prep sub-tab: Security

### Phase 10: Deep Document Understanding
- AI document classifier: 8 categories (medical, property, vehicle, financial, legal, reference, personal, other)
- AI summary: 2-3 sentences per document
- Entity extraction: people, dates, medications, addresses, phones, vehicles, amounts, coordinates
- Cross-reference: extracted names matched against contacts DB
- Auto-runs after embedding completes
- Analyze All button for bulk processing
- Schema migration: 4 new columns on documents table

## Key Architecture Patterns
- **Background threads**: CPU monitor (2s), alert engine (5min), health monitor (10s), node discovery (UDP 18080)
- **Non-blocking CPU**: `_cpu_percent` global from daemon thread, endpoints read instantly
- **Two-click confirmations**: all destructive operations
- **Inline forms**: no prompt()/confirm() — all interactions via inline panels
- **Page Visibility API**: polling skips when `document.hidden`
- **NDJSON stream buffering**: chat uses `streamBuf` for partial lines
- **Offline-first**: MapLibre/PMTiles/Leaflet all bundled in `web/static/` and `web/nukemap/lib/`
- **LAN auth guard**: `@before_request` checks `X-Auth-Token` for dangerous endpoints from non-localhost
- **Install mutex**: `_installing` set prevents concurrent installs of same service
- **Download resume**: HTTP Range requests for partial file continuation

## Download UX
- Service installs: size on button (~310 MB), downloaded/total bytes, completion toast + notification
- ZIM catalog: unified view, per-item state (available/downloading/downloaded), 3 bulk buttons (Essentials/Standard/Everything)
- AI model queue: sequential pull with [2/12] position, speed/size, monotonic progress
- Map downloads: stale .tmp cleanup, retry resume, permission denied guidance
- Disk space warning before large downloads

## Gotchas
- NukeMap: `/nukemap` 301 redirects to `/nukemap/` (trailing slash for relative CSS/JS paths)
- NukeMap path traversal: normpath + startswith check (not just `'..' in filepath`)
- Kiwix: won't start without ZIM files (RuntimeError with user message)
- Stirling PDF: requires Java 17+ (downloads .jar, auto-installs Java)
- Qdrant: `--storage-path` CLI arg removed — use `QDRANT__STORAGE__STORAGE_PATH` env var
- PyInstaller: `_bootstrap()` must skip when `sys.frozen` or fork-bombs
- Kolibri: `_python_exe()` finds Python on PATH when frozen
- Protomaps planet URL: `https://data.source.coop/protomaps/openstreetmap/v4.pmtiles` (NOT build.protomaps.com — dead)
- pmtiles CLI: resolve asset URL via GitHub API (naming changes between releases)
- `web/static/` must exist and be committed or PyInstaller build fails
- Antivirus may block pmtiles.exe — user guided to add exclusion or run as Admin
