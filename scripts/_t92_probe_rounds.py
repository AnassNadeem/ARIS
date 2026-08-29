"""T9.2 iteration probe: score selected 2025 rounds (not part of the gate suite)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.eval.backtest import (  # noqa: E402
    action_class_breakdown,
    match_rate,
    resolve_calendar,
    score_race,
    stay_out_baseline_rate,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--rounds", type=int, nargs="+", default=[4, 9, 11])
    args = parser.parse_args()
    cal = resolve_calendar(args.year)
    want = set(args.rounds)
    for meta in cal:
        if int(meta["round_no"]) not in want:
            continue
        print(
            f"=== {meta['year']} R{meta['round_no']} {meta['gp']} "
            f"country={meta['country']} ===",
            flush=True,
        )
        result = score_race(meta, mc_draws=0)
        _rate, n_match, n_scored = match_rate(result.decisions)
        _stay_rate, stay_n, stay_d = stay_out_baseline_rate(result.decisions)
        print(
            f"  driver={result.driver_code} match={n_match}/{n_scored} "
            f"stay-out={stay_n}/{stay_d} err={result.error}",
            flush=True,
        )
        for d in result.decisions:
            inf = d.inflection
            if d.classification == "divergence_insufficient_info":
                continue
            print(
                f"  L{inf.lap} team_pit={inf.team_pitted} team={inf.compound} "
                f"state={d.state_compound} age={d.state_tyre_life} "
                f"aris={d.aris_label!r} class={d.classification}",
                flush=True,
            )
        br = action_class_breakdown(result.decisions)
        for key, row in br.items():
            if row["n"]:
                print(f"  {key}: {row['current']}/{row['n']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
