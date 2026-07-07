"""Strategy recommender — enumerate pit windows, score with simulate + MC."""

from __future__ import annotations

from pydantic import BaseModel

from aris.montecarlo import DEFAULT_DRAWS, run_mc
from aris.simulate import ActionKind, StrategyAction, simulate
from aris.state import RaceState

PIT_COMPOUNDS = ("MEDIUM", "HARD")


class Recommendation(BaseModel):
    rank: int
    label: str
    action: StrategyAction
    delta_vs_stay_out_s: float
    mean_race_time_s: float
    confidence_std_s: float
    p10_delta_s: float
    p90_delta_s: float
    evidence: str
    narration_context: dict


class RecommendationResult(BaseModel):
    state_lap: int
    driver_code: str
    compound: str
    recommendations: list[Recommendation]


def _candidate_actions(state: RaceState) -> list[StrategyAction]:
    actions: list[StrategyAction] = [
        StrategyAction(kind=ActionKind.STAY_OUT),
        StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=state.pit_compound),
    ]
    for offset in (1, 2, 3, 5):
        pit_lap = state.lap_number + offset
        if pit_lap > state.total_laps:
            continue
        for compound in PIT_COMPOUNDS:
            actions.append(
                StrategyAction(
                    kind=ActionKind.PIT_LAP,
                    pit_lap=pit_lap,
                    pit_compound=compound,
                )
            )
    return actions


def _label_for(action: StrategyAction) -> str:
    if action.kind == ActionKind.STAY_OUT:
        return "Stay out on current tyres"
    if action.kind == ActionKind.PIT_NOW:
        return f"Pit now for {action.pit_compound}"
    return f"Pit lap {action.pit_lap} for {action.pit_compound}"


def recommend(
    state: RaceState,
    *,
    top_k: int = 3,
    mc_draws: int = DEFAULT_DRAWS,
) -> RecommendationResult:
    scored: list[Recommendation] = []

    for action in _candidate_actions(state):
        outcome = simulate(state, action)
        mc = run_mc(state, action, n_draws=mc_draws)
        baseline = outcome.total_race_time_s - outcome.delta_vs_stay_out_s
        scored.append(
            Recommendation(
                rank=0,
                label=_label_for(action),
                action=action,
                delta_vs_stay_out_s=mc.mean_delta_vs_stay_out_s,
                mean_race_time_s=mc.mean_time_s,
                confidence_std_s=mc.std_time_s,
                p10_delta_s=mc.p10_time_s - baseline,
                p90_delta_s=mc.p90_time_s - baseline,
                evidence=outcome.evidence,
                narration_context={
                    "driver": state.driver_code,
                    "lap": state.lap_number,
                    "compound": state.compound,
                    "tyre_life": state.tyre_life,
                    "laps_remaining": state.laps_remaining,
                    "strategy": _label_for(action),
                    "delta_s": round(mc.mean_delta_vs_stay_out_s, 2),
                    "confidence_std_s": round(mc.std_time_s, 2),
                },
            )
        )

    scored.sort(key=lambda r: r.delta_vs_stay_out_s)
    top = scored[:top_k]
    for i, rec in enumerate(top, start=1):
        rec.rank = i

    return RecommendationResult(
        state_lap=state.lap_number,
        driver_code=state.driver_code,
        compound=state.compound,
        recommendations=top,
    )
