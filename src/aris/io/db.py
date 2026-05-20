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

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
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
