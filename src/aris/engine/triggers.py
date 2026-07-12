"""Decision triggers for always-on race engineer."""

from __future__ import annotations

from aris.decisions.queue import DecisionKind
from aris.engine.clock import SectorEvent
from aris.engine.session import RaceEngineSession


def check_triggers(session: RaceEngineSession, event: SectorEvent) -> DecisionKind | None:
    """Return a decision kind if ARIS should propose now."""
    if session.decision_queue.pending is not None:
        return None

    lap = event.index.lap_number
    state = session.build_state(lap)

    if lap == 1 and event.is_new_lap and 1 not in session.triggered_laps:
        session.triggered_laps.add(1)
        return DecisionKind.CONFIRM_STRAT

    if (
        state.track_status
        and str(state.track_status) not in ("1", "None")
        and lap not in session.triggered_laps
    ):
        session.triggered_laps.add(lap)
        return DecisionKind.SC

    life_pct = state.tyre_life / max(state.total_laps, 1)
    thresholds = (0.25, 0.5, 0.75)
    for thr in thresholds:
        key = int(thr * 1000) + lap
        if life_pct >= thr and key not in session.triggered_laps:
            session.triggered_laps.add(key)
            return DecisionKind.PIT

    if state.undercut_threat and lap not in session.triggered_laps:
        session.triggered_laps.add(lap)
        return DecisionKind.PIT

    gaps = session.gaps_for_driver()
    gap_ahead = gaps.get("gap_ahead_s")
    if gap_ahead is not None and gap_ahead < 1.0:
        key = 9000 + lap
        if key not in session.triggered_laps:
            session.triggered_laps.add(key)
            return DecisionKind.TACTICAL

    return None
