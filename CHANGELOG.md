# Changelog

All notable changes to project-nomad-desktop will be documented in this file.

## [v7.44.0] — Phase 1.1: Data Foundation & Localization

### Added
- **FEMA NRI importer** — downloads county-level hazard risk data (18 hazard types, ~3,200 counties) from hazards.fema.gov and bulk-loads into `fema_nri_counties` table. Background-threaded with progress polling.
- **USDA FoodData SR Legacy importer** — downloads 7,793 foods with full macro/micronutrient data from fdc.nal.usda.gov into `nutrition_foods` and `nutrition_nutrients` tables.
- **NOAA Weather Stations importer** — downloads ISD station history (~12K US stations) into new `noaa_stations` table.
- **NOAA Frost Dates importer** — generates frost date data from NOAA Climate Normals or latitude-based approximation into new `noaa_frost_dates` table. Growing season days calculated per station.
- **USDA Hardiness Zones importer** — downloads ZIP-to-zone lookup from PRISM into new `usda_hardiness_zones` table.
- **Regional profile auto-populate** — saving a profile with ZIP/lat/lng now auto-fills: hardiness zone (from ZIP), FEMA risk scores (from county), frost dates (nearest station), nearest NWS station.
- **3 new lookup routes** — `/api/region/hardiness/<zip>`, `/api/region/frost-dates?lat=&lng=`, `/api/region/nearest-station?lat=&lng=`.
- **3 new tables** — `noaa_stations`, `noaa_frost_dates`, `usda_hardiness_zones` with 6 new indexes.
- **Pack importer framework** — `/api/data-packs/<id>/import` triggers background import, `/api/data-packs/<id>/import/status` polls progress.

### Stats
- 5 data pack importers, 3 new tables, 6 new indexes, 3 new lookup routes. All 5 Tier 1 data packs now have working import pipelines. Nutrition blueprint (search, link, summary, micronutrient gaps) was already built — this adds the data that powers it.

## [v7.43.0] — Cross-theme audit + WCAG compliance (Pass 8)

Final pass in the premium CSS polish marathon (v7.38–v7.43). Cross-theme color token audit across all 5 themes, WCAG 2.1 AA contrast compliance on remaining surfaces, reduced-motion coverage expansion.

## [v7.42.0] — Final refinements (Pass 7)

Late-stage polish refinements across auxiliary surfaces and edge-case rendering paths.

## [v7.41.0] — Auxiliary surfaces & micro-polish (Pass 6)

Polish pass targeting auxiliary surfaces (modals, wizards, toasts, popovers) and micro-interaction details.

## [v7.40.0] — Flagship surface polish (Pass 5)

Premium polish on flagship surfaces — Situation Room, Home bento grid, Preparedness dashboards, AI Chat.

## [v7.39.0] — Instrument-grade premium redesign (Pass 4)

Deep premium redesign pass — unified typography scale, refined card depth system, instrument-grade data presentation across all workspaces.

## [v7.38.0] — Multi-LLM review fixes + premium polish + minimalism pass

Multi-LLM code review findings applied. Inline style migration across all `_tab_*.html` partials to CSS classes. aria-busy wiring on long-running operations. ai-dots thinking indicator. Motion primitives centralized to `premium/05_motion.css`. Situation Room `!important` count reduced from 89 to 11. Playwright coverage added (shell-workflows + polish-primitives + opt-in visual tour). Print template `@media` hardening for multi-page documents.

## [v7.37.0] — Premium polish: CSS system coherence pass

System-level cleanup across the premium CSS stack after 14 prior polish rounds. No feature changes; all edits are cosmetic/structural refinements to how existing surfaces render.

