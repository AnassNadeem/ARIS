"""Race Control FSM — T6.

Maps OpenF1 track_status codes and RaceState boolean flags to PhaseConfig
objects that override pit-loss, degradation, and strategy behavior in
simulate() and recommend().
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aris.state import RaceState


class RacePhase(Enum):
    GREEN = auto()
    VSC = auto()           # Virtual Safety Car
    SC = auto()            # Full Safety Car
    RED_FLAG = auto()
    FORMATION_LAP = auto() # Extra formation lap (e.g. Zandvoort 2025)
    STANDING_START = auto()


@dataclass(frozen=True)
class PhaseConfig:
    """Everything that changes when the race phase changes.

    These configs override the default values in simulate() and recommend().
    """

    phase: RacePhase

    # Pit stop timing
    pit_loss_multiplier: float   # 1.0 = full pit loss, 0.5 = halved under SC
    pit_loss_override: float     # -1 = use multiplier, else exact override value

    # Tyre degradation
    deg_multiplier: float        # 0.0 = degradation paused (SC), 1.0 = normal

    # Strategy resets
    strategy_reset: bool         # True = flush active strategies (RED_FLAG)
    free_tyre_change: bool       # True = RED_FLAG free compound change

    # Pace targeting
    pace_target_active: bool     # False = do not generate pace target narration
    delta_mode: bool             # True = pace is delta-limited (VSC/SC)
    delta_fraction: float        # Fraction of normal pace target


PHASE_CONFIGS: dict[RacePhase, PhaseConfig] = {
    RacePhase.GREEN: PhaseConfig(
        phase=RacePhase.GREEN,
        pit_loss_multiplier=1.0,
        pit_loss_override=-1,
        deg_multiplier=1.0,
        strategy_reset=False,
        free_tyre_change=False,
        pace_target_active=True,
        delta_mode=False,
        delta_fraction=1.0,
    ),
    RacePhase.VSC: PhaseConfig(
        phase=RacePhase.VSC,
        pit_loss_multiplier=0.55,  # pit lane relatively cheaper — track still moving
        pit_loss_override=-1,
        deg_multiplier=0.15,       # minimal deg at VSC pace
        strategy_reset=False,
        free_tyre_change=False,
        pace_target_active=False,
        delta_mode=True,
        delta_fraction=0.40,
    ),
    RacePhase.SC: PhaseConfig(
        phase=RacePhase.SC,
        pit_loss_multiplier=0.50,  # cheap pit window — pit loss effectively halved
        pit_loss_override=-1,
        deg_multiplier=0.0,        # degradation paused under SC
        strategy_reset=False,
        free_tyre_change=False,
        pace_target_active=False,
        delta_mode=True,
        delta_fraction=0.60,
    ),
    RacePhase.RED_FLAG: PhaseConfig(
        phase=RacePhase.RED_FLAG,
        pit_loss_multiplier=0.0,
        pit_loss_override=0.0,     # free tyre change — no pit loss
        deg_multiplier=0.0,
        strategy_reset=True,
        free_tyre_change=True,
        pace_target_active=False,
        delta_mode=False,
        delta_fraction=0.0,
    ),
    RacePhase.FORMATION_LAP: PhaseConfig(
        phase=RacePhase.FORMATION_LAP,
        pit_loss_multiplier=1.0,   # pitting on a formation lap is rare and costly
        pit_loss_override=-1,
        deg_multiplier=0.05,       # minimal deg on formation lap
        strategy_reset=False,
        free_tyre_change=False,
        pace_target_active=False,
        delta_mode=False,
        delta_fraction=0.0,
    ),
    RacePhase.STANDING_START: PhaseConfig(
        phase=RacePhase.STANDING_START,
        pit_loss_multiplier=1.0,
        pit_loss_override=-1,
        deg_multiplier=0.0,        # lap counters reset conceptually after standing start
        strategy_reset=True,       # drop prior lap deltas — circuit is different now
        free_tyre_change=False,
        pace_target_active=False,
        delta_mode=False,
        delta_fraction=1.0,
    ),
}


def get_phase_config(race_state: "RaceState") -> PhaseConfig:
    """Determine the current PhaseConfig from RaceState.

    Boolean flags (standing_start, formation_lap) take priority over
    track_status codes. Track status drives SC/VSC/RED_FLAG detection.

    OpenF1 track_status values:
        "1" / "AllClear"             → GREEN
        "2" / "Yellow"               → GREEN (local yellow, no neutralisation)
        "4" / "SafetyCar"            → SC
        "5" / "VirtualSafetyCar"     → VSC
        "6" / "VirtualSafetyCarEnding" → VSC (still delta-limited until green)
        "7" / "RedFlag"              → RED_FLAG
    """
    if getattr(race_state, "standing_start", False):
        return PHASE_CONFIGS[RacePhase.STANDING_START]
    if getattr(race_state, "formation_lap", False):
        return PHASE_CONFIGS[RacePhase.FORMATION_LAP]

    status = str(race_state.track_status or "1").strip()

    if status in ("7", "RedFlag"):
        return PHASE_CONFIGS[RacePhase.RED_FLAG]

    if status in ("4", "SafetyCar"):
        return PHASE_CONFIGS[RacePhase.SC]

    if status in ("5", "6", "VirtualSafetyCar", "VirtualSafetyCarEnding"):
        return PHASE_CONFIGS[RacePhase.VSC]

    # "1" AllClear, "2" Yellow (local), or unknown → GREEN
    return PHASE_CONFIGS[RacePhase.GREEN]
