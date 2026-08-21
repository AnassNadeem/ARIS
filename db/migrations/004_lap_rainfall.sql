-- ARIS migration 004 — per-lap rainfall from FastF1 weather_data['Rainfall'].
-- Apply: psql $ARIS_DB_URL -v ON_ERROR_STOP=1 -f db/migrations/004_lap_rainfall.sql
--
-- session_weather.rainfall stays the session-level any() bit used by walk-forward
-- exclusion. laps.rainfall and weather_samples are the live per-lap signal.

ALTER TABLE laps
    ADD COLUMN IF NOT EXISTS rainfall BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS weather_samples (
    session_id   BIGINT  NOT NULL REFERENCES sessions(session_id),
    sample_idx   INTEGER NOT NULL,
    time_s       REAL    NOT NULL,
    rainfall     BOOLEAN NOT NULL DEFAULT FALSE,
    air_temp_c   REAL,
    track_temp_c REAL,
    PRIMARY KEY (session_id, sample_idx)
);
