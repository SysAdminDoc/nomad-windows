# Contributing to NOMAD Field Desk

## Getting Started

```bash
git clone https://github.com/SysAdminDoc/project-nomad-desktop.git
cd project-nomad-desktop
pip install -r requirements.txt
python nomad.py
```

## Architecture

- **Entry point**: `nomad.py` (Flask + pywebview + system tray)
- **Config**: `config.py` (env-overridable, atomic writes)
- **Database**: `db.py` (SQLite, WAL mode, ~310 tables, connection pool)
- **Routes**: `web/app.py` (core) + `web/blueprints/` (59 blueprint files)
- **Frontend**: `web/templates/index.html` + partials + inline JS
- **CSS**: `web/static/css/app/` (base) + `web/static/css/premium/` (polish)
- **Services**: `services/` (Ollama, Kiwix, CyberChef, etc.)

## Adding a New Blueprint

1. Create `web/blueprints/your_feature.py`:

```python
from flask import Blueprint, request, jsonify
from db import db_session, log_activity
from web.blueprints import get_pagination, error_response

your_bp = Blueprint('your_feature', __name__)

@your_bp.route('/api/your-feature')
def api_list():
    limit, offset = get_pagination()
    with db_session() as db:
        rows = db.execute('SELECT * FROM your_table LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return jsonify([dict(r) for r in rows])
```

2. Register in `web/app.py`:

```python
from web.blueprints.your_feature import your_bp
app.register_blueprint(your_bp)
```

3. Add table schema in `db.py` inside the appropriate `_create_*_tables()` function.

## Adding a Dashboard Widget

Widgets are defined in `dashboard_templates` table. Each widget has a `config_json` with:

```json
{
  "type": "your_widget",
  "refresh_interval_sec": 60,
  "size": "normal"
}
```

Add the API route in a blueprint, then the frontend renderer in the appropriate JS partial.

## Code Style

- Use `db_session()` context manager for all DB operations
- Use `error_response()` for error returns
- Use `get_pagination()` on all list endpoints
- Use `log_activity()` on mutations
- Validate all user input (see `web/validation.py`)
- Escape HTML output with `esc()` from `web/utils.py`

## Running Tests

```bash
pytest tests/ -x -q --tb=short
```

## Security

- Never expose raw exception messages to clients
- Use parameterized queries (never f-strings for SQL)
- Validate file paths with `os.path.normpath` + `startswith`
- Use `hmac.compare_digest` for token comparison
