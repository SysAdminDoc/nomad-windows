# Project N.O.M.A.D. Desktop — Implementation Roadmap

> **Current**: v3.3.0 — 372 routes, 57 tables, 8 managed services, 25 prep sub-tabs, 21 decision guides, 41 calculators, 56 quick reference cards, 4 themes, 3 dashboard modes, full cross-platform support (Windows/Linux/macOS)

---

## Completed Phases (v1.0 → v3.3.0)

<details>
<summary>Phase 1: Proactive AI Situational Awareness ✅</summary>

- [x] Background alert scheduler thread — 5-minute cycles, 5 conditions (burn rate, expiration, pressure drop, incident clusters, low stock)
- [x] Alert API endpoints — /api/alerts, dismiss, dismiss-all, generate-summary
- [x] Alert bar in dashboard header — auto-shows critical alerts, bell icon with badge count
- [x] AI-generated natural language situation summaries via Ollama
- [x] Alert history table in DB with dismissal tracking + 24h dedup + 7-day auto-prune
- [x] Browser notification + alert sound on new critical alerts
- [ ] SSE endpoint for instant push (currently polls every 60s — good enough for now)
</details>

<details>
<summary>Phase 2: Interactive Decision Engine ✅</summary>

- [x] Decision tree data structure — JSON-defined flowcharts with question/result nodes and branching edges
- [x] 21 built-in trees: water purification, wound assessment, shelter, fire starting, food preservation, radio setup, START triage, vehicle emergency, bug-out, antibiotic selection, hypothermia, chest trauma, envenomation, missing person, wound infection, anaphylaxis, electrical hazard, drowning, water assessment, food safety, power outage
- [x] Decision tree UI — card-based step-by-step with back/forward, breadcrumb trail, severity-colored results
- [x] AI enhancement: "Ask AI" button at any step sends context to Ollama for deeper guidance
- [x] Print current decision path as a printable procedure card
- [ ] Context-aware: tree can reference inventory ("You have [X] water filters") and contacts ("Your medic is [name]")
</details>

<details>
<summary>Phase 3: Medical Module ✅</summary>

- [x] Patient profiles linked to contacts — name, age, weight, sex, blood type, allergies, medications, conditions
- [x] Drug interaction checker — 26 drug pairs with major/moderate severity
- [x] Interactive triage flowchart — START triage as decision tree
- [x] Wound documentation — 8 types × 4 severities, location, treatment, chronological timeline
- [x] Vital signs log — BP, pulse, resp, temp, SpO2, pain, GCS with color-coded abnormals
- [x] TCCC MARCH protocol wizard — 5 steps × 4 actions interactive
- [x] Triage board — MCI 4-column Kanban (Immediate/Delayed/Minor/Deceased)
- [x] SBAR handoff report generator with print
- [x] Printable patient care cards
- [ ] Allergy-aware dosage calculator (enhancement)
- [ ] Wound photo upload with side-by-side comparison (enhancement)
- [ ] Medical bag inventory template (enhancement)
</details>

<details>
<summary>Phase 4: Immersive Training Scenarios ✅</summary>

- [x] Scenario engine — state machine with phases, decision branching, progress bar
- [x] 4 multi-phase scenarios: Grid Down (7 phases), Medical Crisis (5), Evacuation Under Threat (5), Winter Storm (5)
- [x] AI complication injector — 50% chance, uses real inventory/contacts data, Ollama-generated with fallback
- [x] Decision logging — timestamped in SQLite
- [x] After-Action Review — AI scores 0-100 with assessment and improvement recommendations
- [x] Scenario state persists across restarts
</details>

<details>
<summary>Phase 5: Food Production Module ✅</summary>

- [x] Garden plots — dimensions, sun exposure, soil type
- [x] USDA hardiness zone lookup — offline latitude-based zones 3a-11a+
- [x] Seed inventory — 25 species with auto-calculated viability
- [x] Harvest log — auto-creates/updates inventory items
- [x] Livestock records — 10 species with health logging
- [x] Planting calendar — 31 zone 7 entries with yield/sqft and calories/lb
- [x] Yield/caloric analysis — person-days of food production
- [x] Preservation log — canned/dried/frozen tracking
- [ ] Garden map overlay — plot boundaries on offline map (enhancement)
</details>

