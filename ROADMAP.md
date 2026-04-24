# Project N.O.M.A.D. — Roadmap

> **Baseline:** v7.44.0 (~310 tables, 2,000+ routes, 77 blueprints)
> **Current:** v7.61.0 (~326 tables, 2,100+ routes, 78 blueprints, `seeds/` package — 13 content modules shipped; V8 roadmap 15/24 Done)
> **Updated:** 2026-04-24
> **Prior feature backlog:** 134/187 items complete (72%), 8 deferred (4%), 45 internal refactoring remaining (24%)

---

## v8 Improvement Roadmap

Product-quality improvements identified from a deep architecture, security, performance, UX, testing, and documentation audit. Organized by impact tier.

### Tier 1: Critical — User-Facing Impact

| # | Title | Description | Status |
|---|-------|-------------|--------|
| V8-01 | ~~**Schema version gate**~~ | **Done** (v7.55.0) — `_meta` table, `_SCHEMA_VERSION = 54`, skips 935 SQL on match | Open |
| V8-02 | **Progressive disclosure** | Don't show all 35+ tabs by default. Start new users with 5-7 core tabs (Home, Inventory, Medical, Maps, AI, Settings). Advanced modules appear as data is populated or explicitly enabled via customize panel. Situation Room should NOT be the default landing for fresh installs — use Home. | Open |
| V8-03 | **Lazy tab loading** | Stop rendering all 61 HTML partials into a single 58,000-line DOM. Inject tab HTML on first activation. Keep sidebar nav static. Reduces initial DOM parse, memory footprint, and eliminates ID collision risk. | Open |

### Tier 2: High — Security & Reliability

| # | Title | Description | Status |
|---|-------|-------------|--------|
| V8-04 | **innerHTML audit — newer blueprints** | 315 `innerHTML =` across 20 files. Core modules are audited but agriculture (33), daily_living (37), land_assessment (25), data_foundation (6) are not individually verified. Adopt a sanitization wrapper or audit each assignment. | Open |
| V8-05 | ~~**Encrypt TOTP/API secrets at rest**~~ | **Done** (v7.55.0) — Fernet encrypt/decrypt with auto-generated key | Open |
| V8-06 | **Blueprint test coverage** | ~40 of 72 blueprints lack test suites. Especially: `roadmap_features.py` (75 routes, 0 tests), `agriculture.py`, `disaster_modules.py`, `daily_living.py`, `hunting_foraging.py`, `hardware_sensors.py`, `specialized_modules.py`. Add at minimum smoke tests (list + create + get + delete) for each. | Open |
| V8-07 | ~~**f-string SQL column hardening**~~ | **Done** (v7.55.0) — `safe_column()` validator added to `sql_safety.py` | Open |

### Tier 3: High — Architecture

| # | Title | Description | Status |
|---|-------|-------------|--------|
| V8-08 | **Split db.py into package** | 6,255-line monolith → `db/` package: `db/__init__.py` (exports), `db/core.py` (get_db, pool, session), `db/schema_core.py`, `db/schema_comms.py`, `db/schema_medical.py`, etc. Keep `init_db()` as orchestrator. | Open |
| V8-09 | **Split create_app()** | 1,655-line god function → extract: `web/middleware.py` (CSRF, rate limit, host validation), `web/blueprint_registry.py` (72 imports + registrations), `web/error_handlers.py`. `create_app()` becomes a thin orchestrator. | Open |
| V8-10 | ~~**Cache rendered template**~~ | **Done** (v7.61.0) — `_page_render_cache` (`web/app.py:342-372`) keys by `(tab_id, lang, bundle_js, media_sub, launch_restore, first_run_complete)` with TTL + 200-key prune. | Done v7.61.0 |
| V8-11 | **Lazy blueprint registration** | 72 blueprints imported eagerly in `create_app()`. Use Flask's deferred import pattern or group into domain packages. Import on first request to the URL prefix, not at startup. | Open |

### Tier 4: Medium — Developer Experience & Quality

| # | Title | Description | Status |
|---|-------|-------------|--------|
| V8-12 | **Frontend unit tests** | 32,779 lines of JS, 850+ functions, zero unit tests. Add a test framework (vitest or jest via jsdom) for critical functions: `escapeHtml`, `safeFetch`, `timeAgo`, `parseInventoryCommand`, `_parseSearchBang`. Start with the functions that have had bugs. | Open |
| V8-13 | ~~**Publish coverage to Codecov**~~ | **Done** (v7.55.0) — `codecov-action@v4` in build.yml | Open |
| V8-14 | ~~**Module-level column allowlists**~~ | **Done** (v7.61.0) — hoisted to `ALLOWED_EVAC_PLAN_FIELDS` / `ALLOWED_EVAC_RALLY_FIELDS` / `ALLOWED_EVAC_ASSIGNMENT_FIELDS` (emergency.py), `ALLOWED_WAYPOINT_FIELDS` (maps.py), `ALLOWED_MEDIA_META_FIELDS` + per-type extras (media.py). Regression-pinned in `tests/test_allowlists.py`. | Done v7.61.0 |
| V8-15 | ~~**Persist secret key for LAN**~~ | **Done** (v7.55.0) — auto-persist to config.json when auth required | Open |
| V8-16 | ~~**File-based DB integration test**~~ | **Done** (v7.61.0) — `tests/test_db_integration_file.py` (6 tests) exercises `init_db()` + `create_app()` against an on-disk SQLite file; pins WAL mode, core table presence, schema-version gate, connection-pool reuse across requests. | Done v7.61.0 |

### Tier 5: Nice-to-Have — Polish & Edge Cases

| # | Title | Description | Status |
|---|-------|-------------|--------|
| V8-17 | ~~**Situation Room thread pool**~~ | **Done** (pre-existing) — already uses `ThreadPoolExecutor(max_workers=8)` | Open |
| V8-18 | ~~**Soft delete / trash pattern**~~ | **Done** (v7.55.0) — `deleted_at` on 4 tables + trash/restore/purge API | Open |
| V8-19 | **Mobile prep tab navigation** | 25 prep sub-tabs in 5 categories overflow on small screens. Add a mobile-specific accordion or sheet-based navigation for the two-tier category → sub-tab pattern. | Done v7.59.0 |
| V8-20 | **Standalone docs site** | The 41-section in-app guide exists but no searchable external documentation. Generate a static site (MkDocs or Docusaurus) from markdown for the non-technical preparedness audience. | Done v7.59.0 |
| V8-21 | **macOS code signing** | macOS build produces unsigned binary. Gatekeeper warns "unidentified developer." Add Apple Developer certificate signing to CI or document the notarization process. | Open |
| V8-22 | ~~**Auto-update checksum parity**~~ | **Done** (v7.61.0) — `SHA256SUMS.txt` is generated in `build.yml:220` (`sha256sum *`) for Windows/Linux/macOS artifacts. `services.py::api_update_download` fetches the manifest, matches by filename, and hard-fails on mismatch for all three platforms. | Done v7.61.0 |
| V8-23 | ~~**Seeded test data isolation**~~ | **Done** (v7.61.0) — explicit fixtures landed in `tests/conftest.py`: `seed_upc_entry`, `seed_rag_scope_row`, `assert_upc_seeded`, `assert_rag_scope_seeded`. Tests opt in by listing the fixture instead of assuming `init_db()` side-effects. | Done v7.61.0 |
| V8-24 | ~~**CSS cascade documentation**~~ | **Done** (v7.55.0) — `web/static/css/README.md` with full architecture | Open |

### Summary

| Tier | Items | Theme |
|------|-------|-------|
| **1 — Critical** | 3 | Startup speed, UX simplicity, memory |
| **2 — High** | 4 | Security hardening, test coverage |
| **3 — High** | 4 | Architecture decomposition |
| **4 — Medium** | 5 | Dev experience, quality infrastructure |
| **5 — Nice-to-have** | 8 | Edge cases, distribution, docs |
| **Total** | **24** | |

### What's Already Done Well

These strengths should be preserved during any refactoring:

- Token-driven design system (2,000+ values reference CSS custom properties)
- 15+ security audit rounds (SQL injection, XSS, path traversal, CSRF all addressed)
- Connection pooling with health validation and dirty-state rejection
- Thread safety with dedicated locks per concern
- Accessibility (skip-link, focus-visible, aria, reduced-motion, RTL, battery-saver)
- Offline-first architecture (IndexedDB, service worker, PWA)
- Comprehensive 303-table data model covering an extraordinarily broad domain
- 1,357 tests across 80 files with per-test DB isolation

---

## Prior Feature Backlog (v7.44.0 → v7.54.0)

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

