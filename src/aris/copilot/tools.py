"""Copilot tool execution — wrap existing ARIS functions; do not recompute race math."""

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)

from aris.copilot.context import FieldCar, get_context, require_state
from aris.copilot.schemas import TOOL_SCHEMAS
from aris.field.rivals import RivalPitEstimate, RivalState, estimate_rival_pit_lap
from aris.physics.tires import get_deg_slope as _get_deg_slope
from aris.physics.tires import normalize_compound
from aris.recommend import UNDERCUT_WINDOW_S, recommend as _recommend
from aris.risk.sc_risk_model import circuit_key, load_historical_rates, predict_sc_risk
from aris.simulate import ActionKind, StrategyAction, get_pit_loss, simulate, simulate_undercut
from aris.simulate_mc import compare_actions_mc
from aris.state import RaceState
from aris.tracks import load_track_config

__all__ = ["TOOL_SCHEMAS", "execute_tool"]

_PRIORS_CACHE: dict[str, Any] | None = None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return float(value)
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except Exception:
            pass
    return str(value)


def _priors() -> dict[str, Any]:
    global _PRIORS_CACHE
    if _PRIORS_CACHE is not None:
        return _PRIORS_CACHE
    from aris.copilot.corpus import load_prior_files

    _PRIORS_CACHE = load_prior_files()
    return _PRIORS_CACHE


def _field_car(code: str) -> FieldCar | None:
    return get_context().car(code)


def _copy_state(*, lap: int | None = None) -> RaceState:
    state = require_state()
    if lap is None or int(lap) == int(state.lap_number):
        return state
    delta = int(lap) - int(state.lap_number)
    return state.model_copy(
        update={
            "lap_number": int(lap),
            "tyre_life": max(1, int(state.tyre_life) + delta),
            "laps_remaining": max(0, int(state.laps_remaining) - delta),
        }
    )


def _parse_action(args: dict[str, Any], state: RaceState) -> StrategyAction:
    raw = str(args.get("action") or args.get("kind") or "").strip()
    compound = args.get("compound") or args.get("pit_compound")
    pit_lap = args.get("pit_lap")
    token = raw.upper().replace("-", "_").replace(" ", "_")
    if token in {"STAY", "STAY_OUT", "STAYOUT"}:
        return StrategyAction(kind=ActionKind.STAY_OUT)
    if token in {"PIT_NOW", "PITNOW", "BOX", "BOX_NOW", "PIT"} and pit_lap is None:
        return StrategyAction(
            kind=ActionKind.PIT_NOW,
            pit_compound=normalize_compound(str(compound or state.pit_compound or "HARD")),
        )
    if token in {"PIT_LAP", "PIT_LATER", "PIT_SOON"} or pit_lap is not None:
        lap = int(pit_lap) if pit_lap is not None else int(state.lap_number) + 1
        return StrategyAction(
            kind=ActionKind.PIT_LAP,
            pit_lap=lap,
            pit_compound=normalize_compound(str(compound or state.pit_compound or "HARD")),
        )
    if compound:
        return StrategyAction(
            kind=ActionKind.PIT_NOW,
            pit_compound=normalize_compound(str(compound)),
        )
    return StrategyAction(kind=ActionKind.STAY_OUT)


def _slopes_for(state: RaceState) -> dict[str, float]:
    return {
        c: _get_deg_slope(
            c,
            circuit_id=state.country,
            year=int(state.year) if state.year else None,
            round_number=int(state.round_no) if state.round_no else None,
        )
        for c in ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")
    }


