"""SQLite database for service state and settings."""

import sqlite3
import os
import glob
import logging
import queue
import threading
from contextlib import contextmanager
import config

_log = logging.getLogger('nomad.db')


# ─── Connection Pool (v7.29.0 — audit M6) ──────────────────────────────
# Process-wide queue of reusable SQLite connections. Reduces per-request
# connect/PRAGMA overhead under LAN multi-user access. Opt-in via env var.
# Default size of 4 keeps memory low for single-user desktop use. SQLite WAL
# tolerates many concurrent readers; contention only appears under write
# load, where the pool has no effect either way.
try:
    _POOL_SIZE = max(0, int(os.environ.get('NOMAD_DB_POOL_SIZE', '4')))
except (ValueError, TypeError):
    _POOL_SIZE = 4
_pool: 'queue.Queue[sqlite3.Connection]' = queue.Queue(maxsize=_POOL_SIZE) if _POOL_SIZE > 0 else None
_pool_lock = threading.Lock()
_pool_db_path: str = None  # pool is keyed by db path; clears on change


def _pool_clear():
    """Drain and close every connection currently in the pool."""
    if _pool is None:
        return
    while True:
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            break
        try:
            conn.close()
        except Exception:
            pass


def get_db_path():
    db_path = config.get_config_value('db_path')
    if isinstance(db_path, str) and db_path:
        return db_path
    data_dir = config.get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'nomad.db')


_wal_set = False
_wal_lock = threading.Lock()
_migration_lock = threading.Lock()


def get_db():
    global _wal_set
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path, timeout=30, uri=db_path.startswith('file:'))
        conn.row_factory = sqlite3.Row
        # WAL mode is persistent on the database file — only set once per process
        if not _wal_set:
            with _wal_lock:
                if not _wal_set:
                    conn.execute('PRAGMA journal_mode=WAL')
                    _wal_set = True
        conn.execute('PRAGMA foreign_keys=ON')
        # Register on flask.g so teardown_appcontext can auto-close leaked connections
        try:
            from flask import g, has_app_context
            if has_app_context():
                g._db_conn = conn
        except Exception as exc:
            _log.debug('Failed to bind DB connection to Flask context: %s', exc)
        return conn
    except Exception:
        if 'conn' in locals():
            try:
                conn.close()
            except Exception:
                pass
        raise


def _pool_acquire():
    """Return a pooled SQLite connection if available, else a fresh one.
    Pooled connections have already-set PRAGMAs (foreign_keys=ON) and are
    validated with a cheap SELECT 1 before reuse. Invalid connections are
    discarded and replaced."""
    global _pool_db_path
    if _pool is None:
        return get_db(), False
    # Invalidate pool if the target DB path changed (test isolation).
    current_path = get_db_path()
    with _pool_lock:
        if _pool_db_path != current_path:
            _pool_clear()
            _pool_db_path = current_path
        try:
            conn = _pool.get_nowait()
        except queue.Empty:
            return get_db(), False
    try:
        conn.execute('SELECT 1').fetchone()
        # Rebind to current flask.g so teardown can see it
        try:
            from flask import g, has_app_context
            if has_app_context():
                g._db_conn = conn
        except Exception:
            pass
        return conn, True
    except sqlite3.Error:
        try:
            conn.close()
        except Exception:
            pass
        return get_db(), False


def _pool_release(conn):
    """Return a connection to the pool if space available, else close it."""
    if _pool is None:
        try:
            conn.close()
        except Exception:
            pass
        return
    # Never pool a connection with an open transaction
    try:
        if conn.in_transaction:
            conn.rollback()
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        return
    try:
        _pool.put_nowait(conn)
    except queue.Full:
        try:
            conn.close()
        except Exception:
            pass


def pool_stats():
    """Return current pool size / capacity for diagnostics."""
    if _pool is None:
        return {'enabled': False, 'size': 0, 'capacity': 0}
    return {'enabled': True, 'size': _pool.qsize(), 'capacity': _POOL_SIZE}


@contextmanager
def db_session():
    """Context manager for DB connections with automatic close/release.

    Usage:
        with db_session() as db:
            db.execute(...)
            db.commit()
    """
    conn, from_pool = _pool_acquire()
    try:
        yield conn
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        # Don't return a possibly-broken conn to the pool
        try:
            conn.close()
        except Exception:
            pass
        raise
    else:
        # Unbind from flask.g before returning to pool so teardown_appcontext
        # does not close a pooled connection still in use by another caller.
        try:
            from flask import g, has_app_context
            if has_app_context() and getattr(g, '_db_conn', None) is conn:
                g._db_conn = None
        except Exception:
            pass
        # Always try to return to pool — Queue.put_nowait bounds size.
        # If pooling disabled or pool full, _pool_release closes it.
        _pool_release(conn)


def log_activity(event: str, service: str = None, detail: str = None, level: str = 'info'):
    """Log an activity event to the DB."""
    try:
        with db_session() as conn:
            conn.execute('INSERT INTO activity_log (event, service, detail, level) VALUES (?, ?, ?, ?)',
                         (event, service, detail, level))
            conn.commit()
    except sqlite3.Error as e:
        _log.debug(f'Failed to log activity: {e}')


