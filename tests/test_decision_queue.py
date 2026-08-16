"""Tests for decision queue."""

import json

from aris.decisions.persist import JsonlDecisionLog
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
        turn = q.propose(_state(), kind=DecisionKind.PIT, use_llm=False, mc_draws=0)
        assert turn.role == "aris"
        assert len(turn.options) >= 2
        record = q.resolve("yes", kind=DecisionKind.PIT, lap=10)
        assert record.accepted
        assert q.pending is None

    def test_engineer_message(self):
        q = DecisionQueue()
        q.push_engineer("Copy, boxing lap 12.")
        assert q.history[-1].role == "engineer"

    def test_unbound_queue_does_not_require_log(self):
        q = DecisionQueue()
        assert not q.has_log()

    def test_propose_resolve_persist_jsonl(self, tmp_path):
        path = tmp_path / "events.jsonl"
        q = DecisionQueue()
        q.bind_log(JsonlDecisionLog(path, source="test"))
        q.propose(_state(), kind=DecisionKind.PIT, use_llm=False, mc_draws=0)
        q.resolve("yes", kind=DecisionKind.PIT, lap=10)
        lines = path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        events = [json.loads(line) for line in lines]
        assert events[0]["event"] == "propose"
        assert events[0]["kind"] == "pit"
        assert events[0]["source"] == "test"
        assert events[1]["event"] == "resolve"
        assert events[1]["accepted"] is True
        assert events[1]["choice_id"] == "yes"

    def test_unwritable_log_fails_loudly(self, tmp_path):
        """Write failures must raise, not drop the event silently."""
        blocked = tmp_path / "not_a_directory"
        blocked.write_text("x", encoding="utf-8")
        q = DecisionQueue()
        q.bind_log(JsonlDecisionLog(blocked / "events.jsonl", source="test"))
        try:
            q.propose(_state(), kind=DecisionKind.PIT, use_llm=False, mc_draws=0)
        except RuntimeError as exc:
            assert "decision log write failed" in str(exc)
            assert "propose" in str(exc)
        else:
            raise AssertionError("expected RuntimeError on unwritable decision log")
