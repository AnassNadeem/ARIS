"""Race debrief: strategy timeline + key decisions from recommend() + narrate()."""

from __future__ import annotations

import io
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
from aris.models.features import estimate_fuel_kg
from aris.narrate import narrate_recommendation
from aris.physics.stint import detect_stints
from aris.physics.tires import normalize_compound
from aris.recommend import recommend
from aris.state import RaceState, track_status_is_sc_vsc

_SC_CODES = ("4",)
_VSC_CODES = ("6", "7")


def get_race_debrief(
    session_id: str,
    focus_driver: str | None = None,
    *,
    year: int | None = None,
    round_number: int | None = None,
    session_type: str | None = None,
    bundle: ExplainBundle | None = None,
) -> dict[str, Any]:
    """Timeline (pits, SC/VSC, rain) plus recommend() top-3 at each inflection."""
    data = bundle or load_explain_bundle(
        session_id or DEFAULT_SESSION_ID,
        year=year,
        round_number=round_number,
        session_type=session_type,
    )
    code = str(focus_driver or "VER").upper()
    laps = detect_stints_inplace(data.laps.copy()) if not data.laps.empty else data.laps
    focus = driver_laps(laps, code)

    pit_stops = _pit_stops(laps, code)
    sc_vsc = _sc_vsc_periods(laps, data.messages)
    rain = _rain_periods(data.weather, data.total_laps)
    decisions = _decisions(data, focus, code, pit_stops)

    return {
        "timeline": {
            "pit_stops": pit_stops,
            "sc_vsc_periods": sc_vsc,
            "rain_periods": rain,
        },
        "decisions": decisions,
        "metadata": {
            "circuit": data.circuit,
            "season": data.year,
            "round_number": data.round_number,
            "total_laps": data.total_laps,
            "session_id": data.session_id,
            "focus_driver": code,
            "session_type": data.session_type,
        },
    }


def debrief_to_parquet_bytes(payload: dict[str, Any]) -> tuple[bytes, str, str]:
    """Flatten debrief decisions to parquet (CSV fallback if pyarrow is missing)."""
    rows = []
    meta = payload.get("metadata") or {}
    for d in payload.get("decisions") or []:
        top = (d.get("recommend_top3") or [{}])[0]
        rows.append(
            {
                "circuit": meta.get("circuit"),
                "season": meta.get("season"),
                "round_number": meta.get("round_number"),
                "focus_driver": meta.get("focus_driver"),
                "lap": d.get("lap"),
                "type": d.get("type"),
                "chosen_action": d.get("chosen_action"),
                "explanation": d.get("explanation"),
                "top1_label": top.get("label"),
                "top1_delta_s": top.get("delta_vs_stay_out_s"),
            }
        )
    if not rows:
        rows.append(
            {
                "circuit": meta.get("circuit"),
                "season": meta.get("season"),
                "round_number": meta.get("round_number"),
                "focus_driver": meta.get("focus_driver"),
                "lap": None,
                "type": "none",
                "chosen_action": None,
                "explanation": None,
                "top1_label": None,
                "top1_delta_s": None,
            }
        )
    frame = pd.DataFrame(rows)
    buf = io.BytesIO()
    try:
        frame.to_parquet(buf, index=False)
        return buf.getvalue(), "application/octet-stream", "debrief.parquet"
    except Exception:
        text = frame.to_csv(index=False)
        return text.encode("utf-8"), "text/csv", "debrief.csv"


def _pit_stops(laps: pd.DataFrame, focus: str) -> list[dict[str, Any]]:
    if laps.empty:
        return []
    work = laps
    if "StintId" not in work.columns and "Stint" not in work.columns:
        try:
            work = detect_stints(work)
        except Exception:
            work = laps
    col = "StintId" if "StintId" in work.columns else ("Stint" if "Stint" in work.columns else None)
    stops: list[dict[str, Any]] = []
    grouped = work[work["Driver"].astype(str).str.upper() == focus] if "Driver" in work.columns else work
    if col is None or grouped.empty:
        return _pits_from_pitin(grouped if not grouped.empty else work, focus)
    blocks = list(grouped.groupby(col, sort=True))
    for i, (_sid, grp) in enumerate(blocks):
        grp = grp.sort_values("LapNumber")
        if i == 0:
            continue
        prev = blocks[i - 1][1].sort_values("LapNumber")
        in_lap = int(prev["LapNumber"].max())
        out_comp = normalize_compound(_first(grp, "Compound"))
        in_comp = normalize_compound(_first(prev, "Compound"))
        stops.append(
            {
                "lap": in_lap,
                "driver": focus,
                "compound_in": in_comp,
                "compound_out": out_comp,
                "stint_length": int(len(prev)),
            }
        )
    if stops:
        return stops
    return _pits_from_pitin(grouped, focus)


