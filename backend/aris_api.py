"""Adapters from the FastAPI broker onto the existing src/aris engine."""

from __future__ import annotations

import uuid
from typing import Any

from backend.models import (
    ChatResponse,
    DebriefDecision,
    DebriefResponse,
    ProjectedPit,
    RecommendAlternative,
    RecommendRequest,
    RecommendResponse,
    SimulateRequest,
    SimulateResponse,
    StratPlanOut,
    StratPlansResponse,
)
from backend.sessions import session_results, session_stints


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

    sid, did, country = _resolve_ids(req.year, req.round_number, req.session_type, req.driver_code)
    state = build_race_state(sid, did, req.current_lap)
    result = aris_recommend(state, top_k=3, mc_draws=0)
    recs = result.recommendations
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
    rec_id = f"DR-{req.year}-R{req.round_number}-L{req.current_lap}-{uuid.uuid4().hex[:6]}"
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
    )


def simulate(req: SimulateRequest) -> SimulateResponse:
    from aris.simulate import ActionKind, StrategyAction, simulate as aris_simulate
    from aris.state import build_race_state

    sid, did, _country = _resolve_ids(req.year, req.round_number, req.session_type, req.driver_code)
    state = build_race_state(sid, did, req.current_lap)
    stay = aris_simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))
    if req.pit_lap:
        action = StrategyAction(
            kind=ActionKind.PIT_LAP,
            pit_lap=req.pit_lap,
            pit_compound=(req.compound or "HARD").upper(),
        )
    else:
        action = StrategyAction(kind=ActionKind.STAY_OUT)
    outcome = aris_simulate(state, action)
    delta = float(outcome.total_race_time_s - stay.total_race_time_s)
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
    pits: list[ProjectedPit] = []
    if req.pit_lap and req.compound:
        pits.append(ProjectedPit(lap=req.pit_lap, compound=req.compound.upper()))
    return SimulateResponse(
        projected_finish_position=None,
        total_race_time_delta_s=round(delta, 3),
        projected_pit_stops=pits,
        risk_level=risk,  # type: ignore[arg-type]
        baseline_delta_s=0.0,
        wet_reduced_confidence=bool(req.rain_lap),
        note=" ".join(note_parts) or None,
    )


def chat(session_key: str | None, driver_code: str | None, question: str) -> ChatResponse:
    from aris.ask import ABSTAIN, answer_question

    text = answer_question(None, question)
    abstained = text.strip() == ABSTAIN or text.startswith("No relevant source")
    cited: list[str] = []
    for token in text.split():
        if token.startswith("DR-") or token.startswith("dec-"):
            cited.append(token.strip(".,;"))
    return ChatResponse(answer=text, cited_ids=cited, abstained=abstained)


def plans(year: int, round_number: int, driver_code: str) -> StratPlansResponse:
    from aris.plan.prewrite import generate_strat_plans
    from aris.tracks import load_track_config

    sid, did, country = _resolve_ids(year, round_number, "R", driver_code)
    track = load_track_config(country or driver_code, year=year, round_no=round_number)
    result = generate_strat_plans(
        sid,
        did,
        year=year,
        round_no=round_number,
        country=country or track.country,
        driver_code=driver_code.upper(),
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
                pace_gain_s=None,
                pit_cost_s=pit_cost,
                risk="Low" if len(plan.pit_laps) == 1 else "Higher",
            )
        )
    return StratPlansResponse(
        year=year,
        round_number=round_number,
        driver_code=driver_code.upper(),
        plans=out,
        pit_loss_s=track.pit_loss_s,
    )


def debrief(year: int, round_number: int, driver_code: str) -> DebriefResponse:
    code = driver_code.upper()
    results = session_results(year, round_number, "R").results
    pits = [s for s in session_stints(year, round_number, "R").stints if s.driver_code == code]
    mine = next((r for r in results if r.driver_code == code), None)
    actual_pits = [s.lap_start for s in pits[1:]]
    decisions: list[DebriefDecision] = []
    try:
        pit_lap = actual_pits[0] if actual_pits else 20
        rec = recommend(
            RecommendRequest(
                year=year,
                round_number=round_number,
                session_type="R",
                driver_code=code,
                current_lap=max(1, pit_lap - 2),
                mode="replay",
            )
        )
        actual = f"BOX → {pits[1].compound}" if len(pits) > 1 else "STAY OUT"
        decisions.append(
            DebriefDecision(
                lap=pit_lap,
                aris_call=f"{rec.action}"
                + (f" → {rec.compound_recommendation}" if rec.compound_recommendation else ""),
                actual_call=actual,
                outcome=rec.reasoning,
                net_delta_s=rec.net_delta_s,
            )
        )
    except Exception as exc:
        decisions.append(
            DebriefDecision(
                lap=0,
                aris_call="unavailable",
                actual_call="see tyre strategy",
                outcome=str(exc),
                net_delta_s=None,
            )
        )
    podium = [r for r in results if r.position is not None and r.position <= 3]
    return DebriefResponse(
        year=year,
        round_number=round_number,
        driver_code=code,
        actual_position=mine.position if mine else None,
        aris_projected_position=None,
        actual_pits=actual_pits,
        decisions=decisions,
        summary="ARIS vs team comparison from ingested session + FastF1 classification.",
        podium=podium,
    )
