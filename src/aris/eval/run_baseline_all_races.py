"""Multi-race MA(window) baseline runner across the eight Week 2 races.

Promoted from the Week 2 dry-run script `scripts/wk2_day3_block4.py` (which
carried its own inline copies of `detect_stints` / `filter_clean_laps` /
`moving_average_baseline`). This version imports the canonical implementations
from the package, so the runner and the rest of ARIS can never drift apart, and
defaults to `window=2` — the floor recorded in `results/wk2-baseline-mae.csv`.

Run it:
    python -m aris.eval.run_baseline_all_races
    python -m aris.eval.run_baseline_all_races --window 3
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from aris.eval.baseline import moving_average_baseline
from aris.eval.scoring import mae, per_race_mae
from aris.physics.stint import detect_stints, filter_clean_laps

# src/aris/eval/run_baseline_all_races.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_CACHE_DIR = _REPO_ROOT / "fastf1_cache"

# The eight races Week 2 scored the baseline on (all pre-warmed in fastf1_cache/).
RACES: list[tuple[int, str]] = [
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
    """Return (actual, predicted) MA(window) lap times for one race."""
    import fastf1  # lazy: import aris first so the requests shim is applied.

    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    preds = moving_average_baseline(clean, window=window).reindex(clean.index)
    mask = preds.notna()
    return clean.loc[mask, "LapTimeS"].to_numpy(), preds.loc[mask].to_numpy()


def run(window: int = 2) -> dict[str, float]:
    """Score every race, print per-race + overall MAE, return the per-race dict."""
    import fastf1

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(_CACHE_DIR))

    all_true: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    all_rids: list[np.ndarray] = []
    for year, gp in RACES:
        race_id = f"{year}-{gp.replace(' ', '_')}"
        yt, yp = score_race(year, gp, window)
        all_true.append(yt)
        all_pred.append(yp)
        all_rids.append(np.full(len(yt), race_id))
        print(f"{race_id:22s} n={len(yt):4d}  MAE={mae(yt, yp):.6f} s")

    yt_all = np.concatenate(all_true)
    yp_all = np.concatenate(all_pred)
    rids_all = np.concatenate(all_rids)
    overall = mae(yt_all, yp_all)
    print(f"\noverall MAE = {overall:.6f} s across {len(yt_all)} laps in {len(RACES)} races")
    return per_race_mae(yt_all, yp_all, rids_all)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-race MA(window) baseline runner.")
    parser.add_argument("--window", type=int, default=2, help="moving-average window (default 2)")
    args = parser.parse_args()
    run(window=args.window)


if __name__ == "__main__":
    main()
