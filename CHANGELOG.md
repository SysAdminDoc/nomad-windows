# Changelog

All notable changes to project-nomad-desktop will be documented in this file.

## [Unreleased]

- **V8-06 — `tests/test_blueprint_benchmark.py` smoke suite (20 tests, 7 routes).** Seventh V8-06 close this session. `web/blueprints/benchmark.py` (538 LOC) — system health benchmarks (CPU/memory/disk/AI/network). Hermetic mocking for /run (20s+ in real mode) and /ai-inference (depends on ollama); real disk I/O exercised on /storage (32MB write+read on the test host). Verifies: /status state passthrough across idle/running/complete, /run 409 concurrent-run guard + daemon-thread spawn, /history newest-first ordering, /ai-inference 400 guard + mocked happy-path with `benchmark_results` row insert + 500 envelope on ollama failure (no exception detail leaked), /results type filter + limit clamp at 500, /storage real I/O round-trip, /network IP validation rejecting loopback/multicast/non-IP + lock-held 409. Pinned a **contract surprise**: the /network default peer is `127.0.0.1` but the validator rejects loopback, so the default is NEVER actually used (test documents the current behavior). 20/20 green first try.

- **fix: brief.py weather + tasks sections — schema-aligned columns end silent failure.** Closes the 2 silent-failure findings flagged in the V8-06 coverage commit. Both sections were never working in production. **Tasks section** queried `title` / `due_at` / `completed_at` against the `scheduled_tasks` schema (which has `name` / `next_due` / `last_completed`), raising `sqlite3.OperationalError` swallowed by the per-section try/except — tasks were absent from every brief output. New query uses canonical columns + filters by `last_completed >= today` and `next_due <= today` for "due/overdue" semantics. **Weather section** read `temp_c` / `humidity` / `pressure` / `conditions` (none in schema) and silently emitted all-None data; new code reads `temp_f` and synthesizes `temp_c` via F→C conversion, surfaces `pressure_hpa` as `pressure`, joins `clouds` + `precip` for a `conditions` summary, and exposes `wind_dir` / `wind_speed` / `visibility`. Both sections emit BOTH legacy aliases (title, due_at, priority, temp_c) AND canonical names (name, next_due, category, temp_f) so renderers built against either era keep working. 22/22 pytest green (5 net new positive-coverage tests replace the pinned-broken test).

- **V8-06 — `tests/test_blueprint_brief.py` smoke suite (18 tests, 2 routes + 6 sections).** Sixth V8-06 close this session. `web/blueprints/brief.py` (335 LOC, Daily Operations Brief compiler) — both routes exercised plus each composition section. **Two real schema mismatches surfaced** (pinned as findings, not fixed): (1) weather section reads `temp_c`/`humidity`/`pressure`/`conditions` from `weather_log` but schema has `temp_f`/`pressure_hpa` without those fields — section appears but all data fields are empty; (2) tasks section queries `SELECT id, title, priority, due_at FROM scheduled_tasks WHERE completed_at IS NULL` but schema has `name`/`next_due`/`last_completed` — query raises `sqlite3.OperationalError`, caught by per-section try/except, section silently absent from every brief output in production. Test `test_tasks_section_absent_when_query_schema_mismatch` pins current broken behavior so a future schema-fix updates the test. Other sections (proximity Haversine filter with 4 coord scenarios, inventory expiring/low-stock filters, family GROUP BY status, emergency banner with case-insensitive truthy parsing, envelope) all pass clean. 18/18 green.

- **V8-06 — `tests/test_blueprint_kiwix.py` smoke suite (21 tests, 7 routes).** Fifth V8-06 close this session. `web/blueprints/kiwix.py` (137 LOC) — all 7 endpoints now exercised via hermetic monkeypatch (no kiwix binary, network, or filesystem side-effects). Covers: ZIM listing (install short-circuit), catalog passthrough, download-zim (SSRF guard across 4 attack vectors: localhost / private IP / non-http scheme / `.local` mDNS suffix; happy-path thread kickoff; running-kiwix restart path via stop+start call counts), progress filter (prefix strip + cross-prefix isolation), delete-zim (400/500/200 guards), check-updates (prefix-match logic pinned against a seeded newer-dated ZIM + no-op cases), wikipedia-options (tier flattening + empty-catalog fallback). 21/21 green.

- **V8-06 — `tests/test_blueprint_land_assessment.py` smoke suite (30 tests, 6 resource classes).** Fourth V8-06 close this session. `web/blueprints/land_assessment.py` (465 LOC, 21 routes) had zero prior tests. Covers: properties CRUD + status filter, assessments (+23-criterion seed with idempotency check), weighted-score calculator (3 hand-computed cases pin the formula — empty returns zeros, (8×2+6×1)/(10×3)×10 = 7.33 / 73.3%, and all-max rounds to exactly 10.0/100%), property features, development plans, BOL comparison aggregator (seeded two-property scenario verifies per-property category_scores + features_count + plans_count + total_dev_cost), summary dashboard (delta verification), criteria-defaults reference. 30/30 green first try.

- **fix: specialized_modules API hardening** — consolidated fix for the 4 findings flagged during the V8-06 coverage pass earlier this session. `POST /fitness` now requires `person` (400 on missing/whitespace — matches every sibling resource; fitness was the lone gap). `POST /fitness` now accepts frontend field-name synonyms and maps them to canonical DB columns (`workout_type→exercise_type`, `duration→duration_min`, `distance→distance_km`, `calories→calories_burned`, `heart_rate→heart_rate_avg`, `exertion→perceived_exertion`; canonical wins if both present). New `GET /fitness/weekly?person=<X>` native route emitting the `{workouts, total_duration, total_calories, total_distance, avg_exertion, person, week_start}` shape that the frontend template's stat cards consume. New `GET /drones/<int:did>/flights` nested alias route that wraps the existing `/flights?drone_id=<id>` filter — template constructed the nested path directly, so the per-drone flight listing was a latent 404. 7 new test assertions verifying each fix end-to-end. 45/45 specialized_modules pytest green (was 38 + 7).

- **V8-06 — `tests/test_blueprint_disaster_modules.py` smoke suite (38 tests, 9 resources).** Third V8-06 coverage close in the same session. `web/blueprints/disaster_modules.py` (898 LOC, 35+ routes) had zero prior tests; now exercises happy-path CRUD for every resource plus specialty endpoints: disaster plans (+reference with all 10 canonical types), disaster checklists (+seed idempotency + auto-pct + auto-status-complete), energy systems (+by_type/by_condition summary aggregator), construction projects (+materials drill-down with completion_pct), building materials (+low-stock trigger filter), fortifications (+assessment aggregator with condition-score rounding verified against a seeded 3-row mix), heating calculator (+insulation-rating monotonicity + delta_t clamp + 400 guard), sandbag calculator (100x3 wall = 960 bags / 6 courses / 38400 lbs verified exactly), disaster summary dashboard shape + aggregates. 38/38 pytest green first try.

- **V8-06 — `tests/test_blueprint_specialized_modules.py` smoke suite (38 tests, 14 resources).** Closes the test-coverage gap flagged during this session's H-17 template migration (commit `1badcf3` noted that no pytest suite existed for `web/blueprints/specialized_modules.py`, a 1,794-line blueprint with 60+ routes). Suite mirrors `tests/test_blueprint_agriculture.py` pattern: one class per resource, happy-path CRUD + 400/404 guards. Resources covered: supply caches (+JSON array round-trip) / pets (+food-status tier classifier) / youth programs / end-of-life plans / procurement (+budget-summary aggregator) / intel / fabrication / badges (+seed) / awards (+leaderboard with cross-person ranking verification) / calendar events (+upcoming) / legal docs (+expiring-soon) / drones / flight logs (+drone_id filter, +stats aggregator shape) / fitness (+stats) / content packs. **Findings uncovered but not fixed this commit (deferred to a future hardening pass)**: `POST /fitness` accepts empty payload without the 400 every sibling enforces; `/flights/stats` returns a LIST (inconsistent with `/procurement/budget-summary` dict shape); frontend template calls `/drones/<id>/flights` nested route but backend only exposes `/flights?drone_id=<id>` query-param route (wiring gap — per-drone flight listing in UI would 404); frontend sends `workout_type`/`calories`/`weight_lbs` but DB columns are `exercise_type`/`calories_burned`/(no `weight_lbs` column applied on insert) so fields silently drop. 38/38 pytest green.