### Fixed
- **`.btn-primary` duplicate definition collision** — `premium/95_premium_polish.css` declared `border-color: transparent` and a single-layer shadow that was silently overridden by the richer multi-layer treatment in `premium/99_final_polish.css` (inset highlight + shadow + accent glow). The 95 block is now reduced to just the gradient fill it uniquely owns; border/shadow/hover system lives in 99 alone. Eliminates a small DPI-dependent rendering jitter on first-paint under some themes.
- **Focus-ring token split** — `--premium-focus-ring` / `--premium-focus-shadow` (95) and `--focus-ring-color` / `--focus-ring-halo` (99) were two parallel systems. The 95 tokens now reference the 99 halo/ring colors via cascade fallback, so all focus treatments share a single source of truth and stay in sync when accent color changes.
- **Hard-coded high z-index values** — replaced raw `10000` / `15000` / `20000` / `100000` declarations with named tokens in `app/00_theme_tokens.css`: `--z-modal-stack` (10000, modal + wizard + photo viewer), `--z-app-overlay` (15000, settings modals above feature modals), `--z-frame-overlay` (20000, customize/edit frame), `--z-command-palette` (100000, always topmost). Six sites updated across `20_primary_workspaces.css`, `30_preparedness_ops.css`, `50_settings.css`, `70_layout_hardening.css`.
- **`transition: all` on `<progress>` fill** — `99_final_polish.css:1749` was the only remaining `transition: all` in the premium layer stack. Replaced with explicit `width`/`background-color`/`box-shadow` list so compositor doesn't animate unrelated properties when the bar fills.
- **Aggressive display-heading letter-spacing** — `.home-launch-title` / `.settings-command-title` / `.settings-panel-title` / `.workspace-context-title` were tightened to `-0.045em`, over 2× the tracking used on `.modal-header h3` (`-0.015em`) and `.wizard-card h2` (`-0.025em`). Unified to `-0.025em` so large tactical titles don't visibly out-compress their modal/wizard counterparts.
- **Reduced-motion entrance-animation snap** — the universal `*, *::before, *::after { animation-duration: 0.001ms }` override at `99_final_polish.css:681` covers most cases but slide/scale entrance keyframes on `.modal-card`, `.wizard-card`, `.command-palette-overlay`, `.settings-modal-card`, `.shortcuts-dialog`, `.toast` now get an explicit `animation: none !important` so they land on their final state instantly instead of compositing a micro-frame of mid-animation geometry.

### Stats
- 6 CSS files changed, 1 Python file bumped. No behavior/runtime changes — all adjustments are style-layer. Test suite unaffected.

## [v7.28.0] — Auth foundation + validation expansion (Roadmap H2/H4 + M1/M2)

### H4 — Authentication enforcement layer
- New `web/auth.py` with `require_auth(role='user')` decorator.
- **Desktop mode (default):** decorator is a no-op; `g.current_user` set to a synthetic admin so downstream code works unchanged. Existing single-user installs require zero migration.
- **Multi-user mode:** opt-in via `NOMAD_AUTH_REQUIRED=1` env var. Validates session token from `Authorization: Bearer <token>` header or `?token=` query against `app_sessions`/`app_users` tables (provisioned by Phase 19's `platform_security` blueprint). Localhost requests always exempt so the local pywebview shell works.
- Role hierarchy: `admin` > `user` > `viewer` > `guest`. `@require_auth('admin')` rejects lower-rank sessions with 403.
- Demo coverage: applied to all 8 mutating financial endpoints (cash/metals/barter/documents × create/update). Pattern can be replicated to any other blueprint with a one-line decorator.

### H2 — Input validation expansion
- `medical_phase2`: 9 routes wrapped — pregnancies, dental, chronic conditions, vaccinations, vet, mental health (create + update where applicable). Schemas enforce types, max lengths (200-5000 chars), numeric bounds (mood/anxiety/sleep ranges), and `choices` enums for severity/species/status fields.
- `vehicles`: 4 routes wrapped — vehicles + maintenance (create + update). Schemas bound year (1900-2100), mpg (0-1000), odometer/cost (≤10M).

### M1 — Pagination expansion (4 more blueprints)
- `agriculture` (food_forest_guilds, food_forest_layers, multi_year_plans), `group_ops` (pods), `readiness_goals`, `land_assessment` (properties). Brings v7.27.0 + v7.28.0 total to **22 list endpoints across 11 blueprints** (financial, daily_living, training_knowledge, hunting_foraging, disaster_modules, movement_ops, evac_drills, agriculture, group_ops, readiness_goals, land_assessment).

### M2 — Activity logging expansion
- `checklists` (create/update/delete) and `weather` (action_rules create/delete) now write to the activity log. Brings v7.27.0 + v7.28.0 total to **4 of 11 audit-flagged blueprints** (contacts, vehicles, checklists, weather). Remaining: brief, kit_builder, kiwix, print_routes, supplies, timeline.

### Stats
- 11 files changed. New files: `web/auth.py`. No DB schema changes (uses Phase 19 tables). Backward compatible — existing single-user desktop installs see no behavior change.

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
