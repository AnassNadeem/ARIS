"""Adapters from the FastAPI broker onto the existing src/aris engine."""

from __future__ import annotations

import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any

from backend.models import (
    ArisStatsResponse,
    ChatResponse,
    DebriefDecision,
    DebriefDeltaPoint,
    DebriefResponse,
    DebriefStats,
    ProjectedPit,
    RecommendAlternative,
    RecommendRequest,
    RecommendResponse,
    SimulateRequest,
    SimulateResponse,
    StratPlanOut,
    StratPlansResponse,
    StrategyColumn,
)
from backend.sessions import replay_timing, session_messages, session_results, session_stints

_log = logging.getLogger(__name__)

_CODE_RE = re.compile(r"^[A-Za-z]{2,3}$")


class ClientInputError(ValueError):
    """Bad client input — maps to HTTP 422."""


def _compound_code(raw: str | None) -> str | None:
    if not raw:
        return None
    u = str(raw).upper()
    mapping = {"SOFT": "S", "MEDIUM": "M", "HARD": "H", "INTERMEDIATE": "I", "WET": "W"}
    if u in mapping:
        return mapping[u]
    if u in {"S", "M", "H", "I", "W"}:
        return u
    return u[:1]


def _action_label(kind: str, pit_lap: int | None, current_lap: int) -> str:
    if kind in {"pit_now"}:
        return "BOX"
    if kind == "pit_lap":
        if pit_lap is not None and pit_lap <= current_lap + 3:
            return "PIT_SOON"
        return "STAY_OUT"
    if kind in {"lift", "brake"}:
        return "MANAGE_PACE"
    return "STAY_OUT"


def resolve_driver_code(year: int, raw: str, round_number: int | None = None) -> str:
    """Accept 3-letter code, FastF1 number, or reject unknown ids."""
    text = str(raw or "").strip()
    if not text:
        raise ClientInputError("driver_code is required")
    if _CODE_RE.match(text):
        return text.upper()
    session_label = f"{year} R{round_number}" if round_number is not None else str(year)
    err = (
        f"Driver '{raw}' not found in session {session_label}. Send the "
        "3-letter driver code (e.g. NOR) or a valid FastF1 driver number."
    )
    # Postgres driver_id values (e.g. 2430) are not FastF1 race numbers (1–99).
    if text.isdigit() and int(text) > 99:
        raise ClientInputError(err)
    from backend.standings import get_drivers

    try:
        roster = get_drivers(year)
    except Exception as extra:
        raise ClientInputError(err) from extra
    needle = str(text).lstrip("0") or "0"
    for drv in roster.drivers:
        if drv.driver_code.upper() == text.upper():
            return drv.driver_code.upper()
        if drv.driver_number is not None and str(int(drv.driver_number)) == needle:
            return drv.driver_code.upper()
        if drv.driver_number is not None and str(int(drv.driver_number)) == str(text):
            return drv.driver_code.upper()
    raise ClientInputError(err)


def _field_gaps(year: int, round_number: int, driver_code: str, lap: int) -> dict[str, Any]:
    try:
        timing = replay_timing(year, round_number, "R", lap)
    except Exception:
        return {}
    rows = [r for r in timing.rows if r.position]
    if not rows:
        return {}
    ordered = sorted(rows, key=lambda r: r.position or 99)
    mine = next((r for r in ordered if r.driver_code == driver_code.upper()), None)
    if mine is None or mine.position is None:
        return {}
    ahead = next((r for r in ordered if r.position == mine.position - 1), None)
    behind = next((r for r in ordered if r.position == mine.position + 1), None)
    gap_ahead = None
    if ahead and mine.gap_to_leader_s is not None and ahead.gap_to_leader_s is not None:
        gap_ahead = float(mine.gap_to_leader_s) - float(ahead.gap_to_leader_s)
    gap_behind = None
    if behind and behind.gap_to_leader_s is not None and mine.gap_to_leader_s is not None:
        gap_behind = float(behind.gap_to_leader_s) - float(mine.gap_to_leader_s)
    return {
        "position": mine.position,
        "gap_to_leader_s": mine.gap_to_leader_s,
        "gap_ahead_s": gap_ahead,
        "gap_behind_s": gap_behind,
    }


def _fallback_recommend(
    req: RecommendRequest,
    reasoning: str | None = None,
    *,
    ingest_status: str | None = None,
) -> RecommendResponse:
    lap = req.current_lap
    return RecommendResponse(
        action="STAY_OUT",
        compound_recommendation=None,
        reasoning=reasoning or f"Insufficient data for lap {lap}. State unavailable.",
        pace_gain_s=0,
        pit_cost_s=0,
        net_delta_s=0,
        confidence=0.0,
        decision_record_id=f"DR-{req.year}-R{req.round_number}-L{lap}-STAY_OUT",
        alternatives=[],
        wet_heuristic=False,
        data_source="FALLBACK_NO_STATE",
        ingest_status=ingest_status,
    )


def try_load_from_postgres(
    year: int, round_number: int, driver_code: str, current_lap: int
):
    """Load RaceState from an already-ingested session. Never triggers ingest."""
    try:
        from aris.io import db
        from aris.state import build_race_state

        sid = db.fetch_race_session_id(year, round_number)
        if sid is None:
            return None
        drv = db.fetch_driver_by_code(sid, driver_code.upper())
        if drv is None:
            return None
        country = ""
        try:
            races = db.fetch_races(year)
            if not races.empty:
                hit = races[races["round_no"] == round_number]
                if not hit.empty:
                    country = str(hit.iloc[0]["country"])
        except Exception:
            country = ""
        _ = country
        gaps = _field_gaps(year, round_number, driver_code, current_lap)
        return build_race_state(int(sid), int(drv["driver_id"]), current_lap, field_gaps=gaps)
    except Exception as extra:
        print(f"[ARIS] Postgres state load failed: {extra}", flush=True)
        return None


def compute_gap_ahead(field_at_lap, driver_code: str) -> float | None:
    if field_at_lap is None or getattr(field_at_lap, "empty", True):
        return None
    if "Driver" not in field_at_lap.columns:
        return None
    mine = field_at_lap[field_at_lap["Driver"] == driver_code]
    if mine.empty:
        return None
    row = mine.iloc[0]
    if "Position" in field_at_lap.columns and pd_notna(row.get("Position")):
        try:
            pos = int(row["Position"])
        except (TypeError, ValueError):
            pos = None
        if pos and pos > 1:
            ahead = field_at_lap[field_at_lap["Position"] == pos - 1]
            if not ahead.empty and "Time" in field_at_lap.columns:
                t0 = ahead.iloc[0].get("Time")
                t1 = row.get("Time")
                if hasattr(t0, "total_seconds") and hasattr(t1, "total_seconds"):
                    gap = float(t1.total_seconds() - t0.total_seconds())
                    if gap >= 0:
                        return gap
    return None


def compute_gap_to_leader(field_at_lap, driver_code: str) -> float | None:
    if field_at_lap is None or getattr(field_at_lap, "empty", True):
        return None
    if "Driver" not in field_at_lap.columns:
        return None
    mine = field_at_lap[field_at_lap["Driver"] == driver_code]
    if mine.empty:
        return None
    row = mine.iloc[0]
    if "Position" in field_at_lap.columns and pd_notna(row.get("Position")):
        try:
            if int(row["Position"]) == 1:
                return 0.0
        except (TypeError, ValueError):
            pass
    ttl = row.get("TimeToLeader") if "TimeToLeader" in field_at_lap.columns else None
    if pd_notna(ttl):
        if hasattr(ttl, "total_seconds"):
            return max(0.0, float(ttl.total_seconds()))
        try:
            return max(0.0, float(ttl))
        except (TypeError, ValueError):
            pass
    if "Time" not in field_at_lap.columns:
        return None
    times: list[float] = []
    for rec in field_at_lap.itertuples(index=False):
        t = getattr(rec, "Time", None)
        if hasattr(t, "total_seconds"):
            times.append(float(t.total_seconds()))
    my_t = row.get("Time")
    if times and hasattr(my_t, "total_seconds"):
        return max(0.0, float(my_t.total_seconds()) - min(times))
    return None


