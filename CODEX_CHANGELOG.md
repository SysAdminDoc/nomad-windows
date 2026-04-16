# CODEX Change Log

Last updated: 2026-04-15 (pass 11)

Purpose: handoff notes for Claude or any follow-on agent so recent Codex work is easy to understand without reconstructing the full thread.

## Summary

This pass was a broad QA, UX, accessibility, and performance audit across the shared shell plus the embedded `NukeMap` and `VIPTrack` workspaces.

The work was not a single feature branch. It was an iterative repair pass focused on:

- shrinking oversized HTML responses
- hardening shared runtime behavior
- restoring keyboard-visible focus across first-party tools
- repairing NukeMap custom toggle keyboard semantics
- hardening import, training, and scanner semantics for keyboard and screen-reader use
- adding missing alt text and intrinsic sizing to runtime-generated media and preview images
- hardening blob URL lifecycle cleanup and export/download safety
- replacing VIPTrack blob-backed PWA assets with static scoped files
- improving semantic labeling/live-region behavior
- fixing a real VIPTrack settings startup bug
- extending regression coverage so these issues do not quietly return

## Major Changes

### 1. Shared runtime extraction and payload reduction

Moved the giant shared inline runtime out of page HTML and into a dedicated cached asset:

- `web/app.py`
- `web/templates/index.html`
- `web/templates/workspace_page.html`
- `web/templates/index_partials/js/_app_core_shell.js`
- `web/templates/index_partials/js/preparedness/_prep_people_comms.js`
- `tests/test_runtime_asset.py`
- `tests/test_core.py`

Impact:

- `/` dropped from about `2,051,740` bytes to about `93,668`
- `/preparedness` dropped to about `526,931`
- `/app-runtime.js` now serves the shared runtime separately at about `1,958,619` bytes with cache headers

Also fixed a real bootstrap bug where the LAN heartbeat payload still depended on inline Jinja templating after the split.

### 2. Shared shell accessibility/runtime defaults

Added runtime-level accessibility defaults in:

- `web/templates/index_partials/js/_app_core_shell.js`

This now:

- adds `type="button"` to buttons missing a type
- infers `aria-label`s for icon-like buttons
- reapplies those defaults to dynamically inserted DOM via `MutationObserver`

This was used to avoid patching dozens of scattered runtime-generated controls one by one.

### 3. CSS performance cleanup

Removed first-party `transition: all` usage from inline workspace partials under:

- `web/templates/index_partials/_tab_*.html`

The transitions were replaced with explicit property lists to reduce unnecessary layout/repaint work.

Regression coverage was added in:

- `tests/test_core.py`

### 4. Focus visibility repairs

Removed first-party `outline: none` / `outline:none` patterns and restored visible keyboard focus in:

- `web/viptrack/index.html`
- `web/nukemap/css/styles.css`
- `web/templates/index_partials/_tab_nukemap.html`
- `web/templates/index_partials/_tab_financial.html`
- `web/templates/index_partials/_tab_vehicles.html`
- `web/templates/index_partials/_tab_water_mgmt.html`

Also tightened tests so first-party CSS/partials do not regress to hidden focus.

### 5. Semantic labeling and live-region cleanup

Added or improved semantics in:

- `web/nukemap/index.html`
- `web/templates/index_partials/_tab_nukemap.html`
- `web/templates/index_partials/_utility_overlays.html`
- `web/templates/index_partials/_shell.html`
- `web/viptrack/index.html`

Notable repairs:

- explicit labels for key NukeMap controls such as warhead filter/select, yield controls, and wind speed
- `LAN` chat message stream exposed as a live log
- LAN encryption toggle explicitly labeled
- intrinsic image dimensions added to shared shell/wizard/VIPTrack logo assets to reduce layout shift
- VIPTrack settings/list sort selects now have explicit labels

### 6. VIPTrack switch semantics and startup bug fix

High-signal repair in:

- `web/viptrack/index.html`
- `tests/ui/shell-workflows.spec.mjs`
- `tests/test_core.py`

Changes:

