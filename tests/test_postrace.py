"""Tests for post-race ARIS vs actual comparison (no DB)."""

import pandas as pd

from aris.decisions.queue import DecisionKind, DecisionQueue, DecisionRecord
from aris.engine.session import PitCommitment, RaceEngineSession, SessionPhase
from aris.eval.postrace import (
    PitSchedule,
    actual_schedule,
    aris_schedule,
    estimate_position,
    schedule_from_commitments,
    schedule_from_plan,
)
from aris.plan.prewrite import StratPlan
from aris.recommend import Recommendation
from aris.simulate import ActionKind, StrategyAction


def _session(**kwargs) -> RaceEngineSession:
    defaults = dict(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        team="RBR",
        year=2024,
        round_no=1,
        country="Bahrain",
        total_laps=57,
        phase=SessionPhase.POST_RACE,
    )
    defaults.update(kwargs)
    return RaceEngineSession(**defaults)


def test_schedule_from_plan_keeps_pits():
    plan = StratPlan(
        id="A",
        name="One-stop",
        pit_laps=[18],
        pit_compounds=["HARD"],
        start_compound="MEDIUM",
    )
    sched = schedule_from_plan(plan)
    assert sched.pit_laps == [18]
    assert sched.pit_compounds == ["HARD"]
    assert sched.start_compound == "MEDIUM"


def test_aris_schedule_prefers_accepted_recs_over_plan():
    rec = Recommendation(
        rank=1,
        label="Pit lap 22 for HARD",
        action=StrategyAction(kind=ActionKind.PIT_LAP, pit_lap=22, pit_compound="HARD"),
        delta_vs_stay_out_s=-5.0,
        mean_race_time_s=5000.0,
        confidence_std_s=1.0,
        p10_delta_s=-8.0,
        p90_delta_s=-2.0,
        evidence="test",
        narration_context={},
    )
    q = DecisionQueue()
    q.decisions.append(
        DecisionRecord(
            kind=DecisionKind.PIT,
            lap=15,
            accepted=True,
            choice_id="yes",
            recommendation=rec,
        )
    )
    session = _session(
        decision_queue=q,
        active_strat=StratPlan(
            id="A", name="x", pit_laps=[18], pit_compounds=["HARD"]
        ),
    )
    sched = aris_schedule(session, "SOFT")
    assert sched.pit_laps == [22]
    assert sched.pit_compounds == ["HARD"]


def test_aris_schedule_falls_back_to_locked_plan():
    session = _session(
        active_strat=StratPlan(
            id="B", name="late", pit_laps=[29], pit_compounds=["HARD"],
            start_compound="MEDIUM",
        )
    )
    sched = aris_schedule(session, "SOFT")
    assert sched.pit_laps == [29]
    assert sched.start_compound == "MEDIUM"


def test_aris_schedule_stay_out_when_nothing_chosen():
    sched = aris_schedule(_session(), "MEDIUM")
    assert sched.pit_laps == []
    assert sched.start_compound == "MEDIUM"


def test_user_schedule_none_without_commitments():
    assert schedule_from_commitments([], "MEDIUM") is None


def test_user_schedule_from_commitments():
    pits = [PitCommitment(lap=20, compound="HARD", source="engineer")]
    sched = schedule_from_commitments(pits, "SOFT")
    assert sched is not None
    assert sched.pit_laps == [20]
    assert sched.pit_compounds == ["HARD"]


def test_actual_schedule_uses_next_lap_compound():
    laps = pd.DataFrame(
        [
            {"lap_number": 1, "compound": "SOFT", "pit_in": False, "lap_time_s": 90.0},
            {"lap_number": 15, "compound": "SOFT", "pit_in": True, "lap_time_s": 95.0},
            {"lap_number": 16, "compound": "HARD", "pit_in": False, "lap_time_s": 92.0},
        ]
    )
    sched = actual_schedule(laps)
    assert sched.pit_laps == [15]
    assert sched.pit_compounds == ["HARD"]
    assert sched.start_compound == "SOFT"


def test_estimate_position_can_gain_or_lose():
    field = {"VER": 5000.0, "HAM": 5010.0, "LEC": 5020.0}
    assert estimate_position(field, "HAM", 4990.0) == 1
    assert estimate_position(field, "HAM", 5010.0) == 2
    assert estimate_position(field, "HAM", 5030.0) == 3


def test_project_aris_finish_does_not_invent_p1():
    from aris.eval.postrace import project_aris_finish

    field = {
        "VER": 5000.0,
        "NOR": 5010.0,
        "LEC": 5020.0,
        "PIA": 5030.0,
        "SAI": 5040.0,
        "HAM": 5050.0,
    }
    # Equal sims must keep classified P6, not jump to P1.
    pos = project_aris_finish(
        field,
        "HAM",
        actual_time_s=5050.0,
        aris_sim_s=6120.0,
        team_sim_s=6120.0,
        classified_pos=6,
    )
    assert pos == 6


def test_project_aris_finish_falls_back_to_classified_without_sims():
    from aris.eval.postrace import project_aris_finish

    pos = project_aris_finish(
        {},
        "HAM",
        actual_time_s=None,
        aris_sim_s=None,
        team_sim_s=None,
        classified_pos=6,
    )
    assert pos == 6


def test_bias_cancel_identity_zero_when_sims_equal():
    """R2.3: ARIS_sim == team_sim must yield position-delta 0 on the time-rank field."""
    from aris.eval.postrace import bias_cancelled_delta

    field = {
        "VER": 5000.0,
        "NOR": 5010.0,
        "LEC": 5020.0,
        "PIA": 5030.0,
        "SAI": 5040.0,
        "HAM": 5050.0,
    }
    aris_pos, actual_rank, delta = bias_cancelled_delta(
        field,
        "SAI",
        actual_time_s=5040.0,
        aris_sim_s=6120.0,
        team_sim_s=6120.0,
    )
    assert actual_rank == 5
    assert aris_pos == 5
    assert delta == 0.0


def test_bias_cancel_negative_delta_when_aris_sim_faster():
    from aris.eval.postrace import bias_cancelled_delta

    field = {
        "VER": 5000.0,
        "NOR": 5010.0,
        "LEC": 5020.0,
        "PIA": 5030.0,
        "SAI": 5040.0,
    }
    _aris_pos, _actual_rank, delta = bias_cancelled_delta(
        field,
        "SAI",
        actual_time_s=5040.0,
        aris_sim_s=100.0,
        team_sim_s=130.0,
    )
    assert delta == -2.0


def test_aris_and_actual_schedules_are_not_forced_equal():
    """The original bug: both ARIS and actual times were the real result."""
    aris = PitSchedule(pit_laps=[18], pit_compounds=["HARD"], start_compound="MEDIUM")
    actual = PitSchedule(pit_laps=[25], pit_compounds=["HARD"], start_compound="MEDIUM")
    assert aris.pit_laps != actual.pit_laps
