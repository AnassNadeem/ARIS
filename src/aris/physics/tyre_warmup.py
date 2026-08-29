"""Tyre warm-up penalty constants for out-lap modelling.

Derived from FastF1 out-lap data (2023–2025 median first-lap delta vs
steady-state G1.5 slope for each compound). Used as fixed priors; can be
fitted per-circuit in a later phase.

The penalty is *additive* on top of the G1.5 compound slopes — it represents
the time cost of a cold tyre during the out-lap phase (laps 1–2 of a new
stint). Do NOT modify G1.5 slope constants.
"""

from __future__ import annotations

# (lap_1_penalty_s, lap_2_penalty_s) relative to steady-state pace.
# HARD takes longer to reach operating window; SOFT comes in fast.
_WARMUP_COSTS: dict[str, tuple[float, float]] = {
    "HARD": (0.8, 0.3),
    "MEDIUM": (0.5, 0.2),
    "SOFT": (0.2, 0.0),
    "INTERMEDIATE": (1.5, 0.5),
    "INTER": (1.5, 0.5),
    "WET": (1.5, 0.5),
}

_DEFAULT_COSTS: tuple[float, float] = (0.5, 0.2)


def tyre_warmup_penalty(compound: str, circuit_type: str = "standard") -> float:
    """Total warm-up penalty for the first two laps on a fresh set.

    Returns the sum of lap-1 and lap-2 penalties in seconds (always ≥ 0).
    ``circuit_type`` is reserved for future per-circuit fitting; currently a
    no-op (all circuits use the same constants).

    HARD:  +0.8s lap 1, +0.3s lap 2 → total +1.1s
    MEDIUM: +0.5s lap 1, +0.2s lap 2 → total +0.7s
    SOFT:   +0.2s lap 1, +0.0s lap 2 → total +0.2s
    INTER/WET: +1.5s lap 1, +0.5s lap 2 → total +2.0s
    """
    del circuit_type  # reserved for per-circuit fitting
    costs = _WARMUP_COSTS.get(str(compound).upper().strip(), _DEFAULT_COSTS)
    return float(costs[0] + costs[1])


def tyre_warmup_lap1(compound: str) -> float:
    """Penalty for lap 1 only (out-lap)."""
    costs = _WARMUP_COSTS.get(str(compound).upper().strip(), _DEFAULT_COSTS)
    return float(costs[0])


def tyre_warmup_lap2(compound: str) -> float:
    """Penalty for lap 2 only (second lap on fresh rubber)."""
    costs = _WARMUP_COSTS.get(str(compound).upper().strip(), _DEFAULT_COSTS)
    return float(costs[1])


def tyre_warmup_for_lap(compound: str, lap_in_stint: int) -> float:
    """Warm-up penalty for a given lap of a new stint (0 after lap 2)."""
    life = int(lap_in_stint)
    if life <= 1:
        return tyre_warmup_lap1(compound)
    if life == 2:
        return tyre_warmup_lap2(compound)
    return 0.0


def apply_warmup(
    lap_time: float,
    compound: str,
    lap_in_stint: int,
    is_out_lap: bool = False,
) -> float:
    """Add the compound warm-up penalty for this stint lap to ``lap_time``."""
    life = 1 if is_out_lap else int(lap_in_stint)
    return float(lap_time) + tyre_warmup_for_lap(compound, life)
