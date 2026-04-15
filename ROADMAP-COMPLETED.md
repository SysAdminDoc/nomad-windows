# Project N.O.M.A.D. — Completed Roadmap Phases (v8)

### Phase 5: Evacuation, Movement & Route Planning ✅ COMPLETE (v7.14.0)
**Theme:** Connect maps + bags + contacts + vehicles into actionable evacuation and movement plans.
**Effort:** L (4-6 sessions)
**Depends on:** Phase 3 (vehicles, loadouts)
**features.md refs:** §15.5 (Evacuation Planning), §47 (Movement & Convoy), §62 (Alternative Transportation), §6.3 (Bug-Out Routes)

#### Deliverables
1. **Evacuation planning module** — §15.5
   - `evacuation_plans` table (name, tier: shelter-in-place/local/bug-out/INCH, trigger_conditions JSON, timeline JSON)
   - Tiered plans with trigger conditions (what escalates from shelter-in-place to bug-out?)
   - Go/no-go decision matrix
   - T-72h through T-GO timeline checklists
   - Family assembly protocol and rally point cascade
   - Pet evacuation plan
   - Vehicle loading plan (which bags in which vehicle, order)
   - Evacuation drill logger with timing
   - Preparedness sub-tab: new "Evacuation" under Operations category
2. **Movement planning** — §47
   - Foot movement: march rate calculator, route planning with water/rest stops
   - Vehicle convoy: SOP builder, communication plan, fuel planning, rally points
   - Hand signals reference chart
   - Pace count calculator (personal pace count per 100m)
   - Night movement planning
3. **Alternative transportation** — §62
   - `alt_vehicles` table (type: bicycle/horse/boat/ATV, name, capacity, range, condition, maintenance_due)
   - Bicycle, pack animal, watercraft, and other vehicle profiles
   - Multi-modal route planning (drive → bike → foot with transition points)
   - Load capacity and range calculators per vehicle type
   - Feed/fuel requirements for animal transport
4. **Bug-out route system** — §6.3
   - PACE routes (Primary, Alternate, Contingency, Emergency)
   - Route hazard markers (bridges, tunnels, chokepoints, flood zones)
   - Fuel stop planning along route
   - Estimated travel time by mode
   - Printable route card (turn-by-turn with distances and landmarks)
   - Route reconnaissance log (last scouted date, conditions)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~6 (evacuation_plans, evacuation_drills, movement_plans, alt_vehicles, route_hazards, route_recon) | ~30 | USDA pack animal data (Tier 1), USGS transportation (Tier 3 optional) |

---

### Phase 6: Communications & Field Operations ✅ COMPLETE (v7.14.0)
**Theme:** Tactical communications planning and field-expedient survival reference.
**Effort:** L (4-6 sessions)
**features.md refs:** §16.3 (Tactical Comms), §2.3 (Comms Module), §57 (Field Expedient), §2.4 (Weather expansion)

#### Deliverables
1. **PACE communications plan builder** — §16.3
   - `comms_plans` table (name, primary, alternate, contingency, emergency — per communication need)
   - Signal plan (visual/audio signals)
   - Authentication code system (challenge/response, rotating daily codes)
   - Brevity code dictionary
   - Message format templates (SITREP, MEDEVAC 9-line, SALUTE, SPOT, ACE, LACE)
   - Frequency hopping schedule
   - Communications window scheduler
   - CHIRP-compatible CSV export for radio programming
2. **Comms module expansion** — §2.3
   - Radio equipment inventory (model, serial, firmware, battery, freq range)
   - Antenna planning tool
   - Repeater directory
   - Net schedule tracker
   - SDR frequency bookmarks
   - Propagation condition reference (enhanced)
   - Comms check scheduling/logging
3. **Field expedient reference** — §57
   - Improvised water solutions (filter construction, solar still, transpiration bag)
   - Improvised shelter & warmth (debris shelter, emergency fire, stove designs)
   - Improvised tools & repairs (material substitution chart, field repair guide)
   - Improvised communications (antenna designs, signal mirrors, trail markers)
   - All as searchable reference cards in Guides sub-tab
