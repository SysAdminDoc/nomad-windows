# Project N.O.M.A.D. — Roadmap

> **Baseline:** v7.43.0 (264 tables, 1,628+ routes, 59 blueprints, 1,357 tests)
> **Updated:** 2026-04-18
> **Structure:** 8 priority tiers, each phase independently shippable.
> **Effort:** S (1 session), M (2-3), L (4-6), XL (7+)

---

## What's Done

All 20 original feature phases (v7.6.0-v7.26.0) are complete. Post-feature work includes:
- Hardening passes v7.27.0-v7.28.0 (pagination, auth, validation, XSS, activity logging)
- FTS5 full-text search + connection pool (v7.29.0)
- Pagination completion across all 19 blueprints (v7.30.0)
- Activity logging completion (v7.31.0)
- Deep security audits, waves 1-2 (v7.32.0)
- AI RAG scope manager (v7.33.0)
- ICS-309 communications log generator (v7.34.0)
- Test coverage for 10 blueprints (v7.35.0-v7.36.0)
- Premium CSS polish marathon, 8 passes (v7.37.0-v7.43.0)

---

## Tier 1: Unfinished Core (from original roadmap)

These are the remaining phases from the original v8 roadmap that were never built. They fill the biggest functional gaps.

---

### 1.1 — Data Foundation & Localization --- COMPLETE (v7.44.0)
**Effort:** L | **Refs:** features.md SS54, datasources.md SS1/SS8/SS17

All 5 Tier 1 data pack importers built. Regional profile auto-populates from data packs on save. Nutrition blueprint (search, link, summary, micronutrient gaps) wired to USDA data. 3 new tables, 6 indexes, 3 lookup routes, 5 importers.

---

### 1.2 — Nutritional Intelligence & Water Management --- COMPLETE (pre-existing)
**Effort:** L | **Depends on:** 1.1

All backend APIs built: nutrition search/link/summary/gaps (8 routes), water storage/filters/sources/quality/budget/alerts (22 routes), consumption profiles with what-if calculator (8 routes). Person-days-of-food calculation in `/api/nutrition/summary`. Micronutrient gap analysis with 10 nutrients and traffic-light indicators. 16 tables, 54 routes total.

---

### 1.3 — Advanced Inventory & Consumption Modeling --- COMPLETE (pre-existing)
**Effort:** M | **Depends on:** 1.2

All backend APIs built: meal planning with recipes/burn-rates/due-score/meals-remaining (16 routes), inventory audit workflow, substitute mapping, standardization advisor. Container/kit management is the only remaining sub-item (deferred).

---

### 1.4 — AI Phase 2 & Automation --- MOSTLY COMPLETE
**Effort:** XL | **Refs:** features.md SS3.1/SS53/SS17/SS2.7

Already built: RAG scope manager (v7.33.0, data-driven, 25 tables), SITREP generation, AI action execution (two-phase commit), persistent AI memory, alert rules engine (25 condition types, 4 action types, cooldown logic), timeline unified view (17 event types, upcoming/overdue/summary routes). v7.44.0 adds scheduled reports (background SITREP generator, report history, schedule config).

Remaining:
- Visual alert rules builder (UI form, not raw API)
- Compound alert conditions (AND/OR logic)
- AI-powered recommendations engine (seasonal, readiness improvement)
- Auto-distribute reports to federation peers

---

## Tier 2: High Differentiation

Features that make NOMAD unique among survival/preparedness tools.

---

### 2.1 — Reticulum / LXMF Mesh Transport --- COMPLETE (v7.44.0)
**Effort:** L

RNS service manager with identity creation, LXMF messaging, announce/discovery. Mesh routes in comms blueprint wired to RNS transport with graceful fallback when not installed. Incoming messages auto-stored + SSE broadcast. Supports direct + propagation delivery modes.

### 2.2 — SDR Sidecar Service
**Effort:** M

Software-defined radio integration. Frequency scanning, signal identification, spectrum waterfall display.

### 2.3 — Shamir Secret Sharing Vault --- COMPLETE (v7.44.0)
Pure-Python GF(256) Shamir SSS. Split/reconstruct API with hash verification. Metadata in `shamir_shares` table.

