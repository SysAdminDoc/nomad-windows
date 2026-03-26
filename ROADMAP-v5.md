# Project N.O.M.A.D. v5.0 Roadmap

> Feature expansion roadmap based on competitive analysis of 40+ open source projects.
> Each phase is independently shippable. Phases are ordered by impact and dependency.

---

## Phase 1: AI Chat Enhancements
**Inspiration:** GPT4All (LocalDocs), Jan.ai (model marketplace), Open WebUI (branching)

| Feature | Description | Effort |
|---------|-------------|--------|
| Folder-based document ingestion | Watch a folder, auto-index new files into KB — like GPT4All's LocalDocs | Medium |
| Model cards in picker | Show param count, quant level, RAM needed, speed benchmark per model | Low |
| Conversation branching | Fork from any message to explore alternative responses | Medium |
| Workspace-scoped RAG | Create named knowledge bases ("Medical KB", "Water KB") instead of one global KB | Medium |
| Image input (multimodal) | Support vision models (llava, etc.) — paste/upload images into chat | Medium |

**API changes:** New `/api/kb/workspaces` CRUD, `/api/kb/watch-folder`, model metadata endpoint.

---

## Phase 2: Knowledge Base Upgrade
**Inspiration:** RAGFlow (GraphRAG), LlamaIndex (hierarchical chunks), LanceDB (embedded)

| Feature | Description | Effort |
|---------|-------------|--------|
| Replace Qdrant with LanceDB | Embedded vector DB — no separate server process, smaller footprint | Medium |
| Hybrid retrieval | Combine vector search + BM25 keyword search for better accuracy | Medium |
| Hierarchical chunking | Parent/child document structures that preserve section context | Medium |
| Source citations | AI answers include page numbers and document names as clickable references | Low |
| Auto-OCR pipeline | PDFs auto-OCR'd on upload via Stirling-PDF, then indexed into KB | Low |

**Impact:** Removes Qdrant service dependency (1 fewer process), better search quality.

---

## Phase 3: Inventory Upgrades
**Inspiration:** InvenTree (barcode scanning), OpenBoxes (lot tracking), Snipe-IT (check-out)

| Feature | Description | Effort |
|---------|-------------|--------|
| Barcode/QR scanning | Webcam-based barcode scanner for quick item lookup and add | Low |
| Photo attachments | Camera capture attached to inventory items | Low |
| Check-in/check-out | Track who has which equipment ("who has the generator?") | Medium |
| Lot tracking | Track batch numbers for medical supplies, water tablets, ammo lots | Medium |
| Location tracking | Which cache, building, or vehicle holds each supply | Low |
| Auto-shopping list | Generate shopping list from items below minimum threshold | Low |

**API changes:** New columns on `inventory` table (location, lot_number, photo_path, checked_out_to), new `/api/inventory/shopping-list`, `/api/inventory/scan`.

---

## Phase 4: Maps & Navigation
**Inspiration:** Protomaps (style themes), OSRM (offline routing), GPX standard

| Feature | Description | Effort |
|---------|-------------|--------|
| Multiple map styles | Dark tactical, terrain/topo, satellite, minimal — switch via button | Low |
| Offline routing | OSRM or Valhalla for driving/walking route calculation without internet | High |
| GPX import/export | Load GPS tracks onto the map, export waypoint routes as GPX | Medium |
| Distance/area measurement | Click-to-measure tool on map | Low |
| Print map to PDF | Print current map view at specified scale for field use | Medium |
| Elevation profiles | Show elevation graph along a route or between waypoints | Medium |

**Dependencies:** OSRM routing requires pre-built routing data (~200MB per region).

---

## Phase 5: Notes Overhaul
**Inspiration:** Obsidian (wiki-links, graph), Joplin (tags, encryption), Logseq (daily journal)

| Feature | Description | Effort |
|---------|-------------|--------|
| Wiki-links `[[page]]` | Type `[[` to autocomplete link to another note; clickable bidirectional links | Medium |
| Tags | `#medical #water #urgent` with tag-based filtering sidebar | Low |
| Daily journal mode | One-click "today's log" that auto-timestamps entries | Low |
| Note templates | "Incident Report", "Patrol Log", "Comms Log", "SITREP" etc. | Low |
| Note attachments | Embed images, PDFs, audio recordings into notes | Medium |
| Backlink panel | Show all notes that link to the current note | Low |

**API changes:** New `note_tags` table, `/api/notes/tags`, `/api/notes/backlinks/<id>`.

---

## Phase 6: Media Library
**Inspiration:** Jellyfin (metadata, resume), Audiobookshelf (chapters, bookmarks)

| Feature | Description | Effort |
|---------|-------------|--------|
| Resume playback | Remember position in videos and audiobooks across sessions | Low |
| Chapter navigation | Jump between chapters in audiobooks and long videos | Medium |
| Auto-thumbnail generation | Extract thumbnail frames from video files | Low |
| Playlist creation | Create and manage audio playlists | Low |
| Subtitle/SRT support | Load subtitle files for video playback | Medium |
| Metadata editor | Edit title, author, description, tags for media files | Low |

**API changes:** New `media_progress` table, `/api/media/progress`, `/api/media/playlists` CRUD.

---

## Phase 7: Medical Module
**Inspiration:** OpenBoxes (pharma tracking), WHO guidelines, TCCC protocols

