# Project N.O.M.A.D. for Windows — Implementation Roadmap

## Phase 1: Proactive AI Situational Awareness
**Builds on:** Existing burn rates, dashboard_critical, weather trend, situation-context AI injection
**Effort:** Medium (1-2 sessions)

- [x] Background alert scheduler thread — runs every 5 minutes, checks 5 conditions (burn rate, expiration, pressure drop, incident clusters, low stock)
- [x] Alert API endpoints — /api/alerts, /api/alerts/<id>/dismiss, /api/alerts/dismiss-all, /api/alerts/generate-summary
- [x] Alert bar in dashboard header — auto-shows critical alerts, bell icon with badge count
- [x] AI-generated natural language situation summaries via Ollama
- [x] Alert history table in DB with dismissal tracking + 24h dedup + 7-day auto-prune
- [x] Browser notification + alert sound on new critical alerts
- [ ] SSE endpoint for instant push (currently polls every 60s — good enough for now)

## Phase 2: Interactive Decision Engine
**Builds on:** Scenario AI personas, situation-context injection, existing reference cards
**Effort:** Medium (1-2 sessions)

- [x] Decision tree data structure — JSON-defined flowcharts with question/result nodes and branching edges
- [x] 6 built-in trees: water purification, wound assessment, shelter construction, fire starting, food preservation, radio setup + START triage
- [x] Decision tree UI — card-based step-by-step with back/forward, breadcrumb trail, severity-colored results
- [ ] Context-aware: tree can reference inventory ("You have [X] water filters") and contacts ("Your medic is [name]")
- [x] Works fully offline without Ollama — pure JS decision logic
- [x] AI enhancement: "Ask AI" button at any step sends context to Ollama for deeper guidance
- [x] Print current decision path as a printable procedure card

## Phase 3: Medical Module
**Builds on:** Dosage calculator, contacts with blood_type/medical_notes, field_medic AI persona
**Effort:** Large (2-3 sessions)

- [x] Patient profiles linked to contacts — name, age, weight, sex, blood type, allergies, medications, conditions, notes
- [x] Drug interaction checker — 26 drug pairs with major/moderate severity (NSAIDs, anticoagulants, opioids, SSRIs, etc)
- [x] Interactive triage flowchart — START triage built as Phase 2 decision tree (already in Guides tab)
- [x] Wound documentation — log by location, type (8), severity (4), description, treatment, chronological timeline
- [x] Vital signs log per patient — BP, pulse, resp, temp, SpO2, pain, GCS with color-coded abnormals
- [x] Printable patient care card — full HTML page with vitals history, wound log, allergies, medications
- [x] Import patients from contacts with one click
- [ ] Allergy-aware dosage calculator — cross-reference patient allergies with med calc (enhancement)
- [ ] Wound photo upload with side-by-side comparison over time (enhancement)
- [ ] Medical bag inventory template — pre-built checklist (can use existing checklist system)

## Phase 4: Immersive Training Scenarios
**Builds on:** Drill system (6 drills with timer/history), scenario AI personas
**Effort:** Large (2-3 sessions)

- [x] Scenario engine — state machine with phases, decision branching, progress bar
- [x] 4 multi-phase scenarios: Grid Down (7 phases), Medical Crisis (5), Evacuation Under Threat (5), Winter Storm (5)
- [x] AI complication injector — 50% chance between phases, uses real inventory/contacts/situation data, Ollama-generated with fallback
- [x] Decision logging — every choice timestamped and stored in SQLite
- [x] After-Action Review — AI scores 0-100 with detailed assessment and improvement recommendations
- [x] Scenario state persists across app restarts (scenarios table)
- [x] Scenario history with score tracking and comparison

## Phase 5: Food Production Module
**Builds on:** Companion planting table, seed saving reference, homesteader AI persona, inventory system
**Effort:** Large (2-3 sessions)

- [x] Garden plots — name, dimensions (sq ft), sun exposure, soil type, total area calc
- [x] USDA hardiness zone lookup — offline latitude-based zones 3a-11a+ with frost dates
- [x] Seed inventory — species, variety, quantity, year harvested, auto-calculated viability (25 species)
- [x] Harvest log — crop, quantity, unit, plot source — auto-creates/updates inventory items
- [x] Livestock records — 10 species, per-animal health event logging, grouped display
- [ ] Planting calendar engine — month-by-month tasks based on zone + crops (enhancement)
- [ ] Preservation calendar — when to can/dry/ferment based on harvest log (enhancement)
- [ ] Garden map overlay — plot boundaries on the offline map (enhancement)

## Phase 6: Advanced Offline Maps
**Builds on:** MapLibre + PMTiles + waypoints + zones + GPX export
**Effort:** Large (2-3 sessions)

