# Project N.O.M.A.D. — Implementation Roadmap v8

> **Baseline:** v7.7.0 (615 commits, 97 source files, 775 tests, 600+ API routes, 95+ DB tables)
> **Source:** `features.md` (63 sections, 1,805 features) + `datasources.md` (22 sections, 53 data packs)
> **Generated:** 2026-04-13
> **Structure:** 4 tiers, 20 phases, ~1,805 features. Each phase is independently shippable.

---

## How to Read This Document

- **Phases** are ordered by dependency and impact. Within a tier, phases can be built in any order unless noted.
- **Effort** is T-shirt sized: S (1 session), M (2-3 sessions), L (4-6 sessions), XL (7+ sessions).
- **Data Packs** lists datasets from `datasources.md` that must be bundled or available before the phase ships.
- **New Tables** estimates new SQLite tables required (drives `db.py` migration work).
- **New Routes** estimates new Flask API endpoints.
- **features.md refs** maps to the exact sections in features.md covered by each phase.

---

## Dependency Graph

```
Tier 1: Critical Path (Phases 1-5)
======================================

  Phase 1: Data Foundation & Localization
      |
      +---> Phase 2: Nutritional Intelligence & Water Management
      |         |
      |         +---> Phase 4: Advanced Inventory & Consumption Modeling
      |
      +---> Phase 3: Core New Modules (Vehicles, BOBs, Financial, Food Preservation)
      |         |
      |         +---> Phase 5: Evacuation, Movement & Route Planning
      |
      (independent)

Tier 2: High Value (Phases 6-10)
======================================

  Phase 6: Communications & Field Ops ----+
  Phase 7: AI Phase 2 & Automation -------+---> Phase 10: Training & Knowledge Systems
  Phase 8: Land Assessment & Property     |
  Phase 9: Medical Phase 2 ---------------+

Tier 3: Strategic (Phases 11-16)
======================================

  Phase 11: Group Operations & Governance (depends on Phase 1 localization)
  Phase 12: Security, OPSEC & Night Ops
  Phase 13: Agriculture & Permaculture (depends on Phase 1 data)
  Phase 14: Disaster-Specific Modules (depends on Phase 1 localization)
  Phase 15: Daily Living & Quality of Life (depends on Phase 4 consumption)
  Phase 16: Interoperability & Data Exchange

Tier 4: Expansion (Phases 17-20)
======================================

  Phase 17: Hunting, Foraging & Wild Food
  Phase 18: Hardware, Sensors & Mesh
  Phase 19: Platform, Deployment & Security
  Phase 20: Specialized Modules & Community
```

---

## Tier 1: Critical Path

These phases address the biggest gaps between NOMAD and what users most need. Build these first.

---

### Phase 1: Data Foundation & Localization
**Theme:** Transform NOMAD from generic to personalized. Bundle offline datasets that power all future phases.
**Effort:** L (4-6 sessions)
**features.md refs:** §54 (Localization & Regional Profiles)
**datasources.md refs:** §1 (USDA FoodData), §8 (FEMA NRI), §17 (NRI, Census, Drought Monitor)

#### Deliverables
1. **Data Pack manager UI** — Settings tab section for downloading/managing offline datasets
   - Tier 1 auto-bundled on first run (~75 MB compressed)
   - Tier 2/3 available as downloadable expansion packs
   - Version tracking, update checking, size display
2. **Regional profile system** — Setup wizard + stored profile
   - Country → state → county → ZIP input
   - Auto-resolve USDA hardiness zone, FEMA risk scores, nearest NWS station
   - Store as `regional_profile` table (location, zone, threat_scores JSON, frost_dates, nearest_stations)
3. **FEMA NRI integration** — County-level hazard scoring
   - Bundle NRI dataset (~20 MB compressed)
   - `/api/region/threats` — ranked hazards for user's county
   - `/api/region/profile` — full regional profile with all auto-configured data
4. **USDA FoodData SR Legacy integration** — Nutritional database
   - Bundle SR Legacy (~25 MB compressed) — 7,793 foods, 150+ nutrients each
   - `/api/nutrition/search` — search foods by name
   - `/api/nutrition/lookup/<fdc_id>` — full nutrient profile
   - Schema: `nutrition_foods`, `nutrition_nutrients` tables