<details>
<summary>Phase 6: Advanced Offline Maps ✅</summary>

- [x] Print layout — captures map as PNG with title, coordinates, compass, scale
- [x] Property boundary tool — polygon area (sq ft/acres) and perimeter
- [x] Map bookmarks — save/recall views
- [x] Bearing & distance calculator — bearing (degrees + cardinal) and distance (km/mi)
- [x] 50+ map sources (Protomaps, Geofabrik, BBBike, Natural Earth, USGS, SRTM, NOAA, FAA, Sentinel-2)
- [x] Route CRUD with waypoint support
- [x] Annotations with 12 icon types and elevation
- [ ] Elevation profiles on routes (requires DEM data)
- [ ] Offline geocoding (requires index extraction)
- [ ] Contour line layer (requires DEM processing)
</details>

<details>
<summary>Phase 7: Multi-Node Federation ✅</summary>

- [x] Node identity — auto-generated UUID + customizable name
- [x] Auto-discovery on LAN — UDP broadcast on port 18080
- [x] One-click LAN sync — push/receive/pull over HTTP (merge mode)
- [x] Sync log with direction, peer identity, IP, table counts
- [x] Federation v2 — trust levels (observer/member/trusted/admin), resource marketplace, SITBOARD
- [ ] Vector clocks for conflict detection (enhancement)
- [ ] Three-way merge UI for conflicts (enhancement)
</details>

<details>
<summary>Phase 8: Power Management ✅</summary>

- [x] Power device registry — 5 types with type-specific specs
- [x] Manual power log — voltage, SOC, solar watts/Wh, load watts/Wh, generator
- [x] Power budget dashboard — autonomy projection, net daily balance, color-coded gauges
- [x] Sensor integration with time-series query and period filtering
- [ ] Charge controller USB integration (stretch — Victron VE.Direct, Renogy RS-232)
- [ ] Weather-aware solar forecast (stretch)
</details>

<details>
<summary>Phase 9: Security Module ✅</summary>

- [x] Camera viewer — MJPEG + snapshot (5s refresh) + HLS
- [x] Camera registry with common camera URL examples
- [x] Access log — entry/exit/patrol with timestamps
- [x] Security dashboard — threat level, active cameras, 24h/48h counts
- [ ] Motion detection alerts (stretch — requires OpenCV)
- [ ] Perimeter zones linked to cameras (enhancement)
</details>

<details>
<summary>Phase 10: Deep Document Understanding ✅</summary>

- [x] Document classifier — 8 categories, auto-runs after embedding
- [x] Entity extraction — people, dates, medications, addresses, phones, vehicles, amounts, coordinates
- [x] Document summary — 2-3 sentence AI summaries
- [x] Cross-reference — extracted names matched against contacts DB
- [x] Analyze All for bulk analysis
- [ ] Auto-populate — extracted entities written back to structured tables (enhancement)
</details>

<details>
<summary>Phase 11: Competitive Feature Parity ✅</summary>

- [x] Skills Tracker — 60 survival skills, 10 categories, proficiency levels
- [x] Ammo Inventory — caliber tracking with summary cards
- [x] Community Resources — mutual aid network with trust levels
- [x] Radiation Dose Tracker — cumulative rem, 7-10 Rule
- [x] Fuel Storage — type-grouped totals, stabilization, expiry
- [x] Equipment Maintenance — service scheduling, status tracking
- [x] 6 new calculators (ballistics, composting, pasture, natural building, fallout, canning)
- [x] 6 new quick reference cards (emergency phrases, animal tracks, mushrooms, foraging calendar, digital modes, ham license)
- [x] ICS-213, ICS-309, ICS-214 forms
- [x] CHIRP CSV export
</details>

<details>
<summary>Phase 12: Original N.O.M.A.D. Feature Parity ✅</summary>