- **V8-04 FULLY CLOSED / H-17 FULLY CLOSED — innerHTML migration: `_tab_agriculture.html` (34 sites) + `_tab_daily_living.html` (37 sites) + `_tab_specialized_modules.html` (44 sites).** Final three H-17 tabs migrated in three atomic commits. **H-17 now 8 of 8 tabs done.** **V8-04 now 24/24 marked Done.** Cross-family L3 audit via `codex-direct.sh` (gpt-5.4) on this closing 3-tab batch returned zero findings P0/P1/P2 across all 6 dimensions.
  - `_tab_agriculture.html` (commit `2d753c5`) — 34 → 0 raw `innerHTML =`. Food-forest guilds + layer tables + yield timeline + soil projects (+pH/N/P/K delta block) + perennials (+dueTag helpers) + livestock breeding (+due-date table) + feed (+summary cards) + homestead systems (+gauge dashboard) + aquaponics + recycling (+flow visualization). Dynamic colors clamped via `--ag-health-tone` / `--ag-soil-tone` / `--ag-gauge-tone,-w` / `--ag-maint-tone` / `--ag-rec-tone` / `--ag-flow-tone`. Every onclick numeric-ID payload hardened with `Number(x)||0`. 8/8 pytest `test_blueprint_agriculture` + vitest 63/63.
  - `_tab_daily_living.html` (commit `f8f41bc`) — 37 → 0 raw `innerHTML =`. Schedules (+stats) + templates + chores + clothing (+assessment) + sanitation (+low-stock alert +category projections) + morale (+trends) + sleep (+debt) + watch rotation + performance (+risk summary +work-rest reference) + recipes (+fuel calc) + ingredient row creation. **Shadowing fix**: two local variables named `html` (`dlLoadAssessment` cold-weather accumulator, performance `/risk-summary` inline scope) renamed via per-block fragment composition so they no longer shadow the global tagged template. 12/12 pytest `test_blueprint_daily_living` + vitest 63/63.
  - `_tab_specialized_modules.html` (commit `1badcf3`) — 44 → 0 raw `innerHTML =`. Supply caches (+summary) + procurement (+budget total) + pets + youth programs + end-of-life plans + intelligence reports (+summary with dynamic by_type cards) + fabrication + badge grid (+award dropdown repop) + awards + leaderboard + calendar events (+upcoming 30d) + legal docs (+expiring-soon block) + drones (+flight selector repop) + flight logs + fitness workouts (+weekly stats). Dynamic colors clamped via `--sm-proc-w,-tone` / `--sm-rem-tone` / `--sm-food-bg,-fg` / `--sm-youth-bg,-fg` / `--sm-eol-bg,-fg` / `--sm-urg-tone`. No dedicated pytest suite for this blueprint (`web/blueprints/specialized_modules.py`) — flagged for V8-06 follow-up. vitest 63/63 + esbuild clean.
  - **Aggregate H-17 total (across both 2026-04-24 sessions, 8 commits)**: ~260 innerHTML assignments migrated from raw string-concatenation or untagged template-literal patterns to the `safeSetHTML + html\`\`` escape-by-default contract. Numerous real XSS holes closed where DB-sourced strings (`${x.name}`, `${x.description}`, `${x.notes}`, free-text action logs, medication/equipment/animal/vehicle names) were previously raw-interpolated without any `esc()` wrapper. Session 1 (2026-04-24 AM): land_assessment 25 + disaster_modules 28. Session 2 (PM): medical_phase2 30 + security_opsec 33 + group_ops 33. Session 3 (late PM): agriculture 34 + daily_living 37 + specialized_modules 44. V8 roadmap advances: 18/24 → **19/24 Done**.

- **V8-04 / H-17 — innerHTML migration: `_tab_medical_phase2.html` (30 sites) + `_tab_security_opsec.html` (33 sites) + `_tab_group_ops.html` (33 sites).** Three more H-17 tabs migrated in three atomic commits (H-17 progress: **5 of 8 tabs done**). All three sit under the V8-04 "innerHTML audit" security tier. Cross-family L3 audit via `codex-direct.sh` (gpt-5.4) returned **zero findings P0/P1/P2** on the aggregate change.
  - `_tab_medical_phase2.html` (commit `26b3554`) — 30 → 0 raw `innerHTML =`. All 8 map-and-join rendered lists (pregnancies / dental / chronic / chronic-alerts / vaccinations / vax-due / mental-health / vet) migrated; 4 direct-template-literal sites (MH trends, IV calc, burns calc, APGAR calc) migrated. `mpDeleteButton` and `mpEmpty` wrapped in `trustedHTML()` when embedded. APGAR score color indicator hardened to CSS custom-property pattern (`--mp-apgar-tone`). Parkland-formula 8h/16h fragment wrapped in `trustedHTML()` to avoid double-escape of pre-built numeric fragment. The `esc()` helper retained for raw-string helpers but the header comment updated to reflect the new contract (`html\`\`` handles interpolations). Tests: 50/50 pytest `test_blueprint_medical_phase2`, vitest 63/63.
  - `_tab_security_opsec.html` — 33 → 0 raw `innerHTML =`. **Closes multiple real XSS holes** — before this commit `${c.name}` (compartments), `${t.name}`/`${t.mitigation}` (threats), `${s.source}`/`${s.mitigation}` (signatures), `${op.name}`/`${op.route}` (observation posts/night ops), `${e.description}` (op log), `${i.name}`/`${i.category}` (CBRN/EMP), `${cl.name}`/`${item.text}` (checklists), `${d.name}`/`${d.description}` (duress), `${p.name}`/`${p.steps}` (procedures), and `${g.title}`/`${g.description}` (signature guide) were all raw-interpolated from DB-sourced strings without any `esc()` pass. All 33 migration sites now escape by default via `html\`\``. `classificationBadge` + `categoryBadge` migrated to `html\`\``. Dynamic color interpolations (threats risk score, checklist %, EMP coverage, CBRN condition) migrated to CSS custom-property pattern (`--so-risk-tone`, `--so-score-tone`, `--so-cov-tone`, `--so-bar-w`). All numeric-ID onclick handlers hardened with `Number(x)||0`. Tests: 25/25 pytest across `test_blueprint_security` + `test_security_v2`, vitest 63/63.
  - `_tab_group_ops.html` — 33 → 0 raw `innerHTML =`. **Closes several real XSS holes**: `${p.name}`/`${p.leader}`/`${p.description}` (pods), `${m.name}`/`${m.role}` (members), `${r.title}`/`${r.assigned_to}` (roles/chain), `${s.title}`/`${s.content}` (SOPs), `${d.assignee}`/`${d.role}` (duty), `${d.title}`/`${d.description}`/`${d.filed_by}` (disputes), `${v.question}`/`${o}` (vote options), `${f.incident_name}` (ICS), `${t.name}`/`${t.leader}`/`${t.members}` (CERT), `${a.location}`/`${a.structure_type}`/`${a.assessed_by}` (damage), `${s.name}`/`${s.location}`/`${s.contact}` (shelters), `${w.title}`/`${w.issued_by}`/`${w.message}` (warnings) all raw-interpolated without `esc()`. **Shadowing fix**: `goLoadVotes` had a local variable named `html` that shadowed the global tagged template — renamed to `out` + `body`. **Vote option onclick hardened**: old pattern `onclick="goCastVote(${v.id},'${o.replace(/'/g,"\\\\'")}')"` (attribute-injection-vulnerable) replaced with `onclick='goCastVote(${Number(v.id)||0}, ${JSON.stringify(o)})'` so `html\`\``-escaped `&quot;` decodes back to `"` inside the single-quoted attribute and yields valid JS. Dynamic colors migrated to CSS custom-property pattern across SOP tone, severity badge, CERT specialty badge, shelter capacity bar, ICS badge, and vote bar. Tests: 10/10 pytest `test_blueprint_group_ops`, vitest 63/63.
  - H-17 progress: **5 of 8 tabs done**. Remaining smallest-first: agriculture (34), daily_living (37), specialized_modules (44).

- **V8-04 / H-17 — innerHTML migration: `_tab_land_assessment.html` (25 sites) + `_tab_disaster_modules.html` (28 sites).** Two of the eight remaining H-17 tabs migrated to the H-05 pilot pattern (`safeSetHTML(el, html\`...\`)`) in two atomic commits:
  - `_tab_land_assessment.html` (commit `0e1fb00`) — 25 → 0 raw `innerHTML =`. 18 static `laEmpty(...)` empty/loading sites and 7 dynamic interpolations now wrapped via `safeSetHTML`. Dynamic loops migrated to `html\`\`` per row with auto-escape via `escapeHtml()`. Pre-built helpers (`laDeleteButton`, score/score-detail markup, category-row clusters) wrapped in `trustedHTML()` to opt out of double-encoding.
  - `_tab_disaster_modules.html` (commit `35f7b2f`) — 28 → 0 raw `innerHTML =`. **Closes real XSS holes**: 16 of the 28 sites previously did raw `${p.name}` / `${e.name}` / `${m.name}` / `${f.name}` / `${c.item_text}` interpolation of DB-sourced strings WITHOUT any `esc()` wrapper. Migration to `html\`\`` auto-escapes every interpolation. Numeric IDs hardened with `Number(x)||0` in onclick handlers and DOM `name` attributes. Tables with map-built tbody rows split into `html\`\`` per row + raw string concat for the `<table>` wrapper to preserve byte-for-byte render output.
  - vitest 63/63 green after each commit.
  - H-17 progress: **2 of 8 tabs done**. Remaining smallest-first: medical_phase2 (32), security_opsec (33), group_ops (33), agriculture (34), daily_living (37), specialized_modules (44).
- **V8-06 — `tests/test_blueprint_roadmap_features.py` smoke suite (commit `89d1818`, 25 tests, 6 resource families).** Closes the largest remaining test gap. `web/blueprints/roadmap_features.py` is 1671 LOC with 75 routes and previously had **zero** dedicated tests. New suite covers Recipes (full CRUD + ingredients + 404), Batteries (list/create/update/delete), Warranties (lifecycle), AI Skills (CRUD), URL Monitors (create/delete), Personal Feeds (create + items + delete) plus the standard 400/404 error paths. Uses the existing per-function `client` fixture (shared in-memory SQLite, isolated per test). Adjacent-suite smoke (132 tests across roadmap_features + agriculture + core + inventory + lazy_blueprints + broadcast_regressions + db_integration): 132/132 green.

