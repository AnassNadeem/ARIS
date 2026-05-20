-- ARIS — Postgres schema (Phase 2, Week 3 Day 2).
--
-- Apply against the local docker container:
--   docker compose exec -T postgres psql -U aris -d aris -v ON_ERROR_STOP=1 < db/schema.sql
--
-- Design rationale: db/SCHEMA-NOTES.md.
-- Natural-key UNIQUE constraints (for idempotent upsert) are added Day 3.
-- This script is idempotent by drop-and-recreate — safe to re-run while there
-- is no production data (there is none until Day 3's ingest).

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
                 CHECK (session_type IN ('FP1', 'FP2', 'FP3', 'Q', 'SQ', 'SS', 'R', 'SR')),
    date         TIMESTAMPTZ
);

CREATE TABLE drivers (
    driver_id BIGSERIAL PRIMARY KEY,
    code      TEXT     NOT NULL,
    year      SMALLINT NOT NULL,
    full_name TEXT     NOT NULL,
    team      TEXT
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
    pit_out      BOOLEAN NOT NULL DEFAULT FALSE
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

CREATE INDEX idx_laps_session            ON laps (session_id);
CREATE INDEX idx_laps_driver             ON laps (driver_id);
CREATE INDEX idx_laps_session_driver_lap ON laps (session_id, driver_id, lap_number);
