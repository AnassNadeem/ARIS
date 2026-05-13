"""Wk2 Day 3 Block 2 dry-run: single-race moving-average baseline on Bahrain 2024.

This is a one-shot scratch driver. The same logic goes into notebooks/05-sector-baseline.ipynb;
running it here first lets us print real numbers and pin them into the notebook output.
"""

from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

CACHE = Path(__file__).resolve().parent.parent / "fastf1_cache"
fastf1.Cache.enable_cache(str(CACHE))


def detect_stints(laps_df: pd.DataFrame) -> pd.DataFrame:
    df = laps_df.sort_values(["Driver", "LapNumber"]).copy()
    df["LapTimeS"] = df["LapTime"].dt.total_seconds()
    df["CompoundChange"] = df.groupby("Driver")["Compound"].transform(lambda s: s != s.shift(1))
    df["StintId"] = df.groupby("Driver")["CompoundChange"].cumsum()
    return df


def moving_average_baseline(laps_df: pd.DataFrame, window: int = 3) -> pd.Series:
    """Predict each lap's LapTimeS from a rolling mean of the prior `window` laps in the same stint.

    Output is aligned to laps_df's index. First `window` laps of every (Driver, StintId) are NaN.
    """
    return (
        laps_df
        .sort_values(["Driver", "StintId", "LapNumber"])
        .groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
        .transform(lambda s: s.shift(1).rolling(window).mean())
    )


def filter_clean_laps(enriched: pd.DataFrame) -> pd.DataFrame:
    """Drop laps that distort lap-time signal: out-laps, in-laps, NaN times."""
    e = enriched.copy()
    e = e[e["LapTimeS"].notna()]
    e = e[e["PitOutTime"].isna() & e["PitInTime"].isna()]
    return e


def main() -> None:
    session = fastf1.get_session(2024, "Bahrain", "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    enriched = detect_stints(session.laps)
    clean = filter_clean_laps(enriched)

    preds = moving_average_baseline(clean, window=3)
    preds = preds.reindex(clean.index)

    n_stints = clean.groupby(["Driver", "StintId"]).ngroups
    expected_nan = n_stints * 3
    actual_nan = int(preds.isna().sum())
    print(f"stints in Bahrain 2024 R (post-filter): {n_stints}")
    print(f"expected NaN preds (n_stints * window = {n_stints} * 3): {expected_nan}")
    print(f"actual NaN preds: {actual_nan}")
    assert actual_nan <= expected_nan, "more NaNs than expected — investigate"

    mask = preds.notna()
    y_true = clean.loc[mask, "LapTimeS"].to_numpy()
    y_pred = preds.loc[mask].to_numpy()
    mae = float(np.mean(np.abs(y_true - y_pred)))
    print(f"\nBahrain 2024 — moving-average-of-3 baseline MAE: {mae:.3f} s on {len(y_true)} laps")


if __name__ == "__main__":
    main()
