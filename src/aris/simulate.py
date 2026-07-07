"""Counterfactual race simulation — pit now vs stay out vs pit lap N."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from aris.models.features import estimate_fuel_kg
from aris.models.predict import predict_lap_time
from aris.physics.bicycle import bahrain_2024
from aris.state import RaceState, state_to_feature_dict

PACE_SIGMA_S = 0.35
PIT_LOSS_S = bahrain_2024().pit_loss_s


class ActionKind(StrEnum):
    STAY_OUT = "stay_out"
    PIT_NOW = "pit_now"
    PIT_LAP = "pit_lap"


class StrategyAction(BaseModel):
    kind: ActionKind
    pit_lap: int | None = None
    pit_compound: str | None = None


class PredictedOutcome(BaseModel):
    action: StrategyAction
    total_race_time_s: float
    delta_vs_stay_out_s: float
    mean_lap_time_s: float
    laps_simulated: int
    evidence: str = ""


def _predict_lap(
    state: RaceState, *, compound: str, tyre_life: int, fuel_kg: float, pit_lap: bool
) -> float:
    base = state_to_feature_dict(state)
    return predict_lap_time(
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel_kg,
        pit_lap=pit_lap,
        lag1_pace=base.get("lag1_pace"),
        lag2_pace=base.get("lag2_pace"),
        stint_roll3=base.get("stint_roll3"),
    )


def _simulate_remainder(
    state: RaceState,
    *,
    pit_on_lap: int | None,
    pit_compound: str,
) -> tuple[float, int, str]:
    total = 0.0
    laps = 0
    compound = state.compound
    tyre_life = state.tyre_life
    evidence_parts: list[str] = []

    for lap in range(state.lap_number, state.total_laps + 1):
        fuel = estimate_fuel_kg(lap, total_laps=state.total_laps)
        is_pit = pit_on_lap is not None and lap == pit_on_lap
        if is_pit:
            evidence_parts.append(f"pit L{lap}->{pit_compound}")
            total += _predict_lap(
                state, compound=compound, tyre_life=tyre_life, fuel_kg=fuel, pit_lap=True
            )
            total += PIT_LOSS_S
            compound = pit_compound
            tyre_life = 1
            laps += 1
            continue

        lap_time = _predict_lap(
            state, compound=compound, tyre_life=tyre_life, fuel_kg=fuel, pit_lap=False
        )
        total += lap_time
        tyre_life += 1
        laps += 1

    evidence = "; ".join(evidence_parts) if evidence_parts else "stay on current compound"
    return total, laps, evidence


def simulate(state: RaceState, action: StrategyAction) -> PredictedOutcome:
    baseline_time, _, _ = _simulate_remainder(
        state, pit_on_lap=None, pit_compound=state.pit_compound
    )

    if action.kind == ActionKind.STAY_OUT:
        pit_lap = None
        pit_compound = state.compound
    elif action.kind == ActionKind.PIT_NOW:
        pit_lap = state.lap_number
        pit_compound = action.pit_compound or state.pit_compound
    elif action.kind == ActionKind.PIT_LAP:
        if action.pit_lap is None:
            raise ValueError("PIT_LAP action requires pit_lap")
        pit_lap = action.pit_lap
        pit_compound = action.pit_compound or state.pit_compound
    else:
        raise ValueError(f"unknown action {action.kind}")

    total, n_laps, evidence = _simulate_remainder(
        state, pit_on_lap=pit_lap, pit_compound=pit_compound
    )
    delta = total - baseline_time
    mean_lap = total / n_laps if n_laps else 0.0

    return PredictedOutcome(
        action=action,
        total_race_time_s=total,
        delta_vs_stay_out_s=delta,
        mean_lap_time_s=mean_lap,
        laps_simulated=n_laps,
        evidence=evidence,
    )