def _pits_from_pitin(focus: pd.DataFrame, driver: str) -> list[dict[str, Any]]:
    if focus.empty or "PitInTime" not in focus.columns:
        return []
    ordered = focus.sort_values("LapNumber")
    stops: list[dict[str, Any]] = []
    rows = list(ordered.itertuples(index=False))
    for i, rec in enumerate(rows):
        val = getattr(rec, "PitInTime", None)
        if val is None or (isinstance(val, float) and np.isnan(val)) or pd.isna(val):
            continue
        in_comp = normalize_compound(str(getattr(rec, "Compound", None) or "MEDIUM"))
        out_comp = in_comp
        if i + 1 < len(rows):
            out_comp = normalize_compound(str(getattr(rows[i + 1], "Compound", None) or in_comp))
        stops.append(
            {
                "lap": int(getattr(rec, "LapNumber")),
                "driver": driver,
                "compound_in": in_comp,
                "compound_out": out_comp,
                "stint_length": None,
            }
        )
    return stops


def _sc_vsc_periods(laps: pd.DataFrame, messages: pd.DataFrame | None = None) -> list[dict[str, Any]]:
    if laps.empty or "TrackStatus" not in laps.columns or "LapNumber" not in laps.columns:
        return _periods_from_messages(messages)
    by_lap: dict[int, str] = {}
    for rec in laps.itertuples(index=False):
        lap = int(getattr(rec, "LapNumber"))
        status = str(getattr(rec, "TrackStatus", None) or "1")
        prev = by_lap.get(lap, "1")
        by_lap[lap] = _worse_status(prev, status)
    periods: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for lap in sorted(by_lap):
        kind = _status_kind(by_lap[lap])
        if kind is None:
            if current:
                current["end_lap"] = lap - 1
                periods.append(current)
                current = None
            continue
        if current and current["kind"] == kind:
            current["end_lap"] = lap
            continue
        if current:
            periods.append(current)
        current = {"kind": kind, "start_lap": lap, "end_lap": lap}
    if current:
        periods.append(current)
    if periods:
        return periods
    return _periods_from_messages(messages)


def _periods_from_messages(messages: pd.DataFrame | None) -> list[dict[str, Any]]:
    if messages is None or messages.empty:
        return []
    periods: list[dict[str, Any]] = []
    for rec in messages.itertuples(index=False):
        blob = " ".join(
            str(x or "")
            for x in (
                getattr(rec, "Flag", None),
                getattr(rec, "Category", None),
                getattr(rec, "Message", None),
            )
        ).upper()
        lap = getattr(rec, "Lap", None)
        try:
            lap_n = int(lap) if lap is not None and not pd.isna(lap) else None
        except (TypeError, ValueError):
            lap_n = None
        if lap_n is None:
            continue
        kind = None
        if "VSC" in blob or "VIRTUAL SAFETY" in blob:
            kind = "VSC"
        elif "SAFETY CAR" in blob or blob.split()[:1] == ["SC"] or " SC " in f" {blob} ":
            kind = "SC"
        if kind:
            periods.append({"kind": kind, "start_lap": lap_n, "end_lap": lap_n})
    return periods


def _rain_periods(weather: pd.DataFrame | None, total_laps: int) -> list[dict[str, Any]]:
    if weather is None or weather.empty:
        return []
    col = "Rainfall" if "Rainfall" in weather.columns else None
    if col is None:
        return []
    n = len(weather)
    raining: list[int] = []
    for i, val in enumerate(weather[col].tolist()):
        if val is None or (isinstance(val, float) and np.isnan(val)):
            continue
        if bool(val):
            lap = int(i / max(n, 1) * max(total_laps, 1)) + 1
            raining.append(min(max(lap, 1), max(total_laps, 1)))
    return _collapse_laps(raining, kind="RAIN")


def _collapse_laps(laps: list[int], *, kind: str) -> list[dict[str, Any]]:
    if not laps:
        return []
    ordered = sorted(set(laps))
    out: list[dict[str, Any]] = []
    start = prev = ordered[0]
    for lap in ordered[1:]:
        if lap == prev + 1:
            prev = lap
            continue
        out.append({"kind": kind, "start_lap": start, "end_lap": prev})
        start = prev = lap
    out.append({"kind": kind, "start_lap": start, "end_lap": prev})
    return out


