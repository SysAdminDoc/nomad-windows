"""SQLite database for service state and settings."""

import sqlite3
import os
from config import get_data_dir


def get_db_path():
    return os.path.join(get_data_dir(), 'nomad.db')


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def log_activity(event: str, service: str = None, detail: str = None, level: str = 'info'):
    """Log an activity event to the DB."""
    try:
        conn = get_db()
        conn.execute('INSERT INTO activity_log (event, service, detail, level) VALUES (?, ?, ?, ?)',
                     (event, service, detail, level))
        conn.commit()
        conn.close()
    except Exception:
        pass


def backup_db():
    """Create a timestamped backup of the database."""
    import shutil
    db_path = get_db_path()
    if not os.path.isfile(db_path):
        return
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    # Keep max 5 backups
    from datetime import datetime
    backup_path = os.path.join(backup_dir, f'nomad_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    shutil.copy2(db_path, backup_path)
    # Prune old backups
    backups = sorted(
        [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.endswith('.db')],
        key=os.path.getmtime,
    )
    for old in backups[:-5]:
        try:
            os.remove(old)
        except Exception:
            pass


def init_db():
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS services (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            category TEXT DEFAULT 'tools',
            installed INTEGER DEFAULT 0,
            running INTEGER DEFAULT 0,
            version TEXT,
            port INTEGER,
            pid INTEGER,
            install_path TEXT,
            exe_path TEXT,
            url TEXT
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL DEFAULT 'New Chat',
            model TEXT,
            messages TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT NOT NULL,
            service TEXT,
            detail TEXT,
            level TEXT DEFAULT 'info',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            content_type TEXT DEFAULT 'text',
            file_size INTEGER DEFAULT 0,
            chunks_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS benchmarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cpu_score REAL DEFAULT 0,
            memory_score REAL DEFAULT 0,
            disk_read_score REAL DEFAULT 0,
            disk_write_score REAL DEFAULT 0,
            ai_tps REAL DEFAULT 0,
            ai_ttft REAL DEFAULT 0,
            nomad_score REAL DEFAULT 0,
            hardware TEXT DEFAULT '{}',
            details TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template TEXT NOT NULL DEFAULT '',
            items TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'other',
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'ea',
            min_quantity REAL DEFAULT 0,
            location TEXT DEFAULT '',
            expiration TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            callsign TEXT DEFAULT '',
            role TEXT DEFAULT '',
            skills TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            freq TEXT DEFAULT '',
            email TEXT DEFAULT '',
            address TEXT DEFAULT '',
            rally_point TEXT DEFAULT '',
            blood_type TEXT DEFAULT '',
            medical_notes TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lan_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL DEFAULT 'Anonymous',
            content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS vault_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            encrypted_data TEXT NOT NULL,
            iv TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS comms_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            freq TEXT NOT NULL DEFAULT '',
            callsign TEXT DEFAULT '',
            direction TEXT DEFAULT 'rx',
            message TEXT DEFAULT '',
            signal_quality TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS drill_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drill_type TEXT NOT NULL,
            title TEXT NOT NULL,
            duration_sec INTEGER DEFAULT 0,
            tasks_total INTEGER DEFAULT 0,
            tasks_completed INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            duration TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS weather_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pressure_hpa REAL,
            temp_f REAL,
            wind_dir TEXT DEFAULT '',
            wind_speed TEXT DEFAULT '',
            clouds TEXT DEFAULT '',
            precip TEXT DEFAULT '',
            visibility TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS waypoints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            category TEXT DEFAULT 'general',
            color TEXT DEFAULT '#5b9fff',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS timers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            duration_sec INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT NOT NULL DEFAULT 'info',
            category TEXT NOT NULL DEFAULT 'other',
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER,
            name TEXT NOT NULL,
            age INTEGER,
            weight_kg REAL,
            sex TEXT DEFAULT '',
            blood_type TEXT DEFAULT '',
            allergies TEXT DEFAULT '[]',
            medications TEXT DEFAULT '[]',
            conditions TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS vitals_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            bp_systolic INTEGER,
            bp_diastolic INTEGER,
            pulse INTEGER,
            resp_rate INTEGER,
            temp_f REAL,
            spo2 INTEGER,
            pain_level INTEGER,
            gcs INTEGER,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS wound_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            location TEXT NOT NULL DEFAULT '',
            wound_type TEXT DEFAULT '',
            severity TEXT DEFAULT 'minor',
            description TEXT DEFAULT '',
            treatment TEXT DEFAULT '',
            photo_path TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS power_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT NOT NULL,
            name TEXT NOT NULL,
            specs TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS power_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            battery_voltage REAL,
            battery_soc INTEGER,
            solar_watts REAL,
            solar_wh_today REAL,
            load_watts REAL,
            load_wh_today REAL,
            generator_running INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sync_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            direction TEXT NOT NULL DEFAULT 'push',
            peer_node_id TEXT DEFAULT '',
            peer_name TEXT DEFAULT '',
            peer_ip TEXT DEFAULT '',
            tables_synced TEXT DEFAULT '{}',
            items_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'success',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS garden_plots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            width_ft REAL DEFAULT 0,
            length_ft REAL DEFAULT 0,
            sun_exposure TEXT DEFAULT 'full',
            soil_type TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS seeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species TEXT NOT NULL,
            variety TEXT DEFAULT '',
            quantity INTEGER DEFAULT 0,
            unit TEXT DEFAULT 'seeds',
            year_harvested INTEGER,
            source TEXT DEFAULT '',
            days_to_maturity INTEGER,
            planting_season TEXT DEFAULT 'spring',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS harvest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'lbs',
            plot_id INTEGER,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS livestock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species TEXT NOT NULL,
            name TEXT DEFAULT '',
            tag TEXT DEFAULT '',
            dob TEXT DEFAULT '',
            sex TEXT DEFAULT '',
            weight_lbs REAL,
            status TEXT DEFAULT 'active',
            health_log TEXT DEFAULT '[]',
            vaccinations TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario_type TEXT NOT NULL,
            title TEXT NOT NULL,
            current_phase INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            decisions TEXT DEFAULT '[]',
            complications TEXT DEFAULT '[]',
            score INTEGER DEFAULT 0,
            aar_text TEXT DEFAULT '',
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'warning',
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            data TEXT DEFAULT '{}',
            dismissed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()

    # Performance indexes
    for idx in [
        'CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_activity_log_level ON activity_log(level)',
        'CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_expiration ON inventory(expiration)',
        'CREATE INDEX IF NOT EXISTS idx_incidents_created ON incidents(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_incidents_category ON incidents(category)',
        'CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(updated_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(pinned DESC, updated_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_weather_log_created ON weather_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_waypoints_category ON waypoints(category)',
        'CREATE INDEX IF NOT EXISTS idx_alerts_dismissed ON alerts(dismissed, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_vitals_patient ON vitals_log(patient_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_wound_patient ON wound_log(patient_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_patients_contact ON patients(contact_id)',
        'CREATE INDEX IF NOT EXISTS idx_power_log_created ON power_log(created_at DESC)',
    ]:
        try:
            conn.execute(idx)
        except Exception:
            pass
    conn.commit()

    # Schema migrations for existing databases
    for migration in [
        'ALTER TABLE inventory ADD COLUMN daily_usage REAL DEFAULT 0',
        'ALTER TABLE notes ADD COLUMN tags TEXT DEFAULT ""',
        'ALTER TABLE notes ADD COLUMN pinned INTEGER DEFAULT 0',
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except Exception:
            pass

    conn.close()
