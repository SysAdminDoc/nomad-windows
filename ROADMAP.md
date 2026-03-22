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

- [ ] Garden plots table — name, dimensions (sq ft), sun exposure (full/partial/shade), soil type, GPS coordinates
- [ ] USDA hardiness zone lookup — offline dataset mapping zip codes/coordinates to zones and frost dates
- [ ] Planting calendar engine — generates month-by-month tasks based on zone, selected crops, and plot specs
- [ ] Seed inventory — structured table: species, variety, quantity, year harvested, viability percentage (auto-calculated from age + species data)
- [ ] Harvest log — date, crop, quantity (weight/count), plot source — auto-creates or updates inventory item
- [ ] Preservation calendar — when to can/dry/ferment/smoke based on harvest log entries
- [ ] Livestock records — per-animal: species, name/tag, DOB, weight log, health events, vaccination schedule, feed consumption
- [ ] Garden map overlay — plot boundaries drawn on the offline map with crop labels

## Phase 6: Advanced Offline Maps
**Builds on:** MapLibre + PMTiles + waypoints + zones + GPX export
**Effort:** Large (2-3 sessions)

- [ ] Elevation data integration — download SRTM/ASTER DEM tiles for the user's region, serve via Flask
- [ ] Elevation profile on routes — click two waypoints, see the elevation change between them
- [ ] Contour line layer — render terrain contours from DEM data as a MapLibre layer
- [ ] Route planning — A* pathfinding on road network from PMTiles data with distance/time/elevation estimates
- [ ] Print layout — dedicated print view with scale bar, legend, north arrow, title block at user-selected zoom/bounds
- [ ] Property boundary tool — draw a polygon, calculate area (acres), perimeter length, tag as "property"
- [ ] Offline geocoding — build a local placename index from PMTiles features for search without Nominatim

## Phase 7: Multi-Node Federation (Sneakernet++)
**Builds on:** Existing ZIP export/import, LAN auth
**Effort:** Medium-Large (2 sessions)

- [ ] Node identity — generate a unique node ID on first run, store in settings (UUID + friendly name)
- [ ] Sync manifest with vector clocks — each record gets a `node_id` + `updated_at` timestamp for conflict detection
- [ ] Three-way merge on import — detect conflicts (same record modified on two nodes), present merge UI
- [ ] Auto-discovery on LAN — mDNS/UDP broadcast to find other N.O.M.A.D. instances on the network
- [ ] One-click LAN sync — select a discovered node, pull/push changes over HTTP
- [ ] Sync log — track what was synced, when, from which node
- [ ] Shared incident log with node attribution — each incident tagged with originating node
- [ ] Distributed watch schedule — assign watch shifts to nodes, display on a shared calendar

## Phase 8: Power Management
**Builds on:** Solar/battery/generator calculators, solar_expert AI persona
**Effort:** Large-Huge (3+ sessions)

- [ ] Power device registry — define solar panels (wattage, count), batteries (type, capacity), charge controllers, inverters
- [ ] Manual power log — log daily readings: battery voltage, solar yield (Wh), load consumption
- [ ] Power budget dashboard — visualize generation vs consumption, projected autonomy
- [ ] Charge controller USB integration (stretch) — Victron VE.Direct protocol parser, Renogy RS-232 protocol
- [ ] Weather-aware solar forecast (stretch) — use barometric pressure trend + cloud observations to estimate next-day yield
- [ ] Low battery alerts — threshold-based alerts integrated with Phase 1 alert system

## Phase 9: Security Module
**Builds on:** Situation board, incident log, tactical AI persona
**Effort:** Huge (3+ sessions, hardware-dependent)

- [ ] Camera viewer — RTSP/HTTP MJPEG stream display in an iframe or canvas element
- [ ] Camera registry — add cameras by URL, name, location on map
- [ ] Motion detection alerts (stretch) — OpenCV-based frame differencing on server-side, push alert to frontend
- [ ] Access log — manual or sensor-triggered entry/exit logging with timestamps
- [ ] Perimeter zones on map — link drawn zones to camera feeds and alert rules
- [ ] Security dashboard — consolidated view of all cameras, recent access log entries, incident timeline
- [ ] RF scanner integration (stretch) — SDR dongle spectrum sweep, identify active transmitters in area

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
