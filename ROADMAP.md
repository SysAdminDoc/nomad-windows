# Project N.O.M.A.D. — Roadmap

> **Baseline:** v7.44.0 (~295 tables, 1,850+ routes, 72 blueprints)
> **Updated:** 2026-04-18
> **Effort:** S (1 session), M (2-3), L (4-6), XL (7+)

Everything below is **not yet built**. Pick by interest or user demand.

---

## AI & Automation (remaining from Phase 1.4)

- **Visual alert rules builder** (M) — drag-and-drop UI for the existing alert_rules engine (25 condition types already work via API)
- **Compound alert conditions** (M) — AND/OR logic for multi-condition rules
- **AI-powered recommendations engine** (L) — "You're short on X based on household + regional threats." Seasonal prep advisor
- **Auto-distribute reports to federation peers** (S) — push scheduled SITREPs to trusted peers via sync

---

## Platform & Infrastructure

- **SDR sidecar service** (M) — software-defined radio integration, frequency scanning, waterfall display
- **Node-RED-style flow editor** (L) — visual canvas for alert rules with connected condition/action nodes
- **Perceptual-hash + C2PA on OSINT images** (M) — manipulated imagery detection in Situation Room feeds
- **Plugin API upgrade + scaffold generator** (L) — full SDK, CLI generator, hook points for routes/tables/UI
- **Mobile PWA functional offline sync** (L) — upgrade IndexedDB foundation to full offline-first with conflict resolution
- **Container/kit management** (M) — nested containers table, assign items to bins, kit completeness %

---

## Field Operations

- **SAR probability grid** (L) — Koester ISRID statistical data + grid calculation engine
- **Terrain-cost range rings** (M) — travel-time rings accounting for slope/vegetation (requires DEM data + weighted Dijkstra)
- **iOverlander + community POI ingest** (M) — import water sources, campsites, fuel for overland route planning
- **AIS/ADS-B deconfliction view** (M) — merged ship/aircraft track display (extends existing Situation Room feeds)

---

## Homestead

- **SSURGO soil profile cache** (M) — USDA soil survey data import + lookup by location
- **Pedigree + breeding cycle tracker** (M) — livestock lineage, heat cycles, gestation countdown

---

## Health & Family

- **CISM debrief wizard** (M) — Critical Incident Stress Management guided debrief workflow
- **Grief protocol + age-banded explainer cards** (S) — age-appropriate loss communication templates
- **Homeschool curriculum tracker** (M) — subject progress, lesson plans, grade tracking

---

## Weather & Earth Science

- K1 Skew-T / upper-air viewer (M) — MetPy-based atmospheric sounding display
- K2 Blitzortung lightning overlay (M) — cached lightning strike positions on map
- K3 NWS Area Forecast Discussion parser (S) — extract key phrases from AFD text
- K4 FARSITE-lite wildfire spread (L) — simplified fire spread model from wind + fuel + slope

---

## Regional Expansion Packs

- M1 Canada (M) — ECCC weather + GeoGratis topo data
- M2 UK (M) — Met Office + Ordnance Survey
- M3 EU Copernicus (M) — satellite earth observation data
- M4 Australia (M) — BOM weather + Geoscience AU hazards

---

## Economy & Recovery

- O1 Multi-party barter network ledger (M) — track trades across community members
- O2 Hyperinflation + historical recovery reference (S) — case studies and planning guides
- O3 Microgrid black-start SOP (S) — step-by-step generator → grid restoration procedure

---

## Comms Depth

- R1 NTS radiogram + formal traffic handling (M)
- R2 ALE / VARA / Pat Winlink integration (L)
- R3 FLDIGI macro library + net control scripts (M)
- AU1-AU6 Shortwave/ARES/SKYWARN directories (S each)

---

## Developer & Platform

- S1 Property-based + fuzz test harness (M)
- S2 Contract + chaos + perf regression tests (L)
- S3 Mutation testing on life-safety calculators (M)
- S4 WCAG 2.2 AA deep audit (L)
- S10 Reproducible builds + SBOM + transparency log (L)
- S12 nomad-cli companion tool (M)
- S14 Tauri alternative shell + WASM calculators (XL)

---

## AI & Simulation

- T1 Role-persona prompt library (S) — pre-built AI personas for different advisory roles
- T2 OPORD autofill engine (M) — generate operations orders from existing data
- T5 Evacuation Monte Carlo simulator (L) — probabilistic evacuation outcome modeling
- T7 Bayesian inventory burn forecaster (M) — probabilistic supply duration predictions
- T8 Fault Tree Analysis engine (M) — failure mode modeling for critical systems

