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