- **H-14 continuation — `create_app()` final thinning (663 → 56 lines).** The v7.65.0 H-14 pass extracted pages + background threads + SSE routes; this follow-up pass extracts the remaining self-contained concerns so the factory is a thin orchestrator:
  - `web/aggregation.py` (NEW, ~440 L) — `SURVIVAL_NEEDS` constant + seven cross-module aggregation routes (`/api/needs`, `/api/needs/<need_id>`, `/api/guides/context`, `/api/planner/calculate`, `/api/readiness-score`, `/api/data-summary`, `/api/search/all`). Shared TTL cache now comes from the module-level `web.state.cached_get` / `cached_set` helpers (the old `_cached` / `_set_cache` closure aliases are gone).
  - `web/bundled_assets.py` (NEW, ~100 L) — NukeMap + VIPTrack static serving with a shared `_resolve_bundle_dir` (frozen / sibling / cwd / external-repo fallback) and `_serve_within` (commonpath-based path-traversal guard that also treats Windows different-drive `ValueError` as forbidden, matching prior behavior exactly).
  - `web/root_routes.py` (NEW, ~60 L) — `/sw.js`, `/favicon.ico`, `/api/offline/snapshot`, `/api/offline/changes-since`. **Fixes a latent crash**: `/favicon.ico` used `Response(...)` but `Response` was never imported at `web/app.py:9`, so the route would have 500'd on first hit. The new module imports `Response` explicitly from `flask`.
  - `web/app.py::create_app()` — now 56 lines; the whole file is 148 lines (from 754). `app.url_map` rule count unchanged at 1866.
  - `tests/test_core.py` — the three `app_text`-based regression pins (`from web.utils import`, `_require_json_body(request)`, `_safe_json_list(cl['items'], [])`) now read `web/aggregation.py` instead of `web/app.py` — they follow the code to its new home so the pins still enforce the same shared-helpers contract.
  - Targeted suites (`test_core`, `test_lazy_blueprints`, `test_data_summary`, `test_broadcast_regressions`, `test_emergency`): 92/92 green. Full pytest sweep: 1634/1634 green. vitest: 63/63 green.
- **`fix: emergency._broadcast imports broadcast_event from web.state`** (commit `a35f901`) — completes the v7.65.0 emergency-mode SSE claim. `web/blueprints/emergency.py` was still doing `from web.app import _broadcast_event` while `family.py` was already switched; this brings the two modules to parity. Covered by the existing `tests/test_broadcast_regressions.py` (4/4) and `tests/test_emergency.py` (9/9).

## [v7.65.0] — Factory-Loop Run: create_app() thinning + lazy blueprints + SSE broadcast fix (2026-04-24)

Three-iteration autonomous factory-loop run. Three long-pending architecture + correctness items close: `create_app()` drops from 1243 to 663 lines (H-14), the two heaviest blueprints now lazy-register on first hit (H-09 / V8-11, ~40 ms / 8% boot saving), and the silently-broken SSE broadcast path for Emergency mode + Family check-in is fixed end-to-end with regression tests. 11 new test assertions land across the run (7 lazy-blueprint + 4 broadcast).

### `_broadcast` SSE silent-failure fix + regression suite (factory-loop iter 3, 2026-04-24)

Fixes a long-standing latent bug in `web/blueprints/emergency.py::_broadcast` and `web/blueprints/family.py::_broadcast`. Both modules previously did:

```python
from web.app import _broadcast_event
_broadcast_event(event_type, payload)
```

`_broadcast_event` was never exported from `web.app` — the canonical SSE publisher is `web.state.broadcast_event` (no leading underscore). A broad `except Exception` in each helper silently swallowed the `ImportError` on every call, so **Emergency-mode state changes and Family check-in updates never reached any connected client**. The fix imports the real symbol directly. Behavior surface this unblocks: live sync of emergency activation/deactivation, bug-out decisions, casualty updates, family-member status changes, and contact-attempt logs across every open tab without the user refreshing.

- `web/blueprints/emergency.py`, `web/blueprints/family.py` — import switched to `from web.state import broadcast_event`; in-source comment documents the prior silent break so the next reviewer doesn't revert it.
- `tests/test_broadcast_regressions.py` (NEW, 4 tests) — registers an SSE queue via `_sse_clients`, triggers `emergency._broadcast` and `family._broadcast`, and asserts the message actually lands on the queue. Also pins: event-type control-char injection is sanitized (no `\nX-Smuggle:` header-split), and neither module's source reintroduces the dead `from web.app import _broadcast_event` line.