5. **Regional content adaptation** — Threat-weighted readiness scoring
   - Readiness score weights adjusted by regional threats (earthquake prep worth more in CA)
   - Regional checklists auto-surfaced (hurricane prep for coastal counties)
   - Regional weather station auto-configured

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~5 (regional_profile, nutrition_foods, nutrition_nutrients, data_packs, data_pack_versions) | ~15 | FEMA NRI, USDA SR Legacy, NOAA frost dates, NOAA weather stations |

#### Implementation Notes
- Data packs stored in `{data_dir}/packs/` with manifest JSON
- First-run wizard: location → auto-configure → optional Tier 2 downloads
- All data pack loading must be lazy (don't block startup)
- Regional profile feeds into every module that shows recommendations

---

### Phase 2: Nutritional Intelligence & Water Management
**Theme:** Answer the #1 and #2 community questions: "How many days can my family eat?" and "How much water do we have?"
**Effort:** L (4-6 sessions)
**Depends on:** Phase 1 (USDA nutritional data, regional profile)
**features.md refs:** §2.1 (Inventory — nutrition), §51.1 (Micronutrient gap analysis), §51.2 (Consumption modeling), §1.4 (Water Management)

#### Deliverables
1. **Inventory nutritional tracking** — Per-item calorie and macro data
   - Link inventory items to USDA FoodData entries (manual search + auto-suggest)
   - New columns on `inventory`: `fdc_id`, `calories_per_serving`, `protein_g`, `fat_g`, `carbs_g`, `servings_per_item`
   - `/api/inventory/nutrition-summary` — total calories, protein, fat, carbs across all food inventory
   - "Person-days of food" calculator: total_calories / (household_size × daily_calorie_need)
2. **Micronutrient gap analysis** — Vitamin and mineral tracking
   - Dashboard showing days of adequate Vitamin C, D, A, iron, calcium, zinc
   - Deficiency risk timeline ("Vitamin C runs out in 14 days at current stores")
   - Traffic-light indicators: green (30+ days), amber (7-30), red (<7)
3. **Macro ratio dashboard** — Protein vs carbs vs fat balance
   - Pie chart of total food stores by macronutrient
   - Dietary restriction flagging per person (allergies, gluten, dairy, nuts)
   - Recommended daily intake comparison per person
4. **Per-person consumption profiles** — Realistic burn rates
   - Profiles: adult male active, adult female sedentary, child (by age), infant, elderly
   - Activity-adjusted caloric needs (resting: 1800, moderate: 2400, heavy labor: 3500+)
   - "What if" group size changes ("if 2 extra people arrive, supplies last X days instead of Y")
5. **Water management system** — Dedicated water tracking module
   - `water_storage` table (container, capacity_gal, fill_date, treatment_method, location)
   - `water_filters` table (type, capacity_gal, gallons_used, replacement_date)
   - `water_sources` table (name, type, lat, lng, year_round, flow_rate, treatment_needed) — linked to waypoints
   - Daily water budget calculator (drinking, cooking, hygiene, medical, livestock, garden)
   - Purification method reference (boiling, bleach, UV, filtration — dosage charts)
   - Filter life tracking with replacement alerts
   - Water sub-tab in Preparedness

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~5 (water_storage, water_filters, water_sources, consumption_profiles, nutrition_link) | ~20 | USDA SR Legacy (from Phase 1) |

#### Implementation Notes
- Nutritional linking is optional per item — don't force it on existing inventory
- Water module is a new Preparedness sub-tab under "Supplies" category
- Person-days calculation must account for activity level if consumption profiles exist
- Integrate water sources with existing Maps module (show on map as waypoint category)

---

### Phase 3: Core New Modules
**Theme:** Four high-impact new modules that every prepper needs. Independent of nutritional data.
**Effort:** XL (7+ sessions)
**Depends on:** None (can run parallel with Phase 2)
**features.md refs:** §1.2 (Vehicle Manager), §1.3 (Bug-Out Bag Manager), §1.1 (Financial Preparedness), §1.7 (Food Preservation)

#### Deliverables
1. **Vehicle & bug-out vehicle manager** — §1.2
   - `vehicles` table (year, make, model, VIN, fuel_type, tank_gal, mpg, location, status)
   - `vehicle_maintenance` table (vehicle_id, service_type, date, mileage, next_due, notes)
   - `vehicle_kits` table (vehicle_id, item inventory link — emergency kit per vehicle)
   - Fuel range calculator, maintenance alerts, spare parts sub-inventory
   - Mileage/trip log
   - Preparedness sub-tab: "Vehicles" under Supplies category
2. **Bug-out bag loadout manager** — §1.3
   - `loadouts` table (name, person_id, type: 72hr/GHB/INCH, last_inspected)
   - `loadout_items` table (loadout_id, inventory_id or custom name, weight_oz, category, packed)
   - Total weight calculation with target limits
   - Kit completeness percentage
   - Seasonal gear swap reminders
   - Printable packing checklist per bag
   - Clone/template bags for family members
3. **Financial preparedness tracker** — §1.1
   - `financial_reserves` table (type: cash/metals/crypto/barter, denomination, amount, location, value_estimate)
   - `financial_documents` table (type: insurance/deed/title, provider, policy_number, coverage, renewal_date, vault_ref)
   - Cash reserves log with denominations and locations
   - Precious metals inventory (weight, purity, spot value estimate)
   - Barter goods inventory (separate from regular supplies)
   - Emergency fund progress tracker with goals
   - Cost-per-day-of-preparedness calculator
4. **Food preservation batch tracker** — §1.7
   - `preservation_batches` table (method: canning/freeze-dry/dehydrate/smoke/ferment, contents, date, quantity, jar_size, status)
   - `canning_supplies` table (jars, lids, rings, pectin, salt, vinegar — with counts)
   - Canning log with pressure/water bath method tracking
   - Fermentation tracker (start date, check dates, ready date)
   - Root cellar inventory with temp/humidity log
   - Printable pantry labels (item, date, batch number)

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~12 (vehicles, vehicle_maintenance, vehicle_kits, loadouts, loadout_items, financial_reserves, financial_documents, preservation_batches, canning_supplies, +3 supporting) | ~50 | EPA fuel economy data (Tier 1, ~5 MB) |

#### Implementation Notes
- Vehicle manager integrates with existing fuel/equipment modules
- Bug-out bag links to existing inventory items where possible (shared data, separate "packed in bag" view)
- Financial tracker stores sensitive data — encrypt at-rest in vault
- Food preservation extends existing `preservation_log` table or replaces it with richer schema
- Each module gets its own Preparedness sub-tab

---

### Phase 4: Advanced Inventory & Consumption Modeling
**Theme:** Transform inventory from a tracking system to a predictive intelligence system.
**Effort:** M (2-3 sessions)
**Depends on:** Phase 2 (nutritional data), Phase 3 (loadouts, vehicles)
**features.md refs:** §16.1 (Container & Kit Management), §51.2 (Advanced Consumption), §51.3 (Physical Inventory), §2.1 remaining items

#### Deliverables
1. **Container/kit management** — §16.1
   - `containers` table (name, type, location, weight_lb, dimensions, parent_container_id — for nesting)
   - Assign inventory items to containers ("which items are in which bin")
   - Kit builder: define kit templates, auto-populate from inventory, show completeness %
   - "Grab bag" quick-filter for 5-minute bug-out items
   - Container location mapping (garage shelf 3, basement bin 2, vehicle trunk)
2. **Consumption rate learning** — §51.2
   - Track actual consumption over time (log when items are used/consumed)
   - Build personalized burn rate models (you actually use 2 gal water/day, not the default 1)
   - Worst-case / best-case duration brackets
   - Auto-reorder point calculation (min stock = burn rate × lead time)
3. **Physical inventory features** — §51.3
   - Weight tracking per item (total weight for vehicle loading and carry capacity)
   - Volume/space tracking (cubic feet per category — storage planning)
   - Inventory audit mode (walk through items, confirm counts, flag discrepancies)
   - Standardization advisor ("you use 3 battery types — standardize to reduce complexity")
   - Alternative/substitute item mapping
4. **Meal planning from inventory** — §2.1
   - Link recipes to available food stocks
   - "Meals remaining" calculator
   - "Due Score" recipe prioritization (Grocy-inspired — cook what expires soonest)
   - Auto-suggest meals from expiring inventory

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~4 (containers, container_items, consumption_log, recipes) | ~20 | None new |

---

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

## Tier 2: High Value

These phases deliver significant capability. Can be built in any order within the tier.

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

### Phase 7: AI Phase 2 & Automation
**Theme:** Make NOMAD proactive. AI that understands your data. Rules that act without asking.
**Effort:** XL (7+ sessions)
**features.md refs:** §3.1 (AI Capabilities), §53 (Deep AI Phase 2), §17 (Automation & Workflows), §2.7 (Tasks expansion)

#### Deliverables
1. **RAG over all NOMAD data** — §3.1, §53.2
   - AI answers questions using actual inventory, contacts, plans, medical data
   - "How many days of water do we have?" → AI queries water storage, calculates per-person
   - "What are we short on?" → AI analyzes all modules, identifies gaps
   - "Plan meals for 7 days using only what we have" → AI creates plan from inventory
   - Context injection from all major tables (inventory, medical, contacts, water, vehicles, loadouts)
2. **AI-powered recommendations** — §3.1
   - "Based on your household size and regional threats, you're short on X"
   - Readiness improvement advisor ("biggest bang for your buck" purchases)
   - Seasonal preparation advisor ("winter is coming: check heating, cold gear, pipes")
3. **Custom alert rules engine** — §17.1
   - `alert_rules` table (name, conditions JSON, actions JSON, enabled, last_triggered)
   - IF/THEN rule builder (IF inventory X < Y THEN alert)
   - Compound conditions (IF pressure drops AND threat level elevated THEN escalate)
   - Alert actions: push notification, SSE, sound, log incident, generate checklist
   - Acknowledgment tracking and escalation
   - Visual rule builder in Settings
4. **Automated reports** — §17.2
   - Scheduled daily operations brief
   - Weekly readiness summary (week-over-week comparison)
   - Monthly inventory audit report
   - Auto-distribute to federation peers
5. **Calendar/timeline unified view** — §2.7
   - All dates across all modules: expirations, maintenance, tasks, drills, certifications
   - Calendar widget on Home
   - Task dependency chains
   - Gantt chart view for project-style tasks
   - Morning briefing auto-generated from due/overdue tasks

| New Tables | New Routes | Data Packs Required |
|---|---|---|
| ~4 (alert_rules, alert_acknowledgments, scheduled_reports, calendar_events) | ~25 | None |

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

## Tier 3: Strategic

These phases build the moat. They're what makes NOMAD truly unique.

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

## Tier 4: Expansion

Community-driven priorities. Build based on user demand.

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

## Implementation Summary

| Tier | Phases | Est. Features | Theme |
|---|---|---|---|
| **1: Critical Path** | 1-5 | ~350 | Data foundation + core modules + evacuation |
| **2: High Value** | 6-10 | ~400 | Comms + AI + land + medical + training |
| **3: Strategic** | 11-16 | ~500 | Groups + security + agriculture + disasters + daily life + interop |
| **4: Expansion** | 17-20 | ~555 | Hunting + hardware + platform + specialized |
| **Total** | 20 phases | ~1,805 | Complete features.md coverage |

### Effort Totals

| Effort | Count | Estimated Sessions |
|---|---|---|
| S (1 session) | 0 | 0 |
| M (2-3 sessions) | 5 phases | 10-15 |
| L (4-6 sessions) | 10 phases | 40-60 |
| XL (7+ sessions) | 5 phases | 35+ |
| **Total** | **20 phases** | **~85-110 sessions** |

### Data Pack Bundling Schedule

| Phase | New Tier 1 Bundles | New Tier 2/3 Available |
|---|---|---|
| 1 | FEMA NRI, USDA SR Legacy, NOAA frost/stations | Census, Drought Monitor |
| 3 | EPA fuel economy | — |
| 5 | Pack animal reference | USGS transportation |
| 6 | — | RepeaterBook |
| 9 | DDInter, NIOSH | — |
| 10 | FEMA CERT | — |
| 11 | Robert's Rules | — |
| 12 | Military work-rest, Venomous species | — |
| 13 | Companion guilds | USDA PLANTS, PFAF, SSURGO |
| 14 | Smithsonian GVP | Drought Monitor |
| 15 | (Military work-rest reuse) | — |
| 17 | — | iNaturalist, Mushroom Observer, FishBase |

### New Database Tables per Phase

| Phase | Est. New Tables | Running Total |
|---|---|---|
| Baseline | 95+ | 95 |
| Phase 1 | 5 | 100 |
| Phase 2 | 5 | 105 |
| Phase 3 | 12 | 117 |
| Phase 4 | 4 | 121 |
| Phase 5 | 6 | 127 |
| Phase 6 | 6 | 133 |
| Phase 7 | 4 | 137 |
| Phase 8 | 4 | 141 |
| Phase 9 | 6 | 147 |
| Phase 10 | 8 | 155 |
| Phase 11 | 12 | 167 |
| Phase 12 | 10 | 177 |
| Phase 13 | 10 | 187 |
| Phase 14 | 6 | 193 |
| Phase 15 | 8 | 201 |
| Phase 16 | 2 | 203 |
| Phase 17 | 10 | 213 |
| Phase 18 | 8 | 221 |
| Phase 19 | 3 | 224 |
| Phase 20 | 25+ | 250+ |

---

## Build Principles

1. **One phase per major session block.** Don't mix phases in a single session — complete and commit one before starting the next.
2. **Ship incrementally.** Every phase produces a working, testable increment. Bump version on each phase completion.
3. **Data packs before features.** If a phase requires bundled data, build the data integration first, then the UI.
4. **New Preparedness sub-tabs are cheap.** The existing 5-category, 25-sub-tab architecture can absorb ~10 more sub-tabs without UX degradation. Beyond that, consider a sixth category.
5. **Blueprints, not monolith.** Each new major module should be a Flask blueprint in `web/blueprints/`. Don't add routes to `app.py`.
6. **Test critical paths.** Add pytest tests for every new CRUD API. Target: 20-30 new tests per phase.
7. **Update CLAUDE.md after every phase.** Keep the project brief current — version, table count, route count, feature summary.
8. **features.md checkboxes.** Mark items `[x]` as they're completed to track progress against the master feature list.

---

## Recommended Starting Order

For maximum impact with minimum dependency complexity:

```
Session 1-2:  Phase 1 — Data Foundation (FEMA NRI + USDA nutrition + regional profiles)
Session 3-4:  Phase 2 — Nutritional Intelligence & Water (unlocks "days of food/water" answer)
Session 5-7:  Phase 3 — Core New Modules (vehicles, BOBs, financial, preservation)
Session 8:    Phase 4 — Advanced Inventory (containers, consumption modeling)
Session 9-10: Phase 5 — Evacuation & Movement (connects everything into action plans)
```

After Tier 1, shift to user-demand-driven priorities within Tier 2-3.

---

## Research & Strategic Gaps (Auto-Generated Analysis)

> **Generated:** 2026-04-14 | **Baseline:** v7.26.0 (all 20 phases complete)
> **Method:** Static analysis of 76,094 lines across 59 blueprints, 264 tables, 1,628 route decorators, 66 test files.
> **Scope:** Architecture, schema integrity, security, reliability, developer experience.

---

### High Priority

**H1. Duplicate `sensor_readings` Table — Schema Conflict (db.py:435 vs db.py:4641)**
- Two CREATE TABLE IF NOT EXISTS `sensor_readings` with incompatible schemas. The first (Phase 1 core) uses `device_id` + `reading_type`; the second (Phase 18 hardware) uses `sensor_id` + `raw_value` + `quality` + `timestamp`. Because of IF NOT EXISTS, the second definition is silently ignored — hardware_sensors.py queries will fail at runtime when referencing columns that don't exist.
- **Fix:** Rename the Phase 18 table to `iot_sensor_readings` and update hardware_sensors.py references. The legacy `sensor_readings` table serves power.py and should remain unchanged.
- **Affected:** hardware_sensors.py (lines 153, 194, 216, 245, 269), db.py line 4641

**H2. Input Validation Coverage — 9 of 1,628 Routes**
- A `@validate_json` decorator exists in web/validation.py but is only applied to 9 routes. The remaining 1,600+ routes accept unvalidated JSON payloads. While parameterized SQL prevents injection, missing validation means:
  - Oversized payloads can bloat the database (no max_length enforcement)
  - Type mismatches cause 500 errors instead of 400s
  - Required fields silently default to empty strings
- **Fix:** Prioritize validation on mutating (POST/PUT) routes in inventory, medical, contacts, and financial blueprints first — these handle the most sensitive data. A phased rollout across all blueprints is realistic at ~5 blueprints per session.

**H3. Mutating Rate Limit Not Enforced (web/app.py:144-149)**
- `Config.RATELIMIT_MUTATING` (60/minute) is configured but the enforcement function body is `pass`. POST/PUT/DELETE requests are not actually rate-limited despite flask-limiter being active for GET requests.
- **Fix:** Apply `limiter.limit(Config.RATELIMIT_MUTATING)` to the before_request hook for non-safe HTTP methods, or decorate mutating routes explicitly.

**H4. No Auth Middleware Wired to Routes**
- Phase 19 built `app_users`, `app_sessions`, and role-based access (admin/user/viewer/guest) in platform_security.py, but zero routes across the 58 other blueprints use `@login_required` or `@auth_required` decorators. The auth system exists but is not enforced anywhere.
- **Fix:** Create a `require_auth` decorator in web/utils.py. Apply it globally via a before_request hook that checks session tokens, with an allowlist for public routes (health check, login, SSE).

**H5. Path Traversal Checks Fragile on Windows (web/app.py:1114, 1153)**
- NukeMap and VIPTrack static file routes use `os.path.normcase()` + string prefix matching for path containment. On Windows, mixed-case and mixed-separator paths can bypass this check.
- **Fix:** Replace with `os.path.commonpath([full_path, base_dir]) == os.path.normcase(base_dir)` which is normalization-safe on all platforms.

---

### Medium Priority

**M1. 19 Blueprints Return Unbounded Query Results**
- These blueprints have no LIMIT clause on their primary list endpoints: agriculture, consumption, daily_living, disaster_modules, emergency, evac_drills, family, financial, group_ops, hunting_foraging, land_assessment, meal_planning, movement_ops, readiness_goals, training_knowledge, and 4 others.
- A table with thousands of rows will return the entire result set in a single JSON response. On constrained hardware (Raspberry Pi), this causes memory spikes and UI freezes.
- **Fix:** Add server-side pagination (LIMIT/OFFSET with sensible defaults of 50-100 rows) to all list endpoints. The pattern already exists in inventory.py, contacts.py, and notes.py — replicate it.

**M2. 11 Blueprints Have No Activity Logging**
- These blueprints never call `log_activity()`: brief, checklists, contacts, kit_builder, kiwix, print_routes, supplies, timeline, vehicles, weather, and __init__. This creates blind spots in the activity log — a user modifying contacts, vehicles, or weather data leaves no audit trail.
- **Fix:** Add `log_activity()` calls to create/update/delete operations in each affected blueprint.

**M3. SSE Client Limit Race Condition (web/app.py:1419-1423)**
- The check `len(_sse_clients) >= MAX_SSE_CLIENTS` and the subsequent queue creation + registration happen outside a single lock acquisition. A concurrent thread can exceed the limit between the check and the registration.
- **Fix:** Hold `_sse_lock` from the limit check through queue creation and registration in one atomic block.

**M4. `access_log` vs `access_logs` Table Name Collision (db.py:862, 4827)**
- Two tables with near-identical names serve different purposes: `access_log` (physical entry/exit, used by security.py) and `access_logs` (API access audit, used by platform_security.py). This is confusing and error-prone.
- **Fix:** Rename `access_logs` to `api_access_log` or `platform_access_log` to disambiguate. Update platform_security.py SQL references.

**M5. No FTS5 Full-Text Search**
- Phase 19 roadmap deliverables included "FTS5 full-text search" but no FTS5 virtual tables exist in db.py. Keyword search across notes, inventory, contacts, and knowledge base still uses LIKE queries, which are O(n) table scans.
- **Fix:** Create FTS5 virtual tables for notes, inventory, contacts, and documents. Add triggers to keep them in sync with the base tables. This is a significant performance win for deployments with 10,000+ records.

**M6. No Connection Pooling**
- Phase 19 deliverables included "connection pooling" but each request creates a new SQLite connection via `db_session()`. SQLite's file-based locking makes this acceptable at low concurrency, but under LAN multi-user access (Phase 19's multi-user auth), contention will cause "database is locked" errors.
- **Fix:** Implement a thread-local connection pool with a configurable max size (default 5). Reuse connections within the same thread/request lifecycle.

