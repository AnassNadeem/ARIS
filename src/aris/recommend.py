"""Strategy recommender — enumerate pit / line actions, score with simulate + MC."""

from __future__ import annotations

from pydantic import BaseModel

from aris.montecarlo import DEFAULT_DRAWS, run_mc
from aris.simulate import ActionKind, StrategyAction, simulate
from aris.state import RaceState

PIT_COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
UNDERCUT_WINDOW_S = 22.0


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
    tactical: str | None = None


class RecommendationResult(BaseModel):
    state_lap: int
    driver_code: str
    compound: str
    recommendations: list[Recommendation]


def _undercut_bonus(state: RaceState, action: StrategyAction) -> float:
    if action.kind == ActionKind.STAY_OUT:
        return 0.0
    gap_ahead = state.gap_ahead_s
    if gap_ahead is not None and 0 < gap_ahead < UNDERCUT_WINDOW_S:
        return -0.3
    return 0.0


def _candidate_actions(state: RaceState) -> list[StrategyAction]:
    actions: list[StrategyAction] = [
        StrategyAction(kind=ActionKind.STAY_OUT),
        StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=state.pit_compound),
    ]
    for offset in (1, 2, 3, 5, 8):
        pit_lap = state.lap_number + offset
        if pit_lap > state.total_laps:
            continue
        for compound in PIT_COMPOUNDS:
            if compound == "SOFT" and state.laps_remaining < 15:
                continue
            actions.append(
                StrategyAction(
                    kind=ActionKind.PIT_LAP,
                    pit_lap=pit_lap,
                    pit_compound=compound,
                )
            )

    mid = state.total_laps // 2
    for pits, compounds in (
        ([mid, state.total_laps - 8], ["MEDIUM", "HARD"]),
        ([mid - 5, mid + 10], ["SOFT", "HARD"]),
    ):
        valid = all(1 <= p <= state.total_laps for p in pits)
        if valid and pits[0] >= state.lap_number:
            actions.append(
                StrategyAction(
                    kind=ActionKind.STAY_OUT,
                    pit_laps=pits,
                    pit_compounds=compounds,
                )
            )

    # Physics-backed line actions (replaces former hardcoded DRS/defend deltas).
    for corner in (1, 7, 10):
        actions.append(
            StrategyAction(kind=ActionKind.LIFT, corner_index=corner, distance_m=30.0)
        )
        actions.append(
            StrategyAction(kind=ActionKind.BRAKE, corner_index=corner, distance_m=20.0)
        )
    return actions


def _label_for(action: StrategyAction) -> str:
    if action.kind == ActionKind.LIFT and action.corner_index and action.distance_m:
        return f"Lift {action.distance_m:.0f}m into T{action.corner_index}"
    if action.kind == ActionKind.BRAKE and action.corner_index and action.distance_m:
        return f"Brake {action.distance_m:.0f}m earlier into T{action.corner_index}"
    if action.pit_laps and action.pit_compounds:
        stops = ", ".join(
            f"L{p}->{c}" for p, c in zip(action.pit_laps, action.pit_compounds, strict=False)
        )
        return f"Plan: {stops}"
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
    include_tactical: bool = True,
) -> RecommendationResult:
    # include_tactical retained for API compatibility; hardcoded DRS/defend
    # deltas were removed in Phase C — line actions are scored via simulate().
    _ = include_tactical
    scored: list[Recommendation] = []

    for action in _candidate_actions(state):
        outcome = simulate(state, action)
        mc = run_mc(state, action, n_draws=mc_draws)
        baseline = outcome.total_race_time_s - outcome.delta_vs_stay_out_s
        delta = mc.mean_delta_vs_stay_out_s + _undercut_bonus(state, action)
        scored.append(
            Recommendation(
                rank=0,
                label=_label_for(action),
                action=action,
                delta_vs_stay_out_s=delta,
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
                    "position": state.position,
                    "gap_ahead_s": state.gap_ahead_s,
                    "strategy": _label_for(action),
                    "delta_s": round(delta, 2),
                    "confidence_std_s": round(mc.std_time_s, 2),
                },
                tactical=(
                    action.kind.value
                    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE)
                    else None
                ),
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
