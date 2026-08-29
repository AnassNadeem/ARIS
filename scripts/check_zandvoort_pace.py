"""Zandvoort identity sanity check after T9.1 pace offsets (HARD must stay best).

Constructs the identity RaceState (lap 25, MEDIUM, tyre life 2) and prints:
  - recommend() top 3
  - remaining-race times for HARD/MEDIUM/SOFT at pit 33 and pit 30

Usage:
  python scripts/check_zandvoort_pace.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.models.features import estimate_fuel_kg  # noqa: E402
from aris.recommend import pit_window_compound_times, recommend  # noqa: E402
from aris.simulate import ActionKind  # noqa: E402
from aris.state import RaceState  # noqa: E402


def _zandvoort_state() -> RaceState:
    return RaceState(
        session_id=1,
        driver_id=1,
        driver_code="VER",
        driver_name="Max Verstappen",
        year=2025,
        round_no=15,
        country="Netherlands",
        lap_number=25,
        compound="MEDIUM",
        tyre_life=2,
        fuel_kg=estimate_fuel_kg(25, total_laps=72),
        laps_remaining=47,
        total_laps=72,
        lag1_pace=74.0,
        lag2_pace=74.0,
        stint_roll3=74.0,
        pit_compound="HARD",
    )


def main() -> int:
    from aris.physics.tires import CIRCUIT_MEDIUM_OFFSET, COMPOUND_PACE_OFFSET, compound_pace_offset

    print(
        "COMPOUND_PACE_OFFSET = "
        f"HARD={COMPOUND_PACE_OFFSET['HARD']}, "
        f"MEDIUM={COMPOUND_PACE_OFFSET['MEDIUM']}, "
        f"SOFT={COMPOUND_PACE_OFFSET['SOFT']}",
        flush=True,
    )
    print(
        "Netherlands MEDIUM offset = "
        f"{compound_pace_offset('MEDIUM', circuit_id='Netherlands'):+.2f} "
        f"(circuit table has {len(CIRCUIT_MEDIUM_OFFSET)} entries)",
        flush=True,
    )
    state = _zandvoort_state()
    fail = False
    for pit_lap in (33, 30):
        times = pit_window_compound_times(state, pit_lap)
        print(
            f"Pit lap {pit_lap}: HARD = {times['HARD']:.1f} s, "
            f"MEDIUM = {times['MEDIUM']:.1f} s, SOFT = {times['SOFT']:.1f} s.",
            flush=True,
        )
        if times["MEDIUM"] < times["HARD"] or times["SOFT"] < times["HARD"]:
            print(f"FAIL: MEDIUM or SOFT beat HARD at pit lap {pit_lap}", flush=True)
            fail = True
        else:
            gap_m = times["MEDIUM"] - times["HARD"]
            gap_s = times["SOFT"] - times["HARD"]
            print(
                f"  HARD still best (+{gap_m:.1f} s vs MEDIUM, "
                f"+{gap_s:.1f} s vs SOFT)",
                flush=True,
            )

    result = recommend(state, top_k=3, mc_draws=0)
    labels = [r.label for r in result.recommendations]
    print("recommend top-3:", labels, flush=True)
    for rec in result.recommendations:
        print(
            f"  {rec.label}: delta_vs_stay={rec.delta_vs_stay_out_s:+.2f} s",
            flush=True,
        )
    if not labels or not str(labels[0]).startswith("Pit lap 33 for HARD"):
        print("FAIL: expected Pit lap 33 for HARD as rank 1", flush=True)
        fail = True
    if not any(str(lab).startswith("Pit lap 30 for HARD") for lab in labels):
        print("FAIL: expected Pit lap 30 for HARD in top-3", flush=True)
        fail = True
    if not any(
        r.action.kind == ActionKind.STAY_OUT and not r.action.pit_laps
        for r in result.recommendations
    ):
        print("FAIL: expected Stay out in top-3", flush=True)
        fail = True
    print("Zandvoort pace check FAIL" if fail else "Zandvoort pace check PASS", flush=True)
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
