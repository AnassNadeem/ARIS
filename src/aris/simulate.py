"""Counterfactual race simulation — pit / lift / brake actions."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from aris.models.features import estimate_fuel_kg
from aris.models.predict import predict_lap_time
from aris.physics.bicycle import Car, approach_delta_s
from aris.state import RaceState
from aris.tracks import load_track_config

PACE_SIGMA_S = 0.35


class ActionKind(StrEnum):
    STAY_OUT = "stay_out"
    PIT_NOW = "pit_now"
    PIT_LAP = "pit_lap"
    LIFT = "lift"
    BRAKE = "brake"


class StrategyAction(BaseModel):
    kind: ActionKind
    pit_lap: int | None = None
    pit_compound: str | None = None
    pit_laps: list[int] | None = None
    pit_compounds: list[str] | None = None
    # 1-based corner index + metres earlier (LIFT / BRAKE).
    corner_index: int | None = None
    distance_m: float | None = None


class PredictedOutcome(BaseModel):
    action: StrategyAction
    total_race_time_s: float
    delta_vs_stay_out_s: float
    mean_lap_time_s: float
    laps_simulated: int
    evidence: str = ""


def _pit_loss_s(state: RaceState) -> float:
    return load_track_config(state.country).pit_loss_s


def _track_for(state: RaceState):
    return load_track_config(state.country).load_physics()


def _update_lags(times: list[float]) -> tuple[float | None, float | None, float | None]:
    if not times:
        return None, None, None
    lag1 = times[-1]
    lag2 = times[-2] if len(times) >= 2 else lag1
    roll3 = sum(times[-3:]) / min(3, len(times[-3:]))
    return lag1, lag2, roll3


def _predict_lap(
    *,
    compound: str,
    tyre_life: int,
    fuel_kg: float,
    pit_lap: bool,
    lag1: float | None,
    lag2: float | None,
    roll3: float | None,
    noise: float = 0.0,
) -> float:
    return predict_lap_time(
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel_kg,
        pit_lap=pit_lap,
        lag1_pace=lag1,
        lag2_pace=lag2,
        stint_roll3=roll3,
    ) + noise


def _line_delta_s(state: RaceState, action: StrategyAction) -> float:
    """Physics delta for a one-shot lift/brake on the current lap."""
    if action.kind not in (ActionKind.LIFT, ActionKind.BRAKE):
        return 0.0
    if action.corner_index is None or action.distance_m is None:
        return 0.0
    track = _track_for(state)
    mode = "lift" if action.kind == ActionKind.LIFT else "brake"
    return approach_delta_s(
        track,
        corner_index=int(action.corner_index),
        distance_m=float(action.distance_m),
        mode=mode,
        car=Car(),
    )


def _pit_schedule(action: StrategyAction, state: RaceState) -> list[tuple[int, str]]:
    if action.pit_laps and action.pit_compounds:
        return list(zip(action.pit_laps, action.pit_compounds, strict=False))
    if action.kind == ActionKind.STAY_OUT:
        return []
    if action.kind == ActionKind.PIT_NOW:
        return [(state.lap_number, action.pit_compound or state.pit_compound)]
    if action.kind == ActionKind.PIT_LAP and action.pit_lap is not None:
        return [(action.pit_lap, action.pit_compound or state.pit_compound)]
    return []


def _simulate_remainder(
    state: RaceState,
    *,
    pit_schedule: list[tuple[int, str]],
    pace_noise: list[float] | None = None,
    line_delta_first_lap_s: float = 0.0,
) -> tuple[float, int, str]:
    total = 0.0
    laps = 0
    compound = state.compound
    tyre_life = state.tyre_life
    evidence_parts: list[str] = []
    recent_times: list[float] = []
    if state.lag1_pace is not None:
        recent_times.append(state.lag1_pace)
    if state.lag2_pace is not None:
        recent_times.insert(0, state.lag2_pace)
    pit_map = dict(pit_schedule)
    pit_loss = _pit_loss_s(state)
    noise_idx = 0
    first_lap = True

    for lap in range(state.lap_number, state.total_laps + 1):
        fuel = estimate_fuel_kg(lap, total_laps=state.total_laps)
        lag1, lag2, roll3 = _update_lags(recent_times)
        noise = 0.0
        if pace_noise is not None and noise_idx < len(pace_noise):
            noise = pace_noise[noise_idx]
            noise_idx += 1

        if lap in pit_map:
            pit_compound = pit_map[lap]
            evidence_parts.append(f"pit L{lap}->{pit_compound}")
            pit_time = _predict_lap(
                compound=compound, tyre_life=tyre_life, fuel_kg=fuel,
                pit_lap=True, lag1=lag1, lag2=lag2, roll3=roll3, noise=noise,
            )
            total += pit_time + pit_loss
            recent_times.append(pit_time)
            compound = pit_compound
            tyre_life = 1
            laps += 1
            first_lap = False
            continue

        lap_time = _predict_lap(
            compound=compound, tyre_life=tyre_life, fuel_kg=fuel,
            pit_lap=False, lag1=lag1, lag2=lag2, roll3=roll3, noise=noise,
        )
        if first_lap and line_delta_first_lap_s:
            lap_time += line_delta_first_lap_s
        total += lap_time
        recent_times.append(lap_time)
        if len(recent_times) > 10:
            recent_times = recent_times[-10:]
        tyre_life += 1
        laps += 1
        first_lap = False

    evidence = "; ".join(evidence_parts) if evidence_parts else "stay on current compound"
    return total, laps, evidence


def simulate(
    state: RaceState,
    action: StrategyAction,
    *,
    pace_noise: list[float] | None = None,
) -> PredictedOutcome:
    stay_schedule: list[tuple[int, str]] = []
    baseline_time, _, _ = _simulate_remainder(
        state, pit_schedule=stay_schedule, pace_noise=pace_noise
    )

    line_delta = _line_delta_s(state, action)
    schedule = _pit_schedule(action, state)
    total, n_laps, evidence = _simulate_remainder(
        state,
        pit_schedule=schedule,
        pace_noise=pace_noise,
        line_delta_first_lap_s=line_delta,
    )
    if action.kind == ActionKind.LIFT and action.corner_index and action.distance_m:
        evidence = (
            f"lift {action.distance_m:.0f}m into T{action.corner_index} "
            f"(+{line_delta:.3f}s physics)"
        )
    elif action.kind == ActionKind.BRAKE and action.corner_index and action.distance_m:
        evidence = (
            f"brake {action.distance_m:.0f}m earlier into T{action.corner_index} "
            f"(+{line_delta:.3f}s physics)"
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


def simulate_full_race(
    state: RaceState,
    *,
    pit_laps: list[int],
    pit_compounds: list[str],
    start_lap: int = 1,
) -> float:
    """Forward sim from race start for pre-race planning."""
    start = RaceState(
        **{
            **state.model_dump(),
            "lap_number": start_lap,
            "compound": state.compound,
            "tyre_life": 1,
            "fuel_kg": estimate_fuel_kg(start_lap, total_laps=state.total_laps),
            "laps_remaining": state.total_laps - start_lap,
            "lag1_pace": None,
            "lag2_pace": None,
            "stint_roll3": None,
        }
    )
    schedule = list(zip(pit_laps, pit_compounds, strict=False))
    total, _, _ = _simulate_remainder(start, pit_schedule=schedule)
    return total
