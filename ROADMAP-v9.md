# Project N.O.M.A.D. — Implementation Roadmap v9

> **Baseline:** v7.32.0 (775 tests, 600+ API routes, 95+ DB tables, 61 blueprints)
> **Generated:** 2026-04-17
> **Supersedes:** `ROADMAP-v8.md` (stale — phases 1-4/7 are partially built as blueprint stubs; see `ROADMAP-COMPLETED.md` for shipped work)
> **Source:** external research survey (Tier A/B/C from 2026-04-17 synthesis) + internal gap audit (integration, data, UX, plugin, build, testing)
> **Structure:** 50 tiers (A-AX), 333 phases, each independently shippable. Research complete through v9.3 — see version log + open queries at bottom.

---

## How to Read This Document

- **Effort:** S (1 session) / M (2-3) / L (4-6) / XL (7+)
- **Depends on:** other phases that must ship first, OR `—` for independent
- **New Tables / Routes:** rough estimate driving `db.py` + blueprint work
- **Inspiration:** the upstream open-source project the idea is drawn from, when applicable
- **Deliverables** are checkboxed for tracking

---

## Dependency Graph

```
Tier A — Foundation unlocks (ship first)
========================================
  Phase A1: USDA FoodData + FoodKeeper bundling
      |
      +---> Phase A2: Consumption profiles + person-days calculator
      |         |
      |         +---> Phase A3: AI RAG scope manager (benefits from wider data reach)
      |
      +---> Phase A4: Evacuation orchestration workflow
                   (depends on fuel/loadouts/contacts already shipped)

  Phase A5: Offline turn-by-turn routing (Valhalla/OSRM)
           — standalone, biggest visible win

Tier B — High differentiation (ship next)
=========================================
  Phase B1: Reticulum / LXMF transport
  Phase B2: SDR sidecar service (ADS-B / AIS / SAME)
  Phase B3: Shamir Secret Sharing vault
  Phase B4: Warrant canary + dead-man's switch
  Phase B5: Node-RED-style flow editor on Alert Rules

Tier C — Polish / ecosystem completion
======================================
  Phase C1: ICS-309 comms log auto-generator
  Phase C2: Codeplug builder with per-radio zones
  Phase C3: Propagation-aware HF scheduler
  Phase C4: Perceptual-hash + C2PA on OSINT images
  Phase C5: Rainwater catchment calculator
  Phase C6: Plugin API upgrade + scaffold generator
  Phase C7: Mobile PWA → functional offline sync
  Phase C8: First-run regional profile wizard

Tier D — Continued research (appended as agents return)
======================================================
  (see bottom of file)
```

---

## Tier A — Foundation unlocks

These four phases close the biggest gaps between what the codebase *claims* to support and what it *does* support. Ship them first; everything downstream benefits.

---

### Phase A1: USDA FoodData + FoodKeeper bundling
**Theme:** Wire the nutritional columns that already exist in the `inventory` schema to real data.
**Effort:** M
**Depends on:** —
**Inspiration:** USDA FoodData Central SR Legacy, USDA FoodKeeper app

#### Deliverables
- [ ] Bundle SR Legacy (~25 MB compressed, 7,793 foods × 150 nutrients) as a Tier 1 data pack
- [ ] Bundle FoodKeeper (~500 KB) — pantry/fridge/freezer TTL by storage method
- [ ] New tables: `nutrition_foods`, `nutrition_nutrients`, `foodkeeper_entries`
- [ ] Routes: `/api/nutrition/search`, `/api/nutrition/lookup/<fdc_id>`, `/api/nutrition/link` (attach `fdc_id` to an inventory row)
- [ ] Inventory form: "Link to USDA" search-picker that populates calories/macros/micros
- [ ] Inventory list: storage-method dropdown (pantry/fridge/freezer/cold-storage) → dynamic expiration badge based on FoodKeeper instead of static `expires` column
- [ ] Micronutrient column on inventory (auto-derived)

| New Tables | New Routes | Data Packs |
|---|---|---|
| 3 | 6 | SR Legacy, FoodKeeper |

---

### Phase A2: Consumption profiles + person-days calculator
**Theme:** "How many days can my family eat?" — the single most-asked prepper question, currently unanswerable.
**Effort:** M
**Depends on:** A1

#### Deliverables
- [ ] `consumption_profiles` table — adult_active / adult_sedentary / child_age / infant / elderly, calories_day, water_gal_day, protein_g_day
- [ ] `household_members` table — links profile to household (age, activity, restrictions JSON)
- [ ] `/api/household/person-days` — sums inventory nutrition ÷ household burn
- [ ] Home dashboard widget: "23 days of food · 14 days of water · 9 days protein-adequate"
- [ ] Micronutrient deficiency timeline (traffic-light per vitamin/mineral)
- [ ] "What-if" simulator: add N people, change activity level, recalculate
- [ ] Per-person restrictions flagged against inventory (gluten / dairy / nut / pork / halal / kosher / vegan)

| New Tables | New Routes | Data Packs |
|---|---|---|
| 2 | 5 | — (uses A1) |

---

### Phase A3: AI RAG scope manager  ✅ SHIPPED v7.33.0
**Theme:** Unlock the 80+ tables the LLM can't currently see.
**Effort:** S
**Depends on:** —

#### Deliverables
- [x] Replace hardcoded context-builder in `ai.py::build_situation_context()` with scope-driven registry
- [x] `rag_scope` table — table_name, label, enabled, weight, max_rows, formatter, columns_json, source
- [x] Settings UI: compact card with per-row enable/weight/max-rows + Reset + Preview
- [x] `/api/ai/rag/preview` — shows exact injected payload for debugging (detail_level=full|summary)
- [x] Default scope config seeded: 10 builtins (enabled) + 15 extended tables (disabled, opt-in)
- [ ] "Add my own documents" — file upload → Qdrant embed → RAG context **(deferred — existing KB module already covers this via /api/ai/chat `knowledge_base: true`; a future pass could unify the UX)**

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 4 | — |

---

### Phase A4: Evacuation orchestration workflow
**Theme:** Evacuation plans are records today; they should be an action.
**Effort:** L
**Depends on:** A1-A2 (for supply validation)

#### Deliverables
- [ ] `/api/emergency/evac-plans/<id>/activate` pre-flight check runs:
  - Fuel: sum tank_gal across `vehicles` vs route distance × mpg
  - Supplies: person-days threshold (default 3) met from Phase A2
  - Loadouts: all assigned BOBs marked `packed` and within 24h of last inspect
  - Contacts: rally-point contact list notified via LAN/federation/SSE
  - Water: per-person × household × days of travel
- [ ] Pre-flight produces a **go/no-go report** with specific gaps ("short 4 gal fuel for Route A, switch to Route B")
- [ ] On confirmed activate: create incident, spawn checklist from plan timeline, broadcast SSE, flip `is_active=1`, enter emergency mode
- [ ] `evacuation_activation_log` for post-action review
- [ ] Rally-point reachability map layer (isochrone from current fuel + bag weight + mode)

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 4 | — |

---

### Phase A5: Offline turn-by-turn routing (Valhalla)
**Theme:** Ship the biggest missing feature vs. OsmAnd/Organic Maps.
**Effort:** L
**Depends on:** —
**Inspiration:** Valhalla, OSRM, GraphHopper

#### Deliverables
- [ ] Bundle Valhalla (or OSRM) as an optional service in `services/` — downloaded per-region (US continental ~8 GB, per-state ~100-500 MB)
- [ ] Tile-pack manager UI — same pattern as existing Kiwix ZIM tier selector
- [ ] `/api/routing/route?from=&to=&costing=auto|bicycle|pedestrian|truck` — standard Valhalla response
- [ ] Map tab: turn-by-turn panel with voice cues via Web Speech API
- [ ] Route profile: avoid highways / avoid tolls / max_gradient / max_width (for trucks/RVs)
- [ ] Integration: evacuation plans use routing API for ETA + fuel math
- [ ] Integration: waypoint list → optimized traveling-salesman route

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 (routing_packs) | 5 | Valhalla regional tiles |

---

## Tier B — High differentiation

Novel features with no meaningful open-source competitor in the prepper space. These are what would make NOMAD stand alone.

---

### Phase B1: Reticulum / LXMF transport
**Theme:** Mesh without IP. Drop the internet dependency for two-node federation.
**Effort:** L
**Depends on:** —
**Inspiration:** Reticulum Network Stack, NomadNet, Sideband

#### Deliverables
- [ ] Add `rnsd` as optional managed service (Python daemon, LoRa/HF/serial interfaces)
- [ ] New `federation_transport` column on `federation_peers` — `ip` | `rns` | `both`
- [ ] LXMF encoder/decoder for existing federation sync payload
- [ ] LAN chat routing layer picks transport based on peer capability
- [ ] Dead-drop messages can be delivered over RNS instead of USB
- [ ] Status panel: transport health per interface (LoRa beacon rate, HF packet loss)

| New Tables | New Routes | Data Packs |
|---|---|---|
| 2 | 6 | — |

---

### Phase B2: SDR sidecar service
**Theme:** Local RTL-SDR ingest so Situation Room keeps working when the internet dies.
**Effort:** L
**Depends on:** —
**Inspiration:** dump1090 (ADS-B), rtl_ais, multimon-ng (SAME), rtl_433 (ISM sensors)

#### Deliverables
- [ ] New managed service `services/sdr.py` — spawns configured decoders as subprocesses
- [ ] Decoder plugins: ADS-B (aircraft), AIS (ships), NOAA SAME weather alerts, rtl_433 (home weather/temp sensors), Meshtastic (via rtl-lora), APRS
- [ ] `/api/sdr/status`, `/api/sdr/start/<decoder>`, `/api/sdr/stop/<decoder>`
- [ ] Decoder output → Situation Room map layers (replaces internet feeds when both available, uses whichever is fresher)
- [ ] `sdr_captures` table — raw decoded messages for AAR
- [ ] Auto-detect connected RTL-SDR devices via `lsusb`/`rtl_test`

| New Tables | New Routes | Data Packs |
|---|---|---|
| 2 | 8 | — |

---

### Phase B3: Shamir Secret Sharing vault
**Theme:** Distributed inheritance — split vault master key across trusted peers or printed QR shards.
**Effort:** M
**Depends on:** —
**Inspiration:** hashicorp/vault Shamir unseal, ssss-cli

#### Deliverables
- [ ] `shamir_shares` table — share_id, threshold, total_shares, peer_id (nullable), qr_printed_at
- [ ] `/api/vault/shamir/split` — generate N shares, threshold K; delete master from memory
- [ ] `/api/vault/shamir/distribute` — push shares to trusted federation peers
- [ ] `/api/vault/shamir/print` — generate printable QR share cards (lamination-ready)
- [ ] `/api/vault/shamir/recover` — collect K shares from peers/scanned QRs, reconstitute master
- [ ] Scheme default: 3-of-5 for family, 5-of-9 for pod

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 5 | — |

---

### Phase B4: Warrant canary + dead-man's switch
**Theme:** Scheduled "prove I'm alive." Missed check-ins trigger real consequences.
**Effort:** M
**Depends on:** B3 (for Shamir-share release)
**Inspiration:** deadmansswitch.com (pattern, not code), canary-watch

#### Deliverables
- [ ] `deadman_policies` table — name, check_in_interval, grace_period, escalation JSON
- [ ] Policy actions: publish signed canary statement; release Shamir share to named peer; wipe encrypted vault; broadcast federation alert; email dead-drop USB payload
- [ ] `/api/deadman/checkin` — heartbeat; resets timer
- [ ] Background worker evaluates missed check-ins; cascades through escalation stages
- [ ] Signed canary output: Ed25519-signed JSON with timestamp, policy name, status
- [ ] UI: clear visualization of next check-in deadline; one-click extend

| New Tables | New Routes | Data Packs |
|---|---|---|
| 2 | 5 | — |

---

### Phase B5: Node-RED-style flow editor for Alert Rules
**Theme:** The rules engine already stores JSON; give users a canvas.
**Effort:** M
**Depends on:** —
**Inspiration:** Node-RED, ThingsBoard rule chains, Drawflow, Rete.js

#### Deliverables
- [ ] Bundle Drawflow or Rete.js (bundled locally, no CDN)
- [ ] New `alert_rule_flows` table — rule_id, flow JSON (nodes + edges)
- [ ] Node catalog: sensor trigger, time trigger, inventory-compare, weather-compare, logic (AND/OR/NOT), action (SSE, incident, checklist, federation broadcast, task create)
- [ ] Flow → existing `alert_rules` JSON compiler; reversible round-trip
- [ ] "Test flow" simulator that fires a synthetic event through the graph
- [ ] 5 canned templates: Hurricane Watch, Low Fuel Escalation, Medical Expiring, Threat Level Elevation, Peer Went Dark

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 4 | — |

---

## Tier C — Polish / ecosystem completion

Each item stands alone as a marquee feature for a minor release.

---

### Phase C1: ICS-309 comms log auto-generator  ✅ SHIPPED v7.34.0
**Theme:** ARES/RACES deployments require 309; NOMAD has everything needed to compose it.
**Effort:** S
**Depends on:** —
**Inspiration:** FEMA ICS-309, Winlink ecosystem

#### Deliverables
- [x] `/api/print/ics-309` — chronological log merging comms_log + lan_messages + mesh_messages within date range (default 24h UTC)
- [x] Printable HTML + PDF (via ReportLab) in standard ICS-309 layout
- [x] Filter by incident name, radio operator callsign, station ID; JSON response for programmatic use
- [x] Print buttons wired into Settings print panel (both HTML + PDF)
- [ ] Appended to operations binder as an optional section **(deferred — standalone route surfaces the same data; a future pass can embed it)**

| New Routes | Data Packs |
|---|---|
| 2 | — |

---

### Phase C2: Codeplug builder with per-radio zones
**Theme:** Beat CHIRP's flat CSV with a real codeplug editor.
**Effort:** M
**Depends on:** —
**Inspiration:** CHIRP, RT Systems, DMRconfig

#### Deliverables
- [ ] `radio_models` table — manufacturer, model, channel_count, zone_support, dmr_support, max_freq_ranges JSON
- [ ] `codeplugs` table — name, radio_model, zones JSON, channels JSON, scan_lists JSON
- [ ] UI: per-zone channel picker from `freq_database`; TX-block toggle; CTCSS/DCS selector
- [ ] Legality flags: Part 90 / Part 95 / Part 97 per channel
- [ ] Export: CHIRP CSV (existing), DMRconfig JSON, RT Systems XML
- [ ] Seed with 10 common radios: Baofeng UV-5R, BF-F8HP, Tidradio TD-H3, AnyTone 878, Retevis RT-97, Yaesu FT-60R, Icom IC-705, Kenwood TK-3170, Motorola GM300, Wouxun KG-UV9D

| New Tables | New Routes | Data Packs |
|---|---|---|
| 2 | 6 | Radio-model reference |

---

### Phase C3: Propagation-aware HF scheduler
**Theme:** Turn HF email from guess-and-check into a daily brief line.
**Effort:** M
**Depends on:** —
**Inspiration:** VOACAP, Pyhamtools, DX propagation tools

#### Deliverables
- [ ] Ingest NOAA SWPC solar indices (SFI, K, A, sunspot number) — cached for offline
- [ ] VOACAP binary (or pure-Python reimpl) bundled; takes my_lat/lng + their_lat/lng + freq + hour → MUF/LUF/SNR prediction
- [ ] `/api/hf/recommend?peer_id=` — returns ranked bands/times for next 24h with reliability %
- [ ] Daily brief card: "Best contact window with Ridgepeak pod: 14:00-16:00 local on 14.340 MHz (89% reliability)"
- [ ] Comms plan PACE tier 3 auto-populated with recommended HF windows

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 3 | VOACAP binary + SWPC cache |

---

### Phase C4: Perceptual-hash + C2PA on OSINT images
**Theme:** 43 Telegram channels + GDELT → stale/reused/deepfake media is the real threat.
**Effort:** S
**Depends on:** —
**Inspiration:** imagehash (pHash/dHash), c2pa-python, Adobe CAI

#### Deliverables
- [ ] On OSINT image ingest: compute pHash + dHash, check against prior corpus
- [ ] Badge on repeated images: "Seen 4 times since 2024-10-03 — earliest: Syria feed"
- [ ] C2PA signature check: green badge if signed & chain valid; amber if unsigned; red if tampered
- [ ] `osint_image_hashes` table (fast Hamming lookup via SQLite BK-tree extension or in-memory index)
- [ ] Situation Room news cards show badges inline

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 2 | — |

---

### Phase C5: Rainwater catchment calculator
**Theme:** Top-five homestead planning question that's nowhere in the 41 calculators.
**Effort:** S
**Depends on:** —
**Inspiration:** rainwaterharvestingcalc patterns, TWDB manuals, ARCSA

#### Deliverables
- [ ] `/api/calc/rainwater` — inputs: roof_sqft, roof_material (asphalt/metal/tile/green), monthly rainfall inches (from PRISM cache or manual entry), first-flush cutoff gal
- [ ] Output: gal/year, gal/month chart, cistern sizing recommendation (N-day drought buffer), overflow rate
- [ ] Bundle PRISM 30-year-normal monthly rainfall by county (~10 MB)
- [ ] Tools tab calculator card; link into `water_mgmt` module so recommended cistern size pre-fills there

| New Tables | New Routes | Data Packs |
|---|---|---|
| — | 2 | PRISM 30-yr normals |