def _decisions(
    data: ExplainBundle,
    focus: pd.DataFrame,
    driver: str,
    pit_stops: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if focus.empty:
        return []
    inflections: list[tuple[int, str, str]] = []
    for stop in pit_stops:
        lap = int(stop["lap"])
        chosen = f"PIT_NOW_{stop.get('compound_out') or 'HARD'}"
        inflections.append((max(1, lap), "pit", chosen))
    if not inflections:
        mid = min(25, max(1, data.total_laps // 3))
        inflections.append((mid, "stay", "STAY_OUT"))

    decisions: list[dict[str, Any]] = []
    for lap, kind, chosen in inflections:
        state = _state_at_lap(data, driver, focus, lap)
        rec_result = recommend(state, top_k=3, mc_draws=0)
        top3 = [_rec_row(r) for r in rec_result.recommendations[:3]]
        explanation = ""
        if rec_result.recommendations:
            explanation = narrate_recommendation(rec_result.recommendations[0], use_llm=False)
        aris_action = top3[0]["label"] if top3 else "Stay out"
        decisions.append(
            {
                "lap": lap,
                "type": kind,
                "recommend_top3": top3,
                "chosen_action": chosen,
                "aris_action": aris_action,
                "explanation": explanation,
            }
        )
    return decisions


def _rec_row(rec: Any) -> dict[str, Any]:
    ctx = getattr(rec, "narration_context", None) or {}
    p_best = ctx.get("p_best") if isinstance(ctx, dict) else None
    return {
        "rank": int(rec.rank),
        "label": str(rec.label),
        "delta_vs_stay_out_s": float(rec.delta_vs_stay_out_s),
        "p_best": p_best,
        "p10_delta_s": float(rec.p10_delta_s) if rec.p10_delta_s is not None else None,
        "p90_delta_s": float(rec.p90_delta_s) if rec.p90_delta_s is not None else None,
        "kind": str(rec.action.kind) if rec.action is not None else None,
    }


def _state_at_lap(
    data: ExplainBundle,
    driver: str,
    focus: pd.DataFrame,
    lap: int,
) -> RaceState:
    ordered = focus.sort_values("LapNumber")
    prior = ordered[ordered["LapNumber"] <= lap]
    row = prior.iloc[-1] if not prior.empty else ordered.iloc[0]
    compound = normalize_compound(str(row.get("Compound") or "MEDIUM"))
    try:
        tyre_life = int(row["TyreLife"]) if pd.notna(row.get("TyreLife")) else 1
    except (TypeError, ValueError):
        tyre_life = 1
    times = []
    for rec in prior.itertuples(index=False):
        raw = getattr(rec, "LapTimeS", None)
        if raw is None or (isinstance(raw, float) and np.isnan(raw)):
            continue
        times.append(float(raw))
    lag1 = times[-1] if times else 74.0
    lag2 = times[-2] if len(times) >= 2 else lag1
    roll3 = sum(times[-3:]) / min(3, len(times)) if times else lag1
    return RaceState(
        session_id=0,
        driver_id=0,
        driver_code=driver,
        driver_name=driver,
        year=data.year,
        round_no=data.round_number,
        country=data.circuit or "Netherlands",
        lap_number=int(lap),
        compound=compound,
        tyre_life=max(1, tyre_life),
        fuel_kg=estimate_fuel_kg(lap, total_laps=data.total_laps),
        laps_remaining=max(0, data.total_laps - lap),
        total_laps=data.total_laps,
        track_name=data.circuit or "Netherlands",
        position=1,
        pit_compound="HARD",
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
        track_status=str(row.get("TrackStatus") or "1"),
    )


def _first(frame: pd.DataFrame, col: str) -> str:
    if col not in frame.columns or frame.empty:
        return "MEDIUM"
    val = frame[col].dropna()
    if val.empty:
        return "MEDIUM"
    return str(val.iloc[0])


def _worse_status(a: str, b: str) -> str:
    if track_status_is_sc_vsc(b):
        return b
    if track_status_is_sc_vsc(a):
        return a
    return b or a or "1"


def _status_kind(status: str) -> str | None:
    s = str(status or "")
    if any(c in s for c in _SC_CODES):
        return "SC"
    if any(c in s for c in _VSC_CODES):
        return "VSC"
    if track_status_is_sc_vsc(s):
        return "SC"
    return None
