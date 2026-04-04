# Project N.O.M.A.D.

## Multi-Agent Collaboration Rules

You are working in the same repo as another coding agent (Codex). Do not revert unrelated changes. Do not use `git reset --hard`, `git checkout --`, `git clean -fd`, or delete files just because they look untracked or generated. Read the current `git diff` before editing, keep changes scoped to the requested task, and avoid files already being touched unless necessary. If a file is already modified, preserve existing edits and work with them.

### Branch & Workflow
- `master` is current and synced with `origin/master`.
- Pull / re-read `git status` and `git diff` before each task.
- Commit small, focused changes. One logical change per commit.
- If both agents need the same file, let one finish first.
- Leave `tmp/` alone unless explicitly asked.

### Protected Files (Do Not Delete)
These are intentional repo assets, not junk:
- `package.json`, `package-lock.json` — frontend tooling
- `esbuild.config.mjs` — JS bundler config
- `playwright.config.mjs` — UI test config
- `tests/ui/shell-workflows.spec.mjs` — Playwright UI tests
- `tools/build_offline_atlas.py` — offline basemap generator
- `web/nukemap/data/offline_atlas.json` — shared offline atlas (NukeMap + VIPTrack)
- `web/viptrack/lib/` — vendored Leaflet + pako for VIPTrack (referenced by tracked index.html)
- `web/checklist_templates_data.py` — imported by `web/app.py`
- `docs/` — project documentation

---

## Overview
Cross-platform edition of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — the most comprehensive offline survival command center available. Runs on Windows, Linux, and macOS. No Docker required. 8 managed services (incl. FlatNotes), **Situation Room** (World Monitor-inspired global intelligence dashboard with RSS news feeds, USGS earthquakes, NWS severe weather, GDACS crisis events, crypto/commodity markets, AI briefings — all cached for offline), proactive + predictive AI alerts, AI SITREP generator + action execution + persistent memory, 21 interactive decision guides, 41 calculators, 56 quick reference cards, medical module (TCCC/triage/SBAR), training scenarios, food production, multi-node federation with community readiness + skill matching, power management with sensor charts, security cameras, AI document intelligence, built-in BitTorrent client, media library with 210 survival channels, 41-section user guide, task scheduler, 9 printable field documents (operations binder, wallet cards, SOI), serial hardware bridge, mesh radio support, CSV import wizard with 5 inventory templates (155 items), PWA with offline caching, UI zoom control, sidebar sub-menus, and a premium dark dashboard with 5 themes (incl. E-Ink).

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2 on Windows, WebKit on macOS, GTK on Linux)
- **SQLite** — 89 tables, WAL mode, 30s timeout, FK enforcement, SQLite backup API, 120 performance indexes
- **CSS** — External files: `web/static/css/app.css` (base) + `web/static/css/premium.css` (polish layer)
- **Native process management** — subprocess for Ollama, kiwix-serve, Kolibri; threading HTTP server for CyberChef
- **pystray** — system tray icon for background operation
- **psutil** — system info (CPU via background monitor thread, RAM, GPU detection, disk devices)
- **MapLibre GL JS + PMTiles** — bundled locally (no CDN dependencies)
- **NukeMap v3.2.0** — 18 JS modules + Leaflet (bundled locally)
- **epub.js** — EPUB reader (bundled locally, `web/static/js/epub.min.js`)
- **yt-dlp** — video/audio downloader (auto-installed to services dir)
- **FFmpeg** — audio conversion (optional, auto-installed for MP3 extraction)
- **libtorrent** — built-in BitTorrent client for survival content torrents

## Project Structure
```
nomad.py              # Entry point — Flask + pywebview + tray + health monitor + service autostart
platform_utils.py     # Cross-platform abstraction — subprocess flags, paths, GPU detection, URLs, process management
db.py                 # SQLite init (89 tables), indexes, migrations (migrations BEFORE indexes), db_session() context manager
config.py             # Data directory management (atomic writes via tmp+replace, XDG-aware paths, mtime-cached reads)
build.spec            # PyInstaller spec for portable exe
icon.ico              # App icon (multi-size, 16-256px)
installer.iss         # Inno Setup installer script
ROADMAP.md            # 22-phase implementation plan (all complete)
.github/workflows/
  build.yml           # CI/CD — PyInstaller + Inno Setup, dual artifact release on tag push
web/
  app.py              # Flask routes (~566 endpoints) — ~17,500 lines
  translations.py     # i18n translations (10 languages, 56 keys per language)
  catalog.py          # Content catalogs (books, videos, audio, torrents)
  static/
    css/
      app.css         # Base styles (~2392 lines) — 5 themes (incl. E-Ink), design system tokens, layout, components, responsive breakpoints (480/768/900/1280/1440/2560px), UI zoom levels, battery saver, mobile bottom nav, RTL support, widget config styles
      premium.css     # Premium polish (~584 lines) — tactical typography, hazard stripes, micro-interactions
    logo.png          # App logo
    maplibre-gl.js    # Map renderer (bundled)
    maplibre-gl.css   # Map styles (bundled)
    pmtiles.js        # Tile format handler (bundled)
    js/
      epub.min.js     # EPUB reader library (bundled)
  routes_advanced.py  # Advanced routes (phases 16-20): AI SITREP, actions, memory, print binder/wallet/SOI, system health, undo, federation community
  templates/
    index.html        # HTML + inline theme vars + JS (~28,500 lines)
  nukemap/            # NukeMap v3.2.0 — index.html, 18 JS modules, CSS, data/, lib/leaflet
tests/
  conftest.py           # pytest fixtures — Flask test_client with isolated tmp_path SQLite DB
  test_inventory.py     # 18 tests — CRUD, search, filter, summary, shopping list, checkout
  test_notes.py         # 14 tests — CRUD, pin, tags, journal, markdown export
  test_contacts.py      # 8 tests — CRUD, search by name/callsign/role
  test_conversations.py # 14 tests — CRUD, rename, delete-all, search, branching, export
  test_weather.py       # 9 tests — weather log CRUD, readings, trend, Zambretti predict
  test_medical.py       # 14 tests — patients CRUD, vitals, wounds, drug interactions, triage, TCCC
  test_checklists.py    # 8 tests — CRUD, templates, summary counts
  test_core.py          # 11 tests — services, alerts, activity, version, 404, settings
  test_radio.py         # 8 tests — frequencies CRUD, radio profiles, propagation
  test_maps.py          # 11 tests — waypoints CRUD, routes, elevation profile
  test_garden.py        # 18 tests — zone, plots, seeds, harvests, companions, calendar, pests
  test_supplies.py      # 14 tests — fuel, equipment, ammo CRUD + summaries
  test_benchmark.py     # 6 tests — status, history, results, storage benchmark
  test_kb.py            # 7 tests — KB documents, status, search, CSV import
  test_medical_reference.py # 11 tests — 15 reference categories, search endpoint
  test_skills.py        # 7 tests — skills CRUD + validation + seed defaults
  test_community.py     # 8 tests — community resources CRUD, float validation
  test_radiation.py     # 5 tests — radiation CRUD, cumulative tracking, clear
  test_ocr_pipeline.py  # 8 tests — OCR pipeline status/start/stop/scan, KB workspaces
  test_validation.py    # 5 tests — fuel/equipment validation, CSV injection, upload limit
  test_incidents.py     # 11 tests — incidents CRUD, filter, clear
  test_tasks.py         # 14 tests — scheduled tasks CRUD, complete, recurrence, due
  test_vault.py         # 12 tests — encrypted vault CRUD, crypto field validation
  test_livestock.py     # 8 tests — livestock CRUD, health log
  test_scenarios.py     # 8 tests — scenarios CRUD, complication fallback, AAR
  test_timers.py        # 7 tests — timers CRUD, remaining/done computation
  test_power.py         # 14 tests — power devices, log, dashboard, history, autonomy
  test_cameras.py       # 5 tests — security cameras CRUD
  test_data_summary.py  # 8 tests — data summary, global search across entities
services/
  manager.py          # Process manager — download (with resume), start, stop, track, uninstall; register_process() for thread-safe tracking; stdout/stderr log capture per service; wait_for_port(), is_healthy() with HTTP probing, SERVICE_HEALTH_URLS
  ollama.py           # Ollama AI
  kiwix.py            # Kiwix
  cyberchef.py        # CyberChef
  kolibri.py          # Kolibri education
  qdrant.py           # Qdrant vector DB
  stirling.py         # Stirling PDF
  flatnotes.py        # FlatNotes — markdown note-taking app (pip install in venv)
  torrent.py          # BitTorrent client (libtorrent) — singleton TorrentManager, thread-safe
```

## Version
v1.0.0 — ~51,300 lines across 6 core files (app.py ~17,500 + index.html ~28,500 + app.css 2,392 + premium.css 717 + db.py 1,455 + translations.py 368), 600+ API routes (17 blueprints incl. situation_room), 95+ DB tables (135+ indexes), ~340 seeded radio frequencies, 8 managed services, 25 prep sub-tabs, 42 calculators, 56 reference cards, 21 decision guides, 38-section user guide, 850+ JS functions, 338 automated pytest tests (34 test files), 10 supported languages, persistent AI copilot dock (all tabs) with model cards + multimodal image input + conversation branching + source citations, SSE real-time alert push (/api/alerts/stream) with polling fallback, context-aware decision trees with live inventory/contacts data, allergy-aware dosage calculator (8 drugs, patient cross-check, pediatric dosing), watch/shift rotation planner with printable schedules, 6 inventory templates (185 items), Zambretti offline weather prediction with pressure graphing + weather-triggered alerts, inventory barcode/QR + lot tracking + check-in/out + photo attachments + auto-shopping list, DTMF tone generator + NATO phonetic trainer + antenna calculator + HF propagation prediction, wiki-links + backlinks + templates + attachments + daily journal in notes, media resume playback + chapter navigation + playlists + auto-thumbnails + subtitle support + metadata editor + Continue Watching, interactive TCCC MARCH flowchart + vital signs trending + expiring meds tracker + 15-category searchable medical reference, KB workspaces, companion planting (20 pairs) + pest guide (10 entries) + seed inventory, map measurement + print + style switcher + GPX + elevation profile graph + saved routes panel, AI inference + storage + network benchmarks, LAN chat channels + AES-GCM encryption + presence indicators + peer file transfer, mesh node map overlay, bento grid home + sidebar group labels + status pills + customize panel, v5.0 roadmap 98% complete (65/66 features)