4. **Weather expansion** — §2.4, §16.5
   - Moon phase calculator
   - Frost date tracker
   - Growing season calendar
   - Cloud identification guide
   - Beaufort wind scale
   - Growing degree day calculator
   - Lightning distance calculator

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~6 (comms_plans, radio_equipment, net_schedules, auth_codes, repeater_directory, comms_checks) | ~30 | RepeaterBook (Tier 2 optional) |

---

### Phase 8: Land Assessment & Property ✅ COMPLETE (v7.15.0)
**Theme:** The most expensive prep decision with zero software support — until now.
**Effort:** M (2-3 sessions)
**features.md refs:** §63 (Land & Property Assessment)

#### Deliverables
1. **Site selection scoring** — §63.1
   - Multi-criteria assessment (defensibility, water, soil, agriculture, timber, roads, neighbors, hazards)
   - Scoring 1-10 per criterion with weighted total
   - Auto-populate some scores from FEMA NRI data (hazard exposure) and Census (neighbor density)
2. **Property mapping** — §63.2
   - GPS boundary walk tool → calculate acreage
   - Infrastructure mapping (buildings, wells, power, fencing — on map)
   - Sight line analysis, water features, vegetation, terrain profile
   - Utility mapping with shut-off locations
3. **Development planning** — §63.3
   - Building/garden/solar/water system site selection tools
   - Defensive improvement planning (prioritized by cost/impact)
   - Multi-year development timeline
   - Cost tracker per project
4. **BOL comparison** — §63.4
   - Multi-property side-by-side scoring
   - Travel time analysis (multiple routes, modes, conditions)
   - Seasonal viability, community assessment, legal considerations

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~4 (properties, property_assessments, property_features, development_plans) | ~15 | FEMA NRI (Phase 1), SSURGO soil (Tier 3 optional), USGS 3DEP (Tier 3 optional) |

---

### Phase 9: Medical Phase 2 ✅ COMPLETE (v7.15.0)
**Theme:** Deep medical expansions for austere and long-duration scenarios.
**Effort:** L (4-6 sessions)
**features.md refs:** §52 (Deep Medical Phase 2), §16.2 (Advanced Clinical), §2.2 remaining

#### Deliverables
1. **Pregnancy & childbirth** — §52.1
   - Prenatal tracking, supply checklist, field delivery protocol, postpartum care, APGAR scoring
2. **Dental emergencies** — §52.2
   - Expanded protocols, supply inventory, tooth preservation, jaw stabilization
3. **Veterinary medicine** — §52.3
   - Pet and livestock emergency protocols, animal dosage calculator, zoonotic disease reference
4. **Long-term health management** — §52.4
   - Chronic condition plans (diabetes, hypertension, asthma without pharmacy)
   - Medication weaning protocols
   - Alternative medicine fallbacks
   - Vision/hearing care inventory
5. **Advanced clinical tools** — §16.2
   - IV fluid calculator, burns BSA calculator, tourniquet time tracker
   - TCCC card auto-populated from patient data
   - Medical supply burn rate prediction
   - Herbal/alternative medicine reference database
6. **Medical module expansion** — §2.2 remaining
   - SOAP note format, body diagram for wound location
   - BP/blood sugar trending charts
   - Mental health check-in log
   - Vaccination schedule tracker

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~6 (pregnancies, dental_records, herbal_remedies, chronic_conditions, vaccinations, mental_health_logs) | ~30 | DDInter drug interactions (Tier 1), NIOSH pocket guide (Tier 1) |

---

### Phase 10: Training, Education & Knowledge Preservation ✅ COMPLETE (v7.16.0)
**Theme:** Structured skill development, drills, and institutional memory.
**Effort:** L (4-6 sessions)
**features.md refs:** §22 (Training & Education), §2.10 (Skills expansion), §60 (Knowledge Preservation), §11 (Content & Knowledge)

#### Deliverables
1. **Structured training system** — §22.1
   - Skill trees per person (prerequisite chains)
   - Training course builder with lessons and assessments
   - Certification tracker with renewal reminders
   - Instructor assignments
   - Cross-training matrix (no single point of failure)
   - Printable training cards
