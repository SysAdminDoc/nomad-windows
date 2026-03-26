"""SQLite database for service state and settings."""

import sqlite3
import os
import logging
from contextlib import contextmanager
from config import get_data_dir

_log = logging.getLogger('nomad.db')


def get_db_path():
    return os.path.join(get_data_dir(), 'nomad.db')


def get_db():
    conn = sqlite3.connect(get_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    # Register on flask.g so teardown_appcontext can auto-close leaked connections
    try:
        from flask import g, has_app_context
        if has_app_context():
            g._db_conn = conn
    except Exception:
        pass
    return conn


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
    finally:
        conn.close()


def log_activity(event: str, service: str = None, detail: str = None, level: str = 'info'):
    """Log an activity event to the DB."""
    try:
        with db_session() as conn:
            conn.execute('INSERT INTO activity_log (event, service, detail, level) VALUES (?, ?, ?, ?)',
                         (event, service, detail, level))
            conn.commit()
    except Exception as e:
        _log.debug(f'Failed to log activity: {e}')


def backup_db():
    """Create a timestamped backup of the database using SQLite backup API."""
    db_path = get_db_path()
    if not os.path.isfile(db_path):
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


def init_db():
    conn = get_db()
    try:
        _init_db_inner(conn)
    finally:
        conn.close()


def _init_db_inner(conn):
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
            color TEXT DEFAULT '#ff0000',
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

        CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry TEXT NOT NULL,
            mood TEXT DEFAULT '',
            tags TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

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
    ''')
    conn.commit()

    # Schema migrations FIRST (before indexes that depend on new columns)
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
    ]:
        try:
            conn.execute(migration)
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists

    # Performance indexes (after migrations so columns exist)
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
        'CREATE INDEX IF NOT EXISTS idx_inventory_lot ON inventory(lot_number)',
        'CREATE INDEX IF NOT EXISTS idx_documents_workspace ON documents(workspace_id)',
        'CREATE INDEX IF NOT EXISTS idx_notes_journal ON notes(is_journal, created_at DESC)',
    ]:
        try:
            conn.execute(idx)
        except sqlite3.OperationalError:
            pass  # Index already exists or related issue
    conn.commit()
