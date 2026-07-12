"""F1-style sector timing colors."""

from __future__ import annotations

from enum import StrEnum

import pandas as pd


class SectorColor(StrEnum):
    PURPLE = "purple"
    GREEN = "green"
    YELLOW = "yellow"
    NONE = "none"


def session_sector_bests(all_laps: pd.DataFrame, through_lap: int) -> dict[int, float]:
    """Best sector time per sector index (1-3) through `through_lap`."""
    subset = all_laps[all_laps["lap_number"] <= through_lap]
    bests: dict[int, float] = {}
    for sector in (1, 2, 3):
        col = f"sector_{sector}_s"
        if col not in subset.columns:
            continue
        vals = subset[col].dropna()
        if not vals.empty:
            bests[sector] = float(vals.min())
    return bests


def driver_personal_bests(
    driver_laps: pd.DataFrame, through_lap: int
) -> dict[int, float]:
    subset = driver_laps[driver_laps["lap_number"] < through_lap]
    bests: dict[int, float] = {}
    for sector in (1, 2, 3):
        col = f"sector_{sector}_s"
        if col not in subset.columns:
            continue
        vals = subset[col].dropna()
        if not vals.empty:
            bests[sector] = float(vals.min())
    return bests


def color_sector_time(
    sector_time: float | None,
    *,
    sector_idx: int,
    session_bests: dict[int, float],
    personal_bests: dict[int, float],
) -> SectorColor:
    if sector_time is None or pd.isna(sector_time):
        return SectorColor.NONE
    t = float(sector_time)
    session_best = session_bests.get(sector_idx)
    personal_best = personal_bests.get(sector_idx)
    if session_best is not None and t <= session_best + 1e-6:
        return SectorColor.PURPLE
    if personal_best is not None and t <= personal_best + 1e-6:
        return SectorColor.GREEN
    return SectorColor.YELLOW


def fastest_driver_per_sector(standings: list) -> dict[int, str]:
    """Map sector index -> driver code with fastest sector time on current lap."""
    result: dict[int, str] = {}
    for sector_idx, attr in ((1, "sector_1_s"), (2, "sector_2_s"), (3, "sector_3_s")):
        best: tuple[str, float] | None = None
        for row in standings:
            val = getattr(row, attr, None)
            if val is None or pd.isna(val):
                continue
            if best is None or float(val) < best[1]:
                best = (row.code, float(val))
        if best:
            result[sector_idx] = best[0]
    return result
