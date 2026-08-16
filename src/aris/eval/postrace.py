"""Post-race comparison — user vs ARIS vs actual."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from aris.engine.session import PitCommitment, RaceEngineSession
from aris.io import db
from aris.plan.prewrite import StratPlan
from aris.simulate import ActionKind, simulate_full_race
from aris.state import RaceState

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_DIR = _REPO_ROOT / "results"


@dataclass
class PitSchedule:
    pit_laps: list[int]
    pit_compounds: list[str]
    start_compound: str


@dataclass
class PostRaceComparison:
    driver_code: str
    user_race_time_s: float | None
    aris_race_time_s: float | None
    actual_race_time_s: float
    user_position_est: int | None
    actual_finish_pos: int | None
    decision_count: int
    pit_lap_error: float | None
    summary: str
    aris_position_est: int | None = None


def _total_race_time(laps: pd.DataFrame) -> float:
    clean = laps.dropna(subset=["lap_time_s"])
    return float(clean["lap_time_s"].sum())


def _actual_pit_laps(laps: pd.DataFrame) -> list[int]:
    pits = laps[laps["pit_in"] == True]  # noqa: E712
    return [int(x) for x in pits["lap_number"].tolist()]


def _start_compound(laps: pd.DataFrame) -> str:
    if laps.empty:
        return "MEDIUM"
    first = laps.sort_values("lap_number").iloc[0]
    raw = first.get("compound")
    return str(raw) if pd.notna(raw) else "MEDIUM"


def schedule_from_plan(plan: StratPlan) -> PitSchedule:
    return PitSchedule(
        pit_laps=list(plan.pit_laps),
        pit_compounds=list(plan.pit_compounds),
        start_compound=plan.start_compound,
    )


def schedule_from_commitments(
    pits: list[PitCommitment], start_compound: str
) -> PitSchedule | None:
    if not pits:
        return None
    ordered = sorted(pits, key=lambda p: p.lap)
    return PitSchedule(
        pit_laps=[p.lap for p in ordered],
        pit_compounds=[p.compound for p in ordered],
        start_compound=start_compound,
    )


def schedule_from_accepted_decisions(
    session: RaceEngineSession, start_compound: str
) -> PitSchedule | None:
    """Compose a pit schedule from accepted ARIS recommendations."""
    pairs: list[tuple[int, str]] = []
    for record in session.decision_queue.decisions:
        if not record.accepted or record.recommendation is None:
            continue
        action = record.recommendation.action
        edited = record.edited_fields or {}
        if action.pit_laps and action.pit_compounds:
            pairs.extend(zip(action.pit_laps, action.pit_compounds, strict=False))
            continue
        compound = str(
            edited.get("compound") or action.pit_compound or "HARD"
        )
        if action.kind == ActionKind.PIT_NOW:
            lap = int(edited.get("pit_lap", record.lap))
            pairs.append((lap, compound))
        elif action.pit_lap:
            lap = int(edited.get("pit_lap", action.pit_lap))
            pairs.append((lap, compound))
    if not pairs:
        return None
    pairs.sort(key=lambda p: p[0])
    return PitSchedule(
        pit_laps=[p[0] for p in pairs],
        pit_compounds=[p[1] for p in pairs],
        start_compound=start_compound,
    )


def aris_schedule(session: RaceEngineSession, start_compound: str) -> PitSchedule:
    """ARIS strategy: accepted recs, else locked prewrite plan, else stay out."""
    from_decisions = schedule_from_accepted_decisions(session, start_compound)
    if from_decisions is not None:
        return from_decisions
    if session.active_strat is not None:
        return schedule_from_plan(session.active_strat)
    return PitSchedule(pit_laps=[], pit_compounds=[], start_compound=start_compound)


def simulate_schedule(state: RaceState, schedule: PitSchedule) -> float:
    start = state.model_copy(update={"compound": schedule.start_compound})
    return float(
        simulate_full_race(
            start,
            pit_laps=schedule.pit_laps,
            pit_compounds=schedule.pit_compounds,
        )
    )


def actual_schedule(laps: pd.DataFrame) -> PitSchedule:
    start = _start_compound(laps)
    pit_laps: list[int] = []
    compounds: list[str] = []
    ordered = laps.sort_values("lap_number")
    for _, row in ordered.iterrows():
        if not bool(row.get("pit_in")):
            continue
        lap = int(row["lap_number"])
        nxt = ordered[ordered["lap_number"] > lap]
        if nxt.empty:
            compound = str(row.get("compound") or "HARD")
        else:
            compound = str(nxt.iloc[0].get("compound") or "HARD")
        pit_laps.append(lap)
        compounds.append(compound)
    return PitSchedule(pit_laps=pit_laps, pit_compounds=compounds, start_compound=start)


def estimate_position(
    field_times: dict[str, float],
    driver_code: str,
    hypothetical_time_s: float,
) -> int | None:
    """Re-rank `driver_code` after replacing their time. Lower time = better."""
    if not field_times:
        return None
    times = dict(field_times)
    times[driver_code] = hypothetical_time_s
    ranked = sorted(times.items(), key=lambda kv: kv[1])
    for i, (code, _) in enumerate(ranked, start=1):
        if code == driver_code:
            return i
    return None


def bias_cancelled_delta(
    field_times: dict[str, float],
    driver_code: str,
    *,
    actual_time_s: float,
    aris_sim_s: float,
    team_sim_s: float,
) -> tuple[int | None, int | None, float | None]:
    """Identity-safe position-delta on a single time-rank field.

    ``adjusted = actual + (ARIS_sim - team_sim)``. Both ARIS and the
    baseline are ranks of that field, so ARIS_sim == team_sim ⇒ delta 0.
    Do not subtract official classification: DNF/partial sums do not
    share an ordering with FIA finish_pos (R2.3: 46/48 identity misses).
    """
    adjusted = actual_time_s + (aris_sim_s - team_sim_s)
    aris_pos = estimate_position(field_times, driver_code, adjusted)
    actual_rank = estimate_position(field_times, driver_code, actual_time_s)
    if aris_pos is None or actual_rank is None:
        return aris_pos, actual_rank, None
    return aris_pos, actual_rank, float(aris_pos - actual_rank)


def compare_post_race(
    session: RaceEngineSession,
    *,
    actual_laps: pd.DataFrame | None = None,
) -> PostRaceComparison:
    if actual_laps is None:
        actual_laps = db.fetch_laps(session.session_id, session.driver_id)

    actual_time = _total_race_time(actual_laps)
    actual_pits = _actual_pit_laps(actual_laps)
    user_pits = [p.lap for p in session.committed_pits]
    start_compound = _start_compound(actual_laps)

    pit_error = None
    if user_pits and actual_pits:
        pit_error = abs(user_pits[0] - actual_pits[0])

    results = db.fetch_session_results(session.session_id)
    finish_pos = None
    if not results.empty:
        row = results[results["code"] == session.driver_code]
        if not row.empty:
            fp = row.iloc[0]["finish_pos"]
            finish_pos = int(fp) if pd.notna(fp) else None

    aris_time: float | None = None
    user_time: float | None = None
    aris_pos: int | None = None
    try:
        start_state = session.build_state(1)
        aris = aris_schedule(session, start_compound)
        aris_time = simulate_schedule(start_state, aris)
        user_sched = schedule_from_commitments(session.committed_pits, start_compound)
        if user_sched is not None:
            user_time = simulate_schedule(start_state, user_sched)
        team = actual_schedule(actual_laps)
        team_sim = simulate_schedule(start_state, team)
        # Physics bias cancels: apply (ARIS sim − team sim) to the real race time
        # then re-rank against other classified drivers' actual totals.
        field_times: dict[str, float] = {}
        drivers = db.fetch_drivers(session.session_id)
        for _, drow in drivers.iterrows():
            code = str(drow["code"])
            dlaps = db.fetch_laps(session.session_id, int(drow["driver_id"]))
            t = _total_race_time(dlaps)
            if t > 0:
                field_times[code] = t
        if aris_time is not None and team_sim is not None:
            adjusted = actual_time + (aris_time - team_sim)
            aris_pos = estimate_position(field_times, session.driver_code, adjusted)
    except (ValueError, RuntimeError):
        aris_time = None
        user_time = None

    aris_bit = f"ARIS sim {aris_time:.1f}s" if aris_time is not None else "ARIS sim n/a"
    user_bit = f"user sim {user_time:.1f}s" if user_time is not None else "user sim n/a"
    summary = (
        f"{session.driver_code}: {len(session.decision_queue.decisions)} decisions, "
        f"actual race time {actual_time:.1f}s, {aris_bit}, {user_bit}"
    )

    return PostRaceComparison(
        driver_code=session.driver_code,
        user_race_time_s=user_time,
        aris_race_time_s=aris_time,
        actual_race_time_s=actual_time,
        user_position_est=session.gaps_for_driver().get("position"),
        actual_finish_pos=finish_pos,
        decision_count=len(session.decision_queue.decisions),
        pit_lap_error=pit_error,
        summary=summary,
        aris_position_est=aris_pos,
    )


def export_postrace(
    session: RaceEngineSession,
    comparison: PostRaceComparison,
) -> Path:
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = _RESULTS_DIR / f"{session.session_id}_{session.driver_code}_postrace.json"
    payload = {
        "session_id": session.session_id,
        "driver_code": session.driver_code,
        "comparison": comparison.__dict__,
        "decisions": [d.model_dump() for d in session.decision_queue.decisions],
        "committed_pits": [p.model_dump() for p in session.committed_pits],
        "active_strat": session.active_strat.model_dump() if session.active_strat else None,
    }
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def save_feedback_rows(session: RaceEngineSession) -> int:
    saved = 0
    for record in session.decision_queue.decisions:
        db.save_strategy_feedback(
            session.session_id,
            session.driver_id,
            record.lap,
            decision_json=record.model_dump(),
            aris_rec_json=record.recommendation.model_dump() if record.recommendation else {},
            actual_json={},
            delta_s=None,
        )
        saved += 1
    return saved
