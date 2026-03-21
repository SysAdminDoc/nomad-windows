<div align="center">
<img src="https://raw.githubusercontent.com/Crosstalk-Solutions/project-nomad/refs/heads/main/admin/public/project_nomad_logo.png" width="200" height="200"/>

# Project N.O.M.A.D.
### Offline Media, Archives, and Data for Windows

**Knowledge That Never Goes Offline**

Native Windows port — no Docker required. Manages offline tools as native processes instead of containers.

[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)
[![Benchmark](https://img.shields.io/badge/Benchmark-Leaderboard-green)](https://benchmark.projectnomad.us)

</div>

---

Project N.O.M.A.D. is a self-contained, offline-first knowledge and education server packed with critical tools, knowledge, and AI to keep you informed and empowered—anytime, anywhere.

![Dashboard](screenshot.png)

## Features

### Services
- **AI Chat (Ollama)** — Local LLM conversations with streaming responses, markdown rendering, thinking indicator, and model management
- **Information Library (Kiwix)** — Offline Wikipedia, medical references, survival guides, computing docs via ZIM files
- **Data Tools (CyberChef)** — Encryption, encoding, hashing toolkit served locally
- **Education Platform (Kolibri)** — Khan Academy courses, textbooks, and offline learning content

### AI Chat
- Persistent conversation history with sidebar navigation
- Create, rename, delete, and delete all conversations
- Markdown rendering (code blocks, bold, italic, lists, headers, blockquotes)
- Thinking/streaming indicator during AI responses
- Model pull with progress tracking
- Custom AI assistant name

### Content Library
- Tiered ZIM catalog (Essential / Standard / Comprehensive)
- 5 content categories: Wikipedia, Medicine, Survival & Preparedness, Computing & Technology, Science & Engineering
- Auto-restart Kiwix after new ZIM downloads

### Offline Maps
- US regional map management with PMTiles
- 9 US geographic regions (Pacific, Mountain, Central, Atlantic, New England)

### Benchmark
- CPU, memory, disk read/write, AI inference (tokens/sec + time-to-first-token)
- Weighted N.O.M.A.D. Score (0-100)
- Benchmark history with past results

### System Monitoring
- Real-time CPU, RAM, and swap gauges (auto-refresh)
- Per-disk device usage bars with capacity warnings
- Hardware info: CPU cores, GPU + VRAM, hostname, uptime
- Network status (online/offline) with LAN IP display

### Infrastructure
- Setup wizard with capability selection (choose which services to install)
- Auto-start previously running services on launch
- System tray (minimize to tray for background operation)
- Health monitor (auto-detects crashed services)
- LAN access URL for other devices on the network
- Notes with auto-save

## Requirements

- Windows 10/11
- Python 3.10+
- WebView2 Runtime (included with Windows 11, auto-installed on Windows 10)

## Quick Start

```bash
git clone https://github.com/SysAdminDoc/nomad-windows.git
cd nomad-windows
python nomad.py
```

Dependencies are auto-installed on first run via the bootstrap system.

## Build (Single Exe)

```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/ProjectNOMAD.exe
```

## Architecture

| Component | Tech |
|-----------|------|
| GUI | pywebview + WebView2 |
| Backend | Flask (background thread) |
| Database | SQLite |
| AI Engine | Ollama (native binary) |
| Library | Kiwix (kiwix-serve + ZIM files) |
| Data Tools | CyberChef (static HTTP server) |
| Education | Kolibri (pip + subprocess) |
| System Tray | pystray |

All services are downloaded as native Windows binaries (or pip packages) and managed via `subprocess` — no Docker, no WSL, no VMs.

## Service Ports

| Service | Port |
|---------|------|
| Dashboard | 8080 |
| Ollama API | 11434 |
| Kiwix | 8888 |
| CyberChef | 8889 |
| Kolibri | 8300 |

## Data Location

All data is stored in `%APPDATA%\ProjectNOMAD\`:
- SQLite database, logs, service binaries, Ollama models, Kiwix ZIM files, map data

## Feature Parity with Original

This Windows port aims for feature parity with the original Docker-based Project N.O.M.A.D.:

| Feature | Original (Docker) | Windows Port |
|---------|-------------------|-------------|
| Ollama + AI Chat | Container | Native binary |
| Kiwix Library | Container | Native binary |
| CyberChef | Container | Static HTTP server |
| Kolibri Education | Container | pip + subprocess |
| FlatNotes | Container | Built-in Notes |
| Tiered ZIM Catalog | Yes | Yes |
| Benchmark System | Yes | Yes |
| System Monitoring | Yes | Yes |
| Offline Maps | Yes | Yes (management) |
| Conversation History | Yes | Yes |
| Setup Wizard | Yes | Yes |
| Health Monitor | Container health | Process health |
| LAN Access | Yes | Yes |

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions.