def tool_get_gap(driver: str, lap: int | None = None, vs_driver: str | None = None) -> dict[str, Any]:
    state = _copy_state(lap=lap)
    ctx = get_context()
    code = (driver or state.driver_code).upper()
    car = ctx.car(code)
    pos = car.position if car and car.position is not None else state.position
    gap_leader = (
        car.gap_to_leader_s
        if car and car.gap_to_leader_s is not None
        else (state.gap_to_leader_s if code == state.driver_code.upper() else None)
    )
    order: list[dict[str, Any]] = []
    rows = sorted(ctx.field, key=lambda r: r.position or 99)
    if not rows and state.driver_code:
        rows = [
            FieldCar(
                driver_code=state.driver_code,
                position=state.position,
                gap_to_leader_s=state.gap_to_leader_s,
                gap_ahead_s=state.gap_ahead_s,
                gap_behind_s=state.gap_behind_s,
                compound=state.compound,
                tyre_life=state.tyre_life,
                last_lap_s=state.lag1_pace,
                name=state.driver_name,
            )
        ]
    for row in rows:
        order.append(
            {
                "position": row.position,
                "driver": row.driver_code,
                "compound": row.compound,
                "tyre_life": row.tyre_life,
                "gap_to_leader_s": row.gap_to_leader_s,
            }
        )
    ahead = next((r for r in rows if (r.position or 99) == (pos or 0) - 1), None)
    behind = next((r for r in rows if (r.position or 99) == (pos or 0) + 1), None)
    gap_ahead = None
    if car and car.gap_ahead_s is not None:
        gap_ahead = car.gap_ahead_s
    elif code == state.driver_code.upper():
        gap_ahead = state.gap_ahead_s
    elif ahead and gap_leader is not None and ahead.gap_to_leader_s is not None:
        gap_ahead = float(gap_leader) - float(ahead.gap_to_leader_s)
    gap_behind = None
    if car and car.gap_behind_s is not None:
        gap_behind = car.gap_behind_s
    elif code == state.driver_code.upper():
        gap_behind = state.gap_behind_s
    elif behind and gap_leader is not None and behind.gap_to_leader_s is not None:
        gap_behind = float(behind.gap_to_leader_s) - float(gap_leader)
    _log.debug(
        "get_gap asked=%s state_driver=%s lap=%s pos=%s gap_leader=%s",
        code,
        state.driver_code,
        int(state.lap_number),
        pos,
        gap_leader,
    )
    out = {
        "driver": code,
        "lap": int(state.lap_number),
        "position": pos,
        "compound": (car.compound if car else None) or (state.compound if code == state.driver_code.upper() else None),
        "tyre_life": (car.tyre_life if car else None)
        if car
        else (state.tyre_life if code == state.driver_code.upper() else None),
        "gap_to_leader_s": gap_leader,
        "gap_ahead_s": gap_ahead,
        "gap_behind_s": gap_behind,
        "ahead": (
            {
                "driver": ahead.driver_code,
                "gap_s": gap_ahead,
                "compound": ahead.compound,
                "tyre_life": ahead.tyre_life,
            }
            if ahead
            else None
        ),
        "behind": (
            {
                "driver": behind.driver_code,
                "gap_s": gap_behind,
                "compound": behind.compound,
                "tyre_life": behind.tyre_life,
            }
            if behind
            else None
        ),
        "order": order,
    }
    if vs_driver:
        vs = str(vs_driver).upper()
        vs_car = ctx.car(vs)
        vs_gap_leader = vs_car.gap_to_leader_s if vs_car is not None else None
        interval = None
        if gap_leader is not None and vs_gap_leader is not None:
            interval = float(gap_leader) - float(vs_gap_leader)
        out["vs_driver"] = vs
        out["focus_driver"] = code
        out["gap_to_target_s"] = interval
    return out


