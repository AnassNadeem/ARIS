-- ARIS — Postgres schema (Phase 2, Week 3; Day 2 tables + Day 3 natural keys).
--
-- Apply against the local docker container:
--   docker compose exec -T postgres psql -U aris -d aris -v ON_ERROR_STOP=1 < db/schema.sql
--
-- Design rationale: db/SCHEMA-NOTES.md.
-- Day 3 adds the natural-key UNIQUE constraints that the idempotent ingest
-- (src/aris/io/ingest.py) keys its INSERT ... ON CONFLICT upserts on.
-- This script is idempotent by drop-and-recreate — safe to re-run while there
-- is no production data worth keeping (ingest re-populates from FastF1).

DROP TABLE IF EXISTS telemetry CASCADE;
DROP TABLE IF EXISTS laps      CASCADE;
DROP TABLE IF EXISTS drivers   CASCADE;
DROP TABLE IF EXISTS sessions  CASCADE;

CREATE TABLE sessions (
    session_id   BIGSERIAL PRIMARY KEY,
    year         SMALLINT NOT NULL,
    round_no     SMALLINT NOT NULL,
    country      TEXT     NOT NULL,
    session_type TEXT     NOT NULL
                 CHECK (session_type IN ('FP1', 'FP2', 'FP3', 'Q', 'SQ', 'SS', 'S', 'R', 'SR')),
    date         TIMESTAMPTZ,
    -- Natural key: a (year, round_no, session_type) triple is exactly one session.
    -- Ingest upserts on this so a re-run of the same weekend is a no-op.
    CONSTRAINT uq_sessions_natural UNIQUE (year, round_no, session_type)
);

CREATE TABLE drivers (
    driver_id BIGSERIAL PRIMARY KEY,
    code      TEXT     NOT NULL,
    year      SMALLINT NOT NULL,
    full_name TEXT     NOT NULL,
    team      TEXT,
    -- Natural key: drivers are versioned per season (see SCHEMA-NOTES.md), so a
    -- 3-letter code reused across years stays distinct, one row per (code, year).
    CONSTRAINT uq_drivers_natural UNIQUE (code, year)
);

CREATE TABLE laps (
    lap_id       BIGSERIAL PRIMARY KEY,
    session_id   BIGINT   NOT NULL REFERENCES sessions(session_id),
    driver_id    BIGINT   NOT NULL REFERENCES drivers(driver_id),
    lap_number   SMALLINT NOT NULL,
    lap_time_s   NUMERIC(8, 3),
    compound     TEXT,
    tyre_life    SMALLINT,
    stint        SMALLINT,
    sector_1_s   NUMERIC(8, 3),
    sector_2_s   NUMERIC(8, 3),
    sector_3_s   NUMERIC(8, 3),
    track_status TEXT,
    pit_in       BOOLEAN NOT NULL DEFAULT FALSE,
    pit_out      BOOLEAN NOT NULL DEFAULT FALSE,
    -- Natural key: one lap per (session, driver, lap_number). Backs the ingest
    -- upsert; its UNIQUE index also serves the dashboard's hot query path, so
    -- the standalone composite index from Day 2 is now redundant and dropped.
    CONSTRAINT uq_laps_natural UNIQUE (session_id, driver_id, lap_number)
);

CREATE TABLE telemetry (
    session_id BIGINT   NOT NULL REFERENCES sessions(session_id),
    driver_id  BIGINT   NOT NULL REFERENCES drivers(driver_id),
    lap_number SMALLINT NOT NULL,
    sample_idx INTEGER  NOT NULL,
    speed      REAL,
    throttle   REAL,
    brake      BOOLEAN,
    gear       SMALLINT,
    drs        SMALLINT,
    rpm        REAL,
    x          REAL,
    y          REAL,
    z          REAL,
    PRIMARY KEY (session_id, driver_id, lap_number, sample_idx)
);

-- laps(session_id, driver_id, lap_number) is already indexed by the
-- uq_laps_natural UNIQUE constraint above, which covers the dashboard's
-- "all laps for one driver in one session, ordered by lap number" path.
-- These two single-column indexes serve the remaining join directions.
CREATE INDEX idx_laps_session ON laps (session_id);
CREATE INDEX idx_laps_driver  ON laps (driver_id);
