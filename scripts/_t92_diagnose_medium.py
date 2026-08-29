"""Diagnose T9.2 compound choice at known 2025 MEDIUM-miss laps."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.engine.session import RaceEngineSession, SessionPhase  # noqa: E402
from aris.eval.backtest import pick_reference_driver, resolve_calendar  # noqa: E402
from aris.physics.tires import compound_pace_offset  # noqa: E402
from aris.recommend import (  # noqa: E402
    _get_available_compounds,
    pit_window_compound_times,
    recommend,
)
from aris.tracks import load_track_config  # noqa: E402


CASES = [
    (2025, 4, 17, "Bahrain L17 MEDIUM"),
    (2025, 4, 32, "Bahrain L32 MEDIUM"),
    (2025, 9, 9, "Spain L9 MEDIUM"),
    (2025, 11, 18, "Austria L18 MEDIUM"),
]


def main() -> int:
    cal = {int(m["round_no"]): m for m in resolve_calendar(2025)}
    for year, round_no, lap, label in CASES:
        meta = cal[round_no]
        session_id = int(meta["session_id"])
        country = str(meta["country"])
        drv = pick_reference_driver(session_id)
        if drv is None:
            print(f"{label}: no driver", flush=True)
            continue
        track = load_track_config(country, year=year, round_no=round_no)
        session = RaceEngineSession(
            session_id=session_id,
            driver_id=int(drv["driver_id"]),
            driver_code=str(drv["code"]),
            team=str(drv.get("team") or "") or None,
            year=year,
            round_no=round_no,
            country=country,
            total_laps=track.total_laps,
            phase=SessionPhase.LIVE,
        )
        state = session.build_state(lap)
        avail = _get_available_compounds(state)
        off = compound_pace_offset("MEDIUM", circuit_id=state.country)
        print(f"\n{label}  {state.driver_code} {country}", flush=True)
        print(
            f"  lap={state.lap_number}/{state.total_laps} remaining={state.laps_remaining} "
            f"compound={state.compound} age={state.tyre_life} "
            f"track_temp={state.track_temp_c} MEDIUM_offset={off:+.2f}",
            flush=True,
        )
        print(f"  available={avail}", flush=True)
        times = pit_window_compound_times(state, lap)
        print(
            f"  pit-now window: HARD={times['HARD']:.1f} MEDIUM={times['MEDIUM']:.1f} "
            f"SOFT={times['SOFT']:.1f}  M-H={times['MEDIUM']-times['HARD']:+.1f}",
            flush=True,
        )
        recs = recommend(state, top_k=3, mc_draws=0)
        for r in recs.recommendations:
            print(f"  rec: {r.label}  delta={r.delta_vs_stay_out_s:+.2f}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