- converted VIPTrack settings toggles from plain `div`s into semantic `button` switches using `role="switch"` and `aria-checked`
- added visible focus styling for those switches
- updated the bookmark modal Enter handler from `keypress` to `keydown`
- added a shared `syncToggleSwitchState(...)` helper so visual and semantic state stay aligned
- fixed a real bug where `trailRenderer` existed but `trailRenderer.init()` was never called, so the trail-direction setting was not actually wired on startup

This was the biggest functional bug found in the wider pass.

### 7. NukeMap switch keyboard semantics repair

Additional repair in:

- `web/nukemap/css/styles.css`
- `web/templates/index_partials/_tab_nukemap.html`
- `web/nukemap/js/app.js`
- `tests/test_core.py`
- `tests/ui/shell-workflows.spec.mjs`

Problem:

- NukeMap's custom toggle rows looked like switches, but the visible control shell itself did not expose reliable keyboard semantics in the embedded workspace audit pass

Changes:

- restored explicit focus-visible styling for the visible NukeMap switch shell in both standalone and embedded CSS
- added `NM.enhanceToggleRows()` so `.toggle-row` labels become keyboard targets with `role="switch"`, `tabindex="0"`, synced `aria-checked`, and `Space` / `Enter` handling
- kept the native checkbox as the backing state source so the existing `change` listeners and feature toggles still work unchanged
- extended regression coverage so the runtime switch semantics and keyboard toggle path are now checked in both Python and Playwright

This closed the biggest remaining keyboard-accessibility gap I found after the earlier focus-outline cleanup.

### 8. Import, training, and scanner semantic repairs

Additional repair in:

- `web/templates/index_partials/_tab_interoperability.html`
- `web/templates/index_partials/_tab_training_knowledge.html`
- `web/templates/index_partials/js/_app_init_runtime.js`
- `web/templates/index_partials/js/preparedness/_prep_inventory_flows.js`
- `tests/test_core.py`

Changes:

- converted the interoperability import drop zone from a click-only `div` into a keyboard-targetable control with `role="button"`, `tabindex="0"`, `data-click-target`, and explicit `:focus-visible` styling
- converted flashcard deck launchers in Training & Knowledge from click-only cards into semantic `button` controls with accessible review labels and visible focus treatment
- added labels to runtime-generated receipt and vision scan editor controls so the per-item checkboxes, name fields, quantity fields, and category/condition selects are programmatically named
- added preview `alt` text for receipt and supply-image previews so those modal scanners are not exposing unnamed images
- labeled the generic CSV column-mapping selects generated in the shared runtime so import mapping controls expose which source column is being assigned

This pass targeted a broader class of keyboard and assistive-technology gaps in first-party generated UI, not just static partial markup.

### 9. Runtime media and preview image semantics

Additional repair in:

- `web/templates/index_partials/js/_app_media_maps_sync.js`
- `web/templates/index_partials/js/_app_services_ai.js`
- `web/templates/index_partials/js/_app_workspaces.js`
- `web/static/css/app/30_secondary_workspaces.css`
- `web/viptrack/index.html`
- `tests/test_core.py`

Changes:

- added `alt` text plus intrinsic `width` and `height` attributes to runtime-generated media thumbnails in the video grid, list view, and channel-browser search results
- added explicit sizing and object-fit treatment to the AI chat image preview thumbnail, plus an accessible preview label based on the selected filename
- added intrinsic dimensions and `alt` text to map export / map print images generated from canvas snapshots
- added intrinsic dimensions to the VIPTrack airline banner image so that small info-panel branding swaps do not reflow unnecessarily
- extended Python regression coverage so these generated image surfaces keep their labels and dimensions instead of silently drifting back

This pass focused on the remaining first-party image elements that were still being created at runtime without enough semantic or layout information.

## Pass 11 — Blob URL lifecycle hardening and VIPTrack PWA cleanup

Files:

- `web/templates/index_partials/js/_app_init_runtime.js`
- `web/templates/index_partials/js/_app_services_ai.js`
- `web/templates/index_partials/js/preparedness/_prep_inventory_flows.js`
- `web/templates/index_partials/js/_app_media_maps_sync.js`
- `web/templates/index_partials/js/_app_situation_room.js`
- `web/viptrack/index.html`
- `web/viptrack/manifest.webmanifest`
- `web/viptrack/sw.js`
- `tests/test_core.py`

Changes:

