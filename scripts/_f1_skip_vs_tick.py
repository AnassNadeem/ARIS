"""F1.1 — compare tick-by-tick vs Skip-to-chequered-flag on 2025 Netherlands.

Mirrors apps/pages/01_Strategy.py LIVE loop vs the skip button. No Streamlit.
Writes a plain-text report to stdout and results/f1_skip_vs_tick.log.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT))

from aris.decisions.queue import DecisionTurn
from aris.engine.clock import SectorClock
from aris.engine.session import RaceEngineSession, SessionPhase
from aris.engine.triggers import check_triggers
from aris.eval.postrace import compare_post_race, export_postrace
from aris.field.state import ReplayIndex
from aris.io import db
from aris.plan.prewrite import generate_strat_plans
from aris.plan.weekend_form import weekend_form, weekend_session_types
from aris.recommend import recommend
from aris.tracks import clear_track_config_cache, load_track_config


def _find_nl(year: int = 2025) -> dict:
    races = db.fetch_races(year)
    nl = races[races["country"].astype(str).str.lower().str.contains("nether")]
    if nl.empty:
        raise RuntimeError(f"Netherlands race not in DB for {year}")
    row = nl.iloc[0]
    return {
        "session_id": int(row["session_id"]),
        "year": year,
        "round_no": int(row["round_no"]),
        "country": str(row["country"]),
    }


def _driver(setup: dict, code: str = "VER") -> dict:
    drivers = db.fetch_drivers(setup["session_id"])
    hit = drivers[drivers["code"] == code]
    drv = hit.iloc[0] if not hit.empty else drivers.iloc[0]
    setup = dict(setup)
    setup["driver_id"] = int(drv["driver_id"])
    setup["driver_code"] = str(drv["code"])
    setup["team"] = str(drv.get("team") or "")
    return setup


def _new_session(setup: dict, total_laps: int, plans) -> RaceEngineSession:
    session = RaceEngineSession(
        session_id=setup["session_id"],
        driver_id=setup["driver_id"],
        driver_code=setup["driver_code"],
        team=setup["team"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        total_laps=total_laps,
        phase=SessionPhase.LIVE,
    )
    if plans.plans:
        session.active_strat = plans.plans[0]
    return session


def _state_snapshot(state) -> dict[str, Any]:
    return {
        "lap_number": state.lap_number,
        "compound": state.compound,
        "tyre_life": state.tyre_life,
        "fuel_kg": round(float(state.fuel_kg), 4) if state.fuel_kg is not None else None,
        "laps_remaining": state.laps_remaining,
        "total_laps": state.total_laps,
        "position": state.position,
        "gap_to_leader_s": state.gap_to_leader_s,
        "gap_ahead_s": state.gap_ahead_s,
        "gap_behind_s": state.gap_behind_s,
        "undercut_threat": state.undercut_threat,
        "pit_compound": state.pit_compound,
        "track_status": state.track_status,
        "recent_sc_pace": state.recent_sc_pace,
        "confidence_caveat": state.confidence_caveat,
        "lag1_pace": state.lag1_pace,
        "lag2_pace": state.lag2_pace,
        "stint_roll3": state.stint_roll3,
    }


def _field_snapshot(field) -> dict[str, Any]:
    if field is None:
        return {"index": None, "n_standings": 0, "top5": []}
    top5 = []
    for row in field.standings[:5]:
        top5.append(
            {
                "pos": row.position,
                "code": getattr(row, "code", None) or getattr(row, "driver_code", None),
                "driver_id": row.driver_id,
                "gap_to_leader_s": row.gap_to_leader_s,
            }
        )
    return {
        "index": (field.index.lap_number, field.index.sector_idx),
        "n_standings": len(field.standings),
        "top5": top5,
    }


def _decision_log(session: RaceEngineSession) -> dict[str, Any]:
    hist = []
    for turn in session.decision_queue.history:
        rec = turn.recommendation
        hist.append(
            {
                "role": turn.role,
                "kind": turn.kind.value if turn.kind else None,
                "text": turn.text,
                "label": rec.label if rec else None,
                "delta": rec.delta_vs_stay_out_s if rec else None,
            }
        )
    resolved = []
    for rec in session.decision_queue.decisions:
        r = rec.recommendation
        resolved.append(
            {
                "kind": rec.kind.value,
                "lap": rec.lap,
                "accepted": rec.accepted,
                "choice_id": rec.choice_id,
                "label": r.label if r else None,
            }
        )
    pending = session.decision_queue.pending
    return {
        "proposed_count": len(session.decision_queue.history),
        "resolved_count": len(session.decision_queue.decisions),
        "pending_kind": pending.kind.value if pending and pending.kind else None,
        "pending_label": (
            pending.recommendation.label if pending and pending.recommendation else None
        ),
        "triggered_laps": sorted(session.triggered_laps, key=str),
        "history": hist,
        "resolved": resolved,
    }


def _weekend_snapshot(year: int, round_no: int) -> dict[str, Any]:
    forms = weekend_form(year, round_no)
    types = weekend_session_types(year, round_no)
    return {
        "n": len(forms),
        "session_types": list(types) if types is not None else None,
        "codes": [f.code for f in forms],
    }


def run_tick_ui_faithful(setup, track, all_laps, plans) -> tuple[RaceEngineSession, dict]:
    """Same loop as 01_Strategy.py LIVE: tick → check_triggers → propose if kind.

    Pending blocks later proposes (engineer has not resolved). That is the
    real Watch-mode path if nobody clicks Yes/No.
    """
    session = _new_session(setup, track.total_laps, plans)
    clock = SectorClock(all_laps, session_id=setup["session_id"], total_laps=track.total_laps)
    ticks = 0
    trigger_attempts: list[dict] = []
    while ticks < 50000:
        event = clock.tick()
        ticks += 1
        session.replay_index = event.index
        session.field_state = event.field
        kind = check_triggers(session, event)
        if kind:
            trigger_attempts.append(
                {
                    "tick": ticks,
                    "lap": event.index.lap_number,
                    "sector": event.index.sector_idx,
                    "kind": kind.value,
                    "proposed": True,
                }
            )
            # Same queue side-effect as propose(): pending blocks later
            # check_triggers. Full recommend() is not run here — one early-lap
            # MC recommend takes minutes and is not required to compare logs.
            turn = DecisionTurn(
                role="aris",
                text="[F1.1] propose() would call recommend() here",
                kind=kind,
            )
            session.decision_queue.pending = turn
            session.decision_queue.history.append(turn)
        if event.is_race_complete:
            session.phase = SessionPhase.POST_RACE
            break
    return session, {"ticks": ticks, "trigger_attempts": trigger_attempts}


def run_tick_harvest(setup, track, all_laps, plans) -> tuple[RaceEngineSession, dict]:
    """Every trigger that would fire if the engineer cleared pending each time.

    Does NOT call propose()/recommend() — records kinds only, so skip's missing
    intermediate history is visible without 287 MC recommend() calls.
    """
    session = _new_session(setup, track.total_laps, plans)
    clock = SectorClock(all_laps, session_id=setup["session_id"], total_laps=track.total_laps)
    ticks = 0
    kinds: list[dict] = []
    while ticks < 50000:
        event = clock.tick()
        ticks += 1
        session.replay_index = event.index
        session.field_state = event.field
        kind = check_triggers(session, event)
        if kind:
            kinds.append(
                {
                    "tick": ticks,
                    "lap": event.index.lap_number,
                    "sector": event.index.sector_idx,
                    "kind": kind.value,
                }
            )
            # Engineer dismissed / resolved — next trigger can fire.
            session.decision_queue.pending = None
        if event.is_race_complete:
            session.phase = SessionPhase.POST_RACE
            break
    return session, {"ticks": ticks, "kinds": kinds}


def run_skip(setup, track, all_laps, plans) -> RaceEngineSession:
    """Exact skip-button body from 01_Strategy.py."""
    session = _new_session(setup, track.total_laps, plans)
    clock = SectorClock(all_laps, session_id=setup["session_id"], total_laps=track.total_laps)
    clock.index = clock.index.__class__(session.total_laps, 3)
    session.replay_index = clock.index
    session.field_state = clock.current_field()
    session.phase = SessionPhase.POST_RACE
    return session


def _eq(a, b, path: str, diffs: list[str]) -> None:
    if a != b:
        diffs.append(f"{path}: tick={a!r}  skip={b!r}")


def main() -> int:
    clear_track_config_cache()
    setup = _driver(_find_nl(2025), "VER")
    track = load_track_config(setup["country"])
    all_laps = db.fetch_all_laps(setup["session_id"])
    plans = generate_strat_plans(
        setup["session_id"],
        setup["driver_id"],
        year=setup["year"],
        round_no=setup["round_no"],
        country=setup["country"],
        driver_code=setup["driver_code"],
    )

    print("=== F1.1 skip-vs-tick 2025 Netherlands ===", flush=True)
    print(
        f"session_id={setup['session_id']} driver={setup['driver_code']} "
        f"total_laps={track.total_laps}",
        flush=True,
    )

    print("\n-- harvest: all trigger kinds along 287 ticks (no propose) --", flush=True)
    harvest_session, harvest_meta = run_tick_harvest(setup, track, all_laps, plans)
    print(f"ticks={harvest_meta['ticks']} trigger_count={len(harvest_meta['kinds'])}", flush=True)
    for row in harvest_meta["kinds"]:
        print(f"  tick {row['tick']:3d}  L{row['lap']} S{row['sector']}  {row['kind']}", flush=True)

    print("\n-- UI-faithful tick (propose; pending blocks later) --", flush=True)
    tick_session, tick_meta = run_tick_ui_faithful(setup, track, all_laps, plans)
    print(
        f"ticks={tick_meta['ticks']} propose_calls={len(tick_meta['trigger_attempts'])}",
        flush=True,
    )
    for row in tick_meta["trigger_attempts"]:
        print(
            f"  proposed tick {row['tick']} L{row['lap']} S{row['sector']} {row['kind']}",
            flush=True,
        )

    print("\n-- skip-to-flag (button body, from lights-out index) --", flush=True)
    skip_session = run_skip(setup, track, all_laps, plans)
    print(
        f"index={skip_session.replay_index} phase={skip_session.phase.value}",
        flush=True,
    )

    tick_state = tick_session.build_state()
    skip_state = skip_session.build_state()
    tick_log = _decision_log(tick_session)
    skip_log = _decision_log(skip_session)
    weekend = _weekend_snapshot(setup["year"], setup["round_no"])

    print("\n-- final RaceState --", flush=True)
    ts, ss = _state_snapshot(tick_state), _state_snapshot(skip_state)
    print(f"tick: {json.dumps(ts, default=str)}", flush=True)
    print(f"skip: {json.dumps(ss, default=str)}", flush=True)

    print("\n-- final field --", flush=True)
    tf, sf = _field_snapshot(tick_session.field_state), _field_snapshot(skip_session.field_state)
    print(f"tick: {json.dumps(tf, default=str)}", flush=True)
    print(f"skip: {json.dumps(sf, default=str)}", flush=True)

    print("\n-- decision logs --", flush=True)
    print(f"tick: {json.dumps(tick_log, default=str, indent=2)}", flush=True)
    print(f"skip: {json.dumps(skip_log, default=str, indent=2)}", flush=True)

    print("\n-- weekend form (path-independent; same call) --", flush=True)
    print(json.dumps(weekend, default=str), flush=True)

    print("\n-- recommend() at final RaceState (mc_draws=15, same as F.8) --", flush=True)
    rec_tick = recommend(tick_state, top_k=3, mc_draws=15)
    rec_skip = recommend(skip_state, top_k=3, mc_draws=15)
    labels_tick = [(r.label, round(r.delta_vs_stay_out_s, 4)) for r in rec_tick.recommendations]
    labels_skip = [(r.label, round(r.delta_vs_stay_out_s, 4)) for r in rec_skip.recommendations]
    print(f"tick recommend: {labels_tick}", flush=True)
    print(f"skip recommend: {labels_skip}", flush=True)

    print("\n-- recommend() at L25 (F.8/E4.1 lock-in lap) --", flush=True)
    rec_tick_25 = recommend(tick_session.build_state(25), top_k=3, mc_draws=15)
    rec_skip_25 = recommend(skip_session.build_state(25), top_k=3, mc_draws=15)
    print(
        "tick L25: "
        + "; ".join(r.label for r in rec_tick_25.recommendations),
        flush=True,
    )
    print(
        "skip L25: "
        + "; ".join(r.label for r in rec_skip_25.recommendations),
        flush=True,
    )

    print("\n-- postrace export --", flush=True)
    cmp_tick = compare_post_race(tick_session)
    cmp_skip = compare_post_race(skip_session)
    # Don't overwrite the F.8 123_VER_postrace.json — write side copies.
    tick_path = _ROOT / "results" / "f1_tick_postrace.json"
    skip_path = _ROOT / "results" / "f1_skip_postrace.json"
    for path, sess, cmp in (
        (tick_path, tick_session, cmp_tick),
        (skip_path, skip_session, cmp_skip),
    ):
        payload = {
            "session_id": sess.session_id,
            "driver_code": sess.driver_code,
            "comparison": cmp.__dict__,
            "decisions": [d.model_dump() for d in sess.decision_queue.decisions],
            "committed_pits": [p.model_dump() for p in sess.committed_pits],
            "active_strat": sess.active_strat.model_dump() if sess.active_strat else None,
            "pending_kind": (
                sess.decision_queue.pending.kind.value
                if sess.decision_queue.pending and sess.decision_queue.pending.kind
                else None
            ),
            "proposed_count": len(sess.decision_queue.history),
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(
        f"tick postrace: decisions={cmp_tick.decision_count} finish={cmp_tick.actual_finish_pos} "
        f"summary={cmp_tick.summary!r} export={tick_path.name}",
        flush=True,
    )
    print(
        f"skip postrace: decisions={cmp_skip.decision_count} finish={cmp_skip.actual_finish_pos} "
        f"summary={cmp_skip.summary!r} export={skip_path.name}",
        flush=True,
    )

    diffs: list[str] = []
    _eq(ts, ss, "RaceState", diffs)
    _eq(tf, sf, "FieldState", diffs)
    _eq(tick_session.replay_index, skip_session.replay_index, "replay_index", diffs)
    _eq(tick_session.phase, skip_session.phase, "phase", diffs)
    _eq(tick_session.committed_pits, skip_session.committed_pits, "committed_pits", diffs)
    _eq(labels_tick, labels_skip, "recommend_final", diffs)
    _eq(
        [r.label for r in rec_tick_25.recommendations],
        [r.label for r in rec_skip_25.recommendations],
        "recommend_L25_labels",
        diffs,
    )
    _eq(cmp_tick.decision_count, cmp_skip.decision_count, "postrace.decision_count", diffs)
    _eq(cmp_tick.actual_finish_pos, cmp_skip.actual_finish_pos, "postrace.finish", diffs)
    _eq(cmp_tick.summary, cmp_skip.summary, "postrace.summary", diffs)
    _eq(tick_log["proposed_count"], skip_log["proposed_count"], "proposed_count", diffs)
    _eq(tick_log["resolved_count"], skip_log["resolved_count"], "resolved_count", diffs)
    _eq(tick_log["pending_kind"], skip_log["pending_kind"], "pending_kind", diffs)
    _eq(tick_log["triggered_laps"], skip_log["triggered_laps"], "triggered_laps", diffs)

    print("\n=== COMPARISON ===", flush=True)
    if diffs:
        print("DIVERGENCES:", flush=True)
        for d in diffs:
            print(f"  - {d}", flush=True)
    else:
        print("No divergences on compared fields.", flush=True)

    print(
        f"\nHarvest trigger kinds skip never saw: {len(harvest_meta['kinds'])} "
        f"(tick UI-faithful proposed {len(tick_meta['trigger_attempts'])} "
        f"because pending blocks later check_triggers).",
        flush=True,
    )
    print("F1.1 DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
