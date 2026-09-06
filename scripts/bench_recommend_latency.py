"""Benchmark recommend() wall-clock (physics → XGB residual → optional MC).

Usage:
  python scripts/bench_recommend_latency.py
  python scripts/bench_recommend_latency.py --n 50 --mc-draws 0
  python scripts/bench_recommend_latency.py --mc-draws 100
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))


def _zandvoort_state():
    from aris.models.features import estimate_fuel_kg
    from aris.state import RaceState

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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n", type=int, default=40, help="timed iterations")
    parser.add_argument("--warmup", type=int, default=3, help="discarded warmups")
    parser.add_argument(
        "--mc-draws",
        type=int,
        default=0,
        help="Monte Carlo draws (0 = production/API default)",
    )
    args = parser.parse_args()

    from aris.recommend import latency_stats, recommend, reset_latency_stats

    state = _zandvoort_state()
    reset_latency_stats()

    for _ in range(args.warmup):
        recommend(state, top_k=3, mc_draws=args.mc_draws)

    reset_latency_stats()
    last_labels: list[str] = []
    for _ in range(args.n):
        result = recommend(state, top_k=3, mc_draws=args.mc_draws)
        last_labels = [r.label for r in result.recommendations]

    stats = latency_stats()
    payload = {
        "fixture": "Zandvoort 2025 VER lap 25",
        "mc_draws": args.mc_draws,
        "warmup": args.warmup,
        "labels": last_labels,
        **stats,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
