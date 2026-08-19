"""build_race_state clamps missing laps instead of raising."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from aris.state import build_race_state


class _Row:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class _Conn:
    def execute(self, stmt, params=None):
        sql = str(stmt).lower()
        if "from sessions" in sql:
            return MagicMock(one=lambda: _Row(year=2024, round_no=15, country="Netherlands"))
        return MagicMock(one=lambda: _Row(code="NOR", full_name="Lando Norris", team="McLaren"))

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Eng:
    def connect(self):
        return _Conn()


def test_build_race_state_clamps_past_max_lap(monkeypatch):
    laps = pd.DataFrame(
        {
            "lap_number": [1, 2, 3],
            "compound": ["SOFT", "SOFT", "SOFT"],
            "tyre_life": [1, 2, 3],
            "lap_time_s": [94.1, 94.2, 94.3],
            "track_status": ["1", "1", "1"],
        }
    )
    monkeypatch.setattr("aris.state.db.engine", lambda: _Eng())
    monkeypatch.setattr("aris.state.db.fetch_laps", lambda *_a, **_k: laps)
    monkeypatch.setattr("aris.state.db.fetch_session_weather", lambda *_a, **_k: {})

    class _Cfg:
        total_laps = 72
        name = "Zandvoort"
        pit_loss_s = 18.0

    monkeypatch.setattr("aris.state.load_track_config", lambda *a, **k: _Cfg())

    state = build_race_state(1, 99, 80)
    assert state.lap_number == 3
    assert state.lap_note and "80" in state.lap_note
    # lag uses laps strictly before the clamped lap
    assert state.lag1_pace == 94.2
