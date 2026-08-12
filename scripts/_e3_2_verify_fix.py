"""Quick verify E3.2 fix on a few races (Bahrain HARD-HARD, NL clean, Japan)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.physics.deg_corrections import detrend_fuel_pace  # noqa: E402
from aris.physics.stint import compute_stint_metrics, detect_stints  # noqa: E402
from aris.physics.tires import fit_track_compound_slopes, normalize_compound  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))

for year, gp in [(2024, "Bahrain"), (2024, "Netherlands"), (2024, "Japan"), (2024, "China"), (2024, "Spain")]:
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    enriched = detect_stints(session.laps)
    total = int(getattr(session, "total_laps", None) or enriched["LapNumber"].max())
    fuelled = detrend_fuel_pace(enriched, total_laps=total)
    metrics = compute_stint_metrics(fuelled, min_laps=3)
    metrics = metrics[metrics["DegSlope"].notna() & (metrics["NumLaps"] >= 5)].copy()
    metrics = metrics[(metrics["DegSlope"] >= -0.5) & (metrics["DegSlope"] <= 1.0)]
    metrics["Compound"] = metrics["Compound"].map(normalize_compound)
    metrics["SessionKey"] = f"{year}-R"
    # merge check
    n_multi = 0
    if "Stint" in enriched.columns:
        for drv, g in enriched.groupby("Driver"):
            for sid, sg in g.groupby("StintId"):
                if sg["Stint"].dropna().nunique() > 1:
                    n_multi += 1
    slopes = fit_track_compound_slopes(metrics)
    dry = {k: round(float(slopes.get(k, float("nan"))), 4) for k in ("SOFT", "MEDIUM", "HARD")}
    ok = dry["SOFT"] > dry["MEDIUM"] > dry["HARD"] and all(0 < dry[k] <= 0.25 for k in dry)
    print(
        f"{year} {gp}: SOFT={dry['SOFT']} MED={dry['MEDIUM']} HARD={dry['HARD']} "
        f"order_mag_ok={ok} n_stints={len(metrics)} merged_ff1_bugs={n_multi}"
    )
    for comp in ("SOFT", "MEDIUM", "HARD"):
        sub = metrics[metrics["Compound"] == comp]
        if sub.empty:
            continue
        print(
            f"  {comp}: n={len(sub)} mean_len={sub['NumLaps'].mean():.1f} "
            f"median_slope={sub['DegSlope'].median():.4f}"
        )
