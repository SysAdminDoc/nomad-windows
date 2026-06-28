# ROADMAP — remaining/incomplete work only

## From 2026-06-09 deep audit (items found but not fixed this pass)

- [ ] P3 — Consolidate the premium CSS override stack
  Why: 80_dark_theme_overrides / 90_theme_consistency / 95_premium_polish / 99_final_polish
  restyle the same selectors in sequence (~170 `!important` in 99 alone); tracing a button's
  final appearance requires reading four layers. Maintenance risk, not a user-facing bug.
  Where: web/static/css/premium/

- [ ] P3 — Replace federation sync HMAC keying with an asymmetric or shared-secret handshake
  Why: v7.66.3 now verifies pinned signed sync payloads and pins the first valid key for
  keyless trusted peers, but the current `public_key` HMAC format is a compatibility bridge
  rather than a full asymmetric sender-authentication model.
  Where: web/blueprints/federation.py, federation peer enrollment UI/API, db.py

- [ ] P3 — Cached fallback for GitHub release lookups in service installers
  Why: all service installs resolve release assets from api.github.com with no cached
  last-known-good URL; GitHub outage = mass install failure with a generic error.
  Where: services/manager.py, services/cyberchef.py, services/qdrant.py, services/stirling.py

- [ ] P3 — Decimal/integer-cents arithmetic for financial aggregation
  Why: amounts are floats (validated 0..1e9); summation across many records can lose cents
  precision. Low risk at desktop scale.
  Where: web/blueprints/financial.py

- [ ] P3 — Triage or drop the stale `stash@{0}` (WIP on 980cf04, v4-era)
  Why: an ancient stash sits in the repo's stash list; popping it conflicts with the modern
  tree (happened 2026-06-09, recovered via reset to pushed HEAD). Decide if anything in it
  is worth salvaging, then `git stash drop`.
  Where: git stash list

## From RESEARCH.md active findings

- [ ] P2 — Continue schema validation on remaining raw-JSON mutating endpoints
  Why: v7.66.11–v7.66.20 hardened system, AI, emergency, comms, supplies, federation,
  Shamir/canary, security/OPSEC, tactical-comms, and medical mutations. v7.66.23
  hardened Situation Room feeds/monitors/search/deduction/watchlist/webhook mutations.
  ~150+ POST/PUT routes in remaining domain blueprints still accept raw JSON without
  local schemas or type normalization.
  Where: exercises.py, hunting_foraging.py, garden.py, agriculture.py, kiwix.py,
  nutrition.py, field_tools.py, field_ops.py, homestead.py, tier8_tools.py,
  roadmap_features.py, alert_rules.py, daily_living.py, disaster_modules.py,
  group_ops.py, hardware_sensors.py, maps.py, media.py, medical_phase2.py,
  specialized_modules.py, training_knowledge.py, remaining_calcs.py

- [ ] P3 — Verify the PyInstaller security floor
  Why: RESEARCH.md flags PyInstaller <6.10.0 for CVE-2025-59042; build tooling does not pin
  or surface the PyInstaller version used for release binaries.
  Where: requirements-dev.txt, build.spec, .github/workflows/

- [ ] P3 — Attach SBOM artifacts to releases
  Why: release binaries include many Python/JS dependencies but no machine-readable SBOM
  for users to audit.
  Where: .github/workflows/build.yml, package-lock.json, requirements*.txt

- [ ] P3 — Add release artifact signing/provenance
  Why: releases include SHA256SUMS but no Sigstore/cosign/SLSA provenance chain.
  Where: .github/workflows/build.yml

- [ ] P3 — Split the `db.py` monolith by domain
  Why: schema, migrations, seed data, and helpers share one very large file, increasing
  merge risk and making audits harder.
  Where: db.py, db_migrations/

- [ ] P3 — Split `situation_room.py` into focused modules
  Why: fetchers, parsers, map layers, analysis, and routes share one very large blueprint,
  making reliability and performance work slower than necessary.
  Where: web/blueprints/situation_room.py

- [ ] P3 — Move large frontend scripts toward explicit modules
  Why: concatenated global-scope JavaScript increases TDZ/global-collision risk and makes
  targeted testing harder.
  Where: web/templates/index_partials/js/, web/static/js/, esbuild.config.mjs

- [ ] P3 — Decide the legacy `index.html` fixture contract
  Why: RESEARCH.md notes the all-tab legacy template is still used by tests but no active
  route renders it; clarify whether to retire it or preserve it as a named test fixture.
  Where: web/templates/index.html, tests/

- [ ] P3 — Audit blueprint auth expectations against the global LAN guard
  Why: RESEARCH.md flagged sparse per-blueprint auth decorators; verify this is fully
  covered by `NOMAD_AUTH_REQUIRED` middleware and document any privileged exceptions.
  Where: web/middleware.py, web/blueprints/

