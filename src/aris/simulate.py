"""Counterfactual race simulation — pit / lift / brake actions."""

from __future__ import annotations

from enum import StrEnum
from typing import NamedTuple

from pydantic import BaseModel

from aris.models.features import estimate_fuel_kg
from aris.models.predict import predict_lap_time, predict_physics
from aris.physics.bicycle import Car, approach_delta_s
from aris.state import RaceState
from aris.tracks import load_track_config

PACE_SIGMA_S = 0.35

# G1.2 2024 held-out single-step counts (real lags): SOFT tyre_life>=25 is
# n=23 laps; MEDIUM 35+ n=191; HARD 35-80 n=1104. Ceilings mark where support
# thins, not a claim of calibration up to them.
COMPOUND_EVIDENCE_TYRE_LIFE: dict[str, int] = {
    "SOFT": 16,
    "MEDIUM": 32,
    "HARD": 50,
}
# G1.1: chained MAE grew ~0.10 s per lap-ahead vs a flat ~0.8 s teacher-forced.
EXTRAPOLATION_STD_PER_LAP = 0.10
# Mild ranking discount: 10 laps beyond ceiling → weight 1/1.5 = 0.67.
EXTRAPOLATION_DISCOUNT_K = 0.05
EXTRAPOLATION_CAVEAT_MIN_BEYOND = 5


class RemainderResult(NamedTuple):
    total: float
    laps: int
    evidence: str
    max_tyre_life: dict[str, int]
    chained_laps: int


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
    extrapolation_beyond_laps: int = 0
    extrapolation_compound: str | None = None
    extrapolation_max_tyre_life: int = 0
    extrapolation_caveat: str | None = None
    chained_laps: int = 0


def evidence_tyre_life_ceiling(compound: str) -> int:
    return COMPOUND_EVIDENCE_TYRE_LIFE.get(str(compound).upper(), 32)


def extrapolation_beyond_laps(max_tyre_life: dict[str, int]) -> tuple[int, str | None]:
    """Laps past the per-compound evidence ceiling, and the worst compound."""
    worst = 0
    worst_c: str | None = None
    for compound, life in max_tyre_life.items():
        beyond = max(0, int(life) - evidence_tyre_life_ceiling(compound))
        if beyond > worst:
            worst = beyond
            worst_c = str(compound).upper()
    return worst, worst_c


def extrapolation_weight(beyond_laps: int) -> float:
    """Discount on delta_vs_stay_out when a sim runs past observed stint lengths."""
    if beyond_laps <= 0:
        return 1.0
    return 1.0 / (1.0 + EXTRAPOLATION_DISCOUNT_K * beyond_laps)


def extrapolation_std_s(beyond_laps: int) -> float:
    """Extra σ from G1.1 compounding (~0.10 s MAE per lap past the ceiling)."""
    return EXTRAPOLATION_STD_PER_LAP * max(0, int(beyond_laps))


