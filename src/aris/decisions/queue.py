"""Conversational decision queue for always-on race engineer."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, PrivateAttr

from aris.decisions.persist import JsonlDecisionLog, dump_recommendation
from aris.narrate import narrate_recommendation
from aris.recommend import Recommendation, recommend
from aris.state import RaceState


class DecisionKind(StrEnum):
    CONFIRM_STRAT = "confirm_strat"
    PIT = "pit"
    TACTICAL = "tactical"
    SC = "safety_car"
    MANUAL_PIT = "manual_pit"


class DecisionOption(BaseModel):
    id: str
    label: str
    recommended: bool = False


class DecisionTurn(BaseModel):
    role: Literal["aris", "engineer"]
    text: str
    kind: DecisionKind | None = None
    options: list[DecisionOption] = Field(default_factory=list)
    recommended_option_id: str | None = None
    editable_fields: dict[str, Any] = Field(default_factory=dict)
    recommendation: Recommendation | None = None


class DecisionRecord(BaseModel):
    kind: DecisionKind
    lap: int
    accepted: bool
    choice_id: str
    recommendation: Recommendation | None = None
    edited_fields: dict[str, Any] = Field(default_factory=dict)


class DecisionQueue(BaseModel):
    history: list[DecisionTurn] = Field(default_factory=list)
    pending: DecisionTurn | None = None
    decisions: list[DecisionRecord] = Field(default_factory=list)
    _log: JsonlDecisionLog | None = PrivateAttr(default=None)

    def bind_log(self, log: JsonlDecisionLog | None) -> None:
        """Attach an append-only store. None disables persistence for this queue."""
        self._log = log

    def has_log(self) -> bool:
        return self._log is not None

    def push_engineer(self, text: str) -> None:
        self.history.append(DecisionTurn(role="engineer", text=text))

    def propose(
        self,
        state: RaceState,
        *,
        kind: DecisionKind,
        use_llm: bool = False,
        mc_draws: int | None = None,
    ) -> DecisionTurn:
        kwargs: dict[str, Any] = {"top_k": 3}
        if mc_draws is not None:
            kwargs["mc_draws"] = mc_draws
        result = recommend(state, **kwargs)
        top = result.recommendations[0] if result.recommendations else None
        if top is None:
            turn = DecisionTurn(
                role="aris",
                text="No recommendation available.",
                kind=kind,
            )
        else:
            radio = narrate_recommendation(top, use_llm=use_llm)
            options = [
                DecisionOption(id="yes", label="Yes", recommended=True),
                DecisionOption(id="no", label="No"),
                DecisionOption(id="edit", label="Edit"),
            ]
            editable: dict[str, Any] = {}
            if kind in (DecisionKind.PIT, DecisionKind.MANUAL_PIT):
                pit_lap = (
                    top.action.pit_lap
                    or (state.lap_number + 1)
                )
                editable = {
                    "pit_lap": pit_lap,
                    "compound": top.action.pit_compound or state.pit_compound,
                }
            turn = DecisionTurn(
                role="aris",
                text=radio,
                kind=kind,
                options=options,
                recommended_option_id="yes",
                editable_fields=editable,
                recommendation=top,
            )
        self.pending = turn
        self.history.append(turn)
        self._persist(
            "propose",
            {
                "kind": kind.value,
                "lap": state.lap_number,
                "recommendation": dump_recommendation(top),
                "candidates": [dump_recommendation(r) for r in result.recommendations],
            },
        )
        return turn

    def resolve(
        self,
        choice_id: str,
        *,
        kind: DecisionKind,
        lap: int,
        edited_fields: dict[str, Any] | None = None,
    ) -> DecisionRecord:
        if self.pending is None:
            raise ValueError("no pending decision")
        accepted = choice_id == "yes" or choice_id == "confirm"
        record = DecisionRecord(
            kind=kind,
            lap=lap,
            accepted=accepted or choice_id == "edit",
            choice_id=choice_id,
            recommendation=self.pending.recommendation,
            edited_fields=edited_fields or {},
        )
        self.decisions.append(record)
        self.pending = None
        self._persist(
            "resolve",
            {
                "kind": kind.value,
                "lap": lap,
                "accepted": record.accepted,
                "choice_id": choice_id,
                "recommendation": dump_recommendation(record.recommendation),
                "edited_fields": record.edited_fields,
            },
        )
        return record

    def _persist(self, event: str, payload: dict[str, Any]) -> None:
        if self._log is None:
            return
        self._log.append(event, payload)