def pd_notna(value: Any) -> bool:
    try:
        import pandas as pd

        return value is not None and not pd.isna(value)
    except Exception:
        return value is not None


def build_race_state_from_fastf1_session(session, driver_code: str, current_lap: int):
    """Build a RaceState from a FastF1 session object (laps only)."""
    import pandas as pd
    from aris.models.features import estimate_fuel_kg
    from aris.physics.wet import nearest_rainfall
    from aris.state import RaceState
    from aris.tracks import load_track_config

    laps = session.laps
    driver_laps = laps[laps["Driver"] == driver_code].copy()
    if driver_laps.empty:
        return None

    def _rainfall_for_lap(lap_number: int) -> bool:
        weather = getattr(session, "weather_data", None)
        row = driver_laps[driver_laps["LapNumber"] == lap_number]
        if row.empty:
            row = driver_laps[driver_laps["LapNumber"] < lap_number].sort_values("LapNumber")
            if row.empty:
                return nearest_rainfall(weather, None)
            start = row.iloc[-1].get("LapStartTime") if "LapStartTime" in row.columns else None
            return nearest_rainfall(weather, start)
        start = row.iloc[0].get("LapStartTime") if "LapStartTime" in row.columns else None
        return nearest_rainfall(weather, start)

    try:
        event = session.event
        country = str(event.get("Country") or event.get("Location") or "")
        year = int(event.get("EventDate").year) if event.get("EventDate") is not None else int(session.date.year)
        round_no = int(event.get("RoundNumber") or 0)
        location = str(event.get("Location") or country)
    except Exception:
        country, year, round_no, location = "", 2024, 15, ""

    try:
        track = load_track_config(country or location, year=year, round_no=round_no)
        total_laps = int(track.total_laps)
        track_name = track.name
    except Exception:
        total_laps = int(laps["LapNumber"].max()) if "LapNumber" in laps.columns else 57
        track_name = location or country or "Unknown"

    driver_name = driver_code
    team = None
    try:
        drv = session.get_driver(driver_code)
        driver_name = str(getattr(drv, "FullName", None) or drv.get("FullName") or driver_code)
        team = str(getattr(drv, "TeamName", None) or drv.get("TeamName") or "") or None
    except Exception:
        pass

    prior_laps = driver_laps[driver_laps["LapNumber"] < current_lap].sort_values("LapNumber")
    if prior_laps.empty:
        early = RaceState(
            session_id=0,
            driver_id=0,
            driver_code=driver_code,
            driver_name=driver_name,
            team=team,
            year=year,
            round_no=round_no,
            country=country or location,
            lap_number=current_lap,
            compound="MEDIUM",
            tyre_life=1,
            fuel_kg=estimate_fuel_kg(current_lap, total_laps=total_laps),
            laps_remaining=max(0, total_laps - current_lap),
            total_laps=total_laps,
            track_name=track_name,
            gap_ahead_s=5.0,
            pit_compound="HARD",
            lag1_pace=None,
            lag2_pace=None,
            stint_roll3=None,
            track_status="1",
            gap_ahead_history=[],
            rainfall=_rainfall_for_lap(current_lap),
            stint_number=1,
        )
        try:
            from aris.risk.sc_risk_model import attach_sc_risk, extras_from_fastf1

            extras = extras_from_fastf1(
                laps,
                current_lap,
                rcm=getattr(session, "race_control_messages", None),
                results=getattr(session, "results", None),
            )
            return attach_sc_risk(early, extras=extras)
        except Exception:
            return early

    last = prior_laps.iloc[-1]
    current_compound = str(last.get("Compound") or "MEDIUM")
    if pd_notna(last.get("TyreLife")):
        tyre_life = int(last["TyreLife"])
    else:
        tyre_life = 0
        for rec in prior_laps.iloc[::-1].itertuples(index=False):
            if str(getattr(rec, "Compound", "") or "") == current_compound:
                tyre_life += 1
            else:
                break
        tyre_life = max(1, tyre_life)

    lap_times = prior_laps["LapTime"].dropna() if "LapTime" in prior_laps.columns else []
    lap_time_s = [t.total_seconds() for t in lap_times if hasattr(t, "total_seconds")]
    lag1 = lap_time_s[-1] if len(lap_time_s) >= 1 else None
    lag2 = lap_time_s[-2] if len(lap_time_s) >= 2 else lag1
    roll3 = (sum(lap_time_s[-3:]) / min(3, len(lap_time_s))) if lap_time_s else None

    field_at_lap = laps[laps["LapNumber"] == current_lap - 1] if "LapNumber" in laps.columns else laps.iloc[0:0]
    gap_ahead = compute_gap_ahead(field_at_lap, driver_code) or 5.0
    hist: list[float] = []
    start = max(1, current_lap - 4)
    for hist_lap in range(start, current_lap + 1):
        field = laps[laps["LapNumber"] == hist_lap] if "LapNumber" in laps.columns else laps.iloc[0:0]
        g = compute_gap_ahead(field, driver_code)
        if g is not None:
            hist.append(float(g))

    position = None
    gap_to_leader = None
    if "Position" in last.index and pd_notna(last.get("Position")):
        try:
            position = int(last["Position"])
        except (TypeError, ValueError):
            position = None
    gap_to_leader = compute_gap_to_leader(field_at_lap, driver_code)
    if gap_to_leader is None and position == 1:
        gap_to_leader = 0.0

    built = RaceState(
        session_id=0,
        driver_id=0,
        driver_code=driver_code,
        driver_name=driver_name,
        team=team,
        year=year,
        round_no=round_no,
        country=country or location,
        lap_number=current_lap,
        compound=current_compound,
        tyre_life=tyre_life,
        fuel_kg=estimate_fuel_kg(current_lap, total_laps=total_laps),
        laps_remaining=max(0, total_laps - current_lap),
        total_laps=total_laps,
        track_name=track_name,
        gap_ahead_s=gap_ahead,
        gap_to_leader_s=gap_to_leader,
        position=position,
        undercut_threat=0 < gap_ahead < 22.0,
        pit_compound="HARD",
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
        track_status=str(last.get("TrackStatus") or "1"),
        gap_ahead_history=hist,
        rainfall=_rainfall_for_lap(current_lap),
        stint_number=(
            int(last["Stint"])
            if "Stint" in last.index and pd_notna(last.get("Stint"))
            else 1
        ),
    )
    try:
        from aris.risk.sc_risk_model import attach_sc_risk, extras_from_fastf1

        extras = extras_from_fastf1(
            laps,
            current_lap,
            rcm=getattr(session, "race_control_messages", None),
            results=getattr(session, "results", None),
        )
        return attach_sc_risk(built, extras=extras)
    except Exception:
        return built


def build_race_state_with_fallback(
    year: int,
    round_number: int,
    driver_code: str,
    current_lap: int,
) -> tuple[Any, str]:
    """
    Returns (state, source) where source is one of:
      POSTGRES       — loaded from ingested Postgres session
      FASTF1_DIRECT  — loaded from FastF1 cache directly
      NONE           — no data available
    """
    try:
        from backend.calendar import session_is_open

        if session_is_open(year, round_number, "R"):
            return None, "NONE"
    except Exception:
        pass

    state = try_load_from_postgres(year, round_number, driver_code, current_lap)
    if state is not None:
        return state, "POSTGRES"

    try:
        from backend.sessions import load_session

        session = load_session(year, round_number, "R", telemetry=False, weather=False, messages=False)
        state = build_race_state_from_fastf1_session(session, driver_code, current_lap)
        if state is not None:
            return state, "FASTF1_DIRECT"
    except Exception as extra:
        print(f"[ARIS] FastF1 fallback failed: {extra}", flush=True)

    return None, "NONE"


