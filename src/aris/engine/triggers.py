"""Decision triggers for always-on race engineer."""

from __future__ import annotations

from aris.decisions.queue import DecisionKind
from aris.engine.clock import SectorEvent
from aris.engine.session import RaceEngineSession
from aris.io import db

APPROACHING_OFFSET = 5
APPROACHING_FRACS = (0.25, 0.50, 0.75)


def approaching_key(frac: float) -> str:
    return f"approaching_{frac:.2f}"


def check_triggers(session: RaceEngineSession, event: SectorEvent) -> DecisionKind | None:
    """Return a decision kind if ARIS should propose now."""
    if session.decision_queue.pending is not None:
        return None

    lap = event.index.lap_number
    if lap != session.last_trigger_lap:
        session.fired_this_lap.clear()
        session.last_trigger_lap = lap

    # Field clock can advance past a DNF'd focus driver's last lap — skip
    # triggers rather than building a synthetic clamped state that would
    # re-fire pit/tyre thresholds forever.
    focus_laps = db.fetch_laps(session.session_id, session.driver_id)
    if focus_laps.empty or lap > int(focus_laps["lap_number"].max()):
        return None

    state = session.build_state(lap)

    if lap == 1 and event.is_new_lap and 1 not in session.triggered_laps:
        if "CONFIRM_STRAT" not in session.fired_this_lap:
            session.fired_this_lap.add("CONFIRM_STRAT")
            session.triggered_laps.add(1)
            return DecisionKind.CONFIRM_STRAT

    if (
        state.track_status
        and str(state.track_status) not in ("1", "None")
        and lap not in session.triggered_laps
        and "SC" not in session.fired_this_lap
    ):
        session.fired_this_lap.add("SC")
        session.triggered_laps.add(lap)
        return DecisionKind.SC

    total = max(state.total_laps, 1)
    if "APPROACHING" not in session.fired_this_lap:
        for frac in APPROACHING_FRACS:
            threshold_laps = int(frac * total)
            key = approaching_key(frac)
            if (
                threshold_laps - APPROACHING_OFFSET <= state.tyre_life < threshold_laps
                and key not in session.fired_triggers
            ):
                session.fired_triggers.add(key)
                session.fired_this_lap.add("APPROACHING")
                return DecisionKind.APPROACHING_WINDOW

    life_pct = state.tyre_life / total
    thresholds = (0.25, 0.5, 0.75)
    for thr in thresholds:
        key = int(thr * 1000) + lap
        if life_pct >= thr and key not in session.triggered_laps and "PIT" not in session.fired_this_lap:
            session.fired_this_lap.add("PIT")
            session.triggered_laps.add(key)
            return DecisionKind.PIT

    if state.undercut_threat and lap not in session.triggered_laps and "PIT" not in session.fired_this_lap:
        session.fired_this_lap.add("PIT")
        session.triggered_laps.add(lap)
        return DecisionKind.PIT

    gaps = session.gaps_for_driver()
    gap_ahead = gaps.get("gap_ahead_s")
    if gap_ahead is not None and gap_ahead < 1.0:
        key = 9000 + lap
        if key not in session.triggered_laps and "TACTICAL" not in session.fired_this_lap:
            session.fired_this_lap.add("TACTICAL")
            session.triggered_laps.add(key)
            return DecisionKind.TACTICAL

    return None
