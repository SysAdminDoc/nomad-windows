# Project N.O.M.A.D. for Windows

## Overview
Native Windows port of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — no Docker required. Manages offline tools (AI chat, Wikipedia, CyberChef) as native Windows processes instead of containers.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2) embedded browser
- **SQLite** — state/settings (replaces MySQL+Redis from original)
- **Native process management** — subprocess for Ollama, kiwix-serve; threading HTTP server for CyberChef
- **pystray** — system tray icon for background operation
- **psutil** — system info (CPU, RAM, GPU detection)

## Project Structure
```
nomad.py              # Entry point — Flask server + WebView2 window + tray
db.py                 # SQLite database init and helpers
build.spec            # PyInstaller spec for single exe
web/
  app.py              # Flask routes (API + dashboard)
  templates/
    index.html        # Single-file dark dashboard (inline CSS/JS)
services/
  manager.py          # Process manager — download, start, stop, track, uninstall
  ollama.py           # Ollama AI service (download, model management, chat)
  kiwix.py            # Kiwix service (kiwix-serve + ZIM catalog + management)
  cyberchef.py        # CyberChef (GitHub Releases API + static HTTP server)
```

## Key Paths
- **Data dir**: `%APPDATA%\ProjectNOMAD\`
- **SQLite DB**: `%APPDATA%\ProjectNOMAD\nomad.db`
- **Log file**: `%APPDATA%\ProjectNOMAD\logs\nomad.log`
- **Services**: `%APPDATA%\ProjectNOMAD\services\{ollama,kiwix,cyberchef}\`
- **Kiwix ZIMs**: `%APPDATA%\ProjectNOMAD\services\kiwix\library\`
- **Ollama models**: `%APPDATA%\ProjectNOMAD\services\ollama\models\`

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

## Features (v0.2.0)
- **Setup wizard** — first-run guided install of all services
- **Auto-start** — previously running services restart on app launch
- **System tray** — minimize to tray, background operation
- **Service management** — install, start, stop, restart, uninstall with disk usage
- **AI Chat** — streaming responses, model pull with progress, model delete, system prompts
- **Kiwix Library** — ZIM catalog browser, download/delete content packs
- **Notes** — markdown notes with auto-save
- **Settings** — system info (CPU/RAM/GPU/disk), model manager with recommended models
- **Download progress** — speed display, percentage tracking

## Architecture Decisions
- **pywebview + WebView2** for dedicated app window (not system browser)
- **Flask in background thread**, webview.start() blocks main thread
- **pystray** for system tray — window close minimizes to tray instead of quitting
- **No Docker dependency** — each service is downloaded as native binary and managed via subprocess
- **CyberChef** served via Python's built-in `http.server` (it's just static HTML)
- **Ollama** uses its official Windows zip release, run via `ollama serve`
- **Kiwix** uses kiwix-tools Windows binary with `kiwix-serve`
- Downloads use GitHub Releases API to resolve versioned URLs dynamically (CyberChef)
- Ollama model pull uses streaming API for real-time progress

## Gotchas
- Kiwix tools URL includes version number — currently hardcoded to 3.8.1
- CyberChef zip filename includes version — resolved dynamically via GitHub API
- `CREATE_NO_WINDOW = 0x08000000` flag used for subprocess to hide console windows
- Kiwix needs restart after downloading new ZIM files (new content not picked up live)
- psutil import used in system info endpoint — included in bootstrap

## Version
v0.2.0

## Status
Working v0.2.0 — all 3 services install/start/stop/restart/uninstall. Auto-start on launch. System tray. Setup wizard. AI chat with streaming + model management. ZIM catalog browser. Notes with auto-save. Settings with system info + GPU detection. PyInstaller build spec.
