"""Walk-forward backtest over the 2024 held-out calendar (Phase G).

Usage:
  python scripts/backtest.py              # all 24 races, chronological
  python scripts/backtest.py --limit 1    # first race only (debug)

Does not shortcut the official 24-race list. --limit is for local probes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.eval.backtest import (  # noqa: E402
    OutcomeScore,
    dataclass_to_jsonable,
    last_year_baseline_rate,
    match_rate,
    position_delta_split,
    resolve_calendar,
    rolling_calendar,
    score_race,
    stay_out_baseline_rate,
)

_OUT_DIR = _ROOT / "results" / "backtest"


def main() -> int:
    parser = argparse.ArgumentParser(description="ARIS 2024 walk-forward backtest")
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="If >0, stop after this many races (debug only)",
    )
    parser.add_argument(
        "--mc-draws",
        type=int,
        default=0,
        help="MC draws per recommend(); 0 = deterministic simulate ranking",
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Aggregate existing 2024_full.json + 2025_full.json (no new walk)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Directory for per-race JSON, summaries, and --combine inputs",
    )
    args = parser.parse_args()
    out_dir = args.out_dir if args.out_dir is not None else _OUT_DIR

    if args.combine:
        return combine_years(out_dir)

    calendar = resolve_calendar(args.year)
    if args.limit > 0:
        calendar = calendar[: args.limit]
        print(
            f"WARN: --limit {args.limit} — official Phase G run uses the full "
            f"{args.year} held-out list",
            flush=True,
        )

    print(
        f"=== Walk-forward backtest {args.year}: {len(calendar)} races, "
        f"mc_draws={args.mc_draws} ===",
        flush=True,
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    races = []
    t0 = time.perf_counter()
    for i, meta in enumerate(calendar, start=1):
        print(
            f"\n[{i}/{len(calendar)}] {meta['year']} {meta['gp']} "
            f"round {meta['round_no']} session_id={meta['session_id']}",
            flush=True,
        )
        started = time.perf_counter()
        result = score_race(meta, mc_draws=args.mc_draws)
        elapsed = time.perf_counter() - started
        races.append(result)
        n_dec = len(result.decisions)
        rate, n_match, n_scored = match_rate(result.decisions)
        rate_s = f"{rate:.3f}" if rate is not None else "n/a"
        pos = result.outcome.position_delta if result.outcome else None
        print(
            f"  driver={result.driver_code} ticks={result.ticks} "
            f"propose={result.n_propose} inflections={n_dec} "
            f"match={rate_s} ({n_match}/{n_scored}) "
            f"pos_delta={pos} {elapsed:.1f}s"
            + (f" ERROR={result.error}" if result.error else ""),
            flush=True,
        )
        gp_slug = str(meta["gp"]).replace(" ", "_")
        race_path = out_dir / f"{meta['year']}_r{meta['round_no']}_{gp_slug}.json"
        race_path.write_text(
            json.dumps(dataclass_to_jsonable(result), indent=2, default=str),
            encoding="utf-8",
        )

    all_decisions = [d for r in races for d in r.decisions]
    overall_match, n_match, n_scored = match_rate(all_decisions)
    stay_rate, stay_n, stay_d = stay_out_baseline_rate(all_decisions)
    ly_rate, ly_n, ly_d = last_year_baseline_rate(all_decisions)

    per_race_match: list[float] = []
    per_race_delta: list[float] = []
    for r in races:
        mr, _, _n_s = match_rate(r.decisions)
        per_race_match.append(mr if mr is not None else float("nan"))
        if r.outcome and r.outcome.position_delta is not None:
            delta = r.outcome.position_delta
        else:
            delta = float("nan")
        per_race_delta.append(delta)
    rolling_rows = rolling_calendar(races, per_race_match, per_race_delta)

    # Proposed target: beat always-stay-out on the same scored set.
    baselines = [x for x in (stay_rate, ly_rate) if x is not None]
    proposed_target = max(baselines) if baselines else None

    finite_delta = [x for x in per_race_delta if x == x]
    mean_pos_delta = sum(finite_delta) / len(finite_delta) if finite_delta else None
    split = position_delta_split([r.outcome for r in races if r.outcome is not None])

    summary = {
        "year": args.year,
        "n_races": len(races),
        "mc_draws": args.mc_draws,
        "elapsed_s": time.perf_counter() - t0,
        "reference_driver": "classified P5 (nearest classified if P5 missing)",
        "overall_match_rate": overall_match,
        "n_match": n_match,
        "n_scored": n_scored,
        "n_insufficient_info": sum(
            1 for d in all_decisions if d.classification == "divergence_insufficient_info"
        ),
        "n_aris_hindsight": sum(
            1 for d in all_decisions if d.classification == "divergence_aris_hindsight"
        ),
        "n_team_hindsight": sum(
            1 for d in all_decisions if d.classification == "divergence_team_hindsight"
        ),
        "always_stay_out_baseline": stay_rate,
        "always_stay_out_n": stay_n,
        "always_stay_out_d": stay_d,
        "copy_last_year_baseline": ly_rate,
        "copy_last_year_n": ly_n,
        "copy_last_year_d": ly_d,
        "proposed_match_rate_target": proposed_target,
        "target_rule": (
            "strictly greater than max(always-stay-out, copy-last-year) "
            "on the same scored inflection set; insufficient-info excluded"
        ),
        "meets_target": (
            overall_match is not None
            and proposed_target is not None
            and overall_match > proposed_target
        ),
        "mean_position_delta": mean_pos_delta,
        "mean_position_delta_clean": split["clean"]["mean"],
        "mean_position_delta_disrupted": split["disrupted"]["mean"],
        "n_position_delta_clean": split["clean"]["n"],
        "n_position_delta_disrupted": split["disrupted"]["n"],
        "position_delta_excluded_races": split["excluded_races"],
        "position_delta_split_flag": split["flag"],
        "rolling": rolling_rows,
        "races": [
            {
                "gp": r.gp,
                "round_no": r.round_no,
                "driver_code": r.driver_code,
                "ticks": r.ticks,
                "n_propose": r.n_propose,
                "match_rate": match_rate(r.decisions)[0],
                "position_delta": r.outcome.position_delta if r.outcome else None,
                "major_disruption": (
                    r.outcome.major_disruption if r.outcome else None
                ),
                "actual_finish_pos": r.outcome.actual_finish_pos if r.outcome else None,
                "aris_finish_pos": r.outcome.aris_finish_pos if r.outcome else None,
                "error": r.error,
            }
            for r in races
        ],
    }

    summary_path = out_dir / f"{args.year}_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    full_path = out_dir / f"{args.year}_full.json"
    full_path.write_text(
        json.dumps([dataclass_to_jsonable(r) for r in races], indent=2, default=str),
        encoding="utf-8",
    )

    print("\n=== Aggregate ===", flush=True)
    print(
        f"match-rate aimed (beat naive max)={proposed_target} "
        f"actual={overall_match} scored={n_match}/{n_scored}",
        flush=True,
    )
    print(
        f"always-stay-out={stay_rate} ({stay_n}/{stay_d}) "
        f"copy-last-year={ly_rate} ({ly_n}/{ly_d})",
        flush=True,
    )
    print(f"meets_target={summary['meets_target']}", flush=True)
    print(
        f"mean position-delta all (ARIS pos - actual)={summary['mean_position_delta']} "
        f"(n={len(finite_delta)})",
        flush=True,
    )
    print(
        f"mean position-delta clean (not major disruption)="
        f"{summary['mean_position_delta_clean']} "
        f"(n={summary['n_position_delta_clean']})",
        flush=True,
    )
    print(
        f"mean position-delta disrupted (red or SC run>=5)="
        f"{summary['mean_position_delta_disrupted']} "
        f"(n={summary['n_position_delta_disrupted']})",
        flush=True,
    )
    print(
        f"excluded (disrupted) races={summary['position_delta_excluded_races']}",
        flush=True,
    )
    print(f"wrote {summary_path} and {full_path}", flush=True)
    return 0


def _flatten_full(path: Path) -> tuple[list[dict], list[dict]]:
    races = json.loads(path.read_text(encoding="utf-8"))
    decisions = [d for r in races for d in (r.get("decisions") or [])]
    return races, decisions


def _match_from_dicts(decisions: list[dict]) -> tuple[float | None, int, int]:
    scored = [
        d for d in decisions if d.get("classification") != "divergence_insufficient_info"
    ]
    if not scored:
        return None, 0, 0
    n_match = sum(1 for d in scored if d.get("classification") == "match")
    return n_match / len(scored), n_match, len(scored)


def _stay_from_dicts(decisions: list[dict]) -> tuple[float | None, int, int]:
    scored = [
        d for d in decisions if d.get("classification") != "divergence_insufficient_info"
    ]
    if not scored:
        return None, 0, 0
    n = sum(1 for d in scored if d.get("stay_out_match"))
    return n / len(scored), n, len(scored)


def combine_years(out_dir: Path | None = None) -> int:
    """Combine 2024 + 2025 walk artefacts. Same match-rate / pos-delta / rolling."""
    from aris.eval.backtest import (  # local import keeps --help cheap
        DecisionScore,
        Inflection,
        last_year_baseline_rate,
        rolling_calendar,
    )

    if out_dir is None:
        out_dir = _OUT_DIR
    p24 = out_dir / "2024_full.json"
    p25 = out_dir / "2025_full.json"
    if not p24.exists() or not p25.exists():
        print(f"need {p24} and {p25}", flush=True)
        return 1
    r24, d24 = _flatten_full(p24)
    r25, d25 = _flatten_full(p25)
    all_d = d24 + d25
    overall, n_match, n_scored = _match_from_dicts(all_d)
    stay_rate, stay_n, stay_d = _stay_from_dicts(all_d)

    def _year_block(year: int, races: list[dict], decisions: list[dict]) -> dict:
        m, nm, ns = _match_from_dicts(decisions)
        s, sn, sd = _stay_from_dicts(decisions)
        deltas = [
            r["outcome"]["position_delta"]
            for r in races
            if r.get("outcome") and r["outcome"].get("position_delta") is not None
        ]
        return {
            "year": year,
            "n_races": len(races),
            "overall_match_rate": m,
            "n_match": nm,
            "n_scored": ns,
            "always_stay_out_baseline": s,
            "always_stay_out_n": sn,
            "always_stay_out_d": sd,
            "mean_position_delta": (sum(deltas) / len(deltas)) if deltas else None,
            "n_aris_hindsight": sum(
                1 for d in decisions if d.get("classification") == "divergence_aris_hindsight"
            ),
            "n_team_hindsight": sum(
                1 for d in decisions if d.get("classification") == "divergence_team_hindsight"
            ),
            "n_insufficient_info": sum(
                1
                for d in decisions
                if d.get("classification") == "divergence_insufficient_info"
            ),
        }

    # Rebuild DecisionScore list only for copy-last-year + rolling helpers.
    def _as_scores(races: list[dict]) -> tuple[list, list[float], list[float], list]:
        scores: list[DecisionScore] = []
        dummy_races = []
        per_match: list[float] = []
        per_delta: list[float] = []
        for r in races:
            from types import SimpleNamespace

            dummy_races.append(
                SimpleNamespace(round_no=r["round_no"], gp=r["gp"], year=r["year"])
            )
            race_scores: list[DecisionScore] = []
            for d in r.get("decisions") or []:
                inf = d["inflection"]
                ds = DecisionScore(
                    gp=d["gp"],
                    year=int(d["year"]),
                    round_no=int(d["round_no"]),
                    driver_code=d["driver_code"],
                    inflection=Inflection(
                        kind=inf["kind"],
                        lap=int(inf["lap"]),
                        compound=inf.get("compound"),
                        team_pitted=bool(inf.get("team_pitted")),
                        notes=str(inf.get("notes") or ""),
                    ),
                    aris_label=d.get("aris_label") or "",
                    classification=d["classification"],
                    team_sim_s=d.get("team_sim_s"),
                    aris_sim_s=d.get("aris_sim_s"),
                    stay_out_match=bool(d.get("stay_out_match")),
                    last_year_match=d.get("last_year_match"),
                )
                race_scores.append(ds)
                scores.append(ds)
            mr, _, _ = match_rate(race_scores)
            per_match.append(mr if mr is not None else float("nan"))
            od = r.get("outcome") or {}
            pdv = od.get("position_delta")
            per_delta.append(float(pdv) if pdv is not None else float("nan"))
        return scores, per_match, per_delta, dummy_races

    s24, m24, dlt24, dummy24 = _as_scores(r24)
    s25, m25, dlt25, dummy25 = _as_scores(r25)
    all_scores = s24 + s25
    ly_rate, ly_n, ly_d = last_year_baseline_rate(all_scores)
    rolling = rolling_calendar(dummy24 + dummy25, m24 + m25, dlt24 + dlt25)

    y24 = _year_block(2024, r24, d24)
    y25 = _year_block(2025, r25, d25)
    finite = [x for x in (dlt24 + dlt25) if x == x]
    mean_pos = sum(finite) / len(finite) if finite else None
    baselines = [x for x in (stay_rate, ly_rate) if x is not None]
    target = max(baselines) if baselines else None

    def _outcomes(races: list[dict]) -> list[OutcomeScore]:
        rows: list[OutcomeScore] = []
        for r in races:
            od = r.get("outcome") or {}
            if not od:
                continue
            if "major_disruption" not in od:
                continue
            rows.append(
                OutcomeScore(
                    gp=str(od.get("gp") or r["gp"]),
                    year=int(od.get("year") or r["year"]),
                    round_no=int(od.get("round_no") or r["round_no"]),
                    driver_code=str(od.get("driver_code") or r["driver_code"]),
                    actual_finish_pos=int(od.get("actual_finish_pos") or 5),
                    aris_finish_pos=od.get("aris_finish_pos"),
                    position_delta=od.get("position_delta"),
                    actual_time_s=float(od.get("actual_time_s") or 0.0),
                    aris_sim_s=od.get("aris_sim_s"),
                    team_sim_s=od.get("team_sim_s"),
                    major_disruption=bool(od.get("major_disruption")),
                )
            )
        return rows

    tagged = _outcomes(r24 + r25)
    split = position_delta_split(tagged) if tagged else None
    summary = {
        "years": [2024, 2025],
        "n_races": len(r24) + len(r25),
        "overall_match_rate": overall,
        "n_match": n_match,
        "n_scored": n_scored,
        "always_stay_out_baseline": stay_rate,
        "always_stay_out_n": stay_n,
        "always_stay_out_d": stay_d,
        "copy_last_year_baseline": ly_rate,
        "copy_last_year_n": ly_n,
        "copy_last_year_d": ly_d,
        "proposed_match_rate_target": target,
        "target_rule": (
            "strictly greater than always-stay-out on the same scored "
            "inflection set (2024+2025 combined); insufficient-info excluded"
        ),
        "meets_target": (
            overall is not None and target is not None and overall > target
        ),
        "mean_position_delta": mean_pos,
        "mean_position_delta_clean": None if split is None else split["clean"]["mean"],
        "mean_position_delta_disrupted": (
            None if split is None else split["disrupted"]["mean"]
        ),
        "n_position_delta_clean": None if split is None else split["clean"]["n"],
        "n_position_delta_disrupted": None if split is None else split["disrupted"]["n"],
        "position_delta_excluded_races": (
            None if split is None else split["excluded_races"]
        ),
        "position_delta_split_flag": None if split is None else split["flag"],
        "n_aris_hindsight": y24["n_aris_hindsight"] + y25["n_aris_hindsight"],
        "n_team_hindsight": y24["n_team_hindsight"] + y25["n_team_hindsight"],
        "n_insufficient_info": y24["n_insufficient_info"] + y25["n_insufficient_info"],
        "by_year": {"2024": y24, "2025": y25},
        "rolling": rolling,
    }
    out = out_dir / "2024_2025_combined_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    print("\n=== Combined 2024+2025 ===", flush=True)
    print(
        f"match-rate aimed (beat stay-out)={target} actual={overall} "
        f"scored={n_match}/{n_scored}",
        flush=True,
    )
    print(
        f"2024 match={y24['overall_match_rate']} ({y24['n_match']}/{y24['n_scored']}) "
        f"stay-out={y24['always_stay_out_baseline']}",
        flush=True,
    )
    print(
        f"2025 match={y25['overall_match_rate']} ({y25['n_match']}/{y25['n_scored']}) "
        f"stay-out={y25['always_stay_out_baseline']}",
        flush=True,
    )
    print(f"meets_target={summary['meets_target']}", flush=True)
    print(f"mean position-delta all={mean_pos}", flush=True)
    if split is not None:
        print(
            f"mean position-delta clean={split['clean']['mean']} "
            f"(n={split['clean']['n']})",
            flush=True,
        )
        print(
            f"mean position-delta disrupted={split['disrupted']['mean']} "
            f"(n={split['disrupted']['n']})",
            flush=True,
        )
        print(f"excluded (disrupted) races={split['excluded_races']}", flush=True)
    print(f"wrote {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