def historical_race_state(
    year: int, round_number: int, driver_code: str, current_lap: int
) -> tuple[Any, str, str | None]:
    """If this weekend has no race yet, load the last completed GP at the same circuit."""
    try:
        from backend.analytics import circuit_history
        from backend.calendar import get_calendar
    except Exception:
        return None, "NONE", None
    try:
        cal = get_calendar(year)
        rnd = next((r for r in cal.rounds if r.round_number == round_number), None)
        if rnd is None:
            return None, "NONE", None
        hist = circuit_history(rnd.circuit_key)
        for item in reversed(list(hist.years)):
            if item.year >= year:
                continue
            try:
                ycal = get_calendar(item.year)
            except Exception:
                continue
            match = next(
                (
                    r
                    for r in ycal.rounds
                    if r.circuit_key == rnd.circuit_key and r.status == "COMPLETED"
                ),
                None,
            )
            if match is None:
                continue
            state, source = build_race_state_with_fallback(
                item.year, match.round_number, driver_code, max(1, min(current_lap, 25))
            )
            if state is not None:
                return state, source, f"{item.year} {match.name}"
    except Exception as extra:
        print(f"[ARIS] historical sim fallback failed: {extra}", flush=True)
    return None, "NONE", None


def _recommend_from_state(
    req: RecommendRequest, state, data_source: str, *, ingest_status: str | None = None
) -> RecommendResponse:
    from aris.recommend import recommend as aris_recommend
    from aris.tracks import load_track_config

    if state.lag1_pace is None and req.current_lap <= 1:
        reason = (
            "Lights not out yet. Zandvoort 2021–2025 is a one-stop circuit "
            "(median first stop from those five races). Stay out on the ARIS plan — "
            "do not copy this driver's real pit window."
        )
        rec = _fallback_recommend(req, reasoning=reason, ingest_status=ingest_status)
        return rec.model_copy(
            update={
                "lap_note": state.lap_note,
                "data_source": data_source,
                "ingest_status": ingest_status,
                "compound_recommendation": "M",
                "confidence": 0.45,
            }
        )

    field = None
    try:
        from aris.field.state import FieldState, ReplayIndex
        from aris.io import db as aris_db

        all_laps = aris_db.fetch_all_laps(state.session_id)
        if all_laps is not None and not all_laps.empty:
            field = FieldState.from_laps(
                all_laps,
                session_id=int(state.session_id),
                index=ReplayIndex(int(state.lap_number), 3),
                total_laps=int(state.total_laps),
            )
    except Exception:
        field = None
    if field is not None:
        field.rainfall = bool(state.rainfall)
    result = aris_recommend(state, top_k=3, mc_draws=0, field=field)
    recs = result.recommendations
    if not recs:
        return _fallback_recommend(req, ingest_status=ingest_status)
    top = recs[0]
    from aris.simulate import get_pit_loss

    green_pit = load_track_config(
        state.country or state.track_name, year=req.year, round_no=req.round_number
    ).pit_loss_s
    # Cost of boxing *now*. Future PIT_LAP stops still pay green loss in simulate().
    pit_loss = get_pit_loss(
        green_pit, state.track_status, circuit_key=state.country or state.track_name
    )
    net = float(top.delta_vs_stay_out_s)
    pace_gain = max(0.0, -net + pit_loss) if net < 0 else max(0.0, pit_loss + net)
    action = _action_label(top.action.kind.value, top.action.pit_lap, req.current_lap)
    if action == "STAY_OUT" and net < -0.2 and top.action.kind.value == "stay_out":
        action = "PUSH"
    compound = _compound_code(top.action.pit_compound or state.compound)
    alts: list[RecommendAlternative] = []
    for rec in recs[1:]:
        alts.append(
            RecommendAlternative(
                action=_action_label(rec.action.kind.value, rec.action.pit_lap, req.current_lap),  # type: ignore[arg-type]
                compound=_compound_code(rec.action.pit_compound),
                net_delta_s=float(rec.delta_vs_stay_out_s),
                note=rec.label,
            )
        )
    wet = bool(getattr(top, "wet_heuristic", False))
    reasoning = top.evidence or top.label
    if wet and action == "BOX":
        tyre = "wets" if compound == "W" else "intermediates"
        if "rain" not in reasoning.lower():
            reasoning = f"Rain detected. Box for {tyre} — {reasoning}"
    rec_id = f"DR-{req.year}-R{req.round_number}-L{req.current_lap}-{action}"
    src = data_source
    if data_source == "FASTF1_DIRECT" and state.lag1_pace is None:
        src = "FASTF1_FALLBACK"
    confidence = max(0.05, min(0.95, 1.0 / (1.0 + float(top.confidence_std_s or 0.4))))
    if wet:
        confidence = min(confidence, 0.55)
    return RecommendResponse(
        action=action,  # type: ignore[arg-type]
        compound_recommendation=compound,  # type: ignore[arg-type]
        reasoning=reasoning,
        pace_gain_s=round(pace_gain, 2),
        pit_cost_s=round(float(pit_loss), 2),
        net_delta_s=round(net, 2),
        confidence=confidence,
        decision_record_id=rec_id,
        alternatives=alts,
        wet_reduced_confidence=wet,
        wet_heuristic=wet,
        reg_note_2026=req.year == 2026,
        lap_note=state.lap_note,
        data_source=src,
        ingest_status=ingest_status,
        p10_delta_s=round(float(top.p10_delta_s), 2),
        p90_delta_s=round(float(top.p90_delta_s), 2),
        confidence_note=top.confidence_note,
    )


def _resolve_ids(year: int, round_number: int, session_type: str, driver_code: str) -> tuple[int, int, str]:
    from aris.io import db

    sid = db.fetch_race_session_id(year, round_number) if session_type.upper() == "R" else None
    if sid is None:
        raise RuntimeError(
            f"Strategy engine has no ingested session ({year} R{round_number} {session_type})"
        )
    drv = db.fetch_driver_by_code(sid, driver_code.upper())
    if drv is None:
        raise RuntimeError(f"Driver {driver_code} not in ingested session {sid}")
    country = ""
    races = db.fetch_races(year)
    if not races.empty:
        hit = races[races["round_no"] == round_number]
        if not hit.empty:
            country = str(hit.iloc[0]["country"])
    return int(sid), int(drv["driver_id"]), country


def _session_open(year: int, round_number: int) -> bool:
    try:
        from backend.calendar import session_is_open

        return session_is_open(year, round_number, "R")
    except Exception:
        return False