**M7. Config Crashes on Invalid Environment Variables (config.py:42-78)**
- All `int(os.environ.get(...))` calls will raise `ValueError` if the env var is set to a non-numeric string. The app crashes at import time before any error handling can catch it.
- **Fix:** Wrap each conversion in a try-except with a fallback to the default value, or use a validated config loader.

**M8. DB Migration System Underpowered — 3 Files for 264 Tables**
- The migration system (`db_migrations/`) has only 3 migration files despite 264 tables and 27 table-creation functions. Most schema changes are handled by `_apply_column_migrations()` which uses ALTER TABLE ADD COLUMN with try-except (silently ignoring if column exists). This works but:
  - No rollback capability
  - No version tracking beyond "column exists or not"
  - Schema changes are invisible to deployment tooling
- **Fix:** For future schema changes, write proper numbered migration files. The existing approach is acceptable for the current state but should not be extended further.

**M9. 326 Bare `except Exception` Catches**
- Across all blueprints, 326 instances of `except Exception` catch and suppress errors. While each returns a JSON error response (not silently swallowing), overly broad catches mask programming errors (KeyError, TypeError, AttributeError) that should crash loudly during development.
- **Fix:** Narrow catches to specific expected exceptions (sqlite3.Error, ValueError, KeyError) in hot paths. Keep broad catches only at the outermost route handler level.