- added shared runtime helpers for safer blob download handling and object URL revocation so export flows no longer depend on immediate post-click `URL.revokeObjectURL(...)` timing
- fixed a real chat-image leak by revoking the preview blob URL on clear and clearing the preview DOM instead of only hiding it
- hardened the preparedness vision-image resize path so temporary object URLs are always cleaned up and canvas/toBlob failures fall back safely to the original file
- cleaned up the Situation Room snapshot download path and worker bootstrap so temporary blob URLs do not stay live longer than needed
- replaced VIPTrack’s blob-backed manifest and blob-backed service worker registration with static first-party files
- narrowed VIPTrack service-worker scope to `/viptrack/` instead of `/`, and stopped unregistering every service worker on the origin during startup
- added regression coverage so the repo keeps the shared blob helper, the preview cleanup, and the static VIPTrack PWA assets

Why this mattered:

- the old export pattern revoked blob URLs immediately after `click()`, which can be timing-fragile across browsers
- the AI chat preview and vision resize flow could accumulate temporary blob URLs over time
- VIPTrack’s installability path depended on a manifest that did not exist on disk plus an immediately revoked blob URL
- VIPTrack also used a root-scoped blob service worker and cleared all registrations on the origin, which was a risky boundary violation for a multi-surface app

## Pass 12 — Print/export popup hardening

Files:

- `web/templates/index_partials/js/_app_init_runtime.js`
- `web/templates/index_partials/js/_app_media_maps_sync.js`
- `web/templates/index_partials/js/_app_workspaces.js`
- `tests/test_core.py`
- `tests/test_print_documents.py`

Changes:

- added shared popup helpers so print/export windows can open immediately under the original user click, render a loading shell, and then swap in the finished document or a useful error state
- moved the ICS-213, ICS-309, and ICS-214 print flows onto that shared popup path instead of each one manually opening and writing its own window
- fixed a real browser-gesture bug in `generateMapAtlas()` by opening the popup before the awaited fetch instead of after it, which reduces legitimate atlas requests getting popup-blocked
- hardened the map print flow so blocked popups fail with a specific user-facing warning instead of a null-window crash path
- added regression coverage for the popup helpers and for atlas escaping so untrusted titles and waypoint labels stay HTML-safe

Why this mattered:

- async print/export flows that call `window.open()` only after network work often lose the browser’s user-gesture trust and get blocked even though the user explicitly clicked the action
- the old atlas path could fail after doing all the server work, leaving the user with a generic error instead of a document
- centralizing popup loading/error handling makes these long-running print flows more predictable and easier to maintain

## Pass 13 — In-app iframe and hidden-print race hardening

Files:

- `web/templates/index_partials/js/_app_init_runtime.js`
- `web/templates/index_partials/js/_app_workspaces.js`
- `web/templates/index_partials/js/preparedness/_prep_dashboards.js`
- `tests/test_core.py`

Changes:

- added shared `writeIframeHtml()` and `printHtmlInHiddenFrame()` runtime helpers so iframe-backed views and hidden print documents no longer depend on fragile one-off timers
- hardened the in-app application frame by canceling pending HTML renders when switching between URL-backed and HTML-backed content, which avoids stale delayed writes winning after rapid overlay changes
- replaced the old `openAppFrameHTML()` 50 ms timer with a tokenized iframe render path and added a defensive error toast when the frame cannot be written
- tightened `printAppFrame()` so it warns when the frame is still blank instead of attempting to print `about:blank`
- moved the preparedness wallet-card printer off of fixed `setTimeout` print/remove delays and onto the shared hidden-frame print helper with `afterprint` cleanup
- added regression coverage so future changes keep using the shared helpers and do not reintroduce the old timer-based frame writes

Why this mattered:

- the app-frame overlay had a real race where older delayed writes could overwrite newer content if users opened or closed embedded views quickly
- timer-based hidden-print cleanup is brittle on slower systems and can remove or desynchronize the print surface before the browser has fully handed off the print job
- centralizing iframe document writes makes these embedded help/print/report surfaces easier to reason about and safer to extend

## Pass 10 — Sub-tab semantics, modal dialog, and workspace route repairs

### 10. Interoperability and Training-Knowledge sub-tab ARIA semantics

Repairs in:

