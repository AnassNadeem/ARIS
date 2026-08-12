"""Regression: Strategy UI survives focus-driver DNF while field clock continues."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from aris.decisions.queue import DecisionQueue
from aris.engine.clock import SectorEvent
from aris.engine.session import RaceEngineSession, SessionPhase
from aris.engine.triggers import check_triggers
from aris.field.state import FieldState, ReplayIndex


def test_check_triggers_skips_after_focus_driver_last_lap(monkeypatch):
    session = RaceEngineSession(
        session_id=1,
        driver_id=99,
        driver_code="NOR",
        team="McLaren",
        year=2025,
        round_no=15,
        country="Netherlands",
        total_laps=72,
        phase=SessionPhase.LIVE,
        decision_queue=DecisionQueue(),
    )
    laps = pd.DataFrame({"lap_number": [1, 2, 3]})
    monkeypatch.setattr(
        "aris.engine.triggers.db.fetch_laps",
        lambda sid, did: laps,
    )
    event = SectorEvent(
        index=ReplayIndex(10, 0),
        field=MagicMock(spec=FieldState),
        is_new_lap=True,
        is_race_complete=False,
    )
    assert check_triggers(session, event) is None
