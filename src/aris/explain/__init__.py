"""T12 explainability — degradation curves, ghost vs real, race debrief.

Read-only over existing ``recommend()`` / ``simulate()`` internals.
Does not change strategy logic.
"""

from aris.explain.debrief import get_race_debrief
from aris.explain.degradation import get_degradation_curve
from aris.explain.ghost import get_ghost_lap_ticks, get_ghost_vs_real

__all__ = [
    "get_degradation_curve",
    "get_ghost_vs_real",
    "get_ghost_lap_ticks",
    "get_race_debrief",
]
