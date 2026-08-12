"""Phase E2.1 — diagnose badly-broken 2024 circuits (read-only).

For each listed race: bias vs variance of errors, physics_pred ballpark vs
real lap times, YAML corner geometry sanity, and REFERENCE_RACES depth.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

import aris  # noqa: E402, F401
import fastf1  # noqa: E402

from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import predict_blended_frame, reset_model_cache  # noqa: E402
from aris.models.residual import REFERENCE_RACES  # noqa: E402
from aris.physics.bicycle import Car, StintState, predict_lap_time  # noqa: E402
from aris.tracks import clear_track_config_cache, load_track_config  # noqa: E402

_CACHE = _ROOT / "fastf1_cache"

# Phase D blended MAE offenders (plus Italy-like Monza for high-speed check).
BAD_RACES: list[tuple[int, str, float]] = [
    (2024, "Japan", 3.681),
    (2024, "Canada", 3.260),
    (2024, "Las Vegas", 3.441),
    (2024, "Mexico City", 3.216),
    (2024, "Austria", 2.756),
    (2024, "Emilia Romagna", 2.871),
    (2024, "United States", 2.283),
    (2024, "Azerbaijan", 2.115),
    (2024, "Miami", 2.277),
]

# Approximate real-world dry race lap ballpark (pole/race-pace mid, seconds).
# Used only as a sanity check — not a scoring target.
REAL_BALLPARK_S: dict[str, tuple[float, float]] = {
    "Japan": (88.0, 96.0),
    "Canada": (72.0, 80.0),
    "Las Vegas": (92.0, 102.0),
    "Mexico City": (76.0, 86.0),
    "Austria": (65.0, 73.0),
    "Emilia Romagna": (74.0, 84.0),
    "United States": (93.0, 103.0),
    "Azerbaijan": (100.0, 110.0),
    "Miami": (88.0, 98.0),
    "Italy": (80.0, 88.0),
}

# Map held-out short names / event fragments → REFERENCE_RACES GP substrings.
REF_MATCH: dict[str, list[str]] = {
    "Japan": ["Japanese Grand Prix"],
    "Canada": ["Canadian Grand Prix"],
    "Las Vegas": ["Las Vegas Grand Prix"],
    "Mexico City": ["Mexican Grand Prix", "Mexico City Grand Prix"],
    "Austria": ["Austrian Grand Prix", "Styrian Grand Prix"],
    "Emilia Romagna": ["Emilia Romagna Grand Prix"],
    "United States": ["United States Grand Prix", "70th Anniversary Grand Prix"],
    "Azerbaijan": ["Azerbaijan Grand Prix"],
    "Miami": ["Miami Grand Prix"],
    "Italy": ["Italian Grand Prix"],
}


def _ref_depth(gp_short: str) -> list[tuple[int, str]]:
    needles = REF_MATCH.get(gp_short, [gp_short])
    hits: list[tuple[int, str]] = []
    for year, name in REFERENCE_RACES:
        for n in needles:
            if name == n or n.lower() in name.lower():
                hits.append((year, name))
                break
    return hits


def _corner_audit(cfg) -> dict:
    corners = list(cfg.corners or [])
    if not corners:
        return {
            "n_corners": 0,
            "default_radius_hits": 0,
            "arc_frac": None,
            "median_radius_m": None,
            "min_radius_m": None,
            "max_radius_m": None,
            "straight_m": None,
            "note": "no corners in YAML",
        }
    radii = [float(c.radius_m) for c in corners]
    arcs = [float(c.arc_length_m) for c in corners]
    arc_total = sum(arcs)
    lap_len = float(cfg.lap_length_m or 0.0)
    default_hits = sum(1 for r in radii if abs(r - 70.0) < 0.05)
    return {
        "n_corners": len(corners),
        "default_radius_hits": default_hits,
        "arc_frac": round(arc_total / lap_len, 3) if lap_len > 0 else None,
        "median_radius_m": round(float(np.median(radii)), 1),
        "min_radius_m": round(float(np.min(radii)), 1),
        "max_radius_m": round(float(np.max(radii)), 1),
        "straight_m": round(lap_len - arc_total, 1) if lap_len > 0 else None,
        "lap_length_m": lap_len,
        "note": "",
    }


def _classify_bias_variance(errors: np.ndarray) -> dict:
    """Systematic bias vs noisy variance.

    Rule of thumb used here (stated explicitly):
      - |mean| / MAE > 0.55  → mostly systematic bias
      - std / MAE > 1.05 and |mean| / MAE < 0.45 → mostly variance
      - else → mixed
    """
    err = errors[np.isfinite(errors)]
    if len(err) == 0:
        return {"label": "empty", "mean": None, "std": None, "mae": None}
    mean = float(np.mean(err))
    std = float(np.std(err))
    mae = float(np.mean(np.abs(err)))
    abs_mean_ratio = abs(mean) / mae if mae > 1e-9 else 0.0
    std_ratio = std / mae if mae > 1e-9 else 0.0
    if abs_mean_ratio > 0.55:
        label = "mostly_bias"
    elif std_ratio > 1.05 and abs_mean_ratio < 0.45:
        label = "mostly_variance"
    else:
        label = "mixed"
    return {
        "label": label,
        "mean": round(mean, 3),
        "std": round(std, 3),
        "mae": round(mae, 3),
        "abs_mean_over_mae": round(abs_mean_ratio, 3),
        "std_over_mae": round(std_ratio, 3),
    }


def diagnose_one(year: int, gp: str, phase_d_blend: float) -> dict:
    print(f"\n=== {year} {gp} (Phase D blend={phase_d_blend:.3f}) ===", flush=True)
    clear_track_config_cache()
    reset_model_cache()
    cfg = load_track_config(gp)
    track = cfg.load_physics()

    frame = build_from_fastf1(year, gp)
    if frame.empty:
        return {"race": f"{year} {gp}", "error": "empty frame"}

    y = frame["target"].to_numpy(dtype=float)
    phys = frame["physics_pred"].to_numpy(dtype=float)
    blended = predict_blended_frame(frame)
    # residual model path error = blended - target? We want prediction error = pred - true
    phys_err = phys - y
    blend_err = blended - y
    # Also physics+residual raw: residual adds to physics
    # blended already includes that mix; also report residual-corrected alone via
    # predict path: physics + residual ≈ from FEATURE — use blended for bias of demo stack.

    phys_stats = _classify_bias_variance(phys_err)
    blend_stats = _classify_bias_variance(blend_err)

    phys_med = float(np.median(phys))
    y_med = float(np.median(y))
    lo, hi = REAL_BALLPARK_S.get(gp, (y_med - 8, y_med + 8))
    if phys_med < lo - 5 or phys_med > hi + 5:
        ballpark = "wildly_implausible"
    elif lo <= phys_med <= hi:
        ballpark = "plausible"
    else:
        ballpark = "plausible_but_imprecise"

    # Reference physics at mediums, tyre_life=1, mid fuel
    base_state = StintState(
        car=Car(),
        track=track,
        fuel_kg=55.0,
        pit_lap=False,
        compound="MEDIUM",
        lap_in_stint=1,
    )
    base_phys = float(predict_lap_time(base_state))

    corners = _corner_audit(cfg)
    refs = _ref_depth(gp)
    years = sorted({y for y, _ in refs})

    # Street / unusual geometry flags
    street = gp in {"Las Vegas", "Azerbaijan", "Miami", "Canada", "Monaco", "Singapore"}
    high_speed = gp in {"Italy", "Austria", "Azerbaijan"}

    out = {
        "race": f"{year} {gp}",
        "phase_d_blended_mae": phase_d_blend,
        "n_laps": int(len(frame)),
        "yaml": {
            "name": cfg.name,
            "total_laps": cfg.total_laps,
            "pit_loss_s": cfg.pit_loss_s,
            "lap_length_m": cfg.lap_length_m,
        },
        "physics": {
            "median_pred_s": round(phys_med, 3),
            "median_actual_s": round(y_med, 3),
            "base_medium_pred_s": round(base_phys, 3),
            "ballpark_range_s": [lo, hi],
            "ballpark_label": ballpark,
            "error": phys_stats,
        },
        "blended": {
            "error": blend_stats,
        },
        "corners": corners,
        "geometry_class": {
            "street_circuit": street,
            "high_speed_low_corner": high_speed or (corners.get("n_corners") or 0) <= 12,
        },
        "training_depth": {
            "n_reference_races": len(refs),
            "years": years,
            "races": [f"{y} {n}" for y, n in refs],
        },
    }
    print(
        f"  phys med={phys_med:.2f} actual med={y_med:.2f} ballpark={ballpark} "
        f"phys_err={phys_stats['label']} mean={phys_stats['mean']} mae={phys_stats['mae']}",
        flush=True,
    )
    print(
        f"  blend_err={blend_stats['label']} mean={blend_stats['mean']} "
        f"std={blend_stats['std']} mae={blend_stats['mae']}",
        flush=True,
    )
    print(
        f"  corners={corners['n_corners']} arc_frac={corners['arc_frac']} "
        f"default_r70={corners['default_radius_hits']} "
        f"r_med={corners['median_radius_m']}",
        flush=True,
    )
    print(
        f"  train depth={len(refs)} years={years}",
        flush=True,
    )
    return out


def main() -> None:
    fastf1.Cache.enable_cache(str(_CACHE))
    rows = [diagnose_one(y, g, mae) for y, g, mae in BAD_RACES]

    # Also peek Italy (Monza) as high-speed low-corner reference even if not in bad list.
    print("\n=== bonus Italy (Monza geometry check) ===", flush=True)
    italy_cfg = load_track_config("Italy")
    italy_corners = _corner_audit(italy_cfg)
    italy_refs = _ref_depth("Italy")
    rows.append(
        {
            "race": "Italy (geometry-only bonus)",
            "corners": italy_corners,
            "training_depth": {
                "n_reference_races": len(italy_refs),
                "years": sorted({y for y, _ in italy_refs}),
            },
            "note": "not a Phase-D top offender; included for high-speed corner audit",
        }
    )
    print(f"  corners={italy_corners}", flush=True)

    out_path = _ROOT / "results" / "e2_1_diagnosis.json"
    out_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}", flush=True)

    # Markdown-ish console table
    print("\nSUMMARY", flush=True)
    print(
        f"{'Race':<22} {'BlendMAE':>8} {'Bias/Var':>14} "
        f"{'PhysBall':>18} {'TrainN':>6} {'ArcFrac':>8} {'R70':>4}",
        flush=True,
    )
    for r in rows:
        if "blended" not in r:
            continue
        print(
            f"{r['race']:<22} {r['phase_d_blended_mae']:8.3f} "
            f"{r['blended']['error']['label']:>14} "
            f"{r['physics']['ballpark_label']:>18} "
            f"{r['training_depth']['n_reference_races']:6d} "
            f"{str(r['corners'].get('arc_frac')):>8} "
            f"{r['corners'].get('default_radius_hits', 0):4d}",
            flush=True,
        )


if __name__ == "__main__":
    main()
