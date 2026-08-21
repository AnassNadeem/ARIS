"""Strategy recommender — enumerate pit / line actions, score with simulate + MC."""

from __future__ import annotations

from pydantic import BaseModel

from aris.montecarlo import DEFAULT_DRAWS, run_mc
from aris.simulate import (
    ActionKind,
    StrategyAction,
    extrapolation_std_s,
    extrapolation_weight,
    simulate,
)
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
    extrapolation_beyond_laps: int = 0
    extrapolation_weight: float = 1.0


class RecommendationResult(BaseModel):
    state_lap: int
    driver_code: str
    compound: str
    recommendations: list[Recommendation]


def compute_undercut_bonus(state: RaceState) -> float:
    """Dynamic undercut bonus. Negative = faster (encourages pit). Cap -0.8s."""
    gap_ahead = state.gap_ahead_s
    if gap_ahead is None or not (0 < gap_ahead < UNDERCUT_WINDOW_S):
        return 0.0
    bonus = -0.3
    if gap_ahead < 3.0:
        bonus -= 0.3
    hist = list(state.gap_ahead_history or [])
    if len(hist) >= 3:
        recent = hist[-3:]
        closing_rate = (recent[0] - recent[-1]) / 3.0
        if closing_rate > 0.05:
            bonus -= 0.2
        elif closing_rate < -0.05:
            bonus += 0.1
    return max(bonus, -0.8)


def _undercut_bonus(state: RaceState, action: StrategyAction) -> float:
    if action.kind == ActionKind.STAY_OUT and not action.pit_laps:
        return 0.0
    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE):
        return 0.0
    return compute_undercut_bonus(state)


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
        baseline = outcome.total_race_time_s - outcome.delta_vs_stay_out_s
        bonus = _undercut_bonus(state, action)
        beyond = outcome.extrapolation_beyond_laps
        weight = extrapolation_weight(beyond)
        extra_std = extrapolation_std_s(beyond)
        # mc_draws<=0: rank on deterministic simulate() only. Live default is
        # still DEFAULT_DRAWS (100). Backtest uses 0 because ranking identity
        # (pit vs stay, lap, compound) is what we score, not MC bands.
        raw_delta = outcome.delta_vs_stay_out_s
        if mc_draws and mc_draws > 0:
            mc = run_mc(state, action, n_draws=mc_draws)
            raw_delta = mc.mean_delta_vs_stay_out_s
            mean_time = mc.mean_time_s
            std_time = float(mc.std_time_s) + extra_std
            p10_delta = mc.p10_time_s - baseline
            p90_delta = mc.p90_time_s - baseline
        else:
            mean_time = outcome.total_race_time_s
            std_time = extra_std
            p10_delta = raw_delta * weight
            p90_delta = raw_delta * weight
        # Discount ranking delta when the action's sim runs past observed
        # stint lengths for that compound (G1.1 compounding / G1.2 SOFT n=23
        # at tyre_life>=25). Stay-out delta is 0 so the weight is a no-op.
        delta = raw_delta * weight + bonus
        caveats = [
            c
            for c in (state.confidence_caveat, outcome.extrapolation_caveat)
            if c
        ]
        combined_caveat = "; ".join(caveats) if caveats else None
        evidence = outcome.evidence
        if state.confidence_caveat and state.confidence_caveat not in evidence:
            evidence = f"{evidence} | caveat: {state.confidence_caveat}"
        if bonus < 0 and state.gap_ahead_s is not None:
            note = f"Gap {state.gap_ahead_s:.1f}s — undercut bonus active."
            if note not in evidence:
                evidence = f"{evidence} | {note}"
        scored.append(
            Recommendation(
                rank=0,
                label=_label_for(action),
                action=action,
                delta_vs_stay_out_s=delta,
                mean_race_time_s=mean_time,
                confidence_std_s=std_time,
                p10_delta_s=p10_delta,
                p90_delta_s=p90_delta,
                evidence=evidence,
                narration_context={
                    "driver": state.driver_code,
                    "lap": state.lap_number,
                    "compound": state.compound,
                    "tyre_life": state.tyre_life,
                    "laps_remaining": state.laps_remaining,
                    "position": state.position,
                    "gap_ahead_s": state.gap_ahead_s,
                    "undercut_bonus_s": round(bonus, 3),
                    "strategy": _label_for(action),
                    "delta_s": round(delta, 2),
                    "raw_delta_s": round(raw_delta, 2),
                    "confidence_std_s": round(std_time, 2),
                    "confidence_caveat": combined_caveat,
                    "recent_sc_pace": state.recent_sc_pace,
                    "extrapolation_beyond_laps": beyond,
                    "extrapolation_weight": round(weight, 3),
                    "extrapolation_compound": outcome.extrapolation_compound,
                    "extrapolation_caveat": outcome.extrapolation_caveat,
                },
                tactical=(
                    action.kind.value
                    if action.kind in (ActionKind.LIFT, ActionKind.BRAKE)
                    else None
                ),
                extrapolation_beyond_laps=beyond,
                extrapolation_weight=weight,
            )
        )

    scored.sort(key=lambda r: r.delta_vs_stay_out_s)

    # Always surface stay-out so the engineer can reject a pit push — even when
    # every pit option scores better on raw delta.
    stay = next(
        (r for r in scored if r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps),
        None,
    )
    top = scored[:top_k]
    if stay is not None and stay not in top:
        top = top[: max(0, top_k - 1)] + [stay]

    for i, rec in enumerate(top, start=1):
        rec.rank = i

    return RecommendationResult(
        state_lap=state.lap_number,
        driver_code=state.driver_code,
        compound=state.compound,
        recommendations=top,
    )