## Audit History (8 rounds)
- **v1.8.0 — Security**: Auth deny-on-failure, thread-safe install lock, path traversal hardening (normpath+startswith on maps/ZIM delete), DB try-finally on all 7 services, stirling stderr crash fix, race conditions (window handler before thread, health monitor MAX_RESTARTS), Flask startup error feedback
- **v1.9.0 — Frontend+DB**: resp.ok on AI warmup, debounced media/channel filters (200ms), try-catch loadNotes, SQLite backup API (WAL-safe), 30s connection timeout, FK enforcement, 10 new indexes, division-by-zero guard on critical_burn
- **v2.0.0 — Performance**: requestAnimationFrame debounce on streaming chat rendering, insertAdjacentHTML for mesh/LAN log (O(1) vs O(n^2)), content-summary 4 queries→1, fetch error handlers on map/vault delete, notes CRUD try-finally
- **v2.1.0 — Input Validation**: Safe int/float with try-except on ammo/fuel/radiation routes, NULL coalescing on cumulative_rem, harvest quantity >= 0 validation, search escapeAttr+parseInt, timer resp.ok, calculator tab try-catch (30 init calls)
- **v2.1.0 — Deep Audit**: teardown_appcontext DB safety net, PATCH endpoint ALLOWED_COLS pattern, set_version() XSS sanitization, safeFetch() utility + Promise.allSettled, CSS cleanup (--glass/--purple removed, focus states), CyberChef stale server cleanup, config.py specific exception types, manager.py thread locks on _processes dict + partial download cleanup, torrent.py session/monitor race condition fixes, +18 DB performance indexes (35→53), content catalogs: 210 channels, 131 videos, 102 audio, 141 books, 152 torrents
- **v2.2.0 — Ops Platform Phase 1-3**: Dashboard mode system (Command Center/Homestead/Essentials — sidebar/prep reordering, mode-aware widget sets), Live situational dashboard (/api/dashboard/live aggregates 12 modules, 12 widget types, auto-refresh 30s), AI copilot integration (quick-query with real inventory/contacts/medical/fuel/ammo data, suggested actions from alerts/expiring/overdue, pre-built question buttons on dashboard)
- **v2.3.0 — Ops Platform Phase 4+9**: Cross-module intelligence (9 survival need categories with keyword matching — Water, Food, Medical, Shelter, Security, Comms, Power, Navigation, Knowledge; /api/needs overview + /api/needs/<id> detail; needs grid on Home with drill-down modal showing supplies+contacts+books+guides), Print field copies (frequency reference card with standard freqs + team contacts, wallet-sized medical cards per patient, bug-out grab-and-go checklist with rally points)
- **v2.4.0 — Ops Platform Phase 5-7**: Enhanced maps (map_routes + map_annotations tables, route CRUD, annotation CRUD, minimap-data endpoint, 12 waypoint category icons with elevation tracking), Communications upgrade (freq_database table seeded with 35 standard frequencies — FRS/GMRS/MURS/2m/70cm/HF/Marine/CB/NOAA/Meshtastic, radio_profiles CRUD, comms dashboard API), Medical EHR upgrade (triage_events + handoff_reports tables, patient triage_category + care_phase columns, wound tourniquet_time + intervention_type columns, triage board API, SBAR handoff report generator with print, TCCC MARCH protocol endpoint)
- **v3.0.0 — Ops Platform Phase 8+10**: Instrumented power & food (sensor_devices + sensor_readings tables, sensor CRUD + time-series query with period filtering, power history charting endpoint, autonomy forecast based on SOC/load/solar trends; planting_calendar table seeded with 31 zone 7 entries including yield_per_sqft and calories_per_lb, garden yield analysis with caloric output and person-days calculation, preservation_log CRUD for canned/dried/frozen tracking), Federation v2 (federation_peers with trust levels observer/member/trusted/admin, federation_offers + federation_requests for resource marketplace, federation_sitboard for aggregated situation from peers, network-map endpoint linking peers to waypoints, auto_sync flag per peer, trust-level CRUD)
- **v3.2.0 — Deep Bug Hunt (31 fixes)**: SQL injection in sync-receive (column name validation), NameError on catalog import, UnboundLocalError in media favorite toggle, PMTiles OOM (streaming), path traversal Windows case bypass (normcase), radiation total_rem logic fix, escapeAttr single-quote XSS, duplicate formatBytes removal, connection-lost banner null crash, 5 missing safeFetch wrappers, duplicate Ctrl+K handler, bare digit shortcut removal, night mode theme fight fix, saveConversation title overwrite, atomic config writes, init_db connection leak, download resume fix (keep partials), _restart_tracker thread safety, register_process() API (all 5 service modules), torrent session null-deref races, health monitor 90s grace period
- **v3.2.0 — Home Screen Overhaul**: Reorganized Home tab from 17 unstructured sections into 6 logical groups: (1) Welcome/Getting Started at top, (2) Search + Live Dashboard widgets, (3) Readiness Score + Needs Grid side-by-side, (4) AI Copilot, (5) Services section with inline Start/Stop All, (6) Quick Navigation + Printable References in collapsible `<details>`, (7) Activity Log collapsible. Removed redundant cmd-dashboard (duplicated live widgets), feature card grid collapsed into compact nav, print buttons moved into collapsible section. Added responsive two-column CSS for readiness+needs
- **v3.2.0 — Cross-Platform Port**: New `platform_utils.py` abstraction layer (~320 lines). Converted all 13 Python files from Windows-only to cross-platform. Subprocess `creationflags` guarded via `popen_kwargs()`/`run_kwargs()`. Hardcoded `.exe` replaced with `exe_name()`. `os.startfile` → `open_folder()`. `ctypes.windll` → `pid_alive()`. PowerShell port queries → `find_pid_on_port()` (uses `lsof`/`ss` on Linux). GPU detection via `lspci` on Linux. Config/data paths use XDG on Linux, `~/Library/Application Support` on macOS. All service download URLs platform-aware via `_get_*_url()` functions. pywebview GUI backend auto-detected per platform
- **v3.3.0 — Original Feature Parity**: Added all missing features from the original Docker-based N.O.M.A.D. to match full parity:
  - **FlatNotes service** (`services/flatnotes.py`) — markdown note-taking app installed via pip in venv, port 8890, auth disabled for local use, auto-creates data directory
  - **Unified download queue** (`/api/downloads/active`) — aggregates all active downloads (services, ZIMs, maps, AI models) into single view with real-time progress; auto-polling banner on Home tab (5s interval)
  - **Service process logs** — `manager.py` captures stdout/stderr from all managed services via PIPE+reader threads into `_service_logs` ring buffer (500 lines/service); UI in Settings with service selector dropdown
  - **Content update checker** (`/api/kiwix/check-updates`) — compares installed ZIM filenames against catalog by prefix to detect newer dated versions; one-click update download
  - **Wikipedia tier selection UI** — dedicated card on Library tab showing all Wikipedia editions (Mini 1.2MB → Full 115GB) with size, description, tier color coding, and install status
  - **Self-update system** (`/api/update-download`, `/api/update-download/status`, `/api/update-download/open`) — checks GitHub releases for platform-specific assets (exe/AppImage/dmg), downloads to temp with progress polling, opens containing folder; UI in Settings About section
  - **Cross-platform startup toggle** — replaced Windows-only `winreg` with platform-aware implementation: Windows registry, macOS LaunchAgent plist, Linux XDG autostart `.desktop` file
  - `find_system_python()` added to `platform_utils.py` for frozen app venv creation
- **v4.0.0 — Full Roadmap Implementation (Phases 13-22)**: All 10 remaining roadmap phases built:
  - **Phase 13 (Hardware)**: Serial port bridge (`/api/serial/ports`, connect, disconnect, status) with pyserial auto-detect + fallback; sensor time-series chart endpoint (`/api/sensors/chart/<id>`) with range aggregation (raw/hour/day/week); Canvas 2D chart UI in Power sub-tab
  - **Phase 14 (Mesh)**: Meshtastic bridge stub (`/api/mesh/status`, messages, nodes) with local message storage; comms status board (`/api/comms/status-board`) aggregating LAN/mesh/federation/radio; `mesh_messages` table added; comms status board UI in Radio sub-tab
  - **Phase 15 (Scheduling)**: Task scheduler engine (`/api/tasks` CRUD + `/api/tasks/<id>/complete` with auto-recurrence + `/api/tasks/due`); sunrise/sunset NOAA calculator (`/api/sun`); predictive alerts (`/api/alerts/predictive`) analyzing burn rates, expiry, overdue maintenance; `scheduled_tasks` table added; task manager UI in Settings; sun widget in live dashboard; predictive alerts integrated into alert bar
  - **Phase 16 (Advanced AI)**: AI SITREP generator (`/api/ai/sitrep`) queries 24h data and generates military-format report; AI action execution (`/api/ai/execute-action`) parses natural language commands; AI memory (`/api/ai/memory`) persists key facts across conversations; SITREP button in Command Post; memory panel in AI Chat header
  - **Phase 17 (Data Import)**: CSV import wizard (`/api/import/csv` + `/api/import/csv/execute`) with column mapping UI and 7 target tables; 6 inventory templates (`/api/templates/inventory`) with 185 realistic prepper items (72hr Kit, Family 30-Day, Bug-Out Bag, First Aid, Vehicle Emergency, Medical Bag); QR code generation (`/api/qr/generate`); CSV import modal in Settings; template dropdown in Inventory
  - **Phase 18 (Print)**: Operations binder (`/api/print/operations-binder`) — complete multi-page HTML document with TOC, contacts, frequencies, medical cards, inventory, checklists, waypoints, procedures; wallet cards (`/api/print/wallet-cards`) — 5 lamination-ready cards (ICE, blood type, medications, rally points, frequencies); SOI generator (`/api/print/soi`) — classified-style signal operating instructions; print buttons in Settings
  - **Phase 19 (Reliability)**: Database integrity check (`/api/system/db-check`) runs PRAGMA integrity_check + foreign_key_check; vacuum/reindex (`/api/system/db-vacuum`); startup self-test (`/api/system/self-test`) checks DB, disk, services, ports, Python, critical tables; undo system (`/api/undo` GET/POST) with 10-entry deque and 30s TTL; system health panel in Settings
  - **Phase 20 (Community)**: Community readiness dashboard (`/api/federation/community-readiness`) aggregates per-node readiness across 7 categories; skill matching (`/api/federation/skill-search`) searches contacts+federation+community; distributed alert relay (`/api/federation/relay-alert`) POSTs to all trusted peers
  - **Phase 21+22 (Mobile + Platform)**: PWA manifest (`manifest.json`) + service worker (`sw.js`) with network-first API strategy and cache-first static strategy; offline fallback for index page; `/sw.js` route for service worker scope; `<meta name="theme-color">` for mobile Chrome
