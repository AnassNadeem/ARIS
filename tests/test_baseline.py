"""Tests for aris.eval.baseline.moving_average_baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aris.eval.baseline import moving_average_baseline


def _two_stint_frame(
    drivers: tuple[str, ...] = ("VER", "HAM"),
    laps_per_stint: int = 10,
    pace_s: float = 90.0,
) -> pd.DataFrame:
    rows = []
    for drv in drivers:
        lap_no = 1
        for stint_id in (1, 2):
            for _ in range(laps_per_stint):
                rows.append(
                    {
                        "Driver": drv,
                        "StintId": stint_id,
                        "LapNumber": lap_no,
                        "LapTimeS": pace_s,
                    }
                )
                lap_no += 1
    return pd.DataFrame(rows)


class TestMovingAverageBaseline:
    def test_first_window_laps_per_stint_are_nan(self):
        df = _two_stint_frame()
        window = 3
        preds = moving_average_baseline(df, window=window).reindex(df.index)
        for (_, _), grp in df.groupby(["Driver", "StintId"]):
            assert preds.loc[grp.index[:window]].isna().all()
            assert preds.loc[grp.index[window:]].notna().all()

    def test_constant_stint_predicts_the_constant(self):
        df = _two_stint_frame(pace_s=90.0)
        preds = moving_average_baseline(df, window=3).reindex(df.index)
        non_nan = preds.dropna()
        assert np.allclose(non_nan.to_numpy(), 90.0)

    def test_window_one_equals_previous_lap(self):
        df = _two_stint_frame()
        df.loc[:, "LapTimeS"] = np.arange(len(df), dtype=float) + 100.0
        preds = moving_average_baseline(df, window=1).reindex(df.index)
        # within each (Driver, StintId), pred[k] should equal LapTimeS[k-1]
        for (_, _), grp in df.groupby(["Driver", "StintId"], sort=False):
            grp = grp.sort_values("LapNumber")
            expected = grp["LapTimeS"].shift(1)
            got = preds.loc[grp.index]
            pd.testing.assert_series_equal(got, expected, check_names=False)

    def test_window_larger_than_stint_yields_all_nan(self):
        df = _two_stint_frame(laps_per_stint=4)
        preds = moving_average_baseline(df, window=10).reindex(df.index)
        assert preds.isna().all()

    def test_does_not_leak_across_stints(self):
        df = _two_stint_frame(laps_per_stint=5)
        df.loc[df["StintId"] == 1, "LapTimeS"] = 80.0
        df.loc[df["StintId"] == 2, "LapTimeS"] = 100.0
        preds = moving_average_baseline(df, window=2).reindex(df.index)
        # first 2 laps of stint 2 must be NaN (no carryover from stint 1)
        stint2_first2 = (
            df[df["StintId"] == 2]
            .sort_values(["Driver", "LapNumber"])
            .groupby("Driver")
            .head(2)
            .index
        )
        assert preds.loc[stint2_first2].isna().all()
        # later predictions in stint 2 are 100 (not contaminated by 80)
        stint2_rest = (
            df[df["StintId"] == 2]
            .sort_values(["Driver", "LapNumber"])
            .groupby("Driver")
            .tail(3)
            .index
        )
        assert preds.loc[stint2_rest].to_numpy() == pytest.approx(100.0)
