"""Rank 2: 48-race lights-out sequential ablation (start compound / first stop / pit count).

Does not change ``recommend()`` defaults, G1.5, or Zandvoort labels.
Position-delta is not FIA points.

  python scripts/_lights_out_ablation.py
  python scripts/_lights_out_ablation.py --perturb
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

_OUT = _ROOT / "results" / "lights_out" / "ablation.json"


def _score_calendar() -> list[dict]:
    from aris.engine.session import RaceEngineSession, SessionPhase
    from aris.eval.backtest import (
        field_race_times,
        pick_reference_driver,
        resolve_calendar,
        team_pit_laps_under_sc_vsc,
    )
    from aris.eval.lights_out_ablation import ablation_row
    from aris.eval.postrace import actual_schedule, schedule_from_plan
    from aris.io import db
    from aris.plan.prewrite import generate_strat_plans
    from aris.tracks import load_track_config

    rows: list[dict] = []
    for year in (2024, 2025):
        try:
            calendar = resolve_calendar(year)
        except Exception as exc:
            print(f"  SKIP {year}: {exc}", flush=True)
            continue
        for meta in calendar:
            sid = int(meta["session_id"])
            drv = pick_reference_driver(sid)
            if drv is None:
                print(f"  SKIP {year} {meta['gp']}: no P5", flush=True)
                continue
            driver_id = int(drv["driver_id"])
            code = str(drv["code"])
            country = str(meta["country"])
            round_no = int(meta["round_no"])
            track = load_track_config(country, year=year, round_no=round_no)
            session = RaceEngineSession(
                session_id=sid,
                driver_id=driver_id,
                driver_code=code,
                team=str(drv.get("team") or "") or None,
                year=year,
                round_no=round_no,
                country=country,
                total_laps=track.total_laps,
                phase=SessionPhase.POST_RACE,
            )
            plans = generate_strat_plans(
                sid,
                driver_id,
                year=year,
                round_no=round_no,
                country=country,
                driver_code=code,
            )
            if not plans.plans:
                print(f"  SKIP {year} {meta['gp']} {code}: no plans", flush=True)
                continue
            recommended = next((p for p in plans.plans if p.recommended), plans.plans[0])
            focus = db.fetch_laps(sid, driver_id)
            if focus.empty:
                continue
            try:
                start_state = session.build_state(1)
            except ValueError as exc:
                print(f"  SKIP {year} {meta['gp']} {code}: {exc}", flush=True)
                continue
            team = actual_schedule(focus)
            aris = schedule_from_plan(recommended)
            actual_time = float(focus.dropna(subset=["lap_time_s"])["lap_time_s"].sum())
            field = field_race_times(sid)
            row = ablation_row(
                field_times=field,
                driver_code=code,
                actual_time_s=actual_time,
                start_state=start_state,
                aris=aris,
                team=team,
                focus_laps=focus,
                sc_vsc_pit_laps=team_pit_laps_under_sc_vsc(focus),
                year=year,
                gp=str(meta["gp"]),
                round_no=round_no,
            )
            rows.append(row)
            base = row["variants"]["baseline"]["position_delta"]
            first = row["variants"]["first_stop"]["position_delta"]
            print(
                f"  {year} {meta['gp']} {code}: baseline {base:+.2f}  "
                f"first_stop {first:+.2f}  extra_stops {row['extra_stops']}"
                f"/{row['extra_stops_ex_sc_vsc']} ex-SC",
                flush=True,
            )
    return rows


def _perturb_once(fuel_kg: float, out_lap_s: float) -> list[dict]:
    import aris.models.features as features
    import aris.physics.tires as tires

    old_fuel = features._FUEL_START_KG
    old_out = tires.OUT_LAP_PENALTY_S
    features._FUEL_START_KG = float(fuel_kg)
    tires.OUT_LAP_PENALTY_S = float(out_lap_s)
    try:
        return _score_calendar()
    finally:
        features._FUEL_START_KG = old_fuel
        tires.OUT_LAP_PENALTY_S = old_out


def main() -> int:
    parser = argparse.ArgumentParser(description="Lights-out sequential ablation")
    parser.add_argument(
        "--perturb",
        action="store_true",
        help="Also score fuel ±5 kg and out-lap 0/1.5/3 s (no new constant)",
    )
    args = parser.parse_args()

    from aris.eval.lights_out_ablation import summarize_ablation
    from aris.io import db  # noqa: F401  — loads .env via db.py

    if not os.getenv("ARIS_DB_URL"):
        print("SKIP: ARIS_DB_URL unset - no ablation written", flush=True)
        return 0

    print("=== Lights-out ablation (identity-safe position-delta, not FIA points) ===", flush=True)
    rows = _score_calendar()
    if not rows:
        print("SKIP: no scored races", flush=True)
        return 0
    summary = summarize_ablation(rows)
    payload: dict = {"summary": summary, "rows": rows, "not_fia_points": True}

    if args.perturb:
        perturbs = []
        for fuel in (105.0, 110.0, 115.0):
            for out_lap in (0.0, 1.5, 3.0):
                print(
                    f"--- perturb fuel={fuel} out_lap={out_lap} (not a new constant) ---",
                    flush=True,
                )
                prow = _perturb_once(fuel, out_lap)
                psum = summarize_ablation(prow)
                base = (psum.get("variants") or {}).get("baseline", {})
                perturbs.append(
                    {
                        "fuel_start_kg": fuel,
                        "out_lap_s": out_lap,
                        "baseline_mean": (base.get("all") or {}).get("mean"),
                        "n": psum.get("n_races"),
                    }
                )
        payload["perturb"] = {
            "note": "Cheap check only. Do not write 0.03 s/kg or 1.5 s out-lap as sourced.",
            "rows": perturbs,
        }

    _OUT.parent.mkdir(parents=True, exist_ok=True)
    _OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(f"Wrote {_OUT}", flush=True)
    variants = summary.get("variants") or {}
    for name, stats in variants.items():
        all_s = stats.get("all") or {}
        print(
            f"  {name}: n={all_s.get('n')} mean={all_s.get('mean')} "
            f"d-vs-baseline={stats.get('delta_vs_baseline_mean')}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
