"""Tests for decision queue."""

from aris.decisions.queue import DecisionKind, DecisionQueue
from aris.state import RaceState


def _state() -> RaceState:
    return RaceState(
        session_id=1, driver_id=1, driver_code="HAM", driver_name="Lewis",
        year=2025, round_no=1, country="Bahrain",
        lap_number=10, compound="MEDIUM", tyre_life=10,
        fuel_kg=80.0, laps_remaining=47,
        lag1_pace=95.0, lag2_pace=95.1, stint_roll3=95.0,
    )


class TestDecisionQueue:
    def test_propose_and_resolve(self):
        q = DecisionQueue()
        turn = q.propose(_state(), kind=DecisionKind.PIT, use_llm=False)
        assert turn.role == "aris"
        assert len(turn.options) >= 2
        record = q.resolve("yes", kind=DecisionKind.PIT, lap=10)
        assert record.accepted
        assert q.pending is None

    def test_engineer_message(self):
        q = DecisionQueue()
        q.push_engineer("Copy, boxing lap 12.")
        assert q.history[-1].role == "engineer"