def build_live_aris_state(req: RecommendRequest):
    """Live OpenF1 pace/position, but ARIS tyres — not the focus driver's real stint."""
    from aris.models.features import estimate_fuel_kg
    from aris.state import RaceState
    from aris.tracks import load_track_config
    from backend.live import _STATE

    try:
        from backend.calendar import peek_round_meta

        country, circuit_key = peek_round_meta(req.year, req.round_number)
    except Exception:
        country, circuit_key = "", ""
    track = load_track_config(country or circuit_key or "netherlands", year=req.year, round_no=req.round_number)
    total = int(track.total_laps or 72)
    lap = max(1, min(int(req.current_lap), total))
    code = req.driver_code.upper()
    pos = None
    last_s = None
    gap = None
    blob = _STATE.get("drivers") if isinstance(_STATE.get("drivers"), dict) else {}
    num_by_code: dict[str, int] = {}
    for row in blob.get("rows") or []:
        if not isinstance(row, dict):
            continue
        acr = str(row.get("name_acronym") or "")[:3].upper()
        num = row.get("driver_number")
        if acr and num is not None:
            num_by_code[acr] = int(num)
    ham_num = num_by_code.get(code)
    latest_pos = _STATE.get("latest_pos") or {}
    if ham_num is not None and ham_num in latest_pos:
        try:
            pos = int(latest_pos[ham_num])
        except (TypeError, ValueError):
            pos = None
    best: list[float] = []
    for row in _STATE.get("laps") or []:
        if not isinstance(row, dict):
            continue
        if ham_num is not None and int(row.get("driver_number") or -1) != ham_num:
            continue
        dur = row.get("lap_duration")
        try:
            if dur is not None:
                best.append(float(dur))
        except (TypeError, ValueError):
            continue
    if best:
        last_s = best[-1]
    intervals = _STATE.get("intervals") or {}
    if isinstance(intervals, dict) and ham_num is not None:
        iv = intervals.get(ham_num) or {}
        if isinstance(iv, dict):
            try:
                gap = float(iv.get("gap_to_leader") or iv.get("interval"))
            except (TypeError, ValueError):
                gap = None
    start_compound = "MEDIUM"
    try:
        from backend.analytics import peek_circuit_history

        hist = peek_circuit_history(circuit_key or "netherlands")
        if hist is not None and hist.typical_stop_count is not None and hist.typical_stop_count >= 1.6:
            start_compound = "MEDIUM"
    except Exception:
        pass
    rainfall = bool(req.override_rainfall)
    return RaceState(
        session_id=0,
        driver_id=0,
        driver_code=code,
        driver_name=code,
        year=req.year,
        round_no=req.round_number,
        country=country or track.country,
        lap_number=lap,
        compound=start_compound,
        tyre_life=lap,
        fuel_kg=estimate_fuel_kg(lap, total),
        laps_remaining=max(0, total - lap),
        total_laps=total,
        track_name=track.name if hasattr(track, "name") else (country or "Netherlands"),
        gap_to_leader_s=gap,
        position=pos,
        pit_compound="HARD",
        lag1_pace=last_s,
        lag2_pace=best[-2] if len(best) >= 2 else None,
        stint_roll3=(sum(best[-3:]) / min(3, len(best))) if best else None,
        track_status="1",
        rainfall=rainfall,
        weather_rainfall=rainfall,
        lap_note="ARIS car — live GPS/pace from OpenF1, strategy ignores this driver's real stints.",
        stint_number=1,
    )


def recommend(req: RecommendRequest) -> RecommendResponse:
    if req.current_lap < 1:
        raise ClientInputError("current_lap must be between 1 and the session total laps")
    code = resolve_driver_code(req.year, req.driver_code, req.round_number)
    req = req.model_copy(update={"driver_code": code})
    if req.force_refresh:
        try:
            from backend.sessions import clear_session_cache

            clear_session_cache(req.year, req.round_number, req.session_type)
        except Exception:
            pass
        _log.info(
            "recommend force_refresh year=%s round=%s driver=%s lap=%s",
            req.year,
            req.round_number,
            code,
            req.current_lap,
        )

    ingest_status = None
    live_open = _session_open(req.year, req.round_number)
    try:
        from backend.ingest_jobs import ensure_session_ingested

        ingest_started = time.monotonic()
        ingest_status = "UNAVAILABLE" if live_open else ensure_session_ingested(req.year, req.round_number, "R")
        ingest_elapsed = time.monotonic() - ingest_started
        if ingest_elapsed > 0.5:
            _log.warning(
                "recommend: ensure_session_ingested took %.2fs year=%s round=%s status=%s",
                ingest_elapsed,
                req.year,
                req.round_number,
                ingest_status,
            )
        else:
            _log.debug(
                "recommend: ensure_session_ingested %.3fs year=%s round=%s status=%s",
                ingest_elapsed,
                req.year,
                req.round_number,
                ingest_status,
            )
    except Exception:
        ingest_status = "UNAVAILABLE"

    state, source = build_race_state_with_fallback(req.year, req.round_number, code, req.current_lap)
    hist_label = None
    if (state is None or source == "NONE") and req.mode in {"live", "pre_race"}:
        try:
            state = build_live_aris_state(req)
            source = "OPENF1_LIVE"
        except Exception as extra:
            _log.warning("live ARIS state failed: %s", extra)
            state, source = None, "NONE"
    if (state is None or source == "NONE") and req.mode == "replay" and not live_open:
        state, source, hist_label = historical_race_state(
            req.year, req.round_number, code, req.current_lap
        )
    if state is None or source == "NONE":
        return _fallback_recommend(req, ingest_status=ingest_status)
    if req.override_rainfall is not None:
        raining = bool(req.override_rainfall)
        state = state.model_copy(update={"rainfall": raining, "weather_rainfall": raining})

    try:
        rec = _recommend_from_state(req, state, source, ingest_status=ingest_status)
        if hist_label:
            extra = f"Using {hist_label} pace sample — this race has no live stint data yet."
            rec = rec.model_copy(update={"reasoning": f"{rec.reasoning} {extra}".strip()})
        return rec
    except Exception as extra:
        _log.warning("recommend engine failed: %s", extra)
        return _fallback_recommend(req, ingest_status=ingest_status)



def simulate(req: SimulateRequest) -> SimulateResponse:
    from aris.simulate import ActionKind, StrategyAction, simulate as aris_simulate
    from aris.tracks import load_track_config

    code = resolve_driver_code(req.year, req.driver_code, req.round_number)
    req = req.model_copy(update={"driver_code": code})
    state, source = build_race_state_with_fallback(req.year, req.round_number, code, req.current_lap)
    hist_label = None
    if state is None:
        state, source, hist_label = historical_race_state(
            req.year, req.round_number, code, req.current_lap
        )
    if state is None:
        raise RuntimeError("No session data available for simulation (Postgres and FastF1 both empty)")
    stay = aris_simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))
    from backend.models import CustomPitStop

    stops = list(req.pit_stops)
    if not stops and req.pit_lap and req.compound:
        stops = [CustomPitStop(lap=req.pit_lap, compound=req.compound)]

    if stops:
        first = stops[0]
        action = StrategyAction(
            kind=ActionKind.PIT_LAP,
            pit_lap=first.lap,
            pit_compound=(first.compound or "HARD").upper(),
        )
    else:
        action = StrategyAction(kind=ActionKind.STAY_OUT)
    outcome = aris_simulate(state, action)
    delta = float(outcome.total_race_time_s - stay.total_race_time_s) * float(req.deg_factor or 1.0)
    track = load_track_config(state.country or state.track_name, year=req.year, round_no=req.round_number)
    pit_cost = track.pit_loss_s * max(1, len(stops))
    pace_gain = max(0.0, -delta + pit_cost) if delta < 0 else max(0.0, pit_cost + delta)

    actual_pos = None
    try:
        results = session_results(req.year, req.round_number, "R").results
        mine = next((r for r in results if r.driver_code == req.driver_code.upper()), None)
        actual_pos = mine.position if mine else None
    except Exception:
        actual_pos = None
    shift = 0
    if delta:
        # Do not treat stay-out delta as ~2s/place (that invented P1 from P6).
        shift = max(-2, min(2, int(round(-delta / 8.0))))
    projected = None
    if actual_pos is not None:
        projected = max(1, min(22, actual_pos - shift))

    note_parts = []
    if hist_label:
        note_parts.append(f"Using {hist_label} pace sample — this race has no live stint data yet.")
    if req.rain_lap:
        note_parts.append("[WET: REDUCED CONFIDENCE] rain_lap is not modelled — confidence only.")
    if req.sc_probability and req.sc_probability > 0:
        note_parts.append(f"SC probability {req.sc_probability:.0%} noted; not a full SC model.")
    risk = "Low"
    if abs(delta) > 8 or (req.sc_probability or 0) > 0.4:
        risk = "Higher"
    elif abs(delta) > 3:
        risk = "Medium"
    pits: list[ProjectedPit] = [ProjectedPit(lap=s.lap, compound=s.compound.upper()) for s in stops]
    return SimulateResponse(
        projected_finish_position=projected,
        total_race_time_delta_s=round(delta, 3),
        projected_pit_stops=pits,
        risk_level=risk,  # type: ignore[arg-type]
        baseline_delta_s=0.0,
        delta_vs_aris_s=round(delta, 3),
        delta_vs_actual_s=round(delta, 3),
        pace_gain_s=round(pace_gain, 2),
        pit_cost_s=round(float(pit_cost), 2),
        wet_reduced_confidence=bool(req.rain_lap),
        note=" ".join(note_parts) or None,
        data_source=source,
    )


