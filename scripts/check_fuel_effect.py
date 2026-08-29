"""Sanity-check the T9.2 remainder fuel deg-trend correction.

Simulates a 30-lap HARD stint at Bahrain with and without the correction.
Prints lap 1 / 15 / 30 times and total stint time.

Usage:
  python scripts/check_fuel_effect.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.models.features import estimate_fuel_kg  # noqa: E402
from aris.models.predict import predict_physics  # noqa: E402
from aris.simulate import (  # noqa: E402
    ActionKind,
    StrategyAction,
    _track_for,
    fuel_correction_s,
    simulate,
)
from aris.state import RaceState  # noqa: E402


def _state() -> RaceState:
    return RaceState(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2025,
        round_no=4,
        country="Bahrain",
        lap_number=1,
        compound="HARD",
        tyre_life=1,
        fuel_kg=estimate_fuel_kg(1, total_laps=30),
        laps_remaining=29,
        total_laps=30,
        lag1_pace=None,
        lag2_pace=None,
        stint_roll3=None,
        pit_compound="HARD",
    )


def _physics_laps(*, fuel_adjusted: bool) -> list[float]:
    """Absolute bicycle laps: heavy fuel adds time; subtracting it (fuel
    correction) makes early laps faster — the detrend used in DegSlope fits.
    """
    state = _state()
    track = _track_for(state)
    times: list[float] = []
    for lap in range(1, 31):
        fuel = estimate_fuel_kg(lap, total_laps=30)
        raw = float(
            predict_physics(
                compound="HARD",
                tyre_life=lap,
                fuel_kg=fuel,
                track=track,
            )
        )
        times.append(raw - fuel_correction_s(fuel) if fuel_adjusted else raw)
    return times


def main() -> int:
    state = _state()
    with_times: list[float] = []
    without_times: list[float] = []
    with_ = simulate(
        state,
        StrategyAction(kind=ActionKind.STAY_OUT),
        fuel_deg_correction=True,
        lap_times_out=with_times,
    )
    without = simulate(
        state,
        StrategyAction(kind=ActionKind.STAY_OUT),
        fuel_deg_correction=False,
        lap_times_out=without_times,
    )

    phys_adj = _physics_laps(fuel_adjusted=True)
    phys_raw = _physics_laps(fuel_adjusted=False)

    def _row(label: str, times: list[float], total: float | None = None) -> None:
        tot = total if total is not None else sum(times)
        print(
            f"  {label}: lap1={times[0]:.3f}  lap15={times[14]:.3f}  "
            f"lap30={times[29]:.3f}  total={tot:.1f} s",
            flush=True,
        )

    print("Absolute bicycle (fuel in physics vs fuel-adjusted = raw - k_fuel*load):", flush=True)
    _row("raw physics (heavy car slower)", phys_raw)
    _row("fuel-adjusted (early laps faster)", phys_adj)
    print(
        f"  lap1 delta (adjusted - raw) = {phys_adj[0] - phys_raw[0]:+.3f} s "
        f"(expect negative: heavy fuel detrended)",
        flush=True,
    )

    print("\nsimulate() remainder chain (fuel-lightening stripped from deg delta):", flush=True)
    _row("with correction", with_times, with_.total_race_time_s)
    _row("without correction", without_times, without.total_race_time_s)
    print(
        f"  total delta (with - without) = "
        f"{with_.total_race_time_s - without.total_race_time_s:+.2f} s",
        flush=True,
    )

    fail = False
    if phys_adj[0] >= phys_raw[0]:
        print("FAIL: fuel-adjusted lap 1 should be faster than raw (heavy car).", flush=True)
        fail = True
    else:
        print("PASS: early physics laps are faster after fuel correction.", flush=True)
    if not (2000.0 < with_.total_race_time_s < 4000.0):
        print(
            f"FAIL: stint total {with_.total_race_time_s:.1f} s is not plausible.",
            flush=True,
        )
        fail = True
    else:
        print("PASS: total stint time is plausible.", flush=True)
    if with_.total_race_time_s <= without.total_race_time_s:
        print(
            "FAIL: remainder with deg-trend correction should be slower "
            "(tyre drop no longer masked by fuel burn).",
            flush=True,
        )
        fail = True
    else:
        print("PASS: remainder without fuel-lightening is slower (deg unmasked).", flush=True)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
