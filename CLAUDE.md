# Project N.O.M.A.D. for Windows

## Overview
Native Windows port of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — the most comprehensive offline survival command center available. No Docker required. 6 managed services, proactive AI alerts, 21 interactive decision guides, 41 calculators, 37+ quick reference cards, medical module, training scenarios, food production, multi-node federation, power management, security cameras, AI document intelligence, built-in BitTorrent client, media library with 210 survival channels, 38-section user guide, and a premium dark dashboard with 4 themes.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2) embedded browser
- **SQLite** — 43 tables, WAL mode, 30s timeout, FK enforcement, SQLite backup API, 35 performance indexes
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
nomad.py              # Entry point — Flask + WebView2 + tray + health monitor + service autostart
db.py                 # SQLite init (43 tables), indexes, migrations (migrations BEFORE indexes)
config.py             # Data directory management
build.spec            # PyInstaller spec for portable exe
icon.ico              # App icon (multi-size, 16-256px)
installer.iss         # Inno Setup installer script
ROADMAP.md            # 10-phase implementation plan (all complete)
.github/workflows/
  build.yml           # CI/CD — PyInstaller + Inno Setup, dual artifact release on tag push
web/
  app.py              # Flask routes (~311 endpoints) — ~8050 lines
  catalog.py          # Content catalogs (books, videos, audio, torrents)
  static/
    css/
      app.css         # Base styles (1191 lines) — 4 themes, layout, components
      premium.css     # Premium polish (557 lines) — glassmorphism, glow effects, micro-interactions, depth
    logo.png          # App logo
    maplibre-gl.js    # Map renderer (bundled)
    maplibre-gl.css   # Map styles (bundled)
    pmtiles.js        # Tile format handler (bundled)
    js/
      epub.min.js     # EPUB reader library (bundled)
  templates/
    index.html        # HTML + inline theme vars + JS (~19,561 lines)
  nukemap/            # NukeMap v3.2.0 — index.html, 18 JS modules, CSS, data/, lib/leaflet
services/
  manager.py          # Process manager — download (with resume), start, stop, track, uninstall
  ollama.py           # Ollama AI
  kiwix.py            # Kiwix
  cyberchef.py        # CyberChef
  kolibri.py          # Kolibri education
  qdrant.py           # Qdrant vector DB
  stirling.py         # Stirling PDF
  torrent.py          # BitTorrent client (libtorrent) — singleton TorrentManager, thread-safe
