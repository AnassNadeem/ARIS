"""Gap-to-nearest-car (G3.3 construction reused in G4)."""

from __future__ import annotations

import pandas as pd
import pytest

from aris.physics.traffic import gaps_at_completed_laps, gaps_from_fastf1_laps


def test_three_car_adjacent_gaps():
    """Leader has no ahead; last has no behind; middle has both; min is nearest."""
    laps = pd.DataFrame(
        {
            "driver_id": [1, 1, 2, 2, 3, 3],
            "lap_number": [1, 2, 1, 2, 1, 2],
            "lap_time_s": [90.0, 90.0, 91.0, 91.5, 93.0, 92.0],
            "compound": ["SOFT", "SOFT", "MEDIUM", "MEDIUM", "HARD", "HARD"],
            "track_status": ["1"] * 6,
            "pit_in": [False] * 6,
            "pit_out": [False] * 6,
        }
    )
    gaps = gaps_at_completed_laps(laps)
    # Lap 1 cumulative: 90, 91, 93 → gaps 1s and 2s
    lap1 = gaps[gaps["lap_number"] == 1].set_index("driver_id")
    assert lap1.loc[1, "gap_ahead_s"] is None or pd.isna(lap1.loc[1, "gap_ahead_s"])
    assert lap1.loc[1, "gap_behind_s"] == 1.0
    assert lap1.loc[1, "min_nearby_s"] == 1.0
    assert lap1.loc[2, "gap_ahead_s"] == 1.0
    assert lap1.loc[2, "ahead_driver"] == 1
    assert lap1.loc[2, "behind_driver"] == 3
    assert lap1.loc[2, "gap_behind_s"] == 2.0
    assert lap1.loc[2, "min_nearby_s"] == 1.0
    assert lap1.loc[3, "gap_ahead_s"] == 2.0
    assert pd.isna(lap1.loc[3, "gap_behind_s"]) or lap1.loc[3, "gap_behind_s"] is None
    assert lap1.loc[3, "min_nearby_s"] == 2.0
    assert set(lap1["position"]) == {1, 2, 3}


def test_single_car_lap_has_no_gap():
    laps = pd.DataFrame(
        {
            "driver_id": [1, 1],
            "lap_number": [1, 2],
            "lap_time_s": [90.0, 91.0],
            "track_status": ["1", "1"],
            "pit_in": [False, False],
            "pit_out": [False, False],
        }
    )
    gaps = gaps_at_completed_laps(laps)
    assert gaps.empty


def test_sc_flag_from_track_status():
    laps = pd.DataFrame(
        {
            "driver_id": [1, 2],
            "lap_number": [1, 1],
            "lap_time_s": [90.0, 91.0],
            "track_status": ["4", "4"],
            "pit_in": [False, False],
            "pit_out": [False, False],
        }
    )
    gaps = gaps_at_completed_laps(laps)
    assert gaps["sc"].all()


def test_fastf1_adapter_uses_driver_and_pit_times():
    laps = pd.DataFrame(
        {
            "Driver": ["VER", "HAM"],
            "LapNumber": [1.0, 1.0],
            "LapTimeS": [90.0, 91.2],
            "Compound": ["SOFT", "HARD"],
            "TyreLife": [1, 1],
            "StintId": [1, 1],
            "PitInTime": [pd.NaT, pd.NaT],
            "PitOutTime": [pd.NaT, pd.NaT],
            "TrackStatus": ["1", "1"],
        }
    )
    gaps = gaps_from_fastf1_laps(laps)
    assert list(gaps["Driver"]) == ["VER", "HAM"]
    assert gaps.iloc[0]["min_nearby_s"] == pytest.approx(1.2)
    assert not bool(gaps["pit"].any())
