"""E3.1 follow-up: same-compound pit stops vs StintId splitting."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))

for year, gp in [(2024, "Bahrain"), (2024, "Netherlands"), (2024, "China"), (2024, "Japan")]:
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    raw = session.laps
    enriched = detect_stints(raw)

    # Count same-compound pit crossings: pit-in lap followed by next lap same compound
    merges = []
    for drv, g in enriched.groupby("Driver"):
        g = g.sort_values("LapNumber")
        for i in range(len(g) - 1):
            a = g.iloc[i]
            b = g.iloc[i + 1]
            pit_in = pd.notna(a.get("PitInTime"))
            same_comp = str(a["Compound"]) == str(b["Compound"])
            same_stint = int(a["StintId"]) == int(b["StintId"])
            tyre_reset = (
                pd.notna(a.get("TyreLife"))
                and pd.notna(b.get("TyreLife"))
                and int(b["TyreLife"]) < int(a["TyreLife"])
            )
            if pit_in and same_comp:
                merges.append(
                    {
                        "driver": drv,
                        "lap_in": int(a["LapNumber"]),
                        "lap_out": int(b["LapNumber"]),
                        "compound": str(a["Compound"]),
                        "stint_id_same": same_stint,
                        "tyre_reset": bool(tyre_reset),
                        "tl_before": int(a["TyreLife"]) if pd.notna(a["TyreLife"]) else None,
                        "tl_after": int(b["TyreLife"]) if pd.notna(b["TyreLife"]) else None,
                        "ff1_stint_a": int(a["Stint"]) if "Stint" in g.columns and pd.notna(a.get("Stint")) else None,
                        "ff1_stint_b": int(b["Stint"]) if "Stint" in g.columns and pd.notna(b.get("Stint")) else None,
                    }
                )

    print(f"\n=== {year} {gp}: same-compound pit crossings: {len(merges)} ===")
    for m in merges[:12]:
        print(m)

    # How often does our StintId disagree with FastF1 Stint?
    if "Stint" in enriched.columns:
        cmp = enriched.dropna(subset=["Stint"]).copy()
        # Within driver, count unique (StintId, Stint) mismatches by grouping
        disagree = 0
        total = 0
        for drv, g in cmp.groupby("Driver"):
            # map our stint ids vs FF1
            for sid, sg in g.groupby("StintId"):
                ff1_stints = sg["Stint"].dropna().unique()
                total += 1
                if len(ff1_stints) > 1:
                    disagree += 1
                    print(
                        f"  MERGE BUG {drv} our StintId={sid} covers FF1 Stints={sorted(int(x) for x in ff1_stints)} "
                        f"comp={sg['Compound'].iloc[0]} laps={int(sg['LapNumber'].min())}-{int(sg['LapNumber'].max())}"
                    )
        print(f"  our-stints covering multiple FF1 stints: {disagree}/{total}")
