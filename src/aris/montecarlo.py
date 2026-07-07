"""Slim Monte Carlo layer — sample pace + pit-loss variance."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from aris.simulate import PACE_SIGMA_S, ActionKind, StrategyAction, simulate
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
    return f"Pit L{action.pit_lap} -> {action.pit_compound or 'HARD'}"


def run_mc(
    state: RaceState,
    action: StrategyAction,
    *,
    n_draws: int = DEFAULT_DRAWS,
    seed: int = 42,
) -> MCDistribution:
    rng = np.random.default_rng(seed)
    baseline = simulate(state, StrategyAction(kind=ActionKind.STAY_OUT))

    totals: list[float] = []
    for _ in range(n_draws):
        outcome = simulate(state, action)
        noise = rng.normal(0.0, PACE_SIGMA_S) * outcome.laps_simulated
        pit_noise = rng.normal(0.0, 0.5) if action.kind != ActionKind.STAY_OUT else 0.0
        totals.append(outcome.total_race_time_s + noise + pit_noise)

    arr = np.array(totals)
    return MCDistribution(
        strategy_label=_action_label(action),
        mean_time_s=float(arr.mean()),
        std_time_s=float(arr.std()),
        p10_time_s=float(np.percentile(arr, 10)),
        p90_time_s=float(np.percentile(arr, 90)),
        mean_delta_vs_stay_out_s=float(arr.mean() - baseline.total_race_time_s),
        n_draws=n_draws,
    )
