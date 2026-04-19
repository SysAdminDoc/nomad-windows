# Changelog

All notable changes to project-nomad-desktop will be documented in this file.

## [v7.50.0] — Final Backend Batch: CSV Export, Aisle Grouping, OCR, Change Detection

### Added
- **Multi-user profiles API (P2-14)** — `/api/profiles` lists users with preferences from `app_users` table.
- **Generic CSV export (P2-18)** — `/api/export/csv/<table_name>` exports any validated table as CSV with safe_table validation. Up to 10K rows.
- **Shopping list aisle grouping (P3-18)** — `/api/shopping-list/grouped` categorizes items into 8 store aisles (Produce, Dairy, Meat, Canned, Pharmacy, Water, Hardware, Hygiene).
- **KB image import with OCR (P5-09)** — `/api/kb/import-image` saves image to KB workspace and runs Tesseract OCR text extraction (graceful fallback when unavailable).
- **Web page change detection (P5-12)** — `/api/monitors/<id>/snapshot` fetches page, computes SHA-256 hash, compares to stored hash, reports `changed: true/false`.
- **Bcrypt password upgrade (P5-23)** — `/api/auth/upgrade-hash` upgrades user password hash from PBKDF2 to bcrypt (12 rounds). Requires `bcrypt` pip package.
- **pyproject.toml (P3-12/P3-I22)** — Modern Python project metadata with pytest and ruff config.

### Stats
71 API routes in `roadmap_features.py` (1,360+ lines).

## [v7.49.0] — 13 More Roadmap Items + CI/Docs

### Added
- **Map bookmark/favorites (P2-16)** — `map_bookmarks` CRUD for quick-jump saved locations.
- **Per-conversation KB scope (P2-23)** — `kb_scope` JSON column on conversations with GET/PUT API.
- **URL-based recipe import (P2-24)** — `/api/recipes/import-url` scrapes JSON-LD structured data from recipe websites.
- **Custom API widget (P4-05)** — `/api/widgets/custom-api` fetches any JSON API for dashboard widget rendering.
- **Favicon auto-fetch (P4-12)** — `/api/favicon?url=` returns base64-encoded favicon for services/bookmarks.
- **Prompt version control (P5-04)** — `ai_prompt_versions` table with version history, commit messages, and rollback.
- **2FA/TOTP authentication (P5-07)** — TOTP setup with provisioning URI, verification with 1-window tolerance, 8 backup recovery codes. Requires `pyotp`.
- **KB archive upload (P5-08)** — `/api/kb/upload-archive` extracts ZIP/TAR contents into KB workspace (up to 500 files, 50MB each).
- **Self-signed cert trust (P5-14)** — `allow_insecure` flag per federation peer for self-signed SSL certificates.
- **Per-page access control (P5-15)** — `tab_permissions` setting maps tab names to allowed role lists.
- **Test coverage in CI (P5-18)** — `pytest-cov` with XML + terminal coverage reports in build pipeline.
- **Release drafter (P5-19)** — `.github/release-drafter.yml` auto-generates release notes from PR labels.
- **CONTRIBUTING.md (P5-20)** — full contribution guide with blueprint + widget + testing examples.

### New Tables (3)
`map_bookmarks`, `ai_prompt_versions`, `totp_secrets`

### Stats
62 API routes in `roadmap_features.py` (1,143 lines). 16 total new tables across v7.48.0-v7.49.0.

## [v7.48.0] — Massive Feature Batch: 18 Roadmap Items

