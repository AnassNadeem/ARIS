"""Ghost vs real: ARIS recommended strategy vs the FastF1 classified run.

Calls ``recommend()`` and ``simulate()`` as-is; does not change either.
The ghost is a parallel run of ARIS's lights-out plan from lap 1.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

from aris.explain.session import (
    DEFAULT_SESSION_ID,
    ExplainBundle,
    detect_stints_inplace,
    driver_laps,
    load_explain_bundle,
)
from aris.ghost import (
    pick_strategy_recommendation,
    schedule_from_recommendation,
    score_parallel_ghost,
)
from aris.models.features import estimate_fuel_kg
from aris.narrate import narrate_recommendation
from aris.physics.tires import normalize_compound
from aris.recommend import recommend
from aris.state import RaceState

_log = logging.getLogger(__name__)

# Lights-out call. Retry lap 2 if lap 1 returns STRATEGY_RESET.
_PRERACE_LAPS = (1, 2)

# (session_id, driver) → full ghost-vs-real payload including per-lap ticks.
_VS_REAL_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def clear_ghost_vs_real_cache() -> None:
    _VS_REAL_CACHE.clear()


def get_ghost_vs_real(
    driver: str,
    session_id: str | None = None,
    *,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    bundle: ExplainBundle | None = None,
) -> dict[str, Any]:
    """Per-lap ghost (ARIS) vs real (FastF1) position, gap, compound, and pit laps."""
    data = bundle or load_explain_bundle(
        session_id or DEFAULT_SESSION_ID,
        year=year,
        round_number=round_number,
        session_type=session_type,
    )
    code = str(driver).upper()
    cache_key = (str(data.session_id), code)
    if bundle is None and cache_key in _VS_REAL_CACHE:
        return _VS_REAL_CACHE[cache_key]

    result = _compute_ghost_vs_real(data, code)
    if bundle is None:
        _VS_REAL_CACHE[cache_key] = result
    return result


def get_ghost_lap_ticks(
    driver: str,
    session_id: str | None = None,
    *,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    bundle: ExplainBundle | None = None,
) -> dict[int, dict | None]:
    """Per-lap ghost_to_dict() map used by replay frames (cached with vs-real)."""
    payload = get_ghost_vs_real(
        driver,
        session_id,
        year=year,
        round_number=round_number,
        session_type=session_type,
        bundle=bundle,
    )
    ticks = payload.get("ticks") or {}
    return {int(k): v for k, v in ticks.items()}


def _compute_ghost_vs_real(data: ExplainBundle, code: str) -> dict[str, Any]:
    all_laps = detect_stints_inplace(data.laps.copy()) if not data.laps.empty else data.laps
    focus = driver_laps(all_laps, code)
    if focus.empty:
        return _empty_ghost(data, code)

    real_times, real_compound, real_pos_raw, real_laps = _series_for_driver(focus)
    if not real_laps:
        return _empty_ghost(data, code)

    real_pits = _pit_laps(focus)
    field_maps = _field_lap_times(all_laps)
    field_lists = {
        d: _aligned_times(ts, real_laps) for d, ts in field_maps.items()
    }
    field_lists[code] = real_times
    real_cum = _cumulative(real_times)
    field_cum = {d: _cumulative(ts) for d, ts in field_lists.items()}
    real_pos, real_gap = _rank_and_gap(code, real_cum, field_cum, fallback_pos=real_pos_raw)

    state, rec_result, card, decision_lap = _prerace_recommend(data, code, focus)
    first = focus.sort_values("LapNumber").iloc[0]
    raw = first["Compound"] if "Compound" in first.index else state.compound
    start_compound = normalize_compound(str(raw if pd.notna(raw) else state.compound))
    plan = schedule_from_recommendation(
        card, start_compound=start_compound, lap_number=decision_lap
    )
    typical = float(np.median(real_times)) if real_times else 90.0
    if not np.isfinite(typical) or typical < 30:
        typical = 90.0

    lap_rows = _lap_rows_from_focus(focus, real_pits)
    field_cum_by_lap: dict[int, dict[str, float]] = {}
    for i, lap_no in enumerate(real_laps):
        field_cum_by_lap[int(lap_no)] = {
            d: float(cum[i]) for d, cum in field_cum.items() if i < len(cum)
        }

    ticks = score_parallel_ghost(
        template_state=state,
        lap_rows=lap_rows,
        plan=plan,
        typical_lap_s=typical,
        field_cum_by_lap=field_cum_by_lap,
    )
    ghost_times = [
        float((ticks.get(int(lap)) or {}).get("ghost_lap_s") or typical)
        for lap in real_laps
    ]
    n = min(len(real_laps), len(ghost_times) or len(real_laps))
    real_laps = real_laps[:n]
    real_times = real_times[:n]
    real_compound = real_compound[:n]
    real_cum = real_cum[:n]
    real_pos = real_pos[:n]
    real_gap = real_gap[:n]

    if len(ghost_times) < n:
        last = ghost_times[-1] if ghost_times else (real_times[-1] if real_times else 90.0)
        ghost_times = list(ghost_times) + [last] * (n - len(ghost_times))
    ghost_times = ghost_times[:n]
    ghost_rank_times: list[float] = []
    for i, lap_no in enumerate(real_laps):
        tick = ticks.get(int(lap_no)) or {}
        delta = float(tick.get("ghost_cumulative_delta") or 0.0)
        ghost_rank_times.append(float(real_cum[i]) - delta)
    ghost_field = {**field_cum, code: ghost_rank_times}
    ghost_pos, ghost_gap = _rank_and_gap(
        code, ghost_rank_times, ghost_field, fallback_pos=real_pos
    )
    ghost_compound = [
        str((ticks.get(lap) or {}).get("ghost_compound") or (ticks.get(lap) or {}).get("ghost_tyre") or start_compound)
        for lap in real_laps
    ]
    if not any(ghost_compound):
        ghost_compound = _compound_by_lap(real_laps, start_compound, plan.pit_laps, plan.pit_compounds)

    # Keep field-rank positions, but stamp them onto ticks so map/tower match debrief.
    for i, lap_no in enumerate(real_laps):
        tick = ticks.get(int(lap_no))
        if not isinstance(tick, dict):
            continue
        tick = dict(tick)
        tick["ghost_position"] = ghost_pos[i] if i < len(ghost_pos) else tick.get("ghost_position")
        tick["typical_lap_s"] = typical
        if tick.get("delta_history"):
            tick["delta_history"][-1]["ghost_pos"] = tick["ghost_position"]
        ticks[int(lap_no)] = tick

    top = rec_result.recommendations[0] if rec_result.recommendations else None
    explanation = ""
    if top is not None:
        explanation = narrate_recommendation(top, use_llm=False)

    _log.info(
        "ghost plan %s %s: decision_lap=%s start=%s pits=%s compounds=%s",
        data.session_id,
        code,
        decision_lap,
        start_compound,
        plan.pit_laps,
        plan.pit_compounds,
    )
    _log.debug(
        "ghost_vs_real driver=%s real_pits=%s ghost_pits=%s L1 real_pos=%s ghost_pos=%s",
        code,
        real_pits,
        list(plan.pit_laps),
        real_pos[0] if real_pos else None,
        ghost_pos[0] if ghost_pos else None,
    )

    return {
        "session_id": data.session_id,
        "driver": code,
        "circuit": data.circuit,
        "ghost": {
            "laps": list(real_laps),
            "position": ghost_pos,
            "gap_to_leader": [round(v, 3) for v in ghost_gap],
            "compound": ghost_compound[:n],
            "pit_laps": list(plan.pit_laps),
            "remaining_s": _remaining(ghost_times),
        },
        "real": {
            "laps": list(real_laps),
            "position": real_pos,
            "gap_to_leader": [round(v, 3) for v in real_gap],
            "compound": real_compound[:n],
            "pit_laps": real_pits,
            "remaining_s": _remaining(real_times),
        },
        "delta": {
            "laps": list(real_laps),
            "position_delta": [g - r for g, r in zip(ghost_pos, real_pos)],
            "gap_delta": [round(g - r, 3) for g, r in zip(ghost_gap, real_gap)],
        },
        "aris_action": plan.aris_action or (top.label if top is not None else "Stay out"),
        "explanation": explanation,
        "ticks": ticks,
        "plan": {
            "decision_lap": decision_lap,
            "start_compound": start_compound,
            "pit_laps": list(plan.pit_laps),
            "pit_compounds": list(plan.pit_compounds),
        },
    }


def _prerace_recommend(
    data: ExplainBundle, code: str, focus: pd.DataFrame
) -> tuple[RaceState, Any, dict | None, int]:
    last_state: RaceState | None = None
    last_result = None
    for decision_lap in _PRERACE_LAPS:
        if decision_lap > max(1, int(data.total_laps)):
            continue
        state = _state_from_laps(data, code, focus, decision_lap=decision_lap)
        rec_result = recommend(state, top_k=3, mc_draws=0)
        card = pick_strategy_recommendation(rec_result)
        last_state, last_result = state, rec_result
        if card and str(card.get("label") or "") != "STRATEGY_RESET":
            return state, rec_result, card, decision_lap
    state = last_state or _state_from_laps(data, code, focus, decision_lap=1)
    rec_result = last_result or recommend(state, top_k=3, mc_draws=0)
    return state, rec_result, pick_strategy_recommendation(rec_result), 1


def _lap_rows_from_focus(focus: pd.DataFrame, real_pits: list[int]) -> list[dict]:
    pit_set = {int(x) for x in real_pits}
    rows: list[dict] = []
    ordered = focus.sort_values("LapNumber")
    lag1 = None
    lag2 = None
    recent: list[float] = []
    for rec in ordered.itertuples(index=False):
        lap_no = int(getattr(rec, "LapNumber"))
        lap_s = _lap_s(rec)
        compound = normalize_compound(str(getattr(rec, "Compound", None) or "MEDIUM"))
        try:
            tyre_life = int(getattr(rec, "TyreLife"))
        except (TypeError, ValueError):
            tyre_life = 1
        pos = getattr(rec, "Position", None)
        try:
            position = int(pos) if pos is not None and not pd.isna(pos) else 1
        except (TypeError, ValueError):
            position = 1
        status = str(getattr(rec, "TrackStatus", None) or "1")
        rows.append(
            {
                "lap_number": lap_no,
                "compound": compound,
                "tyre_life": max(1, tyre_life),
                "real_action": f"PIT_NOW_{compound}" if lap_no in pit_set else "STAY_OUT",
                "position": position,
                "track_status": status,
                "lag1_pace": lag1,
                "lag2_pace": lag2,
                "stint_roll3": (sum(recent[-3:]) / min(3, len(recent))) if recent else None,
            }
        )
        if lap_s is not None:
            lag2 = lag1
            lag1 = lap_s
            recent.append(lap_s)
    return rows


def _series_for_driver(
    focus: pd.DataFrame,
) -> tuple[list[float], list[str], list[int | None], list[int]]:
    times: list[float] = []
    compounds: list[str] = []
    positions: list[int | None] = []
    laps: list[int] = []
    ordered = focus.sort_values("LapNumber")
    for rec in ordered.itertuples(index=False):
        lap_no = int(getattr(rec, "LapNumber"))
        lap_s = _lap_s(rec)
        if lap_s is None:
            continue
        laps.append(lap_no)
        times.append(lap_s)
        compounds.append(normalize_compound(str(getattr(rec, "Compound", None) or "MEDIUM")))
        pos = getattr(rec, "Position", None)
        try:
            positions.append(int(pos) if pos is not None and not pd.isna(pos) else None)
        except (TypeError, ValueError):
            positions.append(None)
    return times, compounds, positions, laps


def _field_lap_times(laps: pd.DataFrame) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    if laps.empty:
        return out
    for rec in laps.itertuples(index=False):
        code = str(getattr(rec, "Driver", "")).upper()
        if not code:
            continue
        lap_no = int(getattr(rec, "LapNumber"))
        lap_s = _lap_s(rec)
        if lap_s is None:
            continue
        out.setdefault(code, {})[lap_no] = lap_s
    return out


def _aligned_times(lap_map: dict[int, float], laps: list[int]) -> list[float]:
    out: list[float] = []
    last = 90.0
    for lap in laps:
        if lap in lap_map:
            last = float(lap_map[lap])
        out.append(last)
    return out


def _cumulative(times: list[float]) -> list[float]:
    acc_list: list[float] = []
    total = 0.0
    for t in times:
        total += float(t)
        acc_list.append(total)
    return acc_list


def _rank_and_gap(
    focus: str,
    focus_cum: list[float],
    field_cum: dict[str, list[float]],
    *,
    fallback_pos: list[int | None],
) -> tuple[list[int], list[float]]:
    n = len(focus_cum)
    positions: list[int] = []
    gaps: list[float] = []
    for i in range(n):
        scores: list[tuple[float, str]] = []
        for code, cum in field_cum.items():
            if i >= len(cum):
                continue
            scores.append((float(cum[i]), str(code).upper()))
        if not scores:
            pos = fallback_pos[i] if i < len(fallback_pos) and fallback_pos[i] else 1
            positions.append(int(pos))
            gaps.append(0.0)
            continue
        scores.sort(key=lambda kv: kv[0])
        leader = scores[0][0]
        rank = next((j + 1 for j, (_t, c) in enumerate(scores) if c == focus), 1)
        positions.append(rank)
        gaps.append(max(0.0, float(focus_cum[i]) - leader))
    return positions, gaps


def _compound_by_lap(
    laps: list[int],
    start_compound: str,
    pit_laps: list[int],
    pit_compounds: list[str],
) -> list[str]:
    current = start_compound
    pit_map = dict(zip(pit_laps, pit_compounds, strict=False))
    out: list[str] = []
    for lap in laps:
        if lap in pit_map:
            current = normalize_compound(pit_map[lap])
        out.append(current)
    return out


def _pit_laps(focus: pd.DataFrame) -> list[int]:
    if "PitInTime" not in focus.columns:
        return []
    pits: list[int] = []
    for rec in focus.sort_values("LapNumber").itertuples(index=False):
        val = getattr(rec, "PitInTime", None)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        if pd.isna(val):
            continue
        pits.append(int(getattr(rec, "LapNumber")))
    return pits


def _remaining(times: list[float]) -> list[float]:
    total = sum(times)
    out: list[float] = []
    ran = 0.0
    for t in times:
        ran += t
        out.append(round(total - ran + t, 3))
    return out


def _lap_s(rec: Any) -> float | None:
    raw = getattr(rec, "LapTimeS", None)
    if raw is not None and not (isinstance(raw, float) and np.isnan(raw)):
        try:
            v = float(raw)
            return v if np.isfinite(v) else None
        except (TypeError, ValueError):
            pass
    lt = getattr(rec, "LapTime", None)
    if lt is not None and hasattr(lt, "total_seconds"):
        try:
            v = float(lt.total_seconds())
            return v if np.isfinite(v) else None
        except (TypeError, ValueError):
            return None
    return None


def _state_from_laps(
    data: ExplainBundle,
    driver: str,
    focus: pd.DataFrame,
    *,
    decision_lap: int,
) -> RaceState:
    ordered = focus.sort_values("LapNumber")
    prior = ordered[ordered["LapNumber"] < decision_lap]
    row = prior.iloc[-1] if not prior.empty else ordered.iloc[0]
    compound = normalize_compound(str(row.get("Compound") or "MEDIUM"))
    try:
        tyre_life = int(row["TyreLife"]) if pd.notna(row.get("TyreLife")) else 1
    except (TypeError, ValueError):
        tyre_life = 1
    times = [
        _lap_s(r)
        for r in prior.itertuples(index=False)
    ]
    times = [t for t in times if t is not None]
    lag1 = times[-1] if times else 74.0
    lag2 = times[-2] if len(times) >= 2 else lag1
    roll3 = sum(times[-3:]) / min(3, len(times)) if times else lag1
    pos = None
    if "Position" in row.index and pd.notna(row.get("Position")):
        try:
            pos = int(row["Position"])
        except (TypeError, ValueError):
            pos = None
    return RaceState(
        session_id=0,
        driver_id=0,
        driver_code=driver,
        driver_name=driver,
        year=data.year,
        round_no=data.round_number,
        country=data.circuit or "Netherlands",
        lap_number=int(decision_lap),
        compound=compound,
        tyre_life=max(1, tyre_life),
        fuel_kg=estimate_fuel_kg(decision_lap, total_laps=data.total_laps),
        laps_remaining=max(0, data.total_laps - decision_lap),
        total_laps=data.total_laps,
        track_name=data.circuit or "Netherlands",
        position=pos or 1,
        gap_to_leader_s=0.0 if (pos or 1) == 1 else 2.0,
        pit_compound="HARD",
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
        track_status=str(row.get("TrackStatus") or "1"),
    )


def _empty_ghost(data: ExplainBundle, driver: str) -> dict[str, Any]:
    empty_series = {
        "laps": [],
        "position": [],
        "gap_to_leader": [],
        "compound": [],
        "pit_laps": [],
        "remaining_s": [],
    }
    return {
        "session_id": data.session_id,
        "driver": driver,
        "circuit": data.circuit,
        "ghost": dict(empty_series),
        "real": dict(empty_series),
        "delta": {"laps": [], "position_delta": [], "gap_delta": []},
        "aris_action": "",
        "explanation": "",
        "ticks": {},
        "plan": {
            "decision_lap": 1,
            "start_compound": "",
            "pit_laps": [],
            "pit_compounds": [],
        },
    }