---

### Low Priority

**L1. Unused CSS Variables Across 7 Tab Partials**
- 25+ CSS custom properties (e.g., `--dm-blue`, `--ag-brown`, `--hf-purple`) are defined but never referenced in their respective tab partials. No functional impact, but adds dead weight to the CSS cascade.
- **Fix:** Remove unused variables or implement them in styling rules during the next UI pass.

**L2. 5 Missing `name` Attributes on Hidden Inputs (_tab_daily_living.html)**
- Hidden inputs at lines 99, 145, 205, 265, 485 lack `name` attributes. These are state-management inputs (edit IDs) not submitted in forms, but violate the `test_partial_controls_have_names` test contract.
- **Fix:** Add `name="dl-sched-edit-id"` (etc.) to each hidden input matching the existing ID pattern.

**L3. `os._exit(0)` Bypasses Python Cleanup (nomad.py:149)**
- On shutdown, `os._exit(0)` is called instead of `sys.exit(0)`. This skips Python's normal cleanup (context managers, finalizers, buffered writes). The app manually flushes log handlers before this call, but any in-flight database writes could be lost.
- **Fix:** Replace with `sys.exit(0)` which allows normal cleanup, or ensure all DB connections are explicitly closed before the call.

**L4. Double Import of Preparedness Module (web/app.py:712, 1269)**
- The preparedness module is imported twice: once for `start_alert_engine` (line 712) and once for `preparedness_bp` (line 1269). No functional bug, but wasteful and confusing.
- **Fix:** Consolidate to a single import at the blueprint registration site.

