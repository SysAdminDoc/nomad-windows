<div align="center">
<img src="project_nomad_logo.png" width="200" height="200"/>

# Project N.O.M.A.D. Desktop v3.2.0
### The Most Complete Offline Survival Command Center Available

**Free. Open Source. No Internet Required After Setup.**

Cross-platform desktop edition — no Docker, no WSL, no VMs. Runs on Windows, Linux, and macOS. 6 managed services, 100+ downloadable datasets, situation-aware AI with proactive alerts and voice input, 3 dashboard modes with 12 live widgets, tactical operations center, nuclear effects simulator, medical module with TCCC/triage, food production with yield analysis, federation v2 with resource marketplace, sensor integration, power management, security cameras, built-in BitTorrent client, 210 survival channels, curated content catalogs (141 books, 131 videos, 102 audio, 152 torrents), and a premium dark dashboard with sparkline charts and night vision mode.

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/project-nomad-desktop?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest)
[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

> Competitors charge $280+ for a USB stick with curated content (Prepper Disk, Prep Drive). N.O.M.A.D. Desktop does everything they do and 10x more — for free. 50+ map sources, 41 interactive calculators, 56 reference cards, 17 emergency procedures, 21 interactive decision guides, 15 checklist templates, 4 training scenarios, NukeMap v3.2.0 nuclear simulator, medical module with TCCC/triage and drug interaction checking, food production with yield analysis, federation v2 with resource marketplace, sensor integration, power management, security cameras, AI document intelligence, built-in BitTorrent client, 210 survival channels, curated content catalogs (141 books, 131 videos, 102 audio, 152 torrents), a 38-section built-in user guide, and printable emergency reference sheets — the most comprehensive offline prepper command center ever built into a single application.

**[Download Portable .exe](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/ProjectNOMAD.exe)** — single file, no install needed, run from anywhere (USB, desktop, etc.)

**[Download Installer](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/ProjectNOMAD-Setup.exe)** — installs to Program Files with Start Menu shortcut and desktop icon

## What Makes This Different

- **Proactive AI Alerts** — A background engine monitors your inventory burn rates, expiring items, weather pressure drops, and incident clusters every 5 minutes. It surfaces actionable alerts automatically and generates AI situation summaries.
- **Situation-Aware AI** — The AI knows your actual inventory levels, burn rates, recent incidents, contacts, threat levels, weather, power status, patient conditions, and garden data. It gives advice based on YOUR specific situation with 7 context sources.
- **Interactive Decision Guides** — 21 step-by-step branching guides with 300+ decision nodes covering water purification, wound assessment, fire starting, shelter, radio, food preservation, triage, power outage, vehicle emergency, bug-out decisions, antibiotic selection, hypothermia, chest trauma, envenomation, missing person search, wound infection, anaphylaxis, electrical hazard, and drowning. Works fully offline without AI.
- **Medical Module** — Patient profiles with vitals tracking, wound documentation, 26-pair drug interaction checker, and printable patient care cards. Field hospital capability in software.
- **Training Scenarios** — Multi-phase survival simulations with AI-generated complications based on your real inventory. Scored after-action reviews track improvement over time.
- **Food Production** — Garden plots, seed inventory with auto-calculated viability (25 species), harvest logging that feeds directly into supply tracking, livestock health records, USDA hardiness zone lookup.
- **Multi-Node Federation** — Sync data between N.O.M.A.D. installations on your LAN. UDP peer discovery, one-click push/pull, full sync history.
- **Complete Command Center** — Full tactical operations with SITREP generator, threat assessment matrix, comms log, incident timeline, daily journal, emergency broadcast, security cameras, power management, and more.
- **Nuclear Effects Simulator** — Bundled NukeMap v3.2.0 with 418 verified targets, 708 warheads, 7 WW3 scenarios, weapon encyclopedia, and HEMP burst mode.
- **Media Library** — 210 curated survival channels across 26 categories, video/audio/book library with downloads, built-in BitTorrent client, and curated content catalogs (141 reference books, 131 tutorial videos, 102 training audio, 152 torrent collections).
- **Night Vision Mode** — Red-on-black theme that preserves scotopic vision during darkness operations. Auto-switches at sunset.
- **Printable Emergency Reports** — Inventory reports, contact directories, patient care cards, and a comprehensive emergency reference sheet aggregating all critical data.
- **Getting Started Wizard** — New user onboarding checklist guides you through initial setup step by step.
- **38-Section User Guide** — Comprehensive built-in reference manual with contextual help icons (?) on every major feature. Covers setup, all tabs, all 25 sub-tabs, AI model selection, inventory best practices, calculators, medical/power/security guides, troubleshooting, FAQ, and glossary.
- **Readiness Score** — Cross-module A-F grade (0-100) with 7 clickable categories (water, food, medical, security, communications, power, planning). Click any category to jump directly to that section.
- **Status Strip** — Persistent bar showing running services, inventory count, contacts, active alerts, and current date/time at a glance.
- **58 Quick-Add Supplies** — One-click templates for common inventory items across 8 categories (water, food, medical, power, fuel, hygiene, tools, communications) with recommended starting quantities.

## 10 Main Tabs

| Tab | What It Does |
|-----|-------------|
| **Services** | 6 managed services + 3 dashboard modes with 12 live widgets, sparkline charts, and AI copilot |
| **AI Chat** | Local AI with 19 presets, situation awareness (7 data sources), file drag-drop, document intelligence |
| **Library** | ZIM content library (100+ datasets) with bulk download (Essential/Standard/Everything) + PDF viewer |
| **Maps** | Offline maps with 10 tools: waypoints, zones, property boundary, print, bookmark, bearing, measure, GPX export |
| **Notes** | Markdown notes with tags, pinning, live preview, per-note and bulk export |
| **Media** | 210 survival channels, video/audio/book library, curated catalogs, downloads, built-in BitTorrent client |
| **Benchmark** | CPU, memory, disk, AI inference scoring (NOMAD Score 0-100) with trend deltas |
| **Tools** | NukeMap, Meshtastic, barcode scanner, guided drills, immersive training scenarios |
| **Preparedness** | 25 sub-tabs of survival tools (see below) |
| **Settings** | System monitoring, AI model management, multi-system sync, preferences, backup/restore, data summary |

## 6 Managed Services

| Service | What It Does | Port |
|---------|-------------|------|
| **Ollama** | Local AI chat — Qwen3, Gemma 3, MedGemma, DeepSeek-R1 + GPU auto-detection | 11434 |
| **Kiwix** | Offline Wikipedia, medical references, survival guides, Army field manuals | 8888 |
| **CyberChef** | Encryption, encoding, hashing, 400+ data operations by GCHQ | 8889 |
| **Kolibri** | Khan Academy courses, textbooks, progress tracking | 8300 |
| **Qdrant** | Vector database for document upload and semantic search (RAG) | 6333 |
| **Stirling PDF** | Merge, split, compress, convert, OCR — 50+ PDF tools | 8443 |

## Media Tab

| Sub-Tab | Features |
|---------|---------|
| **Browse Channels** | 210 curated survival channels across 26 categories. Auto-hides dead channels. Subscriptions, video browsing, search with pagination. |
| **My Videos** | Upload or download instructional videos. Thumbnail cards, watch + download player, 9 categories. Thumbnails + subtitles auto-downloaded. |
| **My Audio** | Audio catalog with favorites, batch operations, sorting. MP3 extraction via FFmpeg. |
| **My Books** | EPUB reader (epub.js) + PDF viewer (WebView2 built-in). Book catalog from Internet Archive. |
| **Torrent Library** | Built-in BitTorrent client (libtorrent) with live download progress UI. 152 curated torrent collections across 12 categories (survival, maps, weather, radio, textbooks, medical, farming, videos, software, encyclopedias, repair, energy). |

## 25 Preparedness Sub-Tabs (ordered by emergency priority)

| Sub-Tab | Features |
|---------|---------|
| **Inventory** | Supply tracking with quantities, expiration alerts, daily usage projections, Days Left, shopping list generator, quick-add 58 common items, one-click Daily Consume, +/- quantity buttons, barcode + cost fields, total value footer, CSV import/export. Harvests auto-feed in from Garden. |
| **Contacts** | Emergency directory with callsigns, roles, skills, blood types, rally points, medical notes. Skills matrix with gap analysis. CSV import/export. Quick-add 7 standard emergency contacts. |
| **Checklists** | 15 templates (72hr kit, bug-out bag, vehicle kit, winter storm, CBRN shelter, infant kit, and more). JSON import/export, custom checklists. |
| **Medical** | Patient profiles linked to contacts. Vital signs tracking (BP, pulse, resp, temp, SpO2, pain, GCS) with color-coded abnormals. Wound documentation (8 types, 4 severities). 26-pair drug interaction checker. Medical supply status panel (expired/expiring/low-stock grouping). Printable patient care cards. |
| **Incidents** | Chronological event timeline with severity levels, category filtering, cluster detection. |
| **Family Plan** | FEMA-style emergency plan: meeting locations, 3 evacuation routes, household members (medical info, blood types), insurance/utility info. Auto-saves as you type. |
| **Security** | IP camera feeds (MJPEG/snapshot/HLS), access logging (entry/exit/patrol), security dashboard with threat level. Camera URL examples for Reolink, Amcrest, Wyze, ONVIF. |
| **Power** | Device registry (solar/battery/controller/inverter/generator). Power log (voltage, SOC, watts). Autonomy projection dashboard with color-coded gauges. |
| **Garden** | Garden plots, seed inventory with auto-viability (25 species), harvest log auto-creates inventory items, livestock records (10 species), USDA hardiness zone lookup. |
| **Weather** | Barometric pressure journal with automated trend analysis and storm prediction. |
| **Guides** | 21 interactive decision trees with 300+ nodes. Step-by-step branching Q&A. "Ask AI" at any step. Printable procedure cards. Works fully offline. |
| **Calculators** | 41 calculators: water needs, food storage, generator runtime, rainwater, radio range, medication dosage, solar sizing, BOB weight, resource planning, travel time, battery life, bleach dosing, ballistics, compost, pasture rotation, natural building, fallout, canning, burn area, IV drip, KI dosage, dead reckoning, shelter protection factor, crop calories, NVIS, weight-based dosing, radiation dose accumulator, dehydration assessment, vital signs assessment, hypothermia assessment, oral rehydration therapy, antibiotic inventory planner, and more. |
| **Procedures** | 17 emergency procedures: CPR, bleeding, water purification, shelter, fire, choking, hypothermia, wound closure, burns, fractures, snake bite, anaphylaxis, and more. Printable wallet card. |
| **Radio** | Complete frequency table: NOAA, FRS (22ch), GMRS, MURS, CB, HAM (2m/70cm/HF), shortwave. CHIRP export. |
| **Quick Ref** | 37+ reference cards: NATO phonetic alphabet + Q codes + APCO 10-codes, Morse code trainer, unit converter, triage, companion planting, wild edibles, EMP guide, OPSEC, game processing, ground-to-air signals, improvised shelter, vital signs by age, drug interactions & contraindications, TCCC/MARCH protocol, blood type compatibility, and more. |
| **Signals** | Ground-to-air emergency signals, sound signal patterns, smoke signal guide. |
| **Command Post** | Situation Report (SITREP) generator, message cipher, infrastructure tracker, vehicle readiness, threat assessment matrix, after-action review, emergency broadcast, home security assessment, ICS 309/214 forms. |
| **Journal** | Daily journal entries with mood tracking (5 moods), tag system, chronological timeline, and full export. |
| **Secure Vault** | AES-256-GCM encrypted storage for passwords, coordinates, sensitive documents. Password generator. |
| **Skills** | 60 survival skills across 10 categories with proficiency tracking and training recommendations. |
| **Ammo** | Ammunition inventory with caliber-grouped summary cards. |
| **Community** | Community resource registry with trust levels and skills/equipment tracking. |
| **Radiation** | Nuclear dose rate log with cumulative rem tracking and exposure alerts. |
| **Fuel** | Fuel storage tracking with type-grouped totals and expiry monitoring. |
| **Equipment** | Equipment maintenance log with service scheduling and status tracking. |

## AI Features

- **Proactive alert engine** — background monitoring with AI-generated natural language situation summaries
- **19 system prompt presets**: General, Medical, Coding, Survival, Teacher, Analyst, Field Medic, HAM Radio, Homesteader, Water/Sanitation, Security/OPSEC, Foraging, Nuclear Preparedness, Solar Power Expert, Land Navigation, Medicinal Herbalist, plus 3 scenario planners
- **Situation-aware context**: Toggle "Include My Prep Data" to auto-inject your inventory, burn rates, incidents, contacts, threat levels, weather, power status, patient conditions, and garden data
- **Document intelligence**: AI classifies uploaded documents (8 categories), generates summaries, extracts entities (people, dates, medications, addresses, vehicles, amounts, coordinates), cross-references against contacts
- **Drag-drop file context**: Attach PDFs, text files, CSVs to your chat messages
- **12 recommended models** including medical-specific (MedGemma, Meditron)
- **RAG pipeline**: Upload documents, auto-embed via nomic-embed-text, semantic search injected into chat
- **Download All models**: One-click bulk download with sequential queue and progress tracking
- **4 AI chat starters**: Quick-start conversations for common scenarios
- **Pre-warmed model**: Ollama model loaded on startup so first chat responds immediately

## Immersive Training Scenarios

4 multi-phase survival simulations with AI-generated complications:

| Scenario | Phases | Description |
|----------|--------|-------------|
| **Grid Down — 7 Days** | 7 | Power failure, water loss, food decisions, security threats, medical issues, comms, recovery |
| **Medical Crisis** | 5 | Trauma assessment, bleeding control, pain management, monitoring, complication handling |
| **Evacuation Under Threat** | 5 | Warning response, packing priorities, route decisions, roadblocks, arrival |
| **Winter Storm Survival** | 5 | Heating crisis, fuel rationing, pipe burst, neighbor aid, rescue |

- AI-generated complications between phases use your REAL inventory and situation data
- Every decision timestamped and logged
- AI-scored After-Action Review (0-100) with improvement recommendations
- Score history tracks improvement over time

## Connect Multiple Systems

Sync data between multiple N.O.M.A.D. installations:

- **UDP peer discovery** on LAN — automatically finds other N.O.M.A.D. instances
- **One-click sync** — push inventory, contacts, checklists, notes, incidents, waypoints to any peer
- **Manual IP** entry for direct connections across subnets
- **Sync history** — full audit trail of every push/receive with timestamps and item counts
- **Node identity** — auto-generated UUID + customizable name (e.g., "Base Camp", "Bug-Out Site")

## Offline Maps

- **50+ downloadable map sources**: Protomaps (PMTiles), Geofabrik, BBBike, Natural Earth, USGS, SRTM, NOAA, FAA, Sentinel-2/Landsat, and more
- **10 map tools**: Drop Pin, Measure, Save Waypoint, Draw Zone, Property Boundary (area/perimeter calc), Clear Pins, Print Layout, Bookmark, Bearing & Distance, Export GPX
- **Regional PMTiles extraction**: Auto-downloads `pmtiles` CLI, extracts 22 regions worldwide
- **Property boundary tool**: Draw polygon, calculates area (sq ft/acres) and perimeter (ft/miles)
- **Coordinate navigation**: Enter lat,lng directly for offline map navigation
- **Offline basemap**: Works without internet — inline dark style with async CDN upgrade

## Tools Tab

- **NukeMap v3.2.0**: 418 verified targets, 708 warheads, 7 WW3 scenarios, weapon encyclopedia, HEMP burst mode, nuclear winter modeling
- **Immersive Training**: 4 multi-phase scenarios with AI complications and scored reviews
- **Meshtastic Integration**: Connect LoRa mesh radio devices via Web Serial API
- **Barcode Scanner**: Camera-based barcode scanning, auto-add to inventory
- **Guided Emergency Drills**: 6 timed drill scenarios with step checklists and persistent history

## Content Library

14 categories, 3 tiers each (Essential / Standard / Comprehensive), 100+ downloadable datasets. Bulk download buttons: **Download All Essentials**, **Download Standard**, **Download Everything**. Each item shows live download state (available/downloading/downloaded).

Wikipedia, Medicine & Health, Survival & Preparedness, Repair & How-To (iFixit), Computing & Technology (Stack Overflow), Science & Engineering, Education (Khan Academy), Books & Literature (Project Gutenberg), Ham Radio & Communications, TED Talks, Reference & Dictionaries, Homesteading & Agriculture, Appropriate Technology, Multi-Language Wikipedia

## 4 Themes

- **NOMAD** (Desert/Tactical) — Default theme
- **Night Ops** (Dark) — Dark tactical theme
- **Cyber** (Blue Dark) — Blue-accent dark theme
- **Red Light** (Night Vision) — Pure red-on-black for preserving night vision. Auto-switches at sunset.

OS dark mode auto-detection applies matching theme on first launch.

## Printable Reports

- **Inventory Report** — Full supply list with quantities, locations, and expiration dates
- **Contact Directory** — Complete personnel directory with all details
- **Patient Care Cards** — Individual patient records with vitals, medications, and conditions
- **Emergency Reference Sheet** — Comprehensive one-page sheet aggregating critical data from all modules (contacts, inventory, medical, power, weather)

## Quick Start

### Option 1: Portable (no install)
1. Download **[ProjectNOMAD.exe](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/ProjectNOMAD.exe)**
2. Double-click to run — works from USB drives, desktops, anywhere
3. Follow the setup wizard and getting-started checklist

### Option 2: Installer
1. Download **[ProjectNOMAD-Setup.exe](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest/download/ProjectNOMAD-Setup.exe)**
2. Run the installer — adds Start Menu shortcut and desktop icon
3. Launch from Start Menu or desktop

### Option 3: Run from source
```bash
git clone https://github.com/SysAdminDoc/project-nomad-desktop.git
cd project-nomad-desktop
python nomad.py
```
Dependencies auto-install on first run.

### Option 4: Build your own exe
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
| Database | SQLite (57 tables, WAL mode, auto-backups, 65 performance indexes) |
| AI | Ollama native + GPU auto-config (NVIDIA/AMD/Intel) |
| Alerts | Background engine (5-min cycle) + browser notifications |
| Encryption | AES-256-GCM via Web Crypto API |
| Maps | MapLibre GL JS + PMTiles (bundled locally) + 50+ sources |
| NukeMap | Leaflet 1.9.4 (bundled locally) — 18 JS modules |
| Federation | UDP discovery (port 18080) + HTTP sync on LAN |
| Medical | Patient tracking, vitals, wounds, drug interactions |
| Power | Device registry, logging, autonomy projections |
| Security | Camera feeds, access logging, threat dashboard |
| Documents | AI classification, summarization, entity extraction |
| Media | yt-dlp + FFmpeg + libtorrent (auto-installed) |
| Tray | pystray (background operation) |
| Build | PyInstaller (single exe) + Inno Setup (installer) |

## Data Location

All data stored in `%APPDATA%\ProjectNOMAD\`:

```
nomad.db           # SQLite (57 tables, WAL mode)
logs/              # Application logs
backups/           # Automatic DB backups (5 rotation)
services/          # Service binaries + data
  ollama/models/   # AI models
  kiwix/library/   # ZIM content files
  pmtiles/         # PMTiles CLI tool
maps/              # Downloaded map data
videos/            # Offline video library
audio/             # Audio files
books/             # EPUB/PDF library
library/           # PDF/ePub documents
kb_uploads/        # Knowledge base documents
```

## Original vs Windows Edition

This project is based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. The original is a Docker-based Linux application; this is a cross-platform desktop edition that extends it significantly.

### What's the Same
Both versions share the same core philosophy: an offline-first, self-contained knowledge and AI platform. Both include Ollama (AI chat), Kiwix (offline encyclopedia), Kolibri (education), ProtoMaps (offline maps), CyberChef (data tools), and Qdrant (vector search). The visual style and "Command Center" branding are consistent.

### What the Original Has That We Don't
| Feature | Original | Windows Edition |
|---------|----------|-----------------|
| Platform | Docker on Linux (Ubuntu/Debian) | Native Desktop (no Docker) |
| Notes | FlatNotes (separate app) | Built-in Markdown notes |
| Community Benchmark | Online leaderboard at benchmark.projectnomad.us | Local-only benchmark |
| Multi-user Auth | Planned | Dashboard password |
| Automatic Updates | Docker image pull | Manual download from releases |

### What the Windows Edition Adds (not in the original)

| Feature | Description |
|---------|-------------|
| **25 Preparedness Sub-Tabs** | Inventory, contacts, checklists, medical, incidents, family plan, security, power, garden, weather, guides, calculators, procedures, radio ref, quick ref, signals, command post, journal, secure vault, skills, ammo, community, radiation, fuel, equipment |
| **Proactive AI Alerts** | Background engine monitors burn rates, expiring items, pressure drops, incident clusters every 5 minutes |
| **Readiness Score** | Cross-module A-F grade (0-100) with 7 categories: water, food, medical, security, comms, power, planning |
| **21 Interactive Decision Guides** | 300+ node step-by-step trees for water, wounds, fire, shelter, radio, food, triage, power outage, vehicle emergency, bug-out decisions, antibiotic selection, water source assessment, food safety assessment, hypothermia, chest trauma, envenomation, missing person, wound infection, anaphylaxis, electrical hazard, drowning |
| **Medical Module** | Patient records, vitals tracking (BP/pulse/resp/temp/SpO2/pain/GCS), wound log, 26-pair drug interaction checker |
| **4 Training Scenarios** | Multi-phase simulations (Grid Down, Medical Crisis, Evacuation, Winter Storm) with AI complications and scored reviews |
| **Food Production** | Garden plots, seed viability tracking (25 species), harvest-to-inventory automation, livestock health records |
| **Power Management** | Solar/battery/generator device registry, power logging, autonomy projection dashboard |
| **Security Module** | IP camera viewer (MJPEG/snapshot/HLS), access logging, threat dashboard |
| **Multi-Node Sync** | LAN auto-discovery + USB offline transfer between N.O.M.A.D. installations |
| **NukeMap v3.2.0** | Nuclear effects simulator with 418 targets, 708 warheads, 7 WW3 scenarios |
| **Media Library** | 210 survival channels across 26 categories, video/audio/book library, curated catalogs (141 books, 131 videos, 102 audio), downloads via yt-dlp |
| **BitTorrent Client** | Built-in libtorrent client with 152 curated torrent collections across 12 categories |
| **AI Document Intelligence** | Auto-classify, summarize, extract entities, cross-reference contacts |
| **Encrypted Vault** | AES-256-GCM encrypted storage for passwords, coordinates, sensitive documents |
| **41 Calculators** | Water needs, food, solar, ballistics, fallout, canning, IV drip, KI dosage, dead reckoning, shelter PF, crop calories, NVIS, radiation dose, dehydration, vital signs, hypothermia, ORT, antibiotic planner, and more |
| **Daily Inventory Consume** | One-click daily supply tracking with burn rate projections |
| **Printable Reports** | Inventory, contacts, patient cards, emergency reference sheet, wallet cards |
| **38-Section User Guide** | Comprehensive built-in reference manual with contextual help icons throughout the app |
| **4 Themes** | NOMAD (desert), Night Ops (dark), Cyber (blue), Red Light (night vision) |
| **Situation-Aware AI** | 7 data sources injected into AI context (inventory, weather, alerts, power, patients, garden, contacts) |
| **15 Checklist Templates** | 72hr kit, bug-out bag, vehicle kit, winter storm, CBRN shelter, infant kit, and more |
| **17 Emergency Procedures** | CPR, bleeding, burns, fractures, choking, hypothermia, snake bite, and more |
| **56 Quick Reference Cards** | NATO alphabet + Q codes + APCO 10-codes, Morse code, knots, triage, companion planting, wild edibles, game processing, vital signs by age, TCCC/MARCH, blood type compatibility, drug interactions, and more |
| **Skills Tracking** | 60 survival skills across 10 categories with proficiency levels |
| **Ammo Inventory** | Caliber-grouped ammunition tracking with summary cards |
| **Radiation Monitoring** | Nuclear dose rate logging with cumulative rem tracking |
| **Fuel Management** | Fuel storage tracking with type-grouped totals and expiry alerts |
| **Equipment Maintenance** | Service scheduling and status tracking for all gear |
| **Community Resources** | Resource registry with trust levels and capability tracking |
| **Portable Executable** | Single .exe file runs from USB — no installation needed |

### Platform Differences
| | Original | Windows Edition |
|---|----------|-----------------|
| Installation | `curl` + bash script, requires Docker | Download .exe and double-click |
| Runtime | Docker containers on Linux | Native processes (Windows/Linux/macOS) |
| Services | Docker Compose orchestration | Python subprocess management |
| Database | MySQL | SQLite (zero config) |
| Frontend | React + Inertia.js + Tailwind | Single-file HTML/CSS/JS |
| Backend | AdonisJS (Node.js/TypeScript) | Flask (Python) |
| Maps | ProtoMaps integration | MapLibre GL JS + PMTiles (bundled) |
| System Tray | N/A (server) | pystray (minimize to tray) |
| Build | Docker image | PyInstaller + Inno Setup |

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Desktop edition by [SysAdminDoc](https://github.com/SysAdminDoc).