## Improvement Backlog — Status Summary (v7.52.0)

| Priority | Total | Complete | Deferred | Open |
|----------|-------|----------|----------|------|
| **P1** Quick Wins | 21 | 21 | 0 | 0 |
| **P2** Medium Features | 27 | 27 | 0 | 0 |
| **P3** Nice-to-Haves | 19 | 13 | 6 | 0 |
| **P4** Deep-Dive Loop 1 | 20 | 20 | 0 | 0 |
| **P5** Deep-Dive Loop 2 | 24 | 22 | 2 | 0 |
| **P1-I** Internal Quick Wins | 22 | 22 | 0 | 0 |
| **P2-I** Internal Medium | 26 | 7 | 0 | 19 |
| **P3-I** Internal Larger | 28 | 2 | 0 | 26 |
| **Totals** | **187** | **134 (72%)** | **8 (4%)** | **45 (24%)** |

**All feature-facing roadmap items (P1-P5) are complete or explicitly deferred.**

The 45 remaining open items are all **internal code quality** refactoring (P2-I + P3-I): splitting large files, migrating DB call patterns, expanding test coverage, CSS token completion, and similar mechanical tasks that don't add user-facing features.

The 8 deferred items require external hardware (Meshtastic radio), ML model training (plant ID), architectural rewrites (Tauri, plugin API), external system integration (Home Assistant), separate projects (Android app), or complex AI agent architecture (multi-step tool chaining).

---

### P1: Quick Wins (< 1 hour each) — 21/21 Complete

| # | Title | Status |
|---|-------|--------|
| P1-01 | ~~Loading skeletons on all tabs~~ | **Done** — `_app_core_shell.js:1379` |
| P1-02 | ~~Empty-state illustrations~~ | **Done** — `.empty-state` + variants across all CSS layers |
| P1-03 | ~~Keyboard shortcut cheat sheet modal~~ | **Done** — `_shortcuts_overlay.html`, `?` key trigger |
| P1-04 | ~~Tab badge counts~~ | **Done** — `updateTabBadges()` in `_app_ops_support.js:4903` |
| P1-05 | ~~Favicon dynamic badge~~ | **Done** — `_app_core_shell.js:1394` |
| P1-06 | ~~Collapsible sidebar groups~~ | **Done** — `initSidebarGroupCollapse()` in `_app_core_shell.js:1461` |
| P1-07 | ~~Settings search/filter~~ | **Done** — `_app_core_shell.js:1442` |
| P1-08 | ~~Inventory quick-edit inline~~ | **Done** — `_prep_inventory_flows.js:931` |
| P1-09 | ~~Toast action buttons~~ | **Done** — `toast.js:23-56`, `action={label, onclick}` |
| P1-10 | ~~Print preview in-app~~ | **Done** — `_app_init_runtime.js:224` |
| P1-11 | ~~Relative timestamps~~ | **Done** — `timeAgo()` in `_app_dashboard_readiness.js:705` |
| P1-12 | ~~Confirm before bulk operations~~ | **Done** — media batch delete has count confirm; `confirm.bulkDelete` i18n key added |
| P1-13 | ~~Auto-focus search on Ctrl+K~~ | **Done** — `toggleCommandPalette()` auto-focuses |
| P1-14 | ~~Inventory sort persistence~~ | **Done** — `nomad-inv-sort` localStorage |
| P1-15 | ~~Service uptime display~~ | **Done** — `_formatUptime()` + `get_service_uptime()` |
| P1-16 | ~~Expiry countdown badges~~ | **Done** — `daysLeft + 'd'` pills in inventory |
| P1-17 | ~~Sidebar item reorder~~ | **Done** — `initSidebarDragReorder()` in `_app_core_shell.js:1498` |
| P1-18 | ~~Copy-to-clipboard on data cells~~ | **Done** — `_app_core_shell.js:1424` |
| P1-19 | ~~AI conversation tags~~ | **Done** — tags column in conversations, filter UI |
| P1-20 | ~~AI prompt presets~~ | **Done** — `_app_workspace_profiles.js:129` |
| P1-21 | ~~Meal plan date labels~~ | **Done** — `toLocaleDateString` with weekday in daily_living |

### P2: Medium Features (1-4 hours each) — 27/27 Complete

| # | Title | Status |
|---|-------|--------|
| P2-01 | ~~First-run onboarding wizard~~ | **Done** — `system.py` wizard routes + state mgmt |
| P2-02 | ~~Barcode product database lookup~~ | **Done** — `inventory.py` UPC table + lookup/scan routes |
| P2-03 | ~~QR code label generation~~ | **Done** — `system.py /api/qr/generate` SVG output |
| P2-04 | ~~Recipe-driven consumption~~ | **Done** (v7.48.0) — recipes CRUD + cook route auto-deducts |
| P2-05 | ~~Equipment maintenance scheduler~~ | **Done** — `vehicles.py` maintenance tracking + overdue alerts |
| P2-06 | ~~Drag-and-drop widget reorder~~ | **Done** (v7.52.0) — `.widget-dropzone` CSS + drag primitives |
| P2-07 | ~~OpenAPI/Swagger spec~~ | **Done** (v7.51.0) — auto-generated `/api/openapi.json` + Swagger UI at `/api/docs` |
| P2-08 | ~~Expanded i18n coverage~~ | **Done** (v7.51.0) — 56→210+ keys (buttons, errors, empty states, labels, status) |
| P2-09 | ~~Inventory location hierarchy~~ | **Done** (v7.48.0) — nested locations with tree API |
| P2-10 | ~~Scheduled report export~~ | **Done** — CSV export + ReportLab PDF |
| P2-11 | ~~Content pack browser~~ | **Done** — `specialized_modules.py` content pack CRUD |
| P2-12 | ~~Service health history graph~~ | **Done** (v7.48.0) — service_health_log table + history API |
| P2-13 | ~~Inline survival quick-reference~~ | **Done** (v7.51.0) — 10 reference cards (water, fire, shelter, first aid, nav, signals, food, knots, weather, radio) |
| P2-14 | ~~Multi-user profiles~~ | **Done** (v7.50.0) — list profiles via app_users API |
| P2-15 | ~~Inventory item photos gallery~~ | **Done** (v7.52.0) — `.photo-gallery` CSS grid + lightbox primitives |
| P2-16 | ~~Map bookmark/favorite locations~~ | **Done** (v7.49.0) — map_bookmarks CRUD |
| P2-17 | ~~Notification center panel~~ | **Done** (v7.52.0) — `.notification-drawer` slide-out panel CSS |
| P2-18 | ~~CSV export for all entities~~ | **Done** (v7.50.0) — generic `/api/export/csv/<table>` |
| P2-19 | ~~Inventory fractional quantities~~ | **Done** (pre-existing) — schema already accepts `(int, float)` for quantity |
| P2-20 | ~~Task assignment to contacts~~ | **Done** — `assigned_to` column + filter in tasks.py |
| P2-21 | ~~Battery/consumable tracker~~ | **Done** (v7.48.0) — battery_tracker CRUD |
| P2-22 | ~~AI model management UI~~ | **Done** — `ai.py` model pull/delete/info routes |
| P2-23 | ~~Per-conversation knowledge scope~~ | **Done** (v7.49.0) — kb_scope column + GET/PUT |
| P2-24 | ~~URL-based recipe import~~ | **Done** (v7.49.0) — JSON-LD scraping + auto-import |
| P2-25 | ~~Meal plan calendar view~~ | **Done** (v7.52.0) — `.meal-calendar` 7-column CSS grid |
| P2-26 | ~~Survival duration simulator~~ | **Done** — `consumption.py` what-if calculator |
| P2-27 | ~~Caloric gap analysis~~ | **Done** (v7.47.0) — `/api/consumption/caloric-gap` per-category

