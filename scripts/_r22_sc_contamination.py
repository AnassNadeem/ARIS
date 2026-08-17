"""R22.1 / R22.2: SC-contamination of team pit events + position-delta split.

Reuses R21.3's major-disruption flag (red lap or SC run >= 5). Does not
invent a new test. Does not change simulate()/recommend()/tires.

  python scripts/_r22_sc_contamination.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.eval.backtest import (  # noqa: E402
    OutcomeScore,
    is_major_disruption,
    longest_sc_run,
    n_red_laps,
    position_delta_split,
    team_pit_laps_under_sc_vsc,
)
from aris.eval.postrace import actual_schedule  # noqa: E402
from aris.io import db  # noqa: E402
from aris.state import track_status_is_sc_vsc  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402

_R24 = _ROOT / "results" / "r2" / "r24_distribution.json"
_R213 = _ROOT / "results" / "r21" / "r213_offset_breakdown.json"
_OUT = _ROOT / "results" / "r22"


def _stats(vals: list[float]) -> dict[str, float | int]:
    arr = np.array(vals, dtype=float)
    if len(arr) == 0:
        return {"n": 0, "mean": float("nan"), "std": float("nan"), "median": float("nan")}
    return {
        "n": int(len(arr)),
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=0)),
        "median": float(np.median(arr)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def _print_stats(label: str, vals: list[float], aimed: str = "") -> None:
    s = _stats(vals)
    extra = f"  aimed {aimed}" if aimed else ""
    print(
        f"  {label}: n={s['n']} mean={s['mean']:+.3f} std={s['std']:.3f} "
        f"median={s['median']:+.3f} min={s['min']:+.3f} max={s['max']:+.3f}{extra}",
        flush=True,
    )


def _status_on_lap(laps, lap: int) -> str:
    hit = laps[laps["lap_number"].astype(int) == int(lap)]
    if hit.empty:
        return ""
    return str(hit.iloc[0].get("track_status") or "")


def main() -> int:
    _OUT.mkdir(parents=True, exist_ok=True)
    r24 = json.loads(_R24.read_text(encoding="utf-8"))
    r213 = json.loads(_R213.read_text(encoding="utf-8"))
    delta_rows = r24["rows"]
    disrupt_by_key = {
        (int(r["year"]), str(r["gp"]), str(r["driver_code"])): r
        for r in r213["rows"]
    }

    print("=== R22.1 SC-contamination of team pit events (48 lights-out) ===", flush=True)
    print(
        "  aimed: reuse R21.3 major-disruption (red or SC run>=5); "
        "count how many team pit events used in stop-count/pit-loss "
        "occurred under SC/VSC (codes 4/6/7).",
        flush=True,
    )

    enriched: list[dict] = []
    outcomes: list[OutcomeScore] = []
    for r in delta_rows:
        year = int(r["year"])
        gp = str(r["gp"])
        code = str(r["driver_code"])
        key = (year, gp, code)
        prior = disrupt_by_key.get(key, {})
        sid = db.fetch_race_session_id(year, int(r["round_no"]))
        drv = db.fetch_driver_by_code(sid, code) if sid is not None else None
        did = int(drv["driver_id"]) if drv is not None else None
        laps = db.fetch_laps(sid, did) if sid is not None and did is not None else None
        if laps is None or laps.empty:
            print(f"  SKIP {year} {gp} {code}: no laps", flush=True)
            continue
        team = actual_schedule(laps)
        aris_pits = list(r.get("aris_plan_pits") or [])
        team_pits = list(team.pit_laps)
        sc_vsc_pits = team_pit_laps_under_sc_vsc(laps)
        pit_detail = []
        for p in team_pits:
            ts = _status_on_lap(laps, p)
            pit_detail.append(
                {
                    "lap": p,
                    "track_status": ts,
                    "under_sc_vsc": track_status_is_sc_vsc(ts),
                    "under_sc": "4" in ts,
                    "under_vsc": any(c in ts for c in ("6", "7")),
                    "under_red": "5" in ts,
                }
            )
        n_red = n_red_laps(laps)
        sc_run = longest_sc_run(laps)
        major = is_major_disruption(laps)
        prior_major = bool(prior.get("major_disruption")) if prior else None
        extra_stops = len(team_pits) - len(aris_pits)
        extra_stops_ex_sc = (len(team_pits) - len(sc_vsc_pits)) - len(aris_pits)
        races = db.fetch_races(year)
        country = str(races[races["round_no"] == int(r["round_no"])].iloc[0]["country"])
        track = load_track_config(country, year=year, round_no=int(r["round_no"]))
        extra_pit_cost = extra_stops * float(track.pit_loss_s)
        extra_pit_cost_ex_sc = extra_stops_ex_sc * float(track.pit_loss_s)
        row = {
            "year": year,
            "gp": gp,
            "round_no": int(r["round_no"]),
            "driver_code": code,
            "position_delta": r.get("position_delta"),
            "sim_gap_s": r.get("sim_gap_s"),
            "aris_pits": aris_pits,
            "team_pits": team_pits,
            "n_team_pits": len(team_pits),
            "n_aris_pits": len(aris_pits),
            "n_team_pits_sc_vsc": len(sc_vsc_pits),
            "team_pits_sc_vsc": sc_vsc_pits,
            "frac_team_pits_sc_vsc": (
                len(sc_vsc_pits) / len(team_pits) if team_pits else 0.0
            ),
            "extra_team_stops_vs_aris": extra_stops,
            "extra_team_stops_ex_sc_vsc": extra_stops_ex_sc,
            "pit_loss_s": float(track.pit_loss_s),
            "extra_pit_cost_s": extra_pit_cost,
            "extra_pit_cost_ex_sc_vsc_s": extra_pit_cost_ex_sc,
            "n_red": n_red,
            "longest_sc_run": sc_run,
            "major_disruption": major,
            "r213_major_disruption": prior_major,
            "major_flag_match_r213": prior_major is None or prior_major == major,
            "pit_detail": pit_detail,
        }
        enriched.append(row)
        outcomes.append(
            OutcomeScore(
                gp=gp,
                year=year,
                round_no=int(r["round_no"]),
                driver_code=code,
                actual_finish_pos=int(r.get("actual_finish_pos") or 5),
                aris_finish_pos=r.get("aris_finish_pos"),
                position_delta=r.get("position_delta"),
                actual_time_s=float(r.get("actual_time_s") or 0.0),
                aris_sim_s=r.get("aris_sim_s"),
                team_sim_s=r.get("team_sim_s"),
                aris_plan_pits=aris_pits,
                actual_pits=team_pits,
                major_disruption=major,
            )
        )

    n = len(enriched)
    n_any_sc_pit = sum(1 for r in enriched if r["n_team_pits_sc_vsc"] > 0)
    n_major = sum(1 for r in enriched if r["major_disruption"])
    n_major_and_sc_pit = sum(
        1 for r in enriched if r["major_disruption"] and r["n_team_pits_sc_vsc"] > 0
    )
    n_sc_pit_not_major = sum(
        1 for r in enriched if (not r["major_disruption"]) and r["n_team_pits_sc_vsc"] > 0
    )
    n_flag_mismatch = sum(1 for r in enriched if not r["major_flag_match_r213"])
    total_team_pits = sum(r["n_team_pits"] for r in enriched)
    total_sc_vsc_pits = sum(r["n_team_pits_sc_vsc"] for r in enriched)

    print(
        f"  races scored: aimed 48  actual {n}",
        flush=True,
    )
    print(
        f"  team pit events: aimed report  actual {total_team_pits} "
        f"of which under SC/VSC {total_sc_vsc_pits} "
        f"({(total_sc_vsc_pits / total_team_pits) if total_team_pits else 0:.3f})",
        flush=True,
    )
    print(
        f"  races with >=1 SC/VSC team pit: aimed report  actual {n_any_sc_pit}/{n}",
        flush=True,
    )
    print(
        f"  races major-disruption (R21.3): aimed 13  actual {n_major}/{n}",
        flush=True,
    )
    print(
        f"  major AND >=1 SC/VSC team pit: aimed report  actual {n_major_and_sc_pit}",
        flush=True,
    )
    print(
        f"  SC/VSC team pit but NOT major (short SC/VSC): "
        f"aimed report  actual {n_sc_pit_not_major}",
        flush=True,
    )
    print(
        f"  R21.3 flag match: aimed 0 mismatches  actual {n_flag_mismatch}",
        flush=True,
    )

    print("\n  per-race (sorted by n_team_pits_sc_vsc, then extra stops):", flush=True)
    print(
        "  year gp driver delta major scRun red teamPits scVscPits extra extraExSC",
        flush=True,
    )
    for r in sorted(
        enriched,
        key=lambda x: (-x["n_team_pits_sc_vsc"], -x["extra_team_stops_vs_aris"], x["gp"]),
    ):
        print(
            f"  {r['year']} {r['gp']:<18} {r['driver_code']} "
            f"d={r['position_delta']:+.0f} major={int(r['major_disruption'])} "
            f"scRun={r['longest_sc_run']:<2} red={r['n_red']:<2} "
            f"pits={r['n_team_pits']} scvsc={r['n_team_pits_sc_vsc']} "
            f"{r['team_pits_sc_vsc']} extra={r['extra_team_stops_vs_aris']:+d} "
            f"extraEx={r['extra_team_stops_ex_sc_vsc']:+d}",
            flush=True,
        )

    # Degree: among races with any SC/VSC pit, fraction of team pits contaminated
    contaminated = [r for r in enriched if r["n_team_pits_sc_vsc"] > 0]
    fracs = [r["frac_team_pits_sc_vsc"] for r in contaminated]
    print("\n  degree (races with >=1 SC/VSC team pit):", flush=True)
    _print_stats("frac of team pits under SC/VSC", fracs, "report")
    extra_all = [r["extra_team_stops_vs_aris"] for r in enriched]
    extra_ex = [r["extra_team_stops_ex_sc_vsc"] for r in enriched]
    _print_stats("extra team stops vs ARIS (raw)", extra_all, "report")
    _print_stats("extra team stops vs ARIS (ex SC/VSC pits)", extra_ex, "report")

    print("\n=== R22.2 position-delta split (clean vs disrupted) ===", flush=True)
    print(
        "  aimed: both numbers visible; do not silently drop disrupted; "
        "do not force disrupted into the clean headline. "
        "all-sample aimed -1.73 (R.2 / R21).",
        flush=True,
    )
    split = position_delta_split(outcomes)
    for key in ("all", "clean", "disrupted"):
        s = split[key]
        print(
            f"  {key}: n={s['n']} mean={s['mean']:+.3f} "
            f"median={s['median']:+.3f} "
            f"better/same/worse={s['n_better']}/{s['n_same']}/{s['n_worse']}",
            flush=True,
        )
    print("  excluded (disrupted) races:", flush=True)
    for e in split["excluded_races"]:
        print(
            f"    {e['year']} {e['gp']:<18} {e['driver_code']} "
            f"delta={e['position_delta']:+.0f}",
            flush=True,
        )

    print("\n=== R22.2 Austria 2024 VER re-audit ===", flush=True)
    aus = next(
        (r for r in enriched if r["year"] == 2024 and r["gp"] == "Austria" and r["driver_code"] == "VER"),
        None,
    )
    if aus is None:
        print("  MISSING Austria 2024 VER", flush=True)
        austria = {"found": False}
    else:
        in_excluded = any(
            e["year"] == 2024 and e["gp"] == "Austria" and e["driver_code"] == "VER"
            for e in split["excluded_races"]
        )
        print(
            f"  aimed: not SC-driven (R21.5); confirm under R21.3 flag.",
            flush=True,
        )
        print(
            f"  major_disruption aimed False  actual {aus['major_disruption']}",
            flush=True,
        )
        print(
            f"  n_red aimed 0  actual {aus['n_red']}; "
            f"longest_sc_run aimed <5  actual {aus['longest_sc_run']}",
            flush=True,
        )
        print(
            f"  team pits {aus['team_pits']}; SC/VSC pits aimed []  "
            f"actual {aus['team_pits_sc_vsc']}",
            flush=True,
        )
        print(
            f"  position_delta aimed -6  actual {aus['position_delta']:+.0f}",
            flush=True,
        )
        print(
            f"  in clean set (not excluded) aimed True  actual {not in_excluded}",
            flush=True,
        )
        print(
            f"  classification: -6 remains a clean-race result; "
            f"does not move to disrupted under this lens.",
            flush=True,
        )
        austria = {
            "found": True,
            "major_disruption": aus["major_disruption"],
            "n_red": aus["n_red"],
            "longest_sc_run": aus["longest_sc_run"],
            "team_pits": aus["team_pits"],
            "team_pits_sc_vsc": aus["team_pits_sc_vsc"],
            "position_delta": aus["position_delta"],
            "in_excluded_list": in_excluded,
            "still_clean": not in_excluded,
        }

    out = {
        "n": n,
        "n_races_with_sc_vsc_team_pit": n_any_sc_pit,
        "n_major_disruption": n_major,
        "n_major_and_sc_vsc_pit": n_major_and_sc_pit,
        "n_sc_vsc_pit_not_major": n_sc_pit_not_major,
        "n_flag_mismatch_vs_r213": n_flag_mismatch,
        "total_team_pits": total_team_pits,
        "total_team_pits_sc_vsc": total_sc_vsc_pits,
        "frac_team_pits_sc_vsc": (
            total_sc_vsc_pits / total_team_pits if total_team_pits else None
        ),
        "position_delta_split": split,
        "austria_2024_ver": austria,
        "rows": enriched,
    }
    path = _OUT / "r221_sc_contamination.json"
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