def backup_db():
    """Create a timestamped backup of the database using SQLite backup API."""
    db_path = get_db_path()
    if db_path.startswith('file:') or not os.path.isfile(db_path):
        return
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    from datetime import datetime
    backup_path = os.path.join(backup_dir, f'nomad_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    # Use SQLite backup API for WAL-safe copies.
    # TRUNCATE checkpoint flushes all WAL frames into the main DB and truncates
    # the WAL file, guaranteeing backup() captures every committed transaction.
    # Fall back to PASSIVE if the database is busy (avoids blocking writers
    # indefinitely during normal operation — startup/shutdown backups are the
    # only callers and contention there is rare).
    src = sqlite3.connect(db_path, timeout=30)
    try:
        try:
            src.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except sqlite3.OperationalError:
            # Database is busy — PASSIVE checkpoint is still better than none.
            src.execute('PRAGMA wal_checkpoint(PASSIVE)')
        dst = sqlite3.connect(backup_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
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


def _get_migrations_dir():
    """Return the path to db_migrations/ relative to this file."""
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db_migrations')


def apply_migrations(conn):
    """Apply unapplied SQL migration files from db_migrations/.

    Each migration is executed inside its own transaction.  The filename
    is recorded in the ``_migrations`` table so it is never replayed.
    """
    migrations_dir = _get_migrations_dir()
    if not os.path.isdir(migrations_dir):
        _log.debug('No db_migrations/ directory found — skipping migrations')
        return

    with _migration_lock:
        # Ensure the tracking table exists (bootstrap)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS _migrations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                filename   TEXT    NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()

        # Which migrations have already been applied?
        applied = {
            row[0]
            for row in conn.execute('SELECT filename FROM _migrations').fetchall()
        }

        # Discover .sql files, sorted by name (numeric prefix keeps order)
        sql_files = sorted(glob.glob(os.path.join(migrations_dir, '*.sql')))

        for path in sql_files:
            filename = os.path.basename(path)
            if filename in applied:
                continue

            _log.info('Applying migration: %s', filename)
            with open(path, 'r', encoding='utf-8') as fh:
                sql = fh.read()

            try:
                # Execute each statement individually inside an explicit
                # transaction so that partial failures roll back cleanly.
                # conn.executescript() auto-commits after every statement,
                # which would leave the schema half-applied on error.
                conn.execute('BEGIN IMMEDIATE')
                for stmt in sql.split(';'):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(stmt)
                conn.execute(
                    'INSERT OR IGNORE INTO _migrations (filename) VALUES (?)', (filename,)
                )
                conn.commit()
                applied.add(filename)
                _log.info('Migration applied: %s', filename)
            except Exception:
                try:
                    conn.rollback()
                except Exception:
                    pass
                _log.exception('Migration FAILED: %s', filename)
                raise


def init_db():
    conn = get_db()
    try:
        _init_db_inner(conn)
        apply_migrations(conn)
        # Prune old activity log entries (older than 90 days)
        try:
            conn.execute("DELETE FROM activity_log WHERE created_at < datetime('now', '-90 days')")
            conn.commit()
        except Exception:
            pass  # Table may not exist yet on first run
    finally:
        conn.close()


def _create_core_tables(conn):
    """Create core tables: services, settings, notes, conversations, activity_log,
    documents, benchmarks, checklists, inventory, contacts, lan_messages,
    vault_entries, comms_log, drill_history."""
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
    ''')
    conn.commit()


def _create_comms_media_tables(conn):
    """Create comms/media tables: videos, audio, books, weather_log, waypoints,
    sensor_devices, sensor_readings."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            folder TEXT DEFAULT '',
            duration TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            url TEXT DEFAULT '',
            thumbnail TEXT DEFAULT '',
            filesize INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            artist TEXT DEFAULT '',
            album TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            folder TEXT DEFAULT '',
            duration TEXT DEFAULT '',
            url TEXT DEFAULT '',
            filesize INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT DEFAULT '',
            filename TEXT NOT NULL,
            format TEXT DEFAULT 'pdf',
            category TEXT DEFAULT 'general',
            folder TEXT DEFAULT '',
            description TEXT DEFAULT '',
            url TEXT DEFAULT '',
            filesize INTEGER DEFAULT 0,
            last_position TEXT DEFAULT '',
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
            icon TEXT DEFAULT 'pin',
            elevation_m REAL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sensor_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT NOT NULL DEFAULT 'manual',
            name TEXT NOT NULL,
            connection_type TEXT DEFAULT 'manual',
            connection_config TEXT DEFAULT '{}',
            polling_interval_sec INTEGER DEFAULT 300,
            last_reading TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id INTEGER NOT NULL,
            reading_type TEXT NOT NULL,
            value REAL NOT NULL,
            unit TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_federation_tables(conn):
    """Create federation tables: planting_calendar, preservation_log,
    federation_peers, federation_offers, federation_requests, federation_sitboard,
    mutual_aid_agreements, federation_transactions, sync_peers, vector_clocks,
    dead_drop_messages, group_exercises, training_datasets, training_jobs."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS planting_calendar (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            zone TEXT DEFAULT '7',
            month INTEGER NOT NULL,
            action TEXT NOT NULL,
            notes TEXT DEFAULT '',
            yield_per_sqft REAL DEFAULT 0,
            calories_per_lb REAL DEFAULT 0,
            days_to_harvest INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS preservation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crop TEXT NOT NULL,
            method TEXT NOT NULL DEFAULT 'canning',
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'quarts',
            batch_date TEXT DEFAULT '',
            shelf_life_months INTEGER DEFAULT 12,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS federation_peers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL UNIQUE,
            node_name TEXT DEFAULT '',
            trust_level TEXT DEFAULT 'observer',
            last_seen TIMESTAMP,
            last_sync TIMESTAMP,
            ip TEXT DEFAULT '',
            port INTEGER DEFAULT 8080,
            public_key TEXT DEFAULT '',
            shared_tables TEXT DEFAULT '[]',
            auto_sync INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS federation_offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            item_id INTEGER,
            quantity REAL DEFAULT 0,
            node_id TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS federation_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_type TEXT NOT NULL,
            description TEXT DEFAULT '',
            quantity REAL DEFAULT 0,
            urgency TEXT DEFAULT 'normal',
            node_id TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS federation_sitboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            node_name TEXT DEFAULT '',
            situation TEXT DEFAULT '{}',
            alerts TEXT DEFAULT '[]',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS mutual_aid_agreements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_node_id TEXT NOT NULL,
            peer_name TEXT DEFAULT '',
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            our_commitments TEXT DEFAULT '[]',
            their_commitments TEXT DEFAULT '[]',
            status TEXT DEFAULT 'draft',
            effective_date TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            signed_by_us INTEGER DEFAULT 0,
            signed_by_peer INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS federation_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            offer_id INTEGER,
            request_id INTEGER,
            from_node_id TEXT NOT NULL,
            to_node_id TEXT NOT NULL,
            item_type TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            status TEXT DEFAULT 'proposed',
            proposed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            accepted_at TIMESTAMP,
            delivered_at TIMESTAMP,
            confirmed_at TIMESTAMP,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sync_peers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id TEXT NOT NULL UNIQUE,
            last_synced_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS vector_clocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            table_name TEXT NOT NULL,
            row_hash TEXT NOT NULL,
            clock TEXT DEFAULT '{}',
            last_node TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(table_name, row_hash)
        );

        CREATE TABLE IF NOT EXISTS dead_drop_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_node_id TEXT DEFAULT '',
            from_name TEXT DEFAULT '',
            recipient TEXT DEFAULT '',
            encrypted_data TEXT DEFAULT '',
            checksum TEXT DEFAULT '',
            message_timestamp TEXT DEFAULT '',
            decrypted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS group_exercises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            exercise_id TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            scenario_type TEXT DEFAULT 'custom',
            description TEXT DEFAULT '',
            initiator_node TEXT DEFAULT '',
            initiator_name TEXT DEFAULT '',
            participants TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            current_phase INTEGER DEFAULT 0,
            shared_state TEXT DEFAULT '{}',
            decisions_log TEXT DEFAULT '[]',
            aar_text TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS training_datasets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            format TEXT DEFAULT 'jsonl',
            record_count INTEGER DEFAULT 0,
            file_path TEXT DEFAULT '',
            base_model TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS training_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dataset_id INTEGER,
            base_model TEXT NOT NULL,
            output_model TEXT DEFAULT '',
            method TEXT DEFAULT 'qlora',
            epochs INTEGER DEFAULT 3,
            learning_rate REAL DEFAULT 0.0002,
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            log_text TEXT DEFAULT '',
            started_at TEXT DEFAULT '',
            completed_at TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (dataset_id) REFERENCES training_datasets(id)
        );
    ''')
    conn.commit()


def _create_medical_security_tables(conn):
    """Create medical/security tables: perimeter_zones, triage_events,
    handoff_reports, freq_database, radio_profiles, map_routes, map_annotations,
    gps_tracks, timers, incidents, patients, vitals_log, wound_log,
    medication_log, triage_history, wound_updates, journal."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS perimeter_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            zone_type TEXT DEFAULT 'perimeter',
            boundary_geojson TEXT DEFAULT '',
            camera_ids TEXT DEFAULT '[]',
            waypoint_ids TEXT DEFAULT '[]',
            alert_on_entry INTEGER DEFAULT 1,
            alert_on_exit INTEGER DEFAULT 0,
            threat_level TEXT DEFAULT 'normal',
            color TEXT DEFAULT '#ff0000',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS triage_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL DEFAULT 'Mass Casualty',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS handoff_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            from_provider TEXT DEFAULT '',
            to_provider TEXT DEFAULT '',
            situation TEXT DEFAULT '',
            background TEXT DEFAULT '',
            assessment TEXT DEFAULT '',
            recommendation TEXT DEFAULT '',
            report_html TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS freq_database (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            frequency REAL NOT NULL,
            mode TEXT DEFAULT 'FM',
            bandwidth TEXT DEFAULT '',
            service TEXT NOT NULL,
            description TEXT DEFAULT '',
            region TEXT DEFAULT 'US',
            license_required INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS radio_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            radio_model TEXT DEFAULT '',
            name TEXT NOT NULL,
            channels TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS map_routes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            waypoint_ids TEXT DEFAULT '[]',
            distance_km REAL DEFAULT 0,
            estimated_time_min INTEGER DEFAULT 0,
            terrain_difficulty TEXT DEFAULT 'moderate',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS map_annotations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT DEFAULT 'polygon',
            geojson TEXT NOT NULL,
            label TEXT DEFAULT '',
            name TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            color TEXT DEFAULT '#ff0000',
            notes TEXT DEFAULT '',
            is_geofence INTEGER DEFAULT 0,
            properties TEXT DEFAULT '{}',
            radius_m REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS gps_tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Track',
            geojson TEXT NOT NULL DEFAULT '{}',
            total_distance_m REAL DEFAULT 0,
            total_ascent_m REAL DEFAULT 0,
            duration_sec INTEGER DEFAULT 0,
            started_at TIMESTAMP,
            ended_at TIMESTAMP,
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
            age INTEGER CHECK (age IS NULL OR (age >= 0 AND age <= 200)),
            weight_kg REAL CHECK (weight_kg IS NULL OR (weight_kg >= 0 AND weight_kg <= 700)),
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
            bp_systolic INTEGER CHECK (bp_systolic IS NULL OR (bp_systolic >= 20 AND bp_systolic <= 350)),
            bp_diastolic INTEGER CHECK (bp_diastolic IS NULL OR (bp_diastolic >= 10 AND bp_diastolic <= 250)),
            pulse INTEGER CHECK (pulse IS NULL OR (pulse >= 0 AND pulse <= 300)),
            resp_rate INTEGER CHECK (resp_rate IS NULL OR (resp_rate >= 0 AND resp_rate <= 100)),
            temp_f REAL CHECK (temp_f IS NULL OR (temp_f >= 70.0 AND temp_f <= 115.0)),
            spo2 INTEGER CHECK (spo2 IS NULL OR (spo2 >= 0 AND spo2 <= 100)),
            pain_level INTEGER CHECK (pain_level IS NULL OR (pain_level >= 0 AND pain_level <= 10)),
            gcs INTEGER CHECK (gcs IS NULL OR (gcs >= 3 AND gcs <= 15)),
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

        CREATE TABLE IF NOT EXISTS medication_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            drug_name TEXT NOT NULL,
            dose TEXT DEFAULT '',
            route TEXT DEFAULT '',
            administered_by TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            next_dose_due TIMESTAMP,
            administered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS triage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            old_category TEXT DEFAULT '',
            new_category TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            changed_by TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS wound_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wound_id INTEGER NOT NULL,
            patient_id INTEGER NOT NULL,
            status TEXT DEFAULT '',
            treatment TEXT DEFAULT '',
            size_cm REAL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry TEXT NOT NULL,
            mood TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_power_garden_tables(conn):
    """Create power/garden tables: cameras, access_log, power_devices, power_log,
    generators, generator_sessions, sync_log, garden_plots, seeds, harvest_log,
    livestock, scenarios, alerts, subscriptions, skills, ammo_inventory,
    community_resources, radiation_log, fuel_storage, equipment_log, scheduled_tasks."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS cameras (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            stream_type TEXT DEFAULT 'mjpeg',
            location TEXT DEFAULT '',
            zone TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL DEFAULT '',
            direction TEXT DEFAULT 'entry',
            location TEXT DEFAULT '',
            method TEXT DEFAULT 'visual',
            notes TEXT DEFAULT '',
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

        CREATE TABLE IF NOT EXISTS generators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            rated_watts INTEGER DEFAULT 0,
            fuel_type TEXT DEFAULT 'gasoline',
            tank_capacity_gal REAL DEFAULT 0,
            fuel_consumption_gph REAL DEFAULT 0,
            oil_change_interval_hours REAL DEFAULT 100,
            total_runtime_hours REAL DEFAULT 0,
            last_started TIMESTAMP,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS generator_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generator_id INTEGER NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            ended_at TIMESTAMP,
            runtime_hours REAL DEFAULT 0,
            fuel_used_gal REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            FOREIGN KEY (generator_id) REFERENCES generators(id)
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

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT NOT NULL,
            channel_url TEXT NOT NULL UNIQUE,
            category TEXT DEFAULT '',
            last_checked TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            proficiency TEXT DEFAULT 'none',
            notes TEXT DEFAULT '',
            last_practiced TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS ammo_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            caliber TEXT NOT NULL,
            brand TEXT DEFAULT '',
            bullet_weight TEXT DEFAULT '',
            bullet_type TEXT DEFAULT '',
            quantity INTEGER DEFAULT 0,
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS community_resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            distance_mi REAL DEFAULT 0,
            skills TEXT DEFAULT '[]',
            equipment TEXT DEFAULT '[]',
            contact TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            trust_level TEXT DEFAULT 'unknown',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS radiation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dose_rate_rem REAL NOT NULL,
            location TEXT DEFAULT '',
            cumulative_rem REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS fuel_storage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fuel_type TEXT NOT NULL,
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'gallons',
            container TEXT DEFAULT '',
            location TEXT DEFAULT '',
            stabilizer_added INTEGER DEFAULT 0,
            date_stored TEXT DEFAULT '',
            expires TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS equipment_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            last_service TEXT DEFAULT '',
            next_service TEXT DEFAULT '',
            service_notes TEXT DEFAULT '',
            status TEXT DEFAULT 'operational',
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'custom',
            recurrence TEXT DEFAULT 'once',
            next_due TIMESTAMP,
            assigned_to TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            completed_count INTEGER DEFAULT 0,
            last_completed TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_extended_tables(conn):
    """Create extended tables: mesh_messages, kb_workspaces, conversation_branches,
    inventory_photos, inventory_checkouts, shopping_list, note_tags, note_links,
    note_templates, media_progress, playlists, drug_interactions, wound_photos,
    weather_readings, lan_channels, lan_presence, lan_transfers, companion_plants,
    seed_inventory, pest_guide, benchmark_results, watch_schedules,
    weather_action_rules, upc_database, inventory_batches, consumption_log,
    motion_events, download_queue, task_completions, comms_schedules, water_log,
    storm_events, note_revisions, skill_progression."""
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS mesh_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_node TEXT DEFAULT '',
            to_node TEXT DEFAULT '',
            message TEXT NOT NULL,
            channel TEXT DEFAULT '',
            rssi REAL,
            snr REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 1: AI Chat — KB Workspaces & Conversation Branching ═══ */
        CREATE TABLE IF NOT EXISTS kb_workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            watch_folder TEXT DEFAULT '',
            auto_index INTEGER DEFAULT 0,
            doc_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS conversation_branches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            parent_message_idx INTEGER NOT NULL DEFAULT 0,
            messages TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 3: Inventory — Photos, Check-out, Locations ═══ */
        CREATE TABLE IF NOT EXISTS inventory_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            caption TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventory_checkouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            checked_out_to TEXT NOT NULL,
            quantity REAL DEFAULT 1,
            reason TEXT DEFAULT '',
            checked_out_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            returned_at TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS shopping_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT '',
            quantity_needed REAL DEFAULT 0,
            unit TEXT DEFAULT 'ea',
            inventory_id INTEGER,
            purchased INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 5: Notes — Tags, Links, Templates ═══ */
        CREATE TABLE IF NOT EXISTS note_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(note_id, tag)
        );

        CREATE TABLE IF NOT EXISTS note_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_note_id INTEGER NOT NULL,
            target_note_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_note_id, target_note_id)
        );

        CREATE TABLE IF NOT EXISTS note_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            content TEXT DEFAULT '',
            icon TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 6: Media — Playback Progress & Playlists ═══ */
        CREATE TABLE IF NOT EXISTS media_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            media_type TEXT NOT NULL,
            media_id INTEGER NOT NULL,
            position_sec REAL DEFAULT 0,
            duration_sec REAL DEFAULT 0,
            completed INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(media_type, media_id)
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            media_type TEXT DEFAULT 'audio',
            items TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 7: Medical — Drug Interactions ═══ */
        CREATE TABLE IF NOT EXISTS drug_interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drug_a TEXT NOT NULL,
            drug_b TEXT NOT NULL,
            severity TEXT DEFAULT 'moderate',
            description TEXT DEFAULT '',
            recommendation TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS wound_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wound_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            caption TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 9: Weather — Readings & Predictions ═══ */
        CREATE TABLE IF NOT EXISTS weather_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT DEFAULT 'manual',
            pressure_hpa REAL,
            temp_f REAL,
            humidity REAL,
            wind_dir TEXT DEFAULT '',
            wind_speed_mph REAL,
            prediction TEXT DEFAULT '',
            zambretti_code INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 10: LAN & Mesh — Channels, Presence, File Transfer ═══ */
        CREATE TABLE IF NOT EXISTS lan_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS lan_presence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_name TEXT NOT NULL,
            ip TEXT NOT NULL,
            status TEXT DEFAULT 'online',
            version TEXT DEFAULT '',
            last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(ip)
        );

        CREATE TABLE IF NOT EXISTS lan_transfers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_size INTEGER DEFAULT 0,
            direction TEXT DEFAULT 'incoming',
            peer_ip TEXT DEFAULT '',
            peer_name TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            progress REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 11: Garden — Companions, Seed Inventory, Pest Guide ═══ */
        CREATE TABLE IF NOT EXISTS companion_plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_a TEXT NOT NULL,
            plant_b TEXT NOT NULL,
            relationship TEXT DEFAULT 'companion',
            notes TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS seed_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            species TEXT NOT NULL,
            variety TEXT DEFAULT '',
            quantity INTEGER DEFAULT 0,
            unit TEXT DEFAULT 'seeds',
            viability_pct REAL DEFAULT 90,
            year_acquired INTEGER,
            source TEXT DEFAULT '',
            days_to_maturity INTEGER,
            planting_depth_in REAL,
            spacing_in REAL,
            sun_requirement TEXT DEFAULT 'full',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS pest_guide (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pest_type TEXT DEFAULT 'insect',
            affects TEXT DEFAULT '',
            symptoms TEXT DEFAULT '',
            treatment TEXT DEFAULT '',
            prevention TEXT DEFAULT '',
            image_url TEXT DEFAULT ''
        );

        /* ═══ v5.0 Phase 12: Benchmark — Extended Test Types ═══ */
        CREATE TABLE IF NOT EXISTS benchmark_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_type TEXT NOT NULL DEFAULT 'full',
            scores TEXT DEFAULT '{}',
            hardware TEXT DEFAULT '{}',
            details TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 15: Watch/Shift Rotation Planner ═══ */
        CREATE TABLE IF NOT EXISTS watch_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'Watch Schedule',
            start_date TEXT NOT NULL,
            end_date TEXT,
            shift_duration_hours INTEGER NOT NULL DEFAULT 4,
            personnel TEXT DEFAULT '[]',
            schedule_json TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ v5.0 Phase 15: Weather-Triggered Action Rules ═══ */
        CREATE TABLE IF NOT EXISTS weather_action_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            condition_type TEXT NOT NULL DEFAULT 'pressure_drop',
            threshold REAL NOT NULL,
            comparison TEXT NOT NULL DEFAULT 'lt',
            action_type TEXT NOT NULL DEFAULT 'alert',
            action_data TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            last_triggered TEXT DEFAULT '',
            cooldown_minutes INTEGER DEFAULT 60,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ UPC Barcode Database ═══ */
        CREATE TABLE IF NOT EXISTS upc_database (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            upc TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'General',
            brand TEXT DEFAULT '',
            size TEXT DEFAULT '',
            unit TEXT DEFAULT 'each',
            default_shelf_life_days INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ═══ Batch-Level Expiration Tracking ═══ */
        CREATE TABLE IF NOT EXISTS inventory_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
            quantity REAL NOT NULL DEFAULT 0,
            expiration TEXT,
            lot_number TEXT,
            date_acquired TEXT,
            cost REAL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        /* ═══ Consumption History ═══ */
        CREATE TABLE IF NOT EXISTS consumption_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL REFERENCES inventory(id) ON DELETE CASCADE,
            amount REAL NOT NULL,
            consumed_at TEXT DEFAULT (datetime('now')),
            notes TEXT
        );

        /* ═══ Motion Detection Captures ═══ */
        CREATE TABLE IF NOT EXISTS motion_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            camera_id INTEGER NOT NULL,
            mean_diff REAL,
            image_path TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        /* ═══ Persistent Download Queue ═══ */
        CREATE TABLE IF NOT EXISTS download_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            status TEXT DEFAULT 'queued',
            retries INTEGER DEFAULT 0,
            error TEXT,
            file_path TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );

        /* ═══ Task Completion History ═══ */
        CREATE TABLE IF NOT EXISTS task_completions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            completed_by TEXT,
            completed_at TEXT DEFAULT (datetime('now')),
            notes TEXT,
            duration_minutes INTEGER
        );

        /* ═══ Communications Window Scheduling ═══ */
        CREATE TABLE IF NOT EXISTS comms_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            frequency TEXT NOT NULL,
            mode TEXT,
            net_name TEXT,
            check_in_time TEXT,
            assigned_operator TEXT,
            priority INTEGER DEFAULT 5,
            active INTEGER DEFAULT 1,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        /* ═══ Garden Water Tracking ═══ */
        CREATE TABLE IF NOT EXISTS water_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plot_id INTEGER,
            source TEXT DEFAULT 'manual',
            gallons REAL NOT NULL,
            date TEXT DEFAULT (date('now')),
            notes TEXT
        );

        /* ═══ Weather Storm Lifecycle ═══ */
        CREATE TABLE IF NOT EXISTS storm_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            storm_type TEXT,
            peak_intensity TEXT,
            total_pressure_drop REAL,
            min_pressure REAL,
            wind_peak REAL,
            precip_total REAL,
            notes TEXT
        );

        /* ═══ Note Version History ═══ */
        CREATE TABLE IF NOT EXISTS note_revisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
            title TEXT,
            content TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        /* ═══ Training Skill Tracking ═══ */
        CREATE TABLE IF NOT EXISTS skill_progression (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_tag TEXT NOT NULL,
            score INTEGER,
            scenario_type TEXT,
            drill_type TEXT,
            recorded_at TEXT DEFAULT (datetime('now'))
        );

        /* ═══ v7.6.0: Family Check-in Board ═══
           One row per household member. Status is one of: 'ok', 'needs_help',
           'en_route', 'unaccounted'. Intentionally separate from contacts
           because (a) not every contact is a family member, and (b) the
           check-in state is high-frequency mutation that doesn't belong in
           the contacts table which is used as a stable reference directory. */
        CREATE TABLE IF NOT EXISTS family_checkins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'ok',
            location TEXT DEFAULT '',
            note TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_water_financial_vehicle_loadout_tables(conn):
    """v7.8.0 — Water management, financial preparedness, vehicles, and loadout tables."""
    conn.executescript('''
        /* ─── Water Management ─── */
        CREATE TABLE IF NOT EXISTS water_storage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            container_type TEXT DEFAULT '',
            capacity_gallons REAL DEFAULT 0,
            current_gallons REAL DEFAULT 0,
            fill_date TEXT DEFAULT '',
            treatment_method TEXT DEFAULT '',
            location TEXT DEFAULT '',
            expiration TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS water_filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            filter_type TEXT DEFAULT '',
            brand TEXT DEFAULT '',
            max_gallons REAL DEFAULT 0,
            gallons_processed REAL DEFAULT 0,
            install_date TEXT DEFAULT '',
            replacement_date TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS water_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            source_type TEXT DEFAULT 'unknown',
            lat REAL,
            lng REAL,
            waypoint_id INTEGER,
            flow_rate_gph REAL DEFAULT 0,
            potable INTEGER DEFAULT 0,
            treatment_required INTEGER DEFAULT 1,
            seasonal INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS water_quality_tests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id INTEGER REFERENCES water_sources(id),
            test_date TEXT DEFAULT '',
            ph REAL,
            tds_ppm REAL,
            turbidity_ntu REAL,
            coliform TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Financial Preparedness ─── */
        CREATE TABLE IF NOT EXISTS financial_cash (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            denomination TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            location TEXT DEFAULT '',
            currency TEXT DEFAULT 'USD',
            notes TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS financial_metals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metal_type TEXT DEFAULT 'gold',
            form TEXT DEFAULT 'coin',
            description TEXT DEFAULT '',
            weight_oz REAL DEFAULT 0,
            purity REAL DEFAULT 0.999,
            purchase_price REAL DEFAULT 0,
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS financial_barter (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'other',
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'ea',
            estimated_value REAL DEFAULT 0,
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS financial_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT DEFAULT 'other',
            description TEXT DEFAULT '',
            account_number TEXT DEFAULT '',
            institution TEXT DEFAULT '',
            expiration TEXT DEFAULT '',
            location TEXT DEFAULT '',
            digital_copy INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Vehicles & BOV ─── */
        CREATE TABLE IF NOT EXISTS vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            year INTEGER,
            make TEXT DEFAULT '',
            model TEXT DEFAULT '',
            vin TEXT DEFAULT '',
            fuel_type TEXT DEFAULT 'gasoline',
            tank_capacity_gal REAL DEFAULT 0,
            mpg REAL DEFAULT 0,
            odometer INTEGER DEFAULT 0,
            color TEXT DEFAULT '',
            plate TEXT DEFAULT '',
            insurance_exp TEXT DEFAULT '',
            registration_exp TEXT DEFAULT '',
            location TEXT DEFAULT '',
            role TEXT DEFAULT 'daily',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS vehicle_maintenance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER REFERENCES vehicles(id),
            service_type TEXT DEFAULT '',
            description TEXT DEFAULT '',
            mileage INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            service_date TEXT DEFAULT '',
            next_due_date TEXT DEFAULT '',
            next_due_mileage INTEGER DEFAULT 0,
            status TEXT DEFAULT 'completed',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS vehicle_fuel_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicle_id INTEGER REFERENCES vehicles(id),
            gallons REAL DEFAULT 0,
            cost_per_gallon REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            odometer INTEGER DEFAULT 0,
            station TEXT DEFAULT '',
            fuel_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Bug-Out Bag Loadout ─── */
        CREATE TABLE IF NOT EXISTS loadout_bags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            owner TEXT DEFAULT '',
            bag_type TEXT DEFAULT '72hour',
            season TEXT DEFAULT 'all',
            target_weight_lb REAL DEFAULT 0,
            location TEXT DEFAULT '',
            last_inspected TEXT DEFAULT '',
            photo_path TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS loadout_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bag_id INTEGER REFERENCES loadout_bags(id),
            name TEXT NOT NULL,
            category TEXT DEFAULT 'other',
            quantity INTEGER DEFAULT 1,
            weight_oz REAL DEFAULT 0,
            packed INTEGER DEFAULT 0,
            expiration TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_pace_evac_container_tables(conn):
    """v7.9.0 — PACE plans, evacuation planning, inventory containers."""
    conn.executescript('''
        /* ─── PACE Communications Plans ─── */
        CREATE TABLE IF NOT EXISTS pace_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            scenario TEXT DEFAULT '',
            is_active INTEGER DEFAULT 0,
            primary_method TEXT DEFAULT '',
            primary_freq TEXT DEFAULT '',
            primary_equipment TEXT DEFAULT '',
            primary_callsign TEXT DEFAULT '',
            primary_schedule TEXT DEFAULT '',
            primary_notes TEXT DEFAULT '',
            alternate_method TEXT DEFAULT '',
            alternate_freq TEXT DEFAULT '',
            alternate_equipment TEXT DEFAULT '',
            alternate_callsign TEXT DEFAULT '',
            alternate_schedule TEXT DEFAULT '',
            alternate_notes TEXT DEFAULT '',
            contingency_method TEXT DEFAULT '',
            contingency_freq TEXT DEFAULT '',
            contingency_equipment TEXT DEFAULT '',
            contingency_callsign TEXT DEFAULT '',
            contingency_schedule TEXT DEFAULT '',
            contingency_notes TEXT DEFAULT '',
            emergency_method TEXT DEFAULT '',
            emergency_freq TEXT DEFAULT '',
            emergency_equipment TEXT DEFAULT '',
            emergency_callsign TEXT DEFAULT '',
            emergency_schedule TEXT DEFAULT '',
            emergency_notes TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Evacuation Plans ─── */
        CREATE TABLE IF NOT EXISTS evac_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            plan_type TEXT DEFAULT 'evacuate',
            is_active INTEGER DEFAULT 0,
            destination TEXT DEFAULT '',
            primary_route TEXT DEFAULT '',
            alternate_route TEXT DEFAULT '',
            distance_miles REAL DEFAULT 0,
            estimated_time_min INTEGER DEFAULT 0,
            trigger_conditions TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS rally_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evac_plan_id INTEGER REFERENCES evac_plans(id),
            name TEXT NOT NULL,
            location TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            point_type TEXT DEFAULT 'assembly',
            sequence_order INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS evac_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evac_plan_id INTEGER REFERENCES evac_plans(id),
            person_name TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            vehicle TEXT DEFAULT '',
            go_bag TEXT DEFAULT '',
            checked_in INTEGER DEFAULT 0,
            checked_in_at TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Inventory Containers ─── */
        CREATE TABLE IF NOT EXISTS inventory_containers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            container_type TEXT DEFAULT 'bag',
            location TEXT DEFAULT '',
            parent_container_id INTEGER DEFAULT NULL,
            weight_capacity_lb REAL DEFAULT 0,
            volume_capacity_cf REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_readiness_alerts_threat_drill_tables(conn):
    """v7.10.0 — Readiness goals, alert rules engine, threat intel, evac drills."""
    conn.executescript('''
        /* ─── Readiness Goals ─── */
        CREATE TABLE IF NOT EXISTS readiness_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'General',
            target_days INTEGER DEFAULT 0,
            target_quantity REAL DEFAULT 0,
            target_unit TEXT DEFAULT '',
            metric_source TEXT DEFAULT 'inventory',
            metric_query TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Alert Rules Engine (generalized from weather_action_rules) ─── */
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            condition_type TEXT NOT NULL DEFAULT 'inventory_low',
            threshold REAL NOT NULL DEFAULT 0,
            comparison TEXT NOT NULL DEFAULT 'lt',
            action_type TEXT NOT NULL DEFAULT 'alert',
            action_data TEXT DEFAULT '{}',
            enabled INTEGER DEFAULT 1,
            cooldown_minutes INTEGER DEFAULT 60,
            severity TEXT DEFAULT 'warning',
            category TEXT DEFAULT '',
            description TEXT DEFAULT '',
            last_triggered TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS alert_rule_triggers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rule_id INTEGER REFERENCES alert_rules(id),
            condition_value REAL DEFAULT 0,
            threshold_value REAL DEFAULT 0,
            action_taken TEXT DEFAULT '',
            triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Threat Intelligence ─── */
        CREATE TABLE IF NOT EXISTS threat_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            feed_type TEXT DEFAULT 'manual',
            url TEXT DEFAULT '',
            category TEXT DEFAULT 'other',
            refresh_interval_min INTEGER DEFAULT 60,
            enabled INTEGER DEFAULT 1,
            last_fetched TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS threat_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            feed_id INTEGER REFERENCES threat_feeds(id),
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'other',
            severity TEXT DEFAULT 'medium',
            severity_score INTEGER DEFAULT 2,
            source_url TEXT DEFAULT '',
            location TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            tags TEXT DEFAULT '[]',
            impact_assessment TEXT DEFAULT '',
            recommended_actions TEXT DEFAULT '',
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Evacuation Drill Runs ─── */
        CREATE TABLE IF NOT EXISTS evac_drill_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evac_plan_id INTEGER REFERENCES evac_plans(id),
            name TEXT NOT NULL,
            drill_type TEXT DEFAULT 'full_evacuation',
            status TEXT DEFAULT 'pending',
            participants INTEGER DEFAULT 0,
            target_time_sec INTEGER DEFAULT 0,
            total_time_sec INTEGER DEFAULT 0,
            started_at TEXT DEFAULT '',
            completed_at TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            weather_conditions TEXT DEFAULT '',
            after_action_notes TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS evac_drill_laps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drill_run_id INTEGER REFERENCES evac_drill_runs(id),
            lap_number INTEGER DEFAULT 1,
            checkpoint_name TEXT DEFAULT '',
            elapsed_sec INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _apply_column_migrations(conn):
    """Apply ALTER TABLE column migrations (before indexes that depend on new columns)."""
    for migration in [
        'ALTER TABLE inventory ADD COLUMN daily_usage REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN barcode TEXT DEFAULT ""',
        'ALTER TABLE inventory ADD COLUMN cost REAL DEFAULT 0',
        'ALTER TABLE notes ADD COLUMN tags TEXT DEFAULT ""',
        'ALTER TABLE notes ADD COLUMN pinned INTEGER DEFAULT 0',
        'ALTER TABLE documents ADD COLUMN doc_category TEXT DEFAULT ""',
        'ALTER TABLE documents ADD COLUMN summary TEXT DEFAULT ""',
        'ALTER TABLE documents ADD COLUMN entities TEXT DEFAULT "[]"',
        'ALTER TABLE documents ADD COLUMN linked_records TEXT DEFAULT "[]"',
        'ALTER TABLE videos ADD COLUMN folder TEXT DEFAULT ""',
        'ALTER TABLE videos ADD COLUMN url TEXT DEFAULT ""',
        'ALTER TABLE videos ADD COLUMN thumbnail TEXT DEFAULT ""',
        'ALTER TABLE videos ADD COLUMN filesize INTEGER DEFAULT 0',
        'ALTER TABLE videos ADD COLUMN favorited INTEGER DEFAULT 0',
        'ALTER TABLE audio ADD COLUMN favorited INTEGER DEFAULT 0',
        'ALTER TABLE books ADD COLUMN favorited INTEGER DEFAULT 0',
        'ALTER TABLE waypoints ADD COLUMN icon TEXT DEFAULT "pin"',
        'ALTER TABLE waypoints ADD COLUMN elevation_m REAL',
        'ALTER TABLE harvest_log ADD COLUMN yield_per_sqft REAL DEFAULT 0',
        'ALTER TABLE power_log ADD COLUMN cumulative_wh REAL DEFAULT 0',
        'ALTER TABLE patients ADD COLUMN triage_category TEXT DEFAULT ""',
        'ALTER TABLE patients ADD COLUMN care_phase TEXT DEFAULT ""',
        'ALTER TABLE wound_log ADD COLUMN tourniquet_time TEXT DEFAULT ""',
        'ALTER TABLE wound_log ADD COLUMN intervention_type TEXT DEFAULT ""',
        # v5.0 migrations
        'ALTER TABLE inventory ADD COLUMN lot_number TEXT DEFAULT ""',
        'ALTER TABLE inventory ADD COLUMN photo_path TEXT DEFAULT ""',
        'ALTER TABLE inventory ADD COLUMN checked_out_to TEXT DEFAULT ""',
        'ALTER TABLE documents ADD COLUMN workspace_id INTEGER DEFAULT 0',
        'ALTER TABLE notes ADD COLUMN template TEXT DEFAULT ""',
        'ALTER TABLE notes ADD COLUMN is_journal INTEGER DEFAULT 0',
        'ALTER TABLE conversations ADD COLUMN branch_count INTEGER DEFAULT 0',
        'ALTER TABLE videos ADD COLUMN subtitle_path TEXT DEFAULT ""',
        'ALTER TABLE audio ADD COLUMN album_art TEXT DEFAULT ""',
        'ALTER TABLE books ADD COLUMN total_pages INTEGER DEFAULT 0',
        'ALTER TABLE patients ADD COLUMN photo_path TEXT DEFAULT ""',
        'ALTER TABLE weather_log ADD COLUMN humidity REAL',
        'ALTER TABLE weather_log ADD COLUMN prediction TEXT DEFAULT ""',
        'ALTER TABLE benchmarks ADD COLUMN test_type TEXT DEFAULT "full"',
        'ALTER TABLE benchmarks ADD COLUMN storage_read_mbps REAL DEFAULT 0',
        'ALTER TABLE benchmarks ADD COLUMN storage_write_mbps REAL DEFAULT 0',
        'ALTER TABLE benchmarks ADD COLUMN net_throughput_mbps REAL DEFAULT 0',
        'ALTER TABLE freq_database ADD COLUMN channel_name TEXT DEFAULT ""',
        'ALTER TABLE freq_database ADD COLUMN tone_freq REAL',
        'ALTER TABLE map_routes ADD COLUMN gpx_data TEXT DEFAULT ""',
        'ALTER TABLE map_routes ADD COLUMN elevation_profile TEXT DEFAULT "[]"',
        # v4.6.0 — garden geo overlay
        'ALTER TABLE garden_plots ADD COLUMN lat REAL',
        'ALTER TABLE garden_plots ADD COLUMN lng REAL',
        'ALTER TABLE garden_plots ADD COLUMN boundary_geojson TEXT DEFAULT ""',
        # v4.6.0 — federation peer geo for supply chain map
        'ALTER TABLE federation_peers ADD COLUMN lat REAL',
        'ALTER TABLE federation_peers ADD COLUMN lng REAL',
        # v4.8.0 — vector clocks for federation conflict detection
        'ALTER TABLE sync_log ADD COLUMN vector_clock TEXT DEFAULT "{}"',
        'ALTER TABLE sync_log ADD COLUMN conflicts_detected INTEGER DEFAULT 0',
        'ALTER TABLE sync_log ADD COLUMN conflict_details TEXT DEFAULT "[]"',
        # v4.9.0 — conflict resolution tracking
        'ALTER TABLE sync_log ADD COLUMN resolved INTEGER DEFAULT 0',
        'ALTER TABLE sync_log ADD COLUMN resolution TEXT DEFAULT ""',
        # GPS tracks & geofence support
        'ALTER TABLE map_annotations ADD COLUMN name TEXT DEFAULT ""',
        'ALTER TABLE map_annotations ADD COLUMN lat REAL',
        'ALTER TABLE map_annotations ADD COLUMN lng REAL',
        'ALTER TABLE map_annotations ADD COLUMN is_geofence INTEGER DEFAULT 0',
        'ALTER TABLE map_annotations ADD COLUMN properties TEXT DEFAULT "{}"',
        'ALTER TABLE map_annotations ADD COLUMN radius_m REAL DEFAULT 0',
        # Nutrition tracking columns for food security dashboard
        'ALTER TABLE inventory ADD COLUMN calories_per_unit REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN protein_g REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN fat_g REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN carbs_g REAL DEFAULT 0',
        'ALTER TABLE preservation_log ADD COLUMN calories_per_unit REAL DEFAULT 0',
        # v7.9.0 — Container management
        'ALTER TABLE inventory ADD COLUMN container_id INTEGER DEFAULT NULL',
        'ALTER TABLE inventory ADD COLUMN weight_oz REAL DEFAULT 0',
        # v7.9.0 — Preservation batch tracker expansion
        'ALTER TABLE preservation_log ADD COLUMN jar_size TEXT DEFAULT ""',
        'ALTER TABLE preservation_log ADD COLUMN jar_count INTEGER DEFAULT 0',
        'ALTER TABLE preservation_log ADD COLUMN processing_time_min INTEGER DEFAULT 0',
        'ALTER TABLE preservation_log ADD COLUMN pressure_psi REAL DEFAULT 0',
        'ALTER TABLE preservation_log ADD COLUMN storage_temp TEXT DEFAULT ""',
        'ALTER TABLE preservation_log ADD COLUMN storage_location TEXT DEFAULT ""',
        'ALTER TABLE preservation_log ADD COLUMN batch_label TEXT DEFAULT ""',
        'ALTER TABLE preservation_log ADD COLUMN success INTEGER DEFAULT 1',
        'ALTER TABLE preservation_log ADD COLUMN yield_amount REAL DEFAULT 0',
        'ALTER TABLE preservation_log ADD COLUMN yield_unit TEXT DEFAULT ""',
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists


def _create_indexes(conn):
    """Create performance indexes (after migrations so columns exist)."""
    for idx in [
        'CREATE INDEX IF NOT EXISTS idx_activity_log_timestamp ON activity_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_activity_log_level ON activity_log(level)',
        'CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_category ON inventory(category)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_category_name ON inventory(category, name)',
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
        'CREATE INDEX IF NOT EXISTS idx_access_log_created ON access_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)',
        'CREATE INDEX IF NOT EXISTS idx_ammo_caliber ON ammo_inventory(caliber)',
        'CREATE INDEX IF NOT EXISTS idx_community_trust ON community_resources(trust_level)',
        'CREATE INDEX IF NOT EXISTS idx_radiation_created ON radiation_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_fuel_type ON fuel_storage(fuel_type)',
        'CREATE INDEX IF NOT EXISTS idx_equipment_status ON equipment_log(status)',
        'CREATE INDEX IF NOT EXISTS idx_equipment_next_service ON equipment_log(next_service)',
        'CREATE INDEX IF NOT EXISTS idx_videos_category ON videos(category)',
        'CREATE INDEX IF NOT EXISTS idx_videos_folder ON videos(folder)',
        'CREATE INDEX IF NOT EXISTS idx_audio_category ON audio(category)',
        'CREATE INDEX IF NOT EXISTS idx_audio_folder ON audio(folder)',
        'CREATE INDEX IF NOT EXISTS idx_books_category ON books(category)',
        'CREATE INDEX IF NOT EXISTS idx_contacts_role ON contacts(role)',
        'CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity)',
        'CREATE INDEX IF NOT EXISTS idx_conversations_model ON conversations(model)',
        'CREATE INDEX IF NOT EXISTS idx_sync_log_created ON sync_log(created_at DESC)',
        # Media tables — sorting/search
        'CREATE INDEX IF NOT EXISTS idx_videos_created ON videos(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_audio_created ON audio(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_books_folder ON books(folder)',
        # Comms & messaging
        'CREATE INDEX IF NOT EXISTS idx_lan_messages_created ON lan_messages(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_comms_log_created ON comms_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_comms_log_callsign ON comms_log(callsign)',
        # Drill & training
        'CREATE INDEX IF NOT EXISTS idx_drill_history_created ON drill_history(created_at DESC)',
        # Garden & livestock
        'CREATE INDEX IF NOT EXISTS idx_harvest_log_created ON harvest_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_harvest_log_plot ON harvest_log(plot_id)',
        'CREATE INDEX IF NOT EXISTS idx_seeds_species ON seeds(species)',
        'CREATE INDEX IF NOT EXISTS idx_livestock_species ON livestock(species)',
        # Security & power
        'CREATE INDEX IF NOT EXISTS idx_cameras_status ON cameras(status)',
        'CREATE INDEX IF NOT EXISTS idx_power_devices_status ON power_devices(status)',
        # Journal & scenarios
        'CREATE INDEX IF NOT EXISTS idx_journal_created ON journal(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_scenarios_status ON scenarios(status)',
        # Fuel & subscriptions
        'CREATE INDEX IF NOT EXISTS idx_fuel_expires ON fuel_storage(expires)',
        'CREATE INDEX IF NOT EXISTS idx_subscriptions_channel ON subscriptions(channel_name)',
        'CREATE INDEX IF NOT EXISTS idx_sensor_readings_device ON sensor_readings(device_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_sensor_readings_type ON sensor_readings(reading_type)',
        'CREATE INDEX IF NOT EXISTS idx_planting_calendar_zone ON planting_calendar(zone, month)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_log_crop ON preservation_log(crop)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_log_date ON preservation_log(batch_date)',
        'CREATE INDEX IF NOT EXISTS idx_federation_peers_node ON federation_peers(node_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_offers_status ON federation_offers(status)',
        'CREATE INDEX IF NOT EXISTS idx_federation_requests_status ON federation_requests(status)',
        'CREATE INDEX IF NOT EXISTS idx_federation_sitboard_node ON federation_sitboard(node_id)',
        'CREATE INDEX IF NOT EXISTS idx_freq_database_service ON freq_database(service)',
        'CREATE INDEX IF NOT EXISTS idx_freq_database_freq ON freq_database(frequency)',
        'CREATE INDEX IF NOT EXISTS idx_radio_profiles_name ON radio_profiles(name)',
        'CREATE INDEX IF NOT EXISTS idx_map_routes_created ON map_routes(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_map_annotations_type ON map_annotations(type)',
        'CREATE INDEX IF NOT EXISTS idx_waypoints_icon ON waypoints(icon)',
        # Scheduled tasks
        'CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_due ON scheduled_tasks(next_due)',
        'CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_category ON scheduled_tasks(category)',
        'CREATE INDEX IF NOT EXISTS idx_scheduled_tasks_assigned ON scheduled_tasks(assigned_to)',
        # Mesh messages
        'CREATE INDEX IF NOT EXISTS idx_mesh_messages_timestamp ON mesh_messages(timestamp DESC)',
        'CREATE INDEX IF NOT EXISTS idx_mesh_messages_channel ON mesh_messages(channel)',
        # Additional performance indexes
        'CREATE INDEX IF NOT EXISTS idx_activity_log_event ON activity_log(event)',
        'CREATE INDEX IF NOT EXISTS idx_activity_log_service ON activity_log(service, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status)',
        'CREATE INDEX IF NOT EXISTS idx_documents_category ON documents(doc_category)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_name ON inventory(name)',
        'CREATE INDEX IF NOT EXISTS idx_triage_events_status ON triage_events(status)',
        'CREATE INDEX IF NOT EXISTS idx_handoff_patient ON handoff_reports(patient_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_patients_triage ON patients(triage_category)',
        'CREATE INDEX IF NOT EXISTS idx_vault_entries_created ON vault_entries(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_services_state ON services(installed, running)',
        # v5.0 indexes
        'CREATE INDEX IF NOT EXISTS idx_kb_workspaces_name ON kb_workspaces(name)',
        'CREATE INDEX IF NOT EXISTS idx_conversation_branches_conv ON conversation_branches(conversation_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_photos_inv ON inventory_photos(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_checkouts_inv ON inventory_checkouts(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_checkouts_open ON inventory_checkouts(returned_at)',
        'CREATE INDEX IF NOT EXISTS idx_shopping_list_purchased ON shopping_list(purchased)',
        'CREATE INDEX IF NOT EXISTS idx_note_tags_note ON note_tags(note_id)',
        'CREATE INDEX IF NOT EXISTS idx_note_tags_tag ON note_tags(tag)',
        'CREATE INDEX IF NOT EXISTS idx_note_links_source ON note_links(source_note_id)',
        'CREATE INDEX IF NOT EXISTS idx_note_links_target ON note_links(target_note_id)',
        'CREATE INDEX IF NOT EXISTS idx_media_progress_lookup ON media_progress(media_type, media_id)',
        'CREATE INDEX IF NOT EXISTS idx_playlists_type ON playlists(media_type)',
        'CREATE INDEX IF NOT EXISTS idx_drug_interactions_a ON drug_interactions(drug_a)',
        'CREATE INDEX IF NOT EXISTS idx_drug_interactions_b ON drug_interactions(drug_b)',
        'CREATE INDEX IF NOT EXISTS idx_wound_photos_wound ON wound_photos(wound_id)',
        'CREATE INDEX IF NOT EXISTS idx_weather_readings_created ON weather_readings(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_weather_readings_source ON weather_readings(source)',
        'CREATE INDEX IF NOT EXISTS idx_lan_channels_name ON lan_channels(name)',
        'CREATE INDEX IF NOT EXISTS idx_lan_presence_ip ON lan_presence(ip)',
        'CREATE INDEX IF NOT EXISTS idx_lan_transfers_status ON lan_transfers(status)',
        'CREATE INDEX IF NOT EXISTS idx_companion_plants_a ON companion_plants(plant_a)',
        'CREATE INDEX IF NOT EXISTS idx_seed_inventory_species ON seed_inventory(species)',
        'CREATE INDEX IF NOT EXISTS idx_pest_guide_type ON pest_guide(pest_type)',
        'CREATE INDEX IF NOT EXISTS idx_benchmark_results_type ON benchmark_results(test_type)',
        'CREATE INDEX IF NOT EXISTS idx_benchmark_results_created ON benchmark_results(created_at DESC)',
        # Watch schedules
        'CREATE INDEX IF NOT EXISTS idx_watch_schedules_start ON watch_schedules(start_date)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_lot ON inventory(lot_number)',
        'CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id)',
        'CREATE INDEX IF NOT EXISTS idx_notes_journal ON notes(is_journal, created_at DESC)',
        # Weather action rules
        'CREATE INDEX IF NOT EXISTS idx_weather_action_rules_enabled ON weather_action_rules(enabled)',
        'CREATE INDEX IF NOT EXISTS idx_vector_clocks_table ON vector_clocks(table_name)',
        'CREATE INDEX IF NOT EXISTS idx_vector_clocks_hash ON vector_clocks(table_name, row_hash)',
        'CREATE INDEX IF NOT EXISTS idx_dead_drop_created ON dead_drop_messages(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_group_exercises_status ON group_exercises(status)',
        'CREATE INDEX IF NOT EXISTS idx_group_exercises_id ON group_exercises(exercise_id)',
        'CREATE INDEX IF NOT EXISTS idx_training_datasets_status ON training_datasets(status)',
        'CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status)',
        'CREATE INDEX IF NOT EXISTS idx_perimeter_zones_type ON perimeter_zones(zone_type)',
        # UPC barcode database (upc column has UNIQUE constraint which auto-creates index)
        'CREATE INDEX IF NOT EXISTS idx_upc_database_category ON upc_database(category)',
        'CREATE INDEX IF NOT EXISTS idx_shopping_list_inventory_id ON shopping_list(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_conversation_branches_parent ON conversation_branches(conversation_id, parent_message_idx)',
        # Inventory batches
        'CREATE INDEX IF NOT EXISTS idx_inventory_batches_inv ON inventory_batches(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_batches_expiration ON inventory_batches(expiration)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_batches_lot ON inventory_batches(lot_number)',
        # Consumption log
        'CREATE INDEX IF NOT EXISTS idx_consumption_log_inv ON consumption_log(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_consumption_log_consumed ON consumption_log(consumed_at DESC)',
        # Medication log
        'CREATE INDEX IF NOT EXISTS idx_medication_log_patient ON medication_log(patient_id, administered_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_medication_log_drug ON medication_log(drug_name)',
        'CREATE INDEX IF NOT EXISTS idx_medication_log_next_dose ON medication_log(next_dose_due)',
        # Wound updates
        'CREATE INDEX IF NOT EXISTS idx_wound_updates_wound ON wound_updates(wound_id)',
        'CREATE INDEX IF NOT EXISTS idx_wound_updates_patient ON wound_updates(patient_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_wound_updates_status ON wound_updates(status)',
        # Triage history
        'CREATE INDEX IF NOT EXISTS idx_triage_history_patient ON triage_history(patient_id, created_at DESC)',
        # GPS tracks
        'CREATE INDEX IF NOT EXISTS idx_gps_tracks_created ON gps_tracks(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_gps_tracks_started ON gps_tracks(started_at DESC)',
        # Generators
        'CREATE INDEX IF NOT EXISTS idx_generators_fuel_type ON generators(fuel_type)',
        # Generator sessions
        'CREATE INDEX IF NOT EXISTS idx_generator_sessions_gen ON generator_sessions(generator_id)',
        'CREATE INDEX IF NOT EXISTS idx_generator_sessions_started ON generator_sessions(started_at DESC)',
        # Motion events
        'CREATE INDEX IF NOT EXISTS idx_motion_events_camera ON motion_events(camera_id, created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_motion_events_created ON motion_events(created_at DESC)',
        # Download queue
        'CREATE INDEX IF NOT EXISTS idx_download_queue_status ON download_queue(status)',
        'CREATE INDEX IF NOT EXISTS idx_download_queue_created ON download_queue(created_at DESC)',
        # Task completions
        'CREATE INDEX IF NOT EXISTS idx_task_completions_task ON task_completions(task_id)',
        'CREATE INDEX IF NOT EXISTS idx_task_completions_completed ON task_completions(completed_at DESC)',
        # Comms schedules
        'CREATE INDEX IF NOT EXISTS idx_comms_schedules_active ON comms_schedules(active)',
        'CREATE INDEX IF NOT EXISTS idx_comms_schedules_priority ON comms_schedules(priority)',
        # Water log
        'CREATE INDEX IF NOT EXISTS idx_water_log_plot ON water_log(plot_id)',
        'CREATE INDEX IF NOT EXISTS idx_water_log_date ON water_log(date DESC)',
        # Storm events
        'CREATE INDEX IF NOT EXISTS idx_storm_events_started ON storm_events(started_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_storm_events_type ON storm_events(storm_type)',
        # Note revisions
        'CREATE INDEX IF NOT EXISTS idx_note_revisions_note ON note_revisions(note_id, created_at DESC)',
        # Skill progression
        'CREATE INDEX IF NOT EXISTS idx_skill_progression_tag ON skill_progression(skill_tag)',
        'CREATE INDEX IF NOT EXISTS idx_skill_progression_recorded ON skill_progression(recorded_at DESC)',
        # ── Missing foreign key indexes ──
        'CREATE INDEX IF NOT EXISTS idx_training_jobs_dataset ON training_jobs(dataset_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_transactions_offer ON federation_transactions(offer_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_transactions_request ON federation_transactions(request_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_transactions_from_node ON federation_transactions(from_node_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_transactions_to_node ON federation_transactions(to_node_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_offers_node ON federation_offers(node_id)',
        'CREATE INDEX IF NOT EXISTS idx_federation_requests_node ON federation_requests(node_id)',
        'CREATE INDEX IF NOT EXISTS idx_mutual_aid_agreements_peer ON mutual_aid_agreements(peer_node_id)',
        'CREATE INDEX IF NOT EXISTS idx_dead_drop_from_node ON dead_drop_messages(from_node_id)',
        'CREATE INDEX IF NOT EXISTS idx_dead_drop_recipient ON dead_drop_messages(recipient)',
        'CREATE INDEX IF NOT EXISTS idx_sync_log_peer_node ON sync_log(peer_node_id)',
        # ── Missing category / status / type filter indexes ──
        'CREATE INDEX IF NOT EXISTS idx_services_category ON services(category)',
        'CREATE INDEX IF NOT EXISTS idx_sensor_devices_status ON sensor_devices(status)',
        'CREATE INDEX IF NOT EXISTS idx_sensor_devices_type ON sensor_devices(device_type)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_log_method ON preservation_log(method)',
        'CREATE INDEX IF NOT EXISTS idx_federation_offers_item_type ON federation_offers(item_type)',
        'CREATE INDEX IF NOT EXISTS idx_federation_requests_item_type ON federation_requests(item_type)',
        'CREATE INDEX IF NOT EXISTS idx_federation_requests_urgency ON federation_requests(urgency)',
        'CREATE INDEX IF NOT EXISTS idx_federation_transactions_status ON federation_transactions(status)',
        'CREATE INDEX IF NOT EXISTS idx_mutual_aid_agreements_status ON mutual_aid_agreements(status)',
        'CREATE INDEX IF NOT EXISTS idx_livestock_status ON livestock(status)',
        'CREATE INDEX IF NOT EXISTS idx_scenarios_type ON scenarios(scenario_type)',
        'CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)',
        'CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type)',
        'CREATE INDEX IF NOT EXISTS idx_subscriptions_category ON subscriptions(category)',
        'CREATE INDEX IF NOT EXISTS idx_equipment_category ON equipment_log(category)',
        'CREATE INDEX IF NOT EXISTS idx_drill_history_type ON drill_history(drill_type)',
        'CREATE INDEX IF NOT EXISTS idx_comms_log_direction ON comms_log(direction)',
        'CREATE INDEX IF NOT EXISTS idx_lan_messages_type ON lan_messages(msg_type)',
        'CREATE INDEX IF NOT EXISTS idx_access_log_direction ON access_log(direction)',
        'CREATE INDEX IF NOT EXISTS idx_sync_log_status ON sync_log(status)',
        'CREATE INDEX IF NOT EXISTS idx_sync_log_direction ON sync_log(direction)',
        'CREATE INDEX IF NOT EXISTS idx_perimeter_zones_threat ON perimeter_zones(threat_level)',
        # ── Missing created_at / updated_at ordering indexes ──
        'CREATE INDEX IF NOT EXISTS idx_contacts_created ON contacts(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_created ON inventory(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_notes_created ON notes(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_checklists_updated ON checklists(updated_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_books_created ON books(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_patients_created ON patients(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_log_created ON preservation_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_federation_transactions_created ON federation_transactions(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_mutual_aid_agreements_created ON mutual_aid_agreements(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_training_datasets_created ON training_datasets(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_training_jobs_created ON training_jobs(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_livestock_created ON livestock(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_scenarios_started ON scenarios(started_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_ammo_created ON ammo_inventory(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_community_created ON community_resources(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_equipment_created ON equipment_log(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_fuel_created ON fuel_storage(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_lan_transfers_created ON lan_transfers(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_perimeter_zones_created ON perimeter_zones(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_triage_events_created ON triage_events(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_group_exercises_created ON group_exercises(created_at DESC)',
        # v7.8.0 — Water management
        'CREATE INDEX IF NOT EXISTS idx_water_storage_location ON water_storage(location)',
        'CREATE INDEX IF NOT EXISTS idx_water_storage_expiration ON water_storage(expiration)',
        'CREATE INDEX IF NOT EXISTS idx_water_filters_status ON water_filters(status)',
        'CREATE INDEX IF NOT EXISTS idx_water_sources_type ON water_sources(source_type)',
        'CREATE INDEX IF NOT EXISTS idx_water_quality_source ON water_quality_tests(source_id)',
        'CREATE INDEX IF NOT EXISTS idx_water_quality_date ON water_quality_tests(test_date DESC)',
        # v7.8.0 — Financial preparedness
        'CREATE INDEX IF NOT EXISTS idx_financial_cash_location ON financial_cash(location)',
        'CREATE INDEX IF NOT EXISTS idx_financial_metals_type ON financial_metals(metal_type)',
        'CREATE INDEX IF NOT EXISTS idx_financial_barter_category ON financial_barter(category)',
        'CREATE INDEX IF NOT EXISTS idx_financial_documents_type ON financial_documents(doc_type)',
        'CREATE INDEX IF NOT EXISTS idx_financial_documents_expiration ON financial_documents(expiration)',
        # v7.8.0 — Vehicles
        'CREATE INDEX IF NOT EXISTS idx_vehicles_role ON vehicles(role)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_maintenance_vehicle ON vehicle_maintenance(vehicle_id)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_maintenance_status ON vehicle_maintenance(status)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_maintenance_next_due ON vehicle_maintenance(next_due_date)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_fuel_log_vehicle ON vehicle_fuel_log(vehicle_id)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_fuel_log_date ON vehicle_fuel_log(fuel_date DESC)',
        # v7.8.0 — Loadout bags
        'CREATE INDEX IF NOT EXISTS idx_loadout_bags_type ON loadout_bags(bag_type)',
        'CREATE INDEX IF NOT EXISTS idx_loadout_bags_owner ON loadout_bags(owner)',
        'CREATE INDEX IF NOT EXISTS idx_loadout_items_bag ON loadout_items(bag_id)',
        'CREATE INDEX IF NOT EXISTS idx_loadout_items_category ON loadout_items(category)',
        'CREATE INDEX IF NOT EXISTS idx_loadout_items_packed ON loadout_items(packed)',
        'CREATE INDEX IF NOT EXISTS idx_loadout_items_expiration ON loadout_items(expiration)',
        # v7.9.0 — PACE plans
        'CREATE INDEX IF NOT EXISTS idx_pace_plans_active ON pace_plans(is_active)',
        # v7.9.0 — Evacuation planning
        'CREATE INDEX IF NOT EXISTS idx_evac_plans_active ON evac_plans(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_evac_plans_type ON evac_plans(plan_type)',
        'CREATE INDEX IF NOT EXISTS idx_rally_points_plan ON rally_points(evac_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_rally_points_sequence ON rally_points(evac_plan_id, sequence_order)',
        'CREATE INDEX IF NOT EXISTS idx_evac_assignments_plan ON evac_assignments(evac_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_evac_assignments_role ON evac_assignments(role)',
        # v7.9.0 — Inventory containers
        'CREATE INDEX IF NOT EXISTS idx_inventory_containers_type ON inventory_containers(container_type)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_containers_parent ON inventory_containers(parent_container_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_container_id ON inventory(container_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_weight ON inventory(weight_oz)',
        # v7.9.0 — Preservation expansion
        'CREATE INDEX IF NOT EXISTS idx_preservation_log_success ON preservation_log(success)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_log_storage ON preservation_log(storage_location)',
        # v7.10.0 — Readiness goals
        'CREATE INDEX IF NOT EXISTS idx_readiness_goals_category ON readiness_goals(category)',
        'CREATE INDEX IF NOT EXISTS idx_readiness_goals_priority ON readiness_goals(priority)',
        'CREATE INDEX IF NOT EXISTS idx_readiness_goals_source ON readiness_goals(metric_source)',
        # v7.10.0 — Alert rules engine
        'CREATE INDEX IF NOT EXISTS idx_alert_rules_enabled ON alert_rules(enabled)',
        'CREATE INDEX IF NOT EXISTS idx_alert_rules_condition ON alert_rules(condition_type)',
        'CREATE INDEX IF NOT EXISTS idx_alert_rules_severity ON alert_rules(severity)',
        'CREATE INDEX IF NOT EXISTS idx_alert_rule_triggers_rule ON alert_rule_triggers(rule_id)',
        'CREATE INDEX IF NOT EXISTS idx_alert_rule_triggers_at ON alert_rule_triggers(triggered_at DESC)',
        # v7.10.0 — Threat intelligence
        'CREATE INDEX IF NOT EXISTS idx_threat_feeds_enabled ON threat_feeds(enabled)',
        'CREATE INDEX IF NOT EXISTS idx_threat_feeds_category ON threat_feeds(category)',
        'CREATE INDEX IF NOT EXISTS idx_threat_entries_feed ON threat_entries(feed_id)',
        'CREATE INDEX IF NOT EXISTS idx_threat_entries_category ON threat_entries(category)',
        'CREATE INDEX IF NOT EXISTS idx_threat_entries_severity ON threat_entries(severity_score DESC)',
        'CREATE INDEX IF NOT EXISTS idx_threat_entries_resolved ON threat_entries(resolved)',
        'CREATE INDEX IF NOT EXISTS idx_threat_entries_created ON threat_entries(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_threat_entries_geo ON threat_entries(lat, lng)',
        # v7.10.0 — Evacuation drills
        'CREATE INDEX IF NOT EXISTS idx_evac_drill_runs_plan ON evac_drill_runs(evac_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_evac_drill_runs_status ON evac_drill_runs(status)',
        'CREATE INDEX IF NOT EXISTS idx_evac_drill_runs_started ON evac_drill_runs(started_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_evac_drill_laps_run ON evac_drill_laps(drill_run_id)',
        'CREATE INDEX IF NOT EXISTS idx_evac_drill_laps_number ON evac_drill_laps(drill_run_id, lap_number)',
        # v7.11.0 — Data Foundation & Localization (Phase 1)
        'CREATE INDEX IF NOT EXISTS idx_regional_profile_active ON regional_profile(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_regional_profile_zip ON regional_profile(zip_code)',
        'CREATE INDEX IF NOT EXISTS idx_data_packs_pack_id ON data_packs(pack_id)',
        'CREATE INDEX IF NOT EXISTS idx_data_packs_status ON data_packs(status)',
        'CREATE INDEX IF NOT EXISTS idx_data_packs_tier ON data_packs(tier)',
        'CREATE INDEX IF NOT EXISTS idx_nutrition_foods_fdc_id ON nutrition_foods(fdc_id)',
        'CREATE INDEX IF NOT EXISTS idx_nutrition_foods_description ON nutrition_foods(description)',
        'CREATE INDEX IF NOT EXISTS idx_nutrition_foods_group ON nutrition_foods(food_group)',
        'CREATE INDEX IF NOT EXISTS idx_nutrition_nutrients_fdc_id ON nutrition_nutrients(fdc_id)',
        'CREATE INDEX IF NOT EXISTS idx_nutrition_nutrients_name ON nutrition_nutrients(nutrient_name)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_nutrition_link_inv ON inventory_nutrition_link(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_nutrition_link_fdc ON inventory_nutrition_link(fdc_id)',
        'CREATE INDEX IF NOT EXISTS idx_fema_nri_county ON fema_nri_counties(state_fips, county_fips)',
        'CREATE INDEX IF NOT EXISTS idx_fema_nri_state ON fema_nri_counties(state_name)',
        'CREATE INDEX IF NOT EXISTS idx_fema_nri_risk ON fema_nri_counties(risk_score DESC)',
        # v7.12.0 — Consumption profiles & water budget
        'CREATE INDEX IF NOT EXISTS idx_consumption_profiles_type ON consumption_profiles(profile_type)',
        'CREATE INDEX IF NOT EXISTS idx_water_budget_category ON water_budget(category)',
        'CREATE INDEX IF NOT EXISTS idx_water_budget_enabled ON water_budget(enabled)',
        # v7.13.0 — Meal planning & inventory intelligence
        'CREATE INDEX IF NOT EXISTS idx_recipes_category ON recipes(category)',
        'CREATE INDEX IF NOT EXISTS idx_recipes_created ON recipes(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe ON recipe_ingredients(recipe_id)',
        'CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_inv ON recipe_ingredients(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_substitutes_inv ON inventory_substitutes(inventory_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_substitutes_sub ON inventory_substitutes(substitute_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_audits_status ON inventory_audits(status)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_audit_items_audit ON inventory_audit_items(audit_id)',
        'CREATE INDEX IF NOT EXISTS idx_inventory_audit_items_inv ON inventory_audit_items(inventory_id)',
        # v7.14.0 — Movement & Route Planning (Phase 5)
        'CREATE INDEX IF NOT EXISTS idx_movement_plans_type ON movement_plans(plan_type)',
        'CREATE INDEX IF NOT EXISTS idx_movement_plans_status ON movement_plans(status)',
        'CREATE INDEX IF NOT EXISTS idx_movement_plans_evac ON movement_plans(evac_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_alt_vehicles_type ON alt_vehicles(vehicle_type)',
        'CREATE INDEX IF NOT EXISTS idx_alt_vehicles_condition ON alt_vehicles(condition)',
        'CREATE INDEX IF NOT EXISTS idx_route_hazards_plan ON route_hazards(movement_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_route_hazards_type ON route_hazards(hazard_type)',
        'CREATE INDEX IF NOT EXISTS idx_route_hazards_severity ON route_hazards(severity)',
        'CREATE INDEX IF NOT EXISTS idx_route_recon_plan ON route_recon(movement_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_route_recon_date ON route_recon(recon_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_loading_evac ON vehicle_loading_plans(evac_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_vehicle_loading_vehicle ON vehicle_loading_plans(vehicle_id)',
        'CREATE INDEX IF NOT EXISTS idx_go_nogo_evac ON go_nogo_matrix(evac_plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_go_nogo_status ON go_nogo_matrix(current_status)',
        # v7.14.0 — Tactical Communications (Phase 6)
        'CREATE INDEX IF NOT EXISTS idx_radio_equipment_type ON radio_equipment(radio_type)',
        'CREATE INDEX IF NOT EXISTS idx_radio_equipment_assigned ON radio_equipment(assigned_to)',
        'CREATE INDEX IF NOT EXISTS idx_radio_equipment_condition ON radio_equipment(condition)',
        'CREATE INDEX IF NOT EXISTS idx_auth_codes_date ON auth_codes(valid_date)',
        'CREATE INDEX IF NOT EXISTS idx_auth_codes_active ON auth_codes(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_auth_codes_set ON auth_codes(code_set_name)',
        'CREATE INDEX IF NOT EXISTS idx_net_schedules_active ON net_schedules(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_net_schedules_type ON net_schedules(net_type)',
        'CREATE INDEX IF NOT EXISTS idx_comms_checks_schedule ON comms_checks(net_schedule_id)',
        'CREATE INDEX IF NOT EXISTS idx_comms_checks_date ON comms_checks(check_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_message_templates_type ON message_templates(template_type)',
        'CREATE INDEX IF NOT EXISTS idx_message_templates_builtin ON message_templates(is_builtin)',
        'CREATE INDEX IF NOT EXISTS idx_sent_messages_template ON sent_messages(template_id)',
        'CREATE INDEX IF NOT EXISTS idx_sent_messages_type ON sent_messages(template_type)',
        'CREATE INDEX IF NOT EXISTS idx_sent_messages_sent ON sent_messages(sent_at DESC)',
        # v7.15.0 — Land Assessment & Property (Phase 8)
        'CREATE INDEX IF NOT EXISTS idx_properties_type ON properties(property_type)',
        'CREATE INDEX IF NOT EXISTS idx_properties_status ON properties(status)',
        'CREATE INDEX IF NOT EXISTS idx_properties_state ON properties(state)',
        'CREATE INDEX IF NOT EXISTS idx_properties_score ON properties(total_score DESC)',
        'CREATE INDEX IF NOT EXISTS idx_property_assessments_prop ON property_assessments(property_id)',
        'CREATE INDEX IF NOT EXISTS idx_property_assessments_cat ON property_assessments(category)',
        'CREATE INDEX IF NOT EXISTS idx_property_features_prop ON property_features(property_id)',
        'CREATE INDEX IF NOT EXISTS idx_property_features_type ON property_features(feature_type)',
        'CREATE INDEX IF NOT EXISTS idx_development_plans_prop ON development_plans(property_id)',
        'CREATE INDEX IF NOT EXISTS idx_development_plans_status ON development_plans(status)',
        'CREATE INDEX IF NOT EXISTS idx_development_plans_priority ON development_plans(priority)',
        # v7.15.0 — Medical Phase 2 (Phase 9)
        'CREATE INDEX IF NOT EXISTS idx_pregnancies_status ON pregnancies(status)',
        'CREATE INDEX IF NOT EXISTS idx_pregnancies_due ON pregnancies(due_date)',
        'CREATE INDEX IF NOT EXISTS idx_dental_records_patient ON dental_records(patient_name)',
        'CREATE INDEX IF NOT EXISTS idx_dental_records_tooth ON dental_records(tooth_number)',
        'CREATE INDEX IF NOT EXISTS idx_herbal_remedies_name ON herbal_remedies(name)',
        'CREATE INDEX IF NOT EXISTS idx_herbal_remedies_builtin ON herbal_remedies(is_builtin)',
        'CREATE INDEX IF NOT EXISTS idx_chronic_conditions_patient ON chronic_conditions(patient_name)',
        'CREATE INDEX IF NOT EXISTS idx_chronic_conditions_status ON chronic_conditions(status)',
        'CREATE INDEX IF NOT EXISTS idx_chronic_conditions_stockpile ON chronic_conditions(medication_stockpile_days)',
        'CREATE INDEX IF NOT EXISTS idx_vaccinations_patient ON vaccinations(patient_name)',
        'CREATE INDEX IF NOT EXISTS idx_vaccinations_next_due ON vaccinations(next_due)',
        'CREATE INDEX IF NOT EXISTS idx_mental_health_patient ON mental_health_logs(patient_name)',
        'CREATE INDEX IF NOT EXISTS idx_mental_health_date ON mental_health_logs(check_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_mental_health_mood ON mental_health_logs(mood_score)',
        'CREATE INDEX IF NOT EXISTS idx_vet_records_animal ON vet_records(animal_name)',
        'CREATE INDEX IF NOT EXISTS idx_vet_records_species ON vet_records(species)',
        'CREATE INDEX IF NOT EXISTS idx_vet_records_next_due ON vet_records(next_due)',
        # v7.16.0 — Training & Knowledge (Phase 10)
        'CREATE INDEX IF NOT EXISTS idx_skill_trees_person ON skill_trees(person_name)',
        'CREATE INDEX IF NOT EXISTS idx_skill_trees_category ON skill_trees(category)',
        'CREATE INDEX IF NOT EXISTS idx_skill_trees_level ON skill_trees(level)',
        'CREATE INDEX IF NOT EXISTS idx_skill_trees_certified ON skill_trees(certified)',
        'CREATE INDEX IF NOT EXISTS idx_skill_trees_person_cat ON skill_trees(person_name, category)',
        'CREATE INDEX IF NOT EXISTS idx_training_courses_status ON training_courses(status)',
        'CREATE INDEX IF NOT EXISTS idx_training_courses_category ON training_courses(category)',
        'CREATE INDEX IF NOT EXISTS idx_training_courses_difficulty ON training_courses(difficulty)',
        'CREATE INDEX IF NOT EXISTS idx_training_courses_created ON training_courses(created_at DESC)',
        'CREATE INDEX IF NOT EXISTS idx_training_lessons_course ON training_lessons(course_id)',
        'CREATE INDEX IF NOT EXISTS idx_training_lessons_number ON training_lessons(course_id, lesson_number)',
        'CREATE INDEX IF NOT EXISTS idx_training_lessons_type ON training_lessons(lesson_type)',
        'CREATE INDEX IF NOT EXISTS idx_certifications_person ON certifications(person_name)',
        'CREATE INDEX IF NOT EXISTS idx_certifications_status ON certifications(status)',
        'CREATE INDEX IF NOT EXISTS idx_certifications_expiration ON certifications(expiration_date)',
        'CREATE INDEX IF NOT EXISTS idx_certifications_name ON certifications(certification_name)',
        'CREATE INDEX IF NOT EXISTS idx_drill_templates_type ON drill_templates(drill_type)',
        'CREATE INDEX IF NOT EXISTS idx_drill_templates_builtin ON drill_templates(is_builtin)',
        'CREATE INDEX IF NOT EXISTS idx_drill_results_template ON drill_results(template_id)',
        'CREATE INDEX IF NOT EXISTS idx_drill_results_date ON drill_results(drill_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_drill_results_grade ON drill_results(overall_grade)',
        'CREATE INDEX IF NOT EXISTS idx_flashcards_deck ON flashcards(deck_name)',
        'CREATE INDEX IF NOT EXISTS idx_flashcards_category ON flashcards(category)',
        'CREATE INDEX IF NOT EXISTS idx_flashcards_next_review ON flashcards(next_review)',
        'CREATE INDEX IF NOT EXISTS idx_flashcards_deck_cat ON flashcards(deck_name, category)',
        'CREATE INDEX IF NOT EXISTS idx_flashcards_ease ON flashcards(ease_factor)',
        'CREATE INDEX IF NOT EXISTS idx_knowledge_packages_person ON knowledge_packages(person_name)',
        'CREATE INDEX IF NOT EXISTS idx_knowledge_packages_status ON knowledge_packages(status)',
        'CREATE INDEX IF NOT EXISTS idx_knowledge_packages_category ON knowledge_packages(category)',
        'CREATE INDEX IF NOT EXISTS idx_knowledge_packages_reviewed ON knowledge_packages(last_reviewed)',
        # v7.17.0 — Group Operations & Governance (Phase 11)
        'CREATE INDEX IF NOT EXISTS idx_pods_status ON pods(status)',
        'CREATE INDEX IF NOT EXISTS idx_pods_leader ON pods(leader_contact_id)',
        'CREATE INDEX IF NOT EXISTS idx_pod_members_pod ON pod_members(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_pod_members_person ON pod_members(person_name)',
        'CREATE INDEX IF NOT EXISTS idx_pod_members_role ON pod_members(role)',
        'CREATE INDEX IF NOT EXISTS idx_pod_members_status ON pod_members(status)',
        'CREATE INDEX IF NOT EXISTS idx_governance_roles_pod ON governance_roles(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_governance_roles_authority ON governance_roles(authority_level DESC)',
        'CREATE INDEX IF NOT EXISTS idx_governance_roles_status ON governance_roles(status)',
        'CREATE INDEX IF NOT EXISTS idx_governance_sops_pod ON governance_sops(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_governance_sops_category ON governance_sops(category)',
        'CREATE INDEX IF NOT EXISTS idx_governance_sops_status ON governance_sops(status)',
        'CREATE INDEX IF NOT EXISTS idx_duty_roster_pod ON duty_roster(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_duty_roster_person ON duty_roster(person_name)',
        'CREATE INDEX IF NOT EXISTS idx_duty_roster_type ON duty_roster(duty_type)',
        'CREATE INDEX IF NOT EXISTS idx_duty_roster_status ON duty_roster(status)',
        'CREATE INDEX IF NOT EXISTS idx_duty_roster_start ON duty_roster(shift_start)',
        'CREATE INDEX IF NOT EXISTS idx_disputes_pod ON disputes(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_disputes_status ON disputes(status)',
        'CREATE INDEX IF NOT EXISTS idx_disputes_severity ON disputes(severity)',
        'CREATE INDEX IF NOT EXISTS idx_disputes_type ON disputes(dispute_type)',
        'CREATE INDEX IF NOT EXISTS idx_votes_dispute ON votes(dispute_id)',
        'CREATE INDEX IF NOT EXISTS idx_votes_status ON votes(status)',
        'CREATE INDEX IF NOT EXISTS idx_ics_forms_pod ON ics_forms(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_ics_forms_type ON ics_forms(form_type)',
        'CREATE INDEX IF NOT EXISTS idx_ics_forms_status ON ics_forms(status)',
        'CREATE INDEX IF NOT EXISTS idx_cert_teams_pod ON cert_teams(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_cert_teams_type ON cert_teams(team_type)',
        'CREATE INDEX IF NOT EXISTS idx_cert_teams_status ON cert_teams(status)',
        'CREATE INDEX IF NOT EXISTS idx_damage_assessments_pod ON damage_assessments(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_damage_assessments_team ON damage_assessments(cert_team_id)',
        'CREATE INDEX IF NOT EXISTS idx_damage_assessments_severity ON damage_assessments(severity)',
        'CREATE INDEX IF NOT EXISTS idx_damage_assessments_date ON damage_assessments(assessment_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_shelters_pod ON shelters(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_shelters_status ON shelters(status)',
        'CREATE INDEX IF NOT EXISTS idx_shelters_type ON shelters(shelter_type)',
        'CREATE INDEX IF NOT EXISTS idx_community_warnings_pod ON community_warnings(pod_id)',
        'CREATE INDEX IF NOT EXISTS idx_community_warnings_status ON community_warnings(status)',
        'CREATE INDEX IF NOT EXISTS idx_community_warnings_severity ON community_warnings(severity)',
        'CREATE INDEX IF NOT EXISTS idx_community_warnings_issued ON community_warnings(issued_at DESC)',
        # v7.18.0 — Security, OPSEC & Night Operations (Phase 12)
        'CREATE INDEX IF NOT EXISTS idx_opsec_compartments_classification ON opsec_compartments(classification)',
        'CREATE INDEX IF NOT EXISTS idx_opsec_compartments_status ON opsec_compartments(status)',
        'CREATE INDEX IF NOT EXISTS idx_opsec_checklists_category ON opsec_checklists(category)',
        'CREATE INDEX IF NOT EXISTS idx_opsec_checklists_compartment ON opsec_checklists(compartment_id)',
        'CREATE INDEX IF NOT EXISTS idx_opsec_checklists_status ON opsec_checklists(status)',
        'CREATE INDEX IF NOT EXISTS idx_opsec_checklists_score ON opsec_checklists(score)',
        'CREATE INDEX IF NOT EXISTS idx_threat_matrix_type ON threat_matrix(threat_type)',
        'CREATE INDEX IF NOT EXISTS idx_threat_matrix_risk ON threat_matrix(risk_score DESC)',
        'CREATE INDEX IF NOT EXISTS idx_threat_matrix_status ON threat_matrix(status)',
        'CREATE INDEX IF NOT EXISTS idx_threat_matrix_assigned ON threat_matrix(assigned_to)',
        'CREATE INDEX IF NOT EXISTS idx_observation_posts_type ON observation_posts(type)',
        'CREATE INDEX IF NOT EXISTS idx_observation_posts_status ON observation_posts(status)',
        'CREATE INDEX IF NOT EXISTS idx_op_log_entries_post ON op_log_entries(post_id)',
        'CREATE INDEX IF NOT EXISTS idx_op_log_entries_category ON op_log_entries(category)',
        'CREATE INDEX IF NOT EXISTS idx_op_log_entries_time ON op_log_entries(entry_time DESC)',
        'CREATE INDEX IF NOT EXISTS idx_op_log_entries_threat ON op_log_entries(threat_level)',
        'CREATE INDEX IF NOT EXISTS idx_signature_assessments_status ON signature_assessments(status)',
        'CREATE INDEX IF NOT EXISTS idx_signature_assessments_score ON signature_assessments(overall_score)',
        'CREATE INDEX IF NOT EXISTS idx_signature_assessments_date ON signature_assessments(assessment_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_night_ops_plans_status ON night_ops_plans(status)',
        'CREATE INDEX IF NOT EXISTS idx_night_ops_plans_date ON night_ops_plans(operation_date)',
        'CREATE INDEX IF NOT EXISTS idx_cbrn_equipment_type ON cbrn_equipment(equipment_type)',
        'CREATE INDEX IF NOT EXISTS idx_cbrn_equipment_condition ON cbrn_equipment(condition)',
        'CREATE INDEX IF NOT EXISTS idx_cbrn_equipment_cal_due ON cbrn_equipment(calibration_due)',
        'CREATE INDEX IF NOT EXISTS idx_cbrn_procedures_type ON cbrn_procedures(procedure_type)',
        'CREATE INDEX IF NOT EXISTS idx_cbrn_procedures_agent ON cbrn_procedures(threat_agent)',
        'CREATE INDEX IF NOT EXISTS idx_cbrn_procedures_builtin ON cbrn_procedures(is_builtin)',
        'CREATE INDEX IF NOT EXISTS idx_emp_inventory_category ON emp_inventory(category)',
        'CREATE INDEX IF NOT EXISTS idx_emp_inventory_protected ON emp_inventory(is_protected)',
        'CREATE INDEX IF NOT EXISTS idx_emp_inventory_priority ON emp_inventory(priority)',
        'CREATE INDEX IF NOT EXISTS idx_emp_inventory_grid ON emp_inventory(grid_dependent)',
        # v7.19.0 — Agriculture & Permaculture (Phase 13)
        'CREATE INDEX IF NOT EXISTS idx_food_forest_guilds_central ON food_forest_guilds(central_species)',
        'CREATE INDEX IF NOT EXISTS idx_food_forest_layers_guild ON food_forest_layers(guild_id)',
        'CREATE INDEX IF NOT EXISTS idx_food_forest_layers_type ON food_forest_layers(layer_type)',
        'CREATE INDEX IF NOT EXISTS idx_food_forest_layers_species ON food_forest_layers(species)',
        'CREATE INDEX IF NOT EXISTS idx_soil_projects_type ON soil_projects(project_type)',
        'CREATE INDEX IF NOT EXISTS idx_soil_projects_status ON soil_projects(status)',
        'CREATE INDEX IF NOT EXISTS idx_perennial_plants_type ON perennial_plants(plant_type)',
        'CREATE INDEX IF NOT EXISTS idx_perennial_plants_health ON perennial_plants(health_status)',
        'CREATE INDEX IF NOT EXISTS idx_perennial_plants_species ON perennial_plants(species)',
        'CREATE INDEX IF NOT EXISTS idx_multi_year_plans_status ON multi_year_plans(status)',
        'CREATE INDEX IF NOT EXISTS idx_multi_year_plans_years ON multi_year_plans(start_year, end_year)',
        'CREATE INDEX IF NOT EXISTS idx_breeding_records_species ON breeding_records(species)',
        'CREATE INDEX IF NOT EXISTS idx_breeding_records_status ON breeding_records(status)',
        'CREATE INDEX IF NOT EXISTS idx_breeding_records_due ON breeding_records(expected_due)',
        'CREATE INDEX IF NOT EXISTS idx_feed_tracking_group ON feed_tracking(animal_group)',
        'CREATE INDEX IF NOT EXISTS idx_feed_tracking_date ON feed_tracking(fed_date DESC)',
        'CREATE INDEX IF NOT EXISTS idx_homestead_systems_type ON homestead_systems(system_type)',
        'CREATE INDEX IF NOT EXISTS idx_homestead_systems_condition ON homestead_systems(condition)',
        'CREATE INDEX IF NOT EXISTS idx_homestead_systems_next_maint ON homestead_systems(next_maintenance)',
        'CREATE INDEX IF NOT EXISTS idx_aquaponics_systems_type ON aquaponics_systems(system_type)',
        'CREATE INDEX IF NOT EXISTS idx_aquaponics_systems_status ON aquaponics_systems(status)',
        'CREATE INDEX IF NOT EXISTS idx_recycling_systems_type ON recycling_systems(system_type)',
        'CREATE INDEX IF NOT EXISTS idx_recycling_systems_status ON recycling_systems(current_status)',
        # ─── Phase 14: Disaster-Specific Modules (v7.20.0) ───
        'CREATE INDEX IF NOT EXISTS idx_disaster_plans_type ON disaster_plans(disaster_type)',
        'CREATE INDEX IF NOT EXISTS idx_disaster_plans_status ON disaster_plans(status)',
        'CREATE INDEX IF NOT EXISTS idx_disaster_plans_env ON disaster_plans(environment_type)',
        'CREATE INDEX IF NOT EXISTS idx_disaster_checklists_plan ON disaster_checklists(plan_id)',
        'CREATE INDEX IF NOT EXISTS idx_disaster_checklists_category ON disaster_checklists(category)',
        'CREATE INDEX IF NOT EXISTS idx_disaster_checklists_status ON disaster_checklists(status)',
        'CREATE INDEX IF NOT EXISTS idx_energy_systems_type ON energy_systems(energy_type)',
        'CREATE INDEX IF NOT EXISTS idx_energy_systems_condition ON energy_systems(condition)',
        'CREATE INDEX IF NOT EXISTS idx_construction_projects_type ON construction_projects(project_type)',
        'CREATE INDEX IF NOT EXISTS idx_construction_projects_status ON construction_projects(status)',
        'CREATE INDEX IF NOT EXISTS idx_construction_projects_priority ON construction_projects(priority)',
        'CREATE INDEX IF NOT EXISTS idx_building_materials_category ON building_materials(category)',
        'CREATE INDEX IF NOT EXISTS idx_building_materials_location ON building_materials(location)',
        'CREATE INDEX IF NOT EXISTS idx_fortifications_type ON fortifications(fortification_type)',
        'CREATE INDEX IF NOT EXISTS idx_fortifications_status ON fortifications(status)',
        'CREATE INDEX IF NOT EXISTS idx_fortifications_condition ON fortifications(condition)',
        # ─── Phase 15: Daily Living & Quality of Life (v7.21.0) ───
        'CREATE INDEX IF NOT EXISTS idx_daily_schedules_type ON daily_schedules(schedule_type)',
        'CREATE INDEX IF NOT EXISTS idx_daily_schedules_status ON daily_schedules(status)',
        'CREATE INDEX IF NOT EXISTS idx_daily_schedules_template ON daily_schedules(is_template)',
        'CREATE INDEX IF NOT EXISTS idx_chore_assignments_schedule ON chore_assignments(schedule_id)',
        'CREATE INDEX IF NOT EXISTS idx_chore_assignments_assigned ON chore_assignments(assigned_to)',
        'CREATE INDEX IF NOT EXISTS idx_chore_assignments_category ON chore_assignments(category)',
        'CREATE INDEX IF NOT EXISTS idx_chore_assignments_status ON chore_assignments(status)',
        'CREATE INDEX IF NOT EXISTS idx_clothing_inventory_person ON clothing_inventory(person)',
        'CREATE INDEX IF NOT EXISTS idx_clothing_inventory_category ON clothing_inventory(category)',
        'CREATE INDEX IF NOT EXISTS idx_clothing_inventory_season ON clothing_inventory(season)',
        'CREATE INDEX IF NOT EXISTS idx_sanitation_supplies_category ON sanitation_supplies(category)',
        'CREATE INDEX IF NOT EXISTS idx_sanitation_supplies_expiry ON sanitation_supplies(expiration_date)',
        'CREATE INDEX IF NOT EXISTS idx_morale_logs_person ON morale_logs(person)',
        'CREATE INDEX IF NOT EXISTS idx_morale_logs_date ON morale_logs(date)',
        'CREATE INDEX IF NOT EXISTS idx_sleep_logs_person ON sleep_logs(person)',
        'CREATE INDEX IF NOT EXISTS idx_sleep_logs_date ON sleep_logs(date)',
        'CREATE INDEX IF NOT EXISTS idx_performance_checks_person ON performance_checks(person)',
        'CREATE INDEX IF NOT EXISTS idx_performance_checks_date ON performance_checks(date)',
        'CREATE INDEX IF NOT EXISTS idx_performance_checks_risk ON performance_checks(risk_assessment)',
        'CREATE INDEX IF NOT EXISTS idx_grid_down_recipes_category ON grid_down_recipes(category)',
        'CREATE INDEX IF NOT EXISTS idx_grid_down_recipes_method ON grid_down_recipes(cooking_method)',
        'CREATE INDEX IF NOT EXISTS idx_grid_down_recipes_rating ON grid_down_recipes(rating)',
        # ─── Phase 16: Interoperability & Data Exchange (v7.22.0) ───
        'CREATE INDEX IF NOT EXISTS idx_data_exports_type ON data_exports(export_type)',
        'CREATE INDEX IF NOT EXISTS idx_data_exports_format ON data_exports(format)',
        'CREATE INDEX IF NOT EXISTS idx_data_exports_status ON data_exports(status)',
        'CREATE INDEX IF NOT EXISTS idx_batch_imports_type ON batch_imports(import_type)',
        'CREATE INDEX IF NOT EXISTS idx_batch_imports_format ON batch_imports(format)',
        'CREATE INDEX IF NOT EXISTS idx_batch_imports_status ON batch_imports(status)',
        # ─── Phase 17: Hunting, Foraging & Wild Food (v7.23.0) ───
        'CREATE INDEX IF NOT EXISTS idx_hunting_game_log_species ON hunting_game_log(species)',
        'CREATE INDEX IF NOT EXISTS idx_hunting_game_log_type ON hunting_game_log(game_type)',
        'CREATE INDEX IF NOT EXISTS idx_hunting_game_log_date ON hunting_game_log(date)',
        'CREATE INDEX IF NOT EXISTS idx_hunting_game_log_method ON hunting_game_log(method)',
        'CREATE INDEX IF NOT EXISTS idx_fishing_log_species ON fishing_log(species)',
        'CREATE INDEX IF NOT EXISTS idx_fishing_log_date ON fishing_log(date)',
        'CREATE INDEX IF NOT EXISTS idx_fishing_log_water_type ON fishing_log(water_type)',
        'CREATE INDEX IF NOT EXISTS idx_foraging_log_plant ON foraging_log(plant_name)',
        'CREATE INDEX IF NOT EXISTS idx_foraging_log_category ON foraging_log(category)',
        'CREATE INDEX IF NOT EXISTS idx_foraging_log_date ON foraging_log(date)',
        'CREATE INDEX IF NOT EXISTS idx_foraging_log_confidence ON foraging_log(confidence_level)',
        'CREATE INDEX IF NOT EXISTS idx_traps_snares_type ON traps_snares(trap_type)',
        'CREATE INDEX IF NOT EXISTS idx_traps_snares_status ON traps_snares(status)',
        'CREATE INDEX IF NOT EXISTS idx_traps_snares_check ON traps_snares(check_date)',
        'CREATE INDEX IF NOT EXISTS idx_wild_edibles_category ON wild_edibles(category)',
        'CREATE INDEX IF NOT EXISTS idx_wild_edibles_region ON wild_edibles(region)',
        'CREATE INDEX IF NOT EXISTS idx_trade_skills_category ON trade_skills(category)',
        'CREATE INDEX IF NOT EXISTS idx_trade_skills_level ON trade_skills(skill_level)',
        'CREATE INDEX IF NOT EXISTS idx_trade_projects_skill ON trade_projects(skill_id)',
        'CREATE INDEX IF NOT EXISTS idx_trade_projects_status ON trade_projects(status)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_methods_type ON preservation_methods(method_type)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_batches_method ON preservation_batches(method_id)',
        'CREATE INDEX IF NOT EXISTS idx_preservation_batches_expiry ON preservation_batches(expiration_date)',
        'CREATE INDEX IF NOT EXISTS idx_hunting_zones_type ON hunting_zones(zone_type)',
        # ─── Phase 18: Hardware, Sensors & Mesh (v7.24.0) ───
        'CREATE INDEX IF NOT EXISTS idx_iot_sensors_type ON iot_sensors(sensor_type)',
        'CREATE INDEX IF NOT EXISTS idx_iot_sensors_protocol ON iot_sensors(protocol)',
        'CREATE INDEX IF NOT EXISTS idx_iot_sensors_status ON iot_sensors(status)',
        'CREATE INDEX IF NOT EXISTS idx_sensor_readings_sensor ON sensor_readings(sensor_id)',
        'CREATE INDEX IF NOT EXISTS idx_sensor_readings_time ON sensor_readings(timestamp)',
        'CREATE INDEX IF NOT EXISTS idx_network_devices_type ON network_devices(device_type)',
        'CREATE INDEX IF NOT EXISTS idx_network_devices_status ON network_devices(status)',
        'CREATE INDEX IF NOT EXISTS idx_network_devices_ip ON network_devices(ip_address)',
        'CREATE INDEX IF NOT EXISTS idx_mesh_nodes_node_id ON mesh_nodes(node_id)',
        'CREATE INDEX IF NOT EXISTS idx_mesh_nodes_status ON mesh_nodes(status)',
        'CREATE INDEX IF NOT EXISTS idx_mesh_nodes_last_heard ON mesh_nodes(last_heard)',
        'CREATE INDEX IF NOT EXISTS idx_weather_stations_type ON weather_stations(station_type)',
        'CREATE INDEX IF NOT EXISTS idx_weather_stations_status ON weather_stations(status)',
        'CREATE INDEX IF NOT EXISTS idx_gps_devices_type ON gps_devices(device_type)',
        'CREATE INDEX IF NOT EXISTS idx_gps_devices_status ON gps_devices(status)',
        'CREATE INDEX IF NOT EXISTS idx_wearable_devices_type ON wearable_devices(device_type)',
        'CREATE INDEX IF NOT EXISTS idx_wearable_devices_wearer ON wearable_devices(wearer)',
        'CREATE INDEX IF NOT EXISTS idx_integration_configs_type ON integration_configs(integration_type)',
        'CREATE INDEX IF NOT EXISTS idx_integration_configs_status ON integration_configs(status)',
        # ─── Phase 19: Platform, Deployment & Security (v7.25.0) ───
        'CREATE INDEX IF NOT EXISTS idx_app_users_username ON app_users(username)',
        'CREATE INDEX IF NOT EXISTS idx_app_users_role ON app_users(role)',
        'CREATE INDEX IF NOT EXISTS idx_app_users_active ON app_users(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_app_sessions_token ON app_sessions(session_token)',
        'CREATE INDEX IF NOT EXISTS idx_app_sessions_user ON app_sessions(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_app_sessions_active ON app_sessions(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_app_sessions_expires ON app_sessions(expires_at)',
        'CREATE INDEX IF NOT EXISTS idx_platform_access_log_user ON platform_access_log(user_id)',
        'CREATE INDEX IF NOT EXISTS idx_platform_access_log_action ON platform_access_log(action)',
        'CREATE INDEX IF NOT EXISTS idx_platform_access_log_created ON platform_access_log(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_deployment_configs_type ON deployment_configs(config_type)',
        'CREATE INDEX IF NOT EXISTS idx_deployment_configs_active ON deployment_configs(is_active)',
        'CREATE INDEX IF NOT EXISTS idx_performance_metrics_type ON performance_metrics(metric_type)',
        'CREATE INDEX IF NOT EXISTS idx_performance_metrics_recorded ON performance_metrics(recorded_at)',
        # ─── Phase 20: Specialized Modules & Community (v7.26.0) ───
        'CREATE INDEX IF NOT EXISTS idx_supply_caches_type ON supply_caches(cache_type)',
        'CREATE INDEX IF NOT EXISTS idx_supply_caches_security ON supply_caches(security_level)',
        'CREATE INDEX IF NOT EXISTS idx_pets_species ON pets(species)',
        'CREATE INDEX IF NOT EXISTS idx_pets_status ON pets(status)',
        'CREATE INDEX IF NOT EXISTS idx_youth_programs_type ON youth_programs(program_type)',
        'CREATE INDEX IF NOT EXISTS idx_youth_programs_status ON youth_programs(status)',
        'CREATE INDEX IF NOT EXISTS idx_end_of_life_plans_person ON end_of_life_plans(person)',
        'CREATE INDEX IF NOT EXISTS idx_end_of_life_plans_status ON end_of_life_plans(status)',
        'CREATE INDEX IF NOT EXISTS idx_procurement_lists_type ON procurement_lists(list_type)',
        'CREATE INDEX IF NOT EXISTS idx_procurement_lists_status ON procurement_lists(status)',
        'CREATE INDEX IF NOT EXISTS idx_procurement_lists_priority ON procurement_lists(priority)',
        'CREATE INDEX IF NOT EXISTS idx_intel_collection_type ON intel_collection(intel_type)',
        'CREATE INDEX IF NOT EXISTS idx_intel_collection_status ON intel_collection(status)',
        'CREATE INDEX IF NOT EXISTS idx_intel_collection_classification ON intel_collection(classification)',
        'CREATE INDEX IF NOT EXISTS idx_fabrication_projects_type ON fabrication_projects(project_type)',
        'CREATE INDEX IF NOT EXISTS idx_fabrication_projects_status ON fabrication_projects(status)',
        'CREATE INDEX IF NOT EXISTS idx_badges_category ON badges(category)',
        'CREATE INDEX IF NOT EXISTS idx_badges_rarity ON badges(rarity)',
        'CREATE INDEX IF NOT EXISTS idx_badge_awards_badge ON badge_awards(badge_id)',
        'CREATE INDEX IF NOT EXISTS idx_badge_awards_person ON badge_awards(person)',
        'CREATE INDEX IF NOT EXISTS idx_seasonal_events_date ON seasonal_events(date)',
        'CREATE INDEX IF NOT EXISTS idx_seasonal_events_type ON seasonal_events(event_type)',
        'CREATE INDEX IF NOT EXISTS idx_seasonal_events_category ON seasonal_events(category)',
        'CREATE INDEX IF NOT EXISTS idx_legal_documents_type ON legal_documents(doc_type)',
        'CREATE INDEX IF NOT EXISTS idx_legal_documents_person ON legal_documents(person)',
        'CREATE INDEX IF NOT EXISTS idx_legal_documents_expiry ON legal_documents(expiry_date)',
        'CREATE INDEX IF NOT EXISTS idx_drones_type ON drones(drone_type)',
        'CREATE INDEX IF NOT EXISTS idx_drones_condition ON drones(condition)',
        'CREATE INDEX IF NOT EXISTS idx_drone_flights_drone ON drone_flights(drone_id)',
        'CREATE INDEX IF NOT EXISTS idx_drone_flights_date ON drone_flights(date)',
        'CREATE INDEX IF NOT EXISTS idx_fitness_logs_person ON fitness_logs(person)',
        'CREATE INDEX IF NOT EXISTS idx_fitness_logs_date ON fitness_logs(date)',
        'CREATE INDEX IF NOT EXISTS idx_fitness_logs_type ON fitness_logs(exercise_type)',
        'CREATE INDEX IF NOT EXISTS idx_content_packs_type ON content_packs(pack_type)',
        'CREATE INDEX IF NOT EXISTS idx_content_packs_status ON content_packs(status)',
    ]:
        try:
            conn.execute(idx)
        except sqlite3.OperationalError:
            pass  # Index already exists or related issue
    conn.commit()


def _create_data_foundation_tables(conn):
    """Phase 1 — Data Foundation & Localization: regional profiles, nutrition DB,
    data pack management, and inventory→nutrition linking."""
    conn.executescript('''
        /* ─── Regional Profile ─── */
        CREATE TABLE IF NOT EXISTS regional_profile (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL DEFAULT 'primary',
            country TEXT DEFAULT 'US',
            state TEXT DEFAULT '',
            county TEXT DEFAULT '',
            zip_code TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            usda_zone TEXT DEFAULT '',
            fema_risk_scores TEXT DEFAULT '{}',
            frost_date_last TEXT DEFAULT '',
            frost_date_first TEXT DEFAULT '',
            nearest_nws_station TEXT DEFAULT '',
            nearest_nws_station_name TEXT DEFAULT '',
            threat_weights TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Data Packs ─── */
        CREATE TABLE IF NOT EXISTS data_packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pack_id TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            tier INTEGER DEFAULT 1,
            category TEXT DEFAULT 'general',
            size_bytes INTEGER DEFAULT 0,
            compressed_size_bytes INTEGER DEFAULT 0,
            version TEXT DEFAULT '1.0.0',
            status TEXT DEFAULT 'available',
            installed_at TEXT DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            manifest TEXT DEFAULT '{}',
            source_url TEXT DEFAULT '',
            checksum TEXT DEFAULT ''
        );

        /* ─── Nutrition Foods (USDA FoodData SR Legacy) ─── */
        CREATE TABLE IF NOT EXISTS nutrition_foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fdc_id INTEGER UNIQUE,
            description TEXT NOT NULL,
            food_group TEXT DEFAULT '',
            calories REAL DEFAULT 0,
            protein_g REAL DEFAULT 0,
            fat_g REAL DEFAULT 0,
            carbs_g REAL DEFAULT 0,
            fiber_g REAL DEFAULT 0,
            sugar_g REAL DEFAULT 0,
            sodium_mg REAL DEFAULT 0,
            serving_size REAL DEFAULT 100,
            serving_unit TEXT DEFAULT 'g',
            data_source TEXT DEFAULT 'sr_legacy'
        );

        /* ─── Nutrition Nutrients (per-food micronutrient detail) ─── */
        CREATE TABLE IF NOT EXISTS nutrition_nutrients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fdc_id INTEGER NOT NULL,
            nutrient_name TEXT NOT NULL,
            nutrient_number TEXT DEFAULT '',
            amount REAL DEFAULT 0,
            unit TEXT DEFAULT '',
            FOREIGN KEY (fdc_id) REFERENCES nutrition_foods(fdc_id)
        );

        /* ─── Inventory ↔ Nutrition Link ─── */
        CREATE TABLE IF NOT EXISTS inventory_nutrition_link (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL,
            fdc_id INTEGER NOT NULL,
            servings_per_item REAL DEFAULT 1,
            calories_per_serving REAL DEFAULT 0,
            protein_per_serving REAL DEFAULT 0,
            fat_per_serving REAL DEFAULT 0,
            carbs_per_serving REAL DEFAULT 0,
            linked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (inventory_id) REFERENCES inventory(id),
            FOREIGN KEY (fdc_id) REFERENCES nutrition_foods(fdc_id)
        );

        /* ─── FEMA NRI County Hazard Data ─── */
        CREATE TABLE IF NOT EXISTS fema_nri_counties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            state_fips TEXT NOT NULL,
            county_fips TEXT NOT NULL,
            state_name TEXT DEFAULT '',
            county_name TEXT DEFAULT '',
            risk_score REAL DEFAULT 0,
            risk_rating TEXT DEFAULT '',
            expected_annual_loss REAL DEFAULT 0,
            social_vulnerability REAL DEFAULT 0,
            community_resilience REAL DEFAULT 0,
            hazard_scores TEXT DEFAULT '{}',
            UNIQUE(state_fips, county_fips)
        );
    ''')
    conn.commit()


def _create_meal_planning_tables(conn):
    """Phase 4 — Advanced Inventory & Consumption Modeling:
    recipes, recipe ingredients, and inventory substitute mapping."""
    conn.executescript('''
        /* ─── Recipes ─── */
        CREATE TABLE IF NOT EXISTS recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'meal',
            servings INTEGER DEFAULT 4,
            prep_time_min INTEGER DEFAULT 0,
            cook_time_min INTEGER DEFAULT 0,
            method TEXT DEFAULT '',
            instructions TEXT DEFAULT '',
            calories_per_serving REAL DEFAULT 0,
            tags TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Recipe Ingredients (linked to inventory/nutrition) ─── */
        CREATE TABLE IF NOT EXISTS recipe_ingredients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipe_id INTEGER NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
            inventory_id INTEGER,
            fdc_id INTEGER,
            name TEXT NOT NULL,
            quantity REAL DEFAULT 1,
            unit TEXT DEFAULT '',
            optional INTEGER DEFAULT 0
        );

        /* ─── Inventory Substitutes ─── */
        CREATE TABLE IF NOT EXISTS inventory_substitutes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL REFERENCES inventory(id),
            substitute_id INTEGER NOT NULL REFERENCES inventory(id),
            ratio REAL DEFAULT 1.0,
            notes TEXT DEFAULT '',
            UNIQUE(inventory_id, substitute_id)
        );

        /* ─── Inventory Audit Runs ─── */
        CREATE TABLE IF NOT EXISTS inventory_audits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT DEFAULT '',
            status TEXT DEFAULT 'in_progress',
            total_items INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            discrepancies INTEGER DEFAULT 0,
            notes TEXT DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS inventory_audit_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            audit_id INTEGER NOT NULL REFERENCES inventory_audits(id) ON DELETE CASCADE,
            inventory_id INTEGER NOT NULL,
            expected_qty REAL DEFAULT 0,
            actual_qty REAL,
            verified INTEGER DEFAULT 0,
            discrepancy_notes TEXT DEFAULT ''
        );
    ''')
    conn.commit()


def _create_consumption_water_budget_tables(conn):
    """Phase 2 — Nutritional Intelligence & Water Management expansion:
    consumption profiles, water budgets, dietary restrictions."""
    conn.executescript('''
        /* ─── Consumption Profiles (per-person caloric needs) ─── */
        CREATE TABLE IF NOT EXISTS consumption_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            profile_type TEXT DEFAULT 'adult_male',
            age_years INTEGER DEFAULT 30,
            weight_lb REAL DEFAULT 0,
            activity_level TEXT DEFAULT 'moderate',
            daily_calories INTEGER DEFAULT 2000,
            daily_water_gal REAL DEFAULT 0.5,
            dietary_restrictions TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Water Budget Categories ─── */
        CREATE TABLE IF NOT EXISTS water_budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            daily_gallons REAL DEFAULT 0,
            per_person INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            enabled INTEGER DEFAULT 1,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_movement_ops_tables(conn):
    """Phase 5 — Evacuation, Movement & Route Planning:
    movement plans, alt vehicles, route hazards/recon, vehicle loading, go/no-go."""
    conn.executescript('''
        /* ─── Movement Plans (foot march, convoy, multi-modal) ─── */
        CREATE TABLE IF NOT EXISTS movement_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            plan_type TEXT DEFAULT 'foot',
            origin TEXT DEFAULT '',
            origin_lat REAL,
            origin_lng REAL,
            destination TEXT DEFAULT '',
            destination_lat REAL,
            destination_lng REAL,
            distance_miles REAL DEFAULT 0,
            pace_count_per_100m INTEGER DEFAULT 65,
            march_rate_mph REAL DEFAULT 3.0,
            estimated_hours REAL DEFAULT 0,
            rest_plan TEXT DEFAULT '10min/hour',
            water_stops TEXT DEFAULT '[]',
            waypoints TEXT DEFAULT '[]',
            convoy_sop TEXT DEFAULT '',
            convoy_order TEXT DEFAULT '[]',
            comm_plan TEXT DEFAULT '',
            hand_signals TEXT DEFAULT '[]',
            night_movement INTEGER DEFAULT 0,
            vehicle_id INTEGER,
            evac_plan_id INTEGER REFERENCES evac_plans(id),
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Alternative Vehicles (bicycle, horse, boat, ATV, etc.) ─── */
        CREATE TABLE IF NOT EXISTS alt_vehicles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            vehicle_type TEXT DEFAULT 'bicycle',
            capacity_lb REAL DEFAULT 0,
            range_miles REAL DEFAULT 0,
            speed_mph REAL DEFAULT 0,
            fuel_type TEXT DEFAULT 'human',
            fuel_consumption TEXT DEFAULT '',
            feed_requirements TEXT DEFAULT '',
            condition TEXT DEFAULT 'good',
            maintenance_due TEXT DEFAULT '',
            storage_location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Route Hazards (bridges, tunnels, chokepoints, flood zones) ─── */
        CREATE TABLE IF NOT EXISTS route_hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_plan_id INTEGER REFERENCES movement_plans(id),
            name TEXT NOT NULL,
            hazard_type TEXT DEFAULT 'chokepoint',
            lat REAL,
            lng REAL,
            severity TEXT DEFAULT 'moderate',
            description TEXT DEFAULT '',
            bypass_route TEXT DEFAULT '',
            seasonal INTEGER DEFAULT 0,
            active_months TEXT DEFAULT '',
            last_verified TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Route Reconnaissance Log ─── */
        CREATE TABLE IF NOT EXISTS route_recon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            movement_plan_id INTEGER REFERENCES movement_plans(id),
            recon_date TEXT NOT NULL,
            observer TEXT DEFAULT '',
            road_condition TEXT DEFAULT 'passable',
            bridge_status TEXT DEFAULT 'intact',
            water_crossings TEXT DEFAULT '[]',
            obstacles TEXT DEFAULT '[]',
            threat_level TEXT DEFAULT 'low',
            population_density TEXT DEFAULT 'rural',
            fuel_available INTEGER DEFAULT 0,
            water_available INTEGER DEFAULT 0,
            shelter_available INTEGER DEFAULT 0,
            photos TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Vehicle Loading Plans (which bags/gear in which vehicle) ─── */
        CREATE TABLE IF NOT EXISTS vehicle_loading_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evac_plan_id INTEGER REFERENCES evac_plans(id),
            vehicle_id INTEGER,
            vehicle_name TEXT DEFAULT '',
            load_order INTEGER DEFAULT 0,
            assigned_persons TEXT DEFAULT '[]',
            assigned_bags TEXT DEFAULT '[]',
            assigned_items TEXT DEFAULT '[]',
            total_weight_lb REAL DEFAULT 0,
            max_weight_lb REAL DEFAULT 0,
            fuel_level_pct INTEGER DEFAULT 100,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Go/No-Go Decision Matrix ─── */
        CREATE TABLE IF NOT EXISTS go_nogo_matrix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evac_plan_id INTEGER REFERENCES evac_plans(id),
            criterion TEXT NOT NULL,
            category TEXT DEFAULT 'security',
            weight REAL DEFAULT 1.0,
            go_threshold TEXT DEFAULT '',
            nogo_threshold TEXT DEFAULT '',
            current_value TEXT DEFAULT '',
            current_status TEXT DEFAULT 'unknown',
            data_source TEXT DEFAULT 'manual',
            last_updated TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_tactical_comms_tables(conn):
    """Phase 6 — Communications & Field Operations:
    radio equipment, auth codes, net schedules, comms checks, field reference."""
    conn.executescript('''
        /* ─── Radio Equipment Inventory ─── */
        CREATE TABLE IF NOT EXISTS radio_equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            model TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            radio_type TEXT DEFAULT 'handheld',
            freq_range_low REAL DEFAULT 0,
            freq_range_high REAL DEFAULT 0,
            power_watts REAL DEFAULT 5,
            battery_type TEXT DEFAULT '',
            battery_count INTEGER DEFAULT 1,
            antenna TEXT DEFAULT '',
            firmware_version TEXT DEFAULT '',
            programmed_channels TEXT DEFAULT '[]',
            condition TEXT DEFAULT 'good',
            assigned_to TEXT DEFAULT '',
            location TEXT DEFAULT '',
            last_tested TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Authentication Codes (challenge/response, daily rotating) ─── */
        CREATE TABLE IF NOT EXISTS auth_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code_set_name TEXT NOT NULL,
            valid_date TEXT NOT NULL,
            challenge TEXT NOT NULL,
            response TEXT NOT NULL,
            running_password TEXT DEFAULT '',
            number_combination TEXT DEFAULT '',
            duress_code TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Net Schedules (radio check-in windows) ─── */
        CREATE TABLE IF NOT EXISTS net_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            net_type TEXT DEFAULT 'daily',
            frequency TEXT DEFAULT '',
            backup_frequency TEXT DEFAULT '',
            day_of_week TEXT DEFAULT 'daily',
            start_time TEXT DEFAULT '0800',
            duration_min INTEGER DEFAULT 30,
            net_control TEXT DEFAULT '',
            call_order TEXT DEFAULT '[]',
            protocol TEXT DEFAULT 'voice',
            is_active INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Comms Checks Log ─── */
        CREATE TABLE IF NOT EXISTS comms_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            net_schedule_id INTEGER REFERENCES net_schedules(id),
            check_date TEXT NOT NULL,
            check_time TEXT DEFAULT '',
            operator TEXT DEFAULT '',
            stations_checked TEXT DEFAULT '[]',
            stations_missed TEXT DEFAULT '[]',
            signal_quality TEXT DEFAULT 'good',
            propagation_notes TEXT DEFAULT '',
            issues TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Message Templates (SITREP, MEDEVAC 9-line, SALUTE, etc.) ─── */
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            template_type TEXT DEFAULT 'SITREP',
            fields TEXT DEFAULT '[]',
            example TEXT DEFAULT '',
            instructions TEXT DEFAULT '',
            is_builtin INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Sent Messages Log ─── */
        CREATE TABLE IF NOT EXISTS sent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER REFERENCES message_templates(id),
            template_type TEXT DEFAULT '',
            content TEXT DEFAULT '{}',
            formatted_text TEXT DEFAULT '',
            sent_via TEXT DEFAULT 'radio',
            sent_to TEXT DEFAULT '',
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged INTEGER DEFAULT 0,
            acknowledged_at TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_land_assessment_tables(conn):
    """Phase 8 — Land Assessment & Property: site scoring, property mapping,
    development planning, BOL comparison."""
    conn.executescript('''
        /* ─── Properties (real estate / BOL sites) ─── */
        CREATE TABLE IF NOT EXISTS properties (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            property_type TEXT DEFAULT 'rural',
            address TEXT DEFAULT '',
            county TEXT DEFAULT '',
            state TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            acreage REAL DEFAULT 0,
            purchase_price REAL DEFAULT 0,
            current_value REAL DEFAULT 0,
            ownership TEXT DEFAULT 'owned',
            access_road TEXT DEFAULT '',
            distance_from_home_miles REAL DEFAULT 0,
            travel_time_hours REAL DEFAULT 0,
            nearest_town TEXT DEFAULT '',
            nearest_town_miles REAL DEFAULT 0,
            population_density TEXT DEFAULT 'rural',
            zoning TEXT DEFAULT '',
            water_rights TEXT DEFAULT '',
            mineral_rights TEXT DEFAULT '',
            total_score REAL DEFAULT 0,
            status TEXT DEFAULT 'prospect',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Property Assessments (scored criteria) ─── */
        CREATE TABLE IF NOT EXISTS property_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL REFERENCES properties(id),
            criterion TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            score INTEGER DEFAULT 5,
            weight REAL DEFAULT 1.0,
            notes TEXT DEFAULT '',
            assessed_date TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Property Features (infrastructure, resources, hazards) ─── */
        CREATE TABLE IF NOT EXISTS property_features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL REFERENCES properties(id),
            feature_type TEXT DEFAULT 'building',
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            lat REAL,
            lng REAL,
            condition TEXT DEFAULT 'good',
            value_estimate REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Development Plans (projects for property improvement) ─── */
        CREATE TABLE IF NOT EXISTS development_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id INTEGER NOT NULL REFERENCES properties(id),
            name TEXT NOT NULL,
            category TEXT DEFAULT 'infrastructure',
            priority TEXT DEFAULT 'medium',
            estimated_cost REAL DEFAULT 0,
            actual_cost REAL DEFAULT 0,
            start_date TEXT DEFAULT '',
            target_date TEXT DEFAULT '',
            completed_date TEXT DEFAULT '',
            status TEXT DEFAULT 'planned',
            impact_score INTEGER DEFAULT 5,
            description TEXT DEFAULT '',
            materials TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_medical_phase2_tables(conn):
    """Phase 9 — Medical Phase 2: pregnancy, dental, veterinary, chronic conditions,
    vaccinations, mental health, herbal remedies, clinical tools."""
    conn.executescript('''
        /* ─── Pregnancy & Childbirth Tracking ─── */
        CREATE TABLE IF NOT EXISTS pregnancies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            due_date TEXT DEFAULT '',
            conception_date TEXT DEFAULT '',
            blood_type TEXT DEFAULT '',
            rh_factor TEXT DEFAULT '',
            gravida INTEGER DEFAULT 1,
            para INTEGER DEFAULT 0,
            risk_factors TEXT DEFAULT '[]',
            prenatal_visits TEXT DEFAULT '[]',
            birth_plan TEXT DEFAULT '',
            supply_checklist TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            outcome TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Dental Records ─── */
        CREATE TABLE IF NOT EXISTS dental_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            tooth_number INTEGER,
            condition TEXT DEFAULT '',
            treatment TEXT DEFAULT '',
            treatment_date TEXT DEFAULT '',
            pain_level INTEGER DEFAULT 0,
            provider TEXT DEFAULT '',
            follow_up_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Herbal & Alternative Remedies Reference ─── */
        CREATE TABLE IF NOT EXISTS herbal_remedies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            common_names TEXT DEFAULT '',
            uses TEXT DEFAULT '[]',
            preparation TEXT DEFAULT '',
            dosage TEXT DEFAULT '',
            contraindications TEXT DEFAULT '[]',
            interactions TEXT DEFAULT '[]',
            season TEXT DEFAULT 'all',
            habitat TEXT DEFAULT '',
            identification TEXT DEFAULT '',
            is_builtin INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Chronic Condition Management ─── */
        CREATE TABLE IF NOT EXISTS chronic_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            condition_name TEXT NOT NULL,
            severity TEXT DEFAULT 'moderate',
            diagnosed_date TEXT DEFAULT '',
            medications TEXT DEFAULT '[]',
            medication_stockpile_days INTEGER DEFAULT 0,
            weaning_protocol TEXT DEFAULT '',
            alternative_treatments TEXT DEFAULT '[]',
            monitoring_schedule TEXT DEFAULT '',
            emergency_protocol TEXT DEFAULT '',
            last_checkup TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Vaccination Tracker ─── */
        CREATE TABLE IF NOT EXISTS vaccinations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            vaccine_name TEXT NOT NULL,
            date_administered TEXT DEFAULT '',
            dose_number INTEGER DEFAULT 1,
            lot_number TEXT DEFAULT '',
            provider TEXT DEFAULT '',
            next_due TEXT DEFAULT '',
            reaction TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Mental Health Check-in Log ─── */
        CREATE TABLE IF NOT EXISTS mental_health_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            check_date TEXT NOT NULL,
            mood_score INTEGER DEFAULT 5,
            anxiety_level INTEGER DEFAULT 0,
            sleep_hours REAL DEFAULT 7,
            sleep_quality TEXT DEFAULT 'fair',
            appetite TEXT DEFAULT 'normal',
            energy_level INTEGER DEFAULT 5,
            stress_sources TEXT DEFAULT '[]',
            coping_strategies TEXT DEFAULT '[]',
            warning_signs TEXT DEFAULT '[]',
            provider_notes TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Veterinary Records (pets & livestock) ─── */
        CREATE TABLE IF NOT EXISTS vet_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_name TEXT NOT NULL,
            species TEXT DEFAULT 'dog',
            breed TEXT DEFAULT '',
            weight_lb REAL DEFAULT 0,
            age_years REAL DEFAULT 0,
            condition TEXT DEFAULT '',
            treatment TEXT DEFAULT '',
            treatment_date TEXT DEFAULT '',
            medications TEXT DEFAULT '[]',
            vaccinations TEXT DEFAULT '[]',
            provider TEXT DEFAULT '',
            next_due TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_training_knowledge_tables(conn):
    """Phase 10 — Training, Education & Knowledge Preservation: skill trees,
    courses, lessons, certifications, drills, flashcards, knowledge packages."""
    conn.executescript('''
        /* ─── Skill Trees ─── */
        CREATE TABLE IF NOT EXISTS skill_trees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            skill_name TEXT NOT NULL,
            category TEXT DEFAULT 'survival',
            level INTEGER DEFAULT 1,
            prerequisites TEXT DEFAULT '[]',
            certified INTEGER DEFAULT 0,
            certified_date TEXT DEFAULT '',
            instructor TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Training Courses ─── */
        CREATE TABLE IF NOT EXISTS training_courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            difficulty TEXT DEFAULT 'beginner',
            estimated_hours REAL DEFAULT 1.0,
            instructor TEXT DEFAULT '',
            max_students INTEGER DEFAULT 10,
            prerequisites_text TEXT DEFAULT '',
            materials_needed TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Training Lessons ─── */
        CREATE TABLE IF NOT EXISTS training_lessons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER NOT NULL REFERENCES training_courses(id) ON DELETE CASCADE,
            lesson_number INTEGER DEFAULT 1,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            duration_minutes INTEGER DEFAULT 30,
            lesson_type TEXT DEFAULT 'lecture',
            materials TEXT DEFAULT '',
            objectives TEXT DEFAULT '[]',
            completed_by TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Certifications ─── */
        CREATE TABLE IF NOT EXISTS certifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            certification_name TEXT NOT NULL,
            issuing_authority TEXT DEFAULT '',
            date_earned TEXT DEFAULT '',
            expiration_date TEXT DEFAULT '',
            renewal_interval_days INTEGER DEFAULT 365,
            status TEXT DEFAULT 'active',
            document_ref TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Drill Templates ─── */
        CREATE TABLE IF NOT EXISTS drill_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            drill_type TEXT DEFAULT 'custom',
            description TEXT DEFAULT '',
            phases TEXT DEFAULT '[]',
            grading_criteria TEXT DEFAULT '[]',
            estimated_duration_minutes INTEGER DEFAULT 30,
            personnel_required INTEGER DEFAULT 2,
            equipment_needed TEXT DEFAULT '',
            is_builtin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Drill Results ─── */
        CREATE TABLE IF NOT EXISTS drill_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id INTEGER REFERENCES drill_templates(id) ON DELETE SET NULL,
            drill_date TEXT NOT NULL,
            participants TEXT DEFAULT '[]',
            overall_grade TEXT DEFAULT '',
            phase_scores TEXT DEFAULT '[]',
            deficiencies TEXT DEFAULT '[]',
            strengths TEXT DEFAULT '[]',
            aar_notes TEXT DEFAULT '',
            corrective_actions TEXT DEFAULT '',
            next_drill_date TEXT DEFAULT '',
            conducted_by TEXT DEFAULT '',
            is_no_notice INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Flashcards (Spaced Repetition) ─── */
        CREATE TABLE IF NOT EXISTS flashcards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            deck_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            front_text TEXT NOT NULL,
            back_text TEXT NOT NULL,
            difficulty INTEGER DEFAULT 1,
            interval_days INTEGER DEFAULT 1,
            ease_factor REAL DEFAULT 2.5,
            next_review TEXT DEFAULT '',
            review_count INTEGER DEFAULT 0,
            correct_count INTEGER DEFAULT 0,
            last_reviewed TEXT DEFAULT '',
            tags TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Knowledge Packages ("If I'm Gone") ─── */
        CREATE TABLE IF NOT EXISTS knowledge_packages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_name TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            category TEXT DEFAULT 'general',
            skills_documented TEXT DEFAULT '[]',
            procedures TEXT DEFAULT '[]',
            contacts_referenced TEXT DEFAULT '[]',
            critical_knowledge TEXT DEFAULT '',
            contingency_plans TEXT DEFAULT '',
            last_reviewed TEXT DEFAULT '',
            review_interval_days INTEGER DEFAULT 90,
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_group_ops_tables(conn):
    """Phase 11 — Group Operations & Governance: pods, members, governance,
    SOPs, duty roster, disputes, votes, ICS forms, CERT, shelters, warnings."""
    conn.executescript('''
        /* ─── Pods (Multi-Household Groups) ─── */
        CREATE TABLE IF NOT EXISTS pods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            location TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            leader_contact_id INTEGER DEFAULT 0,
            member_count INTEGER DEFAULT 0,
            resource_sharing_policy TEXT DEFAULT '',
            communication_plan TEXT DEFAULT '',
            meeting_schedule TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Pod Members ─── */
        CREATE TABLE IF NOT EXISTS pod_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER NOT NULL REFERENCES pods(id) ON DELETE CASCADE,
            contact_id INTEGER DEFAULT 0,
            person_name TEXT NOT NULL,
            role TEXT DEFAULT 'member',
            skills TEXT DEFAULT '[]',
            responsibilities TEXT DEFAULT '',
            joined_date TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Governance Roles ─── */
        CREATE TABLE IF NOT EXISTS governance_roles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER NOT NULL REFERENCES pods(id) ON DELETE CASCADE,
            role_title TEXT NOT NULL,
            person_name TEXT DEFAULT '',
            authority_level INTEGER DEFAULT 1,
            responsibilities TEXT DEFAULT '',
            chain_of_command TEXT DEFAULT '[]',
            succession_order INTEGER DEFAULT 0,
            term_start TEXT DEFAULT '',
            term_end TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Standard Operating Procedures ─── */
        CREATE TABLE IF NOT EXISTS governance_sops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'admin',
            content TEXT DEFAULT '',
            version TEXT DEFAULT '1.0',
            effective_date TEXT DEFAULT '',
            review_date TEXT DEFAULT '',
            approved_by TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Duty Roster ─── */
        CREATE TABLE IF NOT EXISTS duty_roster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            person_name TEXT NOT NULL,
            duty_type TEXT DEFAULT 'watch',
            shift_start TEXT DEFAULT '',
            shift_end TEXT DEFAULT '',
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Disputes ─── */
        CREATE TABLE IF NOT EXISTS disputes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            parties_involved TEXT DEFAULT '[]',
            dispute_type TEXT DEFAULT 'resource',
            severity TEXT DEFAULT 'medium',
            resolution_method TEXT DEFAULT 'mediation',
            resolution TEXT DEFAULT '',
            resolved_by TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            opened_date TEXT DEFAULT '',
            resolved_date TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Votes ─── */
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dispute_id INTEGER REFERENCES disputes(id) ON DELETE CASCADE,
            question TEXT NOT NULL,
            vote_type TEXT DEFAULT 'simple_majority',
            options TEXT DEFAULT '[]',
            results TEXT DEFAULT '{}',
            total_voters INTEGER DEFAULT 0,
            votes_cast INTEGER DEFAULT 0,
            status TEXT DEFAULT 'open',
            deadline TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── ICS Forms ─── */
        CREATE TABLE IF NOT EXISTS ics_forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            form_type TEXT NOT NULL,
            incident_name TEXT DEFAULT '',
            operational_period TEXT DEFAULT '',
            prepared_by TEXT DEFAULT '',
            form_data TEXT DEFAULT '{}',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── CERT Teams ─── */
        CREATE TABLE IF NOT EXISTS cert_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            team_name TEXT NOT NULL,
            team_type TEXT DEFAULT 'search_rescue',
            leader_name TEXT DEFAULT '',
            members TEXT DEFAULT '[]',
            equipment TEXT DEFAULT '[]',
            status TEXT DEFAULT 'standby',
            deployment_location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Damage Assessments ─── */
        CREATE TABLE IF NOT EXISTS damage_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            cert_team_id INTEGER DEFAULT 0,
            location TEXT NOT NULL,
            assessment_date TEXT DEFAULT '',
            damage_type TEXT DEFAULT 'structural',
            severity TEXT DEFAULT 'minor',
            occupancy_status TEXT DEFAULT 'occupied',
            utilities TEXT DEFAULT '{"power":"ok","water":"ok","gas":"ok","sewer":"ok"}',
            hazards TEXT DEFAULT '[]',
            photo_refs TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            assessor_name TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Shelters ─── */
        CREATE TABLE IF NOT EXISTS shelters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            name TEXT NOT NULL,
            location TEXT DEFAULT '',
            capacity INTEGER DEFAULT 10,
            current_occupancy INTEGER DEFAULT 0,
            shelter_type TEXT DEFAULT 'emergency',
            amenities TEXT DEFAULT '[]',
            supplies_status TEXT DEFAULT 'adequate',
            manager_name TEXT DEFAULT '',
            status TEXT DEFAULT 'standby',
            opened_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Community Warnings ─── */
        CREATE TABLE IF NOT EXISTS community_warnings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pod_id INTEGER DEFAULT 0,
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            severity TEXT DEFAULT 'info',
            target_area TEXT DEFAULT '',
            issued_by TEXT DEFAULT '',
            issued_at TEXT DEFAULT '',
            expires_at TEXT DEFAULT '',
            delivery_methods TEXT DEFAULT '[]',
            acknowledged_by TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_security_opsec_tables(conn):
    """Phase 12 — Security, OPSEC & Night Operations: compartments, checklists,
    threat matrix, observation posts, OP log, signatures, night ops, CBRN, EMP."""
    conn.executescript('''
        /* ─── OPSEC Compartments ─── */
        CREATE TABLE IF NOT EXISTS opsec_compartments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            classification TEXT DEFAULT 'open',
            authorized_persons TEXT DEFAULT '[]',
            cover_story TEXT DEFAULT '',
            duress_signal TEXT DEFAULT '',
            review_date TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── OPSEC Checklists ─── */
        CREATE TABLE IF NOT EXISTS opsec_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            compartment_id INTEGER DEFAULT 0,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'digital',
            items TEXT DEFAULT '[]',
            last_audit_date TEXT DEFAULT '',
            next_audit_date TEXT DEFAULT '',
            audited_by TEXT DEFAULT '',
            score INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Threat Matrix ─── */
        CREATE TABLE IF NOT EXISTS threat_matrix (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            threat_name TEXT NOT NULL,
            threat_type TEXT DEFAULT 'human',
            likelihood INTEGER DEFAULT 1,
            impact INTEGER DEFAULT 1,
            risk_score INTEGER DEFAULT 1,
            vulnerability TEXT DEFAULT '',
            countermeasure TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            assigned_to TEXT DEFAULT '',
            review_date TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Observation Posts ─── */
        CREATE TABLE IF NOT EXISTS observation_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            location TEXT DEFAULT '',
            coordinates TEXT DEFAULT '',
            type TEXT DEFAULT 'fixed',
            fields_of_fire TEXT DEFAULT '',
            dead_space TEXT DEFAULT '',
            sectors TEXT DEFAULT '[]',
            equipment TEXT DEFAULT '[]',
            communication TEXT DEFAULT '',
            status TEXT DEFAULT 'planned',
            assigned_to TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── OP Log Entries ─── */
        CREATE TABLE IF NOT EXISTS op_log_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER DEFAULT 0,
            observer TEXT DEFAULT '',
            entry_time TEXT DEFAULT '',
            category TEXT DEFAULT 'other',
            direction TEXT DEFAULT '',
            distance TEXT DEFAULT '',
            description TEXT DEFAULT '',
            threat_level TEXT DEFAULT 'none',
            action_taken TEXT DEFAULT '',
            reported_to TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Signature Assessments ─── */
        CREATE TABLE IF NOT EXISTS signature_assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT DEFAULT '',
            assessment_date TEXT DEFAULT '',
            visual_signatures TEXT DEFAULT '[]',
            audio_signatures TEXT DEFAULT '[]',
            electronic_signatures TEXT DEFAULT '[]',
            thermal_signatures TEXT DEFAULT '[]',
            overall_score INTEGER DEFAULT 0,
            recommendations TEXT DEFAULT '',
            assessed_by TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Night Ops Plans ─── */
        CREATE TABLE IF NOT EXISTS night_ops_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            operation_date TEXT DEFAULT '',
            moonrise TEXT DEFAULT '',
            moonset TEXT DEFAULT '',
            moon_phase TEXT DEFAULT '',
            moon_illumination INTEGER DEFAULT 0,
            ambient_light_level TEXT DEFAULT 'moonless',
            dark_adaptation_minutes INTEGER DEFAULT 30,
            nvg_required INTEGER DEFAULT 0,
            movement_routes TEXT DEFAULT '[]',
            rally_points TEXT DEFAULT '[]',
            signals TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── CBRN Equipment ─── */
        CREATE TABLE IF NOT EXISTS cbrn_equipment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_name TEXT NOT NULL,
            equipment_type TEXT DEFAULT 'ppe',
            model TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            calibration_date TEXT DEFAULT '',
            calibration_due TEXT DEFAULT '',
            condition TEXT DEFAULT 'serviceable',
            assigned_to TEXT DEFAULT '',
            location TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── CBRN Procedures ─── */
        CREATE TABLE IF NOT EXISTS cbrn_procedures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            procedure_type TEXT DEFAULT 'detection',
            threat_agent TEXT DEFAULT 'all',
            mopp_level INTEGER DEFAULT 0,
            steps TEXT DEFAULT '[]',
            equipment_required TEXT DEFAULT '[]',
            time_estimate_minutes INTEGER DEFAULT 30,
            warnings TEXT DEFAULT '',
            reference TEXT DEFAULT '',
            is_builtin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── EMP Hardening Inventory ─── */
        CREATE TABLE IF NOT EXISTS emp_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            category TEXT DEFAULT 'critical_spare',
            description TEXT DEFAULT '',
            protection_method TEXT DEFAULT '',
            is_protected INTEGER DEFAULT 0,
            grid_dependent INTEGER DEFAULT 0,
            manual_alternative TEXT DEFAULT '',
            priority TEXT DEFAULT 'medium',
            location TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            tested_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_agriculture_tables(conn):
    """Phase 13 — Agriculture & Permaculture: food forest, soil, perennials,
    breeding, feed, homestead systems, aquaponics, recycling."""
    conn.executescript('''
        /* ─── Food Forest Guilds ─── */
        CREATE TABLE IF NOT EXISTS food_forest_guilds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            central_species TEXT DEFAULT '',
            support_species TEXT DEFAULT '[]',
            nitrogen_fixers TEXT DEFAULT '[]',
            dynamic_accumulators TEXT DEFAULT '[]',
            pest_confusers TEXT DEFAULT '[]',
            ground_covers TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Food Forest Layers ─── */
        CREATE TABLE IF NOT EXISTS food_forest_layers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            design_name TEXT DEFAULT '',
            layer_type TEXT DEFAULT 'herbaceous',
            species TEXT DEFAULT '',
            spacing_ft REAL DEFAULT 0,
            mature_height_ft REAL DEFAULT 0,
            yield_per_year TEXT DEFAULT '',
            years_to_production INTEGER DEFAULT 1,
            guild_id INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Soil Building Projects ─── */
        CREATE TABLE IF NOT EXISTS soil_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_type TEXT DEFAULT 'compost',
            location TEXT DEFAULT '',
            dimensions TEXT DEFAULT '',
            materials TEXT DEFAULT '[]',
            start_date TEXT DEFAULT '',
            completion_date TEXT DEFAULT '',
            soil_test_before TEXT DEFAULT '{}',
            soil_test_after TEXT DEFAULT '{}',
            status TEXT DEFAULT 'planned',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Perennial Plants ─── */
        CREATE TABLE IF NOT EXISTS perennial_plants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            species TEXT DEFAULT '',
            variety TEXT DEFAULT '',
            plant_type TEXT DEFAULT 'fruit_tree',
            planted_date TEXT DEFAULT '',
            location TEXT DEFAULT '',
            rootstock TEXT DEFAULT '',
            pollinator_group TEXT DEFAULT '',
            years_to_bearing INTEGER DEFAULT 3,
            estimated_yield TEXT DEFAULT '',
            last_pruned TEXT DEFAULT '',
            last_fertilized TEXT DEFAULT '',
            health_status TEXT DEFAULT 'good',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Multi-Year Plans ─── */
        CREATE TABLE IF NOT EXISTS multi_year_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            start_year INTEGER DEFAULT 2024,
            end_year INTEGER DEFAULT 2044,
            goals TEXT DEFAULT '[]',
            milestones TEXT DEFAULT '[]',
            carrying_capacity_persons INTEGER DEFAULT 0,
            land_acres REAL DEFAULT 0,
            climate_zone TEXT DEFAULT '',
            adaptation_strategies TEXT DEFAULT '[]',
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Breeding Records ─── */
        CREATE TABLE IF NOT EXISTS breeding_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_name TEXT NOT NULL,
            species TEXT DEFAULT '',
            breed TEXT DEFAULT '',
            sex TEXT DEFAULT 'female',
            sire TEXT DEFAULT '',
            dam TEXT DEFAULT '',
            birth_date TEXT DEFAULT '',
            breeding_date TEXT DEFAULT '',
            expected_due TEXT DEFAULT '',
            offspring_count INTEGER DEFAULT 0,
            offspring_names TEXT DEFAULT '[]',
            genetic_notes TEXT DEFAULT '',
            health_at_breeding TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Feed Tracking ─── */
        CREATE TABLE IF NOT EXISTS feed_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            animal_group TEXT NOT NULL,
            feed_type TEXT DEFAULT '',
            quantity_lbs REAL DEFAULT 0,
            cost_per_unit REAL DEFAULT 0,
            fed_date TEXT DEFAULT '',
            fed_by TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Homestead Systems ─── */
        CREATE TABLE IF NOT EXISTS homestead_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            system_name TEXT NOT NULL,
            system_type TEXT DEFAULT 'solar',
            location TEXT DEFAULT '',
            capacity TEXT DEFAULT '',
            current_reading TEXT DEFAULT '',
            last_maintenance TEXT DEFAULT '',
            next_maintenance TEXT DEFAULT '',
            condition TEXT DEFAULT 'good',
            metrics TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Aquaponics / Hydroponics Systems ─── */
        CREATE TABLE IF NOT EXISTS aquaponics_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            system_type TEXT DEFAULT 'aquaponics',
            location TEXT DEFAULT '',
            fish_species TEXT DEFAULT '',
            fish_count INTEGER DEFAULT 0,
            plant_species TEXT DEFAULT '[]',
            water_volume_gal REAL DEFAULT 0,
            ph_level REAL DEFAULT 7.0,
            ammonia_ppm REAL DEFAULT 0,
            nitrite_ppm REAL DEFAULT 0,
            nitrate_ppm REAL DEFAULT 0,
            temperature_f REAL DEFAULT 72,
            last_water_change TEXT DEFAULT '',
            feeding_schedule TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Resource Recycling Systems ─── */
        CREATE TABLE IF NOT EXISTS recycling_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            system_type TEXT DEFAULT 'compost',
            location TEXT DEFAULT '',
            capacity TEXT DEFAULT '',
            input_sources TEXT DEFAULT '[]',
            output_products TEXT DEFAULT '[]',
            processing_time_days INTEGER DEFAULT 30,
            current_status TEXT DEFAULT 'active',
            last_turned TEXT DEFAULT '',
            temperature_f REAL DEFAULT 0,
            metrics TEXT DEFAULT '{}',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_disaster_modules_tables(conn):
    """Phase 14 — Disaster-Specific Modules: plans, checklists, energy,
    construction, materials, fortifications."""
    conn.executescript('''
        /* ─── Disaster Plans ─── */
        CREATE TABLE IF NOT EXISTS disaster_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            disaster_type TEXT DEFAULT 'earthquake',
            environment_type TEXT DEFAULT 'general',
            description TEXT DEFAULT '',
            trigger_conditions TEXT DEFAULT '',
            immediate_actions TEXT DEFAULT '[]',
            sustained_actions TEXT DEFAULT '[]',
            resources_required TEXT DEFAULT '[]',
            shelter_plan TEXT DEFAULT '',
            evacuation_triggers TEXT DEFAULT '',
            communication_plan TEXT DEFAULT '',
            estimated_duration TEXT DEFAULT '',
            personnel_assignments TEXT DEFAULT '[]',
            last_reviewed TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Disaster Checklists ─── */
        CREATE TABLE IF NOT EXISTS disaster_checklists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER DEFAULT 0,
            title TEXT NOT NULL,
            category TEXT DEFAULT 'pre_event',
            items TEXT DEFAULT '[]',
            assigned_to TEXT DEFAULT '',
            due_date TEXT DEFAULT '',
            completion_pct INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Alternative Energy Systems ─── */
        CREATE TABLE IF NOT EXISTS energy_systems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            energy_type TEXT DEFAULT 'wood',
            location TEXT DEFAULT '',
            capacity TEXT DEFAULT '',
            fuel_source TEXT DEFAULT '',
            output_rating TEXT DEFAULT '',
            efficiency_pct INTEGER DEFAULT 0,
            installation_date TEXT DEFAULT '',
            condition TEXT DEFAULT 'operational',
            maintenance_schedule TEXT DEFAULT '',
            inventory_link TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Construction Projects ─── */
        CREATE TABLE IF NOT EXISTS construction_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_type TEXT DEFAULT 'infrastructure',
            location TEXT DEFAULT '',
            description TEXT DEFAULT '',
            materials TEXT DEFAULT '[]',
            labor_hours_estimated INTEGER DEFAULT 0,
            labor_hours_actual INTEGER DEFAULT 0,
            start_date TEXT DEFAULT '',
            target_date TEXT DEFAULT '',
            completion_date TEXT DEFAULT '',
            assigned_to TEXT DEFAULT '',
            blueprint_ref TEXT DEFAULT '',
            status TEXT DEFAULT 'planned',
            priority TEXT DEFAULT 'medium',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Building Materials Inventory ─── */
        CREATE TABLE IF NOT EXISTS building_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'other',
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'each',
            location TEXT DEFAULT '',
            cost_per_unit REAL DEFAULT 0,
            supplier TEXT DEFAULT '',
            min_stock REAL DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Fortifications ─── */
        CREATE TABLE IF NOT EXISTS fortifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            fortification_type TEXT DEFAULT 'safe_room',
            location TEXT DEFAULT '',
            protection_level TEXT DEFAULT 'basic',
            dimensions TEXT DEFAULT '',
            materials_used TEXT DEFAULT '[]',
            capacity_persons INTEGER DEFAULT 0,
            construction_time_hours INTEGER DEFAULT 0,
            condition TEXT DEFAULT 'planned',
            last_inspection TEXT DEFAULT '',
            vulnerabilities TEXT DEFAULT '',
            improvements_needed TEXT DEFAULT '',
            status TEXT DEFAULT 'planned',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_daily_living_tables(conn):
    """Phase 15 — Daily Living & Quality of Life: schedules, chores, clothing,
    sanitation, morale, sleep, performance, grid-down recipes."""
    conn.executescript('''
        /* ─── Daily Schedules ─── */
        CREATE TABLE IF NOT EXISTS daily_schedules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            schedule_type TEXT DEFAULT 'normal',
            description TEXT DEFAULT '',
            time_blocks TEXT DEFAULT '[]',
            assigned_to TEXT DEFAULT '',
            is_template INTEGER DEFAULT 0,
            active_days TEXT DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]',
            start_date TEXT DEFAULT '',
            end_date TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Chore Assignments ─── */
        CREATE TABLE IF NOT EXISTS chore_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            schedule_id INTEGER DEFAULT 0,
            chore_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            assigned_to TEXT DEFAULT '',
            frequency TEXT DEFAULT 'daily',
            time_slot TEXT DEFAULT '',
            duration_minutes INTEGER DEFAULT 30,
            priority TEXT DEFAULT 'medium',
            instructions TEXT DEFAULT '',
            rotation_group TEXT DEFAULT '',
            last_completed TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Clothing Inventory ─── */
        CREATE TABLE IF NOT EXISTS clothing_inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT DEFAULT '',
            item_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            size TEXT DEFAULT '',
            quantity INTEGER DEFAULT 1,
            condition TEXT DEFAULT 'good',
            season TEXT DEFAULT 'all',
            warmth_rating INTEGER DEFAULT 3,
            waterproof INTEGER DEFAULT 0,
            material TEXT DEFAULT '',
            location TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Sanitation Supplies ─── */
        CREATE TABLE IF NOT EXISTS sanitation_supplies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'hygiene',
            quantity REAL DEFAULT 0,
            unit TEXT DEFAULT 'each',
            min_stock REAL DEFAULT 0,
            daily_usage_rate REAL DEFAULT 0,
            persons_served INTEGER DEFAULT 1,
            location TEXT DEFAULT '',
            expiration_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Morale Logs ─── */
        CREATE TABLE IF NOT EXISTS morale_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT DEFAULT '',
            date TEXT DEFAULT '',
            morale_score INTEGER DEFAULT 5,
            stress_level INTEGER DEFAULT 5,
            sleep_quality INTEGER DEFAULT 5,
            physical_health INTEGER DEFAULT 5,
            social_connection INTEGER DEFAULT 5,
            activities TEXT DEFAULT '[]',
            concerns TEXT DEFAULT '',
            positive_notes TEXT DEFAULT '',
            interventions TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Sleep Logs ─── */
        CREATE TABLE IF NOT EXISTS sleep_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT DEFAULT '',
            date TEXT DEFAULT '',
            sleep_start TEXT DEFAULT '',
            sleep_end TEXT DEFAULT '',
            duration_hours REAL DEFAULT 0,
            quality INTEGER DEFAULT 5,
            interruptions INTEGER DEFAULT 0,
            watch_duty INTEGER DEFAULT 0,
            watch_start TEXT DEFAULT '',
            watch_end TEXT DEFAULT '',
            sleep_debt_hours REAL DEFAULT 0,
            environment TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Performance Checks ─── */
        CREATE TABLE IF NOT EXISTS performance_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT DEFAULT '',
            date TEXT DEFAULT '',
            check_type TEXT DEFAULT 'routine',
            reaction_time_ms INTEGER DEFAULT 0,
            cognitive_score INTEGER DEFAULT 0,
            physical_score INTEGER DEFAULT 0,
            fatigue_level INTEGER DEFAULT 5,
            hours_awake REAL DEFAULT 0,
            hours_since_last_sleep REAL DEFAULT 0,
            ambient_temp_f REAL DEFAULT 0,
            hydration_status TEXT DEFAULT 'adequate',
            caloric_intake INTEGER DEFAULT 0,
            risk_assessment TEXT DEFAULT 'low',
            recommendations TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Grid-Down Recipes ─── */
        CREATE TABLE IF NOT EXISTS grid_down_recipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'main',
            cooking_method TEXT DEFAULT 'campfire',
            prep_time_minutes INTEGER DEFAULT 15,
            cook_time_minutes INTEGER DEFAULT 30,
            servings INTEGER DEFAULT 4,
            calories_per_serving INTEGER DEFAULT 0,
            protein_per_serving REAL DEFAULT 0,
            ingredients TEXT DEFAULT '[]',
            instructions TEXT DEFAULT '',
            water_required_ml INTEGER DEFAULT 0,
            fuel_required TEXT DEFAULT '',
            equipment_needed TEXT DEFAULT '[]',
            shelf_stable_only INTEGER DEFAULT 1,
            tags TEXT DEFAULT '[]',
            rating INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_interoperability_tables(conn):
    """Phase 16 — Interoperability & Data Exchange: import/export jobs, batch imports."""
    conn.executescript('''
        /* ─── Data Exports ─── */
        CREATE TABLE IF NOT EXISTS data_exports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            export_type TEXT NOT NULL,
            format TEXT DEFAULT 'csv',
            source_table TEXT DEFAULT '',
            filter_params TEXT DEFAULT '{}',
            record_count INTEGER DEFAULT 0,
            file_path TEXT DEFAULT '',
            file_size_bytes INTEGER DEFAULT 0,
            status TEXT DEFAULT 'pending',
            error_message TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT DEFAULT ''
        );

        /* ─── Batch Imports ─── */
        CREATE TABLE IF NOT EXISTS batch_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            import_type TEXT NOT NULL,
            format TEXT DEFAULT 'csv',
            target_table TEXT DEFAULT '',
            source_filename TEXT DEFAULT '',
            total_records INTEGER DEFAULT 0,
            imported_records INTEGER DEFAULT 0,
            skipped_records INTEGER DEFAULT 0,
            error_records INTEGER DEFAULT 0,
            column_mapping TEXT DEFAULT '{}',
            validation_errors TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT DEFAULT ''
        );
    ''')
    conn.commit()


def _create_hunting_foraging_tables(conn):
    """Phase 17 — Hunting, Foraging & Wild Food: game logs, fishing, foraging,
    traps, trade skills, preservation, wild edibles reference."""
    conn.executescript('''
        /* ─── Hunting Game Log ─── */
        CREATE TABLE IF NOT EXISTS hunting_game_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT '',
            species TEXT NOT NULL,
            game_type TEXT DEFAULT 'big_game',
            location TEXT DEFAULT '',
            gps_coords TEXT DEFAULT '',
            method TEXT DEFAULT 'rifle',
            weapon_details TEXT DEFAULT '',
            weight_lbs REAL DEFAULT 0,
            meat_yield_lbs REAL DEFAULT 0,
            field_dressed INTEGER DEFAULT 0,
            trophy INTEGER DEFAULT 0,
            license_tag TEXT DEFAULT '',
            season TEXT DEFAULT '',
            weather_conditions TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Fishing Log ─── */
        CREATE TABLE IF NOT EXISTS fishing_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT '',
            species TEXT NOT NULL,
            location TEXT DEFAULT '',
            gps_coords TEXT DEFAULT '',
            method TEXT DEFAULT 'rod_reel',
            bait_lure TEXT DEFAULT '',
            weight_lbs REAL DEFAULT 0,
            length_inches REAL DEFAULT 0,
            kept INTEGER DEFAULT 1,
            water_type TEXT DEFAULT 'freshwater',
            water_temp_f REAL DEFAULT 0,
            weather_conditions TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Foraging Log ─── */
        CREATE TABLE IF NOT EXISTS foraging_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT DEFAULT '',
            plant_name TEXT NOT NULL,
            scientific_name TEXT DEFAULT '',
            category TEXT DEFAULT 'edible_plant',
            location TEXT DEFAULT '',
            gps_coords TEXT DEFAULT '',
            quantity_harvested TEXT DEFAULT '',
            unit TEXT DEFAULT 'lbs',
            season TEXT DEFAULT '',
            habitat TEXT DEFAULT '',
            confidence_level TEXT DEFAULT 'certain',
            photo_ref TEXT DEFAULT '',
            preparation_notes TEXT DEFAULT '',
            warnings TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Traps & Snares ─── */
        CREATE TABLE IF NOT EXISTS traps_snares (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            trap_type TEXT DEFAULT 'snare',
            target_species TEXT DEFAULT '',
            location TEXT DEFAULT '',
            gps_coords TEXT DEFAULT '',
            set_date TEXT DEFAULT '',
            check_date TEXT DEFAULT '',
            check_frequency_hours INTEGER DEFAULT 24,
            status TEXT DEFAULT 'active',
            catches INTEGER DEFAULT 0,
            materials_used TEXT DEFAULT '[]',
            bait TEXT DEFAULT '',
            instructions TEXT DEFAULT '',
            legal_notes TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Wild Edibles Reference ─── */
        CREATE TABLE IF NOT EXISTS wild_edibles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            common_name TEXT NOT NULL,
            scientific_name TEXT DEFAULT '',
            category TEXT DEFAULT 'plant',
            edible_parts TEXT DEFAULT '[]',
            season_available TEXT DEFAULT '[]',
            habitat TEXT DEFAULT '',
            identification_features TEXT DEFAULT '',
            look_alikes TEXT DEFAULT '',
            preparation_methods TEXT DEFAULT '[]',
            nutritional_info TEXT DEFAULT '',
            medicinal_uses TEXT DEFAULT '',
            toxicity_warnings TEXT DEFAULT '',
            image_ref TEXT DEFAULT '',
            region TEXT DEFAULT 'north_america',
            confidence_required TEXT DEFAULT 'expert',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Trade Skills ─── */
        CREATE TABLE IF NOT EXISTS trade_skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            practitioner TEXT DEFAULT '',
            skill_level TEXT DEFAULT 'beginner',
            tools_required TEXT DEFAULT '[]',
            materials_required TEXT DEFAULT '[]',
            description TEXT DEFAULT '',
            projects_completed INTEGER DEFAULT 0,
            last_practiced TEXT DEFAULT '',
            learning_resources TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Trade Skill Projects ─── */
        CREATE TABLE IF NOT EXISTS trade_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER DEFAULT 0,
            name TEXT NOT NULL,
            description TEXT DEFAULT '',
            materials TEXT DEFAULT '[]',
            tools TEXT DEFAULT '[]',
            steps TEXT DEFAULT '[]',
            time_hours REAL DEFAULT 0,
            difficulty TEXT DEFAULT 'beginner',
            output_item TEXT DEFAULT '',
            output_quantity INTEGER DEFAULT 1,
            status TEXT DEFAULT 'planned',
            started_date TEXT DEFAULT '',
            completed_date TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Preservation Methods ─── */
        CREATE TABLE IF NOT EXISTS preservation_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            method_type TEXT DEFAULT 'canning',
            input_item TEXT DEFAULT '',
            output_item TEXT DEFAULT '',
            equipment_needed TEXT DEFAULT '[]',
            supplies_needed TEXT DEFAULT '[]',
            process_steps TEXT DEFAULT '[]',
            processing_time_hours REAL DEFAULT 0,
            shelf_life_days INTEGER DEFAULT 365,
            yield_ratio REAL DEFAULT 1.0,
            safety_notes TEXT DEFAULT '',
            temperature_requirements TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Preservation Batches ─── */
        CREATE TABLE IF NOT EXISTS preservation_batches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method_id INTEGER DEFAULT 0,
            batch_name TEXT DEFAULT '',
            date_processed TEXT DEFAULT '',
            input_quantity REAL DEFAULT 0,
            input_unit TEXT DEFAULT 'lbs',
            output_quantity REAL DEFAULT 0,
            output_unit TEXT DEFAULT 'jars',
            expiration_date TEXT DEFAULT '',
            storage_location TEXT DEFAULT '',
            quality_check TEXT DEFAULT 'good',
            processor TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Hunting Zones / Areas ─── */
        CREATE TABLE IF NOT EXISTS hunting_zones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            zone_type TEXT DEFAULT 'hunting',
            location TEXT DEFAULT '',
            gps_bounds TEXT DEFAULT '',
            terrain TEXT DEFAULT '',
            target_species TEXT DEFAULT '[]',
            season_dates TEXT DEFAULT '',
            regulations TEXT DEFAULT '',
            access_notes TEXT DEFAULT '',
            blind_stand_locations TEXT DEFAULT '[]',
            trail_cam_locations TEXT DEFAULT '[]',
            last_scouted TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_hardware_sensors_tables(conn):
    """Phase 18 — Hardware, Sensors & Mesh: IoT sensors, network devices,
    Meshtastic nodes, weather stations, GPS devices, wearables, integrations."""
    conn.executescript('''
        /* ─── IoT Sensors ─── */
        CREATE TABLE IF NOT EXISTS iot_sensors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sensor_type TEXT DEFAULT 'temperature',
            protocol TEXT DEFAULT 'mqtt',
            device_id TEXT DEFAULT '',
            location TEXT DEFAULT '',
            topic TEXT DEFAULT '',
            unit TEXT DEFAULT '',
            current_value TEXT DEFAULT '',
            last_reading_at TEXT DEFAULT '',
            min_threshold REAL DEFAULT 0,
            max_threshold REAL DEFAULT 0,
            alert_enabled INTEGER DEFAULT 0,
            calibration_offset REAL DEFAULT 0,
            battery_pct INTEGER DEFAULT 100,
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── IoT Sensor Readings (Phase 18 — distinct from Phase 1 sensor_readings) ─── */
        CREATE TABLE IF NOT EXISTS iot_sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER NOT NULL,
            value REAL DEFAULT 0,
            raw_value TEXT DEFAULT '',
            unit TEXT DEFAULT '',
            quality TEXT DEFAULT 'good',
            timestamp TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Network Devices ─── */
        CREATE TABLE IF NOT EXISTS network_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_type TEXT DEFAULT 'router',
            ip_address TEXT DEFAULT '',
            mac_address TEXT DEFAULT '',
            hostname TEXT DEFAULT '',
            manufacturer TEXT DEFAULT '',
            model TEXT DEFAULT '',
            firmware_version TEXT DEFAULT '',
            location TEXT DEFAULT '',
            vlan TEXT DEFAULT '',
            role TEXT DEFAULT 'infrastructure',
            port_count INTEGER DEFAULT 0,
            uplink_to INTEGER DEFAULT 0,
            last_seen TEXT DEFAULT '',
            status TEXT DEFAULT 'online',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Meshtastic Nodes ─── */
        CREATE TABLE IF NOT EXISTS mesh_nodes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id TEXT NOT NULL,
            long_name TEXT DEFAULT '',
            short_name TEXT DEFAULT '',
            hardware_model TEXT DEFAULT '',
            firmware_version TEXT DEFAULT '',
            role TEXT DEFAULT 'client',
            latitude REAL DEFAULT 0,
            longitude REAL DEFAULT 0,
            altitude_m REAL DEFAULT 0,
            battery_level INTEGER DEFAULT 0,
            voltage REAL DEFAULT 0,
            channel_utilization REAL DEFAULT 0,
            air_util_tx REAL DEFAULT 0,
            snr REAL DEFAULT 0,
            rssi INTEGER DEFAULT 0,
            hops_away INTEGER DEFAULT 0,
            last_heard TEXT DEFAULT '',
            status TEXT DEFAULT 'online',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Weather Stations ─── */
        CREATE TABLE IF NOT EXISTS weather_stations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            station_type TEXT DEFAULT 'personal',
            brand TEXT DEFAULT '',
            model TEXT DEFAULT '',
            protocol TEXT DEFAULT 'ecowitt',
            ip_address TEXT DEFAULT '',
            api_key TEXT DEFAULT '',
            location TEXT DEFAULT '',
            latitude REAL DEFAULT 0,
            longitude REAL DEFAULT 0,
            elevation_ft REAL DEFAULT 0,
            polling_interval_sec INTEGER DEFAULT 60,
            last_poll TEXT DEFAULT '',
            current_data TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── GPS Devices ─── */
        CREATE TABLE IF NOT EXISTS gps_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_type TEXT DEFAULT 'handheld',
            brand TEXT DEFAULT '',
            model TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            connection_type TEXT DEFAULT 'usb',
            port TEXT DEFAULT '',
            baud_rate INTEGER DEFAULT 9600,
            last_fix_lat REAL DEFAULT 0,
            last_fix_lon REAL DEFAULT 0,
            last_fix_alt REAL DEFAULT 0,
            last_fix_time TEXT DEFAULT '',
            accuracy_m REAL DEFAULT 0,
            satellites INTEGER DEFAULT 0,
            battery_pct INTEGER DEFAULT 100,
            status TEXT DEFAULT 'disconnected',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Wearable Health Devices ─── */
        CREATE TABLE IF NOT EXISTS wearable_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            device_type TEXT DEFAULT 'fitness_tracker',
            brand TEXT DEFAULT '',
            model TEXT DEFAULT '',
            wearer TEXT DEFAULT '',
            connection_type TEXT DEFAULT 'bluetooth',
            last_sync TEXT DEFAULT '',
            battery_pct INTEGER DEFAULT 100,
            current_data TEXT DEFAULT '{}',
            status TEXT DEFAULT 'paired',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Integration Configs ─── */
        CREATE TABLE IF NOT EXISTS integration_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            integration_type TEXT DEFAULT 'mqtt',
            endpoint_url TEXT DEFAULT '',
            api_key TEXT DEFAULT '',
            username TEXT DEFAULT '',
            auth_token TEXT DEFAULT '',
            config_json TEXT DEFAULT '{}',
            polling_interval_sec INTEGER DEFAULT 60,
            last_sync TEXT DEFAULT '',
            sync_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'disabled',
            error_message TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_platform_security_tables(conn):
    """Phase 19 — Platform, Deployment & Security: users, sessions, permissions,
    access logs, deployment configs, performance metrics."""
    conn.executescript('''
        /* ─── Users ─── */
        CREATE TABLE IF NOT EXISTS app_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            display_name TEXT DEFAULT '',
            pin_hash TEXT DEFAULT '',
            password_hash TEXT DEFAULT '',
            role TEXT DEFAULT 'user',
            permissions TEXT DEFAULT '[]',
            is_active INTEGER DEFAULT 1,
            last_login TEXT DEFAULT '',
            login_count INTEGER DEFAULT 0,
            failed_attempts INTEGER DEFAULT 0,
            locked_until TEXT DEFAULT '',
            settings TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Sessions ─── */
        CREATE TABLE IF NOT EXISTS app_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            session_token TEXT NOT NULL,
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            device_info TEXT DEFAULT '',
            expires_at TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_activity TEXT DEFAULT ''
        );

        /* ─── Platform Access Log (renamed from access_logs in v7.27.0
              to disambiguate from access_log used by physical security) ─── */
        CREATE TABLE IF NOT EXISTS platform_access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            action TEXT DEFAULT '',
            resource TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            user_agent TEXT DEFAULT '',
            status_code INTEGER DEFAULT 200,
            detail TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Deployment Configs ─── */
        CREATE TABLE IF NOT EXISTS deployment_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            config_type TEXT DEFAULT 'general',
            description TEXT DEFAULT '',
            config_data TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            applied_at TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Performance Metrics ─── */
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_type TEXT DEFAULT 'startup',
            metric_name TEXT DEFAULT '',
            value REAL DEFAULT 0,
            unit TEXT DEFAULT 'ms',
            context TEXT DEFAULT '{}',
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _create_specialized_modules_tables(conn):
    """Phase 20 — Specialized Modules & Community: caches, pets, youth,
    end-of-life, procurement, intel, fabrication, badges, calendar, legal, drones."""
    conn.executescript('''
        /* ─── Supply Caches ─── */
        CREATE TABLE IF NOT EXISTS supply_caches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            cache_type TEXT DEFAULT 'general',
            location_description TEXT DEFAULT '',
            gps_coords TEXT DEFAULT '',
            access_instructions TEXT DEFAULT '',
            concealment_method TEXT DEFAULT '',
            container_type TEXT DEFAULT '',
            contents TEXT DEFAULT '[]',
            last_checked TEXT DEFAULT '',
            condition TEXT DEFAULT 'good',
            known_by TEXT DEFAULT '[]',
            expiration_date TEXT DEFAULT '',
            security_level TEXT DEFAULT 'standard',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Pets & Companion Animals ─── */
        CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            species TEXT DEFAULT 'dog',
            breed TEXT DEFAULT '',
            age_years REAL DEFAULT 0,
            weight_lbs REAL DEFAULT 0,
            microchip_id TEXT DEFAULT '',
            medical_conditions TEXT DEFAULT '[]',
            medications TEXT DEFAULT '[]',
            vaccination_dates TEXT DEFAULT '{}',
            food_type TEXT DEFAULT '',
            daily_food_amount TEXT DEFAULT '',
            food_supply_days INTEGER DEFAULT 0,
            veterinarian TEXT DEFAULT '',
            evacuation_carrier TEXT DEFAULT '',
            temperament TEXT DEFAULT '',
            special_needs TEXT DEFAULT '',
            photo_ref TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Youth Programs ─── */
        CREATE TABLE IF NOT EXISTS youth_programs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            program_type TEXT DEFAULT 'education',
            age_range TEXT DEFAULT '',
            description TEXT DEFAULT '',
            curriculum TEXT DEFAULT '[]',
            materials_needed TEXT DEFAULT '[]',
            instructor TEXT DEFAULT '',
            schedule TEXT DEFAULT '',
            participants TEXT DEFAULT '[]',
            skills_taught TEXT DEFAULT '[]',
            progress_notes TEXT DEFAULT '',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── End-of-Life Plans ─── */
        CREATE TABLE IF NOT EXISTS end_of_life_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT NOT NULL,
            plan_type TEXT DEFAULT 'general',
            wishes TEXT DEFAULT '',
            medical_directives TEXT DEFAULT '',
            organ_donor INTEGER DEFAULT 0,
            body_disposition TEXT DEFAULT '',
            memorial_wishes TEXT DEFAULT '',
            important_documents TEXT DEFAULT '[]',
            digital_accounts TEXT DEFAULT '[]',
            beneficiaries TEXT DEFAULT '[]',
            executor TEXT DEFAULT '',
            attorney TEXT DEFAULT '',
            insurance_info TEXT DEFAULT '',
            last_updated_by TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Procurement Lists ─── */
        CREATE TABLE IF NOT EXISTS procurement_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            list_type TEXT DEFAULT 'shopping',
            priority TEXT DEFAULT 'medium',
            items TEXT DEFAULT '[]',
            budget REAL DEFAULT 0,
            spent REAL DEFAULT 0,
            supplier TEXT DEFAULT '',
            due_date TEXT DEFAULT '',
            assigned_to TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Intel Collection (PIR) ─── */
        CREATE TABLE IF NOT EXISTS intel_collection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            intel_type TEXT DEFAULT 'humint',
            priority_info_req TEXT DEFAULT '',
            source TEXT DEFAULT '',
            source_reliability TEXT DEFAULT 'unknown',
            info_credibility TEXT DEFAULT 'unknown',
            classification TEXT DEFAULT 'unclassified',
            date_collected TEXT DEFAULT '',
            location TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            raw_data TEXT DEFAULT '',
            analysis TEXT DEFAULT '',
            actionable INTEGER DEFAULT 0,
            dissemination TEXT DEFAULT '[]',
            expiry_date TEXT DEFAULT '',
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Fabrication Projects (3D Printing) ─── */
        CREATE TABLE IF NOT EXISTS fabrication_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            project_type TEXT DEFAULT '3d_print',
            description TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            material TEXT DEFAULT 'pla',
            material_amount TEXT DEFAULT '',
            printer_model TEXT DEFAULT '',
            print_settings TEXT DEFAULT '{}',
            estimated_time_hours REAL DEFAULT 0,
            actual_time_hours REAL DEFAULT 0,
            copies_made INTEGER DEFAULT 0,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'queued',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Badges & Achievements ─── */
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            description TEXT DEFAULT '',
            icon TEXT DEFAULT '',
            criteria TEXT DEFAULT '',
            points INTEGER DEFAULT 10,
            rarity TEXT DEFAULT 'common',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Badge Awards ─── */
        CREATE TABLE IF NOT EXISTS badge_awards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            badge_id INTEGER NOT NULL,
            person TEXT NOT NULL,
            awarded_date TEXT DEFAULT '',
            awarded_by TEXT DEFAULT 'system',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Seasonal Events ─── */
        CREATE TABLE IF NOT EXISTS seasonal_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            event_type TEXT DEFAULT 'seasonal',
            date TEXT DEFAULT '',
            recurrence TEXT DEFAULT 'yearly',
            description TEXT DEFAULT '',
            tasks TEXT DEFAULT '[]',
            reminders TEXT DEFAULT '[]',
            category TEXT DEFAULT 'preparedness',
            completed INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Legal Documents ─── */
        CREATE TABLE IF NOT EXISTS legal_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            doc_type TEXT DEFAULT 'general',
            person TEXT DEFAULT '',
            issuing_authority TEXT DEFAULT '',
            document_number TEXT DEFAULT '',
            issue_date TEXT DEFAULT '',
            expiry_date TEXT DEFAULT '',
            file_path TEXT DEFAULT '',
            storage_location TEXT DEFAULT '',
            renewal_reminder INTEGER DEFAULT 0,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Drones ─── */
        CREATE TABLE IF NOT EXISTS drones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            drone_type TEXT DEFAULT 'quadcopter',
            manufacturer TEXT DEFAULT '',
            model TEXT DEFAULT '',
            serial_number TEXT DEFAULT '',
            registration TEXT DEFAULT '',
            weight_grams INTEGER DEFAULT 0,
            max_flight_time_min INTEGER DEFAULT 0,
            max_range_m INTEGER DEFAULT 0,
            camera_specs TEXT DEFAULT '',
            battery_count INTEGER DEFAULT 1,
            battery_type TEXT DEFAULT '',
            firmware_version TEXT DEFAULT '',
            total_flights INTEGER DEFAULT 0,
            total_flight_hours REAL DEFAULT 0,
            last_flight TEXT DEFAULT '',
            condition TEXT DEFAULT 'operational',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Drone Flight Logs ─── */
        CREATE TABLE IF NOT EXISTS drone_flights (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            drone_id INTEGER NOT NULL,
            date TEXT DEFAULT '',
            mission_type TEXT DEFAULT 'recon',
            location TEXT DEFAULT '',
            gps_coords TEXT DEFAULT '',
            duration_min INTEGER DEFAULT 0,
            max_altitude_m INTEGER DEFAULT 0,
            distance_km REAL DEFAULT 0,
            battery_start_pct INTEGER DEFAULT 100,
            battery_end_pct INTEGER DEFAULT 0,
            weather_conditions TEXT DEFAULT '',
            observations TEXT DEFAULT '',
            media_captured TEXT DEFAULT '[]',
            pilot TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Fitness Logs ─── */
        CREATE TABLE IF NOT EXISTS fitness_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person TEXT DEFAULT '',
            date TEXT DEFAULT '',
            exercise_type TEXT DEFAULT 'cardio',
            activity TEXT DEFAULT '',
            duration_min INTEGER DEFAULT 0,
            distance_km REAL DEFAULT 0,
            reps INTEGER DEFAULT 0,
            sets INTEGER DEFAULT 0,
            weight_lbs REAL DEFAULT 0,
            calories_burned INTEGER DEFAULT 0,
            heart_rate_avg INTEGER DEFAULT 0,
            heart_rate_max INTEGER DEFAULT 0,
            perceived_exertion INTEGER DEFAULT 5,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        /* ─── Community Content Packs ─── */
        CREATE TABLE IF NOT EXISTS content_packs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            pack_type TEXT DEFAULT 'knowledge',
            version TEXT DEFAULT '1.0.0',
            author TEXT DEFAULT '',
            description TEXT DEFAULT '',
            contents_manifest TEXT DEFAULT '[]',
            size_bytes INTEGER DEFAULT 0,
            install_date TEXT DEFAULT '',
            source_url TEXT DEFAULT '',
            checksum TEXT DEFAULT '',
            status TEXT DEFAULT 'installed',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    conn.commit()


def _init_db_inner(conn):
    _create_core_tables(conn)
    _create_comms_media_tables(conn)
    _create_federation_tables(conn)
    _create_medical_security_tables(conn)
    _create_power_garden_tables(conn)
    _create_extended_tables(conn)
    _create_water_financial_vehicle_loadout_tables(conn)
    _create_pace_evac_container_tables(conn)
    _create_readiness_alerts_threat_drill_tables(conn)
    _create_data_foundation_tables(conn)
    _create_consumption_water_budget_tables(conn)
    _create_meal_planning_tables(conn)
    _create_movement_ops_tables(conn)
    _create_tactical_comms_tables(conn)
    _create_land_assessment_tables(conn)
    _create_medical_phase2_tables(conn)
    _create_training_knowledge_tables(conn)
    _create_group_ops_tables(conn)
    _create_security_opsec_tables(conn)
    _create_agriculture_tables(conn)
    _create_disaster_modules_tables(conn)
    _create_daily_living_tables(conn)
    _create_interoperability_tables(conn)
    _create_hunting_foraging_tables(conn)
    _create_hardware_sensors_tables(conn)
    _create_platform_security_tables(conn)
    _create_specialized_modules_tables(conn)
    _apply_column_migrations(conn)
    _migrate_access_logs(conn)
    _create_indexes(conn)
    _create_fts5_tables(conn)
    _seed_upc_database(conn)


def _create_fts5_tables(conn):
    """v7.29.0 (audit M5): FTS5 full-text search virtual tables for the
    highest-traffic search targets. Content-external mode mirrors rowid +
    indexed columns of the base tables; triggers keep the FTS index in
    sync on INSERT/UPDATE/DELETE. On first creation the index is populated
    from existing rows via the `rebuild` command.

    Scope (5 tables): notes, inventory, contacts, documents, waypoints.
    Other LIKE-based searches (conversations messages, freq_database,
    skills, etc.) still use LIKE — can be expanded incrementally without
    breaking callers.

    FTS5 is shipped with the Python stdlib sqlite3 on all supported
    platforms. If the extension is somehow unavailable, failure is logged
    and the app falls back to LIKE search — nothing else breaks.
    """
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE _fts5_probe")
    except sqlite3.OperationalError as e:
        _log.warning('FTS5 not available — keyword search will use LIKE fallback: %s', e)
        return

    specs = [
        ('notes_fts', 'notes', ['title', 'content']),
        ('inventory_fts', 'inventory', ['name', 'location', 'notes']),
        ('contacts_fts', 'contacts', ['name', 'callsign', 'role', 'skills', 'notes']),
        ('documents_fts', 'documents', ['filename']),
        ('waypoints_fts', 'waypoints', ['name', 'category', 'notes']),
    ]

    for fts_table, src_table, cols in specs:
        cols_csv = ', '.join(cols)
        new_cols_csv = ', '.join('new.' + c for c in cols)
        old_cols_csv = ', '.join('old.' + c for c in cols)
        already = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (fts_table,),
        ).fetchone()
        conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS {fts_table} USING fts5("
            f"{cols_csv}, content='{src_table}', content_rowid='id', "
            f"tokenize='porter unicode61 remove_diacritics 2')"
        )
        conn.executescript(f'''
            CREATE TRIGGER IF NOT EXISTS {fts_table}_ai AFTER INSERT ON {src_table} BEGIN
                INSERT INTO {fts_table}(rowid, {cols_csv}) VALUES (new.id, {new_cols_csv});
            END;
            CREATE TRIGGER IF NOT EXISTS {fts_table}_ad AFTER DELETE ON {src_table} BEGIN
                INSERT INTO {fts_table}({fts_table}, rowid, {cols_csv}) VALUES('delete', old.id, {old_cols_csv});
            END;
            CREATE TRIGGER IF NOT EXISTS {fts_table}_au AFTER UPDATE ON {src_table} BEGIN
                INSERT INTO {fts_table}({fts_table}, rowid, {cols_csv}) VALUES('delete', old.id, {old_cols_csv});
                INSERT INTO {fts_table}(rowid, {cols_csv}) VALUES (new.id, {new_cols_csv});
            END;
        ''')
        if not already:
            try:
                conn.execute(f"INSERT INTO {fts_table}({fts_table}) VALUES('rebuild')")
            except sqlite3.OperationalError as e:
                _log.warning('FTS5 rebuild failed for %s: %s', fts_table, e)
    conn.commit()


def fts5_available(conn=None):
    """Return True if FTS5 virtual tables were created successfully."""
    own = False
    if conn is None:
        conn = get_db()
        own = True
    try:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='notes_fts'"
        ).fetchone()
        return row is not None
    finally:
        if own:
            conn.close()


def _migrate_access_logs(conn):
    """Audit M4: rename `access_logs` (platform/API audit log) to
    `platform_access_log` to disambiguate from `access_log` (physical entry
    log used by security.py). Idempotent — if old table exists, copy rows
    into the new table and drop the old one. Safe to run on every startup.
    """
    try:
        old_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='access_logs'"
        ).fetchone()
        if not old_exists:
            return
        # Both tables share the same schema; INSERT OR IGNORE preserves any
        # rows the new table already has (in case of partial migrations).
        conn.execute(
            'INSERT OR IGNORE INTO platform_access_log '
            '(id, user_id, action, resource, ip_address, user_agent, '
            ' status_code, detail, created_at) '
            'SELECT id, user_id, action, resource, ip_address, user_agent, '
            ' status_code, detail, created_at FROM access_logs'
        )
        conn.execute('DROP TABLE access_logs')
        conn.commit()
    except Exception as e:
        _log.warning('access_logs migration skipped: %s', e)


def _seed_upc_database(conn):
    """Seed the UPC database with common survival/prep items if empty."""
    count = conn.execute('SELECT COUNT(*) FROM upc_database').fetchone()[0]
    if count > 0:
        return  # Already seeded

    # (upc, name, category, brand, size, unit, default_shelf_life_days)
    items = [
        # ─── Food (27 items) ───
        ('041331024266', 'Black Beans (canned)', 'Food', 'Bush\'s', '15 oz', 'can', 1825),
        ('041331025744', 'Pinto Beans (canned)', 'Food', 'Bush\'s', '15 oz', 'can', 1825),
        ('080000525734', 'Chunk Light Tuna', 'Food', 'Bumble Bee', '5 oz', 'can', 1825),
        ('017400100083', 'Long Grain White Rice', 'Food', 'Riceland', '2 lb', 'bag', 3650),
        ('017400100106', 'Long Grain White Rice', 'Food', 'Riceland', '5 lb', 'bag', 3650),
        ('076808006131', 'Spaghetti Pasta', 'Food', 'Barilla', '16 oz', 'box', 1095),
        ('051500255162', 'Creamy Peanut Butter', 'Food', 'Jif', '16 oz', 'jar', 730),
        ('030000065730', 'Old Fashioned Oats', 'Food', 'Quaker', '42 oz', 'canister', 730),
        ('024300061363', 'Pure Honey', 'Food', 'Sue Bee', '16 oz', 'bottle', 36500),
        ('050000340712', 'Instant Nonfat Dry Milk', 'Food', 'Carnation', '9.6 oz', 'box', 1095),
        ('021130126026', 'MRE Meal Ready to Eat', 'Food', 'Sopakco', '1 meal', 'each', 1825),
        ('020000124407', 'Sweet Peas (canned)', 'Food', 'Del Monte', '15 oz', 'can', 1825),
        ('024000163695', 'Fruit Cocktail (canned)', 'Food', 'Del Monte', '15 oz', 'can', 1825),
        ('044000003319', 'Original Beef Jerky', 'Food', 'Jack Link\'s', '2.85 oz', 'bag', 365),
        ('041789002113', 'Ramen Noodle Soup - Chicken', 'Food', 'Maruchan', '3 oz', 'pack', 365),
        ('051000025111', 'Condensed Chicken Noodle Soup', 'Food', 'Campbell\'s', '10.75 oz', 'can', 1825),
        ('041129070574', 'Extra Virgin Olive Oil', 'Food', 'Bertolli', '17 oz', 'bottle', 730),
        ('024600010603', 'Iodized Salt', 'Food', 'Morton', '26 oz', 'canister', 36500),
        ('049800110069', 'Granulated White Sugar', 'Food', 'Domino', '4 lb', 'bag', 36500),
        ('051500280058', 'All Purpose Flour', 'Food', 'Pillsbury', '5 lb', 'bag', 365),
        ('071524017126', 'Great Northern Beans (dried)', 'Food', 'Goya', '1 lb', 'bag', 3650),
        ('054100003324', 'Chunk Chicken Breast', 'Food', 'Hormel', '10 oz', 'can', 1825),
        ('037600215114', 'Spam Classic', 'Food', 'Spam', '12 oz', 'can', 1825),
        ('016000264601', 'Nature Valley Oats \'N Honey Granola Bars', 'Food', 'Nature Valley', '12 ct', 'box', 365),
        ('021000658756', 'Kraft Mac & Cheese Original', 'Food', 'Kraft', '7.25 oz', 'box', 730),
        ('020000122540', 'Whole Kernel Corn (canned)', 'Food', 'Green Giant', '15.25 oz', 'can', 1825),
        ('020000124674', 'Diced Tomatoes (canned)', 'Food', 'Hunt\'s', '14.5 oz', 'can', 1825),

        # ─── Water (8 items) ───
        ('012000001024', 'Purified Drinking Water', 'Water', 'Aquafina', '16.9 oz', 'bottle', 730),
        ('049000028904', 'Purified Water', 'Water', 'Dasani', '16.9 oz', 'bottle', 730),
        ('078742225654', 'Spring Water Gallon Jug', 'Water', 'Great Value', '1 gal', 'jug', 730),
        ('855801005048', 'LifeStraw Personal Water Filter', 'Water', 'LifeStraw', '1 unit', 'each', 1825),
        ('891274000103', 'Water Purification Tablets', 'Water', 'Potable Aqua', '50 ct', 'bottle', 1460),
        ('050716002041', 'Sawyer Mini Water Filter', 'Water', 'Sawyer', '1 unit', 'each', 3650),
        ('044600010281', 'Regular Bleach (purification)', 'Water', 'Clorox', '64 oz', 'bottle', 365),
        ('071254002019', 'WaterBOB Emergency Water Storage', 'Water', 'WaterBOB', '100 gal', 'each', 3650),

        # ─── Medical (15 items) ───
        ('381370044314', 'Adhesive Bandages Assorted', 'Medical', 'Band-Aid', '100 ct', 'box', 1825),
        ('191565880708', 'Sterile Gauze Pads 4x4', 'Medical', 'Dynarex', '25 ct', 'box', 1825),
        ('381370048060', 'Waterproof Medical Tape', 'Medical', 'Johnson & Johnson', '1 in x 10 yd', 'roll', 1825),
        ('305730169301', 'Ibuprofen 200mg Tablets', 'Medical', 'Advil', '200 ct', 'bottle', 1095),
        ('300450449108', 'Acetaminophen 500mg Extra Strength', 'Medical', 'Tylenol', '100 ct', 'bottle', 1095),
        ('312547781183', 'Triple Antibiotic Ointment', 'Medical', 'Neosporin', '1 oz', 'tube', 1095),
        ('305210016323', 'Hydrogen Peroxide 3%', 'Medical', 'Equate', '32 oz', 'bottle', 1095),
        ('305212530161', '91% Isopropyl Alcohol', 'Medical', 'Equate', '32 oz', 'bottle', 1095),
        ('819731011037', 'CAT Tourniquet Gen 7', 'Medical', 'NAR', '1 unit', 'each', 1825),
        ('819731010078', 'HyFin Vent Chest Seal Twin Pack', 'Medical', 'NAR', '2 ct', 'pack', 1825),
        ('819731010481', 'SAM Splint 36 inch', 'Medical', 'SAM Medical', '1 unit', 'each', 3650),
        ('034197002059', 'Moleskin Plus Padding', 'Medical', 'Dr. Scholl\'s', '3 ct', 'pack', 1825),
        ('816140010838', 'Oral Rehydration Salts', 'Medical', 'DripDrop', '8 ct', 'box', 730),
        ('300450170125', 'Benadryl Allergy 25mg', 'Medical', 'Benadryl', '100 ct', 'bottle', 1095),
        ('041167100103', 'Imodium A-D Anti-Diarrheal', 'Medical', 'Imodium', '24 ct', 'box', 1095),

        # ─── Batteries/Power (8 items) ───
        ('041333030012', 'AA Batteries (Duracell)', 'Batteries/Power', 'Duracell', '20 pk', 'pack', 3650),
        ('039800011329', 'AA Batteries (Energizer)', 'Batteries/Power', 'Energizer', '20 pk', 'pack', 3650),
        ('041333044002', 'AAA Batteries (Duracell)', 'Batteries/Power', 'Duracell', '16 pk', 'pack', 3650),
        ('041333000060', 'D Cell Batteries (Duracell)', 'Batteries/Power', 'Duracell', '4 pk', 'pack', 3650),
        ('041333016016', '9V Battery (Duracell)', 'Batteries/Power', 'Duracell', '2 pk', 'pack', 3650),
        ('039800040985', 'CR123A Lithium Battery', 'Batteries/Power', 'Energizer', '2 pk', 'pack', 3650),
        ('708431100251', '18650 Rechargeable Battery 3500mAh', 'Batteries/Power', 'Panasonic', '2 pk', 'pack', 1825),
        ('840101202015', 'USB Power Bank 20000mAh', 'Batteries/Power', 'Anker', '1 unit', 'each', 1825),

        # ─── Gear (10 items) ───
        ('024099002318', '550 Paracord 100ft', 'Gear', 'Paracord Planet', '100 ft', 'hank', 3650),
        ('075353091012', 'Duct Tape Heavy Duty', 'Gear', '3M', '1.88 in x 60 yd', 'roll', 3650),
        ('078628080056', 'Cable Ties 8 inch (100 ct)', 'Gear', 'Gardner Bender', '100 ct', 'bag', 3650),
        ('044600315409', 'Strike Anywhere Matches', 'Gear', 'Diamond', '250 ct', 'box', 3650),
        ('070330624115', 'BIC Classic Lighter', 'Gear', 'BIC', '1 unit', 'each', 3650),
        ('783583961554', 'Ferro Rod Fire Starter', 'Gear', 'bayite', '6 in', 'each', 36500),
        ('816511010009', 'Heavy Duty Tarp 8x10', 'Gear', 'Everbilt', '8 x 10 ft', 'each', 1825),
        ('091444200203', 'Emergency Mylar Blanket', 'Gear', 'Swiss Safe', '2 pk', 'pack', 3650),
        ('079340687042', 'Glow Sticks 12 hr (12 pk)', 'Gear', 'Cyalume', '12 ct', 'pack', 1460),
        ('013700835414', 'Contractor Trash Bags 42 gal', 'Gear', 'Glad', '20 ct', 'box', 3650),

        # ─── Hygiene (8 items) ───
        ('037000388876', 'Ivory Bar Soap', 'Hygiene', 'Ivory', '10 pk', 'pack', 1095),
        ('037000449652', 'Crest Cavity Protection Toothpaste', 'Hygiene', 'Crest', '5.7 oz', 'tube', 730),
        ('021130235018', 'Hand Sanitizer 8 oz', 'Hygiene', 'Purell', '8 oz', 'bottle', 1095),
        ('037000862376', 'Charmin Toilet Paper', 'Hygiene', 'Charmin', '12 mega rolls', 'pack', 3650),
        ('036000431063', 'Huggies Simply Clean Wipes', 'Hygiene', 'Huggies', '64 ct', 'pack', 730),
        ('036000196207', 'U by Kotex Security Maxi Pads', 'Hygiene', 'Kotex', '36 ct', 'box', 1825),
        ('044600010502', 'Clorox Disinfecting Bleach', 'Hygiene', 'Clorox', '81 oz', 'bottle', 365),
        ('013700835216', 'ForceFlex Tall Kitchen Trash Bags', 'Hygiene', 'Glad', '80 ct', 'box', 3650),
    ]

    for upc, name, category, brand, size, unit, shelf_life in items:
        try:
            conn.execute(
                'INSERT OR IGNORE INTO upc_database (upc, name, category, brand, size, unit, default_shelf_life_days) VALUES (?, ?, ?, ?, ?, ?, ?)',
                (upc, name, category, brand, size, unit, shelf_life)
            )
        except Exception:
            pass
    conn.commit()
    _log.info(f'Seeded UPC database with {len(items)} items')
