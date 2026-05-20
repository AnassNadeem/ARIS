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
