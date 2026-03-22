<div align="center">
<img src="https://raw.githubusercontent.com/Crosstalk-Solutions/project-nomad/refs/heads/main/admin/public/project_nomad_logo.png" width="200" height="200"/>

# Project N.O.M.A.D. for Windows v3.5.0
### The Most Complete Offline Survival Command Center Available

**Free. Open Source. No Internet Required After Setup.**

Native Windows port — no Docker, no WSL, no VMs. 6 managed services, 100+ downloadable datasets, situation-aware AI, tactical operations center, nuclear effects simulator, and a premium dark dashboard with night vision mode.

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/nomad-windows?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/nomad-windows/releases/latest)
[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

> Competitors charge $280+ for a USB stick with curated content (Prepper Disk, Prep Drive). N.O.M.A.D. for Windows does everything they do and 10x more — for free. 16,000+ lines of code, 50+ map sources, 10 interactive calculators, 20+ reference cards, 17 emergency protocols, and the most comprehensive offline prepper knowledge base ever built into a single application.

Download **[ProjectNOMAD.exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest)** — single file, double-click to run.

![Dashboard](screenshot.png)

## What Makes This Different

- **Situation-Aware AI** — The AI knows your actual inventory levels, burn rates, recent incidents, and threat status. It gives advice based on YOUR specific situation.
- **Complete Command Center** — Not just a content library. Full tactical operations with SITREP generator, threat assessment matrix, comms log, incident timeline, and emergency broadcast.
- **Comprehensive Knowledge Base** — START triage, companion planting, calorie density database, livestock care, WHO essential medicines, wild edible plants, survival knots, navigation, water purification, sanitation, COMSEC, and more — all embedded and available offline.
- **Night Vision Mode** — Red-on-black theme that preserves scotopic vision during darkness operations. Auto-switches at sunset.
- **LAN Chat** — Everyone on your local WiFi can message each other through the dashboard. No internet needed.
- **Nuclear Effects Simulator** — Bundled NukeMap with blast radius, thermal, fallout, and casualty modeling for nuclear preparedness planning.
- **Printable Emergency Cards** — Wallet-size cards with medical info, contacts, rally points, and quick reference protocols.

## 9 Main Tabs

| Tab | What It Does |
|-----|-------------|
| **Services** | 6 managed services + command dashboard with situation overview |
| **AI Chat** | Local AI with 18 presets, situation awareness, file drag-drop, conversation starters |
| **Library** | ZIM content library (100+ datasets) + PDF/document viewer |
| **Maps** | Offline maps with waypoints, zones, 50+ downloadable map sources, PMTiles region extract |
| **Notes** | Markdown notes with tags, pinning, live preview |
| **Benchmark** | CPU, memory, disk, AI inference scoring (NOMAD Score 0-100) |
| **Tools** | Meshtastic integration, barcode scanner, video library, guided drills |
| **Preparedness** | 13 sub-tabs of survival tools (see below) |
| **Settings** | System monitoring, model management, external Ollama, auth, host power control |

## 6 Managed Services

| Service | What It Does | Port |
|---------|-------------|------|
| **Ollama** | Local AI chat — Qwen3, Gemma 3, MedGemma, DeepSeek-R1 + GPU auto-detection | 11434 |
| **Kiwix** | Offline Wikipedia, medical references, survival guides, Army field manuals | 8888 |
| **CyberChef** | Encryption, encoding, hashing, 400+ data operations by GCHQ | 8889 |
| **Kolibri** | Khan Academy courses, textbooks, progress tracking | 8300 |
| **Qdrant** | Vector database for document upload and semantic search (RAG) | 6333 |
| **Stirling PDF** | Merge, split, compress, convert, OCR — 50+ PDF tools | 8443 |

## 13 Preparedness Sub-Tabs

| Sub-Tab | Features |
|---------|---------|
| **Checklists** | 11 templates: 72hr kit, bug-out bag, medical, comms, vehicle, home, earthquake, hurricane, pandemic, wildfire, civil unrest. JSON export/import. |
| **Incident Log** | Chronological event timeline with severity levels and category filtering |
| **Inventory** | Supply tracking with quantities, expiration alerts, burn rate dashboard, daily usage projections, Days Left column, shopping list generator, CSV import/export |
| **Contacts** | Emergency directory with callsigns, roles, skills, blood types, rally points, medical notes. Skills matrix with automatic gap analysis. CSV import/export. |
| **Calculators** | 10 interactive calculators: water needs, food storage planner (LDS/FEMA), generator fuel (4 fuel types), rainwater harvest, radio range estimator (12 radio types), medication dosage (weight-based), solar power sizing, bug-out bag weight tracker, resource allocation planner, plus travel time, battery life, bleach/disinfection, and more |
| **Radio Ref** | Complete frequency table: NOAA, FRS (22ch), GMRS, MURS, CB, HAM (2m/70cm/HF), shortwave. HAM net control script. |
| **Quick Ref** | 25+ reference cards: NATO alphabet, Morse code trainer, unit converter, START triage decision tree, companion planting matrix (15 crops), calorie density database (20 foods), livestock care (9 animals), WHO essential medicines (25+ meds), essential knots (8), navigation without GPS, water purification decision tree, grid-down sanitation, improvised tools (12), wild edible plants by season (18), vehicle emergency kit, EMP/Faraday guide, gray man OPSEC, water source finding, supply cache guide, group organization template, cloud weather prediction, COMSEC basics, seed saving (8 crops), soil pH reference, fermentation guide (6 products), medicinal plants (20), shelter defense assessment, game processing, barter values |
| **Protocols** | 17 emergency procedures: CPR, severe bleeding, water purification, shelter construction, fire starting, choking/Heimlich, hypothermia, wound closure, burn treatment, fracture/splinting, snake bite, anaphylaxis, dental emergency, psychological first aid (RAPID model), CERT guide, tornado, earthquake, flood, wildfire, hurricane. Printable emergency wallet card generator. |
| **Vault** | AES-256-GCM encrypted document storage. Emergency legal document templates (will, medical POA, asset inventory, child custody). Password generator. |
| **Weather** | Barometric pressure journal with automated trend analysis and weather forecasting |
| **Signals** | Radio check-in schedule planner + full communications log (HAM-style contact tracking) |
| **Operations** | SITREP generator, message cipher, infrastructure tracker (12 utilities), vehicle readiness board, threat assessment matrix, after-action review, emergency broadcast, 35-item home security hardening assessment with score |
| **Family Plan** | FEMA-style family emergency plan: meeting locations, 3 evacuation routes, household members (medical info, blood types), insurance/utility info |

## AI Features

- **18 system prompt presets**: General, Medical, Coding, Survival, Teacher, Analyst, Field Medic, HAM Radio, Homesteader, Water/Sanitation, Security/OPSEC, Foraging, Solar Power Expert, Land Navigation, Medicinal Herbalist, plus 3 scenario planners (Grid Down, Medical Emergency, Evacuation)
- **Situation-aware context**: Toggle "My Situation" to auto-inject your inventory, burn rates, incidents, contacts, and threat levels into the conversation
- **Drag-drop file context**: Attach PDFs, text files, CSVs to your chat messages
- **12 recommended models** including medical-specific (MedGemma, Meditron)
- **RAG pipeline**: Upload documents, auto-embed via nomic-embed-text, semantic search injected into chat
- **External Ollama host**: Point to a remote Ollama server on another machine
- **Conversation starters**: 8 pre-built questions for common prepper scenarios

## Offline Maps

- **50+ downloadable map sources**: Protomaps (PMTiles), Geofabrik (OSM extracts by continent/country/state), BBBike (200+ cities), Natural Earth, USGS National Map, OpenTopography, SRTM elevation, NOAA nautical charts, FAA sectional charts, Sentinel-2/Landsat satellite, HOT humanitarian exports, WorldClim climate data
- **Regional PMTiles extraction**: Auto-downloads `pmtiles` CLI, extracts regions by bounding box from the Protomaps daily planet build
- **Custom URL download**: Paste any PMTiles URL to download
- **Local file import**: Import .pmtiles, .pbf, .geojson, .mbtiles, .shp, and other map formats
- **MapLibre GL JS** viewer with Nominatim search, waypoints, zones, distance matrix, GPX export

## Tools Tab

- **Meshtastic Integration**: Connect LoRa mesh radio devices via Web Serial API for off-grid messaging
- **Barcode Scanner**: Camera-based barcode scanning via BarcodeDetector API, auto-add to inventory
- **Offline Video Library**: Upload, categorize (9 categories), and play instructional videos
- **Guided Emergency Drills**: 6 timed drill scenarios with step checklists, live timer, completion tracking, and persistent drill history
- **Nuclear Effects Simulator**: Bundled NukeMap v3.1.0 with blast radius, thermal radiation, fallout, and casualty modeling

## Content Library

14 categories, 3 tiers each (Essential / Standard / Comprehensive), 100+ downloadable datasets:

Wikipedia, Medicine & Health, Survival & Preparedness (Post-Disaster Guide, Water Treatment, Army Field Manuals), Repair & How-To (iFixit), Computing & Technology (Stack Overflow), Science & Engineering, Education (Khan Academy, CrashCourse), Books & Literature (Project Gutenberg), Ham Radio & Communications, TED Talks, Reference & Dictionaries, Homesteading & Agriculture, Appropriate Technology (Appropedia, Energypedia), Multi-Language (Spanish, French, German, Portuguese Wikipedia)

## 4 Themes

- **NOMAD** (Desert/Tactical) — Default theme
- **Night Ops** (Dark) — Dark tactical theme
- **Cyber** (Blue Dark) — Blue-accent dark theme
- **Red Light** (Night Vision) — Pure red-on-black for preserving night vision. Auto-switches at sunset.

## Quick Start

### Option 1: Download the exe
1. Download **[ProjectNOMAD.exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest)**
2. Double-click to run
3. Follow the setup wizard

### Option 2: Run from source
```bash
git clone https://github.com/SysAdminDoc/nomad-windows.git
cd nomad-windows
python nomad.py
```
Dependencies auto-install on first run.

### Option 3: Build your own exe
```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/ProjectNOMAD.exe
```

## Requirements

- Windows 10/11
- Python 3.10+ (bundled in exe, needed for source)
- WebView2 Runtime (included with Windows 11)

## Architecture

| Component | Technology |
|-----------|-----------|
| Window | pywebview + WebView2 |
| Backend | Flask (0.0.0.0 for LAN access) |
| Database | SQLite (19 tables, WAL mode, auto-backups) |
| AI | Ollama native + GPU auto-config (NVIDIA/AMD/Intel) |
| Encryption | AES-256-GCM via Web Crypto API |
| Maps | MapLibre GL JS + PMTiles + 50+ sources |
| NukeMap | Leaflet 1.9.4 (bundled locally) |
| Tray | pystray (background operation) |
| Build | PyInstaller (single exe) |

## Data Location

All data stored in `%APPDATA%\ProjectNOMAD\`:

```
nomad.db           # SQLite (19 tables)
logs/              # Application logs
backups/           # Automatic DB backups (5 rotation)
services/          # Service binaries + data
  ollama/models/   # AI models
  kiwix/library/   # ZIM content files
  pmtiles/         # PMTiles CLI tool
maps/              # Downloaded map data
videos/            # Offline video library
library/           # PDF/ePub documents
kb_uploads/        # Knowledge base documents
```

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Windows port by [SysAdminDoc](https://github.com/SysAdminDoc).
