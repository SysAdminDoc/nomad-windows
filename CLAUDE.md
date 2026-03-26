# Project N.O.M.A.D.

## Overview
Cross-platform edition of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — the most comprehensive offline survival command center available. Runs on Windows, Linux, and macOS. No Docker required. 8 managed services (incl. FlatNotes), proactive + predictive AI alerts, AI SITREP generator + action execution + persistent memory, 21 interactive decision guides, 41 calculators, 56 quick reference cards, medical module (TCCC/triage/SBAR), training scenarios, food production, multi-node federation with community readiness + skill matching, power management with sensor charts, security cameras, AI document intelligence, built-in BitTorrent client, media library with 210 survival channels, 41-section user guide, task scheduler, 9 printable field documents (operations binder, wallet cards, SOI), serial hardware bridge, mesh radio support, CSV import wizard with 5 inventory templates (155 items), PWA with offline caching, UI zoom control, sidebar sub-menus, and a premium dark dashboard with 4 themes.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2 on Windows, WebKit on macOS, GTK on Linux)
- **SQLite** — 59 tables, WAL mode, 30s timeout, FK enforcement, SQLite backup API, 81 performance indexes
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
db.py                 # SQLite init (59 tables), indexes, migrations (migrations BEFORE indexes), db_session() context manager
config.py             # Data directory management (atomic writes via tmp+replace, XDG-aware paths, mtime-cached reads)
build.spec            # PyInstaller spec for portable exe
icon.ico              # App icon (multi-size, 16-256px)
installer.iss         # Inno Setup installer script
ROADMAP.md            # 22-phase implementation plan (all complete)
.github/workflows/
  build.yml           # CI/CD — PyInstaller + Inno Setup, dual artifact release on tag push
web/
  app.py              # Flask routes (~420 endpoints) — ~10,800 lines
  catalog.py          # Content catalogs (books, videos, audio, torrents)
  static/
    css/
      app.css         # Base styles (~1460 lines) — 4 themes, design system tokens, layout, components, responsive breakpoints (480/768/900/1280/1440/2560px), UI zoom levels
      premium.css     # Premium polish (~584 lines) — tactical typography, hazard stripes, micro-interactions
    logo.png          # App logo
    maplibre-gl.js    # Map renderer (bundled)
    maplibre-gl.css   # Map styles (bundled)
    pmtiles.js        # Tile format handler (bundled)
    js/
      epub.min.js     # EPUB reader library (bundled)
  routes_advanced.py  # Advanced routes (phases 16-20): AI SITREP, actions, memory, print binder/wallet/SOI, system health, undo, federation community
  templates/
    index.html        # HTML + inline theme vars + JS (~22,100 lines)
  nukemap/            # NukeMap v3.2.0 — index.html, 18 JS modules, CSS, data/, lib/leaflet
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
v4.1.0 — ~120,000 lines, 467 API routes, 76 DB tables (111 indexes), 8 managed services, 25 prep sub-tabs, 38-section user guide, 21 decision guides, 42 calculators, 56 quick reference cards, 3 dashboard modes, 13 live widgets, persistent AI copilot dock (all tabs) with model cards, 9 survival need categories with progress bars, 9 printable field documents, weather-triggered + predictive alerts, Zambretti offline weather prediction with pressure graphing, inventory barcode/QR + lot tracking + check-in/out + photo attachments + auto-shopping list, DTMF tone generator + NATO phonetic trainer, wiki-links + backlinks + templates + attachments in notes, media resume playback + playlists + metadata editor, KB workspaces, companion planting (20 pairs) + pest guide (10 entries) + seed inventory, vital signs trending charts, expiring meds tracker, map measurement + print + style switcher + GPX, AI inference + storage + network benchmarks, LAN chat channels + presence, antenna calculator, bento grid home + sidebar labels + status pills + customize panel, full UI customization with localStorage persistence

## Audit History (7 rounds)
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
  - **Phase 17 (Data Import)**: CSV import wizard (`/api/import/csv` + `/api/import/csv/execute`) with column mapping UI and 7 target tables; 5 inventory templates (`/api/templates/inventory`) with 155 realistic prepper items (72hr Kit, Family 30-Day, Bug-Out Bag, First Aid, Vehicle Emergency); QR code generation (`/api/qr/generate`); CSV import modal in Settings; template dropdown in Inventory
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

## 11 Main Tabs
Services, AI Chat, Library, Maps, Notes, Media, Tools, Preparedness, Benchmark, Settings (+ NukeMap opens in-app frame)

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