- [x] FlatNotes service — markdown note-taking app (port 8890)
- [x] Unified download queue — aggregates all downloads (services, ZIMs, maps, models) in single view
- [x] Service process logs — stdout/stderr capture per service (500-line ring buffer)
- [x] Content update checker — detects newer ZIM versions against catalog
- [x] Wikipedia tier selection UI — size picker (Mini 1.2MB → Full 115GB)
- [x] Self-update system — GitHub release download with platform detection
- [x] Cross-platform startup toggle — Windows registry, macOS LaunchAgent, Linux XDG autostart
</details>

---

## THE OPTIMAL VERSION — Implemented in v4.0.0

All 10 phases of the optimal vision have been implemented. The app has been transformed from a comprehensive data management tool into a **living operations center**.

---

<details>
<summary>Phase 13: Real-Time Hardware Integration ✅</summary>

- [x] **Serial port bridge** — `/api/serial/ports`, `/api/serial/connect`, `/api/serial/disconnect`, `/api/serial/status` with pyserial auto-detect + graceful fallback
- [x] **Sensor data charts** — `/api/sensors/chart/<device_id>` with range aggregation (raw/hour/day/week) for time-series visualization
- [x] **Historical data graphing** — Canvas 2D chart UI in Power sub-tab with device selector
- [x] **Serial port manager UI** — Settings tab with scan, connect/disconnect, status indicators
- [ ] Victron VE.Direct / Renogy RS-232 specific protocols (stretch — requires hardware testing)
- [ ] BMP280/BME280 sensor bridge (stretch — requires Arduino/ESP32)
- [ ] Weather station bridge (stretch — Davis/Ambient/Ecowitt)
- [ ] GPS receiver auto-position (stretch — u-blox USB)
</details>

<details>
<summary>Phase 14: Mesh Networking & Resilient Communications ✅</summary>

- [x] **Meshtastic bridge stub** — `/api/mesh/status`, `/api/mesh/messages` (GET/POST), `/api/mesh/nodes` with local message storage in `mesh_messages` table
- [x] **Comms status board** — `/api/comms/status-board` aggregating LAN peers, mesh nodes, federation peers, comms_log, active frequencies
- [x] **Comms status board UI** — Radio sub-tab with channel status indicators and federation peer counts
- [ ] Full Meshtastic Web Serial API integration (requires hardware)
- [ ] JS8Call / Winlink / APRS integration (requires radio software)
- [ ] Federation over mesh (requires Meshtastic hardware)
- [ ] Dead drop encrypted USB messaging (enhancement)
</details>

<details>
<summary>Phase 15: Intelligent Automation & Scheduling ✅</summary>

- [x] **Task scheduler engine** — `/api/tasks` CRUD + `/api/tasks/<id>/complete` with auto-recurrence (daily/weekly/monthly) + `/api/tasks/due`; `scheduled_tasks` table
- [x] **Sunrise/sunset engine** — `/api/sun` pure Python NOAA solar calculator; returns sunrise, sunset, civil twilight, golden hour, day length
- [x] **Predictive alerts** — `/api/alerts/predictive` analyzes inventory burn rates, expiration dates, fuel expiry, equipment maintenance overdue, scheduled tasks overdue
- [x] **Task manager UI** — Settings tab with create/complete/delete, color-coded due dates, category badges, recurrence icons
- [x] **Sun widget** — Live dashboard widget showing sunrise/sunset/day length
- [x] **Predictive alerts UI** — Integrated into alert bar with "PREDICTED" badge
- [ ] Weather-triggered actions (enhancement — requires weather station data)
- [ ] Shift/watch planner with rotation schedules (enhancement)
</details>

<details>
<summary>Phase 16: Advanced AI Capabilities ✅</summary>

