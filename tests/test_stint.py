"""Tests for aris.physics.stint on synthetic, known-shape lap data."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aris.physics.stint import (
    Stint,
    compute_stint_metrics,
    detect_stints,
    filter_clean_laps,
    stints_from_metrics,
)


def _make_synthetic_laps(
    drivers: tuple[str, ...] = ("VER", "HAM", "LEC"),
    laps_per_stint: int = 15,
    deg_per_lap: float = 0.05,
    base_pace_s: float = 90.0,
) -> pd.DataFrame:
    """Build a 3-driver × (2 × laps_per_stint) frame with two clean stints per driver."""
    rows = []
    for drv in drivers:
        lap_no = 1
        for stint_idx, compound in enumerate(["MEDIUM", "HARD"], start=1):
            for tyre_life in range(1, laps_per_stint + 1):
                pace = base_pace_s + deg_per_lap * tyre_life + 0.5 * stint_idx
                rows.append(
                    {
                        "Driver": drv,
                        "LapNumber": lap_no,
                        "Compound": compound,
                        "TyreLife": tyre_life,
                        "LapTime": pd.Timedelta(seconds=pace),
                        "PitInTime": pd.NaT,
                        "PitOutTime": pd.NaT,
                    }
                )
                lap_no += 1
    return pd.DataFrame(rows)


class TestDetectStints:
    def test_enriches_with_expected_columns(self):
        df = detect_stints(_make_synthetic_laps())
        for col in ("LapTimeS", "CompoundChange", "StintId"):
            assert col in df.columns

    def test_stint_id_is_two_per_driver(self):
        df = detect_stints(_make_synthetic_laps())
        for _drv, grp in df.groupby("Driver"):
            assert set(grp["StintId"].unique()) == {1, 2}

    def test_first_lap_of_each_driver_is_a_compound_change(self):
        df = detect_stints(_make_synthetic_laps())
        firsts = df.groupby("Driver").head(1)
        assert firsts["CompoundChange"].all()


class TestComputeStintMetrics:
    def test_returns_six_rows_for_three_drivers_two_stints(self):
        enriched = detect_stints(_make_synthetic_laps())
        metrics = compute_stint_metrics(enriched)
        assert len(metrics) == 6

    def test_median_pace_within_tolerance(self):
        enriched = detect_stints(_make_synthetic_laps(laps_per_stint=15, deg_per_lap=0.05))
        metrics = compute_stint_metrics(enriched)
        # stint 1: pace = 90 + 0.05*tyre_life + 0.5 → median tyre_life=8 → 90.9
        # stint 2: pace = 90 + 0.05*tyre_life + 1.0 → median tyre_life=8 → 91.4
        stint1 = metrics[metrics["StintNumber"] == 1]
        stint2 = metrics[metrics["StintNumber"] == 2]
        assert stint1["MedianPaceS"].iloc[0] == pytest.approx(90.9, abs=0.01)
        assert stint2["MedianPaceS"].iloc[0] == pytest.approx(91.4, abs=0.01)

    def test_deg_slope_recovers_synthetic_gradient(self):
        enriched = detect_stints(_make_synthetic_laps(deg_per_lap=0.05))
        metrics = compute_stint_metrics(enriched)
        assert np.allclose(metrics["DegSlope"], 0.05, atol=1e-9)

    def test_short_stint_yields_nan_slope(self):
        enriched = detect_stints(_make_synthetic_laps(drivers=("VER",), laps_per_stint=2))
        metrics = compute_stint_metrics(enriched, min_laps=3)
        assert metrics["DegSlope"].isna().all()


class TestStintsFromMetrics:
    def test_returns_frozen_stint_records(self):
        enriched = detect_stints(_make_synthetic_laps())
        metrics = compute_stint_metrics(enriched)
        stints = stints_from_metrics(metrics)
        assert len(stints) == 6
        assert all(isinstance(s, Stint) for s in stints)
        assert stints[0].length == stints[0].num_laps

    def test_nan_slope_becomes_none(self):
        enriched = detect_stints(_make_synthetic_laps(drivers=("VER",), laps_per_stint=2))
        metrics = compute_stint_metrics(enriched, min_laps=3)
        stints = stints_from_metrics(metrics)
        assert all(s.deg_slope_s_per_lap is None for s in stints)


class TestFilterCleanLaps:
    def test_drops_pit_in_and_out_laps(self):
        laps = _make_synthetic_laps()
        laps["PitOutTime"] = pd.Series(pd.NaT, index=laps.index, dtype="timedelta64[ns]")
        laps["PitInTime"] = pd.Series(pd.NaT, index=laps.index, dtype="timedelta64[ns]")
        laps.loc[0, "PitOutTime"] = pd.Timedelta(seconds=1)
        laps.loc[5, "PitInTime"] = pd.Timedelta(seconds=2)
        enriched = detect_stints(laps)
        clean = filter_clean_laps(enriched)
        assert len(clean) == len(enriched) - 2