- **v4.0.0 — Bug Fixes & Integration**: AI memory injected into main chat system prompt + quick-query copilot; predictive alerts badge count includes predictions + severity-aware coloring; inventory form inputs cleared on close; database restore from automatic backups (`/api/backups`, `/api/backups/restore`) with UI modal in Settings; emergency sheet enhanced with scheduled tasks + AI memory sections; 3 new help guide sections (Task Scheduler, AI Memory, Printable Field Documents — guide now 41 sections); `clearRadiation()` and `clearIncidents()` now require `confirm()` dialog
- **v4.0.0 — UX/UI Navigation Overhaul**:
  - **Prep sub-tabs reorganized**: 25 flat tabs → 5 category groups (Supplies, People, Readiness, Knowledge, Operations) with two-tier navigation; `PREP_CATEGORIES` JS object + `showPrepCategory()` + `_findCategoryForSub()`; dashboard widget clicks auto-switch to correct category
  - **Sidebar sub-menus**: Home (Services, Field Documents, Activity Log), Library (Wikipedia, Content Catalog, Documents), Media (Channels, Videos, Audio, Books, Torrents), Preparedness (Inventory, Contacts, Medical, Checklists, Guides), Settings (AI Models, Tasks, System Health); auto-show on active tab, `scrollToSection()` helper for smooth navigation
  - **Inventory toolbar decluttered**: essential actions always visible (filter, search, add, quick-add); advanced actions (templates, shopping list, daily consume, import/export) in collapsible `<details>` section
  - **Medical vitals input**: 9-field single-row flex → 4-column grid in collapsible `<details>`, full-width inputs
  - **Settings preferences split**: core settings always visible; system/backup/data settings in collapsible section
  - **Home Quick Navigation replaced**: removed 7 redundant tab-duplicate cards; replaced with "Printable Field Documents" section (6 document cards)
  - **Tour system updated**: 4 steps → 6 steps with Preparedness category explanation and Maps step
  - **Calculator search**: filter box at top of Calculators sub-tab, searches against card text content
  - **YouTube channel browse**: auto-installs yt-dlp with progress when not present, instead of showing cryptic error
- **v4.0.0 — CSS Design System**:
  - **Typography scale**: 7-step token system (`--text-xs` through `--text-2xl`)
  - **Spacing scale**: `--sp-1` through `--sp-8` (4px base unit), `--card-pad`, `--card-pad-sm`
  - **UI zoom control**: 4 levels via `html[data-zoom]` + `--ui-zoom` CSS variable; setting in Preferences, persists in localStorage
  - **Responsive breakpoints**: added 768px, 1280px, 1440px, 2560px breakpoints (was only 480px/900px)
  - **Unified input focus**: all form inputs get consistent `border-color` + `box-shadow` on focus
  - **Keyboard accessibility**: `focus-visible` outlines on all buttons, cards, tabs, links, prep category buttons, prep sub-tabs
  - **Link hover**: underline on hover (was missing), focus outline
  - **Scrollbar consistency**: resolved 4px/5px conflict between app.css and premium.css (both 5px now)
  - **Reduced motion**: `@media (prefers-reduced-motion)` disables all animations
  - **Collapsible `<details>` polish**: chevron rotation animation, hidden native marker, hover accent color, `focus-visible` outline
  - **Settings row breathing**: 8px padding + subtle separator borders between rows
  - **Late-binding wrapper eliminated**: `_origSwitchPrepSub` pattern merged into main `switchPrepSub()` function

- **v4.0.0 — Bug Audit & Infrastructure Improvements (6 fixes, 9 improvements)**:
  - **Bug fixes**: (1) `api_ai_quick_query` iterated `ollama.chat(stream=False)` dict as if streaming lines — fixed to extract response directly; (2) `torrent.py add_magnet()` deadlocked — `_get_session()` acquires `self._lock` internally but was called inside `with self._lock:` (non-reentrant Lock), also used `self._session` instead of local `ses` variable; (3) `routes_advanced.py` AI action regex matched against `action.lower()` then `.title()`-cased results, destroying original casing ("AAA Batteries" → "Aaa Batteries") — now uses `re.IGNORECASE` on original text; (4) `qdrant.py` and `stirling.py` `start()` had no `running()` guard, allowing duplicate process spawning that orphans the first PID; (5) `platform_utils.py pid_alive()` on Windows only checked `OpenProcess` success (returns true for exited processes) — now checks `GetExitCodeProcess` against `STILL_ACTIVE (259)`
  - **db.py**: Added `db_session()` context manager for safe DB connection handling (`with db_session() as db:`); improved `log_activity` to `_log.debug()` failures instead of bare `except: pass`; added 11 missing performance indexes (`activity_log(event)`, `activity_log(service, created_at)`, `documents(status)`, `documents(doc_category)`, `inventory(name)`, `triage_events(status)`, `handoff_reports(patient_id, created_at)`, `patients(triage_category)`, `vault_entries(created_at)`, `services(installed, running)`)
  - **config.py**: Added mtime-based config caching — `load_config()` now caches parsed JSON and only re-reads from disk when file mtime changes (eliminates filesystem read+JSON parse on every `get_data_dir()` call, which is hit on every DB connection). Added `get_config_value(key, default)` helper. Cache invalidated on `save_config()`.
  - **nomad.py**: Replaced `FileHandler` with `RotatingFileHandler` (5 MB max, 3 backups) to prevent unbounded log growth. Extracted `LOG_FORMAT` constant to avoid duplication.
  - **manager.py**: Added `wait_for_port(port, timeout, interval)` utility for reuse across services. Added `is_healthy(service_id)` with HTTP health endpoint probing (`SERVICE_HEALTH_URLS` dict mapping service IDs to health URLs). Added shutdown timeout warning log when `proc.wait(10)` expires.
  - **ollama.py**: `chat()` now catches `requests.ConnectionError` ("AI service is not running"), `requests.Timeout` ("AI request timed out"), and HTTP 404 ("Model not found. Pull it first") with descriptive `RuntimeError` messages instead of raw exceptions.
  - **web/app.py**: Added global `@app.errorhandler(Exception)` and `@app.errorhandler(404)` for consistent JSON error responses on `/api/` routes. Extracted `build_situation_context(db)`, `get_ai_memory_text()`, and `_safe_json_list()` shared helpers — eliminated ~100 lines of duplicated AI context-building code between `api_ai_chat` and `api_ai_quick_query`. Fixed 36 bare `db.close()` calls (no `try/finally`) to prevent connection leaks on exceptions.

- **v4.1.0 — UX Facelift & Customization**:
  - **Premium spacing overhaul**: 28 edits to `app.css`, 14 edits to `premium.css`, 15 edits to `index.html` — increased padding/gaps across all cards (service +4px, settings +4px, gauge +4px, CC +4px), container padding 24×32→32×40, sidebar nav gap 2→4px, all grid gaps +4px, section margins 12-16→20-28px. New spacing CSS variables (`--gap` 12→16, `--pad` 16→20)
  - **Sidebar group labels**: Nav items organized under `OVERVIEW`, `INTEL`, `FIELD OPS`, `SYSTEM` section headers (`.sidebar-group-label` class, monospace uppercase with gradient underline)
  - **Bento grid home layout**: Replaced linear vertical stack with asymmetric 2-column grid (`3fr 2fr`). Row 1: Situation Dashboard + Needs Overview side-by-side. Services section full-width. Row 2: Field Documents + Activity Log side-by-side in card containers
  - **Status strip pills**: Plain text stats → pill-shaped chips (`.ss-pill`) with colored status dots that update dynamically (green=healthy, orange/red=attention). Dots use `box-shadow: 0 0 4px currentColor` glow
  - **AI Copilot dock**: Moved from inline home section to persistent fixed bottom bar (`position:fixed;bottom:0;left:240px`). Available on ALL tabs. Slim input bar, answer slides up when active. Backdrop blur, shadow separation. Old `copilot-strip` removed
  - **Service card status variants**: `.svc-running` (green left border), `.svc-stopped` (gray left border), `.svc-not-installed` (dashed border, 75% opacity, full on hover)
  - **Needs progress bars**: Thin 3px progress bar at bottom of each need card showing coverage percentage. Color-coded green/orange/red
  - **Readiness tab**: New dedicated tab with heartbeat icon. Readiness Score moved off home page (no more red "F" on first launch). Page has larger grade display (48px), action cards linking to Preparedness, coverage grid
  - **Customize panel**: Right-side slide-out panel (420px, backdrop blur overlay) triggered from sidebar footer button. Sections: Theme (4-card visual grid), Interface Scale (4 zoom levels), Dashboard Mode (3 illustrated options), Sidebar Navigation (11 toggle switches to show/hide any tab), Home Page Sections (8 toggle switches for search/dashboard/needs/services/docs/activity/copilot/status-strip). All persisted to `localStorage('nomad-customize')`. Reset to defaults button. Escape key closes panel
  - **Emoji icon fix**: 9 survival need icons in `SURVIVAL_NEEDS` dict changed from HTML entities (`&#128167;`) to Unicode escapes (`\U0001F4A7`) — entities were double-escaped by `escapeHtml()` in JSON→HTML pipeline
  - **Audit fixes (135+ issues)**: 19 hardcoded `'Cascadia Code'` fonts → `var(--font-data)`. 9 inline section headers → `.section-header-label` CSS class. 2 `onmouseover/onmouseout` → `.hover-reveal` CSS class. 10 list item paddings standardized (convo/note/prep/activity/incident/check/catalog/media items all +2-4px). 11 CSS utility classes added (`.mb-12` through `.mb-24`, `.gap-10/12/16`, `.p-12/16/20`). Smooth scroll (`scroll-behavior:smooth`). Focus ring consistency on all new components. Empty state polish (48px icons, centered text). Card entrance stagger (7-slot animation delay). Bento skeleton loader with shimmer
  - **New CSS components**: `.sidebar-group-label`, `.ss-pill`, `.bento-grid`, `.copilot-dock`, `.svc-running/stopped/not-installed`, `.need-progress`, `.section-collapse-btn`, `.hover-reveal`, `.customize-panel/overlay/section/row/theme-grid/theme-card/sortable-item`, `.toggle-switch/slider`, `.sidebar-customize-btn`, `.section-header-label`, `.bento-skeleton`
  - **ROADMAP-v5.md**: 12-phase feature expansion roadmap based on competitive analysis of 40+ open source projects. Covers AI (GPT4All-style LocalDocs, conversation branching), KB (LanceDB replacement, hybrid search), Inventory (barcode scanning, lot tracking), Maps (OSRM offline routing, GPX), Notes (wiki-links, tags), Media (resume playback, chapters), Medical (drug interactions, TCCC flowchart), Radio (Meshtastic serial, freq database), Weather (Zambretti prediction), LAN (file transfer, channels), Garden (planting calendar), Benchmark (AI inference speed)