| Feature | Description | Effort |
|---------|-------------|--------|
| Drug interaction checker | Flag conflicts between medications a patient is taking | Medium |
| Wound documentation with photos | Camera capture attached to patient wound records | Low |
| Interactive TCCC flowchart | Step-by-step decision tree for tactical casualty care | Medium |
| Vital signs trending | Chart BP/HR/temp/SpO2 over time to spot deterioration | Low |
| Medication expiry cross-reference | Link med inventory expiry dates to patient prescriptions | Low |
| Offline medical reference DB | Curated WHO/public domain guidelines searchable offline | High |

**Dependencies:** Drug interaction data requires a curated database (public domain sources exist).

---

## Phase 8: Radio & Communications
**Inspiration:** CHIRP (freq database), Fldigi (digital modes), Meshtastic (mesh networking)

| Feature | Description | Effort |
|---------|-------------|--------|
| Expanded frequency database | 22,000+ allocations by region (import from CHIRP data) | Medium |
| Antenna calculator with diagrams | Visual dipole, vertical, Yagi length calculator with SVG diagrams | Low |
| Propagation prediction | Basic HF propagation forecast from time/date/solar conditions | Medium |
| Native Meshtastic integration | Connect to Meshtastic via USB serial — send/receive messages from NOMAD | High |
| DTMF tone generator | Generate DTMF tones for radio programming through audio output | Low |
| Phonetic alphabet trainer | Interactive practice tool for NATO alphabet | Low |

**API changes:** New `/api/radio/frequencies` with region filter, `/api/mesh/serial/connect`.

---

## Phase 9: Weather & Environment
**Inspiration:** WeeWX (station integration), Open-Meteo, Zambretti algorithm

| Feature | Description | Effort |
|---------|-------------|--------|
| Barometric pressure history graph | Track pressure over 24-48hrs with visual trend line | Low |
| Zambretti weather prediction | Pure offline forecasting from pressure + wind + season (no internet) | Low |
| USB weather station support | Read data from USB weather stations via serial interface | Medium |
| Weather-triggered alerts | Auto-create alerts when pressure drops rapidly or temp hits extremes | Low |
| Wind chill / heat index calculator | Real-time comfort index from temp + wind/humidity | Low |

**API changes:** New `weather_readings` table, `/api/weather/history`, `/api/weather/predict`.

---

## Phase 10: LAN & Mesh Networking
**Inspiration:** LAN Messenger (file transfer), KouChat (serverless), BeeBEEP (groups)

| Feature | Description | Effort |
|---------|-------------|--------|
| LAN file transfer | Drag-and-drop send files between NOMAD instances | Medium |
| Group channels | Named channels ("Security", "Medical", "Logistics") | Low |
| Message encryption | AES encrypt LAN chat messages end-to-end | Medium |
| User presence/status | Show online/away/busy for each LAN node | Low |
| Mesh node map overlay | Show Meshtastic nodes on map with signal strength indicators | Low |
| Mesh alert relay | Broadcast emergency alerts to all mesh nodes | Low |

**API changes:** New `/api/lan/transfer`, `/api/lan/channels` CRUD, `/api/lan/presence`.

---

## Phase 11: Garden & Food Production
**Inspiration:** Plant-it (care tracking), GrowVeg (planting calendar)

| Feature | Description | Effort |
|---------|-------------|--------|
| Planting calendar | Auto-calculate plant/harvest dates from last frost date and zone | Low |
| Companion planting guide | Reference showing which plants grow well together | Low |
| Harvest yield tracking | Log actual vs expected yield to improve next season | Low |
| Seed inventory | Track seed stock with viability dates and germination rates | Low |
| Pest/disease identifier | Reference guide for common garden problems with treatments | Low |

**API changes:** Expand `planting_calendar` table, new `seed_inventory` table, `/api/garden/companions`.

---

## Phase 12: Benchmark & Diagnostics
**Inspiration:** Phoronix Test Suite, sysbench

| Feature | Description | Effort |
|---------|-------------|--------|
| AI inference benchmark | Measure tokens/second per installed model (NOMAD-specific) | Low |
| Storage I/O benchmark | Test USB drive speed — critical for offline content performance | Low |
| Network throughput test | Measure LAN speed for multi-node setups | Low |
| Historical comparison graph | Chart benchmark scores over time to detect degradation | Low |

**API changes:** Expand `benchmark_results` table with test_type column.

---

## Implementation Priority

### Tier 1 — Ship First (highest user impact, lowest risk)
1. **Phase 3** — Inventory (barcode scanning, locations, shopping list)
2. **Phase 1** — AI Chat (folder ingestion, model cards)
3. **Phase 9** — Weather (Zambretti prediction, pressure graph)

### Tier 2 — Core Platform (medium effort, high value)
4. **Phase 5** — Notes (wiki-links, tags, journal)
5. **Phase 6** — Media (resume playback, chapters)
6. **Phase 2** — KB Upgrade (LanceDB, hybrid search)

### Tier 3 — Differentiation (unique capabilities)
7. **Phase 8** — Radio (Meshtastic integration, freq database)
8. **Phase 4** — Maps (offline routing, GPX)
9. **Phase 10** — LAN/Mesh (file transfer, channels)

### Tier 4 — Depth (specialized improvements)
10. **Phase 7** — Medical (drug interactions, TCCC flowchart)
11. **Phase 11** — Garden (planting calendar, seed inventory)
12. **Phase 12** — Benchmark (AI inference, storage I/O)

---

## Version Targets

| Version | Phases | Theme |
|---------|--------|-------|
| v5.0.0 | 1, 3, 9 | Smarter AI + Better Inventory + Offline Weather |
| v5.1.0 | 2, 5, 6 | Knowledge Upgrade + Notes + Media |
| v5.2.0 | 4, 8, 10 | Maps + Radio + Networking |
| v5.3.0 | 7, 11, 12 | Medical + Garden + Diagnostics |