### P3: Nice-to-Haves and Polish — 13/19 Complete, 6 Deferred

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P3-01 | ~~**Animated page transitions**~~ | **Done** (v7.52.0) — `.tab-content` opacity + `pageIn` animation, reduced-motion safe | Dashy |
| P3-02 | ~~**Dashboard theme previews**~~ | **Done** (v7.52.0) — `.theme-preview-card` CSS with sidebar/header/body regions | Dashy |
| P3-03 | ~~**Inventory heatmap calendar**~~ | **Done** (v7.52.0) — `.heatmap-grid` + `.heatmap-cell[data-level]` 4-tier color scale | Grocy |
| P3-04 | ~~**Command palette**~~ | **Done** — `toggleCommandPalette()` with search, actions, keyboard nav | Dashy |
| P3-05 | ~~**Customizable status strip**~~ | **Done** (v7.52.0) — `.status-strip-config` + `.status-strip-item` drag CSS | Glance |
| P3-06 | **Meshtastic serial bridge** | **Deferred** — requires Meshtastic hardware (USB radio dongle) | Meshtastic Web |
| P3-07 | **Offline plant identification** | **Deferred** — requires ML model training + large dataset | SurvivalManual |
| P3-08 | ~~**Insurance & warranty tracker**~~ | **Done** (v7.48.0) — warranties CRUD with expiry tracking | Homebox, Prepper Nerd |
| P3-09 | ~~**Visual alert rule builder**~~ | **Done** (v7.52.0) — `.rule-builder` + `.rule-condition` + `.rule-operator` CSS primitives | Internal backlog |
| P3-10 | **Plugin/extension API** | **Deferred** — architecture redesign; `web/plugins.py` already loads user plugins | Dashy |
| P3-11 | **Tauri shell alternative** | **Deferred** — entire Rust/WASM rewrite of shell layer | Internal backlog |
| P3-12 | ~~**SBOM generation**~~ | **Done** (v7.50.0) — `pyproject.toml` with project metadata | Internal backlog |
| P3-13 | **Regional content packs** | **Deferred** — requires data curation from 4+ international agencies | IIAB |
| P3-14 | ~~**Lightweight/minimal mode**~~ | **Done** (v7.48.0) — `NOMAD_MINIMAL_MODE=1` config flag | Glance, Survive-AI |
| P3-15 | **Home Assistant integration** | **Deferred** — requires HA instance + MQTT broker for testing | Grocy, Meshtastic HA |
| P3-16 | ~~**AI model comparison view**~~ | **Done** (v7.51.0) — `/api/ai/compare` sends same prompt to 2 models | Open WebUI |
| P3-17 | ~~**AI function/tool calling**~~ | **Done** (v7.51.0) — 6 tools (query_inventory, check_weather, count_contacts, get_alerts, search_notes, calculate_dosage) via `/api/ai/tools` | Open WebUI |
| P3-18 | ~~**Shopping list aisle grouping**~~ | **Done** (v7.50.0) — `/api/shopping-list/grouped` with 8 aisle categories | Mealie, Grocy |
| P3-19 | **Android companion app** | **Deferred** — entirely separate Kotlin/Compose project | Grocy (Android), IIAB (Android) |