### Added
- **Recipe-driven consumption (P2-04)** — `recipes` + `recipe_ingredients` tables, CRUD routes, `/api/recipes/<id>/cook` auto-deducts inventory ingredients with multiplier support.
- **Inventory location hierarchy (P2-09)** — `inventory_locations` table with `parent_id` for nesting. Tree view endpoint at `/api/inventory/locations/tree`.
- **Service health history (P2-12)** — `service_health_log` table. `/api/services/health-history/<id>` with configurable time window (1-720 hours).
- **Battery/consumable tracker (P2-21)** — `battery_tracker` CRUD with expected life days, installed date, and last-checked tracking.
- **Insurance & warranty tracker (P3-08)** — `warranties` CRUD with expiry dates, policy numbers, and document paths.
- **Lightweight/minimal mode (P3-14)** — `NOMAD_MINIMAL_MODE=1` config flag for Raspberry Pi / low-RAM hardware.
- **Per-widget refresh intervals (P4-01)** — `dashboard_templates` table stores per-widget config including refresh intervals.
- **Dashboard templates (P4-02)** — CRUD for preconfigured dashboard layouts.
- **Dashboard config export/import (P4-03)** — `/api/dashboard/config/export` downloads full config as JSON; `/api/dashboard/config/import` restores it.
- **Calendar with ICS import (P4-04)** — `calendar_events` table, CRUD, and `/api/calendar/import-ics` for VCALENDAR file import (up to 500 events).
- **Torrent dashboard widget (P4-14)** — `/api/dashboard/torrent-widget` returns active/downloading/seeding counts.
- **Config env var injection (P4-18)** — `${ENV_VAR}` syntax in config.json values, expanded by `get_config_value()`.
- **AI Skills profiles (P5-01)** — `ai_skills` table with name, system_prompt, kb_scope. Full CRUD for reusable domain expertise definitions.
- **AI usage analytics (P5-03)** — `ai_usage_log` table. `/api/ai/usage` returns per-model query counts, token totals, daily breakdown over configurable period.
- **URL monitor widget (P5-10)** — `url_monitors` CRUD with manual check trigger. Tracks response time, status code, consecutive failures.
- **Todo/task dashboard widget (P5-11)** — `/api/dashboard/tasks-widget` returns overdue + upcoming tasks for home dashboard.
- **OPML import for RSS (P5-13)** — `/api/feeds/import-opml` bulk-imports RSS feeds from OPML files with duplicate detection.
- **Personal RSS reader (P5-24)** — `personal_feeds` + `personal_feed_items` tables. CRUD, per-feed refresh with RSS 2.0 + Atom parsing.

### New Tables (12)
`recipes`, `recipe_ingredients`, `inventory_locations`, `service_health_log`, `battery_tracker`, `warranties`, `ai_skills`, `ai_usage_log`, `url_monitors`, `personal_feeds`, `personal_feed_items`, `calendar_events`, `dashboard_templates`

### Stats
45 new API routes in `web/blueprints/roadmap_features.py` (683 lines). 13 new database tables.

## [v7.47.0] — Auth Proxy, Caloric Gap, Security Hardening

### Added
- **Auth proxy support (P4-15)** — set `NOMAD_AUTH_PROXY=1` to trust `X-Forwarded-User` and `X-Remote-User` headers from reverse proxies (Authelia, Caddy forward_auth, nginx). Optional `X-Forwarded-Role` header maps to NOMAD roles (admin/user/viewer/guest). Enables seamless LAN multi-user without NOMAD's own session tokens.
- **Caloric gap analysis (P2-27)** — new `GET /api/consumption/caloric-gap` endpoint. Compares total stored calories vs daily household need per food category. Returns coverage days, 30-day gap in calories, per-category breakdown, and water coverage. Builds on existing consumption profiles and nutrition links.
- **Security notice in README (P5-17)** — prominent security blockquote with guidance on reverse proxy, NOMAD_ALLOWED_HOSTS, and NOMAD_AUTH_REQUIRED for LAN deployments.

### Verified Already Complete
- P2-20 (task assignment to contacts) — `assigned_to` column already in `scheduled_tasks` table with full API support.
- P1-12 (confirm before bulk ops) — media batch delete already has count confirmation dialog.

## [v7.46.0] — Security, Search Bangs, CPU Temp, CI Hardening

### Added
- **Search bangs in command palette (P4-06)** — type `/i water` to search only inventory, `/c smith` for contacts, `/n todo` for notes. 11 bang prefixes: `/i` inventory, `/c` contacts, `/n` notes, `/m` medical, `/w` waypoints, `/f` frequencies, `/d` documents, `/t` checklists, `/e` equipment, `/a` ammo, `/s` skills.
- **CPU temperature monitoring (P4-13)** — `cpu_temp` field in `/api/system` response. Uses psutil `sensors_temperatures()` with fallback chain (coretemp, k10temp, cpu_thermal, acpitz). Available on Linux; gracefully returns `null` on Windows/macOS.
- **Host header validation (P5-16)** — set `NOMAD_ALLOWED_HOSTS=nomad.local,192.168.1.50` to reject requests with unexpected Host headers. Prevents DNS rebinding attacks on LAN deployments. Localhost always exempt. Disabled by default.

