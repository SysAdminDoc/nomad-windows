<div align="center">
<img src="logo.png" width="140" height="140"/>

# NOMAD Field Desk v7.57.0

### Your Personal Intelligence & Preparedness Command Center

**One app. Everything you need. Nothing leaves your machine.**

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/project-nomad-desktop?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

<details>
<summary><b>Table of Contents</b></summary>

- [Why NOMAD?](#why-nomad)
- [Capabilities Overview](#capabilities-overview)
- [Situation Room](#-situation-room)
- [AI Assistant](#-ai-assistant)
- [Inventory & Supply Chain](#-inventory--supply-chain)
- [Medical](#-medical)
- [Maps & Navigation](#-maps--navigation)
- [Communications](#-communications)
- [Preparedness & Planning](#-preparedness--planning)
- [Agriculture & Food Production](#-agriculture--food-production)
- [Security & OPSEC](#-security--opsec)
- [Group Operations](#-group-operations)
- [Training & Knowledge](#-training--knowledge)
- [Daily Living](#-daily-living)
- [Hunting, Foraging & Wild Food](#-hunting-foraging--wild-food)
- [Hardware & Sensors](#-hardware--sensors)
- [Specialized Modules](#-specialized-modules)
- [NukeMap](#-nukemap)
- [VIPTrack](#-viptrack)
- [Print & Export](#-print--export)
- [Interoperability](#-interoperability)
- [Integrated Services](#integrated-services)
- [Data Sources](#data-sources)
- [Themes & Dashboard Modes](#themes--dashboard-modes)
- [Getting Started](#getting-started)
- [Requirements](#requirements)
- [Building from Source](#building-from-source)
- [Architecture](#architecture)
- [Credits](#credits)

</details>

---

## Security Notice

> NOMAD is designed for **localhost-only** use by default. If you expose it on a LAN or reverse proxy, you **must** place it behind an authenticating reverse proxy (Caddy, nginx + Authelia, Traefik + forward-auth) that enforces TLS and validates Host headers. Set `NOMAD_ALLOWED_HOSTS=your-hostname.local` to reject DNS rebinding requests. Enable `NOMAD_AUTH_REQUIRED=1` for token-based access control on LAN deployments. Never expose NOMAD directly to the internet without authentication.

---

## Why NOMAD?

Most people piece together their preparedness across a dozen apps, bookmarks, and spreadsheets. When you actually need it, nothing talks to each other and half of it requires internet you might not have.

NOMAD puts everything in one place — live global intelligence, private AI, offline maps, supply tracking, medical references, communications tools, and more — in a single portable app that runs on your desktop. Your data never touches a cloud server. When the internet is available, you get live feeds. When it's not, everything you've cached still works.

**Download it. Run it. That's it.** No accounts, no subscriptions, no setup wizards that take an hour.

---

## Capabilities Overview

| | |
|:---|:---|
| **Tabs** | Situation Room, Home, Readiness, Preparedness, Maps, Tools, NukeMap, VIPTrack, Water, Financial, Vehicles, Loadout, Movement, Tac Comms, Timeline, Threats, Land, Med+, Training, Group Ops, OPSEC, Agriculture, Disasters, Daily Living, Import/Export, Wild Food, Hardware, Library, Notes, Media, AI Chat, Diagnostics, Data Packs, Settings |
| **Backend** | 1,644 API routes across 59 blueprints |
| **Database** | 264 tables, 611 indexes (SQLite, WAL mode) |
| **Test Suite** | 888 automated tests |
| **Services** | Ollama (AI), Kiwix (Wikipedia), CyberChef, Kolibri, Qdrant, Stirling PDF, FlatNotes, BitTorrent |
| **Intelligence** | 36+ data sources, 100+ RSS feeds, 45 map layers, 108+ dashboard cards |
| **Data Packs** | 53 offline datasets across 3 tiers (auto-bundled through optional deep data) |
| **Platform** | Windows, Linux, macOS — single portable executable per platform |
| **Themes** | Desert, Night Ops, Cyber, Red Light, E-Ink |
| **Privacy** | All data stored locally. No accounts. No telemetry. No cloud. |

---

## Module Reference

Each section below maps to a dedicated tab (or set of tabs) in the application. Every feature works offline.

---

### 🌐 Situation Room

A global intelligence dashboard that aggregates 36+ live data sources into a unified command view. All fetched data is cached locally so you always have a recent snapshot, even without internet.

<table>
<tr><td width="50%">

**Intelligence Feeds**
- USGS earthquakes (M2.5+, real-time GeoJSON)
- NWS severe weather alerts
- GDACS global crisis events
- NASA FIRMS satellite fire detection
- Smithsonian volcanic eruption database
- WHO disease outbreak notifications
- NOAA space weather (Kp index, solar flares, CME)
- Polymarket prediction markets
- 100+ curated RSS news feeds across 20 categories

</td><td width="50%">

**Financial & Market Tracking**
- CoinGecko crypto prices (BTC, ETH, SOL)
- Yahoo Finance stock indices (S&P 500, Nasdaq, Dow)
- Gold and silver spot prices (metals.dev)
- EIA Brent oil commodity pricing
- Fear & Greed Index (market sentiment)

**Live Video**
- 12 rotating YouTube news channels (Al Jazeera, France 24, DW, Sky News, Reuters, NBC, ABC)

</td></tr>
</table>

**Dashboard Features:** Configurable desk presets (Executive, Crisis, Markets, Cyber, Regional) | Breaking news banner | Color-coded composite threat level (1–5) | Ticker strip with real-time count badges | AM Brief / Crisis Handoff / Market Note snapshot templates | Proximity-based alerts for your location

---

### 🤖 AI Assistant

A local AI that runs entirely on your hardware. It knows your actual inventory levels, contacts, weather, medical data, and incidents — so it gives answers relevant to *your* situation, not generic advice.

| Feature | Detail |
|:---|:---|
| **Engine** | Ollama (local LLM inference), GPU-accelerated (CUDA/Metal/ROCm) |
| **Default Model** | llama3.2:3b — 41+ recommended models available |
| **RAG** | Retrieval-augmented generation over all NOMAD data via Qdrant vector DB |
| **Embeddings** | nomic-embed-text:v1.5 (768-dim vectors) |
| **Document Pipeline** | Upload PDFs, images, text — auto-OCR, chunk, embed, index |
| **Knowledge Base** | Named workspaces ("Medical KB", "Water KB"), source citations with page numbers |
| **Conversations** | Branching, forking, context windows, streaming responses |
| **Capabilities** | SITREP generation, scenario analysis, inventory gap assessment, meal planning from stock |

---

### 📦 Inventory & Supply Chain

Track everything you own with barcode scanning, receipt OCR, burn rate projections, and expiration alerts. The system tells you what you're burning through and what to restock before you run out.

<table>
<tr><td width="50%">

**Core Inventory**
- Multi-category tracking (food, supplies, medical, fuel, ammo)
- Barcode/QR scanning with UPC database (76 pre-seeded items)
- Receipt OCR for quick data entry
- Photo attachments per item
- Check-in/check-out tracking ("who has the generator?")
- Lot/batch tracking for medical supplies and ammo
- Location tracking (cache, building, vehicle, container)
- Expiration alerts with timeline aggregation

</td><td width="50%">

**Intelligence Layer**
- USDA FoodData nutritional linking (7,793 foods, 150+ nutrients)
- Person-days of food calculator
- Micronutrient gap analysis with deficiency timeline
- Per-person consumption profiles (14 activity levels)
- Burn rate modeling from actual consumption data
- Auto-reorder point calculation
- Substitute item mapping
- Physical audit mode with discrepancy tracking

</td></tr>
</table>

**Additional Modules:** Shopping list generation | Container/bin management with nesting | Kit builder wizard with 5 pre-built templates (72-hour, bug-out, vehicle, medical, 30-day) | Recipes linked to inventory with "meals remaining" and expiration-priority cooking | Water storage, filter life, source tracking, quality testing, daily budget calculator | Financial tracker (cash reserves, precious metals, barter goods, insurance documents)

---

### 🏥 Medical

Patient tracking with vital signs trending, wound documentation, drug interaction checking, TCCC protocols, triage boards, and a printable pocket-sized medical flipbook. No cell signal required.

<table>
<tr><td width="50%">

**Clinical**
- Patient records linked to contacts
- Vital signs trending (BP, HR, temp, SpO2, GCS)
- Wound documentation with photo comparison
- Medication administration log
- 26-pair drug interaction checker
- TCCC/MARCH 5-step flowchart
- START triage system
- SBAR handoff reports
- Burns BSA calculator, IV fluid calculator

</td><td width="50%">

**Extended (Phase 2)**
- Pregnancy & childbirth tracking (prenatal, EDD, APGAR)
- Dental emergency records and protocols
- Veterinary medicine with animal dosage calculator
- Chronic condition management (diabetes, hypertension, asthma)
- Medication weaning protocols
- Herbal/alternative medicine reference database
- Vaccination schedule tracker with renewal
- Mental health check-in log
- 15-category offline medical reference with full-text search

</td></tr>
</table>

---

### 🗺️ Maps & Navigation

Download regional map tiles once and they're yours forever. Waypoints, routes, elevation profiles, perimeter zones, GPX import/export — all powered by MapLibre with 50+ tile sources.

| Feature | Detail |
|:---|:---|
| **Tile Support** | PMTiles, MBTiles — download once, use forever |
| **Styles** | Dark tactical, terrain/topo, satellite — cycle with one click |
| **Waypoints** | Categories, custom icons, elevation, notes |
| **Routes** | Multi-waypoint with GPX data, turn-by-turn distances |
| **Measurement** | Haversine distance and area calculation |
| **Elevation** | Profile graphs along routes and between waypoints |
| **Overlays** | GeoJSON annotations, perimeter zones, infrastructure points (1,275+) |
| **Layers** | 45 data layers including earthquakes, fires, aircraft, volcanic activity |
| **Export** | GPX, GeoJSON, KML, print to PDF at specified scale |
| **Geocoding** | Local geocoding — no external API required |

---

### 📡 Communications

Stay connected when infrastructure fails. LAN chat with encryption, DTMF tones, NATO phonetic trainer, antenna calculators, HF propagation charts, and a Meshtastic mesh radio bridge.

<table>
<tr><td width="50%">

**Radio & Comms**
- Frequency database (~340 allocations: US, EU, international)
- Radio equipment inventory (model, serial, firmware, freq range)
- CHIRP-compatible CSV export for radio programming
- Antenna calculator with SVG diagrams (4 types)
- HF propagation prediction (MUF, 7-band table)
- DTMF tone generator (WebAudio 16-key pad)
- NATO phonetic alphabet trainer (quiz + reference)

</td><td width="50%">

**Tactical**
- PACE communications plan builder
- Authentication code system (challenge/response, rotating daily)
- Net schedule tracker with comms check logging
- Message format templates (SITREP, MEDEVAC 9-line, SALUTE, SPOT, ACE, LACE)
- Brevity code dictionary
- LAN chat with AES-GCM encryption
- LAN file transfer (drag-and-drop)
- Meshtastic mesh node management with map overlay

</td></tr>
</table>

---

### 🎯 Preparedness & Planning

Goal-based readiness scoring, alert rules engine, evacuation planning, and a unified timeline that aggregates every date across every module.

<table>
<tr><td width="50%">

**Readiness System**
- Goal-based scoring (% complete per category)
- Regional threat weighting (FEMA NRI county hazard data)
- Daily operations brief (weather, inventory, tasks, family status)
- Custom alert rules engine (IF/THEN conditions with actions)
- Threat intelligence feeds (10 severity categories)
- Emergency Mode orchestrator (broadcasts SSE, auto-creates incident log)

</td><td width="50%">

**Evacuation & Movement**
- Tiered evacuation plans (shelter-in-place → local → bug-out → INCH)
- Go/no-go decision matrix with trigger conditions
- Movement plans (foot march rate, convoy SOP, fuel planning)
- Alternative vehicles (bicycle, horse, boat, ATV) with range calculators
- Route hazard markers (bridges, tunnels, chokepoints, flood zones)
- Route reconnaissance logging
- Rally point cascade and family assembly protocol
- Bug-out bag loadouts (72hr, GHB, INCH, EDC, medical, vehicle)
- Vehicle fleet management with maintenance scheduling

</td></tr>
</table>

**More:** Evacuation drills with live timing and performance tracking | Unified calendar/timeline aggregating all dated events across all modules | Checklists with templates and progress tracking | Countdown timers | Watch/shift rotation planner

---

### 🌾 Agriculture & Food Production

Long-term food independence through garden planning, permaculture design, livestock management, and resource recycling systems.

| Category | Features |
|:---|:---|
| **Garden** | Plot management, USDA hardiness zone lookup, frost date tracking, companion planting (20 pairs), pest/disease guide (10 entries), seed inventory with viability tracking |
| **Permaculture** | Food forest guild designer, 7-layer planting plans, canopy calculator, yield timeline |
| **Soil** | Hugelkultur, swales, biochar, sheet mulching, cover crop projects |
| **Livestock** | Animal records, breeding records with lineage, feed tracking, production logging, pasture rotation |
| **Infrastructure** | Solar tracking, battery health, well monitoring, wood inventory, heating BTU calculator |
| **Aquaponics** | System tracking, water chemistry, fish health, nutrient calculator |
| **Recycling** | Composting, greywater, biogas, material reuse — closed-loop system tracking |
| **Planning** | 1–20 year agricultural development timeline, land carrying capacity, climate adaptation |

---

### 🔒 Security & OPSEC

Tactical-grade security operations, signature management, night operations planning, and CBRN preparedness.

<table>
<tr><td width="50%">

**Physical Security**
- Surveillance camera management (URL, stream type)
- Access log (entry/exit tracking)
- Perimeter zones (geofenced)
- Motion detection events
- Incident reporting (severity, category)
- Encrypted vault for credentials and secrets

</td><td width="50%">

**OPSEC & Tactical**
- Information compartment manager
- OPSEC audit checklists (digital + physical)
- Threat matrix with CARVER assessment
- Observation post logging with range cards
- Signature assessment (visual, audio, electronic, thermal)
- Night operations planner (moonrise/set, ambient light, dark adaptation)
- CBRN equipment inventory and decon procedures
- EMP hardening inventory and grid dependency scanner

</td></tr>
</table>

---

### 👥 Group Operations

Multi-household coordination, leadership structures, ICS/NIMS compliance, and community defense.

| Category | Features |
|:---|:---|
| **Pods** | Multi-household pod management with member roles and skills |
| **Governance** | Chain of command, SOPs, duty roster, onboarding procedures |
| **ICS Forms** | ICS-201, 202, 204, 205, 206, 213, 214, 215 — IAP generator |
| **CERT** | Team management, damage assessment forms, volunteer tracking |
| **Civil Defense** | Shelter management, community warning broadcasts, resource allocation |
| **Disputes** | Mediation tracking, voting/polling system, rationing fairness audit |
| **Federation** | Multi-node peer sync (CRDT-like), dead drop messaging, mutual aid agreements, group exercises |

---

### 📚 Training & Knowledge

Structured skill development with spaced repetition, drill systems, and institutional memory preservation.

| Feature | Detail |
|:---|:---|
| **Skill Trees** | Prerequisite chains per person, cross-training matrix |
| **Courses** | Training course builder with lessons, assessments, instructor assignments |
| **Certifications** | Tracker with renewal reminders and expiry alerts |
| **Drills** | Template library (fire, lockdown, medical, comms failure), no-notice launcher, grading rubric, AAR |
| **Flashcards** | Spaced repetition system (SM-2 algorithm) for critical knowledge |
| **Knowledge Packages** | "If I'm gone" packages per key person — institutional memory preservation |
| **Reference** | Offline field guides, military field manual reference, searchable reference cards |

---

### 🏠 Daily Living

Actually surviving day-to-day under grid-down conditions — schedules, chores, morale, sleep, and recipes that don't need a microwave.

| Module | Features |
|:---|:---|
| **Schedules** | Daily routine builder with templates, work/rest cycle management |
| **Chores** | Assignment rotation with fair distribution tracking |
| **Clothing** | Per-person inventory with cold weather assessment and protective gear tracking |
| **Sanitation** | Supply tracking with consumption projections, waste management, disease prevention |
| **Morale** | Mood tracking with trend analysis, recreational supply inventory, morale events |
| **Sleep** | Sleep log with debt tracking, watch schedule optimizer, fatigue risk assessment |
| **Performance** | Human performance checks with auto risk scoring, work-rest reference (6 profiles) |
| **Recipes** | Grid-down cooking database (campfire, rocket stove, solar oven, dutch oven, preserved foods) |

---

### 🦌 Hunting, Foraging & Wild Food

| Module | Features |
|:---|:---|
| **Hunting** | Game harvest log (species, method, weight, GPS), hunting zones with season management |
| **Fishing** | Catch records (species, bait, conditions, GPS) |
| **Foraging** | Find log with GPS locations, confidence rating, seasonal notes |
| **Traps & Snares** | Placement tracking with check scheduling and catch logging |
| **Wild Edibles** | Reference database (10 seeded species) with photos, season, habitat, look-alikes |
| **Trade Skills** | 13 categories (blacksmithing, woodworking, leatherwork, sewing, soap, candles, etc.) |
| **Preservation** | 8 methods seeded (tanning, distillation, vinegar, cheese, herbal tinctures), batch tracking |

---

### 🔧 Hardware & Sensors

| Module | Features |
|:---|:---|
| **IoT Sensors** | 12 sensor types (temp, humidity, soil moisture, water level, AQI, radiation, pressure, wind, precipitation) with time-series dashboard |
| **Network** | Device inventory with topology tree visualization |
| **Mesh** | Meshtastic node management with map overlay and signal stats |
| **Weather Stations** | Direct integration (Davis, Ecowitt, Ambient Weather) |
| **GPS** | Device management with fix recording and track history |
| **Wearables** | Health data import from wearable devices |
| **Integrations** | MQTT broker, Home Assistant, Node-RED, webhook, CalDAV, Meshtastic — all with test endpoints |

---

### 🧩 Specialized Modules

| Module | Features |
|:---|:---|
| **Supply Caches** | Hidden cache locations with GPS, concealment method, inventory linking |
| **Pets** | Companion animal records with food supply projections and vet records |
| **Youth Programs** | Children and family program management |
| **End-of-Life** | Estate planning, document storage, directive management |
| **Procurement** | Shopping/procurement lists with budget tracking and priority |
| **Intel Collection** | Priority Information Requirements (PIR), classification levels, source tracking |
| **Fabrication** | 3D printing and CNC project tracker with material inventory |
| **Gamification** | 10 achievement badges with awards, leaderboard, and progress tracking |
| **Seasonal Events** | Calendar integration with upcoming event views |
| **Legal Vault** | Legal document storage with expiry alerts and renewal tracking |
| **Drones** | Drone inventory with flight logging, GPS tracks, and maintenance |
| **Fitness** | Exercise logging with weekly stats and trend analysis |
| **Content Packs** | Community content pack sharing and import |

---

### ☢️ NukeMap

Model nuclear detonation effects for 32 real warheads — blast radius, thermal burns, fallout patterns, shelter survival odds, and full WW3 exchange simulations.

| Feature | Detail |
|:---|:---|
| **Warheads** | 32 real-world warhead profiles with accurate yield data |
| **Effects** | Blast overpressure rings, thermal radiation, ionizing radiation, fallout plume |
| **Shelter** | Survival probability by shelter type and distance |
| **Scenarios** | Full WW3 exchange simulation with 418 verified target locations |
| **Physics** | Based on published nuclear effects data (Glasstone & Dolan) |
| **Offline** | Shared basemap with VIPTrack — works without internet |

---

### ✈️ VIPTrack

Real-time military and VIP aircraft monitoring using live ADS-B data feeds.

| Feature | Detail |
|:---|:---|
| **Military Aircraft** | 11,000+ military aircraft database |
| **Government/VIP** | 12,000+ government and VIP aircraft |
| **Visualization** | Altitude-colored trails, photos, aircraft details |
| **Watchlists** | Custom watchlists with alert notifications |
| **Data** | OpenSky Network ADS-B feed (no API key required) |

---

### 🖨️ Print & Export

Generate field-ready documents from your data, formatted for print or lamination.

- **Operations Binder** — complete field reference from all modules
- **Emergency Sheets** — quick-reference cards for grab-and-go
- **Laminated Wallet Cards** — vehicle cards, medication cards, contact cards
- **Signal Operating Instructions** — frequency reference, auth codes, net schedules
- **Medical Flipbook** — pocket-sized TCCC/triage reference
- **FEMA Household Plan** — standard family emergency plan format
- **Skills Gap Report** — cross-training needs analysis
- **Seasonal Calendar** — planting, maintenance, and preparedness schedule

---

### 🔄 Interoperability

No data lock-in. Import and export in standard formats.

| Direction | Formats |
|:---|:---|
| **Import** | CSV, vCard, GPX, GeoJSON, KML, iCalendar (ICS), CHIRP radio CSV |
| **Export** | CSV, vCard, GPX, GeoJSON, KML, ICS, CHIRP, ADIF (ham radio), FHIR R4 (medical), Markdown |
| **Batch** | Bulk import/export operations with format auto-detection |
| **History** | Full export/import history tracking |
| **Print** | PDF generation for all major modules |

---

## Integrated Services

NOMAD manages 8 external services automatically. Each is optional — install what you need, skip what you don't.

| Service | Port | Purpose |
|:---|:---:|:---|
| **Ollama** | 11434 | Local LLM inference — GPU-accelerated (CUDA, Metal, ROCm) |
| **Qdrant** | 6333 | Vector database for RAG knowledge base |
| **Kiwix** | 8888 | Offline Wikipedia and reference libraries (13 ZIM categories, 3 tiers) |
| **CyberChef** | 8889 | Data encoding, decoding, encryption, and analysis |
| **Kolibri** | 8300 | Offline Khan Academy and educational content |
| **Stirling PDF** | 8443 | PDF merge, split, compress, OCR, and convert |
| **FlatNotes** | 8890 | Markdown note-taking |
| **BitTorrent** | dynamic | Media content downloading (via libtorrent) |

All services feature auto-start, health monitoring (crash detection + auto-restart), download resume, and ordered shutdown.

---

## Data Sources

NOMAD bundles or connects to 53 offline-compatible datasets across 3 tiers. No API keys required.

### Tier 1 — Bundled (~75 MB, auto-included)

USDA FoodData SR Legacy (7,793 foods) | FEMA National Risk Index (all US counties) | NOAA frost dates & weather stations | USDA hardiness zones by ZIP | USDA FoodKeeper shelf life | World Magnetic Model (compass correction) | EPA fuel economy | Firewood BTU ratings | FRS/GMRS/MURS frequencies | NRC nuclear facility locations | ICS resource typing | HYG star database (celestial navigation) | MIL-STD-2525 symbology

### Tier 2 — Downloadable (100 MB–1 GB each)

Open Food Facts (barcode lookup) | RepeaterBook (amateur radio) | USGS earthquake catalog & faults | SRTM elevation tiles | NOAA storm events | National Hydrography Dataset | NREL solar irradiance | HIFLD critical infrastructure | USDA PLANTS database | SIDER drug side effects | iNaturalist/GBIF species data | FishBase | Global Wind Atlas | US Census population density | PFAF edible perennials | Mushroom Observer

### Tier 3 — Deep Data (1 GB+ each)

OpenStreetMap state extracts | FEMA National Flood Hazard Layer | SSURGO soil survey | DrugBank interactions (2.5M pairs) | ESA WorldCover (10m land cover) | USGS 3DEP LiDAR DEM | Full NHD hydrography

---

## Themes & Dashboard Modes

### Themes

| Theme | Style |
|:---|:---|
| **Atlas** | Clean desert sand — default light theme |
| **Midnight** | Deep dark — night operations friendly |
| **Cobalt** | Blue steel — tactical display aesthetic |
| **Ember** | Warm dark — reduced eye strain |
| **Paper** | High contrast — E-Ink and print optimized |

### Dashboard Modes

| Mode | Focus |
|:---|:---|
| **Command Center** | Full operational dashboard — all modules visible |
| **Homestead** | Farm and self-reliance focus — agriculture, livestock, garden, weather |
| **Essentials** | Streamlined basics — inventory, medical, maps, contacts, weather |

---

## Getting Started

### Windows

Download **NOMADFieldDesk-Windows.exe** (portable) or **NOMAD-Setup.exe** (installer) from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest) and double-click. No install needed — runs from USB, desktop, anywhere.

### Linux

Download **NOMADFieldDesk-Linux** from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest), `chmod +x`, and run. AppImage also available. Requires GTK WebKit:
```bash
sudo apt install python3-gi gir1.2-webkit2-4.1
```

### macOS

Download **NOMADFieldDesk-macOS** from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest). Uses native WebKit — no extra dependencies.

---

## Requirements

| Platform | Dependencies |
|:---|:---|
| **Windows 10/11** | WebView2 Runtime (included in Windows 11) |
| **Linux** | Python 3.10+, GTK WebKit (`python3-gi gir1.2-webkit2-4.1`) |
| **macOS** | Python 3.10+ (uses native WebKit) |

---

## Building from Source

```bash
git clone https://github.com/SysAdminDoc/project-nomad-desktop.git
cd project-nomad-desktop
pip install -r requirements.txt
python nomad.py
```

### Build portable executable

```bash
pip install pyinstaller
pyinstaller build.spec
```

### CI/CD

GitHub Actions builds multi-platform binaries on every tagged release:
- Windows: `.exe` + Inno Setup installer (optional code signing)
- Linux: Binary + AppImage
- macOS: Universal binary
- All releases include `SHA256SUMS.txt` for integrity verification

---

## Architecture

```
nomad.py                          Entry point — pywebview + pystray + Flask
config.py                         Configuration (env-overridable, portable mode)
db.py                             SQLite layer — 264 tables, WAL mode, FK enforcement

web/
├── app.py                        Flask app factory — 59 blueprint registrations
├── blueprints/                   59 REST API modules (~1,644 routes)
├── templates/
│   ├── index.html                SPA shell
│   └── index_partials/           30+ tab partials (Jinja2)
├── static/                       CSS/JS bundles (esbuild)
├── nukemap/                      Nuclear effects simulator
└── viptrack/                     Aircraft tracking UI

services/
├── manager.py                    Process manager (GPU detection, health monitor)
├── ollama.py                     LLM inference service
├── kiwix.py                      Offline reference library
├── cyberchef.py                  Data encoding/analysis
├── kolibri.py                    Educational content
├── qdrant.py                     Vector database
├── stirling.py                   PDF tools
├── flatnotes.py                  Markdown notes
└── torrent.py                    BitTorrent client

db_migrations/                    Numbered SQL migration scripts
tests/                            888 pytest tests
.github/workflows/build.yml       Multi-platform CI/CD
```

**Design Principles:** Offline-first | Data sovereignty | Print-friendly | Modular | Low-resource compatible | Fail graceful | AI-optional (enhances, never gates) | Federation-aware | Import/export everything (no lock-in) | Regionally adapted | Multi-scale (solo → family → pod → federation)

---

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Desktop edition by [SysAdminDoc](https://github.com/SysAdminDoc).
