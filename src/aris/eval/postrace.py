"""Post-race comparison — user vs ARIS vs actual."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from aris.engine.session import RaceEngineSession
from aris.io import db

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESULTS_DIR = _REPO_ROOT / "results"


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


def _total_race_time(laps: pd.DataFrame) -> float:
    clean = laps.dropna(subset=["lap_time_s"])
    return float(clean["lap_time_s"].sum())


def _actual_pit_laps(laps: pd.DataFrame) -> list[int]:
    pits = laps[laps["pit_in"] == True]  # noqa: E712
    return [int(x) for x in pits["lap_number"].tolist()]


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

    return PostRaceComparison(
        driver_code=session.driver_code,
        user_race_time_s=actual_time,
        aris_race_time_s=actual_time,
        actual_race_time_s=actual_time,
        user_position_est=session.gaps_for_driver().get("position"),
        actual_finish_pos=finish_pos,
        decision_count=len(session.decision_queue.decisions),
        pit_lap_error=pit_error,
        summary=(
            f"{session.driver_code}: {len(session.decision_queue.decisions)} decisions, "
            f"actual race time {actual_time:.1f}s"
        ),
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