def tool_get_undercut_window(
    focus_driver: str,
    rival_driver: str,
    compound: str | None = None,
) -> dict[str, Any]:
    state = require_state()
    pit_compound = normalize_compound(str(compound or state.pit_compound or "HARD"))
    cfg = load_track_config(state.country, year=state.year, round_no=state.round_no)
    pit_loss = get_pit_loss(cfg.pit_loss_s, state.track_status, circuit_key=state.country)
    slopes = _slopes_for(state)
    rival_car = _field_car(rival_driver)
    focus_car = _field_car(focus_driver)
    gap = None
    if focus_car and rival_car and focus_car.gap_to_leader_s is not None and rival_car.gap_to_leader_s is not None:
        gap = abs(float(focus_car.gap_to_leader_s) - float(rival_car.gap_to_leader_s))
    elif state.gap_ahead_s is not None:
        gap = float(state.gap_ahead_s)
    rival_state = RivalState(
        driver_code=str(rival_driver).upper(),
        position=int(rival_car.position or 2) if rival_car else 2,
        compound=str(rival_car.compound or "MEDIUM") if rival_car else "MEDIUM",
        tyre_life=int(rival_car.tyre_life or 12) if rival_car else 12,
        gap_to_focus=float(gap or 0.0),
        gap_trend=0.0,
        team="",
        last_lap_s=float(
            (rival_car.last_lap_s if rival_car and rival_car.last_lap_s is not None else None)
            or state.lag1_pace
            or 90.0
        ),
    )
    estimate = estimate_rival_pit_lap(
        rival_state,
        int(state.lap_number),
        int(state.total_laps),
        state.country,
    )
    window_laps: list[int] = []
    per_lap: list[dict[str, Any]] = []
    horizon = min(8, max(1, int(state.laps_remaining)))
    for offset in range(horizon):
        snapped = state.model_copy(
            update={
                "lap_number": int(state.lap_number) + offset,
                "tyre_life": max(1, int(state.tyre_life) + offset),
                "laps_remaining": max(0, int(state.laps_remaining) - offset),
            }
        )
        delta = float(
            simulate_undercut(snapped, estimate, pit_compound, pit_loss, slopes)
        )
        in_gap = gap is not None and gap <= float(UNDERCUT_WINDOW_S)
        open_now = delta < 0.0 or in_gap
        per_lap.append(
            {
                "lap": int(snapped.lap_number),
                "delta_s": delta,
                "in_gap_window": in_gap,
            }
        )
        if open_now:
            window_laps.append(int(snapped.lap_number))
    now_delta = per_lap[0]["delta_s"] if per_lap else 0.0
    return {
        "focus_driver": str(focus_driver).upper(),
        "rival_driver": str(rival_driver).upper(),
        "compound": pit_compound,
        "window_open": bool(window_laps),
        "window_laps": window_laps,
        "window_start_lap": window_laps[0] if window_laps else None,
        "window_end_lap": window_laps[-1] if window_laps else None,
        "delta_s": now_delta,
        "gap_to_rival_s": gap,
        "undercut_window_s": float(UNDERCUT_WINDOW_S),
        "rival_estimated_pit_lap": int(estimate.estimated_pit_lap),
        "per_lap": per_lap,
        "source": "simulate_undercut",
    }


def tool_get_deg_slope(
    compound: str,
    circuit_id: str | None = None,
    year: int | None = None,
    round_number: int | None = None,
) -> dict[str, Any]:
    ctx = get_context()
    state = ctx.state
    circuit = circuit_id or (state.country if state else None)
    yr = year if year is not None else (int(state.year) if state else None)
    rnd = round_number if round_number is not None else (int(state.round_no) if state else None)
    slope = float(_get_deg_slope(compound, circuit, yr, rnd))
    return {
        "compound": normalize_compound(compound),
        "slope_s_per_lap": slope,
        "circuit_id": circuit,
        "year": yr,
        "round_number": rnd,
    }


def tool_simulate(**args: Any) -> dict[str, Any]:
    state = require_state()
    action = _parse_action(args, state)
    outcome = simulate(state, action)
    dumped = outcome.model_dump()
    dumped["label"] = (
        "Stay out"
        if action.kind == ActionKind.STAY_OUT
        else (
            f"Pit now for {action.pit_compound}"
            if action.kind == ActionKind.PIT_NOW
            else f"Pit lap {action.pit_lap} for {action.pit_compound}"
        )
    )
    return dumped


