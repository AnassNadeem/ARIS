"""E4.4 — one narrow China no-lag2 attempt.

When lag2 is missing but lag1 exists, precision-weight blend physics+residual
toward lag1 (IV), WITHOUT treating lag1 as an MA(2) substitute that updates
the MA error history (suspected Australia poison in the E3 MA(1) trial).

Scoped only to the no-lag2 branch. Does not modify production code until
this script shows a clean win (China helps, no Australia/others regress).
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

from aris.models.blend import inverse_variance_blend, rolling_error_variance  # noqa: E402
from aris.models.features import build_from_fastf1  # noqa: E402
from aris.models.predict import (  # noqa: E402
    _BLEND_FALLBACK_VAR,
    _BLEND_MIN_OBS,
    _BLEND_WINDOW,
    ma2_from_lags,
    predict_from_lap_row,
    reset_model_cache,
)

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))

# E3 held-out MA(2) for aimed bars (from PHASE-E3-SUMMARY)
_MA2 = {
    "China": 0.3756,
    "Australia": 0.4632,
    "Netherlands": 0.4270,
    "Sao Paulo": 0.7815,  # E3 table 0.782
    "Italy": 0.4535,
    "Spain": 0.4760,
    "Belgium": 0.4260,
    "United States": 0.3930,
    "Bahrain": 0.2840,
    "Japan": 0.6440,
}


def score(gp: str, *, mode: str) -> dict:
    """mode: baseline | ma1_subst | shrink_nolag2 | shrink_nolag2_disagree"""
    reset_model_cache()
    frame = build_from_fastf1(2024, gp)
    work = frame.sort_values(["Driver", "LapNumber"])
    err_r: dict[str, list[float]] = defaultdict(list)
    err_m: dict[str, list[float]] = defaultdict(list)
    abs_errs: list[float] = []
    n_nolag2 = 0
    n_shrink = 0

    for _, row in work.iterrows():
        drv = str(row["Driver"])
        y = float(row["target"])
        pred_r = predict_from_lap_row(row)
        lag1 = float(row["lag1_pace"]) if pd.notna(row.get("lag1_pace")) else None
        lag2 = float(row["lag2_pace"]) if pd.notna(row.get("lag2_pace")) else None
        pred_m = ma2_from_lags(lag1, lag2)

        if pred_m is None:
            n_nolag2 += 1
            if mode == "baseline" or lag1 is None or not np.isfinite(lag1):
                abs_errs.append(abs(y - pred_r))
                err_r[drv].append(y - pred_r)
                continue

            if mode == "ma1_subst":
                # E3 attempt: treat lag1 as MA substitute AND update err_m
                pred_m = lag1
                y_hat = inverse_variance_blend(
                    pred_r,
                    pred_m,
                    rolling_error_variance(
                        err_r[drv][-_BLEND_WINDOW:],
                        min_obs=_BLEND_MIN_OBS,
                        fallback=_BLEND_FALLBACK_VAR,
                    ),
                    rolling_error_variance(
                        err_m[drv][-_BLEND_WINDOW:],
                        min_obs=_BLEND_MIN_OBS,
                        fallback=_BLEND_FALLBACK_VAR,
                    ),
                )
                abs_errs.append(abs(y - y_hat))
                err_r[drv].append(y - pred_r)
                err_m[drv].append(y - pred_m)
                n_shrink += 1
                continue

            # shrink_nolag2: IV toward lag1, do NOT update err_m
            var_r = rolling_error_variance(
                err_r[drv][-_BLEND_WINDOW:],
                min_obs=_BLEND_MIN_OBS,
                fallback=_BLEND_FALLBACK_VAR,
            )
            var_l1 = _BLEND_FALLBACK_VAR
            if mode == "shrink_nolag2_disagree":
                # Inflate phys+res variance by squared disagreement with lag1
                # so large physics bias pulls weight toward the observed lap.
                var_r = max(var_r, float((pred_r - lag1) ** 2))
            y_hat = inverse_variance_blend(pred_r, lag1, var_r, var_l1)
            abs_errs.append(abs(y - y_hat))
            err_r[drv].append(y - pred_r)
            # intentionally no err_m update
            n_shrink += 1
            continue

        y_hat = inverse_variance_blend(
            pred_r,
            pred_m,
            rolling_error_variance(
                err_r[drv][-_BLEND_WINDOW:],
                min_obs=_BLEND_MIN_OBS,
                fallback=_BLEND_FALLBACK_VAR,
            ),
            rolling_error_variance(
                err_m[drv][-_BLEND_WINDOW:],
                min_obs=_BLEND_MIN_OBS,
                fallback=_BLEND_FALLBACK_VAR,
            ),
        )
        abs_errs.append(abs(y - y_hat))
        err_r[drv].append(y - pred_r)
        err_m[drv].append(y - pred_m)

    mae = float(np.mean(abs_errs))
    aimed = 1.5 * _MA2[gp]
    return {
        "mae": mae,
        "aimed": aimed,
        "pass": mae <= aimed,
        "n": len(abs_errs),
        "n_nolag2": n_nolag2,
        "n_shrink_applied": n_shrink,
        "margin": aimed - mae,
    }


def main() -> int:
    gps = list(_MA2.keys())
    modes = ["baseline", "ma1_subst", "shrink_nolag2", "shrink_nolag2_disagree"]
    rows = []
    for gp in gps:
        row = {"gp": gp, "ma2": _MA2[gp]}
        for mode in modes:
            row[mode] = score(gp, mode=mode)
            print(
                f"{gp:<16} {mode:<24} mae={row[mode]['mae']:.4f} "
                f"aimed={row[mode]['aimed']:.4f} "
                f"{'PASS' if row[mode]['pass'] else 'MISS'} "
                f"margin={row[mode]['margin']:+.4f} "
                f"shrink_n={row[mode]['n_shrink_applied']}/{row[mode]['n_nolag2']}",
                flush=True,
            )
        rows.append(row)

    # Decision: shrink mode must (a) make China PASS or clearly help without
    # (b) flipping any previously-passing race to MISS vs baseline.
    def decide(candidate: str) -> dict:
        china_base = next(r for r in rows if r["gp"] == "China")
        base_c = china_base["baseline"]["mae"]
        cand_c = china_base[candidate]["mae"]
        aimed_c = china_base["baseline"]["aimed"]
        regressions = []
        for r in rows:
            b, c = r["baseline"], r[candidate]
            # Regression = was PASS under baseline, MISS under candidate
            if b["pass"] and not c["pass"]:
                regressions.append(
                    {
                        "gp": r["gp"],
                        "baseline_mae": b["mae"],
                        "candidate_mae": c["mae"],
                        "aimed": b["aimed"],
                        "delta": c["mae"] - b["mae"],
                    }
                )
            # Also flag any MAE worsening > 0.02 even if still pass
            elif c["mae"] - b["mae"] > 0.02:
                regressions.append(
                    {
                        "gp": r["gp"],
                        "baseline_mae": b["mae"],
                        "candidate_mae": c["mae"],
                        "aimed": b["aimed"],
                        "delta": c["mae"] - b["mae"],
                        "note": "mae_worse_gt_0.02_still_pass"
                        if c["pass"]
                        else "mae_worse",
                    }
                )
        china_pass = cand_c <= aimed_c
        china_delta = cand_c - base_c
        ship = china_pass and not any(
            x.get("note") != "mae_worse_gt_0.02_still_pass" for x in regressions
            if "note" not in x or x["note"] != "mae_worse_gt_0.02_still_pass"
        )
        # Stricter: no pass→miss regressions; mild still-pass worsenings OK if China passes
        hard_regs = [x for x in regressions if x.get("note") != "mae_worse_gt_0.02_still_pass"]
        ship = bool(china_pass and len(hard_regs) == 0)
        return {
            "candidate": candidate,
            "china_baseline_mae": base_c,
            "china_candidate_mae": cand_c,
            "china_aimed": aimed_c,
            "china_delta": china_delta,
            "china_pass": china_pass,
            "regressions": regressions,
            "hard_regressions": hard_regs,
            "ship": ship,
        }

    decisions = {m: decide(m) for m in modes if m != "baseline"}
    ship_any = any(d["ship"] for d in decisions.values())
    out = {
        "rows": rows,
        "decisions": decisions,
        "verdict": (
            "SHIP "
            + ", ".join(m for m, d in decisions.items() if d["ship"])
            if ship_any
            else "DO_NOT_SHIP — accept China 0.033s miss; no clean no-lag2 shrinkage without regression"
        ),
    }
    path = _ROOT / "results" / "e4_4_china_nolag2_shrink.json"
    # numpy types
    path.write_text(json.dumps(out, indent=2, default=float), encoding="utf-8")
    print("\n" + out["verdict"])
    print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
