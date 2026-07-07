"""Held-out lap-time MAE evaluation harness."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from aris.eval.baseline import moving_average_baseline
from aris.eval.scoring import mae, per_race_mae
from aris.models.features import build_from_fastf1
from aris.models.predict import predict_from_lap_row, reset_model_cache
from aris.models.residual import DEFAULT_MODEL_PATH, train_residual_model
from aris.physics.stint import detect_stints, filter_clean_laps

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BASELINE_FLOOR_S = 0.460

HELD_OUT_RACES: list[tuple[int, str]] = [
    (2024, "Japan"),
    (2024, "Miami"),
    (2023, "Belgium"),
    (2023, "Abu Dhabi"),
    (2024, "Australia"),
]


def _score_baseline(year: int, gp: str, window: int = 2) -> tuple[np.ndarray, np.ndarray, str]:
    import fastf1

    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    preds = moving_average_baseline(clean, window=window).reindex(clean.index)
    mask = preds.notna()
    race_id = f"{year}-{gp.replace(' ', '_')}"
    return clean.loc[mask, "LapTimeS"].to_numpy(), preds.loc[mask].to_numpy(), race_id


def _score_predictor(year: int, gp: str) -> tuple[np.ndarray, np.ndarray, str]:
    race_id = f"{year}-{gp.replace(' ', '_')}"
    frame = build_from_fastf1(year, gp)
    if frame.empty:
        return np.array([]), np.array([]), race_id
    y_true = frame["target"].to_numpy()
    y_pred = np.array([predict_from_lap_row(row) for _, row in frame.iterrows()])
    return y_true, y_pred, race_id


def run_eval(*, train_if_missing: bool = True) -> dict[str, float]:
    import fastf1

    cache = _REPO_ROOT / "fastf1_cache"
    cache.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache))

    reset_model_cache()
    if train_if_missing and not DEFAULT_MODEL_PATH.exists():
        print("No residual model found — training now...")
        _, metrics = train_residual_model()
        print(f"Training CV MAE: {metrics['cv_mae_mean']:.3f} +/- {metrics['cv_mae_std']:.3f} s")
        reset_model_cache()

    all_true: list[np.ndarray] = []
    all_pred: list[np.ndarray] = []
    all_rids: list[np.ndarray] = []
    per_race: dict[str, float] = {}

    print("=== ARIS predictor (physics + tyres + XGBoost residual) ===")
    for year, gp in HELD_OUT_RACES:
        yt, yp, rid = _score_predictor(year, gp)
        if len(yt) == 0:
            print(f"{rid:22s} SKIP (no scored laps)")
            continue
        m = mae(yt, yp)
        per_race[rid] = m
        all_true.append(yt)
        all_pred.append(yp)
        all_rids.append(np.full(len(yt), rid))
        print(f"{rid:22s} n={len(yt):4d}  MAE={m:.3f} s")

    overall = mae(np.concatenate(all_true), np.concatenate(all_pred))
    print(f"\nOverall held-out MAE = {overall:.3f} s  (baseline floor = {_BASELINE_FLOOR_S:.3f} s)")
    if overall < _BASELINE_FLOOR_S:
        print("PASS — beats MA(2) baseline floor.")
    else:
        print("NOTE — does not beat MA(2) floor yet; stack still usable for strategy demo.")

    yt = np.concatenate(all_true)
    yp = np.concatenate(all_pred)
    rids = np.concatenate(all_rids)
    return per_race_mae(yt, yp, rids)


def main() -> None:
    parser = argparse.ArgumentParser(description="Held-out lap-time MAE evaluation.")
    parser.add_argument("--no-train", action="store_true", help="fail if model artefact missing")
    args = parser.parse_args()
    run_eval(train_if_missing=not args.no_train)


if __name__ == "__main__":
    main()