### Changed
- **CI esbuild step (P2-I09)** — `build.yml` now runs `npm ci && node esbuild.config.mjs` before PyInstaller build, ensuring `web/static/dist/` is always fresh in CI artifacts. Node.js 20 added to build matrix.

### Roadmap Audit
Comprehensive audit of all P1-P5, UX, and internal items against codebase. Marked 34 additional items as complete that were implemented but not tracked: P1-02, P1-03, P1-04, P1-09, P1-12, P1-16, P1-19, P1-21, P2-01, P2-02, P2-03, P2-05, P2-10, P2-11, P2-22, P2-26, P3-04, P1-I03, P1-I11, P1-I12, P2-I08, and others.

## [v7.45.0] — Internal Audit Quick Wins + UX Improvements

### Fixed
- **`apiFetch()` network error handling (P1-I18)** — network-level `TypeError` (offline, DNS failure, timeout) now returns a structured error with `status: 0` and `network: true` flag instead of re-throwing the raw exception. Callers get meaningful error messages ("Request timed out" / "Network error — check your connection").
- **SSE reconnect flap protection (P1-I19)** — `_reconnectDelay` no longer resets to 1000ms immediately on `onopen()`. Now waits 30s of sustained connection before resetting backoff, preventing rapid connect/disconnect cycles from flooding the server.
- **Ollama port hardcoding (P1-I15)** — 3 API calls in `ai.py` (model info, vision chat, model details) now use `ollama.OLLAMA_PORT` constant instead of hardcoded `localhost:11434`. Training job route already used the constant.

### Added
- **`/healthz` endpoint (P4-19)** — lightweight health check returning `{status, version, uptime, db_ok, services_running}` for external monitors (UptimeKuma, Prometheus, etc.). Returns 200 when healthy, 503 when DB is unreachable.
- **Sunrise/sunset-aware auto night mode (P4-10)** — auto night-mode now uses actual sunrise/sunset times from `/api/sun` when location data is available, instead of hardcoded 9pm-6am. Falls back to time-based logic when sun data is unavailable.

### Internal Audit Verification
Verified 12 additional P1-I items were already resolved in prior releases (v7.29-v7.44): shared helpers centralized in utils.py (I01/I02), sitroom HTTP timeouts (I13), AI stream AbortController (I17), process kill escalation (I04), thread locks on manager dicts (I05/I06), PRAGMA optimization (I07), config fsync (I14), SSE subscriber locking (I16), NukeMap inline DOM (I20), libtorrent import cache (I21), FTS5 double-quote sanitization (I08).

### Verified P1 Features Already Implemented
Confirmed 15 P1 roadmap items already shipped: loading skeletons (P1-01), favicon badge (P1-05), collapsible sidebar groups (P1-06), settings search (P1-07), inline quantity edit (P1-08), print preview in-app (P1-10), relative timestamps (P1-11), auto-focus Ctrl+K (P1-13), inventory sort persistence (P1-14), service uptime (P1-15), expiry countdown badges (P1-16), sidebar reorder (P1-17), click-to-copy (P1-18), AI prompt presets (P1-20), tab badge counts (P1-04), keyboard shortcuts overlay (P1-03).

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
- **Scheduled reports system** — new `scheduled_reports` blueprint with background SITREP generator. Configurable schedule (1-168 hour interval). Report history with search/detail/delete. On-demand generation via `/api/reports/generate`. Schedule config via `/api/reports/schedule`. Background scheduler thread checks every 5 minutes, generates SITREP when due. Failed reports saved with `status: failed` for visibility.
- **`scheduled_reports` table** — report_type, title, content, context_snapshot, model, trigger (manual/scheduled), status, word_count, generated_at. 2 indexes.

### Tier 2 — High Differentiation
- **Shamir Secret Sharing vault** — pure-Python GF(256) implementation with no external dependencies. Split secrets into N shares with M-of-N reconstruction threshold. `/api/shamir/split` generates hex-encoded shares, `/api/shamir/reconstruct` recovers the original secret with hash verification. Metadata tracked in `shamir_shares` table (no secrets stored server-side). Supports labels, 2-10 threshold, up to 254 shares.
- **Warrant canary + dead-man's switch** — configurable signed statement with renewal interval (1-720 hours). `/api/canary` status endpoint detects expiry (dead-man trigger). `/api/canary/renew` resets the timer with new SHA-256 signature. `/api/canary/revoke` for duress signaling. Dead-man's switch actions configurable via `/api/canary/deadman-actions` (alert_federation, broadcast_message, lock_vault, export_data, clear_sensitive). All stored in settings table.

