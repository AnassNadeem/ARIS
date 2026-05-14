"""Statistical baselines for lap-time prediction. Floor that ML must beat."""

from __future__ import annotations

import pandas as pd


def moving_average_baseline(laps_df: pd.DataFrame, window: int = 3) -> pd.Series:
    """Predict LapTimeS from a rolling mean of the prior `window` laps in the same stint."""
    return (
        laps_df.sort_values(["Driver", "StintId", "LapNumber"])
        .groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
        .transform(lambda s: s.shift(1).rolling(window).mean())
    )
