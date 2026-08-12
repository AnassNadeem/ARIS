"""Score current blended predictor on specific Zandvoort races (2024 held-out + 2025)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: F401
import fastf1
import numpy as np

from aris.eval.baseline import moving_average_baseline
from aris.eval.scoring import mae
from aris.models.features import build_from_fastf1
from aris.models.predict import predict_blended_frame, predict_from_lap_row, reset_model_cache
from aris.physics.stint import detect_stints, filter_clean_laps

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))


def score_race(year: int, gp: str) -> None:
    reset_model_cache()
    print(f"\n=== {year} {gp} ===", flush=True)

    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    preds = moving_average_baseline(clean, window=2).reindex(clean.index)
    mask = preds.notna()
    ma2 = mae(clean.loc[mask, "LapTimeS"].to_numpy(), preds.loc[mask].to_numpy())
    print(f"MA(2)              n={int(mask.sum()):4d}  MAE={ma2:.3f} s", flush=True)

    frame = build_from_fastf1(year, gp)
    if frame.empty:
        print("NO FEATURE FRAME", flush=True)
        return
    y = frame["target"].to_numpy()
    phys = frame["physics_pred"].to_numpy()
    print(f"Physics-only       n={len(y):4d}  MAE={mae(y, phys):.3f} s", flush=True)

    y_pr = np.array([predict_from_lap_row(row) for _, row in frame.iterrows()])
    print(f"Physics+residual   n={len(y):4d}  MAE={mae(y, y_pr):.3f} s", flush=True)

    y_b = predict_blended_frame(frame)
    print(f"Blended            n={len(y):4d}  MAE={mae(y, y_b):.3f} s", flush=True)


def main() -> None:
    for year, gp in [(2024, "Netherlands"), (2025, "Netherlands")]:
        score_race(year, gp)


if __name__ == "__main__":
    main()