- `web/templates/index_partials/_tab_interoperability.html`
- `web/templates/index_partials/_tab_training_knowledge.html`
- `web/app.py`
- `tests/test_core.py`
- `tests/ui/shell-workflows.spec.mjs`

**Sub-tab tablist pattern (both tabs):**

- Added `role="tablist"` + `aria-label` to each `.io-sub-tabs` / `.tk-sub-tabs` container
- Added `role="tab"` + `aria-selected` + `aria-controls` + `id` + `type="button"` to every sub-tab button
- Added `role="tabpanel"` + `tabindex="-1"` + `aria-labelledby` to every panel div
- Updated JS sub-tab switching to call `setAttribute('aria-selected', ...)` so screen readers track the active tab
- Added `aria-label` to the two history tables in Interoperability (`Recent exports`, `Recent imports`)
- Added `.io-sub-tab:focus-visible` and `.io-btn:focus-visible` CSS rules (Interoperability was missing these; Training-Knowledge already had them)

**Cross-training matrix modal (Training-Knowledge):**

- Added `role="dialog"` + `aria-modal="true"` + `aria-labelledby="tk-matrix-title"` to `#tk-matrix-modal`
- Added `id="tk-matrix-title"` to the h3 so the dialog has a programmatic label
- Added `id="tk-matrix-close"` + `type="button"` + `aria-label="Close cross-training matrix"` to the close button
- Updated `tkShowMatrix()` to call `closeBtn.focus()` on open so keyboard focus lands in the dialog

**Navigation bug fix (both tabs):**

Both tabs used a hardcoded `is-hidden` initial class and had no page-level routes. This caused broken navigation: when a user clicked either tab from any workspace page, the shell could not find the tab content in the DOM and would loop back to the current page.

Fixes:
- Added `'training-knowledge'` and `'interoperability'` entries to `workspace_pages` in `web/app.py` with routes `/training-knowledge` (alias `/training`) and `/interoperability` (alias `/data-exchange`)
- Added Flask route handlers `training_knowledge_page()` and `interoperability_page()`
- Replaced hardcoded `class="tab-content is-hidden"` with `class="tab-content{% if active_tab == '...' %} active{% endif %}"` in both tab partials, following the same pattern used by all other workspace tabs

**Regression coverage added:**

- `test_interoperability_and_training_sub_tab_semantics` — 26 static assertions covering tablist/tab/tabpanel roles, aria-selected, aria-controls, labelledby, history table labels, focus-visible CSS, JS aria-selected toggling, modal dialog semantics, and focus-on-open
- Three new Playwright tests:
  - `interoperability sub-tabs expose correct ARIA tablist semantics and toggle aria-selected`
  - `training-knowledge sub-tabs expose correct ARIA tablist semantics and toggle aria-selected`
  - `training-knowledge cross-training matrix modal has dialog semantics and receives focus on open`

These are the first route-specific browser tests for these two workspaces.

## Verification

Final verification status after pass 19:

- `pytest -q` -> `916 passed`
- `npm run visual:test` -> `22 passed`

Important note:

- do not run the Python suite and the Playwright visual suite in parallel on this machine
- `tests/test_crud_api.py` needs exclusive access to `C:\Users\--\AppData\Roaming\ProjectNOMAD\nomad.db`
- if a web server or another process is holding that DB open, collection can fail with a Windows file lock error

Running them sequentially was clean.

## Pass 14 — Premium shell, empty-state, and microcopy refinement

### 14. Shared shell/home/settings polish pass

Repairs in:

- `web/static/css/premium/90_theme_consistency.css`
- `web/templates/index_partials/_shell.html`
- `web/templates/index_partials/_tab_services.html`
- `web/templates/index_partials/_tab_settings.html`
- `tests/test_core.py`

**Shared premium CSS refinements:**

- Slightly increased the size and rhythm of shared buttons, shell icon buttons, shell status pills, and compact actions so the UI feels less cramped and more touch-friendly without changing the product structure
- Refined the sidebar context hub and workspace context bar with calmer spacing, clearer typography, softer metadata treatment, and stronger surface layering
- Added a shared premium empty-state treatment across high-traffic utility classes including `sidebar-empty-state`, `workspace-empty-copy`, `settings-empty-state`, `training-empty-state`, `activity-feed-empty`, `daily-brief-empty`, `home-continue-empty`, `prep-empty-state`, `benchmark-empty-state`, and `sr-empty`
- Softened a few overly shouty metadata chips (`home-launch-chip`, `services-console-kicker`, settings pills) so the visual hierarchy leans more on content and less on tiny all-caps labels

