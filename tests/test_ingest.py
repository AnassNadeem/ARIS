"""Integration tests for the FastF1 -> Postgres ingest.

Marked `integration` and skipped when `ARIS_DB_URL` is unset — that is the
expected state in CI, where no Postgres is provisioned. Locally they run
against the docker container and ingest Bahrain 2024 R; because the ingest is
idempotent, running the suite repeatedly never duplicates a row.
"""

import os

import pytest
from sqlalchemy import text

from aris.io import db
from aris.io.ingest import ingest_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("ARIS_DB_URL"),
        reason="ARIS_DB_URL not set — no Postgres available (expected in CI)",
    ),
]

# Raw, unfiltered FastF1 lap count for Bahrain 2024 R, hand-checked Wk3 Day3.
# This is the ingested-row count, not the Wk2 baseline's post-filter count (908).
BAHRAIN_2024_R_LAPS = 1129


@pytest.fixture(scope="module")
def bahrain_session_id() -> int:
    """Ensure Bahrain 2024 R is ingested; yield its session_id.

    The ingest is idempotent, so calling it here is safe whether or not a
    previous run already populated the row.
    """
    ingest_session(2024, 1, "R")
    with db.engine().connect() as conn:
        return conn.execute(
            text(
                "SELECT session_id FROM sessions "
                "WHERE year = 2024 AND round_no = 1 AND session_type = 'R'"
            )
        ).scalar_one()


def test_ingest_is_idempotent(bahrain_session_id):
    """Re-ingesting an already-present session inserts zero rows."""
    counts = ingest_session(2024, 1, "R")
    assert counts == {"sessions": 0, "drivers": 0, "laps": 0}


def test_ingest_row_counts(bahrain_session_id):
    """The ingested lap count matches the hand-checked raw FastF1 count."""
    with db.engine().connect() as conn:
        n_laps = conn.execute(
            text("SELECT count(*) FROM laps WHERE session_id = :sid"),
            {"sid": bahrain_session_id},
        ).scalar_one()
    assert n_laps == BAHRAIN_2024_R_LAPS


def test_no_orphan_laps(bahrain_session_id):
    """Every laps row resolves to a real session and driver — FK integrity holds."""
    with db.engine().connect() as conn:
        orphans = conn.execute(
            text(
                """
                SELECT count(*)
                FROM laps l
                LEFT JOIN sessions s ON l.session_id = s.session_id
                LEFT JOIN drivers  d ON l.driver_id  = d.driver_id
                WHERE s.session_id IS NULL OR d.driver_id IS NULL
                """
            )
        ).scalar_one()
    assert orphans == 0


def test_no_out_of_range_gears_in_telemetry():
    """The Week 4 gear-cleaning invariant: no stored gear is outside 1..8."""
    with db.engine().connect() as conn:
        bad = conn.execute(
            text("SELECT count(*) FROM telemetry WHERE gear < 1 OR gear > 8")
        ).scalar_one()
    assert bad == 0
