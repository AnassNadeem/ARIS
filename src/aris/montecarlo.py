"""Slim Monte Carlo layer — per-lap pace variance."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from aris.simulate import (
    PACE_SIGMA_S,
    ActionKind,
    StrategyAction,
    _pit_schedule,
    _simulate_remainder,
)
from aris.state import RaceState

DEFAULT_DRAWS = 100


class MCDistribution(BaseModel):
    strategy_label: str
    mean_time_s: float
    std_time_s: float
    p10_time_s: float
    p90_time_s: float
    mean_delta_vs_stay_out_s: float
    n_draws: int = DEFAULT_DRAWS


def _action_label(action: StrategyAction) -> str:
    if action.kind == ActionKind.STAY_OUT:
        return "Stay out"
    if action.kind == ActionKind.PIT_NOW:
        return f"Pit now -> {action.pit_compound or 'HARD'}"
    if action.kind == ActionKind.LIFT:
        return f"Lift {action.distance_m or 0:.0f}m into T{action.corner_index}"
    if action.kind == ActionKind.BRAKE:
        return f"Brake {action.distance_m or 0:.0f}m earlier into T{action.corner_index}"
    if action.pit_laps:
        return f"Pits {action.pit_laps} -> {action.pit_compounds}"
    return f"Pit L{action.pit_lap} -> {action.pit_compound or 'HARD'}"


def _simulate_with_draw(
    state: RaceState, action: StrategyAction, rng: np.random.Generator
) -> float:
    n_laps = max(1, state.laps_remaining)
    noise = rng.normal(0.0, PACE_SIGMA_S, size=n_laps).tolist()
    schedule = _pit_schedule(action, state)
    if action.kind != ActionKind.STAY_OUT:
        pit_noise = rng.normal(0.0, 0.5)
        if noise:
            noise[0] += pit_noise
    total = _simulate_remainder(state, pit_schedule=schedule, pace_noise=noise).total
    return total


def run_mc(
    state: RaceState,
    action: StrategyAction,
    *,
    n_draws: int = DEFAULT_DRAWS,
    seed: int = 42,
) -> MCDistribution:
    rng = np.random.default_rng(seed)
    baseline = _simulate_with_draw(state, StrategyAction(kind=ActionKind.STAY_OUT), rng)

    totals: list[float] = []
    for _ in range(n_draws):
        totals.append(_simulate_with_draw(state, action, rng))

    arr = np.array(totals)
    return MCDistribution(
        strategy_label=_action_label(action),
        mean_time_s=float(arr.mean()),
        std_time_s=float(arr.std()),
        p10_time_s=float(np.percentile(arr, 10)),
        p90_time_s=float(np.percentile(arr, 90)),
        mean_delta_vs_stay_out_s=float(arr.mean() - baseline),
        n_draws=n_draws,
    )
