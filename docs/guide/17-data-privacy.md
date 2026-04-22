## 17. Data & Privacy

**All data stays on your computer.** NOMAD has zero telemetry, zero cloud connections, and zero tracking. The only time it connects to the internet is when YOU choose to download services, content packs, or AI models.

Data is stored in `%APPDATA%\\\\NOMADFieldDesk\\\\` on new installs (or the custom location you chose during setup). Upgraded systems may still use the legacy `%APPDATA%\\\\ProjectNOMAD\\\\` folder. This includes:
- `nomad.db` — SQLite database with all your data (32 tables)
- `logs/` — Application logs
- `backups/` — Automatic database backups (keeps last 5)
- `services/` — Downloaded service binaries and AI models
- `maps/` — Downloaded offline map data
- `videos/` — Your uploaded video library
- `kb_uploads/` — Uploaded documents for AI analysis
