-- Situation Room v2: additional tables for expanded features

-- Aviation tracking (OpenSky Network)
CREATE TABLE IF NOT EXISTS sitroom_aviation (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    icao24        TEXT    NOT NULL,
    callsign      TEXT    DEFAULT '',
    origin_country TEXT   DEFAULT '',
    lat           REAL    DEFAULT 0,
    lng           REAL    DEFAULT 0,
    altitude_m    REAL    DEFAULT 0,
    velocity_ms   REAL    DEFAULT 0,
    heading       REAL    DEFAULT 0,
    vertical_rate REAL    DEFAULT 0,
    on_ground     INTEGER DEFAULT 0,
    squawk        TEXT    DEFAULT '',
    cached_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Space weather (NOAA SWPC)
CREATE TABLE IF NOT EXISTS sitroom_space_weather (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    data_type     TEXT    NOT NULL,
    value_json    TEXT    DEFAULT '{}',
    cached_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Volcanic activity
CREATE TABLE IF NOT EXISTS sitroom_volcanoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    volcano_name  TEXT    NOT NULL,
    country       TEXT    DEFAULT '',
    lat           REAL    DEFAULT 0,
    lng           REAL    DEFAULT 0,
    vei           INTEGER DEFAULT 0,
    start_date    TEXT    DEFAULT '',
    end_date      TEXT    DEFAULT '',
    detail_json   TEXT    DEFAULT '{}',
    cached_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Prediction markets
CREATE TABLE IF NOT EXISTS sitroom_predictions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id     TEXT    UNIQUE,
    question      TEXT    NOT NULL,
    category      TEXT    DEFAULT '',
    outcome_yes   REAL    DEFAULT 0,
    outcome_no    REAL    DEFAULT 0,
    volume        REAL    DEFAULT 0,
    end_date      TEXT    DEFAULT '',
    active        INTEGER DEFAULT 1,
    cached_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_sitroom_aviation_icao ON sitroom_aviation(icao24);
CREATE INDEX IF NOT EXISTS idx_sitroom_aviation_cached ON sitroom_aviation(cached_at DESC);
CREATE INDEX IF NOT EXISTS idx_sitroom_space_weather_type ON sitroom_space_weather(data_type);
CREATE INDEX IF NOT EXISTS idx_sitroom_volcanoes_name ON sitroom_volcanoes(volcano_name);
CREATE INDEX IF NOT EXISTS idx_sitroom_predictions_active ON sitroom_predictions(active, volume DESC);
CREATE INDEX IF NOT EXISTS idx_sitroom_events_type_mag ON sitroom_events(event_type, magnitude DESC);
CREATE INDEX IF NOT EXISTS idx_sitroom_events_type_cached ON sitroom_events(event_type, cached_at DESC);