2. **Drill system** — §22.2
   - Drill template library (fire, lockdown, medical, comms failure)
   - No-notice drill launcher
   - Multi-phase exercises with injects
   - Grading rubric with deficiency tracking
   - AAR template and hot-wash
3. **Spaced repetition** — §22.3
   - Flashcard system for critical knowledge (medical dosages, radio procedures, knots)
   - Embedded quiz system for any knowledge base section
   - Scenario-linked knowledge (surface relevant articles during scenarios)
4. **Knowledge preservation** — §60
   - "If I'm gone" packages per key person
   - Knowledge bus factor dashboard
   - Skill documentation templates
   - Community journal and decision log
   - Annual knowledge audit
5. **Reference content** — §11.1
   - Offline field guides (edible plants, knots, shelters, fire starting)
   - Military field manual reference
   - Offline recipe database for camp/preservation cooking
   - All as searchable reference cards

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~8 (skill_trees, training_courses, training_lessons, certifications, drill_templates, drill_results, flashcards, knowledge_packages) | ~35 | FEMA CERT materials (Tier 1) |

---

### Phase 11: Group Operations & Governance ✅ COMPLETE (v7.17.0)
**Theme:** Multi-household coordination, leadership, and fair resource allocation.
**Effort:** L (4-6 sessions)
**features.md refs:** §56 (Multi-Household Pod), §15.10 (Group Governance), §61 (Dispute Resolution), §44 (ICS/NIMS), §45 (Civil Defense)

#### Deliverables
1. **Pod management** — §56 (all)
2. **Group governance** — §15.10 (chain of command, roles, SOPs, duty roster, onboarding)
3. **Dispute resolution** — §61 (mediation, voting systems, rationing, work equity, fairness audit)
4. **ICS forms** — §44 (ICS-201, 202, 204, 205, 206, 213, 214, 215 + IAP generator)
5. **CERT integration** — §44 expansion (CERT forms, team management, damage assessment)
6. **Civil defense** — §45 (shelter management, community warning, volunteer management)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~12 | ~40 | FEMA CERT (Tier 1), Robert's Rules (Tier 1) |

---

### Phase 12: Security, OPSEC & Night Operations ✅ COMPLETE (v7.18.0)
**Theme:** Tactical-grade security operations and signature management.
**Effort:** L (4-6 sessions)
**features.md refs:** §1.5 (OPSEC), §16.4 (Tactical Security), §48 (Signature Management), §28 (Night Operations), §15.4 (CBRN), §46 (EMP)

#### Deliverables
1. **OPSEC module** — §1.5 (compartment manager, audit checklist, cover stories, duress signals, digital/physical security)
2. **Tactical security** — §16.4 (threat matrix, CARVER, pattern of life, OP log, range cards, counter-surveillance)
3. **Signature management** — §48 (visual, audio, electronic, thermal — assessment and reduction)
4. **Night operations** — §28 (moonrise/set, ambient light, dark adaptation timer, NVG inventory, blackout protocol, lighting management)
5. **CBRN module** — §15.4 (equipment inventory, decon procedures, KI dosage, fallout decay, contamination mapping, MOPP levels)
6. **EMP hardening** — §46 (Faraday inventory, grid dependency scanner, manual alternative mapping, cascading failure analysis)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~10 | ~35 | Military work-rest tables (Tier 1), Venomous species (Tier 1) |

---

### Phase 13: Agriculture & Permaculture ✅ COMPLETE (v7.19.0)
**Theme:** Long-term food independence through perennial and advanced agricultural systems.
**Effort:** M (2-3 sessions)
**features.md refs:** §58 (Permaculture), §12 (Homesteading expansion), §55 (Resource Recycling)