- **v4.4.0 — Feature Expansion & Bug Fixes**:
  - **SSE real-time alerts** — `/api/alerts/stream` Server-Sent Events endpoint with per-client `queue.Queue(maxsize=50)`, 30s heartbeat, auto-cleanup on disconnect; `_notify_alert_subscribers()` fires on new alerts, dismiss, and dismiss-all; frontend `connectAlertSSE()` with automatic fallback to 60s polling on error
  - **Context-aware decision trees** — `/api/guides/context` returns live inventory by category + contacts by role + summary (medic, comms officer auto-detect); `enrichGuideText()` replaces `{inv:category}`, `{medic_name}`, `{comms_officer}`, `{contact:role}`, `{water_count}` placeholders; context strip shows resources while navigating guides; water_purify + wound_assess guides updated with placeholders
  - **Allergy-aware dosage calculator** — `DOSAGE_GUIDE` with 8 drugs (Ibuprofen, Acetaminophen, Diphenhydramine, Amoxicillin, Loperamide, Aspirin, ORS, Prednisone); `POST /api/medical/dosage-calculator` checks patient allergies against contraindications, current medications against DRUG_INTERACTIONS, validates minimum age, calculates weight-based pediatric doses; `GET /api/medical/dosage-drugs`; UI with drug/patient selectors, age/weight inputs, color-coded warnings
  - **Watch/shift rotation planner** — `watch_schedules` table + `idx_watch_schedules_start` index; `/api/watch-schedules` CRUD with auto-rotation generation (configurable 1-24h shifts); `/api/watch-schedules/<id>/print` printable HTML; UI with form, schedule list, detail view, print button
  - **Medical bag inventory template** — 30-item IFAK+ template (CAT tourniquets, chest seals, hemostatic gauze, NPAs, SAM splints, pulse oximeter, BP cuff, stethoscope, 8 medications); total 6 templates, 185 items
  - **Bug fixes**: radiation cumulative tracking used `ORDER BY created_at DESC` which failed on rapid inserts with identical timestamps → fixed to `ORDER BY id DESC`; checklist test isolation fix (`data[0]` → filter by name)

- **v4.5.0 — Feature Expansion (Batch 2)**:
  - **Wound photo upload** — `POST /api/patients/<pid>/wounds/<wid>/photo` multipart file upload with path traversal protection; JSON array of photo paths per wound; side-by-side comparison modal in UI; camera icon badges on wound entries
  - **Weather-triggered action rules** — `weather_action_rules` table + `idx_weather_action_rules_enabled` index; `/api/weather/action-rules` CRUD + `/api/weather/action-rules/evaluate`; `_evaluate_weather_action_rules(db)` internal helper with 6 condition types (temp_above/below, wind_above, pressure_below, humidity_above, precip_above); seed rules on first load; rule management UI with evaluate button
  - **Entity auto-populate** — `POST /api/kb/documents/<id>/import-entities` imports extracted entities to structured tables: person→contacts, medication→inventory, coordinates→waypoints; "Import Entities to Database" button in KB document detail UI
  - **Medical reference flipbook** — `/api/print/medical-flipbook` in `routes_advanced.py`; 8-page printable HTML field reference (vital signs, GCS scale, TCCC MARCH, drug dosages, wound care, burns, anaphylaxis, CPR, fractures, hypothermia, environmental emergencies, SBAR format, 9-line MEDEVAC); buttons on Home + Settings print sections
  - **Conversation branching** — "What If?" fork button on AI responses; `forkWhatIf()`, `switchToBranch()`, `returnToMainConversation()` JS functions; branch panel with visual indicators; branch count in conversation list; `.whatif-btn`, `.branch-banner`, `.branch-panel`, `.convo-branch-badge` CSS
  - **XSS fix**: patient care card allergies/medications/conditions escaped via `_esc()` helper
  - **DB connection leak fix**: alert engine `get_db()` calls wrapped in try/finally with cleanup in except handler
  - **Query limits**: Added LIMIT clauses to 10+ unbounded queries (burn_items 50, low_stock 50, wound_log 100, predictive alerts 200, guides context 500/200)

- **v4.6.0 — Batch 3: UX, Accessibility, Map Overlays**:
  - **WCAG 2.1 AA accessibility** — skip-nav link, `role="main"` on content area, `aria-live="polite"` on toast notifications, `focus-visible` outlines on all interactive elements, `prefers-reduced-motion` media query in base CSS
  - **Crash recovery** — `FormStateRecovery` utility: auto-saves inventory/contact/patient form state to localStorage (500ms debounce), 24h staleness expiry, recovery toast on restore, auto-clear on submit/cancel
  - **Mobile bottom tab bar** — `<nav id="mobile-tab-bar">` with 5 tabs (Home, Prep, Map, AI, More); "More" slide-up panel with 7 remaining sections in 3-column grid; `@media (max-width: 768px)` hides sidebar, shows bottom bar, adds safe-area padding
  - **Garden map overlay** — `GET /api/garden/plots/geo` GeoJSON endpoint; `PUT /api/garden/plots/<id>` update route; `lat`/`lng`/`boundary_geojson` columns on `garden_plots`; MapLibre fill+outline+circle+label layers; polygon drawing tool (click to add vertices, double-click to finish); toggle button on map toolbar
  - **Supply chain visualization** — `GET /api/federation/supply-chain` GeoJSON endpoint with peer nodes + trade route lines; `lat`/`lng` columns on `federation_peers`; peer circles color-coded by trust level (observer=gray, member=blue, trusted=green, admin=gold); trade route dashed lines between peers with matching offer↔request; popups with offers/requests detail; toggle button on map toolbar
  - **Audit fixes** — SQL injection in undo system (column names now validated against `PRAGMA table_info`); XSS in wiki-link onclick (stripped `\\'"&<>` from titles); unescaped `d.speed`/`d.percent` in download queue HTML (now `escapeHtml()`); SITREP unbounded queries (added LIMIT 50 to low_stock, expired, inv_summary); error message no longer leaks exception details

- **v4.7.0 — Batch 4: AI, Federation, Mobile Sensors, Notifications**:
  - **Multi-document RAG with citations** — Enhanced KB RAG injection to track source documents (filename, doc_id, relevance score, excerpt); citations sent as first SSE chunk before streaming response; `formatRAGCitations()` renders clickable source badges with relevance percentage; `viewKBDocument()` navigates to Library→Documents; KB badge suppressed when citations already shown
  - **Mutual aid agreements** — `mutual_aid_agreements` table (14 columns: peer info, commitments as JSON, status, signatures, dates); 5 CRUD endpoints (`/api/federation/mutual-aid` GET/POST, `/<id>` PUT/DELETE, `/<id>/sign` POST); dual-signature workflow (signed_by_us + signed_by_peer → auto-activate); activity logging on create/sign
  - **Compass & inclinometer** — Tools tab card with CSS compass rose (needle, N/S/E/W labels), heading in degrees + 16-point cardinal direction, pitch/roll inclinometer; `DeviceOrientationEvent` API with iOS permission request; 3-second fallback message if no sensor data
  - **Push notifications** — Enhanced SSE alert handler to fire notifications when page is hidden/backgrounded; service worker `message` listener for `push-alert` type with `showNotification()` (icon, badge, tag, renotify, requireInteraction); `notificationclick` handler focuses existing app window or opens new one

- **v5.3.0 — Wave 1+2: Solar, Backups, Analytics, A11y, Widgets, SSE, i18n**:
  - **Solar forecast** — `_calculate_solar()` helper with declination/air mass/cloud factor; `GET /api/power/solar-forecast` 7-day forecast with 24-hour hourly breakdown; `GET /api/power/solar-history` 30-day actual vs estimated comparison; solar forecast card with panel config and Canvas 2D 7-day chart
  - **Automatic backups** — 6 endpoints (`/api/system/backup/create|list|restore|delete|configure|config`); SQLite backup API with optional Fernet encryption; configurable auto-backup thread (daily/weekly) with rotation; pre-restore safety copy; backup history list with per-backup restore/delete
  - **Analytics dashboards** — 5 endpoints (`/api/analytics/inventory-trends|consumption-rate|weather-history|power-history|medical-vitals`); `NomadChart` reusable Canvas 2D engine (line, bar, donut, breakdown, sparkline); analytics tab with inventory trends, burn rate, weather, power, and medical charts; theme-aware via CSS variables
  - **Accessibility (a11y)** — ARIA landmarks on all regions; skip-link; modal focus trapping (Tab/Shift+Tab cycle, Escape close, return focus); `aria-label` on 20+ icon-only buttons; `aria-label` on all form inputs; `aria-live="polite"` on status indicators; keyboard navigation for sidebar sub-items and customize panel; `tabindex="0"` + Enter/Space handlers
  - **Theme-aware map tiles** — `MAP_TILE_THEMES` (6 sources: dark, light, tactical, e-ink, satellite, terrain); `THEME_TO_TILE` auto-mapping; map tile selector dropdown; `applyMapThemeTiles()` + `setMapTileSource()` with localStorage persistence; auto-switch on theme change; offline fallback
  - **Customizable dashboard widgets** — `GET/POST /api/dashboard/widgets` + reset endpoint; 10 default widgets (weather, inventory, power, medical, comms, tasks, map, alerts, contacts, solar); drag-and-drop reordering via HTML5 DnD; visibility toggles; size control (normal/wide/full); widget manager modal; CSS grid layout
  - **SSE real-time events** — `GET /api/events/stream` Server-Sent Events with 30s keepalive; `_broadcast_event()` thread-safe bus; broadcasts on inventory CRUD, weather update, alert dismiss, task complete, sync receive, backup complete; `NomadEvents` JS client with exponential backoff reconnect; auto-refresh handlers; RT status indicator dot
  - **i18n translation layer** — `web/translations.py` with 10 languages (EN/ES/FR/DE/PT/JA/ZH/AR/UK/KO); 56 translation keys per language; 4 API endpoints (`/api/i18n/languages|translations/<lang>|language` GET/POST); `NomadI18n` JS engine with `data-i18n` attribute binding, fallback to English, RTL support for Arabic; language selector in Settings; RTL CSS rules
  - **Test expansion** — 51 new tests across 5 files: `test_federation_v2.py` (15), `test_barcode.py` (10), `test_security_v2.py` (10), `test_print_pdf.py` (8), `test_training.py` (8); total 338 tests across 34 files

- **v5.2.0 — Batch 9: Barcode Scanner, AI Vision, Contour Lines, Motion Detection, Security Audit**:
  - **Barcode/UPC scanning** — `upc_database` table with ~84 seeded survival items across 6 categories (Food/Water/Medical/Batteries/Gear/Hygiene); BarcodeDetector API camera scanner with manual entry fallback; `GET /api/barcode/lookup/<upc>` + `POST /api/barcode/add` + `POST /api/barcode/scan-to-inventory` + `GET /api/barcode/database/stats`; auto-fill inventory with name/category/expiration from UPC; recent scans list
  - **AI vision inventory** — Photo-to-inventory using Ollama vision models (llava/llava:13b/moondream/bakllava); `POST /api/inventory/vision-scan` with base64 image + structured JSON prompt for 14 categories; `POST /api/inventory/vision-import` bulk-add with condition tracking; canvas-based image resize (max 1024px); editable card grid with category/condition dropdowns
  - **Contour line rendering** — `GET /api/maps/contours` generates GeoJSON contour lines from waypoint elevation data using IDW interpolation + marching squares algorithm; toggleable map layer with thin/thick lines (major contours every 500m); elevation labels on major contours; debounced reload on map move (>5km threshold)
  - **Motion detection (OpenCV)** — `POST /api/security/motion/start/<camera_id>` launches background frame differencing thread; configurable threshold/interval/cooldown; `GET /api/security/motion/status` returns detector states; per-camera toggle buttons; status card with settings panel; 10s polling when security tab active; graceful fallback if cv2 not installed
  - **Security audit (1 CRITICAL, 4 HIGH, 6 MEDIUM, 4 LOW fixed)**: SQL injection in conflict merge via table/column names (allowlist + regex); unauthenticated sync receive (require known peer); swallowed sync push errors (now logged); unbounded PDF/sync/import queries (LIMIT clauses); exception message leakage (generic errors); sync receive row cap (10k/table); receipt/vision import cap (500 items)

