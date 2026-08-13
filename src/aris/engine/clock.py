"""Sector clock — auto-advance replay index."""

from __future__ import annotations

import os
import time
import warnings
from dataclasses import dataclass

from aris.field.state import FieldState, ReplayIndex

FAST_CLOCK_ENV = "ARIS_FAST_CLOCK"
FAST_CLOCK_WARNING = (
    "ARIS_FAST_CLOCK=1 is set — the sector clock ticks on every rerun instead "
    "of the 25 s cadence. Unset it for a real demo or deployment. "
    "This flag is screenshot/harness-only."
)


def fast_clock_enabled() -> bool:
    """True only when ARIS_FAST_CLOCK=1. Absent or any other value is off."""
    return os.getenv(FAST_CLOCK_ENV) == "1"


@dataclass
class SectorEvent:
    index: ReplayIndex
    field: FieldState
    is_new_lap: bool
    is_race_complete: bool


class SectorClock:
    """Sector-by-sector replay clock with speed control."""

    def __init__(
        self,
        all_laps,
        *,
        session_id: int,
        total_laps: int,
        base_sector_s: float = 25.0,
    ) -> None:
        self._all_laps = all_laps
        self._session_id = session_id
        self._total_laps = total_laps
        self._base_sector_s = base_sector_s
        self.index = ReplayIndex(1, 0)
        self.speed = 1.0
        self.paused = False
        self._last_tick = time.monotonic()
        if fast_clock_enabled():
            warnings.warn(FAST_CLOCK_WARNING, UserWarning, stacklevel=2)

    def set_speed(self, multiplier: float) -> None:
        self.speed = max(0.0, multiplier)
        self.paused = multiplier == 0.0

    def should_tick(self) -> bool:
        if self.paused or self.speed <= 0:
            return False
        # Screenshot / UI harness only. Default demo path is unchanged.
        if fast_clock_enabled():
            self._last_tick = time.monotonic()
            return True
        now = time.monotonic()
        interval = self._base_sector_s / self.speed
        if now - self._last_tick >= interval:
            self._last_tick = now
            return True
        return False

    def tick(self) -> SectorEvent:
        prev_lap = self.index.lap_number
        self.index = self.index.advance(self._total_laps)
        field = FieldState.from_laps(
            self._all_laps,
            session_id=self._session_id,
            index=self.index,
            total_laps=self._total_laps,
        )
        complete = self.index.is_done(self._total_laps)
        return SectorEvent(
            index=self.index,
            field=field,
            is_new_lap=self.index.lap_number != prev_lap,
            is_race_complete=complete,
        )

    def current_field(self) -> FieldState:
        return FieldState.from_laps(
            self._all_laps,
            session_id=self._session_id,
            index=self.index,
            total_laps=self._total_laps,
        )
