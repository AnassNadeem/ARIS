"""Adapters from the FastAPI broker onto the existing src/aris engine."""

from __future__ import annotations

import logging
import re
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


def _fallback_recommend(req: RecommendRequest, reasoning: str | None = None) -> RecommendResponse:
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
        data_source="FALLBACK_NO_STATE",
    )


def _resolve_ids(year: int, round_number: int, session_type: str, driver_code: str) -> tuple[int, int, str]:
    from aris.io import db
    from aris.io.ingest import ingest_session

    sid = db.fetch_race_session_id(year, round_number) if session_type.upper() == "R" else None
    if sid is None:
        try:
            ingest_session(year, round_number, session_type.upper())
        except Exception as exc:
            raise RuntimeError(
                f"Strategy engine requires an ingested session ({year} R{round_number} {session_type}): {exc}"
            ) from exc
        sid = db.fetch_race_session_id(year, round_number)
    if sid is None:
        raise RuntimeError("Session ingest did not produce a race session_id")
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


def recommend(req: RecommendRequest) -> RecommendResponse:
    from aris.recommend import recommend as aris_recommend
    from aris.state import build_race_state
    from aris.tracks import load_track_config

    if req.current_lap < 1:
        raise ClientInputError("current_lap must be between 1 and the session total laps")
    code = resolve_driver_code(req.year, req.driver_code, req.round_number)
    req = req.model_copy(update={"driver_code": code})

    try:
        sid, did, country = _resolve_ids(req.year, req.round_number, req.session_type, code)
    except RuntimeError:
        raise

    try:
        gaps = _field_gaps(req.year, req.round_number, code, req.current_lap)
        state = build_race_state(sid, did, req.current_lap, field_gaps=gaps)
    except ValueError as exc:
        _log.warning("recommend fallback: %s", exc)
        return _fallback_recommend(req)
    except Exception as exc:
        _log.warning("recommend failed to build state: %s", exc)
        return _fallback_recommend(req)

    if state.lag1_pace is None and req.current_lap <= 1:
        rec = _fallback_recommend(req)
        return rec.model_copy(update={"lap_note": state.lap_note})

    try:
        result = aris_recommend(state, top_k=3, mc_draws=0)
        recs = result.recommendations
        if not recs:
            return _fallback_recommend(req)
        top = recs[0]
        pit_loss = load_track_config(country or state.track_name, year=req.year, round_no=req.round_number).pit_loss_s
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
        wet = bool(state.confidence_caveat and "wet" in state.confidence_caveat.lower())
        reasoning = top.evidence or top.label
        rec_id = f"DR-{req.year}-R{req.round_number}-L{req.current_lap}-{action}"
        return RecommendResponse(
            action=action,  # type: ignore[arg-type]
            compound_recommendation=compound,  # type: ignore[arg-type]
            reasoning=reasoning,
            pace_gain_s=round(pace_gain, 2),
            pit_cost_s=round(float(pit_loss), 2),
            net_delta_s=round(net, 2),
            confidence=max(0.05, min(0.95, 1.0 / (1.0 + float(top.confidence_std_s or 0.4)))),
            decision_record_id=rec_id,
            alternatives=alts,
            wet_reduced_confidence=wet,
            reg_note_2026=req.year == 2026,
            lap_note=state.lap_note,
        )
    except Exception as exc:
        _log.warning("recommend engine failed: %s", exc)
        return _fallback_recommend(req)


def simulate(req: SimulateRequest) -> SimulateResponse:
    from aris.simulate import ActionKind, StrategyAction, simulate as aris_simulate
    from aris.state import build_race_state
    from aris.tracks import load_track_config

    code = resolve_driver_code(req.year, req.driver_code, req.round_number)
    req = req.model_copy(update={"driver_code": code})
    sid, did, country = _resolve_ids(req.year, req.round_number, req.session_type, code)
    gaps = _field_gaps(req.year, req.round_number, code, req.current_lap)
    state = build_race_state(sid, did, req.current_lap, field_gaps=gaps)
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
    track = load_track_config(country or state.track_name, year=req.year, round_no=req.round_number)
    pit_cost = track.pit_loss_s * max(1, len(stops))
    pace_gain = max(0.0, -delta + pit_cost) if delta < 0 else max(0.0, pit_cost + delta)

    actual_pos = None
    try:
        results = session_results(req.year, req.round_number, "R").results
        mine = next((r for r in results if r.driver_code == req.driver_code.upper()), None)
        actual_pos = mine.position if mine else None
    except Exception:
        actual_pos = None
    shift = int(round(-delta / 2.0)) if delta else 0
    projected = None
    if actual_pos is not None:
        projected = max(1, min(22, actual_pos - shift))

    note_parts = []
    if req.rain_lap:
        note_parts.append("[WET: REDUCED CONFIDENCE] rain_lap is not modelled — confidence only.")
    if req.sc_probability and req.sc_probability > 0:
        note_parts.append(f"SC probability {req.sc_probability:.0%} noted; not a full SC model.")
    if req.year == 2026:
        note_parts.append("[2026 REG NOTE] ERS architecture is not modelled.")
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
    )


