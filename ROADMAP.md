# Project N.O.M.A.D. for Windows — Implementation Roadmap

## Phase 1: Proactive AI Situational Awareness
**Builds on:** Existing burn rates, dashboard_critical, weather trend, situation-context AI injection
**Effort:** Medium (1-2 sessions)

- [ ] Background alert scheduler thread in `nomad.py` — runs every 5 minutes, checks:
  - Inventory items with <7 days burn rate remaining
  - Items expiring within 14 days
  - Barometric pressure drop >4mb in 6 hours
  - 3+ incidents in same category within 48 hours
- [ ] Server-Sent Events (SSE) endpoint `/api/alerts/stream` for real-time push to frontend
- [ ] Alert banner in dashboard header — auto-shows critical alerts without user polling
- [ ] AI-generated natural language alert summaries — feed alert data into Ollama with a terse prompt, return "Water supply critical: 4 days remaining at current usage. Reduce consumption or locate new source."
- [ ] Alert history table in DB with dismissal tracking
- [ ] Browser notification for critical alerts (reuse existing `sendNotification()`)

## Phase 2: Interactive Decision Engine
**Builds on:** Scenario AI personas, situation-context injection, existing reference cards
**Effort:** Medium (1-2 sessions)

- [ ] Decision tree data structure — JSON-defined flowcharts with nodes (question/action/result), edges (yes/no/condition)
- [ ] Built-in trees for: water purification, wound assessment, shelter construction, fire starting, food preservation, radio setup
- [ ] Decision tree UI component — card-based step-by-step with back/forward, breadcrumb trail
- [ ] Context-aware: tree can reference inventory ("You have [X] water filters") and contacts ("Your medic is [name]")
- [ ] Works fully offline without Ollama — pure JS decision logic
- [ ] AI enhancement: at any step, user can click "Ask AI" to get deeper guidance
- [ ] Print current decision path as a procedure card

## Phase 3: Medical Module
**Builds on:** Dosage calculator, contacts with blood_type/medical_notes, field_medic AI persona
**Effort:** Large (2-3 sessions)

- [ ] Patient profiles linked to contacts — structured fields: weight, age, allergies (array), current medications (array), conditions (array)
- [ ] Allergy-aware dosage calculator — reads patient profile, flags contraindicated meds
- [ ] Drug interaction matrix — offline SQLite table with ~200 common drug pairs and interaction severity (source: FDA open data)
- [ ] Interactive triage flowchart — START/JumpSTART branching logic as a decision tree (Phase 2 engine)
- [ ] Wound documentation — photo upload per incident with timestamp, linked to patient, side-by-side comparison over time
- [ ] Vital signs log per patient — BP, pulse, temp, SpO2, pain level with timestamped entries and trend chart
- [ ] Medical bag inventory template — pre-built checklist with standard first aid + trauma kit items
- [ ] Printable patient care card — one-page summary of a patient's vitals, meds, allergies, wound photos

## Phase 4: Immersive Training Scenarios
**Builds on:** Drill system (6 drills with timer/history), scenario AI personas
**Effort:** Large (2-3 sessions)

- [ ] Scenario engine — state machine with phases, each phase has: situation description, available actions, time pressure, resource costs
- [ ] 4 multi-phase scenarios: Grid Down (7 days), Medical Crisis, Evacuation Under Fire, Winter Storm
- [ ] AI complication injector — at phase transitions, AI generates context-aware complications based on the user's actual inventory/contacts/situation
- [ ] Decision logging — every user choice is timestamped and stored
- [ ] After-Action Review — AI evaluates decisions against doctrinal best practices, scores each phase, generates improvement recommendations
- [ ] Scenario state persists across app restarts (SQLite table)
- [ ] Leaderboard — compare your scenario scores over time

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
