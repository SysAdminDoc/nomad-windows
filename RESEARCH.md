# Research - NOMAD Field Desk

## Executive Summary

NOMAD Field Desk is a local-first preparedness workstation: Flask, SQLite WAL, pywebview, Jinja workspaces, large server-rendered JavaScript surfaces, managed local services, offline maps/library, local model support, and a desktop release path through PyInstaller/Inno/AppImage tooling. Current HEAD is much stronger than the prior research file: LAN QR generation is local, legacy client-only auto-backup was retired, GitHub Actions workflows were removed, Situation Room and Movement Ops mutation validation landed, plugin manifests are required, and backup verification/diagnostics/service journals exist. Highest-value direction is to prove the offline/local promise end-to-end and make large-data operations understandable: finish raw-JSON schema validation, add KB indexing budget/cancel/purge and hybrid retrieval work already on the roadmap, add storage relocation, make mesh readiness honest, add accessibility/mobile/no-network gates, replace stale release-build assumptions with a local packaging pipeline, harden PyInstaller startup, add Kiwix/OpenZIM content lifecycle controls, and add reviewed-source guardrails for high-risk medical/foraging/disaster guidance.

## Product Map

- Core workflows: Situation Room monitoring, home/readiness planning, inventory and consumption, medical records and printable references, maps/routes/waypoints, comms/mesh, services, local AI chat, KB/library, notes/media, security/OPSEC, federation, diagnostics, backup/restore, and settings.
- User personas: solo household operator, preparedness family, small pod/group coordinator, offline-library maintainer, LAN appliance operator, and incident volunteer who needs field references without cloud dependency.
- Platforms and distribution: Windows, Linux, and macOS desktop through Python/pywebview; PyInstaller `build.spec`, Inno `installer.iss`, Linux AppImage helper, PWA manifests, and GitHub Releases as the public download channel.
- Key integrations and data flows: SQLite app DB, data directory uploads/maps/backups/services, Ollama embeddings/chat, Qdrant vectors, Kiwix/ZIM content, CyberChef/Kolibri/Stirling/FlatNotes/torrent services, Reticulum/LXMF optional mesh, public alert/feed sources, GitHub release metadata, and local import/export artifacts.

## Competitive Landscape

- Project NOMAD upstream: closest ecosystem match for offline AI/library/service orchestration. Its open issues show concrete pain around ZIM indexing cost, false progress, Qdrant count drift, and hybrid retrieval. Field Desk should keep the desktop-local security posture while borrowing the KB lifecycle lessons.
- HazAdapt and Red Cross emergency apps: strong at preloaded, guided, plain-language hazard actions and mobile/offline access. Field Desk should learn the "do no harm" review posture and step-by-step emergency UX, while avoiding unreviewed AI diagnosis or plant/medical inference.
- Sahana Eden and Ushahidi: stronger for professional disaster coordination, organizations, role permissions, crowdsourced reports, and CAP/GIS workflows. Field Desk should borrow normalized incident/report/permission patterns, not a heavy multi-tenant humanitarian stack.
- Grocy, Mealie, and Homebox: better at narrow household inventory, labels/barcodes, recipes/shopping, maintenance, locations, and low-friction daily use. Field Desk should learn unit consistency, label workflows, and stock-to-shopping ergonomics without becoming a food-only ERP.
- Kiwix, Internet-in-a-Box, and OpenZIM: validate the offline library strategy. The missing layer in Field Desk is not another content source; it is catalog metadata, version/update awareness, storage budgeting, checksum/orphan cleanup, indexing policy, and clear searchable vs. non-searchable states.
- Open WebUI and Qdrant: set expectations for local RAG collections, citations, hybrid dense/sparse retrieval, tool permissions, and structured extraction. Field Desk already has Ollama/Qdrant primitives, but needs hybrid retrieval, source citations, and schema-constrained extraction paths.
- Home Assistant backup UX: useful reference for visible backup schedule, locations, retention, encryption, and restore confidence. Field Desk should stay local/removable-media first and avoid default cloud backup assumptions.

## Security, Privacy, and Reliability

- Verified fixed: `web/templates/index_partials/js/_app_init_runtime.js` no longer uses `api.qrserver.com`; `/api/qr/generate` is schema-validated in `web/blueprints/system.py`, and README documents local LAN QR generation.
- Verified fixed: the old client-side auto-backup scheduler is gone from `_tab_settings.html` and `_app_ops_support.js`; server-side scheduling now lives in `web/background.py` and backup APIs in `web/blueprints/system.py`.
- Verified current gap: `README.md` still says GitHub Actions builds multi-platform binaries, but HEAD `d79346a` removed workflows and `.github/` now only contains release-drafter config. Release packaging needs a local, reproducible command and docs that match the repo policy.
- Verified current gap: `build.spec` has `runtime_hooks=[]`, and `nomad.py` does not call `multiprocessing.freeze_support()` before imports. PyInstaller docs recommend freeze support before multiprocessing in frozen apps; a desktop release smoke test should also prove only one main app process launches.
- Verified current gap: many domain mutating routes still lack `@validate_json`; `ROADMAP.md` already tracks the broad remaining schema-validation pass, so do not duplicate it.
- Verified current gap: `@require_auth` is present on some high-risk routes, but route-level viewer/user/admin policy is not consistently declared across hundreds of mutating endpoints. Existing RBAC roadmap work remains valid.
- Verified current gap: `services/reticulum.py` supports RNS/LXMF when packages exist, but `/api/mesh/status` returns generic mesh state when unavailable. Existing mesh-readiness roadmap work remains valid.
- Verified current gap: Playwright tests cover shell/theme/workflow details, but `package.json` has no axe/WCAG gate and `playwright.config.mjs` uses a single 1600x1000 viewport. Existing accessibility and mobile-field roadmap items remain valid.
- Verified current gap: KB upload/document analysis in `web/blueprints/kb.py` uses Ollama JSON mode and post-parse cleanup, but not JSON Schema structured outputs for high-risk extraction. Existing structured-output roadmap work remains valid.

