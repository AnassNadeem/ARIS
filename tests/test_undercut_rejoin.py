"""Empirical undercut / rejoin table. Does not change T2-D defaults."""

from __future__ import annotations

import pandas as pd

from aris.eval.undercut_rejoin import (
    find_undercut_attempts,
    gap_bin,
    summarize_attempts,
)
from aris.physics.traffic import gaps_at_completed_laps
from aris.recommend import UNDERCUT_WINDOW_S, compute_undercut_bonus
from tests.test_strategy import _sample_state


def test_t2d_window_unchanged():
    assert UNDERCUT_WINDOW_S == 22.0
    state = _sample_state(gap_ahead_s=2.0)
    assert compute_undercut_bonus(state) == -0.6
    far = _sample_state(gap_ahead_s=22.0)
    assert compute_undercut_bonus(far) == 0.0


def test_gap_bins_match_reporting_edges():
    assert gap_bin(0.5) == "<1s"
    assert gap_bin(2.0) == "1-3s"
    assert gap_bin(5.0) == "3-8s"
    assert gap_bin(10.0) == "8-22s"
    assert gap_bin(22.0) == ">=22s"


def test_gaps_include_ahead_driver():
    laps = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "lap_number": [1, 1],
            "lap_time_s": [90.0, 91.0],
            "track_status": ["1", "1"],
            "pit_in": [False, False],
            "pit_out": [False, False],
        }
    )
    gaps = gaps_at_completed_laps(laps)
    by_id = gaps.set_index("driver_id")
    assert pd.isna(by_id.loc[1, "ahead_driver"]) or by_id.loc[1, "ahead_driver"] is None
    assert by_id.loc[2, "ahead_driver"] == 1
    assert by_id.loc[1, "behind_driver"] == 2


def _two_car_laps(*, a_pit_status: str = "1") -> pd.DataFrame:
    """B (1) leads; A (2) pits lap 3; A jumps B on the first flying lap."""
    rows = []
    # B stays out, slows after A's stop so a position swap is observable.
    b_times = {1: 90.0, 2: 90.0, 3: 90.0, 4: 120.0, 5: 120.0, 6: 120.0}
    a_times = {1: 91.0, 2: 91.0, 3: 100.0, 4: 80.0, 5: 80.0, 6: 80.0}
    for lap in range(1, 7):
        rows.append(
            {
                "driver_id": 1,
                "code": "B",
                "lap_number": lap,
                "lap_time_s": b_times[lap],
                "compound": "MEDIUM",
                "track_status": "1",
                "pit_in": False,
                "pit_out": False,
            }
        )
        rows.append(
            {
                "driver_id": 2,
                "code": "A",
                "lap_number": lap,
                "lap_time_s": a_times[lap],
                "compound": "SOFT" if lap >= 4 else "MEDIUM",
                "track_status": a_pit_status if lap == 3 else "1",
                "pit_in": lap == 3,
                "pit_out": lap == 4,
            }
        )
    return pd.DataFrame(rows)


def test_green_undercut_records_swap():
    attempts = find_undercut_attempts(_two_car_laps(), circuit="bahrain", year=2024)
    assert len(attempts) == 1
    hit = attempts[0]
    assert hit["pit_lap"] == 3
    assert hit["gap_bin"] == "1-3s"
    assert hit["swapped"] is True
    assert hit["timeout"] is False
    assert hit["a_compound"] == "SOFT"
    assert hit["b_compound"] == "MEDIUM"


def test_sc_pits_are_excluded():
    attempts = find_undercut_attempts(_two_car_laps(a_pit_status="4"))
    assert attempts == []


def test_summarize_by_bin_does_not_invent_dirty_air():
    attempts = find_undercut_attempts(_two_car_laps(), circuit="bahrain")
    summary = summarize_attempts(attempts)
    assert summary["n_attempts"] == 1
    assert summary["n_swapped"] == 1
    assert summary["by_gap_bin"]["1-3s"]["n"] == 1
    assert "+0.6..+1.2" in summary["meta"]["do_not_ship_dirty_air"]
