"""Grounded Q&A over race session state — Ask ARIS mode.

Keyword / rule-based matching on the question text against a structured
session snapshot. Not retrieval-augmented generation.
"""

from __future__ import annotations

import json
from typing import Any

from aris.engine.session import RaceEngineSession
from aris.narrate import _fallback_narration
from aris.plan.weekend_form import weekend_form


def _session_snapshot(session: RaceEngineSession) -> dict[str, Any]:
    state = session.build_state()
    gaps = session.gaps_for_driver()
    return {
        "driver": session.driver_code,
        "team": session.team,
        "lap": state.lap_number,
        "compound": state.compound,
        "tyre_life": state.tyre_life,
        "position": gaps.get("position"),
        "gap_to_leader_s": gaps.get("gap_to_leader_s"),
        "gap_ahead_s": gaps.get("gap_ahead_s"),
        "active_strat": session.active_strat.name if session.active_strat else None,
        "committed_pits": [p.model_dump() for p in session.committed_pits],
        "recent_decisions": len(session.decision_queue.decisions),
    }


def answer_question(session: RaceEngineSession, question: str, *, use_llm: bool = False) -> str:
    """Grounded answer from structured session snapshot only."""
    q = question.lower()
    snap = _session_snapshot(session)
    forms = weekend_form(session.year, session.round_no)
    driver_form = next((f for f in forms if f.code == session.driver_code), None)

    if "pit" in q:
        pits = [p.model_dump() for p in session.committed_pits]
        strat = snap.get("active_strat")
        return f"Committed pit windows: {json.dumps(pits)}. Active strat: {strat}."
    if "tyre" in q or "tire" in q or "compound" in q:
        return (
            f"Currently on {snap['compound']} (life {snap['tyre_life']}). "
            f"Source: session snapshot lap {snap['lap']}."
        )
    if "gap" in q or "position" in q:
        return (
            f"P{snap.get('position', '?')} — "
            f"{snap.get('gap_to_leader_s', 0):.1f}s to leader, "
            f"{snap.get('gap_ahead_s', '—')}s ahead."
        )
    if "quali" in q or "practice" in q and driver_form:
        return (
            f"Quali best: {driver_form.quali_time}s. "
            f"FP bests — SOFT {driver_form.best_soft}, "
            f"MEDIUM {driver_form.best_medium}, HARD {driver_form.best_hard}."
        )
    if session.decision_queue.history:
        last = session.decision_queue.history[-1]
        if last.recommendation:
            return _fallback_narration(last.recommendation)

    return f"Based on current data: {json.dumps(snap)}"