### 2.4 — Warrant Canary + Dead-Man's Switch --- COMPLETE (v7.44.0)
Signed canary with configurable renewal interval. Dead-man's switch with 5 action types. Revoke for duress signaling.

### 2.5 — Node-RED-style Flow Editor for Alert Rules
**Effort:** L

Visual drag-and-drop flow editor for the alert rules engine. Replaces form-based rule creation with a canvas of connected condition/action nodes.

---

## Tier 3: Polish & Ecosystem

---

### 3.1 — Codeplug Builder with Per-Radio Zones --- COMPLETE (v7.44.0)
Full CRUD for radios, zones, channels. Import frequencies from freq_database. CHIRP CSV export with zone comments. 3 new tables + 3 indexes.

### 3.2 — Propagation-Aware HF Scheduler --- COMPLETE (v7.44.0)
24-hour HF propagation schedule with 10 bands, season/SFI factors, noise weighting. Band recommendation endpoint with net schedule cross-reference.

### 3.3 — Perceptual-Hash + C2PA on OSINT Images
**Effort:** M

Detect manipulated OSINT imagery. Content authenticity verification. Duplicate/near-duplicate detection across Situation Room feeds.

### 3.4 — Rainwater Catchment Calculator --- COMPLETE (v7.44.0)
Roof area + rainfall → annual yield, tank sizing (with standard sizes), first-flush diverter volume, monthly breakdown, material efficiency guide, self-sufficiency analysis.

### 3.5 — Plugin API Upgrade + Scaffold Generator
**Effort:** L

Expand the existing plugin foundation (v7.22.0) with a full SDK. CLI scaffold generator for new plugins. Hook points for routes, tables, UI panels.

### 3.6 — Mobile PWA Functional Offline Sync
**Effort:** L

Upgrade existing PWA + IndexedDB foundation to full offline-first sync. Conflict resolution. Background sync on reconnect.

### 3.7 — First-Run Regional Profile Wizard --- COMPLETE (v7.44.0)
Setup status endpoint with 4-step checklist (location, data packs, threats, household). Reports completion per step + data pack install detail. Auto-populate wired in Phase 1.1.

---

## Tier 4: Field Operations

SAR, overland, maritime, aviation specializations.

---

### 4.1 — ICS-205/205A Comms Plan Auto-Builder --- COMPLETE (v7.44.0)
Auto-generates ICS-205 from radio equipment + frequencies + net schedules + contacts. JSON + printable HTML output.

### 4.2 — SAR Probability Grid (Koester ISRID)
**Effort:** L — Not started. Requires ISRID statistical data + grid calculation engine.

### 4.3 — Clue Log + Containment Tracker --- COMPLETE (v7.44.0)
Georeferenced clue CRUD with GeoJSON export for map overlay. Containment sector tracking with POD, searcher count, search type. 2 new tables + 3 indexes.

### 4.4 — Overland Tire Pressure + Payload Advisor --- COMPLETE (v7.44.0)
8 terrain types with PSI adjustment factors. Front/rear split. Payload capacity tracking with overload warning.

### 4.5 — Terrain-Cost Range Rings
**Effort:** M — Not started. Requires DEM data + weighted Dijkstra.

### 4.6 — iOverlander + Community POI Ingest
**Effort:** M — Not started. Requires iOverlander API integration.

### 4.7 — Maritime: Tide + Current Predictor --- COMPLETE (v7.44.0)
Simplified lunar harmonic model with spring/neap detection. NOT for navigation — approximation only.

### 4.8 — Aviation: Density Altitude + Takeoff Distance --- COMPLETE (v7.44.0)
Pressure altitude, density altitude, Koch chart takeoff roll estimation. Weight factor, runway adequacy check, safety warnings.

### 4.9 — AIS/ADS-B Deconfliction View
**Effort:** M — Not started. Extends existing Situation Room feeds.

---

## Tier 5: Specialized Threats & Environment

CBRN, alpine, forensics, threat intel depth.

---