def tool_recommend() -> dict[str, Any]:
    state = require_state()
    result = _recommend(state, top_k=3, mc_draws=0)
    rows = []
    for rec in result.recommendations:
        rows.append(
            {
                "rank": rec.rank,
                "label": rec.label,
                "delta_vs_stay_out_s": rec.delta_vs_stay_out_s,
                "mean_race_time_s": rec.mean_race_time_s,
                "p10_delta_s": rec.p10_delta_s,
                "p90_delta_s": rec.p90_delta_s,
                "p_best": None,
                "evidence": rec.evidence,
                "action": rec.action.model_dump(),
            }
        )
    return {
        "driver_code": result.driver_code,
        "lap": result.state_lap,
        "compound": result.compound,
        "top_3": rows,
    }


def tool_get_sc_risk(lap: int | None = None, horizon: int = 5) -> dict[str, Any]:
    state = _copy_state(lap=lap)
    p5, p10 = predict_sc_risk(state=state)
    h = 5 if int(horizon) <= 5 else 10
    p = p5 if h <= 5 else p10
    circuit = str(state.country or state.track_name or "")
    hist = load_historical_rates().get(circuit_key(circuit), None)
    return {
        "p_sc": float(p),
        "horizon": h,
        "lap": int(state.lap_number),
        "p_sc_next_5": float(p5),
        "p_sc_next_10": float(p10),
        "historical_circuit_rate": hist,
        "note": (
            "SC/VSC risk AUC is ~0.55; the circuit prior is the useful part, "
            "not lap-to-lap incident detection."
        ),
    }


def tool_get_wet_state(lap: int | None = None) -> dict[str, Any]:
    state = _copy_state(lap=lap)
    from aris.risk.wet_classifier import classify_track_state_rules, rain_laps_last_5

    rain_flag = bool(getattr(state, "rainfall", False))
    n_rain = rain_laps_last_5(None, int(state.lap_number), current_rainfall=rain_flag)
    temp = getattr(state, "track_temp_c", None)
    label, conf = classify_track_state_rules(
        rain_flag=rain_flag,
        rain_laps_last_5=n_rain,
        track_temp_c=float(temp) if temp is not None else 25.0,
        inter_on_track=normalize_compound(state.compound) in {"INTERMEDIATE", "WET"},
        inter_pace_advantage_s=0.0,
    )
    # Prefer values already stamped on RaceState when present (build_race_state path).
    stamped = str(getattr(state, "track_state", "") or "")
    if stamped and not rain_flag and n_rain == 0:
        label = stamped
        conf = float(getattr(state, "track_state_confidence", conf) or conf)
    return {
        "track_state": label,
        "confidence": float(conf),
        "rainfall": rain_flag,
        "lap": int(state.lap_number),
        "note": "Rule-based T10-C classifier; not a fitted model (only 5 wet races 2024–2025).",
    }


def _mc_action(action: dict[str, Any], state: RaceState, pit_loss: float, slopes: dict[str, float]) -> dict[str, Any]:
    parsed = _parse_action(action, state)
    name = str(action.get("name") or action.get("label") or parsed.kind.value)
    if parsed.kind == ActionKind.STAY_OUT:
        return {
            "name": name if name not in {"stay_out", "STAY_OUT"} else "Stay out",
            "pit_lap": None,
            "compound": state.compound,
            "pit_compound_slope": float(slopes.get(normalize_compound(state.compound), 0.03)),
            "pit_loss": 0.0,
        }
    abs_lap = parsed.pit_lap if parsed.pit_lap is not None else int(state.lap_number)
    rel = max(0, int(abs_lap) - int(state.lap_number))
    compound = normalize_compound(str(parsed.pit_compound or "HARD"))
    if parsed.kind == ActionKind.PIT_NOW:
        rel = 0
        name = name if "pit" in name.lower() or "box" in name.lower() else f"Pit now {compound}"
    return {
        "name": name,
        "pit_lap": rel,
        "compound": compound,
        "pit_compound_slope": float(slopes.get(compound, 0.03)),
        "pit_loss": float(pit_loss),
    }