- [ ] P3 — Speed up test database setup
  Why: fixtures recreate the full 264-table schema and 611 indexes per test, making full
  suite iteration slow and encouraging under-testing.
  Where: tests/conftest.py, db.py

- [ ] P3 — Track schema migration versions instead of replaying all migrations
  Why: startup migration code rechecks broad migration state on every launch; tracked
  migration versions would reduce startup work and make upgrade state more explicit.
  Where: db.py, db_migrations/

- [ ] P3 — Evaluate FEMA IPAWS as a backup CAP alert source
  Why: RESEARCH.md identifies FEMA public alert feeds as a possible resilience improvement,
  but developer access/MOA requirements need validation before implementation.
  Where: web/blueprints/situation_room.py, RESEARCH.md

- [ ] P3 — Evaluate OpenZIM MCP integration vs. a narrow local adapter
  Why: OpenZIM MCP could improve AI-to-ZIM search, but footprint and dependency tradeoffs
  need a repo-specific decision before build work.
  Where: services/kiwix.py, AI/Kiwix integration surfaces, RESEARCH.md

- [ ] P3 — Define the first supported recipe/inventory unit set
  Why: unit consistency affects fractional quantities, recipes, shopping lists, and burn-rate
  math; selecting the first supported unit family avoids piecemeal conversions.
  Where: web/blueprints/inventory.py, web/blueprints/roadmap_features.py, README.md

- [ ] P3 — Evaluate first-class Pi/LAN appliance mode
  Why: deployment mode affects auth, binding defaults, service discovery, and offline
  content assumptions.
  Where: config.py, README.md, docs/

- [ ] P3 — Revisit MapLibre v5 upgrade constraints
  Why: MapLibre v5 is ESM-only; the app bundles a legacy-compatible path today, so upgrade
  feasibility needs proof before dependency churn.
  Where: package.json, esbuild.config.mjs, map/VIPTrack/NukeMap frontend code

## Research-Driven Additions

- [ ] P2 - Add KB indexing budget, cancel, and purge controls
  Why: Offline knowledge workflows can run for hours or consume large storage, and upstream NOMAD issue signal centers on ZIM/Wikipedia indexing, stall warnings, and storage growth.
  Evidence: Crosstalk-Solutions/project-nomad issues #1015, #947, #883, and #858; `services/kiwix.py`; `web/blueprints/kb.py`.
  Touches: `web/blueprints/kb.py`, `services/kiwix.py`, `services/qdrant.py`, AI/Library UI.
  Acceptance: Before indexing, UI shows estimated documents/bytes/time; active jobs show rate/progress/cancel; purge by source frees vectors/files with confirmation.
  Complexity: L

- [ ] P2 - Add mobile field-mode visual smoke coverage
  Why: HAVEN and dashboard competitors set a mobile/offline field expectation; Field Desk has PWA manifests and responsive UI but no dedicated narrow-viewport workflow gate for core field tasks.
  Evidence: HAVEN feature pages; Glance mobile optimization; `web/static/manifest.json`; `tests/ui/`.
  Touches: `tests/ui/`, `web/static/manifest.json`, shell/workspace CSS, top workflow templates.
  Acceptance: Playwright covers 390px/430px widths for Situation Room, Inventory, Medical, Maps, Comms, Settings, AI Chat, and Services with no overlap/clipping and usable primary actions.
  Complexity: M

- [ ] P2 - Make mesh transport readiness explicit
  Why: Reticulum/LXMF service code exists, but `/api/mesh/status` falls back to generic mesh state when RNS is absent; users need clear readiness before relying on off-grid comms.
  Evidence: `services/reticulum.py`; `web/blueprints/comms.py`; Meshtastic 2.7 firmware notes.
  Touches: `services/reticulum.py`, `web/blueprints/comms.py`, comms UI, tests.
  Acceptance: Mesh UI distinguishes unavailable/installable/running/degraded states, exposes identity/peer counts, and includes install guidance without implying transport is active.
  Complexity: M

- [ ] P3 - Add i18n coverage ratchet for visible shell text
  Why: Translation data exists for 10 languages, but only 12 `data-i18n` hooks were found across primary templates against thousands of visible text nodes.
  Evidence: `web/translations.py`; `web/static/js/i18n.js`; `web/templates/index_partials/` scan.
  Touches: `web/templates/index_partials/`, `web/static/js/i18n.js`, `tests/`.
  Acceptance: A test fails when new shell/sidebar/settings/service labels lack `data-i18n`; first pass covers the app shell, Settings, Services, and Diagnostics.
  Complexity: L

