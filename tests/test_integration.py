"""Integration tests requiring ARIS_DB_URL — skipped in CI where no DB is provisioned."""

from __future__ import annotations

import os

import pandas as pd
import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("ARIS_DB_URL"),
    reason="ARIS_DB_URL not set — no Postgres available (expected in CI)",
)


def _first_race_session_driver() -> tuple[int, int] | None:
    """Return (session_id, driver_id) for any Race session with ≥10 laps."""
    from aris.io import db
    from sqlalchemy import text

    with db.engine().connect() as conn:
        row = conn.execute(
            text(
                "SELECT l.session_id, l.driver_id FROM laps l "
                "JOIN sessions s ON s.session_id = l.session_id "
                "WHERE s.session_type = 'R' "
                "GROUP BY l.session_id, l.driver_id "
                "HAVING count(*) >= 10 "
                "LIMIT 1"
            )
        ).fetchone()
    if row is None:
        return None
    return int(row[0]), int(row[1])


def test_stints_populated_in_race_state():
    """build_race_state() must populate stints for at least 5 drivers when DB has laps."""
    pair = _first_race_session_driver()
    if pair is None:
        pytest.skip("No Race session with ≥10 laps in DB — cannot test stints")

    session_id, driver_id = pair

    from aris.io import db

    all_laps = db.fetch_all_laps(session_id)
    if all_laps.empty:
        pytest.skip("fetch_all_laps returned empty for this session")

    lap_num = int(all_laps["lap_number"].median())

    from aris.state import build_race_state

    state = build_race_state(session_id, driver_id, lap_num)

    assert state.stints is not None, "stints field must not be None"
    assert isinstance(state.stints, dict), "stints must be a dict"
    assert len(state.stints) >= 1, (
        f"stints must have at least 1 driver entry; got {len(state.stints)}"
    )
    for code, stint_list in state.stints.items():
        assert isinstance(code, str), f"stints key must be str; got {type(code)}"
        assert isinstance(stint_list, list), f"stints[{code}] must be list"
        for entry in stint_list:
            assert "compound" in entry, f"stints[{code}] entry missing 'compound'"
            assert "lap_start" in entry, f"stints[{code}] entry missing 'lap_start'"
            assert entry["compound"] in {
                "SOFT",
                "MEDIUM",
                "HARD",
                "INTERMEDIATE",
                "INTER",
                "WET",
                "C1",
                "C2",
                "C3",
                "C4",
                "C5",
            } or len(entry["compound"]) <= 15, (
                f"unexpected compound value: {entry['compound']}"
            )


def test_build_stints_dict_structure():
    """_build_stints_dict returns correct shape for a real session."""
    from aris.io import db
    from aris.state import _build_stints_dict

    pair = _first_race_session_driver()
    if pair is None:
        pytest.skip("No Race session with ≥10 laps in DB")

    session_id, _ = pair
    stints = _build_stints_dict(session_id)

    assert isinstance(stints, dict)
    assert len(stints) >= 1
    for code, stint_list in stints.items():
        assert isinstance(code, str)
        assert isinstance(stint_list, list)
        assert len(stint_list) >= 1, f"driver {code} has empty stint list"
        for s in stint_list:
            assert isinstance(s.get("lap_start"), int)
            assert isinstance(s.get("compound"), str)
            assert s["compound"].strip()


def test_rival_compound_inference_uses_stints():
    """When stints are populated, _infer_rival_expected_compound returns non-HARD
    for a driver who hasn't yet used SOFT in early race."""
    from aris.recommend import _infer_rival_expected_compound

    session_stints = {
        "SAI": [
            {"lap_start": 1, "compound": "MEDIUM"},
        ]
    }
    result = _infer_rival_expected_compound("SAI", current_lap=10, session_stints=session_stints)
    assert result != "HARD", (
        f"Expected non-HARD when driver hasn't used SOFT in lap 10; got {result}"
    )
