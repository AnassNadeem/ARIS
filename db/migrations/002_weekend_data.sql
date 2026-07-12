-- ARIS migration 002 — weekend data tables for always-on race engineer.
-- Apply: psql $ARIS_DB_URL -v ON_ERROR_STOP=1 -f db/migrations/002_weekend_data.sql

CREATE TABLE IF NOT EXISTS session_weather (
    session_id    BIGINT PRIMARY KEY REFERENCES sessions(session_id),
    air_temp_c    REAL,
    track_temp_c  REAL,
    humidity_pct  REAL,
    rainfall      BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS session_results (
    session_id  BIGINT   NOT NULL REFERENCES sessions(session_id),
    driver_id   BIGINT   NOT NULL REFERENCES drivers(driver_id),
    grid_pos    SMALLINT,
    finish_pos  SMALLINT,
    points      REAL,
    PRIMARY KEY (session_id, driver_id)
);

CREATE TABLE IF NOT EXISTS strategy_feedback (
    id             BIGSERIAL PRIMARY KEY,
    session_id     BIGINT   NOT NULL REFERENCES sessions(session_id),
    driver_id      BIGINT   NOT NULL REFERENCES drivers(driver_id),
    lap_number     SMALLINT NOT NULL,
    decision_json  JSONB    NOT NULL DEFAULT '{}',
    aris_rec_json  JSONB    NOT NULL DEFAULT '{}',
    actual_json    JSONB    NOT NULL DEFAULT '{}',
    delta_s        REAL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_strategy_feedback_session
    ON strategy_feedback (session_id, driver_id);

CREATE INDEX IF NOT EXISTS idx_laps_session_driver
    ON laps (session_id, driver_id, lap_number);