#### Deliverables
1. **Food forest design** — §58.1 (layer planner, guild designer, yield timeline, canopy calculator)
2. **Soil building** — §58.2 (hugelkultur, swales, sheet mulching, biochar, cover crops)
3. **Perennial management** — §58.3 (fruit trees, grafting, mushroom cultivation, herb spirals, pollinators, seed saving)
4. **Multi-year planning** — §58.4 (1-20 year plan, land carrying capacity, climate adaptation)
5. **Livestock expansion** — §12.2 (breeding records, feed tracking, production tracking, pasture rotation)
6. **Homestead infrastructure** — §12.3 (solar tracking, battery health, well monitoring, wood inventory)
7. **Aquaponics/hydroponics** — §12.4 (water chemistry, fish health, nutrient calculator)
8. **Resource recycling** — §55 (composting, greywater, biogas, material reuse, closed-loop systems)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~10 | ~35 | USDA PLANTS (Tier 2), PFAF perennials (Tier 2), Companion planting guilds (Tier 1), SSURGO soil (Tier 3 optional) |

---

### Phase 14: Disaster-Specific Modules ✅ COMPLETE (v7.20.0)
**Theme:** Specialized preparedness for each disaster type. One size does not fit all.
**Effort:** L (4-6 sessions)
**features.md refs:** §39 (all 10 disaster types), §40 (4 environment types), §15.6 (Alternative Energy), §15.7 (Construction)

#### Deliverables
1. **10 disaster modules** — §39.1-39.10 (earthquake, hurricane, tornado, wildfire, flood, pandemic, EMP/solar, economic collapse, volcanic ashfall, drought)
2. **4 environment modules** — §40.1-40.4 (winter/arctic, desert/arid, urban, maritime/coastal)
3. **Alternative energy** — §15.6 (wood inventory, heating calculator, biogas, micro-hydro, wind, charcoal)
4. **Construction & fortification** — §15.7 (project tracker, materials inventory, fortification assessment, safe room reference)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~6 (disaster_plans, disaster_checklists, energy_systems, construction_projects, building_materials, fortifications) | ~30 | Smithsonian GVP eruptions (Tier 1), US Drought Monitor (Tier 2), FEMA NRI (Phase 1) |

---

### Phase 15: Daily Living & Quality of Life ✅ COMPLETE (v7.21.0)
**Theme:** Actually surviving day-to-day under grid-down conditions.
**Effort:** M (2-3 sessions)
**features.md refs:** §30 (Quality of Life), §15.2 (Sanitation), §15.3 (Clothing), §15.8 (Psychological), §59 (Sleep & Performance)

#### Deliverables
1. **Grid-down cooking & meals** — §30.1 (recipe database, meal planner from inventory, calorie tracking, sprouting)
2. **Hygiene & health routines** — §30.2 (water ration allocation, dental care, feminine hygiene calc, foot care)
3. **Shelter & comfort** — §30.3 (heating zone planner, cooling without power, sleeping bag inventory, pest control)
4. **Daily routine builder** — §30.4 (schedule templates, chore rotation, work/rest cycles, meal coordination)
5. **Sanitation** — §15.2 (supply inventory, waste management, greywater, disease prevention, vector control)
6. **Clothing** — §15.3 (per-person inventory, cold weather assessment, protective gear, sewing supplies)
7. **Psychological preparedness** — §15.8 (morale tracker, PFA reference, recreational supplies, sleep schedule, morale events)
8. **Sleep & human performance** — §59 (watch optimization, sleep debt, performance degradation, work-rest tables, fatigue risk)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~8 (daily_schedules, chore_assignments, clothing_inventory, sanitation_supplies, morale_logs, sleep_logs, performance_checks, grid_down_recipes) | ~30 | Military work-rest tables (Tier 1) |

---

### Phase 16: Interoperability & Data Exchange ✅ COMPLETE (v7.22.0)
**Theme:** Import/export everything. No data lock-in. Plugin foundation.
**Effort:** L (4-6 sessions)
**features.md refs:** §18 (Interoperability), §7 (Print & Export), §34.2 (Data Entry)