- [ ] P3 - Rehearse pywebview 6 upgrade behind a compatibility branch
  Why: Runtime pins `pywebview>=5.0,<6.0` while 6.2.1 is current; v6 has breaking API changes, so upgrade needs evidence before lifting the pin.
  Evidence: `requirements.txt`; `nomad.py`; pywebview 6.0 notes; `pip index versions pywebview`.
  Touches: `requirements.txt`, `nomad.py`, platform launch paths, `build.spec`, UI smoke tests.
  Acceptance: A matrix run proves Windows/WebView2, Linux GTK, and macOS launch/close/download flows on pywebview 6 or documents blocked APIs with exact code references.
  Complexity: M

- [ ] P3 - Add docs coverage checks against the blueprint/workspace registry
  Why: MkDocs pages are much thinner than README and can drift as 59+ blueprints evolve.
  Evidence: `mkdocs.yml`; `docs/guide/*.md`; `web/blueprint_registry.py`; README architecture.
  Touches: docs coverage/check script, `mkdocs.yml`, docs guide pages.
  Acceptance: CI reports unmentioned registered workspaces/blueprints, stale nav links, and missing setup/security pages without forcing docs writes during tests.
  Complexity: S

- [ ] P3 - Add structured local AI output schemas for high-risk extractors
  Why: Ollama supports JSON Schema structured outputs; Field Desk has OCR/receipt/document extraction and action execution where malformed model JSON can degrade workflows.
  Evidence: Ollama structured-output docs; `web/blueprints/ai.py`; `web/blueprints/inventory.py`; `tests/test_services_ai_contracts.py`.
  Touches: `services/ollama.py`, AI extraction/action helpers, inventory OCR, tests.
  Acceptance: Receipt/document extraction and action proposal paths request schema-constrained output, reject malformed model responses, and keep a raw-response debug trail.
  Complexity: M

- [ ] P2 — Add storage relocation and migration preflight
  Why: Large ZIMs, models, maps, backups, uploads, and managed services make storage location a reliability concern, and upstream Project NOMAD users repeatedly hit custom-path and storage-mount problems.
  Evidence: `config.py`, `web/blueprints/system.py`, Project NOMAD issues #367/#464/#588/#655/#938.
  Touches: setup/settings UI, `config.py`, system/storage routes, backup/restore, service manager paths, tests around unavailable drives.
  Acceptance: users can stage a new data directory, see required/free-space estimates, verify write access, stop affected services, copy data with a manifest/checksum, atomically switch config, and roll back to the previous path on failure.
  Complexity: L

- [ ] P2 — Add hybrid lexical/vector KB retrieval with citations
  Why: Current KB search is primarily semantic vector retrieval, while local AI tools such as Open WebUI now set user expectations for hybrid BM25/vector search, reranking, full-context controls, and source citations.
  Evidence: `web/blueprints/kb.py`, `services/qdrant.py`, Open WebUI knowledge documentation, Project NOMAD issue #947.
  Touches: KB indexing/search routes, SQLite FTS/chunk storage, Qdrant merge logic, AI/RAG callers, KB UI, retrieval tests.
  Acceptance: KB search merges SQLite FTS5/BM25 hits with Qdrant hits, deduplicates by document/chunk, returns source citations and score components, and has tests for exact lexical terms, semantic queries, and offline operation without Qdrant.
  Complexity: L

- [ ] P2 — Add a network-disconnect field readiness drill
  Why: The product promise is local/offline use after setup, but the current test surface does not explicitly prove that core workflows remain usable when external network calls fail.
  Evidence: `README.md`, `tests/ui/`, Situation Room external fetch paths, Project NOMAD offline-use discussions.
  Touches: Playwright smoke tests, fetch/error handling, Situation Room degraded states, Maps/Library/Services health UI, docs for offline expectations.
  Acceptance: a repeatable test mode blocks outbound network access and verifies Home, Situation Room cached/degraded state, Maps offline assets, Library/Kiwix status, AI/service degradation messages, and backup/restore entry points without unhandled console errors.
  Complexity: M

- [ ] P3 — Enforce workspace role policies after the auth audit
  Why: Roles and session management exist, but sensitive workspace writes are not consistently expressed as explicit viewer/user/admin permissions across domain routes.
  Evidence: `web/auth.py`, `web/middleware.py`, `web/blueprints/platform_security.py`, Mealie group/household permissions, Open WebUI tool/RBAC documentation.
  Touches: route decorators, blueprint permission metadata, frontend disabled/hidden states, platform security settings, tests for LAN `NOMAD_AUTH_REQUIRED=1`.
  Acceptance: a documented role matrix covers at least Inventory, Medical, Services, Platform Security, and KB actions; non-loopback requests below the required role receive 403; UI controls reflect permission state; tests cover allowed and denied paths.
  Complexity: L

### P2 - Evidence Quality and Observability