H-17 (V8-04 remaining 8 tab templates to `safeSetHTML(el, html\`\`)`) remains open and tracked for a dedicated future iteration — these are consistency/discoverability wins, not security fixes (each tab's existing `esc()` helper already blocks the XSS surface), and the migration is large enough to merit its own focused pass.

### H-09 / V8-11 — Lazy blueprint registration for cold blueprints (factory-loop iter 2, 2026-04-24)

Long-open architecture item. Two blueprints (`platform_security` at ~21 ms and `hunting_foraging` at ~14 ms per `python -X importtime`) dominate boot but neither is on the dashboard landing path. They are now lazy-loaded on the first request to their URL prefix, shaving a measured **~40 ms (8%)** off `create_app()` — median boot drops from ~514 ms to ~474 ms across three subprocess samples.

- **`web/lazy_blueprints.py`** (NEW) — `LazyBlueprintDispatcher` is WSGI middleware that peeks at `PATH_INFO`, matches against a `DEFERRED_BLUEPRINTS` prefix map, lazily imports and registers the matching blueprint, then forwards the request to Flask's original `wsgi_app`. By the time Flask matches the URL, the routes exist, so the cold-hit request returns the same response as a warmed path. Flask's post-first-request registration guard (`_got_first_request`) is briefly flipped during `register_blueprint` and restored immediately.
- **Concurrency safety** — the initial implementation had a race where a third thread arriving between a winner's `pending.pop()` and its `register_blueprint()` would observe an empty pending map, skip the load path, and forward to a Flask URL map that hadn't finished updating — a 404 on what should have been a 200. Fix: the prefix stays in `_pending` until `register_blueprint` has fully returned; only then is the entry deleted. All three state transitions (get, register, delete) happen under the same `threading.Lock()`, giving a clean happens-before to late-arriving threads. Confirmed via an 8-way barrier-synchronized concurrent-hit test (`tests/test_lazy_blueprints.py::test_concurrent_first_hits_register_exactly_once`).
- **`tests/test_lazy_blueprints.py`** (NEW, 7 tests) — pins: deferred modules are not imported during `create_app()`; first hit to `/api/platform/*` lazy-registers `platform_security_bp`; first hit to `/api/hunting/*` lazy-registers `hunting_foraging_bp`; duplicate registration never occurs; unrelated requests don't trigger a load; 8 concurrent cold hits all return 200 with exactly one registration; prefix match is path-separator bounded so `/api/platformOTHER` doesn't match `/api/platform`.
- **`web/blueprint_registry.py`** — removed eager imports of the two deferred blueprints (replaced with sentinel comments pointing at the lazy registration path).
- **`web/app.py`** — wraps `app.wsgi_app` with `LazyBlueprintDispatcher(app, DEFERRED_BLUEPRINTS)` after eager registration completes.

### H-14 — `create_app()` thinning (factory-loop iter 1, 2026-04-24)

Long-pending V8-09 carry-over. `web/app.py::create_app()` body shrinks from **1243 → 663 lines** (47% reduction) by extracting four self-contained concerns into dedicated modules. No behavior change — every workspace route, i18n endpoint, and SSE route returns identical responses.

- **`web/pages.py`** (NEW, ~430 lines) — owns `WORKSPACE_PAGES` metadata for all 17 tabs, the `_render_workspace_page` cache (V8-10), `get_current_language` / `get_template_i18n_context` / `is_first_run_complete` accessors, the `@app.context_processor` that injects i18n vars, all 19 page routes (including the 8 alias routes like `/briefing` → situation-room), the `/app-runtime.js` endpoint, and the four `/api/i18n/*` endpoints. Per-app caches (`_lang_cache`, `_first_run_cache`, `_page_render_state`) live on `app.config` so test harnesses get isolated state. The page-render-state initializer now uses a module-level lock + `setdefault` to close a TOCTOU where two cold-start request threads could each create their own state dict with separate locks.
- **`web/background.py`** (NEW, ~230 lines) — owns the federation UDP discovery listener, the auto-backup scheduler trio (`_load_auto_backup_config` / `_run_auto_backup` / `_rotate_backups` / `_schedule_auto_backup`), and the SSE stale-client cleanup loop. Each `start_*(app)` is idempotent via module-level guards. `app.config['_schedule_auto_backup']` and `app.config['_sse_cleanup_stop']` are still wired so blueprints and shutdown hooks reach them unchanged.
- **`web/sse_routes.py`** (NEW, ~85 lines) — owns `/api/events/stream` and `/api/events/test`. The per-IP rate-limit ledger (`_sse_connects`) now lives on `app.config` instead of a closure dict so test apps don't share state.
- **`web/app.py`** trimmed accordingly: `_load_bundle_manifest`, the inline language helpers, the workspace-pages dict, the discovery + auto-backup blocks, the SSE event-stream block, and the i18n routes are all gone. Module-level `_get_node_id` import lifted to the file header so the offline snapshot route can still stamp its node identifier.
- Test pin updated: `tests/test_core.py::test_runtime_uses_shared_json_safety_helpers_for_saved_state_and_payloads` now points the `_safe_json_value(data, {})` assertion at `web/background.py` (where the discovery listener lives) instead of `web/app.py`.
- Smoke verification: 29/29 page + i18n routes return 200; vitest 63/63 pass; `tests/test_crud_api.py` 51/51 pass; full pytest suite green (sqlite_master locked race in `test_inventory` / `test_barcode` is a pre-existing intermittent — both pass in isolation).



Final iteration of the 3-pass factory-loop run. Closes three iter 1 audit carry-overs (H-11 AST regression tests for `_start_lock` placement, H-13 `_parse_feed` malformed-input resilience, H-16 db-leak audit classifier refinement), narrows another 9 bare `except Exception` sites in Situation-Room fetch workers (44 → 35; cumulative 64 → 35 across 3 iterations), and upgrades the db-leak audit tool's classifier so it produces a clean report instead of a 34-entry noise list.

### H-11 — AST regression tests for `services.ollama.start()` guard placement

Two new assertions in `tests/test_services_ollama.py` pin the H-01 invariant so a future edit can't silently regress the double-start fix:

- `test_ollama_start_takes_start_lock_before_launch_work` walks every `start_process(...)` call in the function body and asserts each has a `with _start_lock:` ancestor. Any refactor that lifts the launch out of the lock, or opens a new branch that bypasses it, fails the test.
- `test_ollama_start_has_short_circuit_guard_first_in_lock` finds the first `with _start_lock:` block and asserts its first body statement is an `If` whose test calls both `is_running()` AND `check_port()`. Prevents an edit that reorders launch work above the guard (silent double-start even while holding the lock).

Full ollama test count: 5 → 7.

### H-13 — `_parse_feed` malformed-input coverage

New `TestParseFeedResilience` class in `tests/test_blueprint_situation_room.py` (5 assertions). The fetch worker chain (`_fetch_rss_feeds` / `_fetch_disease_outbreaks` / `_fetch_cyber_threats` / `_fetch_arxiv_papers`) all call `_parse_feed(resp.text, ...)`. A single raise inside `_parse_feed` would tear down an entire `ThreadPoolExecutor` batch via the `as_completed` path. Tests pin that the parser returns `[]` for every malformed shape instead of raising:

- DOCTYPE declaration rejected (billion-laughs vector).
- Bare ENTITY declaration rejected.
- Empty string → `[]` via the inner `ET.ParseError` catch.
- Non-XML garbage (HTML 429 page, JSON, truncated XML) all return `[]`.
- RSS with some items missing `<title>` silently drops them (title is the UPSERT key).

### H-16 — db-leak audit classifier refinement (34 → 5 findings)

Iter 2 delivered `tools/audit_db_sessions.py` + initial report with 34 findings. Iter 3 investigation showed ~26 of those were false positives from a too-strict classifier:

1. **Next-sibling Try pattern** — `db = get_db()` followed by a `try: ... finally: db.close()` block as the next sibling statement. Classifier now walks the ancestor chain to find the enclosing list that contains the Assign, reads the next element, checks if it's a `Try` whose `finalbody` closes the target.
2. **Helper-wrapped close** — `_close_db_safely(db, 'context')` and similar wrappers. Classifier recognises any call whose function name contains `close` / `release` / `dispose` and takes the target as its first positional argument.
3. **Cross-block close** — `try: db = get_db() except: ... ; try: db.execute() finally: db.close()`. Classifier walks the enclosing function body forward from the assign and checks if the target is closed anywhere downstream. Deliberately loose (a cleanup-skipping branch could still leak) but prioritises precision on real leaks.

Post-refinement count: **5 findings, all documented as known-safe patterns** (`db.py::_pool_acquire` by-design, `tests/test_db_safety.py::test_get_db_*` exercising cleanup-on-failure, `tests/conftest.py::db` keeper fixture). Report now has a "Known-safe patterns" section so future regressions show up as a delta against 5, not 34. H-16 conversion pass effectively became a classifier bug fix — the codebase was already cleaner than the initial report suggested.

### H-03 (batch 3) — 9 more bare-except sites narrowed (44 → 35)

Third and final narrowing batch in `web/blueprints/situation_room.py` fetch workers. Each block typed per its real raise surface:

- `_fetch_internet_outages` Cloudflare Radar + IODA fallback: `(requests.RequestException, ValueError, KeyError, AttributeError)` — `.get()[:30]` navigation adds AttributeError for unexpected payload shapes.
- `_fetch_disease_outbreaks` WHO RSS: `(requests.RequestException, ET.ParseError, ValueError)` — adds ET.ParseError because `_parse_feed` internally catches it but a caller-level network error could still surface.
- `_fetch_radiation` Safecast: `(requests.RequestException, ValueError, KeyError)`.
- `_fetch_gdelt_trending`: `(requests.RequestException, ValueError, KeyError)`.
- `_fetch_ucdp_conflicts`: `(requests.RequestException, ValueError, KeyError)`.
- `_fetch_cyber_threats` CISA KEV: adds AttributeError for `.get()` chain on missing payload shapes.
- `_fetch_cyber_threats` CISA advisories RSS: adds ET.ParseError + KeyError for `_parse_feed` + iteration chain.
- `_fetch_yield_curve` US Treasury: adds AttributeError for the `payload.get('data', [])` chain.

Cumulative iter 1 + iter 2 + iter 3: **29 sites narrowed, 64 → 35 total**. The remaining 35 are split between `finally: resp.close()` cleanup paths (intentionally broad) and non-fetch-worker code paths that would need different exception sets per context. **H-03 marked Substantially Done** for the fetch-worker surface — further narrowing is low-value vs. review cost.

### Deferred with rationale

- **H-12 `trustedHTML` → `markTrusted` rename** — pure cosmetic; parked at P3. Re-evaluate if a second caller appears outside the test suite.
- **H-17 V8-04 remaining 8 tab templates** — most already use a per-tab `esc()` helper that mitigates the XSS surface. The migration is a consistency / grep-discoverability improvement, not a security fix. Deferred past iter 3 for a dedicated batch iteration.
- **H-08 / H-09 / H-14 create_app() thinning + V8-11 lazy blueprints** — the shared closures (`_render_workspace_page`, `_discovery_listener_started` module lock, `_safe_json_value`) in `web/app.py` make naive extraction risky. Warrants a dedicated iteration with close build/test monitoring.

### Test/build gate summary

- pytest adjacent suite (7 files, 152 assertions) — green in 49 s.
- vitest — 63/63 assertions green.
- esbuild — bundle + CSS built clean.
- `create_app()` smoke — 72 blueprints register without error.
- `tools/audit_db_sessions.py` — 5 findings, deterministic, all documented as known-safe.

### Factory-loop final state

- **V8 roadmap**: 16/24 Done, 1 Partial (V8-09), 6 Open, 1 Blocked (V8-21 needs Apple Developer credentials).
- **Hardening ledger**: 9 of 17 H-items Done (H-01 / H-02 / H-04 / H-05 / H-07 / H-11 / H-13 / H-15 / H-16), 2 Substantially Done (H-03, H-06), 3 Deferred with rationale (H-10 / H-12 / H-17), 3 architectural follow-ups (H-08 / H-09 / H-14).
- **Tools added**: `tools/audit_db_sessions.py` + `docs/db-leak-audit.md`.
- **Tests added across 3 iterations**: 7 in `tests/test_services_ollama.py` (NEW file) + 5 `TestParseFeedResilience` + 15 vitest assertions for the V8-04 primitives. **27 new test assertions** total.
- **Security surface hardened**: ollama double-start guard (H-01) + chat() 404 FD leak (H-07) + 29 bare-except sites narrowed (H-03) + `_parse_feed` malformed-input proven resilient (H-13) + `html\`\`` / `trustedHTML` / `safeSetHTML` primitives with prototype-pollution guard rolled out the escape-by-default pattern (H-05) + AST regression tests pin both `_start_lock` placement and `start_process` atomicity (H-02, H-11).

## [v7.63.0] — Factory-Loop Iteration 2: DB-Leak Audit Tool + Bare-Except Batch 2 (2026-04-24)

Second iteration of the factory-loop run. Delivers a reusable AST-driven audit tool for `get_db()` leak sites (groundwork for the iter 3 conversion pass), narrows another 11 bare `except Exception` sites in Situation-Room fetch workers (55 → 44 total), and reconciles V8-09's status now that `web/middleware.py` + `web/blueprint_registry.py` have landed.

### H-06 / H-15 — `get_db()` try/finally audit tool

New `tools/audit_db_sessions.py` — zero-dependency stdlib-only AST walker. For every `get_db()` call it classifies:
- **assigned-but-not-closed** — `db = get_db()` without a `try/finally` that closes `db`. Highest-priority leak shape; the caller holds a pooled connection for its entire lifetime.
- **bare-call** — `get_db().execute(...)` as an inline expression. Connection abandoned after the chained call; the pool reclaims it eventually but transactions may linger.
- **safe** — `with db_session() as db:` or a `try:` whose `finalbody` explicitly calls `<target>.close()`. Not reported.

First report committed as `docs/db-leak-audit.md`: **34 suspect call sites across 14 files**, weighted toward `services/` (21) and `db.py` (5). Severity legend + per-module breakdown included so iter 3 can prioritize the conversion pass.

CLI supports `--fail-on-find` so a future CI step can gate on the count dropping to zero. Runs in < 200 ms against the full tree.

### H-03 continuation — 11 more bare-except sites narrowed (55 → 44)

Second batch of `except Exception` narrowing in `web/blueprints/situation_room.py` fetch workers:
- **`_fetch_market_data` Fear/Greed block** — `(requests.RequestException, ValueError, KeyError, IndexError, TypeError)`.
- **`_fetch_conflict_data` (GDACS)** — `(requests.RequestException, ValueError, KeyError)`.
- **`_fetch_ais_ships` primary + fallback** — primary: full typed set; fallback `marinetraffic` swallow narrowed to `requests.RequestException` only.
- **`_fetch_space_weather`** — four separate `try:` blocks covering NOAA scales / Kp index / solar probabilities / alerts. Each typed per-block based on the real payload navigation path (e.g. Kp uses list indexing so `IndexError`/`TypeError` are added; alerts uses only list shape checks).
- **`_fetch_volcanoes` (Smithsonian GVP)** — `(requests.RequestException, ValueError, KeyError)`.
- **`_fetch_predictions` (Polymarket)** — `(requests.RequestException, ValueError, KeyError)`.
- **`_fetch_fires` (NASA FIRMS CSV)** — `requests.RequestException` only; CSV parsing lives below the try and raises deterministic errors that are currently handled via `if len(lines) < 2: return`.

Iter 1 + Iter 2 cumulative: **20 bare-except sites narrowed (64 → 44)**. Iter 3 target: remaining non-finally sites.

### V8-09 status reconciliation (Partial → Partial with follow-up)

Audit surfaced that `web/middleware.py` (339 L, housing CSRF / rate-limiting / host validation / auth guard / LAN auth / security headers / DB cleanup / `_setup_error_handlers`) and `web/blueprint_registry.py` (237 L, 72-blueprint registry) **already shipped in v7.57.0**. `create_app()` is now 1,243 lines (down from 1,655). The Tier-3 V8-09 row in ROADMAP flipped to **Partial** with an explicit follow-up (**H-14**) that captures the remaining work: extract 50+ inline page routes into `web/pages.py` blueprint + 4 background-thread setup trios (discovery listener, auto-backup scheduler, SSE cleanup, CPU monitor) into `web/background.py`. Target: `create_app()` ≤ 300 lines. Deferred to a dedicated iteration because the shared closures (`_render_workspace_page`, `_get_template_i18n_context`, `_safe_json_value`, `_discovery_listener_started` module lock) make a naive extract risky.

### Roadmap tidy

`ROADMAP.md` updated:
- H-01 / H-02 / H-04 / H-05 / H-07 marked Done v7.62.0.
- H-03 marked **Open (partial)** with the remaining count explicit.
- H-10 marked **Open (partial — pilot H-05 done)** with the remaining 8 tabs listed.
- Three new audit carry-over items appended: **H-11** (AST test for future `_start_lock` regressions), **H-12** (rename `trustedHTML` → `markTrusted`), **H-13** (`_parse_feed` malformed-input test).
- Two V8-09 / H-06 follow-ups: **H-14** (create_app() final thinning) and **H-15** (db-leak audit tool — already delivered this iteration).
- Iteration cadence updated to reflect iter 1 shipped + iter 2 shipping.

### Test/build gate summary

- pytest adjacent suite (7 files, 145 assertions) — green in 49 s.
- vitest — 63/63 assertions green.
- esbuild — bundle + CSS built clean.
- `create_app()` smoke — 72 blueprints register without error.
- `tools/audit_db_sessions.py` — produces identical report on re-run (deterministic).

### Deferred to iteration 3

- **H-09 / V8-11** — lazy blueprint registration (depends on H-14).
- **H-10 remaining** — innerHTML audit of 8 tab templates (batch-migrate using the H-05 pilot pattern).
- **H-14** — the V8-09 final thinning work sketched above.
- **H-11 / H-12 / H-13** — the three carry-over audit items.
- `get_db()` → `db_session()` conversions driven by the `docs/db-leak-audit.md` report.

## [v7.62.0] — Factory-Loop Iteration 1: Hardening + V8-04 Pilot (2026-04-24)

Targeted hardening pass driven by the factory-loop recipe. Closes V8-12 (frontend unit tests — verified vitest + 48 assertions cover the 5 named critical functions), launches the V8-04 innerHTML-audit pilot (3 new escape-safe primitives + migration of `_tab_data_foundation.html`), ships two concurrency fixes in `services/ollama.py`, plugs a `chat()` FD leak, narrows 9 swallowing `except Exception` sites in Situation-Room fetch workers, and pins the existing `services/manager.py::start_process` atomicity invariant with an AST-based regression test.

### H-01 / H-02 — Ollama double-start guard + manager atomicity pin

`services/ollama.py::start()` now serializes concurrent callers on a module-level `_start_lock` and short-circuits when `is_running(SERVICE_ID) and check_port(OLLAMA_PORT)` are both true: it returns the registered PID from the `services` row instead of killing its own port holder and relaunching. Prior behavior on repeat `start()` was the double-start / self-kill cycle. The lock is **released before** the ~30 s port-responsiveness poll so a concurrent `stop()` / `running()` / shutdown handler isn't blocked up to 30 s waiting on launch confirmation. `stop()` deliberately does NOT take `_start_lock` — it delegates to `services.manager.stop_process`, which has its own `_lock`. Taking both would risk a deadlock if shutdown is invoked during startup.

`tests/test_services_ollama.py` (NEW — 5 assertions):
- `test_start_noop_when_already_running` — the short-circuit returns the registered PID and never touches `_kill_port_holder` / `start_process`.
- `test_start_lock_serializes_concurrent_callers` — 5 threads calling `start()` against a simulated 50 ms Popen all receive the same PID, only one launch happens, zero self-kills.
- `test_manager_start_process_check_and_popen_live_in_same_with_lock_block` — AST-based invariant: walks `services.manager.start_process`, finds the `ast.With` node whose context expression is `_lock`, verifies **both** the `<proc>.poll() is None` liveness check AND the `subprocess.Popen(...)` call are descendants of the same lock block. A future refactor that splits them across two lock blocks fails the test.
- `test_chat_stream_closes_on_early_abandonment` / `test_chat_stream_closes_on_full_iteration` — the streaming generator's `finally` releases the underlying `requests.Response` on both explicit `gen.close()` after partial iteration and full stream exhaustion.

### H-07 — `chat()` 404 FD leak fixed

When Ollama returns `404` for a missing model, `chat()` previously raised a `RuntimeError` without closing the response, leaking one socket FD per model-not-found call. Close now runs before the raise in both branches of `raise_for_status()` handling. `_safe_response_payload` also now handles a `None` response defensively.

### H-03 — Situation Room bare-except narrowing (partial, 9 sites)

`web/blueprints/situation_room.py` — narrowed 9 bare `except Exception` sites in fetch workers and helpers (64 → 55 total): `_fetch_with_retry` (dropped redundant `(requests.RequestException, Exception)`), `_safe_response_json`, `_fetch_single_feed`, `_fetch_earthquakes`, `_fetch_weather_alerts`, `_fetch_market_data` (3 inline sites in yahoo indices / yahoo sectors / coingecko / metals outer + 1 DB read inner). New exception set per site is a subset of `(requests.RequestException, ValueError, KeyError, IndexError, TypeError, AttributeError, ET.ParseError, sqlite3.Error)`. A programming bug (NameError, ImportError) now surfaces instead of being swallowed per-fetch. The silent `try: resp.close() except Exception: pass` passes inside `finally` blocks were intentionally kept broad — a socket-shutdown error must not mask a real fetch error. 55 bare-except sites remain; batches 2-3 scheduled for iterations 2-3.

### H-05 — V8-04 innerHTML sanitization pilot

New escape-by-default primitives in `web/templates/index_partials/js/_app_core_shell.js`:
- `html\`…${v}…\`` — tagged template, runs every interpolation through `escapeHtml`.
- `trustedHTML(s)` — sentinel marker so a caller can opt a specific slot out of escaping (e.g. a row string already built from escaped parts). The check uses `Object.prototype.hasOwnProperty.call(v, '__nomadTrustedHTML__')` so a hypothetical `Object.prototype.__nomadTrustedHTML__ = true` pollution attack can't downgrade every interpolation.
- `safeSetHTML(el, str)` — thin wrapper around `el.innerHTML = …` with null-safe coercion; reads explicitly at call sites as the "set innerHTML" action.

Mirrored into `tests/js/utils.js` and covered by 15 new vitest assertions (now 63 total passing), including a prototype-pollution regression that temporarily installs `__nomadTrustedHTML__ = true` on `Object.prototype` and verifies a plain `{}` still escapes instead of short-circuiting.

Pilot migration in `web/templates/index_partials/_tab_data_foundation.html`: all 10 `.innerHTML = template` / `.innerHTML += template` sites in `loadPacks` / `loadThreats` / `loadGaps` / `searchFoods` converted to `safeSetHTML(el, html\`…\`)` with per-row `.map().join('')`. Inline `onclick="dfInstallPack('${p.pack_id}')"` attribute interpolation replaced with a delegated click listener reading `data-pack-action` + `data-pack-id` attributes — closes the attribute-injection hole if `pack_id` ever contained a quote. Numeric CSS custom-property interpolations clamped with `Math.min(Math.max(Number(x) || 0, 0), 100)` as belt-and-braces. Only `dfInstallPack` / `dfUninstallPack` call sites in the repo are inside this tab; no stragglers.

### H-04 — V8-12 frontend unit tests — status reconciliation

Verified the v7.58.0 work already covers every named function in the V8-12 description: `tests/js/utils.test.js` has 48 assertions (now 63 with the new primitives) against `escapeHtml`, `formatBytes`, `timeAgo`, `parseInventoryCommand`, `parseSearchBang`. Row flipped to **Done v7.58.0** in the Tier-4 table. `safeFetch` is exercised indirectly via the Playwright shell-workflow suite.

### Audit + counter-audit

Pre-release code-review pass surfaced 3 HIGH / 10 MED / 7 LOW findings against the iteration 1 diff. HIGH fixes shipped in this version: (1) `chat()` 404 FD leak, (2) `_start_lock` no longer held across the 30 s port poll, (3) Situation-Room narrowing explicitly flagged as partial rather than "done". MED fixes: (4) manager atomicity test rebuilt on AST walking instead of fragile string slicing, (5) prototype-pollution guard added to `html\`\``, (6) grep verified no extra `dfInstallPack` / `dfUninstallPack` call sites. LOW fixes: `_safe_response_payload` narrowed to `(ValueError, TypeError, AttributeError)`, H-04 row reconciled with Done state.

### Test/build gate summary

- pytest adjacent suite (7 files, 145 assertions) — green in 50 s.
- vitest — 63/63 assertions green.
- esbuild — bundle + CSS built clean.
- `create_app()` smoke — 72 blueprints register without error.
- Full pytest suite (1,368+ assertions) has a pre-existing isolation-order flake in `tests/test_garden.py::test_create_plot` unrelated to this change set — the test passes standalone.

## [v7.61.0] — Test Coverage + Roadmap Convergence (2026-04-24)

Five V8 roadmap items closed in a single pass. Two were already shipped and verified during this iteration's audit (`V8-10` template cache, `V8-22` checksum parity); three required real work (`V8-14` allowlist hoist, `V8-16` file-backed DB integration test, `V8-23` seeded test data isolation). All 11 new tests pass green; related blueprint suites unaffected.

### V8-14 — Module-level column allowlists
Hoisted three inline `allowed = {...}` sets from route handlers in `web/blueprints/emergency.py` into module-level `frozenset` constants (`ALLOWED_EVAC_PLAN_FIELDS`, `ALLOWED_EVAC_RALLY_FIELDS`, `ALLOWED_EVAC_ASSIGNMENT_FIELDS`). Same pattern in `web/blueprints/maps.py` (`ALLOWED_WAYPOINT_FIELDS`) and `web/blueprints/media.py` (`ALLOWED_MEDIA_META_FIELDS` + per-type extras exposed via new `_allowed_media_meta_fields(media_type)` helper). Auditable in one place; no more handler-scoped schema truth.

### V8-16 — File-based DB integration test
New `tests/test_db_integration_file.py` spins up a temp directory, points `config` at an on-disk SQLite path, runs `init_db()` + `create_app()`, then asserts:
- The `.db` file is materialized and non-empty after `init_db()`.
- WAL journal mode is applied and persists on the file.
- The `_meta.schema_version` gate is populated.
- Core tables (`settings`, `inventory`, `notes`, `contacts`, `waypoints`) exist and the migrated schema is ≥50 tables wide.
- The root route responds 200 under a file-backed DB.
- The connection pool handles 5 repeat `/api/inventory` requests without 500s (pool reuse smoke).
Fixture restores global `_wal_set` / `_pool_db_path` / `config._config_cache` on teardown so the test does not contaminate sibling tests.

### V8-10 — Template cache (verified in place)
Audit confirmed `_page_render_cache` at `web/app.py:342-372` already memoizes rendered workspace pages keyed by `(tab_id, lang, bundle_js, media_sub, launch_restore, first_run_complete)` with TTL + 200-key prune threshold. Marked Done.

### V8-22 — Auto-update checksum parity (verified in place)
Audit confirmed `.github/workflows/build.yml:220` runs `sha256sum *` over the full release directory (Windows + Linux + macOS + AppImage artifacts) and uploads `SHA256SUMS.txt`. `services.py::api_update_download` fetches that manifest on every self-update attempt, matches by filename, and hard-fails with file deletion on mismatch for all platforms. Marked Done.

### V8-23 — Seeded test data isolation (verified in place)
Audit confirmed `tests/conftest.py` already exposes `seed_upc_entry`, `seed_rag_scope_row`, `assert_upc_seeded`, `assert_rag_scope_seeded`. Tests now declare their data dependencies instead of implicitly relying on `init_db()` seed side-effects. Marked Done.

### Test coverage delta
- `tests/test_allowlists.py` — 5 tests pinning the exact field sets exposed by each blueprint. Guards against silent regression if the hoist is ever reverted, and includes a hostile-key rejection check (SQLi-flavored keys must be dropped).
- `tests/test_db_integration_file.py` — 6 tests covering the file-backed DB lifecycle.

## [v7.60.1] — Deep Audit Hardening Pass

Eight concrete bugs fixed across backend, frontend, services layer, and test harness. No behavior changes; every fix is a correctness or defensive-hardening improvement. 22 new regression tests in `tests/test_audit_hardening.py`.

### Correctness
- **`web.utils.esc()` silently dropped every falsy value** — `esc(0)` returned `''`, losing legitimate zero values from printed inventory counts, medical dosages, RST tone scores. Now only `None` is treated as absent; `0`, `False`, `''`, `[]`, `{}` all round-trip to their string forms.
- **`web.static.js.api.js` empty-body responses crashed `apiFetch`** — a 204 No Content or a 200 with `Content-Length: 0` (from routes that return `'', 200`) threw `SyntaxError` inside `resp.json()` and bubbled up as a generic "Network error" to the user. Now checks status/content-length and returns `{}` for intentionally empty bodies, returns `{_raw: text}` for non-JSON success bodies.

### Concurrency & Thread Safety
- **`web.utils.validate_download_url` leaked 5s socket timeout into every thread** — the prior implementation used `socket.setdefaulttimeout(5)` around `getaddrinfo()`, a process-wide mutation that altered the default timeout for every other concurrent socket connect for the duration of the DNS lookup. Replaced with a bounded background-thread `join(timeout=5.0)` so only this call's DNS is capped.
- **`web.static.js.api.js` leaked timeout callbacks** — the 30s default abort-timer was armed but never cleared on successful responses; long-running UI sessions accumulated arm-then-no-op callbacks. `clearTimeout(timeoutHandle)` now runs on both success and failure paths.

### Reliability & Input Validation
- **`web.state.broadcast_event` sanitization missed control bytes** — only `\n`, `\r`, and `:` were stripped from SSE event names. Raw control bytes (NUL, BEL, tab, DEL, etc.) pass through to the wire and corrupt downstream proxies. Now strips all of `U+0000..U+001F` + DEL + `:` and coerces non-string event types to `str`. Extracted into `_sanitize_sse_event_type()` for reuse.
- **`web.state.broadcast_event` silently dropped unserializable payloads** — `json.dumps(data)` with no `default` raised `TypeError` for common values (datetime, set, bytes, Decimal, Path) and the whole event was discarded with no trace. New `_json_default()` handles those types; circular refs now emit a `{'_unserializable': True, 'type': ...}` envelope so listeners still see the event.
- **`web.middleware._host_header_check` broke for IPv6 literal hosts** — a naive `host.split(':')[0]` yielded `[` for `[::1]:8080` and silently failed the allow-host check for every IPv6 client. Now extracts the literal between brackets for IPv6 and uses `rsplit(':', 1)` for IPv4/hostname so the port is always split from the right.

### Platform Robustness
- **`services.manager.download_file` had no read timeout** — `timeout=30` on a streaming request applies only to initial connect; a server that stalled mid-body (TCP keepalives but no data) blocked the download worker indefinitely. Now uses tuple timeout `(30, 60)` so each read is bounded.
- **`services.manager.uninstall_service` leaked directories on Windows** — `shutil.rmtree(ignore_errors=True)` swallowed antivirus/explorer-held-handle errors and returned with the directory still on disk, making the next install think the service was already present. New `_rmtree_with_retry()` helper retries up to 5 times with backoff and writes a `.delete-pending` marker if cleanup still fails.

### Test Infrastructure
- **Alert engine + scheduler now skip startup under pytest** — the daemon threads in `_run_alert_checks` and `_ensure_scheduler` raced with per-test `init_db()` migrations in `conftest.py` and caused intermittent `database table is locked: sqlite_master` errors during the full suite run. `blueprint_registry` now gates thread startup on `app.config['TESTING']` / `PYTEST_CURRENT_TEST`. Full suite is now deterministic.

## [v7.60.0] — Content Expansion: Seeds Package + Field Medicine + CBRN Reference

### Infrastructure — `seeds/` package pattern established
Reference data now lives in per-topic modules under `seeds/` with idempotent `_seed_*()` functions in `db.py`. Keeps `db.py` from ballooning as content grows. First landing: 13 seed modules covering companion plants, weather action rules, pest guide, planting calendar, medicinal herbs, appliance wattage, loadout templates, radio reference, water purification, frequencies, medications, disaster checklists, and hazmat agents.

### Content — CE Tier 1 & 2
- **CE-01: Planting calendar** — 47 crops × 8 USDA zones = 1,069 rows with yield / calories / days-to-harvest (`seeds/planting_calendar.py`).
- **CE-02: Companion plants** — 92 directed pairs covering tomato, brassica, three-sisters, nightshade, and universal helpers (`seeds/companion_plants.py`).
- **CE-03 / CE-04: Field medicine** — DOSAGE_GUIDE expanded from 8 to 47 drugs; DRUG_INTERACTIONS from 26 to 78 pairs. Pregnancy category, shelf-life, pediatric weight-based dosing, contraindications (`seeds/medications.py`).
- **CE-06: Appliance wattage** — 84 loads across 10 categories with running / surge watts + typical hours/day, exposed via `/api/power/appliance-wattage`.
- **CE-07: Weather action rules** — 15 default rule templates (freeze, heat, wind, flash-flood rain, lightning, AQI, mold-risk) with severity-graded action messages.
- **CE-10: Loadout templates** — 15 curated bag templates (72-hr adult/child, EDC, get-home, INCH, vehicle variants, IFAK+, winter-mountain, desert, canoe/boat, urban) with per-item weight. `POST /api/loadout/templates/launch` creates bag + items in one transaction.
- **CE-11: Disaster checklists** — 20-25 items per disaster type (earthquake, hurricane, tornado, wildfire, flood, pandemic, EMP, volcanic, drought, economic collapse) replacing 5-item stubs.
- **CE-12: Hazmat / CBRN reference** — 22 agents across chemical, nerve, blister, biological, radiological (chlorine, ammonia, HCN, phosgene, H2S, sarin, VX, mustard, lewisite, anthrax, smallpox, plague, botulinum, Cs-137, I-131, etc.). Each row carries CAS / UN number, IDLH, ERPG-1/2/3, symptoms, route, decon, first aid, antidote, PPE level, evac distance. Sourced from NIOSH, DOT ERG 2024, AIHA, CDC, USAMRIID. Read-only defensive reference exposed via `/api/hazmat/agents` (list + filter + search) and `/api/hazmat/agents/<id>`.
- **CE-13: Pediatric growth + weight estimation** — WHO 0-24mo + CDC 2-20yr percentile curves, 20 Broselow-style weight bands, `estimate_pediatric_weight(age_years)` helper, exposed via `/api/medical/pediatric-growth` and `/api/medical/pediatric-weight-estimate`.
- **CE-14: Radio reference cards** — NATO + LAPD phonetic alphabets, full International Morse + prosigns, 31 US voice prowords, 3-axis RST, 21 Q-codes, 16 digital-mode comparison card, US General-class HF band plan. Exposed via `/api/radio/reference`, `/api/radio/phonetic`, `/api/radio/morse/<text>`.
- **CE-15: Medicinal herbs** — Expanded from 10 to 50+ species (peppermint, valerian, goldenseal, usnea, St. John's Wort, kava, ashwagandha, turmeric, etc.) with uses, preparation, dosing, contraindications, season, habitat.
- **CE-16: Pest guide** — 38 entries covering insects, mollusks, diseases (early/late blight, powdery mildew, fire blight), vertebrate pests, physiological disorders with IPM-first treatment.
- **CE-19: Water purification reference** — 10 methods (boil, bleach, iodine, CLO2, ceramic, hollow-fiber, RO, UV, SODIS, distillation) with removes / does_not_remove / equipment / time / cost; CDC boil-times by altitude; bleach + iodine dose charts (1 qt → 275 gal IBC); iodine contraindications; 9-class contaminant-response matrix. Legacy `/api/water/purification-reference` shape preserved (`{methods: [...], boil_times, bleach_dosing, iodine_dosing, ...}`) with every legacy key still present on each row.

### Architecture
- **Setup wizard extracted** — `_app_setup_wizard.js` (499 lines) split out of `_app_workspaces.js` to keep that file under the per-module size ceiling. Wizard-only state (`_wiz*`) and helpers moved over; guided-tour stays behind.
- **`nomad.py` SERVICE_MODULES hardened** — flatnotes added so `tray_quit()` actually stops the child process on graceful shutdown (every id in `services.manager.DEPENDENCIES` except `torrent` now maps to a module). Test enforces this invariant.

### Security / Reliability
- **SSE event-type sanitization** — `broadcast_event()` strips colons, CR/LF, and control characters from event names (a colon in an SSE `event:` line is parsed as a field separator; CR/LF ends the frame early). Empty names fall back to `message`.
- **`config.save_config()` crash cleanup** — partial tmp file is removed when `json.dump` or `os.fsync` raises so a later `load_config()` can't recover truncated data.
- **`get_node_id()` race-safe** — concurrent first-call requests converge on a single stored value via `INSERT OR IGNORE` + re-read (previously racing callers each minted their own UUID).
- **`flatnotes` install timeouts** — `venv` creation (300s) and `pip install flatnotes` (600s) now capped so a wedged network doesn't leave the UI spinning indefinitely.

### Theme tokens
- **`--surface-tint-*` tokens** in `00_theme_tokens.css` produce direction-aware overlays via `color-mix()` — subtle darkening in light themes, subtle lightening in dark themes.
- **Theme-token migration** — `sr-alert-toast`, `.kit-stat-*`, `.kit-item-status`, `.copilot-handsfree-btn`, `.copilot-voice-state-badge` swapped hardcoded hex for semantic tokens (`--red`, `--green`, `--warning`, `--info`) so theme switches carry through.
- **Theme coverage test** — new `tests/test_theme_coverage.py` enforces every declared theme defines the full semantic token set and that kit-builder / daily-brief / family-checkin / triage-step status colors route through semantic tokens.

### Tests
- 68 new content-seed tests (`tests/test_content_seeds.py`) covering all seed modules, idempotency, and the new reference endpoints.
- SSE event-type sanitization tests in `test_sse.py`.
- `nomad.SERVICE_MODULES` completeness tests in `test_pass21_hardening.py`.
- Wizard-split regression guards in `test_core.py`.

## [v7.59.0] — V8-19: Mobile Prep Nav + V8-20: Docs Site

### UX (V8-19)
- **Mobile sub-tab navigation** — Preparedness sub-tab button bar replaced with a compact `<select>` at ≤600px viewport width, enabling one-handed workspace switching on phones and small tablets
- Scenario grid compacts to 2-column at 480–600px and single-column below 420px, preventing card overflow on narrow screens
- Workbench strip (Resume / Pinned Workspaces) stacks vertically at ≤600px instead of hiding; all workspace functionality preserved
- Verbose prep heading copy hidden at ≤600px to maximize content area
- `_syncMobileSubSelect()` helper keeps the `<select>` in sync whenever `showPrepCategory()` rebuilds the lane tab bar
- `switchPrepSub()` keeps mobile select value in sync on direct tab navigation
- Delegated `change` listener routes mobile select changes through `switchPrepSub()` so all existing load hooks fire normally

### Documentation (V8-20)
- **Standalone MkDocs docs site** — `mkdocs.yml` with Material for MkDocs theme (dark/light toggle, tabs, search)
- `docs/guide/` — 41 markdown files extracted from the in-app Help Guide covering every feature section
- `docs/index.md` — landing page with feature summary and quick-navigation links
- `requirements-docs.txt` — `mkdocs>=1.6`, `mkdocs-material>=9.5`
- `.github/workflows/docs.yml` — CI workflow: builds and deploys to GitHub Pages on every push to `master` that touches `docs/`, `mkdocs.yml`, or `requirements-docs.txt`
- `scripts/extract_guide_to_docs.py` — idempotent extraction script to regenerate `docs/guide/` from the in-app guide source; handles steps, tips, warnings, and tables

## [v7.58.0] — V8-12: Frontend Unit Tests

### Developer Experience (V8-12)
- **Frontend unit tests** (vitest) — Added `tests/js/utils.test.js` with 48 tests covering 5 critical utility functions:
  - `escapeHtml` (8 tests) — null/undefined handling, HTML entity escaping, XSS payload
  - `formatBytes` (5 tests) — B/KB/MB/GB formatting
  - `timeAgo` (5 tests) — "Just now", minutes, hours, days boundaries
  - `parseInventoryCommand` (18 tests) — action detection, quantity/unit/location parsing, 8-category classification
  - `parseSearchBang` (12 tests) — all bang prefixes, case-insensitivity, query trimming
- `vitest.config.mjs` configured with jsdom environment
- `package.json` adds vitest v2, @vitest/coverage-v8, jsdom to devDependencies; adds `test` and `test:watch` scripts
- `tests/js/utils.js` — pure-JS extraction of template functions for unit testing (logic-identical to template source)

## [v7.57.0] — V8 Blueprint Coverage & App Factory Refactor

### Architecture (V8-09, V8-11)
- **Middleware extracted** (`web/middleware.py`) — All `before_request`, `after_request`, `teardown_appcontext`, and `errorhandler` hooks extracted from `create_app()` into `setup_middleware(app)`. Covers: rate limiting, CSRF origin/token checks, host header validation, LAN auth guard, security headers (CSP, X-Frame-Options, Referrer-Policy, Permissions-Policy), DB connection cleanup, and global error handlers. `MUTATING_METHODS`, `_CSP_POLICY`, and `_EMBED_CSP_POLICY` are now module-level constants.
- **Blueprint registry** (`web/blueprint_registry.py`) — All 72 blueprint imports and `register_blueprint()` calls extracted into `register_blueprints(app)`. Also manages `start_alert_engine()`, `_ensure_scheduler()`, and `load_plugins(app)`. Blueprint imports are deferred inside the function body (lazy-on-call).
- `create_app()` reduced from 1,822 lines to 1,362 lines (net −460 lines).

### Testing (V8-06)
- **Blueprint test coverage** — Added 15 new test files covering 131 routes across previously untested blueprints: contacts, tasks, checklists, notes, medical, weather, power, services, security, agriculture, evac_drills, readiness_goals, group_ops, health_family, daily_living. All 131 tests pass.

## [v7.56.0] — V8 Architecture & DX Hardening

### Architecture (V8-10, V8-11-prep)
- **Template render cache** (`web/app.py`) — `_render_workspace_page()` now caches rendered HTML with a 5-second TTL using a thread-safe `dict` + `Lock`. Cache key covers `tab_id`, language, bundle hash, media sub-tab, first-run state. Evicts entries after 200-key high-water mark.
- **Progressive disclosure groundwork** (V8-02) — Shell nav tab buttons now render `id="tab-X"` only for the active tab (via Jinja conditional). `workspace-inspector` panel suppressed on the home/services page.

### Developer Experience (V8-14, V8-16, V8-23)
- **Module-level column allowlists** (V8-14) — 95 function-level `allowed = [...]` lists across 29 blueprint files refactored to module-level `frozenset` constants (`_TABLE_ALLOWED_FIELDS`). Eliminates per-request list allocation; frozensets allow O(1) membership tests.
- **File-based DB integration tests** (V8-16) — `tests/test_db_integration.py` with 10 tests covering real-file SQLite: WAL mode, schema gate, connection pool stats, Flask startup, foreign-key enforcement, seed data.
- **Seeded test data isolation** (V8-23) — `conftest.py` gains `seed_upc_entry`, `seed_rag_scope_row`, `assert_upc_seeded`, `assert_rag_scope_seeded` fixtures to make seed-data dependencies explicit.

### CI/CD (V8-21)
- **macOS code signing** — `build.yml` gains "Sign macOS binary" step: decodes `MACOS_CERT_BASE64` → temporary keychain → `codesign --force --options runtime` → `xcrun notarytool submit --wait` (if Apple credentials present). Step is a no-op when secrets are absent.

## [v7.55.1] — Frontend Security & UX Hardening

### Security
- **XSS: Journal mood badge** (`_app_ops_support.js`) — `e.mood` was injected into `innerHTML` without escaping. User-entered mood values are now passed through `escapeHtml()`.
- **XSS: Medical reference table headers** (`_app_init_runtime.js`) — Column header keys from `data.items[0]` were inserted raw. Now escaped with `escapeHtml(k.replace(/_/g,' '))`.
- **XSS: LAN QR modal URL** (`_app_init_runtime.js`) — `${url}` in `innerHTML` template was unescaped. Wrapped in `escapeHtml(url)`.

### Bug Fixes
- **CSRF race condition** (`api.js`) — `apiFetch` documented that it awaits `_csrfTokenPromise` before sending mutating requests, but the code didn't. Fixed: POST/PUT/DELETE/PATCH now awaits the initial token fetch if `_csrfToken` is not yet populated, preventing 403s on LAN for the very first mutating request after page load.
- **Double-submit: `sendBroadcast`** (`_app_ops_support.js`) — Broadcast send button is now disabled with `aria-busy` during the async request and re-enabled in a `finally` block, preventing duplicate broadcasts on rapid clicks.
- **Double-submit: `submitJournal`** (`_app_ops_support.js`) — Journal "Log Entry" button is now disabled with `aria-busy` during submission and re-enabled in `finally`, preventing duplicate journal entries.



### Architecture (V8-01)
- **Schema version gate** — `_meta` table with `schema_version` check. On subsequent starts, skips all 935 `CREATE TABLE/INDEX IF NOT EXISTS` statements when version matches. First-run still creates everything. Cuts startup time 30-50% for returning users.

### Security (V8-05, V8-07, V8-15)
- **Encrypt TOTP secrets at rest** — `_encrypt_secret()` / `_decrypt_secret()` via Fernet. Encryption key auto-generated and persisted in `config.json`. Graceful fallback for legacy plaintext secrets.
- **`safe_column()` validator** — new function in `web/sql_safety.py` for single-column validation (sort_by, order_by). Validates against identifier regex + explicit allowlist.
- **Persist secret key for LAN** — when `NOMAD_AUTH_REQUIRED=1`, auto-generates and persists `NOMAD_SECRET_KEY` to `config.json` so Flask sessions survive app restarts.

### UX (V8-18)
- **Soft delete / trash pattern** — `deleted_at` column on inventory, contacts, notes, patients. `/api/trash` lists trashed items, `/api/trash/<table>/<id>/restore` recovers them, `/api/trash/purge` permanently deletes items older than 30 days.

### CI/CD (V8-13, V8-24)
- **Codecov integration** — `codecov-action@v4` uploads coverage XML from Linux CI runner.
- **CSS cascade documentation** — `web/static/css/README.md` with full load order, token reference, and contribution rules.

### Roadmap Status
V8-01, V8-05, V8-07, V8-13, V8-15, V8-17, V8-18, V8-24 complete (8/24).

## [v7.54.0] — Complete Design Token Migration

### Design System Migration — 2,000+ Values Tokenized
- **Font-size**: 1,535 hardcoded values → design tokens (100% app layer, 99.5% premium layer)
- **Border-radius**: 700+ hardcoded values → design tokens (95%+ app layer, 93% premium layer)
- **Transition durations**: 200+ values migrated to `--duration-*` tokens
- **Transition easing**: 200+ bare `ease` → `var(--easing-standard)`
- **New token**: `--text-3xs` (7px) for Situation Room ultra-dense data labels

### Impact
Changing a single token value (e.g., `--text-sm: 11px` → `12px`) now propagates to 1,500+ locations across all 21 CSS files and all 5 themes simultaneously. The design system is now fully token-driven — the product can be restyled, rescaled, and re-themed entirely through `00_theme_tokens.css` without touching component CSS.

## [v7.53.0] — Premium Design System Polish Pass

### Design Token Expansion (`00_theme_tokens.css`)
- **Typography scale**: 7 → 12 steps. Added `--text-2xs` (9px), `--text-sm-md` (12px), `--text-md-lg` (15px), `--text-3xl` (28px), `--text-4xl` (32px). Covers all component sizes without hardcoding.
- **Transition duration scale**: 2 → 8 steps. Added `--duration-micro` (0.1s), `--duration-snappy` (0.18s), `--duration-mid` (0.3s), `--duration-slow` (0.5s), `--duration-slower` (1s), `--duration-slowest` (1.5s). Unified timing language.
- **Easing functions**: Added `--easing-decelerate`, `--easing-accelerate`, `--easing-spring` alongside existing `--easing-standard`.
- **Border radius scale**: 4 → 9 steps. Added `--radius-2xs` (2px), `--radius-xs` (4px), `--radius-md` (14px), `--radius-lg` (18px), `--radius-2xl` (24px), `--radius-full` (999px).
- **Opacity scale**: New. `--opacity-disabled` (0.4), `--opacity-muted` (0.5), `--opacity-secondary` (0.7), `--opacity-subtle` (0.8).
- **Elevation shadows**: New 4-level scale (`--elev-1` through `--elev-4`) for consistent card/modal/dropdown depth.
- **Focus system**: New `--focus-ring`, `--focus-offset`, `--focus-shadow` tokens for unified keyboard focus.
- **Touch targets**: New `--touch-min: 44px` utility token.
- **Spacing**: Added `--sp-7` (28px), `--sp-10` (40px), `--sp-12` (48px), `--sp-16` (64px).

### Premium Polish (`99_final_polish.css`)
- **Unified card base**: Cards (`cc-card`, `service-card`, `gauge-card`, `settings-card`) now share consistent hover elevation (`--elev-2`), border-color transition, and press scale effect.
- **Unified input focus**: All text inputs, selects, and textareas get consistent `border-color + box-shadow` focus ring using `--focus-shadow` token.
- **Button refinements**: All buttons get `--radius-sm` radius, press scale on active, proper disabled state with `--opacity-disabled`, explicit primary/danger focus-visible styles.
- **Empty state polish**: Standardized padding, icon opacity, font size, and line height across all empty state variants.
- **Modal elevation**: Modals and wizards use `--elev-4` instead of hardcoded shadows. Proper `--radius-lg`/`--radius-xl`.
- **Scrollbar consistency**: Unified 5px width/height on all scrollbars.
- **Context menu refinement**: Proper animation, elevation shadow, rounded inner items, hover/active states.
- **Notification drawer**: Elevation shadow from token, proper transition easing, hover state on items.
- **All v7.52.0 CSS primitives** migrated from hardcoded values to design tokens: border-radius, spacing, durations, shadows, z-indexes, opacity.

## [v7.52.0] — Frontend Primitives, Internal Hardening, Roadmap Completion

### Added (Frontend CSS/JS)
- **Animated page transitions (P3-01)** — `.tab-content` opacity transition + `pageIn` animation, `prefers-reduced-motion` safe.
- **Dashboard theme previews (P3-02)** — `.theme-preview-card` with sidebar/header/body color regions.
- **Inventory heatmap calendar (P3-03)** — `.heatmap-grid` + `.heatmap-cell[data-level]` 4-tier GitHub-style color scale.
- **Customizable status strip (P3-05)** — `.status-strip-config` draggable layout.
- **Visual alert rule builder (P3-09)** — `.rule-builder` + `.rule-condition` + `.rule-operator` CSS primitives.
- **Right-click context menus (P4-07)** — `.context-menu` CSS + `initContextMenus()` JS with Edit/Copy/Delete actions.
- **Minimal startpage mode (P4-08)** — `?view=minimal` URL param hides sidebar/strip/copilot.
- **Workspace tiled view (P4-09)** — `.tiled-workspace` CSS grid (2/3/4 panel layouts).
- **Service opening methods (P4-11)** — `.service-open-dropdown` + `.service-open-menu` CSS.
- **Mobile swipe navigation (P4-16)** — touch swipe JS handler + `.swipe-indicator` / `.swipe-dot` CSS.
- **Icon library system (P4-17)** — `[data-icon]::before` CSS primitive.
- **Masonry grid layout (P4-20)** — `.masonry-grid` CSS columns auto-layout.
- **Widget drag-and-drop (P2-06)** — `.widget-dropzone` CSS with active state.
- **Photo gallery (P2-15)** — `.photo-gallery` grid + `.photo-gallery-item` with hover zoom.
- **Notification drawer (P2-17)** — `.notification-drawer` slide-out panel with unread dots.
- **Meal plan calendar (P2-25)** — `.meal-calendar` 7-column grid with today highlight.
- **AI message queuing indicator (P5-02)** — `.chat-queued-indicator` pill.
- **AI citation highlights (P5-05)** — `.citation-highlight` with scroll-margin.
- **Active task indicator (P5-21)** — `.convo-task-indicator` pulsing dot.
- **Fuzzy settings search (P5-22)** — `upgradeFuzzySettingsSearch()` with 12 keyword alias mappings.

### Internal Hardening
- **Max download size (P2-I19)** — 2 GB cap on `download_file()` with Content-Length check.
- **Disk space check before VACUUM (P2-I20)** — refuses if free space < 2x DB size.
- **Source maps in esbuild (P3-I27)** — `sourcemap: true` on both JS and CSS bundles.
- **requirements-dev.txt (P2-I15)** — separate dev dependencies (pytest, pytest-cov).

### Deferred (8 items — external deps required)
P3-06 (Meshtastic hardware), P3-07 (ML model), P3-10 (plugin architecture), P3-11 (Tauri rewrite), P3-13 (regional data), P3-15 (Home Assistant), P3-19 (Android app), P5-06 (AI agent loop).

## [v7.51.0] — OpenAPI, AI Tools, Survival Reference, i18n Expansion

### Added
- **OpenAPI/Swagger spec (P2-07)** — auto-generated `/api/openapi.json` from Flask routes. Swagger UI at `/api/docs`.
- **Expanded i18n (P2-08)** — 56 → 210+ translation keys covering buttons, errors, empty states, labels, status, confirmations, toasts, and time units.
- **Inline survival quick-reference (P2-13)** — 10 built-in reference cards: water purification, fire starting, shelter, first aid, navigation, signaling, wild edibles, knots, weather prediction, emergency radio frequencies. Searchable via `/api/reference/survival`.
- **AI model comparison (P3-16)** — `/api/ai/compare` sends same prompt to two models and returns both responses side-by-side.
- **AI function/tool calling (P3-17)** — 6 structured tools (query_inventory, check_weather, count_contacts, get_alerts, search_notes, calculate_dosage) callable via `/api/ai/tools/<name>`. Replaces regex-based action parsing for structured operations.

### Verified Already Complete
- P2-19 (fractional quantities) — schema already accepts `(int, float)` since v7.32.0.

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
