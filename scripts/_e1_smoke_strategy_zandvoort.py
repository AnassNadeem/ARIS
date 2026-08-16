"""Headless end-to-end Strategy pipeline smoke test for Zandvoort (Phase E1.4).

Exercises the same building blocks as apps/pages/01_Strategy.py without Streamlit:
  session setup → strat cards (prewrite) → live clock replay →
  Watch/Ask/What-if equivalents → postrace comparison.
"""
from __future__ import annotations

import sys
import traceback
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.engine.clock import SectorClock
from aris.engine.session import RaceEngineSession, SessionPhase
from aris.engine.triggers import check_triggers
from aris.eval.mc_intervals import mc_delta_interval
from aris.eval.postrace import compare_post_race, export_postrace
from aris.io import db
from aris.montecarlo import run_mc
from aris.plan.prewrite import derive_pit_windows, generate_strat_plans
from aris.plan.weekend_form import weekend_form
from aris.recommend import recommend
from aris.simulate import ActionKind, StrategyAction, simulate
from aris.tracks import clear_track_config_cache, load_track_config


def _find_zandvoort_race(year: int = 2025) -> dict:
    races = db.fetch_races(year)
    if races.empty:
        raise RuntimeError(f"no races in DB for {year}")
    # Netherlands country
    nl = races[races["country"].astype(str).str.lower().str.contains("nether")]
    if nl.empty:
        raise RuntimeError(f"Netherlands race not in DB for {year}: {races.to_dict()}")
    row = nl.iloc[0]
    return {
        "session_id": int(row["session_id"]),
        "year": year,
        "round_no": int(row["round_no"]),
        "country": str(row["country"]),
    }


