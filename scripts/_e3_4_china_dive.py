"""E3.4 China deep-dive — why still short of 1.5× MA(2)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.eval.baseline import moving_average_baseline  # noqa: E402
from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import (  # noqa: E402
    ma2_from_lags,
    predict_blended_frame,
    predict_from_lap_row,
    reset_model_cache,
)
from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))
reset_model_cache()
frame = build_from_fastf1(2024, "China")
y = frame["target"].to_numpy(dtype=float)
phys = frame["physics_pred"].to_numpy(dtype=float)
blend = predict_blended_frame(frame)
phys_res = np.array([predict_from_lap_row(r) for _, r in frame.iterrows()])

# Per-lap MA2 availability
has_ma2 = frame.apply(
    lambda r: ma2_from_lags(
        float(r["lag1_pace"]) if pd.notna(r["lag1_pace"]) else None,
        float(r["lag2_pace"]) if pd.notna(r["lag2_pace"]) else None,
    )
    is not None,
    axis=1,
).to_numpy()

def mae(a, b):
    return float(np.mean(np.abs(a - b)))

print(f"n={len(frame)} has_ma2={has_ma2.sum()} no_ma2={(~has_ma2).sum()}")
print(f"overall blend={mae(blend,y):.4f} physres={mae(phys_res,y):.4f} phys={mae(phys,y):.4f}")
print(f"blend on ma2-laps={mae(blend[has_ma2], y[has_ma2]):.4f}")
print(f"blend on no-ma2={mae(blend[~has_ma2], y[~has_ma2]):.4f}")
print(f"physres on no-ma2={mae(phys_res[~has_ma2], y[~has_ma2]):.4f}")

# Compare to clean-lap MA2 baseline
session = fastf1.get_session(2024, "China", "R")
session.load(laps=True, telemetry=False, weather=False, messages=False)
clean = filter_clean_laps(detect_stints(session.laps))
ma2 = moving_average_baseline(clean, window=2).reindex(clean.index)
m = ma2.notna()
print(f"clean MA2 mae={mae(clean.loc[m,'LapTimeS'], ma2.loc[m]):.4f} n={int(m.sum())}")

# Error by tyre life / lap buckets
work = frame.copy()
work["err_blend"] = np.abs(y - blend)
work["err_pr"] = np.abs(y - phys_res)
work["has_ma2"] = has_ma2
print("\nBy compound:")
for c, g in work.groupby(work.get("compound", work.get("Compound", pd.Series(["?"])*len(work)))):
    print(f"  {c}: n={len(g)} blend_mae={g['err_blend'].mean():.4f} pr={g['err_pr'].mean():.4f}")

# compound_code
print("\nBy compound_code:")
for c, g in work.groupby("compound_code"):
    print(f"  code={c}: n={len(g)} blend={g['err_blend'].mean():.4f}")

print("\nBy tyre_life quartile:")
work["tl_q"] = pd.qcut(work["tyre_life"], 4, duplicates="drop")
print(work.groupby("tl_q", observed=True)["err_blend"].mean())

print("\nTop 15 worst blend errors:")
cols = ["Driver", "LapNumber", "tyre_life", "compound_code", "target", "physics_pred", "err_blend", "err_pr", "has_ma2"]
# Driver may be in frame
for c in ("Driver", "LapNumber"):
    if c not in work.columns and c.lower() in [x.lower() for x in work.columns]:
        pass
worst = work.nlargest(15, "err_blend")
print(worst[[c for c in cols if c in worst.columns]].to_string(index=False))

# SC / wet?
if "TrackStatus" in clean.columns:
    print("\nTrackStatus value counts (clean):")
    print(clean["TrackStatus"].astype(str).value_counts().head())
print("Rainfall" if "Rainfall" in session.laps.columns else "no Rainfall col on laps")
