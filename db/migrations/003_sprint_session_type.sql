-- ARIS migration 003 — allow FastF1 Sprint identifier 'S'.
-- Sprint weekends use FP1 / SQ / S / Q / R (no FP2/FP3).
-- Apply: psql $ARIS_DB_URL -v ON_ERROR_STOP=1 -f db/migrations/003_sprint_session_type.sql

ALTER TABLE sessions DROP CONSTRAINT IF EXISTS sessions_session_type_check;
ALTER TABLE sessions ADD CONSTRAINT sessions_session_type_check
    CHECK (session_type IN ('FP1', 'FP2', 'FP3', 'Q', 'SQ', 'SS', 'S', 'R', 'SR'));
