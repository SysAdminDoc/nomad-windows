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

        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT NOT NULL DEFAULT 'info',
            category TEXT NOT NULL DEFAULT 'other',
            description TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()
    conn.close()
