"""Demo: lift 30 m into T7 — predicted lap-time delta (Phase C Block C.2)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "src"))

from aris.physics.bicycle import Car, StintState, approach_delta_s, bahrain_2024, predict_lap_time
from aris.simulate import ActionKind, StrategyAction, simulate
from aris.state import RaceState


def main() -> None:
    track = bahrain_2024()
    car = Car()
    state_phys = StintState(
        car=car,
        track=track,
        fuel_kg=50.0,
        compound="SOFT",
        lap_in_stint=12,
    )
    baseline = predict_lap_time(state_phys)
    delta = approach_delta_s(
        track, corner_index=7, distance_m=30.0, mode="lift", car=car
    )

    race = RaceState(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2024,
        round_no=1,
        country="Bahrain",
        lap_number=15,
        compound="SOFT",
        tyre_life=12,
        fuel_kg=50.0,
        laps_remaining=42,
        lag1_pace=94.5,
        lag2_pace=94.3,
        stint_roll3=94.4,
        pit_compound="HARD",
    )
    outcome = simulate(
        race,
        StrategyAction(kind=ActionKind.LIFT, corner_index=7, distance_m=30.0),
    )

    lines = [
        "ARIS Phase C demo — lift 30 m into T7",
        f"Track: {track.name} ({len(track.corners)} corners)",
        f"Physics baseline lap: {baseline:.3f} s",
        f"Lift 30 m into T7 physics delta: +{delta:.3f} s",
        f"Simulate() race delta vs stay-out: {outcome.delta_vs_stay_out_s:+.3f} s",
        f"Evidence: {outcome.evidence}",
    ]
    text = "\n".join(lines) + "\n"
    out = _REPO / "results" / "lift-t7-demo.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