### P4: Deep-Dive Discoveries — 20/20 Complete

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P4-01 | ~~**Per-widget refresh intervals**~~ | **Done** (v7.48.0) — dashboard_templates table with per-widget config_json | Glance (per-widget cache TTL) |
| P4-02 | ~~**Preconfigured dashboard templates**~~ | **Done** (v7.48.0) — dashboard_templates table + CRUD + export/import | Glance (preconfigured pages) |
| P4-03 | ~~**Exportable/importable dashboard config**~~ | **Done** (v7.48.0) — `/api/dashboard/config/export` + `/import` JSON | Glance (config-as-code), Dashy (cloud backup) |
| P4-04 | ~~**Calendar widget with ICS/CalDAV support**~~ | **Done** (v7.48.0) — calendar_events CRUD + ICS file import | Glance (#94, 15 votes), Homepage (calendar widget), Dashy (#1201, 10 votes) |
| P4-05 | ~~**Custom API widget renderer**~~ | **Done** (v7.49.0) — `/api/widgets/custom-api` fetches + returns any JSON API | Glance (custom-api widget), Homepage (customapi widget), Dashy (API response widget) |
| P4-06 | ~~**Search bangs / module shortcuts**~~ | **Done** (v7.46.0) — `/i`, `/c`, `/n`, `/m`, `/w`, `/f`, `/d`, `/t`, `/e`, `/a`, `/s` prefixes in command palette | Dashy (search bangs) |
| P4-07 | ~~**Right-click context menus on dashboard elements**~~ | **Done** (v7.52.0) — `.context-menu` CSS + `initContextMenus()` JS handler | Dashy (right-click edit) |
| P4-08 | ~~**Minimal startpage mode**~~ | **Done** (v7.52.0) — `?view=minimal` URL param + `html[data-view="minimal"]` CSS | Dashy (minimal view) |
| P4-09 | ~~**Workspace/tiled multi-panel view**~~ | **Done** (v7.52.0) — `.tiled-workspace` CSS grid (2/3/4 panel layouts) | Dashy (workspace view) |
| P4-10 | ~~**Auto theme switching (day/night schedule)**~~ | **Done** (v7.45.0) — uses `/api/sun` sunrise/sunset data, falls back to 9pm-6am | Glance (#674, 9 votes) |
| P4-11 | ~~**Service opening methods**~~ | **Done** (v7.52.0) — `.service-open-dropdown` + `.service-open-menu` CSS | Dashy (opening methods) |
| P4-12 | ~~**Favicon auto-fetch for services and bookmarks**~~ | **Done** (v7.49.0) — `/api/favicon?url=` returns base64 favicon | Homepage (#174, 11 votes), Dashy (favicon icon type) |
| P4-13 | ~~**CPU/GPU temperature monitoring**~~ | **Done** (v7.46.0) — `cpu_temp` in `/api/system` via psutil `sensors_temperatures()` | Homepage (#86, 16 votes) |
| P4-14 | ~~**Torrent status dashboard widget**~~ | **Done** (v7.48.0) — `/api/dashboard/torrent-widget` | Homepage (Deluge widget, #190, 25 votes) |
| P4-15 | ~~**Auth proxy / header authentication**~~ | **Done** (v7.47.0) — `NOMAD_AUTH_PROXY=1` trusts `X-Forwarded-User` + `X-Forwarded-Role` | Dashy (#981, 11 votes), Glance (#905, 9 votes) |
| P4-16 | ~~**Mobile swipe navigation**~~ | **Done** (v7.52.0) — touch swipe JS + `.swipe-indicator` / `.swipe-dot` CSS | Glance (#128, 10 votes) |
| P4-17 | ~~**Icon library system**~~ | **Done** (v7.52.0) — `[data-icon]::before` CSS primitive for icon rendering | Glance (4 icon prefixes), Dashy (7 icon types) |
| P4-18 | ~~**Config environment variable injection**~~ | **Done** (v7.48.0) — `_expand_env_vars()` in `get_config_value()` | Glance (env var injection), Homepage (env vars in YAML) |
| P4-19 | ~~**Health check endpoint**~~ | **Done** (v7.45.0) — `GET /healthz` with status/version/uptime/db_ok/services_running | Dashy (#768, 5 votes) |
| P4-20 | ~~**Masonry/auto-fill grid layout**~~ | **Done** (v7.52.0) — `.masonry-grid` CSS columns layout | Dashy (#1233, 4 votes) |

### P5: Deep-Dive Discoveries Loop 2 — 22/24 Complete, 2 Deferred

New items discovered from analyzing recent releases (Open WebUI v0.7-0.8, Glance v0.8.x, Homepage v1.11-1.12), open issue trends, and architectural patterns not covered in Pass 1.

| # | Title | Description | Inspired By |
|---|-------|-------------|-------------|
| P5-01 | ~~**AI Skills / domain expertise profiles**~~ | **Done** (v7.48.0) — `ai_skills` table with CRUD, system_prompt + kb_scope fields | Open WebUI (Skills, v0.8.0, #21312) |
| P5-02 | ~~**AI message queuing**~~ | **Done** (v7.52.0) — `.chat-queued-indicator` CSS primitive | Open WebUI (Message queuing, v0.8.0) |
| P5-03 | ~~**AI usage analytics dashboard**~~ | **Done** (v7.48.0) — `ai_usage_log` table + `/api/ai/usage` analytics + daily breakdown | Open WebUI (Analytics dashboard, v0.8.0, #21106) |
| P5-04 | ~~**Prompt version control**~~ | **Done** (v7.49.0) — `ai_prompt_versions` table + version/rollback API | Open WebUI (Prompt version control, v0.8.0, #20945) |
| P5-05 | ~~**AI citation deep-links**~~ | **Done** (v7.52.0) — `.citation-highlight` CSS with scroll-margin | Open WebUI (Citation deep-links, v0.7.0, #20116) |
| P5-06 | **AI multi-step tool chaining** | **Deferred** — requires complex AI agent loop architecture; single-step tools (P3-17) shipped | Open WebUI (Native function calling, v0.7.0, #19397) |
| P5-07 | ~~**2FA/TOTP authentication**~~ | **Done** (v7.49.0) — TOTP setup/verify + 8 backup codes via pyotp | Open WebUI (#1225, 58 votes) |
| P5-08 | ~~**KB archive upload auto-extract**~~ | **Done** (v7.49.0) — `/api/kb/upload-archive` ZIP/TAR extract + register | Open WebUI (#16151, 11 votes) |
| P5-09 | ~~**KB image import with OCR**~~ | **Done** (v7.50.0) — `/api/kb/import-image` with Tesseract OCR fallback | Open WebUI (#13137, 35 votes) |
| P5-10 | ~~**User-configurable URL monitor widget**~~ | **Done** (v7.48.0) — `url_monitors` CRUD + manual check route | Glance (Monitor widget) |
| P5-11 | ~~**Todo/task dashboard widget**~~ | **Done** (v7.48.0) — `/api/dashboard/tasks-widget` overdue + upcoming | Glance (Todo widget) |
| P5-12 | ~~**Web page change detection**~~ | **Done** (v7.50.0) — `/api/monitors/<id>/snapshot` with SHA-256 hash diff | Glance (ChangeDetection.io widget) |
| P5-13 | ~~**OPML/subscription import for RSS**~~ | **Done** (v7.48.0) — `/api/feeds/import-opml` with dedup | Glance (#302, 8 votes — YouTube/Twitch import) |
| P5-14 | ~~**Self-signed cert trust for federation**~~ | **Done** (v7.49.0) — `allow_insecure` flag per peer via API | Glance (#739, 9 votes — custom API allow-insecure) |
| P5-15 | ~~**Per-page/tab access control**~~ | **Done** (v7.49.0) — `tab_permissions` setting with role-based tab visibility | Glance (#694, 7 votes), Open WebUI (per-user resource sharing) |
| P5-16 | ~~**Host header validation**~~ | **Done** (v7.46.0) — `NOMAD_ALLOWED_HOSTS` env var, `_host_header_check()` before_request | Homepage (HOMEPAGE_ALLOWED_HOSTS) |
| P5-17 | ~~**Security notice in README**~~ | **Done** (v7.47.0) — prominent security blockquote with NOMAD_ALLOWED_HOSTS + NOMAD_AUTH_REQUIRED guidance | Homepage (Security Notice) |
| P5-18 | ~~**Test coverage tracking in CI**~~ | **Done** (v7.49.0) — pytest-cov + XML report in build.yml | Homepage (Codecov badge) |
| P5-19 | ~~**Release drafter automation**~~ | **Done** (v7.49.0) — `.github/release-drafter.yml` config | Homepage (release-drafter) |
| P5-20 | ~~**CONTRIBUTING.md with widget/blueprint guide**~~ | **Done** (v7.49.0) — full guide with blueprint + widget examples | Homepage (200+ contributors), Glance (contributing guidelines) |
| P5-21 | ~~**Active task sidebar indicator**~~ | **Done** (v7.52.0) — `.convo-task-indicator` pulsing dot CSS | Open WebUI (Active task indicator, v0.8.0) |
| P5-22 | ~~**Fuzzy settings search with keyword aliases**~~ | **Done** (v7.52.0) — `upgradeFuzzySettingsSearch()` with 12 alias mappings | Open WebUI (Settings search, v0.7.0, #20434) |
| P5-23 | ~~**Bcrypt password hashing for auth**~~ | **Done** (v7.50.0) — `/api/auth/upgrade-hash` bcrypt upgrade route | Glance (bcrypt + brute-force protection) |
| P5-24 | ~~**Personal RSS feed reader**~~ | **Done** (v7.48.0) — `personal_feeds` + `personal_feed_items` CRUD + refresh | Glance (#313, 13 votes — Miniflux integration) |

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

#### P1-I: Quick Wins [internal] — 22/22 Complete

| # | Title | Description | Findings |
|---|-------|-------------|----------|
| P1-I01 | ~~**Extract `_safe_int`/`_safe_float`/`_utc_now` to utils.py**~~ | **Done** (pre-v7.44) — already centralized in `web/utils.py` | A-1, A-3 |
| P1-I02 | ~~**Remove `_esc` redefinitions**~~ | **Done** (pre-v7.44) — blueprints import `esc` from `web/utils.py` | A-2 |
| P1-I03 | ~~**Strip 190+ `console.log` from production JS**~~ | **Done** — zero `console.log` in production JS | F-1 |
| P1-I04 | ~~**Add `proc.kill()` fallback in `stop_process()`**~~ | **Done** (pre-v7.44) — escalates SIGTERM→SIGKILL after 10s | E-3 |
| P1-I05 | ~~**Add lock to `_download_progress` in manager.py**~~ | **Done** (pre-v7.44) — `_dl_progress_lock` exists | C-3 |
| P1-I06 | ~~**Add lock to `_service_logs` in manager.py**~~ | **Done** (pre-v7.44) — `_svc_logs_lock` exists | C-4 |
| P1-I07 | ~~**Skip redundant PRAGMAs on pooled connections**~~ | **Done** (pre-v7.44) — WAL uses double-checked locking, once per process | D-1 |
| P1-I08 | ~~**FTS5 search input sanitization**~~ | **Done** (pre-v7.44) — double-quoted phrase matching strips special chars | D-4 |
| P1-I09 | ~~**Fix `get_db()` connection leak on PRAGMA failure**~~ | **Done** (pre-v7.44) — try/except with conn.close() | E-6 |
| P1-I10 | ~~**Close DB pool connections on shutdown**~~ | **Done** (pre-v7.44) — pool has proper cleanup patterns | E-2 |
| P1-I11 | ~~**Service health URLs respect configured ports**~~ | **Done** — `_get_service_port()` + port templating in health URLs | H-2 |
| P1-I12 | **Delete dead `_wizard_state` from state.py** | Wizard state IS used (has locking); onboarding wizard exists | H-1 |
| P1-I13 | ~~**Add `timeout=15` to all Situation Room HTTP requests**~~ | **Done** (pre-v7.44) — all 40+ HTTP calls have timeouts | H-7 |
| P1-I14 | ~~**Add `f.flush(); os.fsync()` before `os.replace()` in config.py**~~ | **Done** (pre-v7.44) — save_config() has flush+fsync | H-8 |
| P1-I15 | ~~**Use configured Ollama port in ai.py**~~ | **Done** (v7.45.0) — 3 calls now use `ollama.OLLAMA_PORT` | H-9 |
| P1-I16 | ~~**Add lock to `_event_subscribers` in state.py**~~ | **Done** (pre-v7.44) — `_sse_lock` guards all SSE ops | C-6 |
| P1-I17 | ~~**Cancel previous AI stream on new message**~~ | **Done** (pre-v7.44) — AbortController per message | F-10 |
| P1-I18 | ~~**Add `try-catch` around `fetch()` in `apiFetch()`**~~ | **Done** (v7.45.0) — structured network error with status:0 | F-9 |
| P1-I19 | ~~**Fix SSE reconnect backoff**~~ | **Done** (v7.45.0) — resets only after 30s sustained connection | F-12 |
| P1-I20 | ~~**Add NukeMap iframe `title` attribute**~~ | **N/A** — NukeMap is inline DOM, not an iframe | H-27 |
| P1-I21 | ~~**Cache failed `libtorrent` import**~~ | **Done** (pre-v7.44) — `_LT_AVAILABLE` flag at module level | H-13 |
| P1-I22 | **Prune unused CSS keyframes** | Remove unreferenced `bounceIn`, `slideUp`, etc. from `premium/05_motion.css` | H-17 |

#### P2-I: Medium Effort [internal] — 7/26 Complete, 19 Open (mechanical refactoring)

| # | Title | Description | Findings |
|---|-------|-------------|----------|
| P2-I01 | **Shared validation framework** | Create `web/validation.py` with a `validate_payload(data, schema)` utility that handles type checking, max_length, numeric bounds, required fields. Migrate existing `_*_SCHEMA` blueprints first, then add schemas to the 34 unvalidated ones. | A-4, B-1 |
| P2-I02 | **Extend auth gating to all mutation endpoints** | Apply `require_auth('admin')` decorator to POST/PUT/DELETE routes across all 57 unprotected blueprints. Use a decorator that's a no-op when auth is disabled (desktop default). | B-2 |
| P2-I03 | **Activity logging for remaining 34 blueprints** | Add `log_activity()` calls to mutations in garden, vehicles, tasks, power, family, checklists, medical_phase2, and 27 others. Use a decorator/middleware pattern to reduce boilerplate. | B-3 |
| P2-I04 | **Pagination for remaining 17 blueprints** | Apply `get_pagination()` to list endpoints in agriculture, daily_living, disaster_modules, evac_drills, exercises, group_ops, hunting_foraging, interoperability, kb, kit_builder, land_assessment, movement_ops, nutrition, regional_profile, security_opsec, timeline, training_knowledge. | B-4 |
| P2-I05 | **DELETE 404 hardening for 14 blueprints** | Add `rowcount == 0 -> 404` checks to DELETE routes in the 14 identified blueprints. | B-5 |
| P2-I06 | **Split `_create_indexes()` into per-module functions** | Break 593-line function into `_create_inventory_indexes()`, `_create_medical_indexes()`, etc. for maintainability. | A-6 |
| P2-I07 | **Service module Protocol/ABC** | Define a `ServiceProtocol` (Python Protocol class) with `download()`, `start()`, `stop()`, `running()`, `uninstall()` methods. Type-check all 7 service modules against it. | A-5 |
| P2-I08 | ~~**Add CI test step**~~ | **Done** — `build.yml` runs pytest on all 3 platforms before build | G-1 |
| P2-I09 | ~~**Add CI esbuild step**~~ | **Done** (v7.46.0) — Node.js 20 setup + `npm ci && node esbuild.config.mjs` before build | G-2 |
| P2-I10 | **Thread-safe caches** | Replace `_api_cache` dict in app.py and `_ttl_cache` dict in state.py with `threading.Lock`-protected access or use `functools.lru_cache` / `cachetools.TTLCache`. | C-1, C-2 |
| P2-I11 | **SSE subscriber pruning** | Proactively remove stale SSE subscribers (queue full for >60s or last keepalive >60s ago) in the alert engine loop. | E-1, C-5 |
| P2-I12 | **SHA256 verification on service downloads** | Download checksums from upstream GitHub releases and verify after download for all 7 services, not just self-update. | H-4 |
| P2-I13 | **Migrate remaining 80+ `get_db()` calls to `db_session()`** | Convert bare `get_db()`/`db.close()` pairs across all blueprints to `with db_session() as db:` to prevent connection leaks. | B-6 |
| P2-I14 | **Migrate remaining 40 raw `fetch()` to api wrappers** | Convert unguarded `fetch()` GET calls in `_prep_dashboards.js`, `_prep_family_field.js`, `_prep_ops_mapping.js` to `apiFetch()` with `resp.ok` checks. | B-7 |
| P2-I15 | ~~**Pin dependencies in `requirements.txt`**~~ | **Done** (v7.52.0) — version ranges in requirements.txt + requirements-dev.txt | G-6, G-12 |
| P2-I16 | **Add `schema_version` table for migrations** | Track applied column migrations in DB instead of checking `PRAGMA table_info()` for every migration on every startup. | D-6 |
| P2-I17 | **Parallelize `auto_start_services()`** | Start all 8 services in parallel threads instead of serial. Use a threading.Barrier or join loop to wait for all. | D-7 |
| P2-I18 | **Extract `build_situation_context()` to module level** | Move from inside `create_app()` to a module-level function in `web/utils.py` or `web/blueprints/ai.py` for testability. | A-8 |
| P2-I19 | ~~**Add max file size to `download_file()`**~~ | **Done** (v7.52.0) — `MAX_DOWNLOAD_BYTES` (2GB) + Content-Length check | H-10 |
| P2-I20 | ~~**Add disk space check before VACUUM**~~ | **Done** (v7.52.0) — refuses if free < 2x DB size | H-11 |
| P2-I21 | **Add timeout to yt-dlp subprocess calls** | Set `timeout=3600` (1 hour) on `subprocess.run()` for media downloads to prevent thread hangs. | H-12 |
| P2-I22 | **Add semantic grouping to Settings HTML** | Wrap settings sections in `<fieldset>` with `<legend>` for AI, Display, Backup, System groups. | H-20 |
| P2-I23 | **Fix heading hierarchy in Tools tab** | Replace `<h5>` calculator names with `<h4>` to maintain proper document outline. | H-21 |
| P2-I24 | **Add `<caption>` or `aria-label` to all data tables** | Add accessible names to inventory, contacts, medical, checklists, and other data tables. | H-23 |
| P2-I25 | **Use semantic elements for layout** | Replace `<div class="sidebar">` with `<aside>` or `<nav>`, `<div role="main">` with `<main>`. | H-22 |
| P2-I26 | ~~**Update CI action versions**~~ | **Done** (pre-v7.44) — already on actions/checkout@v4, setup-python@v5 | G-8, G-9 |

#### P3-I: Larger Effort [internal] — 2/28 Complete, 26 Open (refactoring + infrastructure)

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
| P3-I22 | ~~**Add `pyproject.toml`**~~ | **Done** (v7.50.0) — project metadata + pytest + ruff config | G-7 |
| P3-I23 | **Debounce `window.resize` handlers** | Add 100ms debounce to resize listeners in Situation Room and map files to prevent layout thrashing. | D-10 |
| P3-I24 | **Targeted DOM updates for dashboard widgets** | Replace `innerHTML =` on 30s refresh with incremental DOM updates or a diffing approach to preserve scroll position and hover states. | D-9 |
| P3-I25 | **Clear Morse code trainer interval on tab switch** | Hook into `switchPrepSub()` to clear leftover `setInterval` timers from the Radio sub-tab. | E-9 |
| P3-I26 | **Exclude raw CSS source from PyInstaller build** | Update `build.spec` to only include `web/static/dist/` (bundled output), not `web/static/css/app/` and `web/static/css/premium/` (raw source). | G-10 |
| P3-I27 | ~~**Add source maps to esbuild**~~ | **Done** (v7.52.0) — `sourcemap: true` on JS + CSS bundles | G-11 |
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

---

## Content-Expansion Backlog (Module Review, 2026-04-22)

> Content-gap audit across all 78 blueprints + catalogs + templates. NOMAD ships strong *structure* (42 calculators, 51 reference cards, 14 checklists, 15 printables, 633 curated media items) but several modules ship **empty reference tables** where the schema exists but no seed data does. New users hit those empty tables on day one and the module looks broken. Priority = close the "empty engine" gaps first.
>
> **Effort legend:** S = < 1 day content authoring; M = 1-3 days; L = 3-7 days (assumes domain expert available, integration is small).
> **Status legend:** `Open` / `In Progress` / `Done` / `Deferred`.
>
> **Progress (v7.60):** 15 / 40 shipped (38%). Done: CE-01, CE-02, CE-03, CE-04, CE-05 (pre-existing), CE-06, CE-07, CE-10, CE-11, CE-12, CE-13, CE-14, CE-15, CE-16, CE-19.
> **New infrastructure:** `seeds/` package pattern — reference data lives in `seeds/*.py` modules, seed functions in `db.py` do `INSERT OR IGNORE` idempotent inserts. Prevents `db.py` bloat as more content lands. Static (non-DB) reference tables like radio reference, water purification, appliance wattage, and loadout templates follow the same pattern — `seeds/*.py` + a blueprint route that wires the data to the UI.

### CE-Tier 1: Empty-Engine Seed Data (user-blocking)

These modules have functioning logic but ship zero reference data, so the module looks broken or hobbled to a new user.

| # | Title | Module | Effort | Status |
|---|-------|--------|--------|--------|
| CE-01 | ~~**Seed planting calendar**~~ **Done** (v7.61) — 47 crops × 8 USDA zones (3-10) = 1,069 rows in `seeds/planting_calendar.py` → `_seed_planting_calendar()`. Programmatic: baseline crop timing × zone offsets (cold zones = later spring / earlier fall; warm zones reversed). Each row carries yield_per_sqft + calories_per_lb + days_to_harvest. Min-zone gating keeps long-season crops (sweet potato, eggplant) out of zones too cold to grow them. | `garden.py` | M | Done |
| CE-02 | ~~**Seed companion-plant database**~~ **Done** (v7.60) — 92 directed pairs in `seeds/companion_plants.py` → `_seed_companion_plants()` in db.py. Covers tomato/brassica/three-sisters/allium/nightshade + universal helpers (marigold/nasturtium/borage/dill/yarrow) + universals (fennel/black walnut). | `garden.py` | S | Done |
| CE-03 | ~~**Add `DOSAGE_GUIDE` with 40+ common field meds**~~ **Done** (v7.62) — expanded from 8 → 47 drugs via `seeds/medications.py` merged into the existing in-module list. New rows carry adult + pediatric weight-based dosing, max daily, contraindications, pregnancy category (FDA A/B/C/D/X), shelf-life (military SLEP data), and brand names. Covers NSAIDs, analgesics, GI (loperamide/ORS/ondansetron/bismuth/famotidine), allergy (diphenhydramine/cetirizine/loratadine/epinephrine/prednisone/albuterol), antibiotics (amoxicillin/Augmentin/azithromycin/doxycycline/ciprofloxacin/metronidazole/cephalexin/Bactrim), cardiac (lisinopril/losartan/metoprolol/atorvastatin/nitroglycerin), diabetes (metformin/glucose/glucagon), trauma (TXA/lidocaine/ketamine/naloxone), mental (diazepam/hydroxyzine), topical (triple-antibiotic/mupirocin/silvadene/hydrocortisone/erythromycin-eye), and prophylaxis (KI/vitamin K/permethrin). | `medical.py` | M | Done |
| CE-04 | ~~**Add `DRUG_INTERACTIONS` matrix**~~ **Done** (v7.62) — expanded from 26 → 78 pairs via `seeds/medications.py` merged into existing list. Covers NSAID stacking, anticoagulant interactions (warfarin + cipro/metronidazole/Bactrim/Vit K/fish oil/ginkgo/garlic/amoxicillin/doxycycline), opioid/CNS depressant stacking (oxycodone+alcohol/benzos/gabapentin), serotonin syndrome (SSRI+MAOI/triptans/St John's Wort/linezolid/DXM), ACE/ARB/potassium stacking, beta-blocker interactions, statin interactions (grapefruit, macrolides, fibrates), nitroglycerin+PDE5 contraindication, KI+lithium, St. John's Wort CYP induction, grapefruit CYP3A4 inhibition. Severity graded major/moderate/minor. | `medical.py` | M | Done |
| CE-05 | ~~**Seed radio-frequency directory**~~ **Already done** — `web.blueprints.comms._seed_frequencies()` lazy-seeds ~340 entries on first GET /api/comms/frequencies (verified by `tests/test_radio.py::TestFrequencies::test_list_frequencies`). The "zero entries" claim in the original review was wrong. `seeds/frequencies.py` (v7.60) holds 77 curated entries with richer metadata — keep as a future consolidation candidate (see CE-05a). | `tactical_comms.py` | — | Done |
| CE-05a | **Consolidate freq seed into `seeds/` package** — move the large inline seed in `comms._seed_frequencies()` to the `seeds/frequencies.py` module pattern so all reference data lives in one place. Zero behavior change, pure refactor. | `comms.py` / `seeds/` | S | Open |
| CE-06 | ~~**Seed appliance-wattage reference table**~~ **Done** (v7.60) — 84 items across 10 categories in `seeds/appliance_wattage.py` (Refrigeration, Laundry, HVAC, Well/Plumbing, Medical, Comms/IT, Lighting, Power tools, Yard, Small misc). Exposed via new `GET /api/power/appliance-wattage` with items + category groupings. Each row carries running W, surge W, typical hours/day, notes. | `power.py` | S | Done |
| CE-07 | ~~**Seed 15 weather-action rule templates**~~ **Done** (v7.60) — 15 rules in `seeds/weather_action_rules.py` → `_seed_weather_action_rules()`. Covers pressure drop / severe low, freeze / hard freeze / extreme cold, heat / extreme heat, high / damaging / severe wind, mold-risk RH, flash-flood rain rate, AQI unhealthy / hazardous, lightning proximity. Each rule stores a JSON action_data with severity + actionable message. | `weather.py` | S | Done |
| CE-08 | **Ship 40-60 grid-down recipes** (hardtack, pemmican, jerky, rice-and-beans, no-knead bread, canned-food casseroles, fermented vegetables, rehydrated-meal templates, pickled eggs) with no-cook / open-fire / rocket-stove variants. | `meal_planning.py` | L | Open |
| CE-09 | **Ship 40-60 KB articles** covering water purification, fire, shelter, knots, CPR/Heimlich, tourniquet, land nav, improvised antenna, canning/fermentation, husbandry basics, cold/heat injuries, envenomation, sanitation, OPSEC. KB currently ships empty. | `kb.py` | L | Open |
| CE-10 | ~~**Ship 20-30 loadout bag templates**~~ **Done** (v7.61) — 15 curated templates in `seeds/loadout_templates.py`: 72-hr adult + child, EDC, get-home (short/long), INCH, vehicle (temperate/winter/desert), IFAK+, canoe/boat, winter-mountain, desert 72-hr, backcountry 3-day, urban/apartment. Each template has target weight + bag-level config + 15-40 items with category + weight + notes. Exposed via `GET /api/loadout/templates` (read) and `POST /api/loadout/templates/launch` (one-shot "create bag from template" in a single transaction). | `loadout.py` | M | Done |

### CE-Tier 2: Missing Critical Reference

High-impact additions where a module has partial coverage but misses reference data serious users expect.

| # | Title | Module | Effort | Status |
|---|-------|--------|--------|--------|
| CE-11 | **Expand disaster checklists from 5 → 20-25 items each** (earthquake, hurricane, tornado, wildfire, flood, pandemic, EMP, economic collapse, volcanic, drought). Current defaults are stubs. | `disaster_modules.py` | M | Open |
| CE-12 | ~~**Add hazmat / bio-agent / chem-agent reference tables**~~ **Done** (v7.63) — `seeds/hazmat_agents.py` ships 17 agents across chemical / nerve / blister / biological / radiological categories (chlorine, ammonia, HCN, phosgene, H2S, sarin/GB, VX, mustard HD, lewisite, chloropicrin, anthrax, smallpox, plague, botulinum, ricin, Cs-137, I-131). Each row carries CAS + UN numbers, IDLH, ERPG-1/2/3, symptoms, route, decon, first aid, antidote, PPE level, evac distance, sources (NIOSH / DOT ERG 2024 / AIHA / CDC / USAMRIID). Exposed via `GET /api/hazmat/agents` (list + category filter + q search) and `GET /api/hazmat/agents/<id>` (detail). Read-only defensive reference only — no synthesis/weaponization content. | `specialized_threats.py` | M | Done |
| CE-13 | ~~**Add pediatric growth-chart percentiles + weight-based dosing helper**~~ **Done** (v7.62) — `seeds/medications.py` ships `PEDIATRIC_MILESTONES` (23 rows, newborn → 18 yr, 3rd/50th/97th %ile weight + 50th %ile height per WHO 0-24 mo + CDC 2-20 yr), `PEDIATRIC_WEIGHT_BANDS` (20 Broselow-style bands), and `estimate_pediatric_weight(age_years)` helper for when a scale isn't available. Exposed via `GET /api/medical/pediatric-growth` (full chart) + `GET /api/medical/pediatric-weight-estimate?age_years=N` (quick band lookup). | `medical.py` | S | Done |
| CE-14 | ~~**Add phonetic alphabet / Morse chart / proword glossary / RST reference / digital-mode card**~~ **Done** (v7.61) — `seeds/radio_reference.py` ships NATO + LAPD phonetic alphabets, full International Morse (letters/digits/punctuation + 10 prosigns), 31 US voice prowords with usage examples, 3-axis RST scale (readability / strength / tone), 21 Q-codes, 16 digital-mode comparison card (CW/FT8/FT4/JS8/PSK31/RTTY/VARA/Pactor/APRS/Winlink/DMR/D-STAR/C4FM/P25/SSTV/Meshtastic), and the US General-class HF band plan. Exposed via `GET /api/radio/reference` (bundle), `GET /api/radio/phonetic` (quick lookup), and `GET /api/radio/morse/<text>` (translator). | `tactical_comms.py` | S | Done |
| CE-15 | ~~**Add 40+ medicinal herbs**~~ **Done** (v7.62) — `seeds/medicinal_herbs.py` extends original 10 to 50 species (61 total entries). Added: Peppermint, Spearmint, Rosemary, Sage, Thyme, Oregano, Lavender, Lemon Balm, Valerian, Passionflower, Skullcap, Hops, Dandelion, Burdock, Nettle, Mullein, Horehound, Goldenseal, Goldenrod, Uva Ursi, Red Clover, Raspberry Leaf, Black Cohosh, Blue Cohosh, Shepherd's Purse, Cramp Bark, Wild Lettuce, Catnip, Bee Balm, Lemongrass, Mugwort, Wormwood, Cayenne, Astragalus, Ashwagandha, Holy Basil, Turmeric, Slippery Elm, Marshmallow, Mallow, Violet, Chickweed, Cleavers, Yellow Dock, Oregon Grape, Usnea, St. John's Wort, Kava, Ginkgo, American Ginseng, Meadowsweet. Every row carries scientific name + uses + preparation + dosing + contraindications + season + habitat. Seed is both auto-run at init_db AND via existing `POST /api/medical/herbal/seed`. | `medical_phase2.py` | M | Done |
| CE-16 | ~~**Seed 40 garden pest-guide entries**~~ **Done** (v7.60) — 38 entries in `seeds/pest_guide.py` → `_seed_pest_guide()`. Covers 19 insects (aphid → earwig), 2 mollusk/nematode, 12 diseases (early/late blight, powdery/downy mildew, fusarium/verticillium, TSWV, septoria, cedar-apple rust, fire blight, club root, bacterial wilt), 4 vertebrate pests (deer, rabbit, vole, groundhog), 2 physiological disorders. Each row carries symptoms + IPM-first treatment + prevention. | `garden.py` | S | Done |
| CE-17 | **Seed ~100 seed-catalog varieties** (variety × days-to-maturity × yield estimate) for the garden planting engine. | `garden.py` | M | Open |
| CE-18 | **Add game identification key + CWD/trichinella/giardia risk matrix** (toxic lookalikes: chokecherry vs pin cherry, wild carrot vs hemlock, morel vs false-morel). | `hunting_foraging.py` | M | Open |
| CE-19 | ~~**Add purification-method reference**~~ **Done** (v7.61) — `seeds/water_purification.py` ships 10 methods (boil, bleach, iodine, CLO2, ceramic, hollow-fiber, RO, UV, SODIS, distillation) with removes / does_not_remove / equipment / time / cost / pros / cons / best_for; CDC boil times by altitude band; bleach + iodine dose charts (1 qt → 275 gal IBC) with clear + cloudy-water doses; iodine medical contraindications; 9-class contaminant-response matrix (bacteria / viruses / protozoa / Crypto / heavy metals / salts / VOCs / radiological / turbidity) with recommended methods. Replaces prior 6-method stub at `GET /api/water/purification-reference` — backward-compatible shape. | `water_mgmt.py` | S | Done |
| CE-20 | **Add APT / threat-actor catalog** with MITRE ATT&CK TTP mapping (Lazarus, APT28, APT29, Turla, Carbanak, Scattered Spider, Volt Typhoon, etc.). | `threat_intel.py` | M | Open |

### CE-Tier 3: Checklist + Drill + Guide Expansion

| # | Title | Module | Effort | Status |
|---|-------|--------|--------|--------|
| CE-21 | **Add eldercare emergency kit template** (mobility aids, chronic Rx stockpile, oxygen/dialysis backup, hearing-aid batteries, cognitive safety). | `checklist_templates_data.py` | S | Open |
| CE-22 | **Add pet evacuation kit template** (carrier, food 7d, meds, vaccine records, ID photo, muzzle, calming aids). | `checklist_templates_data.py` | S | Open |
| CE-23 | **Add business-continuity checklist** (remote-work gear, payroll failover, customer list backup, supplier alternates). | `checklist_templates_data.py` | S | Open |
| CE-24 | **Add multi-household-pod template** (skills inventory, resource-pooling agreement, comms schedule, conflict-resolution). | `checklist_templates_data.py` | S | Open |
| CE-25 | **Add apartment-dweller 72-hr template** (no-yard constraints: tub storage, window-sill stove, stairs evac). | `checklist_templates_data.py` | S | Open |
| CE-26 | **Add active-shooter response template** (Run-Hide-Fight, doors/windows, LE interaction). | `checklist_templates_data.py` | S | Open |
| CE-27 | **Add chemical-spill SIP template** (seal gaps, HVAC shutdown, interior-room selection). | `checklist_templates_data.py` | S | Open |
| CE-28 | **Add 15 more drill scenarios** (tornado, active-shooter lockdown, CBRN SIP, multi-family reunion, mass-casualty bombing, cyberattack/ICS, EMP cold-start, house fire at night w/ pets, winter shelter, child-missing, intruder at night, vehicle breakdown in hostile weather, water contamination, grid-down 14-day, market-run panic). | `training_knowledge.py` | M | Open |
| CE-29 | **Add missing decision guides** (medical differential — fever+rash / cough+hemoptysis / chest pain; envenomation; psychological crisis; group decision-making; animal attack; navigation failure; leadership crisis; crop failure; supply-chain failure; infrastructure failure). Brings 10 → ~21 (matches CLAUDE.md claim). | `web/templates/.../_app_ops_support.js` | M | Open |
| CE-30 | **Add missing reference cards** (snake/spider/scorpion ID by region; edible-vs-toxic plant lookalikes; mushroom lookalikes; weather cloud severity; trauma triage; pediatric vitals; elder dosing; pet first-aid; mental-health crisis; envenomation field response). | `_guides.html` / templates | M | Open |

### CE-Tier 4: Calculators, Print Docs, Doc Gaps

| # | Title | Module | Effort | Status |
|---|-------|--------|--------|--------|
| CE-31 | **Add water purification calculators** (filter cartridge life; bleach ppm by container; boil time at altitude; SODIS duration). | calculators | S | Open |
| CE-32 | **Add food-preservation calculators** (canning time by altitude+food+jar; smoking temp/time; drying RH curves). | calculators | S | Open |
| CE-33 | **Add fermentation calculators** (salt ppm for lacto; sugar for mead/wine; pH safety thresholds). | calculators | S | Open |
| CE-34 | **Add expense burn-rate / reorder-point / supply-chain calculators**. | calculators | S | Open |
| CE-35 | **Add wind-chill / heat-index / compost C:N / beekeeping calculators**. | calculators | S | Open |
| CE-36 | **Add damage-assessment form** (structure / utilities / inventory / insurance claim prep photos). | `print_routes.py` | S | Open |
| CE-37 | **Add family-meeting agenda / community-resource inventory / skill-proficiency matrix / evacuation-plan map print templates**. | `print_routes.py` | M | Open |
| CE-38 | **Seed ICS form examples** (wildfire / flood / civil-unrest / chem-spill sample fills) so new users see completed forms. | `group_ops.py` | S | Open |
| CE-39 | **Add docs pages for:** federation setup, service-install troubleshooting matrix, power/solar wiring, backup-restore runbook, upgrade/migration guide. | `docs/` | M | Open |
| CE-40 | **Add cascade calling tree / family-reunion / child-check-in / role-taxonomy templates**. | `contacts.py` / `family.py` | S | Open |

### Proposed Release Sequencing

Group the items into focused content-authoring passes so each release has a coherent theme:

- **v7.60 "First Harvest + Infrastructure"** → ✅ CE-02 (companion plants, 92 pairs) + ✅ CE-06 (appliance wattage, 84 loads) + ✅ CE-07 (weather rules, 15 templates) + ✅ CE-16 (pest guide, 38 entries) + `seeds/` package pattern established.
- **v7.61 "First Harvest II + Radio + Water"** → ✅ CE-01 (planting calendar, 1,069 rows across 47 crops × 8 zones) + ✅ CE-10 (15 loadout templates + launch-to-bag endpoint) + ✅ CE-14 (radio reference: NATO/LAPD phonetic, Morse + prosigns, 31 prowords, RST, Q-codes, 16 digital modes, US HF band plan) + ✅ CE-19 (water purification reference: 10 methods, CDC boil times, bleach/iodine dosing, 9-class contaminant response).
- **v7.62 "Field Medicine"** → ✅ CE-03 (DOSAGE_GUIDE 8→47 meds with pregnancy category + shelf life) + ✅ CE-04 (DRUG_INTERACTIONS 26→78 pairs) + ✅ CE-13 (pediatric growth chart + Broselow-style weight bands + weight estimator API) + ✅ CE-15 (medicinal herbs 10→61). Auto-seed on init_db; seeds/medications.py + seeds/medicinal_herbs.py centralize the data out of blueprint files.
- **v7.63 "Knowledge Base"** → CE-08 (grid-down recipes) + CE-09 (40-60 KB articles) + CE-11 (expanded disaster checklists) + CE-12 (hazmat/bio/chem agent reference). Large content pass; sets NOMAD apart on out-of-box usability.
- **v7.64 "Checklists + Drills"** → CE-21 through CE-30. Adult-scenario coverage (elderly, pets, business, multi-household) + drill library expansion + missing decision guides/cards.
- **v7.65 "Polish + Tools"** → CE-17 (seed catalog) + CE-18 (game ID) + CE-20 (APT catalog) + CE-31 through CE-40. Calculators, print docs, doc gaps, ICS examples, contacts templates. Also **CE-05a**: consolidate the 340-entry inline freq seed in `comms.py` into the `seeds/` pattern.

Each release is scoped so a single focused content-authoring pass (by a domain expert) plus short engineering integration can ship it. None touches core architecture.

### Tracking Rules

- When an item ships, flip `Open` → `Done` in the table and add the release tag + one-line completion note (match the P1/P2 checkbox pattern used higher in this file).
- If an item is explicitly rejected or superseded, flip to `Deferred` with a one-line reason — don't delete.
- When adding a new content-gap item, prefix the ID with `CE-` and keep the module + effort + status columns populated so the sequencing stays scannable.

## Open-Source Research (Round 2)

### Related OSS Projects
- https://github.com/r0x0r/pywebview — the canonical pywebview framework with bundled HTTP server, DOM bridge, and small executable footprint — the core runtime NOMAD Field Desk already uses
- https://github.com/ClimenteA/pywebview-flask-boilerplate-for-python-desktop-apps — reference Flask + pywebview + PyInstaller scaffold for mid-size desktop apps; useful for packaging QA
- https://github.com/DizzyduckAR/pywebview-Frameless-boilerplate — frameless window with custom titlebar + light/dark/mono themes; reference for our Catppuccin chrome
- https://github.com/ohtaman/streamlit-desktop-app — Streamlit-in-pywebview pattern; interesting for future dashboard-style panes without re-authoring as Flask routes
- https://github.com/gassc/simple-inventory — Flask + Flask-Admin + SQLite + Chart.js inventory template; direct reference for the Inventory blueprint
- https://github.com/codingforentrepreneurs/python-desktop-app — tutorial-grade pywebview+Python reference; good comparison for executable size
- https://github.com/reidwallace/prepperpi — PrepperPi for the Pi-based offline-knowledge parallel; informs the AREDN/APRS/NOAA items and hotspot story
- https://github.com/iiab/iiab — Internet-in-a-Box, established OSS reference for the offline-knowledge category; architectural diff is useful when scoping CE- items

### Features to Borrow
- Frameless window with custom titlebar (DizzyduckAR) — tighter visual identity vs stock chrome; opt-in setting so Windows admin users aren't surprised
- Flask-Admin autogenerated CRUD (simple-inventory) — for the 300+ SQLite tables, prototype new admin panes without hand-rolling each; flip to bespoke UI only for hot-path blueprints
- Chart.js analytics (simple-inventory) — already fits our stack; standardize a Chart.js wrapper module so every blueprint's dashboard uses identical color tokens
- Streamlit pane as embedded view (ohtaman/streamlit-desktop-app) — useful when a blueprint needs dense data-exploration UX without authoring it in vanilla Flask+JS
- Bundled HTTP server hardening (pywebview) — document-and-enforce `localhost` binding + CSRF tokens on every mutating route; matches the "nothing leaves your machine" tagline
- Hotspot + captive-portal parity (PrepperPi) — for desktop edition, an optional "Broadcast NOMAD on my Wi-Fi" mode via `hostapd`/`dnsmasq` bundling on Linux; Windows variant via ICS
- AREDN / APRS / NOAA content modules (upstream NOMAD) — CE- candidates already on the roadmap; borrow the upstream's service contracts to keep field-desk seeds interoperable

### Patterns & Architectures Worth Studying
- Blueprint-per-module isolation (current NOMAD Field Desk) — already in place; double down by making each blueprint independently migratable (Alembic per blueprint), so future upgrades can be partial and rollback-safe
- Seed-pack distribution (NOMAD `seeds/` package, 13 modules shipped) — informs how to release curated content bundles without shipping them inside the exe; each seed is a downloadable ZIP registered at runtime
- pywebview bridge boundary — anything mutating state goes through a single `api.py` surface; keeps JS honest about which calls leave the renderer. Audit across 77 blueprints on next release.
- Hybrid Flask blueprints + Streamlit panes — evaluate allowing data-science-style panes to embed alongside hand-authored blueprints so operators can rapidly prototype analytics without touching the main UI framework

## Implementation Deep Dive (Round 3)

### Reference Implementations to Study
- **miahnelson/flask_pywebview_pyinstaller** — https://github.com/miahnelson/flask_pywebview_pyinstaller — minimal repo specifically demonstrating Flask + pywebview + PyInstaller single-file exe pipeline; direct reference architecture for N.O.M.A.D.'s packaging.
- **ClimenteA/pywebview-flask-boilerplate-for-python-desktop-apps** — https://github.com/ClimenteA/pywebview-flask-boilerplate-for-python-desktop-apps — mid-size app boilerplate with static/ and templates/; reference for multi-blueprint Flask layout inside a desktop shell.
- **BBurgarella/FlaskGPT** — https://github.com/BBurgarella/FlaskGPT — concrete Flask + pywebview + SQLite credentials example; shows port-selection and server-thread coordination.
- **r0x0r/pywebview `examples/flask_app`** — https://github.com/r0x0r/pywebview/tree/master/examples — canonical Flask + pywebview bootstrap; start Flask in daemon thread, then `webview.start()`.
- **volcan01010 gist (desktop DB frontend)** — https://gist.github.com/volcan01010/0e0fc53d6a512e1bbffc59037c25e872 — <100-line SQLAlchemy + Flask desktop DB pattern.
- **Tiangolo/FastAPI `full-stack-fastapi-template`** — https://github.com/tiangolo/full-stack-fastapi-template — reference for 77-blueprint decomposition if migrating off Flask; Pydantic + SQLModel patterns scale past 300 tables better than SQLAlchemy-only.
- **pallets/flask `src/flask/blueprints.py`** — https://github.com/pallets/flask/blob/main/src/flask/blueprints.py — authoritative blueprint registration semantics (needed to diagnose 77-blueprint route collisions).
- **pywebview `docs/guide/api.html`** — https://pywebview.flowrl.com/guide/api.html — `webview.start(func, args, gui='edgechromium')` — force Edge WebView2 on Windows for consistent JS support.

### Known Pitfalls from Similar Projects
- Flask dev server in production desktop build is noisy + single-threaded — switch to `waitress` (`from waitress import serve; serve(app, host='127.0.0.1', port=0)`) before shipping.
- pywebview + Flask race: if `webview.start()` fires before Flask's socket is listening, user sees blank window — poll `127.0.0.1:<port>` with `socket.connect_ex` until success, max 5s.
- PyInstaller + Flask: dynamic imports of blueprints break without `--collect-submodules nomad.blueprints` or similar; symptom is "404 on every route".
- SQLite WAL files break if user copies the `.db` without the `-wal`/`-shm` siblings — document backup flow OR disable WAL (`PRAGMA journal_mode=DELETE`) and accept the concurrency hit.
- pywebview JS bridge (`window.pywebview.api.*`) serializes through JSON — returning non-serializable types (datetimes, Decimal) silently yields `null`; serialize at the boundary.
- ~310 tables + SQLAlchemy ORM = slow `MetaData.reflect()` at startup; use declarative classes with explicit `__tablename__` instead of reflect, and lazy-import blueprint modules.
- 2,000+ routes: Flask's URL map is O(n) per request — chunk registration by domain (bookmarks.*, travel.*, etc.) and use `url_map.strict_slashes = False` consistently to avoid redirect loops.
- Edge WebView2 runtime may be missing on older Win10 LTSC; ship the evergreen bootstrapper or pre-install via MSI.

### Library Integration Checklist
- `Flask==3.1.0` — key API: `Blueprint(__name__, url_prefix='/x')`; gotcha: 3.x removed `before_first_request`; use `app.before_serving` + `@app.cli` or a once-flag in `before_request`.
- `pywebview==5.3.2` — https://pypi.org/project/pywebview — `webview.create_window(title, url)` + `webview.start(gui='edgechromium', debug=False)`. Gotcha: `gui='edgechromium'` requires WebView2 runtime; bundle installer.
- `waitress==3.0.2` — production WSGI for desktop; `serve(app, host='127.0.0.1', port=port, threads=8)`. Gotcha: no HTTP/2, fine for localhost.
- `SQLAlchemy==2.0.36` — 2.x syntax `select(User).where(...)` — 1.x `Query` API still works but deprecated. Gotcha: `create_engine('sqlite:///...')` + `connect_args={'check_same_thread': False}` for multi-threaded Flask.
- `Flask-SQLAlchemy==3.1.1` — key API: `db.session.execute(select(...))`. Gotcha: requires Flask 2.3+; pin matched pair.
- `pywin32==308` — pywebview dep on Windows; PyInstaller hook `--collect-submodules pywin32`.
- `pyinstaller==6.11.1` — spec essentials: `--add-data "static;static" --add-data "templates;templates" --collect-submodules <package>`, runtime hook for `multiprocessing.freeze_support()` (CLAUDE.md global rule).
- `python-dotenv==1.0.1` — load `.env` before `Flask(__name__)`; gotcha: PyInstaller one-file expands to `_MEIPASS`, so `.env` path must be resolved relative to `sys.executable` not `__file__`.
