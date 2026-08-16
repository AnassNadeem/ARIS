"""Phase R.2 diagnosis: full-race chained rollout, plan selection, bias-cancel.

G1.1 methodology first (teacher-forced vs chained on green stretches), then
the production physics-delta path on the same stretches, then lights-out /
bias-cancel checks on real races.

  python scripts/_r2_diagnose.py --only r21
  python scripts/_r2_diagnose.py --only r22
  python scripts/_r2_diagnose.py --only r23
  python scripts/_r2_diagnose.py --only r24
  python scripts/_r2_diagnose.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

import fastf1  # noqa: E402

from aris.eval.backtest import (  # noqa: E402
    BACKTEST_GPS_2025,
    OutcomeScore,
    RaceEngineSession,
    SessionPhase,
    _score_outcome,
    field_race_times,
    pick_reference_driver,
    resolve_calendar,
)
from aris.eval.laptime import HELD_OUT_RACES  # noqa: E402
from aris.eval.postrace import (  # noqa: E402
    actual_schedule,
    estimate_position,
    schedule_from_plan,
    simulate_schedule,
)
from aris.io import db  # noqa: E402
from aris.models.features import estimate_fuel_kg  # noqa: E402
from aris.models.predict import (  # noqa: E402
    damp_residual_toward_pace,
    predict_physics,
    reset_model_cache,
)
from aris.models.residual import ResidualModel  # noqa: E402
from aris.physics.bicycle import FUEL_PENALTY_S_PER_KG  # noqa: E402
from aris.physics.stint import detect_stints  # noqa: E402
from aris.physics.tires import tire_pace_loss  # noqa: E402
from aris.plan.prewrite import generate_strat_plans  # noqa: E402
from aris.simulate import _update_lags  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402

_MAIN_CACHE = Path(r"C:\Users\anass\OneDrive\Desktop\ARIS\fastf1_cache")
_CACHE = _MAIN_CACHE if _MAIN_CACHE.exists() else (_ROOT / "fastf1_cache")
_CACHE.mkdir(parents=True, exist_ok=True)
fastf1.Cache.enable_cache(str(_CACHE), use_requests_cache=False)

_OUT = _ROOT / "results" / "r2"
_G11_HORIZONS = (1, 5, 10, 20)  # aimed: reproduce G1.1 table
_LONG_HORIZONS = (1, 5, 10, 20, 40, 60, 70)
_SKIP_INTO_STINT = 3
_MIN_STINT_LAPS = 20
_G11_AIMED = {
    "+1": {"chained_mae_s": 0.861, "chained_bias_s": 0.235, "forced_mae_s": 0.861},
    "+5": {"chained_mae_s": 1.861, "chained_bias_s": 0.389, "forced_mae_s": 0.765},
    "+10": {"chained_mae_s": 2.444, "chained_bias_s": 0.566, "forced_mae_s": 0.762},
    "+20": {"chained_mae_s": 2.790, "chained_bias_s": 0.572, "forced_mae_s": 0.791},
}

STREET_GPS = frozenset({
    "Monaco", "Singapore", "Azerbaijan", "Miami", "Las Vegas", "Canada", "Australia",
})


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0:
        return float("nan")
    return float(np.mean(np.abs(a - b)))


def _bias(pred: np.ndarray, true: np.ndarray) -> float:
    if len(pred) == 0:
        return float("nan")
    return float(np.mean(pred - true))


def _load_model() -> ResidualModel:
    reset_model_cache()
    return ResidualModel.load()


def _components(
    *,
    compound: str,
    tyre_life: int,
    fuel_kg: float,
    lag1: float | None,
    lag2: float | None,
    roll3: float | None,
    track,
    model: ResidualModel,
) -> dict[str, float | None]:
    physics = float(
        predict_physics(
            compound=compound,
            tyre_life=tyre_life,
            fuel_kg=fuel_kg,
            pit_lap=False,
            track=track,
        )
    )
    tire = float(tire_pace_loss(compound, tyre_life, slopes=track.compound_slopes))
    fuel = float(FUEL_PENALTY_S_PER_KG * fuel_kg)
    residual_raw = 0.0
    residual_damped = 0.0
    if lag1 is not None:
        row = pd.Series(
            {
                "compound_code": {"SOFT": 0, "MEDIUM": 1, "HARD": 2}.get(
                    str(compound).upper(), 1
                ),
                "tyre_life": tyre_life,
                "fuel_kg": fuel_kg,
                "lag1_pace": lag1,
                "lag2_pace": lag2 if lag2 is not None else lag1,
                "stint_roll3": roll3 if roll3 is not None else lag1,
                "physics_pred": physics,
            }
        )
        residual_raw = float(model.predict_residual(pd.DataFrame([row]))[0])
        residual_damped = float(damp_residual_toward_pace(physics, lag1, residual_raw))
    pred = physics + residual_damped if lag1 is not None else physics
    return {
        "physics": physics,
        "tire_deg": tire,
        "fuel": fuel,
        "residual_damped": residual_damped,
        "pred": pred,
    }


def _load_race_laps(year: int, gp: str):
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    cfg = load_track_config(gp, year=year)
    track = cfg.load_physics()
    enriched = detect_stints(session.laps)
    return enriched, track, cfg


def _green_runs(stint: pd.DataFrame) -> list[pd.DataFrame]:
    work = stint.sort_values("LapNumber").copy()
    work["is_green"] = (
        work["LapTimeS"].notna()
        & work["PitOutTime"].isna()
        & work["PitInTime"].isna()
        & (work["TrackStatus"].astype("string").fillna("") == "1")
    )
    runs: list[pd.DataFrame] = []
    current: list = []
    for idx, row in work.iterrows():
        if bool(row["is_green"]):
            current.append(idx)
        elif current:
            runs.append(work.loc[current])
            current = []
    if current:
        runs.append(work.loc[current])
    return runs


def _horizon_cells(
    chained: np.ndarray,
    forced: np.ndarray,
    physics_delta: np.ndarray,
    observed: np.ndarray,
    horizons: tuple[int, ...],
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for h in horizons:
        if len(chained) < h:
            out[f"+{h}"] = None
            continue
        ch_err = float(chained[h - 1] - observed[h - 1])
        fo_err = float(forced[h - 1] - observed[h - 1])
        pd_err = float(physics_delta[h - 1] - observed[h - 1])
        ch_cum = float(np.sum(chained[:h] - observed[:h]))
        fo_cum = float(np.sum(forced[:h] - observed[:h]))
        pd_cum = float(np.sum(physics_delta[:h] - observed[:h]))
        out[f"+{h}"] = {
            "chained_err_s": ch_err,
            "forced_err_s": fo_err,
            "physics_delta_err_s": pd_err,
            "chained_abs_s": abs(ch_err),
            "forced_abs_s": abs(fo_err),
            "physics_delta_abs_s": abs(pd_err),
            "chained_cum_err_s": ch_cum,
            "forced_cum_err_s": fo_cum,
            "physics_delta_cum_err_s": pd_cum,
        }
    return out


def _rollout_run(
    run: pd.DataFrame,
    *,
    track,
    cfg,
    model: ResidualModel,
    skip: int = _SKIP_INTO_STINT,
    horizons: tuple[int, ...] = _LONG_HORIZONS,
) -> dict[str, Any] | None:
    """G1.1 residual-chained + teacher-forced, plus production physics-delta."""
    run = run.sort_values("LapNumber").reset_index(drop=True)
    if len(run) < skip + 5:
        return None
    start = skip
    observed = run["LapTimeS"].to_numpy(dtype=float)
    compounds = run["Compound"].astype(str).str.upper().to_numpy()
    tyre_life = run["TyreLife"].fillna(1).astype(int).to_numpy()
    lap_numbers = run["LapNumber"].astype(int).to_numpy()
    total_laps = int(cfg.total_laps)

    prior = observed[:start].tolist()
    if len(prior) < 1:
        return None

    chained: list[float] = []
    forced: list[float] = []
    physics_delta: list[float] = []
    recent_chained = list(prior)
    recent_forced = list(prior)
    prev_physics: float | None = None
    prev_pd_pred: float | None = None

    for i in range(start, len(run)):
        fuel = estimate_fuel_kg(int(lap_numbers[i]), total_laps=total_laps)
        lag1_c, lag2_c, roll3_c = _update_lags(recent_chained)
        lag1_f, lag2_f, roll3_f = _update_lags(recent_forced)
        comp = _components(
            compound=str(compounds[i]),
            tyre_life=int(tyre_life[i]),
            fuel_kg=fuel,
            lag1=lag1_c,
            lag2=lag2_c,
            roll3=roll3_c,
            track=track,
            model=model,
        )
        forced_c = _components(
            compound=str(compounds[i]),
            tyre_life=int(tyre_life[i]),
            fuel_kg=fuel,
            lag1=lag1_f,
            lag2=lag2_f,
            roll3=roll3_f,
            track=track,
            model=model,
        )
        physics = float(comp["physics"])
        if prev_physics is None:
            # First predicted lap: residual with real opening lags (G1.4).
            lag1_pd, lag2_pd, roll3_pd = _update_lags(prior)
            pd_c = _components(
                compound=str(compounds[i]),
                tyre_life=int(tyre_life[i]),
                fuel_kg=fuel,
                lag1=lag1_pd,
                lag2=lag2_pd,
                roll3=roll3_pd,
                track=track,
                model=model,
            )
            pd_pred = float(pd_c["pred"])
        else:
            pd_pred = float(prev_pd_pred) + (physics - prev_physics)

        chained.append(float(comp["pred"]))
        forced.append(float(forced_c["pred"]))
        physics_delta.append(pd_pred)
        recent_chained.append(float(comp["pred"]))
        recent_forced.append(float(observed[i]))
        if len(recent_chained) > 10:
            recent_chained = recent_chained[-10:]
        if len(recent_forced) > 10:
            recent_forced = recent_forced[-10:]
        prev_physics = physics
        prev_pd_pred = pd_pred

    obs_rem = observed[start:]
    ch = np.array(chained, dtype=float)
    fo = np.array(forced, dtype=float)
    pdelta = np.array(physics_delta, dtype=float)
    return {
        "n_steps": len(ch),
        "start_lap": int(lap_numbers[start]),
        "end_lap": int(lap_numbers[-1]),
        "compound": str(compounds[start]),
        "tyre_life_at_start": int(tyre_life[start]),
        "horizon": _horizon_cells(ch, fo, pdelta, obs_rem, horizons),
        "chained_mae_s": _mae(ch, obs_rem),
        "forced_mae_s": _mae(fo, obs_rem),
        "physics_delta_mae_s": _mae(pdelta, obs_rem),
        "chained_bias_s": _bias(ch, obs_rem),
        "forced_bias_s": _bias(fo, obs_rem),
        "physics_delta_bias_s": _bias(pdelta, obs_rem),
        "last_step": int(len(ch)),
        "last_chained_err_s": float(ch[-1] - obs_rem[-1]) if len(ch) else float("nan"),
        "last_forced_err_s": float(fo[-1] - obs_rem[-1]) if len(fo) else float("nan"),
        "last_physics_delta_err_s": (
            float(pdelta[-1] - obs_rem[-1]) if len(pdelta) else float("nan")
        ),
    }


def _horizon_pool(rows: list[dict[str, Any]], h: int, key: str) -> list[float]:
    vals: list[float] = []
    for r in rows:
        cell = r["horizon"].get(f"+{h}")
        if cell is not None:
            vals.append(float(cell[key]))
    return vals


def _summarise(rows: list[dict[str, Any]], horizons: tuple[int, ...]) -> dict[str, Any]:
    out: dict[str, Any] = {"n_stints": len(rows)}
    for h in horizons:
        ch = np.array(_horizon_pool(rows, h, "chained_err_s"), dtype=float)
        fo = np.array(_horizon_pool(rows, h, "forced_err_s"), dtype=float)
        pdelta = np.array(_horizon_pool(rows, h, "physics_delta_err_s"), dtype=float)
        ch_cum = np.array(_horizon_pool(rows, h, "chained_cum_err_s"), dtype=float)
        pd_cum = np.array(_horizon_pool(rows, h, "physics_delta_cum_err_s"), dtype=float)
        out[f"+{h}"] = {
            "n": int(len(ch)),
            "chained_mae_s": float(np.mean(np.abs(ch))) if len(ch) else float("nan"),
            "chained_bias_s": float(np.mean(ch)) if len(ch) else float("nan"),
            "forced_mae_s": float(np.mean(np.abs(fo))) if len(fo) else float("nan"),
            "forced_bias_s": float(np.mean(fo)) if len(fo) else float("nan"),
            "physics_delta_mae_s": (
                float(np.mean(np.abs(pdelta))) if len(pdelta) else float("nan")
            ),
            "physics_delta_bias_s": float(np.mean(pdelta)) if len(pdelta) else float("nan"),
            "chained_cum_mae_s": (
                float(np.mean(np.abs(ch_cum))) if len(ch_cum) else float("nan")
            ),
            "chained_cum_bias_s": float(np.mean(ch_cum)) if len(ch_cum) else float("nan"),
            "physics_delta_cum_mae_s": (
                float(np.mean(np.abs(pd_cum))) if len(pd_cum) else float("nan")
            ),
            "physics_delta_cum_bias_s": (
                float(np.mean(pd_cum)) if len(pd_cum) else float("nan")
            ),
        }
    return out


def _print_horizon_table(label: str, summary: dict[str, Any], horizons: tuple[int, ...]) -> None:
    print(f"\n  {label}  n_stints={summary.get('n_stints')}", flush=True)
    print(
        "  horizon  n  chained MAE (bias)  physics-delta MAE (bias)  "
        "teacher-forced MAE (bias)",
        flush=True,
    )
    for h in horizons:
        cell = summary.get(f"+{h}") or {}
        n = cell.get("n", 0)
        if not n:
            print(f"  +{h:>2}  n=0  (no green stretch this long)", flush=True)
            continue
        aimed = _G11_AIMED.get(f"+{h}")
        aimed_bit = ""
        if aimed:
            aimed_bit = (
                f"  aimed G1.1 chained MAE={aimed['chained_mae_s']:.3f} "
                f"forced={aimed['forced_mae_s']:.3f}"
            )
        print(
            f"  +{h:>2}  n={n:<4}  "
            f"{cell['chained_mae_s']:.3f} ({cell['chained_bias_s']:+.3f})  "
            f"{cell['physics_delta_mae_s']:.3f} ({cell['physics_delta_bias_s']:+.3f})  "
            f"{cell['forced_mae_s']:.3f} ({cell['forced_bias_s']:+.3f})"
            f"{aimed_bit}",
            flush=True,
        )
        print(
            f"       cum  chained MAE={cell['chained_cum_mae_s']:.3f} "
            f"bias={cell['chained_cum_bias_s']:+.3f}  "
            f"physics-delta MAE={cell['physics_delta_cum_mae_s']:.3f} "
            f"bias={cell['physics_delta_cum_bias_s']:+.3f}",
            flush=True,
        )


def r21_rollout(model: ResidualModel) -> dict[str, Any]:
    print("\n=== R2.1 chained rollout at full-race horizons ===", flush=True)
    print(
        "Same method as G1.1: 20+ lap green stretches, start 3 laps in with "
        "real lags. Residual-chained = G1.1 path. Physics-delta = current "
        "simulate() after the first residual-corrected lap. Teacher-forced = "
        "observed lags every step.",
        flush=True,
    )
    all_runs: list[dict[str, Any]] = []
    by_compound: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for year, gp in HELD_OUT_RACES:
        if year != 2024:
            continue
        print(f"  loading {year} {gp}...", flush=True)
        try:
            enriched, track, cfg = _load_race_laps(year, gp)
        except Exception as exc:  # noqa: BLE001
            print(f"    SKIP {gp}: {exc}", flush=True)
            continue
        for (driver, stint_id), stint in enriched.groupby(["Driver", "StintId"], sort=False):
            if len(stint) < _MIN_STINT_LAPS:
                continue
            compound = str(stint["Compound"].dropna().iloc[0]).upper()
            if compound not in {"SOFT", "MEDIUM", "HARD"}:
                continue
            for run in _green_runs(stint):
                if len(run) < _MIN_STINT_LAPS:
                    continue
                result = _rollout_run(run, track=track, cfg=cfg, model=model)
                if result is None:
                    continue
                row = {
                    "year": year,
                    "gp": gp,
                    "driver": str(driver),
                    "stint_id": int(stint_id),
                    "stint_laps": int(len(stint)),
                    "green_laps": int(len(run)),
                    "total_laps": int(cfg.total_laps),
                    **result,
                }
                all_runs.append(row)
                by_compound[compound].append(row)

    aggregate = {
        "all": _summarise(all_runs, _LONG_HORIZONS),
        "by_compound": {
            c: _summarise(rows, _LONG_HORIZONS) for c, rows in by_compound.items()
        },
    }
    print(
        f"  stints scored: {len(all_runs)} "
        f"(HARD={len(by_compound['HARD'])} MED={len(by_compound['MEDIUM'])} "
        f"SOFT={len(by_compound['SOFT'])})",
        flush=True,
    )
    _print_horizon_table("all compounds", aggregate["all"], _LONG_HORIZONS)
    for compound in ("HARD", "MEDIUM", "SOFT"):
        if compound in aggregate["by_compound"]:
            _print_horizon_table(compound, aggregate["by_compound"][compound], _LONG_HORIZONS)

    long_runs = sorted(all_runs, key=lambda r: r["n_steps"], reverse=True)[:12]
    examples = []
    print("\n  longest green stretches (chained / physics-delta / forced err at last lap):", flush=True)
    for r in long_runs:
        print(
            f"    {r['gp']} {r['driver']} {r['compound']} "
            f"L{r['start_lap']}-{r['end_lap']} green={r['green_laps']} "
            f"steps={r['n_steps']}  last chained={r['last_chained_err_s']:+.2f} "
            f"pd={r['last_physics_delta_err_s']:+.2f} "
            f"forced={r['last_forced_err_s']:+.2f}",
            flush=True,
        )
        examples.append({k: v for k, v in r.items() if k != "horizon"} | {
            "horizon": {hk: hv for hk, hv in r["horizon"].items() if hv is not None}
        })

    n_ge = {h: int(aggregate["all"].get(f"+{h}", {}).get("n") or 0) for h in _LONG_HORIZONS}
    return {
        "metric": "chained_rollout_error_full_race_horizons",
        "method": (
            "G1.1: start 3 green laps into a 20+ lap green stretch. Residual-"
            "chained feeds prior predictions as lags. Physics-delta applies "
            "residual once then adds tyre+fuel physics deltas (current "
            "simulate()). Teacher-forced uses observed lags at every step."
        ),
        "horizons": list(_LONG_HORIZONS),
        "g11_aimed": _G11_AIMED,
        "n_runs": len(all_runs),
        "n_at_horizon": n_ge,
        "aggregate": aggregate,
        "examples": examples,
        "runs_slim": [
            {k: v for k, v in r.items() if k != "horizon"} | {
                "horizon": {hk: hv for hk, hv in r["horizon"].items() if hv is not None}
            }
            for r in all_runs
        ],
    }


def _session_for(meta: dict[str, Any], driver_id: int, driver_code: str) -> RaceEngineSession:
    track = load_track_config(meta["country"], year=meta["year"], round_no=meta["round_no"])
    return RaceEngineSession(
        session_id=int(meta["session_id"]),
        driver_id=driver_id,
        driver_code=driver_code,
        year=int(meta["year"]),
        round_no=int(meta["round_no"]),
        country=str(meta["country"]),
        total_laps=track.total_laps,
        phase=SessionPhase.LIVE,
    )


def _plans_for_race(meta: dict[str, Any], driver_id: int, driver_code: str):
    return generate_strat_plans(
        int(meta["session_id"]),
        driver_id,
        year=int(meta["year"]),
        round_no=int(meta["round_no"]),
        country=str(meta["country"]),
        driver_code=driver_code,
    )


def r22_plan_selection() -> dict[str, Any]:
    print("\n=== R2.2 prewrite recommended=True vs simulated A/B/C ===", flush=True)
    print(
        "Aimed: the plan marked recommended=True is the min expected_race_time_s "
        "among A/B/C on every scored race. Not assumed — checked.",
        flush=True,
    )
    rows: list[dict[str, Any]] = []
    mismatches = 0
    n = 0
    for year in (2024, 2025):
        try:
            calendar = resolve_calendar(year)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {year}: {exc}", flush=True)
            continue
        for meta in calendar:
            drv = pick_reference_driver(int(meta["session_id"]))
            if drv is None:
                continue
            driver_id = int(drv["driver_id"])
            driver_code = str(drv["code"])
            try:
                plans = _plans_for_race(meta, driver_id, driver_code)
            except Exception as exc:  # noqa: BLE001
                print(f"  SKIP {year} {meta['gp']}: {exc}", flush=True)
                continue
            scored = [
                {
                    "id": p.id,
                    "name": p.name,
                    "recommended": bool(p.recommended),
                    "expected_race_time_s": p.expected_race_time_s,
                    "pit_laps": list(p.pit_laps),
                    "pit_compounds": list(p.pit_compounds),
                    "start_compound": p.start_compound,
                }
                for p in plans.plans
            ]
            times = [
                p["expected_race_time_s"]
                for p in scored
                if p["expected_race_time_s"] is not None
            ]
            rec = next((p for p in scored if p["recommended"]), None)
            best = min(scored, key=lambda p: p["expected_race_time_s"] or 1e18)
            ok = rec is not None and rec["id"] == best["id"]
            n += 1
            if not ok:
                mismatches += 1
            row = {
                "year": year,
                "gp": meta["gp"],
                "round_no": meta["round_no"],
                "driver_code": driver_code,
                "ok": ok,
                "recommended_id": rec["id"] if rec else None,
                "best_id": best["id"],
                "recommended_s": rec["expected_race_time_s"] if rec else None,
                "best_s": best["expected_race_time_s"],
                "spread_s": (max(times) - min(times)) if times else None,
                "plans": scored,
            }
            rows.append(row)
            mark = "OK" if ok else "MISMATCH"
            print(
                f"  {mark} {year} {meta['gp']} {driver_code} "
                f"rec={row['recommended_id']} best={row['best_id']} "
                f"rec_s={row['recommended_s']} best_s={row['best_s']} "
                f"spread={row['spread_s']}",
                flush=True,
            )
    print(
        f"  aimed: 0 mismatches. actual: {mismatches}/{n}",
        flush=True,
    )
    return {
        "metric": "recommended_is_best_simulated",
        "aimed_mismatches": 0,
        "n": n,
        "mismatches": mismatches,
        "rows": rows,
    }


def _time_rank(field: dict[str, float], driver_code: str) -> int | None:
    return estimate_position(field, driver_code, field[driver_code]) if driver_code in field else None


def r23_bias_cancel() -> dict[str, Any]:
    print("\n=== R2.3 bias-cancel identity and stability ===", flush=True)
    print(
        "Controlled: if ARIS_sim == team_sim, adjusted_time == actual, "
        "aimed position-delta = 0 vs official P5 (and vs time-rank).",
        flush=True,
    )

    synthetic_field = {
        "VER": 5000.0, "NOR": 5010.0, "LEC": 5020.0, "PIA": 5030.0, "SAI": 5040.0,
        "HAM": 5050.0, "RUS": 5060.0, "ALO": 5070.0, "STR": 5080.0, "GAS": 5090.0,
    }
    actual = synthetic_field["SAI"]
    aris_sim = 6120.0
    team_sim = 6120.0
    adjusted = actual + (aris_sim - team_sim)
    synth_pos = estimate_position(synthetic_field, "SAI", adjusted)
    synthetic = {
        "aris_sim": aris_sim,
        "team_sim": team_sim,
        "actual": actual,
        "adjusted": adjusted,
        "aris_pos": synth_pos,
        "actual_pos": 5,
        "position_delta": (synth_pos - 5) if synth_pos is not None else None,
    }
    print(
        f"  synthetic identity: aimed delta=0  actual delta={synthetic['position_delta']} "
        f"aris_pos={synth_pos} (P5 SAI, ARIS_sim=team_sim={aris_sim})",
        flush=True,
    )

    rows: list[dict[str, Any]] = []
    for year in (2024, 2025):
        try:
            calendar = resolve_calendar(year)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {year}: {exc}", flush=True)
            continue
        for meta in calendar:
            sid = int(meta["session_id"])
            drv = pick_reference_driver(sid)
            if drv is None:
                continue
            driver_id = int(drv["driver_id"])
            driver_code = str(drv["code"])
            focus = db.fetch_laps(sid, driver_id)
            if focus.empty:
                continue
            team = actual_schedule(focus)
            results = db.fetch_session_results(sid)
            finish_pos = 5
            if not results.empty:
                hit = results[results["code"] == driver_code]
                if not hit.empty and pd.notna(hit.iloc[0]["finish_pos"]):
                    finish_pos = int(hit.iloc[0]["finish_pos"])
            session = _session_for(meta, driver_id, driver_code)
            try:
                start_state = session.build_state(1)
                team_sim = simulate_schedule(start_state, team)
                identity_adjusted = float(focus.dropna(subset=["lap_time_s"])["lap_time_s"].sum())
                field = field_race_times(sid)
                identity_pos = estimate_position(field, driver_code, identity_adjusted)
                time_rank = _time_rank(field, driver_code)
                identity_delta_vs_official = (
                    (identity_pos - finish_pos) if identity_pos is not None else None
                )
                identity_delta_vs_timerank = (
                    (identity_pos - time_rank)
                    if identity_pos is not None and time_rank is not None
                    else None
                )
                plans = _plans_for_race(meta, driver_id, driver_code)
                rec = next((p for p in plans.plans if p.recommended), plans.plans[0] if plans.plans else None)
                aris_sim = None
                if rec is not None:
                    session.active_strat = rec
                    aris_sim = simulate_schedule(start_state, schedule_from_plan(rec))
                sim_gap = (aris_sim - team_sim) if aris_sim is not None else None
                actual_time = identity_adjusted
                row = {
                    "year": year,
                    "gp": meta["gp"],
                    "round_no": meta["round_no"],
                    "country": meta["country"],
                    "driver_code": driver_code,
                    "official_finish_pos": finish_pos,
                    "time_rank": time_rank,
                    "time_rank_minus_official": (
                        (time_rank - finish_pos) if time_rank is not None else None
                    ),
                    "team_sim_s": team_sim,
                    "aris_sim_s": aris_sim,
                    "actual_time_s": actual_time,
                    "sim_gap_s": sim_gap,
                    "team_minus_actual_s": team_sim - actual_time,
                    "aris_minus_actual_s": (aris_sim - actual_time) if aris_sim is not None else None,
                    "identity_pos": identity_pos,
                    "identity_delta_vs_official": identity_delta_vs_official,
                    "identity_delta_vs_timerank": identity_delta_vs_timerank,
                    "track_group": "street" if meta["gp"] in STREET_GPS else "permanent",
                    "aris_pits": list(rec.pit_laps) if rec is not None else [],
                    "team_pits": list(team.pit_laps),
                    "total_laps": session.total_laps,
                }
            except Exception as exc:  # noqa: BLE001
                row = {
                    "year": year,
                    "gp": meta["gp"],
                    "error": str(exc),
                }
            rows.append(row)
            if "error" in row:
                print(f"  ERR {year} {meta['gp']}: {row['error']}", flush=True)
            else:
                print(
                    f"  {year} {meta['gp']} {driver_code} "
                    f"id_delta_official={row['identity_delta_vs_official']} "
                    f"id_delta_timerank={row['identity_delta_vs_timerank']} "
                    f"time_rank-off={row['time_rank_minus_official']} "
                    f"sim_gap={None if row['sim_gap_s'] is None else round(row['sim_gap_s'], 1)} "
                    f"team-actual={row['team_minus_actual_s']:.1f} "
                    f"group={row['track_group']}",
                    flush=True,
                )

    scored = [r for r in rows if "error" not in r]
    id_off = [r["identity_delta_vs_official"] for r in scored if r["identity_delta_vs_official"] is not None]
    id_tr = [r["identity_delta_vs_timerank"] for r in scored if r["identity_delta_vs_timerank"] is not None]
    gaps = [r["sim_gap_s"] for r in scored if r["sim_gap_s"] is not None]
    team_bias = [r["team_minus_actual_s"] for r in scored]
    by_group: dict[str, dict[str, Any]] = {}
    for group in ("street", "permanent"):
        sub = [r for r in scored if r.get("track_group") == group]
        g_bias = [r["team_minus_actual_s"] for r in sub]
        g_gap = [r["sim_gap_s"] for r in sub if r["sim_gap_s"] is not None]
        by_group[group] = {
            "n": len(sub),
            "mean_team_minus_actual_s": float(np.mean(g_bias)) if g_bias else float("nan"),
            "std_team_minus_actual_s": float(np.std(g_bias)) if g_bias else float("nan"),
            "mean_sim_gap_s": float(np.mean(g_gap)) if g_gap else float("nan"),
            "std_sim_gap_s": float(np.std(g_gap)) if g_gap else float("nan"),
        }
    by_pos: dict[str, dict[str, Any]] = {}
    for r in scored:
        key = str(r["official_finish_pos"])
        by_pos.setdefault(key, []).append(r["team_minus_actual_s"])
    pos_summary = {
        k: {
            "n": len(v),
            "mean_team_minus_actual_s": float(np.mean(v)),
            "std_team_minus_actual_s": float(np.std(v)),
        }
        for k, v in sorted(by_pos.items(), key=lambda kv: int(kv[0]))
    }
    n_id_off_nonzero = sum(1 for x in id_off if x != 0)
    n_id_tr_nonzero = sum(1 for x in id_tr if x != 0)
    print(
        f"  identity vs official P5: aimed all delta=0; "
        f"actual nonzero {n_id_off_nonzero}/{len(id_off)}  "
        f"mean={float(np.mean(id_off)) if id_off else float('nan'):.3f}",
        flush=True,
    )
    print(
        f"  identity vs time-rank: aimed all delta=0; "
        f"actual nonzero {n_id_tr_nonzero}/{len(id_tr)}  "
        f"mean={float(np.mean(id_tr)) if id_tr else float('nan'):.3f}",
        flush=True,
    )
    print(
        f"  team_sim - actual: mean={float(np.mean(team_bias)):.1f}s "
        f"std={float(np.std(team_bias)):.1f}s  n={len(team_bias)}  "
        f"(G1.2 physics offset ~18s/lap * ~70 laps would be ~1260s if uncancelled)",
        flush=True,
    )
    print(
        f"  ARIS_sim - team_sim: mean={float(np.mean(gaps)) if gaps else float('nan'):.1f}s "
        f"std={float(np.std(gaps)) if gaps else float('nan'):.1f}s",
        flush=True,
    )
    for group, stats in by_group.items():
        print(
            f"  {group}: n={stats['n']} team-actual mean={stats['mean_team_minus_actual_s']:.1f} "
            f"std={stats['std_team_minus_actual_s']:.1f}  "
            f"sim_gap mean={stats['mean_sim_gap_s']:.1f} std={stats['std_sim_gap_s']:.1f}",
            flush=True,
        )
    return {
        "metric": "bias_cancel_identity_and_stability",
        "synthetic_identity": synthetic,
        "aimed_identity_delta": 0,
        "n_identity_vs_official_nonzero": n_id_off_nonzero,
        "n_identity_vs_timerank_nonzero": n_id_tr_nonzero,
        "mean_identity_delta_vs_official": float(np.mean(id_off)) if id_off else float("nan"),
        "mean_identity_delta_vs_timerank": float(np.mean(id_tr)) if id_tr else float("nan"),
        "mean_team_minus_actual_s": float(np.mean(team_bias)) if team_bias else float("nan"),
        "std_team_minus_actual_s": float(np.std(team_bias)) if team_bias else float("nan"),
        "mean_sim_gap_s": float(np.mean(gaps)) if gaps else float("nan"),
        "std_sim_gap_s": float(np.std(gaps)) if gaps else float("nan"),
        "by_track_group": by_group,
        "by_official_pos": pos_summary,
        "rows": rows,
    }


def r24_distribution() -> dict[str, Any]:
    print("\n=== R2.4 position-delta distribution (48 races) ===", flush=True)
    print(
        "Lights-out outcome only (no inflection walk). Aimed mean <= 0; "
        "G1.5 actual mean +2.96. Report the full distribution.",
        flush=True,
    )
    rows: list[dict[str, Any]] = []
    for year in (2024, 2025):
        try:
            calendar = resolve_calendar(year)
        except Exception as exc:  # noqa: BLE001
            print(f"  SKIP {year}: {exc}", flush=True)
            continue
        for meta in calendar:
            sid = int(meta["session_id"])
            drv = pick_reference_driver(sid)
            if drv is None:
                print(f"  SKIP {year} {meta['gp']}: no P5", flush=True)
                continue
            driver_id = int(drv["driver_id"])
            driver_code = str(drv["code"])
            session = _session_for(meta, driver_id, driver_code)
            focus = db.fetch_laps(sid, driver_id)
            team = actual_schedule(focus)
            results = db.fetch_session_results(sid)
            finish_pos = 5
            if not results.empty:
                hit = results[results["code"] == driver_code]
                if not hit.empty and pd.notna(hit.iloc[0]["finish_pos"]):
                    finish_pos = int(hit.iloc[0]["finish_pos"])
            try:
                plans = _plans_for_race(meta, driver_id, driver_code)
                rec = next((p for p in plans.plans if p.recommended), plans.plans[0])
                session.active_strat = rec
                outcome = _score_outcome(
                    session,
                    gp=str(meta["gp"]),
                    year=int(meta["year"]),
                    round_no=int(meta["round_no"]),
                    driver_code=driver_code,
                    finish_pos=finish_pos,
                    focus_laps=focus,
                    team_sched=team,
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  ERR {year} {meta['gp']}: {exc}", flush=True)
                continue
            field = field_race_times(sid)
            time_rank = (
                estimate_position(field, driver_code, outcome.actual_time_s)
                if driver_code in field
                else None
            )
            delta_vs_timerank = None
            if outcome.aris_finish_pos is not None and time_rank is not None:
                delta_vs_timerank = float(outcome.aris_finish_pos - time_rank)
            n_focus = int(focus.dropna(subset=["lap_time_s"]).shape[0])
            n_short = 0
            same_distance: dict[str, float] = {}
            for code, t in field.items():
                drow = db.fetch_driver_by_code(sid, code)
                if drow is None:
                    continue
                dlaps = db.fetch_laps(sid, int(drow["driver_id"]))
                n = int(dlaps.dropna(subset=["lap_time_s"]).shape[0])
                if n < n_focus - 2:
                    n_short += 1
                    continue
                same_distance[code] = t
            sim_gap = (
                (outcome.aris_sim_s - outcome.team_sim_s)
                if outcome.aris_sim_s is not None and outcome.team_sim_s is not None
                else None
            )
            same_actual = (
                estimate_position(same_distance, driver_code, outcome.actual_time_s)
                if driver_code in same_distance
                else None
            )
            same_aris = None
            if driver_code in same_distance and sim_gap is not None:
                same_aris = estimate_position(
                    same_distance, driver_code, outcome.actual_time_s + sim_gap
                )
            delta_same_distance = (
                (same_aris - same_actual)
                if same_aris is not None and same_actual is not None
                else None
            )
            row = {
                "year": year,
                "gp": meta["gp"],
                "round_no": meta["round_no"],
                "driver_code": driver_code,
                "actual_finish_pos": outcome.actual_finish_pos,
                "aris_finish_pos": outcome.aris_finish_pos,
                "position_delta": outcome.position_delta,
                "time_rank": time_rank,
                "delta_vs_timerank": delta_vs_timerank,
                "n_short_field": n_short,
                "same_distance_actual_pos": same_actual,
                "same_distance_aris_pos": same_aris,
                "delta_same_distance": delta_same_distance,
                "actual_time_s": outcome.actual_time_s,
                "aris_sim_s": outcome.aris_sim_s,
                "team_sim_s": outcome.team_sim_s,
                "sim_gap_s": sim_gap,
                "aris_plan_pits": outcome.aris_plan_pits,
                "actual_pits": outcome.actual_pits,
                "track_group": "street" if meta["gp"] in STREET_GPS else "permanent",
            }
            rows.append(row)
            print(
                f"  {year} {meta['gp']} {driver_code} "
                f"P{outcome.actual_finish_pos}->P{outcome.aris_finish_pos} "
                f"delta_official={outcome.position_delta} "
                f"delta_timerank={delta_vs_timerank} "
                f"delta_samedist={delta_same_distance} "
                f"gap={None if sim_gap is None else round(sim_gap, 1)}s "
                f"short={n_short} "
                f"aris_pits={outcome.aris_plan_pits} team_pits={outcome.actual_pits}",
                flush=True,
            )

    deltas = [r["position_delta"] for r in rows if r["position_delta"] is not None]
    arr = np.array(deltas, dtype=float)
    mean = float(np.mean(arr)) if len(arr) else float("nan")
    median = float(np.median(arr)) if len(arr) else float("nan")
    spain = [r for r in rows if r["gp"] == "Spain"]
    without_spain = [
        r["position_delta"]
        for r in rows
        if r["position_delta"] is not None and r["gp"] != "Spain"
    ]
    worst = sorted(rows, key=lambda r: -(r["position_delta"] or -999))[:8]
    best = sorted(rows, key=lambda r: (r["position_delta"] if r["position_delta"] is not None else 999))[:8]
    n_better = sum(1 for x in deltas if x < 0)
    n_same = sum(1 for x in deltas if x == 0)
    n_worse = sum(1 for x in deltas if x > 0)
    print(
        f"  n={len(deltas)}  aimed mean<=0  actual mean={mean:.3f}  "
        f"median={median:.3f}  G1.5 aimed-vs +2.96",
        flush=True,
    )
    print(
        f"  better/same/worse = {n_better}/{n_same}/{n_worse}",
        flush=True,
    )
    if without_spain:
        print(
            f"  mean without Spain: {float(np.mean(without_spain)):.3f} "
            f"(n={len(without_spain)}; Spain rows={spain})",
            flush=True,
        )
    qs = [0.10, 0.25, 0.50, 0.75, 0.90]
    quantiles = {f"p{int(q*100)}": float(np.quantile(arr, q)) for q in qs} if len(arr) else {}
    print(f"  quantiles official: {quantiles}", flush=True)
    tr = np.array(
        [r["delta_vs_timerank"] for r in rows if r["delta_vs_timerank"] is not None],
        dtype=float,
    )
    sd = np.array(
        [r["delta_same_distance"] for r in rows if r["delta_same_distance"] is not None],
        dtype=float,
    )
    mean_tr = float(np.mean(tr)) if len(tr) else float("nan")
    mean_sd = float(np.mean(sd)) if len(sd) else float("nan")
    print(
        f"  delta vs time-rank: aimed mean<=0  actual mean={mean_tr:.3f}  "
        f"median={float(np.median(tr)) if len(tr) else float('nan'):.3f}  "
        f"better/same/worse="
        f"{int((tr < 0).sum()) if len(tr) else 0}/"
        f"{int((tr == 0).sum()) if len(tr) else 0}/"
        f"{int((tr > 0).sum()) if len(tr) else 0}",
        flush=True,
    )
    print(
        f"  delta vs same-distance field: aimed mean<=0  actual mean={mean_sd:.3f}  "
        f"median={float(np.median(sd)) if len(sd) else float('nan'):.3f}  "
        f"better/same/worse="
        f"{int((sd < 0).sum()) if len(sd) else 0}/"
        f"{int((sd == 0).sum()) if len(sd) else 0}/"
        f"{int((sd > 0).sum()) if len(sd) else 0}",
        flush=True,
    )
    return {
        "metric": "position_delta_distribution",
        "aimed_mean": 0.0,
        "g15_mean": 2.96,
        "n": len(deltas),
        "mean": mean,
        "median": median,
        "std": float(np.std(arr)) if len(arr) else float("nan"),
        "min": float(np.min(arr)) if len(arr) else float("nan"),
        "max": float(np.max(arr)) if len(arr) else float("nan"),
        "quantiles": quantiles,
        "n_better": n_better,
        "n_same": n_same,
        "n_worse": n_worse,
        "mean_without_spain": float(np.mean(without_spain)) if without_spain else float("nan"),
        "spain": spain,
        "worst": worst,
        "best": best,
        "mean_vs_timerank": mean_tr,
        "median_vs_timerank": float(np.median(tr)) if len(tr) else float("nan"),
        "mean_vs_same_distance": mean_sd,
        "median_vs_same_distance": float(np.median(sd)) if len(sd) else float("nan"),
        "n_better_timerank": int((tr < 0).sum()) if len(tr) else 0,
        "n_same_timerank": int((tr == 0).sum()) if len(tr) else 0,
        "n_worse_timerank": int((tr > 0).sum()) if len(tr) else 0,
        "n_better_samedist": int((sd < 0).sum()) if len(sd) else 0,
        "n_same_samedist": int((sd == 0).sum()) if len(sd) else 0,
        "n_worse_samedist": int((sd > 0).sum()) if len(sd) else 0,
        "rows": rows,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, default=_OUT)
    parser.add_argument(
        "--only",
        choices=("all", "r21", "r22", "r23", "r24"),
        default="all",
    )
    args = parser.parse_args()
    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    if args.only in ("all", "r21"):
        model = _load_model()
        r21 = r21_rollout(model)
        (out / "r21_rollout.json").write_text(
            json.dumps(r21, indent=2, default=str), encoding="utf-8"
        )
        print("CHECKPOINT R2.1 written.", flush=True)

    if args.only in ("all", "r22"):
        r22 = r22_plan_selection()
        (out / "r22_plans.json").write_text(
            json.dumps(r22, indent=2, default=str), encoding="utf-8"
        )

    if args.only in ("all", "r23"):
        r23 = r23_bias_cancel()
        (out / "r23_bias_cancel.json").write_text(
            json.dumps(r23, indent=2, default=str), encoding="utf-8"
        )

    if args.only in ("all", "r24"):
        r24 = r24_distribution()
        (out / "r24_distribution.json").write_text(
            json.dumps(r24, indent=2, default=str), encoding="utf-8"
        )

    print(f"\nWrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