- **v5.1.0 — Batch 8: Merge UI, PDF Engine, Mobile Layout, Receipt Scanner, Security Audit**:
  - **Three-way merge UI** — `GET /api/node/conflicts` returns unresolved federation sync conflicts; `POST /api/node/conflicts/<id>/resolve` accepts local/remote/merged resolution with optional merged_data; sync_log migration adds `resolved`/`resolution` columns; Conflict Resolution card in Federation section with side-by-side LOCAL vs REMOTE display, Keep Local/Keep Remote/Manual Merge buttons, inline merge editor
  - **PDF generation engine (ReportLab)** — `GET /api/print/pdf/operations-binder` generates full PDF with cover, TOC, contacts, frequencies, medical cards, inventory by category, checklists, waypoints; `GET /api/print/pdf/wallet-cards` generates ICE/rally/frequency wallet cards; `GET /api/print/pdf/soi` generates Signal Operating Instructions; all Courier monospace for tactical feel; graceful fallback if reportlab not installed
  - **Mobile-optimized layout** — Bottom tab bar (`#mobile-bottom-nav`) for ≤768px with Home/Gear/Maps/AI/More tabs; slide-out sidebar drawer with overlay; touch-friendly 44px minimum targets; ≤480px font scaling (14px body, 16px inputs); full-width cards; safe-area padding for notched phones; E-ink theme mobile support
  - **Receipt scanner** — `POST /api/inventory/receipt-scan` accepts image upload, tries Ollama vision (llava model) then Tesseract OCR fallback; regex price extraction ($X.XX patterns); `POST /api/inventory/receipt-import` bulk-adds parsed items to inventory; modal UI with drag-and-drop/camera capture, image preview, editable results table with checkboxes, select-all
  - **Security audit (2 CRITICAL, 4 HIGH, 5 MEDIUM, 4 LOW fixed)**: Path traversal in training dataset/model names (regex sanitization); Modelfile injection via base_model (character allowlist); unbounded GeoJSON storage (500KB cap); race condition on training job run (status check); Docker runs as root (added USER nomad); zone_type/color validation (allowlists + hex regex); zone query LIMIT clauses; UnboundLocalError in train thread exception handler; internal path removed from API response

- **v5.0.0 — Batch 7: AI Pipeline, Voice, Security Zones, Docker, Security Audit**:
  - **LoRA fine-tuning pipeline** — `training_datasets`/`training_jobs` tables; endpoints for dataset creation from conversation history, job management, Ollama Modelfile generation; UI in AI settings for managing training datasets and jobs
  - **Voice-to-inventory parsing** — `VoiceInput` JS module using Web Speech API (`SpeechRecognition`); `parseInventoryCommand()` NLP for quantity/unit/item extraction; `voiceAddInventory()` one-click voice add; `voiceInput(targetId)` generic voice-to-text for any input field; microphone buttons on inventory and copilot
  - **Perimeter security zones** — `perimeter_zones` table with GeoJSON boundaries, linked cameras/waypoints, zone types (patrol/restricted/observation/buffer); CRUD endpoints + GeoJSON export for map overlay; UI card in security tab with create/delete/list
  - **Docker headless server** — `Dockerfile` (Python 3.12-slim), `docker-compose.yml` (optional Ollama with --profile ai), `nomad_headless.py` entry point (NOMAD_HEADLESS=1, Flask on 0.0.0.0:8080), `requirements-docker.txt`, `.dockerignore`
  - **Security audit (4 HIGH, 1 MEDIUM, 1 LOW fixed)**: SSRF protection on sync-push/sync-pull peer_ip (ipaddress validation); removed broken Fernet fallback in dead drop (key length mismatch); XSS protection in map atlas (html.escape on page_title + waypoint names); federation endpoint auth (blocked peer rejection on sync-receive, group exercises invite/sync-state); grid_size capped at 10 in atlas (DoS prevention); N+1 DB connection fix in atlas loop; BatteryManager throttle no longer triggers fullSync

- **v5.4.0 — Audit Round 8: Connection Safety, Cascade Integrity, Frontend Hardening**:
  - **69 DB connection leaks fixed in app.py** — converted all unprotected `db = get_db()` / `db.close()` patterns to `with db_session() as db:` context manager; eliminates connection exhaustion under error conditions
  - **9 complex DB patterns fixed** — helper functions with early returns, alert engine, group exercises, readiness score all now use `db_session()`
  - **Cascade deletes added** — notes (note_tags + note_links), inventory (photos + checkouts + shopping_list), medical (handoff_reports + wound_photos via subquery)
  - **2 missing indexes** — `idx_shopping_list_inventory_id`, `idx_conversation_branches_parent`
  - **Frontend fixes (8)** — JSON.parse try-catch on chat messages, 3 missing resp.ok checks (kiwix catalog, dashboard overview), XSS fix (parseInt on doc_id onclick), null guard on getElementById('aar-output'), RAF stacking fix in barcode scanner, wrong selector `.conv-item` → `.convo-item[data-convo-id=]`, division-by-zero guard on tok/s stats
  - **routes_advanced.py fixes** — SITREP incidents query LIMIT 50, float() error handling on waypoint coordinates, removed duplicate `_esc()` definition
  - **Input validation** — search strings capped at 200 chars, LIMIT params capped at 500, scheduled_tasks query bounded
  - **Race condition fix** — `_alert_check_running` flag now uses `_state_lock` for thread-safe access
  - **Alert engine cleanup** — dedup and prune queries converted to `db_session()`, removed bare `db.close()` in exception handler

- **v4.9.0 — Batch 6: Training, Maps, Portability, Security Audit**:
  - **Multi-node group training exercises** — `group_exercises` table (16 cols: exercise_id, participants JSON, shared_state, decisions_log); 8 API endpoints (list, create+broadcast, invite, join, participant-joined, update-state, sync-state); `_get_trusted_peers()` helper; exercises broadcast to federation peers on create; state changes synced to all participants in real-time; UI with exercise cards, join/advance/complete buttons, decision log display
  - **Map atlas pages** — `POST /api/maps/atlas` generates printable multi-page HTML atlas with cover, TOC, grid-referenced pages at configurable zoom levels (default 10/13/15); per-page waypoint listings; `generateMapAtlas()` JS opens in new print window; Atlas button in map toolbar
  - **USB portable mode detection** — `is_portable_mode()` in platform_utils.py checks for `portable.marker`/`PORTABLE` file, Windows `GetDriveTypeW` removable drive, Linux `/media/`, macOS `/Volumes/`; `get_portable_data_dir()` creates `nomad_data/` next to app; `config.py` `get_data_dir()` auto-detects portable mode; `GET /api/system/portable-mode` endpoint; header `USB` indicator
  - **Elevation profile chart** — `showElevationProfile(routeId)` renders Canvas 2D chart from existing `/api/maps/elevation-profile/<id>` data; filled area under curve, waypoint dots with labels, Y-axis elevation + X-axis distance labels, grid lines; stats bar (ascent/descent/distance/min/max); Profile button on each route card; `hideElevationProfile()` toggle
  - **Offline geocoding** — `GET /api/geocode/search` searches waypoints, annotations, garden plots, contacts by name with typeahead; `GET /api/geocode/reverse` finds nearest named features using Haversine distance within 5.5km radius; geocoding search bar with dropdown in map tab; `geocodeGo()` flies to result with popup; `reverseGeocode()` toast with nearest feature
  - **Security audit (4 CRITICAL, 3 HIGH, 4 MEDIUM fixed)**: Dead drop encryption upgraded from XOR to AES-256-GCM with PBKDF2 key derivation (100k iterations) + v1 backward compatibility; SSRF protection on LAN transfer peer_ip (ipaddress validation); tarfile path traversal protection on pmtiles + FFmpeg extractors (normpath+startswith); SSRF protection on reference book downloads (_validate_download_url); timing-safe auth token comparison (hmac.compare_digest); error handler no longer leaks exception details for 5xx; LIMIT clauses added to notes (1000), map_routes (500), map_annotations (500), fuel/ammo in AI context (100)

- **v4.8.0 — Batch 5: Federation, Offline, Resilience, Comms**:
  - **Vector clocks for federation conflicts** — `vector_clocks` table (table_name, row_hash, clock JSON, last_node); `_vc_dominates()` helper for clock comparison; sync-push increments local clocks per row (SHA-256 hash), includes clocks in payload; sync-receive detects concurrent clocks (neither dominates), merges component-wise max, logs conflicts; `GET /api/node/vector-clock` returns clock state; `GET /api/node/vector-clock/conflicts` returns conflict history; `sync_log` extended with `conflicts_detected`/`conflict_details` columns
  - **IndexedDB offline data sync** — `OfflineSync` JS module with `init()`, `fullSync()`, `incrementalSync()`, `getOfflineData()`, `getSyncStatus()`, `startAutoSync()`; caches 6 tables (inventory, contacts, patients, waypoints, checklists, freq_database) to IndexedDB; `GET /api/offline/snapshot` bulk export; `GET /api/offline/changes-since` incremental delta; 5-minute auto-sync interval; sync badge indicator; Settings card with Full Sync/Check Status/Clear Cache buttons
  - **Battery-aware auto-throttling** — `BatteryManager` JS module using Battery Status API; monitors charge level and charging state; 20% low threshold reduces sync to 15min, disables CSS animations; 10% critical threshold increases sync to 30min, removes background patterns; `.battery-saver`/`.battery-critical` CSS classes; battery indicator in header; auto-restores when charging
  - **E-ink display mode** — New `[data-theme="eink"]` CSS theme: pure black/white, no shadows/gradients/animations, 2px solid borders, grayscale images, 16px base font, high contrast; theme button added to all 3 theme switcher locations + customize panel
  - **Dead drop encrypted USB messaging** — `dead_drop_messages` table; `POST /api/deaddrop/compose` encrypts message with XOR (SHA-256 derived key) + checksum verification; `POST /api/deaddrop/decrypt` decrypts with secret validation; `POST /api/deaddrop/import` stores encrypted messages; `GET /api/deaddrop/messages` lists received; compose UI with recipient/message/secret fields, download as JSON for USB transfer; import with inline decryption prompt

