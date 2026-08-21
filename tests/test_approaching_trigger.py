"""T2-C: approaching pit-window trigger fires once on a stable key."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from aris.decisions.queue import DecisionKind, DecisionQueue
from aris.engine.clock import SectorEvent
from aris.engine.session import RaceEngineSession, SessionPhase
from aris.engine.triggers import APPROACHING_OFFSET, approaching_key, check_triggers
from aris.field.state import FieldState, ReplayIndex
from aris.state import RaceState


def _session() -> RaceEngineSession:
    return RaceEngineSession(
        session_id=1,
        driver_id=99,
        driver_code="NOR",
        team="McLaren",
        year=2024,
        round_no=15,
        country="Netherlands",
        total_laps=72,
        phase=SessionPhase.LIVE,
        decision_queue=DecisionQueue(),
    )


def _event(lap: int) -> SectorEvent:
    return SectorEvent(
        index=ReplayIndex(lap, 0),
        field=MagicMock(spec=FieldState),
        is_new_lap=True,
        is_race_complete=False,
    )


def _state(*, lap: int, tyre_life: int, track_status: str = "1") -> RaceState:
    return RaceState(
        session_id=1,
        driver_id=99,
        driver_code="NOR",
        driver_name="Lando Norris",
        year=2024,
        round_no=15,
        country="Netherlands",
        lap_number=lap,
        compound="MEDIUM",
        tyre_life=tyre_life,
        fuel_kg=80.0,
        laps_remaining=max(0, 72 - lap),
        total_laps=72,
        track_status=track_status,
    )


def _patch_laps(monkeypatch, *, last_lap: int = 72) -> None:
    laps = pd.DataFrame({"lap_number": list(range(1, last_lap + 1))})
    monkeypatch.setattr("aris.engine.triggers.db.fetch_laps", lambda sid, did: laps)


def test_nl_72_tyre_life_13_fires_once(monkeypatch):
    session = _session()
    _patch_laps(monkeypatch)
    life = {"v": 13}

    def fake_state(self, lap_number: int | None = None) -> RaceState:
        lap = int(lap_number or 14)
        return _state(lap=lap, tyre_life=life["v"])

    monkeypatch.setattr(RaceEngineSession, "build_state", fake_state)

    assert APPROACHING_OFFSET == 5
    assert int(0.25 * 72) - APPROACHING_OFFSET == 13
    first = check_triggers(session, _event(14))
    assert first == DecisionKind.APPROACHING_WINDOW
    assert approaching_key(0.25) in session.fired_triggers

    life["v"] = 14
    second = check_triggers(session, _event(15))
    assert second != DecisionKind.APPROACHING_WINDOW
    assert second is None or second == DecisionKind.PIT


def test_hard_threshold_18_still_fires_pit(monkeypatch):
    session = _session()
    _patch_laps(monkeypatch)
    monkeypatch.setattr(
        RaceEngineSession,
        "build_state",
        lambda self, lap_number=None: _state(lap=int(lap_number or 19), tyre_life=18),
    )
    kind = check_triggers(session, _event(19))
    assert kind == DecisionKind.PIT


def test_approaching_does_not_block_sc(monkeypatch):
    session = _session()
    _patch_laps(monkeypatch)
    monkeypatch.setattr(
        RaceEngineSession,
        "build_state",
        lambda self, lap_number=None: _state(
            lap=int(lap_number or 20), tyre_life=13, track_status="4"
        ),
    )
    assert check_triggers(session, _event(20)) == DecisionKind.SC
