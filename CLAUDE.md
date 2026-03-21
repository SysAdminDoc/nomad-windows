# Project N.O.M.A.D. for Windows

## Overview
Native Windows port of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — no Docker required. Manages offline tools (AI chat, Wikipedia, CyberChef, Kolibri) as native Windows processes instead of containers.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2) embedded browser
- **SQLite** — state/settings (replaces MySQL+Redis from original)
- **Native process management** — subprocess for Ollama, kiwix-serve, Kolibri; threading HTTP server for CyberChef
- **pystray** — system tray icon for background operation
- **psutil** — system info (CPU, RAM, GPU detection, disk devices, live metrics)

## Project Structure
```
nomad.py              # Entry point — Flask server + WebView2 window + tray + health monitor
db.py                 # SQLite database init and helpers
build.spec            # PyInstaller spec for single exe
icon.ico              # App icon (multi-size, 16-256px)
installer.iss         # Inno Setup installer script
.github/workflows/
  build.yml           # CI/CD — PyInstaller build + auto-release on tag push
web/
  app.py              # Flask routes (API + dashboard) — services, AI, ZIM, maps, benchmark, system
  templates/
    index.html        # Single-file dark dashboard (inline CSS/JS) — 7 tabs
services/
  manager.py          # Process manager — download, start, stop, track, uninstall
  ollama.py           # Ollama AI service (download, model management, chat)
  kiwix.py            # Kiwix service (kiwix-serve + tiered ZIM catalog)
  cyberchef.py        # CyberChef (GitHub Releases API + static HTTP server)
  kolibri.py          # Kolibri education platform (pip install + subprocess)
  qdrant.py           # Qdrant vector DB (GitHub Releases binary + REST API)
  stirling.py         # Stirling PDF toolkit (GitHub Releases exe + Java runtime)
```

## Key Paths
- **Data dir**: `%APPDATA%\ProjectNOMAD\`
- **SQLite DB**: `%APPDATA%\ProjectNOMAD\nomad.db`
- **Log file**: `%APPDATA%\ProjectNOMAD\logs\nomad.log`
- **Services**: `%APPDATA%\ProjectNOMAD\services\{ollama,kiwix,cyberchef,kolibri}\`
- **Kiwix ZIMs**: `%APPDATA%\ProjectNOMAD\services\kiwix\library\`
- **Ollama models**: `%APPDATA%\ProjectNOMAD\services\ollama\models\`
- **Maps**: `%APPDATA%\ProjectNOMAD\maps\`
- **Benchmark temp**: `%APPDATA%\ProjectNOMAD\benchmark\`

## Run
```bash
python nomad.py
```

## Build (single exe)
```bash
pip install pyinstaller
pyinstaller build.spec
# Output: dist/ProjectNOMAD.exe
```

## Service URLs
- Dashboard: http://localhost:8080
- Ollama API: http://localhost:11434
- Kiwix: http://localhost:8888
- CyberChef: http://localhost:8889
- Kolibri: http://localhost:8300
- Stirling PDF: http://localhost:8443

## Features (v1.7.0)
- **6 services**: Ollama (AI), Kiwix (offline content), CyberChef (data tools), Kolibri (education), Qdrant (vector DB), Stirling PDF (PDF toolkit)
- **Setup wizard** — capability selection (choose which services to install)
- **Auto-start** — previously running services restart on app launch
- **System tray** — minimize to tray, background operation
- **Health monitor** — background crash detection, auto-marks failed services as stopped
- **Service management** — install, start, stop, restart, uninstall with disk usage
- **AI Chat** — streaming responses, markdown rendering, thinking indicator, model management
- **Conversation history** — persistent chat sessions with sidebar, rename, delete, delete all
- **Custom AI name** — configurable assistant name in settings
- **Kiwix Library** — tiered ZIM catalog (Essential/Standard/Comprehensive), 5 categories (Wikipedia, Medicine, Survival, Computing, Science)
- **Offline Maps** — US regional PMTiles map management, map region browser
- **Notes** — markdown notes with auto-save
- **Benchmark** — CPU, memory, disk read/write, AI inference (tok/s + TTFT), weighted N.O.M.A.D. Score 0-100
- **System monitoring** — real-time CPU/RAM/swap gauges (3s polling), disk device breakdown with usage bars, uptime
- **Network status** — online/offline indicator with LAN IP, LAN access banner + URL
- **Settings** — system info (hostname, arch, cores, GPU VRAM), AI model manager with recommended models, storage devices
- **Download progress** — speed display, percentage tracking

## Architecture Decisions
- **pywebview + WebView2** for dedicated app window (not system browser)
- **Flask in background thread**, webview.start() blocks main thread
- **pystray** for system tray — window close minimizes to tray instead of quitting
- **No Docker dependency** — each service is downloaded as native binary and managed via subprocess
- **CyberChef** served via Python's built-in `http.server` (it's just static HTML)
- **Ollama** uses its official Windows zip release, run via `ollama serve`
- **Kiwix** uses kiwix-tools Windows binary with `kiwix-serve`
- **Kolibri** installed via pip, run as `python -m kolibri start --foreground`
- Downloads use GitHub Releases API to resolve versioned URLs dynamically (CyberChef)
- Ollama model pull uses streaming API for real-time progress
- Conversations stored as JSON messages blob in SQLite
- Health monitor runs every 15s, checks `running()` on each service module
- Network status checks connectivity to 1.1.1.1:443, LAN IP via UDP socket trick
- Benchmark uses pure Python tests (prime calc, memory alloc, file I/O, Ollama generate API)
- Live system gauges poll `/api/system/live` every 3s when Settings tab is active
- ZIM catalog organized in tiers matching original Project N.O.M.A.D. categories
- PMTiles served via Flask with range request support for MapLibre GL JS

## Gotchas
- Kiwix tools URL includes version number — currently hardcoded to 3.8.1
- CyberChef zip filename includes version — resolved dynamically via GitHub API
- `CREATE_NO_WINDOW = 0x08000000` flag used for subprocess to hide console windows
- Kiwix needs restart after downloading new ZIM files (auto-handled now)
- psutil import used in system info endpoint — included in bootstrap
- Kolibri is a large pip package (~200MB), install takes time
- Kolibri uses `KOLIBRI_HOME` env var to store data in ProjectNOMAD folder
- Benchmark disk test creates/deletes temp files in ProjectNOMAD\benchmark\

## Version
v1.7.0

## Status
Working v1.7.0 — Command Center Edition. 8-tab dashboard. Preparedness tab with 8 sub-sections and persistent Situation Board (6-domain threat level dashboard). Incident Log for chronological event tracking with severity/categories. Watch/guard rotation schedule generator. Medication dosage reference, barter value guide. 8 emergency protocols (added choking/Heimlich, hypothermia, wound closure). Plus all v1.3.0 features: inventory, contacts, LAN chat, checklists, calculators, radio ref, quick ref cards, 12 AI presets.

## Gotchas (v0.8.0)
- Stirling PDF requires Java 17+ (downloads .jar, not .exe — no Windows exe in releases)
- Qdrant: --storage-path CLI arg removed — use QDRANT__STORAGE__STORAGE_PATH env var
- Kiwix: won't start without ZIM files (raises RuntimeError with user-friendly message)
- PyInstaller frozen exe: _bootstrap() must skip (sys.frozen check) or fork-bombs via sys.executable
- Kolibri uses _python_exe() helper to find real Python on PATH when frozen