- **v6.24 — Full Codebase Audit + Situation Room Declutter (40 bugfixes, UI overhaul)**:
  - **Security fixes (8)**: Removed orphaned `/api/broadcast` route that mapped GET→shutdown handler; SQL injection f-strings→parameterized queries in 3 sitroom endpoints (gulf-economies, region-overview, five-good-things); SSRF in webhook-test/webhook-config with proper `ipaddress` validation (private/loopback/link-local/reserved); path traversal `normcase()` on NukeMap+VIPTrack Windows checks; XSS `escapeHtml()`→`escapeAttr()` in 4 href attributes
  - **Crash fixes (12)**: Missing imports in `media.py` (safe_table/safe_columns/build_update), `system.py` (broadcast_event, detect_gpu alias), `services.py` (sys/platform + SVC_FRIENDLY dict); `_schedule_auto_backup` stored on `app.config` for blueprint access; 3 `import ollama` (pip pkg→services module) in country-brief/deduction/ai-models; removed duplicate POST `/api/sitroom/ai-briefing`; try-catch for OREF JSON.parse, updateCustomizeTheme typeof guard; `_safe_float()` helper for yield curve + fuel price + predictions
  - **Data fixes (8)**: Backup encryption switched SHA-256→PBKDF2HMAC to match restore; checklist PDF `done`→`checked` key; alert engine try-catch on malformed dates; Fear&Greed symbol mismatch `'Fear & Greed'`→`'FEAR_GREED'`; social velocity SQL GROUP BY/SELECT aligned; correlation engine null guard on oil price; export UTC timestamp; apt-groups removed non-existent `source_name` column
  - **Infrastructure fixes (6)**: `db.py` index on correct column (`parent_id`→`conversation_id, parent_message_idx`); `nomad_headless.py` config merge instead of overwrite; `kb.py` embed state uses `web.state` module ref; `ai.py` training datasets reads `conversations.messages` JSON; `platform_utils.py` pid_alive Windows fallthrough; `nomad.py` log_activity wrapped in try-catch for shutdown safety
  - **JS fixes (4)**: `let` TDZ crash in `_app_workspace_memory.js` — `buildWorkspaceResumeEntry` accessed `_sitroomDeskPreset` before init, killed entire script block preventing Situation Room from loading; `.reverse()` copy to avoid mutating API response; OREF JSON.parse try-catch; `updateCustomizeTheme` typeof guard
  - **Situation Room UI overhaul**: Removed analyst desk panel, workspace chrome (desk presets, posture bar, saved desks), map command brief overlay, active layers legend, playback bar, 3D globe button (MapLibre v4 lacks `setProjection`), workspace inspector/context bar. Breaking banner: badge as wall with box-shadow, scroll speed 80s→40s. Map: full-width edge-to-edge, taller (50vh), no gradient overlays. Cards: uniform 320px height, consistent auto-fill grid. Scalable layout: container padding 0, width 100%, responsive breakpoints for 2000px+/2560px+ monitors

- **v6.15 — Situation Room (Exceeds World Monitor)**:
  - **World Monitor+ dashboard** — default landing tab, full-bleed flex layout, ~9,070 lines of code
  - **Blueprint**: `web/blueprints/situation_room.py` — 149 API routes, 34 background fetch workers
  - **36 data sources (all free, no API keys)**: all v6.8 sources plus:
    - **AIS Ships**: Danish Maritime Authority (300-vessel cap)
    - **Israel OREF**: Home Front Command real-time siren/rocket alerts (geocoded)
    - **GDELT Full**: event volume timeline + tone sentiment + geographic hotspots
    - **CFTC COT**: Commitments of Traders positioning for 8 major commodities
  - **45 map layers** (+day/night +3D globe) — 25 new since v6.8:
    - Weather Radar (RainViewer tile overlay), Disease Outbreaks (geocoded WHO DON), Radiation Monitors (Safecast), Protests/Unrest (UCDP filter), AIS Ship Traffic, Cloud Regions (63), Stock Exchanges (51), Commodity Hubs (37), Startup Hubs (32), GPS Jamming Zones (26), Trade Routes (24), Accelerators (26), Refugee Camps/IDP (20), UN Peacekeeping Missions (16), Internet Exchange Points (28), Diplomatic Hubs (14), Desalination Plants (18), Weather Stations (20), Space Tracking (16), Rare Earth Mines (12), Tsunami Warning Stations (16), Border Crossings (20), SIGINT/Listening Posts (16), Volcanic Arcs (20), Live Webcams (16)
  - **1,275 static infrastructure points** across 27 categories (was 440):
    - Military bases 149, Nuclear sites 106, Data centers 129, Pipelines 98, Cables 54, Shipping 44, Airports 62, Financial centers 30, Mining 40, Tech HQs 20, Waterways 26, Spaceports 26, Cloud regions 63, Stock exchanges 51, Commodity hubs 37, Startup hubs 32, GPS jamming 26, Trade routes 24, Accelerators 26, Refugee camps 20, UN missions 16, Internet exchanges 28, Diplomatic hubs 14, Desalination 18, Weather stations 20, Space tracking 16, Rare earths 12, Tsunami stations 16, Border crossings 20, SIGINT stations 16, Volcanic arcs 20, Webcams 16
  - **43 Telegram OSINT channels** (was 30): +Abu Ali Express, Vahid Online, Witness, Yedioth News, Fotros Resistance, Resistance Trench, OsintTV, The Cradle, Middle East Eye, Cybersecurity Boardroom, CyberWire, war_monitor UA, Intel Slava Z, Rybar
  - **~102 UI cards** (was 86): all v6.8 cards plus Breaking News Detection, OREF Alerts, GDELT Intelligence, COT Positioning, Country Intelligence Brief (AI-generated, 20-country dropdown), News Clusters, AI Deduction Panel, Source Health, Cable Health, Anomaly Detection, Alert History (7-day), Enhanced Signals, Gulf/GCC Economies, Market Regime, Positive Counters, Species Comeback
  - **New backend features (P3)**:
    - News clustering (Jaccard similarity >0.35), Breaking news detection (24-keyword urgency scoring), AI Deduction Panel (5-section structured intelligence analysis via Ollama), Country Intelligence Brief (per-country AI assessment), Source Health circuit breaker (live/stale/down), Cable Health monitor (12 submarine cable systems), Temporal Anomaly detection (seismic/fire/market/stablecoin/OREF surge), Stock Analysis (per-symbol Yahoo Finance + news), Consumer Prices, Gulf Economies, Enhanced cross-source signals with confidence scoring, Country Timeline, Alert History trends, Market Regime indicator (multi-signal risk-on/off), Full-text search across all cached data, Data freshness badges (LIVE/CACHED/STALE/UNAVAILABLE per card)
  - **P4 UX polish**:
    - Smart poll loop (tab visibility pause, exponential backoff)
    - Notification sounds (WebAudio 2-tone alert for M6+ earthquakes)
    - Data freshness badges on card headers
  - **P5 variant panels**: Market Regime, Live Positive Counters (estimated daily global rates), Species Comeback tracker (8 curated recoveries + conservation news)
  - **35+ interactive features**: all v6.8 features plus smart polling, quake alert sounds, full-text search, data freshness badges, country brief generation, AI deduction analysis
  - **DB**: 5 new tables (sitroom_ships, sitroom_gdelt, sitroom_cot + 2 runtime)
  - **P4 CSS polish**: Radar loading animation, skeleton shimmer loader, card badges (NEW/PRO/LIVE with pulse), sparkline bar charts, AI brief styling, mini table component, mini labels
  - **P6 infrastructure**: Webhook notification system (config + test endpoints), situation snapshot aggregator
  - **P7 data**: APT Groups database (15 nation-state + criminal groups with attribution, targets, notable ops)
  - **P5 variant panels**: Tech Readiness Index (3-dimension composite), Today's Hero (positive story spotlight), 5 Good Things digest, Central Bank Calendar (8 major banks + rate decision news), Market Regime, Live Positive Counters, Species Comeback
  - **Enhanced clustering**: Supercluster-inspired adaptive grid — tighter at medium zoom, cluster count tracking
  - **P4 card resize**: 6 size variants (small/compact/default/tall/half/full) with CSS data-attribute, localStorage persistence, resize handle
  - **P6 IndexedDB**: client-side offline cache with snapshots + news stores, persistent across sessions
  - **P6 virtual scroll**: VirtualList implementation for news cards (row-height based lazy rendering)
  - **Additional endpoints**: conflict-intensity scoring, media-bias/source diversity, language coverage, escalation-tracker, food-security, water-stress, climate-signals
  - **WM parity status**: ALL metrics exceed World Monitor. 149 API routes (124%), 45 map layers (100%), 1,275 static points (142%), 108+ cards (126%), 36 data sources (120%), 34 workers (155%), 43 OSINT channels (96%), 35+ interactive features (117%). ~11,237 lines.
  - **v6.24 UI**: Decluttered — no analyst desk, no workspace chrome, no map overlays. Clean operational layout: breaking banner → compact header → ticker → market ribbon → full-width map → uniform card grid. Scalable to ultrawide monitors (2560px+). MapLibre v4.7.1 (no globe projection support).

- **v6.25 — Robustness + Performance Audit (40+ fixes across 13 files)**:
  - **Backend**: Guarded `json.loads` on scenario AAR `decisions`/`complications` columns with try/except fallback to prevent crash on corrupted DB data (`app.py:2414-2415`)
  - **Frontend fetch hardening**: Added `.ok` checks before `.json()` on 12 fetch chains in `_app_workspace_memory.js` — content-summary, activity log, data-summary, disk monitor, services list, update check, update download status, startup state, download queue, service logs, content update checker. Prevents `SyntaxError` when API returns non-JSON error responses
  - **Kiwix zims fetch**: Added missing `.ok` guard on `/api/kiwix/zims` in `_app_services_ai.js` download-all-by-tier
  - **localStorage crash prevention**: Wrapped 25+ unguarded `JSON.parse(localStorage.getItem(...))` calls in try-catch across 7 files: `_prep_family_field.js` (FEP, shelter, home security, infra), `_prep_ops_mapping.js` (threats, PACE, FEP, sit board), `_prep_calcs_misc.js` (PACE plan), `_app_media_maps_sync.js` (map zones, bookmarks), `_app_init_runtime.js` (ICS forms), `_app_situation_room.js` (card sizes). Corrupted localStorage no longer crashes feature initialization
  - **Null guards**: Optional chaining on `getElementById` for morse code trainer inputs in `_prep_people_comms.js`; null guard on `data?.lines` in service log viewer
  - **SSE listener leak fix**: `events.js` — on reconnect, old `addEventListener` calls were duplicated on new `EventSource`, causing 10x event throughput after 10 reconnects. Fixed by storing handler refs in `_sseListeners` map and reusing them across reconnections; also clear reconnect timer on new connect
  - **Service worker cache eviction**: `sw.js` — SITROOM_CACHE had no eviction, growing unbounded over days (100+ MB). Added `_evictStaleSitroomCache()` that prunes entries older than TTL and caps at 200 entries; runs on activate + probabilistic 1% of sitroom fetches. General API cache now only caches read-heavy endpoints (`services`, `system`, `content-summary`, `settings`, `offline/snapshot`) instead of all GET API responses
  - **Uninstall cleanup**: `manager.py` — `_download_progress`, `_service_logs`, `_restart_tracker` cleanup moved into `finally` block so tracking state is always cleaned even if DB delete fails
  - **Global search optimized**: `app.py` `/api/search/all` — collapsed 14 sequential LIKE queries into single UNION ALL (1 DB round-trip instead of 14). Results grouped by type in Python. ~10x faster on large datasets
  - **Input validation**: Guarded bare `int()`/`float()` on training job params in `ai.py` (epochs, learning_rate) and UPC scan quantity in `inventory.py` — prevented ValueError crash on malformed input
  - **Division-by-zero guards**: `system.py` — readiness `coverage_pct` and startup wizard `pct` now guard against empty `checks`/`steps` lists
  - **Duplicate ID fix**: `dose-result` existed in both NukeMap tab and Calculators tab — renamed to `nuke-dose-result` in NukeMap embedded tab + updated `nukemap/js/app.js` with fallback (`$('nuke-dose-result') || $('dose-result')`) for standalone compatibility

