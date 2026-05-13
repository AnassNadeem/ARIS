"""Wk2 Day 3 Block 5 dry-run: sweep window in [1,2,3,5,7], pick the elbow."""

from pathlib import Path
import sys

import fastf1
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.eval.scoring import mae  # noqa: E402

CACHE = ROOT / "fastf1_cache"
fastf1.Cache.enable_cache(str(CACHE))

RACES = [
    (2024, "Bahrain"),
    (2024, "Saudi Arabia"),
    (2024, "Australia"),
    (2024, "Japan"),
    (2024, "Miami"),
    (2023, "Bahrain"),
    (2023, "Belgium"),
    (2023, "Abu Dhabi"),
]


def detect_stints(laps_df):
    df = laps_df.sort_values(["Driver", "LapNumber"]).copy()
    df["LapTimeS"] = df["LapTime"].dt.total_seconds()
    df["CompoundChange"] = df.groupby("Driver")["Compound"].transform(lambda s: s != s.shift(1))
    df["StintId"] = df.groupby("Driver")["CompoundChange"].cumsum()
    return df


def filter_clean_laps(enriched):
    e = enriched[enriched["LapTimeS"].notna()].copy()
    e = e[e["PitOutTime"].isna() & e["PitInTime"].isna()]
    return e


def moving_average_baseline(laps_df, window):
    return (
        laps_df
        .sort_values(["Driver", "StintId", "LapNumber"])
        .groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
        .transform(lambda s: s.shift(1).rolling(window).mean())
    )


# Cache all (race, clean_df) up-front so we don't reload 5x.
race_frames = []
for year, gp in RACES:
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    enriched = detect_stints(session.laps)
    race_frames.append((f"{year}-{gp.replace(' ', '_')}", filter_clean_laps(enriched)))

WINDOWS = [1, 2, 3, 5, 7]
rows = []
for w in WINDOWS:
    yt_all = []
    yp_all = []
    for rid, clean in race_frames:
        preds = moving_average_baseline(clean, window=w).reindex(clean.index)
        mask = preds.notna()
        yt_all.append(clean.loc[mask, "LapTimeS"].to_numpy())
        yp_all.append(preds.loc[mask].to_numpy())
    yt = np.concatenate(yt_all)
    yp = np.concatenate(yp_all)
    m = mae(yt, yp)
    rows.append({"window": w, "mae_s": m, "n_laps": len(yt)})
    print(f"window={w}  n={len(yt):5d}  MAE={m:.4f} s")

sweep = pd.DataFrame(rows)
best_idx = int(sweep["mae_s"].idxmin())
best = sweep.loc[best_idx]
print(f"\nbest window = {int(best['window'])} with MAE = {best['mae_s']:.4f} s")

out_csv = ROOT / "results" / "wk2-window-sweep.csv"
sweep.to_csv(out_csv, index=False)
print(f"wrote {out_csv}")

fig, ax = plt.subplots(figsize=(7, 4))
ax.plot(sweep["window"], sweep["mae_s"], marker="o", color="#e10600", linewidth=2)
ax.scatter([best["window"]], [best["mae_s"]], color="#333", zorder=5, s=80, label=f"best (w={int(best['window'])})")
ax.set_xlabel("rolling window (laps)")
ax.set_ylabel("MAE (s)")
ax.set_title("Moving-average baseline — window sweep across 8 cached races")
ax.grid(True, alpha=0.3)
ax.legend()
fig.tight_layout()
out_png = ROOT / "assets" / "screenshots" / "wk2-baseline-window-sweep.png"
out_png.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(out_png, dpi=140, bbox_inches="tight")
print(f"wrote {out_png}")