def tool_run_mc_comparison(actions: list[dict[str, Any]], n_scenarios: int = 200) -> dict[str, Any]:
    state = require_state()
    cfg = load_track_config(state.country, year=state.year, round_no=state.round_no)
    pit_loss = float(cfg.pit_loss_s)
    slopes = _slopes_for(state)
    remaining = max(int(state.laps_remaining), 1)
    p5 = float(getattr(state, "p_sc_next_5_laps", 0.07) or 0.07)
    p_sc = 1.0 - (1.0 - min(max(p5, 0.0), 1.0)) ** (1.0 / 5.0)
    try:
        from aris.uncertainty.conformal import load_conformal_result

        conf = load_conformal_result() or {}
        mae = float(conf.get("median_abs_error") or 0.5)
    except Exception:
        mae = 0.5
    deg_sigma = max(0.01, mae / (remaining ** 0.5))
    from aris.physics.tyre_warmup import tyre_warmup_penalty

    warmups = {c: float(tyre_warmup_penalty(c)) for c in ("SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET")}
    mc_actions = [_mc_action(a, state, pit_loss, slopes) for a in (actions or [])]
    if not any(a.get("pit_lap") is None for a in mc_actions):
        mc_actions.append(
            {
                "name": "Stay out",
                "pit_lap": None,
                "compound": state.compound,
                "pit_compound_slope": float(slopes.get(normalize_compound(state.compound), 0.03)),
                "pit_loss": 0.0,
            }
        )
    rows = compare_actions_mc(
        mc_actions,
        {
            "laps_remaining": remaining,
            "base_lap_time": float(state.lag1_pace or 90.0),
            "deg_slope": float(slopes.get(normalize_compound(state.compound), 0.03)),
            "deg_sigma": deg_sigma,
            "tyre_age": int(state.tyre_life or 1),
            "p_sc_per_lap": p_sc,
            "sc_duration_laps": 3,
            "sc_pit_loss_multiplier": 0.50,
        },
        n_scenarios=int(n_scenarios or 200),
        warmup_penalties=warmups,
        seed=42,
    )
    return {"n_scenarios": int(n_scenarios or 200), "actions": rows}


def tool_get_driver_style(driver: str) -> dict[str, Any]:
    code = str(driver or "").upper()
    drivers = (_priors().get("drivers") or {})
    rec = drivers.get(code) or {}
    if not rec:
        return {
            "driver": code,
            "found": False,
            "note": "No driver prior indexed for that code.",
        }
    return {
        "driver": code,
        "found": True,
        "name": rec.get("name"),
        "tyre_style": rec.get("tyre_style"),
        "text": rec.get("text"),
        "typical_stint_laps": rec.get("typical_stint_laps") or {},
        "lap_time_variance_s": rec.get("lap_time_variance_s"),
        "overtakes_per_race": rec.get("overtakes_per_race"),
        "source": "data/priors/drivers.json",
    }