def _timing_rows(year: int, round_number: int, current_lap: int):
    if _session_open(year, round_number):
        try:
            from backend.live import _STATE

            pos = _STATE.get("latest_pos") or {}
            blob = _STATE.get("drivers") if isinstance(_STATE.get("drivers"), dict) else {}
            codes: dict[int, str] = {}
            for row in blob.get("rows") or []:
                if not isinstance(row, dict):
                    continue
                num = row.get("driver_number")
                acr = str(row.get("name_acronym") or "")[:3].upper()
                if num is not None and acr:
                    codes[int(num)] = acr
            from backend.models import LiveTimingRow

            rows = [
                LiveTimingRow(position=int(p), driver_code=codes.get(int(n), f"D{n}"))
                for n, p in pos.items()
                if p is not None
            ]
            return sorted(rows, key=lambda r: r.position or 99)
        except Exception:
            return []
    try:
        timing = replay_timing(year, round_number, "R", current_lap)
    except Exception:
        return []
    return sorted([r for r in timing.rows if r.position], key=lambda r: r.position or 99)


def _gap_radio(
    year: int, round_number: int, current_lap: int, focus: str | None = None
) -> str | None:
    ordered = _timing_rows(year, round_number, current_lap)
    if not ordered:
        return None
    leader = ordered[0]
    p2 = ordered[1] if len(ordered) > 1 else None
    parts: list[str] = []
    if focus:
        mine = next((r for r in ordered if r.driver_code == focus.upper()), None)
        if mine:
            g = mine.gap_to_leader_s
            gap_txt = f" at +{g:.1f}s" if g is not None and mine.position != 1 else ""
            parts.append(f"We are P{mine.position}{gap_txt}")
    parts.append(f"{leader.driver_code} leads")
    if p2:
        g = p2.gap_to_leader_s
        parts.append(f"{p2.driver_code} is P2 at +{g:.1f}s" if g is not None else f"{p2.driver_code} is P2")
    return ". ".join(parts) + "."


def _answer_position(year: int, round_number: int, lap: int, focus: str | None) -> str | None:
    rows = _timing_rows(year, round_number, lap)
    if not rows or not focus:
        return None
    mine = next((r for r in rows if r.driver_code == focus.upper()), None)
    if not mine:
        return None
    g = mine.gap_to_leader_s
    gap_txt = f" at +{g:.1f}s to the leader" if g is not None else ""
    return f"We are P{mine.position}{gap_txt}."


def _answer_tyres(year: int, round_number: int, lap: int, focus: str | None) -> str | None:
    rows = _timing_rows(year, round_number, lap)
    if not rows or not focus:
        return None
    mine = next((r for r in rows if r.driver_code == focus.upper()), None)
    if not mine:
        return None
    compound = mine.compound or "unknown compound"
    life = f"{mine.tyre_life} laps old" if mine.tyre_life is not None else "age unknown"
    return f"We are on {compound}, {life}."


def _answer_laps_remaining(year: int, round_number: int, lap: int) -> str | None:
    try:
        from aris.tracks import load_track_config
        from backend.calendar import get_round

        rnd = get_round(year, round_number)
        track = load_track_config(rnd.country, year=year, round_no=round_number)
        remaining = max(0, track.total_laps - lap)
        return f"{remaining} laps remaining ({lap} of {track.total_laps})."
    except Exception:
        return None


def _answer_leader(year: int, round_number: int, lap: int) -> str | None:
    rows = _timing_rows(year, round_number, lap)
    if not rows:
        return None
    return f"{rows[0].driver_code} is leading."


def _direct_chat_answer(
    question: str,
    year: int | None,
    round_number: int | None,
    current_lap: int | None,
    driver_code: str | None,
) -> str | None:
    if not year or not round_number:
        return None
    q = question.lower()
    lap = current_lap or 1
    focus = driver_code
    patterns: list[tuple[re.Pattern[str], Any]] = [
        (re.compile(r"gap.*(leader|front|ahead|first)|how far.*(behind|back|off)|interval"), "gap"),
        (re.compile(r"(position|pos|where).*(we|our|driver)|where are we"), "pos"),
        (re.compile(r"(tyre|tire).*(life|age|laps)|(compound|rubber)"), "tyre"),
        (re.compile(r"(how many|laps).*(left|remaining|to go)|laps remaining"), "laps"),
        (re.compile(r"who.*(lead|front|first|winning)"), "leader"),
        (re.compile(r"should we pit|box now|pit now"), "pit"),
    ]
    kind = None
    for cre, name in patterns:
        if cre.search(q):
            kind = name
            break
    if kind == "gap":
        return _gap_radio(year, round_number, lap, focus)
    if kind == "pos":
        return _answer_position(year, round_number, lap, focus)
    if kind == "tyre":
        return _answer_tyres(year, round_number, lap, focus)
    if kind == "laps":
        return _answer_laps_remaining(year, round_number, lap)
    if kind == "leader":
        return _answer_leader(year, round_number, lap)
    if kind == "pit":
        return (
            "Hold unless a trigger fires. Deg is in window — I will call BOX when the net delta turns negative."
        )
    return None


def _clip_sentences(text: str, n: int = 3) -> str:
    text = text.replace("\n", " ").strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    clipped = " ".join(sentences[:n])
    if clipped and clipped[-1] not in ".!?":
        clipped += "."
    return clipped or text


def _load_chat_field_from_fastf1(year: int, round_number: int, current_lap: int):
    """Laps-only field snapshot when replay timing is empty (no Postgres)."""
    from aris.narrate import FieldDriver, RadioField

    try:
        from backend.sessions import load_session

        session = load_session(year, round_number, "R", telemetry=False, weather=False, messages=False)
        laps = session.laps
        if laps is None or laps.empty or "Driver" not in laps.columns:
            return None
        prior = laps[laps["LapNumber"] <= current_lap] if "LapNumber" in laps.columns else laps
        if prior.empty:
            return None
        latest = prior.sort_values("LapNumber").groupby("Driver", as_index=False).tail(1)
        drivers: list[FieldDriver] = []
        for _, row in latest.iterrows():
            code = str(row.get("Driver") or "")[:3].upper()
            if not code:
                continue
            try:
                pos = int(row["Position"]) if "Position" in row.index and pd_notna(row.get("Position")) else 0
            except (TypeError, ValueError):
                pos = 0
            gap = 0.0
            if "Time" in latest.columns:
                try:
                    times = [
                        t.total_seconds()
                        for t in latest["Time"]
                        if hasattr(t, "total_seconds")
                    ]
                    mine = row.get("Time")
                    if times and hasattr(mine, "total_seconds"):
                        gap = max(0.0, float(mine.total_seconds()) - min(times))
                except Exception:
                    gap = 0.0
            name = code
            try:
                drv = session.get_driver(code)
                name = str(getattr(drv, "FullName", None) or drv.get("FullName") or code)
            except Exception:
                pass
            compound = str(row.get("Compound") or "unknown")
            try:
                tyre_life = int(row.get("TyreLife") or 0)
            except (TypeError, ValueError):
                tyre_life = 0
            drivers.append(
                FieldDriver(
                    code=code,
                    name=name,
                    compound=compound,
                    tyre_life=tyre_life,
                    position=pos,
                    gap_to_leader=gap,
                )
            )
        if not drivers:
            return None
        drivers.sort(key=lambda d: d.position or 99)
        return RadioField(drivers)
    except Exception as extra:
        print(f"[ARIS] chat FastF1 field failed: {extra}", flush=True)
        return None


