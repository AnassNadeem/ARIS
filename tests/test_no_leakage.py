"""Leakage tripwire — the single most important test of Phase 3.

A feature builder predicting lap N may only depend on laps *strictly before* N
within the same (driver, stint). It must never see lap N's own target, nor any
future lap. This test proves that operationally rather than by inspection:

  * Each synthetic lap carries a unique, never-reused `LapTimeS` value, so any
    feature that secretly includes a lap shifts measurably when that lap is
    perturbed.
  * `_feature_i_moves_when_perturbing` perturbs a chosen set of laps' targets and
    reports whether lap i's feature moved. A leakage-safe builder leaves lap i's
    feature bit-identical when laps >= i are perturbed (it only looked back).

The tripwire is red against a builder that forgets the `shift(1)` (sees lap N)
and green against the correct `shift(1).rolling`. It runs in CI with no DB.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aris.eval.baseline import moving_average_baseline


def _synthetic_stint(n_laps: int = 10, seed: int = 0) -> pd.DataFrame:
    """One driver, one stint, monotonic laps; each lap a unique-and-never-reused time.

    The widely-separated per-lap values are the tripwire signal: a rolling mean
    that quietly includes lap N or a future lap cannot stay constant when that
    lap's `LapTimeS` is perturbed.
    """
    rng = np.random.default_rng(seed)
    lap_number = np.arange(1, n_laps + 1)
    tyre_life = lap_number - 1
    # +100 per lap guarantees every value is distinct and far apart
    unique_time = 90.0 + 0.05 * tyre_life + np.arange(n_laps) * 100.0 + rng.normal(0, 1, n_laps)
    return pd.DataFrame(
        {
            "Driver": "VER",
            "StintId": 1,
            "LapNumber": lap_number,
            "TyreLife": tyre_life,
            "LapTimeS": unique_time,
        }
    )


# --- builders under test -----------------------------------------------------


def _correct_builder(df: pd.DataFrame, window: int = 3) -> pd.Series:
    """shift(1).rolling(window).mean() — predicts lap N from the past only."""
    return moving_average_baseline(df, window=window)


def _leaky_builder(df: pd.DataFrame, window: int = 3) -> pd.Series:
    """rolling(window).mean() WITHOUT the shift — includes lap N. Deliberately wrong."""
    return (
        df.sort_values(["Driver", "StintId", "LapNumber"])
        .groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
        .transform(lambda s: s.rolling(window).mean())
    )


# --- perturbation machinery --------------------------------------------------


def _eq_nan(a: float, b: float) -> bool:
    """Scalar equality treating NaN == NaN as True (an undefined feature is fine)."""
    if np.isnan(a) and np.isnan(b):
        return True
    return bool(a == b)


def _feature_i_moves_when_perturbing(builder, df: pd.DataFrame, i: int, perturb: list[int]) -> bool:
    """True if perturbing the targets at `perturb` positions changes lap i's feature."""
    base = builder(df).to_numpy()[i]
    pert = df.copy()
    pert.loc[df.index[perturb], "LapTimeS"] = pert.loc[df.index[perturb], "LapTimeS"] + 1000.0
    after = builder(pert).to_numpy()[i]
    return not _eq_nan(base, after)


def assert_leakage_safe(builder, df: pd.DataFrame) -> None:
    """Raise AssertionError if any lap's feature depends on its own or a future lap."""
    n = len(df)
    for i in range(n):
        # self-leak: perturbing lap i must not move lap i's own feature
        if _feature_i_moves_when_perturbing(builder, df, i, [i]):
            raise AssertionError(f"lap {i} feature depends on its own target — self leak")
        # future-leak: perturbing any later lap must not move lap i's feature
        future = list(range(i + 1, n))
        if future and _feature_i_moves_when_perturbing(builder, df, i, future):
            raise AssertionError(f"lap {i} feature depends on a future lap — forward leak")


# --- the tripwire ------------------------------------------------------------


class TestLeakageTripwire:
    def test_correct_builder_is_leakage_safe(self):
        df = _synthetic_stint()
        assert_leakage_safe(_correct_builder, df)  # green: only looks back

    def test_leaky_builder_is_caught(self):
        df = _synthetic_stint()
        with pytest.raises(AssertionError, match="self leak"):
            assert_leakage_safe(_leaky_builder, df)

    def test_ma_baseline_regression_guard(self):
        # the exact MA(2) baseline Phase 2 shipped must stay leakage-safe
        df = _synthetic_stint()
        assert_leakage_safe(lambda d: moving_average_baseline(d, window=2), df)

    def test_shuffling_future_rows_leaves_past_features_bit_identical(self):
        # sketch assertion 2, stated directly: lap N's feature is invariant to the future
        df = _synthetic_stint(n_laps=12, seed=7)
        base = _correct_builder(df).to_numpy()
        rng = np.random.default_rng(99)
        n = len(df)
        for cut in range(2, n - 1):  # cut = first "future" lap
            shuffled = df.copy()
            future = df.index[cut:]
            shuffled.loc[future, "LapTimeS"] = rng.permutation(shuffled.loc[future, "LapTimeS"])
            after = _correct_builder(shuffled).to_numpy()
            past = slice(0, cut)
            assert np.allclose(base[past], after[past], equal_nan=True)

    def test_feature_support_is_subset_of_earlier_laps(self):
        # the very first non-NaN feature appears no earlier than it could from the past
        df = _synthetic_stint(n_laps=8)
        feats = _correct_builder(df, window=3).to_numpy()
        # shift(1).rolling(3): laps 0..2 NaN, first real prediction at lap 3
        assert np.isnan(feats[:3]).all()
        assert not np.isnan(feats[3])