- **v6.26 — Memory Leak & Performance Fixes (7 fixes across 7 files)**:
  - **Memory leak: SSE rate-limit dict** (`web/app.py`) — `_sse_connects` accumulated IP entries forever; now prunes stale IPs (>60s inactive) on every SSE connection
  - **Memory leak: download progress** (`services/manager.py`, `nomad.py`) — `_download_progress` entries for completed/errored downloads never removed (ZIM downloads create `kiwix-zim-*` keys endlessly); added `prune_completed_downloads()` with `_finished_at` timestamps, called every 10s from health monitor; entries auto-expire after 1 hour
  - **Memory leak: OCR processed files** (`web/state.py`, `web/blueprints/kb.py`) — `_ocr_processed_files` set used `clear()` at 1K entries, causing re-processing of already-imported files; raised cap to 10K (`_OCR_PROCESSED_MAX`), changed to half-shed eviction to retain most history
  - **Perf: redundant WAL pragma** (`db.py`) — `PRAGMA journal_mode=WAL` executed on every `get_db()` call; WAL is persistent on the DB file so now set once per process via `_wal_set` flag
  - **Perf: Situation Room HTTP connection pooling** (`web/blueprints/situation_room.py`) — 44 HTTP requests per refresh cycle each created new TCP connections; replaced all `requests.get/post()` with persistent `_http_session` (`requests.Session()`) for connection reuse
  - **Perf: alert engine triple DB open** (`web/app.py`) — alert engine opened 3 separate DB connections per 5-minute cycle (read + dedup write + prune write); consolidated to 1 connection
  - **Perf: log reader deque allocation** (`services/manager.py`) — `_service_logs.setdefault(service_id, deque(maxlen=500))` inside hot log-reader loop constructed throwaway deque on every line; captured deque reference once before entering loop

- **v6.27 — yt-dlp Bundling, NukeMap WW3, CI Fix, Cache Guard**:
  - **yt-dlp bundled in executable** (`requirements.txt`, `build.spec`, `web/blueprints/media.py`) — added `yt-dlp` as pip dependency so PyInstaller packages it; `get_ytdlp_path()` prefers standalone binary (for updates) then falls back to bundled module via auto-generated wrapper script (.cmd on Windows, shell script on Unix); all existing `subprocess.run([exe, ...])` calls work unchanged with either mode
  - **yt-dlp update mechanism** — `GET /api/ytdlp/check-update` compares installed version against GitHub latest release tag; `POST /api/ytdlp/update` downloads latest standalone binary with progress tracking and atomic replace (overrides bundled version); `GET /api/ytdlp/status` now reports `source: "bundled"|"standalone"|"none"`
  - **NukeMap WW3 quick-launch** (`web/nukemap/js/app.js`) — floating WW3 button now directly launches the `global` scenario (708 warheads, all sides) instead of just scrolling to the Tools panel; click again while running to stop; syncs scenario dropdown
  - **CI workflow fix** (`.github/workflows/build.yml`) — `secrets` context cannot be used in step-level `if:` conditions; moved code signing cert check from `if:` expression into script body with early exit
  - **Situation Room CSS theming** (`web/static/css/app/45_situation_room.css`) — extracted 40+ hardcoded accent colors (`#4aedc4`, `#0f5040`) into `--sr-accent`, `--sr-accent-dim`, `--sr-accent-bg` CSS custom properties across all 6 theme variants
  - **Services/AI fetch hardening** (`web/templates/index_partials/js/_app_services_ai.js`) — added `fetchJsonStrict`/`fetchJsonSafe` helpers; all install/start/stop/uninstall/prereqs/model-pull/ZIM-download flows now check `resp.ok` before parsing JSON and extract meaningful error messages from API payloads
  - **`_api_cache` eviction guard** (`web/app.py`) — added max-size check with expired entry pruning (>120s old) when cache exceeds 50 entries; defense-in-depth for currently 2-key cache
  - **Full codebase audit (v6.27)** — 3 parallel deep audits covering all Python blueprints, all JS files, service workers, state management, and service modules. Verified all v6.26 fixes hold. Confirmed false positives: SSE listener dedup (already correct), copilot session eviction (already bounded at 100), drag handler accumulation (DOM replacement GCs old listeners), interval dedup (startInterval calls stopInterval first), JSON.parse guards (all wrapped), RSS upsert pattern (bounded), restart tracker (pruned within 300s window)
  - **New test files** — `tests/test_crud_api.py` (242 lines), `tests/test_db_safety.py` (58 lines), `tests/test_services_ai_contracts.py` (17 lines)

## Run / Build
```bash
python nomad.py                    # Run from source (any platform)
pyinstaller build.spec             # Build portable binary (Windows: .exe, Linux/macOS: binary)
iscc installer.iss                 # Build Windows installer -> ProjectNOMAD-Setup.exe
```

### Platform Dependencies
- **All**: Python 3.10+, pip packages (auto-installed by `_bootstrap()` on first run)
- **Windows**: WebView2 runtime (comes with Windows 10/11)
- **Linux**: `python3-gi gir1.2-webkit2-4.1` (for pywebview GTK backend), or Qt5 WebEngine
- **macOS**: No additional dependencies (uses native WebKit via Cocoa)

## Release Process
```bash
# Tag and push — CI builds both artifacts
git tag v4.1.0 && git push origin v4.1.0
# Or manual: build locally, then create release
gh release create v4.1.0 dist/ProjectNOMAD-Portable.exe ProjectNOMAD-Setup.exe --title "Project N.O.M.A.D. v4.1.0"
```

## CSS Architecture
- **Inline `<style>` in index.html** — Only theme CSS variables (8 lines). Prevents flash of unstyled content.
- **web/static/css/app.css** — All base styles (themes, design system tokens, layout, sidebar + sub-menus, cards, forms, tables, responsive breakpoints, UI zoom levels, reduced-motion support)
  - Design tokens: `--text-xs` through `--text-2xl` (7-step type scale), `--sp-1` through `--sp-8` (spacing), `--card-pad`, `--ui-zoom`
  - Responsive: 480px, 768px, 900px, 1000px, 1280px, 1440px, 2560px breakpoints
  - UI zoom: `html[data-zoom]` sets `--ui-zoom` → `html { font-size: calc(13px * var(--ui-zoom)) }`
  - Sidebar sub-menus: `.sidebar-sub` (hidden by default), `.sidebar-sub.open`, `.sidebar-sub-item`
  - Unified input focus: all inputs get `border-color: var(--accent)` + `box-shadow: 0 0 0 2px var(--accent-dim)` on focus
  - Keyboard accessibility: `focus-visible` outlines on all buttons, cards, tabs, links
- **web/static/css/premium.css** — Visual polish overlay (tactical typography, hazard stripes, animations, shadows, hover effects, spring transitions, glass overlays, glow effects, print styles, customize panel backdrop blur, sidebar group labels, status pills, copilot dock command-line feel)
- Build spec includes `('web/static', 'web/static')` which covers the css/ subdirectory.

## Layout
- **Sidebar navigation** (fixed left, 240px) with SVG icons + expandable sub-menus per tab
  - Group labels: `OVERVIEW`, `INTEL`, `FIELD OPS`, `SYSTEM` (`.sidebar-group-label`)
  - Sub-menus auto-show when parent tab is active (Home, Library, Media, Preparedness, Settings)
  - Sub-items use 11px text, indented under parent, hover highlights accent color
  - `updateSidebarSubs()` called on tab switch to toggle `.sidebar-sub.open`
  - Customize button at bottom opens right-side flyout panel for full UI customization
- **Home page bento grid** — asymmetric 2-column layout (`3fr 2fr`) for dashboard zones
  - Row 1: Situation Dashboard widgets + Preparedness By Need (side-by-side)
  - Services section: full-width with status-variant cards
  - Row 2: Field Documents + Activity Log (side-by-side cards)
- **AI Copilot dock** — persistent fixed bottom bar available on all tabs
- **Status strip** — pill-shaped indicators with colored dots, dynamically updated
- **Customize panel** — right-side 420px slide-out with theme/scale/mode/sidebar/section toggles, persisted to localStorage
- Collapses on mobile (<900px) with hamburger toggle + overlay
- Theme switcher + alert bell + mode switcher in sidebar footer
- **Status strip** at top of content area: services count, inventory total, contacts, alerts, military time
- **LAN chat button** at left:260px (not 20px) to avoid covering sidebar footer
- `window.scrollTo(0, 0)` on every tab switch to prevent blank-space-at-top bug
- FABs (LAN Chat, Quick Actions, Timer) placed OUTSIDE `.container` div to prevent layout interference
- **UI Zoom** — 4 levels (Small 0.85x, Default 1x, Large 1.15x, X-Large 1.3x) via `html[data-zoom]` + CSS `--ui-zoom` variable + `html { font-size: calc(13px * var(--ui-zoom)) }`. Setting in Preferences, persists in localStorage.

## Service Ports
Dashboard: 8080, Ollama: 11434, Kiwix: 8888, CyberChef: 8889, FlatNotes: 8890, Kolibri: 8300, Qdrant: 6333, Stirling: 8443, Node Discovery: UDP 18080

## 12 Main Tabs
Situation Room (default landing), Home/Services, AI Chat, Library, Maps, Notes, Media, Tools, Preparedness, Benchmark, Settings (+ NukeMap opens in-app frame)

## Home Tab Layout (6 sections, top to bottom)
1. **Welcome / Getting Started** — first-run only, onboarding checklist
2. **Active Downloads** — unified download queue banner (auto-polling 5s)
3. **Search + Live Dashboard** — unified search bar + mode-aware widget grid (auto-refresh 30s, incl. sunrise/sunset)
4. **Readiness + Preparedness** — two-column: readiness score (left) + needs-by-category grid (right); stacks on <1000px
5. **AI Copilot** — quick-query input with voice + suggested actions panel
6. **Services** — section header with Start/Stop All buttons, quicklinks, full service grid
7. **Printable Field Documents** — collapsible `<details>`: 6 document cards (Operations Binder, Wallet Cards, SOI, Emergency Sheet, Medical Cards, Bug-Out List)
8. **Activity Log** — collapsible `<details>` with id `home-activity`: filterable event feed