---

## Hardware Reference Catalogs

- U1-U7 (S each) — Generator, heater/stove, inverter/charge-controller, water pump, refrigeration, firearm maintenance, lifetime-tool catalogs

---

## Drill & Exercise Engine

- V1 Scenario library + inject-timer (M)
- V2 Tabletop exercise engine (M)
- V3 Functional exercise engine (L)
- V4 Federation drill orchestrator (M)
- V5 Difficulty scaler (S)

---

## Navigation (GPS-denied)

- AJ2 Polaris-altitude latitude + Southern Cross (S)
- AJ3 Lunar azimuth table (S)
- AJ4 Sun-angle clock (no-watch time) (S)
- AJ6 Improvised sextant + HO-249 tables (M)
- AJ7 Terrain-association route builder (M)
- AJ8 Barometric altimeter calibration (S)
- AJ9 Offline star map (M)

---

## Foraging & Game Processing

- AI1-AI8 (M-L) — Offline plant-ID model, regional foraging calendar, deadly-lookalike ledger, toxicity decision tree, spore-print atlas, HAB/shellfish overlay, famine-food reference, ethnobotanical vault
- AK1-AK10 (S-M each) — Field-dressing SOPs, live-weight yield calculator, aging climate matrix, offal/zoonosis, hide processing, humane dispatch, fish regs/bite predictor, toxic fish ID, aquaponics, fish preservation

---

## Outdoor Cooking

- AL1 Fire-heat temperature chart (S)
- AL3 Rocket-stove design + fuel efficiency math (M)
- AL4 Solar-oven performance curve (S)
- AL6 Pit cooking SOP (S)
- AL7 Haybox retained-heat calculator (S)
- AL8 Bulk-cooking math + foil-packet reference (S)

---

## Financial Preparedness

- AT1 Portfolio stress-test scenarios (M)
- AT2 Insurance coverage audit (S)
- AT5 Asset-portability classifier (S)
- AT6 Credit freeze calendar (S)
- AT7 Income diversification tracker (M)

---

## Environmental Monitoring

- Z1-Z6 (S-M each) — Indoor air station adapter, dew-point/mold index, pollen feed, private-well baseline, heritage hazards (lead/asbestos), garden soil safety

---

## Medical Depth II

- AA1-AA10 (S-M each) — Wilderness-med progression ladder, SOAP note journal, scenario library, improvised splint reference, evacuation decision matrix, PPE doffing SOP, home isolation zone builder, decontamination product matrix, quarantine roster, transmission route reference

---

## Water Quality

- AC1-AC6 (S-M each) — Potability test-strip workflow, well yield test, Legionella guard, boil-order feed, cistern cleaning + first-flush sizing, source complexity ladder

---

## Community Health

- AD1-AD9 (S-M each) — Pod health pulse, stock mosaic (opt-in), mutual-aid queue, sick-call roster, post-event welfare census, K6/PHQ-2 anonymous check-in, after-action archive, historical crisis case library, oral history capture

---

## OPSEC / Privacy

- AE1-AE7 (S each) — Cover-story template library, social-footprint self-audit, address privacy scorer, EXIF scrubber, gray-man checklist, vehicle-profile audit, compartmentalization ledger

---

## Biosecurity

- AR1-AR7 (S-M each) — Avian-flu response SOP, farm biosecurity zone layout, 21-day quarantine protocol, carcass disposal matrix, zoonosis register, vector-ID cards, vaccination calendar

---

## Digital Asset Sovereignty

- AP1-AP7 (S-M each) — BIP39/SLIP39 seed vault, hardware wallet ledger, multi-sig quorum map, crypto estate plan, U2F/FIDO2 key registry, cold-storage air-gap SOP, 2FA reset kit

---

## SOHO Business Continuity

- AQ1-AQ6 (S-M each) — Client notification cascade, revenue buffer calculator, workstation redundancy matrix, COOP plan template, business dependency graph, offline invoice archive

---

## Explicit Omissions

- Interactive substance-withdrawal tapers (medical risk too high)
- Home distillation of potable spirits (federal permit required)
- Paper-currency / scrip printing templates (counterfeiting-adjacent)
- Full-depth theology / scripture libraries
- Interactive flint-knapping / flintlock guides
- Offline Google Translate competitor
