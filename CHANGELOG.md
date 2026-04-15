# Changelog

All notable changes to project-nomad-desktop will be documented in this file.

## [v7.27.0] — Hardening & Polish (Audit Backlog)
- Fixed: Disk-space pre-check before yt-dlp downloads (media.py) — rejects when approx size + 500 MB margin exceeds free space on the video dir volume
- Fixed: Streaming CSV import for contacts (interoperability.py) — new `_iter_upload_lines()` decoder + batched 500-row commits avoid loading multi-hundred-MB uploads fully into memory
- Fixed: Duty roster cleanup on pod member removal (group_ops.py) — cancels scheduled/active shifts for the removed person in the same pod instead of leaving orphaned roster entries
- Fixed: XSS — user-sourced strings rendered via innerHTML in `_tab_medical_phase2.html` and `_tab_agriculture.html` are now escaped through a local `esc()` helper that prefers the global `window.escapeHtml`
- Fixed: Ollama streaming resilience (ai.py) — corrupt/partial JSON chunks from a crashing Ollama backend are now skipped with a debug log instead of forwarded to the client reader
- Fixed: Config crashes on invalid env vars (config.py M7) — new `_env_int()` helper falls back to defaults with a warning instead of raising ValueError at import time
- Fixed: Double preparedness import (app.py L4) — consolidated to a single import at the `start_alert_engine` site; blueprint is reused at registration
- Fixed: `os._exit(0)` → `sys.exit(0)` on shutdown (nomad.py L3) — allows interpreter cleanup so in-flight DB commits actually land
- Fixed: Missing `name` attrs on 5 hidden inputs in `_tab_daily_living.html` (L2) — satisfies the `test_partial_controls_have_names` contract
- Added: `@validate_json` schemas applied to all 8 mutating financial endpoints (cash/metals/barter/documents × create/update) per audit H2. Schemas enforce types, max lengths (200-2000 chars), and numeric bounds (≤1B for monetary fields). Financial is the most sensitive blueprint per the audit and gets first coverage.
- Fixed: `access_logs` table renamed to `platform_access_log` (audit M4) — disambiguates from `access_log` used by physical-security blueprint. New `_migrate_access_logs()` runs on every startup: idempotent, copies any existing rows into the new table via `INSERT OR IGNORE`, then drops the old. Index names also updated. SQL references in `platform_security.py` rewritten.
- Fixed: Mutating rate limit actually enforced (audit H3) — replaced empty `pass` body with a per-remote-IP sliding-window counter (60s / N from `Config.RATELIMIT_MUTATING`). Localhost exempt. Returns 429 + `retry_after` on overflow.
- Fixed: Path traversal on Windows in NukeMap/VIPTrack static-file routes (audit H5) — replaced `normcase` + prefix matching with `os.path.commonpath([full, base]) == base`, which is normalization-safe across mixed-case/mixed-separator paths.
- Added: Shared `get_pagination()` helper in `web/blueprints/__init__.py` (default 100, max 1000) and applied `LIMIT ? OFFSET ?` to primary list endpoints in 7 blueprints — `financial` (cash/metals/barter/documents), `daily_living` (schedules/clothing/sanitation×2/morale/sleep/performance), `training_knowledge` (skill_trees/courses/drill_templates/knowledge_packages), `hunting_foraging` (trade_skills/preservation_methods/preservation_batches/hunting_zones), `disaster_modules` (energy_systems/building_materials), `movement_ops` (alt_vehicles/route_hazards/route_recon), `evac_drills` (drill_runs). Addresses audit M1 — blueprints were returning unbounded result sets that caused memory spikes and UI freezes on constrained hardware.
- Added: `log_activity()` audit trail to `contacts` (create/update/delete) and `vehicles` (create/update/delete) — was blind spot per audit M2. Weather module deferred (most mutating endpoints are internal alert-rule triggers, not user data).
- Fixed: PID recycling in service manager (services/manager.py L6) — `is_running()` now verifies the stored PID's process executable basename matches the service's recorded `exe_path` via psutil; `_pid_alive` alone could match a recycled PID that the OS had reassigned to an unrelated process after a crash
- Added: `esc()` helper (XSS guard) in 7 remaining Phase 17-20 partials — `_tab_hunting_foraging`, `_tab_daily_living`, `_tab_disaster_modules`, `_tab_specialized_modules`, `_tab_group_ops`, `_tab_training_knowledge`, `_tab_security_opsec`. Foundation is in place; `_tab_group_ops` statusBadge and `_tab_security_opsec` classificationBadge/categoryBadge are already wrapped. Remaining per-row field escaping will land incrementally.
- Fixed: XSS in `_tab_hunting_foraging.html` — 5 primary render functions (game, zones, fishing, foraging, edibles, traps) plus shared `gameTypeBadge`/`statusBadge`/`confClass` helpers now route all user-sourced strings (species, plant names, locations, scientific names, toxicity warnings, bait, notes) through `esc()`. This is the worst-offender Phase 17-20 partial per the audit (56 endpoints, 0 tests).
- Stats: Addresses 9 backlog items (#8 partial, #10, #11, #12, #13, L2, L3, L4, M7) from the v7.27.0 hardening punch list in ROADMAP-v8.md

## [v7.26.0] — Phase 20: Specialized Modules & Community
- Added: Supply caches with GPS and concealment tracking
- Added: Pets & companion animals with food supply projections
- Added: Youth programs, end-of-life plans, legal document vault
- Added: Procurement lists with budget tracking
- Added: Intel collection with PIR management and classification
- Added: Digital fabrication project tracker (3D printing, CNC)
- Added: Gamification — 10 badges with awards and leaderboard
- Added: Seasonal events with upcoming calendar view
- Added: Drone manager with flight logging
- Added: Fitness logs with weekly stats
- Added: Content packs for community sharing
- Stats: 81 new routes, 15 new tables, 1,644 total routes

## [v7.25.0] — Phase 19: Platform, Deployment & Security
- Added: Multi-user authentication with PIN hash (SHA-256)
- Added: Session management (24hr expiry, token-based)
- Added: PIN lockout (5 attempts / 15 min cooldown)
- Added: Role-based access control (admin/user/viewer/guest)
- Added: Access logging with summaries
- Added: Deployment configuration management
- Added: Performance metrics with aggregation
- Stats: 26 new routes, 5 new tables

## [v7.24.0] — Phase 18: Hardware, Sensors & Mesh
- Added: IoT sensor dashboard (12 sensor types) with time-series readings
- Added: Network device inventory with topology tree
- Added: Meshtastic mesh node management with map and stats
- Added: Weather station direct integration
- Added: GPS device management with fix recording
- Added: Wearable device tracking
- Added: Integration configs (MQTT, Home Assistant, Node-RED, webhook, CalDAV, Meshtastic)
- Stats: 45 new routes, 8 new tables

## [v7.23.0] — Phase 17: Hunting, Foraging & Wild Food
- Added: Hunting game log with species, method, weight tracking
- Added: Fishing log with species, bait, conditions
- Added: Foraging log with GPS locations and confidence rating
- Added: Traps & snares with check scheduling
- Added: Wild edibles reference (10 seeded species)
- Added: Trade skills tracker (13 categories)
- Added: Preservation methods (8 seeded) and batch tracking
- Added: Hunting zones with season management
- Stats: 56 new routes, 10 new tables

## [v7.22.0] — Phase 16: Interoperability & Data Exchange
- Added: 12 export formats (CSV, vCard, GPX, GeoJSON, KML, ICS, CHIRP, ADIF, FHIR, Markdown, custom)
- Added: 8 import routes with format auto-detection
- Added: 4 print routes (FEMA household plan, vehicle cards, medication cards, skills gap report)
- Added: Batch import/export operations
- Added: Export history tracking
- Stats: 31 new routes, 2 new tables

## [v7.21.0] — Phase 14+15: Disaster Modules & Daily Living
- Added: Disaster plans with 10 built-in checklist seeds per disaster type
- Added: Energy systems tracking (wood heating BTU, solar, biogas, micro-hydro)
- Added: Construction project tracker with materials inventory
- Added: Fortification assessment and safe room reference
- Added: Daily schedule builder with chore rotation
- Added: Clothing inventory with cold weather assessment
- Added: Sanitation supply tracking with projections
- Added: Morale logs with trend analysis
- Added: Sleep logs with debt tracking and watch optimizer
- Added: Performance checks with auto risk assessment
- Added: Grid-down recipe database (5 seeded)
- Stats: 80 new routes, 14 new tables

## [v7.19.0] — Phase 13: Agriculture & Permaculture
- Added: Food forest design (guilds, layers, canopy calculator)
- Added: Soil building projects (hugelkultur, swales, biochar, cover crops)
- Added: Perennial plant management with seed saving
- Added: Multi-year agricultural plans (1-20 year timeline)
- Added: Livestock breeding records and feed tracking
- Added: Homestead infrastructure (solar, battery, well, wood inventory)
- Added: Aquaponics systems with water chemistry
- Added: Resource recycling systems (composting, greywater, biogas)
- Stats: 59 new routes, 10 new tables

## [v7.18.0] — Phase 12: Security, OPSEC & Night Operations
- Added: OPSEC compartment manager with audit checklists
- Added: Threat matrix with CARVER assessment
- Added: Observation post logging and range cards
- Added: Signature assessment (visual, audio, electronic, thermal)
- Added: Night operations planner with moonrise/set and ambient light
- Added: CBRN equipment inventory and decon procedures
- Added: EMP hardening inventory and grid dependency scanner
- Stats: 47 new routes, 10 new tables

## [v7.17.0] — Phase 11: Group Operations & Governance
- Added: Pod (multi-household) management with member roles
- Added: Governance roles, SOPs, duty roster, onboarding
- Added: Dispute resolution with mediation and voting systems
- Added: ICS forms (201, 202, 204, 205, 206, 213, 214, 215)
- Added: CERT team management with damage assessment
- Added: Shelter management and community warning system
- Stats: 42 new routes, 12 new tables

## [v7.16.0] — Phase 10: Training, Education & Knowledge Preservation
- Added: Skill trees with prerequisite chains per person
- Added: Training courses with lessons and assessments
- Added: Certification tracker with renewal reminders
- Added: Drill template library with grading rubric and AAR
- Added: Spaced repetition flashcard system
- Added: Knowledge packages ("if I'm gone" per key person)
- Stats: 49 new routes, 8 new tables

## [v7.15.0] — Phase 8+9: Land Assessment & Medical Phase 2
- Added: Property site selection with multi-criteria scoring
- Added: Property mapping (GPS boundary, infrastructure, sight lines)
- Added: Development planning with multi-year timeline and cost tracker
- Added: BOL comparison (side-by-side property scoring)
- Added: Pregnancy & childbirth tracking with field delivery protocol
- Added: Dental emergency records and protocols
- Added: Veterinary medicine with animal dosage calculator
- Added: Chronic condition management plans
- Added: Herbal/alternative medicine reference database
- Added: Vaccination schedule tracker and mental health log
- Stats: 55 new routes, 10 new tables

## [v7.14.0] — Phase 5+6: Movement Ops & Tactical Communications
- Added: Movement plans (foot march rate, convoy SOP, fuel planning)
- Added: Alternative vehicles (bicycle, horse, boat, ATV) with range calculators
- Added: Route hazard markers and recon logging
- Added: Vehicle loading plans with go/no-go matrix
- Added: PACE communications plan builder
- Added: Radio equipment inventory with antenna planning
- Added: Authentication code system (challenge/response, rotating daily)
- Added: Net schedule tracker and comms check scheduling
- Added: Message format templates (SITREP, MEDEVAC 9-line, SALUTE, SPOT)
- Stats: 65 new routes, 12 new tables

## [v7.13.0] — Phase 4: Advanced Inventory & Consumption Modeling
- Added: Inventory audits with per-item discrepancy tracking
- Added: Consumption profiles (activity-adjusted caloric needs per person)
- Added: Water budget calculator (drinking, cooking, hygiene, medical)
- Added: Recipe manager linked to inventory with "meals remaining"
- Added: Inventory substitute mapping
- Stats: 28 new routes, 6 new tables

## [v7.12.0] — Phase 2: Nutritional Intelligence & Water Management
- Added: USDA FoodData nutritional linking per inventory item
- Added: Micronutrient gap analysis with deficiency timeline
- Added: Person-days of food calculator
- Added: Water storage, filter life, and source tracking
- Added: Water quality testing log
- Stats: 22 new routes, 5 new tables

## [v7.11.0] — Phase 1: Data Foundation & Localization
- Added: Regional profile system (country → state → county → ZIP)
- Added: Data pack manager with tiered offline datasets
- Added: FEMA NRI county-level hazard scoring integration
- Added: USDA FoodData SR Legacy nutritional database (7,793 foods)
- Added: Threat-weighted readiness scoring by region
- Stats: 18 new routes, 4 new tables

## [v7.10.0] — High Value: Readiness Goals, Alert Engine, Timeline, Threat Intel, Evac Drills

## [v7.9.0] — PACE Plans, Evacuation, Containers, Preservation Expansion

## [v7.8.0] — Critical Path: Water, Financial, Vehicles, Loadout + Nutrition Fix

## [v7.7.0] — Daily Operations Brief

## [v7.6.0] — Family Check-in Board

## [v7.5.0] — Emergency Mode (capstone)

## [v7.4.0] — Route Plan with Milestones

## [v7.3.0] — Interactive Kit Builder Wizard

## [v7.2.0] — Location-aware Situation Room (Near You)
