"""Recompute the Week 2 MA(2) lap-time baseline -> results/wk2-baseline-mae.csv.

Background: the committed `wk2-baseline-mae.csv` declared `window=2` in its
footer, but its per-race rows were actually generated at window=3 — the
`wk2_day3_block4.py` dry-run default — totalling 6391 laps, not the 6734 the
window=2 entry of `wk2-window-sweep.csv` records. Week 3 Day 4's SQL baseline
cross-check surfaced the inconsistency.

This script regenerates the file correctly at window=2 through the package API
(`aris.physics.stint` / `aris.eval.baseline` / `aris.eval.scoring`) — the same
pandas-over-FastF1 path Week 2 used — so the artifact is self-consistent and
the cross-check has a correct target.

    python scripts/recompute_wk2_baseline.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `aris` importable when the package is not installed into the environment.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import fastf1  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from aris.eval.baseline import moving_average_baseline  # noqa: E402
from aris.eval.scoring import mae  # noqa: E402
from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402

CACHE = ROOT / "fastf1_cache"
OUT_CSV = ROOT / "results" / "wk2-baseline-mae.csv"
WINDOW = 2

# The 8 races Week 2 scored the baseline on (all pre-warmed in fastf1_cache/).
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


def score_race(year: int, gp: str, window: int) -> tuple[np.ndarray, np.ndarray]:
    """Return (actual, predicted) lap times for the MA(window) baseline of one race."""
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    preds = moving_average_baseline(clean, window=window).reindex(clean.index)
    mask = preds.notna()
    return clean.loc[mask, "LapTimeS"].to_numpy(), preds.loc[mask].to_numpy()


def main() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE))

    rows: list[dict] = []
    all_true: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    for year, gp in RACES:
        race_id = f"{year}-{gp.replace(' ', '_')}"
        yt, yp = score_race(year, gp, WINDOW)
        rows.append({"race_id": race_id, "n_laps": len(yt), "mae_s": mae(yt, yp)})
        all_true.append(yt)
        all_pred.append(yp)
        print(f"{race_id:22s} n={len(yt):4d}  MAE={mae(yt, yp):.6f} s")

    df = pd.DataFrame(rows)
    overall = mae(np.concatenate(all_true), np.concatenate(all_pred))
    total = int(df["n_laps"].sum())

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    with OUT_CSV.open("a", encoding="utf-8") as fh:
        fh.write(
            f"# BASELINE: window={WINDOW}, MAE={overall:.3f} s, "
            f"{len(RACES)} races ({total} laps), leakage-free per-stint shift. "
            f"Floor that Phase 3 must beat.\n"
        )

    print(f"\noverall MAE = {overall:.6f} s across {total} laps in {len(RACES)} races")
    print(f"wrote {OUT_CSV}")


if __name__ == "__main__":
    main()
