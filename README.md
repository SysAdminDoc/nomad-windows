<div align="center">
<img src="project_nomad_logo.png" width="200" height="200"/>

# Project N.O.M.A.D. for Windows v1.0.0
### The Most Complete Offline Survival Command Center Available

**Free. Open Source. No Internet Required After Setup.**

Native Windows port — no Docker, no WSL, no VMs. 6 managed services, 100+ downloadable datasets, situation-aware AI with proactive alerts, tactical operations center, nuclear effects simulator, medical module, food production tracking, multi-node federation, power management, security cameras, and a premium dark dashboard with night vision mode.

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/nomad-windows?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/nomad-windows/releases/latest)
[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

> Competitors charge $280+ for a USB stick with curated content (Prepper Disk, Prep Drive). N.O.M.A.D. for Windows does everything they do and 10x more — for free. ~34,000 lines of code, 228 API endpoints, 32 database tables, 50+ map sources, 10 interactive calculators, 25+ reference cards, 17 emergency protocols, 10 interactive decision guides with 200+ nodes, 15 checklist templates, 4 training scenarios, NukeMap v3.2.0 nuclear simulator, medical module with drug interaction checking, food production tracking, multi-node sync, power management, security cameras, AI document intelligence, and printable emergency reference sheets — the most comprehensive offline prepper command center ever built into a single application.

**[Download Portable .exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest/download/ProjectNOMAD.exe)** — single file, no install needed, run from anywhere (USB, desktop, etc.)

**[Download Installer](https://github.com/SysAdminDoc/nomad-windows/releases/latest/download/ProjectNOMAD-Setup.exe)** — installs to Program Files with Start Menu shortcut and desktop icon

## What Makes This Different

- **Proactive AI Alerts** — A background engine monitors your inventory burn rates, expiring items, weather pressure drops, and incident clusters every 5 minutes. It surfaces actionable alerts automatically and generates AI situation summaries.
- **Situation-Aware AI** — The AI knows your actual inventory levels, burn rates, recent incidents, weather, power status, patient conditions, and garden data. It gives advice based on YOUR specific situation with 7 context sources.
- **Interactive Decision Guides** — 10 step-by-step branching guides with 200+ decision nodes that ask about YOUR water source, wound type, equipment, power situation, or environment and give the exact procedure. Works fully offline without AI.
- **Medical Module** — Patient profiles with vitals tracking, wound documentation, 26-pair drug interaction checker, and printable patient care cards. Field hospital capability in software.
- **Training Scenarios** — Multi-phase survival simulations with AI-generated complications based on your real inventory. Scored after-action reviews track improvement over time.
- **Food Production** — Garden plots, seed inventory with auto-calculated viability (25 species), harvest logging that feeds directly into supply tracking, livestock health records, USDA hardiness zone lookup.
- **Multi-Node Federation** — Sync data between N.O.M.A.D. installations on your LAN. UDP peer discovery, one-click push/pull, full sync history.
- **Complete Command Center** — Full tactical operations with SITREP generator, threat assessment matrix, comms log, incident timeline, daily journal, emergency broadcast, security cameras, power management, and more.
- **Nuclear Effects Simulator** — Bundled NukeMap v3.2.0 with 418 verified targets, 708 warheads, 7 WW3 scenarios, weapon encyclopedia, and HEMP burst mode.
- **Night Vision Mode** — Red-on-black theme that preserves scotopic vision during darkness operations. Auto-switches at sunset.
- **Printable Emergency Reports** — Inventory reports, contact directories, patient care cards, and a comprehensive emergency reference sheet aggregating all critical data.
- **Getting Started Wizard** — New user onboarding checklist guides you through initial setup step by step.

## 9 Main Tabs

| Tab | What It Does |
|-----|-------------|
| **Services** | 6 managed services + command dashboard with proactive alerts and situation overview |
| **AI Chat** | Local AI with 19 presets, situation awareness (7 data sources), file drag-drop, document intelligence |
| **Library** | ZIM content library (100+ datasets) with bulk download (Essential/Standard/Everything) + PDF viewer |
| **Maps** | Offline maps with 10 tools: waypoints, zones, property boundary, print, bookmark, bearing, measure, GPX export |
| **Notes** | Markdown notes with tags, pinning, live preview, per-note and bulk export |
| **Benchmark** | CPU, memory, disk, AI inference scoring (NOMAD Score 0-100) with trend deltas |
| **Tools** | NukeMap, Meshtastic, barcode scanner, video library, guided drills, immersive training scenarios |
| **Preparedness** | 19 sub-tabs of survival tools (see below) |
| **Settings** | System monitoring, model management, network federation, power management, security, host control |

## 6 Managed Services

| Service | What It Does | Port |
|---------|-------------|------|
| **Ollama** | Local AI chat — Qwen3, Gemma 3, MedGemma, DeepSeek-R1 + GPU auto-detection | 11434 |
| **Kiwix** | Offline Wikipedia, medical references, survival guides, Army field manuals | 8888 |
| **CyberChef** | Encryption, encoding, hashing, 400+ data operations by GCHQ | 8889 |
| **Kolibri** | Khan Academy courses, textbooks, progress tracking | 8300 |
| **Qdrant** | Vector database for document upload and semantic search (RAG) | 6333 |
| **Stirling PDF** | Merge, split, compress, convert, OCR — 50+ PDF tools | 8443 |

## 19 Preparedness Sub-Tabs

| Sub-Tab | Features |
|---------|---------|
| **Checklists** | 15 templates (72hr kit, bug-out bag, medical, comms, vehicle, winter storm, grid failure, CBRN shelter, infant kit, and more). JSON import/export, custom checklists. |
| **Incident Log** | Chronological event timeline with severity levels, category filtering, cluster detection. |
| **Inventory** | Supply tracking with quantities, expiration alerts, burn rate dashboard, daily usage projections, Days Left, shopping list generator, CSV import/export. Harvests auto-feed in from Garden tab. |
| **Contacts** | Emergency directory with callsigns, roles, skills, blood types, rally points, medical notes. Skills matrix with gap analysis. CSV import/export. Quick-add 7 standard emergency contacts (911, poison control, etc). |
| **Security** | IP camera feeds (MJPEG/snapshot/HLS), access logging (entry/exit/patrol), security dashboard with threat level, 24h access count, 48h incident count. Common camera URL examples (Reolink, Amcrest, Wyze, ONVIF). |
| **Power** | Device registry (solar panels, batteries, charge controllers, inverters, generators). Power log (voltage, SOC, solar/load watts). Autonomy projection dashboard with color-coded gauges (green >7d, orange >3d, red <3d). |
| **Garden** | Garden plots (dimensions, sun exposure, soil). Seed inventory with auto-calculated viability (25 species). Harvest log auto-creates inventory items. Livestock records (10 species) with health event logging. USDA hardiness zone lookup by latitude. |
| **Medical** | Patient profiles linked to contacts (weight, age, allergies, medications, conditions). Vital signs tracking (BP, pulse, resp, temp, SpO2, pain, GCS) with color-coded abnormals. Wound documentation (8 types, 4 severities). 26-pair drug interaction checker. Printable patient care cards. Import patients from contacts with one click. |
| **Calculators** | 10+ interactive calculators: water, food storage (LDS/FEMA), generator fuel, rainwater harvest, radio range (12 types), medication dosage (weight-based), solar sizing, BOB weight, resource planning, travel time, battery life, bleach dosing, and more. |
| **Guides** | 10 interactive decision trees with 200+ nodes: water purification, wound assessment, fire starting, shelter construction, radio setup, food preservation, START triage, power outage response, vehicle emergency, bug-out vs shelter decision. Step-by-step branching Q&A. "Ask AI" button at any step. Printable procedure cards. Works fully offline. |
| **Radio Ref** | Complete frequency table: NOAA, FRS (22ch), GMRS, MURS, CB, HAM (2m/70cm/HF), shortwave. |
| **Quick Ref** | 25+ reference cards: NATO alphabet, Morse code trainer, unit converter, triage, companion planting, calorie DB, livestock care, WHO medicines, knots, navigation, sanitation, wild edibles, EMP guide, OPSEC, and more. |
| **Protocols** | 17 emergency procedures with search and expand-all: CPR, bleeding, water purification, shelter, fire, choking, hypothermia, wound closure, burns, fractures, snake bite, anaphylaxis, dental, PFA, CERT, tornado/earthquake/flood/wildfire/hurricane. Printable wallet card. |
| **Vault** | AES-256-GCM encrypted document storage with password verification. Legal document templates. Password generator with show/hide toggle. |
| **Weather** | Barometric pressure journal with automated trend analysis and weather forecasting. |
| **Signals** | Radio check-in schedule planner + full communications log (HAM-style contact tracking). |
| **Operations** | SITREP generator, message cipher, infrastructure tracker (12 utilities), vehicle readiness board, threat assessment matrix, after-action review, emergency broadcast, 35-item home security assessment. |
| **Family Plan** | FEMA-style family emergency plan: meeting locations, 3 evacuation routes, household members (medical info, blood types), insurance/utility info. |
| **Journal** | Daily journal entries with mood tracking (5 moods), tag system, chronological timeline, and full export. |

## AI Features

- **Proactive alert engine** — background monitoring with AI-generated natural language situation summaries
- **19 system prompt presets**: General, Medical, Coding, Survival, Teacher, Analyst, Field Medic, HAM Radio, Homesteader, Water/Sanitation, Security/OPSEC, Foraging, Nuclear Preparedness, Solar Power Expert, Land Navigation, Medicinal Herbalist, plus 3 scenario planners
- **Situation-aware context**: Toggle "My Situation" to auto-inject your inventory, burn rates, incidents, contacts, threat levels, weather, power status, patient conditions, and garden data (7 context sources)
- **Document intelligence**: AI classifies uploaded documents (8 categories), generates summaries, extracts entities (people, dates, medications, addresses, vehicles, amounts, coordinates), cross-references against contacts
- **Drag-drop file context**: Attach PDFs, text files, CSVs to your chat messages
- **12 recommended models** including medical-specific (MedGemma, Meditron)
- **RAG pipeline**: Upload documents, auto-embed via nomic-embed-text, semantic search injected into chat
- **Download All models**: One-click bulk download with sequential queue and progress tracking
- **4 AI chat starters**: Quick-start conversations for common scenarios

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

## Network Federation

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
- **Offline Video Library**: Upload, categorize (9 categories), and play instructional videos
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
1. Download **[ProjectNOMAD.exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest/download/ProjectNOMAD.exe)**
2. Double-click to run — works from USB drives, desktops, anywhere
3. Follow the setup wizard and getting-started checklist

### Option 2: Installer
1. Download **[ProjectNOMAD-Setup.exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest/download/ProjectNOMAD-Setup.exe)**
2. Run the installer — adds Start Menu shortcut and desktop icon
3. Launch from Start Menu or desktop

### Option 3: Run from source
```bash
git clone https://github.com/SysAdminDoc/nomad-windows.git
cd nomad-windows
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
| Backend | Flask (0.0.0.0 for LAN access) — 228 API routes |
| Database | SQLite (32 tables, WAL mode, auto-backups, performance indexes) |
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
| Tray | pystray (background operation) |
| Build | PyInstaller (single exe) + Inno Setup (installer) |

## Data Location

All data stored in `%APPDATA%\ProjectNOMAD\`:

```
nomad.db           # SQLite (32 tables)
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

## Original vs Windows Edition

This project is based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. The original is a Docker-based Linux application; this is a native Windows port that extends it significantly.

### What's the Same
Both versions share the same core philosophy: an offline-first, self-contained knowledge and AI platform. Both include Ollama (AI chat), Kiwix (offline encyclopedia), Kolibri (education), ProtoMaps (offline maps), CyberChef (data tools), and Qdrant (vector search). The visual style and "Command Center" branding are consistent.

### What the Original Has That We Don't
| Feature | Original | Windows Edition |
|---------|----------|-----------------|
| Platform | Docker on Linux (Ubuntu/Debian) | Native Windows (no Docker) |
| Notes | FlatNotes (separate app) | Built-in Markdown notes |
| Community Benchmark | Online leaderboard at benchmark.projectnomad.us | Local-only benchmark |
| Multi-user Auth | Planned | Dashboard password |
| Automatic Updates | Docker image pull | Manual download from releases |

### What the Windows Edition Adds (not in the original)

| Feature | Description |
|---------|-------------|
| **19 Preparedness Sub-Tabs** | Inventory, contacts, checklists, medical, incidents, family plan, security, power, garden, weather, guides, calculators, procedures, radio ref, quick ref, signals, command post, journal, secure vault |
| **Proactive AI Alerts** | Background engine monitors burn rates, expiring items, pressure drops, incident clusters every 5 minutes |
| **Readiness Score** | Cross-module A-F grade (0-100) with 7 categories: water, food, medical, security, comms, power, planning |
| **10 Interactive Decision Guides** | 200+ node step-by-step trees for water, wounds, fire, shelter, radio, food, triage, power outage, vehicle emergency, bug-out decisions |
| **Medical Module** | Patient records, vitals tracking (BP/pulse/resp/temp/SpO2/pain/GCS), wound log, 26-pair drug interaction checker |
| **4 Training Scenarios** | Multi-phase simulations (Grid Down, Medical Crisis, Evacuation, Winter Storm) with AI complications and scored reviews |
| **Food Production** | Garden plots, seed viability tracking (25 species), harvest-to-inventory automation, livestock health records |
| **Power Management** | Solar/battery/generator device registry, power logging, autonomy projection dashboard |
| **Security Module** | IP camera viewer (MJPEG/snapshot/HLS), access logging, threat dashboard |
| **Multi-Node Sync** | LAN auto-discovery + USB offline transfer between N.O.M.A.D. installations |
| **NukeMap v3.2.0** | Nuclear effects simulator with 418 targets, 708 warheads, 7 WW3 scenarios |
| **AI Document Intelligence** | Auto-classify, summarize, extract entities, cross-reference contacts |
| **Encrypted Vault** | AES-256-GCM encrypted storage for passwords, coordinates, sensitive documents |
| **Daily Inventory Consume** | One-click daily supply tracking with burn rate projections |
| **Printable Reports** | Inventory, contacts, patient cards, emergency reference sheet, wallet cards |
| **38-Section User Guide** | Comprehensive built-in reference manual with contextual help icons throughout the app |
| **4 Themes** | NOMAD (desert), Night Ops (dark), Cyber (blue), Red Light (night vision) |
| **Situation-Aware AI** | 7 data sources injected into AI context (inventory, weather, alerts, power, patients, garden, contacts) |
| **15 Checklist Templates** | 72hr kit, bug-out bag, vehicle kit, winter storm, CBRN shelter, infant kit, and more |
| **17 Emergency Procedures** | CPR, bleeding, burns, fractures, choking, hypothermia, snake bite, and more |
| **25+ Quick Reference Cards** | NATO alphabet, Morse code, knots, triage, companion planting, wild edibles, and more |
| **Portable Executable** | Single .exe file runs from USB — no installation needed |

### Platform Differences
| | Original | Windows Edition |
|---|----------|-----------------|
| Installation | `curl` + bash script, requires Docker | Download .exe and double-click |
| Runtime | Docker containers on Linux | Native Windows processes |
| Services | Docker Compose orchestration | Python subprocess management |
| Database | MySQL | SQLite (zero config) |
| Frontend | React + Inertia.js + Tailwind | Single-file HTML/CSS/JS |
| Backend | AdonisJS (Node.js/TypeScript) | Flask (Python) |
| Maps | ProtoMaps integration | MapLibre GL JS + PMTiles (bundled) |
| System Tray | N/A (server) | pystray (minimize to tray) |
| Build | Docker image | PyInstaller + Inno Setup |

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Windows port by [SysAdminDoc](https://github.com/SysAdminDoc).
