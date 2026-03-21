"""SQLite database for service state and settings."""

import sqlite3
import os


def get_db_path():
    data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ProjectNOMAD')
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'nomad.db')


def get_db():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


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
    ''')
    conn.commit()
    conn.close()
