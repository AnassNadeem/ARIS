"""Sector time split ratios from historical lap data.

``sector_splits_for_session`` and ``predict_sector_times`` are
**post-session-only** utilities: they read every lap in the session and take
median s1/s2/s3 fractions. They must not be called from a live / mid-replay
path that needs a temporal cutoff — doing so would leak later-lap sector
structure into earlier decisions.

Currently unused by the product path (orphan); left in place pending a
wire-in-or-delete decision.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from aris.io import db

DEFAULT_SPLITS = (0.32, 0.38, 0.30)


@lru_cache(maxsize=32)
def sector_splits_for_session(session_id: int) -> tuple[float, float, float]:
    """Median s1/s2/s3 fractions of lap time for a **completed** session.

    Post-session only — see module docstring.
    """
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
    """Split a lap time using post-session median fractions (not replay-safe)."""
    s1, s2, s3 = sector_splits_for_session(session_id)
    return lap_time_s * s1, lap_time_s * s2, lap_time_s * s3
