# Project N.O.M.A.D. — Roadmap

> **Baseline:** v7.44.0 (~295 tables, 1,900+ routes, 74 blueprints)
> **Updated:** 2026-04-18
> **Effort:** S (1 session), M (2-3), L (4-6), XL (7+)

Everything below requires external dependencies, hardware, significant frontend work, or XL effort. All S/M calculator and reference items have been built.

---

## Requires External Dependencies or Hardware

- **SDR sidecar service** (M) — needs `rtl-sdr` or `SoapySDR` libraries + USB hardware
- **Perceptual-hash + C2PA on OSINT images** (M) — needs `imagehash` + C2PA Python library
- **SSURGO soil profile cache** (M) — needs USDA SSURGO data download (~large dataset)
- **Skew-T / upper-air viewer** (M) — needs `MetPy` library for atmospheric sounding plots
- **Blitzortung lightning overlay** (M) — needs Blitzortung.org API access or websocket feed
- **FARSITE-lite wildfire spread** (L) — needs fire behavior model implementation + DEM/fuel data
- **SAR probability grid (ISRID)** (L) — needs Koester ISRID statistical dataset (commercial)
- **Terrain-cost range rings** (M) — needs DEM elevation data + weighted Dijkstra pathfinding
- **iOverlander POI ingest** (M) — needs iOverlander API integration
- **Offline plant-ID model** (L) — needs ML model (TFLite/ONNX) + training data
- **ALE / VARA / Winlink integration** (L) — needs Pat Winlink client + radio hardware
- **FLDIGI macro library** (M) — needs FLDIGI XML-RPC integration

---

## Requires Significant Frontend / UI Work

- **Visual alert rules builder** (M) — drag-and-drop canvas UI for condition/action nodes
- **Compound alert conditions** (M) — AND/OR logic UI + backend evaluation changes
- **Node-RED-style flow editor** (L) — visual canvas with connected nodes (overlaps alert builder)
- **Mobile PWA functional offline sync** (L) — IndexedDB conflict resolution + background sync
- **Plugin API upgrade + scaffold generator** (L) — full SDK, CLI tool, hook system

---

## Requires XL Effort / Research

- **AI-powered recommendations engine** (L) — seasonal advisor, readiness improvement suggestions from regional data
- **Evacuation Monte Carlo simulator** (L) — probabilistic outcome modeling
- **Tauri alternative shell + WASM calculators** (XL) — rewrite shell layer in Rust/WASM
- **Reproducible builds + SBOM + transparency log** (L) — build system hardening
- **WCAG 2.2 AA deep audit** (L) — comprehensive accessibility pass

---

## Remaining Content Items (low effort but niche)

- **Regional packs** (M each) — Canada (ECCC), UK (Met Office), EU (Copernicus), Australia (BOM)
- **NTS radiogram handling** (M) — formal amateur radio traffic message format
- **NWS AFD parser** (S) — extract key phrases from Area Forecast Discussion text
- **Pedigree + breeding cycle tracker** (M) — livestock lineage, heat cycles, gestation
- **CISM debrief wizard** — guided workflow UI (reference data already built)
- **Homeschool curriculum tracker** (M) — subject/lesson/grade management
- **Scenario library + drill engines** (V1-V5, M-L) — tabletop/functional exercise system
- **AIS/ADS-B deconfliction** (M) — merged track display from existing Situation Room feeds
- **Multi-party barter ledger** (M) — community trade tracking across federation
- **Offline star map** (M) — celestial navigation reference
- **Foraging calendar + game processing** (M-L) — regional plant/animal field guides
- **Property-based + fuzz tests** (M) — test infrastructure improvement

---

## Explicit Omissions

- Interactive substance-withdrawal tapers (medical risk too high)
- Home distillation of potable spirits (federal permit required)
- Paper-currency / scrip printing templates (counterfeiting-adjacent)
- Full-depth theology / scripture libraries
- Interactive flint-knapping / flintlock guides
- Offline Google Translate competitor