#### Deliverables
1. **Import formats** — §18.1 (CHIRP CSV, GPX tracks, GeoJSON, KML/KMZ, vCard, ICS/iCalendar, FHIR medical, spreadsheet templates)
2. **Export formats** — §18.2 (CHIRP CSV, GeoJSON, KML/KMZ, ICS, vCard, FHIR, Excel/XLSX, Markdown, encrypted ZIP, ADIF ham log)
3. **Print expansion** — §7.1 (FEMA household plan, vehicle card, medication card, property map, skills gap report, seasonal calendar)
4. **API & integration** — §18.3 (REST API documentation via OpenAPI/Swagger, webhook enhancement, MQTT publish, CalDAV)
5. **Plugin system foundation** — §18.3 (extension registry, hook points for route/table/UI registration — architectural foundation)
6. **Data entry improvements** — §34.2 (batch entry mode, template-based entry, autocomplete, paste from spreadsheet)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~2 (plugins, plugin_config) | ~30 | None |

---

### Phase 17: Hunting, Foraging & Wild Food ✅ COMPLETE (v7.23.0)
**Effort:** M (2-3 sessions) | **features.md refs:** §23 (all), §38 (Trade Skills)
- Hunting management, fishing, foraging & wild edibles, trapping & snaring
- Trade skills tracker (blacksmithing, woodworking, leatherwork, sewing, soap, candles)
- Preservation arts (tanning, distillation, vinegar, cheese, herbal tinctures)

| New Tables | New Routes | Data Packs |
|---|---|---|
| ~10 | ~30 | USDA PLANTS (Tier 2), iNaturalist/GBIF (Tier 2), Mushroom Observer (Tier 2), FishBase (Tier 2) |

---

### Phase 18: Hardware, Sensors & Mesh ✅ COMPLETE (v7.24.0)
**Effort:** XL (7+ sessions — hardware-dependent) | **features.md refs:** §13 (Sensors), §4.3 (Specialized Services), §24 (Networking)
- MQTT broker for IoT sensors (soil moisture, water level, temp/humidity, air quality, Geiger counter)
- Full Meshtastic serial integration
- Weather station direct integration (Davis, Ecowitt, Ambient Weather)
- GPS device import, satellite communicator integration
- Wearable health data import
- Network management tools (device inventory, topology, mesh coverage map)
- Home Assistant / Node-RED integration stubs

| New Tables | New Routes | Data Packs |
|---|---|---|
| ~8 | ~30 | None (hardware-dependent) |

---

### Phase 19: Platform, Deployment & Security ✅ COMPLETE (v7.25.0)
**Effort:** XL (7+ sessions) | **features.md refs:** §9 (Platform), §10 (Security), §32 (Deployment), §33 (Performance)
- SQLCipher full database encryption
- Multi-user authentication with roles
- TLS/HTTPS for LAN access
- Session timeout, PIN/password protection
- Docker image + Compose stack
- Raspberry Pi SD card image
- Linux packages (AppImage, .deb, .rpm, Flatpak)
- Signed macOS DMG
- ARM64 builds
- Database sharding, FTS5 full-text search, connection pooling
- Startup optimization, memory profiling

| New Tables | New Routes | Data Packs |
|---|---|---|
| ~3 (users, sessions, permissions) | ~15 | None |

---

### Phase 20: Specialized Modules & Community ✅ COMPLETE (v7.26.0)
**Effort:** XL (7+ sessions) | **features.md refs:** §36, §37, §41, §42, §43, §49, §50, §29, §35, §5 remaining, §21, §26, §27

Grab-bag of remaining modules, built based on community demand:
- Cache & hidden supply management (§36)
- Pets & companion animals (§37)
- Children, youth & family programs (§41)
- End-of-life & body management (§42)
- Shopping, procurement & supply chain (§43)
- Intelligence collection & PIR management (§49)
- 3D printing & digital fabrication (§50)
- Signal intelligence & OSINT (§29)
- Community content packs & sharing (§35)
- Federation v3: DTN, sneakernet sync, BT/WiFi-Direct (§5 expansion)
- Gamification & badges (§21)
- Analytics deep dive (§26)
- Seasonal & calendar features (§27)
- Accessibility & inclusivity (§20)
- Legal & administrative vault (§15.9)
- Drone manager (§1.6)
- Fitness tracker (§1.10)

| New Tables | New Routes | Data Packs |
|---|---|---|
| ~25+ | ~80+ | Various Tier 2/3 as needed |

---