- [x] **AI SITREP generator** — `/api/ai/sitrep` queries 24h activity, inventory, incidents, weather, power, vitals; generates military-format situation report via Ollama
- [x] **AI action execution** — `/api/ai/execute-action` parses natural language: "add [qty] [item] to inventory", "log incident [desc]", "create note [title]", "add waypoint [name] at [lat],[lng]"
- [x] **AI memory** — `/api/ai/memory` GET/POST/DELETE; persistent key facts across conversations stored in settings as JSON; injected into system prompt
- [x] **SITREP button** — Command Post sub-tab with modal display
- [x] **Memory panel** — AI Chat header dropdown with fact list, add/delete
- [ ] Multi-document RAG with citations (enhancement)
- [ ] Conversation branching (enhancement)
- [ ] Model fine-tuning pipeline (enhancement)
</details>

<details>
<summary>Phase 17: Offline-First Data Collection & Import ✅</summary>

- [x] **CSV import wizard** — `/api/import/csv` (upload + preview with headers/samples) + `/api/import/csv/execute` (column mapping to 7 target tables: inventory, contacts, waypoints, seeds, ammo, fuel, equipment)
- [x] **Template quick entry** — `/api/templates/inventory` with 5 templates (155 total items): 72-Hour Kit, Family of 4 - 30 Days, Bug-Out Bag, First Aid Kit, Vehicle Emergency Kit
- [x] **QR code generation** — `/api/qr/generate` produces SVG QR codes (qrcode library with fallback)
- [x] **CSV import modal** — Settings tab with file upload, table selector, column mapping UI, preview, import execution
- [x] **Template dropdown** — Inventory sub-tab quick template selector
- [ ] Barcode/UPC scanning with offline database (enhancement)
- [ ] Photo inventory via AI vision model (enhancement)
- [ ] Voice inventory parsing (enhancement)
</details>

<details>
<summary>Phase 18: Print & Field Operations ✅</summary>

- [x] **Operations binder** — `/api/print/operations-binder` generates complete multi-page HTML: cover, TOC, contacts, frequencies, medical cards, inventory by category, checklists, waypoints, procedures, family plan; @media print CSS
- [x] **Wallet cards** — `/api/print/wallet-cards` generates 5 lamination-ready 3.375"×2.125" cards: ICE, blood type, medications, rally points, frequency quick-ref
- [x] **SOI generator** — `/api/print/soi` classified-style Signal Operating Instructions with frequency assignments, call sign matrix, radio profiles, net schedule, authentication
- [x] **Print buttons** — Settings tab with one-click open for all 3 documents (9 total printable documents now)
- [ ] PDF generation engine (ReportLab/WeasyPrint — enhancement over HTML print)
- [ ] Map atlas pages at multiple zoom levels (enhancement)
</details>

<details>
<summary>Phase 19: Hardened Reliability & Edge Cases ✅</summary>

- [x] **Database integrity check** — `/api/system/db-check` runs PRAGMA integrity_check + foreign_key_check
- [x] **Database optimize** — `/api/system/db-vacuum` runs VACUUM + REINDEX
- [x] **Startup self-test** — `/api/system/self-test` checks DB access, disk space (>100MB), service binaries, port availability, Python version, critical tables
- [x] **Undo system** — `/api/undo` GET/POST with 10-entry deque and 30-second TTL; reverses delete/update operations
- [x] **System health panel** — Settings tab with Run Self-Test, Check Database, Optimize Database buttons and results display
- [x] **Service worker** — Offline-first caching for static assets via PWA
- [ ] Full crash recovery with form state persistence (enhancement)
- [ ] E-ink display mode (enhancement)
- [ ] Battery-aware polling reduction (enhancement)
</details>

<details>
<summary>Phase 20: Community Intelligence Network ✅</summary>

- [x] **Community readiness dashboard** — `/api/federation/community-readiness` aggregates per-node readiness across 7 categories (water/food/medical/shelter/security/comms/power) with network-wide averages
- [x] **Skill matching** — `/api/federation/skill-search` searches local contacts, federation sitboard, and community_resources for matching skills
- [x] **Distributed alert relay** — `/api/federation/relay-alert` POSTs critical alerts to all trusted/admin/member federation peers
- [ ] Supply chain mapping on network map (enhancement)
- [ ] Mutual aid agreements (enhancement)
- [ ] Group scenario training across nodes (enhancement)
</details>

<details>
<summary>Phase 21+22: Mobile Companion & Platform Polish ✅</summary>

