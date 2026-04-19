# Project N.O.M.A.D. — Roadmap

> **Baseline:** v7.44.0 (~310 tables, 2,000+ routes, 77 blueprints)
> **Updated:** 2026-04-19

---

## Competitor Analysis

NOMAD Desktop occupies a unique niche: an offline-first, all-in-one preparedness command center with local AI integration. No single competitor covers the full scope. The comparison below maps overlapping tools whose UX patterns or feature depth can inform improvements.

| Project | Stars | Category | What They Do Better | Missing from NOMAD |
|---------|-------|----------|--------------------|--------------------|
| [Crosstalk-Solutions/project-nomad](https://github.com/Crosstalk-Solutions/project-nomad) | ~22k | Upstream (Docker) | Polished onboarding wizard, content-pack marketplace UI, one-click Docker deploy, wider community & YouTube ecosystem (475K subscribers) | Content-pack download UI comparable to an app store; guided first-run experience with progress tracking |
| [grocy/grocy](https://github.com/grocy/grocy) | ~8.8k | Household ERP | Barcode-to-product lookup via OpenFoodFacts, recipe-driven consumption (auto-deduct ingredients), chore scheduling with user assignment, battery replacement tracker, full Swagger UI API docs, Home Assistant integration | Recipe-driven auto-consumption, product database lookup, chore/maintenance scheduler with assignees, HA integration |
| [sysadminsmedia/homebox](https://github.com/sysadminsmedia/homebox) | ~5.7k | Home Inventory | QR code label printing per item, warranty & maintenance schedule tracking, receipt/document attachments per item, ultra-light resource usage (~50 MB RAM), nested tag hierarchies (parent/child), fractional quantities, OpenTelemetry tracing | QR label generation per inventory item, warranty tracking fields, nested tag trees, fractional quantities |
| [glanceapp/glance](https://github.com/glanceapp/glance) | ~32k | Dashboard | YAML-based widget config (no code), clean card-based layout with consistent spacing, RSS/Reddit/HN/GitHub/weather widgets with minimal setup, single binary in Go (~50 MB RAM), responsive mobile-first design | Declarative widget configuration file, cleaner card density on home page, drastically lower resource usage |
| [gethomepage/homepage](https://github.com/gethomepage/homepage) | ~29.6k | Dashboard | 100+ service integrations with live status, Docker auto-discovery, bookmarks/quick-launch groups, per-widget refresh intervals, i18n with 40+ languages | Service health widget auto-discovery, bookmark groups, deeper i18n (NOMAD has 10 languages / 56 keys) |
| [Lissy93/dashy](https://github.com/Lissy93/dashy) | ~24.7k | Dashboard | Visual UI config editor (no YAML), 50+ built-in widgets, multi-page workspaces, icon packs, status checks with history graph, Keycloak/OIDC auth | Visual drag-and-drop dashboard editor, status check history graphs, icon pack system |
| [iiab/iiab](https://github.com/iiab/iiab) | ~1.8k | Offline Knowledge | Multi-language content packs with regional catalogs, Kolibri + Sugarizer + Moodle integration, mesh networking support, SD-card-ready images for Raspberry Pi | Regional content catalogs with language filters, education platform integrations |
| [ligi/SurvivalManual](https://github.com/ligi/SurvivalManual) | ~2.5k | Survival Reference | Illustrated survival manual with offline search, chapter-based navigation, lightweight (single APK), community translations | Illustrated inline survival reference content (NOMAD links to external books/ZIMs instead) |
| [Prepper Nerd UPS](https://prepper-nerd.com/) | Commercial | Prep Inventory | Barcode scanning with auto-fill (description, calories, servings), calorie-per-day burn-down dashboard, insurance/warranty tracker, personalized prep coaching, Excel/PDF export scheduling | Auto-fill from barcode product database, insurance tracker, scheduled report exports |
| [meshtastic/web](https://github.com/meshtastic/web) | ~1.5k | Mesh Comms | Real-time node map with signal quality, message threading, channel management UI, Bluetooth/serial/HTTP transport selection, position sharing, Home Assistant integration | Direct Meshtastic serial integration (NOMAD has stub), signal quality visualization |
| [s-samarth/survive-ai](https://github.com/s-samarth/survive-ai) | New | Offline AI Survival | On-device AI (Gemma 2B, 4 GB RAM), RAG-grounded answers with citations from curated survival docs, conflict-zone + wilderness focus, ~500 MB total footprint | Lighter AI fallback model option for low-spec hardware; RAG specifically tuned for survival docs |
| [ShAd0wZi/Offline-Survival-KIt](https://github.com/ShAd0wZi/Offline-Survival-KIt) | New | Survival PWA | Zero-dependency React PWA, 6 pre-loaded illustrated survival guides, one-click "Download All" for offline sync, instant search, extremely lightweight | Bundled illustrated step-by-step survival guides as first-class content (not external ZIM) |
| [sahana/eden](https://github.com/sahana/eden) | ~21 | Emergency Mgmt | ICS/NIMS incident command integration, volunteer management, shelter/camp tracking, missing persons registry, formal humanitarian coordination workflows | Formal ICS organizational charts, volunteer skill matching at scale, shelter capacity tracking |

### Key Gaps Identified

1. **Onboarding & First-Run** — No guided setup wizard; new users face a wall of 33+ tabs
2. **Inventory UX** — No barcode-to-product database lookup, no QR label printing, no recipe-driven auto-consumption
3. **Dashboard configurability** — Widget layout is code-driven, not user-configurable beyond show/hide toggles
4. **i18n depth** — 10 languages with only 56 keys each; competitors offer 40+ languages with full coverage
5. **Maintenance scheduling** — No recurring maintenance reminders for equipment/vehicles/generators
6. **Data export scheduling** — No automated periodic export (email/file) of inventory or reports
7. **API documentation** — No Swagger/OpenAPI spec for the 2,000+ routes
8. **Survival reference content** — Relies on external ZIMs; no built-in illustrated quick-reference
9. **Meshtastic integration** — Stub only; no real serial/BLE bridge
10. **Resource footprint** — Glance runs in 50 MB RAM; NOMAD has no lightweight/minimal mode for constrained hardware

---

## Deep Dive: Glance (~32k stars)

**Repo**: [glanceapp/glance](https://github.com/glanceapp/glance) | **Latest**: v0.8.4 (2025-06-10) | **Stack**: Go, single binary (<20 MB), vanilla JS, YAML config

### What They Do Better

1. **Declarative YAML configuration with hot-reload** — Config changes take effect on save without restart. Glance never touches a database for layout; everything is a flat YAML file. This makes backup, version control, and sharing trivial. NOMAD's widget/dashboard config is scattered across localStorage, DB settings, and JS objects.
2. **`$include` directive for modular configs** — Users split config into `home.yml`, `videos.yml`, `homelab.yml` and compose them. Encourages reuse and sharing of preconfigured page templates (Glance ships 3: Startpage, Markets, Gaming).
3. **Community widgets ecosystem** — Separate [community-widgets](https://github.com/glanceapp/community-widgets) repo lets users contribute custom widget types without forking the main project. Plugin boundary is well-defined (custom-api widget + extension widget + HTML widget + iframe widget).
4. **Icon library system** — 4 icon packs via prefix (`si:`, `sh:`, `di:`, `mdi:`) from CDN, plus `auto-invert` for theme-aware icons. NOMAD uses inline SVGs and emoji; no unified icon vocabulary.
5. **Extreme resource efficiency** — <20 MB binary, minimal RAM. Pages load in ~1s. No background workers unless explicitly configured. Cache TTLs are per-widget, not global.
6. **Preconfigured page templates** — Ship-ready layouts (Startpage, Markets, Gaming) that users copy-paste. Lowers the "blank canvas" intimidation factor.
7. **Environment variable injection anywhere** — `${ENV_VAR}` syntax works in any YAML value, plus Docker secrets support via `${secret:name}` and file-based secrets via `${readFileFromEnv:VAR}`.

### Top Feature Requests (by thumbs-up)

| Votes | Issue | NOMAD Relevance |
|-------|-------|-----------------|
| 23 | Auto-refresh page/widget content on interval (#327) | NOMAD has SSE + polling but no per-widget configurable refresh intervals |
| 17 | Translation/i18n support (#61) | NOMAD has 10 languages but only 56 keys; Glance has none yet — opportunity to lead |
| 15 | Calendar events / CalDAV support (#94, #902) | NOMAD has no calendar integration; could add offline ICS/CalDAV reader |
| 13 | Miniflux RSS reader integration (#313) | NOMAD's Situation Room has RSS but not personal feed reader integration |
| 12 | Proxmox monitoring (#349) | Infrastructure monitoring not in scope but shows demand for system metrics |
| 11 | GitHub Trending widget (#72) | Interesting for Knowledge/Intel section |
| 11 | GUI config editor (#221) | NOMAD has customize panel but no visual widget/page layout editor |
| 10 | Swipe navigation on mobile (#128) | NOMAD's mobile bottom nav could benefit from swipe between tabs |
| 10 | Address-bar-style search (#229) | NOMAD's Ctrl+K search could act as URL bar for services |
| 9 | Automatic theme switching (day/night) (#674) | NOMAD has night mode but it's manual; could auto-switch by sunrise/sunset |
| 9 | OIDC/SSO authentication (#905) | NOMAD has basic auth; OIDC would help LAN multi-user deployments |

### Architectural Decisions to Adopt

- **Per-widget cache TTL**: Each widget declares its own cache lifetime instead of a global refresh rate. More efficient for mixed-frequency data.
- **Config-as-code philosophy**: Exportable/importable dashboard config files make sharing setups between users trivial.
- **Preconfigured templates**: Ship ready-to-use page layouts that new users can start from instead of building from scratch.

---

## Deep Dive: Homepage (~29.6k stars)

**Repo**: [gethomepage/homepage](https://github.com/gethomepage/homepage) | **Latest**: v1.12.3 (2026-04-01) | **Stack**: Next.js, statically generated, YAML config

### What They Do Better

1. **150+ service widget integrations** — From Plex to Proxmox to Sonarr to Home Assistant, Homepage has pre-built widgets for essentially every self-hosted app. Each widget knows the service's API and displays relevant stats (active streams, queue sizes, storage usage). NOMAD manages 8 services but doesn't integrate with external self-hosted apps.
2. **Docker auto-discovery via labels** — Services running in Docker are automatically detected and added to the dashboard via container labels. Zero manual configuration for new services.
3. **Full i18n via Crowdin** — 40+ languages with community translations managed through Crowdin, ensuring coverage stays current. NOMAD's 10 languages with 56 keys is thin by comparison.
4. **Proxied API requests** — All backend API calls are server-side proxied, keeping API keys hidden from the browser. This is a strong security pattern NOMAD could adopt for federation/external API calls.
5. **Statically generated pages** — Next.js static generation means instant page loads. While NOMAD's Flask+SSR approach is different, the lesson is clear: minimize client-side rendering for dashboard views.
6. **Bookmark groups with favicons** — Quick-launch bookmark sections with auto-fetched favicons. Simple but highly useful for a command center.
7. **Custom API widget** — A generic widget that can query any JSON API and render results with a configurable template. This is the extensibility escape hatch that avoids needing a plugin system.
8. **Resource widgets (CPU/RAM/disk/uptime)** — Built-in system monitoring widgets with clean, consistent presentation. GPU temperature was a top request (#86, 16 votes).
9. **Calendar widget with iCal support** — Displays upcoming events from any iCal/CalDAV feed. Practical for ops planning.

### Top Feature Requests (closed issues, by thumbs-up)

| Votes | Issue | NOMAD Relevance |
|-------|-------|-----------------|
| 25 | Deluge widget (#190) | Shows demand for torrent client status widgets — NOMAD has built-in torrent but no dashboard widget |
| 19 | Audiobookshelf widget (#525) | Media library integration demand |
| 16 | CPU temperature (#86) | NOMAD shows CPU% but not temp; psutil can read temps on Linux |
| 15 | Sonarr calendar widget (#242) | Calendar/scheduling demand |
| 15 | Server uptime display (#240) | Already in NOMAD backlog as P1-15 |
| 12 | Config variables (#60) | Glance solved this; NOMAD should too |
| 11 | Favicon auto-fetch for bookmarks (#174) | Useful for service links/bookmarks |
| 10 | Home Assistant integration (#683) | Already in NOMAD backlog as P3-15 |
| 8 | Custom widget support (#467) | Generic widget renderer for arbitrary APIs |

### Architectural Decisions to Adopt

- **Server-side API proxying**: Never expose API keys to the browser. Route all external API calls through the Flask backend.
- **Widget integration manifest**: Each widget is a self-contained module with a defined interface. Makes adding new integrations systematic.
- **Crowdin for i18n management**: Professional translation management instead of manual JSON file editing.

---

## Deep Dive: Dashy (~24.7k stars)

**Repo**: [Lissy93/dashy](https://github.com/Lissy93/dashy) | **Latest**: 3.3.0 (2026-04-15) | **Stack**: Vue.js, Node.js, YAML config, Docker

### What They Do Better

1. **Visual config editor with live preview** — Right-click any section to edit it. Enter "Edit Mode" to click any part of the page and modify it inline. Changes preview instantly before saving. This is the gold standard for dashboard configuration UX.
2. **Multi-view architecture** — Three distinct views: Default (full dashboard), Minimal (browser startpage), and Workspace (multi-app simultaneous view with iframe panels). NOMAD could offer a "Startpage" minimal view.
3. **70+ built-in widgets** — Clock, weather, RSS, crypto, stocks, system info, Pi-Hole, Proxmox, Nextcloud, code stats, flight data, sports scores, XKCD, NASA APOD, GitHub trending, vulnerability feeds, exchange rates, public holidays, transit status, and more. Many are fun/lifestyle widgets that make the dashboard feel personal.
4. **Comprehensive icon system** — Font Awesome, Simple Icons, selfh.st homelab icons, Material Icons, emoji, generative identicons, URL images, and local files. Auto-favicon fetching from service URLs.
5. **SSO/OIDC authentication** — Full Keycloak integration with multi-user access, per-user permissions (admin vs read-only guest), and granular visibility controls per section/item.
6. **Cloud backup & sync** — E2E encrypted config backup to Cloudflare Workers/KV. Restore on any instance. Config portability without self-hosting a sync server.
7. **Opening methods** — Items can open in: new tab, same tab, modal popup, workspace iframe, or copy URL to clipboard. Right-click for all options. NOMAD services only open in new tabs.
8. **Search bangs** — Prefix-based search routing: `/r` → Reddit, `/w` → Wikipedia, `!so` → StackOverflow. Customizable per-user.
9. **Custom hotkeys per item** — Assign number keys 0-9 to frequently used services for instant launch.
10. **30+ community-translated languages** — Including Pirate (arr!). Human-translated, not auto-generated.

### Top Feature Requests (by thumbs-up)

| Votes | Issue | NOMAD Relevance |
|-------|-------|-----------------|
| 11 | Header authentication (#981) | Auth proxy support (Authelia/Authentik) — useful for LAN multi-user |
| 10 | Calendar widget (#1201) | Third time this appears across competitors — clear demand |
| 6 | Font Awesome v6 (#1424) | Icon library versioning |
| 5 | qBittorrent queue widget (#1122) | Torrent status widget demand — NOMAD has torrent built in |
| 5 | Health check endpoint (#768) | `/healthz` endpoint for monitoring Dashy itself |
| 4 | Random image/video background (#721) | Cosmetic personalization |
| 4 | Masonry layout (#1233) | Pinterest-style auto-filling grid layout |
| 3 | Notes widget (#636) | Note-taking on dashboard — NOMAD already has full Notes module |
| 3 | Dual URL per item (#820) | Internal vs external URL for same service |

### Architectural Decisions to Adopt

- **Right-click context menus**: Every dashboard element has a context menu with Edit, Move, Delete, Open In... options. Much faster than navigating to a settings page.
- **Workspace/iframe multi-app view**: Open multiple services simultaneously in tiled iframes. Useful for monitoring multiple NOMAD modules side by side.
- **Search bangs**: Custom search shortcuts that route to specific tools/modules. Could map `/i` → inventory search, `/m` → medical, `/c` → contacts.
- **Cloud-synced config backup**: E2E encrypted config backup for federation/multi-node deployments.
- **Minimal startpage mode**: A stripped-down view showing only bookmarks + search + clock for use as a browser start page.

---

## Improvement Backlog

### P1: Quick Wins (< 1 hour each)

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P1-01 | **Loading skeletons on all tabs** | Add shimmer placeholder skeletons to remaining tabs that lack them (Medical, Garden, Radio, etc.) — Situation Room already has them | Glance, Dashy |
| P1-02 | **Empty-state illustrations** | Replace plain "No data" text with helpful empty-state cards that explain what the section does and have a CTA button | Homebox, Homepage |
| P1-03 | **Keyboard shortcut cheat sheet modal** | Add `?` shortcut overlay showing all available keyboard shortcuts in a searchable grid | Dashy |
| P1-04 | **Tab badge counts** | Show unread/actionable counts on sidebar tabs (e.g., overdue tasks, expiring items, unread messages) | Homepage, Glance |
| P1-05 | **Favicon dynamic badge** | Update browser favicon with alert count badge when alerts are active | Glance |
| P1-06 | **Collapsible sidebar groups** | Let users collapse sidebar group headers (OVERVIEW, INTEL, etc.) to reduce visual noise; persist state to localStorage | Dashy |
| P1-07 | **Settings search/filter** | Add a search box at the top of Settings to filter visible setting rows | Grocy |
| P1-08 | **Inventory quick-edit inline** | Double-click inventory quantity to edit inline without opening full edit modal | Grocy |
| P1-09 | **Toast action buttons** | Add "Undo" action button on delete toasts (leverage existing undo system with 30s TTL) | Homebox |
| P1-10 | **Print preview in-app** | Show print preview in a modal/iframe instead of opening a new browser tab | Upstream NOMAD |
| P1-11 | **Relative timestamps** | Show "2 hours ago" / "3 days ago" alongside absolute timestamps in activity log and alerts | Glance, Dashy |
| P1-12 | **Confirm before bulk operations** | Add confirmation count ("Delete 12 items?") on all bulk-delete actions | Homebox |
| P1-13 | **Auto-focus search on Ctrl+K** | Ensure global search input auto-focuses and selects existing text when opened | Dashy |
| P1-14 | **Inventory sort persistence** | Persist the user's last-used sort column/direction in localStorage | Grocy |
| P1-15 | **Service uptime display** | Show how long each managed service has been running (uptime) on service cards | Homepage |
| P1-16 | **Expiry countdown badges** | Show "Expires in 3 days" warning badges on inventory items nearing expiration, not just color-coded rows | Grocy, Prepper Nerd |
| P1-17 | **Sidebar item reorder** | Let users drag sidebar items within groups to reorder; persist to localStorage | Dashy |
| P1-18 | **Copy-to-clipboard on data cells** | Click-to-copy on coordinates, frequencies, callsigns, and other reference data | Meshtastic Web |

### P2: Medium Features (1-4 hours each)

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P2-01 | **First-run onboarding wizard** | 5-step guided wizard on first launch: set location, pick dashboard mode, install first content pack, configure AI, import sample data | Upstream NOMAD |
| P2-02 | **Barcode product database lookup** | On barcode scan, query bundled UPC database + OpenFoodFacts offline dump for product name, calories, category auto-fill | Grocy, Prepper Nerd |
| P2-03 | **QR code label generation** | Generate printable QR code labels for inventory items linking to their detail page; batch print sheet layout | Homebox |
| P2-04 | **Recipe-driven consumption** | Add recipes that reference inventory items; "Cook this" button auto-deducts ingredient quantities and logs the meal | Grocy |
| P2-05 | **Equipment maintenance scheduler** | Recurring maintenance reminders for generators, vehicles, water filters, etc. with overdue alerts and history log | Homebox, Prepper Nerd |
| P2-06 | **Drag-and-drop widget reorder** | Let users drag widgets on the home page to reorder with visual drop zones; persist layout to localStorage/DB | Dashy, Glance |
| P2-07 | **OpenAPI/Swagger spec** | Auto-generate OpenAPI 3.0 spec from Flask routes + validation schemas; serve Swagger UI at `/api/docs` | Grocy |
| P2-08 | **Expanded i18n coverage** | Increase translation keys from 56 to 200+ covering all UI labels, button text, and error messages; add Spanish and French complete coverage first | Homepage (40+ languages) |
| P2-09 | **Inventory location hierarchy** | Support nested locations (Building > Room > Shelf > Bin) with tree view and breadcrumb navigation | Homebox, Grocy |
| P2-10 | **Scheduled report export** | Configurable weekly/monthly auto-export of inventory summary, readiness score, and alerts to PDF/CSV in data dir | Prepper Nerd |
| P2-11 | **Content pack browser** | Dedicated UI for browsing available data packs (ZIMs, maps, books) with search, categories, size indicators, and one-click install | Upstream NOMAD |
| P2-12 | **Service health history graph** | Track service up/down over time in `service_health_log` table; show sparkline uptime graph on each service card | Dashy, Homepage |
| P2-13 | **Inline survival quick-reference** | Bundle a curated offline survival reference (water purification, fire, shelter, first aid, navigation) as searchable built-in cards with illustrations instead of external ZIM dependency | SurvivalManual, Offline-Survival-Kit |
| P2-14 | **Multi-user profiles** | Support multiple named profiles (family members) with per-user preferences and optional PIN lock | Prepper Nerd |
| P2-15 | **Inventory item photos gallery** | Grid view of all inventory photos with lightbox zoom; filter by category; click to jump to item detail | Homebox |
| P2-16 | **Map bookmark/favorite locations** | Star frequently-used map locations for quick jump; show in a "Favorites" sidebar panel on map tab | Upstream NOMAD |
| P2-17 | **Notification center panel** | Unified notification drawer (slide-out) aggregating alerts, task due dates, expiring items, service events with mark-as-read | Homepage, Glance |
| P2-18 | **CSV export for all entities** | One-click CSV export button on every list view (contacts, medical, tasks, garden, livestock, etc.), not just inventory | Grocy |
| P2-19 | **Inventory fractional quantities** | Support decimal quantities (0.5 kg, 1.25 L) with configurable unit display | Homebox |
| P2-20 | **Task assignment to contacts** | Assign scheduled tasks to specific family members/contacts; filter task view by assignee | Grocy |
| P2-21 | **Battery/consumable tracker** | Track batteries and consumable parts in devices (flashlights, radios, filters) with replacement date reminders and low-stock alerts | Grocy |

### P3: Nice-to-Haves and Polish

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P3-01 | **Animated page transitions** | Subtle slide/fade transitions between tabs instead of instant swap; respect `prefers-reduced-motion` | Dashy |
| P3-02 | **Dashboard theme previews** | Show live mini-preview of each theme in the theme picker instead of just a color swatch | Dashy |
| P3-03 | **Inventory heatmap calendar** | Calendar view showing daily additions/consumptions as a GitHub-style contribution heatmap | Grocy |
| P3-04 | **Command palette** | Ctrl+K opens a VS Code-style command palette for jumping to any section, running actions, searching across all entities | Dashy |
| P3-05 | **Customizable status strip** | Let users choose which metrics appear in the top status strip via drag-and-drop config | Glance |
| P3-06 | **Meshtastic serial bridge** | Real Meshtastic integration via serial/USB with node map, signal quality display, message threading, and channel config | Meshtastic Web |
| P3-07 | **Offline plant identification** | Bundled lightweight ML model for plant ID from camera photos (edible vs toxic classification) | SurvivalManual |
| P3-08 | **Insurance & warranty tracker** | Track warranties, insurance policies, and important document expiry dates with reminders and document attachments | Homebox, Prepper Nerd |
| P3-09 | **Visual alert rule builder** | Drag-and-drop UI for building compound alert rules with AND/OR logic (backend already supports evaluation) | Internal backlog |
| P3-10 | **Plugin/extension API** | Define hook points and a simple plugin manifest so community can add custom tabs/routes without forking | Dashy |
| P3-11 | **Tauri shell alternative** | Replace pywebview with Tauri for smaller binary, faster startup, and native feel | Internal backlog |
| P3-12 | **SBOM generation** | Generate Software Bill of Materials on each release for supply-chain transparency | Internal backlog |
| P3-13 | **Regional content packs** | Pre-configured data bundles for Canada (ECCC), UK (Met Office), EU (Copernicus), Australia (BOM) with localized weather sources | IIAB |
| P3-14 | **Lightweight/minimal mode** | Startup flag or setting to disable Situation Room, heavy services, and background workers for Raspberry Pi / low-RAM hardware | Glance, Survive-AI |
| P3-15 | **Home Assistant integration** | MQTT or REST bridge to expose NOMAD sensor data (power, weather, inventory counts) to Home Assistant | Grocy, Meshtastic HA |

### P4: Deep-Dive Discoveries (from competitor research loop 2)

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P4-01 | **Per-widget refresh intervals** | Let each dashboard widget declare its own auto-refresh interval (e.g., weather 30min, alerts 60s, services 10s) instead of a single global refresh rate; store in widget config | Glance (per-widget cache TTL) |
| P4-02 | **Preconfigured dashboard templates** | Ship 3-5 ready-to-use dashboard layouts (Minimal Startpage, Full Command Center, Homestead, Field Ops, Family Hub) that users select on first run or from Settings; each template pre-configures visible tabs, widget order, and theme | Glance (preconfigured pages) |
| P4-03 | **Exportable/importable dashboard config** | Export entire dashboard configuration (visible tabs, widget layout, theme, sidebar order, zoom level) as a single JSON/YAML file; import on another instance or share with community | Glance (config-as-code), Dashy (cloud backup) |
| P4-04 | **Calendar widget with ICS/CalDAV support** | Offline calendar widget displaying events from local `.ics` files or cached CalDAV feeds; show upcoming events on home dashboard; integrate with task scheduler due dates | Glance (#94, 15 votes), Homepage (calendar widget), Dashy (#1201, 10 votes) |
| P4-05 | **Custom API widget renderer** | Generic widget type that fetches any JSON API endpoint (internal or external) and renders results using a user-defined HTML/Mustache template; acts as an extensibility escape hatch | Glance (custom-api widget), Homepage (customapi widget), Dashy (API response widget) |
| P4-06 | **Search bangs / module shortcuts** | Ctrl+K search supports prefix shortcuts: `/i query` searches inventory, `/m` medical, `/c` contacts, `/n` notes, `/w` waypoints, `/f` frequencies; user-configurable in Settings | Dashy (search bangs) |
| P4-07 | **Right-click context menus on dashboard elements** | Right-click any service card, widget, inventory item, or contact for contextual actions (Edit, Delete, Copy, Open, Pin) instead of navigating to a separate edit view | Dashy (right-click edit) |
| P4-08 | **Minimal startpage mode** | A stripped-down view showing only search bar, clock, bookmarks grid, and service status indicators; usable as a browser start page; toggle via Settings or URL parameter `?view=minimal` | Dashy (minimal view) |
| P4-09 | **Workspace/tiled multi-panel view** | Open 2-4 NOMAD modules simultaneously in a tiled iframe layout (e.g., Map + Inventory + Contacts side-by-side); useful for multi-monitor or ultrawide setups | Dashy (workspace view) |
| P4-10 | **Auto theme switching (day/night schedule)** | Automatically switch between dark and light themes based on sunrise/sunset times (already have `/api/sun` endpoint) or a user-defined schedule; configurable in Settings | Glance (#674, 9 votes) |
| P4-11 | **Service opening methods** | Service cards offer multiple launch options: open in new tab, open in modal/iframe overlay, open in workspace panel, copy URL to clipboard; right-click or dropdown selector per service | Dashy (opening methods) |
| P4-12 | **Favicon auto-fetch for services and bookmarks** | Automatically fetch and cache favicons from service URLs for display on service cards and any bookmark/link widgets; fall back to generated identicon | Homepage (#174, 11 votes), Dashy (favicon icon type) |
| P4-13 | **CPU/GPU temperature monitoring** | Add CPU and GPU temperature readings to system info (psutil `sensors_temperatures()` on Linux, WMI on Windows); display on System Health card with high-temp alerts | Homepage (#86, 16 votes) |
| P4-14 | **Torrent status dashboard widget** | Home page widget showing active torrent count, total download/upload speed, seeding ratio, and storage used; leverages existing TorrentManager API | Homepage (Deluge widget, #190, 25 votes) |
| P4-15 | **Auth proxy / header authentication** | Support `X-Forwarded-User` and `X-Remote-User` headers from auth proxies (Authelia, Authentik, Caddy forward_auth) for seamless LAN multi-user without NOMAD's own auth | Dashy (#981, 11 votes), Glance (#905, 9 votes) |
| P4-16 | **Mobile swipe navigation** | Swipe left/right between tabs on mobile (touch event handlers on `.content` area); visual tab indicator dots; configurable gesture sensitivity | Glance (#128, 10 votes) |
| P4-17 | **Icon library system** | Unified icon prefix system for all UI elements: `fa:` (Font Awesome), `si:` (Simple Icons), `mdi:` (Material Design Icons), `emoji:`, `url:` (custom image URL); replaces current mix of inline SVGs and emoji | Glance (4 icon prefixes), Dashy (7 icon types) |
| P4-18 | **Config environment variable injection** | Support `${ENV_VAR}` syntax in NOMAD config.json for secrets, API keys, and per-deployment overrides; useful for federation nodes with different credentials | Glance (env var injection), Homepage (env vars in YAML) |
| P4-19 | **Health check endpoint** | `GET /healthz` returns 200 with JSON `{status, uptime, db_ok, services_count}` for external monitoring tools (UptimeKuma, Prometheus, etc.) to monitor NOMAD itself | Dashy (#768, 5 votes) |
| P4-20 | **Masonry/auto-fill grid layout** | Alternative dashboard layout where cards auto-fill available space in a masonry pattern (no fixed rows); especially useful for varying-height widgets on ultrawide monitors | Dashy (#1233, 4 votes) |

---

## UX Improvements

Issues identified from competitor analysis and UX review of the current app.

### Navigation & Information Architecture

| # | Issue | Recommendation |
|---|-------|----------------|
| U-01 | **Tab overload** — 33+ tabs visible in sidebar is overwhelming for new users | Default to showing only core tabs (8-10); use "Show More" expansion or the existing customize panel more aggressively; consider collapsible groups defaulting to collapsed |
| U-02 | **No breadcrumb trail** — deep sub-tabs (Prep > Supplies > Inventory) have no visual path indicator | Add breadcrumb bar below status strip showing current navigation path |
| U-03 | **Prep category double-navigation** — category buttons + sub-tab buttons is two layers of clicks | Consider merging into a single accordion or tree-based navigation |
| U-04 | **Sidebar sub-menus auto-show** — expanding sub-menus push other items down unexpectedly | Use flyout sub-menus on hover (desktop) or dedicated back-navigation (mobile) instead of inline expansion |

### Visual Design & Consistency

| # | Issue | Recommendation |
|---|-------|----------------|
| U-05 | **Card height inconsistency** — service cards, need cards, and dashboard cards have different heights | Standardize card heights within each grid using `min-height` or `aspect-ratio` |
| U-06 | **Dense information overload** — home page tries to show everything at once | Default to a focused dashboard (3-4 key widgets) with a "Show all sections" toggle |
| U-07 | **Status strip too subtle** — important status info is easy to miss in thin strip | Make status strip expandable; click to see detail panel |
| U-08 | **Inconsistent button styles** — mix of primary/secondary/ghost buttons without clear hierarchy | Audit all buttons; establish max 3 button variants (primary action, secondary, ghost/text) per context |

### Forms & Data Entry

| # | Issue | Recommendation |
|---|-------|----------------|
| U-09 | **Long forms without sections** — inventory add form has 17+ fields in a flat list | Group fields into collapsible sections (Required, Details, Tracking, Notes) |
| U-10 | **No form field validation feedback** — errors shown only as toast after submit | Add inline validation with red borders and helper text on blur |
| U-11 | **Modal overuse** — many operations open full modals when a slide-out panel or inline edit would suffice | Use slide-out drawer pattern for edit forms; reserve modals for confirmations and critical actions |
| U-12 | **No autosave drafts** — FormStateRecovery exists but is limited to 3 forms | Extend FormStateRecovery to all forms with data entry; add visible "Draft saved" indicator |

### Mobile & Responsive

| # | Issue | Recommendation |
|---|-------|----------------|
| U-13 | **Bottom nav "More" menu** — tapping More opens a panel covering content | Use a full-screen drawer or tab-based navigation instead of overlay panel |
| U-14 | **Map controls too small on mobile** — MapLibre controls are default size | Increase map control button sizes to 44px minimum touch targets |
| U-15 | **Horizontal scrolling on narrow screens** — some data tables overflow without scroll indicators | Add scroll shadow indicators on table containers |

### Performance & Feedback

| # | Issue | Recommendation |
|---|-------|----------------|
| U-16 | **No progress indicator for large operations** — content pack downloads show progress, but DB operations (vacuum, import) don't | Add progress bar or spinner for any operation taking >1 second |
| U-17 | **Situation Room initial load** — 34 fetch workers fire simultaneously on tab open | Prioritize above-the-fold cards; lazy-load below-fold cards on scroll into view (IntersectionObserver) |
| U-18 | **Service start feedback delay** — clicking "Start" on a service shows no immediate feedback | Show immediate "Starting..." state with spinner; poll health endpoint |

---

## Internal Audit

Findings from a deep inward codebase audit — issues that no competitor comparison would reveal. Grouped by category with severity and actionable backlog items at the end.

### A. Code Duplication & Missing Abstractions

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| A-1 | **`_safe_int()` / `_safe_float()` duplicated in 8+ blueprints** — independently defined in inventory.py, medical.py, security.py, power.py, supplies.py, hardware_sensors.py, situation_room.py, and others. Identical logic each time. Should live in `web/utils.py` once. | Backend | Medium |
| A-2 | **`_esc()` redefined in 3+ blueprints** despite `esc()` existing in `web/utils.py` — routes_advanced.py, situation_room.py, and others define their own local `_esc` helper. | Backend | Low |
| A-3 | **`_utc_now()` defined independently in alert_rules.py and vehicles.py** — should be a shared utility in `web/utils.py`. | Backend | Low |
| A-4 | **No shared validation framework** — 11 blueprints define their own `_*_SCHEMA` dicts with ad-hoc validation logic. No common `validate_payload(data, schema)` utility. Each blueprint reinvents field type checking, max_length enforcement, and required-field logic. | Backend | High |
| A-5 | **No base class or protocol for service modules** — 7 service modules (ollama, kiwix, cyberchef, kolibri, qdrant, stirling, flatnotes) share a similar `download()/start()/stop()/running()/uninstall()` interface but have no ABC or Protocol. Missing methods are only caught at runtime. | Services | Medium |
| A-6 | **`db.py _create_indexes()` is 593 lines** — a single function containing 611 `CREATE INDEX IF NOT EXISTS` statements. Should be split into per-module helpers (e.g., `_create_inventory_indexes()`, `_create_medical_indexes()`). | Backend | Medium |
| A-7 | **Dual SSE endpoints** — `/api/alerts/stream` and `/api/events/stream` are separate endpoints with separate subscriber lists. Could be unified into a single multiplexed SSE stream with event types. | Backend | Low |

### B. Consistency Gaps Across Blueprints

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| B-1 | **34 of 45+ mutating blueprints lack input validation** — only ~11 blueprints (contacts, inventory, alert_rules, vehicles, financial, loadout, water_mgmt, medical_phase2, meal_planning, threat_intel, tactical_comms) have schema validation. The remaining 34 accept raw JSON without field-type or bounds checking. | Backend | High |
| B-2 | **57 of 59 blueprints lack auth gating** — only contacts.py and inventory.py enforce `require_auth('admin')`. If `NOMAD_AUTH_REQUIRED=1` is set for LAN multi-user, all other mutation endpoints are unprotected. | Backend | High |
| B-3 | **~34 blueprints with mutations don't call `log_activity()`** — only ~7 blueprints (contacts, inventory, supplies, kit_builder, kiwix, notes, medical) log mutations. Changes to garden, vehicles, tasks, power, family, checklists, and 27 other modules are invisible in the activity log. | Backend | Medium |
| B-4 | **~17 blueprints lack pagination on list endpoints** — agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, interoperability, kb, kit_builder, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, timeline, training_knowledge. | Backend | Medium |
| B-5 | **~14 blueprints have DELETE routes without 404 checks** — agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, specialized_modules, training_knowledge. They return 200 even when the target resource doesn't exist. | Backend | Medium |

### C. Thread Safety & Concurrency

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| C-1 | **`_api_cache` in app.py is a plain dict without locking** — accessed from multiple request threads. Cache eviction (check size, iterate, delete) is not atomic. | Backend | Medium |
| C-2 | **`_ttl_cache` in state.py is not thread-safe** — `cached_get()`/`cached_set()` can race on concurrent requests. | Backend | Medium |
| C-3 | **`_download_progress` in manager.py lacks a lock** — written by download threads, read by API request threads and health monitor. | Services | Medium |
| C-4 | **`_service_logs` in manager.py lacks a lock** — written by log reader threads, read by API request threads. | Services | Medium |
| C-5 | **SSE `_sse_subscribers` list has no lock** — appended from request threads, iterated from alert engine thread. | Backend | Low |

### D. Performance Issues

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| D-1 | **`get_db()` executes 3 PRAGMAs on every connection** — `foreign_keys`, `busy_timeout`, `cache_size` run on every `get_db()` call, including pooled connections that already have them set. Only WAL uses a once-per-process flag. | Backend | Medium |
| D-2 | **611 indexes checked on every startup** — `_create_indexes()` runs all 611 `CREATE INDEX IF NOT EXISTS` on every launch. Even checking existence is measurable on large databases. | Backend | Low |
| D-3 | **`api_search_all()` searches 14+ entity types every time** — no early-exit optimization. If user only needs inventory results, they still pay for searching contacts, notes, waypoints, etc. | Backend | Low |
| D-4 | **FTS5 MATCH queries don't sanitize special characters** — `*`, `"`, `NEAR`, `OR` in search input can cause unexpected FTS5 behavior or errors. | Backend | Medium |
| D-5 | **Situation Room fires 34 fetch workers simultaneously** — no prioritization or lazy-loading. All data sources fetch on tab open regardless of viewport position. | Frontend | Medium |

### E. Resource Leaks & Cleanup

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| E-1 | **SSE stale subscribers accumulate** — clients that connect but never read fill their queue (maxsize=50), alerts are silently dropped via `put_nowait`, but the subscriber is never pruned until disconnect. | Backend | Medium |
| E-2 | **DB connection pool not closed on shutdown** — pool connections are garbage-collected rather than explicitly closed, risking dirty WAL state. | Backend | Medium |
| E-3 | **`stop_process()` doesn't call `kill()` after wait timeout** — if `proc.wait(10)` times out, the process is logged as a warning but continues running as a potential zombie. | Services | Medium |
| E-4 | **No PID files for managed services** — if `nomad.py` crashes, all managed service processes become unrecoverable orphans with no tracking mechanism. | Services | Medium |
| E-5 | **Abandoned `.part` download files never expire** — partial downloads are preserved for resume but have no TTL. They persist indefinitely on disk. | Services | Low |
| E-6 | **`get_db()` leaks connection if PRAGMAs fail** — if `sqlite3.connect()` succeeds but a subsequent PRAGMA fails (e.g., read-only filesystem), no close in except handler. | Backend | Low |

### F. Frontend Quality

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| F-1 | **190+ `console.log` statements in production JS** — scattered across all major JS files. Largest offender: `_app_situation_room.js` (63 occurrences). Should be removed or gated behind a debug flag. | Frontend | Medium |
| F-2 | **280+ inline `style=` attributes in templates** — active migration to CSS classes is documented but has significant backlog. Largest: `_tab_nukemap.html` (70+, documented exception), `_tab_settings.html` (~50+), `_tab_tools.html` (~40). | Frontend | Low |
| F-3 | **7 JS files over 1,000 lines** — `_app_situation_room.js` (11,237), `_app_init_runtime.js` (~4,100), `_app_workspace_memory.js` (~2,912), `_app_media_maps_sync.js` (~2,650), `_app_services_ai.js` (~2,440), `_prep_calcs_misc.js` (~1,500), `_app_dashboard_readiness.js` (~1,500). | Frontend | Medium |
| F-4 | **No JS module system** — all JS files are concatenated into the HTML template. Every top-level `let`/`const`/`function` is effectively global. This creates TDZ hazards (documented gotcha) and namespace pollution (~50+ global variables per major file). | Frontend | High |
| F-5 | **500+ hardcoded English strings** — i18n system has only 56 keys per language. Button labels, section headers, error messages, toast messages, and empty states are all hardcoded English. | Frontend | Medium |
| F-6 | **CSS design token adoption incomplete** — some files still use raw transition durations (`0.2s`/`0.3s`) instead of `var(--duration-fast)`/`var(--duration-normal)`, and raw font-family values instead of `var(--font-data)`. | Frontend | Low |
| F-7 | **Event listener accumulation risk** — situation room adds map/card event listeners on tab switch without deduplication guards. Re-opening the tab may accumulate redundant listeners. | Frontend | Low |
| F-8 | **Accessibility gaps** — status dots rely on color alone (no icon/text pairing), `tone-muted`/`tone-dim` may not meet WCAG AA contrast on dark backgrounds, map interactions lack keyboard alternatives. | Frontend | Medium |

### G. CI/CD & Build

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| G-1 | **CI has no test step** — `build.yml` builds the executable and installer but never runs `pytest`. Broken code produces release artifacts. | CI/CD | High |
| G-2 | **CI has no esbuild step** — if `web/static/dist/` (esbuild output) is gitignored, the CI must run `npm install && node esbuild.config.mjs` before PyInstaller. Currently it doesn't. | CI/CD | High |
| G-3 | **CI only builds Windows** — no Linux AppImage or macOS dmg despite cross-platform support in the code and `platform_utils.py`. | CI/CD | Medium |
| G-4 | **No artifact smoke test** — after building, the workflow doesn't verify the exe runs (e.g., `--self-test` flag). | CI/CD | Medium |
| G-5 | **5 hardcoded service version strings** — kiwix (3.7.0), cyberchef (10.19.4), kolibri (0.17.3), qdrant (v1.12.6), stirling (0.36.6). Require manual updates when upstream releases. No automated version-check mechanism. | Services | Low |

### H. Miscellaneous

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| H-1 | **`_wizard_state` in state.py is dead** — only used by the onboarding wizard which doesn't exist yet (ROADMAP P2-01). | Backend | Low |
| H-2 | **Service health check URLs use hardcoded ports** — if a user changes a service port via config, health checks silently fail against the old port. | Services | Medium |
| H-3 | **No service dependency graph** — services can be started in any order, but AI features need Ollama + Qdrant. No dependency declaration or ordered startup. | Services | Low |
| H-4 | **No checksum verification on service downloads** — only self-update downloads verify SHA256. All 7 service downloads are trust-on-first-download. | Services | Medium |
| H-5 | **situation_room.py is 5,400+ lines** — the single largest file in the project (149 routes, 34 workers). Previously identified for splitting but never done. | Backend | Medium |
| H-6 | **Alert engine has no retry/restart** — if `_run_alert_engine` crashes with an exception, it logs and the interval continues, but persistent failures (e.g., DB corruption) silently stop alerting forever. | Backend | Low |

---

### Internal Audit Backlog

Items derived from audit findings above, tagged `[internal]`.

#### P1: Quick Wins (< 1 hour each) [internal]

| # | Title | Description | Findings |
|---|-------|-------------|----------|
| P1-I01 | **Extract `_safe_int`/`_safe_float`/`_utc_now` to utils.py** | Move duplicated helpers to `web/utils.py`, update all 10+ blueprint imports | A-1, A-3 |
| P1-I02 | **Remove `_esc` redefinitions** | Delete local `_esc` helpers in blueprints, import `esc` from `web/utils.py` | A-2 |
| P1-I03 | **Strip 190+ `console.log` from production JS** | Search-and-remove or gate behind `if(DEBUG)` flag across all JS files | F-1 |
| P1-I04 | **Add `proc.kill()` fallback in `stop_process()`** | After `proc.wait(10)` timeout, call `proc.kill()` then `proc.wait(5)` to prevent zombies | E-3 |
| P1-I05 | **Add lock to `_download_progress` in manager.py** | Wrap dict access in `threading.Lock` for thread-safe read/write | C-3 |
| P1-I06 | **Add lock to `_service_logs` in manager.py** | Wrap dict access in `threading.Lock` for thread-safe read/write | C-4 |
| P1-I07 | **Skip redundant PRAGMAs on pooled connections** | Set `foreign_keys`/`busy_timeout`/`cache_size` once on connection creation, not on every `get_db()` call | D-1 |
| P1-I08 | **FTS5 search input sanitization** | Strip/escape FTS5 special characters (`*`, `"`, `NEAR`, `OR`, `AND`, `NOT`) from user search queries before MATCH | D-4 |
| P1-I09 | **Fix `get_db()` connection leak on PRAGMA failure** | Add try/except around PRAGMAs with `conn.close()` in the except handler | E-6 |
| P1-I10 | **Close DB pool connections on shutdown** | Add `atexit` handler or shutdown hook to drain and close all pool connections | E-2 |
| P1-I11 | **Service health URLs respect configured ports** | Read port from config/env instead of hardcoding in `SERVICE_HEALTH_URLS` dict | H-2 |
| P1-I12 | **Delete dead `_wizard_state` from state.py** | Remove unused wizard state dict until onboarding wizard (P2-01) is built | H-1 |

#### P2: Medium Effort (1-4 hours each) [internal]

| # | Title | Description | Findings |
|---|-------|-------------|----------|
| P2-I01 | **Shared validation framework** | Create `web/validation.py` with a `validate_payload(data, schema)` utility that handles type checking, max_length, numeric bounds, required fields. Migrate existing `_*_SCHEMA` blueprints first, then add schemas to the 34 unvalidated ones. | A-4, B-1 |
| P2-I02 | **Extend auth gating to all mutation endpoints** | Apply `require_auth('admin')` decorator to POST/PUT/DELETE routes across all 57 unprotected blueprints. Use a decorator that's a no-op when auth is disabled (desktop default). | B-2 |
| P2-I03 | **Activity logging for remaining 34 blueprints** | Add `log_activity()` calls to mutations in garden, vehicles, tasks, power, family, checklists, medical_phase2, and 27 others. Use a decorator/middleware pattern to reduce boilerplate. | B-3 |
| P2-I04 | **Pagination for remaining 17 blueprints** | Apply `get_pagination()` to list endpoints in agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, interoperability, kb, kit_builder, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, timeline, training_knowledge. | B-4 |
| P2-I05 | **DELETE 404 hardening for 14 blueprints** | Add `rowcount == 0 → 404` checks to DELETE routes in the 14 identified blueprints. | B-5 |
| P2-I06 | **Split `_create_indexes()` into per-module functions** | Break 593-line function into `_create_inventory_indexes()`, `_create_medical_indexes()`, etc. for maintainability. | A-6 |
| P2-I07 | **Service module Protocol/ABC** | Define a `ServiceProtocol` (Python Protocol class) with `download()`, `start()`, `stop()`, `running()`, `uninstall()` methods. Type-check all 7 service modules against it. | A-5 |
| P2-I08 | **Add CI test step** | Add `pytest` run before PyInstaller build in `.github/workflows/build.yml`. Fail the workflow on test failures. | G-1 |
| P2-I09 | **Add CI esbuild step** | Add `npm ci && node esbuild.config.mjs` step before PyInstaller in CI workflow. | G-2 |
| P2-I10 | **Thread-safe caches** | Replace `_api_cache` dict in app.py and `_ttl_cache` dict in state.py with `threading.Lock`-protected access or use `functools.lru_cache` / `cachetools.TTLCache`. | C-1, C-2 |
| P2-I11 | **SSE subscriber pruning** | Proactively remove stale SSE subscribers (queue full for >60s or last keepalive >60s ago) in the alert engine loop. | E-1, C-5 |
| P2-I12 | **SHA256 verification on service downloads** | Download checksums from upstream GitHub releases and verify after download for all 7 services, not just self-update. | H-4 |

#### P3: Larger Effort / Nice-to-Have [internal]

| # | Title | Description | Findings |
|---|-------|-------------|----------|
| P3-I01 | **Split situation_room.py (5,400 lines)** | Break into 4-5 sub-blueprints: `sitroom_data.py` (workers/fetchers), `sitroom_api.py` (routes), `sitroom_map.py` (map layers/points), `sitroom_analysis.py` (AI deduction/signals/clustering). | H-5 |
| P3-I02 | **Split large JS files** | Code-split `_app_situation_room.js` (11,237 lines), `_app_init_runtime.js` (4,100), `_app_workspace_memory.js` (2,912) into focused modules. Requires adopting a JS module system or lazy-loading pattern. | F-3 |
| P3-I03 | **JS module system** | Migrate from concatenated globals to ES modules or an IIFE-based module pattern. Eliminates TDZ hazards, reduces global namespace pollution, enables tree-shaking. | F-4 |
| P3-I04 | **Expand i18n from 56 to 300+ keys** | Audit all hardcoded English strings in templates/JS. Prioritize: button labels, section headers, error messages, empty states, toast messages. | F-5 |
| P3-I05 | **Inline style migration backlog** | Continue migrating 280+ remaining inline `style=` attributes to CSS classes following the documented migration pattern in CLAUDE.md. Exclude NukeMap (70+ intentional). | F-2 |
| P3-I06 | **CSS design token completion** | Audit remaining raw values (transition durations, font-family, colors) and replace with design tokens from `00_theme_tokens.css`. | F-6 |
| P3-I07 | **Cross-platform CI** | Add Linux (AppImage) and macOS (dmg) build jobs to `.github/workflows/build.yml`. | G-3 |
| P3-I08 | **CI smoke test** | After building, run the exe with `--self-test` flag (or equivalent) to verify it launches without crash. | G-4 |
| P3-I09 | **PID file tracking for managed services** | Write PID files on service start, check for orphans on NOMAD startup, offer to reclaim or kill. Prevents unrecoverable orphan processes after crash. | E-4 |
| P3-I10 | **Lazy-load Situation Room cards** | Use IntersectionObserver to only fetch data for cards visible in the viewport. Prioritize above-the-fold cards (map, breaking news, market ticker). | D-5 |
| P3-I11 | **WCAG AA contrast audit** | Verify `tone-muted`/`tone-dim` meet 4.5:1 contrast ratio on all theme backgrounds. Add icon/text pairing to color-only status indicators. Add keyboard alternatives for map interactions. | F-8 |
| P3-I12 | **Automated service version checking** | Query GitHub releases API for kiwix, cyberchef, kolibri, qdrant, stirling on startup (or weekly) to detect available updates without hardcoded version bumps. | G-5 |
| P3-I13 | **Expired partial download cleanup** | Add a TTL (e.g., 7 days) to `.part` files. Prune on startup or via health monitor. | E-5 |
| P3-I14 | **Situation Room lazy fetch deduplication** | Guard against re-adding event listeners on repeated tab switches in `_app_situation_room.js`. Track listener registration state. | F-7 |
| P3-I15 | **Unify dual SSE endpoints** | Merge `/api/alerts/stream` and `/api/events/stream` into a single `/api/sse` endpoint with event-type multiplexing. Reduces client connections and subscriber management overhead. | A-7 |

---

## Explicit Omissions

These items are intentionally excluded from the roadmap:

- Interactive substance-withdrawal tapers (medical risk too high)
- Home distillation of potable spirits (federal permit required)
- Paper-currency / scrip printing templates (counterfeiting-adjacent)
- Full-depth theology / scripture libraries
- Interactive flint-knapping / flintlock guides
- Offline Google Translate competitor

---

## Dependency-Gated Items

Items that are buildable but require specific external libraries or hardware.

### Requires External Libraries (pip-installable)

- **Skew-T / upper-air viewer** — needs `MetPy` for atmospheric sounding plots
- **Perceptual-hash on OSINT images** — needs `imagehash` for near-duplicate detection
- **SSURGO soil profile cache** — needs USDA SSURGO data download (large dataset)

### Requires Hardware

- **SDR sidecar service** — needs `rtl-sdr` or `SoapySDR` + USB SDR dongle
- **ALE / VARA / Winlink integration** — needs Pat Winlink client + radio hardware
- **FLDIGI macro library** — needs FLDIGI running locally (XML-RPC)

### Requires Large Research / XL Effort

- **FARSITE-lite wildfire spread** — fire behavior model + DEM/fuel data
- **SAR probability grid (ISRID)** — commercial Koester ISRID statistical dataset
- **Terrain-cost range rings** — DEM elevation data + weighted Dijkstra
- **Evacuation Monte Carlo** — probabilistic outcome modeling
- **Tauri alternative shell** — Rust/WASM rewrite of shell layer
- **Reproducible builds + SBOM** — build system hardening
- **WCAG 2.2 AA deep audit** — comprehensive accessibility pass
- **Offline plant-ID model** — ML model training/integration