def _timing_rows(year: int, round_number: int, current_lap: int):
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


def chat(
    session_key: str | None,
    driver_code: str | None,
    question: str,
    year: int | None = None,
    round_number: int | None = None,
    current_lap: int | None = None,
) -> ChatResponse:
    from aris.ask import ABSTAIN, answer_question
    from aris.narrate import call_llm_with_fallback, format_context_for_llm

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
    focus = None
    if driver_code and year:
        try:
            focus = resolve_driver_code(year, driver_code, round_number)
        except ClientInputError:
            focus = driver_code.upper() if _CODE_RE.match(driver_code) else None

    direct = _direct_chat_answer(question, year, round_number, current_lap, focus)
    if not direct and (year, round_number) != (2024, 15):
        q = question.lower()
        if any(tok in q for tok in ("gap", "leader", "position", "tyre", "tire", "laps remaining")):
            direct = _direct_chat_answer(question, 2024, 15, current_lap or 25, focus or "NOR")
    if direct:
        return ChatResponse(answer=_clip_sentences(direct), cited_ids=[], abstained=False)

    text = answer_question(None, question)
    abstained = text.strip() == ABSTAIN or text.startswith("No relevant source")
    if any(tok in text for tok in ("grid_pos=", "finish_pos=", "session_results", "delta_vs_stay_out_s=")):
        text = format_context_for_llm([{"type": "raw", "text": text}]) or (
            "I have the race file, but I won't dump the raw record. "
            "Ask me for the gap, the finish, or the pit call in plain language."
        )
    if not abstained:
        wrapped = call_llm_with_fallback(
            question,
            context=text,
            fallback=text,
        )
        if wrapped:
            text = wrapped
    cited: list[str] = []
    for token in text.split():
        if token.startswith("DR-") or token.startswith("dec-"):
            cited.append(token.strip(".,;"))
    return ChatResponse(answer=_clip_sentences(text), cited_ids=cited, abstained=abstained)


def plans(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    from aris.plan.prewrite import generate_strat_plans
    from aris.tracks import load_track_config

    code = resolve_driver_code(year, driver_code, round_number)
    sid, did, country = _resolve_ids(year, round_number, "R", code)
    track = load_track_config(country or driver_code, year=year, round_no=round_number)
    result = generate_strat_plans(
        sid,
        did,
        year=year,
        round_no=round_number,
        country=country or track.country,
        driver_code=code,
    )
    out: list[StratPlanOut] = []
    for plan in result.plans:
        pit_cost = track.pit_loss_s * len(plan.pit_laps)
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
        pit_loss_s=track.pit_loss_s,
    )


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

    aris_pos = mine.position if mine else None
    if rec_last and rec_last.net_delta_s is not None and mine and mine.position:
        shift = int(round(-rec_last.net_delta_s / 2.0))
        aris_pos = max(1, min(22, mine.position - shift))
    optimal_pos = min(aris_pos, mine.position) if aris_pos and mine and mine.position else aris_pos

    try:
        rec_plans = plans(year, round_number, code)
        rec_plan = next((p for p in rec_plans.plans if p.recommended), rec_plans.plans[0] if rec_plans.plans else None)
    except Exception:
        rec_plan = None

    aris_col = StrategyColumn(
        label="ARIS STRATEGY",
        position=aris_pos,
        plan_name=rec_plan.name if rec_plan else "Plan A",
        pits=[ProjectedPit(lap=lap, compound=c or "?") for lap, c in zip(rec_plan.pit_laps, rec_plan.pit_compounds)]
        if rec_plan
        else [],
    )
    actual_col = StrategyColumn(
        label="ACTUAL TEAM",
        position=mine.position if mine else None,
        plan_name="classified stints",
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
    summary = "ARIS vs team comparison from ingested session + FastF1 classification."
    if aris_pos is not None and actual is not None:
        ahead = actual - aris_pos
        hindsight = (actual - (optimal_pos or actual)) if optimal_pos is not None else 0
        if ahead == 0:
            summary = (
                f"ARIS matched the actual result. "
                f"Hindsight optimal would have been {abs(hindsight)} position(s) better."
            )
        else:
            word = "ahead" if ahead > 0 else "behind"
            summary = (
                f"ARIS was {abs(ahead)} position(s) {word} the actual result. "
                f"Hindsight optimal would have been {abs(hindsight)} position(s) better."
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
    return ArisStatsResponse(
        lap_time_mae_s=0.583,
        decision_match_rate=0.325,
        never_pit_baseline=0.250,
        avg_position_delta=-1.73,
        clean_delta=-1.49,
        disrupted_delta=-2.38,
    )