def extrapolation_caveat_text(
    beyond_laps: int,
    compound: str | None,
    max_life: int,
) -> str | None:
    if beyond_laps < EXTRAPOLATION_CAVEAT_MIN_BEYOND or not compound:
        return None
    return (
        f"this call extends {compound} to tyre life {max_life}, "
        "beyond typical observed stints — lower confidence"
    )


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
    track=None,
) -> float:
    return predict_lap_time(
        compound=compound,
        tyre_life=tyre_life,
        fuel_kg=fuel_kg,
        pit_lap=pit_lap,
        track=track,
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


def _lap_physics(compound: str, tyre_life: int, fuel_kg: float, track) -> float:
    return float(
        predict_physics(
            compound=compound,
            tyre_life=tyre_life,
            fuel_kg=fuel_kg,
            pit_lap=False,
            track=track,
        )
    )


def _simulate_remainder(
    state: RaceState,
    *,
    pit_schedule: list[tuple[int, str]],
    pace_noise: list[float] | None = None,
    line_delta_first_lap_s: float = 0.0,
) -> RemainderResult:
    """Forward-sim remaining laps.

    The residual model is a one-step pace tracker: held-out MAE uses *observed*
    lag1/lag2 at every lap (G1.2: HARD tyre_life>=25 bias ≈ 0). ``simulate()``
    used to feed its own predictions back as lags. G1.1 measured that chained
    path directly: MAE 0.86s at +1 → 2.79s at +20 (teacher-forced stays ~0.8s).
    G1.3's ARIS-hindsight deltas were residual artifacts on compound changes
    (−40 to −312 s), not tyre physics.

    After the first residual-corrected lap (real lags), later laps add only
    the physics delta (tyre slope + fuel). Compound changes inherit the
    anchored pace; SOFT vs HARD then differs by slope, not by a re-applied
    residual on fake lags.
    """
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
    track = _track_for(state)
    noise_idx = 0
    first_lap = True
    prev_physics: float | None = None
    prev_pred: float | None = None
    max_tyre_life: dict[str, int] = {}

    for lap in range(state.lap_number, state.total_laps + 1):
        fuel = estimate_fuel_kg(lap, total_laps=state.total_laps)
        physics = _lap_physics(compound, tyre_life, fuel, track)
        noise = 0.0
        if pace_noise is not None and noise_idx < len(pace_noise):
            noise = pace_noise[noise_idx]
            noise_idx += 1

        if prev_physics is None:
            lag1, lag2, roll3 = _update_lags(recent_times)
            pred = _predict_lap(
                compound=compound,
                tyre_life=tyre_life,
                fuel_kg=fuel,
                pit_lap=False,
                lag1=lag1,
                lag2=lag2,
                roll3=roll3,
                noise=noise,
                track=track,
            )
        else:
            pred = float(prev_pred) + (physics - prev_physics) + noise

        max_tyre_life[compound] = max(max_tyre_life.get(compound, 0), int(tyre_life))

        if lap in pit_map:
            pit_compound = pit_map[lap]
            evidence_parts.append(f"pit L{lap}->{pit_compound}")
            # Green-pace on old tyres + track pit_loss once.
            # (Do not also set pit_lap=True — that would double-count pit_loss
            # inside physics when track is passed.)
            total += pred + pit_loss
            recent_times.append(pred)
            prev_physics = physics
            prev_pred = pred
            compound = pit_compound
            tyre_life = 1
            laps += 1
            first_lap = False
            continue

        if first_lap and line_delta_first_lap_s:
            pred += line_delta_first_lap_s
        total += pred
        recent_times.append(pred)
        if len(recent_times) > 10:
            recent_times = recent_times[-10:]
        prev_physics = physics
        prev_pred = pred
        tyre_life += 1
        laps += 1
        first_lap = False

    evidence = "; ".join(evidence_parts) if evidence_parts else "stay on current compound"
    chained = max(0, laps - 1)
    return RemainderResult(total, laps, evidence, max_tyre_life, chained)


def _extrapolation_fields(result: RemainderResult) -> dict[str, object]:
    beyond, compound = extrapolation_beyond_laps(result.max_tyre_life)
    max_life = 0
    if compound:
        max_life = int(result.max_tyre_life[compound])
    return {
        "extrapolation_beyond_laps": beyond,
        "extrapolation_compound": compound,
        "extrapolation_max_tyre_life": max_life,
        "extrapolation_caveat": extrapolation_caveat_text(beyond, compound, max_life),
        "chained_laps": result.chained_laps,
    }


def simulate(
    state: RaceState,
    action: StrategyAction,
    *,
    pace_noise: list[float] | None = None,
) -> PredictedOutcome:
    stay_schedule: list[tuple[int, str]] = []
    baseline = _simulate_remainder(
        state, pit_schedule=stay_schedule, pace_noise=pace_noise
    )

    line_delta = _line_delta_s(state, action)
    schedule = _pit_schedule(action, state)
    result = _simulate_remainder(
        state,
        pit_schedule=schedule,
        pace_noise=pace_noise,
        line_delta_first_lap_s=line_delta,
    )
    evidence = result.evidence
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

    extra = _extrapolation_fields(result)
    caveat = extra["extrapolation_caveat"]
    if caveat:
        evidence = f"{evidence} | caveat: {caveat}"

    delta = result.total - baseline.total
    mean_lap = result.total / result.laps if result.laps else 0.0

    return PredictedOutcome(
        action=action,
        total_race_time_s=result.total,
        delta_vs_stay_out_s=delta,
        mean_lap_time_s=mean_lap,
        laps_simulated=result.laps,
        evidence=evidence,
        extrapolation_beyond_laps=int(extra["extrapolation_beyond_laps"]),
        extrapolation_compound=(
            str(extra["extrapolation_compound"])
            if extra["extrapolation_compound"]
            else None
        ),
        extrapolation_max_tyre_life=int(extra["extrapolation_max_tyre_life"]),
        extrapolation_caveat=str(caveat) if caveat else None,
        chained_laps=int(extra["chained_laps"]),
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
    return _simulate_remainder(start, pit_schedule=schedule).total
