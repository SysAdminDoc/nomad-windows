# Project N.O.M.A.D. — Roadmap

> **Baseline:** v7.44.0 (~310 tables, 2,000+ routes, 77 blueprints)
> **Updated:** 2026-04-19

---

## Competitor Analysis

NOMAD Desktop occupies a unique niche: an offline-first, all-in-one preparedness command center with local AI integration. No single competitor covers the full scope. The comparison below maps overlapping tools whose UX patterns or feature depth can inform improvements.

| Project | Stars | Category | What They Do Better | Missing from NOMAD |
|---------|-------|----------|--------------------|--------------------|
| [Crosstalk-Solutions/project-nomad](https://github.com/Crosstalk-Solutions/project-nomad) | ~24.4k | Upstream (Docker) | Polished onboarding wizard, content-pack marketplace UI, one-click Docker deploy, wider community & YouTube ecosystem (475K subscribers) | Content-pack download UI comparable to an app store; guided first-run experience with progress tracking |
| [open-webui/open-webui](https://github.com/open-webui/open-webui) | ~132k | AI Chat Frontend | Model builder UI, RAG with 9 vector DB backends, web search injection (15+ providers), Python function calling, image generation (DALL-E/ComfyUI), RBAC + LDAP/SSO, persistent artifacts/tools workspace, conversation tagging & filtering, knowledge collections, SCIM provisioning | Model management UI (pull/create/delete from web), RAG web search injection, AI function/tool calling, conversation tags & filters, knowledge collection management, model comparison side-by-side |
| [grocy/grocy](https://github.com/grocy/grocy) | ~9.0k | Household ERP | Barcode-to-product lookup via OpenFoodFacts, recipe-driven consumption (auto-deduct ingredients), chore scheduling with user assignment, battery replacement tracker, full Swagger UI API docs, Home Assistant integration | Recipe-driven auto-consumption, product database lookup, chore/maintenance scheduler with assignees, HA integration |
| [sysadminsmedia/homebox](https://github.com/sysadminsmedia/homebox) | ~5.7k | Home Inventory | QR code label printing per item, warranty & maintenance schedule tracking, receipt/document attachments per item, ultra-light resource usage (~50 MB RAM), nested tag hierarchies (parent/child), fractional quantities, OpenTelemetry tracing | QR label generation per inventory item, warranty tracking fields, nested tag trees, fractional quantities |
| [glanceapp/glance](https://github.com/glanceapp/glance) | ~33k | Dashboard | YAML-based widget config (no code), clean card-based layout with consistent spacing, RSS/Reddit/HN/GitHub/weather widgets with minimal setup, single binary in Go (~50 MB RAM), responsive mobile-first design | Declarative widget configuration file, cleaner card density on home page, drastically lower resource usage |
| [gethomepage/homepage](https://github.com/gethomepage/homepage) | ~30k | Dashboard | 150+ service integrations with live status, Docker auto-discovery, bookmarks/quick-launch groups, per-widget refresh intervals, i18n with 40+ languages | Service health widget auto-discovery, bookmark groups, deeper i18n (NOMAD has 10 languages / 56 keys) |
| [Lissy93/dashy](https://github.com/Lissy93/dashy) | ~24.7k | Dashboard | Visual UI config editor (no YAML), 50+ built-in widgets, multi-page workspaces, icon packs, status checks with history graph, Keycloak/OIDC auth | Visual drag-and-drop dashboard editor, status check history graphs, icon pack system |
| [mealie-recipes/mealie](https://github.com/mealie-recipes/mealie) | ~12k | Meal Planning | URL-based recipe import (paste URL, auto-scrape), multi-household support, shopping list with aisle grouping, nutritional info per recipe, mobile-friendly Vue UI, webhook integrations, meal plan calendar view | URL-based recipe import, shopping list aisle grouping, meal plan calendar view, nutritional breakdown per recipe |
| [iiab/iiab](https://github.com/iiab/iiab) | ~1.8k | Offline Knowledge | Multi-language content packs with regional catalogs, Kolibri + Sugarizer + Moodle integration, mesh networking support, SD-card-ready images for Raspberry Pi, Android deployment via Termux | Regional content catalogs with language filters, education platform integrations, Android deployment |
| [ligi/SurvivalManual](https://github.com/ligi/SurvivalManual) | ~2.5k | Survival Reference | Illustrated survival manual with offline search, chapter-based navigation, lightweight (single APK), community translations | Illustrated inline survival reference content (NOMAD links to external books/ZIMs instead) |
| [PrepSoft/SPS](https://prepsoftsystems.com/) | N/A | Prep Platform | Built-in SIP phone for local comms, 60+ offline calculators, food storage nutritional tracking with caloric needs calculator, survival simulations (supply duration modeling), Raspberry Pi deployment | SIP/VoIP local comms, survival duration simulation engine, caloric needs vs storage gap analysis |
| [Prepper Nerd UPS](https://prepper-nerd.com/) | Commercial | Prep Inventory | Barcode scanning with auto-fill (description, calories, servings), calorie-per-day burn-down dashboard, insurance/warranty tracker, personalized prep coaching, Excel/PDF export scheduling | Auto-fill from barcode product database, insurance tracker, scheduled report exports |
| [meshtastic/web](https://github.com/meshtastic/web) | ~1.5k | Mesh Comms | Real-time node map with signal quality, message threading, channel management UI, Bluetooth/serial/HTTP transport selection, position sharing, Home Assistant integration | Direct Meshtastic serial integration (NOMAD has stub), signal quality visualization |
| [s-samarth/survive-ai](https://github.com/s-samarth/survive-ai) | New | Offline AI Survival | On-device AI (Gemma 2B, 4 GB RAM), RAG-grounded answers with citations from curated survival docs, conflict-zone + wilderness focus, ~500 MB total footprint | Lighter AI fallback model option for low-spec hardware; RAG specifically tuned for survival docs |
| [sahana/eden](https://github.com/sahana/eden) | ~21 | Emergency Mgmt | ICS/NIMS incident command integration, volunteer management, shelter/camp tracking, missing persons registry, formal humanitarian coordination workflows | Formal ICS organizational charts, volunteer skill matching at scale, shelter capacity tracking |

### Key Gaps Identified

1. **AI Chat UX** — Open WebUI (132k stars) sets the bar: model management UI, conversation tags/filters, knowledge collections, function calling, side-by-side model comparison. NOMAD's AI chat is functional but basic by comparison.
2. **Onboarding & First-Run** — No guided setup wizard; new users face a wall of 33+ tabs
3. **Inventory UX** — No barcode-to-product database lookup, no QR label printing, no recipe-driven auto-consumption
4. **Meal Planning** — Mealie (12k stars) shows the standard: URL-based recipe import, shopping list with aisle grouping, meal plan calendar. NOMAD has basic meal planning but lacks recipe import and calendar view.
5. **Dashboard configurability** — Widget layout is code-driven, not user-configurable beyond show/hide toggles
6. **i18n depth** — 10 languages with only 56 keys each; competitors offer 40+ languages with full coverage
7. **Maintenance scheduling** — No recurring maintenance reminders for equipment/vehicles/generators
8. **Data export scheduling** — No automated periodic export (email/file) of inventory or reports
9. **API documentation** — No Swagger/OpenAPI spec for the 2,000+ routes
10. **Survival reference content** — Relies on external ZIMs; no built-in illustrated quick-reference
11. **Meshtastic integration** — Stub only; no real serial/BLE bridge
12. **Resource footprint** — Glance runs in 50 MB RAM; NOMAD has no lightweight/minimal mode for constrained hardware
13. **Local comms** — SPS has built-in SIP phone for grid-down voice comms; NOMAD only has text-based LAN chat

---

## Deep Dive: Open WebUI (~132k stars)

**Repo**: [open-webui/open-webui](https://github.com/open-webui/open-webui) | **Latest**: v0.8.12 (2026-03-27) | **Stack**: SvelteKit, Python, Docker/pip

### What They Do Better

1. **Model management UI** — Pull, create, delete, and configure models from the web interface. Modelfile builder with live preview. NOMAD requires navigating to a settings sub-panel and typing model names.
2. **Knowledge collections** — Named document collections (not just a flat KB). Users create "Medical", "Radio", "Survival" collections and attach them to specific conversations. NOMAD has KB workspaces but they're not attachable per-conversation.
3. **Conversation organization** — Tags, folders, pinning, archiving, search with filters (by model, date range, tag). NOMAD has flat conversation list with basic search.
4. **Function calling / tools** — Users write Python functions that LLMs can call. Built-in code editor. Enables structured actions (query APIs, run calculations) without hardcoding them into the backend.
5. **Model comparison** — Side-by-side responses from two models on the same prompt. Useful for evaluating which model works best for survival/medical queries.
6. **Web search RAG injection** — 15+ search providers (SearXNG, Brave, etc.) inject web results into context. When online, this dramatically improves answer quality. NOMAD's RAG is purely local documents.
7. **Artifacts system** — Persistent key-value store for AI-generated content (journals, trackers, leaderboards). Conversations can create and reference persistent state.
8. **RBAC + SSO** — Full role-based access control, LDAP/AD integration, OAuth. Critical for LAN multi-user deployments that NOMAD's basic auth can't serve.
9. **Skills system (v0.8.0)** — Reusable AI skill definitions with instructions, referenced via `$` command or attached to models. Separates domain expertise from conversation context. NOMAD hardcodes domain knowledge in system prompts.
10. **Analytics dashboard (v0.8.0)** — Admin analytics with model usage stats, token consumption per user/model, activity rankings, and time-series charts. NOMAD has no AI usage tracking.
11. **Message queuing (v0.8.0)** — Queue follow-up messages while AI generates, auto-combined and sent on completion. NOMAD blocks input during generation.
12. **Prompt version control (v0.8.0)** — Prompts have full version history with commit messages, diffs, and rollback. NOMAD prompt presets have no versioning.
13. **Native built-in tools (v0.7.0)** — AI autonomously searches KB, notes, past chats, and web without user manually attaching files. Models can chain multi-step workflows (research + save note + generate image). NOMAD's AI action parsing is regex-based and single-step.
14. **Clickable citation deep-links (v0.7.0)** — Citations link directly to the relevant portion of source documents with text highlighting. NOMAD shows citation badges but doesn't jump to the exact passage.
15. **Cloud storage integration (v0.8.0)** — Native Google Drive and OneDrive/SharePoint file pickers for document import. Not relevant for offline-first, but the pattern of pluggable storage backends is.
16. **OpenTelemetry observability (v0.8.0)** — Built-in tracing, metrics, and logs for production monitoring. NOMAD has basic file logging only.

### Top Feature Requests (by thumbs-up, open issues)

| Votes | Issue | NOMAD Relevance |
|-------|-------|-----------------|
| 58 | 2FA/MFA TOTP support (#1225) | Strong demand for auth hardening; NOMAD's auth is basic |
| 56 | OpenAI real-time API (#5894) | Voice/streaming API; NOMAD has voice input but no real-time streaming voice |
| 50 | Data sources (#5872) | External data feeds injected into AI context; mirrors NOMAD's RAG scope concept |
| 39 | Auth control for shared chats (#2904) | Granular sharing permissions; NOMAD has no chat sharing |
| 39 | File upload without backend processing (#12228) | Users want to attach files as-is without chunking; useful for field documents |
| 35 | Knowledge Base image import + OCR (#13137) | Image-to-text in KB; NOMAD has OCR pipeline but not image KB support |
| 32 | Nextcloud integration (#12724) | Self-hosted cloud storage integration demand |
| 25 | Native companion mobile app (#8414) | High demand for mobile app; NOMAD has PWA but no native app |
| 15 | Confirming inputs to MCP/tools (#16940) | User approval before AI executes actions; NOMAD added `confirmed:true` pattern |
| 14 | More keyboard shortcuts (#1008) | Power user demand for keyboard-driven workflows |
| 14 | Notes feature (#13464) | Persistent notes separate from chat; NOMAD already has full Notes module |
| 13 | Shared links management (#2890) | Centralized link/bookmark management |
| 11 | Admin dashboard (#1450) | Usage analytics for admins |
| 11 | Channels enhancement (#8050) | Team messaging channels; NOMAD has LAN chat channels |
| 11 | Compressed archive uploads (#16151) | Upload ZIP/TAR and auto-extract for KB; NOMAD lacks this |

### Features to Adopt (Practical for NOMAD)

- **Conversation tags & folders** — Low effort, high UX impact. Tag conversations by topic (medical, inventory, planning).
- **Per-conversation knowledge attachment** — "Use Medical KB for this conversation" toggle.
- **Model card UI with recommendations** — Show VRAM requirements, speed benchmarks, and use-case tags per model.
- **Prompt templates/presets** — Save and reuse prompt templates ("SITREP format", "Inventory gap analysis", "Medical triage").
- **AI Skills / domain expertise definitions** — Define reusable skill profiles ("Medical Triage Expert", "Radio Operator", "Supply Chain Analyst") with tailored system prompts and attached KB scopes.
- **Message queuing during generation** — Allow typing follow-up while AI is streaming; queue and send automatically.
- **AI usage analytics** — Track which models are used, token consumption over time, response quality ratings.
- **Archive upload auto-extract for KB** — Upload ZIP/TAR containing PDFs/docs, auto-extract and index all contents into KB workspace.

---

## Deep Dive: Glance (~33k stars)

**Repo**: [glanceapp/glance](https://github.com/glanceapp/glance) | **Latest**: v0.8.4 (2025-06-10) | **Stack**: Go, single binary (<20 MB), vanilla JS, YAML config

### What They Do Better

1. **Declarative YAML configuration with hot-reload** — Config changes take effect on save without restart. Glance never touches a database for layout; everything is a flat YAML file. This makes backup, version control, and sharing trivial. NOMAD's widget/dashboard config is scattered across localStorage, DB settings, and JS objects.
2. **`$include` directive for modular configs** — Users split config into `home.yml`, `videos.yml`, `homelab.yml` and compose them. Encourages reuse and sharing of preconfigured page templates (Glance ships 3: Startpage, Markets, Gaming).
3. **Community widgets ecosystem** — Separate [community-widgets](https://github.com/glanceapp/community-widgets) repo lets users contribute custom widget types without forking the main project. Plugin boundary is well-defined (custom-api widget + extension widget + HTML widget + iframe widget).
4. **Icon library system** — 4 icon packs via prefix (`si:`, `sh:`, `di:`, `mdi:`) from CDN, plus `auto-invert` for theme-aware icons. NOMAD uses inline SVGs and emoji; no unified icon vocabulary.
5. **Extreme resource efficiency** — <20 MB binary, minimal RAM. Pages load in ~1s. No background workers unless explicitly configured. Cache TTLs are per-widget, not global.
6. **Preconfigured page templates** — Ship-ready layouts (Startpage, Markets, Gaming) that users copy-paste. Lowers the "blank canvas" intimidation factor.
7. **Environment variable injection anywhere** — `${ENV_VAR}` syntax works in any YAML value, plus Docker secrets support via `${secret:name}` and file-based secrets via `${readFileFromEnv:VAR}`.
8. **28 widget types with consistent interface** — RSS, Videos, Hacker News, Lobsters, Reddit, Search, Group, Split Column, Custom API, Extension, Weather, Todo, Monitor, Releases, Docker Containers, DNS Stats, Server Stats, Repository, Bookmarks, ChangeDetection.io, Clock, Calendar, Markets, Twitch Channels, Twitch top games, iframe, HTML. Each widget has a `cache` property for per-widget TTL. NOMAD's dashboard widgets are hardcoded with no user-definable types.
9. **Todo widget** — Built-in todo list widget on the dashboard. Simple but practical for daily task visibility alongside feeds and monitors.
10. **Monitor widget** — HTTP/TCP/ICMP health checks with status display. Each monitor has configurable URL, expected status code, and check interval. NOMAD has service health checks but not user-configurable endpoint monitoring.
11. **ChangeDetection.io integration** — Monitor web pages for changes. Useful for tracking government advisories, supply availability, or regulatory updates — relevant for preparedness.
12. **Strict no-dependency, no-package.json philosophy** — Contributing guidelines explicitly forbid `package.json` and new dependencies. Forces minimal, maintainable code. NOMAD has 30+ pip dependencies.
13. **Authentication with hashed passwords + brute-force protection** — Built-in basic auth with bcrypt hashing and rate limiting. Simple but effective. NOMAD's auth is a flat token comparison.

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
| 10 | YouTube proxy support (#479) | YouTube widgets bypass region blocks; NOMAD's media downloader could benefit |
| 10 | Swipe navigation on mobile (#128) | NOMAD's mobile bottom nav could benefit from swipe between tabs |
| 10 | Address-bar-style search (#229) | NOMAD's Ctrl+K search could act as URL bar for services |
| 9 | Custom API allow-insecure (#739) | Self-signed cert support for internal APIs; relevant for LAN federation |
| 9 | Automatic theme switching (day/night) (#674) | NOMAD has night mode but it's manual; could auto-switch by sunrise/sunset |
| 9 | Calendar *arr integration (#90) | Media calendar integration; shows demand for calendar-based views |
| 8 | YouTube/Twitch import subscriptions (#302) | Bulk import from existing accounts; NOMAD could import OPML/subscription lists |
| 7 | Per-page user access control (#694) | Page-level auth; relevant for NOMAD's multi-user LAN scenario |
| 6 | Auto-create default config on first start (#589) | First-run config generation; NOMAD should generate sensible defaults |

### Architectural Decisions to Adopt

- **Per-widget cache TTL**: Each widget declares its own cache lifetime instead of a global refresh rate. More efficient for mixed-frequency data.
- **Config-as-code philosophy**: Exportable/importable dashboard config files make sharing setups between users trivial.
- **Preconfigured templates**: Ship ready-to-use page layouts that new users can start from instead of building from scratch.
- **Widget type abstraction**: Each widget is a self-contained unit with shared properties (title, cache TTL, CSS class) plus type-specific config. NOMAD should formalize a widget interface.
- **Monitor widget pattern**: User-configurable URL health checks are broadly useful — monitor federation peers, external APIs, local services, even internet connectivity.
- **No-build frontend**: Glance's vanilla JS approach means zero build step, instant dev iteration. NOMAD's esbuild step adds friction; consider whether the bundle is worth it for the frontend complexity level.

---

## Deep Dive: Homepage (~30k stars)

**Repo**: [gethomepage/homepage](https://github.com/gethomepage/homepage) | **Latest**: v1.12.3 (2026-04-01) | **Stack**: Next.js 16, statically generated, YAML config, Crowdin i18n

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
10. **Aggressive security posture** — Explicit security notice in README: "if reachable from any untrusted network, it MUST sit behind a reverse proxy that enforces authentication, TLS, and strictly validates Host headers." NOMAD should have similar prominent security guidance for LAN deployments.
11. **Block highlighting with units** — Resource widgets support raw value display with configurable units and threshold-based color highlighting. Clean pattern for NOMAD's power/inventory/weather dashboard widgets.
12. **Codecov integration** — Test coverage badge in README backed by CI coverage reports. NOMAD has no coverage tracking despite 775+ tests.
13. **Release drafter automation** — GitHub Actions auto-generate release notes from PR labels. NOMAD's releases are manual.
14. **200+ contributors** — Healthy contributor pipeline via clear CONTRIBUTING.md, focused PR scope, and well-defined widget interface that makes first contributions easy.
15. **`HOMEPAGE_ALLOWED_HOSTS` security** — Explicit host validation to prevent DNS rebinding attacks. NOMAD binds to localhost by default but has no host header validation for LAN mode.

### Top Feature Requests (closed issues, by thumbs-up)

| Votes | Issue | NOMAD Relevance |
|-------|-------|-----------------|
| 25 | Deluge widget (#190) | Shows demand for torrent client status widgets — NOMAD has built-in torrent but no dashboard widget |
| 19 | Audiobookshelf widget (#525) | Media library integration demand |
| 16 | CPU temperature (#86) | NOMAD shows CPU% but not temp; psutil can read temps on Linux |
| 15 | Sonarr calendar widget (#242) | Calendar/scheduling demand |
| 15 | Server uptime display (#240) | Already in NOMAD backlog as P1-15 |
| 12 | Uptime Kuma widget (#123) | Status page / uptime monitoring demand; NOMAD could expose /healthz for external monitors |
| 12 | Config variables (#60) | Glance solved this; NOMAD should too |
| 11 | Layout options for bookmarks (#601) | Configurable grid/list layout for bookmark sections |
| 11 | Favicon auto-fetch for bookmarks (#174) | Useful for service links/bookmarks |
| 10 | Home Assistant integration (#683) | Already in NOMAD backlog as P3-15 |
| 10 | OpenMediaVault widget (#268) | NAS storage monitoring demand |
| 10 | Calendar *arr widget (#654) | Second request for media calendar; confirms calendar widget demand |
| 9 | qBittorrent widget (#152) | Yet another torrent client widget request — validates NOMAD's P4-14 |
| 8 | Custom widget support (#467) | Generic widget renderer for arbitrary APIs |

### Architectural Decisions to Adopt

- **Server-side API proxying**: Never expose API keys to the browser. Route all external API calls through the Flask backend.
- **Widget integration manifest**: Each widget is a self-contained module with a defined interface. Makes adding new integrations systematic.
- **Crowdin for i18n management**: Professional translation management instead of manual JSON file editing.
- **Host header validation**: Add `NOMAD_ALLOWED_HOSTS` config to reject requests with unexpected Host headers when running on LAN.
- **Release drafter**: Automate changelog generation from commit/PR labels in CI workflow.
- **CONTRIBUTING.md with widget guide**: Lower the barrier for community contributions by documenting how to add a new widget type or blueprint with a focused tutorial.

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
| P1-19 | **AI conversation tags** | Tag AI conversations with labels (medical, inventory, planning, etc.) for filtering and organization | Open WebUI |
| P1-20 | **AI prompt presets** | Save and reuse prompt templates ("SITREP format", "Inventory gap analysis", "Medical triage") from a dropdown in AI chat | Open WebUI |
| P1-21 | **Meal plan date labels** | Show day-of-week headers on meal planning entries instead of raw dates | Mealie |

### P2: Medium Features (1-4 hours each)

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P2-01 | **First-run onboarding wizard** | 5-step guided wizard on first launch: set location, pick dashboard mode, install first content pack, configure AI, import sample data | Upstream NOMAD |
| P2-02 | **Barcode product database lookup** | On barcode scan, query bundled UPC database + OpenFoodFacts offline dump for product name, calories, category auto-fill | Grocy, Prepper Nerd |
| P2-03 | **QR code label generation** | Generate printable QR code labels for inventory items linking to their detail page; batch print sheet layout | Homebox |
| P2-04 | **Recipe-driven consumption** | Add recipes that reference inventory items; "Cook this" button auto-deducts ingredient quantities and logs the meal | Grocy, Mealie |
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
| P2-22 | **AI model management UI** | Pull, delete, and view model details (VRAM requirement, parameter count, quantization) from a dedicated model manager panel instead of typing model names into a text field | Open WebUI |
| P2-23 | **Per-conversation knowledge scope** | Toggle which KB workspaces are active for a specific AI conversation ("Use Medical KB for this chat") | Open WebUI |
| P2-24 | **URL-based recipe import** | Paste a recipe URL and auto-scrape title, ingredients, and instructions using structured data (JSON-LD/Microdata) parsing | Mealie |
| P2-25 | **Meal plan calendar view** | Weekly/monthly calendar grid showing planned meals with drag-to-reschedule; auto-generate shopping list from selected date range | Mealie |
| P2-26 | **Survival duration simulator** | Given current inventory levels, household size, and daily caloric/water needs, project how many days supplies will last with burn-down chart | SPS |
| P2-27 | **Caloric gap analysis** | Compare total stored calories vs. daily household caloric need; show coverage days per food category and identify gaps | SPS, Prepper Nerd |

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
| P3-16 | **AI model comparison view** | Side-by-side responses from two models on the same prompt for evaluating model quality | Open WebUI |
| P3-17 | **AI function/tool calling** | Let AI execute structured actions via defined Python functions (query inventory, check weather, calculate dosage) instead of regex-based action parsing | Open WebUI |
| P3-18 | **Shopping list aisle grouping** | Group shopping list items by store aisle/section (Produce, Dairy, Pharmacy, etc.) for efficient shopping trips | Mealie, Grocy |
| P3-19 | **Android companion app** | Lightweight Android app for barcode scanning, inventory lookup, and checklist access that syncs with desktop instance via LAN API | Grocy (Android), IIAB (Android) |

### P4: Deep-Dive Discoveries (from competitor research)

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

### P5: Deep-Dive Discoveries — Loop 2 (from expanded competitor research)

New items discovered from analyzing recent releases (Open WebUI v0.7-0.8, Glance v0.8.x, Homepage v1.11-1.12), open issue trends, and architectural patterns not covered in Pass 1.

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P5-01 | **AI Skills / domain expertise profiles** | Define reusable skill definitions ("Medical Triage Expert", "Radio Operator", "Supply Chain Analyst") with tailored system prompts, attached KB scopes, and enabled tools; reference via `$skill` in chat or attach to models permanently; store in `ai_skills` table | Open WebUI (Skills, v0.8.0, #21312) |
| P5-02 | **AI message queuing** | Allow typing follow-up messages while AI is streaming a response; queue and auto-combine on completion; prevents losing train of thought during long generations | Open WebUI (Message queuing, v0.8.0) |
| P5-03 | **AI usage analytics dashboard** | Track model usage (queries/day), token consumption per model/session, response quality ratings (thumbs up/down), time-series charts; admin-only view in Settings | Open WebUI (Analytics dashboard, v0.8.0, #21106) |
| P5-04 | **Prompt version control** | Prompt presets get version history with commit messages, diff viewer, and rollback; store versions in `ai_prompt_versions` table | Open WebUI (Prompt version control, v0.8.0, #20945) |
| P5-05 | **AI citation deep-links** | When AI cites a KB document, clicking the citation badge scrolls to the relevant passage with text highlighting instead of just opening the document | Open WebUI (Citation deep-links, v0.7.0, #20116) |
| P5-06 | **AI multi-step tool chaining** | AI autonomously chains multiple actions in sequence (search KB -> query inventory -> create note -> generate report) without user re-prompting; replace regex-based action parsing with structured tool definitions | Open WebUI (Native function calling, v0.7.0, #19397) |
| P5-07 | **2FA/TOTP authentication** | Add TOTP-based two-factor authentication for LAN multi-user deployments; pyotp library; QR code provisioning; backup recovery codes | Open WebUI (#1225, 58 votes) |
| P5-08 | **KB archive upload auto-extract** | Upload ZIP/TAR containing multiple PDFs/docs; auto-extract and index all contents into a KB workspace in one operation | Open WebUI (#16151, 11 votes) |
| P5-09 | **KB image import with OCR** | Import images directly into knowledge base with automatic OCR text extraction; store both image and extracted text for RAG | Open WebUI (#13137, 35 votes) |
| P5-10 | **User-configurable URL monitor widget** | Dashboard widget that performs HTTP/TCP health checks against user-defined URLs (federation peers, external APIs, internet connectivity test); configurable check interval, expected status code, and alert on failure | Glance (Monitor widget) |
| P5-11 | **Todo/task dashboard widget** | Lightweight todo list directly on the home dashboard showing today's tasks, overdue items, and quick-add; reads from existing `scheduled_tasks` table | Glance (Todo widget) |
| P5-12 | **Web page change detection** | Monitor specific URLs for content changes (government advisories, supply availability, weather warnings); store diffs; alert on change; useful for offline-to-online transition monitoring | Glance (ChangeDetection.io widget) |
| P5-13 | **OPML/subscription import for RSS** | Import OPML files or YouTube subscription exports to bulk-add RSS feeds to Situation Room and media channels | Glance (#302, 8 votes — YouTube/Twitch import) |
| P5-14 | **Self-signed cert trust for federation** | Allow federation peers with self-signed SSL certificates to be trusted via explicit certificate pinning or an `allow-insecure` flag per peer | Glance (#739, 9 votes — custom API allow-insecure) |
| P5-15 | **Per-page/tab access control** | In LAN multi-user mode, restrict which tabs/pages each user can see; e.g., hide Situation Room from family members, restrict Settings to admin | Glance (#694, 7 votes), Open WebUI (per-user resource sharing) |
| P5-16 | **Host header validation** | Add `NOMAD_ALLOWED_HOSTS` config to reject requests with unexpected Host headers when running on LAN; prevent DNS rebinding attacks | Homepage (HOMEPAGE_ALLOWED_HOSTS) |
| P5-17 | **Security notice in README** | Add prominent security notice explaining that LAN-exposed instances should sit behind a reverse proxy with auth/TLS, matching Homepage's security posture documentation | Homepage (Security Notice) |
| P5-18 | **Test coverage tracking in CI** | Add coverage reporting (pytest-cov + Codecov badge) to CI pipeline; baseline coverage visibility for the 775+ test suite | Homepage (Codecov badge) |
| P5-19 | **Release drafter automation** | GitHub Actions workflow that auto-generates release notes from commit messages and PR labels, reducing manual release effort | Homepage (release-drafter) |
| P5-20 | **CONTRIBUTING.md with widget/blueprint guide** | Formal contribution guide explaining how to add a new dashboard widget or Flask blueprint; lower barrier for community contributions | Homepage (200+ contributors), Glance (contributing guidelines) |
| P5-21 | **Active task sidebar indicator** | Show which AI conversations have active/pending tasks running (e.g., SITREP generation, action execution) with a visual indicator in the conversation list sidebar | Open WebUI (Active task indicator, v0.8.0) |
| P5-22 | **Fuzzy settings search with keyword aliases** | Extend P1-07's basic filter with fuzzy matching and keyword aliases (e.g., typing "whisper" finds Audio settings, "rag" finds AI Documents); cross-category search, not just per-section filtering | Open WebUI (Settings search, v0.7.0, #20434) |
| P5-23 | **Bcrypt password hashing for auth** | Upgrade from PBKDF2-SHA256 to bcrypt for credential hashing; add brute-force rate limiting on login attempts | Glance (bcrypt + brute-force protection) |
| P5-24 | **Personal RSS feed reader** | Add a personal RSS feed reader (separate from Situation Room's curated feeds) where users add their own feeds for news, blogs, and updates; manage via Settings | Glance (#313, 13 votes — Miniflux integration) |

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

### AI Chat UX (inspired by Open WebUI)

| # | Issue | Recommendation |
|---|-------|----------------|
| U-19 | **Flat conversation list** — no way to organize or filter conversations | Add tags, pinning, archiving, and search-by-model/date filters |
| U-20 | **Model selection is a text dropdown** — no information about model capabilities or requirements | Show model cards with VRAM requirement, speed rating, and recommended use-case tags |
| U-21 | **No conversation context indicator** — user can't see which KB workspaces or RAG scope is active | Show active knowledge sources as badges in chat header |
| U-22 | **AI action parsing is regex-based** — fragile natural language parsing for structured actions | Migrate to structured function calling with defined schemas for inventory/medical/waypoint actions |

---

## Internal Audit

Findings from deep inward codebase audits — issues that no competitor comparison would reveal. Grouped by category with severity and actionable backlog items at the end. Pass 2 (2026-04-19) added 46 new findings from 4 parallel audits across Python, JS, CSS/HTML, and test/CI infrastructure.

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
| A-8 | **`build_situation_context()` nested inside `create_app()`** — this ~100-line function is defined inline in the factory function, making it impossible to import or test independently. Should be a module-level function or moved to `web/utils.py`. | Backend | Medium |
| A-9 | **`formatDate()` / `formatDateTime()` duplicated across 3+ JS files** — independently defined in `_app_init_runtime.js`, `_app_situation_room.js`, and `_app_workspace_memory.js` with slightly different implementations. Should be in a shared `utils.js`. | Frontend | Low |
| A-10 | **40+ tab-switching loader functions share identical patterns** — `loadChecklists()`, `loadMedicalPatients()`, `loadContacts()`, etc. in `_app_init_runtime.js` each implement the same fetch-parse-render pattern with no shared abstraction. | Frontend | Medium |

### B. Consistency Gaps Across Blueprints

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| B-1 | **34 of 45+ mutating blueprints lack input validation** — only ~11 blueprints (contacts, inventory, alert_rules, vehicles, financial, loadout, water_mgmt, medical_phase2, meal_planning, threat_intel, tactical_comms) have schema validation. The remaining 34 accept raw JSON without field-type or bounds checking. | Backend | High |
| B-2 | **57 of 59 blueprints lack auth gating** — only contacts.py and inventory.py enforce `require_auth('admin')`. If `NOMAD_AUTH_REQUIRED=1` is set for LAN multi-user, all other mutation endpoints are unprotected. | Backend | High |
| B-3 | **~34 blueprints with mutations don't call `log_activity()`** — only ~7 blueprints (contacts, inventory, supplies, kit_builder, kiwix, notes, medical) log mutations. Changes to garden, vehicles, tasks, power, family, checklists, and 27 other modules are invisible in the activity log. | Backend | Medium |
| B-4 | **~17 blueprints lack pagination on list endpoints** — agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, interoperability, kb, kit_builder, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, timeline, training_knowledge. | Backend | Medium |
| B-5 | **~14 blueprints have DELETE routes without 404 checks** — agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, specialized_modules, training_knowledge. They return 200 even when the target resource doesn't exist. | Backend | Medium |
| B-6 | **80+ `get_db()` calls without `db_session()` context manager** — despite `db_session()` being the recommended pattern, many blueprints still use bare `get_db()`/`db.close()`. A `get_db()` without try/finally leaks connections on exception. | Backend | Medium |
| B-7 | **~40 remaining raw `fetch()` calls without `resp.ok` guards** — partially migrated to `apiPost`/`apiFetch` wrappers in v6.31, but `_prep_dashboards.js`, `_prep_family_field.js`, and `_prep_ops_mapping.js` still have unguarded raw fetch GET calls. | Frontend | Medium |

### C. Thread Safety & Concurrency

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| C-1 | **`_api_cache` in app.py is a plain dict without locking** — accessed from multiple request threads. Cache eviction (check size, iterate, delete) is not atomic. | Backend | Medium |
| C-2 | **`_ttl_cache` in state.py is not thread-safe** — `cached_get()`/`cached_set()` can race on concurrent requests. | Backend | Medium |
| C-3 | **`_download_progress` in manager.py lacks a lock** — written by download threads, read by API request threads and health monitor. | Services | Medium |
| C-4 | **`_service_logs` in manager.py lacks a lock** — written by log reader threads, read by API request threads. | Services | Medium |
| C-5 | **SSE `_sse_subscribers` list has no lock** — appended from request threads, iterated from alert engine thread. | Backend | Low |
| C-6 | **`_event_subscribers` in state.py iterated without lock during `_broadcast_event()`** — appended from request threads, iterated from broadcast thread. Could raise `RuntimeError: list changed size during iteration`. | Backend | Medium |

### D. Performance Issues

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| D-1 | **`get_db()` executes 3 PRAGMAs on every connection** — `foreign_keys`, `busy_timeout`, `cache_size` run on every `get_db()` call, including pooled connections that already have them set. Only WAL uses a once-per-process flag. | Backend | Medium |
| D-2 | **611 indexes checked on every startup** — `_create_indexes()` runs all 611 `CREATE INDEX IF NOT EXISTS` on every launch. Even checking existence is measurable on large databases. | Backend | Low |
| D-3 | **`api_search_all()` searches 14+ entity types every time** — no early-exit optimization. If user only needs inventory results, they still pay for searching contacts, notes, waypoints, etc. | Backend | Low |
| D-4 | **FTS5 MATCH queries don't sanitize special characters** — `*`, `"`, `NEAR`, `OR` in search input can cause unexpected FTS5 behavior or errors. | Backend | Medium |
| D-5 | **Situation Room fires 34 fetch workers simultaneously** — no prioritization or lazy-loading. All data sources fetch on tab open regardless of viewport position. | Frontend | Medium |
| D-6 | **`_apply_column_migrations()` runs on every startup without tracking** — each migration uses `PRAGMA table_info()` to check column existence before ALTER TABLE. All migrations re-check every launch. Should track applied migrations in a `schema_version` table. | Backend | Medium |
| D-7 | **`auto_start_services()` starts all services sequentially** — each service start + `wait_for_port()` is serial. With 8 services and up to 30s timeout each, worst case is 240s startup. Should parallelize. | Backend | Medium |
| D-8 | **Test fixture creates 264 tables + 611 indexes per test** — `conftest.py` runs full `init_db()` for each of 775+ tests. Session-scoped fixture with per-test transaction rollback would be dramatically faster. | Tests | High |
| D-9 | **Dashboard widgets re-create innerHTML on every 30s refresh** — destroys scroll position, hover states, and causes visible flicker. Should use targeted DOM updates. | Frontend | Medium |
| D-10 | **No debounce on `window.resize` handlers** — multiple files add resize listeners without debouncing, causing layout thrashing in Situation Room with MapLibre. | Frontend | Medium |

### E. Resource Leaks & Cleanup

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| E-1 | **SSE stale subscribers accumulate** — clients that connect but never read fill their queue (maxsize=50), alerts are silently dropped via `put_nowait`, but the subscriber is never pruned until disconnect. | Backend | Medium |
| E-2 | **DB connection pool not closed on shutdown** — pool connections are garbage-collected rather than explicitly closed, risking dirty WAL state. | Backend | Medium |
| E-3 | **`stop_process()` doesn't call `kill()` after wait timeout** — if `proc.wait(10)` times out, the process is logged as a warning but continues running as a potential zombie. | Services | Medium |
| E-4 | **No PID files for managed services** — if `nomad.py` crashes, all managed service processes become unrecoverable orphans with no tracking mechanism. | Services | Medium |
| E-5 | **Abandoned `.part` download files never expire** — partial downloads are preserved for resume but have no TTL. They persist indefinitely on disk. | Services | Low |
| E-6 | **`get_db()` leaks connection if PRAGMAs fail** — if `sqlite3.connect()` succeeds but a subsequent PRAGMA fails (e.g., read-only filesystem), no close in except handler. | Backend | Low |
| E-7 | **Alert engine opens a new DB connection every 5 minutes** — uses `get_db()` without `db_session()` in some paths. Over 24 hours = 288 connections opened/leaked. | Backend | Medium |
| E-8 | **MapLibre instance may leak GPU memory on tab re-open** — `_app_media_maps_sync.js` checks `if (!window._nomadMap)` but doesn't verify the container is clean. Previous WebGL context may not be disposed on some browsers. | Frontend | Medium |
| E-9 | **Morse code trainer `setInterval` not cleared on tab switch** — `_prep_people_comms.js` starts timers that accumulate on repeated tab navigation. | Frontend | Medium |

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
| F-9 | **`apiFetch()` doesn't catch network-level errors** — when `fetch()` throws `TypeError` (offline, DNS failure), `apiFetch` propagates it. Callers without try-catch get unhandled promise rejections. | Frontend | High |
| F-10 | **AI chat streaming doesn't cancel previous stream on new message** — if user sends while previous response is still streaming, both streams write to DOM simultaneously, producing garbled output. No AbortController cancellation. | Frontend | High |
| F-11 | **Sitroom errors swallowed silently** — `fetchSitroomData()`, `_loadBreakingNews()`, `_loadOREFAlerts()` log to console but show no toast or UI indicator. Users see stale/empty cards with no explanation. | Frontend | Medium |
| F-12 | **SSE reconnect backoff doesn't increase on flap** — `_reconnectDelay` resets to 1000ms after every connection. Rapid connect/disconnect cycles flood the server. | Frontend | Medium |
| F-13 | **Tab scroll position not preserved** — `window.scrollTo(0,0)` on every tab switch. Users deep in inventory (1000+ items) lose position when switching away and back. | Frontend | Low |
| F-14 | **Calculator inputs produce NaN without feedback** — some calculators use `parseFloat()` chains without NaN guards. Empty inputs produce NaN displayed to the user with no validation message. | Frontend | Low |
| F-15 | **VirtualList doesn't handle container resize** — sitroom virtual scroll calculates visible rows from initial container height. Window resize causes clipped or invisible items. | Frontend | Low |

### G. CI/CD & Build

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| G-1 | **CI has no test step** — `build.yml` builds the executable and installer but never runs `pytest`. Broken code produces release artifacts. | CI/CD | High |
| G-2 | **CI has no esbuild step** — if `web/static/dist/` (esbuild output) is gitignored, the CI must run `npm install && node esbuild.config.mjs` before PyInstaller. Currently it doesn't. | CI/CD | High |
| G-3 | **CI only builds Windows** — no Linux AppImage or macOS dmg despite cross-platform support in the code and `platform_utils.py`. | CI/CD | Medium |
| G-4 | **No artifact smoke test** — after building, the workflow doesn't verify the exe runs (e.g., `--self-test` flag). | CI/CD | Medium |
| G-5 | **5 hardcoded service version strings** — kiwix (3.7.0), cyberchef (10.19.4), kolibri (0.17.3), qdrant (v1.12.6), stirling (0.36.6). Require manual updates when upstream releases. No automated version-check mechanism. | Services | Low |
| G-6 | **`requirements.txt` has unpinned dependencies** — dependencies listed without version pins. Builds are not reproducible — different installs get different versions. | Build | Medium |
| G-7 | **No `pyproject.toml` or `.python-version`** — project requires Python 3.10+ but has no machine-readable version constraint. Would also enable modern tooling (uv, ruff, mypy). | Build | Low |
| G-8 | **CI uses outdated GitHub Actions** — `actions/checkout@v3` (should be v4), `actions/setup-python@v4` (should be v5), `actions/upload-artifact@v3` (should be v4). Node 16 runners are EOL. | CI/CD | Low |
| G-9 | **No CI caching for pip/npm** — every CI run does full `pip install` and `npm install` from scratch. `actions/cache` would cut build times significantly. | CI/CD | Low |
| G-10 | **`build.spec` includes raw CSS source AND bundled output** — `datas=[('web', 'web')]` copies both `web/static/css/app/*.css` (raw) and `web/static/dist/` (bundled). Raw source is redundant in the exe, bloating it by ~500KB-1MB. | Build | Low |
| G-11 | **`esbuild.config.mjs` has no source maps** — bundled JS/CSS cannot be debugged in production. Browser dev tools show concatenated code with no mapping to source files. | Build | Low |
| G-12 | **No `requirements-dev.txt`** — test dependencies (`pytest`, `pytest-cov`) are not separated from production deps. | Build | Low |
| G-13 | **`package.json` missing `engines` field** — Node.js version not specified; esbuild config requires Node 18+ features. | Build | Low |

### H. Miscellaneous

| # | Finding | Scope | Severity |
|---|---------|-------|----------|
| H-1 | **`_wizard_state` in state.py is dead** — only used by the onboarding wizard which doesn't exist yet (ROADMAP P2-01). | Backend | Low |
| H-2 | **Service health check URLs use hardcoded ports** — if a user changes a service port via config, health checks silently fail against the old port. | Services | Medium |
| H-3 | **No service dependency graph** — services can be started in any order, but AI features need Ollama + Qdrant. No dependency declaration or ordered startup. | Services | Low |
| H-4 | **No checksum verification on service downloads** — only self-update downloads verify SHA256. All 7 service downloads are trust-on-first-download. | Services | Medium |
| H-5 | **situation_room.py is 5,400+ lines** — the single largest file in the project (149 routes, 34 workers). Previously identified for splitting but never done. | Backend | Medium |
| H-6 | **Alert engine has no retry/restart** — if `_run_alert_engine` crashes with an exception, it logs and the interval continues, but persistent failures (e.g., DB corruption) silently stop alerting forever. | Backend | Low |
| H-7 | **Situation Room HTTP workers have no request timeout** — 34 `requests.get()` calls via `_http_session` set no `timeout` parameter. A hung upstream server blocks the worker thread indefinitely. | Backend | High |
| H-8 | **`config.py` `save_config()` doesn't flush before `os.replace()`** — temp file write uses `f.write()` without `f.flush(); os.fsync()`. Crash between write and replace can leave incomplete temp file. | Backend | Medium |
| H-9 | **`ai.py` hardcodes Ollama URL `http://localhost:11434`** — should use the configured port. If user changes Ollama's port, AI routes silently fail. | Backend | Medium |
| H-10 | **`download_file()` in manager.py has no max file size limit** — downloads to disk without checking Content-Length. A corrupted upstream URL could fill the disk. | Services | Medium |
| H-11 | **`system.py` `api_db_vacuum` runs VACUUM without disk space check** — SQLite VACUUM creates a full copy of the DB. Nearly-full disk could cause corruption. | Backend | Medium |
| H-12 | **`media.py` yt-dlp subprocess calls have no timeout** — `subprocess.run()` for downloads has no `timeout`. A hung yt-dlp process blocks the request thread forever. | Backend | Medium |
| H-13 | **`torrent.py` `_get_session()` retries failed `libtorrent` import on every call** — if `libtorrent` is not installed, the import error is not cached. Every torrent API request retries the failing import. | Services | Low |
| H-14 | **39 of 59 blueprints have no dedicated test file** — only ~20 blueprints have test coverage. agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, interoperability, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, specialized_modules, training_knowledge, comms (partial), emergency (partial), garden (partial), and others are untested. | Tests | Medium |
| H-15 | **Test suite only tests happy paths** — sampling test files shows they test CRUD success but rarely test: invalid input types, SQL injection attempts, concurrent access, empty strings, extremely long inputs, or permission denied scenarios. Only `test_validation.py` (5 tests) explicitly tests validation. | Tests | Medium |
| H-16 | **No test for SSE event propagation** — `test_sse.py` only tests that the SSE endpoint connects. No test verifies events are pushed to subscribers when data changes (inventory CRUD -> SSE event). | Tests | Medium |
| H-17 | **13 unused CSS animation keyframes** — `premium/05_motion.css` defines `bounceIn`, `slideUp`, `cardEntrance`, etc. but several are never referenced in CSS or JS. | Frontend | Low |
| H-18 | **`premium/30_preparedness_ops.css` is 1,800+ lines** — single file covers all prep sub-tabs with highly specific selectors. Should be split per sub-tab for maintainability. | Frontend | Medium |
| H-19 | **`app/45_situation_room.css` has 80+ scattered media queries** — duplicate `@media (max-width: 768px)` blocks throughout instead of grouped at the end. | Frontend | Low |
| H-20 | **Settings rows lack `<fieldset>` / `<legend>` semantic grouping** — 50+ settings in flat divs. Screen readers can't distinguish between AI, Display, and Backup settings sections. | Frontend | Medium |
| H-21 | **Heading hierarchy skips `<h4>` in Tools tab** — jumps from `<h3>` section titles to `<h5>` calculator names. Accessibility tools flag this. | Frontend | Medium |
| H-22 | **No `<main>` element, sidebar not `<nav>` or `<aside>`** — uses `<div role="main">` and `<div class="sidebar">` instead of semantic elements. | Frontend | Medium |
| H-23 | **15+ data tables without `<caption>` or `aria-label`** — inventory, contacts, medical, checklists tables have no accessible name for screen readers. | Frontend | Medium |
| H-24 | **Print styles scattered across 4+ CSS files** — `@media print` rules in tokens, final_polish, accessibility, and inline tab HTML. No single print stylesheet. | Frontend | Low |
| H-25 | **Dark theme overrides split across 3 CSS files** — tokens (`00_theme_tokens.css`), dedicated overrides (`80_dark_theme_overrides.css`), and consistency fixes (`90_theme_consistency.css`). Hard to find where a specific dark-mode color comes from. | Frontend | Low |
| H-26 | **`backdrop-filter: blur()` in customize panel** — causes significant performance issues on low-end hardware and Linux without GPU. Should have `@supports` fallback or battery-saver bypass. | Frontend | Low |
| H-27 | **NukeMap iframe missing `title` attribute** — screen readers announce it as "frame" with no context. | Frontend | Low |
| H-28 | **Test fixtures have no shared seed data** — `conftest.py` provides bare empty tables. Each test file manually inserts its own data via API calls, causing boilerplate and inconsistency. | Tests | Low |

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
| P1-I13 | **Add `timeout=15` to all Situation Room HTTP requests** | Add `timeout` parameter to all 34 `_http_session.get()` calls in sitroom workers to prevent thread hangs | H-7 |
| P1-I14 | **Add `f.flush(); os.fsync()` before `os.replace()` in config.py** | Prevent incomplete temp file on crash during config save | H-8 |
| P1-I15 | **Use configured Ollama port in ai.py** | Replace hardcoded `http://localhost:11434` with port from config/service module constant | H-9 |
| P1-I16 | **Add lock to `_event_subscribers` in state.py** | Prevent `RuntimeError: list changed size` during `_broadcast_event()` iteration | C-6 |
| P1-I17 | **Cancel previous AI stream on new message** | Use `AbortController` in AI chat to abort the previous `fetch()` stream before starting a new one | F-10 |
| P1-I18 | **Add `try-catch` around `fetch()` in `apiFetch()`** | Catch `TypeError` for offline/DNS-failure and return a structured error instead of propagating | F-9 |
| P1-I19 | **Fix SSE reconnect backoff** | Don't reset `_reconnectDelay` on connect; only reset after a sustained (>30s) successful connection | F-12 |
| P1-I20 | **Add NukeMap iframe `title` attribute** | Set `title="Nuclear effects map"` for screen reader context | H-27 |
| P1-I21 | **Cache failed `libtorrent` import** | Set a flag after first ImportError so subsequent calls skip the retry | H-13 |
| P1-I22 | **Prune unused CSS keyframes** | Remove unreferenced `bounceIn`, `slideUp`, etc. from `premium/05_motion.css` | H-17 |

#### P2: Medium Effort (1-4 hours each) [internal]

| # | Title | Description | Findings |
|---|-------|-------------|----------|
| P2-I01 | **Shared validation framework** | Create `web/validation.py` with a `validate_payload(data, schema)` utility that handles type checking, max_length, numeric bounds, required fields. Migrate existing `_*_SCHEMA` blueprints first, then add schemas to the 34 unvalidated ones. | A-4, B-1 |
| P2-I02 | **Extend auth gating to all mutation endpoints** | Apply `require_auth('admin')` decorator to POST/PUT/DELETE routes across all 57 unprotected blueprints. Use a decorator that's a no-op when auth is disabled (desktop default). | B-2 |
| P2-I03 | **Activity logging for remaining 34 blueprints** | Add `log_activity()` calls to mutations in garden, vehicles, tasks, power, family, checklists, medical_phase2, and 27 others. Use a decorator/middleware pattern to reduce boilerplate. | B-3 |
| P2-I04 | **Pagination for remaining 17 blueprints** | Apply `get_pagination()` to list endpoints in agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, interoperability, kb, kit_builder, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, timeline, training_knowledge. | B-4 |
| P2-I05 | **DELETE 404 hardening for 14 blueprints** | Add `rowcount == 0 -> 404` checks to DELETE routes in the 14 identified blueprints. | B-5 |
| P2-I06 | **Split `_create_indexes()` into per-module functions** | Break 593-line function into `_create_inventory_indexes()`, `_create_medical_indexes()`, etc. for maintainability. | A-6 |
| P2-I07 | **Service module Protocol/ABC** | Define a `ServiceProtocol` (Python Protocol class) with `download()`, `start()`, `stop()`, `running()`, `uninstall()` methods. Type-check all 7 service modules against it. | A-5 |
| P2-I08 | **Add CI test step** | Add `pytest` run before PyInstaller build in `.github/workflows/build.yml`. Fail the workflow on test failures. | G-1 |
| P2-I09 | **Add CI esbuild step** | Add `npm ci && node esbuild.config.mjs` step before PyInstaller in CI workflow. | G-2 |
| P2-I10 | **Thread-safe caches** | Replace `_api_cache` dict in app.py and `_ttl_cache` dict in state.py with `threading.Lock`-protected access or use `functools.lru_cache` / `cachetools.TTLCache`. | C-1, C-2 |
| P2-I11 | **SSE subscriber pruning** | Proactively remove stale SSE subscribers (queue full for >60s or last keepalive >60s ago) in the alert engine loop. | E-1, C-5 |
| P2-I12 | **SHA256 verification on service downloads** | Download checksums from upstream GitHub releases and verify after download for all 7 services, not just self-update. | H-4 |
| P2-I13 | **Migrate remaining 80+ `get_db()` calls to `db_session()`** | Convert bare `get_db()`/`db.close()` pairs across all blueprints to `with db_session() as db:` to prevent connection leaks. | B-6 |
| P2-I14 | **Migrate remaining 40 raw `fetch()` to api wrappers** | Convert unguarded `fetch()` GET calls in `_prep_dashboards.js`, `_prep_family_field.js`, `_prep_ops_mapping.js` to `apiFetch()` with `resp.ok` checks. | B-7 |
| P2-I15 | **Pin dependencies in `requirements.txt`** | Add `==X.Y.Z` version pins to all dependencies for reproducible builds. Add `requirements-dev.txt` for test deps. | G-6, G-12 |
| P2-I16 | **Add `schema_version` table for migrations** | Track applied column migrations in DB instead of checking `PRAGMA table_info()` for every migration on every startup. | D-6 |
| P2-I17 | **Parallelize `auto_start_services()`** | Start all 8 services in parallel threads instead of serial. Use a threading.Barrier or join loop to wait for all. | D-7 |
| P2-I18 | **Extract `build_situation_context()` to module level** | Move from inside `create_app()` to a module-level function in `web/utils.py` or `web/blueprints/ai.py` for testability. | A-8 |
| P2-I19 | **Add max file size to `download_file()`** | Check `Content-Length` header against a configurable maximum (e.g., 2 GB for services) before downloading. Abort if exceeded. | H-10 |
| P2-I20 | **Add disk space check before VACUUM** | Query available disk space with `shutil.disk_usage()` and refuse VACUUM if free space < current DB size. | H-11 |
| P2-I21 | **Add timeout to yt-dlp subprocess calls** | Set `timeout=3600` (1 hour) on `subprocess.run()` for media downloads to prevent thread hangs. | H-12 |
| P2-I22 | **Add semantic grouping to Settings HTML** | Wrap settings sections in `<fieldset>` with `<legend>` for AI, Display, Backup, System groups. | H-20 |
| P2-I23 | **Fix heading hierarchy in Tools tab** | Replace `<h5>` calculator names with `<h4>` to maintain proper document outline. | H-21 |
| P2-I24 | **Add `<caption>` or `aria-label` to all data tables** | Add accessible names to inventory, contacts, medical, checklists, and other data tables. | H-23 |
| P2-I25 | **Use semantic elements for layout** | Replace `<div class="sidebar">` with `<aside>` or `<nav>`, `<div role="main">` with `<main>`. | H-22 |
| P2-I26 | **Update CI action versions** | Upgrade to `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`. Add pip/npm cache. | G-8, G-9 |

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
| P3-I16 | **Session-scoped test fixture with transaction rollback** | Replace per-test `init_db()` (264 tables + 611 indexes per test) with a session-scoped fixture that creates the schema once and uses transaction rollback for test isolation. | D-8 |
| P3-I17 | **Expand test coverage to 39 untested blueprints** | Add at minimum smoke tests (list + create + get + delete) for each blueprint without a test file. Prioritize mutation-heavy blueprints. | H-14 |
| P3-I18 | **Add error-path and edge-case tests** | Add tests for invalid inputs, empty strings, extremely long values, non-existent IDs, and permission denied scenarios across all tested blueprints. | H-15 |
| P3-I19 | **Add SSE event propagation tests** | Test that inventory CRUD, alert creation, and task completion push events through `/api/events/stream`. | H-16 |
| P3-I20 | **Split `premium/30_preparedness_ops.css` (1,800 lines)** | Break into per-sub-tab CSS files (inventory, medical, garden, power, security, radio, weather). | H-18 |
| P3-I21 | **Consolidate print styles** | Merge scattered `@media print` rules from 4+ CSS files into a single `print.css` imported last. | H-24 |
| P3-I22 | **Add `pyproject.toml`** | Modern Python project metadata, build config, and tool settings in one file. Enables uv, ruff, mypy. | G-7 |
| P3-I23 | **Debounce `window.resize` handlers** | Add 100ms debounce to resize listeners in Situation Room and map files to prevent layout thrashing. | D-10 |
| P3-I24 | **Targeted DOM updates for dashboard widgets** | Replace `innerHTML =` on 30s refresh with incremental DOM updates or a diffing approach to preserve scroll position and hover states. | D-9 |
| P3-I25 | **Clear Morse code trainer interval on tab switch** | Hook into `switchPrepSub()` to clear leftover `setInterval` timers from the Radio sub-tab. | E-9 |
| P3-I26 | **Exclude raw CSS source from PyInstaller build** | Update `build.spec` to only include `web/static/dist/` (bundled output), not `web/static/css/app/` and `web/static/css/premium/` (raw source). | G-10 |
| P3-I27 | **Add source maps to esbuild** | Enable `sourcemap: true` in `esbuild.config.mjs` for production debugging. | G-11 |
| P3-I28 | **Extract shared tab-loader abstraction** | Create a generic `loadTabData(url, renderFn, containerId)` utility for the 40+ identical fetch-parse-render patterns in `_app_init_runtime.js`. | A-10 |

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
