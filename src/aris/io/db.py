"""Postgres connection helpers for ARIS.

`engine()` builds a process-wide SQLAlchemy `Engine` from `ARIS_DB_URL`, which is
loaded from the repo-root `.env` at import time. `get_session()` hands back a
`Session` for the occasional write path.

Reads go through raw parameterized SQL (see `fetch_laps`), not the SQLAlchemy ORM.
Rationale: Phase 2's read pattern is dumb — "give me the laps for one driver in
one session" is a single `SELECT ... WHERE` with no relationship traversal. An ORM
buys lazy loading, identity maps and unit-of-work tracking that this project never
uses; raw SQL keeps the query that runs identical to the query you read, which is
worth far more when Day 4 cross-checks the SQL baseline against the pandas one.
SQLAlchemy still earns its place as the connection pool and the `text()`
parameter-binding layer that keeps the queries injection-safe.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

# db.py is src/aris/io/db.py -> parents[3] is the repo root that holds .env.
_REPO_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_REPO_ROOT / ".env")


@lru_cache(maxsize=1)
def engine() -> Engine:
    """Process-wide SQLAlchemy Engine. Raises if `ARIS_DB_URL` is unset."""
    url = os.getenv("ARIS_DB_URL")
    if not url:
        raise RuntimeError(
            "ARIS_DB_URL not set — copy .env.example to .env (see db/SCHEMA-NOTES.md)"
        )
    return create_engine(url, pool_pre_ping=True, future=True)


def get_session() -> Session:
    """A new SQLAlchemy Session bound to the shared engine (write path only)."""
    return sessionmaker(bind=engine(), future=True)()


# Columns the baseline + Streamlit dashboard read; kept in sync with db/schema.sql.
_LAPS_QUERY = text(
    """
    SELECT lap_number, lap_time_s, compound, tyre_life, stint,
           sector_1_s, sector_2_s, sector_3_s, track_status, pit_in, pit_out
    FROM laps
    WHERE session_id = :session_id AND driver_id = :driver_id
    ORDER BY lap_number
    """
)


def fetch_laps(session_id: int, driver_id: int) -> pd.DataFrame:
    """Every lap for one driver in one session, ordered by lap number.

    Returns an empty DataFrame (correct columns, zero rows) when the pair has no
    laps — callers never have to guard against a None.
    """
    with engine().connect() as conn:
        return pd.read_sql(
            _LAPS_QUERY,
            conn,
            params={"session_id": session_id, "driver_id": driver_id},
        )


_LAP_SECTORS_QUERY = text(
    """
    SELECT lap_number,
           sector_1_s::float8 AS sector_1_s,
           sector_2_s::float8 AS sector_2_s,
           sector_3_s::float8 AS sector_3_s
    FROM laps
    WHERE session_id = :session_id AND driver_id = :driver_id
    ORDER BY lap_number
    """
)


def fetch_lap_sectors(session_id: int, driver_id: int) -> pd.DataFrame:
    """Per-lap sector times (s1 / s2 / s3, seconds) for one driver in one session.

    A column projection of the same `laps` rows `fetch_laps` reads; `NUMERIC` is
    cast to `float8` at the SQL boundary so the chart gets plain floats, not
    Decimals. Returns the right columns with zero rows when the pair has no laps.
    """
    with engine().connect() as conn:
        return pd.read_sql(
            _LAP_SECTORS_QUERY,
            conn,
            params={"session_id": session_id, "driver_id": driver_id},
        )


# --- dashboard dropdown queries ------------------------------------------------
# Three small reads that populate the Streamlit app's season -> race -> driver
# selectboxes. Kept here, not in the app, so every query the app runs is raw
# parameterized SQL living next to fetch_laps.


def fetch_seasons() -> list[int]:
    """Distinct seasons present in `sessions`, newest first."""
    with engine().connect() as conn:
        rows = conn.execute(
            text("SELECT DISTINCT year FROM sessions ORDER BY year DESC")
        ).all()
    return [int(r[0]) for r in rows]


_RACES_QUERY = text(
    """
    SELECT session_id, round_no, country
    FROM sessions
    WHERE year = :year AND session_type = 'R'
    ORDER BY round_no
    """
)


def fetch_races(year: int) -> pd.DataFrame:
    """Every race (session_type 'R') of one season, ordered by round number."""
    with engine().connect() as conn:
        return pd.read_sql(_RACES_QUERY, conn, params={"year": year})


_DRIVERS_QUERY = text(
    """
    SELECT driver_id, code, full_name, team
    FROM drivers
    WHERE driver_id IN (SELECT DISTINCT driver_id FROM laps WHERE session_id = :session_id)
    ORDER BY code
    """
)


def fetch_drivers(session_id: int) -> pd.DataFrame:
    """Drivers who have at least one lap in the given session, ordered by code.

    Includes `team` (nullable) so the dashboard can label a driver with their
    constructor where the ingest captured it.
    """
    with engine().connect() as conn:
        return pd.read_sql(_DRIVERS_QUERY, conn, params={"session_id": session_id})


_DRIVER_MA2_QUERY = text(
    """
    WITH clean AS (
        SELECT stint, lap_number, lap_time_s::float8 AS lap_time_s
        FROM laps
        WHERE session_id = :session_id AND driver_id = :driver_id
          AND lap_time_s IS NOT NULL AND NOT pit_in AND NOT pit_out
          AND track_status = '1'
    ),
    predicted AS (
        SELECT lap_time_s,
               avg(lap_time_s) OVER ma2 AS ma2_pred,
               count(*)        OVER ma2 AS ma2_n
        FROM clean
        WINDOW ma2 AS (
            PARTITION BY stint ORDER BY lap_number
            ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING
        )
    )
    SELECT count(*) AS n_laps, avg(abs(lap_time_s - ma2_pred)) AS mae_s
    FROM predicted
    WHERE ma2_n = 2
    """
)


_TEAMS_QUERY = text(
    """
    SELECT DISTINCT team
    FROM drivers
    WHERE driver_id IN (SELECT DISTINCT driver_id FROM laps WHERE session_id = :session_id)
      AND team IS NOT NULL
    ORDER BY team
    """
)


def fetch_teams(session_id: int) -> list[str]:
    """Distinct teams with at least one lap in the session."""
    with engine().connect() as conn:
        rows = conn.execute(_TEAMS_QUERY, {"session_id": session_id}).all()
    return [str(r[0]) for r in rows]


_DRIVERS_BY_TEAM_QUERY = text(
    """
    SELECT driver_id, code, full_name, team
    FROM drivers
    WHERE driver_id IN (SELECT DISTINCT driver_id FROM laps WHERE session_id = :session_id)
      AND team = :team
    ORDER BY code
    """
)


def fetch_drivers_by_team(session_id: int, team: str) -> pd.DataFrame:
    """Drivers for one team in a session."""
    with engine().connect() as conn:
        return pd.read_sql(
            _DRIVERS_BY_TEAM_QUERY,
            conn,
            params={"session_id": session_id, "team": team},
        )


_ALL_LAPS_QUERY = text(
    """
    SELECT d.driver_id, d.code, d.full_name, d.team,
           l.lap_number, l.lap_time_s, l.compound, l.tyre_life, l.stint,
           l.sector_1_s, l.sector_2_s, l.sector_3_s,
           l.track_status, l.pit_in, l.pit_out
    FROM laps l
    JOIN drivers d ON d.driver_id = l.driver_id
    WHERE l.session_id = :session_id
    ORDER BY l.lap_number, d.code
    """
)


def fetch_all_laps(session_id: int) -> pd.DataFrame:
    """Field-wide laps with driver metadata for leaderboard replay."""
    with engine().connect() as conn:
        return pd.read_sql(_ALL_LAPS_QUERY, conn, params={"session_id": session_id})


_WEEKEND_SESSIONS_QUERY = text(
    """
    SELECT session_id, session_type, country, date
    FROM sessions
    WHERE year = :year AND round_no = :round_no
    ORDER BY CASE session_type
        WHEN 'FP1' THEN 1 WHEN 'FP2' THEN 2 WHEN 'FP3' THEN 3
        WHEN 'Q' THEN 4 WHEN 'SQ' THEN 5 WHEN 'SS' THEN 6
        WHEN 'R' THEN 7 WHEN 'SR' THEN 8 ELSE 9 END
    """
)


def fetch_weekend_sessions(year: int, round_no: int) -> pd.DataFrame:
    """All sessions for a race weekend."""
    with engine().connect() as conn:
        return pd.read_sql(
            _WEEKEND_SESSIONS_QUERY,
            conn,
            params={"year": year, "round_no": round_no},
        )


_WEATHER_QUERY = text(
    """
    SELECT air_temp_c, track_temp_c, humidity_pct, rainfall
    FROM session_weather
    WHERE session_id = :session_id
    """
)


def fetch_session_weather(session_id: int) -> dict | None:
    """Session weather summary or None if not ingested."""
    with engine().connect() as conn:
        row = conn.execute(_WEATHER_QUERY, {"session_id": session_id}).fetchone()
    if row is None:
        return None
    return {
        "air_temp_c": float(row.air_temp_c) if row.air_temp_c is not None else None,
        "track_temp_c": float(row.track_temp_c) if row.track_temp_c is not None else None,
        "humidity_pct": float(row.humidity_pct) if row.humidity_pct is not None else None,
        "rainfall": bool(row.rainfall),
    }


_SESSION_RESULTS_QUERY = text(
    """
    SELECT d.code, d.full_name, d.team, r.grid_pos, r.finish_pos, r.points
    FROM session_results r
    JOIN drivers d ON d.driver_id = r.driver_id
    WHERE r.session_id = :session_id
    ORDER BY COALESCE(r.finish_pos, 99), d.code
    """
)


def fetch_session_results(session_id: int) -> pd.DataFrame:
    """Grid/finish results for a session."""
    with engine().connect() as conn:
        return pd.read_sql(_SESSION_RESULTS_QUERY, conn, params={"session_id": session_id})


def fetch_driver_by_code(session_id: int, code: str) -> pd.Series | None:
    """Resolve driver_id for a 3-letter code in a session."""
    drivers = fetch_drivers(session_id)
    match = drivers[drivers["code"] == code.upper()]
    if match.empty:
        return None
    return match.iloc[0]


def fetch_race_session_id(year: int, round_no: int) -> int | None:
    """Session id for the race (R) of a weekend."""
    with engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT session_id FROM sessions "
                "WHERE year = :year AND round_no = :round_no AND session_type = 'R'"
            ),
            {"year": year, "round_no": round_no},
        ).fetchone()
    return int(row[0]) if row else None


def save_strategy_feedback(
    session_id: int,
    driver_id: int,
    lap_number: int,
    *,
    decision_json: dict,
    aris_rec_json: dict,
    actual_json: dict,
    delta_s: float | None = None,
) -> None:
    """Persist one post-race feedback row."""
    import json

    with engine().begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO strategy_feedback
                    (session_id, driver_id, lap_number, decision_json,
                     aris_rec_json, actual_json, delta_s)
                VALUES
                    (:session_id, :driver_id, :lap_number,
                     CAST(:decision_json AS jsonb), CAST(:aris_rec_json AS jsonb),
                     CAST(:actual_json AS jsonb), :delta_s)
                """
            ),
            {
                "session_id": session_id,
                "driver_id": driver_id,
                "lap_number": lap_number,
                "decision_json": json.dumps(decision_json),
                "aris_rec_json": json.dumps(aris_rec_json),
                "actual_json": json.dumps(actual_json),
                "delta_s": delta_s,
            },
        )


def fetch_driver_ma2_mae(session_id: int, driver_id: int) -> tuple[float | None, int]:
    """MA(2) baseline MAE for one driver in one session.

    The same window-2 moving-average computation as db/queries/baseline_ma2.sql,
    scoped to a single driver. Returns `(mae_s, n_scored_laps)`; `mae_s` is None
    when the driver has too few clean laps to score — every stint needs three or
    more clean laps before MA(2) yields its first prediction.
    """
    with engine().connect() as conn:
        row = conn.execute(
            _DRIVER_MA2_QUERY, {"session_id": session_id, "driver_id": driver_id}
        ).one()
    return (None if row.mae_s is None else float(row.mae_s)), int(row.n_laps)