## Architecture Assessment

- Backend boundaries: 73 blueprint files plus `db.py` at about 300k bytes are workable but audit-heavy. Existing roadmap items to split `db.py`, split Situation Room, and continue schema validation are still the right maintenance path.
- Frontend boundaries: Jinja partials and app JS are pragmatic for a bundled local app, but large global scripts, many inline workspace scripts, and theme override layers make regression isolation expensive. Existing module/CSS consolidation items remain valid.
- Data lifecycle: storage pressure is the central reliability risk because ZIMs, map packs, models, media, uploads, service binaries, backups, and Qdrant indexes can all grow independently. Existing storage relocation and KB budget/cancel/purge items should be treated as P2 trust work.
- Offline proof: the product promise is "works offline after setup," but the strongest test path is still visual/workflow smoke rather than an outbound-network-blocked drill. Existing no-network field readiness work should verify cached/degraded states, not just page load.
- Distribution: after workflow removal, release quality depends on local scripts. Build outputs need clean artifact directories, version checks, SHA256SUMS, SBOM/build manifest, PyInstaller frozen-app guardrails, and update-download compatibility with `/api/update-download`.
- Emergency guidance: medical, wild food, CBRN, nuclear, and local-AI workflows need source/review signals and printable fallbacks. Community and competitor signal supports digital tools only when they degrade safely and do not replace analog skills.

## Rejected Ideas

- Default cloud accounts/sync: conflicts with the local-first privacy promise; any future sync should remain explicit, LAN/removable-media aware, and optional.
- Native mobile rewrite now: competitor signal supports mobile field use, but current value is better served by narrow-viewport and no-network gates in the existing app.
- AI diagnosis, plant identification, or medication substitution recommendations: high-risk and liability-heavy unless constrained to reviewed references, citations, and non-diagnostic workflow support.
- Arbitrary plugin execution without permission enforcement: Open WebUI-style tools are useful, but Field Desk should finish manifest, route-prefix, and role policy boundaries first.
- A full offline installer ISO before lifecycle controls: large bundled media is attractive, but storage relocation, content cataloging, checksum verification, and diagnostics should land first.
- Reintroducing GitHub Actions for releases: conflicts with repo policy and the latest commit direction; build/test/release automation should be local.

## Sources

### Project and Upstream

- https://github.com/Crosstalk-Solutions/project-nomad
- https://github.com/Crosstalk-Solutions/project-nomad/issues/883
- https://github.com/Crosstalk-Solutions/project-nomad/issues/933
- https://github.com/Crosstalk-Solutions/project-nomad/issues/947

### Competitors and Adjacent Products

- https://www.hazadapt.com/our-products/hazard-guide
- https://www.redcross.org/get-help/how-to-prepare-for-emergencies/mobile-apps.html
- https://sahanafoundation.org/
- https://www.ushahidi.com/
- https://grocy.info/
- https://docs.mealie.io/documentation/getting-started/features/
- https://homebox.software/
- https://www.home-assistant.io/blog/2025/01/03/3-2-1-backup/

### Offline Knowledge and RAG

- https://qdrant.tech/documentation/search/hybrid-queries/
- https://qdrant.tech/course/essentials/day-3/sparse-retrieval-demo/
- https://docs.ollama.com/capabilities/structured-outputs
- https://docs.openwebui.com/features/workspace/knowledge/
- https://github.com/alexanderop/awesome-local-first
- https://github.com/DisasterTechCrew/awesome-disastertech

### Standards, Platform, and Security

- https://www.fema.gov/emergency-managers/practitioners/integrated-public-alert-warning-system/technology-developers/all-hazards-information-feed
- https://www.weather.gov/documentation/services-web-alerts
- https://docs.oasis-open.org/emergency/cap/v1.2/CAP-v1.2-os.html
- https://nodejs.org/en/about/previous-releases
- https://pywebview.flowrl.com/blog/pywebview6
- https://maplibre.org/news/
- https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html
- https://flask.palletsprojects.com/en/stable/changes/
- https://pillow.readthedocs.io/en/latest/releasenotes/12.2.0.html

### Community Signal

- https://www.reddit.com/r/preppers/comments/1iwyimu/calling_all_preppers_lets_build_the_ultimate/
- https://www.reddit.com/r/preppers/comments/1h0hrmf/prepping_tech_what_digital_tools_could_solve_your/
- https://www.reddit.com/r/preppers/comments/1s8rnuo/informational_sheets/

## Open Questions

- Which artifacts are official for the next local release: portable Windows exe, Inno installer, Linux binary, AppImage, macOS binary, or a smaller subset?
- Should CAP/IPAWS work consume only public feeds first, or should it support authenticated IPAWS/COG workflows later?
- Which high-risk guide sources count as reviewed/trusted for medical, foraging, CBRN, nuclear, and AI-assisted emergency guidance?
