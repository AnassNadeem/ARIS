"""Sector time split ratios from historical lap data."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from aris.io import db

DEFAULT_SPLITS = (0.32, 0.38, 0.30)


@lru_cache(maxsize=32)
def sector_splits_for_session(session_id: int) -> tuple[float, float, float]:
    """Median s1/s2/s3 fractions of lap time for a session."""
    all_laps = db.fetch_all_laps(session_id)
    if all_laps.empty:
        return DEFAULT_SPLITS

    rows: list[tuple[float, float, float]] = []
    for _, lap in all_laps.iterrows():
        lt = lap.get("lap_time_s")
        s1, s2, s3 = lap.get("sector_1_s"), lap.get("sector_2_s"), lap.get("sector_3_s")
        if any(pd.isna(v) for v in (lt, s1, s2, s3)):
            continue
        total = float(lt)
        if total <= 0:
            continue
        rows.append((float(s1) / total, float(s2) / total, float(s3) / total))

    if not rows:
        return DEFAULT_SPLITS
    df = pd.DataFrame(rows, columns=["s1", "s2", "s3"])
    return (float(df["s1"].median()), float(df["s2"].median()), float(df["s3"].median()))


def predict_sector_times(lap_time_s: float, session_id: int) -> tuple[float, float, float]:
    s1, s2, s3 = sector_splits_for_session(session_id)
    return lap_time_s * s1, lap_time_s * s2, lap_time_s * s3
