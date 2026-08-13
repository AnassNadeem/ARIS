"""Phase G1.1–G1.3 diagnosis: chained rollout, tyre-age bias, divergence audits.

No production code changes. Uses simulate()'s actual predict_lap_time path
(physics + damped residual, lags chained from prior *predictions*), not the
held-out MAE path (real lag1/lag2 at every step; optional MA(2) blend).

  python scripts/_g1_diagnose.py
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
    classify_decision,
    team_action_for,
)
from aris.eval.laptime import HELD_OUT_RACES  # noqa: E402
from aris.io import db  # noqa: E402
from aris.models.features import estimate_fuel_kg  # noqa: E402
from aris.models.predict import (  # noqa: E402
    damp_residual_toward_pace,
    predict_physics,
    reset_model_cache,
)
from aris.models.residual import ResidualModel  # noqa: E402
from aris.physics.bicycle import FUEL_PENALTY_S_PER_KG  # noqa: E402
from aris.physics.stint import detect_stints, filter_clean_laps  # noqa: E402
from aris.physics.tires import tire_pace_loss  # noqa: E402
from aris.recommend import recommend  # noqa: E402
from aris.simulate import (  # noqa: E402
    ActionKind,
    StrategyAction,
    _update_lags,
)
from aris.state import build_race_state  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402

fastf1.Cache.enable_cache(str(_ROOT / "fastf1_cache"))
_OUT = _ROOT / "results" / "g1"
_HORIZONS = (1, 5, 10, 20)
_SKIP_INTO_STINT = 3  # start a few green laps in, so lag1/lag2 are real
_MIN_STINT_LAPS = 20
_HIGH_TYRE_LIFE = 25


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    if len(a) == 0:
        return float("nan")
    return float(np.mean(np.abs(a - b)))


def _bias(pred: np.ndarray, true: np.ndarray) -> float:
    """pred - true. Positive = over-predict (too slow)."""
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
    """One-step prediction decomposed the same way predict_lap_time does."""
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
    base = physics - tire - fuel
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
        "base": base,
        "tire_deg": tire,
        "fuel": fuel,
        "residual_raw": residual_raw,
        "residual_damped": residual_damped,
        "pred": pred,
        "phys_minus_lag1": (physics - lag1) if lag1 is not None else None,
    }


def _load_race_laps(year: int, gp: str):
    session = fastf1.get_session(year, gp, "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    cfg = load_track_config(gp)
    track = cfg.load_physics()
    enriched = detect_stints(session.laps)
    return enriched, track, cfg


def _green_runs(stint: pd.DataFrame) -> list[pd.DataFrame]:
    """Consecutive TrackStatus=='1' non-pit laps inside one stint, in lap order."""
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


def _rollout_run(
    run: pd.DataFrame,
    *,
    track,
    cfg,
    model: ResidualModel,
    skip: int = _SKIP_INTO_STINT,
) -> dict[str, Any] | None:
    """Chained vs teacher-forced rollout over one green stretch."""
    run = run.sort_values("LapNumber").reset_index(drop=True)
    if len(run) < skip + max(_HORIZONS) :
        # Still allow shorter runs if they have 20+ stint laps but <20 remaining;
        # require at least skip+5 so +1 and +5 exist.
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
    chained_parts: list[dict[str, Any]] = []
    recent_chained = list(prior)
    recent_forced = list(prior)

    remaining = list(range(start, len(run)))
    for i in remaining:
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
        chained.append(float(comp["pred"]))
        forced.append(float(forced_c["pred"]))
        recent_chained.append(float(comp["pred"]))
        recent_forced.append(float(observed[i]))
        if len(recent_chained) > 10:
            recent_chained = recent_chained[-10:]
        if len(recent_forced) > 10:
            recent_forced = recent_forced[-10:]
        step = i - start + 1
        chained_parts.append(
            {
                "step": step,
                "lap": int(lap_numbers[i]),
                "compound": str(compounds[i]),
                "tyre_life": int(tyre_life[i]),
                "observed": float(observed[i]),
                "chained_pred": float(comp["pred"]),
                "forced_pred": float(forced_c["pred"]),
                "chained_physics": float(comp["physics"]),
                "chained_tire_deg": float(comp["tire_deg"]),
                "chained_residual_damped": float(comp["residual_damped"]),
                "chained_err": float(comp["pred"]) - float(observed[i]),
                "forced_err": float(forced_c["pred"]) - float(observed[i]),
            }
        )

    obs_rem = observed[start:]
    ch = np.array(chained, dtype=float)
    fo = np.array(forced, dtype=float)
    horizon_err: dict[str, Any] = {}
    for h in _HORIZONS:
        if len(ch) < h:
            horizon_err[f"+{h}"] = None
            continue
        horizon_err[f"+{h}"] = {
            "chained_err_s": float(ch[h - 1] - obs_rem[h - 1]),
            "forced_err_s": float(fo[h - 1] - obs_rem[h - 1]),
            "chained_abs_s": float(abs(ch[h - 1] - obs_rem[h - 1])),
            "forced_abs_s": float(abs(fo[h - 1] - obs_rem[h - 1])),
        }
    return {
        "n_steps": len(ch),
        "start_lap": int(lap_numbers[start]),
        "end_lap": int(lap_numbers[-1]),
        "compound": str(compounds[start]),
        "tyre_life_at_start": int(tyre_life[start]),
        "horizon": horizon_err,
        "chained_mae_s": _mae(ch, obs_rem),
        "forced_mae_s": _mae(fo, obs_rem),
        "chained_bias_s": _bias(ch, obs_rem),
        "forced_bias_s": _bias(fo, obs_rem),
        "steps": chained_parts,
    }


def g11_rollout(model: ResidualModel) -> dict[str, Any]:
    print("\n=== G1.1 chained rollout accuracy ===", flush=True)
    print(
        "Distinct from held-out MAE: lags are the model's own prior predictions "
        "(simulate() mechanism), not observed lag1/lag2.",
        flush=True,
    )
    examples: list[dict[str, Any]] = []
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
                    **{k: v for k, v in result.items() if k != "steps"},
                    "steps": result["steps"],
                }
                all_runs.append(row)
                by_compound[compound].append(row)

    def _horizon_pool(rows: list[dict[str, Any]], h: int, kind: str) -> list[float]:
        key = "chained_err_s" if kind == "chained" else "forced_err_s"
        vals: list[float] = []
        for r in rows:
            cell = r["horizon"].get(f"+{h}")
            if cell is not None:
                vals.append(float(cell[key]))
        return vals

    def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {"n_stints": len(rows)}
        for h in _HORIZONS:
            ch = np.array(_horizon_pool(rows, h, "chained"), dtype=float)
            fo = np.array(_horizon_pool(rows, h, "forced"), dtype=float)
            out[f"+{h}"] = {
                "n": int(len(ch)),
                "chained_mae_s": float(np.mean(np.abs(ch))) if len(ch) else float("nan"),
                "chained_bias_s": float(np.mean(ch)) if len(ch) else float("nan"),
                "forced_mae_s": float(np.mean(np.abs(fo))) if len(fo) else float("nan"),
                "forced_bias_s": float(np.mean(fo)) if len(fo) else float("nan"),
            }
        if rows:
            out["full_horizon_chained_mae_s"] = float(
                np.mean([r["chained_mae_s"] for r in rows])
            )
            out["full_horizon_chained_bias_s"] = float(
                np.mean([r["chained_bias_s"] for r in rows])
            )
        return out

    # Pick diverse named examples: longest green run per (compound) across tracks.
    picked: list[dict[str, Any]] = []
    used_gps: set[str] = set()
    for compound in ("HARD", "MEDIUM", "SOFT"):
        cand = sorted(
            by_compound.get(compound, []),
            key=lambda r: r["green_laps"],
            reverse=True,
        )
        for r in cand:
            if r["gp"] in used_gps and len(picked) >= 2:
                continue
            slim = {k: v for k, v in r.items() if k != "steps"}
            # keep a few step snapshots at horizons
            snaps = []
            for h in _HORIZONS:
                steps = r.get("steps") or []
                if len(steps) >= h:
                    snaps.append(steps[h - 1])
            slim["horizon_steps"] = snaps
            picked.append(slim)
            used_gps.add(r["gp"])
            if sum(1 for p in picked if p["compound"] == compound) >= 2:
                break
        if compound == "HARD" and len([p for p in picked if p["compound"] == "HARD"]) < 3:
            for r in cand:
                if r["gp"] in used_gps:
                    continue
                slim = {k: v for k, v in r.items() if k != "steps"}
                snaps = []
                for h in _HORIZONS:
                    steps = r.get("steps") or []
                    if len(steps) >= h:
                        snaps.append(steps[h - 1])
                slim["horizon_steps"] = snaps
                picked.append(slim)
                used_gps.add(r["gp"])
                if sum(1 for p in picked if p["compound"] == "HARD") >= 3:
                    break

    aggregate = {
        "all": _summarise(all_runs),
        "by_compound": {c: _summarise(rows) for c, rows in by_compound.items()},
    }
    print(
        f"  stints scored: {len(all_runs)} "
        f"(HARD={len(by_compound['HARD'])} MED={len(by_compound['MEDIUM'])} "
        f"SOFT={len(by_compound['SOFT'])})",
        flush=True,
    )
    for h in _HORIZONS:
        cell = aggregate["all"].get(f"+{h}", {})
        print(
            f"  +{h} laps  chained MAE={cell.get('chained_mae_s')} "
            f"bias={cell.get('chained_bias_s')}  "
            f"(teacher-forced MAE={cell.get('forced_mae_s')} "
            f"bias={cell.get('forced_bias_s')})  n={cell.get('n')}",
            flush=True,
        )
    for p in picked:
        print(
            f"  example {p['gp']} {p['driver']} {p['compound']} "
            f"L{p['start_lap']}-{p['end_lap']} green={p['green_laps']}",
            flush=True,
        )
    examples = picked
    # Drop bulky per-step traces from the all_runs dump (keep aggregate + examples).
    slim_runs = [{k: v for k, v in r.items() if k != "steps"} for r in all_runs]
    return {
        "metric": "chained_rollout_error_distinct_from_heldout_mae",
        "method": (
            "Start 3 green laps into a 20+ lap green stretch. Forward-simulate "
            "with predict_lap_time, feeding prior *predictions* as lag1/lag2/"
            "stint_roll3 (same as simulate._simulate_remainder). Teacher-forced "
            "control uses observed lags at every step (held-out-MAE style)."
        ),
        "horizons": list(_HORIZONS),
        "aggregate": aggregate,
        "examples": examples,
        "n_runs": len(all_runs),
        "runs_slim": slim_runs,
    }


def g12_tyre_age(model: ResidualModel) -> dict[str, Any]:
    print("\n=== G1.2 high tyre_life single-step (real lags, not chained) ===", flush=True)
    rows: list[dict[str, Any]] = []
    for year, gp in HELD_OUT_RACES:
        if year != 2024:
            continue
        print(f"  loading {year} {gp}...", flush=True)
        try:
            enriched, track, cfg = _load_race_laps(year, gp)
        except Exception as exc:  # noqa: BLE001
            print(f"    SKIP {gp}: {exc}", flush=True)
            continue
        clean = filter_clean_laps(enriched)
        if clean.empty:
            continue
        grouped = clean.groupby(["Driver", "StintId"], sort=False)["LapTimeS"]
        clean = clean.copy()
        clean["lag1_pace"] = grouped.shift(1)
        clean["lag2_pace"] = grouped.shift(2)
        clean["stint_roll3"] = grouped.transform(
            lambda s: s.shift(1).rolling(3, min_periods=1).mean()
        )
        total_laps = int(cfg.total_laps)
        for _, lap in clean.iterrows():
            if pd.isna(lap.get("lag1_pace")):
                continue
            compound = str(lap.get("Compound") or "MEDIUM").upper()
            if compound not in {"SOFT", "MEDIUM", "HARD"}:
                continue
            life = int(lap["TyreLife"]) if pd.notna(lap.get("TyreLife")) else 1
            fuel = estimate_fuel_kg(int(lap["LapNumber"]), total_laps=total_laps)
            lag1 = float(lap["lag1_pace"])
            lag2 = float(lap["lag2_pace"]) if pd.notna(lap.get("lag2_pace")) else lag1
            roll3 = float(lap["stint_roll3"]) if pd.notna(lap.get("stint_roll3")) else lag1
            c = _components(
                compound=compound,
                tyre_life=life,
                fuel_kg=fuel,
                lag1=lag1,
                lag2=lag2,
                roll3=roll3,
                track=track,
                model=model,
            )
            observed = float(lap["LapTimeS"])
            rows.append(
                {
                    "gp": gp,
                    "driver": str(lap["Driver"]),
                    "compound": compound,
                    "tyre_life": life,
                    "observed": observed,
                    "pred": float(c["pred"]),
                    "physics": float(c["physics"]),
                    "tire_deg": float(c["tire_deg"]),
                    "residual_damped": float(c["residual_damped"]),
                    "err": float(c["pred"]) - observed,
                    "physics_err": float(c["physics"]) - observed,
                }
            )

    frame = pd.DataFrame(rows)
    buckets = [(1, 10), (11, 20), (21, 24), (25, 34), (35, 80)]

    def _bucket_summary(sub: pd.DataFrame) -> dict[str, Any]:
        if sub.empty:
            return {"n": 0}
        err = sub["err"].to_numpy(dtype=float)
        phys = sub["physics_err"].to_numpy(dtype=float)
        return {
            "n": int(len(sub)),
            "model_mae_s": float(np.mean(np.abs(err))),
            "model_bias_s": float(np.mean(err)),
            "physics_mae_s": float(np.mean(np.abs(phys))),
            "physics_bias_s": float(np.mean(phys)),
        }

    by_compound: dict[str, Any] = {}
    for compound in ("HARD", "MEDIUM", "SOFT"):
        sub = frame[frame["compound"] == compound]
        entry: dict[str, Any] = {
            "all": _bucket_summary(sub),
            "tyre_life_ge_25": _bucket_summary(sub[sub["tyre_life"] >= _HIGH_TYRE_LIFE]),
            "buckets": {},
        }
        for lo, hi in buckets:
            chunk = sub[(sub["tyre_life"] >= lo) & (sub["tyre_life"] <= hi)]
            entry["buckets"][f"{lo}-{hi}"] = _bucket_summary(chunk)
        by_compound[compound] = entry
        ge25 = entry["tyre_life_ge_25"]
        print(
            f"  {compound} tyre_life>={_HIGH_TYRE_LIFE}: n={ge25.get('n', 0)} "
            f"model bias={ge25.get('model_bias_s')} MAE={ge25.get('model_mae_s')}  "
            f"physics-only bias={ge25.get('physics_bias_s')} "
            f"MAE={ge25.get('physics_mae_s')}",
            flush=True,
        )

    return {
        "metric": "single_step_high_tyre_life_bias",
        "method": (
            "Real lag1/lag2/roll3 at every lap (not chained). Bias = pred - observed; "
            "positive means the model makes old tyres look slower than they were."
        ),
        "high_tyre_life_threshold": _HIGH_TYRE_LIFE,
        "n_laps": int(len(frame)),
        "by_compound": by_compound,
    }


def _load_divergence_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted((_ROOT / "results" / "backtest").glob("2024_r*.json")):
        if path.name.endswith("_full.json") or path.name.endswith("_summary.json"):
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for d in data.get("decisions") or []:
            if d.get("classification") != "divergence_aris_hindsight":
                continue
            cases.append(
                {
                    "gp": data["gp"],
                    "year": data["year"],
                    "round_no": data["round_no"],
                    "session_id": data["session_id"],
                    "driver_code": data["driver_code"],
                    **d,
                }
            )
    return cases


def _sum_parts(parts: list[dict[str, Any]]) -> dict[str, float]:
    keys = ("physics", "base", "tire_deg", "fuel", "residual_damped", "pred")
    out = {k: 0.0 for k in keys}
    for p in parts:
        for k in keys:
            out[k] += float(p[k])
    return out


def _simulate_parts(
    state,
    action: StrategyAction,
    model: ResidualModel,
    *,
    max_laps: int | None = None,
) -> dict[str, Any]:
    """Mirror _simulate_remainder with per-lap physics/residual/tyre breakdown."""
    from aris.simulate import _pit_loss_s, _pit_schedule, _track_for

    schedule = _pit_schedule(action, state)
    pit_map = dict(schedule)
    pit_loss = _pit_loss_s(state)
    track = _track_for(state)
    compound = state.compound
    tyre_life = state.tyre_life
    recent: list[float] = []
    if state.lag1_pace is not None:
        recent.append(state.lag1_pace)
    if state.lag2_pace is not None:
        recent.insert(0, state.lag2_pace)
    parts: list[dict[str, Any]] = []
    total = 0.0
    last_lap = state.total_laps if max_laps is None else min(
        state.total_laps, state.lap_number + max_laps - 1
    )
    pit_loss_total = 0.0
    for lap in range(state.lap_number, last_lap + 1):
        fuel = estimate_fuel_kg(lap, total_laps=state.total_laps)
        lag1, lag2, roll3 = _update_lags(recent)
        if lap in pit_map:
            c = _components(
                compound=compound,
                tyre_life=tyre_life,
                fuel_kg=fuel,
                lag1=lag1,
                lag2=lag2,
                roll3=roll3,
                track=track,
                model=model,
            )
            pred = float(c["pred"])
            total += pred + pit_loss
            pit_loss_total += pit_loss
            recent.append(pred)
            parts.append(
                {
                    "lap": lap,
                    "event": f"pit->{pit_map[lap]}",
                    "compound": compound,
                    "tyre_life": tyre_life,
                    "pit_loss_s": pit_loss,
                    **{k: float(c[k]) if c[k] is not None else None for k in c},
                }
            )
            compound = pit_map[lap]
            tyre_life = 1
            continue
        c = _components(
            compound=compound,
            tyre_life=tyre_life,
            fuel_kg=fuel,
            lag1=lag1,
            lag2=lag2,
            roll3=roll3,
            track=track,
            model=model,
        )
        pred = float(c["pred"])
        total += pred
        recent.append(pred)
        if len(recent) > 10:
            recent = recent[-10:]
        parts.append(
            {
                "lap": lap,
                "event": "green",
                "compound": compound,
                "tyre_life": tyre_life,
                "pit_loss_s": 0.0,
                **{k: float(c[k]) if c[k] is not None else None for k in c},
            }
        )
        tyre_life += 1
    summed = _sum_parts(parts)
    summed["pit_loss_s"] = pit_loss_total
    summed["total_s"] = total
    return {"total_s": total, "sum": summed, "n_laps": len(parts), "laps": parts}


def g13_audit(model: ResidualModel) -> dict[str, Any]:
    print("\n=== G1.3 divergence_aris_hindsight audits ===", flush=True)
    cases = _load_divergence_cases()
    print(f"  loaded {len(cases)} ARIS-hindsight cases", flush=True)
    # Spread across tracks: first case per GP, then fill to >=6.
    by_gp: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in cases:
        by_gp[c["gp"]].append(c)
    selected: list[dict[str, Any]] = []
    for gp, rows in by_gp.items():
        selected.append(rows[0])
        if len(selected) >= 8:
            break
    if len(selected) < 6:
        for c in cases:
            if c not in selected:
                selected.append(c)
            if len(selected) >= 6:
                break

    audits: list[dict[str, Any]] = []
    for case in selected:
        gp = case["gp"]
        sid = int(case["session_id"])
        code = str(case["driver_code"])
        lap = int(case["inflection"]["lap"])
        print(f"  audit {gp} {code} L{lap} {case['aris_label']}", flush=True)
        drivers = db.fetch_drivers(sid)
        hit = drivers[drivers["code"] == code]
        if hit.empty:
            audits.append({**case, "error": "driver not in DB"})
            continue
        driver_id = int(hit.iloc[0]["driver_id"])
        try:
            state = build_race_state(sid, driver_id, lap)
        except Exception as exc:  # noqa: BLE001
            audits.append({**case, "error": f"build_race_state: {exc}"})
            continue
        rec_result = recommend(state, top_k=3, mc_draws=0)
        top = rec_result.recommendations[0] if rec_result.recommendations else None
        from aris.eval.backtest import Inflection

        inf = Inflection(
            kind=str(case["inflection"]["kind"]),
            lap=lap,
            compound=case["inflection"].get("compound"),
            team_pitted=bool(case["inflection"].get("team_pitted")),
            notes=str(case["inflection"].get("notes") or ""),
        )
        team_act = team_action_for(inf, state)
        aris_act = top.action if top is not None else StrategyAction(kind=ActionKind.STAY_OUT)
        team_parts = _simulate_parts(state, team_act, model)
        aris_parts = _simulate_parts(state, aris_act, model)
        stay_parts = _simulate_parts(
            state, StrategyAction(kind=ActionKind.STAY_OUT), model
        )
        klass, team_s, aris_s = classify_decision(top, inf, state, rainfall=False)
        delta = aris_parts["total_s"] - team_parts["total_s"]
        breakdown = {
            "pit_loss_delta_s": aris_parts["sum"]["pit_loss_s"]
            - team_parts["sum"]["pit_loss_s"],
            "physics_delta_s": aris_parts["sum"]["physics"] - team_parts["sum"]["physics"],
            "tire_deg_delta_s": aris_parts["sum"]["tire_deg"]
            - team_parts["sum"]["tire_deg"],
            "fuel_delta_s": aris_parts["sum"]["fuel"] - team_parts["sum"]["fuel"],
            "base_delta_s": aris_parts["sum"]["base"] - team_parts["sum"]["base"],
            "residual_delta_s": aris_parts["sum"]["residual_damped"]
            - team_parts["sum"]["residual_damped"],
            "total_delta_s": delta,
        }
        # End-of-horizon tyre state snapshot (last predicted lap).
        def _tail(parts: dict[str, Any]) -> dict[str, Any]:
            last = parts["laps"][-1] if parts["laps"] else {}
            return {
                "compound": last.get("compound"),
                "tyre_life": last.get("tyre_life"),
                "pred": last.get("pred"),
                "physics": last.get("physics"),
                "tire_deg": last.get("tire_deg"),
                "residual_damped": last.get("residual_damped"),
            }

        audit = {
            "gp": gp,
            "year": case["year"],
            "round_no": case["round_no"],
            "driver_code": code,
            "lap": lap,
            "inflection": case["inflection"],
            "logged_aris_label": case.get("aris_label"),
            "logged_team_sim_s": case.get("team_sim_s"),
            "logged_aris_sim_s": case.get("aris_sim_s"),
            "recomputed_classification": klass,
            "state": {
                "compound": state.compound,
                "tyre_life": state.tyre_life,
                "fuel_kg": state.fuel_kg,
                "laps_remaining": state.laps_remaining,
                "lag1_pace": state.lag1_pace,
                "lag2_pace": state.lag2_pace,
                "track_status": state.track_status,
                "confidence_caveat": state.confidence_caveat,
            },
            "team_action": team_act.model_dump(),
            "aris_action": aris_act.model_dump(),
            "aris_label": top.label if top else None,
            "team_total_s": team_parts["total_s"],
            "aris_total_s": aris_parts["total_s"],
            "stay_total_s": stay_parts["total_s"],
            "recomputed_team_sim_s": team_s,
            "recomputed_aris_sim_s": aris_s,
            "breakdown_aris_minus_team": breakdown,
            "team_sum": team_parts["sum"],
            "aris_sum": aris_parts["sum"],
            "stay_sum": stay_parts["sum"],
            "team_tail": _tail(team_parts),
            "aris_tail": _tail(aris_parts),
            "aris_first_10": aris_parts["laps"][:10],
            "team_first_10": team_parts["laps"][:10],
        }
        print(
            f"    team={team_act.kind.value} {team_act.pit_compound} "
            f"aris={top.label if top else None}",
            flush=True,
        )
        print(
            f"    delta ARIS-team={delta:.1f}s  "
            f"tire={breakdown['tire_deg_delta_s']:.1f} "
            f"phys={breakdown['physics_delta_s']:.1f} "
            f"resid={breakdown['residual_delta_s']:.1f} "
            f"pit_loss={breakdown['pit_loss_delta_s']:.1f}",
            flush=True,
        )
        audits.append(audit)

    label_kinds = defaultdict(int)
    for c in cases:
        lbl = str(c.get("aris_label") or "")
        if lbl.lower().startswith("pit"):
            label_kinds["pit"] += 1
        elif "stay" in lbl.lower():
            label_kinds["stay"] += 1
        elif lbl.lower().startswith("brake") or lbl.lower().startswith("lift"):
            label_kinds["line"] += 1
        elif lbl.lower().startswith("plan"):
            label_kinds["plan"] += 1
        else:
            label_kinds["other"] += 1
    return {
        "n_aris_hindsight": len(cases),
        "label_mix": dict(label_kinds),
        "n_audited": len(audits),
        "audits": audits,
    }


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    model = _load_model()
    g11 = g11_rollout(model)
    (_OUT / "g11_rollout.json").write_text(
        json.dumps(g11, indent=2, default=str), encoding="utf-8"
    )
    g12 = g12_tyre_age(model)
    (_OUT / "g12_tyre_age.json").write_text(
        json.dumps(g12, indent=2, default=str), encoding="utf-8"
    )
    g13 = g13_audit(model)
    (_OUT / "g13_audits.json").write_text(
        json.dumps(g13, indent=2, default=str), encoding="utf-8"
    )
    print(f"\nWrote {_OUT}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