### 5.1 — Gaussian Plume Estimator (ALOHA-style) --- COMPLETE (v7.44.0)
Pasquill-Gifford dispersion model (6 stability classes). Downwind concentration at multiple distances. Hazard corridor GeoJSON output for map overlay.

### 5.2 — Household Epi Line List + Rt Tracker --- COMPLETE (v7.44.0)
Full CRUD line list with onset dates, symptoms, isolation tracking. Reproduction number (Rt) estimation via ratio method. Epidemic curve endpoint. New `epi_line_list` table.

### 5.3 — Avalanche ATES + Elevation-Banded Weather --- COMPLETE (v7.44.0)
ATES 3-class terrain rating from slope, traps, forest cover. Aspect risk assessment (N-face persistent slab). Elevation band classification (alpine/treeline/below). Essential gear list.

### 5.4 — Chain-of-Custody Evidence Ledger --- COMPLETE (v7.44.0)
SHA-256 integrity hash on collection. Custody transfer chain (append-only JSON). Hash verification endpoint. New `evidence_ledger` table.

### 5.5 — MISP-lite IOC Ingest + ATT&CK Mapping --- COMPLETE (v7.44.0)
IOC CRUD with 9 indicator types. ATT&CK tactic/technique/ID mapping. Heat-map matrix endpoint. TLP classification. New `ioc_tracker` table + 3 indexes.

---

## Tier 6: Homestead & Off-Grid Depth

Calculators and trackers for self-sufficient living.

---

### 6.1 — Greywater Branched-Drain Designer --- COMPLETE (v7.44.0)
### 6.2 — Humanure Thermophilic Tracker --- COMPLETE (v7.44.0)
### 6.3 — Wood BTU + Cord Ledger --- COMPLETE (v7.44.0)
### 6.4 — Passive Solar Sun-Path Plotter --- COMPLETE (v7.44.0)
### 6.5 — Battery Bank Cycle-Life Model --- COMPLETE (v7.44.0)
### 6.6 — Food Preservation Safety Math --- COMPLETE (v7.44.0)
### 6.7 — SSURGO Soil Profile Cache | M — Not started (requires SSURGO data import)
### 6.8 — Seed-Saving Isolation Distance Planner --- COMPLETE (v7.44.0)
### 6.9 — Beekeeping Varroa Calendar --- COMPLETE (v7.44.0)
### 6.10 — Livestock Drug + Withdrawal Timer --- COMPLETE (v7.44.0)
### 6.11 — Pedigree + Breeding Cycle Tracker | M — Not started

---

## Tier 7: Health, Community & Family

Medical depth, psychosocial support, family continuity.

---

### 7.1 — Pediatric Broselow-Equivalent Dose Engine --- COMPLETE (v7.44.0)
### 7.2 — Chronic Condition Grid-Down Playbooks --- COMPLETE (v7.44.0)
### 7.3 — Wilderness Medicine Decision Trees --- COMPLETE (v7.44.0)
### 7.4 — CISM Debrief Wizard | M — Not started
### 7.5 — Grief Protocol + Age-Banded Explainer Cards | S — Not started
### 7.6 — Sustained-Ops Sleep Hygiene Tracker | S — pre-existing (sleep_logs table + daily_living)
### 7.7 — NCMEC-style Child ID Packet Generator --- COMPLETE (v7.44.0)
### 7.8 — Reunification Cascade --- COMPLETE (v7.44.0)
### 7.9 — Homeschool Curriculum Tracker | M — Not started
### 7.10 — Skill-Transfer Ledger --- COMPLETE (v7.44.0)
### 7.11 — State-Specific Legal Doc Vault | M — pre-existing (vault_entries + legal docs in specialized_modules)

---

## Tier 8: Deep Domain Expansions

Cherry-pick as needed. Each is independently shippable.

---

**Weather & Earth Science:**
K1 Skew-T viewer, K2 Blitzortung lightning overlay, K3 NWS AFD parser, K4 FARSITE-lite wildfire spread

**Regional Packs:**
M1 Canada (ECCC + GeoGratis), M2 UK (Met Office + OS), M3 EU Copernicus, M4 Australia (BOM + Geoscience AU)

