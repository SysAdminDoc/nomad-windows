<div align="center">
<img src="nomad-mark.png" width="180" height="180"/>

# NOMAD Field Desk v1.0.0
### Desktop-First Offline Preparedness and Field Operations Workspace

**Free. Open Source. No Internet Required After Setup.**

Cross-platform — runs natively on Windows, Linux, and macOS. No Docker, no WSL, no VMs. 8 managed services, 600+ API routes, 95 database tables, **Situation Room** with full [World Monitor](https://github.com/koala73/worldmonitor) parity (86 cards, 435+ feeds, 32 data sources, 20 map layers + 3D globe, correlation engine, 30 OSINT channels), situation-aware AI with persistent memory, vision, and action execution, conversation branching with "What If" scenarios, Zambretti offline weather prediction, full inventory management with barcode/UPC scanning and receipt OCR, 42 interactive calculators, wiki-linked notes, media library with resume playback, VIPTrack military aircraft tracker, and a fully customizable dashboard with 5 themes including night vision and e-ink modes.

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/project-nomad-desktop?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest)
[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

> Competitors charge $280+ for a USB stick with curated content (Prepper Disk, Prep Drive). NOMAD Field Desk gives you a richer local-first workspace for preparedness planning, field reference, operations tracking, AI-assisted decision support, and offline knowledge management — without subscriptions or cloud lock-in.

**[Download for Windows (Portable)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMADFieldDesk-Windows.exe)** — single file, no install needed, run from anywhere (USB, desktop, etc.)

**[Download for Windows (Installer)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMAD-Setup.exe)** — installs to Program Files with Start Menu shortcut and desktop icon

**[Download for Linux](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMADFieldDesk-Linux)** — portable binary, `chmod +x` and run

**[Download for macOS](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMADFieldDesk-macOS)** — portable binary, `chmod +x` and run

---

## What Makes This Different

### Intelligence & Awareness
- **Situation Room** — Comprehensive [World Monitor](https://worldmonitor.app)-class global intelligence dashboard as the default landing page. **86 UI cards**, **32 data sources**, **72 API routes**, **30 background fetch workers** — all free, no API keys required. Aggregates **435+ RSS feeds** across 40+ categories, **30 Telegram OSINT channels** via RSS bridge (BNO News, Bellingcat, OSINTdefender, DeepState UA, Aurora Intel, and more), **8 think tank feeds** (Atlantic Council, CSIS, Brookings, Carnegie, RAND, Chatham House, CFR), USGS earthquakes, NWS severe weather, GDACS crises, UCDP armed conflicts, CISA cyber threats (KEV + advisories), NASA FIRMS satellite fire detection, WHO disease outbreaks, Cloudflare/IODA internet outages, Safecast radiation monitoring, GDELT trending intelligence, OFAC sanctions, UNHCR displacement, Polymarket predictions, and more. **~59 market symbols**: stock indices (S&P 500, NASDAQ, DOW, FTSE, DAX, Nikkei, Hang Seng, Euro Stoxx), forex (EUR/USD, GBP/USD, USD/JPY, DXY), 7 crypto coins, 4 stablecoins with depeg detection, 11 S&P sector ETFs, commodities (gold, silver, oil), Fear & Greed Index, yield curve (FRED), and national debt (US Treasury). **20 interactive map layers** with 440+ static infrastructure points: earthquakes, weather, crises, aviation, volcanoes, fires, nuclear sites (51), military bases (58), undersea cables (20), data centers (46), pipelines (26), waterways (14), spaceports (16), shipping hubs (16), UCDP conflicts, airports (20), financial centers (16), mining sites (20), tech HQs (20) — plus day/night terminator and **3D globe** via MapLibre GL native globe projection. **Cross-domain correlation engine** detects convergent signals across military-economic, disaster-cascade, cyber-infrastructure, escalation, energy-geopolitical, and radiation domains. **AI strategic briefing** via local Ollama with structured fallback. **Command palette** (Ctrl+K) for instant search across all cached data. **Country deep dive** slide-in panel. **Keyword monitors** with persistent watch lists. Panel drag reorder, collapse, map resize drag handle, map fullscreen (F key), scrolling market ribbon, DEFCON-style threat level badge, UTC + world clock (12 timezones), event timeline, critical alert toasts, intelligence report export (text SITREP), news deduplication (Jaccard similarity), sector heatmap, Fear & Greed gauge, stablecoin depeg monitoring, Big Mac Index (PPP comparison), fuel prices, GitHub trending, Product Hunt, earnings tracker, social velocity, service status (AWS/GitHub/Cloudflare/GCP/Azure), humanitarian overview, intelligence gap detection (27-source freshness monitor), news sentiment analysis, market brief generation, population exposure estimation, playback time slider, story detail modal, and 12 live YouTube news channel embeds. All data cached to SQLite for full offline access.
- **Zambretti Offline Weather Prediction** — Pure barometric pressure-based forecasting that works without any internet. Pressure history graph, trend analysis, weather-triggered alerts and automated action rules when storms approach.
- **Proactive + Predictive Alerts** — Background engine monitors burn rates, expiring items, pressure drops, and incident clusters every 5 minutes. Alerts fire for rapid pressure drops (>4 hPa = storm warning), extreme temps, and inventory depletion.
- **Situation-Aware AI with Memory & Vision** — The AI knows your actual inventory, burn rates, incidents, contacts, weather, power, patients, and garden data. Persistent memory remembers your location, group size, and ongoing situations. AI can execute actions directly ("Add 50 gallons of water to inventory"). Multimodal support lets you attach images for AI analysis.
- **AI SITREP Generator** — One-click military-format situation report compiled from 24h of activity, inventory changes, incidents, weather, power, and medical data.
- **Conversation Branching** — Fork any AI conversation at any message. "What If?" scenarios let you explore alternate decisions without losing the original thread. Branch management panel for navigating between timelines.
- **VIPTrack** — Military & VIP aircraft tracker using live ADS-B data feeds. Monitors global military aviation activity with type-accurate aircraft silhouettes, altitude-colored trails, watchlist alerts, and comprehensive intelligence databases. Launches embedded or via hosted fallback.

### Preparedness & Inventory
- **Advanced Inventory System** — Supply tracking with barcode/QR scanning, UPC database lookup (76 pre-loaded items), lot number tracking, check-in/check-out ("who has the generator?"), photo attachments, daily burn rate projections, expiration alerts, auto-generated shopping lists, location tracking, and 5 quick-entry templates (155 items).
- **Receipt Scanner** — Drag-and-drop or camera-capture receipt images. AI Vision (Gemma 3, LLaVA) or Tesseract OCR parses items, quantities, and prices. Bulk import parsed items into inventory with one click.
- **AI Vision Scanner** — Photograph items and let multimodal AI identify and categorize them for inventory entry.
- **Interactive Decision Guides** — 21 step-by-step branching guides with 300+ decision nodes covering water, wounds, fire, shelter, radio, food, triage, and 14 more topics. Works fully offline without AI.
- **Medical Module** — Patient profiles with vital signs trending charts (HR, BP, SpO2, temp over time), wound documentation with photo capture and side-by-side healing comparison, 26-pair drug interaction checker, expiring medication tracker, TCCC MARCH protocol wizard, START triage board, SBAR handoff reports, dosage calculator, and printable care cards. New printable 8-page Medical Reference Flipbook (pocket-sized 4x6").
- **Training Scenarios** — 4 multi-phase survival simulations with AI-generated complications based on your real inventory. Scored after-action reviews track improvement. Multi-node group exercises via federation.
- **Analytics Dashboard** — Visual charts for inventory trends, category breakdown, consumption/burn rate, weather history, power history, and patient vitals.

### Knowledge & Notes
- **Wiki-Linked Notes** — Obsidian-style `[[Note Title]]` bidirectional linking with backlink panel, tag-based filtering, 6 built-in templates (SITREP, Incident Report, Patrol Log, Comms Log, Meeting Notes, Daily Journal), file attachments, and markdown preview.
- **Media Library with Resume** — Video, audio, and book library with resume playback ("Continue Watching"), playlist creation, metadata editor, and 210 curated survival channels.
- **Knowledge Base Workspaces** — Create named knowledge bases ("Medical KB", "Water KB") with folder-watch auto-indexing. Model cards show parameter count, quantization, and RAM requirements.

### Communications & Radio
- **DTMF Tone Generator** — Full 16-key keypad generating accurate dual-tone frequencies via WebAudio. Sequence input for automated playback.
- **NATO Phonetic Alphabet Trainer** — Interactive quiz mode with scoring, plus complete A-Z + 0-9 reference grid.
- **Antenna Length Calculator** — Half-wave dipole, quarter-wave vertical, full-wave loop, and J-pole calculations from any frequency.
- **HF Propagation Forecast** — Band condition data for HF radio planning.
- **Mesh Radio** — Meshtastic bridge for LoRa mesh messaging, comms status board aggregating all channels (LAN/mesh/HF/VHF/federation).
- **LAN Chat with Channels** — Local network messaging with named channels (General, Security, Medical, Logistics), presence indicators showing online nodes, AES-GCM encrypted messages, and file transfer support.
- **Dead Drop Messaging** — Encrypted messages for USB thumb drive exchange using shared secret keys.

### Garden & Food Production
- **Companion Planting Guide** — 20 plant pair relationships (companion + antagonist) with searchable reference.
- **Pest & Disease Guide** — 10 common garden pest reference cards with symptoms, treatment, and prevention.
- **Seed Inventory** — Track seed stock with viability percentages, days to maturity, and planting season.
- **Planting Calendar** — Zone-based planting/harvest date calculations.
- **Harvest Yield Tracking** — Log actual vs expected yield with caloric output analysis.
- **Garden Geo Overlay** — Plot boundaries on the map with lat/lng coordinates and GeoJSON.

### Maps & Navigation
- **Offline Maps** — MapLibre GL + PMTiles with 50+ tile sources, downloadable per-region.
- **3 Map Styles** — Default, dark tactical, and satellite — cycle with one click.
- **Distance Measurement** — Click-to-measure Haversine distance calculator on map.
- **Elevation Profiles** — Canvas-based elevation charts for routes with contour line overlay.
- **Geocode Search** — Location search with autocomplete and reverse geocode on click.
- **Print Map** — Export current map view as PNG and print via browser.
- **GPX Import/Export** — Load GPS tracks onto the map, export waypoints as GPX files.
- **Perimeter Zones** — Define security zones with GeoJSON boundaries, camera/waypoint associations, threat levels, and entry/exit alerts.

### Security & Operations
- **Watch Rotation Planner** — Create shift schedules with customizable duration, personnel assignment, and printable views.
- **Perimeter Zones** — GeoJSON zone boundaries with camera associations, threat level assignments, and color-coded map overlays.
- **IP Camera Feeds** — MJPEG, snapshot, and HLS camera integration with access logging and security dashboard.
- **Weather Action Rules** — Automated triggers based on weather conditions (pressure drops, temperature extremes) with configurable thresholds, action types, and cooldowns.

### Benchmarking & Diagnostics
- **AI Inference Benchmark** — Measure tokens/second for any installed model.
- **Storage I/O Benchmark** — 32MB read/write test to verify USB drive speed.
- **Network Throughput** — TCP socket test measuring LAN speed in Mbps.
- **Historical Comparison** — Chart benchmark scores over time to detect hardware degradation.

### Customization & UX
- **Full Customization Panel** — Right-side slide-out panel to toggle any sidebar tab on/off, show/hide any home page section, switch themes, change UI scale, and pick dashboard modes. All preferences persist in localStorage.
- **Dashboard Widget Configuration** — Drag-and-drop widget reordering with resizable widgets (normal, wide, full-width). Toggle widgets on/off through a visual manager.
- **Bento Grid Dashboard** — Asymmetric two-column layout: Situation Dashboard + Needs Overview side-by-side, services full-width, Field Documents + Activity Log side-by-side.
- **Persistent AI Copilot Dock** — Fixed bottom bar available on every tab. Ask questions, get answers, dismiss when done. Ctrl+/ focuses instantly. Voice input supported.
- **5 Themes** — Desert (default light), Night Ops (tactical dark), Cyber (blue dark), Red Light (night vision preserving scotopic vision), E-Ink (high-contrast black-and-white for e-readers and paper-like displays).
- **Status Strip Pills** — Colored pill indicators with live status dots for services, supplies, contacts, alerts, and situation.
- **Desktop Window Layout** — Desktop-first shell with dense but orderly workspace layouts, predictable window resizing, and keyboard-friendly navigation.
- **Voice Input** — Hands-free inventory entry and AI chat via Web Speech API with natural language parsing.
- **Form State Recovery** — Auto-saves form inputs to localStorage. Prevents data loss on accidental navigation or crash.
- **RTL Language Support** — Full right-to-left layout for Arabic, Hebrew, and other RTL languages.
- **Internationalization** — `data-i18n` attribute system with language selector and translation API.

---

## 12 Main Tabs

| Tab | What It Does |
|-----|-------------|
| **Situation Room** | Default landing page — World Monitor-class dashboard with 86 cards, 435+ RSS feeds, 30 OSINT channels, 32 data sources, 20 map layers (+3D globe), 440+ infrastructure points, correlation engine, AI briefing, command palette, country deep dive, keyword monitors |
| **Home** | Bento grid dashboard with configurable widgets, needs overview, services, field documents, activity log |
| **AI Chat** | Local AI with 19 presets, multimodal vision, conversation branching, model cards, situation awareness, persistent memory, SITREP generation, action execution, document intelligence, RAG pipeline |
| **Library** | ZIM content library (100+ datasets, 14 categories) with Wikipedia tier selector, content updates, bulk downloads |
| **Maps** | Offline maps with 50+ sources, 3 styles, waypoints, perimeter zones, elevation profiles, geocode search, measurement, GPX, print, bookmarks |
| **Notes** | Wiki-linked markdown notes with tags, backlinks, templates, attachments, daily journal, live preview |
| **Media** | 210 survival channels, video/audio/book library, resume playback, playlists, metadata editor, BitTorrent |
| **Tools** | NukeMap, VIPTrack, Meshtastic, DTMF generator, phonetic trainer, guided drills, immersive training scenarios |
| **Preparedness** | 26 sub-tabs: inventory, medical, garden, power, security, radio, analytics, calculators, guides, and more |
| **Readiness** | Readiness score dashboard with category breakdown, improvement actions, coverage overview |
| **Diagnostics** | CPU, memory, disk, AI inference, storage I/O, network throughput scoring with trend history |
| **Settings** | System monitoring, AI models, task scheduler, watch rotation, serial ports, system health, CSV import, sync, i18n, preferences |

## 8 Managed Services

| Service | What It Does | Port |
|---------|-------------|------|
| **Ollama** | Local AI chat — Qwen3, Gemma 3, MedGemma, DeepSeek-R1 + GPU auto-detection | 11434 |
| **Kiwix** | Offline Wikipedia, medical references, survival guides, Army field manuals | 8888 |
| **CyberChef** | Encryption, encoding, hashing, 400+ data operations by GCHQ | 8889 |
| **FlatNotes** | Markdown note-taking with tags, search, and flat-file storage | 8890 |
| **Kolibri** | Khan Academy courses, textbooks, progress tracking | 8300 |
| **Qdrant** | Vector database for document upload and semantic search (RAG) | 6333 |
| **Stirling PDF** | Merge, split, compress, convert, OCR — 50+ PDF tools | 8443 |
| **BitTorrent** | Built-in libtorrent client with 152 curated survival torrent collections | in-process |

## 26 Preparedness Sub-Tabs

| Sub-Tab | Features |
|---------|---------|
| **Inventory** | Supply tracking with barcode/QR, UPC database (76 items), receipt scanner (AI Vision + OCR), AI vision scanner, lot numbers, check-in/out, photos, burn rates, expiration alerts, auto-shopping list, 5 templates (155 items), CSV import/export, location tracking |
| **Contacts** | Emergency directory with callsigns, roles, skills, blood types, rally points, medical notes |
| **Checklists** | 15 templates (72hr kit, bug-out bag, vehicle kit, winter storm, CBRN shelter, infant kit, and more) |
| **Medical** | Patient profiles, vital signs trending charts, wound photos with healing comparison, drug interactions, expiring med tracker, TCCC/MARCH wizard, triage board, SBAR handoffs, dosage calculator, printable care cards, 8-page Medical Reference Flipbook |
| **Incidents** | Chronological event timeline with severity levels, category filtering, cluster detection |
| **Family Plan** | FEMA-style emergency plan: meeting locations, evacuation routes, household members, insurance/utility info |
| **Security** | IP camera feeds (MJPEG/snapshot/HLS), perimeter zones with GeoJSON, access logging, security dashboard with threat level |
| **Power** | Device registry, power logging, autonomy projection dashboard, sensor time-series charts |
| **Garden** | Plots with geo overlay, companion planting guide (20 pairs), pest/disease guide (10 entries), seed inventory, harvest log, livestock, zone lookup, planting calendar, yield analysis, preservation log |
| **Weather** | Zambretti offline prediction, barometric pressure history graph, trend analysis, weather-triggered alerts and action rules, wind chill/heat index calculator |
| **Guides** | 21 interactive decision trees with 300+ nodes. "Ask AI" at any step. Printable procedure cards. |
| **Calculators** | 42 calculators: water, food, solar, ballistics, fallout, canning, IV drip, dead reckoning, antenna length, and more |
| **Procedures** | 17 emergency procedures with printable wallet cards |
| **Radio** | Frequency table (FRS/GMRS/MURS/CB/HAM/NOAA), DTMF tone generator, phonetic trainer, antenna calculator, HF propagation forecast, comms status board, radio profiles |
| **Quick Ref** | 56+ reference cards: NATO alphabet, Morse code, triage, companion planting, wild edibles, TCCC/MARCH, and more |
| **Signals** | Ground-to-air emergency signals, sound signal patterns, smoke signal guide |
| **Command Post** | SITREP generator (AI-powered), dead drop messaging, message cipher, threat assessment matrix, ICS 309/214 forms, emergency broadcast |
| **Journal** | Daily journal entries with mood tracking, tags, chronological timeline, full export |
| **Secure Vault** | AES-256-GCM encrypted storage for passwords, coordinates, sensitive documents |
| **Skills** | 60 survival skills across 10 categories with proficiency tracking |
| **Ammo** | Ammunition inventory with caliber-grouped summary cards |
| **Community** | Community resource registry with trust levels, skills/equipment tracking, mutual aid agreements |
| **Radiation** | Nuclear dose rate log with cumulative rem tracking |
| **Fuel** | Fuel storage tracking with type-grouped totals and expiry monitoring |
| **Equipment** | Equipment maintenance log with service scheduling |
| **Analytics** | Visual charts: inventory trends, category breakdown, consumption rate, weather history, power history, vitals |

## 9 Printable Field Documents

| Document | Description |
|----------|-------------|
| **Operations Binder** | Complete multi-page reference: TOC, contacts, frequencies, medical cards, inventory, checklists, waypoints, procedures, family plan. Available as HTML or PDF. |
| **Wallet Cards** | 5 lamination-ready cards (3.375"x2.125"): ICE, blood type, medications, rally points, frequency quick-ref. PDF export. |
| **SOI** | Signal Operating Instructions: frequency assignments, call sign matrix, radio profiles, net schedule. PDF export. |
| **Frequency Card** | Standard emergency frequencies with team contacts |
| **Medical Cards** | Per-patient vital signs, medications, conditions |
| **Medical Flipbook** | 8-page pocket-sized (4x6") reference: vital signs, GCS, TCCC MARCH, drug dosages, wound care, anaphylaxis, CPR, fractures, hypothermia, envenomation, SBAR, 9-Line MEDEVAC |
| **Bug-Out Checklist** | Grab-and-go packing list with rally points |
| **Inventory Report** | Full supply list with quantities, locations, expiration dates |
| **Contact Directory** | Complete personnel directory |

---

## Quick Start

### Option 1: Windows Portable (no install)
1. Download **[NOMADFieldDesk-Windows.exe](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMADFieldDesk-Windows.exe)**
2. Double-click to run — works from USB drives, desktops, anywhere
3. Follow the setup wizard (choose Essential, Standard, Maximum, or Custom)

### Option 2: Windows Installer
1. Download **[NOMAD-Setup.exe](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMAD-Setup.exe)**
2. Run installer — adds Start Menu shortcut and desktop icon
3. Launch from Start Menu

### Option 3: Linux
```bash
wget https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMADFieldDesk-Linux
chmod +x NOMADFieldDesk-Linux
./NOMADFieldDesk-Linux
```

### Option 4: macOS
```bash
curl -LO https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/NOMADFieldDesk-macOS
chmod +x NOMADFieldDesk-macOS
./NOMADFieldDesk-macOS
```

### Option 5: Run from source (any platform)
```bash
git clone https://github.com/SysAdminDoc/project-nomad-desktop.git
cd project-nomad-desktop
python nomad.py
```
Then install dependencies with `pip install -r requirements.txt` before launch.

### Option 6: Build your own binary
```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/NOMADFieldDesk (or NOMADFieldDesk.exe on Windows)
```

---

## Requirements

- **Windows**: Windows 10/11 + WebView2 Runtime (included with Windows 11)
- **Linux**: Python 3.10+, `python3-gi gir1.2-webkit2-4.1` (for pywebview GTK backend)
- **macOS**: Python 3.10+ (uses native WebKit via Cocoa)
- Python 3.10+ bundled in portable exe, needed only for running from source

---

## Architecture

| Component | Technology |
|-----------|-----------|
| Window | pywebview (WebView2 on Windows, WebKit on macOS, GTK on Linux) |
| Backend | Flask with 16 Blueprints — 600+ API routes |
| Database | SQLite (95 tables, WAL mode, auto-backups, 128 performance indexes, migration system) |
| AI | Ollama native + GPU auto-config (NVIDIA/AMD/Intel) + multimodal vision |
| Config | `Config` class with environment variable overrides and `.env` file support |
| Security | CSRF tokens, rate limiting (flask-limiter), SQL injection prevention, input validation |
| Situation Room | World Monitor parity: 86 cards, 435+ feeds (40+ categories), 30 OSINT channels, 32 data sources, 20 map layers + 3D globe, 440+ static points, correlation engine, AI briefing (Ollama), 72 API routes, 30 fetch workers |
| Alerts | Background engine (5-min cycle) + weather-triggered action rules + predictive trend analysis |
| Weather | Zambretti barometric algorithm (pure offline) + pressure graphing + automated action rules |
| Scheduler | Recurring tasks with auto-recurrence (daily/weekly/monthly) + watch rotation planner |
| Encryption | AES-256-GCM via Web Crypto API + optional encrypted backups (Fernet) |
| Maps | MapLibre GL JS + PMTiles (bundled locally) + 50+ sources + 3 styles + elevation profiles + perimeter zones |
| NukeMap | Leaflet 1.9.4 (bundled) — 18 JS modules |
| VIPTrack | Military/VIP aircraft tracker (embedded or hosted) — live ADS-B data |
| Notes | Wiki-links + backlinks + tags + templates + attachments |
| Media | Resume playback + playlists + yt-dlp + FFmpeg + libtorrent |
| Radio | DTMF WebAudio + phonetic trainer + antenna calculator + HF propagation + freq database |
| Federation | UDP discovery + HTTP sync + vector clocks + mutual aid + community readiness + skill matching + alert relay + group exercises |
| Medical | Vitals trending + wound photos + drug interactions + TCCC + triage + SBAR + dosage calculator + Medical Flipbook |
| Garden | Companion planting (20 pairs) + pest guide (10) + seed inventory + yield analysis + geo overlay |
| Hardware | pyserial bridge for USB sensors, time-series charting |
| Mesh | Meshtastic LoRa bridge, comms status board |
| Print | 9+ field documents (operations binder, wallet cards, SOI, medical flipbook, and more) with PDF export |
| Benchmarks | AI inference + storage I/O + network throughput + historical comparison |
| LAN | Chat channels + presence indicators + AES-GCM encryption + heartbeat discovery + dead drop messaging |
| Tray | pystray (background operation) |
| PWA | Service worker + manifest.json + push notifications + IndexedDB offline cache |
| Build | PyInstaller (single binary) + Inno Setup (Windows installer) |
| Customization | Full UI panel (theme, scale, mode, sidebar, sections, widget layout) + localStorage persistence |
| Accessibility | WCAG 2.1 AA — skip links, ARIA roles, focus management, RTL support, i18n |
| Voice | Web Speech API for hands-free inventory entry and AI chat |

---

## Data Location

Data stored in platform-appropriate location:
- **Windows**: `%APPDATA%\NOMADFieldDesk\` for new installs, with legacy `ProjectNOMAD` upgrades still supported
- **Linux**: `~/.local/share/NOMADFieldDesk/` (or `$XDG_DATA_HOME`)
- **macOS**: `~/Library/Application Support/NOMADFieldDesk/`

```
nomad.db                # SQLite (95 tables, WAL mode)
logs/                   # Application logs (rotating, 5MB max)
backups/                # Automatic DB backups (5 rotation, optional encryption)
db_migrations/          # SQL migration scripts
services/               # Service binaries + data
  ollama/models/        # AI models
  kiwix/library/        # ZIM content files
  flatnotes/            # FlatNotes venv + data
maps/                   # Downloaded map data
videos/                 # Offline video library
audio/                  # Audio files
books/                  # EPUB/PDF library
library/                # PDF/ePub documents
kb_uploads/             # Knowledge base documents
torrents/               # BitTorrent downloads
photos/                 # Inventory + wound photos
attachments/            # Note attachments
```

---

## Original vs Desktop Edition

This project is based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. The original is a Docker-based Linux application; this is a cross-platform desktop edition that extends it significantly.

### What's the Same
Both share the same core philosophy: an offline-first, self-contained knowledge and AI platform. Both include Ollama, Kiwix, Kolibri, ProtoMaps, CyberChef, and Qdrant. The visual style and "Command Center" branding are consistent.

### What the Desktop Edition Adds

Everything from the original plus: Situation Room with full World Monitor parity (86 cards, 435+ feeds, 32 data sources, 20 map layers + 3D globe, correlation engine, AI briefing, command palette, 30 OSINT channels, 440+ infrastructure points), 26 preparedness sub-tabs, proactive + predictive + weather-triggered alerts with automated action rules, Zambretti offline weather prediction with pressure graphing, AI SITREP generation + action execution + persistent memory + multimodal vision + conversation branching + model cards, VIPTrack military aircraft tracker, receipt scanner with AI Vision OCR, UPC barcode database, task scheduler, watch rotation planner, 21 decision guides, medical module (TCCC/triage/SBAR/vital signs trending/drug interactions/expiring meds/dosage calculator/Medical Flipbook), 4 training scenarios + multi-node group exercises, food production (companion planting, pest guide, seed inventory, yield analysis, geo overlay), power management with sensor charts, security cameras + perimeter zones, multi-node federation with vector clocks + mutual aid agreements + community readiness + skill matching + alert relay + group exercises, NukeMap v3.2.0, media library (210 channels, resume playback, playlists, 152 torrents), DTMF tone generator, NATO phonetic trainer, antenna calculator, HF propagation forecast, dead drop encrypted messaging, wiki-linked notes with templates + backlinks + attachments, serial hardware bridge, mesh radio, 9+ printable field documents with PDF export, CSV import wizard, 5 inventory templates (155 items), inventory barcode/QR + UPC database + lot tracking + check-in/out + photos + auto-shopping list, map measurement + print + style switcher + GPX + elevation profiles + geocode + perimeter zones, AI inference + storage + network benchmarks, LAN chat channels + AES-GCM encryption + presence, analytics dashboard, QR code generation, database migration system, CSRF + rate limiting + SQL injection prevention, undo system, full UI customization panel with widget configuration, bento grid dashboard, PWA with offline caching + push notifications, 5 themes (including E-Ink), voice input, form recovery, RTL support, i18n, 42 calculators, 56 reference cards, 17 emergency procedures, encrypted vault, and a 38-section user guide.

### Platform Differences
| | Original | Desktop Edition |
|---|----------|-----------------|
| Installation | `curl` + bash script, requires Docker | Download .exe / .AppImage / .dmg and run |
| Runtime | Docker containers on Linux | Native processes (Windows/Linux/macOS) |
| Database | MySQL | SQLite (zero config, 95 tables, migration system) |
| Frontend | React + Inertia.js | Single-file HTML/CSS/JS with asset bundling |
| Backend | AdonisJS (Node.js) | Flask + 16 Blueprints (Python, 600+ routes) |
| Build | Docker image | PyInstaller + Inno Setup |

---

## v1.0.0 Highlights

- **600+ API routes** across 95 SQLite tables with 128 performance indexes
- **16 Flask Blueprints** — modular architecture with dedicated `sql_safety.py`, `validation.py`, and `state.py`
- **Situation Room** — Full [World Monitor](https://worldmonitor.app) parity: 86 cards, 435+ feeds, 32 data sources, 20 map layers + 3D globe, correlation engine, AI briefing, command palette, 30 OSINT channels, 440+ infrastructure points
- **9 audit rounds** — security hardening, XSS prevention, DB connection safety (db_session context manager), cascade integrity, input validation, CSRF tokens, rate limiting
- **338 automated tests** across 34 test files
- **5 themes** — Desert, Night Ops, Cyber, Red Light, E-Ink
- **10 languages** with RTL support
- **PWA** with service worker, offline caching, and push notifications
- **CI/CD** — GitHub Actions builds portable binaries + Windows installer for all 3 platforms on tag push

---

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Desktop edition by [SysAdminDoc](https://github.com/SysAdminDoc).