def tool_get_circuit_info(circuit_id: str) -> dict[str, Any]:
    needle = str(circuit_id or "").strip()
    circuits = _priors().get("circuits") or {}
    rec: dict[str, Any] = {}
    key = needle.lower().replace(" ", "_")
    if key in circuits:
        rec = circuits[key]
        rec_key = key
    else:
        rec_key = key
        for cid, row in circuits.items():
            aliases = [cid, str(row.get("name") or "").lower()]
            aliases.extend(str(a).lower() for a in (row.get("aliases") or []))
            if needle.lower() in aliases or key in {a.replace(" ", "_") for a in aliases}:
                rec = row
                rec_key = cid
                break
    try:
        cfg = load_track_config(rec.get("name") or needle)
    except Exception:
        cfg = None
    rates = load_historical_rates()
    from aris.risk.sc_risk_model import circuit_key as sc_key

    hist = rates.get(sc_key(rec.get("name") or needle))
    return {
        "circuit_id": rec_key,
        "name": rec.get("name") or (cfg.name if cfg else needle),
        "deg": rec.get("deg"),
        "text": rec.get("text"),
        "typical_sc_rate": rec.get("typical_sc_rate") if rec.get("typical_sc_rate") is not None else hist,
        "historical_sc_rate": hist,
        "lap_length_m": rec.get("lap_length_m") or (cfg.lap_length_m if cfg else None),
        "total_laps": cfg.total_laps if cfg else None,
        "pit_loss_s": cfg.pit_loss_s if cfg else None,
        "source": "data/priors/circuits.json + track YAML",
    }


def tool_get_session_result(
    year: int | None = None,
    country: str | None = None,
    last_year: bool = False,
    podium: bool = False,
) -> dict[str, Any]:
    """Classified winner/podium from loaded race-result documents."""
    del podium  # always return podium rows; the agent chooses what to narrate
    ctx = get_context()
    state = ctx.state
    loc = (country or (state.country if state else "") or "").strip()
    y = int(year) if year is not None else (int(state.year) if state and state.year else None)
    if last_year and y is not None:
        y -= 1
    if not y or not loc:
        return {
            "year": y,
            "country": loc or None,
            "winner": None,
            "podium": [],
            "found": False,
        }
    from aris.ask.sources import load_race_documents

    loc_l = loc.lower()
    rows: list[dict[str, Any]] = []
    for doc in load_race_documents():
        facts = doc.facts
        if facts.get("year") != y:
            continue
        if str(facts.get("country") or "").lower() != loc_l:
            continue
        pos = facts.get("finish_pos")
        if pos is None:
            continue
        try:
            pos_i = int(pos)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "driver_code": facts.get("driver_code"),
                "full_name": facts.get("full_name"),
                "team": facts.get("team"),
                "finish_pos": pos_i,
                "grid_pos": facts.get("grid_pos"),
                "year": y,
                "country": facts.get("country"),
            }
        )
    rows.sort(key=lambda r: int(r["finish_pos"]))
    winner = next((r for r in rows if r["finish_pos"] == 1), None)
    return {
        "year": y,
        "country": loc,
        "winner": winner,
        "podium": [r for r in rows if r["finish_pos"] <= 3],
        "found": winner is not None,
    }


_DISPATCH = {
    "get_gap": tool_get_gap,
    "get_undercut_window": tool_get_undercut_window,
    "get_deg_slope": tool_get_deg_slope,
    "simulate": tool_simulate,
    "recommend": tool_recommend,
    "get_sc_risk": tool_get_sc_risk,
    "get_wet_state": tool_get_wet_state,
    "run_mc_comparison": tool_run_mc_comparison,
    "get_driver_style": tool_get_driver_style,
    "get_circuit_info": tool_get_circuit_info,
    "get_session_result": tool_get_session_result,
}


def execute_tool(name: str, args: dict | None = None) -> Any:
    """Import the ARIS function, inject RaceState, call it, return JSON-able data."""
    fn = _DISPATCH.get(str(name))
    if fn is None:
        return {"error": f"unknown_tool:{name}"}
    kwargs = dict(args or {})
    kwargs.pop("state", None)
    kwargs.pop("race_state", None)
    kwargs.pop("RaceState", None)
    try:
        return _jsonable(fn(**kwargs))
    except TypeError as extra:
        return {"error": f"bad_args:{name}:{extra}"}
    except Exception as extra:
        return {"error": f"{type(extra).__name__}:{extra}"}