- [x] **PWA manifest** — `manifest.json` with app name, icons, standalone display mode, theme color
- [x] **Service worker** — `sw.js` with network-first API strategy, cache-first static strategy, offline fallback for index page; cache name `nomad-v1`
- [x] **Service worker route** — `/sw.js` endpoint for proper scope
- [x] **Meta tags** — `<meta name="theme-color">` + `<link rel="manifest">` for mobile Chrome/Safari
- [x] **Service worker registration** — Auto-registers on page load
- [ ] Mobile-optimized layout with bottom tab bar (enhancement)
- [ ] IndexedDB offline sync for critical data (enhancement)
- [ ] Push notifications (enhancement)
- [ ] Linux .deb/.rpm/AppImage/Flatpak packages (enhancement)
- [ ] Signed macOS DMG (enhancement)
- [ ] ARM64 builds for Raspberry Pi + Apple Silicon (enhancement)
- [ ] Docker headless image (enhancement)
</details>

---

## All 22 Phases Complete — Enhancement Backlog

These items are deferred enhancements that would further improve the platform:

### Hardware (Phase 13 stretch)
- [ ] Victron VE.Direct / Renogy RS-232 charge controller protocols
- [ ] BMP280/BME280 USB sensor bridge
- [ ] Weather station integration (Davis/Ambient/Ecowitt)
- [ ] USB GPS receiver for auto-position

### Communications (Phase 14 stretch)
- [ ] Full Meshtastic Web Serial API
- [ ] JS8Call / Winlink / APRS integration
- [ ] Federation sync over mesh radio
- [ ] Dead drop encrypted USB messaging

### Scheduling (Phase 15 stretch)
- [ ] Weather-triggered actions
- [ ] Shift/watch rotation planner with print

### AI (Phase 16 stretch)
- [ ] Multi-document RAG with clickable citations
- [ ] Conversation branching for "what if" scenarios
- [ ] LoRA fine-tuning pipeline for custom models

### Data Import (Phase 17 stretch)
- [ ] Camera barcode scanning with offline UPC database
- [ ] AI vision inventory (LLaVA/Moondream)
- [ ] Voice-to-inventory natural language parsing
- [ ] Receipt scanner with OCR price extraction

### Print (Phase 18 stretch)
- [ ] ReportLab/WeasyPrint PDF engine
- [ ] Map atlas pages at multiple zoom levels
- [ ] Medical reference pocket flipbook

### Reliability (Phase 19 stretch)
- [ ] Full crash recovery with form state
- [ ] E-ink display optimized mode
- [ ] Battery-aware auto-throttling
- [ ] WCAG 2.1 AA accessibility audit

### Community (Phase 20 stretch)
- [ ] Supply chain visualization on network map
- [ ] Mutual aid agreement contracts
- [ ] Multi-node group training exercises

### Mobile (Phase 21 stretch)
- [ ] Bottom tab bar mobile layout
- [ ] IndexedDB offline data sync
- [ ] Push notifications via Web Push API
- [ ] Compass + inclinometer from phone sensors

### Platform (Phase 22 stretch)
- [ ] Linux .deb/.rpm/AppImage/Flatpak packages
- [ ] Signed + notarized macOS DMG
- [ ] ARM64 builds (Raspberry Pi + Apple Silicon)
- [ ] Docker headless server image
- [ ] USB portable mode detection

### Earlier Phases
- [ ] SSE endpoint for instant alert push (Phase 1)
- [ ] Context-aware decision trees referencing live data (Phase 2)
- [ ] Allergy-aware dosage calculator (Phase 3)
- [ ] Wound photo upload with comparison (Phase 3)
- [ ] Garden map overlay on offline map (Phase 5)
- [ ] Elevation profiles on routes (Phase 6)
- [ ] Contour line rendering (Phase 6)
- [ ] Offline geocoding (Phase 6)
- [ ] Vector clocks for federation conflicts (Phase 7)
- [ ] Motion detection alerts via OpenCV (Phase 9)
- [ ] Auto-populate entities to structured tables (Phase 10)
