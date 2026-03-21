<div align="center">
<img src="https://raw.githubusercontent.com/Crosstalk-Solutions/project-nomad/refs/heads/main/admin/public/project_nomad_logo.png" width="200" height="200"/>

# Project N.O.M.A.D.
### Offline Media, Archives, and Data for Windows

**Knowledge That Never Goes Offline**

[![Website](https://img.shields.io/badge/Website-projectnomad.us-blue)](https://www.projectnomad.us)
[![Discord](https://img.shields.io/badge/Discord-Join%20Community-5865F2)](https://discord.com/invite/crosstalksolutions)
[![Benchmark](https://img.shields.io/badge/Benchmark-Leaderboard-green)](https://benchmark.projectnomad.us)

</div>

---

Project N.O.M.A.D. is a self-contained, offline-first knowledge and education server packed with critical tools, knowledge, and AI to keep you informed and empowered—anytime, anywhere.

## Features

- **AI Chat** — Local LLM conversations via Ollama with streaming responses, model management, and persistent conversation history
- **Information Library** — Offline Wikipedia, medical references, survival guides via Kiwix with ZIM catalog browser
- **Data Tools** — CyberChef encryption, encoding, hashing toolkit served locally
- **Setup Wizard** — First-run guided install of all services
- **Service Management** — Install, start, stop, restart, uninstall with disk usage tracking
- **Health Monitor** — Background crash detection automatically marks failed services as stopped
- **Auto-Start** — Previously running services restart on app launch
- **System Tray** — Minimize to tray for background operation
- **Conversation History** — Persistent chat sessions with sidebar navigation
- **Notes** — Markdown notes with auto-save
- **Network Status** — Online/offline indicator with LAN IP display
- **Settings** — System info (CPU/RAM/GPU/disk), AI model manager with recommended models

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
| System Tray | pystray |

All services are downloaded as native Windows binaries and managed via `subprocess` — no Docker, no WSL, no VMs.

## Service Ports

| Service | Port |
|---------|------|
| Dashboard | 8080 |
| Ollama API | 11434 |
| Kiwix | 8888 |
| CyberChef | 8889 |

## Data Location

All data is stored in `%APPDATA%\ProjectNOMAD\`:
- SQLite database, logs, service binaries, Ollama models, Kiwix ZIM files

## Credits

Based on [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) by Crosstalk Solutions.
