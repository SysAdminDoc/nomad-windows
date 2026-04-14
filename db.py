"""SQLite database for service state and settings."""

import sqlite3
import os
import glob
import logging
import threading
from contextlib import contextmanager
import config

_log = logging.getLogger('nomad.db')


def get_db_path():
    db_path = config.get_config_value('db_path')
    if isinstance(db_path, str) and db_path:
        return db_path
    data_dir = config.get_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, 'nomad.db')


_wal_set = False
_migration_lock = threading.Lock()


def get_db():
    global _wal_set
    db_path = get_db_path()
    try:
        conn = sqlite3.connect(db_path, timeout=30, uri=db_path.startswith('file:'))
        conn.row_factory = sqlite3.Row
        # WAL mode is persistent on the database file — only set once per process
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


@contextmanager
def db_session():
    """Context manager for DB connections with automatic close.

    Usage:
        with db_session() as db:
            db.execute(...)
            db.commit()
    """
    conn = get_db()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def log_activity(event: str, service: str = None, detail: str = None, level: str = 'info'):
    """Log an activity event to the DB."""
    try:
        with db_session() as conn:
            conn.execute('INSERT INTO activity_log (event, service, detail, level) VALUES (?, ?, ?, ?)',
                         (event, service, detail, level))
            conn.commit()
    except (sqlite3.OperationalError, sqlite3.InterfaceError) as e:
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
    # Use SQLite backup API for WAL-safe copies
    src = sqlite3.connect(db_path, timeout=30)
    try:
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
                conn.executescript(sql)
                conn.execute(
                    'INSERT OR IGNORE INTO _migrations (filename) VALUES (?)', (filename,)
                )
                conn.commit()
                applied.add(filename)
                _log.info('Migration applied: %s', filename)
            except Exception:
                conn.rollback()
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
    _apply_column_migrations(conn)
    _create_indexes(conn)
    _seed_upc_database(conn)


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
