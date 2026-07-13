"""Monte Carlo strategy simulation for pre-race planning."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from aris.models.features import estimate_fuel_kg
from aris.models.predict import predict_physics
from aris.physics.tires import DEFAULT_COMPOUND_SLOPE
from aris.tracks import load_track_config

SAFETY_CAR_PROB = 0.18
PIT_LOSS_S = 22.0
PACE_SIGMA_S = 0.35
N_SIMULATIONS = 1000

# Expected tyre life (laps) for degradation bar
TYRE_LIFE_ESTIMATE = {"SOFT": 22, "MEDIUM": 34, "HARD": 45, "INTERMEDIATE": 30, "WET": 25}


@dataclass
class StrategyDef:
    id: str
    name: str
    compounds: list[str]  # stint sequence
    pit_laps: list[int]
    stint_laps: list[int] = field(default_factory=list)


@dataclass
class StrategyResult:
    strategy: StrategyDef
    total_time_s: float
    p1_prob: float
    p2_prob: float
    p3_plus_prob: float
    pit_loss_s: float
    recommended: bool = False


def _default_strategies(total_laps: int = 57) -> list[StrategyDef]:
    """Three fixed strategy templates scaled to race length."""
    return [
        StrategyDef(
            id="aggressive",
            name="2-stop aggressive",
            compounds=["SOFT", "MEDIUM", "HARD"],
            pit_laps=[18, 40],
            stint_laps=[18, 22, total_laps - 40],
        ),
        StrategyDef(
            id="conservative",
            name="1-stop conservative",
            compounds=["MEDIUM", "HARD"],
            pit_laps=[28],
            stint_laps=[28, total_laps - 28],
        ),
        StrategyDef(
            id="balanced",
            name="2-stop balanced",
            compounds=["SOFT", "HARD", "MEDIUM"],
            pit_laps=[20, 40],
            stint_laps=[20, 20, total_laps - 40],
        ),
    ]


def _simulate_race_time(
    strategy: StrategyDef,
    total_laps: int,
    rng: np.random.Generator,
    *,
    sc_active: bool,
) -> float:
    """Simulate total race time for one draw."""
    pit_loss = PIT_LOSS_S
    total = 0.0
    compound_idx = 0
    current_compound = strategy.compounds[0]
    lap_in_stint = 0
    pit_idx = 0
    pit_laps = strategy.pit_laps
    lag1: float | None = None

    for lap in range(1, total_laps + 1):
        fuel = estimate_fuel_kg(lap, total_laps=total_laps)
        is_pit = pit_idx < len(pit_laps) and lap == pit_laps[pit_idx]

        if is_pit:
            lap_in_stint = 1
            compound_idx += 1
            if compound_idx < len(strategy.compounds):
                current_compound = strategy.compounds[compound_idx]
            pit_idx += 1
            lt = predict_physics(compound=current_compound, tyre_life=1, fuel_kg=fuel, pit_lap=True)
            total += lt + pit_loss + rng.normal(0, 0.5)
            lag1 = lt
            continue

        lap_in_stint += 1
        noise = rng.normal(0, PACE_SIGMA_S)
        if sc_active:
            noise += rng.uniform(0.5, 2.0)

        lt = predict_physics(
            compound=current_compound,
            tyre_life=lap_in_stint,
            fuel_kg=fuel,
            pit_lap=False,
        ) + noise
        total += lt
        lag1 = lt

    return total


def _opponent_baseline(total_laps: int, rng: np.random.Generator) -> float:
    """Simplified opponent race time (P2 reference)."""
    total = 0.0
    compound = "MEDIUM"
    lap_in_stint = 0
    for lap in range(1, total_laps + 1):
        if lap == 28:
            compound = "HARD"
            lap_in_stint = 0
            total += PIT_LOSS_S
        lap_in_stint += 1
        fuel = estimate_fuel_kg(lap, total_laps=total_laps)
        total += predict_physics(compound=compound, tyre_life=lap_in_stint, fuel_kg=fuel) + rng.normal(0, PACE_SIGMA_S)
    return total


def run_strategy_mc(
    *,
    total_laps: int = 57,
    country: str = "Bahrain",
    n_sims: int = N_SIMULATIONS,
    seed: int = 42,
) -> list[StrategyResult]:
    """Run MC for all 3 strategies, sort by P1 prob, badge top as recommended."""
    _ = load_track_config(country)  # validate track exists
    rng = np.random.default_rng(seed)
    strategies = _default_strategies(total_laps)
    results: list[StrategyResult] = []

    for strat in strategies:
        our_times: list[float] = []
        opp_times: list[float] = []
        wins = 0
        second = 0

        for _ in range(n_sims):
            sc = rng.random() < SAFETY_CAR_PROB
            our_t = _simulate_race_time(strat, total_laps, rng, sc_active=sc)
            opp_t = _opponent_baseline(total_laps, rng)
            # Field noise — 3 more competitors
            field = [opp_t]
            for _ in range(3):
                field.append(_opponent_baseline(total_laps, rng) + rng.normal(0, 5))
            our_times.append(our_t)
            opp_times.append(min(field))
            rank = 1 + sum(1 for t in field if t < our_t)
            if rank == 1:
                wins += 1
            elif rank == 2:
                second += 1

        p1 = wins / n_sims
        p2 = second / n_sims
        p3 = 1.0 - p1 - p2
        n_stops = len(strat.pit_laps)
        results.append(StrategyResult(
            strategy=strat,
            total_time_s=float(np.mean(our_times)),
            p1_prob=p1,
            p2_prob=p2,
            p3_plus_prob=p3,
            pit_loss_s=n_stops * PIT_LOSS_S,
            recommended=False,
        ))

    results.sort(key=lambda r: r.p1_prob, reverse=True)
    results[0].recommended = True
    return results


def predict_lap_trace(
    strategy: StrategyDef,
    total_laps: int = 57,
) -> tuple[list[int], list[float], list[int]]:
    """Deterministic lap time trace for selected strategy."""
    laps: list[int] = []
    times: list[float] = []
    pit_markers: list[int] = []
    compound_idx = 0
    current_compound = strategy.compounds[0]
    lap_in_stint = 0
    pit_idx = 0

    for lap in range(1, total_laps + 1):
        fuel = estimate_fuel_kg(lap, total_laps=total_laps)
        is_pit = pit_idx < len(strategy.pit_laps) and lap == strategy.pit_laps[pit_idx]

        if is_pit:
            pit_markers.append(lap)
            lap_in_stint = 1
            compound_idx += 1
            if compound_idx < len(strategy.compounds):
                current_compound = strategy.compounds[compound_idx]
            pit_idx += 1
            lt = predict_physics(compound=current_compound, tyre_life=1, fuel_kg=fuel, pit_lap=True) + PIT_LOSS_S
            laps.append(lap)
            times.append(lt)
            continue

        lap_in_stint += 1
        lt = predict_physics(compound=current_compound, tyre_life=lap_in_stint, fuel_kg=fuel)
        laps.append(lap)
        times.append(lt)

    return laps, times, pit_markers


def tyre_info_table() -> list[dict]:
    """Tyre life estimates from tires.py coefficients."""
    rows = []
    for compound, slope in DEFAULT_COMPOUND_SLOPE.items():
        if compound in ("INTERMEDIATE", "WET"):
            continue
        life = TYRE_LIFE_ESTIMATE.get(compound, 30)
        rows.append({
            "compound": compound,
            "life_laps": f"~{life - 4}-{life + 4}",
            "deg_rate": f"{slope:.2f}s/lap",
        })
    return rows


def format_race_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h}h {m}.{int(s):02d}m est"
    return f"{m}m {s:.1f}s est"
