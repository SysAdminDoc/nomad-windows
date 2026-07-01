"""SQLite database for service state and settings."""

import atexit
import sqlite3
import os
import glob
import logging
import queue
import threading
from contextlib import contextmanager
import config
from db_schema import *  # noqa: F403
from db_seeds import *  # noqa: F403

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

atexit.register(lambda: _pool_clear())


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


def pool_shutdown():
    """Drain and close all pooled connections. Call at process exit."""
    _pool_clear()


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
        # Clear flask.g binding so teardown_appcontext doesn't try to
        # close an already-closed connection and generate a needless exception.
        try:
            from flask import g, has_app_context
            if has_app_context() and getattr(g, '_db_conn', None) is conn:
                g._db_conn = None
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
    """Create a timestamped backup of the database using SQLite backup API.

    Writes to a `.tmp` file first and atomically renames on success so that a
    crash mid-backup can't leave behind a truncated file with the canonical
    name. Backup files are chmod'd to 0o600 on POSIX to prevent sibling
    users from reading them.
    """
    db_path = get_db_path()
    if db_path.startswith('file:') or not os.path.isfile(db_path):
        return
    backup_dir = os.path.join(os.path.dirname(db_path), 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    from datetime import datetime
    backup_path = os.path.join(backup_dir, f'nomad_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
    tmp_path = backup_path + '.tmp'
    # Use SQLite backup API for WAL-safe copies.
    # TRUNCATE checkpoint flushes all WAL frames into the main DB and truncates
    # the WAL file, guaranteeing backup() captures every committed transaction.
    # Fall back to PASSIVE if the database is busy (avoids blocking writers
    # indefinitely during normal operation — startup/shutdown backups are the
    # only callers and contention there is rare). A PASSIVE checkpoint may
    # leave a few uncommitted WAL frames outside the backup, which is an
    # acceptable tradeoff for not blocking live writers.
    src = sqlite3.connect(db_path, timeout=30)
    try:
        try:
            src.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        except sqlite3.OperationalError:
            try:
                src.execute('PRAGMA wal_checkpoint(PASSIVE)')
            except sqlite3.OperationalError as e:
                _log.debug('Backup checkpoint skipped: %s', e)
        dst = sqlite3.connect(tmp_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    except Exception:
        # Roll back the half-written tmp file so we don't leak cruft.
        try:
            if os.path.isfile(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        src.close()
        raise
    else:
        src.close()
    try:
        os.replace(tmp_path, backup_path)
    except OSError as e:
        _log.warning('Could not finalize backup %s: %s', backup_path, e)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        return
    # POSIX: restrict backup readability to the current user.
    if os.name == 'posix':
        try:
            os.chmod(backup_path, 0o600)
        except OSError as e:
            _log.debug('Could not chmod backup %s: %s', backup_path, e)
    # Prune old backups (keep newest 5). Log failures — silent OS errors here
    # have masked real issues (locked files, full disks) in past incidents.
    try:
        backups = sorted(
            [os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
             if f.endswith('.db') and not f.endswith('.tmp.db')],
            key=os.path.getmtime,
        )
    except OSError as e:
        _log.warning('Could not list backup directory for pruning: %s', e)
        return
    for old in backups[:-5]:
        try:
            os.remove(old)
        except OSError as e:
            _log.warning('Failed to prune old backup %s: %s', old, e)


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
                #
                # Use ``sqlite3.complete_statement`` to handle statements
                # containing embedded semicolons — e.g. CREATE TRIGGER
                # ... BEGIN ...; ...; END; — which a naive ``sql.split(';')``
                # would mangle into syntax errors.
                conn.execute('BEGIN IMMEDIATE')
                buffer = ''
                for line in sql.splitlines(keepends=True):
                    buffer += line
                    if sqlite3.complete_statement(buffer):
                        stmt = buffer.strip()
                        if stmt:
                            conn.execute(stmt)
                        buffer = ''
                # Trailing content without a final ; — treat as one statement
                trailing = buffer.strip()
                if trailing:
                    conn.execute(trailing)
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


# V8-01: Schema version gate — skip 935 SQL statements on subsequent starts
_SCHEMA_VERSION = 57  # v7.62: CE-03/04/13/15 Field Medicine — expanded meds, interactions, pediatric, 50 herbs


def init_db():
    conn = get_db()
    try:
        # Check if schema is already at current version
        try:
            row = conn.execute(
                "SELECT value FROM _meta WHERE key = 'schema_version'"
            ).fetchone()
            if row and int(row[0]) >= _SCHEMA_VERSION:
                _log.debug('Schema version %s is current — skipping init', row[0])
                # Still prune old activity log
                try:
                    conn.execute("DELETE FROM activity_log WHERE created_at < datetime('now', '-90 days')")
                    conn.commit()
                except Exception:
                    pass
                return
        except Exception:
            pass  # _meta table doesn't exist yet — first run

        _init_db_inner(conn)
        apply_migrations(conn)

        # Write schema version marker
        conn.execute('''
            CREATE TABLE IF NOT EXISTS _meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute(
            "INSERT OR REPLACE INTO _meta (key, value) VALUES ('schema_version', ?)",
            (str(_SCHEMA_VERSION),)
        )
        conn.commit()

        # Prune old activity log entries (older than 90 days)
        try:
            conn.execute("DELETE FROM activity_log WHERE created_at < datetime('now', '-90 days')")
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


_COLUMN_MIGRATION_VERSION = 1

_COLUMN_MIGRATIONS = {
    1: [
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
        'ALTER TABLE garden_plots ADD COLUMN lat REAL',
        'ALTER TABLE garden_plots ADD COLUMN lng REAL',
        'ALTER TABLE garden_plots ADD COLUMN boundary_geojson TEXT DEFAULT ""',
        'ALTER TABLE federation_peers ADD COLUMN lat REAL',
        'ALTER TABLE federation_peers ADD COLUMN lng REAL',
        'ALTER TABLE sync_log ADD COLUMN vector_clock TEXT DEFAULT "{}"',
        'ALTER TABLE sync_log ADD COLUMN conflicts_detected INTEGER DEFAULT 0',
        'ALTER TABLE sync_log ADD COLUMN conflict_details TEXT DEFAULT "[]"',
        'ALTER TABLE sync_log ADD COLUMN resolved INTEGER DEFAULT 0',
        'ALTER TABLE sync_log ADD COLUMN resolution TEXT DEFAULT ""',
        'ALTER TABLE map_annotations ADD COLUMN name TEXT DEFAULT ""',
        'ALTER TABLE map_annotations ADD COLUMN lat REAL',
        'ALTER TABLE map_annotations ADD COLUMN lng REAL',
        'ALTER TABLE map_annotations ADD COLUMN is_geofence INTEGER DEFAULT 0',
        'ALTER TABLE map_annotations ADD COLUMN properties TEXT DEFAULT "{}"',
        'ALTER TABLE map_annotations ADD COLUMN radius_m REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN calories_per_unit REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN protein_g REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN fat_g REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN carbs_g REAL DEFAULT 0',
        'ALTER TABLE preservation_log ADD COLUMN calories_per_unit REAL DEFAULT 0',
        'ALTER TABLE inventory ADD COLUMN container_id INTEGER DEFAULT NULL',
        'ALTER TABLE inventory ADD COLUMN weight_oz REAL DEFAULT 0',
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
        'ALTER TABLE conversations ADD COLUMN tags TEXT DEFAULT "[]"',
        'ALTER TABLE inventory ADD COLUMN deleted_at TIMESTAMP',
        'ALTER TABLE contacts ADD COLUMN deleted_at TIMESTAMP',
        'ALTER TABLE notes ADD COLUMN deleted_at TIMESTAMP',
        'ALTER TABLE patients ADD COLUMN deleted_at TIMESTAMP',
        'ALTER TABLE conversations ADD COLUMN kb_scope TEXT DEFAULT "[]"',
    ],
}


def _apply_column_migrations(conn):
    """Apply ALTER TABLE column migrations, skipping already-applied versions.

    On an existing database where all columns already exist, this reduces
    startup from ~80 try/except ALTER TABLE calls to a single SELECT.
    """
    conn.execute('''
        CREATE TABLE IF NOT EXISTS _column_migration_versions (
            version    INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

    applied = {
        row[0]
        for row in conn.execute('SELECT version FROM _column_migration_versions').fetchall()
    }

    for version in sorted(_COLUMN_MIGRATIONS):
        if version in applied:
            continue
        _log.info('Applying column migration batch v%d (%d statements)',
                  version, len(_COLUMN_MIGRATIONS[version]))
        for migration in _COLUMN_MIGRATIONS[version]:
            try:
                conn.execute(migration)
                conn.commit()
            except sqlite3.OperationalError as e:
                if 'duplicate column name' not in str(e).lower():
                    _log.error('Column migration FAILED (%s): %s', migration[:80], e)
                    raise
        conn.execute(
            'INSERT OR IGNORE INTO _column_migration_versions (version) VALUES (?)',
            (version,),
        )
        conn.commit()
        _log.info('Column migration batch v%d applied', version)


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
    _create_roadmap_v747_tables(conn)
    _create_kb_chunks_table(conn)
    _create_guidance_sources_table(conn)
    _apply_column_migrations(conn)
    _migrate_access_logs(conn)
    _create_indexes(conn)
    _create_fts5_tables(conn)
    _seed_upc_database(conn)
    _create_rag_scope_table(conn)
    _seed_rag_scope(conn)
    # Content-expansion seeds (roadmap CE-tier 1, v7.60 + v7.61 + v7.62)
    # NOTE: freq_database is lazy-seeded on first GET /api/comms/frequencies
    # by web.blueprints.comms._seed_frequencies(). Don't pre-fill here or the
    # lazy path's empty-check skips and we lose ~260 of the 340 entries.
    _seed_companion_plants(conn)
    _seed_weather_action_rules(conn)
    _seed_pest_guide(conn)
    _seed_planting_calendar(conn)
    _seed_medicinal_herbs(conn)


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

    Wraps copy + drop in an explicit BEGIN so a failure during DROP cannot
    leave the old table drained into the new one but still lingering —
    either both steps land or neither does.
    """
    try:
        old_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='access_logs'"
        ).fetchone()
        if not old_exists:
            return
        conn.execute('BEGIN IMMEDIATE')
        try:
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
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
    except Exception as e:
        _log.warning('access_logs migration skipped: %s', e)


