<div align="center">
<img src="nomad-mark.png" width="140" height="140"/>

# NOMAD Field Desk

### Local-First Preparedness & Intelligence Workspace

**Free. Open Source. Runs on your machine.**

[![Release](https://img.shields.io/github/v/release/SysAdminDoc/project-nomad-desktop?include_prereleases&label=Download&color=blue)](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)

</div>

---

> Cross-platform desktop app for Windows, Linux, and macOS. No Docker. No cloud subscriptions. All data stays on your machine. Live intelligence features use internet; AI, maps, reference, and cached data work offline.

**[Download for Windows](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest)** (portable exe, no install needed)

---

## What Is It

NOMAD Field Desk is a local-first desktop workspace for preparedness, real-time intelligence monitoring, and field operations. It bundles 8 managed services, 600+ API routes, and 95+ database tables into a single portable executable. Live features (Situation Room feeds, VIPTrack, market data) use internet when available; AI chat, maps, reference materials, and all cached data work fully offline.

### Core Features

**Situation Room** — Real-time global intelligence dashboard with 108+ cards, 36 data sources, 149 API routes, 45 map layers, 1,275 infrastructure points, and 435+ RSS feeds. Tracks earthquakes, severe weather, armed conflicts, cyber threats, disease outbreaks, satellite fires, market indices, crypto, commodities, prediction markets, space weather, and more. All data cached locally for offline access. No API keys needed.

**NukeMap** — Nuclear effects simulator with 32 warheads, WW3 simulation (418 targets, 708 warheads), MIRV strikes, fallout modeling, shelter survival analysis, and 12 map styles. Physics based on Glasstone & Dolan.

**VIPTrack** — Military & VIP aircraft tracker using live ADS-B data. 11,383 military + 12,420 VIP aircraft databases. Real-time global tracking with watchlists, alerts, and aircraft photos.

**AI Assistant** — Local AI via Ollama with persistent memory, vision support, conversation branching, action execution, and SITREP generation. Knows your actual inventory, contacts, weather, and medical data.

**Inventory & Preparedness** — Barcode/QR scanning, UPC database, receipt OCR, burn rate projections, 5 templates (155 items), medical module with TCCC/triage/vital signs, 21 decision guides, 42 calculators, and 56 reference cards.

**Offline Maps** — MapLibre GL + PMTiles with 50+ tile sources, waypoints, elevation profiles, perimeter zones, GPX import/export, and geocode search.

**Communications** — DTMF tone generator, NATO phonetic trainer, antenna calculator, LAN chat with encryption, mesh radio bridge, dead drop messaging, and HF propagation forecast.

**Media Library** — 210 survival channels, video/audio/book library with resume playback, built-in BitTorrent client with 152 curated collections.

---

## Main Tabs

| Tab | Description |
|-----|-------------|
| Situation Room | Global intelligence dashboard — live feeds, maps, markets, threats |
| Home | Widget dashboard with services, documents, activity |
| AI Chat | Local AI with memory, vision, branching, action execution |
| Library | Offline Wikipedia, ZIM content, document library |
| Maps | Offline maps, waypoints, routes, elevation profiles |
| Notes | Wiki-linked markdown notes with tags and templates |
| Media | Video, audio, books, channels, torrents |
| Tools | Calculators, drills, scenarios, procedures |
| NukeMap | Nuclear effects simulator |
| VIPTrack | Military & VIP aircraft tracker |
| Preparedness | Inventory, medical, garden, power, security, radio, guides |
| Settings | System config, AI models, backups, health monitoring |

## Managed Services

| Service | Purpose | Port |
|---------|---------|------|
| Ollama | Local AI (Qwen3, Gemma 3, DeepSeek-R1) | 11434 |
| Kiwix | Offline Wikipedia & reference | 8888 |
| CyberChef | Data tools (GCHQ, 400+ operations) | 8889 |
| FlatNotes | Markdown notes | 8890 |
| Kolibri | Khan Academy courses | 8300 |
| Qdrant | Vector search (RAG) | 6333 |
| Stirling PDF | 50+ PDF tools | 8443 |
| BitTorrent | Built-in torrent client | in-process |

---

## Quick Start

### Windows (portable)
Download **NOMADFieldDesk.exe** from [Releases](https://github.com/SysAdminDoc/project-nomad-desktop/releases/latest) and double-click. No install needed.

### From source (any platform)
```bash
git clone https://github.com/SysAdminDoc/project-nomad-desktop.git
cd project-nomad-desktop
pip install -r requirements.txt
python nomad.py
```

### Build portable binary
```bash
pip install pyinstaller
pyinstaller build.spec
```

---

## Requirements

| Platform | Requirements |
|----------|-------------|
| Windows | Windows 10/11, WebView2 Runtime (built into Win 11) |
| Linux | Python 3.10+, `python3-gi gir1.2-webkit2-4.1` |
| macOS | Python 3.10+ (native WebKit) |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Window | pywebview (WebView2/WebKit/GTK) |
| Backend | Flask + 17 Blueprints, 600+ routes |
| Database | SQLite (95+ tables, WAL mode, 135+ indexes) |
| AI | Ollama + Qdrant RAG |
| Maps | MapLibre GL JS v4.7.1 + PMTiles |
| NukeMap | Leaflet + 18 JS physics modules |
| VIPTrack | Leaflet + live ADS-B feeds |
| Media | yt-dlp + FFmpeg + libtorrent |
| Build | PyInstaller + Inno Setup |
| Themes | 5 themes (Desert, Night Ops, Cyber, Red Light, E-Ink) |

---

## Data Location

| Platform | Path |
|----------|------|
| Windows | `%APPDATA%\NOMADFieldDesk\` |
| Linux | `~/.local/share/NOMADFieldDesk/` |
| macOS | `~/Library/Application Support/NOMADFieldDesk/` |

---

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions. Desktop edition by [SysAdminDoc](https://github.com/SysAdminDoc).
