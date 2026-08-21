"""T3 consolidation — targeted undercut / overcut inflection filters."""

from __future__ import annotations

import pandas as pd

from aris.decisions.queue import DecisionKind
from aris.eval.backtest import (
    Inflection,
    is_overcut_event,
    is_undercut_event,
    rival_pitted_in_window,
    undercut_trigger_kind,
)
from tests.test_strategy import _sample_state


def test_undercut_keeps_pit_inside_22s_window():
    state = _sample_state(gap_ahead_s=8.0)
    inf = Inflection(kind="pit", lap=20, compound="HARD", team_pitted=True)
    assert undercut_trigger_kind(inf, 8.0) is DecisionKind.PIT
    assert is_undercut_event(state, inf) is True


def test_undercut_drops_gap_at_or_beyond_22s():
    inf = Inflection(kind="pit", lap=20, compound="HARD", team_pitted=True)
    assert is_undercut_event(_sample_state(gap_ahead_s=22.0), inf) is False
    assert is_undercut_event(_sample_state(gap_ahead_s=30.0), inf) is False
    assert is_undercut_event(_sample_state(gap_ahead_s=None), inf) is False


def test_undercut_tactical_when_gap_under_one():
    inf = Inflection(kind="compound", lap=18, compound="MEDIUM", team_pitted=False)
    state = _sample_state(gap_ahead_s=0.6)
    assert undercut_trigger_kind(inf, 0.6) is DecisionKind.TACTICAL
    assert is_undercut_event(state, inf) is True


def test_undercut_drops_sc_with_large_gap():
    inf = Inflection(kind="sc", lap=12, compound="MEDIUM", team_pitted=False)
    assert is_undercut_event(_sample_state(gap_ahead_s=10.0), inf) is False


def test_overcut_requires_rival_pit_and_gap():
    laps = pd.DataFrame(
        {
            "driver_id": [1, 2, 2, 1],
            "lap_number": [18, 18, 19, 20],
            "pit_in": [False, False, True, False],
        }
    )
    inf = Inflection(kind="pit", lap=20, compound="HARD", team_pitted=False)
    close = _sample_state(gap_ahead_s=1.5, lap_number=20)
    far = _sample_state(gap_ahead_s=3.0, lap_number=20)
    assert rival_pitted_in_window(laps, focus_driver_id=1, lap=20) is True
    assert is_overcut_event(close, inf, laps, 1) is False
    assert is_overcut_event(far, inf, laps, 1) is True


def test_overcut_ignores_focus_driver_own_pit():
    laps = pd.DataFrame(
        {
            "driver_id": [1, 1],
            "lap_number": [18, 19],
            "pit_in": [True, True],
        }
    )
    inf = Inflection(kind="sc", lap=20, compound="MEDIUM", team_pitted=False)
    state = _sample_state(gap_ahead_s=4.0, lap_number=20)
    assert rival_pitted_in_window(laps, focus_driver_id=1, lap=20) is False
    assert is_overcut_event(state, inf, laps, 1) is False