---

### Phase C6: Plugin API upgrade + scaffold generator
**Theme:** `plugins/` loader exists but plugins are toys. Give them the surface the core uses.
**Effort:** M
**Depends on:** —

#### Deliverables
- [ ] Plugin base class with hooks: `register_blueprint`, `register_rag_table`, `register_alert_action`, `register_calculator`, `register_checklist_template`, `register_activity_logger`, `register_db_migration`
- [ ] Plugin manifest schema (`plugin.json`): name, version, author, permissions, required_nomad_version
- [ ] Permission system: plugins declare data access scope (read-inventory, write-activity-log, etc.)
- [ ] `tools/new_plugin.py` scaffold generator
- [ ] `/api/plugins/catalog` — curated online directory (opt-in, GitHub-hosted index)
- [ ] Three reference plugins: "Ham Exam Spaced Repetition", "Beekeeping Log", "Hurricane Prep Checklist Pack"
- [ ] Plugin test harness in `tests/plugins/`

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 | 4 | — |

---

### Phase C7: Mobile PWA → functional offline sync
**Theme:** Manifest + SW exist, sync and bottom-nav are CSS-only shells today.
**Effort:** L
**Depends on:** —

#### Deliverables
- [ ] Full IndexedDB snapshot of: inventory, contacts, patients, waypoints, checklists, freq_database, household, loadouts
- [ ] Delta sync: `/api/offline/changes-since?ts=` (already exists — harden it + add 10 more tables)
- [ ] Write queue: mutations while offline → replayed on reconnect with conflict prompt
- [ ] Mobile-first re-layout of the 5 most-used tabs (Home, Prep, Maps, AI, More)
- [ ] Bottom-nav wired to actual tab switcher, not just CSS
- [ ] Background sync via Service Worker `sync` event
- [ ] Camera permission flow for barcode/vision-inventory/wound-photo on mobile
- [ ] GPS continuous tracking option (for field movement)

| New Tables | New Routes | Data Packs |
|---|---|---|
| 1 (sync_queue) | 4 | — |

---

### Phase C8: First-run regional profile wizard
**Theme:** Wizard only hits Services today; capture location + household on day 1 so everything downstream personalizes.
**Effort:** S
**Depends on:** —

#### Deliverables
- [ ] Multi-step wizard (reuses shell from existing first-run): location → household composition → dietary restrictions → top threats (auto-ranked from FEMA NRI) → service preferences → theme
- [ ] Persists to `regional_profile` + `household_members` (from Phase A2)
- [ ] Readiness score weighted by regional threats (coastal FL: hurricane × 2; Tornado Alley: tornado × 2; CA: earthquake × 2; NE: ice storm × 2)
- [ ] Regional checklists auto-surfaced on Readiness tab
- [ ] Regional weather station auto-configured (nearest NWS AWOS/ASOS)
- [ ] Tour step 1 explains the personalization and offers "skip and set later"

| New Tables | New Routes | Data Packs |
|---|---|---|
| — | 3 | FEMA NRI (20 MB) |

---

## Tier D — Field Operations

Tactical civilian, SAR, overland, maritime, aviation. Most items are standalone S/M phases.

### Phase D1: ICS-205/205A comms plan auto-builder
**Effort:** S · **Depends on:** C1, C2 · **Inspiration:** NIFC e-ICS, FEMA ICS forms
- [ ] `/api/print/ics-205` — incident radio comms plan with frequency assignments per net/function/team
- [ ] Generates from codeplug (C2) + assignment roster + incident record
- [ ] 205A (Communications List) populated from `contacts` + `freq_database`
- [ ] Appended to operations binder as optional section

### Phase D2: Hasty search probability grid (Koester ISRID)
**Effort:** M · **Depends on:** A5 · **Inspiration:** SARTopo, MapSAR, Robert Koester's *Lost Person Behavior*
- [ ] Bundle ISRID lost-person-behavior profiles (hiker, hunter, child-1-3/4-6/7-12, dementia, despondent, ATV, etc.) — distance statistics per terrain class
- [ ] `/api/sar/probability-grid?lpc=hiker&ipp=lat,lng&terrain=mountain` → GeoJSON 25-50-75-95% radius rings
- [ ] Segment decomposition with PoD × PoA weighting; mark segments searched + update residual PoS
- [ ] New tables: `sar_operations`, `sar_segments`, `sar_behavior_profiles`

### Phase D3: Clue log + containment tracker
**Effort:** S · **Depends on:** D2 · **Inspiration:** SARCOP, D4H
- [ ] `sar_clues` table — geotagged, timestamp, tier (definite/possible/dismissed), confidence, finder, photo_path
- [ ] Containment segments: ridges/roads/rivers with patrol state (covered/leaking/unassigned)
- [ ] Auto-regenerate probability grid as clues tier up or down
- [ ] Print the clue log as a post-op attachment

### Phase D4: Overland tire pressure + payload advisor
**Effort:** S · **Depends on:** — · **Inspiration:** OnX Offroad forums, Overland Bound, Toyo/BFG load tables
- [ ] `/api/calc/tire-pressure` — inputs: tire spec (LT size, load range), axle load, altitude, surface (highway/gravel/sand/rock), temperature
- [ ] Output: cold PSI recommendation with source chart citation
- [ ] Linked to `vehicles` — saved recipe per vehicle/trailer/load config

### Phase D5: Terrain-cost range rings
**Effort:** M · **Depends on:** A5 · **Inspiration:** Gaia GPS "plan" mode
- [ ] Replace naive straight-line range rings with isochrones weighted by elevation gain, surface type, vehicle class
- [ ] Uses Valhalla costing model under the hood (from A5)
- [ ] Fuel-based ring + water-based ring overlay
- [ ] Integrated into the evacuation orchestration (A4) rally-point-reachability layer

### Phase D6: iOverlander + community POI ingest
**Effort:** S · **Depends on:** — · **Inspiration:** iOverlander GeoJSON, OpenCampingMap
- [ ] Import ingester accepts iOverlander JSON dump, OpenCampingMap, OSM Overpass POI queries (camps, water, dump stations, mechanics, free showers)
- [ ] New waypoint category set (+60 icons)
- [ ] Conflict resolution against existing waypoints via proximity + name match
- [ ] Quarterly refresh via optional online sync

### Phase D7: Maritime — tide + current predictor (XTide)
**Effort:** M · **Depends on:** — · **Inspiration:** XTide, OpenCPN, WxTide
- [ ] Bundle NOAA harmonic constants for 3,000+ US stations (~15 MB)
- [ ] Pure-math tide prediction (no internet) via harmonic synthesis
- [ ] `/api/maritime/tides?station=&from=&to=` — tidal curve + high/low table
- [ ] Map layer: selected station's current tide/current with arrow overlay
- [ ] Printable daily tide card for field ops

### Phase D8: Aviation — density altitude + takeoff distance
**Effort:** S · **Depends on:** — · **Inspiration:** ForeFlight, CAVU, POH charts
- [ ] Calculator: pressure altitude → density altitude from temp/humidity
- [ ] Takeoff + landing distance multipliers per common GA aircraft (C172, PA28, CTLS, RV-series) — tabular data from POH excerpts
- [ ] Backcountry strip database (seed with 150+ US public airstrips) linked to waypoints
- [ ] Useful for drone-ops ceiling too

### Phase D9: AIS/ADS-B deconfliction view
**Effort:** S · **Depends on:** B2 · **Inspiration:** OpenCPN, Virtual Radar Server
- [ ] Merged "moving-contacts" map layer with AIS + ADS-B + APRS + Meshtastic positions on one plot
- [ ] CPA/TCPA (closest point of approach / time) alerting against self-position
- [ ] Contact details panel with track history + vector

---

## Tier E — Specialized Threats

CBRN, alpine, LE/forensics, threat intel.

### Phase E1: Gaussian plume estimator (ALOHA-style)
**Effort:** M · **Depends on:** — · **Inspiration:** ALOHA (public domain), HPAC, EPA CAMEO
- [ ] Pure-math Gaussian plume with Pasquill-Gifford stability class + local wind speed/direction
- [ ] Chemical library seeded with NIOSH IDLH top-200 industrial chemicals (molecular weight, vapor pressure, IDLH/TEEL thresholds)
- [ ] Output: footprint GeoJSON with red/orange/yellow contours (lethal / serious-injury / PPE-threshold)
- [ ] Map overlay at threat location; integration with emergency-mode to trigger shelter-in-place vs. evacuate recommendation
- [ ] New tables: `plume_scenarios`, `chemical_library`

### Phase E2: Household epi line list + Rt tracker
**Effort:** S · **Depends on:** — · **Inspiration:** EpiCollect, CDC FluView, ProMED
- [ ] `epi_cases` table — household member, onset_date, symptoms JSON, severity, recovery, exposure_source
- [ ] Rolling Rt (effective reproduction number) per household/pod (Cori method)
- [ ] ILI/CLI trend chart in Situation Room when cases present
- [ ] Isolation / quarantine countdown per case with CDC-standard timing

### Phase E3: Avalanche ATES + elevation-banded weather
**Effort:** M · **Depends on:** A5 · **Inspiration:** Avalanche Canada, CalTopo slope-angle shading, Mountain-Forecast
- [ ] Slope-angle shading layer from DEM (already possible with contour data from v5.2)
- [ ] ATES classification (simple / challenging / complex) auto-derived from slope + aspect + terrain trap flags
- [ ] Lapse-rate weather synthesis: surface forecast + per-1000ft-band temperature, precip, wind
- [ ] Avalanche bulletin composer with hazard rose (NASC 5-level scale)

### Phase E4: Chain-of-custody evidence ledger
**Effort:** M · **Depends on:** — · **Inspiration:** Autopsy, CopBook, ISO/IEC 17025
- [ ] `evidence_items` table — tag_id, type, capture_time, capture_location_waypoint_id, sha256_hash, c2pa_chain, photo_paths JSON
- [ ] `custody_transfers` table — from_party, to_party, signature_png, notes
- [ ] Hash-chained log (each entry signed against prior) for tamper detection
- [ ] Printable transfer form + sealed-bag QR
- [ ] C2PA binding (ties into C4)

### Phase E5: MISP-lite IOC ingest + ATT&CK mapping
**Effort:** M · **Depends on:** — · **Inspiration:** MISP, STIX/TAXII 2.1, MITRE ATT&CK Navigator
- [ ] STIX 2.1 bundle ingester — feed URLs configured, scheduled pulls
- [ ] Local IOC store: domains, IPs, file-hashes, YARA rules
- [ ] Alert on matches observed in local firewall logs, DNS queries (if imported), or manually checked
- [ ] Civilian ATT&CK playbook: map observed anomaly → technique → home-network mitigations

---

## Tier F — Infrastructure Awareness

### Phase F1: Grid outage correlator
**Effort:** S · **Depends on:** — · **Inspiration:** poweroutage.us, OSM Power
- [ ] Scheduled scrape of poweroutage.us county-level CSV (when online)
- [ ] Cross-reference against federation peer locations + home county
- [ ] Map layer: outage severity by county with trend arrows
- [ ] Alert differentiates "just you" from "regional event" — changes the response calculus

### Phase F2: LibreTime-style broadcast scheduler
**Effort:** M · **Depends on:** B1, B2 · **Inspiration:** LibreTime, icecast
- [ ] Playlist + rotation schedule for: scheduled SITREPs on FRS/GMRS repeaters, shortwave listening alerts, automated station-ID timer, Meshtastic broadcast digest
- [ ] Audio recording bank (WAV/MP3) with metadata
- [ ] Run-time: cron-driven triggers play clips via configured output (USB soundcard → radio mic input)
- [ ] Useful for neighborhood information station during multi-day events

---

## Tier G — Homestead Depth

Calculators and trackers for the off-grid lifestyle that NOMAD already indexes but doesn't compute.

### Phase G1: Greywater branched-drain designer
**Effort:** S · **Depends on:** — · **Inspiration:** Art Ludwig's *Create an Oasis with Greywater* (CC), oasisdesign.net
- [ ] Branched-drain calculator: source fixture flow → 1-2-4-8 split geometry, pipe slope, mulch-basin sizing
- [ ] Per-plant mulch-basin demand table (fruit tree 20-50 gal/week, etc.)
- [ ] Printable schematic with dimensions

### Phase G2: Humanure thermophilic tracker
**Effort:** S · **Depends on:** — · **Inspiration:** Jenkins *Humanure Handbook* (CC-licensed)
- [ ] `humanure_piles` table — start_date, temp_log, turn_events, cure_until
- [ ] Temperature threshold alerts (must hit 55°C/131°F for pathogen kill)
- [ ] 12-month cure countdown before use on food crops

### Phase G3: Septic + perc-test logger
**Effort:** S · **Depends on:** — · **Inspiration:** EPA 625/R-00/008 onsite manual
- [ ] Perc-test time per hole logged; drainfield sizing from soil group
- [ ] Tank pumping alert by (occupants × days × gal_per_day) model
- [ ] Leach-field loading rate per soil type reference

### Phase G4: Wood BTU + cord ledger
**Effort:** S · **Depends on:** — · **Inspiration:** USFS FPL-RN-0229
- [ ] `wood_stockpile` table — species, cords, split_date, moisture_meter_pct, seasoning_target
- [ ] BTU/cord seeded for 30+ species
- [ ] Heating-degree-day math: "18 cords serves a 2000 sqft cabin in zone 5 for 180 days"
- [ ] Stove derating by efficiency rating

### Phase G5: Passive solar sun-path plotter
**Effort:** S · **Depends on:** — · **Inspiration:** SunCalc OSS, Mazria *Passive Solar Energy Book*
- [ ] Lat/lon-driven sun-angle table per month
- [ ] Overhang calculator: given window height + latitude, size overhang for summer shade / winter gain
- [ ] Glazing-to-floor-area ratio by climate zone
- [ ] SVG sun-path diagram printable

### Phase G6: Battery bank cycle-life model
**Effort:** M · **Depends on:** — · **Inspiration:** Battery University, OpenEnergyMonitor
- [ ] Chemistry library: FLA, AGM, Gel, LiFePO4, Ni-Fe, vanadium flow — DoD vs cycle curves
- [ ] `battery_banks` table — chemistry, capacity_kWh, install_date, cycles_logged, SoH_pct
- [ ] SoH (state-of-health) projection graph; end-of-life forecast
- [ ] C-rate derating — realistic usable capacity at mission discharge rates

