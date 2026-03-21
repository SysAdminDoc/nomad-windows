# Project N.O.M.A.D. for Windows

## Overview
Native Windows port of [Project N.O.M.A.D.](https://github.com/Crosstalk-Solutions/project-nomad) — no Docker required. Manages offline tools (AI chat, Wikipedia, CyberChef) as native Windows processes instead of containers.

## Tech Stack
- **Python 3** — Flask web server + pywebview (WebView2) embedded browser
- **SQLite** — state/settings (replaces MySQL+Redis from original)
- **Native process management** — subprocess for Ollama, kiwix-serve; threading HTTP server for CyberChef

## Project Structure
```
nomad.py              # Entry point — Flask server + WebView2 window
db.py                 # SQLite database init and helpers
web/
  app.py              # Flask routes (API + dashboard)
  templates/
    index.html        # Single-file dark dashboard (inline CSS/JS)
services/
  manager.py          # Process manager — download, start, stop, track
  ollama.py           # Ollama AI service (downloads from GitHub releases)
  kiwix.py            # Kiwix service (kiwix-serve + ZIM file management)
  cyberchef.py        # CyberChef (static HTTP server)
```

## Key Paths
- **Data dir**: `%APPDATA%\ProjectNOMAD\`
- **SQLite DB**: `%APPDATA%\ProjectNOMAD\nomad.db`
- **Services**: `%APPDATA%\ProjectNOMAD\services\{ollama,kiwix,cyberchef}\`
- **Kiwix ZIMs**: `%APPDATA%\ProjectNOMAD\services\kiwix\library\`

## Run
```bash
python nomad.py
```

## Service URLs
- Dashboard: http://localhost:8080
- Ollama API: http://localhost:11434
- Kiwix: http://localhost:8888
- CyberChef: http://localhost:8889

## Architecture Decisions
- **pywebview + WebView2** for dedicated app window (not system browser)
- **Flask in background thread**, webview.start() blocks main thread
- **No Docker dependency** — each service is downloaded as native binary and managed via subprocess
- **CyberChef** served via Python's built-in `http.server` (it's just static HTML)
- **Ollama** uses its official Windows zip release, run via `ollama serve`
- **Kiwix** uses kiwix-tools Windows binary with `kiwix-serve`
- Downloads use GitHub Releases API to resolve versioned URLs dynamically (CyberChef)

## Gotchas
- Kiwix tools URL includes version number — currently hardcoded to 3.8.1
- CyberChef zip filename includes version — resolved dynamically via GitHub API
- After install, services are registered in SQLite but processes aren't auto-started on app launch
- `CREATE_NO_WINDOW = 0x08000000` flag used for subprocess to hide console windows

## Version
v0.1.0

## Status
Working v0.1.0 — all 3 services install and run. AI chat streams responses. Notes with auto-save. Dark theme dashboard in embedded WebView2 window.