**Home and shell microcopy cleanup:**

- Updated the shell quick-return language so the sidebar context hub reads more like a polished product affordance and less like an internal utility
- Renamed the workspace context prompt from `Suggested Next Moves` to `Suggested actions` and tightened the helper sentence so it is calmer and easier to scan
- Reworded the Services home hero, resume copy, live dashboard loading state, prep-gap empty state, and daily brief empty state to be clearer and more premium

**Settings UX copy cleanup:**

- Tightened the settings command-deck description and renamed the first pill to `Desk modes`
- Rewrote the desk-memory empty states to be more direct and confidence-building
- Replaced terse loading copy in the monitoring/system/model sections with clearer status language

**Regression coverage added:**

- Updated the shell/home HTML assertions for the new premium copy
- Added `test_shared_premium_polish_contract_for_shell_home_and_settings` to pin the new shell/context/empty-state contract and the highest-value home/settings copy improvements

## Pass 15 — Specialty workspace command-deck and hierarchy refinement

Repairs in:

- `web/templates/index_partials/_tab_interoperability.html`
- `web/templates/index_partials/_tab_training_knowledge.html`
- `web/templates/index_partials/_tab_benchmark.html`
- `web/static/css/premium/60_benchmark_tools.css`
- `tests/test_core.py`

**Interoperability premium pass:**

- added a real command-deck header with clearer product framing, top-level actions (`Export Packs`, `Import Files`, `Batch Intake`, `Review History`), and calmer workflow pills
- rebuilt the sub-tab shell into a stronger surface with better hierarchy and more premium pill navigation
- added `ioActivatePanel()` so the new top actions drive the existing sub-tab system instead of being decorative
- rewrote export/import history loading, empty, and failure copy so the workspace feels more intentional and less like a raw utility table

**Training-Knowledge premium pass:**