```

## Version
v3.1.0 — ~95,000 lines, 364 API routes, 57 DB tables (65 indexes), 25 prep sub-tabs, 38-section user guide, 21 decision guides, 41 calculators, 56 quick reference cards, 3 dashboard modes, 12 live widgets, AI copilot, 9 survival need categories, 6 printable field documents, route/annotation planning, frequency database (35 seeded), TCCC/triage system, sensor integration, planting calendar (31 seeded), yield analysis, preservation tracking, federation v2, unified search (14 data types), keyboard shortcuts, guided onboarding, system health diagnostics

## Audit History (5 rounds)
- **v1.8.0 — Security**: Auth deny-on-failure, thread-safe install lock, path traversal hardening (normpath+startswith on maps/ZIM delete), DB try-finally on all 7 services, stirling stderr crash fix, race conditions (window handler before thread, health monitor MAX_RESTARTS), Flask startup error feedback
- **v1.9.0 — Frontend+DB**: resp.ok on AI warmup, debounced media/channel filters (200ms), try-catch loadNotes, SQLite backup API (WAL-safe), 30s connection timeout, FK enforcement, 10 new indexes, division-by-zero guard on critical_burn
- **v2.0.0 — Performance**: requestAnimationFrame debounce on streaming chat rendering, insertAdjacentHTML for mesh/LAN log (O(1) vs O(n^2)), content-summary 4 queries→1, fetch error handlers on map/vault delete, notes CRUD try-finally
- **v2.1.0 — Input Validation**: Safe int/float with try-except on ammo/fuel/radiation routes, NULL coalescing on cumulative_rem, harvest quantity >= 0 validation, search escapeAttr+parseInt, timer resp.ok, calculator tab try-catch (30 init calls)
- **v2.1.0 — Deep Audit**: teardown_appcontext DB safety net, PATCH endpoint ALLOWED_COLS pattern, set_version() XSS sanitization, safeFetch() utility + Promise.allSettled, CSS cleanup (--glass/--purple removed, focus states), CyberChef stale server cleanup, config.py specific exception types, manager.py thread locks on _processes dict + partial download cleanup, torrent.py session/monitor race condition fixes, +18 DB performance indexes (35→53), content catalogs: 210 channels, 131 videos, 102 audio, 141 books, 152 torrents
- **v2.2.0 — Ops Platform Phase 1-3**: Dashboard mode system (Command Center/Homestead/Essentials — sidebar/prep reordering, mode-aware widget sets), Live situational dashboard (/api/dashboard/live aggregates 12 modules, 12 widget types, auto-refresh 30s), AI copilot integration (quick-query with real inventory/contacts/medical/fuel/ammo data, suggested actions from alerts/expiring/overdue, pre-built question buttons on dashboard)
- **v2.3.0 — Ops Platform Phase 4+9**: Cross-module intelligence (9 survival need categories with keyword matching — Water, Food, Medical, Shelter, Security, Comms, Power, Navigation, Knowledge; /api/needs overview + /api/needs/<id> detail; needs grid on Home with drill-down modal showing supplies+contacts+books+guides), Print field copies (frequency reference card with standard freqs + team contacts, wallet-sized medical cards per patient, bug-out grab-and-go checklist with rally points)
- **v2.4.0 — Ops Platform Phase 5-7**: Enhanced maps (map_routes + map_annotations tables, route CRUD, annotation CRUD, minimap-data endpoint, 12 waypoint category icons with elevation tracking), Communications upgrade (freq_database table seeded with 35 standard frequencies — FRS/GMRS/MURS/2m/70cm/HF/Marine/CB/NOAA/Meshtastic, radio_profiles CRUD, comms dashboard API), Medical EHR upgrade (triage_events + handoff_reports tables, patient triage_category + care_phase columns, wound tourniquet_time + intervention_type columns, triage board API, SBAR handoff report generator with print, TCCC MARCH protocol endpoint)
- **v3.0.0 — Ops Platform Phase 8+10**: Instrumented power & food (sensor_devices + sensor_readings tables, sensor CRUD + time-series query with period filtering, power history charting endpoint, autonomy forecast based on SOC/load/solar trends; planting_calendar table seeded with 31 zone 7 entries including yield_per_sqft and calories_per_lb, garden yield analysis with caloric output and person-days calculation, preservation_log CRUD for canned/dried/frozen tracking), Federation v2 (federation_peers with trust levels observer/member/trusted/admin, federation_offers + federation_requests for resource marketplace, federation_sitboard for aggregated situation from peers, network-map endpoint linking peers to waypoints, auto_sync flag per peer, trust-level CRUD)

## Run / Build
```bash
python nomad.py                    # Run from source
pyinstaller build.spec             # Build portable exe -> dist/ProjectNOMAD.exe
iscc installer.iss                 # Build installer -> ProjectNOMAD-Setup.exe
```

## Release Process
```bash
# Tag and push — CI builds both artifacts
git tag v3.1.0 && git push origin v3.1.0
# Or manual: build locally, then create release
gh release create v3.1.0 dist/ProjectNOMAD-Portable.exe ProjectNOMAD-Setup.exe --title "Project N.O.M.A.D. v3.1.0"
```

## CSS Architecture
- **Inline `<style>` in index.html** — Only theme CSS variables (8 lines). Prevents flash of unstyled content.
- **web/static/css/app.css** — All base styles (themes, layout, sidebar, cards, forms, tables, etc.)
- **web/static/css/premium.css** — Visual polish overlay (typography, animations, shadows, hover effects, spring transitions, glass overlays, glow effects, reduced-motion support, print styles)
- Build spec includes `('web/static', 'web/static')` which covers the css/ subdirectory.

## Layout
- **Sidebar navigation** (fixed left, 240px) with SVG icons, matching original N.O.M.A.D.
- Collapses on mobile (<900px) with hamburger toggle + overlay
- Theme switcher + alert bell in sidebar footer
- **Status strip** at top of content area: services count, inventory total, contacts, alerts, date/time
- **LAN chat button** at left:260px (not 20px) to avoid covering sidebar footer
- `window.scrollTo(0, 0)` on every tab switch to prevent blank-space-at-top bug
- FABs (LAN Chat, Quick Actions, Timer) placed OUTSIDE `.container` div to prevent layout interference

## Service Ports
Dashboard: 8080, Ollama: 11434, Kiwix: 8888, CyberChef: 8889, Kolibri: 8300, Qdrant: 6333, Stirling: 8443, Node Discovery: UDP 18080

## 11 Main Tabs
Services, AI Chat, Library, Maps, Notes, Media, Tools, Preparedness, Benchmark, Settings (+ NukeMap opens in-app frame)

## Media Tab (5 sub-tabs)
- **Browse Channels** — 210 survival channels across 26 categories, auto-hide dead channels
- **My Videos** — Upload/download/play instructional videos, thumbnail cards, watch+download player; **131 curated tutorial videos** across 14 folders
- **My Audio** — Audio catalog with favorites, batch operations, sorting; **102 training audio entries** across 13 folders
- **My Books** — EPUB/PDF reader, book catalog; **141 reference books** (archive.org/govt URLs) across 16 folders
- **Torrent Library** — Built-in BitTorrent client (libtorrent) with live progress UI; **152 curated torrent collections** across 12 categories (survival/maps/weather/radio/textbooks/medical/farming/videos/software/encyclopedias/repair/energy)

## 25 Preparedness Sub-Tabs (ordered by emergency priority)
Inventory, Contacts, Checklists, Medical, Incidents, Family Plan, Security, Power, Garden, Weather, Guides, Calculators, Procedures, Radio, Quick Ref, Signals, Command Post, Journal, Secure Vault, Skills, Ammo, Community, Radiation, Fuel, Equipment

## Critical Gotchas
- **DECISION_GUIDES array**: ALL 21 guide objects must be inside the `];`. Placing objects after the closing bracket causes a JS syntax error that kills ALL interactivity.
- **escapeAttr function**: Contains HTML entities (`&amp;`, `&quot;`, `&lt;`) which are correct — browsers do NOT decode entities inside `<script>` tags.
- **FABs must be outside .container**: LAN Chat, Quick Actions, and Timer widgets (position:fixed) must be DOM siblings of .main-content, NOT inside .container.
- **scrollTo on tab switch**: Without `window.scrollTo(0,0)` in the tab click handler, switching from a scrolled-down tab leaves the viewport at the old scroll position.
- **Duplicate CSS removed**: Inline `<style>` in index.html now contains ONLY theme variables (8 lines). All component/layout CSS is in external app.css. Don't re-add inline CSS.
- **subprocess.PIPE blocks on Windows** — all service Popen calls MUST use subprocess.DEVNULL (4KB pipe buffer fills, process hangs forever)
- **Ollama OLLAMA_MODELS env var** — must always point to app's configured data dir. Kill any system Ollama on port 11434 before starting app's own instance
- **AI chat streaming** — must check `resp.ok` before calling `resp.body.getReader()`, otherwise 503 errors silently hang. Streaming render uses requestAnimationFrame to avoid jank.
- **DB connections** — all service files use try-finally on get_db(). Write routes (ammo, fuel, radiation, harvest, notes, media) also wrapped. SQLite timeout is 30s, FK enforcement ON.
- **Input validation** — int/float conversions on user input (ammo qty, fuel stabilizer, radiation dose) wrapped in try-except with fallback to 0. Harvest quantity forced >= 0.
- **Calculator tab init** — 30 calculator functions called on tab switch; wrapped in try-catch to prevent blank tab if any single calc fails.
- **Extra </div> tags** — psub sections can have extra closes that push settings tab outside .container. Always verify nesting after editing prep sub-tabs.
- **User data dir on G: drive** — config at `%LOCALAPPDATA%\ProjectNOMAD\config.json` → `{"data_dir":"G:\\ProjectNOMAD"}`
- NukeMap: `/nukemap` redirects to `/nukemap/` (trailing slash for relative paths)
- PyInstaller: `_bootstrap()` must skip when `sys.frozen`
- DB migrations must run BEFORE index creation
- json.loads from DB needs `or '{}'` / `or '[]'` fallback for NULL values
- Kiwix won't start without ZIM files
- Qdrant uses env var not CLI arg for storage path
- Planet PMTiles URL: `https://data.source.coop/protomaps/openstreetmap/v4.pmtiles` (build.protomaps.com is dead)
- `switchPrepSub` is overridden at bottom of script to auto-load new tab data; override must come AFTER original definition
- `switchPrepSub` override must call `loadChecklists()` for 'checklists' sub — it doesn't auto-load from the original function
- Readiness score factors in: ammo (security), fuel (shelter/power), skills proficiency (planning), trusted community members (planning)
- Equipment `markServiced()` sends full record with updated last_service + status='operational' via PUT

## UX Design Principles
- All jargon removed — plain English throughout (no Ollama/Kiwix/PMTiles/Sneakernet)
- Download sizes shown on all install/download buttons
- Empty states with helpful guidance on every panel
- Contextual help icons (?) linking to relevant user guide sections
- System presets grouped by category in dropdown
- Prep sub-tabs ordered by emergency priority (Inventory first)
- Quick-add templates for 58 common inventory items across 8 categories
- Status strip shows key metrics at a glance
- Debounced search inputs (media filter, channel filter) at 200ms
- Error feedback on destructive actions (map delete, vault delete, model delete)
