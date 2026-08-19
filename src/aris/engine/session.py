"""Race engineer session — game state parallel to replay."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from aris.decisions.persist import JsonlDecisionLog, decision_log_enabled
from aris.decisions.queue import DecisionQueue, DecisionRecord
from aris.field.state import FieldState, ReplayIndex
from aris.plan.prewrite import StratPlan
from aris.state import RaceState, build_race_state


class SessionPhase(StrEnum):
    SETUP = "setup"
    PRE_RACE = "pre_race"
    LIVE = "live"
    POST_RACE = "post_race"


class PitCommitment(BaseModel):
    lap: int
    compound: str
    source: str = "aris"


class RaceEngineSession(BaseModel):
    session_id: int
    driver_id: int
    driver_code: str
    team: str | None = None
    year: int
    round_no: int
    country: str
    total_laps: int
    phase: SessionPhase = SessionPhase.SETUP
    active_strat: StratPlan | None = None
    committed_pits: list[PitCommitment] = Field(default_factory=list)
    synthetic_compound: str | None = None
    synthetic_tyre_life: int | None = None
    decision_queue: DecisionQueue = Field(default_factory=DecisionQueue)
    replay_index: ReplayIndex = Field(default_factory=lambda: ReplayIndex(1, 0))
    clock_speed: float = 1.0
    paused: bool = False
    field_state: FieldState | None = None
    triggered_laps: set[int] = Field(default_factory=set)
    fired_this_lap: set[str] = Field(default_factory=set)
    last_trigger_lap: int = 0

    def model_post_init(self, __context: Any) -> None:
        # Live + backtest sessions persist propose/resolve past process end.
        # Bare DecisionQueue (unit tests) stays memory-only until bind_log.
        if decision_log_enabled() and not self.decision_queue.has_log():
            log = JsonlDecisionLog.for_session(
                session_id=self.session_id,
                driver_code=self.driver_code,
                year=self.year,
                round_no=self.round_no,
                source="live",
            )
            log.meta = {
                "session_id": self.session_id,
                "driver_id": self.driver_id,
                "driver_code": self.driver_code,
                "year": self.year,
                "round_no": self.round_no,
                "country": self.country,
            }
            self.decision_queue.bind_log(log)

    def gaps_for_driver(self) -> dict[str, Any]:
        if self.field_state is None:
            return {}
        row = self.field_state.standing_for(self.driver_id)
        if row is None:
            return {}
        return {
            "position": row.position,
            "gap_to_leader_s": row.gap_to_leader_s,
            "gap_ahead_s": row.gap_ahead_s,
            "gap_behind_s": row.gap_behind_s,
        }

    def build_state(self, lap_number: int | None = None) -> RaceState:
        lap = lap_number or max(1, self.replay_index.lap_number)
        try:
            state = build_race_state(
                self.session_id,
                self.driver_id,
                lap,
                field_gaps=self.gaps_for_driver(),
            )
        except ValueError:
            # Focus driver retired / DNF / missing lap while the field clock
            # continues — clamp to their last recorded lap so Watch/What-if
            # panels keep working instead of crashing the Strategy UI.
            from aris.io import db as _db

            laps = _db.fetch_laps(self.session_id, self.driver_id)
            if laps.empty:
                raise
            last = int(laps["lap_number"].max())
            state = build_race_state(
                self.session_id,
                self.driver_id,
                last,
                field_gaps=self.gaps_for_driver(),
            )
        if self.synthetic_compound:
            state = state.model_copy(update={"compound": self.synthetic_compound})
        if self.synthetic_tyre_life is not None:
            state = state.model_copy(update={"tyre_life": self.synthetic_tyre_life})
        return state

    def commit_pit(self, lap: int, compound: str, source: str = "engineer") -> None:
        self.committed_pits.append(PitCommitment(lap=lap, compound=compound, source=source))
        self.synthetic_compound = compound
        self.synthetic_tyre_life = 1

    def record_decision(self, record: DecisionRecord) -> None:
        if record.accepted and record.recommendation:
            rec = record.recommendation
            action = rec.action
            if action.pit_lap:
                compound = (
                    record.edited_fields.get("compound")
                    or action.pit_compound
                    or "HARD"
                )
                pit_lap = int(record.edited_fields.get("pit_lap", action.pit_lap))
                self.commit_pit(pit_lap, str(compound))
            elif action.kind.value == "pit_now":
                compound = str(
                    record.edited_fields.get("compound")
                    or action.pit_compound
                    or "HARD"
                )
                pit_lap = int(record.edited_fields.get("pit_lap", self.replay_index.lap_number))
                self.commit_pit(pit_lap, compound)