## Media Tab (5 sub-tabs)
- **Browse Channels** — 210 survival channels across 26 categories, auto-hide dead channels
- **My Videos** — Upload/download/play instructional videos, thumbnail cards, watch+download player; **131 curated tutorial videos** across 14 folders
- **My Audio** — Audio catalog with favorites, batch operations, sorting; **102 training audio entries** across 13 folders
- **My Books** — EPUB/PDF reader, book catalog; **141 reference books** (archive.org/govt URLs) across 16 folders
- **Torrent Library** — Built-in BitTorrent client (libtorrent) with live progress UI; **152 curated torrent collections** across 12 categories (survival/maps/weather/radio/textbooks/medical/farming/videos/software/encyclopedias/repair/energy)

## 25 Preparedness Sub-Tabs (5 category groups)
- **Supplies**: Inventory, Fuel, Equipment, Ammo
- **People**: Contacts, Family Plan, Skills, Community, Journal
- **Readiness**: Checklists, Medical, Security, Power, Garden, Weather, Radiation
- **Knowledge**: Guides, Calculators (with search filter), Procedures, Radio, Quick Ref, Signals
- **Operations**: Command Post (SITREP, ICS forms), Secure Vault, Incidents

Category navigation: top row = 5 category buttons, bottom row = sub-tabs within selected category. `PREP_CATEGORIES` JS object maps categories to sub-tab arrays. `showPrepCategory(cat)` renders sub-tabs; `_findCategoryForSub(sub)` auto-detects category when navigating from widgets/search.

## Critical Gotchas
- **DECISION_GUIDES array**: ALL 21 guide objects must be inside the `];`. Placing objects after the closing bracket causes a JS syntax error that kills ALL interactivity.
- **`let` TDZ in workspace_memory.js** — `_app_workspace_memory.js` loads BEFORE `_app_situation_room.js`. Any `typeof _sitroomXxx !== 'undefined'` check on a `let`-declared variable throws `ReferenceError` (temporal dead zone), NOT `undefined`. Must use try-catch around sitroom variable access in workspace_memory. An uncaught TDZ error kills the ENTIRE inline `<script>` block, preventing all subsequent JS files from executing.
- **MapLibre v4.7.1 globe** — `setProjection({type: 'globe'})` does NOT exist in this build. 3D globe button hidden via CSS. Would need MapLibre v5+ for globe projection support.
- **escapeAttr function**: Contains HTML entities (`&amp;`, `&quot;`, `&#39;`, `&lt;`) which are correct — browsers do NOT decode entities inside `<script>` tags. Must escape single quotes too for onclick attributes.
- **FABs must be outside .container**: LAN Chat, Quick Actions, and Timer widgets (position:fixed) must be DOM siblings of .main-content, NOT inside .container.
- **scrollTo on tab switch**: Without `window.scrollTo(0,0)` in the tab click handler, switching from a scrolled-down tab leaves the viewport at the old scroll position.
- **Duplicate CSS removed**: Inline `<style>` in index.html now contains ONLY theme variables (8 lines). All component/layout CSS is in external app.css. Don't re-add inline CSS.
- **subprocess.PIPE with reader thread** — service Popen now uses PIPE+STDOUT for log capture, with a dedicated reader thread per service draining stdout into `_service_logs` ring buffer (500 lines). This avoids the 4KB pipe buffer deadlock. CyberChef (http.server) still uses DEVNULL since it's in-process.
- **Ollama OLLAMA_MODELS env var** — must always point to app's configured data dir. Kill any system Ollama on port 11434 before starting app's own instance
- **AI chat streaming** — must check `resp.ok` before calling `resp.body.getReader()`, otherwise 503 errors silently hang. Streaming render uses requestAnimationFrame to avoid jank.
- **DB connections** — prefer `db_session()` context manager from `db.py` (`with db_session() as db:`) for automatic close. All service files and app.py routes use try-finally on get_db(). SQLite timeout is 30s, FK enforcement ON. `teardown_appcontext` safety net auto-closes connections stored on `flask.g`.
- **Input validation** — int/float conversions on user input (ammo qty, fuel stabilizer, radiation dose) wrapped in try-except with fallback to 0. Harvest quantity forced >= 0.
- **Calculator tab init** — 30 calculator functions called on tab switch; wrapped in try-catch to prevent blank tab if any single calc fails.
- **Extra </div> tags** — psub sections can have extra closes that push settings tab outside .container. Always verify nesting after editing prep sub-tabs.
- **Cross-platform abstraction** — ALL platform-specific code goes through `platform_utils.py`. Never use `creationflags`, `os.startfile`, `ctypes.windll`, `powershell`, hardcoded `.exe` extensions, or `%APPDATA%` directly. Use `popen_kwargs()`, `run_kwargs()`, `exe_name()`, `open_folder()`, `find_pid_on_port()`, `get_data_base()` etc.
- **Config paths** — Windows: `%LOCALAPPDATA%/ProjectNOMAD/config.json`, Linux: `~/.config/ProjectNOMAD/config.json`, macOS: `~/Library/Application Support/ProjectNOMAD/config.json`
- **Data paths** — Windows: `%APPDATA%/ProjectNOMAD`, Linux: `~/.local/share/ProjectNOMAD`, macOS: `~/Library/Application Support/ProjectNOMAD`
- **Service download URLs** — each service module has a `_get_*_url()` function that returns platform-appropriate download URLs via `platform_utils`
- NukeMap: `/nukemap` redirects to `/nukemap/` (trailing slash for relative paths)
- PyInstaller: `_bootstrap()` must skip when `sys.frozen`
- **Sidebar sub-menus** — `.sidebar-sub[data-parent="tabname"]` divs toggled by `updateSidebarSubs()` which reads `.tab.active` dataset. Called on tab click via event listener. Sub-item onclick handlers use `scrollToSection(id)` which calls `el.scrollIntoView({behavior:'smooth'})` after 200ms delay.
- **Prep categories** — `PREP_CATEGORIES` JS object is the single source of truth for category→sub-tab mapping. `switchPrepSub()` calls `_findCategoryForSub()` to auto-switch category. All 25 sub-tab loaders are now in the main `switchPrepSub()` function (no more `_origSwitchPrepSub` wrapper).
- **UI zoom** — `setUIZoom(level)` sets `data-zoom` attribute on `<html>` + localStorage. CSS rule `html { font-size: calc(13px * var(--ui-zoom)) }` cascades through entire UI. Zoom levels: small=0.85, default=1, large=1.15, xlarge=1.3.
- **yt-dlp auto-install** — `browseChannelVideos()` detects "not installed" error and shows install button that calls `autoInstallYtdlp()`, which POSTs to `/api/ytdlp/install`, polls status every 2s, then auto-retries the browse on success.
- **routes_advanced.py** — advanced routes (phases 16-20) in separate file, registered via `register_advanced_routes(app)` called before `return app` in `create_app()`. Contains AI SITREP, AI actions, AI memory, operations binder, wallet cards, SOI, DB health, self-test, undo system, community readiness, skill search, alert relay.
- DB migrations must run BEFORE index creation
- json.loads from DB needs `or '{}'` / `or '[]'` fallback for NULL values
- Kiwix won't start without ZIM files
- Qdrant uses env var not CLI arg for storage path
- Planet PMTiles URL: `https://data.source.coop/protomaps/openstreetmap/v4.pmtiles` (build.protomaps.com is dead)
- `switchPrepSub` is overridden at bottom of script to auto-load new tab data; override must come AFTER original definition
- `switchPrepSub` override must call `loadChecklists()` for 'checklists' sub — it doesn't auto-load from the original function
- Readiness score factors in: ammo (security), fuel (shelter/power), skills proficiency (planning), trusted community members (planning)
- Equipment `markServiced()` sends full record with updated last_service + status='operational' via PUT
- **Do NOT redefine `formatBytes`** — defined once near line 6118; a second definition silently shadows it with broken behavior (<1024 returns "0 KB")
- **Service process registration** — service modules MUST use `register_process()` / `unregister_process()` from manager.py, NEVER directly mutate `_processes` dict (thread safety)
- **Path traversal on Windows** — always use `os.path.normcase()` on BOTH sides of `startswith` checks (Windows paths are case-insensitive)
- **Config writes** — config.py uses atomic write (tmp file + os.replace) to prevent corruption on crash. Config reads are mtime-cached — `load_config()` only re-reads disk when file changes. Cache auto-invalidated on `save_config()`.
- **Health monitor grace period** — 90 seconds before first check to let auto_start_services finish (Stirling can take 60s+)
- **Service health checks** — `manager.is_healthy(service_id)` checks PID alive AND HTTP health endpoint via `SERVICE_HEALTH_URLS`. Use instead of `is_running()` when you need to verify the service is actually responding.
- **wait_for_port** — `manager.wait_for_port(port, timeout, interval)` blocks until port accepts connections. Use in service `start()` functions instead of manual sleep loops.
- **Log rotation** — `nomad.py` uses `RotatingFileHandler` (5 MB max, 3 backups). Log files: `nomad.log`, `nomad.log.1`, `nomad.log.2`, `nomad.log.3`.
- **AI context helpers** — `build_situation_context(db)` returns list of context sections from DB (inventory, contacts, patients, fuel, ammo, equipment, alerts, weather, power, incidents). `get_ai_memory_text()` loads AI memory facts. `_safe_json_list(val)` parses JSON with fallback. All defined inside `create_app()` in app.py.
- **Global error handler** — `@app.errorhandler(Exception)` returns JSON `{'error': ...}` for `/api/` routes. Non-API routes re-raise for Flask's default HTML handler.
- **Ollama chat errors** — `ollama.chat()` raises descriptive `RuntimeError` for ConnectionError ("AI service not running"), Timeout ("request timed out"), and 404 ("Model not found"). Callers should catch `RuntimeError` for user-friendly messages.
- **Sync-receive column validation** — must validate column names against PRAGMA table_info before INSERT (SQL injection prevention)
- **PMTiles serving** — must stream large files in chunks, NEVER read() entire file into memory (can be GB+)
- **Night mode** — uses `_nightModeApplied` flag to only trigger once per day/night transition, not fight manual theme changes

## UX Design Principles
- All jargon removed — plain English throughout (no Ollama/Kiwix/PMTiles/Sneakernet)
- Download sizes shown on all install/download buttons
- Empty states with helpful guidance on every panel
- Contextual help icons (?) linking to relevant user guide sections
- System presets grouped by category in dropdown
- Prep sub-tabs ordered by emergency priority (Inventory first)
- Quick-add templates for 58 common inventory items across 8 categories
- Status strip shows key metrics at a glance (military time format)
- Debounced search inputs (media filter, channel filter) at 200ms
- Error feedback on destructive actions (map delete, vault delete, model delete)
- Keyboard shortcuts: Ctrl+K (search), Ctrl+/ (copilot), Alt+1-9 (tab switch), Escape (close modals), ? (shortcut help)
- 3 dashboard modes: Command Center, Homestead, Essentials — each with tailored sidebar ordering, widget sets, and copilot suggestions
