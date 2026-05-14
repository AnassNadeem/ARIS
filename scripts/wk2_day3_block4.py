"""Wk2 Day 3 Block 4 dry-run: multi-race MA(3) baseline across the 8 cached races."""

import sys
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aris.eval.scoring import mae, per_race_mae  # noqa: E402

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


def detect_stints(laps_df: pd.DataFrame) -> pd.DataFrame:
    df = laps_df.sort_values(["Driver", "LapNumber"]).copy()
    df["LapTimeS"] = df["LapTime"].dt.total_seconds()
    df["CompoundChange"] = df.groupby("Driver")["Compound"].transform(lambda s: s != s.shift(1))
    df["StintId"] = df.groupby("Driver")["CompoundChange"].cumsum()
    return df


def filter_clean_laps(enriched: pd.DataFrame) -> pd.DataFrame:
    e = enriched[enriched["LapTimeS"].notna()].copy()
    e = e[e["PitOutTime"].isna() & e["PitInTime"].isna()]
    return e


def moving_average_baseline(laps_df: pd.DataFrame, window: int = 3) -> pd.Series:
    return (
        laps_df
        .sort_values(["Driver", "StintId", "LapNumber"])
        .groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
        .transform(lambda s: s.shift(1).rolling(window).mean())
    )


def score_race(year: int, gp: str, window: int = 3):
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    enriched = detect_stints(session.laps)
    clean = filter_clean_laps(enriched)
    preds = moving_average_baseline(clean, window=window).reindex(clean.index)
    mask = preds.notna()
    return clean.loc[mask, "LapTimeS"].to_numpy(), preds.loc[mask].to_numpy()


def main() -> None:
    rows = []
    all_true: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    all_rids: list[np.ndarray] = []

    for year, gp in RACES:
        rid = f"{year}-{gp.replace(' ', '_')}"
        yt, yp = score_race(year, gp, window=3)
        race_mae = mae(yt, yp)
        rows.append({"race_id": rid, "n_laps": len(yt), "mae_s": race_mae})
        all_true.append(yt)
        all_pred.append(yp)
        all_rids.append(np.array([rid] * len(yt)))
        print(f"{rid:30s}  n={len(yt):4d}  MAE={race_mae:.3f} s")

    df = pd.DataFrame(rows)
    yt_all = np.concatenate(all_true)
    yp_all = np.concatenate(all_pred)
    rids_all = np.concatenate(all_rids)
    overall = mae(yt_all, yp_all)
    per_race = per_race_mae(yt_all, yp_all, rids_all)

    print("\nPer-race MAE (via aris.eval.scoring.per_race_mae):")
    for k, v in per_race.items():
        print(f"  {k:30s}  {v:.3f} s")
    print(f"\nOverall MAE across {len(yt_all)} laps in 8 races: {overall:.3f} s")

    out_csv = ROOT / "results" / "wk2-baseline-mae.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(f"\nwrote {out_csv}")
    print(f"overall (concatenated): {overall:.4f} s")


if __name__ == "__main__":
    main()