- **Reticulum / LXMF mesh transport** — new `services/reticulum.py` service manager. Pure-Python RNS integration with identity management (create/load keypair), LXMF message router (encrypted, delay-tolerant), peer discovery via announce, and incoming message callback with SSE broadcast. Comms blueprint mesh routes (`/api/mesh/*`) upgraded from stubs to real RNS transport: start/stop, announce, send via LXMF with direct + propagation fallback, peer listing from RNS destination table. Graceful degradation when `rns`/`lxmf` packages not installed — all routes return informative errors, no crashes.

### Tier 3 — Polish & Ecosystem
- **Codeplug builder** — full CRUD for radios, zones, channels. Import frequencies from `freq_database` into zones. CHIRP-compatible CSV export with zone names as comments. 3 new tables (`codeplug_radios`, `codeplug_zones`, `codeplug_channels`) + 3 indexes.
- **Propagation-aware HF scheduler** — 24-hour propagation schedule for 10 HF bands with season factor, solar flux index, and noise weighting. `/api/propagation/recommend` suggests best bands for current conditions with net schedule cross-reference.
- **Rainwater catchment calculator** — `/api/calculators/rainwater` takes roof area + rainfall → annual yield, recommended tank size (snaps to standard sizes), first-flush diverter volume, monthly surplus/deficit breakdown, material efficiency guide, self-sufficiency determination.
- **First-run setup wizard** — `/api/region/setup-status` returns 4-step checklist (location, data packs, threats, household) with per-step completion status and data pack install detail.

### Tier 4 — Field Operations
- **ICS-205 comms plan auto-builder** — `/api/ics/comms-plan` generates ICS-205 from radio equipment, freq_database, net schedules, and contacts. JSON + printable HTML (`/api/ics/comms-plan/print`). Auto-populates channels, equipment roster, operator list, net schedule.
- **SAR clue log + containment tracker** — `/api/sar/clues` CRUD with georeferencing. GeoJSON export for map overlay. Containment sector tracking with POD (probability of detection), searcher count, search type. 2 new tables (`sar_clue_log`, `sar_containment`) + 3 indexes.
- **Overland tire pressure + payload advisor** — `/api/calculators/tire-pressure` with 8 terrain types (highway through ice). Front/rear PSI split, payload capacity tracking, overload warning.
- **Maritime tide predictor** — `/api/calculators/tides` simplified lunar harmonic model. High/low tide times, spring/neap detection, moon phase. Includes navigation disclaimer.
- **Aviation density altitude** — `/api/calculators/density-altitude` with pressure altitude, density altitude (Koch chart), takeoff roll estimation, weight factor, runway adequacy check, safety warnings.

### Tier 5 — Specialized Threats
- **Gaussian plume estimator** — `/api/calculators/plume` Pasquill-Gifford atmospheric dispersion model (6 stability classes A-F). Calculates downwind centerline concentration at configurable distances. Returns sigma_y/sigma_z, plume width, mg/m3, ppm. Generates hazard corridor GeoJSON for map overlay.
- **Household epi line list + Rt tracker** — full CRUD `/api/epi/cases` with onset dates, symptoms, diagnosis, isolation tracking, exposure source. `/api/epi/rt` estimates reproduction number via ratio method with configurable window. `/api/epi/curve` for epidemic curve charting. New `epi_line_list` table.
- **Avalanche ATES calculator** — `/api/calculators/avalanche-ates` rates terrain to 3-class ATES from slope angle, terrain traps, forest cover. Aspect risk (N-face persistent slab), elevation band classification (alpine/treeline/below-treeline), essential gear list.
- **Chain-of-custody evidence ledger** — `/api/evidence` CRUD with SHA-256 integrity hash on collection. `/api/evidence/<id>/transfer` appends custody transfers (append-only JSON chain). `/api/evidence/<id>/verify` re-computes hash for tamper detection. New `evidence_ledger` table.
- **IOC tracker + ATT&CK mapping** — `/api/ioc` CRUD for 9 indicator types (IP, domain, URL, hash, email, CVE, etc.). MITRE ATT&CK tactic/technique/ID fields. `/api/ioc/attack-matrix` groups by tactic for heat-map. TLP classification. New `ioc_tracker` table + 3 indexes.

