"""Walk-forward strategy backtest over the 2024 held-out calendar.

Drives the live engine (SectorClock + RaceEngineSession + check_triggers +
recommend) unattended. Does not reimplement temporal cutoff: FieldState and
build_race_state already hide future laps/sectors.

Observation mode: ARIS recommendations are logged, then pending is cleared
with choice_id ``observe`` and pits are not committed, so later ticks still
see the real race.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from aris.decisions.persist import JsonlDecisionLog
from aris.engine.clock import SectorClock
from aris.engine.session import RaceEngineSession, SessionPhase
from aris.engine.triggers import check_triggers
from aris.eval.laptime import HELD_OUT_RACES
from aris.eval.postrace import (
    actual_schedule,
    estimate_position,
    schedule_from_plan,
    simulate_schedule,
)
from aris.io import db
from aris.plan.prewrite import generate_strat_plans
from aris.recommend import Recommendation, recommend
from aris.simulate import ActionKind, StrategyAction, simulate
from aris.state import RaceState, track_status_is_sc_vsc
from aris.tracks import load_track_config

REFERENCE_FINISH_POS = 5
PIT_LAP_TOLERANCE = 2
HINDSIGHT_MARGIN_S = 2.0
ROLLING_WINDOW = 5
DRY_COMPOUNDS = frozenset({"SOFT", "MEDIUM", "HARD", "C1", "C2", "C3", "C4", "C5"})
WET_COMPOUNDS = frozenset({"INTERMEDIATE", "WET", "UNKNOWN"})

# 2025 calendar in round order. Not in HELD_OUT_RACES (that's the 2024
# lap-time MAE split vs 2018–2023 train). 2025 is a second held-out year
# for the walk-forward only.
BACKTEST_GPS_2025: list[str] = [
    "Australia",
    "China",
    "Japan",
    "Bahrain",
    "Saudi Arabia",
    "Miami",
    "Emilia Romagna",
    "Monaco",
    "Spain",
    "Canada",
    "Austria",
    "Britain",
    "Belgium",
    "Hungary",
    "Netherlands",
    "Italy",
    "Azerbaijan",
    "Singapore",
    "United States",
    "Mexico City",
    "Sao Paulo",
    "Las Vegas",
    "Qatar",
    "Abu Dhabi",
]

DecisionClass = Literal[
    "match",
    "divergence_aris_hindsight",
    "divergence_team_hindsight",
    "divergence_insufficient_info",
]


@dataclass
class Inflection:
    kind: str  # pit | sc | compound
    lap: int
    compound: str | None
    team_pitted: bool
    notes: str = ""


@dataclass
class DecisionScore:
    gp: str
    year: int
    round_no: int
    driver_code: str
    inflection: Inflection
    aris_label: str
    classification: DecisionClass
    team_sim_s: float | None = None
    aris_sim_s: float | None = None
    stay_out_match: bool = False
    last_year_match: bool | None = None


@dataclass
class OutcomeScore:
    gp: str
    year: int
    round_no: int
    driver_code: str
    actual_finish_pos: int
    aris_finish_pos: int | None
    position_delta: float | None  # aris_pos - actual_pos; negative = ARIS better
    actual_time_s: float
    aris_sim_s: float | None
    team_sim_s: float | None
    aris_plan_pits: list[int] = field(default_factory=list)
    actual_pits: list[int] = field(default_factory=list)


@dataclass
class RaceBacktest:
    gp: str
    year: int
    round_no: int
    session_id: int
    driver_code: str
    ticks: int
    n_propose: int
    outcome: OutcomeScore | None
    decisions: list[DecisionScore]
    error: str | None = None


def rolling_mean(values: list[float], window: int = ROLLING_WINDOW) -> list[float]:
    out: list[float] = []
    for i in range(len(values)):
        chunk = values[max(0, i - window + 1) : i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def rolling_calendar(
    races: list,
    per_race_match: list[float],
    per_race_delta: list[float],
    window: int = ROLLING_WINDOW,
) -> list[dict[str, Any]]:
    """Rolling mean over the last ``window`` calendar races (not skipping holes)."""
    rows: list[dict[str, Any]] = []
    for i, r in enumerate(races):
        lo = max(0, i - window + 1)
        mvals = [x for x in per_race_match[lo : i + 1] if x == x]
        dvals = [x for x in per_race_delta[lo : i + 1] if x == x]
        rows.append(
            {
                "end_round": r.round_no,
                "end_gp": r.gp,
                "n_races_in_window": i - lo + 1,
                "n_match_rates_in_window": len(mvals),
                "rolling_match_rate": (sum(mvals) / len(mvals)) if mvals else None,
                "rolling_position_delta": (sum(dvals) / len(dvals)) if dvals else None,
            }
        )
    return rows


def _norm_compound(raw: object) -> str:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return "UNKNOWN"
    s = str(raw).strip().upper()
    return s if s else "UNKNOWN"


def _is_wet(compound: str) -> bool:
    token = _norm_compound(compound)
    if token in WET_COMPOUNDS:
        return True
    if token in DRY_COMPOUNDS:
        return False
    return "INTER" in token or token == "WET"


def extract_inflections(laps: pd.DataFrame) -> list[Inflection]:
    """Pit-in laps, SC/VSC period starts, and compound changes not tied to a pit."""
    if laps.empty:
        return []
    ordered = laps.sort_values("lap_number").reset_index(drop=True)
    pit_laps: set[int] = set()
    out: list[Inflection] = []
    prev_status_sc = False
    prev_compound: str | None = None
    prev_pit = False

    for _, row in ordered.iterrows():
        lap = int(row["lap_number"])
        compound = _norm_compound(row.get("compound"))
        pit_in = bool(row.get("pit_in"))
        status = None if pd.isna(row.get("track_status")) else str(row.get("track_status"))
        is_sc = track_status_is_sc_vsc(status)

        if pit_in:
            nxt = ordered[ordered["lap_number"] > lap]
            new_c = _norm_compound(nxt.iloc[0].get("compound")) if not nxt.empty else compound
            out.append(
                Inflection(
                    kind="pit",
                    lap=lap,
                    compound=new_c,
                    team_pitted=True,
                    notes="pit_in",
                )
            )
            pit_laps.add(lap)
            if not nxt.empty:
                pit_laps.add(int(nxt.iloc[0]["lap_number"]))

        if is_sc and not prev_status_sc:
            out.append(
                Inflection(
                    kind="sc",
                    lap=lap,
                    compound=compound,
                    team_pitted=pit_in,
                    notes="sc_vsc_start",
                )
            )

        if (
            prev_compound is not None
            and compound != prev_compound
            and not pit_in
            and not prev_pit
            and lap not in pit_laps
        ):
            out.append(
                Inflection(
                    kind="compound",
                    lap=lap,
                    compound=compound,
                    team_pitted=False,
                    notes=f"{prev_compound}->{compound}",
                )
            )

        prev_status_sc = is_sc
        prev_compound = compound
        prev_pit = pit_in

    return out


def rec_is_stay(rec: Recommendation | None) -> bool:
    if rec is None:
        return False
    action = rec.action
    if action.pit_laps:
        return False
    # Line actions are not a stay-out strategy call.
    return action.kind == ActionKind.STAY_OUT


def rec_pit_calls(rec: Recommendation | None, fallback_lap: int) -> list[tuple[int, str]]:
    if rec is None:
        return []
    action = rec.action
    if action.pit_laps and action.pit_compounds:
        return list(zip(action.pit_laps, action.pit_compounds, strict=False))
    if action.kind == ActionKind.PIT_NOW:
        return [(fallback_lap, action.pit_compound or "HARD")]
    if action.kind == ActionKind.PIT_LAP and action.pit_lap is not None:
        return [(int(action.pit_lap), action.pit_compound or "HARD")]
    return []


def matches_team_pit(
    rec: Recommendation | None,
    actual_lap: int,
    actual_compound: str | None,
    *,
    lap_tol: int = PIT_LAP_TOLERANCE,
) -> bool:
    calls = rec_pit_calls(rec, actual_lap)
    if not calls:
        return False
    want = _norm_compound(actual_compound) if actual_compound else None
    for lap, compound in calls:
        if abs(int(lap) - actual_lap) > lap_tol:
            continue
        if want and want in DRY_COMPOUNDS and _norm_compound(compound) != want:
            continue
        return True
    return False


def matches_team_action(rec: Recommendation | None, inflection: Inflection) -> bool:
    if inflection.team_pitted or inflection.kind == "pit":
        return matches_team_pit(rec, inflection.lap, inflection.compound)
    return rec_is_stay(rec)


def team_action_for(inflection: Inflection, state: RaceState) -> StrategyAction:
    if inflection.team_pitted or inflection.kind == "pit":
        compound = inflection.compound or state.pit_compound
        if _is_wet(compound):
            compound = state.pit_compound
        return StrategyAction(kind=ActionKind.PIT_NOW, pit_compound=compound)
    return StrategyAction(kind=ActionKind.STAY_OUT)


def classify_decision(
    rec: Recommendation | None,
    inflection: Inflection,
    state: RaceState,
    *,
    rainfall: bool,
) -> tuple[DecisionClass, float | None, float | None]:
    if rainfall or _is_wet(inflection.compound or "") or _is_wet(state.compound):
        return "divergence_insufficient_info", None, None
    status = str(state.track_status or "")
    if "5" in status:
        return "divergence_insufficient_info", None, None

    if matches_team_action(rec, inflection):
        return "match", None, None

    if rec is None:
        return "divergence_insufficient_info", None, None

    try:
        aris_out = simulate(state, rec.action)
        team_out = simulate(state, team_action_for(inflection, state))
    except Exception:
        return "divergence_insufficient_info", None, None

    aris_s = float(aris_out.total_race_time_s)
    team_s = float(team_out.total_race_time_s)
    if aris_s + HINDSIGHT_MARGIN_S < team_s:
        return "divergence_aris_hindsight", team_s, aris_s
    return "divergence_team_hindsight", team_s, aris_s


def pick_reference_driver(session_id: int) -> pd.Series | None:
    """Classified P5. If missing, nearest classified finish to P5 with laps."""
    results = db.fetch_session_results(session_id)
    drivers = db.fetch_drivers(session_id)
    if results.empty or drivers.empty:
        return None
    classified = results.dropna(subset=["finish_pos"]).copy()
    classified["finish_pos"] = classified["finish_pos"].astype(int)
    hit = classified[classified["finish_pos"] == REFERENCE_FINISH_POS]
    if hit.empty:
        classified["dist"] = (classified["finish_pos"] - REFERENCE_FINISH_POS).abs()
        hit = classified.sort_values(["dist", "finish_pos"]).head(1)
    if hit.empty:
        return None
    code = str(hit.iloc[0]["code"])
    row = drivers[drivers["code"] == code]
    if row.empty:
        return None
    return row.iloc[0]


def field_race_times(session_id: int) -> dict[str, float]:
    drivers = db.fetch_drivers(session_id)
    times: dict[str, float] = {}
    for _, row in drivers.iterrows():
        laps = db.fetch_laps(session_id, int(row["driver_id"]))
        clean = laps.dropna(subset=["lap_time_s"])
        if clean.empty:
            continue
        times[str(row["code"])] = float(clean["lap_time_s"].sum())
    return times


def last_year_pit_laps(year: int, gp: str, driver_code: str) -> list[tuple[int, str]] | None:
    try:
        import fastf1

        cache = Path(__file__).resolve().parents[3] / "fastf1_cache"
        cache.mkdir(parents=True, exist_ok=True)
        fastf1.Cache.enable_cache(str(cache))
        session = fastf1.get_session(year - 1, gp, "R")
        session.load(laps=True, telemetry=False, weather=False, messages=False)
        event_name = str(session.event["EventName"]).lower()
        tokens = [t for t in gp.lower().replace("-", " ").split() if len(t) >= 3]
        if tokens and not any(t in event_name for t in tokens):
            return None
        try:
            laps = session.laps.pick_drivers(driver_code)
        except Exception:
            laps = session.laps[session.laps["Driver"] == driver_code]
        if laps is None or laps.empty:
            return None
        pits: list[tuple[int, str]] = []
        for _, row in laps.iterrows():
            if pd.isna(row.get("PitInTime")):
                continue
            pits.append((int(row["LapNumber"]), _norm_compound(row.get("Compound"))))
        return pits
    except Exception:
        return None


def last_year_matches_pit(
    last_pits: list[tuple[int, str]] | None, actual_lap: int
) -> bool | None:
    if last_pits is None:
        return None
    return any(abs(lap - actual_lap) <= PIT_LAP_TOLERANCE for lap, _ in last_pits)


def resolve_calendar(year: int = 2024) -> list[dict[str, Any]]:
    """Pair the walk-forward GP list with DB race rows in round order."""
    races = db.fetch_races(year)
    if races.empty:
        raise RuntimeError(f"no {year} races in DB")
    if year == 2024:
        held = [gp for y, gp in HELD_OUT_RACES if y == year]
    elif year == 2025:
        held = list(BACKTEST_GPS_2025)
    else:
        raise RuntimeError(f"no walk-forward calendar for {year}")
    if len(races) != len(held):
        raise RuntimeError(
            f"{year} DB races={len(races)} vs calendar={len(held)}"
        )
    out: list[dict[str, Any]] = []
    ordered = races.sort_values("round_no")
    for (_, row), gp in zip(ordered.iterrows(), held, strict=True):
        out.append(
            {
                "year": year,
                "gp": gp,
                "session_id": int(row["session_id"]),
                "round_no": int(row["round_no"]),
                "country": str(row["country"]),
            }
        )
    return out


def _bind_backtest_log(session: RaceEngineSession) -> None:
    log = JsonlDecisionLog.for_session(
        session_id=session.session_id,
        driver_code=session.driver_code,
        year=session.year,
        round_no=session.round_no,
        source="backtest",
    )
    log.meta = {
        "session_id": session.session_id,
        "driver_id": session.driver_id,
        "driver_code": session.driver_code,
        "year": session.year,
        "round_no": session.round_no,
        "country": session.country,
    }
    session.decision_queue.bind_log(log)


def walk_race_triggers(
    session: RaceEngineSession,
    all_laps: pd.DataFrame,
    *,
    mc_draws: int = 0,
) -> tuple[int, dict[int, Recommendation]]:
    """Tick the real clock; propose at every trigger; observe (do not commit)."""
    clock = SectorClock(
        all_laps,
        session_id=session.session_id,
        total_laps=session.total_laps,
    )
    by_lap: dict[int, Recommendation] = {}
    ticks = 0
    n_prop = 0
    max_ticks = 50000
    while ticks < max_ticks:
        event = clock.tick()
        ticks += 1
        session.replay_index = event.index
        session.field_state = event.field
        kind = check_triggers(session, event)
        if kind is not None:
            n_prop += 1
            if n_prop == 1 or n_prop % 10 == 0:
                print(
                    f"    propose #{n_prop} {kind.value} L{event.index.lap_number}",
                    flush=True,
                )
            state = session.build_state(event.index.lap_number)
            turn = session.decision_queue.propose(
                state, kind=kind, use_llm=False, mc_draws=mc_draws
            )
            if turn.recommendation is not None:
                by_lap[event.index.lap_number] = turn.recommendation
            session.decision_queue.resolve(
                "observe",
                kind=kind,
                lap=event.index.lap_number,
            )
        if event.is_race_complete:
            break
    session.phase = SessionPhase.POST_RACE
    return ticks, by_lap


def _recommend_at_lap(
    session: RaceEngineSession,
    lap: int,
    cached: dict[int, Recommendation],
    *,
    mc_draws: int,
) -> Recommendation | None:
    if lap in cached:
        return cached[lap]
    try:
        state = session.build_state(lap)
    except ValueError:
        return None
    result = recommend(state, top_k=3, mc_draws=mc_draws)
    top = result.recommendations[0] if result.recommendations else None
    if top is not None:
        cached[lap] = top
    return top


def _score_outcome(
    session: RaceEngineSession,
    *,
    gp: str,
    year: int,
    round_no: int,
    driver_code: str,
    finish_pos: int,
    focus_laps: pd.DataFrame,
    team_sched,
) -> OutcomeScore:
    actual_time = float(focus_laps.dropna(subset=["lap_time_s"])["lap_time_s"].sum())
    start_state = session.build_state(1)
    if session.active_strat is not None:
        aris_sim = simulate_schedule(start_state, schedule_from_plan(session.active_strat))
        aris_pits = list(session.active_strat.pit_laps)
    else:
        aris_sim = float(
            simulate(start_state, StrategyAction(kind=ActionKind.STAY_OUT)).total_race_time_s
        )
        aris_pits = []
    team_sim = simulate_schedule(start_state, team_sched)
    adjusted = actual_time + (aris_sim - team_sim)
    aris_pos = estimate_position(
        field_race_times(session.session_id), driver_code, adjusted
    )
    pos_delta = (aris_pos - finish_pos) if aris_pos is not None else None
    return OutcomeScore(
        gp=gp,
        year=year,
        round_no=round_no,
        driver_code=driver_code,
        actual_finish_pos=finish_pos,
        aris_finish_pos=aris_pos,
        position_delta=float(pos_delta) if pos_delta is not None else None,
        actual_time_s=actual_time,
        aris_sim_s=float(aris_sim),
        team_sim_s=float(team_sim),
        aris_plan_pits=aris_pits,
        actual_pits=list(team_sched.pit_laps),
    )


def score_race(meta: dict[str, Any], *, mc_draws: int = 0) -> RaceBacktest:
    session_id = int(meta["session_id"])
    gp = str(meta["gp"])
    year = int(meta["year"])
    round_no = int(meta["round_no"])
    country = str(meta["country"])
    drv = pick_reference_driver(session_id)
    if drv is None:
        return RaceBacktest(
            gp=gp, year=year, round_no=round_no, session_id=session_id,
            driver_code="?", ticks=0, n_propose=0, outcome=None, decisions=[],
            error="no reference driver",
        )
    driver_id = int(drv["driver_id"])
    driver_code = str(drv["code"])
    track = load_track_config(country, year=year, round_no=round_no)
    session = RaceEngineSession(
        session_id=session_id,
        driver_id=driver_id,
        driver_code=driver_code,
        team=str(drv.get("team") or "") or None,
        year=year,
        round_no=round_no,
        country=country,
        total_laps=track.total_laps,
        phase=SessionPhase.LIVE,
    )
    _bind_backtest_log(session)

    plans = generate_strat_plans(
        session_id,
        driver_id,
        year=year,
        round_no=round_no,
        country=country,
        driver_code=driver_code,
    )
    if plans.plans:
        recommended = next((p for p in plans.plans if p.recommended), plans.plans[0])
        session.active_strat = recommended

    all_laps = db.fetch_all_laps(session_id)
    ticks, recs_by_lap = walk_race_triggers(session, all_laps, mc_draws=mc_draws)

    focus_laps = db.fetch_laps(session_id, driver_id)
    inflections = extract_inflections(focus_laps)
    weather = db.fetch_session_weather(session_id) or {}
    rainfall = bool(weather.get("rainfall"))
    last_pits = last_year_pit_laps(year, gp, driver_code)

    decisions: list[DecisionScore] = []
    for inf in inflections:
        rec = _recommend_at_lap(session, inf.lap, recs_by_lap, mc_draws=mc_draws)
        try:
            state = session.build_state(inf.lap)
        except ValueError:
            continue
        klass, team_s, aris_s = classify_decision(rec, inf, state, rainfall=rainfall)
        stay_match = (not inf.team_pitted) and inf.kind != "pit"
        ly = last_year_matches_pit(last_pits, inf.lap) if inf.kind == "pit" else None
        decisions.append(
            DecisionScore(
                gp=gp,
                year=year,
                round_no=round_no,
                driver_code=driver_code,
                inflection=inf,
                aris_label=rec.label if rec else "",
                classification=klass,
                team_sim_s=team_s,
                aris_sim_s=aris_s,
                stay_out_match=stay_match,
                last_year_match=ly,
            )
        )

    results = db.fetch_session_results(session_id)
    finish_pos = REFERENCE_FINISH_POS
    if not results.empty:
        row = results[results["code"] == driver_code]
        if not row.empty and pd.notna(row.iloc[0]["finish_pos"]):
            finish_pos = int(row.iloc[0]["finish_pos"])

    team_sched = actual_schedule(focus_laps)
    try:
        outcome = _score_outcome(
            session,
            gp=gp,
            year=year,
            round_no=round_no,
            driver_code=driver_code,
            finish_pos=finish_pos,
            focus_laps=focus_laps,
            team_sched=team_sched,
        )
        error = None
    except Exception as exc:
        actual_time = float(focus_laps.dropna(subset=["lap_time_s"])["lap_time_s"].sum())
        outcome = OutcomeScore(
            gp=gp, year=year, round_no=round_no, driver_code=driver_code,
            actual_finish_pos=finish_pos, aris_finish_pos=None, position_delta=None,
            actual_time_s=actual_time, aris_sim_s=None, team_sim_s=None,
            actual_pits=list(team_sched.pit_laps),
        )
        error = str(exc)

    return RaceBacktest(
        gp=gp,
        year=year,
        round_no=round_no,
        session_id=session_id,
        driver_code=driver_code,
        ticks=ticks,
        n_propose=len(session.decision_queue.decisions),
        outcome=outcome,
        decisions=decisions,
        error=error,
    )


def match_rate(scores: list[DecisionScore]) -> tuple[float | None, int, int]:
    scored = [s for s in scores if s.classification != "divergence_insufficient_info"]
    if not scored:
        return None, 0, 0
    n_match = sum(1 for s in scored if s.classification == "match")
    return n_match / len(scored), n_match, len(scored)


def stay_out_baseline_rate(scores: list[DecisionScore]) -> tuple[float | None, int, int]:
    scored = [s for s in scores if s.classification != "divergence_insufficient_info"]
    if not scored:
        return None, 0, 0
    n = sum(1 for s in scored if s.stay_out_match)
    return n / len(scored), n, len(scored)


def last_year_baseline_rate(scores: list[DecisionScore]) -> tuple[float | None, int, int]:
    pit_scores = [
        s for s in scores
        if s.inflection.kind == "pit"
        and s.last_year_match is not None
        and s.classification != "divergence_insufficient_info"
    ]
    if not pit_scores:
        return None, 0, 0
    n = sum(1 for s in pit_scores if s.last_year_match)
    return n / len(pit_scores), n, len(pit_scores)


def dataclass_to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: dataclass_to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [dataclass_to_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: dataclass_to_jsonable(v) for k, v in obj.items()}
    return obj
