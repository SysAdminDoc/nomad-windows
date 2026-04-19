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

### 2.1 — Reticulum / LXMF Mesh Transport
**Effort:** L

Pure-Python mesh networking for PACE comms. Reticulum transport layer + LXMF messaging. Enables true off-grid node-to-node communication without internet. Highest external-audit recommendation.

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

### 3.1 — Codeplug Builder with Per-Radio Zones
**Effort:** M

Build radio codeplugs (channel/zone/scan-list configs) for common radios. CHIRP CSV export. Per-radio zone assignment.

### 3.2 — Propagation-Aware HF Scheduler
**Effort:** M

HF propagation prediction integrated with net schedules. Recommend best frequencies for time-of-day and solar conditions.

### 3.3 — Perceptual-Hash + C2PA on OSINT Images
**Effort:** M

Detect manipulated OSINT imagery. Content authenticity verification. Duplicate/near-duplicate detection across Situation Room feeds.

### 3.4 — Rainwater Catchment Calculator
**Effort:** S

Roof area + local rainfall data = estimated annual yield. Tank sizing. First-flush diverter sizing.

### 3.5 — Plugin API Upgrade + Scaffold Generator
**Effort:** L

Expand the existing plugin foundation (v7.22.0) with a full SDK. CLI scaffold generator for new plugins. Hook points for routes, tables, UI panels.

### 3.6 — Mobile PWA Functional Offline Sync
**Effort:** L

Upgrade existing PWA + IndexedDB foundation to full offline-first sync. Conflict resolution. Background sync on reconnect.

### 3.7 — First-Run Regional Profile Wizard
**Effort:** S | **Depends on:** 1.1

Guided first-run experience that configures regional profile, downloads appropriate data packs, and pre-configures threat-weighted readiness scoring.

---

## Tier 4: Field Operations

SAR, overland, maritime, aviation specializations.

---

### 4.1 — ICS-205/205A Comms Plan Auto-Builder
**Effort:** M

Generate ICS comms plans from existing radio equipment, frequencies, and net schedules.

### 4.2 — SAR Probability Grid (Koester ISRID)
**Effort:** L

Hasty search probability mapping based on lost-person behavior statistics. Search sector prioritization.

### 4.3 — Clue Log + Containment Tracker
**Effort:** M

Georeferenced clue logging for SAR operations. Containment probability tracking.

### 4.4 — Overland Tire Pressure + Payload Advisor
**Effort:** S

Terrain-based tire pressure recommendations. Vehicle payload calculator with CG estimation.

### 4.5 — Terrain-Cost Range Rings
**Effort:** M

Travel-time range rings accounting for terrain slope, vegetation, and trail conditions (not just Euclidean distance).

### 4.6 — iOverlander + Community POI Ingest
**Effort:** M

Import community-contributed points of interest (water sources, campsites, fuel) for overland route planning.

### 4.7 — Maritime: Tide + Current Predictor (XTide)
**Effort:** M

Offline tide predictions. Current estimation for coastal navigation planning.

### 4.8 — Aviation: Density Altitude + Takeoff Distance
**Effort:** S

Density altitude calculator. Takeoff/landing distance estimation for bush flying.

### 4.9 — AIS/ADS-B Deconfliction View
**Effort:** M

Merged ship/aircraft track display for coastal and airfield situational awareness. Extends existing Situation Room AIS/ADS-B feeds.

---

## Tier 5: Specialized Threats & Environment

CBRN, alpine, forensics, threat intel depth.

---

### 5.1 — Gaussian Plume Estimator (ALOHA-style)
**Effort:** L

Chemical/radiological plume dispersion modeling. Wind-driven hazard corridor visualization on map.

### 5.2 — Household Epi Line List + Rt Tracker
**Effort:** M

Household-level epidemic tracking. Reproduction number estimation. Quarantine timeline management.

### 5.3 — Avalanche ATES + Elevation-Banded Weather
**Effort:** M

Avalanche terrain exposure scoring. Elevation-banded weather forecasts for mountain operations.

### 5.4 — Chain-of-Custody Evidence Ledger
**Effort:** S

Timestamped, hash-verified evidence chain for post-incident documentation.

### 5.5 — MISP-lite IOC Ingest + ATT&CK Mapping
**Effort:** M

Import threat intelligence indicators. Map to MITRE ATT&CK framework. Extends existing threat_intel blueprint.

---

## Tier 6: Homestead & Off-Grid Depth

Calculators and trackers for self-sufficient living.

---

### 6.1 — Greywater Branched-Drain Designer | S
### 6.2 — Humanure Thermophilic Tracker | S
### 6.3 — Wood BTU + Cord Ledger | S
### 6.4 — Passive Solar Sun-Path Plotter | M
### 6.5 — Battery Bank Cycle-Life Model | M
### 6.6 — Food Preservation Safety Math (cure, ferment, grain) | M
### 6.7 — SSURGO Soil Profile Cache | M
### 6.8 — Seed-Saving Isolation Distance Planner | S
### 6.9 — Beekeeping Varroa Calendar | S
### 6.10 — Livestock Drug + Withdrawal Timer | S
### 6.11 — Pedigree + Breeding Cycle Tracker | M

---

## Tier 7: Health, Community & Family

Medical depth, psychosocial support, family continuity.

---

### 7.1 — Pediatric Broselow-Equivalent Dose Engine | M
### 7.2 — Chronic Condition Grid-Down Playbooks | M
### 7.3 — Wilderness Medicine Decision Trees | L
### 7.4 — CISM Debrief Wizard | M
### 7.5 — Grief Protocol + Age-Banded Explainer Cards | S
### 7.6 — Sustained-Ops Sleep Hygiene Tracker | S
### 7.7 — NCMEC-style Child ID Packet Generator | S
### 7.8 — Reunification Cascade | M
### 7.9 — Homeschool Curriculum Tracker | M
### 7.10 — Skill-Transfer Ledger | S
### 7.11 — State-Specific Legal Doc Vault | M

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