### Tier 6 — Homestead & Off-Grid Depth
- **Greywater branched-drain designer** — pipe sizing, mulch basin dimensions, soil infiltration rates (6 soil types), plant recommendations. Biocompatible soap guidance.
- **Humanure thermophilic tracker** — batch CRUD with temperature logging. Tracks thermophilic threshold (131°F for 3+ days). New `humanure_batches` table.
- **Wood BTU reference + heating calculator** — 20 wood species BTU/cord database. Heating needs calculator from sqft, insulation quality, HDD, stove efficiency. Cord estimate + cost range.
- **Passive solar sun-path** — hourly altitude/azimuth from lat/lng/date. Sunrise/sunset, solar noon, declination. Overhang sizing calculation for passive solar design.
- **Battery bank cycle-life model** — 6 chemistries (FLA, AGM, gel, LiFePO4, NMC, NiFe). Sizing from daily kWh + autonomy. Cycle life estimation with DOD correction. Cost per cycle.
- **Food preservation safety math** — curing salt calculator (Prague #1/#2, equilibrium brine) with FDA nitrite limits. Fermentation brine calculator with temperature guide.
- **Seed-saving isolation distance** — 17 crop reference with pollination method, isolation distance, viability years.
- **Beekeeping varroa calendar** — 12-month management calendar with latitude adjustment. 5 treatment methods with temperature windows. Mite count thresholds.
- **Livestock drug withdrawal timer** — 10 common drugs with meat/milk/egg withdrawal periods. Date calculator showing safe harvest dates and days remaining.

### Tier 7 — Health, Community & Family
- **Pediatric Broselow-equivalent dose engine** — 10 color zones (grey through tan), 7 drugs with weight-based dosing. Input by weight_kg or length_cm. Volume calculations from concentration. Max dose caps.
- **Chronic condition grid-down playbooks** — 6 conditions (T1/T2 diabetes, hypertension, asthma, epilepsy, hypothyroidism). Each with critical supplies, grid-down protocol, rationing strategy, substitutions.
- **Wilderness medicine decision trees** — 5 trees (wound assessment, chest injury, anaphylaxis, hypothermia, snakebite). Step-by-step yes/no clinical decision paths.
- **Child ID packet generator** — NCMEC-style CRUD with 14 fields (physical description, blood type, allergies, meds, identifying marks, fingerprint/photo refs, emergency contacts). New `child_id_packets` table.
- **Reunification cascade** — configurable plan with primary/secondary rally points, out-of-area contact, code words (safe/duress/evacuating), cascade order, meeting times.
- **Skill-transfer ledger** — CRUD tracking teacher→student knowledge transfer with proficiency levels and hours. Bus factor endpoint identifies single-point-of-failure skills. New `skill_transfers` table.

### Tier 8 — Deep Domain Expansions (selected)
- **OODA loop tracker** — CRUD for decision cycles with observe/orient/decide/act phases, outcome logging, cycle time tracking. New `ooda_cycles` table.
- **AAR template engine** — Army 4-question After Action Report (What was planned? What happened? Why? What next?). Sustains/improves lists, action items, participant roster. New `aar_reports` table.
- **Cynefin domain classifier** — 5-domain reference (Clear/Complicated/Complex/Chaotic/Confused) with guided classification from situational indicators.
- **Pack-animal load calculator** — 5 species (horse, mule, donkey, llama, goat) with max load, daily range, water/feed requirements, terrain factors.
- **Canoe/kayak portage planner** — weight distribution, back-and-forth walking distance, time estimate.
- **E-bike range calculator** — 4 terrain types, 5 assist levels, weight factor, battery runtime.
- **Dutch-oven coal calculator** — diameter-based coal count with top/bottom split for baking temperatures.
- **Altitude boiling + canning safety** — boiling point by elevation, canning PSI adjustment, cooking time factor.
- **Emergency fund tier calculator** — 6-tier (1-24 months) progress tracker with months-to-next-tier estimate.
- **Debt elimination calculator** — snowball and avalanche methods with month-by-month payoff simulation.
- **Shadow-stick compass** — step-by-step GPS-denied navigation with hemisphere-aware instructions.
- **Dead-reckoning error budget** — pace count + compass error → error circle radius. Terrain factors, navigation tips.

### Stats
- 5 data pack importers, 18 new tables, 21 new indexes, 105+ new routes. Tiers 1-8 substantially complete.

## [v7.43.0]

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