- [x] Print layout — captures map as PNG, generates printable page with title, coordinates, compass, scale
- [x] Property boundary tool — draw polygon, calculates area (sq ft/acres) and perimeter (ft/miles), saved as zone layer
- [x] Map bookmarks — save/recall map views (center + zoom), bookmark list in management area
- [x] Bearing & distance calculator — click two points, shows bearing (degrees + cardinal) and distance (km/mi) with line
- [ ] Elevation data integration — download SRTM/ASTER DEM tiles (enhancement — requires large dataset)
- [ ] Elevation profile on routes — click two waypoints, see elevation change (enhancement — requires DEM)
- [ ] Contour line layer — render terrain contours (enhancement — requires DEM processing)
- [ ] Route planning — A* pathfinding on road network (enhancement — requires graph extraction from PMTiles)
- [ ] Offline geocoding — local placename index from PMTiles features (enhancement)

## Phase 7: Multi-Node Federation (Sneakernet++)
**Builds on:** Existing ZIP export/import, LAN auth
**Effort:** Medium-Large (2 sessions)

- [x] Node identity — auto-generated UUID + customizable name, persistent in settings
- [x] Auto-discovery on LAN — UDP broadcast on port 18080, background listener auto-responds
- [x] One-click LAN sync — push/receive/pull data between nodes over HTTP (merge mode)
- [x] Sync log — tracks direction, peer identity, IP, table counts, timestamps
- [x] Node attribution — synced records tagged with source node ID
- [ ] Vector clocks for conflict detection (enhancement — current merge is additive)
- [ ] Three-way merge UI for conflicts (enhancement)
- [ ] Distributed watch schedule (enhancement)

## Phase 8: Power Management
**Builds on:** Solar/battery/generator calculators, solar_expert AI persona
**Effort:** Large-Huge (3+ sessions)

- [x] Power device registry — 5 types (solar, battery, controller, inverter, generator) with type-specific specs
- [x] Manual power log — battery voltage, SOC, solar watts/Wh, load watts/Wh, generator status
- [x] Power budget dashboard — autonomy projection, net daily balance, color-coded SOC and autonomy
- [ ] Charge controller USB integration (stretch — Victron VE.Direct, Renogy RS-232)
- [ ] Weather-aware solar forecast (stretch — pressure trend + cloud data)
- [ ] Low battery alerts integrated with Phase 1 alert system (enhancement)

## Phase 9: Security Module
**Builds on:** Situation board, incident log, tactical AI persona
**Effort:** Huge (3+ sessions, hardware-dependent)

- [x] Camera viewer — MJPEG live streams + snapshot auto-refresh (5s) + HLS support
- [x] Camera registry — name, URL, stream type, location, with common camera URL examples
- [x] Access log — person, direction (entry/exit/patrol), location, method (visual/camera/sensor/radio), notes
- [x] Security dashboard — threat level, active cameras, 24h access count, 48h incident count
- [ ] Motion detection alerts (stretch — requires OpenCV)
- [ ] Perimeter zones linked to cameras (enhancement)
- [ ] RF scanner integration (stretch — requires SDR hardware)

## Phase 10: Deep Document Understanding
**Builds on:** Full RAG pipeline (Qdrant + nomic-embed-text + chunking)
**Effort:** Large (2-3 sessions)

- [ ] Document classifier — on upload, AI categorizes document type (medical, property, vehicle, financial, legal, reference)
- [ ] Entity extraction — AI extracts structured data from documents: names, dates, medications, addresses, coordinates, vehicle specs
- [ ] Auto-populate — extracted entities written back to structured tables (contacts, inventory, waypoints)
- [ ] Multi-collection Qdrant — separate collections per document type for more precise retrieval
- [ ] Document summary — AI generates a 2-3 sentence summary stored with each document for quick browsing
- [ ] Cross-reference — "This document mentions [contact name] — link it?" prompts when entities match existing records

---

## Priority Order Rationale

1. **Proactive AI** — Highest user value, medium effort, builds entirely on existing infrastructure
2. **Decision Engine** — Transforms static reference cards into actionable guidance, works offline
3. **Medical** — Life-safety impact, builds on Phase 2 decision tree engine
4. **Training** — Differentiator from competitors, builds on Phase 2 + existing drills
5. **Food Production** — High value for long-term preparedness users
6. **Maps** — Advanced features for serious users, high complexity
7. **Federation** — Force multiplier for groups/communities
8. **Power** — Hardware integration complexity, niche audience
9. **Security** — Highest hardware dependency, most complex
10. **Deep Documents** — AI quality dependent, can improve incrementally
