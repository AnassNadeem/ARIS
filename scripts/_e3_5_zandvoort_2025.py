"""E3.5 — why Zandvoort 2025 misses 1.5× MA(2) while 2024 passes."""
from __future__ import annotations

import json
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
    damp_residual_toward_pace,
    ma2_from_lags,
    predict_blended_frame,
    predict_from_lap_row,
    reset_model_cache,
)
from aris.models.residual import ResidualModel  # noqa: E402
from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402
from aris.tracks import clear_track_config_cache  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))


def mae(a, b):
    return float(np.mean(np.abs(np.asarray(a) - np.asarray(b))))


def analyse(year: int) -> dict:
    clear_track_config_cache()
    reset_model_cache()
    gp = "Netherlands"
    frame = build_from_fastf1(year, gp)
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    ma2 = moving_average_baseline(clean, window=2).reindex(clean.index)
    m = ma2.notna()
    ma2_mae = mae(clean.loc[m, "LapTimeS"], ma2.loc[m])

    y = frame["target"].to_numpy(dtype=float)
    phys = frame["physics_pred"].to_numpy(dtype=float)
    model = ResidualModel.load()
    raw = model.predict_residual(frame)
    damped = np.array(
        [
            damp_residual_toward_pace(
                float(phys[i]),
                float(frame.iloc[i]["lag1_pace"])
                if np.isfinite(frame.iloc[i]["lag1_pace"])
                else None,
                float(raw[i]),
            )
            for i in range(len(frame))
        ]
    )
    blend = predict_blended_frame(frame)
    phys_res = phys + damped

    # Weather
    weather = {}
    try:
        w = session.weather_data
        if w is not None and len(w):
            weather = {
                "rain_any": bool(w["Rainfall"].fillna(False).astype(bool).any())
                if "Rainfall" in w.columns
                else None,
                "track_temp_median": float(w["TrackTemp"].median())
                if "TrackTemp" in w.columns
                else None,
                "air_temp_median": float(w["AirTemp"].median())
                if "AirTemp" in w.columns
                else None,
                "humidity_median": float(w["Humidity"].median())
                if "Humidity" in w.columns
                else None,
            }
    except Exception as exc:  # noqa: BLE001
        weather = {"error": repr(exc)}

    # Strategy / compound mix
    compounds = (
        clean.groupby("Compound").size().astype(int).to_dict()
        if "Compound" in clean.columns
        else {}
    )
    stint_lens = (
        clean.groupby(["Driver", "StintId"]).size().describe().to_dict()
        if len(clean)
        else {}
    )

    # Track status richness
    ts_counts = (
        session.laps["TrackStatus"].astype(str).value_counts().head(8).to_dict()
        if "TrackStatus" in session.laps.columns
        else {}
    )

    # Pace level
    out = {
        "year": year,
        "n_frame": len(frame),
        "n_clean": len(clean),
        "ma2_mae": round(ma2_mae, 4),
        "aimed": round(1.5 * ma2_mae, 4),
        "phys_mae": round(mae(phys, y), 4),
        "phys_res_mae": round(mae(phys_res, y), 4),
        "blend_mae": round(mae(blend, y), 4),
        "pass": bool(mae(blend, y) <= 1.5 * ma2_mae),
        "phys_median": round(float(np.median(phys)), 3),
        "target_median": round(float(np.median(y)), 3),
        "phys_bias": round(float(np.median(phys) - np.median(y)), 3),
        "raw_res_mean": round(float(np.mean(raw)), 4),
        "damped_res_mean": round(float(np.mean(damped)), 4),
        "mean_abs_phys_lag1": round(
            float(np.mean(np.abs(phys - frame["lag1_pace"].to_numpy(dtype=float)))), 4
        ),
        "weather": weather,
        "compound_counts_clean": {str(k): int(v) for k, v in compounds.items()},
        "track_status_top": {str(k): int(v) for k, v in ts_counts.items()},
        "total_laps_session": int(getattr(session, "total_laps", 0) or 0),
    }

    # Error by compound_code
    by_comp = {}
    for c, g in frame.assign(err=np.abs(y - blend)).groupby("compound_code"):
        by_comp[str(int(c))] = {
            "n": int(len(g)),
            "blend_mae": round(float(g["err"].mean()), 4),
        }
    out["blend_by_compound_code"] = by_comp

    # SC-affected?
    out["frac_nongreen_raw_laps"] = round(
        float((session.laps["TrackStatus"].astype(str) != "1").mean()), 4
    ) if "TrackStatus" in session.laps.columns else None

    return out


def main() -> None:
    results = {str(y): analyse(y) for y in (2024, 2025)}
    # Diff highlights
    a, b = results["2024"], results["2025"]
    diff = {
        "blend_delta_2025_minus_2024": round(b["blend_mae"] - a["blend_mae"], 4),
        "ma2_delta": round(b["ma2_mae"] - a["ma2_mae"], 4),
        "phys_mae_delta": round(b["phys_mae"] - a["phys_mae"], 4),
        "target_median_delta": round(b["target_median"] - a["target_median"], 4),
        "phys_bias_delta": round(b["phys_bias"] - a["phys_bias"], 4),
        "weather_2024": a["weather"],
        "weather_2025": b["weather"],
        "compounds_2024": a["compound_counts_clean"],
        "compounds_2025": b["compound_counts_clean"],
        "nongreen_frac_2024": a["frac_nongreen_raw_laps"],
        "nongreen_frac_2025": b["frac_nongreen_raw_laps"],
    }
    payload = {"years": results, "diff": diff}
    path = _ROOT / "results" / "e3_5_zandvoort_2025.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2), flush=True)
    print(f"Wrote {path}", flush=True)


if __name__ == "__main__":
    main()