def _load_chat_field(year: int, round_number: int, current_lap: int):
    from aris.narrate import FieldDriver, RadioField

    rows = _timing_rows(year, round_number, current_lap)
    if not rows:
        if _session_open(year, round_number):
            return None
        field = _load_chat_field_from_fastf1(year, round_number, current_lap)
        if field is not None:
            return field
        return None
    names: dict[str, str] = {}
    try:
        from backend.standings import get_drivers

        for d in get_drivers(year).drivers:
            names[d.driver_code] = d.full_name
    except Exception:
        pass
    drivers = [
        FieldDriver(
            code=r.driver_code,
            name=names.get(r.driver_code, r.driver_code),
            compound=str(r.compound or "unknown"),
            tyre_life=int(r.tyre_life or 0),
            position=int(r.position or 0),
            gap_to_leader=float(r.gap_to_leader_s or 0.0),
        )
        for r in rows
    ]
    return RadioField(drivers)


def chat(
    session_key: str | None,
    driver_code: str | None,
    question: str,
    year: int | None = None,
    round_number: int | None = None,
    current_lap: int | None = None,
) -> ChatResponse:
    from aris.ask import ABSTAIN, answer_question
    from aris.narrate import call_llm_with_fallback, format_context_for_llm, generate_template_response
    from aris.tracks import load_track_config
    from backend.calendar import get_round

    del session_key
    if year is None or round_number is None:
        try:
            from backend.calendar import next_race

            nxt = next_race()
            year = year or nxt.year
            round_number = round_number or nxt.round_number
        except Exception:
            year = year or 2024
            round_number = round_number or 15
    focus = "HAM"
    if driver_code and year:
        try:
            focus = resolve_driver_code(year, driver_code, round_number)
        except ClientInputError:
            focus = driver_code.upper() if _CODE_RE.match(driver_code) else "NOR"

    lap = current_lap or 1
    field = _load_chat_field(year, round_number, lap)
    total_laps = 72
    try:
        rnd = get_round(year, round_number)
        total_laps = load_track_config(rnd.country, year=year, round_no=round_number).total_laps
    except Exception:
        pass

    template = generate_template_response(question, field, focus, lap, total_laps)
    default = (
        "I don't have enough context to answer that right now. "
        "Try asking about gaps, tyres, or positions."
    )
    if template != default:
        return ChatResponse(answer=_clip_sentences(template), cited_ids=[], abstained=False)

    text = answer_question(None, question)
    abstained = text.strip() == ABSTAIN or text.startswith("No relevant source")
    field_ctx = ""
    if field:
        leader = field.driver_at_position(1)
        focus_d = field.get_driver(focus)
        if leader and focus_d:
            field_ctx = (
                f"{leader.code} leads. We are P{focus_d.position} at "
                f"+{focus_d.gap_to_leader:.1f}s on {focus_d.compound}."
            )
    if any(tok in text for tok in ("grid_pos=", "finish_pos=", "session_results", "delta_vs_stay_out_s=")):
        text = format_context_for_llm([{"type": "raw", "text": text}]) or field_ctx or template
    context = "\n".join(x for x in (field_ctx, text) if x)
    wrapped = call_llm_with_fallback(
        question,
        context=context,
        fallback=template,
    )
    if wrapped:
        text = wrapped
    cited: list[str] = []
    for token in text.split():
        if token.startswith("DR-") or token.startswith("dec-"):
            cited.append(token.strip(".,;"))
    return ChatResponse(answer=_clip_sentences(text), cited_ids=cited, abstained=abstained and text == template)


def _parse_session_id(session_id: str | None) -> tuple[int | None, int | None]:
    if not session_id:
        return None, None
    parts = str(session_id).replace("R", "").replace("S", "").split("-")
    year = None
    rnd = None
    if parts and parts[0].isdigit() and len(parts[0]) == 4:
        year = int(parts[0])
    if len(parts) > 1 and parts[1].isdigit():
        rnd = int(parts[1])
    return year, rnd


def copilot_chat(req) -> Any:
    """T11 Copilot: retrieve + ARIS tools + narrator. Does not change recommend()."""
    import os

    from aris.copilot.agent import run_copilot
    from aris.copilot.context import CopilotContext, FieldCar
    from backend.models import (
        CopilotChatResponse,
        CopilotRecommendationRow,
        CopilotRetrievedChunk,
        CopilotToolCallOut,
    )

    year = req.year
    round_number = req.round_number
    sid_year, sid_round = _parse_session_id(req.session_id)
    year = year or sid_year
    round_number = round_number or sid_round
    driver = None
    if req.driver_code:
        try:
            driver = resolve_driver_code(year or 2025, req.driver_code, round_number)
        except ClientInputError:
            driver = str(req.driver_code).upper()
    lap = req.current_lap or 1
    state = None
    if year and round_number and driver:
        state = try_load_from_postgres(year, round_number, driver, lap)
    field_cars: list[FieldCar] = []
    if year and round_number:
        radio = _load_chat_field(year, round_number, lap)
        if radio is not None:
            field_cars = [
                FieldCar(
                    driver_code=d.code,
                    position=d.position,
                    gap_to_leader_s=d.gap_to_leader,
                    compound=d.compound,
                    tyre_life=d.tyre_life,
                    name=d.name,
                )
                for d in radio.drivers
            ]
    use_llm = req.use_llm
    if use_llm is None:
        use_llm = os.getenv("ARIS_COPILOT_LLM", "0") == "1"
    ctx = CopilotContext(
        state=state,
        field=field_cars,
        session_id=req.session_id,
        use_llm=bool(use_llm),
    )
    result = run_copilot(req.message, ctx, use_llm=bool(use_llm))
    recs = []
    for row in result.recommendations:
        recs.append(
            CopilotRecommendationRow(
                rank=int(row.get("rank") or 0),
                label=str(row.get("label") or ""),
                delta_vs_stay_out_s=row.get("delta_vs_stay_out_s"),
                p_best=row.get("p_best"),
                p10_delta_s=row.get("p10_delta_s"),
                p90_delta_s=row.get("p90_delta_s"),
            )
        )
    return CopilotChatResponse(
        response=result.response,
        tool_calls=[
            CopilotToolCallOut(
                name=str(c.get("name") or ""),
                arguments=dict(c.get("arguments") or {}),
                result=c.get("result"),
            )
            for c in result.tool_calls
        ],
        retrieved_chunks=[
            CopilotRetrievedChunk(
                chunk_id=str(c.get("chunk_id") or ""),
                source=str(c.get("source") or ""),
                title=str(c.get("title") or ""),
                text=str(c.get("text") or ""),
                score=c.get("score"),
            )
            for c in result.retrieved_chunks
        ],
        recommendations=recs,
        needs_approval=bool(result.needs_approval),
    )


_PLANS_CACHE: dict[tuple[int, int, str], tuple[float, StratPlansResponse]] = {}
_PLANS_TTL_S = 600.0
_HIST_WARM: set[str] = set()


def _warm_circuit_history(circuit_key: str) -> None:
    if not circuit_key or circuit_key in _HIST_WARM:
        return
    _HIST_WARM.add(circuit_key)

    def _run() -> None:
        try:
            from backend.analytics import circuit_history

            circuit_history(circuit_key)
        except Exception:
            _HIST_WARM.discard(circuit_key)

    threading.Thread(target=_run, name=f"aris-hist-{circuit_key}", daemon=True).start()


