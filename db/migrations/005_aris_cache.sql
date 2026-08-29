-- ARIS application cache (replay packs, HTTP catalog, OpenF1/Jolpica).
-- Production durability for ARIS_CACHE_BACKEND=postgres.
-- FastF1's native filesystem cache is NOT stored here.
--
-- The PostgresCacheBackend also CREATE TABLE IF NOT EXISTS on first use so
-- a Heroku Mini dyno becomes healthy without a separate migrate step.

CREATE TABLE IF NOT EXISTS aris_cache (
    cache_key  TEXT PRIMARY KEY,
    payload    BYTEA NOT NULL,
    expires_at TIMESTAMPTZ
);