**L5. Internationalization Stub — No Active Translations**
- `web/translations.py` (444 lines) exists but contains no `translate()` or `_t()` functions. The i18n system is scaffolded but not wired to any UI strings.
- **Note:** This is architectural debt, not a bug. Wire it only when localization becomes a user requirement.

**L6. PID Recycling in Service Manager (services/manager.py:277-295)**
- `is_running()` checks if a PID is alive but does not verify the process name. If a service crashes and the OS recycles the PID to a different process, the health monitor will incorrectly report the service as running.
- **Fix:** Store the process name or creation time alongside the PID and verify both in `is_running()`.

---

### Strategic Observations

**Architecture is sound.** The blueprint-per-domain pattern scales well. The 59-blueprint structure is maintainable because each module is self-contained with consistent CRUD patterns. No monolithic files need splitting.

**Biggest risk is data integrity.** The sensor_readings schema conflict (H1) is the only bug that will cause runtime failures. The auth gap (H4) is the biggest security exposure — the multi-user system exists but isn't enforced. Everything else is hardening, not triage.

**Performance ceiling is SQLite.** For single-user desktop use, SQLite with WAL is excellent. For the LAN multi-user scenario (Phase 19), the lack of connection pooling (M6) and FTS5 (M5) will become bottlenecks before anything else. If federation scales beyond 5 nodes, consider WAL2 or a SQLite connection proxy.

**Test coverage is strong.** 888 tests across 66 files with every blueprint covered is well above average for a project this size. The test infrastructure is a solid foundation for regression prevention during the fixes above.

**Next development phase should focus on hardening, not features.** All 1,805 features are built. A "v7.27.0 — Hardening & Polish" release addressing H1-H5 and M1-M6 would dramatically improve production readiness without adding complexity.
