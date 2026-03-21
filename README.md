<div align="center">
<img src="https://raw.githubusercontent.com/Crosstalk-Solutions/project-nomad/refs/heads/main/admin/public/project_nomad_logo.png" width="200" height="200"/>

# Project N.O.M.A.D. for Windows
### Offline Media, Archives, and Data

**Knowledge That Never Goes Offline**

Native Windows port — no Docker required. 5 managed services, 70+ downloadable datasets, AI chat with RAG, offline maps, and a premium dark dashboard.

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/nomad-windows?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/nomad-windows/releases/latest)
[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

Project N.O.M.A.D. is a self-contained, offline-first knowledge and AI command center packed with critical tools, reference libraries, and local AI — designed to keep you informed and capable when the internet isn't available.

Download **[ProjectNOMAD.exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest)** (66 MB) — single file, double-click to run.

![Dashboard](screenshot.png)

## 5 Managed Services

| Service | What It Does | Port |
|---------|-------------|------|
| **Ollama** | Local AI chat — Llama 3, Mistral, Gemma, DeepSeek + GPU auto-detection (NVIDIA/AMD/Intel) | 11434 |
| **Kiwix** | Offline Wikipedia, medical references, survival guides, 70+ downloadable content packs | 8888 |
| **CyberChef** | Encryption, encoding, hashing, and data analysis toolkit by GCHQ | 8889 |
| **Kolibri** | Khan Academy courses, textbooks, progress tracking, offline education platform | 8300 |
| **Qdrant** | Vector database enabling document upload, semantic search, and RAG for AI chat | 6333 |

All services are downloaded as native Windows binaries and managed as processes — no Docker, no WSL, no VMs.

## 13-Category Content Library

70+ downloadable datasets organized into **Essential / Standard / Comprehensive** tiers:

| Category | Highlights |
|----------|-----------|
| **Wikipedia** | Mini (1.2 MB) through Full with images (115 GB) |
| **Medicine & Health** | WikiMed (10 GB, 73k articles), MedlinePlus, CDC, NHS Medicines, Military Medicine |
| **Survival & Preparedness** | FEMA Ready.gov (2.3 GB), Survivor Library, Wikibooks, Outdoors SE |
| **Repair & How-To** | iFixit (2.5 GB, 44k guides), DIY SE, Cooking SE, Gardening SE |
| **Computing & Technology** | Stack Overflow (55 GB), DevDocs, Super User, Python docs, Server Fault |
| **Science & Engineering** | PhET Simulations, Physics/Chemistry/Biology/Math/Engineering SE |
| **Education** | Khan Academy (168 GB), CrashCourse (21 GB), GCFGlobal, OpenStax, Wikiversity |
| **Books & Literature** | Project Gutenberg (78k books), Wikiquote, Wikisource |
| **Ham Radio & Communications** | Ham Radio SE, Electronics SE, Signal Processing SE |
| **TED Talks & Videos** | Top 100 through all 6,658 talks |
| **Reference & Dictionaries** | Wiktionary, Cheatography (11 GB), Wikinews |
| **Homesteading & Agriculture** | Gardening SE, Cooking SE, Sustainability SE, Survivor Library |

See **[OFFLINE-DATASETS.md](OFFLINE-DATASETS.md)** for a complete reference of 100+ downloadable datasets including non-ZIM content (military field manuals, FEMA nuclear guides, Red Cross first aid, FCC frequency charts, OpenStax textbooks).

## AI Chat

- **Streaming responses** with full markdown rendering (code blocks, headers, lists, bold/italic)
- **Conversation history** — create, rename, search, export to markdown, delete all
- **Knowledge Base (RAG)** — upload PDFs and text, auto-embed via nomic-embed-text, semantic search injected into chat context
- **6 system prompt presets** — General Assistant, Medical Advisor, Coding Helper, Survival Guide, Teacher/Tutor, Data Analyst
- **Model management** — pull, delete, recommended models with one-click install
- **Custom AI name** — configurable assistant identity

## Offline Maps

- **MapLibre GL JS** with dark Carto basemap
- **Location search** via Nominatim geocoding
- **Drop pins** with labels, **measurement tool** (haversine distance in km/mi)
- **Coordinate display** on mouse hover, scale control, fullscreen, geolocate
- **US regional PMTiles** map management (9 regions)

## System Tools

| Tool | Description |
|------|-------------|
| **Benchmark** | CPU, memory, disk R/W, AI inference (tok/s + TTFT) with weighted NOMAD Score (0-100) |
| **System Monitoring** | Real-time CPU/RAM/swap gauges (3s polling), per-disk usage bars with >90% warnings |
| **Unified Search** | Search across conversations, notes, and KB documents from one search bar |
| **Content Summary** | Total offline knowledge capacity: models, ZIMs, documents, conversations, notes |
| **Activity Log** | Timestamped event feed with level filtering (info/warning/error) |
| **Disk Monitor** | Space breakdown with cleanup recommendations |
| **Notes** | Markdown editor with live preview, auto-save |

## Infrastructure

- **Setup wizard** — choose which services to install on first run
- **Auto-restart** — crashed services restart automatically (rate-limited 3 per 5 min)
- **Service dependencies** — prerequisites auto-start when needed
- **GPU auto-detection** — NVIDIA CUDA, AMD ROCm, Intel Arc configured for Ollama
- **Graceful shutdown** — ordered service stop with DB backup
- **SQLite backup** — 5-rotation backup on every startup
- **System tray** — minimize to background, tray menu for show/quit
- **LAN access** — Flask on 0.0.0.0, dashboard accessible from other devices on the network
- **Health monitor** — 10-second polling detects crashed services
- **Download resume** — interrupted downloads continue where they left off

## Quick Start

### Option 1: Download the exe
1. Download **[ProjectNOMAD.exe](https://github.com/SysAdminDoc/nomad-windows/releases/latest)**
2. Double-click to run
3. Follow the setup wizard

### Option 2: Run from source
```bash
git clone https://github.com/SysAdminDoc/nomad-windows.git
cd nomad-windows
python nomad.py
```
Dependencies auto-install on first run.

### Option 3: Build your own exe
```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/ProjectNOMAD.exe
```

## Requirements

- Windows 10/11
- Python 3.10+ (bundled in exe, needed for source)
- WebView2 Runtime (included with Windows 11)

## Architecture

| Component | Technology |
|-----------|-----------|
| Window | pywebview + WebView2 |
| Backend | Flask (background thread, 0.0.0.0) |
| Database | SQLite with WAL mode + automatic backups |
| AI | Ollama native binary + GPU auto-config |
| Library | Kiwix (kiwix-serve + ZIM files) |
| Data Tools | CyberChef (Python HTTP server) |
| Education | Kolibri (pip + subprocess) |
| Vector DB | Qdrant native binary (REST API) |
| Embeddings | nomic-embed-text v1.5 via Ollama |
| Maps | MapLibre GL JS + PMTiles protocol |
| System Tray | pystray |

## Data Location

All data stored in `%APPDATA%\ProjectNOMAD\`:

```
nomad.db          # SQLite database (services, settings, conversations, notes, benchmarks)
logs/             # Application logs
backups/          # Automatic DB backups (5 rotation)
services/         # Downloaded service binaries (Ollama, Kiwix, CyberChef, Qdrant)
  ollama/models/  # AI models
  kiwix/library/  # ZIM content files
  kolibri/data/   # Education platform data
  qdrant/storage/ # Vector database storage
maps/             # PMTiles map data
kb_uploads/       # Knowledge base documents
benchmark/        # Benchmark temp files
```

## Feature Parity with Original

| Feature | Original (Docker) | Windows Port |
|---------|-------------------|-------------|
| Ollama + AI Chat | Container | Native binary + GPU auto-detect |
| Kiwix Library | Container (6 categories) | Native binary (13 categories, 70+ datasets) |
| CyberChef | Container | Static HTTP server |
| Kolibri Education | Container | pip + subprocess |
| Qdrant + RAG | Container | Native binary + full pipeline |
| FlatNotes | Container | Built-in Notes with markdown preview |
| Tiered ZIM Catalog | Yes | Yes (expanded) |
| Benchmark System | Yes | Yes |
| System Monitoring | Yes | Yes (real-time gauges) |
| Offline Maps | Yes | Yes (MapLibre + measurement tools) |
| Conversation History | Yes | Yes (+ search, export, presets) |
| Setup Wizard | Yes (capability tiers) | Yes (capability selection) |
| Health Monitor | Container health | Auto-restart with rate limiting |
| LAN Access | Yes | Yes (0.0.0.0 + dashboard URL) |
| Activity Log | No | Yes |
| Unified Search | No | Yes |
| Content Summary | No | Yes |

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Windows port by [SysAdminDoc](https://github.com/SysAdminDoc).