**Leadership & Doctrine:**
L1 OODA loop tracker, L2 AAR template engine, L3 Cynefin domain classifier

**Economy & Recovery:**
O1 Multi-party barter network ledger, O2 Hyperinflation reference, O3 Microgrid black-start SOP

**Transportation:**
P1 Pack-animal load calculator, P2 Canoe/kayak portage planner, P3 E-bike range calculator

**Comms Depth:**
R1 NTS radiogram handling, R2 ALE/VARA/Winlink, R3 FLDIGI macro library, AU1-AU6 shortwave/ARES/SKYWARN directories

**Developer & Platform:**
S1 Property-based + fuzz tests, S2 Contract + chaos + perf regression, S3 Mutation testing on life-safety calcs, S4 WCAG 2.2 AA audit, S10 Reproducible builds + SBOM, S12 nomad-cli companion, S14 Tauri alternative shell

**AI & Simulation:**
T1 Role-persona prompt library, T2 OPORD autofill, T5 Evacuation Monte Carlo, T7 Bayesian inventory burn forecaster, T8 Fault Tree Analysis

**Hardware Catalogs:**
U1-U7 Generator, heater, inverter, water pump, refrigeration, firearm maintenance, lifetime-tool catalogs

**Drill & Exercise:**
V1-V5 Scenario library, tabletop engine, functional exercises, federation drills, difficulty scaler

**Navigation (GPS-denied):**
AJ1-AJ9 Shadow-stick solver, celestial navigation, dead-reckoning, terrain association, offline star map

**Foraging & Game Processing:**
AI1-AI8 Offline plant-ID, foraging calendar, deadly-lookalike ledger, toxicity decision tree
AK1-AK10 Field-dressing SOPs, yield calculator, aging matrix, fish regs, aquaponics

**Outdoor Cooking:**
AL1-AL8 Fire-heat chart, Dutch-oven coal calculator, rocket-stove design, solar-oven curves, altitude canning

**Financial Preparedness:**
AT1-AT7 Portfolio stress-test, insurance audit, debt calculator, emergency-fund tiers, credit freeze calendar

**Environmental Monitoring:**
Z1-Z6 Indoor air station, dew-point/mold index, pollen feed, private-well baseline, heritage hazards, soil safety

**Medical Depth II:**
AA1-AA10 Wilderness-med progression, SOAP notes, improvised splint reference, PPE doffing, quarantine roster

**Water Quality:**
AC1-AC6 Potability test-strip workflow, well yield test, Legionella guard, cistern sizing

**Community Health:**
AD1-AD9 Pod health pulse, mutual-aid queue, sick-call roster, K6/PHQ-2 check-in, oral history capture

**OPSEC/Privacy:**
AE1-AE7 Cover-story templates, social-footprint audit, EXIF scrubber, gray-man checklist

**Biosecurity:**
AR1-AR7 Avian-flu SOP, farm biosecurity zones, carcass disposal matrix, vaccination calendar

**Digital Asset Sovereignty:**
AP1-AP7 BIP39 seed vault, hardware wallet ledger, multi-sig quorum, crypto estate plan, 2FA reset kit

**SOHO Business Continuity:**
AQ1-AQ6 Client notification cascade, revenue buffer calculator, COOP plan template

---

## Explicit Omissions

- Interactive substance-withdrawal tapers (medical risk too high)
- Home distillation of potable spirits (federal permit required)
- Paper-currency / scrip printing templates (counterfeiting-adjacent)
- Full-depth theology / scripture libraries
- Interactive flint-knapping / flintlock guides
- Offline Google Translate competitor

---

## Build Principles

1. **One phase per session block.** Complete and commit one before starting the next.
2. **Ship incrementally.** Every phase produces a working, testable increment. Bump version on completion.
3. **Data packs before features.** If a phase requires bundled data, build the data integration first.
4. **Blueprints, not monolith.** Each new module is a Flask blueprint in `web/blueprints/`.
5. **Test critical paths.** Add pytest tests for every new CRUD API. Target: 20-30 new tests per phase.
6. **Update docs after every phase.** Keep CLAUDE.md, README, CHANGELOG, and this roadmap in sync.
