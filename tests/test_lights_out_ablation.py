"""Lights-out sequential ablation (no DB). Position-delta is not FIA points."""

from __future__ import annotations

import pytest

from aris.eval.lights_out_ablation import (
    extra_stops,
    extra_stops_ex_sc_vsc,
    force_first_stop,
    force_pit_count,
    force_start_compound,
    score_schedules,
    stacked_constraints,
    summarize_ablation,
)
from aris.eval.postrace import PitSchedule
from tests.test_strategy import _sample_state


def _aris() -> PitSchedule:
    return PitSchedule(pit_laps=[30], pit_compounds=["HARD"], start_compound="MEDIUM")


def _team() -> PitSchedule:
    return PitSchedule(
        pit_laps=[18, 40], pit_compounds=["HARD", "MEDIUM"], start_compound="SOFT"
    )


def test_force_start_compound_only():
    out = force_start_compound(_aris(), _team())
    assert out.start_compound == "SOFT"
    assert out.pit_laps == [30]


def test_force_first_stop_copies_team_lap():
    out = force_first_stop(_aris(), _team())
    assert out.pit_laps[0] == 18
    assert out.start_compound == "MEDIUM"


def test_force_first_stop_noop_when_team_never_boxed():
    team = PitSchedule(pit_laps=[], pit_compounds=[], start_compound="MEDIUM")
    out = force_first_stop(_aris(), team)
    assert out.pit_laps == [30]


def test_force_pit_count_extends_and_trims():
    extended = force_pit_count(_aris(), _team())
    assert len(extended.pit_laps) == 2
    assert extended.pit_laps[1] == 40
    trimmed = force_pit_count(
        _team(),
        PitSchedule(pit_laps=[18], pit_compounds=["HARD"], start_compound="SOFT"),
    )
    assert trimmed.pit_laps == [18]


def test_stacked_applies_all_three():
    out = stacked_constraints(_aris(), _team())
    assert out.start_compound == "SOFT"
    assert out.pit_laps[0] == 18
    assert len(out.pit_laps) == 2


def test_extra_stops_drop_sc_from_count_only():
    aris = _aris()
    team = _team()
    assert extra_stops(aris, team) == 1
    assert extra_stops_ex_sc_vsc(aris, team, [40]) == 0


def test_equal_schedules_position_delta_zero():
    state = _sample_state(lap_number=1, laps_remaining=56, total_laps=57, compound="MEDIUM")
    sched = PitSchedule(pit_laps=[24], pit_compounds=["HARD"], start_compound="MEDIUM")
    field = {"VER": 5000.0, "HAM": 5010.0, "LEC": 5020.0}
    scored = score_schedules(
        field,
        "HAM",
        actual_time_s=5010.0,
        start_state=state,
        aris=sched,
        team=sched,
    )
    assert scored["position_delta"] == 0.0


def test_summarize_splits_clean_and_disrupted():
    rows = [
        {
            "major_disruption": False,
            "extra_stops": 1,
            "extra_stops_ex_sc_vsc": 0,
            "variants": {
                "baseline": {"position_delta": -1.0},
                "start_compound": {"position_delta": -1.0},
                "first_stop": {"position_delta": 0.0},
                "pit_count": {"position_delta": 0.0},
                "stacked": {"position_delta": 0.0},
            },
        },
        {
            "major_disruption": True,
            "extra_stops": 2,
            "extra_stops_ex_sc_vsc": 1,
            "variants": {
                "baseline": {"position_delta": -2.0},
                "start_compound": {"position_delta": -2.0},
                "first_stop": {"position_delta": -1.0},
                "pit_count": {"position_delta": -1.0},
                "stacked": {"position_delta": -1.0},
            },
        },
    ]
    summary = summarize_ablation(rows)
    assert summary["n_races"] == 2
    assert summary["n_clean"] == 1
    assert summary["n_disrupted"] == 1
    assert summary["not_fia_points"] is True
    assert summary["variants"]["baseline"]["all"]["mean"] == pytest.approx(-1.5)
    assert summary["variants"]["first_stop"]["delta_vs_baseline_mean"] == pytest.approx(1.0)
