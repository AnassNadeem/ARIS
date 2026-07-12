#!/usr/bin/env python3
"""Headless E2E dry run — Bahrain weekend, full sector race loop.

Usage:
    python scripts/dry_run_bahrain_2025.py --code HAM --no-llm
    python scripts/dry_run_bahrain_2025.py --year 2024 --code VER --no-llm
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))

from aris.decisions.queue import DecisionKind  # noqa: E402
from aris.engine.clock import SectorClock  # noqa: E402
from aris.engine.session import RaceEngineSession, SessionPhase  # noqa: E402
from aris.engine.triggers import check_triggers  # noqa: E402
from aris.eval.postrace import compare_post_race, export_postrace  # noqa: E402
from aris.io import db  # noqa: E402
from aris.plan.prewrite import generate_strat_plans  # noqa: E402
from aris.tracks import load_track_config  # noqa: E402


def _resolve_session(year: int, event: str = "Bahrain") -> tuple[int, int, str]:
    races = db.fetch_races(year)
    if races.empty:
        raise RuntimeError(f"No races for {year} — run ingest_weekend.py {year} {event}")
    match = races[races["country"].str.contains("Bahrain", case=False, na=False)]
    if match.empty:
        row = races.iloc[0]
    else:
        row = match.iloc[0]
    session_id = int(row["session_id"])
    round_no = int(row["round_no"])
    country = str(row["country"])
    return session_id, round_no, country


def run_dry(
    *,
    year: int,
    driver_code: str,
    use_llm: bool,
    reject_rate: float,
    max_ticks: int,
) -> RaceEngineSession:
    session_id, round_no, country = _resolve_session(year)
    driver = db.fetch_driver_by_code(session_id, driver_code)
    if driver is None:
        raise RuntimeError(f"Driver {driver_code} not found in session {session_id}")

    driver_id = int(driver["driver_id"])
    track = load_track_config(country)
    all_laps = db.fetch_all_laps(session_id)

    session = RaceEngineSession(
        session_id=session_id,
        driver_id=driver_id,
        driver_code=str(driver["code"]),
        team=str(driver["team"]) if driver.get("team") else None,
        year=year,
        round_no=round_no,
        country=country,
        total_laps=track.total_laps,
        phase=SessionPhase.PRE_RACE,
    )

    plans = generate_strat_plans(
        session_id,
        driver_id,
        year=year,
        round_no=round_no,
        country=country,
        driver_code=driver_code,
    )
    recommended = next((p for p in plans.plans if p.recommended), plans.plans[0])
    session.active_strat = recommended
    session.phase = SessionPhase.LIVE

    clock = SectorClock(all_laps, session_id=session_id, total_laps=track.total_laps)
    clock.set_speed(100.0)
    ticks = 0
    decisions = 0

    while ticks < max_ticks:
        event = clock.tick()
        session.replay_index = event.index
        session.field_state = event.field
        ticks += 1

        kind = check_triggers(session, event)
        if kind:
            turn = session.decision_queue.propose(
                session.build_state(), kind=kind, use_llm=use_llm
            )
            choice = "yes"
            if random.random() < reject_rate:
                choice = "no"
            session.decision_queue.resolve(choice, kind=kind, lap=event.index.lap_number)
            session.record_decision(session.decision_queue.decisions[-1])
            decisions += 1

        if event.is_race_complete:
            break

    session.phase = SessionPhase.POST_RACE
    comparison = compare_post_race(session)
    export_postrace(session, comparison)

    print(f"\n=== Dry run complete ===")
    print(f"Driver: {driver_code} | Year: {year} | Ticks: {ticks}")
    print(f"Decisions: {decisions}")
    print(f"Active strat: {recommended.name}")
    print(comparison.summary)

    if decisions == 0:
        raise RuntimeError("No decisions triggered — check trigger thresholds")

    return session


def main() -> None:
    parser = argparse.ArgumentParser(description="ARIS Bahrain dry run")
    parser.add_argument("--year", type=int, default=2025)
    parser.add_argument("--code", default="HAM", help="Driver code")
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--reject-rate", type=float, default=0.0)
    parser.add_argument("--max-ticks", type=int, default=500)
    args = parser.parse_args()

    try:
        run_dry(
            year=args.year,
            driver_code=args.code.upper(),
            use_llm=not args.no_llm,
            reject_rate=args.reject_rate,
            max_ticks=args.max_ticks,
        )
    except RuntimeError as exc:
        if args.year == 2025:
            print(f"2025 failed ({exc}) — falling back to 2024")
            run_dry(
                year=2024,
                driver_code="VER" if args.code.upper() == "HAM" else args.code.upper(),
                use_llm=not args.no_llm,
                reject_rate=args.reject_rate,
                max_ticks=args.max_ticks,
            )
        else:
            raise


if __name__ == "__main__":
    main()
