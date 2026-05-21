# ARIS — database schema notes

Phase 2, Week 3 Day 2. Four tables: `sessions`, `drivers`, `laps`, `telemetry`.
Written *before* `db/schema.sql` so every column is a deliberate choice, not an
accident of whatever FastF1 happened to return.

**Scope this week:** `sessions` / `drivers` / `laps` are designed *and* populated
(ingest is Day 3); `telemetry` is designed and created but populated only for one
race as a schema check — full population is Week 4. Natural-key `UNIQUE`
constraints (for idempotent upsert) are added **Day 3**, not here — Day 2 ships
surrogate `BIGSERIAL` PKs plus FKs and indexes.

## `sessions`

One row per session of a race weekend (the race, each practice, qualifying,
sprint). `session_id BIGSERIAL` is the surrogate PK every other table references —
a stable integer that never changes even if FastF1 renames an event. `year` and
`round_no` locate the weekend in the championship; `round_no` is used rather than
the event name because names are inconsistent ("Bahrain" vs "Bahrain Grand Prix")
while round numbers are not. `country` is kept denormalised because the dashboard
renders it as a label and a join purely to fetch a string is not worth it.
`session_type` is constrained by a `CHECK` to the eight values FastF1 emits
(`FP1/FP2/FP3/Q/SQ/SS/R/SR`) so a typo in the ingest fails at the database, not
three layers downstream. `date` is `TIMESTAMPTZ` — sessions happen at a real
instant and timezone-naive timestamps silently corrupt cross-event ordering. The
**natural key is `(year, round_no, session_type)`** — that triple uniquely
identifies a session and is what Day 3's idempotent upsert will key on.

## `drivers`

`driver_id BIGSERIAL` PK; `code` is the 3-letter abbreviation (VER, HAM), plus
`full_name` and `team`. **Decision — version drivers by season:** a `year` column
is included and the natural key is `(code, year)`. The Day 1 plan left this open
("tolerate duplicates per session, or version by season"). A 3-letter code is
reused across seasons by different people (a rookie inherits a retired driver's
slot), and a driver can change teams between seasons — so keying on `code` alone
collides across years, while keying per-session would explode the table to ~20×
the session count. Per-season versioning is the middle ground: one row per
`(code, year)`, with `team` reflecting that season's entry. Mid-season team swaps
are rare and not modelled this week. (`year` here also keeps `drivers` joinable to
`sessions.year` without a denormalised copy on every lap.)

## `laps`

`lap_id BIGSERIAL` PK; `session_id` and `driver_id` are `BIGINT` FKs into the two
tables above. `lap_number` is the lap index within the session. `lap_time_s` is
`NUMERIC(8,3)` — three-decimal seconds is the precision FastF1 reports and is
ample for a 1.088 s-MAE baseline; a binary `FLOAT` would invite float-compare
bugs in Day 4's SQL-vs-pandas baseline cross-check. `compound`, `tyre_life` and
`stint` carry the tyre-degradation story from Week 2's stint analysis.
`sector_1_s` / `sector_2_s` / `sector_3_s` feed Week 4's sector-breakdown chart.
`track_status` is stored because the Week 2 retro flagged that unfiltered
safety-car / red-flag laps inflated Miami and Australia MAE — filtering needs the
column present. `pit_in` and `pit_out` are `BOOLEAN`: in-laps and out-laps are
dropped before any pace statistic, and storing the flag beats re-deriving it from
raw pit timestamps on every query. **Natural key: `(session_id, driver_id,
lap_number)`.**

## `telemetry`

Per-sample car data — `speed`, `throttle`, `brake`, `gear`, `drs`, `rpm` and the
`x` / `y` / `z` position trace. There is no meaningful surrogate id, so the
**composite PK `(session_id, driver_id, lap_number, sample_idx)`** is the natural
identity of a sample; making it the PK also gives idempotent re-ingest for free in
Week 4. `speed` / `throttle` / `rpm` / `x` / `y` / `z` are `REAL` — continuous
channels where single precision is plenty. `brake` is `BOOLEAN` (FastF1 reports it
as on/off, not a percentage); `gear` and `drs` are `SMALLINT` discrete codes.
Schema only this week — at roughly 500k rows per race, full-season population is a
deliberate, separate Week 4 decision.

## Indexes

The dashboard's hot query path is "all laps for driver *D* in session *S*, ordered
by lap number." The `uq_laps_natural` `UNIQUE (session_id, driver_id, lap_number)`
constraint added Day 3 creates exactly the composite index that path needs, so the
standalone composite index from Day 2 was dropped as redundant. Two single-column
indexes — `laps(session_id)` and `laps(driver_id)` — remain to serve joins that
filter on only one of the two foreign keys.

## Day 3 — natural-key constraints

`db/schema.sql` now declares `UNIQUE` constraints for all three natural keys:
`uq_sessions_natural (year, round_no, session_type)`, `uq_drivers_natural
(code, year)`, and `uq_laps_natural (session_id, driver_id, lap_number)`.
`telemetry` needs no separate constraint — its composite PK *is* the natural key.
These are what `src/aris/io/ingest.py` targets with `INSERT ... ON CONFLICT
(...) DO NOTHING`, which is what makes re-running an ingest a no-op instead of a
duplicate. `DO NOTHING` (not `DO UPDATE`) is correct here: a finished race is
immutable — a lap time never changes once recorded — so there is nothing to
refresh on conflict.
