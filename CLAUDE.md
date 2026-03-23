# Project N.O.M.A.D. for Windows

## Overview
Native Windows port of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — the most comprehensive offline survival command center available. No Docker required. 6 managed services, proactive AI alerts, 10 interactive decision guides, medical module, training scenarios, food production, multi-node federation, power management, security cameras, AI document intelligence, 38-section user guide, and a premium dark dashboard with 4 themes. All 10 roadmap phases complete.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2) embedded browser
- **SQLite** — 35 tables, WAL mode, auto-backups, performance indexes
- **CSS** — External files: `web/static/css/app.css` (base) + `web/static/css/premium.css` (polish layer)
- **Native process management** — subprocess for Ollama, kiwix-serve, Kolibri; threading HTTP server for CyberChef
- **pystray** — system tray icon for background operation
- **psutil** — system info (CPU via background monitor thread, RAM, GPU detection, disk devices)
- **MapLibre GL JS + PMTiles** — bundled locally (no CDN dependencies)
- **NukeMap v3.2.0** — 18 JS modules + Leaflet (bundled locally)
- **epub.js** — EPUB reader (bundled locally, `web/static/js/epub.min.js`)
- **yt-dlp** — video/audio downloader (auto-installed to services dir)
- **FFmpeg** — audio conversion (optional, auto-installed for MP3 extraction)

## Project Structure
```
nomad.py              # Entry point — Flask + WebView2 + tray + health monitor + service autostart
db.py                 # SQLite init (32 tables), indexes, migrations (migrations BEFORE indexes)
config.py             # Data directory management
build.spec            # PyInstaller spec for portable exe
icon.ico              # App icon (multi-size, 16-256px)
installer.iss         # Inno Setup installer script (v1.0.0)
ROADMAP.md            # 10-phase implementation plan (all complete)
.github/workflows/
  build.yml           # CI/CD — PyInstaller + Inno Setup, dual artifact release on tag push
web/
  app.py              # Flask routes (~260 endpoints) — ~6500 lines
  static/
    css/
      app.css         # Base styles (1117 lines) — themes, layout, components
      premium.css     # Premium polish (421 lines) — animations, shadows, hover effects
    logo.png          # App logo
    maplibre-gl.js    # Map renderer (bundled)
    maplibre-gl.css   # Map styles (bundled)
    pmtiles.js        # Tile format handler (bundled)
    js/
      epub.min.js     # EPUB reader library (bundled)
  templates/
    index.html        # HTML + inline theme vars + JS (~12,500 lines)
  nukemap/            # NukeMap v3.2.0 — index.html, 18 JS modules, CSS, data/, lib/leaflet
services/
  manager.py          # Process manager — download (with resume), start, stop, track, uninstall
  ollama.py           # Ollama AI
  kiwix.py            # Kiwix
  cyberchef.py        # CyberChef
  kolibri.py          # Kolibri education
  qdrant.py           # Qdrant vector DB
  stirling.py         # Stirling PDF
```

## Version
v1.0.0 — ~35,000 lines, 231 API routes, 32 DB tables, 19 prep sub-tabs, 38-section user guide

## Run / Build
```bash
python nomad.py                    # Run from source
pyinstaller build.spec             # Build portable exe → dist/ProjectNOMAD.exe
iscc installer.iss                 # Build installer → ProjectNOMAD-Setup.exe
```

## Release Process
```bash
gh release delete v1.0.0 --yes
git push origin :refs/tags/v1.0.0
git tag -d v1.0.0
git tag v1.0.0
git push origin v1.0.0
# CI auto-builds both artifacts and creates release
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

## 19 Preparedness Sub-Tabs (ordered by emergency priority)
Inventory, Contacts, Checklists, Medical, Incidents, Family Plan, Security, Power, Garden, Weather, Guides, Calculators, Procedures, Radio, Quick Ref, Signals, Command Post, Journal, Secure Vault

## Key APIs Added
- `/api/readiness-score` — 7 categories (water/food/medical/security/comms/shelter/planning), letter grades A-F
- `/api/inventory/<id>/consume` — decrement by daily_usage or custom amount
- `/api/inventory/batch-consume` — one-click daily consume for all tracked items
- `/api/data-summary` — record counts across all 32 tables

## 38-Section User Guide
`showHelp(section)` opens an iframe-based guide with optional scroll-to anchor.
28 contextual help icons (?) throughout the app link to relevant guide sections.
Sections cover: getting started, all 9 tabs, all 19 prep sub-tabs, AI model selection, inventory best practices, printable reports, calculators reference, NukeMap guide, medical/garden/power/security/weather/comms/vault in-depth guides, training scenarios, FAQ, and glossary.

## Critical Gotchas
- **DECISION_GUIDES array**: ALL 10 guide objects must be inside the `];`. Placing objects after the closing bracket causes a JS syntax error that kills ALL interactivity. Verify with `node -e "vm.createScript(script)"`.
- **escapeAttr function**: Contains HTML entities (`&amp;`, `&quot;`, `&lt;`) which are correct — browsers do NOT decode entities inside `<script>` tags. Node.js testing with manual HTML decode gives false positives.
- **FABs must be outside .container**: LAN Chat, Quick Actions, and Timer widgets (position:fixed) must be DOM siblings of .main-content, NOT inside .container. Being inside .container between tab-content divs causes layout interference.
- **scrollTo on tab switch**: Without `window.scrollTo(0,0)` in the tab click handler, switching from a scrolled-down tab leaves the viewport at the old scroll position, showing blank space.
- **Duplicate CSS removed**: Inline `<style>` in index.html now contains ONLY theme variables (8 lines). All component/layout CSS is in external app.css. Don't re-add inline CSS.
- NukeMap: `/nukemap` redirects to `/nukemap/` (trailing slash for relative paths)
- PyInstaller: `_bootstrap()` must skip when `sys.frozen`
- DB migrations must run BEFORE index creation
- json.loads from DB needs `or '{}'` / `or '[]'` fallback for NULL values
- Nested f-strings require Python 3.12+ — extract to variables
- Kiwix won't start without ZIM files
- Qdrant uses env var not CLI arg for storage path
- Planet PMTiles URL: `https://data.source.coop/protomaps/openstreetmap/v4.pmtiles` (build.protomaps.com is dead)
- Media tab has 3 sub-tabs (Videos/Audio/Books) sharing the same sidebar folder navigation
- yt-dlp.exe and ffmpeg.exe are auto-installed to services dir, not bundled
- epub.js is bundled (`web/static/js/epub.min.js`), PDFs use WebView2's built-in PDF viewer via iframe
- Book catalog URLs point to Internet Archive — may change or go down

## UX Design Principles
- All jargon removed — plain English throughout (no Ollama/Kiwix/PMTiles/Sneakernet)
- Download sizes shown on all install/download buttons
- Empty states with helpful guidance on every panel
- Contextual help icons (?) linking to relevant user guide sections
- System presets grouped by category in dropdown
- Prep sub-tabs ordered by emergency priority (Inventory first)
- Quick-add templates for 58 common inventory items across 8 categories
- Status strip shows key metrics at a glance