def main() -> int:
    clear_track_config_cache()
    errors: list[str] = []
    print("=== E1.4 Zandvoort Strategy smoke ===", flush=True)

    # 1) Session setup
    try:
        setup = _find_zandvoort_race(2025)
        print(f"[setup] {setup}", flush=True)
        drivers = db.fetch_drivers(setup["session_id"])
        if drivers.empty:
            raise RuntimeError("no drivers")
        # Prefer a race finisher for the full clock path; DNF path covered by unit test
        # + optional second pass below.
        drv = drivers.iloc[0]
        for code in ("VER", "PIA", "RUS", "NOR", "LEC"):
            hit = drivers[drivers["code"] == code]
            if not hit.empty:
                drv = hit.iloc[0]
                break
        setup["driver_id"] = int(drv["driver_id"])
        setup["driver_code"] = str(drv["code"])
        setup["team"] = str(drv.get("team") or "")
        print(
            f"[setup] driver={setup['driver_code']} team={setup['team']} id={setup['driver_id']}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL setup: {exc}", flush=True)
        traceback.print_exc()
        return 1

    track = load_track_config(
        setup["country"], year=setup["year"], round_no=setup["round_no"]
    )
    print(
        f"[track] total_laps={track.total_laps} pit_loss={track.pit_loss_s} "
        f"slopes={track.compound_slopes}",
        flush=True,
    )
    if track.total_laps != 72:
        errors.append(f"expected 72 laps, got {track.total_laps}")

    # 2) Strat cards / prewrite
    try:
        windows = derive_pit_windows(track.total_laps, track.pit_loss_s)
        print(f"[prewrite] windows A/B/C = {windows}", flush=True)
        for name, laps in windows.items():
            if any(l < 1 or l > track.total_laps for l in laps):
                errors.append(f"window {name} out of range: {laps}")
        # Sensible 72-lap band: early one-stop roughly teens–20s, late ~25–35, two-stop interior
        if not (12 <= windows["A"][0] <= 28):
            errors.append(f"Strat A window looks off for 72 laps: {windows['A']}")
        if not (20 <= windows["B"][0] <= 40):
            errors.append(f"Strat B window looks off for 72 laps: {windows['B']}")

        plans = generate_strat_plans(
            setup["session_id"],
            setup["driver_id"],
            year=setup["year"],
            round_no=setup["round_no"],
            country=setup["country"],
            driver_code=setup["driver_code"],
        )
        print(
            f"[prewrite] plans={len(plans.plans)} "
            + ", ".join(f"{p.id}:{p.pit_laps}" for p in plans.plans),
            flush=True,
        )
        if len(plans.plans) < 3:
            errors.append(f"expected >=3 strat plans, got {len(plans.plans)}")
        for p in plans.plans:
            if p.expected_race_time_s is None or not (p.expected_race_time_s > 0):
                errors.append(f"plan {p.id} missing expected_race_time_s")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL prewrite: {exc}", flush=True)
        traceback.print_exc()
        errors.append(f"prewrite: {exc}")

    # Weekend form (may be empty if FP/Q not ingested — non-fatal warning)
    try:
        forms = weekend_form(setup["year"], setup["round_no"])
        print(f"[weekend_form] n={len(forms)}", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"WARN weekend_form: {exc}", flush=True)

    # 3) Live clock replay
    session = RaceEngineSession(
        session_id=setup["session_id"],
        driver_id=setup["driver_id"],
        driver_code=setup["driver_code"],
        team=setup["team"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        total_laps=track.total_laps,
        phase=SessionPhase.LIVE,
    )
    if plans.plans:
        session.active_strat = plans.plans[0]

    try:
        all_laps = db.fetch_all_laps(setup["session_id"])
        print(f"[clock] all_laps rows={len(all_laps)}", flush=True)
        clock = SectorClock(
            all_laps,
            session_id=setup["session_id"],
            total_laps=track.total_laps,
        )
        clock.set_speed(4.0)
        ticks = 0
        max_ticks = 50000
        while ticks < max_ticks:
            event = clock.tick()
            ticks += 1
            session.replay_index = event.index
            session.field_state = event.field
            check_triggers(session, event)
            if event.is_race_complete:
                break
        print(
            f"[clock] ticks={ticks} final_lap={session.replay_index.lap_number} "
            f"complete={event.is_race_complete}",
            flush=True,
        )
        if not event.is_race_complete:
            errors.append("clock did not reach race complete")
        session.phase = SessionPhase.POST_RACE
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL clock: {exc}", flush=True)
        traceback.print_exc()
        errors.append(f"clock: {exc}")

    # 4) Watch / Ask / What-if at mid-race state
    try:
        mid_lap = min(25, track.total_laps - 5)
        state = session.build_state(mid_lap)
        print(
            f"[live-state] L{state.lap_number} compound={state.compound} "
            f"tyre_life={state.tyre_life}",
            flush=True,
        )
        # What-if
        action = StrategyAction(
            kind=ActionKind.PIT_LAP,
            pit_lap=mid_lap + 5,
            pit_compound="HARD",
        )
        outcome = simulate(state, action)
        mc = run_mc(state, action, n_draws=20)
        lo, hi = mc_delta_interval(mc)
        print(
            f"[what-if] delta={outcome.delta_vs_stay_out_s:+.2f}s "
            f"MC P10/P90={lo:+.2f}/{hi:+.2f}",
            flush=True,
        )
        # Ask / recommend
        rec = recommend(state, top_k=3, mc_draws=15)
        print(
            f"[ask/recommend] n={len(rec.recommendations)} "
            + "; ".join(r.label for r in rec.recommendations[:3]),
            flush=True,
        )
        if not rec.recommendations:
            errors.append("recommend returned empty")
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL what-if/ask: {exc}", flush=True)
        traceback.print_exc()
        errors.append(f"what-if/ask: {exc}")

    # 5) Postrace
    try:
        comparison = compare_post_race(session)
        path = export_postrace(session, comparison)
        print(
            f"[postrace] decisions={comparison.decision_count} "
            f"finish={comparison.actual_finish_pos} "
            f"summary={comparison.summary!r} export={path.name}",
            flush=True,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL postrace: {exc}", flush=True)
        traceback.print_exc()
        errors.append(f"postrace: {exc}")

    if errors:
        print("\nSMOKE FAILURES:", flush=True)
        for e in errors:
            print(f"  - {e}", flush=True)
        return 1
    print("\nSMOKE OK", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
