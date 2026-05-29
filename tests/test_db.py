"""Integration test: ARIS <-> Postgres round-trip.

Skipped when `ARIS_DB_URL` is unset — that is the expected state in CI, where no
database is provisioned. Locally it is loaded from `.env` by importing `db`.
"""

import os

import pytest
from sqlalchemy import text

from aris.io import db

pytestmark = pytest.mark.skipif(
    not os.getenv("ARIS_DB_URL"),
    reason="ARIS_DB_URL not set — no Postgres available (expected in CI)",
)


def test_select_one_round_trips():
    """The simplest possible proof the connection works end-to-end."""
    with db.engine().connect() as conn:
        assert conn.execute(text("SELECT 1")).scalar() == 1


def test_fetch_lap_sectors_empty_has_right_columns():
    """A pair with no laps returns the sector columns and zero rows, not an error."""
    df = db.fetch_lap_sectors(session_id=-1, driver_id=-1)
    assert list(df.columns) == ["lap_number", "sector_1_s", "sector_2_s", "sector_3_s"]
    assert len(df) == 0
