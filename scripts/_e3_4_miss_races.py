"""E3.4 — per-race diagnosis for races that missed 1.5× MA(2) in E2.7."""
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
    predict_blended_frame,
    reset_model_cache,
)
from aris.models.residual import ResidualModel  # noqa: E402
from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402
from aris.tracks import clear_track_config_cache, load_track_config  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))

# E2.7 misses (ex Sao Paulo handled in E3.3)
_RACES = [
    ("Australia", 0.486, 0.909, 0.729),
    ("China", 0.400, 0.933, 0.600),
    ("Spain", 0.484, 0.913, 0.726),
    ("Belgium", 0.444, 0.780, 0.666),
    ("Italy", 0.469, 1.009, 0.704),
    ("United States", 0.394, 0.729, 0.591),
]


def mae(a, b) -> float:
    return float(np.mean(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))))


def diagnose(gp: str, ma2_e2: float, blend_e2: float, aimed: float) -> dict:
    clear_track_config_cache()
    reset_model_cache()
    cfg = load_track_config(gp)
    frame = build_from_fastf1(2024, gp)
    target = frame["target"].to_numpy(dtype=float)
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
    blended = predict_blended_frame(frame)
    # MA(2) on clean laps for this build
    session = fastf1.get_session(2024, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    clean = filter_clean_laps(detect_stints(session.laps))
    ma2 = moving_average_baseline(clean, window=2).reindex(clean.index)
    mask = ma2.notna()
    ma2_mae = mae(clean.loc[mask, "LapTimeS"], ma2.loc[mask])

    true_res = target - phys
    phys_med = float(np.median(phys))
    tgt_med = float(np.median(target))
    lag1 = frame["lag1_pace"].to_numpy(dtype=float)
    gap = np.abs(phys - lag1)
    gap = gap[np.isfinite(gap)]

    slopes = cfg.compound_slopes
    out = {
        "gp": gp,
        "n": len(frame),
        "ma2_mae": round(ma2_mae, 4),
        "ma2_e2_ref": ma2_e2,
        "aimed_1_5x_ma2": round(1.5 * ma2_mae, 4),
        "aimed_e2_ref": aimed,
        "phys_mae": round(mae(phys, target), 4),
        "phys_res_raw_mae": round(mae(phys + raw, target), 4),
        "phys_res_damped_mae": round(mae(phys + damped, target), 4),
        "blend_mae": round(mae(blended, target), 4),
        "blend_e2_ref": blend_e2,
        "pass_aimed": bool(mae(blended, target) <= 1.5 * ma2_mae),
        "phys_median": round(phys_med, 3),
        "target_median": round(tgt_med, 3),
        "phys_bias_med": round(phys_med - tgt_med, 3),
        "true_res_mean": round(float(np.mean(true_res)), 4),
        "raw_res_mean": round(float(np.mean(raw)), 4),
        "damped_res_mean": round(float(np.mean(damped)), 4),
        "mean_abs_phys_lag1_gap": round(float(np.mean(gap)), 4) if len(gap) else None,
        "frac_gap_lt_4s": round(float(np.mean(gap < 4)), 4) if len(gap) else None,
        "frac_gap_lt_8s": round(float(np.mean(gap < 8)), 4) if len(gap) else None,
        "compound_slopes": {k: float(v) for k, v in (slopes or {}).items()}
        if slopes
        else None,
        "yaml_stem": cfg.stem if hasattr(cfg, "stem") else None,
        "track_name": getattr(cfg, "name", None),
        "n_corners": len(getattr(cfg, "corners", []) or []),
    }
    # Bucket residual helpfulness
    buckets = []
    for lo, hi in [(0, 4), (4, 10), (10, 20), (20, 100)]:
        m = (np.abs(true_res) >= lo) & (np.abs(true_res) < hi)
        if not m.any():
            continue
        buckets.append(
            {
                "abs_phys_err": f"[{lo},{hi})",
                "n": int(m.sum()),
                "phys_mae": round(mae(phys[m], target[m]), 3),
                "damped_mae": round(mae(phys[m] + damped[m], target[m]), 3),
                "raw_mae": round(mae(phys[m] + raw[m], target[m]), 3),
            }
        )
    out["buckets"] = buckets
    return out


def main() -> None:
    results = []
    for gp, ma2, blend, aimed in _RACES:
        print(f"\n=== {gp} ===", flush=True)
        try:
            r = diagnose(gp, ma2, blend, aimed)
        except Exception as exc:  # noqa: BLE001
            r = {"gp": gp, "error": repr(exc)}
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k != "buckets"}, indent=2), flush=True)
        if "buckets" in r:
            print("buckets:", r["buckets"], flush=True)

    path = _ROOT / "results" / "e3_4_miss_races_diagnosis.json"
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nWrote {path}", flush=True)
    print("\nSUMMARY", flush=True)
    for r in results:
        if "error" in r:
            print(f"  {r['gp']}: ERROR {r['error']}")
            continue
        print(
            f"  {r['gp']:<16} blend={r['blend_mae']:.3f} aimed={r['aimed_1_5x_ma2']:.3f} "
            f"{'PASS' if r['pass_aimed'] else 'MISS'} "
            f"(E2 blend={r['blend_e2_ref']:.3f}) phys={r['phys_mae']:.3f}"
        )


if __name__ == "__main__":
    main()