- added a matching command-deck header with direct workspace actions and clearer framing around skills, drills, flashcards, and knowledge retention
- upgraded the sub-tab shell and card styling so the workspace aligns better with the newer premium command surfaces elsewhere in the app
- added `tkActivatePanel()` so command-deck actions switch the existing tab panels cleanly
- tightened multiple high-traffic empty and loading states (`skills`, `courses`, `lessons`, `certifications`, `drills`, `flashcards`, matrix modal, flashcard review`) so the workspace reads as guided and complete instead of sparse

**Diagnostics/benchmark premium pass:**

- tightened the diagnostics command-deck copy and hero messaging so the workspace emphasizes real-world responsiveness rather than just raw scores
- softened benchmark command pills to match the calmer premium system instead of tiny all-caps utility labels
- rewrote the benchmark empty/history copy and initial progress text to make the page feel more polished before the first run

**Regression coverage added:**

- added `test_specialty_workspaces_gain_premium_command_decks_and_calmer_empty_states`
- extended `test_interoperability_and_training_sub_tab_semantics` to pin the new command-deck panel-jump hooks

## Pass 16 — Agriculture and daily-living premium workspace refinement

Repairs in:

- `web/templates/index_partials/_tab_agriculture.html`
- `web/templates/index_partials/_tab_daily_living.html`
- `tests/test_core.py`

**Agriculture & Permaculture premium pass:**

- replaced the legacy single-line header with a real command deck that frames the workspace around guild design, soil recovery, infrastructure, and resource loops
- rebuilt the agriculture sub-tab row into a stronger premium shell with keyboard-safe tab semantics, clearer focus treatment, and direct top-level panel-jump actions
- added `agActivatePanel()` so command-deck actions and tabs drive the same panel state instead of relying on decorative buttons or one-off click handlers
- tightened the highest-traffic loading and empty states across guilds, layers, yields, soil projects, livestock, homestead systems, aquaponics, and recycling so the workspace feels more guided and less like a raw admin surface

**Daily Living & Quality of Life premium pass:**

- replaced the older header and emoji-heavy tab row with a calmer premium command deck focused on routines, sanitation, morale, sleep, and cooking
- upgraded the workspace tabs to real tablist semantics with `role="tablist"`, `aria-selected`, `aria-controls`, panel labeling, and shared panel-jump actions via `dlActivatePanel()`
- improved the rhythm of cards, buttons, empty states, and focus treatment so the workspace feels less cramped and more deliberate
- rewrote the most visible loading and empty states for schedules, chores, clothing, sanitation, morale, sleep, watch planning, readiness checks, recipes, and recipe search to make the space read like a guided household operations desk instead of a legacy utility

**Regression coverage added:**

- added `test_agriculture_and_daily_living_gain_premium_command_decks_and_accessible_panel_switching`
- kept the no-`outline:none` focus contract intact by using transparent outlines plus visible ring styling

## Pass 17 — Group-ops and disaster-modules premium workspace refinement

Repairs in:

- `web/templates/index_partials/_tab_group_ops.html`
- `web/templates/index_partials/_tab_disaster_modules.html`
- `tests/test_core.py`

**Group Operations & Governance premium pass:**

- replaced the legacy single-line header with a premium command deck focused on staffing, duty coverage, disputes, and civil defense instead of a plain utility title
- rebuilt the group-ops tab row into a stronger workflow shell with real `tablist` / `tab` / `tabpanel` semantics, clearer focus treatment, and `goActivatePanel()` so top-level actions and tabs drive the same workspace state
- expanded the copy quality across pods, governance, duties, disputes, votes, ICS forms, CERT teams, shelters, and warnings so the workspace feels calmer and more operationally guided
- normalized the tab label from `Civil Def` to `Civil Defense` so the surface scans like a polished product instead of an internal shorthand

**Disaster Modules premium pass:**

- replaced the older header with a readiness command deck that frames scenario plans, backup power, construction, fortifications, and checklist work more intentionally
- upgraded the disaster-modules tabs to the same premium shell and semantic panel model used by newer workspaces, including `dmActivatePanel()` for direct command-deck jumps
- rewrote the most visible loading and empty states for plans, quick-reference data, energy systems, construction projects, materials, fortifications, and checklists so the workspace feels complete even before data exists
- tightened card and button treatment to better match the newer preparedness surfaces without redesign churn

**Regression coverage added:**

- added `test_group_ops_and_disaster_modules_gain_premium_command_decks_and_accessible_panel_switching`
- re-ran targeted `tests/test_core.py`, then full sequential verification

## Pass 18 — Medical phase 2 and movement-ops premium workspace refinement

Repairs in:

- `web/templates/index_partials/_tab_medical_phase2.html`
- `web/templates/index_partials/_tab_movement_ops.html`
- `tests/test_core.py`

**Medical Phase 2 premium pass:**

- replaced the older utility header with a continuity-care command deck focused on maternal care, chronic conditions, wellness, veterinary support, and quick calculators
- rebuilt the medical sub-tab shell into a stronger premium navigation surface with real `tablist` / `tab` / `tabpanel` semantics, clearer focus treatment, and `mpActivatePanel()` so top-level actions and tabs drive the same state
- normalized terse labels like `Vet` into `Veterinary` so the workspace scans more like a finished product than an internal tool
- rewrote the highest-traffic loading and empty states for maternal care, dental records, chronic care, medication alerts, vaccinations, wellness check-ins, veterinary records, and herbal lookup so the desk feels calmer and more guided before data exists

**Movement Operations premium pass:**

- replaced the legacy single-line header with a route-planning command deck that frames movement plans, alternate transport, hazards, staging, and departure criteria more intentionally
- upgraded the workspace tabs to the same premium shell used in the newer preparedness desks, including semantic panel switching through `moActivatePanel()`
- tightened the card rhythm, button sizing, focus treatment, and mobile stacking so the surface feels less cramped and more deliberate on smaller widths
- rewrote the most visible loading and empty states for movement plans, alternate transport assets, route hazards, vehicle staging, and go/no-go gates so the workspace feels ready for first use instead of sparse

**Regression coverage added:**

- added `test_medical_phase2_and_movement_ops_gain_premium_command_decks_and_accessible_panel_switching`
- re-ran targeted `tests/test_core.py`, then full sequential verification

## Pass 19 — Security-opsec and tactical-comms premium workspace refinement

Repairs in:

- `web/templates/index_partials/_tab_security_opsec.html`
- `web/templates/index_partials/_tab_tactical_comms.html`
- `tests/test_core.py`

**Security & OPSEC premium pass:**

- replaced the old single-line security header with a command deck that frames compartments, threat posture, observation logs, night movement, and CBRN readiness as one coordinated protection surface
- upgraded the workspace tabs to real `tablist` / `tab` / `tabpanel` semantics and added `soActivatePanel()` so both the top-level command actions and the pills drive the same panel state
- normalized the rougher labels and navigation affordances so `Threat Matrix`, `Observation Log`, `Night Movement`, and `CBRN & EMP` scan like a polished product rather than an internal utility
- rewrote the roughest loading and empty states for compartments, duress signals, threats, observation posts, signature notes, night plans, CBRN inventory, procedures, and EMP analysis so the desk feels guided even before records exist

**Tactical Communications premium pass:**

- replaced the legacy header with a communications command deck focused on radio readiness, authentication, schedule discipline, standard message formats, and field weather tools
- rebuilt the comms sub-tab shell into the newer premium navigation pattern with semantic panel switching through `tcActivatePanel()`
- tightened card treatment, button sizing, focus states, and sub-tab hierarchy so the workspace feels calmer and more deliberate at first glance
- rewrote the highest-traffic loading and empty states for radios, auth sets, net schedules, and templates, and softened the built-in template helper copy so first-run use feels less abrupt

**Regression coverage added:**

- added `test_security_opsec_and_tactical_comms_gain_premium_command_decks_and_accessible_panel_switching`
- re-ran targeted `tests/test_core.py`, then full sequential verification

## Pass 20 — Backend hardening for request guards, LAN auth, and destructive actions

Repairs in:

- `web/utils.py`
- `web/app.py`
- `web/blueprints/__init__.py`
- `web/blueprints/alert_rules.py`
- `web/blueprints/benchmark.py`
- `web/blueprints/comms.py`
- `web/blueprints/medical.py`
- `web/blueprints/medical_phase2.py`
- `web/blueprints/preparedness.py`
- `web/blueprints/services.py`
- `web/blueprints/situation_room.py`
- `web/blueprints/system.py`
- `web/blueprints/tactical_comms.py`
- `web/blueprints/threat_intel.py`
- `web/blueprints/timeline.py`
- `tests/test_request_hardening.py`
- `tests/test_csrf.py`
- `tests/test_blueprint_system.py`

**Request hardening and correctness:**

- added shared bounded integer parsing through `coerce_int()` / `get_query_int()` and pushed it through pagination, activity, threat intel, and service-log endpoints so negative or oversized query args no longer bypass limits or trigger accidental over-read behavior
- tightened CSRF origin validation to true same-origin semantics, including rejecting different-port loopback origins while still allowing same-port localhost aliases
- fixed `/api/network` so it advertises the configured host and port instead of always hardcoding `:8080` or returning a LAN URL when the app is bound only to localhost

**Runtime stability and auth hardening:**

- added singleton guards around the UDP discovery listener and SSE stale-client cleanup worker so repeated `create_app()` calls do not spawn duplicate background threads
- upgraded simple LAN auth from unsalted SHA-256 comparisons to PBKDF2-backed password hashes while preserving backward compatibility for existing installs
- taught the remote auth path to transparently rehash legacy simple-auth values after a successful validated request
- fixed `/api/auth/check` so remote callers with a valid `X-Auth-Token` are reported as authenticated instead of being treated like unauthenticated LAN users
- hardened `/api/system/shutdown` to reject malformed JSON payloads and invalid actions instead of silently treating unknown input as shutdown

**Regression coverage added:**

- added `tests/test_request_hardening.py` to lock down bounded query parsing, service log tail clamping, and correct network URL reporting
- updated `tests/test_csrf.py` to cover same-origin loopback behavior and block different-port localhost origins
- extended `tests/test_blueprint_system.py` with PBKDF2 storage, legacy-hash upgrade, remote auth-check, remote mutation, malformed JSON, and invalid power-action coverage
- ran `python -m pytest -q` (`928 passed`) and kept the earlier `npm run build` success as the frontend/build verification baseline for this pass

## Files With High Handoff Value

If another agent needs fast context, start here:

- `web/app.py`
- `web/templates/index.html`
- `web/templates/workspace_page.html`
- `web/templates/index_partials/js/_app_core_shell.js`
- `web/templates/index_partials/js/_app_init_runtime.js`
- `web/templates/index_partials/js/_app_media_maps_sync.js`
- `web/templates/index_partials/js/_app_services_ai.js`
- `web/templates/index_partials/js/_app_workspaces.js`
- `web/templates/index_partials/js/preparedness/_prep_people_comms.js`
- `web/templates/index_partials/js/preparedness/_prep_inventory_flows.js`
- `web/static/css/premium/90_theme_consistency.css` ← pass 14: shared premium shell/home/settings polish
- `web/templates/index_partials/_tab_services.html` ← pass 14: home hero/resume/loading/brief copy refinement
- `web/templates/index_partials/_tab_settings.html` ← pass 14: system/memory/model copy refinement
- `web/templates/index_partials/_tab_interoperability.html` ← pass 10: tablist/tab/tabpanel semantics, focus-visible, routes
- `web/templates/index_partials/_tab_training_knowledge.html` ← pass 10: tablist/tab/tabpanel semantics, modal dialog, routes
- `web/templates/index_partials/_tab_agriculture.html` ← pass 16: premium command deck, tab semantics, calmer empty states
- `web/templates/index_partials/_tab_daily_living.html` ← pass 16: premium command deck, tab semantics, calmer household workflow copy
- `web/templates/index_partials/_tab_group_ops.html` ← pass 17: premium command deck, tab semantics, calmer operational empty states
- `web/templates/index_partials/_tab_disaster_modules.html` ← pass 17: premium command deck, tab semantics, calmer readiness/response copy
- `web/templates/index_partials/_tab_medical_phase2.html` ← pass 18: premium command deck, accessible panel switching, calmer continuity-care states
- `web/templates/index_partials/_tab_movement_ops.html` ← pass 18: premium command deck, accessible panel switching, calmer route-planning states
- `web/templates/index_partials/_tab_security_opsec.html` ← pass 19: premium command deck, accessible panel switching, calmer protection/CBRN states
- `web/templates/index_partials/_tab_tactical_comms.html` ← pass 19: premium command deck, accessible panel switching, calmer comms readiness states
- `web/static/css/app/30_secondary_workspaces.css`
- `web/viptrack/index.html`
- `web/nukemap/index.html`
- `web/nukemap/css/styles.css`
- `web/templates/index_partials/_tab_nukemap.html`
- `web/templates/index_partials/_utility_overlays.html`
- `web/templates/index_partials/_shell.html`
- `tests/test_core.py`
- `tests/test_runtime_asset.py`
- `tests/ui/shell-workflows.spec.mjs`

## Remaining Audit Opportunities

The repo is green after this pass, but the next worthwhile audit areas are:

- JS-generated controls outside `VIPTrack`/`NukeMap` that may still need stronger semantics once rendered
- older embedded-tool surfaces that may still have accessibility debt not covered by the current browser suite
- dense tool focus order inside large control panes like `NukeMap` if we want to further streamline keyboard travel, even though the toggle switches now expose their own keyboard semantics
- remaining older preparedness workspaces that still use the pre-command-deck header pattern, especially if we want the full preparedness surface area to feel equally premium
- ~~route-specific browser coverage for workspaces like `interoperability` and `training-knowledge`~~ — done in pass 10 (routes added, 3 Playwright tests added)
- route-specific browser coverage for the newly polished preparedness workspaces like `medical_phase2`, `movement_ops`, `security_opsec`, and `tactical_comms`, since the visual suite is still green without directly exercising those routes yet
- additional runtime-generated image surfaces in specialty/preparedness flows if we want to push the same alt/dimension audit beyond media, chat, and map export
- any additional shared-state restoration bugs in long-lived iframe workspaces

## Repo State Notes

There were unrelated pre-existing untracked files in the repo during this work, including:

- `ROADMAP-COMPLETED.md`
- `banner.png`
- `favicon.ico`
- `file`
- `icon.png`
- `icon.svg`
- `icons/`

Those were not reverted as part of this pass.