### Phase G7: Food preservation safety math (cure, ferment, grain)
**Effort:** M · **Depends on:** — · **Inspiration:** Rytek Kutas, Marianski, Sandor Katz, BYU food-storage extension
- [ ] Nitrite cure calculator (Prague #1/#2, celery equiv) with botulism-margin check by meat weight
- [ ] Sourdough + kraut/kimchi/kombucha ferment timelines at temp; pH gate guidance
- [ ] Grain storage O2-absorber sizer (mylar/bucket volume → cc absorbers + nitrogen-flush option); shelf-life by moisture%
- [ ] All three are safety-critical — current preservation module is date-tracking only

### Phase G8: SSURGO soil profile cache
**Effort:** M · **Depends on:** — · **Inspiration:** USDA Web Soil Survey, SoilWeb OSS
- [ ] Bundle SSURGO tiles for saved parcels — drainage class, Available Water Capacity, slope, flood frequency
- [ ] Offline soil-report PDF generator per waypoint
- [ ] Garden module integration: suggest amendments from soil type

### Phase G9: Seed-saving isolation distance planner
**Effort:** S · **Depends on:** — · **Inspiration:** Seed Savers Exchange, Suzanne Ashworth *Seed to Seed*
- [ ] Per-species isolation distance reference (corn 1mi, brassicas 800ft, squash 1mi or bag)
- [ ] Map-aware planner: warn when two incompatible crops are within isolation distance
- [ ] Alternative strategies catalog (timing isolation, bagging, caging)

### Phase G10: Beekeeping varroa calendar
**Effort:** S · **Depends on:** — · **Inspiration:** HoneyBeeHealthCoalition *Tools for Varroa Management*
- [ ] `hives` table — queen date, varroa counts per sugar-roll, treatments log
- [ ] Climate-zone-specific treatment calendar (OA dribble, OA vapor, formic, apivar)
- [ ] Brood-break timing alerts
- [ ] Queen-rearing calendar for pod-scale apiary

### Phase G11: Livestock drug + withdrawal timer
**Effort:** S · **Depends on:** — · **Inspiration:** FARAD database, Merck Vet Manual
- [ ] Weight-based dose calculator for common livestock meds (penicillin, LA-200, ivermectin, banamine, etc.)
- [ ] Milk/meat withdrawal countdown per drug/route
- [ ] Integration with existing livestock module; logs auto-create inventory checkout
- [ ] Prevents the #1 small-farm mistake — selling during withdrawal

### Phase G12: Pedigree + breeding cycle tracker
**Effort:** M · **Depends on:** — · **Inspiration:** FarmOS (weak here), ADGA/ABGA registries
- [ ] Family-tree schema per livestock animal; inbreeding coefficient check (Wright)
- [ ] Heat/gestation/lambing/kidding/farrowing calendars per species
- [ ] "Best pair" recommender for maintaining genetic diversity in closed herds

---

## Tier H — Health Depth

### Phase H1: Pediatric Broselow-equivalent dose engine
**Effort:** M · **Depends on:** — · **Inspiration:** Broselow tape, WHO IMCI, Harriet Lane
- [ ] Extend the 8-drug calculator to 40+ meds with weight+length dosing
- [ ] Concentration math (mg/mL → mL to administer)
- [ ] Age-banded red-flag vitals reference
- [ ] Printable wallet card per child in household

### Phase H2: Chronic condition grid-down playbooks
**Effort:** L · **Depends on:** — · **Inspiration:** MSF Clinical Guidelines (CC-BY-SA), Where There Is No Doctor
- [ ] Branching decision trees for: Type-1 diabetes (insulin rationing, DKA triage, ketone tracking), asthma (bottle spacer construction, rescue-med tapers), epilepsy (rescue med protocols, trigger logs), dialysis-skip contingency (low-K diet, fluid restriction), warfarin/coumadin without INR, Addison's crisis
- [ ] Per-household-member condition flags with personalized playbook surfacing
- [ ] Medication-ration calculator: "at current rate you have 14 days of insulin; stretching to 0.6× dose extends to 23 days with acceptable risk"

### Phase H3: Wilderness medicine decision trees
**Effort:** M · **Depends on:** — · **Inspiration:** NOLS WMI, Wilderness Medical Society practice guidelines
- [ ] WFR-protocol flowcharts: spine clearance, field anaphylaxis epi dosing, hypothermia rewarming gates, lightning triage (reverse triage), altitude illness (AMS/HACE/HAPE), drowning
- [ ] Tied into existing decision-guide framework

### Phase H4: Dental emergency pack
**Effort:** S · **Depends on:** — · **Inspiration:** Hesperian's *Where There Is No Dentist* (CC)
- [ ] Avulsed-tooth reimplant countdown timer (5-60 min matters)
- [ ] Temporary filling guide (IRM / zinc-oxide / clove oil)
- [ ] Abscess I&D safety decision tree
- [ ] Inventory template: dental field kit
- [ ] Dental is consistently cited as the #1 grid-down medical gap

### Phase H5: Equine + pet emergency triage
**Effort:** S · **Depends on:** — · **Inspiration:** Merck Vet Manual (free), AAEP colic scorecard
- [ ] Species-specific triage: dog hemorrhage pressure points, cat urinary blockage, horse colic scoring, tick ID cards, snakebite decision trees
- [ ] Pet evac kit inventory template
- [ ] Integrates with existing livestock schema for non-production animals

---

## Tier I — Community & Continuity

### Phase I1: Skill-transfer ledger
**Effort:** S · **Depends on:** — · **Inspiration:** Transition Towns, hOurworld time-bank
- [ ] `skills_offered` + `skills_sought` + `skill_transfer_log` tables
- [ ] Apprenticeship hour tracker (who's teaching whom, hours logged)
- [ ] Matrix view across federation pod: who covers what
- [ ] Auto-suggests pairings based on gaps + offers

### Phase I2: State-specific legal doc vault
**Effort:** M · **Depends on:** — · **Inspiration:** Nolo Press templates, state bar self-help forms
- [ ] Template library: living will, POA (general + healthcare), guardianship, custody contingency, small-claims, gun-trust (where legal)
- [ ] State-jurisdiction-aware: filter templates by user's state
- [ ] Fillable offline PDFs; encrypted storage in existing vault
- [ ] Renewal-date + witness-signature tracker

### Phase I3: Home funeral SOP + dignity-in-death toolkit
**Effort:** S · **Depends on:** — · **Inspiration:** National Home Funeral Alliance guides
- [ ] State-by-state home-burial legality reference
- [ ] Dry-ice cooling timing chart
- [ ] Body-care dignity checklist (positioning, washing, dressing)
- [ ] Paperwork reference (death certificate, disposition permit)
- [ ] Heavily requested and universally absent from prepper tooling

---

## Tier J — Psychosocial & Family Continuity

Trauma, grief, cohesion, reunification. Consistently the first thing that breaks in a sustained event; consistently ignored by prepper tooling.

### Phase J1: CISM debrief wizard
**Effort:** S · **Depends on:** — · **Inspiration:** ICISF Mitchell-model protocols
- [ ] Structured 7-phase debrief (intro / fact / thought / reaction / symptom / teaching / re-entry) with prompts for peer-support leads
- [ ] Session log tied to `incidents`; private per participant
- [ ] Printable facilitator card

### Phase J2: Grief protocol + age-banded explainer cards
**Effort:** S · **Depends on:** — · **Inspiration:** NCTSN Psychological First Aid, Sesame Workshop "Here for Each Other", FEMA Prepare with Pedro
- [ ] Age-banded (3-5 / 6-11 / 12-17 / adult) printable scripts for loss conversations
- [ ] Read-aloud mode for parents with low reading stamina under stress
- [ ] Disaster-type picker ("boil water order", "why we're leaving home", "where grandpa went")

### Phase J3: Sustained-ops sleep hygiene tracker
**Effort:** S · **Depends on:** — · **Inspiration:** USAF SOF fatigue countermeasures, Army FM 7-22
- [ ] Rotational sleep log with chronotype-aware shift builder (extends existing watch-rotation planner)
- [ ] Caffeine half-life overlay — "last coffee at 14:00, effective on sleep onset until 22:00"
- [ ] Fatigue decision-quality warning at 17h awake; forced-rest flag at 24h

### Phase J4: NCMEC-style child ID packet generator
**Effort:** S · **Depends on:** — · **Inspiration:** NCMEC standard child ID kit
- [ ] `child_id_packets` table linked to `household_members`
- [ ] Auto-builds PDF: current photo (quarterly refresh prompts), dental chart field, fingerprint template, identifying marks, scar/birthmark slots, last-seen-clothing slot
- [ ] Auto-alert at 6-month staleness
- [ ] Encrypted at rest; optional printed wallet copy

### Phase J5: Reunification cascade
**Effort:** S · **Depends on:** — · **Inspiration:** FEMA Family Communication Plan
- [ ] Rally-point tree: primary → secondary → tertiary → out-of-state contact
- [ ] Per-member wallet card generator with cascade
- [ ] School pickup cascade (authorized adults per child per school)
- [ ] Wired into evacuation orchestration (A4) — activation triggers cascade notification

### Phase J6: Homeschool curriculum tracker
**Effort:** M · **Depends on:** — · **Inspiration:** Ambleside Online, Khan Academy Offline, Classical Conversations
- [ ] Scope-and-sequence templates per curriculum + grade level
- [ ] Per-child progress checkboxes; lesson log
- [ ] Auto-schedule generator from lesson count × school-days-per-week
- [ ] Offline — no cloud dependency

### Phase J7: Age-appropriate chore + drill assignment board
**Effort:** S · **Depends on:** — · **Inspiration:** Montessori practical-life, BSA patrol method
- [ ] Task matrix (age band × task type) rotating weekly
- [ ] Drill rotation built-in: fire drill, bug-out bag check, comms check, water fill — whose week is it
- [ ] Household dashboard widget

---

## Tier K — Weather & Earth-Science Depth

### Phase K1: Skew-T / upper-air viewer (MetPy)
**Effort:** L · **Depends on:** — · **Inspiration:** MetPy, BUFKIT, RAOB
- [ ] Offline GRIB2 ingester for HRRR + GFS + RAP (scheduled when online)
- [ ] Skew-T log-P renderer with CAPE / CIN / LI / SHEAR auto-computed parcel lines
- [ ] Dewpoint/temp profile + wind barbs at 1000/850/700/500/300/200 mb
- [ ] Per-sounding interpretation snippets ("high CAPE low shear — pulse storms")
- [ ] Single biggest forecasting upgrade short of a full NWP suite

### Phase K2: Blitzortung lightning overlay (cached)
**Effort:** S · **Depends on:** — · **Inspiration:** Blitzortung.org community network
- [ ] 60-minute strike data pulls when online; decay-timer heatmap
- [ ] Alert on strikes within N miles within M minutes

### Phase K3: NWS Area Forecast Discussion parser
**Effort:** S · **Depends on:** — · **Inspiration:** NOAA AFD product
- [ ] Ingest AFD text; extract confidence language ("model uncertainty", "potent signal")
- [ ] Highlight forecaster caveats; diff today vs yesterday
- [ ] Briefing card surfaces the 3 key points automatically

### Phase K4: FARSITE-lite wildfire spread
**Effort:** M · **Depends on:** — · **Inspiration:** USFS BehavePlus / FARSITE (public domain)
- [ ] Rothermel surface-fire-behavior math
- [ ] Fuel-model picker (13 NFFL models); slope + wind inputs from local station
- [ ] Map overlay: 1/3/6/12/24h spread polygons from ignition point
- [ ] High-value in WUI households

---

## Tier L — Leadership & Decision Doctrine

### Phase L1: OODA loop tracker
**Effort:** S · **Depends on:** — · **Inspiration:** Boyd's OODA doctrine
- [ ] Timestamped Observe / Orient / Decide / Act journal per incident
- [ ] Loop-time analytics ("average OODA cycle 14 min, trending down")
- [ ] Used in post-event self-review

### Phase L2: AAR template engine (Army 4-question)
**Effort:** S · **Depends on:** — · **Inspiration:** TC 25-20
- [ ] 4-question AAR: what was planned / what happened / why / sustain-improve
- [ ] Tagged by sub-system (comms / medical / logistics / security)
- [ ] Rollup of top 5 recurring "improve" items across last 90 days
- [ ] Export as lessons-learned appendix to operations binder

### Phase L3: Cynefin domain classifier
**Effort:** S · **Depends on:** — · **Inspiration:** Dave Snowden's Cynefin framework
- [ ] Wizard places current problem in Clear / Complicated / Complex / Chaotic / Disorder
- [ ] Recommends response pattern per domain
- [ ] Prevents applying static checklists to chaotic events

---

## Tier M — Regional Expansion Packs

Beyond USA. Each is a data-pack with format-appropriate parsing; blueprints share schema.

### Phase M1: Canada pack (ECCC + GeoGratis)
**Effort:** M · **Depends on:** A1 · **Inspiration:** open.canada.ca
- [ ] Environment Canada alerts + radar imagery
- [ ] NRCan CanVec tiles
- [ ] Provincial EMO feeds; metric-first UI flag

### Phase M2: UK pack (Met Office + OS)
**Effort:** M · **Depends on:** A1 · **Inspiration:** Met Office DataPoint, Ordnance Survey OpenMap
- [ ] DataHub warnings feed; OS OpenMap + Terrain 50 tiles
- [ ] UK civil defence + flood-warning integration

### Phase M3: EU Copernicus pack
**Effort:** M · **Depends on:** A1 · **Inspiration:** Copernicus Programme
- [ ] EMS rapid-mapping products; CAMS air-quality tiles; ERA5 reanalysis
- [ ] Complements GDACS already in Situation Room

### Phase M4: Australia pack (BOM + Geoscience AU)
**Effort:** M · **Depends on:** A1 · **Inspiration:** bom.gov.au, Geoscience Australia
- [ ] BOM warnings, radar, tide feeds
- [ ] Geoscience AU elevation tiles
- [ ] Bushfire-specific module tie-in (Fire Danger Rating)

---

## Tier N — Sanitation & Hygiene Depth

### Phase N1: Menstrual supply planner
**Effort:** S · **Depends on:** — · **Inspiration:** Days for Girls, MSF field kits
- [ ] `menstrual_supply` table per person — type (disposable / cup / cloth / underwear), quantity, reuse cycle
- [ ] Person-month coverage calculator
- [ ] Inventory template: "Female 3mo / 6mo / 12mo kit"
- [ ] Closes a consistently ignored gap

### Phase N2: Dental-without-paste protocol
**Effort:** S · **Depends on:** H4 · **Inspiration:** WHO oral health in emergencies, Hesperian
- [ ] Baking soda + salt ratio reference; chew-stick species field guide (USDA PLANTS); oil-pulling protocol
- [ ] Integrates with dental-emergency pack (H4)

### Phase N3: Handwash without plumbing SOP
**Effort:** S · **Depends on:** — · **Inspiration:** CDC + WASH cluster
- [ ] Tippy-tap build plans; ash-soap protocol (hardwood ash lye + fat tables); greywater discipline
- [ ] Printable field card

### Phase N4: Cloth-diapering during shortage SOP
**Effort:** S · **Depends on:** — · **Inspiration:** cloth-diaper community wikis
- [ ] Inventory template: "Infant cloth kit"
- [ ] Wash protocol without electric washer
- [ ] Rotation math: daily changes × dry time → required stock

### Phase N5: Field treatment of lice / scabies
**Effort:** S · **Depends on:** — · **Inspiration:** CDC parasitic disease guidelines
- [ ] Decision-tree: lice (permethrin → comb-out → essential-oil adjuncts)
- [ ] Scabies decontamination SOP (clothing, bedding, 72h isolation bag)
- [ ] Inventory template entries

---

## Tier O — Economy & Recovery

### Phase O1: Multi-party barter network ledger
**Effort:** M · **Depends on:** federation (shipped) · **Inspiration:** LETS, historical wartime scrip
- [ ] Triangular-trade graph across federation pod
- [ ] Reputation score per peer
- [ ] Cryptographically unique ration coupons (no double-spend; **not** printed paper)
- [ ] Extends existing single-node barter inventory

### Phase O2: Hyperinflation + historical recovery reference
**Effort:** S · **Depends on:** — · **Inspiration:** Ferguson *The Ascent of Money*, Sargent
- [ ] Case cards: Weimar, Zimbabwe, Venezuela, Argentina, Lebanon
- [ ] "What worked" table: hard assets, portable skills, social capital, black-market ethics
- [ ] Curated offline reading list (Kiwix-compatible)

### Phase O3: Microgrid black-start SOP
**Effort:** M · **Depends on:** G6 · **Inspiration:** NERC EOP-005, local co-op procedures
- [ ] Black-start sequencing reference for neighborhood operators
- [ ] Load-shed priority order template
- [ ] Cranking-path docs per generator type
- [ ] Interlocks with battery-bank module for grid-form vs grid-follow state

---

## Tier P — Transportation Depth

### Phase P1: Pack-animal load calculator
**Effort:** S · **Depends on:** — · **Inspiration:** US Army FM 3-05.213
- [ ] Species tables: horse, mule, llama, donkey — pack % of body weight by terrain
- [ ] Daily feed + water; altitude + grade derating
- [ ] Integrated with existing `alt_vehicles`

### Phase P2: Canoe / kayak portage planner
**Effort:** S · **Depends on:** A5 · **Inspiration:** BWCA / Quetico outfitter tables
- [ ] Boat + gear weight vs trail-mile rest cadence
- [ ] Chained water + portage route planner
- [ ] Useful for PNW / Great Lakes / Adirondack evac

### Phase P3: E-bike range calculator
**Effort:** S · **Depends on:** — · **Inspiration:** Grin Tech motor simulator data
- [ ] Wh/mi model by grade, wind, cargo weight
- [ ] Solar-recharge time from configured panel wattage
- [ ] Ties into vehicles + solar forecast

---

## Tier Q — Documentation, Insurance & Cultural

### Phase Q1: Property photo-inventory builder
**Effort:** M · **Depends on:** — · **Inspiration:** III.org home-inventory standard
- [ ] Room-by-room guided capture workflow
- [ ] EXIF-locked photos + serial# OCR (reuses vision AI)
- [ ] SHA-256-signed manifest for claim defensibility
- [ ] Encrypted export for off-site backup
- [ ] Genuinely novel in prepper tooling

### Phase Q2: Pre/post-disaster comparison packet
**Effort:** S · **Depends on:** Q1 · **Inspiration:** FEMA damage assessment
- [ ] Side-by-side before/after PDF per room with GPS + timestamp proof-chain
- [ ] Auto-match post-event photos to pre-event by room tag
- [ ] Claim-ready with per-image hash signatures

### Phase Q3: Multi-faith dietary + calendar reference
**Effort:** S · **Depends on:** A2 · **Inspiration:** tradition primary sources
- [ ] Kosher / halal / Hindu vegetarian / Buddhist / Jain flags on food DB
- [ ] Religious-calendar overlay: Ramadan, Lent, Yom Kippur, Ekadashi
- [ ] Basic funeral-rite references per tradition (see I3)
- [ ] Deliberately a reference module — defers to Kiwix for depth

### Phase Q4: Pre-modern skills reference pack
**Effort:** M · **Depends on:** — · **Inspiration:** Foxfire book series, Sheridan's *Smithing*, ethnobotany field guides
- [ ] Blacksmith color-temperature chart; pottery cone chart; soap saponification calc (lye + fat tables)
- [ ] Cordage / basketry fiber ID by USDA PLANTS region
- [ ] Natural-dye plant catalog
- [ ] Leather tanning (bark / brain / alum) safety-ordered reference
- [ ] Tallow → candle / soap yield math

---

## Honest omissions (explicitly OUT of v9)

Surveyed and intentionally excluded. Future contributors: don't relitigate.

- **Additional security audits** — 14 rounds already, diminishing returns
- **Pure CSS polish** — handled in the existing inline-style migration pattern
- **Roadmap v8 Phase 1-4 & 7** — their blueprint stubs exist; real deliverables live under A1-A3
- **Anything requiring external SaaS** — offline-first is non-negotiable
- **Interactive substance-withdrawal tapers** (alcohol, benzodiazepines, opioids) — **medical-risk-of-death too high for DIY tooling**. Acute benzo/alcohol withdrawal can kill; amateur tapers compound the risk. Ship cached ASAM/SAMHSA reference PDFs with "physician required" messaging instead.
- **Home distillation of potable spirits** — federal US law requires permit; counterfeiting-adjacent to automate. **Water distillation for purification stays in-scope** (legal, safe).
- **Paper-currency / scrip printing templates** — printing currency in a functioning jurisdiction is counterfeiting-adjacent. O1 uses cryptographic unique-ID digital coupons instead.
- **Full-depth theology / scripture libraries** — scope creep; defer to Kiwix. Ship only dietary + calendar + funeral-rite *structured reference* (Q3, I3).
- **Interactive flint-knapping / flintlock / cap-and-ball guides** — legal but niche. Kept as passive reference in Q4, not a module.
- **Full sign-language instruction** — out of scope. ASL/BSL *emergency signal cards* fine within existing signals reference.
- **Offline Google-Translate competitor** — current open-source offline MT (Bergamot, NLLB-200 distilled) isn't field-ready at bundle sizes. Revisit 12-24 months; ship cached survival/medical phrasebook flashcards meanwhile.
- **Custom-trained LLM on prepper corpus** — existing Ollama + RAG (A3) gets 90% of value at 1% of cost.

---

## Tier R — Comms / Cyber / Family-Ops Depth

### Phase R1: NTS radiogram + formal traffic handling
**Effort:** S · **Depends on:** C2 (codeplug), federation · **Inspiration:** ARRL FSD-3/FSD-218, NTS
- [ ] Radiogram composer: preamble, check, place-of-origin, signature, ARL numbered-text macros
- [ ] Relay-chain log with station callsigns and timestamps per hop
- [ ] Printable radiogram pad
- [ ] Integrates with federation sync for multi-node relay audit trail

### Phase R2: ALE + VARA + Pat Winlink integration
**Effort:** M · **Depends on:** C3 (propagation) · **Inspiration:** MIL-STD-188-141 (civilian 2G/3G-ALE only), Rosmodem VARA, Pat (la5nta/pat, GPL-3)
- [ ] ALE sounding-window scheduler + LQA matrix (time × band × peer callsign × SNR)
- [ ] VARA session log table (modem, bandwidth, SNR, retries, throughput, peer)
- [ ] Pat client integration hooks — Pat replaces closed-source Winlink Express on non-Windows targets
- [ ] **LEGAL FLAG:** 4G-ALE / STANAG 4538 is export-controlled; v9 scope is civilian 2G/3G only

### Phase R3: FLDIGI macro library + net control scripts
**Effort:** S · **Depends on:** — · **Inspiration:** FLDIGI reference + NBEMS ICS-213 templates, ARES/RACES NCS handbook
- [ ] Versioned macro library table (mode, macro name, body, variables, last-used, source)
- [ ] Net-control session table (net, frequency, NCS op, preamble, check-in roster, traffic list, announcements, closing)
- [ ] Net typology reference: formal (NTS/ARES) vs tactical vs directed vs open
- [ ] Macro export across federation so multiple operators share the same library

### Phase R4: Household-tier cyber resilience
**Effort:** M · **Depends on:** — · **Inspiration:** dnscrypt-proxy v2, Smallstep step-ca, KeePassXC, OpenWrt Table of Hardware
- [ ] DoH fallback: dnscrypt-proxy config generator with upstream rotation + stub resolver for when Pi-hole dies
- [ ] Household PKI registry: step-ca offline root + intermediate keyring (CA, fingerprint, validity, CRL, subject CN)
- [ ] KeePassXC vault registry (vault path, last-opened, key-file location, rotation schedule)
- [ ] Router firmware ledger: OpenWrt/DD-WRT hashes (device, version, sha256, source URL, verified date, recovery-image location)

### Phase R5: Sneakernet malware firewall
**Effort:** M · **Depends on:** — · **Inspiration:** YARA + VirusShare rule packs, CISA removable-media guidance, Kanguru FlashTrust
- [ ] YARA rule set registry + per-USB-ingress scan log (stick ID, scan date, rules matched, quarantine action)
- [ ] Sacrificial-scanner-station SOP checklist (airgap PC, boot medium, scan order, disposal)
- [ ] WriteSafe USB registry for hardware-write-protected devices (Kanguru, Nexcopy) with direction-enforcement
- [ ] Offline NVD CVE feed ingester (JSON 2.0 schema) with CPE match + local full-text search

### Phase R6: 3-2-1-1-0 backup policy engine
**Effort:** S · **Depends on:** — · **Inspiration:** Veeam's extension of Krogh's 3-2-1
- [ ] Backup set registry enforcing 3-2-1-1-0 (3 copies, 2 media types, 1 offsite, 1 offline, 0 verification errors)
- [ ] Auto-verification job — re-checksum offline media on schedule
- [ ] Alert when any rule violated for > 30 days
- [ ] Integrates with existing auto-backup module

### Phase R7: Kids-as-operators framework
**Effort:** M · **Depends on:** J7 · **Inspiration:** BSA/4-H progression, FCC Part 97.3(a)(6) third-party rules, Red Cross first-aid tiers
- [ ] Age-task delegation matrix (task, min age, supervision level, co-signoff required, revocable)
- [ ] Spotter-flag gate — task can't be marked active without named adult spotter
- [ ] Kid-mode UI toggle per profile: 56px buttons, simple vocabulary, no destructive actions
- [ ] Internal cert ledger (operator, skill, level, examiner, date, expiry) — mirrors Technician / General / Extra + first-aid tiers
- [ ] **LEGAL FLAG:** FCC Part 97.3(a)(6) requires licensed control-op for under-licensed TX — enforce in UI

### Phase R8: Elderly / disability accommodation
**Effort:** M · **Depends on:** — · **Inspiration:** Medicare O2 coverage criteria, OSHA safe patient handling
- [ ] Mobility-aid manifest (item, weight kg, stowed LxWxH cm, user, power need W, runtime hrs) — reuses vehicle cargo math
- [ ] O2 concentrator runtime cascade (source, type [concentrator/tank/battery], LPM, capacity, runtime min, swap-by timestamp). E-tank formula 0.28 × psi ÷ LPM
- [ ] Hearing-aid battery log (size 10/312/13/675, daily hours, per-cell life, reserve days)
- [ ] Audio-first UI mode + TTS callouts via plugin API
- [ ] Pill voice-reminder TTS extension on existing med table
- [ ] Transfer SOP (two-person, slide board, Hoyer) with contraindications
- [ ] BLE wander-beacon registry for cognitively impaired adults — **requires stored consent record / POA**

### Phase R9: Vehicle self-diagnostics depth
**Effort:** M · **Depends on:** — · **Inspiration:** Haynes + FSM common-cause indices, SAE J2012 + J1979 public code list, USTMA repair guidelines
- [ ] Field diagnostic decision trees (system [brake/tire/fluid/fuel/electrical] → symptom → test → action)
- [ ] OBD-II DTC library (code, SAE/mfr, system, description, common causes, civilian fix scope, tool needed)
- [ ] Diesel cold-start protocol matrix (ambient temp → block heater min → glow cycle → ether permitted Y/N → cycle count). **SAFETY FLAG:** ether on glow-plug engines can detonate — UI warns
- [ ] 12V parasitic-draw log + reserve-capacity math
- [ ] Tire repair decision tree with DOT 569 legality gates
- [ ] Tool-tier column per diagnostic linking to go-bag / garage / shop

### Phase R10: Seasonal quick-start playbook graph
**Effort:** L · **Depends on:** A4, A5 and the rest · **Inspiration:** NWS impact-based decision support, FEMA Ready.gov timelines
- [ ] PlaybookGraph table — orchestration references to EXISTING feature IDs (not new features)
- [ ] Schema: playbook, trigger, sequence, feature_ref, offset_hours, owner
- [ ] Seed playbooks: Hurricane-72h, WinterStorm-24h, HeatDome-48h, WildfireEvac-Imminent, TornadoWatch-to-Warning, IceStorm-48h, FloodWatch-24h
- [ ] UI: "Activate playbook" button spawns checklist items across all involved tabs; dashboard shows progress

### Phase R11: Offline content pipeline expansion
**Effort:** M · **Depends on:** — · **Inspiration:** yt-dlp (bundled), Project Gutenberg, MIT OCW, OpenStax
- [ ] YT-DLP curated-creator whitelist table (channel, URL, category, last-synced, disk used) — ship EMPTY, user curates. **LEGAL FLAG:** creator ToS + copyright — user-responsibility doc
- [ ] Gutenberg filter view (bookshelf = Agriculture/Medicine/Survival/Reference) over local mirror
- [ ] MIT OCW + OpenStax course manifest (course, level, subject, files, license)
- [ ] Podcast RSS archive table with mp3 downloader
- [ ] MediaWiki API / Discourse-export ingester for non-Kiwix wikis (Permies, Homesteading Today) — uses official dumps only; logs ToS compliance per source

---

## Tier S — Developer, Operator, Distribution

### Phase S1: Property-based + fuzz test harness
**Effort:** M · **Depends on:** — · **Inspiration:** Hypothesis, atheris, OSS-Fuzz
- [ ] Hypothesis property tests on every Pydantic model (household, inventory, plume inputs, routing queries)
- [ ] atheris fuzz harness on file-upload parsers (CSV, GPX, PMTiles, EXIF, image) — nightly CI job
- [ ] Corpus-seeded with real-world malformed samples
- [ ] Coverage report surfaced to PR checks

### Phase S2: Contract + chaos + perf regression
**Effort:** M · **Depends on:** OpenAPI spec (new) · **Inspiration:** schemathesis, toxiproxy, Jepsen, pytest-benchmark
- [ ] OpenAPI 3.1 spec generated from Flask route decorators
- [ ] schemathesis suite hits all 600+ routes; PR-blocking on drift
- [ ] toxiproxy chaos harness simulates partition / clock-skew / peer-death during federation sync
- [ ] pytest-benchmark budgets per hot route (P95 < 80ms for `/inventory`)
- [ ] Load test: 8 concurrent household devices → single node (Locust scenario)

### Phase S3: Mutation testing on life-safety calculators
**Effort:** S · **Depends on:** — · **Inspiration:** mutmut, Stryker
- [ ] mutmut configured for person-days, plume, rainwater, routing, nitrite cure, pediatric dose, O2 runtime
- [ ] 90% mutant-kill threshold gate in CI
- [ ] Surfaces untested branches in life-safety math

### Phase S4: WCAG 2.2 AA audit + ARIA deep-dive
**Effort:** M · **Depends on:** — · **Inspiration:** W3C WCAG 2.2 normative
- [ ] Full WCAG 2.2 SC coverage (focus-not-obscured, dragging, target size 24px minimum)
- [ ] NVDA / JAWS / Orca semantic audit; fix unlabeled landmarks / regions / groups
- [ ] Keyboard-only flow per primary workflow (no mouse-required paths)

### Phase S5: Operator-stress UX modes
**Effort:** M · **Depends on:** S4 · **Inspiration:** military HMI guidelines, Apple AssistiveTouch, ColorBrewer/Viridis
- [ ] Glove mode: 56px targets, 400ms click debounce, confirmation buffers on destructive actions
- [ ] Tremor-guard: double-tap cancel on destructive actions
- [ ] Color-blind-safe palette variants switchable per theme (deuteranopia, protanopia, tritanopia)
- [ ] OpenDyslexic + Atkinson Hyperlegible bundled fonts + toggle
- [ ] Plain-language alternate copy track for jargon surfaces (plume, NBC, OPSEC)

### Phase S6: Voice I/O — captions + commands
**Effort:** M · **Depends on:** — · **Inspiration:** whisper.cpp, Vosk, NASA hands-busy UX
- [ ] whisper.cpp live captions on TTS output (local-only; deaf/HoH parity for AI briefings)
- [ ] Vosk grammar-mode hands-free commands: "log water 5 gallons", "show medical dashboard", "set emergency level 2"
- [ ] Wake-word option (Porcupine-lite) for genuinely hands-free ops

### Phase S7: Family-wizard installer + fleet seed + repair mode
**Effort:** M · **Depends on:** C8 · **Inspiration:** MDM zero-touch, Office Click-to-Run repair, Chrome ADMX
- [ ] "Install for my household" wizard — seeds members, region, theme, roles in one flow
- [ ] Post-install launch checklist: location → Tier-1 packs → backup target → done
- [ ] `--profile profile.json` for sysadmins staging 5-10 family laptops
- [ ] Preflight checks narrate reasons + remediation links (no cryptic MSI errors)
- [ ] Repair-install mode detects corrupt SQLite, rebuilds indexes, preserves user data
- [ ] Silent-install via `/qn` + MST transforms for mass deployment
- [ ] ADMX/ADML Group Policy templates

### Phase S8: Data pack signing + diff + license ledger
**Effort:** M · **Depends on:** A1 · **Inspiration:** Sigstore, C2PA, SPDX, `git diff --word-diff`
- [ ] Ed25519-signed manifest per pack (source URL, download date, SHA256 chain, license SPDX-ID)
- [ ] Per-pack license surfaced in About; redistribution compliance docs
- [ ] Row-level pack-diff UI: "what changed between FEMA NRI v1 and v2"
- [ ] Situation Room feed-item provenance: publisher + hash + timestamp on every card

### Phase S9: Drift sentry + annotation layer
**Effort:** S · **Depends on:** S8 · **Inspiration:** package-lock audits, Hypothes.is
- [ ] Scheduled hash-check of pack sources when online; flag drift in UI
- [ ] User-owned annotation layer over pack rows ("FEMA NRI underestimates ice storms in this county per 2024 experience")
- [ ] Annotations survive pack upgrades; migrate forward on row-ID match

### Phase S10: Reproducible builds + SBOM + transparency log
**Effort:** M · **Depends on:** — · **Inspiration:** SLSA Level 3, Syft, Sigstore, Rekor
- [ ] SLSA L3 build attestation in CI
- [ ] Syft SBOM per release artifact
- [ ] cosign-signed binaries + Rekor transparency log entry
- [ ] Verify-before-run helper in installer; UI shows "Verified" badge

### Phase S11: Local observability stack
**Effort:** M · **Depends on:** — · **Inspiration:** Prometheus node_exporter, lnav, Jaeger all-in-one, WinDirStat
- [ ] Embedded Prometheus exposition on `/metrics` (no egress)
- [ ] In-app structured-log search over `nomad.log` (filter, facet, follow)
- [ ] OpenTelemetry collector writing to local SQLite; flame-graph viewer for slow-route diagnosis
- [ ] D3 sunburst of data-dir usage by table / service / media
- [ ] Per-page "DB cost" panel with SQLite EXPLAIN QUERY PLAN

### Phase S12: nomad-cli companion + migration CLI
**Effort:** M · **Depends on:** — · **Inspiration:** gh CLI, Alembic, Prisma Migrate
- [ ] Single binary `nomad-cli`: `inventory add`, `backup run`, `sse tail`, `pack verify`, `federation peer list`
- [ ] Alembic-style migration CLI with up / down / status + compat matrix
- [ ] Faker-driven realistic household seeds (retired couple, family-of-5, bug-out cabin)
- [ ] Fixtures loader for test + demo DBs

### Phase S13: Component catalog (UIBook)
**Effort:** S · **Depends on:** — · **Inspiration:** Storybook
- [ ] Catalog page rendering every `premium/99_final_polish.css` primitive (`.ss-pill`, `.nomad-check`, `.drag-handle`, `.ai-dots`, toasts, tone-* classes)
- [ ] Accessible via `/devtools/uibook` when `NOMAD_DEV=1`
- [ ] Prevents component drift across 87 phases of future development

### Phase S14: Tauri alternative shell + WASM calculators
**Effort:** L · **Depends on:** — · **Inspiration:** Tauri, Pyodide, SQLite-WASM
- [ ] Parallel Tauri build path (WebView2/WKWebView) — target ~30 MB vs current 300 MB footprint
- [ ] WASM-compiled hot calculators: person-days, plume, rainwater, OBD decode → zero-RTT in browser
- [ ] Feature flag gates: some features (ollama, libtorrent) stay Python-side; Tauri is the thin-shell option
- [ ] Useful for mobile/tablet handoff where disk space is scarce

### Phase S15: Release operations — canary, rollback, delta, air-gap
**Effort:** L · **Depends on:** S10 · **Inspiration:** Firefox Beta, Proxmox rollback, Chrome Courgette, RHEL DVD ISO
- [ ] Opt-in canary channel with telemetry-free feedback form
- [ ] One-click rollback to N-1 with DB-compat guard + auto-backup first
- [ ] Delta patches (courgette / bsdiff) between versions — bandwidth-limited preppers
- [ ] Air-gap install ISO: installer + Tier-1 packs pre-fetched for first-boot on truly offline systems
- [ ] Offline update delivery via WriteSafe USB using R5 infrastructure

---

## Tier T — AI Decision Support & Simulation Depth

### Phase T1: Role-persona prompt library
**Effort:** S · **Depends on:** A3 · **Inspiration:** USMC MCDP-1, runbook-as-prompt
- [ ] Structured system-prompt templates per role (medic / comms / logistics / security / NCO / leader)
- [ ] "Apply role to situation" one-click — AI wears the hat
- [ ] Codifies tribal knowledge into reusable templates

### Phase T2: OPORD autofill engine
**Effort:** M · **Depends on:** T1 · **Inspiration:** Army FM 5-0 / ATP 5-0.2
- [ ] AI drafts 5-paragraph OPORD from existing inventory, vehicles, contacts, waypoints, threats
- [ ] User reviews + edits; AI-drafted sections tagged for quick sanity-check
- [ ] Turns hours of paperwork into reviewable draft in seconds

### Phase T3: Commander's intent propagator
**Effort:** S · **Depends on:** T1 · **Inspiration:** mission-command doctrine
- [ ] Leader writes intent in natural language; AI drafts subordinate tasks with MoE
- [ ] Enforces intent-based decentralization in small pods

### Phase T4: Pre-mortem red-team
**Effort:** S · **Depends on:** A3 · **Inspiration:** Gary Klein pre-mortem
- [ ] AI plays "this plan failed — why?" against current plan
- [ ] Ranks failure modes by likelihood × impact
- [ ] Runs before execution, not during AAR

### Phase T5: Evacuation Monte Carlo simulator
**Effort:** L · **Depends on:** A4, A5 · **Inspiration:** FEMA HAZUS-MH
- [ ] N-trial simulator varying fuel / traffic / weather / contact availability
- [ ] Outputs per-route success probability + most-likely failure mode
- [ ] Converts single-point plans into probabilistic tree

### Phase T6: Plume dispersion ensemble
**Effort:** M · **Depends on:** E1 · **Inspiration:** NOAA HYSPLIT ensemble
- [ ] Gaussian puff with wind-field perturbations, 10,000 realizations
- [ ] Heatmap overlay showing uncertainty cone instead of false-precision single plume
- [ ] Decision-support: "95% of realizations keep lethal zone east of rally point"

### Phase T7: Bayesian inventory burn forecaster
**Effort:** M · **Depends on:** A2 · **Inspiration:** pymc, Kalman
- [ ] Replaces linear depletion with posterior-updating model
- [ ] Flags accelerating consumption before stockout
- [ ] Credible-interval bands on "days remaining" numbers

### Phase T8: Fault Tree Analysis engine
**Effort:** M · **Depends on:** — · **Inspiration:** NRC/NASA reliability engineering
- [ ] Hierarchical failure-mode tree with historical frequencies
- [ ] Quantifies cascading-failure risk across systems
- [ ] Visual gate tree (AND / OR) with probability computation

### Phase T9: Readiness-under-shock Monte Carlo
**Effort:** S · **Depends on:** T5-T8 · **Inspiration:** financial stress testing
- [ ] Composite readiness score under compound shocks (layoff + illness + storm)
- [ ] Dashboard widget: "p(sustain 30 days) = 0.68 under 3-shock scenario"

---

## Tier U — Hardware Reference Catalogs

All catalogs seed a `hw_catalog` table with specs, parts lookup, fuel/power curves, manufacturer + model.

### Phase U1: Generator catalog
**Effort:** M · **Depends on:** — · **Inspiration:** Honda / Predator / Champion / Westinghouse service manuals
- [ ] Specs + parts + fuel-consumption curves per load
- [ ] Tank-sizing math drives realistic runtime planning
- [ ] Integrates with existing fuel module

### Phase U2: Heater + stove reference
**Effort:** M · **Depends on:** G4 · **Inspiration:** NFPA 211, EPA certified stove list
- [ ] Wood / rocket-mass / kerosene / pellet / propane catalog
- [ ] Installation clearances + CO math reference
- [ ] **SAFETY:** heating-related deaths exceed cold-exposure deaths in most grid-down events

### Phase U3: Inverter / charge-controller catalog
**Effort:** S · **Depends on:** G6 · **Inspiration:** Victron VRM, MorningStar, Outback
- [ ] Sizing + firmware version tracking per installed device
- [ ] Linked to solar forecast and battery-bank modules

### Phase U4: Water pump catalog
**Effort:** S · **Depends on:** — · **Inspiration:** Grundfos / Shurflo specsheets
- [ ] 12V / 120V / hand / solar-submersible with flow-head curves
- [ ] Integrates with water sources + rainwater calc (C5)

### Phase U5: Refrigeration catalog
**Effort:** S · **Depends on:** — · **Inspiration:** EnergyStar data
- [ ] RV / propane / chest / upright with kWh/day consumption tables
- [ ] Cold-chain is biggest off-grid energy load — this drives solar sizing

### Phase U6: Firearm maintenance ledger — **STORAGE/CLEANING/INVENTORY ONLY**
**Effort:** S · **Depends on:** — · **Inspiration:** MIL-STD preventive maintenance
- [ ] **HARD LIMITS:** NO ballistic solvers, NO reloading tables, NO tactical/engagement content
- [ ] Serialized inventory tied to existing vault
- [ ] Humidity + temp storage logs (desiccant replacement alerts)
- [ ] Parts-wear counters (AR BCG rounds-fired, Glock RSA spring cycles)
- [ ] Cleaning-schedule reminders tied to round-count
- [ ] **LEGAL:** jurisdiction-specific storage/registration rules stay user-configured

### Phase U7: Lifetime-tool catalog
**Effort:** S · **Depends on:** — · **Inspiration:** Project Farm durability rankings
- [ ] Lifetime hand tools + serviceable power tools inventory
- [ ] Spare-part strategy per tool
- [ ] Tool attrition is silent until SHTF

---

## Tier V — Drill & Exercise Engine

### Phase V1: Scenario library + inject-timer
**Effort:** M · **Depends on:** — · **Inspiration:** FEMA HSEEP, DHS National Exercise Program
- [ ] 15+ pre-built tabletop scenarios (ice storm, cyber outage, pandemic wave, refugee influx, hurricane)
- [ ] Scripted inject delivery with timing + branching (MSEL-style)
- [ ] Role cards printable (NCS, medic, logistics, leader, observer)

### Phase V2: Tabletop engine
**Effort:** M · **Depends on:** V1, L2 · **Inspiration:** FEMA HSEEP tabletop guides
- [ ] Role assignment + player action capture
- [ ] Hooks into existing L2 AAR engine for hot-wash + 30-day follow-up
- [ ] Shared whiteboard via existing LAN chat

### Phase V3: Functional exercise engine
**Effort:** L · **Depends on:** V1 · **Inspiration:** DHS NEP functional exercises
- [ ] Injects fire against LIVE NOMAD data — simulated hurricane shifts inventory, generates predictive alerts
- [ ] Full-system realism without actual crisis
- [ ] Auto-reset to snapshot after exercise ends

### Phase V4: Federation drill orchestrator
**Effort:** M · **Depends on:** V3 · **Inspiration:** mutual-aid comm exercises
- [ ] Pod runs synchronized exercise across 5 households via federation sync
- [ ] Pod-level readiness is the unit that matters in real events

### Phase V5: Difficulty scaler
**Effort:** S · **Depends on:** V1 · **Inspiration:** aviation sim curricula
- [ ] Green / amber / red progression per scenario
- [ ] Prevents learned helplessness from always-hard or always-easy drills

---

## Tier W — Signals, Siting & Direction-Finding

### Phase W1: TDOA + AoA triangulation
**Effort:** M · **Depends on:** B2 (SDR) · **Inspiration:** KiwiSDR TDoA, ARRL ARDF manual
- [ ] 3-station time-difference-of-arrival solver
- [ ] AoA beam-width math for yagi-based bearing plots
- [ ] Triangulation overlay with error ellipses on existing MapLibre
- [ ] Signal log: freq / time / bearing / confidence
- [ ] Fox-hunt gamification for skill-building (progressive difficulty)
- [ ] **LEGAL FLAG:** scope strictly to ham + unlicensed ISM + known-public transmitters; UI surfaces this

### Phase W2: Viewshed analyzer
**Effort:** M · **Depends on:** K1 DEM data · **Inspiration:** GRASS GIS `r.viewshed`
- [ ] Elevation-based line-of-sight polygons from waypoint
- [ ] Uses existing contour data infrastructure
- [ ] Drives OPSEC + comms siting decisions

### Phase W3: Cover + concealment scorer
**Effort:** S · **Depends on:** W2 · **Inspiration:** Army FM 21-76 site selection
- [ ] Bivouac site rating from terrain + vegetation + slope
- [ ] Quantifies gut-feel into repeatable criteria

### Phase W4: Defensible-space + safe-room siting
**Effort:** S · **Depends on:** — · **Inspiration:** CAL FIRE PRC 4291, FEMA P-320/P-361
- [ ] Wildfire defensible-space zones (0-5 / 5-30 / 30-100 ft) auto-drawn on map
- [ ] Tornado safe-room siting reference with cost estimator
- [ ] Flood elevation lookup from USGS NHD + FEMA FIRM

### Phase W5: Water-to-shelter distance guides
**Effort:** S · **Depends on:** — · **Inspiration:** EPA + USDA siting guides
- [ ] Rule-of-thumb reference (100 ft septic, 50 ft contamination, etc.)
- [ ] Planning-time gating is free; retrofits are expensive

---

## Tier X — Energy Defense & Grounding Reference

All phases are REFERENCE-ONLY — licensed electrical work required in every jurisdiction.

### Phase X1: EMP protection reference
**Effort:** S · **Depends on:** — · **Inspiration:** MIL-STD-188-125, Arthur Bradley research
- [ ] Faraday cage sizing + grounding topology + mesh-size math calculator
- [ ] Most DIY cages fail the math — this surfaces the math

### Phase X2: Surge-device catalog
**Effort:** S · **Depends on:** — · **Inspiration:** UL 1449 listings
- [ ] Joule rating + response time + clamp voltage per device
- [ ] "Surge protector" is a marketing term without specs

### Phase X3: Lightning-rod siting SOP
**Effort:** S · **Depends on:** — · **Inspiration:** NFPA 780
- [ ] Per-structure type with cone-of-protection math
- [ ] Rural off-grid sites are lightning targets

### Phase X4: Generator bonding + transfer-switch reference
**Effort:** S · **Depends on:** U1 · **Inspiration:** NEC 250 + 702
- [ ] Neutral-ground bond diagrams + transfer-switch legality
- [ ] **SAFETY:** wrong bonding kills people and equipment

### Phase X5: PV rapid-shutdown compliance
**Effort:** S · **Depends on:** G6 · **Inspiration:** NEC 690.12, SolarEdge/Tigo RSD docs
- [ ] 2017+ code compliance checklist
- [ ] Firefighters won't touch non-compliant arrays

---

## Tier Y — International & Cultural Defaults

### Phase Y1: Unit-locale auto-switcher
**Effort:** S · **Depends on:** existing i18n · **Inspiration:** ICU MeasureFormat
- [ ] Metric / imperial per region with per-field overrides
- [ ] 98.6°F fever threshold unusable for German operator

### Phase Y2: Regional emergency dialpad
**Effort:** S · **Depends on:** — · **Inspiration:** ITU E.161
- [ ] 112 / 911 / 119 / 110 / 000 / 999 library + non-emergency + poison-control + coast guard per region
- [ ] Auto-selects from detected locale

### Phase Y3: Civic defense lexicon crosswalk
**Effort:** S · **Depends on:** — · **Inspiration:** UN OCHA glossary, Sphere Handbook
- [ ] FEMA IS-100 ↔ UK JESIP ↔ EU Mechanism ↔ JP 自主防災 ↔ AU AIIMS terminology mapping
- [ ] Users reading foreign guidance can map "Silver Command" to "Operations Section Chief"

### Phase Y4: Staple-swap calorie-equivalent tables
**Effort:** M · **Depends on:** A1 · **Inspiration:** FAO Food Balance Sheets
- [ ] Rice / wheat / maize / cassava / teff / plantain with calorie-equivalent swap tables tied to RegionPack
- [ ] Ration calculators currently Western-wheat-biased; invalid for 60% of world

### Phase Y5: Faith observance engine
**Effort:** S · **Depends on:** Q3 · **Inspiration:** IslamicFinder / Chabad calendar patterns
- [ ] Prayer-time windows, fasting schedules, grief/mourning observances affecting preparedness scheduling
- [ ] Extends Q3 (dietary + calendar) to time-of-day operational planning

### Phase Y6: Document expiry vault
**Effort:** S · **Depends on:** Q1 · **Inspiration:** Henley Passport Index
- [ ] Country-specific passport / visa / driver-permit / ID templates
- [ ] Renewal lead-times + embassy locator
- [ ] Expired passport during crisis = stranded

---

## Tier Z — Environmental Exposure Monitoring

### Phase Z1: Indoor air station adapter
**Effort:** M · **Depends on:** — · **Inspiration:** Home Assistant integrations
- [ ] Awair / Airthings / uHoo / PurpleAir / Netatmo API adapters
- [ ] Logs PM2.5, PM10, VOC, CO2, CO, radon
- [ ] Outdoor AQI covered by CAMS; indoor is where people spend 90% of time

### Phase Z2: Per-room dew-point + mold index
**Effort:** S · **Depends on:** Z1 · **Inspiration:** ASHRAE 160, VTT Mold Growth Model
- [ ] Temp + RH logger computing dew point and mold-risk bands
- [ ] Moisture intrusion is #1 prepper-stockpile destroyer

### Phase Z3: Pollen feed
**Effort:** S · **Depends on:** — · **Inspiration:** Pollen.com, Copernicus CAMS pollen layer
- [ ] Regional tree / grass / weed / mold-spore ingestion
- [ ] Family-member × exposure × symptom log

### Phase Z4: Private-well baseline + schedule
**Effort:** M · **Depends on:** AE1 (water quality) · **Inspiration:** EPA "Drinking Water from Household Wells", Health Canada
- [ ] pH / TDS / nitrate / coliform / arsenic / lead baseline + scheduled re-tests
- [ ] 15% of US households on private wells with zero monitoring

### Phase Z5: Heritage hazards (lead / asbestos / lead-solder)
**Effort:** S · **Depends on:** — · **Inspiration:** HUD Lead Safe Housing Rule, EPA asbestos guidance
- [ ] Pre-1978 lead paint, pre-1980 asbestos, pre-1986 lead solder mapped to home build-year
- [ ] Renovation during grid-down = exposure event

### Phase Z6: Soil garden safety
**Effort:** S · **Depends on:** G8 SSURGO · **Inspiration:** USDA NRCS, Cornell WMI
- [ ] Heavy-metal background check before garden siting (Pb, As, Cd)
- [ ] Post-industrial sites concentrate lead

---

## Tier AA — Medical Depth II

### Phase AA1: Wilderness-med progression ladder
**Effort:** M · **Depends on:** H3 · **Inspiration:** NOLS WMI / WMA International / SOLO
- [ ] WFA (16h) → WOEC (40h) → WFR (80h) → WEMT (180h) curriculum + recert calendar per family member
- [ ] H3 covers decision trees; this tracks the humans learning them

### Phase AA2: SOAP note journal
**Effort:** S · **Depends on:** — · **Inspiration:** WMA SOAP format, NREMT PCR
- [ ] Subjective / Objective / Assessment / Plan digital note with vitals trending
- [ ] Handoff-ready PDF export; structured documentation survives caregiver rotation

### Phase AA3: Wilderness-med scenario library
**Effort:** M · **Depends on:** V1 · **Inspiration:** NOLS scenario bank
- [ ] Lightning MCI, avalanche burial, swiftwater, 4hr-out femur, 6hr anaphylaxis
- [ ] Tabletop and live-action formats

### Phase AA4: Improvised splint + litter reference
**Effort:** S · **Depends on:** — · **Inspiration:** WMS Practice Guidelines
- [ ] Field-expedient material × anatomy matrix (ski pole / SAM / foam pad × radius / tibia / femur / c-spine)
- [ ] Improvised litter (poleless, ski-pole, tarp, jacket)

### Phase AA5: Evacuation decision matrix
**Effort:** S · **Depends on:** AA2 · **Inspiration:** WMS evacuation guidelines, MARCH-PAWS
- [ ] Rapid / non-rapid / walk-out / shelter-in-place gate
- [ ] Vitals-triggered auto-escalation

### Phase AA6: PPE doffing SOP
**Effort:** S · **Depends on:** — · **Inspiration:** CDC PPE sequence, MSF Ebola protocols
- [ ] Step-numbered sequences (N95 / surgical / Tyvek / PAPR / coverall)
- [ ] Common failure-mode callouts; video-reference hooks
- [ ] 90% of contamination happens during doffing

### Phase AA7: Home isolation zone builder
**Effort:** M · **Depends on:** — · **Inspiration:** CDC airborne isolation specs, ASHRAE 170
- [ ] Anteroom + Tyvek tape line + negative-pressure fan sizing (CFM per room volume) + HEPA return path
- [ ] Hospital overflow = home isolation; zero consumer guidance exists

### Phase AA8: Decontamination product matrix
**Effort:** S · **Depends on:** — · **Inspiration:** EPA Lists N/K/L
- [ ] Pathogen × surface × approved product × contact time
- [ ] Regional: US EPA / EU BPR / UK HSE / AU APVMA
- [ ] Wrong product or insufficient dwell time = false-security

### Phase AA9: Household quarantine roster
**Effort:** S · **Depends on:** E2 · **Inspiration:** CDC contact-tracing worksheet
- [ ] Per-person symptom-onset / exposure-date / isolation-end auto-calculator
- [ ] Complements existing household Rt tracker

### Phase AA10: Transmission route reference
**Effort:** S · **Depends on:** — · **Inspiration:** WHO IPC, Chin's *Control of Communicable Diseases Manual*
- [ ] Airborne / droplet / fomite / fecal-oral / vector reference driving PPE tier
- [ ] Over-spec wastes supplies; under-spec kills

---

## Tier AB — Alternative Medicine (Evidence-Tiered) — **MEDICAL/LEGAL FLAGS**

**Foundational gate:** every entry in AB wrapped with MD-consult modal on first-open, jurisdiction check, pregnancy/pediatric/hepatorenal contraindication display, explicit "reference only" + "do not use without professional guidance" banner.

### Phase AB1: Herbal catalog with evidence tiers
**Effort:** M · **Depends on:** AB0 gate · **Inspiration:** MSK "About Herbs", NIH NCCIH, WHO Monographs
- [ ] Entries tagged S1 Cochrane-reviewed / S2 peer-reviewed RCT / S3 ethnobotanical / S4 anecdotal
- [ ] Hard structural gate prevents tier confusion

### Phase AB2: Herb-drug interaction database
**Effort:** M · **Depends on:** AB1 · **Inspiration:** Natural Medicines Database, Stockley's
- [ ] St. John's Wort × SSRI / warfarin / OC; grapefruit × statin; ginkgo × antiplatelet
- [ ] Most dangerous alt-med failure mode; literature is scattered

### Phase AB3: Essential-oil safety reference
**Effort:** S · **Depends on:** AB0 gate · **Inspiration:** Tisserand & Young, ASPCA toxic plant list
- [ ] Topical dilution / oral contraindication / pediatric exclusion / pet toxicity
- [ ] Peppermint on infants = apnea; widespread harm from mass adoption

### Phase AB4: Grow-your-apothecary garden plan
**Effort:** S · **Depends on:** existing garden · **Inspiration:** Rosemary Gladstar curricula
- [ ] Calendula / yarrow / chamomile / plantain / comfrey per climate + soil
- [ ] Closes loop between garden + herb reference

### Phase AB5: Veterinary-grade antibiotic reference — **HARM-REDUCTION ONLY**
**Effort:** S · **Depends on:** AB0 gate · **Inspiration:** harm-reduction pattern
- [ ] **PRESENTATION ONLY** — zero dosing tables
- [ ] FDA warnings + resistance-breeding discussion + legal status by jurisdiction
- [ ] Explicit "do not use" recommendation
- [ ] Topic will be searched regardless; silence is worse than honest warnings

---

## Tier AC — Water Quality Depth (fills the `water_mgmt` stub)

### Phase AC1: Potability test-strip workflow
**Effort:** M · **Depends on:** A2 (water mgmt backbone) · **Inspiration:** WHO GDWQ 4th ed, EPA SDWA MCLs
- [ ] pH / TDS / free chlorine / total chlorine / nitrate / nitrite / hardness / coliform logger
- [ ] Test-strip purchase + use reminder schedule
- [ ] Backbone the water_mgmt stub has been missing

### Phase AC2: Well yield test
**Effort:** S · **Depends on:** AC1 · **Inspiration:** USGS WRIR 89-4089
- [ ] 4-hour drawdown test protocol + recovery-rate math
- [ ] gpm-vs-family-size adequacy check
- [ ] Well depth is meaningless without yield

### Phase AC3: Legionella guard
**Effort:** S · **Depends on:** — · **Inspiration:** ASHRAE Guideline 12, OSHA III:7
- [ ] Hot-water storage temperature logger (> 60°C storage / > 55°C tap)
- [ ] Monthly flush schedule for low-use outlets
- [ ] Grid-down = reduced water-heater temps = Legionella bloom

### Phase AC4: Boil-order feed ingestion
**Effort:** S · **Depends on:** — · **Inspiration:** EPA CMDP, WaterISAC
- [ ] CDC BRFSS / UK DWI / Santé publique France boil-water advisory ingestion
- [ ] Household-facing checklist with duration tracking

### Phase AC5: Cistern cleaning cycle + first-flush sizing
**Effort:** S · **Depends on:** C5 · **Inspiration:** Texas A&M AgriLife RWH manual, ARCSA standards
- [ ] Annual disinfection SOP (50 mg/L chlorine, 24 h contact, flush)
- [ ] First-flush diverter sizing calc (1 gal per 100 sqft catchment)

### Phase AC6: Source complexity ladder
**Effort:** S · **Depends on:** AC1 · **Inspiration:** WHO Sanitary Inspection Forms
- [ ] Treatment-complexity scoring: protected spring (1) < deep well (2) < shallow well (3) < rainwater (4) < stream (5) < lake (6) < urban-surface (7)
- [ ] Drives treatment-train recommendation engine

---

## Tier AD — Community Health Vigilance + Crisis Archaeology

### Phase AD1: Pod health pulse
**Effort:** S · **Depends on:** federation · **Inspiration:** Flu Near You, CMU Delphi
- [ ] Anonymous symptom aggregator → pod-level Rt estimate
- [ ] Early-warning without per-person tracking
- [ ] **PRIVACY:** on-device only, no identifiers synced

### Phase AD2: Stock mosaic (opt-in, category-only)
**Effort:** S · **Depends on:** federation · **Inspiration:** Red Cross neighborhood CERT
- [ ] Category-level heatmap ("3 households have >30d water")
- [ ] Household-level opacity tiers; identifies gaps without doxxing preppers

### Phase AD3: Mutual-aid queue
**Effort:** S · **Depends on:** federation · **Inspiration:** Buy Nothing Project, Freecycle
- [ ] Request / offer board with auto-fill matching rules + cooldowns
- [ ] Turns intent into action before fatigue

### Phase AD4: Sick-call roster
**Effort:** S · **Depends on:** — · **Inspiration:** LDS ward Relief Society rotations
- [ ] Rotating caregiver schedule prevents one-household burnout

### Phase AD5: Post-event welfare census
**Effort:** S · **Depends on:** — · **Inspiration:** ARRL ARES welfare traffic, SKYWARN
- [ ] "Reply OK" roll-call with escalation timer
- [ ] Pinpoints who needs wellness check

### Phase AD6: K6 / PHQ-2 anonymous check-in
**Effort:** S · **Depends on:** AD0 privacy gate · **Inspiration:** VA mental-health screeners
- [ ] Anonymous Kessler-6 + PHQ-2 self-screen with local-only results
- [ ] Crisis-line fallback links baked in
- [ ] **PRIVACY:** store on-device only; never sync identifiers

### Phase AD7: Post-event after-action archive
**Effort:** S · **Depends on:** L2 · **Inspiration:** Army AAR doctrine, NTSB investigation format
- [ ] Supply autopsy: this item lasted N months; that one failed early
- [ ] Structured "failed / sustained / adapted / surprised us" capture
- [ ] Compounds learning across events

### Phase AD8: Historical crisis case library
**Effort:** M · **Depends on:** — · **Inspiration:** FEWS NET, ICRC archives, academic famine studies
- [ ] Structured lessons: Great Depression, Blitz 1940, Sarajevo 1992-96, Special Period Cuba, Venezuela 2014+, Beirut 2019+, Texas Feb-2021, Ukraine 2022+
- [ ] Case-based reasoning beats principle memorization

### Phase AD9: Oral history capture
**Effort:** S · **Depends on:** — · **Inspiration:** StoryCorps DIY, Library of Congress Veterans History Project
- [ ] Audio interview template + local transcription pipeline (whisper.cpp from S6)
- [ ] Elder survivors' primary-source knowledge dies with them
- [ ] Informed-consent template; OCAP principles for indigenous communities

---

## Tier AE — OPSEC / Privacy Hygiene (Normal-Privacy Framing)

**Framing gate:** every phase clearly frames as everyday privacy, not LE evasion. No adversarial language.

### Phase AE1: Cover-story template library
**Effort:** S · **Depends on:** — · **Inspiration:** journalism source-protection guides
- [ ] Plausible benign answers to bulk-buying / range-trip / garden-size questions
- [ ] Reduces awkward disclosures

### Phase AE2: Social-footprint self-audit
**Effort:** M · **Depends on:** — · **Inspiration:** Sherlock, Intelius scrubbing
- [ ] Scans user-provided handles for prep-revealing posts (keywords, geotags)
- [ ] Shows what strangers can learn

### Phase AE3: Address privacy scorer
**Effort:** S · **Depends on:** — · **Inspiration:** Michael Bazzell *Extreme Privacy*
- [ ] Rates PO box vs CMRA vs residential per USPS Form 1583 rules
- [ ] Actionable hardening steps

### Phase AE4: EXIF scrubber
**Effort:** S · **Depends on:** — · **Inspiration:** ExifTool, Signal's scrubber
- [ ] Drag-and-drop metadata stripper before sharing (GPS, serials, timestamps in background)
- [ ] One-click hygiene

### Phase AE5: Gray-man checklist
**Effort:** S · **Depends on:** — · **Inspiration:** travel-safety literature
- [ ] Wardrobe / gear reference to blend in (avoid 5.11, MultiCam, morale patches)
- [ ] Reduces target profile

### Phase AE6: Vehicle-profile audit
**Effort:** S · **Depends on:** — · **Inspiration:** auto-theft prevention guides
- [ ] Self-rates bumper stickers, racks, visible cargo
- [ ] Low-friction awareness

### Phase AE7: Compartmentalization ledger
**Effort:** S · **Depends on:** — · **Inspiration:** intelligence need-to-know doctrine
- [ ] Who-knows-what matrix with trust tiers (family / pod / acquaintance)
- [ ] Prevents oversharing drift

---

## Tier AF — Self-Defense Reference (REFERENCE-ONLY, HARD LIMITS)

**HARD LIMITS enforced app-wide:**
- NO ballistic solvers, NO range cards, NO target prioritization, NO ambush templates
- All content cited to statute / doctrine / primary source
- No "engagement" language; no tactical targeting tools
- Every phase header carries reference-only disclaimer

### Phase AF1: State force-of-law reference
**Effort:** M · **Depends on:** AF0 disclaimer gate · **Inspiration:** USCCA, Handgun Law US
- [ ] Castle doctrine / duty-to-retreat / brandishing laws by US state
- [ ] Cited to statute only; informational

### Phase AF2: Force-continuum reference
**Effort:** S · **Depends on:** — · **Inspiration:** FLETC / IACP use-of-force models
- [ ] Presence → verbal → empty-hand → intermediate → lethal ladder
- [ ] Frames proportionality

### Phase AF3: De-escalation playbook
**Effort:** S · **Depends on:** — · **Inspiration:** Thompson's *Verbal Judo*, CIT training
- [ ] Verbal-judo scripts + tactical disengagement
- [ ] Avoids force entirely

### Phase AF4: Home defense planning SOP
**Effort:** S · **Depends on:** — · **Inspiration:** Massad Ayoob MAG-20 civilian curriculum
- [ ] Safe-room selection, family assembly points, 911 script
- [ ] Planning, not targeting

### Phase AF5: Run/Hide/Fight public-ref card
**Effort:** S · **Depends on:** — · **Inspiration:** DHS "Run Hide Fight" (public domain)
- [ ] Active-shooter civilian response reference

### Phase AF6: Trespass + firearm-storage legality per state
**Effort:** M · **Depends on:** — · **Inspiration:** state DNR guides, Giffords + NRA-ILA trackers, FOPA
- [ ] Posted-notice and purple-paint laws by state
- [ ] Storage / transport legality per state

---

## Tier AG — Children's Wartime Precedent + Dependency & Governance

### Phase AG1: Historical wartime-children case library
**Effort:** M · **Depends on:** AD8 · **Inspiration:** IWM / USHMM oral histories
- [ ] Operation Pied Piper, Blitz, Leningrad, Sarajevo, Aleppo displacement — curated lessons
- [ ] Evidence-based parenting framework

### Phase AG2: Child resilience ladder
**Effort:** S · **Depends on:** — · **Inspiration:** AAP resilience guidelines
- [ ] Age-graded scenario exposure (lights-out dinner → camp night → 72h drill)
- [ ] Gradual habituation

### Phase AG3: Separation protocol packet
**Effort:** S · **Depends on:** J4, J5 · **Inspiration:** WWII evacuee ID-tag system
- [ ] Documented evac-to-relatives packet (auth letter, medical POA, code words)
- [ ] Prevents chaos at separation point

### Phase AG4: Education continuity offline cache
**Effort:** M · **Depends on:** R11, J6 · **Inspiration:** refugee-camp schooling programs
- [ ] Khan Academy Lite + Project Gutenberg children's shelf
- [ ] Routine preservation is resilience

### Phase AG5: Pediatric comfort loadout
**Effort:** S · **Depends on:** existing loadouts · **Inspiration:** FEMA Ready Kids, AAP disaster pediatrics
- [ ] Comfort object, photos, meds, ID card per child
- [ ] Child-specific go-bag template

### Phase AG6: Emotional-pattern guide
**Effort:** S · **Depends on:** AG1 · **Inspiration:** child-psychiatry Blitz cohort studies
- [ ] Historically-validated coping rituals (bedtime routine preservation, story-telling)

### Phase AG7: Infrastructure dependency graph
**Effort:** M · **Depends on:** — · **Inspiration:** DHS CISA sector interdependency studies
- [ ] Node-edge graph: grid → well → water → hygiene → health
- [ ] Visual cascade

### Phase AG8: Cascade timeline ("T+N hours until X fails")
**Effort:** S · **Depends on:** AG7 · **Inspiration:** Koppel *Lights Out*, Black Start studies
- [ ] Per-household cascade timing given outage type
- [ ] Converts abstract risk to concrete hours

### Phase AG9: Critical-node rank + SPOF audit
**Effort:** S · **Depends on:** AG7 · **Inspiration:** FMEA
- [ ] Weighted ranking of single points (well pump, furnace igniter, CPAP)
- [ ] Checklist flags solo water/heat/egress

### Phase AG10: Utility contact ledger
**Effort:** S · **Depends on:** — · **Inspiration:** CA PG&E Medical Baseline program
- [ ] Outage numbers, medical-priority program enrollment, PSPS registries
- [ ] Pre-crisis paperwork avoids crisis-time scramble

---

## Tier AH — Economics, Governance & Working Animals

### Phase AH1: Hour ledger (time-banking)
**Effort:** M · **Depends on:** I1 · **Inspiration:** Edgar Cahn time-dollars, TimeBanks USA, hOurworld
- [ ] Hour-denominated exchange ledger (IRS non-taxable)
- [ ] Dual-sign attestation on completed trades

### Phase AH2: Skill marketplace + peer attestation
**Effort:** S · **Depends on:** AH1 · **Inspiration:** Ithaca HOURS, LETSystems, PGP web-of-trust
- [ ] Offer / request board denominated in hours not dollars
- [ ] Reputation via signed endorsements from completed trades (no star ratings)

### Phase AH3: Barter price discovery + perishability discount
**Effort:** S · **Depends on:** O1 · **Inspiration:** FairMarket, USDA shelf-life tables
- [ ] Rolling median of recent trades per category
- [ ] Time-decay valuation for food/meds nearing expiry
- [ ] Moves stock before loss

### Phase AH4: Tradeable-vs-personal toggle
**Effort:** S · **Depends on:** — · **Inspiration:** HIPAA personal-health carveout pattern
- [ ] Per-inventory-item flag (never-trade insulin vs freely-trade rice)
- [ ] Prevents desperate mistakes

### Phase AH5: Commons simulator + public-goods framework
**Effort:** M · **Depends on:** V1 · **Inspiration:** Elinor Ostrom CPR governance, VCM experimental econ
- [ ] Tabletop simulator for shared-resource depletion (well, fuel cache)
- [ ] Contribution / free-rider modeling quantifies defection risk

### Phase AH6: Sharing-agreement templates
**Effort:** S · **Depends on:** I2 · **Inspiration:** Sustainable Economies Law Center
- [ ] Legal-lite MOUs: joint generator, tool library, shared well
- [ ] Pre-negotiated trust avoids crisis-time dispute

### Phase AH7: Mediation ladder
**Effort:** S · **Depends on:** — · **Inspiration:** Quaker clearness committees, restorative justice
- [ ] Peer talk → mediator → council → federation arbitration
- [ ] Prevents pod split

### Phase AH8: Defection-signal (anonymous, mediator-gated)
**Effort:** S · **Depends on:** AH7 · **Inspiration:** whistleblower ombudsman models
- [ ] Anonymous flag for chronic over-draw; threshold-triggered mediator notice
- [ ] **POD-WEAPONIZATION SAFEGUARD:** never public, always mediator-gated, logged for audit

### Phase AH9: Ration-fairness engine + dynamic rebalance
**Effort:** M · **Depends on:** A2 · **Inspiration:** Minnesota Starvation Experiment, WFP ration scales
- [ ] Need-based allocation (child / pregnant / elderly / laborer kcal multipliers)
- [ ] Recomputes rations as stores shift or new mouths arrive

### Phase AH10: Caloric-equity rolling audit
**Effort:** S · **Depends on:** AH9 · **Inspiration:** Amartya Sen capability approach
- [ ] Visual fairness audit over rolling 7-day window
- [ ] Transparency without surveillance

### Phase AH11: Logistics intelligence bundle
**Effort:** M · **Depends on:** — · **Inspiration:** ISM supplier-tier, Wilson EOQ, post-COVID resilience research
- [ ] JIT fragility detector — flags categories with < 7-day upstream supply
- [ ] Supplier redundancy score (1 / 2 / 3+ sources per item)
- [ ] Shipping-lane dependency map (Panama / Suez / LA / rail corridors) linked to inventory categories
- [ ] Port-closure impact predictor ("if X closes, Y hits your stock in Z days")
- [ ] Manufactured-good substitution catalog (homemade vs commercial)
- [ ] Inventory velocity + reorder-point + kit consolidation + evac volume optimizer

### Phase AH12: Working-animal signal library + bioindicator reference
**Effort:** S · **Depends on:** — · **Inspiration:** AKC Herding, Temple Grandin, Jon Young *What the Robin Knows*
- [ ] K9 whistle + hand-signal library (herding, SAR, perimeter, LGD commands)
- [ ] Livestock body-language / vocalization stress cues (cattle, horse, chicken, goat)
- [ ] Wild alarm-call reference (songbird, crow, squirrel) — passive 300m intrusion-detection

---

## Tier AI — Foraging, Plant & Mushroom ID

### Phase AI1: Offline plant-ID model
**Effort:** M · **Depends on:** — · **Inspiration:** Pl@ntNet lite, Seek (iNaturalist)
- [ ] Bundle on-device image-classification model (~200 MB; species set filtered to NOMAD region)
- [ ] Photo → species with confidence + regional-match flag

### Phase AI2: Regional foraging calendar (WildSeasonGrid)
**Effort:** S · **Depends on:** — · **Inspiration:** Samuel Thayer harvest calendars
- [ ] Species × week × ecoregion heatmap
- [ ] "What's in season near me now?" glance card

### Phase AI3: Deadly-lookalike ledger
**Effort:** S · **Depends on:** — · **Inspiration:** Mushroaming, NAMA fatality reviews
- [ ] Side-by-side pair cards (water hemlock vs Queen Anne's; death cap vs puffball; false vs true morel; pokeweed vs elderberry)
- [ ] 90% of fatal forage poisonings are lookalike errors

### Phase AI4: Toxicity-ingestion decision tree
**Effort:** S · **Depends on:** AI3 · **Inspiration:** AAPCC Webpoison categories
- [ ] Plant/fungal ingestion → symptom-onset → Poison Control triage
- [ ] Collapses panic into minutes

### Phase AI5: Spore-print atlas + personal journal
**Effort:** S · **Depends on:** AI1 · **Inspiration:** Michael Kuo's MushroomExpert keys
- [ ] Spore-print color + microscopy reference
- [ ] Photo-journal slot for user's own prints

### Phase AI6: HAB / shellfish-closure feed overlay
**Effort:** S · **Depends on:** — · **Inspiration:** NOAA HAB-OFS, state DOH shellfish advisories
- [ ] Red-tide / PSP / ASP / DSP overlay on coastal foraging waypoints
- [ ] **SAFETY:** PSP has no taste; death in hours

### Phase AI7: Cambium + famine-food edibility reference
**Effort:** S · **Depends on:** — · **Inspiration:** Mors Kochanski
- [ ] Inner-bark protocols (pine, spruce, willow, birch, slippery elm) — harvest-without-killing
- [ ] Bark / seaweed / lichen / cattail-pollen tiers

### Phase AI8: Ethnobotanical vault + foraging legality
**Effort:** S · **Depends on:** — · **Inspiration:** OCAP/CARE data-sovereignty, USFS / BLM / NPS regs
- [ ] Indigenous / traditional-use entries with elder-attribution + permission tier + OCAP flags
- [ ] State/province/federal foraging regs per waypoint
- [ ] **LEGAL:** NPS prohibits most foraging; surfaces in UI

---

## Tier AJ — Offline Navigation (GPS-denied)

### Phase AJ1: Shadow-stick / sun-compass solver
**Effort:** S · **Depends on:** — · **Inspiration:** 500-year-old technique
- [ ] Stick + two shadow tips → true north with latitude/season correction

### Phase AJ2: Polaris-altitude latitude + Southern Cross
**Effort:** S · **Depends on:** AJ9 · **Inspiration:** marine celestial-nav primer
- [ ] Polaris altitude = latitude; Octantis pole-finder for southern hemisphere

### Phase AJ3: Lunar azimuth table
**Effort:** S · **Depends on:** — · **Inspiration:** existing moon-phase calc (shipped)
- [ ] Moonrise/set azimuth by date/lat; night nav without stars

### Phase AJ4: Sun-angle clock (no-watch time)
**Effort:** S · **Depends on:** — · **Inspiration:** equation-of-time pedagogy
- [ ] Time-of-day from sun altitude + azimuth with hemispheric EoT correction

### Phase AJ5: Dead-reckoning error budget
**Effort:** M · **Depends on:** — · **Inspiration:** marine CYC piloting
- [ ] Bearing + pace + drift + declination logger
- [ ] Gaussian error-ellipse growth per leg; knowing uncertainty matters more than knowing position

### Phase AJ6: Improvised sextant + HO-249 tables
**Effort:** M · **Depends on:** AJ9 · **Inspiration:** Kamal, shadow-square, HO-249 abridged
- [ ] Plumb-protractor sextant math + sight-reduction tables
- [ ] Celestial fix with zero gear

### Phase AJ7: Terrain-association route builder
**Effort:** S · **Depends on:** — · **Inspiration:** orienteering pedagogy
- [ ] Landmark-chain (handrail / backstop / catching-feature) without coordinate reference

### Phase AJ8: Barometric altimeter calibration
**Effort:** S · **Depends on:** AM1 · **Inspiration:** USGS benchmark lookups
- [ ] Drift correction via known-elevation benchmarks along route

### Phase AJ9: Offline star map
**Effort:** M · **Depends on:** — · **Inspiration:** Hipparcos bright-star subset
- [ ] Constellation renderer by date / lat / time (< 5 MB bundled)
- [ ] Powers AJ2 + AJ6

---

## Tier AK — Game Processing & Fishing

### Phase AK1: Per-species field-dressing SOPs
**Effort:** M · **Depends on:** — · **Inspiration:** MeatEater, Steven Rinella, USDA FSIS
- [ ] Whitetail / elk / moose / hog / pronghorn / upland bird / waterfowl / rabbit / squirrel / trout / salmon protocols
- [ ] Step-by-step avoids contamination + spoilage

### Phase AK2: Live-weight → freezer yield calculator
**Effort:** S · **Depends on:** — · **Inspiration:** state F&W yield tables
- [ ] Live → field-dressed → hanging → boneless-trim math per species + condition factor

### Phase AK3: Aging climate matrix + bone-sour risk
**Effort:** S · **Depends on:** — · **Inspiration:** USDA aging standards
- [ ] Dry/wet-age window × temp × RH × species with spoilage flag
- [ ] Carcass-cooling curve (mass + ambient + ventilation → core-temp timeline)

### Phase AK4: Offal utility + zoonosis flag
**Effort:** S · **Depends on:** G11, AA10 · **Inspiration:** CWD Alliance data
- [ ] Liver / heart / kidney / tongue / marrow prep per species with trichinella / fluke / CWD / brucellosis / tularemia lookup
- [ ] **LEGAL:** CWD-positive disposal regs vary by state

### Phase AK5: Hide + rawhide processing path
**Effort:** S · **Depends on:** Q4 · **Inspiration:** Mors Kochanski, Matt Richards
- [ ] Brain-tan / bark-tan / alum / rawhide method trees with timeline + chemical math

### Phase AK6: Humane dispatch + emergency livestock salvage
**Effort:** S · **Depends on:** G11 · **Inspiration:** AVMA-aligned
- [ ] Emergency euthanasia + salvage protocol for injured livestock
- [ ] **LEGAL:** on-farm slaughter regs vary by jurisdiction

### Phase AK7: Fish reg lookup + bite predictor
**Effort:** M · **Depends on:** — · **Inspiration:** state F&W data, Solunar Theory
- [ ] Species × waterbody × season × bag × size-limit lookup per state
- [ ] Solunar + water-temp + barometric-trend + turbidity fish-activity model

### Phase AK8: Toxic-fish + scombroid + ciguatera ID
**Effort:** S · **Depends on:** — · **Inspiration:** EPA fish-consumption advisories
- [ ] Scombroid-prone / ciguatera-risk / pufferfish / mercury-heavy species by region
- [ ] Fish-poisoning is invisible pre-symptom

### Phase AK9: Aquaponics + passive-gear reference
**Effort:** S · **Depends on:** G8 · **Inspiration:** UVI ratios
- [ ] Tank gal × fish density × plant-biofilter surface math
- [ ] Trotline / jugline / gillnet / fyke / weir legality-by-state + diagrams
- [ ] **LEGAL:** most states prohibit passive gear for non-commercial

### Phase AK10: Fish preservation + parasite safety
**Effort:** S · **Depends on:** G7 · **Inspiration:** FDA 21 CFR 123
- [ ] Smoke / salt / pickle / lutefisk / gravlax / surströmming protocols with a_w + pH targets
- [ ] Anisakis freeze-kill (-4 °F / 7 d or -31 °F / 15 h)

---

## Tier AL — Outdoor Cooking Depth

### Phase AL1: Fire-heat temperature chart
**Effort:** S · **Depends on:** — · **Inspiration:** SCA / Boy Scout cookery
- [ ] Flame / ember / coal ranges × technique (searing / roasting / baking / slow)

### Phase AL2: Dutch-oven coal-count calculator
**Effort:** S · **Depends on:** — · **Inspiration:** Lodge / IDOS Society doctrine
- [ ] Diameter + 3 top, diameter - 3 bottom = 350 °F formula + altitude / wind adjustments

### Phase AL3: Rocket-stove design + fuel-efficiency math
**Effort:** M · **Depends on:** — · **Inspiration:** Aprovecho Research
- [ ] J-tube / L-tube geometry + heat-riser ratio + fuel-load math
- [ ] 40% less fuel at objective efficiency

### Phase AL4: Solar-oven performance curve
**Effort:** S · **Depends on:** G5 · **Inspiration:** Solar Cookers International
- [ ] Reflector area + absorber mass + glazing loss → peak-temp model by lat + month + sky

### Phase AL5: Altitude boiling + canning safety
**Effort:** S · **Depends on:** G7 · **Inspiration:** USDA-binding canning adjustments
- [ ] Boil temp + extended cook times by elevation (8000 ft = 197 °F)
- [ ] Pressure-canning altitude adjustments per USDA Complete Guide

### Phase AL6: Pit cooking SOP (hangi / bean-hole / luau / pachamanca)
**Effort:** S · **Depends on:** — · **Inspiration:** 4000-year-old tech
- [ ] Pit depth, stone mass, preheat hours, food-load timing

### Phase AL7: Haybox retained-heat calculator
**Effort:** S · **Depends on:** — · **Inspiration:** WWII haybox revival
- [ ] R-value → cook-finish time for grains / stews
- [ ] Fuel-free second half of cooking

### Phase AL8: Bulk-cooking math + foil-packet reference
**Effort:** S · **Depends on:** A2 · **Inspiration:** USDA quantity-recipe tables
- [ ] Recipe × household size × days → portioning calculator
- [ ] Foil-packet ingredient-pairing + time/temp matrix

---

## Tier AM — Personal Weather Station

### Phase AM1: Siting SOP (WMO + CoCoRaHS)
**Effort:** S · **Depends on:** — · **Inspiration:** WMO Guide No. 8
- [ ] Stevenson screen build, ground clearance, thermal exposure, rain-gauge placement
- [ ] Most home stations read 4 °F high from siting error

### Phase AM2: CWOP uploader (APRS-IS)
**Effort:** M · **Depends on:** B2 · **Inspiration:** NOAA Citizen Weather Observer Program
- [ ] APRS-IS weather-packet formatter + callsign registration path
- [ ] Your station becomes public data

### Phase AM3: Station bridge adapter
**Effort:** M · **Depends on:** — · **Inspiration:** Home Assistant integrations
- [ ] Ambient / Davis / Ecowitt / Tempest JSON → NOMAD internal weather bus

### Phase AM4: Calibration schedule + sensor drift alerts
**Effort:** S · **Depends on:** AM3 · **Inspiration:** manufacturer cal procedures
- [ ] Per-sensor cal + desiccant-replace + recoat intervals with reminders

### Phase AM5: Frost-point alert engine
**Effort:** S · **Depends on:** Z2 · **Inspiration:** ag extension frost models
- [ ] Dewpoint + windspeed + sky-cover → radiative-frost probability per overnight

### Phase AM6: METAR/AWOS reconciliation
**Effort:** S · **Depends on:** AM1 · **Inspiration:** bias-correction doctrine
- [ ] Delta-log vs nearest METAR with bias-correction suggestion

---

## Tier AN — Geology & Hydrology Hazards

### Phase AN1: Karst + sinkhole risk lookup
**Effort:** S · **Depends on:** — · **Inspiration:** USGS karst map
- [ ] Polygon lookup per waypoint with sinkhole-density score

### Phase AN2: Liquefaction zones
**Effort:** S · **Depends on:** — · **Inspiration:** USGS / state geology (CA, PNW, New Madrid, Charleston)
- [ ] Earthquake-amplifier zones per waypoint

### Phase AN3: Landslide + debris-flow hazard
**Effort:** S · **Depends on:** K4 · **Inspiration:** USGS PS-08 landslide index
- [ ] Slope + soil + saturation + recent-rainfall scoring
- [ ] Debris flow after wildfire is #1 post-fire killer

### Phase AN4: Watershed flood proximity
**Effort:** M · **Depends on:** A5 · **Inspiration:** USGS NHD + gauge data
- [ ] Nearest USGS gauge + stage + flood threshold + upstream-lag calc

### Phase AN5: Snowmelt runoff + SWE calc
**Effort:** S · **Depends on:** AN4 · **Inspiration:** SNOTEL / NRCS
- [ ] SWE × basin area × degree-day factor → melt-runoff volume + timing

### Phase AN6: Cave safety reference
**Effort:** S · **Depends on:** — · **Inspiration:** NSS cave-safety doctrine
- [ ] CO2 stratification + sump risk + hypothermia gradient + SRT check
- [ ] **LEGAL:** white-nose bat protocols mandatory in many states

### Phase AN7: Abandoned-mine hazard database
**Effort:** S · **Depends on:** — · **Inspiration:** USGS MRDS, state AML inventories
- [ ] Polygon lookup with hazard class (open shaft / adit / subsidence)
- [ ] **LEGAL:** trespass + MSHA warnings surfaced in UI

### Phase AN8: Radon-by-geology + regional well chem risk
**Effort:** S · **Depends on:** Z5 · **Inspiration:** EPA radon zones, USGS groundwater chem
- [ ] Bedrock-type → radon class (granite/uranium-rich = high; limestone = variable)
- [ ] Arsenic (glacial aquifers), fluoride (volcanic), uranium (sandstone), nitrate (ag-land) risk per region

---

## Tier AO — Local Ecosystem Knowledge Capture

### Phase AO1: "My Land Knows" georeferenced knowledge layer
**Effort:** M · **Depends on:** — · **Inspiration:** OnX Hunt markup, indigenous land-knowledge projects
- [ ] Mushroom patches, springs, deer beds, blowdowns, fence crossings
- [ ] Privacy tiers: private / family / trusted-neighbor / federation

### Phase AO2: Phenology journal
**Effort:** S · **Depends on:** — · **Inspiration:** USA-NPN Nature's Notebook
- [ ] Bloom / leaf-out / frost / bird-arrival log per property
- [ ] Year-over-year delta + climate-drift calc

### Phase AO3: Keystone-tree + apex-species registry
**Effort:** S · **Depends on:** AO1 · **Inspiration:** arborist + old-growth inventory
- [ ] DBH + age estimate + succession role per tagged tree

### Phase AO4: Invasive-species encroachment log
**Effort:** S · **Depends on:** — · **Inspiration:** iMapInvasives export format
- [ ] First-sighting + spread-rate + treatment log per site
- [ ] Early detection = cheap removal

### Phase AO5: Pollinator + birding observation log
**Effort:** S · **Depends on:** — · **Inspiration:** Bumble Bee Watch, eButterfly, eBird export
- [ ] Bee / butterfly / moth / hummingbird observations

### Phase AO6: Federation-scoped neighbor knowledge exchange
**Effort:** M · **Depends on:** AO1, federation · **Inspiration:** Solid, ActivityPub
- [ ] Per-entry consent + expiry + attribution
- [ ] Community knowledge without centralized harvester

### Phase AO7: Water dowsing / witching log (empirical record)
**Effort:** S · **Depends on:** AC2 · **Inspiration:** hydrogeology literature
- [ ] Strike / dry-hole log with verifiable water-table + yield
- [ ] **FLAG:** dowsing efficacy scientifically disputed — logged as empirical record, not method endorsement

---

## Tier AP — Digital Asset Sovereignty

### Phase AP1: BIP39 / SLIP39 seed vault
**Effort:** M · **Depends on:** B3, vault · **Inspiration:** Jameson Lopp seed-storage taxonomy
- [ ] Seed-phrase registry with passphrase hints, derivation path notes, metal-backup serial log (Cryptosteel / Blockplate)
- [ ] Seeds are the single point of failure for self-custody

### Phase AP2: Hardware wallet ledger
**Effort:** S · **Depends on:** — · **Inspiration:** Coldcard best-practices
- [ ] Ledger / Trezor / Coldcard / Keystone inventory
- [ ] Firmware version + purchase provenance + tamper-seal photo + PIN attempt counter

### Phase AP3: Multi-sig quorum map
**Effort:** S · **Depends on:** AP1 · **Inspiration:** Unchained Capital vault model
- [ ] 2-of-3 / 3-of-5 topology with co-signer identity, geographic distribution, recovery drill schedule

### Phase AP4: Crypto estate plan
**Effort:** M · **Depends on:** B4 · **Inspiration:** Casa Covenant
- [ ] Encrypted posthumous envelope (triggered by existing dead-man switch)
- [ ] Executor instructions, exchange recovery, tax-basis handoff

### Phase AP5: U2F / FIDO2 key registry
**Effort:** S · **Depends on:** R4 · **Inspiration:** Yubico enterprise deployment guide
- [ ] YubiKey / SoloKey / Nitrokey inventory per service (primary + backup + offsite)

### Phase AP6: Cold-storage air-gap SOP
**Effort:** S · **Depends on:** AP1-AP2 · **Inspiration:** Glacier Protocol
- [ ] PSBT transport via QR/SD, offline machine build spec, verification ceremony checklist

### Phase AP7: 2FA reset kit
**Effort:** S · **Depends on:** R4 · **Inspiration:** NIST SP 800-63B
- [ ] TOTP seed backup (encrypted) + scratch-code registry + SMS-fallback rotation
- [ ] Phone loss = account lockout cascade without this

---

## Tier AQ — SOHO Business Continuity

### Phase AQ1: Client notification cascade
**Effort:** S · **Depends on:** — · **Inspiration:** NIST SP 800-34 COOP
- [ ] Priority tiers + pre-drafted delay templates (power / weather / medical) + SLA breach math

### Phase AQ2: Revenue buffer + runway calculator
**Effort:** S · **Depends on:** — · **Inspiration:** Profit First
- [ ] Operating-reserve math: burn rate, runway months, variable / fixed cost split, tax-deferred buffer tier

### Phase AQ3: Workstation redundancy matrix
**Effort:** S · **Depends on:** R6 · **Inspiration:** 3-2-1 extended to compute
- [ ] Primary / backup / air-gap rig inventory with config-drift detection, restore-from-image drill schedule

### Phase AQ4: COOP plan template generator
**Effort:** M · **Depends on:** — · **Inspiration:** FEMA COOP framework
- [ ] Essential-functions, alternate-facilities, delegation-of-authority, reconstitution sections
- [ ] SOHO-scaled COOP doesn't exist; they need it more than enterprises

### Phase AQ5: Business dependency graph
**Effort:** M · **Depends on:** AG7 · **Inspiration:** SRE error-budget + dependency mapping
- [ ] Supplier / client / tool / network criticality map
- [ ] SPOF flagging (one cloud vendor, 60% revenue from one client)

### Phase AQ6: Offline invoice + receipt archive
**Effort:** S · **Depends on:** — · **Inspiration:** Hledger + FreshBooks export
- [ ] Offline PDF vault with search, tax-year partition, client-lookup index
- [ ] IRS audit during grid-down is a real tail risk

---

## Tier AR — Biosecurity & Farm Disease

### Phase AR1: Avian-flu response SOP
**Effort:** M · **Depends on:** — · **Inspiration:** USDA Defend the Flock
- [ ] H5N1/H5N2 flock-surveillance, symptom checklist, APHIS contact tree, depopulation decision tree, PPE doffing order

### Phase AR2: Farm biosecurity zone layout
**Effort:** S · **Depends on:** — · **Inspiration:** Iowa State Extension
- [ ] Dirty / clean / restricted map with footbath stations, tool segregation, visitor SOP

### Phase AR3: 21-day quarantine protocol for incoming livestock
**Effort:** S · **Depends on:** — · **Inspiration:** AAVLD guidelines
- [ ] Pen distance, test battery, observation log

### Phase AR4: Carcass disposal decision matrix
**Effort:** S · **Depends on:** — · **Inspiration:** USDA Carcass Disposal handbook
- [ ] Burn / bury / compost / render with local-reg lookup, groundwater setbacks, pit dimensions

### Phase AR5: Zoonosis register
**Effort:** S · **Depends on:** — · **Inspiration:** CDC One Health
- [ ] Per-household zoonotic risk inventory (rabies, leptospirosis, Q-fever, psittacosis, salmonella)
- [ ] Exposure pathway + mitigation

### Phase AR6: Vector-ID cards
**Effort:** S · **Depends on:** — · **Inspiration:** CDC vector surveillance
- [ ] Mosquito / tick / flea / midge ID with disease-carried matrix (EEE, Lyme, plague, bluetongue)

### Phase AR7: Vaccination calendar (poultry / small ruminant / canine)
**Effort:** S · **Depends on:** G11 · **Inspiration:** AVMA vaccination guidelines
- [ ] Marek's, Newcastle, ILT, CDT, scrapie, rabies, DHPP schedule with cold-chain log

---

## Tier AS — Specialized SAR Disciplines

All phases REFERENCE-ONLY. Certification required for operational use. UI shows disclaimers.

### Phase AS1: Swiftwater rescue reference
**Effort:** S · **Depends on:** — · **Inspiration:** Rescue 3 International SRT
- [ ] Throw-bag technique, defensive/aggressive swimming, rope angle, strainer/sieve recognition

### Phase AS2: Ice-rescue SOP
**Effort:** S · **Depends on:** — · **Inspiration:** Dive Rescue Int'l ice curriculum
- [ ] Self-rescue (ice awls), reach-throw-row-go-tow hierarchy, ice-thickness table

### Phase AS3: High-angle awareness
**Effort:** S · **Depends on:** — · **Inspiration:** NFPA 1006, Rigging for Rescue
- [ ] Mechanical advantage (2:1, 3:1, 5:1 Z-rig), anchor SOP (EARNEST/SERENE), belay protocol

### Phase AS4: Avalanche rescue depth
**Effort:** S · **Depends on:** E3 · **Inspiration:** AIARE level-1
- [ ] Beacon search (signal / coarse / fine), probe-strike protocol, V-trench shovel geometry
- [ ] 35-minute survival cliff

### Phase AS5: Confined-space awareness
**Effort:** S · **Depends on:** — · **Inspiration:** OSHA 1910.146
- [ ] Permit-required classification, 4-gas monitor sequence (O2 / LEL / CO / H2S), retrieval-line SOP
- [ ] Farm silos / cisterns / wells kill helpers more than original victims

### Phase AS6: Collapsed-structure awareness
**Effort:** S · **Depends on:** — · **Inspiration:** FEMA US&R Structures Specialist
- [ ] Cribbing 4x4 box / criss-cross, void identification, secondary-collapse indicators

### Phase AS7: Technical tree-rescue
**Effort:** S · **Depends on:** — · **Inspiration:** ArborMaster, ANSI Z133
- [ ] Aloft-arborist rescue, cut-and-chuck avoidance, spider-line access

---

## Tier AT — Financial Preparedness Depth

### Phase AT1: Portfolio stress-test scenarios
**Effort:** M · **Depends on:** — · **Inspiration:** Bridgewater All Weather, Dalio *Changing World Order*
- [ ] 50% equity crash / hyperinflation / bank holiday / crypto winter / USD reserve-status loss
- [ ] Per-scenario recovery timeline

### Phase AT2: Insurance coverage audit
**Effort:** M · **Depends on:** — · **Inspiration:** Consumer Reports audit framework
- [ ] Homeowner / auto / life / umbrella / flood / earthquake gap analysis
- [ ] Exclusion callouts (mold, earth movement, pandemic)

### Phase AT3: Debt elimination calculator
**Effort:** S · **Depends on:** — · **Inspiration:** Dave Ramsey + Mr Money Mustache
- [ ] Avalanche vs snowball math, rate-arbitrage detection, refi trigger thresholds

### Phase AT4: Emergency-fund tier calculator
**Effort:** S · **Depends on:** — · **Inspiration:** Bogleheads emergency-fund ladder
- [ ] 1 / 3 / 6 / 12 / 24 month tiers with instrument mapping (checking / HYSA / T-bills / I-bonds / cash / metals)

### Phase AT5: Asset-portability classifier
**Effort:** S · **Depends on:** — · **Inspiration:** FerFAL Argentina memoir
- [ ] Liquidity matrix per stress type (cash / gold / crypto / art / RE / guns)

### Phase AT6: Credit freeze calendar
**Effort:** S · **Depends on:** — · **Inspiration:** Krebs on Security freeze guide
- [ ] Experian / Equifax / TransUnion / Innovis / ChexSystems / LexisNexis freeze + thaw scheduler

### Phase AT7: Income diversification tracker
**Effort:** S · **Depends on:** — · **Inspiration:** Taleb barbell strategy
- [ ] Revenue-stream count, Herfindahl concentration ratio, correlation matrix

---

## Tier AU — Specialized Comms Content

### Phase AU1: Shortwave listening schedule
**Effort:** S · **Depends on:** — · **Inspiration:** EiBi schedules, WWDXC
- [ ] VOA / BBC WS / RNE / Radio Habana / Deutsche Welle / CRI schedules by freq × time × language

### Phase AU2: Clandestine / numbers-station directory
**Effort:** S · **Depends on:** — · **Inspiration:** Priyom.org, ENIGMA 2000
- [ ] Public-domain catalog of numbers stations + clandestine broadcasters
- [ ] **LEGAL:** listening legal in US, rebroadcast is not

### Phase AU3: ARES / RACES net directory
**Effort:** S · **Depends on:** — · **Inspiration:** ARRL Net Directory
- [ ] Per-state net schedule with frequency, NCS rotation, check-in protocol

### Phase AU4: SKYWARN frequencies per state
**Effort:** S · **Depends on:** — · **Inspiration:** NWS SKYWARN program
- [ ] Spotter-net frequencies + NWS office callsign

### Phase AU5: IPAWS + EAS test calendar
**Effort:** S · **Depends on:** — · **Inspiration:** FEMA IPAWS-OPEN
- [ ] National + state EAS/WEA test schedule with message-class reference (EAN, CAE, NPT)
- [ ] Distinguishes test from real

### Phase AU6: Foreign gov / mil HF broadcast reference
**Effort:** S · **Depends on:** — · **Inspiration:** UDXF, HFGCS refs
- [ ] Listening guide
- [ ] **LEGAL:** listening legal; encrypted-content decoding varies

---

## Tier AV — Lockpicking & Physical Security

HARD LIMIT: reference-only, "my own locks" framing, state-legality gate.

### Phase AV1: Safe + lockbox inventory
**Effort:** S · **Depends on:** B3 · **Inspiration:** UL 687 standard
- [ ] UL rating (RSC / TL-15 / TL-30 / TXTL-60)
- [ ] Combo backup via Shamir split
- [ ] Relocker status, anchor method

### Phase AV2: Physical-security audit
**Effort:** S · **Depends on:** — · **Inspiration:** LPL audit framework, ASSA Abloy guide
- [ ] Deadbolt ANSI grade, strike-plate screw length, hinge-pin side, kick-resistance scoring

### Phase AV3: Window-security reference
**Effort:** S · **Depends on:** — · **Inspiration:** 3M Ultra S800, ASTM F1233
- [ ] Film mil rating, laminated glass, burglar bars, sliding-door pin-lock

### Phase AV4: Door-reinforcement DIY
**Effort:** S · **Depends on:** — · **Inspiration:** Door Armor, StrikeMaster
- [ ] 3-inch strike screws, Door Armor-style kits, jamb reinforcement, astragal selection

### Phase AV5: Safe-rating decoder
**Effort:** S · **Depends on:** AV1 · **Inspiration:** UL 687 + ASTM F883
- [ ] RSC, TL-15, TL-30, TXTL-60x6, B-rate, C-rate, gun-safe RSC-II decoder
- [ ] Marketing ratings mislead; real standard lookup

### Phase AV6: Lockpicking reference ("my own locks only")
**Effort:** S · **Depends on:** AV0 legality gate · **Inspiration:** LockPickersUnited wiki, MIT Guide to Lock Picking
- [ ] Pin-tumbler anatomy, SPP/raking theory, security-pin recognition
- [ ] **LEGAL:** possession illegal in IL / NV / OH without license; state legality lookup surfaces in UI
- [ ] Frame as "knowing lock failure modes informs buying decisions"

---

## Tier AW — Radiation & CBRN Depth

### Phase AW1: Geiger catalog + dosimeter protocol
**Effort:** S · **Depends on:** — · **Inspiration:** ORAU museum, NRC 10 CFR 20
- [ ] CDV-700/715/717, Radiacode, GQ GMC, Mazur catalog with calibration interval, dead time, detector type
- [ ] Film / TLD / OSL badge swap schedule + cumulative dose log + ALARA alerts

### Phase AW2: KI (potassium iodide) dosing reference
**Effort:** S · **Depends on:** — · **Inspiration:** FDA Guidance 2001 KI
- [ ] Age/weight matrix with contraindication flags (thyroid disease, iodine allergy)
- [ ] **MEDICAL:** KI only blocks radioiodine; consult physician

### Phase AW3: Shelter protection-factor calculator
**Effort:** M · **Depends on:** — · **Inspiration:** FEMA CPG 2-1-A1, Kearny *Nuclear War Survival Skills*
- [ ] Mass-thickness PF math (10 halving thicknesses = PF 1024)
- [ ] Shelter geometry + ventilation exchange-rate
- [ ] "Basement" isn't automatic shelter

### Phase AW4: Shelter duration + decay calculator
**Effort:** S · **Depends on:** AW3 · **Inspiration:** Kearny NWSS, FEMA Planning Guidance
- [ ] 7-10 rule decay curve
- [ ] Exit-window calculator by initial dose rate
- [ ] Leaving too early kills; staying too long starves

### Phase AW5: Decontamination station layout
**Effort:** S · **Depends on:** AA6 · **Inspiration:** FEMA CBRNE decon curriculum
- [ ] 3-zone setup (hot / warm / cold), doffing sequence, rinse/catch protocol, waste containment

### Phase AW6: Airspace + fallout plume integration
**Effort:** M · **Depends on:** E1, T6, K2 · **Inspiration:** NOAA HYSPLIT, CDC Radiation Emergencies
- [ ] Couples plume ensemble to regional weather for real-time fallout-arrival prediction
- [ ] Shelter-decision support rather than blind-take-cover

---

## Tier AX — Cyber-Physical Intersection

### Phase AX1: Digital estate takeout scheduler
**Effort:** M · **Depends on:** B4 · **Inspiration:** Google Inactive Account Manager, Apple Legacy Contact
- [ ] Google / Apple / Meta / Bitwarden / GitHub export scheduler
- [ ] Dead-man-switch trigger delivery to executor
- [ ] Accounts outlive people; unplanned lockout destroys family history

### Phase AX2: Household incident-response plan
**Effort:** M · **Depends on:** — · **Inspiration:** NIST SP 800-61 scaled to household
- [ ] Playbooks: ransomware on laptop, SIM swap, account takeover, child-device compromise
- [ ] Isolation / eradication / recovery steps
- [ ] Families are IR targets with no IR capability

### Phase AX3: Cyber-physical drill generator
**Effort:** S · **Depends on:** V1 · **Inspiration:** CISA tabletop exercise packages
- [ ] Combined scenarios: malware + weather, SIM-swap + travel, ransomware + medical event
- [ ] Real crises compound; single-axis drills miss this

### Phase AX4: Per-feature privacy impact assessment
**Effort:** M · **Depends on:** — · **Inspiration:** NIST Privacy Framework, GDPR DPIA
- [ ] What's logged locally, what touches network, what persists, retention period
- [ ] Surfaced in About page per feature
- [ ] A prepper tool that silently leaks OPSEC is worse than no tool

---

## Version log

- **2026-04-17 — v9.0** — Initial roadmap. 17 tiers (A-Q), ~76 phases.
- **2026-04-17 — v9.1** — Added Tier R (Comms / Cyber / Family-Ops Depth, 11 phases) + Tier S (Developer, Operator, Distribution, 15 phases). Totals: 19 tiers (A-S), ~102 phases.
- **2026-04-17 — v9.2** — Added Tiers T-AH (AI & simulation, hardware catalogs, drill/exercise engine, RDF + siting, energy defense, international/cultural, environmental exposure, medical depth II + alt-med, water quality depth, community health + crisis archaeology, OPSEC / privacy, self-defense reference, children's wartime precedent + infrastructure dependency + governance + working animals). Totals: 34 tiers (A-AH), 221 phases.
- **2026-04-17 — v9.3** — Added Tiers AI-AX (foraging / plant / mushroom ID, offline celestial + DR navigation, game processing + fishing + aquaculture, outdoor cooking depth, personal weather stations, geology + hydrology hazards, local-ecosystem knowledge capture, digital-asset sovereignty, SOHO business continuity, biosecurity + farm disease, specialized SAR, financial depth, specialized comms content, lockpicking + physical security, CBRN depth, cyber-physical intersection). Totals: 50 tiers (A-AX), 333 phases.

---

## Open research queries (next waves)

All known blind spots have been surveyed. Candidate areas to open in a future wave when scope is exhausted here:

- **AI-assisted decision-making**: structured prompts / chain-of-thought for specific operator roles (medic, comms, logistics)
- **Simulation depth**: Monte Carlo on evacuation route success, plume + wind ensemble
- **Content curation**: survival-creator attribution and royalty patterns for ingested YouTube archives
- **Hardware reference**: exhaustive catalog of field-serviceable gear (AR-15, Glock, AK, MDT, common generators, wood stoves) with parts diagrams — scope + legality review needed
- **International / non-English depth**: beyond translations — culturally appropriate defaults for EU, Japan, Latin America
- **Air quality / environmental exposure**: beyond Copernicus CAMS — indoor PM2.5/VOC/radon monitoring integration
- **Wilderness-tier first aid progression**: WFA → WFR → WEMT curriculum tracker
- **Animal communication**: working-dog whistle/hand-signal library, livestock body-language reference
- **Archaeology-of-crisis**: post-event documentation standards (who kept what working, which patterns failed)
