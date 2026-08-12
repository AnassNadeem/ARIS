"""Shared DegSlope confound corrections (fuel + track evolution) for tyre fits.

Fuel burn and track rubbering-in both trend with session progress and can bias
compound DegSlope estimates. Within a single stint, LapNumber and TyreLife are
collinear, so track evolution must be estimated from *between-stint* variation
at matched tyre life (fresh flying laps), then subtracted before within-stint
polyfits.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aris.models.features import estimate_fuel_kg
from aris.physics.bicycle import FUEL_PENALTY_S_PER_KG

# Flying-lap window used to estimate session-level track evolution at matched
# tyre state (excludes cold out-lap TyreLife==1).
_EVO_TYRE_LIFE_MIN = 2
_EVO_TYRE_LIFE_MAX = 3
_EVO_MIN_POINTS = 8


def detrend_fuel_pace(enriched: pd.DataFrame, *, total_laps: int) -> pd.DataFrame:
    """Subtract bicycle fuel-time term so DegSlope is not fuel-confounded."""
    out = enriched.copy()
    fuel_kg = out["LapNumber"].map(
        lambda n: estimate_fuel_kg(int(n), total_laps=total_laps)
    )
    out["LapTimeS"] = out["LapTimeS"] - FUEL_PENALTY_S_PER_KG * fuel_kg
    out["FuelCorrected"] = True
    return out


def estimate_track_evolution_slope_s_per_lap(
    enriched: pd.DataFrame,
    *,
    tyre_life_min: int = _EVO_TYRE_LIFE_MIN,
    tyre_life_max: int = _EVO_TYRE_LIFE_MAX,
    min_points: int = _EVO_MIN_POINTS,
) -> float:
    """Session rubbering-in rate (s/lap) from fresh flying laps vs LapNumber.

    Uses only TyreLife in [tyre_life_min, tyre_life_max] so the slope is not
    the within-stint tyre DegSlope. Negative ⇒ track getting faster.
    Returns 0.0 when there are too few points or LapNumber has no spread.
    """
    if "LapTimeS" not in enriched.columns or "LapNumber" not in enriched.columns:
        return 0.0
    if "TyreLife" not in enriched.columns:
        return 0.0
    pool = enriched[
        enriched["LapTimeS"].notna()
        & enriched["LapNumber"].notna()
        & enriched["TyreLife"].notna()
        & (enriched["TyreLife"] >= tyre_life_min)
        & (enriched["TyreLife"] <= tyre_life_max)
    ]
    if "PitInTime" in pool.columns:
        pool = pool[pool["PitInTime"].isna()]
    if "TrackStatus" in pool.columns:
        # Prefer green-flag only when the column is present.
        ts = pool["TrackStatus"].astype(str)
        pool = pool[ts.str.startswith("1") | (ts == "1")]
    if len(pool) < min_points or pool["LapNumber"].nunique() < 3:
        return 0.0
    slope, _ = np.polyfit(
        pool["LapNumber"].to_numpy(dtype=float),
        pool["LapTimeS"].to_numpy(dtype=float),
        1,
    )
    if not np.isfinite(slope):
        return 0.0
    # Sanity clip: rubbering-in is typically a few hundredths per lap, not seconds.
    return float(np.clip(slope, -0.2, 0.05))


def detrend_track_evolution(
    enriched: pd.DataFrame,
    *,
    evolution_slope: float | None = None,
) -> tuple[pd.DataFrame, float]:
    """Remove session-level LapNumber trend estimated at matched tyre life.

    Corrected time = LapTimeS - slope * (LapNumber - 1). Early laps unchanged;
    later laps have the rubbering-in advantage removed so within-stint DegSlope
    is not confounded by when in the session the stint ran.
    """
    out = enriched.copy()
    slope = (
        float(evolution_slope)
        if evolution_slope is not None
        else estimate_track_evolution_slope_s_per_lap(out)
    )
    out["LapTimeS"] = out["LapTimeS"] - slope * (out["LapNumber"].astype(float) - 1.0)
    out["TrackEvolutionSlope"] = slope
    out["TrackEvolutionCorrected"] = True
    return out, slope
