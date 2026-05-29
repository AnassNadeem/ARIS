-- ARIS — MA(2) lap-time baseline, recomputed in SQL (Phase 2, Week 3 Day 4).
--
-- The Phase-2 canary. Week 2's moving-average baseline (window = 2) was
-- computed in pandas over FastF1 frames; this query recomputes the identical
-- statistic straight from the Postgres `laps` table. If the per-race MAE
-- matches Week 2's numbers within float precision, the FastF1 -> Postgres
-- ingest neither dropped nor duplicated a lap. If it does not, it did — and
-- the discrepancy must be found before the Phase-2 deploy.
--
-- Method, mirroring aris.eval.baseline.moving_average_baseline at window = 2
-- (and Week 2's filter_clean_laps):
--   1. keep only race laps that are timed and are neither pit-in nor pit-out
--      laps,
--   2. within each (session, driver, stint), predict a lap from the mean of
--      the two preceding laps — pandas: LapTimeS.shift(1).rolling(2).mean(),
--   3. score only laps where both preceding laps exist (rolling(2)'s
--      min_periods = 2 — the first two laps of every stint get no prediction),
--   4. MAE = mean absolute error, grouped per race.
--
-- `stint` is the compound-change-cumsum StintId the ingest stored — the same
-- partition Week 2's groupby(["Driver", "StintId"]) used — so the window
-- partitions line up exactly with the pandas groups.
--
-- Run standalone:
--   docker compose exec -T postgres psql -U aris -d aris -f db/queries/baseline_ma2.sql
-- Or via scripts/baseline_crosscheck.py, which diffs this output against
-- results/wk2-baseline-mae.csv.

WITH clean AS (
    -- filter_clean_laps: timed, steady-state, green-flag race laps only.
    -- track_status = '1' drops SC / VSC / yellow / red-flag laps (a multi-code
    -- status like '24' is not '1', so it is excluded) — mirrors the Week 4
    -- TrackStatus green-only filter added to aris.physics.stint.filter_clean_laps.
    SELECT
        s.year,
        s.round_no,
        s.country,
        l.session_id,
        l.driver_id,
        l.stint,
        l.lap_number,
        l.lap_time_s::float8 AS lap_time_s
    FROM laps l
    JOIN sessions s ON s.session_id = l.session_id
    WHERE s.session_type = 'R'
      AND l.lap_time_s IS NOT NULL
      AND NOT l.pit_in
      AND NOT l.pit_out
      AND l.track_status = '1'
),
predicted AS (
    -- MA(2): mean of the two preceding laps in the same (driver, stint).
    SELECT
        year,
        round_no,
        country,
        lap_time_s,
        avg(lap_time_s) OVER ma2 AS ma2_pred,
        count(*)        OVER ma2 AS ma2_n
    FROM clean
    WINDOW ma2 AS (
        PARTITION BY session_id, driver_id, stint
        ORDER BY lap_number
        ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING
    )
)
SELECT
    year,
    round_no,
    country,
    count(*)                       AS n_laps,
    avg(abs(lap_time_s - ma2_pred)) AS mae_s
FROM predicted
WHERE ma2_n = 2  -- both preceding laps present (= pandas rolling(2) min_periods)
GROUP BY year, round_no, country
ORDER BY year, round_no;