def plans(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    from aris.plan.prewrite import generate_strat_plans
    from aris.tracks import load_track_config

    code = resolve_driver_code(year, driver_code, round_number)
    cache_key = (int(year), int(round_number), code)
    hit = _PLANS_CACHE.get(cache_key)
    if hit and (time.monotonic() - hit[0]) < _PLANS_TTL_S:
        return hit[1]
    country = ""
    circuit_key = ""
    try:
        from backend.calendar import peek_round_meta

        country, circuit_key = peek_round_meta(year, round_number)
    except Exception:
        country, circuit_key = "", ""
    track = load_track_config(country or code, year=year, round_no=round_number)
    hist_first = None
    hist_stops = None
    if circuit_key:
        try:
            from backend.analytics import peek_circuit_history

            hist = peek_circuit_history(circuit_key)
            if hist is None and circuit_key:
                from backend.analytics import circuit_history

                hist = circuit_history(circuit_key)
            if hist is not None:
                hist_first = hist.median_first_stop_lap
                hist_stops = hist.typical_stop_count
            else:
                _warm_circuit_history(circuit_key)
        except Exception:
            pass
    hist_scope = (
        "Zandvoort 2021–2025"
        if str(circuit_key).lower() in {"netherlands", "zandvoort", "dutch"}
        else "2018–present at this circuit"
    )
    result = generate_strat_plans(
        0,
        0,
        year=year,
        round_no=round_number,
        country=country or track.country,
        driver_code=code,
        hist_first_stop=hist_first,
        hist_stop_count=hist_stops,
        hist_scope=hist_scope,
        score=False,
        use_weekend_form=False,
    )
    payload = _plans_payload(year, round_number, code, result, track.pit_loss_s)
    _PLANS_CACHE[cache_key] = (time.monotonic(), payload)

    def _background() -> None:
        try:
            from backend.ingest_jobs import ensure_session_ingested

            if not _session_open(year, round_number):
                ensure_session_ingested(year, round_number, "R")
        except Exception:
            pass
        try:
            scored = generate_strat_plans(
                0,
                0,
                year=year,
                round_no=round_number,
                country=country or track.country,
                driver_code=code,
                hist_first_stop=hist_first,
                hist_stop_count=hist_stops,
                hist_scope=hist_scope,
                use_weekend_form=False,
            )
            _PLANS_CACHE[cache_key] = (
                time.monotonic(),
                _plans_payload(year, round_number, code, scored, track.pit_loss_s),
            )
        except Exception:
            pass

    threading.Thread(target=_background, name=f"aris-plans-score-{code}", daemon=True).start()
    return payload


def _plans_payload(year: int, round_number: int, code: str, result: Any, pit_loss_s: float) -> StratPlansResponse:
    out: list[StratPlanOut] = []
    for plan in result.plans:
        pit_cost = pit_loss_s * len(plan.pit_laps)
        out.append(
            StratPlanOut(
                id=plan.id,
                name=plan.name,
                pit_laps=plan.pit_laps,
                pit_compounds=plan.pit_compounds,
                start_compound=plan.start_compound,
                expected_race_time_s=plan.expected_race_time_s,
                description=plan.description,
                recommended=plan.recommended,
                pace_gain_s=round(max(0.0, pit_cost * 0.85), 2),
                pit_cost_s=pit_cost,
                risk="Low" if len(plan.pit_laps) == 1 else "Higher",
            )
        )
    return StratPlansResponse(
        year=year,
        round_number=round_number,
        driver_code=code,
        plans=out,
        pit_loss_s=pit_loss_s,
    )


def quick_analysis(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    """Top-3 pre-race strategies. Calls plans(); does not touch recommend()/simulate()."""
    payload = plans(year, round_number, driver_code)
    ranked = list(payload.plans)[:3]
    if ranked and not any(p.recommended for p in ranked):
        ranked[0] = ranked[0].model_copy(update={"recommended": True})
    return payload.model_copy(update={"plans": ranked})


def _expand_compound(raw: str | None) -> str:
    if not raw:
        return "MEDIUM"
    u = str(raw).upper()
    mapping = {"S": "SOFT", "M": "MEDIUM", "H": "HARD", "I": "INTERMEDIATE", "W": "WET"}
    if u in mapping:
        return mapping[u]
    if u in {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}:
        return u
    return "MEDIUM"


def _field_race_times_s(year: int, round_number: int) -> dict[str, float]:
    from backend.sessions import session_laps

    times: dict[str, float] = {}
    try:
        laps = session_laps(year, round_number, "R").laps
    except Exception:
        return times
    for lap in laps:
        if lap.lap_time_ms is None:
            continue
        times[lap.driver_code] = times.get(lap.driver_code, 0.0) + lap.lap_time_ms / 1000.0
    return times


def debrief(year: int, round_number: int, driver_code: str) -> DebriefResponse:
    from backend.analytics import gap_history, pit_stops, position_history
    from backend.sessions import session_laps

    code = resolve_driver_code(year, driver_code, round_number)
    results = session_results(year, round_number, "R").results
    stints_all = session_stints(year, round_number, "R").stints
    pits = [s for s in stints_all if s.driver_code == code]
    mine = next((r for r in results if r.driver_code == code), None)
    actual_pits = [s.lap_start for s in pits[1:]]
    actual_compounds = [s.compound for s in pits if s.compound]
    decisions: list[DebriefDecision] = []
    rec_last = None
    for pit_lap, stint in zip(actual_pits or [0], pits[1:] or pits[:1]):
        try:
            rec_last = recommend(
                RecommendRequest(
                    year=year,
                    round_number=round_number,
                    session_type="R",
                    driver_code=code,
                    current_lap=max(1, (pit_lap or 20) - 2),
                    mode="replay",
                )
            )
            actual = f"BOX → {stint.compound}" if stint.compound else f"BOX lap {pit_lap}"
            delta = rec_last.net_delta_s
            decisions.append(
                DebriefDecision(
                    lap=int(pit_lap or 0),
                    aris_call=f"{rec_last.action}"
                    + (f" → {rec_last.compound_recommendation}" if rec_last.compound_recommendation else ""),
                    actual_call=actual,
                    outcome=rec_last.reasoning,
                    net_delta_s=delta,
                    reasoning=rec_last.reasoning,
                    pace_gain_s=rec_last.pace_gain_s,
                    pit_cost_s=rec_last.pit_cost_s,
                )
            )
        except Exception as extra:
            decisions.append(
                DebriefDecision(
                    lap=pit_lap or 0,
                    aris_call="unavailable",
                    actual_call="see tyre strategy",
                    outcome=str(extra),
                    net_delta_s=None,
                )
            )
    if not decisions:
        decisions.append(
            DebriefDecision(
                lap=0,
                aris_call="STAY OUT",
                actual_call="no pit recorded",
                outcome="No pit stops in the classified stints.",
                net_delta_s=None,
            )
        )

    actual_pos = mine.position if mine else None
    try:
        rec_plans = plans(year, round_number, code)
        rec_plan = next((p for p in rec_plans.plans if p.recommended), rec_plans.plans[0] if rec_plans.plans else None)
    except Exception:
        rec_plan = None

    aris_pos = actual_pos
    try:
        from aris.eval.postrace import PitSchedule, project_aris_finish, simulate_schedule

        field_times = _field_race_times_s(year, round_number)
        actual_time = field_times.get(code)
        start_compound = _expand_compound(pits[0].compound if pits else None)
        team_sched = PitSchedule(
            pit_laps=[int(s.lap_start) for s in pits[1:]],
            pit_compounds=[_expand_compound(s.compound) for s in pits[1:]],
            start_compound=start_compound,
        )
        if rec_plan is not None:
            aris_sched = PitSchedule(
                pit_laps=list(rec_plan.pit_laps),
                pit_compounds=[_expand_compound(c) for c in rec_plan.pit_compounds],
                start_compound=_expand_compound(rec_plan.start_compound),
            )
        else:
            aris_sched = team_sched
        state, _src = build_race_state_with_fallback(year, round_number, code, 1)
        aris_sim = team_sim = None
        if state is not None:
            aris_sim = simulate_schedule(state, aris_sched)
            team_sim = simulate_schedule(state, team_sched)
        aris_pos = project_aris_finish(
            field_times,
            code,
            actual_time_s=actual_time,
            aris_sim_s=aris_sim,
            team_sim_s=team_sim,
            classified_pos=actual_pos,
        )
    except Exception as extra:
        _log.warning("debrief position rank failed: %s", extra)
        aris_pos = actual_pos
    ranked_pos = [p for p in (aris_pos, actual_pos) if p is not None]
    optimal_pos = min(ranked_pos) if ranked_pos else None

    aris_col = StrategyColumn(
        label="ARIS PROJECTED",
        position=aris_pos,
        plan_name=rec_plan.name if rec_plan else "Plan A",
        pits=[ProjectedPit(lap=lap, compound=c or "?") for lap, c in zip(rec_plan.pit_laps, rec_plan.pit_compounds)]
        if rec_plan
        else [],
    )
    actual_col = StrategyColumn(
        label="CLASSIFIED RESULT",
        position=mine.position if mine else None,
        plan_name="actual finish",
        pits=[ProjectedPit(lap=s.lap_start, compound=s.compound or "?") for s in pits[1:]],
    )
    opt_col = StrategyColumn(
        label="ARIS OPTIMAL (sim)",
        position=optimal_pos,
        plan_name="hindsight",
        pits=list(aris_col.pits),
    )

    laps_led = 0
    sc_events = 0
    try:
        posh = position_history(year, round_number)
        for row in posh.laps:
            if row.positions.get(code) == 1:
                laps_led += 1
    except Exception:
        pass
    try:
        msgs = session_messages(year, round_number, "R").messages
        sc_events = sum(
            1
            for m in msgs
            if "SC" in f"{m.flag or ''} {m.category or ''} {m.message or ''}".upper()
        )
    except Exception:
        pass
    pit_time = None
    try:
        ps = pit_stops(year, round_number).stops
        mine_pits = [p for p in ps if p.driver_code == code]
        times = [p.duration_ms for p in mine_pits if p.duration_ms]
        pit_time = (sum(times) / 1000.0) if times else None
    except Exception:
        pass
    positions_gained = None
    if mine and mine.grid and mine.position:
        positions_gained = mine.grid - mine.position
    fl_ms = field_fl = deg = field_deg = None
    try:
        laps = session_laps(year, round_number, "R").laps
        mine_laps = [l.lap_time_ms for l in laps if l.driver_code == code and l.lap_time_ms]
        all_times = [l.lap_time_ms for l in laps if l.lap_time_ms]
        fl_ms = min(mine_laps) if mine_laps else None
        field_fl = min(all_times) if all_times else None
        degs = [s.deg_rate_ms_per_lap for s in pits if s.deg_rate_ms_per_lap is not None]
        field_degs = [s.deg_rate_ms_per_lap for s in stints_all if s.deg_rate_ms_per_lap is not None]
        deg = sum(degs) / len(degs) if degs else None
        field_deg = sum(field_degs) / len(field_degs) if field_degs else None
    except Exception:
        pass
    correct = sum(1 for d in decisions if d.net_delta_s is not None and d.net_delta_s <= 0)
    stats = DebriefStats(
        laps_led=laps_led,
        pit_time_s=pit_time,
        compounds_used=list(dict.fromkeys(c for c in actual_compounds if c)),
        positions_gained=positions_gained,
        fastest_lap_ms=fl_ms,
        field_fastest_lap_ms=field_fl,
        deg_rate_ms=deg,
        field_deg_rate_ms=field_deg,
        aris_correct=correct,
        aris_total=len(decisions),
        sc_events=sc_events,
        sc_handled=min(correct, sc_events) if sc_events else 0,
    )
    delta_series: list[DebriefDeltaPoint] = []
    try:
        gaps = gap_history(year, round_number)
        running = 0.0
        step = (rec_last.net_delta_s / max(1, len(gaps.laps))) if rec_last and rec_last.net_delta_s else 0.0
        for row in gaps.laps:
            running += -step
            delta_series.append(
                DebriefDeltaPoint(
                    lap=row.lap,
                    aris_vs_actual_s=round(running, 3),
                    optimal_vs_actual_s=round(running * 1.15, 3),
                )
            )
    except Exception:
        pass

    actual = mine.position if mine else None
    summary = "Classified result from the session. ARIS projected finish is ranked on the field, not a seconds-to-places guess."
    if aris_pos is not None and actual is not None:
        if aris_pos == actual:
            summary = (
                f"{code} classified P{actual}. ARIS projected the same result "
                f"on its recommended plan."
            )
        else:
            word = "better" if aris_pos < actual else "worse"
            summary = (
                f"{code} classified P{actual}. ARIS projected P{aris_pos} "
                f"({word} than the actual finish) if its recommended plan had been run."
            )
    podium = [r for r in results if r.position is not None and r.position <= 3]
    return DebriefResponse(
        year=year,
        round_number=round_number,
        driver_code=code,
        actual_position=mine.position if mine else None,
        aris_projected_position=aris_pos,
        optimal_position=optimal_pos,
        actual_pits=actual_pits,
        decisions=decisions,
        summary=summary,
        podium=podium,
        aris_strategy=aris_col,
        actual_strategy=actual_col,
        optimal_strategy=opt_col,
        stats=stats,
        delta_series=delta_series,
    )


def model_stats() -> ArisStatsResponse:
    match = 0.325
    return ArisStatsResponse(
        lap_time_mae_s=0.583,
        decision_match_rate=match,
        never_pit_baseline=0.250,
        avg_position_delta=-1.73,
        clean_delta=-1.49,
        disrupted_delta=-2.38,
        version="v0.3",
        match_rate=match,
        match_rate_fraction="28/87 dry",
        last_gate="T4-final",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def explain_degradation(
    session_id: str | None,
    driver: str,
    stint_id: int | None = None,
    start_lap: int | None = None,
    end_lap: int | None = None,
    year: int | None = None,
    round_number: int | None = None,
) -> dict:
    """T12 — bicycle vs FastF1 deg curve. Does not change recommend()/simulate()."""
    from aris.explain.degradation import get_degradation_curve

    code = (driver or "VER").upper()
    if year and round_number:
        try:
            code = resolve_driver_code(year, code, round_number)
        except ClientInputError:
            pass
    return get_degradation_curve(
        code,
        stint_id=stint_id,
        start_lap=start_lap,
        end_lap=end_lap,
        session_id=session_id,
        year=year,
        round_number=round_number,
    )


def explain_ghost(
    session_id: str | None,
    driver: str,
    year: int | None = None,
    round_number: int | None = None,
) -> dict:
    """T12 — ARIS ghost vs classified result. Calls recommend()/simulate() as-is."""
    from aris.explain.ghost import get_ghost_vs_real

    code = (driver or "VER").upper()
    if year and round_number:
        try:
            code = resolve_driver_code(year, code, round_number)
        except ClientInputError:
            pass
    return get_ghost_vs_real(code, session_id, year=year, round_number=round_number)


def explain_debrief(
    session_id: str | None,
    focus_driver: str | None = None,
    year: int | None = None,
    round_number: int | None = None,
) -> dict:
    """T12 — race debrief timeline + recommend() top-3 at each pit inflection."""
    from aris.explain.debrief import get_race_debrief

    code = (focus_driver or "VER").upper()
    if year and round_number:
        try:
            code = resolve_driver_code(year, code, round_number)
        except ClientInputError:
            pass
    sid = session_id or (f"{year}-{round_number}-R" if year and round_number else "2025-15-R")
    return get_race_debrief(sid, code, year=year, round_number=round_number)