- [ ] P2 -- Add an automated accessibility regression gate
  Why: The repo has targeted ARIA/focus tests, but no automated WCAG/axe-style scan across the shell and core workspaces where regressions are easiest to miss.
  Evidence: `tests/ui/`; `tests/test_loadout_accessibility.py`; `web/static/css/app/60_accessibility_platform.css`; Playwright accessibility testing docs; WCAG 2.2; WebAIM Million 2026.
  Touches: Playwright tests, `package.json`, `package-lock.json`, app shell/settings/services/Situation Room templates, CI.
  Acceptance: Playwright accessibility spec scans the app shell plus Settings, Services, Inventory, Medical, Maps, and Situation Room; critical/serious violations fail CI; any justified suppressions are explicit and selector-scoped.
  Complexity: M

- [ ] P2 - Create a local release packaging pipeline after workflow removal
  Why: HEAD removed GitHub Actions workflows, but README/build assumptions still describe remote multi-platform release builds; local release output needs one reproducible path.
  Evidence: `d79346a`; `.github/release-drafter.yml`; `README.md` CI/CD section; `build.spec`; `installer.iss`; `tools/build_appimage.sh`; Node.js release schedule.
  Touches: release tooling, README release docs, `build.spec`, `installer.iss`, `tools/build_appimage.sh`, update-download compatibility checks.
  Acceptance: one local command cleans stale artifacts, verifies version consistency, runs required tests/builds, produces official artifacts plus `SHA256SUMS.txt` and a build manifest, and refuses release output if any artifact or checksum is missing.
  Complexity: L

- [ ] P2 - Add PyInstaller frozen-app startup guard and release smoke test
  Why: `build.spec` has no runtime hook and `nomad.py` does not call `multiprocessing.freeze_support()` before imports, so packaged desktop startup should explicitly guard against frozen child-process relaunch regressions.
  Evidence: `build.spec`; `nomad.py`; PyInstaller multiprocessing/freeze-support documentation.
  Touches: `nomad.py`, `build.spec`, optional runtime hook file, release smoke script, packaging docs.
  Acceptance: frozen builds include a runtime hook plus first-executable-statement `freeze_support()`, and the release smoke test launches the built app, verifies a single main process, reaches `/api/health`, then exits cleanly.
  Complexity: M

- [ ] P2 - Add Kiwix/OpenZIM content lifecycle controls
  Why: Offline library value depends on knowing which ZIMs are installed, searchable, stale, corrupt, orphaned, or safe to purge, not just whether Kiwix runs.
  Evidence: Project NOMAD issues #883/#933/#947; Kiwix/OpenZIM ecosystem; `services/kiwix.py`; `web/blueprints/kiwix.py`; `web/templates/index_partials/_tab_library.html`.
  Touches: Kiwix service metadata, library UI, content-tier installer, checksum/orphan cleanup, diagnostics bundle, KB indexing queue.
  Acceptance: installed ZIMs show title/language/date/size/checksum/searchable status; stale or corrupt files are flagged; orphaned files can be reviewed and purged; index state is tied to each source.
  Complexity: L

- [ ] P2 - Add reviewed-source guardrails for high-risk field guidance
  Why: Medical, foraging, CBRN, nuclear, and local-AI guidance can cause harm if presented without source/review status, citation trail, or printable fallback.
  Evidence: HazAdapt hazard-guide posture; Red Cross emergency app model; `web/blueprints/medical.py`; `web/blueprints/medical_phase2.py`; `web/blueprints/hunting_foraging.py`; `web/blueprints/specialized_threats.py`; `web/blueprints/ai.py`.
  Touches: high-risk guide templates, AI prompt/context builders, print exports, source metadata, tests for citation/review badges.
  Acceptance: high-risk guidance surfaces show reviewed/unreviewed state, source references, last-reviewed date where known, and a printable reference path; AI responses for these domains stay non-diagnostic and cite local sources when available.
  Complexity: L

- [ ] P3 - Normalize CAP alert ingestion after IPAWS source validation
  Why: FEMA IPAWS, NWS CAP, and OASIS CAP 1.2 provide a common warning format that would make non-weather alert ingestion less bespoke once source access is confirmed.
  Evidence: existing roadmap item "Evaluate FEMA IPAWS as a backup CAP alert source"; FEMA IPAWS All-Hazards Information Feed docs; NWS CAP alert docs; OASIS CAP 1.2.
  Touches: `web/blueprints/situation_room.py`, alert feed parsers, cache tables, proximity rules, degraded/offline alert UI.
  Acceptance: CAP parser tests cover event/severity/urgency/certainty/geocode/effective/expires fields; NWS CAP works as the first source; IPAWS remains disabled unless access requirements are met.
  Complexity: M
