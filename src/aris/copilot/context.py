"""Live/replay context injected into Copilot tools (the LLM never sends RaceState)."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field

from aris.state import RaceState


@dataclass
class FieldCar:
    driver_code: str
    position: int | None = None
    gap_to_leader_s: float | None = None
    gap_ahead_s: float | None = None
    gap_behind_s: float | None = None
    compound: str | None = None
    tyre_life: int | None = None
    last_lap_s: float | None = None
    name: str | None = None


@dataclass
class CopilotContext:
    state: RaceState | None = None
    field: list[FieldCar] = field(default_factory=list)
    session_id: str | None = None
    use_llm: bool = False

    def car(self, code: str) -> FieldCar | None:
        needle = (code or "").upper()
        for row in self.field:
            if row.driver_code.upper() == needle:
                return row
        return None

    def car_at_position(self, position: int) -> FieldCar | None:
        for row in self.field:
            if row.position == position:
                return row
        return None


_CTX: ContextVar[CopilotContext | None] = ContextVar("aris_copilot_ctx", default=None)


def set_context(ctx: CopilotContext | None) -> None:
    _CTX.set(ctx)


def get_context() -> CopilotContext:
    ctx = _CTX.get()
    if ctx is None:
        ctx = CopilotContext()
        _CTX.set(ctx)
    return ctx


def require_state() -> RaceState:
    state = get_context().state
    if state is None:
        raise RuntimeError("Copilot has no RaceState for this session")
    return state
