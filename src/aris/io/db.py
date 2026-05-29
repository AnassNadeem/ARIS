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
