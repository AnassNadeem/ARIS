"""Tests for fuel + track-evolution DegSlope confound corrections."""

import numpy as np
import pandas as pd
import pytest

from aris.physics.bicycle import FUEL_PENALTY_S_PER_KG
from aris.physics.deg_corrections import (
    detrend_fuel_pace,
    detrend_track_evolution,
    estimate_track_evolution_slope_s_per_lap,
)
from aris.models.features import estimate_fuel_kg


def test_detrend_fuel_pace_subtracts_known_penalty():
    df = pd.DataFrame(
        {
            "LapNumber": [1, 10, 20],
            "LapTimeS": [90.0, 90.0, 90.0],
        }
    )
    out = detrend_fuel_pace(df, total_laps=57)
    for i, lap in enumerate([1, 10, 20]):
        expected = 90.0 - FUEL_PENALTY_S_PER_KG * estimate_fuel_kg(lap, total_laps=57)
        assert out["LapTimeS"].iloc[i] == pytest.approx(expected)
    assert bool(out["FuelCorrected"].iloc[0]) is True


def test_track_evolution_estimated_from_fresh_flying_laps():
    # Two stints at different LapNumbers, same TyreLife 2–3, getting faster.
    rows = []
    rng = np.random.default_rng(0)
    for start in (5, 25, 45):
        for life in (2, 3):
            lap = start + life - 1
            # true evo = -0.05 s/lap vs lap 1; tyre deg not in this pool
            t = 80.0 - 0.05 * (lap - 1) + float(rng.normal(0, 0.01))
            rows.append(
                {
                    "LapNumber": lap,
                    "TyreLife": life,
                    "LapTimeS": t,
                    "PitInTime": pd.NaT,
                    "TrackStatus": "1",
                }
            )
    df = pd.DataFrame(rows)
    slope = estimate_track_evolution_slope_s_per_lap(df, min_points=6)
    assert slope == pytest.approx(-0.05, abs=0.02)


def test_detrend_track_evolution_removes_session_trend():
    df = pd.DataFrame(
        {
            "LapNumber": [1, 11, 21],
            "TyreLife": [2, 2, 2],
            "LapTimeS": [80.0, 79.5, 79.0],  # -0.05 s/lap
            "PitInTime": [pd.NaT, pd.NaT, pd.NaT],
            "TrackStatus": ["1", "1", "1"],
        }
    )
    # Force known slope so the unit test is not sample-size fragile.
    out, slope = detrend_track_evolution(df, evolution_slope=-0.05)
    assert slope == pytest.approx(-0.05)
    # Lap 1 unchanged; later laps have rubbering advantage removed.
    assert out["LapTimeS"].iloc[0] == pytest.approx(80.0)
    assert out["LapTimeS"].iloc[1] == pytest.approx(79.5 - (-0.05) * 10)
    assert out["LapTimeS"].iloc[2] == pytest.approx(79.0 - (-0.05) * 20)


def test_evolution_returns_zero_when_too_few_points():
    df = pd.DataFrame(
        {
            "LapNumber": [1, 2],
            "TyreLife": [2, 2],
            "LapTimeS": [80.0, 79.9],
        }
    )
    assert estimate_track_evolution_slope_s_per_lap(df) == 0.0
